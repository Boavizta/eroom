#!/usr/bin/env python3
"""
HAR -> SiteSpec adapter. The ONLY module of the library allowed to read files
(raw HAR, env-data.json).

ZERO e-footprint import here either: this module only reads and deduces, it
builds no e-footprint object (that is `build.py`'s job). It can therefore stay
testable without the library installed, like `spec.py` and `compose.py`.

WHAT THIS MODULE SOLVES
-----------------------
A real site does not always have a single server. `detect_infrastructures()`
groups the hosts seen in the HAR into distinct 1st-party infrastructures
(candidates for a separate e-footprint `Server`, cf. persistent memory
"model distinct infras") and into third-party hosts (network only).

MEASURED PITFALL, DO NOT FORGET: the PAGE NAME (page.title in the HAR) does
not always say who serves it. On the ANTS case, a page titled
"moncompte.ants.gouv.fr/backend/api/..." actually draws ALL its bytes from
predemande-permisdeconduire.ants.gouv.fr (a background API call). Attributing
a page to a server must therefore be done on the host carrying the MOST
BYTES in that specific page, never on the displayed name.
"""

import base64
import html as _html
import json
import re
from urllib.parse import urlparse

from .compose import compose
from .spec import (
    AudienceSpec,
    Evidence,
    ExternalApiSpec,
    JobSpec,
    JourneySpec,
    ServerSpec,
    SiteSpec,
    StepSpec,
    ThirdPartyHost,
    measured,
    measured_label,
    script_default,
    script_default_label,
)
from .user_time import nielsen_raw_seconds, recalibration_factor, step_user_time

# Provider alias: same mapping as PROVIDER_ALIASES in
# run_efootprint.py. e-footprint expects "ovhcloud"; collect_env_data.py (via
# detect_cloud_provider()) detects "ovh". Duplicated here on purpose: the
# two files read provider names at different moments of the pipeline, and
# making from_har.py depend on run_efootprint.py would reverse the import
# direction.
_PROVIDER_ALIASES = {"ovh": "ovhcloud"}

# Default instance template per provider, same values as
# DEFAULT_INSTANCE_BY_PROVIDER in run_efootprint.py (2 vCPU / 4 GB).
# Duplicated for the same reason as _PROVIDER_ALIASES.
_DEFAULT_INSTANCE_BY_PROVIDER = {
    "aws": "t3.medium",
    "azure": "f2s_v2",
    "gcp": "c2d-highcpu-2",
    "ovhcloud": "c3-4",
    "scaleway": "play2-nano",
}

# ---------------------------------------------------------------------------
# Root domain (registrable domain): known two-level suffixes
# ---------------------------------------------------------------------------
# genericity: ok-start - generic public suffixes (no audit case)
# Deliberately short list: covers the TWO-label suffixes encountered in the
# sites audited so far. A missing suffix at worst climbs back to a too-wide
# root domain (e.g. "gouv.fr" instead of "ants.gouv.fr"), which over-groups
# rather than failing to group: a reasonable safety net until a real public
# suffix list (PSL) is used if the need generalizes.
_TWO_LABEL_SUFFIXES = frozenset({
    "gouv.fr", "co.uk", "org.uk", "ac.uk", "gov.uk", "com.br", "co.jp",
    "com.au", "co.nz", "com.mx", "co.in", "com.cn",
})
# genericity: ok-end


def registrable_domain(host):
    """The root domain of a host: the last two labels, or the last three if
    the last two form a known public suffix (e.g. "gouv.fr").

    Purpose: deciding whether two hosts belong to the same organization
    without a per-site whitelist. An IP is not enough (two 1st-party hosts
    can share an IP without being related, cf. ANTS ajcb/kntw; the reverse
    also happens: two organizations can share a host).
    """
    labels = host.lower().split(".")
    if len(labels) <= 2:
        return host.lower()
    last_two = ".".join(labels[-2:])
    if last_two in _TWO_LABEL_SUFFIXES:
        return ".".join(labels[-3:])
    return last_two


