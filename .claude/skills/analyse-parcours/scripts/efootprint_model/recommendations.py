#!/usr/bin/env python3
"""
Simulation of the cumulative effect of retained recommendations on a
`SiteSpec`.

WHAT THIS MODULE DOES, AND DOES NOT DO
--------------------------------------
It computes, for each retained recommendation (dead JS, dead CSS, duplicate
resources, Brotli not enabled), how many `data_transferred` bytes would be
removed from a `JobSpec` if it were applied - then it applies this cumulative
sum, tier by tier, to produce a NEW `SiteSpec`. It does NOT recalculate the
resulting e-footprint `System` (no kg CO2e here): that is the calling code's
job, via `build_system()` on the transformed `SiteSpec`.

ZERO e-footprint import here, like `from_har.py` and `compose.py`: this module
only builds `spec.py` dataclasses. `archetypes/dynamic_db.py` follows the same
rule (`from ..spec import ...` without ever touching the e-footprint library
itself); this module imports it as `from .spec` since it lives at the same
level as `spec.py`, not in a subfolder.

WHY AN INTERMEDIATE `Reduction`
--------------------------------
Each calculation function (`dead_code_reductions`, `duplicate_reductions`,
`brotli_reductions`) produces a list of `Reduction` rather than modifying the
`SiteSpec` directly. Two reasons: `apply_recommendations()` must be able to
cumulate SEVERAL recommendations on the same job before removing its
`data_transferred` once (removing recommendation by recommendation would make
the result depend on the application order); and the calling code needs the
flat list to expose each `Traced` in a report appendix, recommendation by
recommendation.

EVERYTHING COMPUTED HERE IS "ESTIMATED", NEVER "MEASURED"
---------------------------------------------------------
A byte reduction is always an INFERENCE from a collected datum (a dead-code
percentage measured by Coverage, a request occurrence counted in the HAR, a
real but partial Brotli recompression): never a pure external hypothesis.
Hence the exclusive use of `estimated()` (cf. `spec.py`), never `assumed()`,
in this module.
"""

import base64
import json
from dataclasses import dataclass, replace
from typing import Dict, List, Optional

from .spec import JobSpec, SiteSpec, Traced, estimated

# Literal prefix set by `from_har.py::spec_from_env_data()` on the label of
# each "page" Job (`label=f"Loading {url}"`). Generative AI call
# Jobs (`_ai_job_specs_for_step()`) carry another label
# ("AI call (...)") and are therefore never picked up by `_job_url()`: none
# of this module's recommendations concern them, they carry no HTML/JS/CSS
# page weight.
_LOADING_PREFIX = "Loading "

# The three cumulative tiers accepted by `apply_recommendations()`.
_TIER_SETS = {
    "prio1": frozenset({"prio1"}),
    "prio1_2": frozenset({"prio1", "prio2"}),
    "prio1_2_3": frozenset({"prio1", "prio2", "prio3"}),
}


@dataclass
class Reduction:
    """A byte reduction computed for ONE Job, by ONE recommendation.

    `traced` carries the full provenance (value, source, confidence, comment
    of the limits): this is what the caller will expose in an appendix. No
    deduplicated field here: several `Reduction`s can target the same
    `job_key` (a dead-JS recommendation and a duplicates recommendation on
    the same Job, for example); the cumulation is `apply_recommendations()`'s
    work.
    """

    job_key: str
    recommendation: str  # "js_dead" / "css_dead" / "duplicates" / "brotli"
    tier: str            # "prio1" / "prio2" / "prio3"
    bytes_removed: float
    traced: Traced
    page_url: Optional[str] = None
    bytes_removed_decompressed: float = 0.0
    requests_removed: int = 0


# ---------------------------------------------------------------------------
# Shared helpers: Job label decoding, real network bytes of an entry
# ---------------------------------------------------------------------------