def _same_registrable_domain(host, audited_domain):
    return registrable_domain(host) == registrable_domain(audited_domain)


# ---------------------------------------------------------------------------
# Raw HAR reading
# ---------------------------------------------------------------------------

def _load_har(har_path):
    with open(har_path, encoding="utf-8") as f:
        return json.load(f)


def _entries_by_host(har):
    """{host: [entries]}, in order of first appearance."""
    grouped = {}
    for entry in har.get("log", {}).get("entries", []):
        host = urlparse(entry.get("request", {}).get("url", "")).netloc
        if not host:
            continue
        grouped.setdefault(host, []).append(entry)
    return grouped


def _entry_bytes(entry):
    """REAL network bytes (compressed), not the decompressed weight.

    Same convention as `collect_env_data._entry_transfer_bytes()` (Lot 1):
    it is the transferred weight that drives the network energy of the
    e-footprint calculation, not `content.size`. Same fallback chain:
    _transferSize, then bodySize+headersSize, then content.size as a last
    resort.
    """
    resp = entry.get("response", {})
    transfer_size = resp.get("_transferSize")
    if transfer_size is not None and transfer_size >= 0:
        return transfer_size
    body = resp.get("bodySize", -1)
    if body is not None and body >= 0:
        headers = resp.get("headersSize", -1)
        return body + (headers if headers and headers > 0 else 0)
    return resp.get("content", {}).get("size", 0) or 0


def _entry_has_cache_header(entry):
    headers = entry.get("response", {}).get("headers", [])
    names = {h.get("name", "").lower() for h in headers}
    return bool(names & {"x-cache", "cf-cache-status", "age", "via"})


def _entry_ip(entry):
    ip = entry.get("serverIPAddress", "")
    return ip if ip and not ip.startswith(("127.", "::1")) else None


# ---------------------------------------------------------------------------
# Grouping hosts into infrastructures
# ---------------------------------------------------------------------------

def _attaches_to(host, known_host):
    """Does `host` attach to `known_host` (already spotted as infra)?

    Rule: the name of `host` ends with ".{known_host}" (prefix in front,
    separated by a dot). Attaches "ajcb.moncompte.ants.gouv.fr" to
    "moncompte.ants.gouv.fr". Does NOT attach
    "predemande-permisdeconduire.ants.gouv.fr" to
    "permisdeconduire.ants.gouv.fr": the hyphen is not a dot, the required
    prefix cut does not happen at the right place.
    """
    return host != known_host and host.endswith("." + known_host)


def detect_infrastructures(har_path, audited_domain, first_party_extra=()):
    """Groups the HAR hosts into 1st-party infrastructures and third-party
    hosts.

    audited_domain      : domain of the audited site (e.g. "octo.com"), for
                          the default rule "same root domain".
    first_party_extra   : hosts to treat as 1st-party despite a different
                          root domain (e.g. "api.analytics.octo.tools"
                          for octo.com: a service self-hosted by the same
                          company, under a name no algorithm can deduce
                          from the HAR alone — a human judgment, traced
                          here).

    Returns (infrastructures, third_party) :
      infrastructures : list of dicts {key, hosts, ips, request_count,
                        transferred_bytes, cache_header_seen}, sorted by
                        decreasing bytes (the first is the main infra).
                        `key` is the "group leader" host
                        (the first seen in decreasing byte order).
      third_party     : list of dicts {host, request_count,
                        transferred_bytes} for the non-1st-party hosts.
    """
    har = _load_har(har_path)
    by_host = _entries_by_host(har)
    first_party_extra = set(first_party_extra)

    def is_first_party(host):
        return _same_registrable_domain(host, audited_domain) or host in first_party_extra

    host_totals = {
        host: sum(_entry_bytes(e) for e in entries)
        for host, entries in by_host.items()
    }
    first_party_hosts = sorted(
        (h for h in by_host if is_first_party(h)),
        key=lambda h: -host_totals[h],
    )

    groups = []  # list of dicts, mutable during construction
    group_by_host = {}
    for host in first_party_hosts:
        parent = next((g for g in groups if _attaches_to(host, g["key"])), None)
        if parent is None:
            group = {"key": host, "hosts": [host]}
            groups.append(group)
            group_by_host[host] = group
        else:
            parent["hosts"].append(host)
            group_by_host[host] = parent

    infrastructures = []
    for group in groups:
        entries = [e for h in group["hosts"] for e in by_host[h]]
        ips = {ip for e in entries if (ip := _entry_ip(e))}
        infrastructures.append({
            "key": group["key"],
            "hosts": tuple(group["hosts"]),
            "ips": tuple(sorted(ips)),
            "request_count": len(entries),
            "transferred_bytes": sum(_entry_bytes(e) for e in entries),
            "cache_header_seen": any(_entry_has_cache_header(e) for e in entries),
        })
    infrastructures.sort(key=lambda i: -i["transferred_bytes"])

    third_party = []
    for host, entries in by_host.items():
        if is_first_party(host):
            continue
        third_party.append({
            "host": host,
            "request_count": len(entries),
            "transferred_bytes": sum(_entry_bytes(e) for e in entries),
        })
    third_party.sort(key=lambda h: -h["transferred_bytes"])

    return infrastructures, third_party


def infra_for_host(infrastructures, host):
    """The infra (dict) that `host` belongs to, or None."""
    for infra in infrastructures:
        if host in infra["hosts"]:
            return infra
    return None


# ---------------------------------------------------------------------------
# Page content: word count
# ---------------------------------------------------------------------------

_NOISE_TAGS = re.compile(
    r"<(script|style|noscript|template|svg)\b[^>]*>.*?</\1>",
    re.DOTALL | re.IGNORECASE,
)
_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_ANY_TAG = re.compile(r"<[^>]+>")
_HAS_LETTER = re.compile(r"[a-zA-ZÀ-ÿ]")


def _strip_html(text):
    text = _COMMENT.sub(" ", text)
    text = _NOISE_TAGS.sub(" ", text)
    text = _ANY_TAG.sub(" ", text)
    return _html.unescape(text)


def count_words(html_text):
    """Number of tokens containing at least one letter, outside script/style/
    tags/comments. A direct measurement, not an estimate."""
    cleaned = _strip_html(html_text)
    return sum(1 for token in cleaned.split() if _HAS_LETTER.search(token))


def _page_html_body(page_entries):
    """HTML body of the page, decoded if necessary.

    MEASURED PITFALL: a HAR entry can carry `content.encoding == "base64"`
    even for text/html (observed on an octo.com page). Without explicit
    decoding, `content.text` is raw base64, almost devoid of letters: the
    count silently drops to ~0 instead of the real value.
    """
    for entry in page_entries:
        content = entry.get("response", {}).get("content", {})
        if "html" not in content.get("mimeType", ""):
            continue
        text = content.get("text", "")
        if not text:
            continue
        if content.get("encoding") == "base64":
            try:
                text = base64.b64decode(text).decode("utf-8", errors="replace")
            except (ValueError, base64.binascii.Error):
                continue
        return text
    return None


def detect_page_content(har_path):
    """Word count per page, with a TRACED fallback (never silent).

    Returns a list of dicts {page_id, url, word_count, confidence, note},
    in the order of the HAR's pages (preserves the real journey order).
    confidence="high" (direct measurement) if an HTML body was found,
    confidence="low"/explicit note otherwise (client-rendered page, body not
    captured, etc. — the exact cause is not deducible from the HAR alone, so
    it is not asserted).
    """
    har = _load_har(har_path)
    entries_by_page = {}
    for entry in har.get("log", {}).get("entries", []):
        entries_by_page.setdefault(entry.get("pageref", ""), []).append(entry)

    results = []
    for i, page in enumerate(har.get("log", {}).get("pages", [])):
        pid = page.get("id", f"page_{i + 1}")
        url = page.get("title", "")
        page_entries = entries_by_page.get(pid, [])
        body = _page_html_body(page_entries)
        if body is not None:
            results.append({
                "page_id": pid, "url": url,
                "word_count": count_words(body),
                "confidence": "high",
                "note": None,
            })
        else:
            results.append({
                "page_id": pid, "url": url,
                "word_count": None,
                "confidence": "low",
                "note": "no HTML body captured for this page (client-side "
                        "rendering, body not kept at capture time, or "
                        "non-document page): the word count is unavailable, "
                        "not zero.",
            })
    return results