def _job_url(job: JobSpec) -> Optional[str]:
    """Page URL carried by this Job, or None if it is not a "page" Job
    (e.g. a generative AI call Job, cf. `_LOADING_PREFIX`)."""
    if not job.label.startswith(_LOADING_PREFIX):
        return None
    return job.label[len(_LOADING_PREFIX):]


def _url_to_job_key(site_spec: SiteSpec) -> Dict[str, str]:
    """Index page URL -> key of the Job carrying it, from the labels already
    set by `spec_from_env_data()`. Does not depend on any recalculation of
    `job_key = f"job_{step_index}"`: we start from the already-built
    `SiteSpec`, as requested (the step_index index is not reproduced here)."""
    mapping: Dict[str, str] = {}
    for job in site_spec.jobs:
        url = _job_url(job)
        if url is not None:
            mapping[url] = job.key
    return mapping


def _job_key_to_url(site_spec: SiteSpec) -> Dict[str, str]:
    """Inverse of `_url_to_job_key`: Job key -> page URL it carries.

    Injective by construction (`_job_url()` keeps only one "page" Job per
    URL): useful to rebuild `page_url` on a `Reduction` built from a
    `job_key` (duplicates, Brotli) rather than from a direct URL.
    """
    return {job_key: url for url, job_key in _url_to_job_key(site_spec).items()}