# ---------------------------------------------------------------------------
# Page-carrying server: by real bytes, never by displayed name
# ---------------------------------------------------------------------------

def _page_dominant_infra_key(page_entries, infrastructures, third_party_hosts):
    """The infra (key) carrying the MOST REAL BYTES in this page.

    MEASURED PITFALL (cf. module docstring): the page name is not enough. A
    page can be named after one host while all its bytes come from another.
    Only the direct measurement decides.

    Returns (infra_key, is_first_party). If the dominant host is a third party
    (no 1st-party infra carried the most bytes), returns (None, False): the
    page then has no 1st-party server to be attributed to, which must be
    signaled rather than guessed.
    """
    by_host = {}
    for entry in page_entries:
        host = urlparse(entry.get("request", {}).get("url", "")).netloc
        if host:
            by_host[host] = by_host.get(host, 0) + _entry_bytes(entry)
    if not by_host:
        return None, False

    dominant_host = max(by_host, key=by_host.get)
    infra = infra_for_host(infrastructures, dominant_host)
    if infra is not None:
        return infra["key"], True
    return dominant_host, False


# ---------------------------------------------------------------------------
# Full assembly: env-data.json + HAR -> SiteSpec
# ---------------------------------------------------------------------------

_SRC = "env-data.json + HAR (direct measurement)"


def _normalize_provider(detected):
    if not detected:
        return None
    return _PROVIDER_ALIASES.get(detected, detected)


def _server_spec_from_info(server_info, key):
    """A ServerSpec from an env-data.json["servers"] entry.

    Reuses the same template as run_efootprint.py (base_ram/base_compute/
    storage as script_default, cf. its PROVIDER_ALIASES /
    DEFAULT_INSTANCE_BY_PROVIDER docstring): this is not a modeling
    regression, it is the same default applied to several servers instead of
    one.

    PROVIDER NOT DETECTED (shared host, e.g. "Orange S.A.", not a public
    cloud): fallback to the GENERIC SERVER field set (power/
    carbon_footprint_fabrication/pue), same values as the fallback of
    `run_efootprint.py:build_efootprint_model()` (300 W, 600 kg, PUE 1.2).
    Without this fallback, a server without a provider would fail
    build_system() (neither the cloud set nor the generic set complete).
    """
    provider = _normalize_provider(server_info.get("detected_provider"))
    country = server_info.get("efootprint_country") or "FRANCE"
    carbon_intensity = server_info.get("carbon_intensity_g_kwh")

    fields = dict(
        key=key,
        label=f"Server {server_info['host']}",
        server_type=script_default_label("autoscaling", "default sizing mode"),
        country=measured_label(country, _SRC) if server_info.get("country_code")
                else script_default_label(country, "country unresolved, France default"),
        storage_gb=script_default(50.0, "GB_stored"),
        evidence=Evidence(
            hosts=tuple(server_info.get("hosts") or [server_info["host"]]),
            ips=tuple([server_info["ip"]]) if server_info.get("ip") else (),
            request_count=server_info.get("request_count"),
            transferred_bytes=server_info.get("transferred_bytes"),
            cache_header_seen=bool(server_info.get("cache_header_seen")),
        ),
    )
    if carbon_intensity is not None:
        fields["carbon_intensity"] = measured(carbon_intensity, "g/kWh", _SRC)

    if provider:
        fields["base_ram"] = script_default(1.0, "GB_ram")
        fields["base_compute"] = script_default(0.1, "cpu_core")
        fields["provider"] = measured_label(provider, _SRC)
        instance_type = _DEFAULT_INSTANCE_BY_PROVIDER.get(provider, "t3.medium")
        fields["instance_type"] = script_default_label(
            instance_type, "2 vCPU/4 GB template, small-production assumption")
    else:
        fields["power"] = script_default(300.0, "W")
        fields["carbon_footprint_fabrication"] = script_default(600.0, "kg")
        fields["pue"] = script_default(1.2, "dimensionless")
    return ServerSpec(**fields)


# Default hypothesis when the user does not know the typical length of a
# response (multiple-choice decision of 28/08/2026, cf. track 1 plan):
# ~150 words ("average response", same order of magnitude as the "Average"
# option of the question asked at Step 30), converted to tokens via the
# ~1.3 token/word ratio documented in the same place.
_DEFAULT_OUTPUT_TOKENS = 195.0


def _ai_job_specs_for_step(step_index, page_entries, ai_external_apis, server_key):
    """JobSpec(s) carrying a detected third-party generative AI call on THIS
    page.

    `ai_external_apis` : env-data.json::ai_external_apis block (host ->
    {provider, model_name, output_tokens, resolved}), written by
    collect_env_data.py (detection) and completed by the skill orchestration
    (user answers, cf. collect_env_data.py --set-ai-model). A host not
    "resolved" or without a known model_name (answer "I don't know" to the
    MODEL question) produces NO job: it stays in the current documentary
    display, never an invented value for the model — EcoLogits has no
    reasonable default to offer across very different providers/model sizes.

    `output_tokens` absent (answer "I don't know" to the LENGTH question,
    multiple-choice decision of 28/08/2026): NO exclusion this time — a
    documented default hypothesis ("average response", cf.
    `_DEFAULT_OUTPUT_TOKENS`) is used instead, visible as such in the
    report's assumptions appendix. Difference from the model: an order of
    magnitude of response length is a reasonable default once the model is
    known, unlike guessing WHICH model is called.

    `data_transferred=0` on the returned job: the bytes of this call are
    already counted in the page job's `total_bytes` (which sums ALL the
    page's hosts, third parties included). This job exists ONLY to carry the
    EcoLogits calculation (`external_api`) without counting the network a
    second time.
    `compute_needed`/`ram_needed` deliberately absent (None): this job
    consumes no resource of the 1st-party server it is attached to
    (`server_key`, the same as the page job's — never a fictitious server, cf.
    track 1 plan on the double counting identified in the `ia_streaming.py`
    archetype), only EcoLogits computes the PROVIDER's compute.
    """
    if not ai_external_apis:
        return []
    jobs = []
    for host, info in ai_external_apis.items():
        if not info.get("resolved") or not info.get("model_name"):
            continue
        output_tokens = info.get("output_tokens")
        request_count = sum(
            1 for e in page_entries
            if urlparse(e.get("request", {}).get("url", "")).netloc == host
        )
        if request_count == 0:
            continue
        host_key = re.sub(r"[^a-z0-9]+", "_", host.lower()).strip("_")
        output_tokens_traced = (
            measured(output_tokens, "dimensionless", _SRC)
            if output_tokens is not None
            else script_default(
                _DEFAULT_OUTPUT_TOKENS, "dimensionless",
                comment="No response length provided by the user "
                        "(question asked at Step 30, unanswered): default "
                        "assumption of an \"average\" response (~150 words).")
        )
        jobs.append(JobSpec(
            key=f"job_ia_{step_index}_{host_key}",
            server_key=server_key,
            label=f"AI call ({info.get('rule_name') or host})",
            data_transferred=script_default(
                0.0, "B",
                comment="Bytes already counted in the page job; this job only "
                        "carries the EcoLogits calculation (external_api)."),
            external_api=ExternalApiSpec(
                provider=info["provider"],
                model_name=info["model_name"],
                output_tokens=output_tokens_traced,
                request_count_per_step=float(request_count),
            ),
        ))
    return jobs