def _entry_transfer_bytes(entry: dict) -> float:
    """REAL network bytes (compressed) of a HAR entry.

    Deliberate copy of `collect_env_data.py::_entry_transfer_bytes()`
    (and of its equivalent `from_har.py::_entry_bytes()`): reproducing these
    few lines avoids a circular dependency towards `collect_env_data.py`
    (which itself imports higher-level things in the pipeline).
    Same fallback chain: _transferSize (direct measurement), then
    bodySize+headersSize, then content.size (decompressed, last resort).
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


def _pageref_to_url(har: dict) -> Dict[str, str]:
    """Index pageref (HAR page id) -> page URL (HAR title), to resolve which
    page an entry belongs to (via `entry["pageref"]`)."""
    return {
        page["id"]: page.get("title", "")
        for page in har.get("log", {}).get("pages", [])
        if "id" in page
    }


def _load_har(har_path) -> dict:
    with open(har_path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# 1. Dead JS / CSS code
# ---------------------------------------------------------------------------

_DEAD_CODE_COMMENT = (
    "Approximation: the dead-code percentage is measured on the "
    "DECOMPRESSED weight (Coverage), applied as-is to the TRANSFERRED/compressed "
    "weight of the page - ratio assumed comparable, not directly measured on "
    "the network."
)


def _best_env_page_by_url(env_data: dict) -> Dict[str, dict]:
    """The `env_data["pages"]` page heaviest in transferred bytes, per URL.

    `env_data["pages"]` (collect_env_data.py::extract_har_data()) contains ONE
    entry per HAR page (per pageref), NOT deduplicated by URL: several
    reloads of the same URL appear there. `spec_from_env_data()` retains for
    each URL the heaviest repetition in transferred bytes as the canonical
    page (the one carrying the Job's `data_transferred`). Reproducing this
    same choice here is necessary: without it, a Job could be matched to an
    almost-empty reload (e.g. a 0-byte repetition) instead of the actually
    counted capture, and produce a JS/CSS breakdown incoherent with the Job's
    weight.
    """
    best: Dict[str, dict] = {}
    for page in env_data.get("pages") or []:
        url = page.get("url", "")
        transfer = page.get("size_transfer_bytes", 0) or 0
        current = best.get(url)
        if current is None or transfer > (current.get("size_transfer_bytes", 0) or 0):
            best[url] = page
    return best


def _page_weight_by_type_transfer_bytes(page: dict) -> dict:
    """Transferred bytes by resource type for an `env_data` page.

    Expected field at the top level: `weight_by_type_transfer_bytes`. In
    `env_data["pages"]` as currently written by
    `collect_env_data.py::extract_har_data()`, this detail actually lives
    under `page["breakdown"]["by_type_transfer_bytes"]` (the name
    `weight_by_type_transfer_bytes` only appears, itself, in the aggregate
    `env_data["job"]["efootprint"]`, for the single heaviest page of the
    site). So we try the top-level name first, with a fallback to
    `breakdown.by_type_transfer_bytes` - which covers the current schema
    without changing anything if a future format exposes the first name
    directly.
    """
    direct = page.get("weight_by_type_transfer_bytes")
    if direct is not None:
        return direct
    return (page.get("breakdown") or {}).get("by_type_transfer_bytes", {}) or {}


def _page_weight_by_type_bytes(page: dict) -> dict:
    """DECOMPRESSED bytes by resource type for an `env_data` page.

    Same fallback as `_page_weight_by_type_transfer_bytes`: top level
    (`weight_by_type_bytes`), otherwise `breakdown.by_type_bytes`
    (`collect_env_data.py::_page_breakdown()`, lines 601/622). Unlike the
    transferred weight, this calculation is DIRECT (no transposition):
    Coverage already measures dead code on the decompressed weight.
    """
    direct = page.get("weight_by_type_bytes")
    if direct is not None:
        return direct
    return (page.get("breakdown") or {}).get("by_type_bytes", {}) or {}


def _entry_decompressed_bytes(entry: dict) -> float:
    """DECOMPRESSED bytes of a HAR entry (`content.size`, never transposed)."""
    return entry.get("response", {}).get("content", {}).get("size", 0) or 0


def dead_code_reductions(site_spec: SiteSpec, env_data: dict,
                          coverage_pages: List[dict]) -> List[Reduction]:
    """`data_transferred` reduction linked to dead JS and CSS, per page.

    Thresholds taken as-is from `generate_report_html.py::_section_recommandations()`:
      - dead JS  : > 70 % -> tier "prio1" ; between 50 % (excluded) and
        70 % (included) -> "prio2" ; <= 50 % -> no reduction.
      - dead CSS : > 80 % -> tier "prio2" (never a prio1 tier for CSS, that
        is the report's exact rule) ; <= 80 % -> no reduction.

    A Job without a matching `env_data` page or without a matching
    `coverage_pages` page (same exact URL) is silently skipped: not all
    captured pages necessarily have a Coverage measurement.
    """
    best_env_page = _best_env_page_by_url(env_data)
    coverage_by_url: Dict[str, dict] = {}
    for cov_page in coverage_pages or []:
        url = cov_page.get("url", "")
        if url and url not in coverage_by_url:
            coverage_by_url[url] = cov_page

    reductions: List[Reduction] = []
    for job in site_spec.jobs:
        url = _job_url(job)
        if url is None:
            continue
        env_page = best_env_page.get(url)
        cov_page = coverage_by_url.get(url)
        if env_page is None or cov_page is None:
            continue

        weight_by_type = _page_weight_by_type_transfer_bytes(env_page)
        js_bytes = weight_by_type.get("js", 0) or 0
        css_bytes = weight_by_type.get("css", 0) or 0

        # DECOMPRESSED weight: same canonical `env_page` (chosen on the
        # transferred criterion by `_best_env_page_by_url()`), read a second
        # time under its decompressed angle - a single canonical repetition
        # for both weights, not a separate selection.
        weight_by_type_decompressed = _page_weight_by_type_bytes(env_page)
        js_bytes_decompressed = weight_by_type_decompressed.get("js", 0) or 0
        css_bytes_decompressed = weight_by_type_decompressed.get("css", 0) or 0

        js_pct = cov_page.get("js_unused_pct", 0.0) or 0.0
        css_pct = cov_page.get("css_unused_pct", 0.0) or 0.0

        js_tier = None
        if js_pct > 70:
            js_tier = "prio1"
        elif js_pct > 50:
            js_tier = "prio2"
        if js_tier is not None:
            removed = js_bytes * (js_pct / 100.0)
            if removed > 0:
                reductions.append(Reduction(
                    job_key=job.key,
                    recommendation="js_dead",
                    tier=js_tier,
                    bytes_removed=removed,
                    traced=estimated(
                        removed, "B",
                        "dead JS code (Chrome DevTools Coverage)",
                        comment=_DEAD_CODE_COMMENT,
                    ),
                    page_url=url,
                    # DIRECT calculation (no transposition): Coverage already
                    # measures dead code on the decompressed weight.
                    bytes_removed_decompressed=js_bytes_decompressed * (js_pct / 100.0),
                ))

        if css_pct > 80:
            removed = css_bytes * (css_pct / 100.0)
            if removed > 0:
                reductions.append(Reduction(
                    job_key=job.key,
                    recommendation="css_dead",
                    tier="prio2",
                    bytes_removed=removed,
                    traced=estimated(
                        removed, "B",
                        "dead CSS code (Chrome DevTools Coverage)",
                        comment=_DEAD_CODE_COMMENT,
                    ),
                    page_url=url,
                    bytes_removed_decompressed=css_bytes_decompressed * (css_pct / 100.0),
                ))

    return reductions


# ---------------------------------------------------------------------------
# 2. Duplicate resources
# ---------------------------------------------------------------------------

def duplicate_reductions(site_spec: SiteSpec, har_path) -> List[Reduction]:
    """`data_transferred` reduction linked to resources loaded twice.

    Tier "prio2" unconditional as soon as at least one duplicate is found
    (exact rule of `_section_recommandations()`). NEW calculation: neither
    `analyze_har.py::compute_duplicate_urls()` (gives neither size nor page)
    nor any other existing code is reused.

    For each HAR request URL, the FIRST occurrence encountered (entry order)
    is judged necessary. Each SUBSEQUENT occurrence is a duplicate, whose
    transferred bytes are attributed to the Job of the page where it
    occurred - if this page matches no Job of the model (non-canonical page
    or outside the 1st-party scope), its bytes are ignored: this calculation
    is deliberately a FLOOR, not an exhaustive total.

    `bytes_removed` (TRANSFERRED bytes) counts ALL 2nd+ occurrences, including
    HTTP 304 revalidations (real network cost, but minimal: headers only).
    `bytes_removed_decompressed`, on the other hand, EXCLUDES the 304s: their
    body is never re-transferred nor re-decoded (the browser reuses the
    cached content), so their decompressed weight already counts in the
    EcoIndex weight of the page whether the duplicate is removed or not -
    only a real full re-download (200) frees this weight.
    """
    har = _load_har(har_path)
    log = har.get("log", {})
    pageref_to_url = _pageref_to_url(har)
    url_to_job = _url_to_job_key(site_spec)
    job_key_to_url = _job_key_to_url(site_spec)

    totals: Dict[str, float] = {}
    decompressed_totals: Dict[str, float] = {}
    counts: Dict[str, int] = {}
    seen_urls = set()
    for entry in log.get("entries", []):
        req_url = entry.get("request", {}).get("url", "")
        if req_url not in seen_urls:
            seen_urls.add(req_url)
            continue

        pageref = entry.get("pageref", "")
        page_url = pageref_to_url.get(pageref)
        job_key = url_to_job.get(page_url) if page_url is not None else None
        if job_key is None:
            continue

        totals[job_key] = totals.get(job_key, 0.0) + _entry_transfer_bytes(entry)
        # A 304 revalidation never re-decodes the resource body: its
        # DECOMPRESSED weight already counts in the page's EcoIndex weight
        # (the browser reuses the already-cached content) - removing it does
        # not really remove it. Only a real full re-download (200) frees this
        # weight. The TRANSFERRED bytes (already minimal for a 304) and the
        # request count, though, stay unchanged: the revalidation request
        # itself would indeed disappear with a longer cache (Cache-Control
        # max-age), and its real network cost is already correctly counted
        # above.
        if (entry.get("response", {}) or {}).get("status") != 304:
            decompressed_totals[job_key] = (
                decompressed_totals.get(job_key, 0.0) + _entry_decompressed_bytes(entry)
            )
        counts[job_key] = counts.get(job_key, 0) + 1

    reductions: List[Reduction] = []
    for job_key, total in totals.items():
        if total <= 0:
            continue
        reductions.append(Reduction(
            job_key=job_key,
            recommendation="duplicates",
            tier="prio2",
            bytes_removed=total,
            traced=estimated(
                total, "B",
                "HAR duplicate calculation (new, no existing code reused)",
                comment=(
                    "Bytes of the 2nd+ occurrences of the same URL in the HAR, "
                    "attributed to the page where they occurred; occurrences on "
                    "a page not retained as canonical (1st-party fallback or "
                    "HAR dedup) are ignored - this figure is a floor, not an "
                    "exhaustive total of duplicates."
                ),
            ),
            page_url=job_key_to_url.get(job_key),
            bytes_removed_decompressed=decompressed_totals.get(job_key, 0.0),
            # The only one of the 3 reduction functions where a whole request
            # disappears (dead JS/CSS and Brotli never remove a request, only
            # the size of an already-counted request).
            requests_removed=counts.get(job_key, 0),
        ))
    return reductions


# ---------------------------------------------------------------------------
# 3. Brotli not enabled
# ---------------------------------------------------------------------------

def brotli_reductions(site_spec: SiteSpec, env_data: dict, har_path,
                       quality: int = 11) -> List[Reduction]:
    """`data_transferred` reduction linked to the absence of Brotli
    compression.

    Tier "prio3" unconditional (always triggered in
    `_section_recommandations()`). It is a REAL measurement, but partial:
    only the HAR entries whose response body was captured can really be
    recompressed; the rest is EXTRAPOLATED from the saving ratio observed on
    the measurable sample of the same page. No extrapolation is produced for a
    page without any measurable entry (no invented default ratio).

    `env_data` is currently not used by this calculation: each entry's
    current weight and its recompressibility come entirely from the HAR
    (necessary to access the captured response body, absent from
    env-data.json). The parameter is kept for a homogeneous signature with the
    two other reduction functions and a possible future use.
    """
    try:
        import brotli
    except ImportError as exc:
        raise ImportError(
            "brotli_reductions() requires the Python package 'brotli' "
            "(pip install brotli), not found in the current environment."
        ) from exc

    har = _load_har(har_path)
    log = har.get("log", {})
    pageref_to_url = _pageref_to_url(har)
    url_to_job = _url_to_job_key(site_spec)
    job_key_to_url = _job_key_to_url(site_spec)

    measured_bytes: Dict[str, float] = {}   # current bytes, measured entries
    saved_bytes: Dict[str, float] = {}      # saved bytes, measured entries
    unsampled_bytes: Dict[str, float] = {}  # current bytes, entries outside the sample

    for entry in log.get("entries", []):
        resp = entry.get("response", {}) or {}
        content = resp.get("content", {}) or {}
        mime = (content.get("mimeType", "") or "").lower()
        if "javascript" not in mime and "css" not in mime:
            continue

        headers = resp.get("headers", []) or []
        encoding_header = next(
            (h.get("value", "") for h in headers
             if (h.get("name", "") or "").lower() == "content-encoding"),
            "",
        )
        if (encoding_header or "").strip().lower() == "br":
            continue

        pageref = entry.get("pageref", "")
        page_url = pageref_to_url.get(pageref)
        job_key = url_to_job.get(page_url) if page_url is not None else None
        if job_key is None:
            continue

        current_bytes = _entry_transfer_bytes(entry)
        text = content.get("text")
        if text is None:
            unsampled_bytes[job_key] = unsampled_bytes.get(job_key, 0.0) + current_bytes
            continue

        if content.get("encoding") == "base64":
            body_bytes = base64.b64decode(text)
        else:
            body_bytes = text.encode("utf-8")

        compressed = brotli.compress(body_bytes, quality=quality)
        saved = max(0.0, current_bytes - len(compressed))

        measured_bytes[job_key] = measured_bytes.get(job_key, 0.0) + current_bytes
        saved_bytes[job_key] = saved_bytes.get(job_key, 0.0) + saved

    reductions: List[Reduction] = []
    for job_key, measured_total in measured_bytes.items():
        if measured_total <= 0:
            continue
        saved = saved_bytes.get(job_key, 0.0)
        unsampled = unsampled_bytes.get(job_key, 0.0)
        ratio = saved / measured_total
        extrapolated = unsampled * ratio
        total = saved + extrapolated
        if total <= 0:
            continue

        if unsampled > 0:
            comment = (
                f"Really measured on {measured_total:.0f} bytes of non-Brotli JS/CSS whose "
                f"body was captured in the HAR (observed ratio {ratio:.1%}); "
                f"extrapolated to the remaining {unsampled:.0f} bytes whose body "
                "was not captured - NOT measured on this part, it is an "
                "extrapolation of the observed ratio, not an independent calculation."
            )
        else:
            comment = (
                f"Really measured on {measured_total:.0f} bytes of non-Brotli JS/CSS whose "
                f"body was captured in the HAR (observed ratio {ratio:.1%}); "
                "no extrapolation: all the non-Brotli JS/CSS resources of this "
                "page had a captured body."
            )

        reductions.append(Reduction(
            job_key=job_key,
            recommendation="brotli",
            tier="prio3",
            bytes_removed=total,
            traced=estimated(
                total, "B",
                "actual Brotli recompression (brotli library, quality=11) on the "
                "captured sample, extrapolated to the rest",
                comment=comment,
            ),
            page_url=job_key_to_url.get(job_key),
            # EXACT zero, not an approximation: Brotli never changes
            # `content.size` (decompressed weight) nor the request count.
            bytes_removed_decompressed=0.0,
            requests_removed=0,
        ))
    return reductions


# ---------------------------------------------------------------------------
# 4. Cumulative application to a tier
# ---------------------------------------------------------------------------

def apply_recommendations(site_spec: SiteSpec, reductions: List[Reduction],
                          tier: str) -> SiteSpec:
    """Returns a NEW `SiteSpec` where each affected Job's `data_transferred`
    is reduced by the cumulative sum of the `Reduction`s whose tier belongs to
    the tier set designated by `tier` ("prio1" -> {prio1} ; "prio1_2" ->
    {prio1, prio2} ; "prio1_2_3" -> {prio1, prio2, prio3}).

    ASSUMED SIMPLIFICATION: reductions from different recommendations are not
    deduplicated against each other (a duplicated file can also contain dead
    code counted separately): the cumulative sum may slightly overestimate the
    real gain.

    A Job without `data_transferred` is skipped (nothing to reduce). Jobs
    without a calculated reduction for this tier stay unchanged.
    """
    tier_set = _TIER_SETS.get(tier)
    if tier_set is None:
        raise ValueError(
            f"unknown tier: {tier!r}. Expected one of "
            f"{sorted(_TIER_SETS)}."
        )

    totals: Dict[str, float] = {}
    for reduction in reductions:
        if reduction.tier in tier_set:
            totals[reduction.job_key] = (
                totals.get(reduction.job_key, 0.0) + reduction.bytes_removed
            )

    new_jobs = []
    for job in site_spec.jobs:
        total_reduction = totals.get(job.key)
        if not total_reduction or job.data_transferred is None:
            new_jobs.append(job)
            continue

        original_bytes = job.data_transferred.value
        new_bytes = max(0.0, original_bytes - total_reduction)
        new_traced = estimated(
            new_bytes, job.data_transferred.unit,
            f"tier {tier}: applied recommendations",
            comment=(
                f"Original transferred weight {original_bytes:.0f} B reduced by "
                f"{original_bytes - new_bytes:.0f} B through the cumulative "
                "application of the recommendations retained for this tier."
            ),
        )
        new_jobs.append(replace(job, data_transferred=new_traced))

    return replace(site_spec, jobs=tuple(new_jobs))