def spec_from_env_data(env_data, har_path, audited_domain, *,
                       first_party_extra=(), name=None):
    """Assembles a complete SiteSpec from env-data.json + the raw HAR.

    One step per distinct captured HAR page (deduplicated by URL, keeping the
    heaviest capture in real bytes), attributed to the server that really
    carries the most bytes IN this page (never to the displayed name — cf.
    ANTS page_3 pitfall). Journey in order of first appearance of the pages,
    which reflects the real captured navigation order.

    user_time comes from `user_time.step_user_time()` (Lot 4, Nielsen 2008
    recalibrated) for each step whose word count is known. The recalibration
    factor is computed ONCE for the whole site, from
    `env_data["traffic"]["avg_time_on_page_s"]` (SimilarWeb Engagments, cf.
    similarweb_api.py) compared to the average of the journey steps' raw
    Nielsens (cf. the `user_time.py` docstring on why an average against an
    average). Step without a word count (Lot 3 fallback): explicit script
    default, never guessed by Nielsen.

    Returns (SiteSpec, warnings) where warnings lists the pages whose
    dominant server is a third-party host (page not attributable to a
    1st-party infra): to be reported, never to be hidden.
    """
    servers_info = env_data.get("servers") or []
    if not servers_info:
        raise ValueError(
            "spec_from_env_data(): env-data.json contains no \"servers\" "
            "entry. Run collect_env_data.py (Lot 3) to produce it."
        )

    infrastructures, third_party = detect_infrastructures(
        har_path, audited_domain, first_party_extra=first_party_extra)

    servers = tuple(_server_spec_from_info(info, info["host"]) for info in servers_info)

    har = _load_har(har_path)
    entries_by_page = {}
    for entry in har.get("log", {}).get("entries", []):
        entries_by_page.setdefault(entry.get("pageref", ""), []).append(entry)

    word_counts = {p["page_id"]: p for p in detect_page_content(har_path)}

    # Deduplication by URL: the heaviest page in real bytes represents each
    # distinct URL (several captures of the same URL are reloads, not
    # different journey steps).
    best_by_url = {}
    order = []
    pids_by_url = {}
    for i, page in enumerate(har.get("log", {}).get("pages", [])):
        pid = page.get("id", f"page_{i + 1}")
        url = page.get("title", "")
        page_entries = entries_by_page.get(pid, [])
        total_bytes = sum(_entry_bytes(e) for e in page_entries)
        pids_by_url.setdefault(url, []).append(pid)
        if url not in best_by_url or total_bytes > best_by_url[url][1]:
            if url not in best_by_url:
                order.append(url)
            best_by_url[url] = (pid, total_bytes, page_entries)

    # First pass: keep only the pages attributable to a 1st-party infra (the
    # others become a warning, never a step), and note their word count.
    # Necessary BEFORE building the steps: the Nielsen recalibration factor
    # (below) is computed on the whole retained journey, not step by step.
    kept, warnings = [], []
    for step_index, url in enumerate(order):
        pid, total_bytes, page_entries = best_by_url[url]
        infra_key, is_first_party = _page_dominant_infra_key(
            page_entries, infrastructures, third_party)
        if not is_first_party:
            warnings.append(
                f"page {url!r}: the server carrying the most bytes "
                f"({infra_key!r}) is not a detected 1st-party infra. "
                "Step skipped: no server in the model can carry it."
            )
            continue
        # The word count may have been measured on ANOTHER repetition of this
        # URL than the one retained for the weight (e.g. a reload served from
        # the HTTP cache carries the HTML body, while the one carrying the
        # most real bytes does not). Both measurements come from the same
        # HAR; keeping only the weight's pid would lose an available count
        # and wrongly fall back to the script default below.
        word_count = next(
            (wc for other_pid in pids_by_url[url]
             if (wc := word_counts.get(other_pid, {}).get("word_count")) is not None),
            None,
        )
        kept.append((step_index, url, infra_key, total_bytes, word_count))

    avg_time_on_page_s = (env_data.get("traffic") or {}).get("avg_time_on_page_s")
    nielsen_raws = [nielsen_raw_seconds(wc) for _, _, _, _, wc in kept if wc is not None]
    factor = recalibration_factor(avg_time_on_page_s, nielsen_raws)

    ai_external_apis = env_data.get("ai_external_apis") or {}

    jobs, steps = [], []
    for step_index, url, infra_key, total_bytes, word_count in kept:
        job_key = f"job_{step_index}"
        step_key = f"step_{step_index}"
        jobs.append(JobSpec(
            key=job_key,
            server_key=infra_key,
            label=f"Loading {url}",
            data_transferred=measured(total_bytes, "B", _SRC),
            compute_needed=script_default(0.05, "cpu_core"),
            ram_needed=script_default(50.0, "MB_ram"),
            data_stored=script_default(0.0, "kB_stored"),
        ))
        step_jobs = {job_key: 1}

        # Detected third-party generative AI call(s) on this page (track 1,
        # cf. plan): never an extra server/job that would double-count the
        # network weight, cf. _ai_job_specs_for_step() docstring.
        page_entries = best_by_url[url][2]
        for ai_job in _ai_job_specs_for_step(step_index, page_entries, ai_external_apis, infra_key):
            jobs.append(ai_job)
            step_jobs[ai_job.key] = 1

        user_time = step_user_time(word_count, factor) if word_count is not None else None
        step_fields = dict(
            key=step_key,
            label=url,
            user_time=user_time or script_default(
                1.0, "min",
                "no word count for this page (Lot 3 fallback): "
                "Nielsen not applicable, script default until a content "
                "measurement exists."
            ),
            jobs=step_jobs,
            url=url,
        )
        if word_count is not None:
            step_fields["words"] = measured(float(word_count), "dimensionless", _SRC)
        steps.append(StepSpec(**step_fields))

    journey_key = "journey"
    journey = JourneySpec(
        key=journey_key, label="Captured journey",
        steps=tuple(s.key for s in steps),
    )

    third_party_specs = tuple(
        ThirdPartyHost(
            host=h["host"],
            request_count=h["request_count"],
            transferred_bytes=h["transferred_bytes"],
        )
        for h in third_party
    )

    audience = _audience_spec_from_env_data(env_data, journey_key)

    base = SiteSpec(
        name=name or audited_domain,
        servers=servers,
        jobs=tuple(jobs),
        steps=tuple(steps),
        journeys=(journey,),
    )
    spec = compose(base, audience=audience)
    return spec, warnings


def _audience_spec_from_env_data(env_data, journey_key):
    """AudienceSpec from the device_mix/network_mix/traffic/server blocks of
    env-data.json. Reuses the same keys as run_efootprint.py:resolve_visits
    and build_efootprint_model, generalized to N servers."""
    device = env_data.get("device_mix") or {}
    network = env_data.get("network_mix") or {}
    traffic = env_data.get("traffic") or {}
    server = env_data.get("server") or {}

    visits = traffic.get("visits_per_year")
    country = server.get("efootprint_country") or "FRANCE"

    fields = dict(
        key="audience",
        label="Annual visitors",
        country=measured_label(country, _SRC),
        journey_key=journey_key,
    )
    if visits is not None:
        fields["visits_per_year"] = measured(float(visits), "dimensionless", _SRC)
    if device.get("phone_fraction") is not None and device.get("desktop_fraction") is not None:
        fields["phone_fraction"] = measured(device["phone_fraction"], "dimensionless", _SRC)
        fields["desktop_fraction"] = measured(device["desktop_fraction"], "dimensionless", _SRC)
    if network.get("wifi_fraction") is not None and network.get("mobile_fraction") is not None:
        fields["wifi_fraction"] = measured(network["wifi_fraction"], "dimensionless", _SRC)
        fields["mobile_fraction"] = measured(network["mobile_fraction"], "dimensionless", _SRC)
    return AudienceSpec(**fields)
