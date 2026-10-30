#!/usr/bin/env python3
"""
Phase 3 - CO2e estimation of a website via e-footprint (Boavizta).

IMPORTANT: ALL displayed values are HYPOTHETICAL ESTIMATES.
They are computed from automatically collected data (HAR, CrUX,
ipinfo) and many default assumptions. These results are NOT a real
measurement of the website's environmental impact.

Usage:
    python3 run_efootprint.py <source_dir>
    python3 run_efootprint.py <source_dir> --visits 500000      # annual traffic
    python3 run_efootprint.py <source_dir> --instance t3.large  # instance (provider-specific
                                                                # name)
    python3 run_efootprint.py <source_dir> --refresh-data       # re-collect env-data.json

Reads env-data.json in source_dir (produced by collect_env_data.py).
Writes efootprint-boavizta-model.json in source_dir (re-runnability) and
efootprint-python-summary.json (consumed by generate_report_html.py and
check_efootprint_contract.py).

SINCE LOT 5: this script delegates all modeling to `efootprint_model`
(spec_from_env_data -> build_system -> ranges), instead of hand-building a model
single-page/single-server by hand. The HAR is therefore required in addition to
env-data.json (spec_from_env_data() needs it to detect
infrastructures and split the journey into steps).
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))

from efootprint_model import SpecError, arbitrations_for, calculation_reserves  # noqa: E402
from efootprint_model.from_har import spec_from_env_data  # noqa: E402
from collect_env_data import find_har  # noqa: E402
from efootprint_model.build import (  # noqa: E402
    build_system, consistency_report, energy_kg, fabrication_kg, step_impact_shares, total_kg)
from efootprint_model.compose import (  # noqa: E402
    collect_sources, primary_server, servers_note)
from efootprint_model.ranges import footprint_ranges_kg  # noqa: E402
from efootprint_model.recommendations import (  # noqa: E402
    apply_recommendations, brotli_reductions, dead_code_reductions, duplicate_reductions)
from efootprint_model.sizing_report import servers_sizing  # noqa: E402
from efootprint_model.to_plantuml import site_to_plantuml, _sanitize_alias  # noqa: E402
from efootprint_model import topology_overview  # noqa: E402
from efootprint_model.user_time import (  # noqa: E402
    is_within_nielsen_domain, nielsen_raw_seconds, recalibration_factor,
    NIELSEN_BASE_SECONDS, NIELSEN_SECONDS_PER_100_WORDS)
import coverage_metrics  # noqa: E402

# Sibling module (same directory): technology (stack) detection by home-grown
# rules on the HAR, reused for the pre-calculation overview (Step 25).
# Guarded import (the rest works if the module is absent), same pattern
# as collect_env_data.py.
try:
    import detect_tech
except ImportError:
    detect_tech = None

RAW_DATA_DIR = "raw-data-potentially-sensitive"


# ---------------------------------------------------------------------------
# Loading data
# ---------------------------------------------------------------------------

def load_env_data(source_dir):
    path = source_dir / "env-data.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def ensure_env_data(source_dir, refresh=False):
    """Runs collect_env_data.py if env-data.json is missing or --refresh-data."""
    collect_script = SCRIPTS_DIR / "collect_env_data.py"
    cmd = [sys.executable, str(collect_script), str(source_dir)]
    if refresh:
        cmd.append("--refresh")

    env_data_path = source_dir / "env-data.json"
    if not env_data_path.exists() or refresh:
        print("[collect] Launching collect_env_data.py...")
        result = subprocess.run(cmd)
        if result.returncode != 0:
            print("[collect] Collection failed, stopping.")
            sys.exit(1)


def infer_audited_domain(env_data, source_dir):
    """Audited domain: pages[0].url of env-data.json, else the directory name.

    Same priority order as `similarweb_api.infer_domain()`, without depending
    on that module (no network call needed here, just a domain name).
    """
    from urllib.parse import urlparse
    pages = env_data.get("pages") or []
    if pages:
        host = urlparse(pages[0].get("url", "")).netloc
        if host:
            return host.removeprefix("www.")
    return source_dir.name


def build_topology_overview(source_dir):
    """Step 25 (efootprint skill): builds the overview (text +
    PlantUML) BEFORE any CO2e calculation. Computes nothing (no build_system(),
    no kg total): only reading/presentation.

    Deliberately the same chain as the start of main() (load_env_data ->
    find_har -> infer_audited_domain -> spec_from_env_data), so it never
    diverges from what Step 40 will really see. No dependency on the
    Step 30 parameters (visits/instance): the spec always has a resolved default
    (100k/year) as early as Step 20 (resolve_traffic() in collect_env_data.py).

    Returns (spec, overview_text, plantuml_text, warnings). Raises RuntimeError
    (actionable message, never a raw traceback) if the preconditions are sont
    not met: HAR missing, or env-data.json with no server detected.
    """
    env_data = load_env_data(source_dir)
    if not env_data:
        raise RuntimeError(
            f"env-data.json not found in {source_dir}: run Step 20 "
            "(collect_env_data.py) before asking for the overview.")

    har_path = find_har(source_dir)
    if not har_path:
        raise RuntimeError(
            f"No .har found in {source_dir} (nor in {RAW_DATA_DIR}/). "
            "The overview needs the HAR to detect the topology "
            "(servers, suspected DB/streaming/AI).")

    audited_domain = infer_audited_domain(env_data, source_dir)

    try:
        spec, warnings = spec_from_env_data(env_data, str(har_path), audited_domain)
    except (SpecError, ValueError) as exc:
        # NEW ValueError: spec_from_env_data() raises this type (not SpecError)
        # when env_data["servers"] is empty (from_har.py) — identified trap,
        # `except SpecError` alone is not enough.
        raise RuntimeError(
            f"Cannot build the topology: {exc}. Re-run "
            "Step 20 (collect_env_data.py) if env-data.json is incomplete.")

    tech_result = detect_tech.detect_from_har(har_path) if detect_tech else None
    spec = topology_overview.annotate_third_party_hosts(spec, tech_result)

    text = topology_overview.overview_text(spec, tech_result)
    # The audience country mix (SimilarWeb) lives in env-data.json, never in
    # the SiteSpec (AudienceSpec.country_mix exists but is populated by no
    # adapter): read here to display it in the diagram's assumptions note.
    audience_mix = (env_data.get("audience") or {}).get("mix")
    puml = site_to_plantuml(spec, title=audited_domain, audience_mix=audience_mix)

    return spec, text, puml, warnings


DEFAULT_VISITS_PER_YEAR = 100_000

# Provider name as detected by collect_env_data.py -> name expected by
# e-footprint. Without this table, a well-detected provider crashes the
# calculation: the script entered the Boavizta branch with "ovh", which
# e-footprint rejects (it expects "ovhcloud"), and the "generic server" fallback
# never triggered. Case seen on a site hosted at OVH.
PROVIDER_ALIASES = {"ovh": "ovhcloud"}


def normalize_provider(detected):
    """e-footprint name of the detected provider, or None if not cloud-modelable.

    Only returns a name if e-footprint REALLY knows it: the list is read from
    the library, not copied, so it cannot silently go stale.
    The caller falls back to a generic server when the answer is None.
    """
    if not detected:
        return None
    name = PROVIDER_ALIASES.get(detected, detected)
    try:
        from efootprint.builders.hardware.boavizta_cloud_server import (
            all_boavizta_cloud_providers)
    except ImportError:
        return None
    return name if name in {p.value for p in all_boavizta_cloud_providers} else None


def resolve_visits_override(cli_visits, spec):
    """--visits (CLI, client analytics) takes precedence over the traffic already
    resolved by spec_from_env_data() (SimilarWeb 'traffic' block, or nothing).

    Returns an AudienceSpec, possibly replaced if --visits is provided.
    Unlike the old script, there is no 100,000/year default here anymore:
    AudienceSpec.visits_per_year is not a critical field (cf. spec.py), the
    lib already says so at construction time if needed (build.py:241).
    """
    from dataclasses import replace
    from efootprint_model.spec import measured
    audience = spec.audience
    if cli_visits is None or audience is None:
        return spec
    new_visits = measured(float(cli_visits), "dimensionless", "manual entry (--visits)",
                          comment="Traffic entered on the command line (client analytics or "
                                  "explicit assumption), takes precedence over the 'traffic' block.")
    return replace(spec, audience=replace(audience, visits_per_year=new_visits))


def resolve_instance_override(cli_instance, cli_instance_source, cli_instance_source_url, spec):
    """--instance can target ONLY ONE server: each BoaviztaCloudServer carries
    its own instance_type (confirmed by the e-footprint doc, no notion of a
    "site instance"). Chosen convention: the PRIMARY server, the one
    carrying the most bytes (primary_server(), already used for the singular
    provider/instance_type keys of the results JSON).
    """
    from dataclasses import replace
    from efootprint_model.spec import estimated_label, unjustified

    if cli_instance is None:
        return spec, None

    target = primary_server(spec)
    if target is None or target.provider is None:
        print("  ⚠ --instance ignored: no cloud server (Boavizta provider) "
              "in the model.")
        return spec, None

    if cli_instance_source:
        new_instance = estimated_label(
            cli_instance, cli_instance_source, source_url=cli_instance_source_url)
    else:
        new_instance = unjustified(
            cli_instance,
            comment="Instance specified on the command line (--instance) without "
                    "verifiable justification (--instance-source absent).")

    new_servers = tuple(
        replace(server, instance_type=new_instance) if server.key == target.key else server
        for server in spec.servers
    )
    return replace(spec, servers=new_servers), target.key


# ---------------------------------------------------------------------------
# Printing the assumptions summary
# ---------------------------------------------------------------------------

CONFIDENCE_LABELS = {
    "high":               "collected ",
    "medium":             "estimated ",
    "low":                "assumed   ",
    "default":            "lib default",
    "default_efootprint": "lib default",
    "default_script":     "script default",
    "unjustified":        "stated",
}


def fmt_conf(conf):
    return CONFIDENCE_LABELS.get(conf, conf or "?")


def print_hypotheses(spec):
    """Summary of the assumptions read directly from the SiteSpec (Traced), more
    faithful than the old table (which re-read env-data.json in parallel with
    the calculation and could diverge from what is actually used)."""
    print()
    print("-" * 65)
    print("  WARNING: HYPOTHETICAL ESTIMATION")
    print("  The values below are calculation assumptions.")
    print("  They are not a real measurement.")
    print("-" * 65)
    print()
    print(f"  {'Parameter':<35} {'Value':<18} {'Source'}")
    print(f"  {'-'*35} {'-'*18} {'-'*12}")

    print(f"  {'1st-party servers':<35} {len(spec.servers):<18}{'detected HAR'}")
    for server in spec.servers:
        label = f"{server.key} ({server.provider.value if server.provider else 'generic'})"
        instance = server.instance_type.value if server.instance_type else "-"
        conf = fmt_conf(server.instance_type.confidence) if server.instance_type else "-"
        print(f"    {label:<33} {instance:<18}{conf}")

    steps_label = "Number of journey steps"
    print(f"  {steps_label:<35} {len(spec.steps):<18}{'detected HAR'}")

    audience = spec.audience
    if audience and audience.visits_per_year:
        v = audience.visits_per_year
        print(f"  {'Estimated annual traffic':<35} "
              f"{int(v.value):,} visits".ljust(20) + " "
              f"{fmt_conf(v.confidence)}")
    else:
        print(f"  {'Estimated annual traffic':<35} {'not provided':<18}{'-'}")
    if audience and audience.phone_fraction:
        print(f"  {'Device mix (phone / desktop)':<35} "
              f"{audience.phone_fraction.value:.0%} / {audience.desktop_fraction.value:.0%}"
              .ljust(20) + " " + fmt_conf(audience.phone_fraction.confidence))
    print()
    print("  Legend: collected = API/HAR  |  estimated = inferred  |  assumed = default value")
    print()


def print_reserves(reserves):
    print()
    print("-" * 65)
    print("  CALCULATION RESERVES — the spec cannot be published as is")
    print("-" * 65)
    for code, message in reserves:
        print(f"\n  [{code}] {message}")
        options = arbitrations_for(code)
        if options:
            print("  Possible remedies:")
            for option in options:
                print(f"    - {option}")
    print()


def print_results(spec, built, ranges):
    fab_kg = fabrication_kg(built)
    energy_kg_ = energy_kg(built)
    total = total_kg(built)
    visits = spec.audience.visits_per_year.value if spec.audience and spec.audience.visits_per_year else 0

    print()
    print("-" * 65)
    print("  RESULTS — HYPOTHETICAL CO2e ESTIMATION")
    if visits:
        print(f"  Base: {visits:,.0f} visits/year")
    print("-" * 65)
    print()
    print(f"  Estimated annual total : ~{total:.1f} kg CO2e/year")
    if visits:
        print(f"  Per estimated visit    : ~{total * 1000 / visits:.2f} g CO2e/visit")
    print()

    print("  Manufacturing (amortized over lifetime):")
    for cat, kg in sorted(fab_kg.items(), key=lambda kv: -kv[1]):
        if kg > 0:
            print(f"    {cat:<14} {kg:>8.2f} kg CO2e/year  (assumption)")
    print(f"    {'TOTAL':<14} {sum(fab_kg.values()):>8.2f} kg CO2e/year")
    print()

    print("  Energy (annual usage):")
    for cat, kg in sorted(energy_kg_.items(), key=lambda kv: -kv[1]):
        if kg > 0:
            print(f"    {cat:<14} {kg:>8.4f} kg CO2e/year  (assumption)")
    print(f"    {'TOTAL':<14} {sum(energy_kg_.values()):>8.4f} kg CO2e/year")
    print()

    infra_lo, infra_hi = ranges["infra_range_kg"]
    usage_lo, usage_hi = ranges["usage_range_kg"]
    print("  Ranges (non-cumulative uncertainties, cf. report):")
    print(f"    infra (sizing mode): {infra_lo:.1f} - {infra_hi:.1f} kg CO2e/year")
    print(f"    usage (Nielsen user time): {usage_lo:.1f} - {usage_hi:.1f} kg CO2e/year")
    print()

    print("  These values are hypothetical orders of magnitude.")
    print("  To refine: re-run with adjusted --visits and --instance.")
    print()


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def export_system_json(built, out_path):
    """NATIVE e-footprint (Boavizta) serialization of a `built` (return of
    `build_system()`) to `out_path`, via `system_to_json`. Common factor of
    `save_boavizta_model()` (reference scenario) and the cumulative
    cumulative recommendation scenarios (`run_recommendation_scenarios()`)."""
    from efootprint.api_utils.system_to_json import system_to_json
    system_to_json(built.system, save_calculated_attributes=False, output_filepath=str(out_path))


def save_boavizta_model(built, source_dir):
    """Writes efootprint-boavizta-model.json: NATIVE serialization of the
    e-footprint (Boavizta) library via `system_to_json`, independent of
    this project. Useful to reload the model in the real e-footprint web
    UI (model_builder) or via `json_to_system`, never read by
    `generate_report_html.py` nor `check_efootprint_contract.py` (cf.
    `save_python_summary()` for the format consumed by this project)."""
    out_path = source_dir / "efootprint-boavizta-model.json"
    export_system_json(built, out_path)
    print(f"  Model serialized: {out_path}")


def save_python_summary(spec, built, ranges, source_dir, env_data, warnings, reserves):
    """Writes efootprint-python-summary.json: application-level summary specific to this
    project (NOT an e-footprint format), consumed by two Python scripts:
    `generate_report_html.py` (feeds the HTML report) and
    `check_efootprint_contract.py` (regression guardrail, compared to
    a baseline). Never meant to be opened directly nor reloaded into
    the e-footprint library (cf. `save_boavizta_model()` for that).

    STRICTLY additive vs the old format (cf. handoff of 05/08/2026,
    section F.3): the ~60 historical, DOCUMENTARY `hypotheses` keys (weight
    by type, har_facts, audience mix by country, device scenarios...),
    are still read from `env_data` as before, in the same place, with the same
    meaning — they describe HAR/CrUX/SimilarWeb measurements independent of the
    e-footprint model. The keys DRIVEN BY THE MODEL (provider,
    instance_type, country, carbon_intensity, storage_gb) instead come from
    `primary_server(spec)`, not `env_data["server"]` : with
    several 1st-party infras, it is not necessarily the same server
    (checked on ants-permis, where `env_data["server"]` denotes a host
    different from the server that actually carries the most bytes).
    The new content (ranges, several servers, traced sources) goes
    into a top-level `model` block, ignored by the current report as long as
    `_section_model() does not exist (Lot 9).
    """
    fab_kg = fabrication_kg(built)
    energy_kg_ = energy_kg(built)
    total = total_kg(built)
    impact_shares = step_impact_shares(built)
    audience = spec.audience
    visits = audience.visits_per_year.value if audience and audience.visits_per_year else 0

    main_server = primary_server(spec)
    job = env_data.get("job", {})
    device = env_data.get("device_mix", {})
    network = env_data.get("network_mix", {})
    audience_env = env_data.get("audience", {})

    def _traced_dict(traced):
        return traced.as_dict() if traced is not None else None

    # Reading time (Nielsen 2008 recalibrated): re-derived here for the appendix, from
    # the same word counts that spec_from_env_data() used
    # (from_har.py::step_user_time()). Recomputation rather than direct reading of the
    # steps' Traced: they only carry the RECALIBRATED value, whereas
    # the appendix must also show the raw (unrecalibrated) value so that the person
    # reading the report understands where the gap comes from, cf. persistent memory
    # "verify before recommending" (never a figure without explaining the
    # calculation behind it).
    avg_time_on_page_s = (env_data.get("traffic") or {}).get("avg_time_on_page_s")
    _step_word_counts = [step.words.value for step in spec.steps if step.words]
    _nielsen_raws = [nielsen_raw_seconds(w) for w in _step_word_counts]
    _factor = recalibration_factor(avg_time_on_page_s, _nielsen_raws)
    reading_time = {
        "formula": f"{NIELSEN_BASE_SECONDS:.0f} s + {NIELSEN_SECONDS_PER_100_WORDS:.1f} s / 100 words",
        "source_name": "Nielsen 2008 (nngroup.com), formula adjusted on Weinreich et al. 2008 (ACM ToWeb)",
        "source_url": "https://www.nngroup.com/articles/how-little-do-users-read/",
        "domain_min_words": 30,
        "domain_max_words": 1250,
        "avg_time_on_page_s": avg_time_on_page_s,
        "recalibration_factor": round(_factor, 4) if _factor is not None else None,
        "recalibrated": _factor is not None,
        "total_raw_s": round(sum(_nielsen_raws), 1) if _nielsen_raws else None,
        "total_recalibrated_s": (round(sum(_nielsen_raws) * _factor, 1)
                                  if (_nielsen_raws and _factor is not None) else None),
    }

    traffic_env = env_data.get("traffic") or {}
    # spec_from_env_data() does not trace source_url/note for visits_per_year
    # (from_har.py:605, simple measurement): they come from the raw 'traffic' block
    # of env-data.json, unless --visits (CLI) replaced the value, in which case
    # the spec's Traced carries the comment "manual entry" to be restored.
    _cli_override = bool(audience and audience.visits_per_year
                          and audience.visits_per_year.source_name == "manual entry (--visits)")
    results = {
        "generated_at": env_data.get("collected_at"),
        "visits_per_year": visits,
        "traffic": {
            "visits_per_year": visits,
            "monthly_visits": traffic_env.get("monthly_visits"),
            "source": audience.visits_per_year.source_name if audience and audience.visits_per_year else "default",
            "source_url": (None if _cli_override else traffic_env.get("source_url")),
            "snapshot": traffic_env.get("snapshot"),
            "confidence": audience.visits_per_year.confidence if audience and audience.visits_per_year else "default",
            "note": (audience.visits_per_year.comment if _cli_override else traffic_env.get("note")),
        },
        "totals": {
            "total_kg_co2e_per_year": round(total, 3),
            "per_visit_g_co2e": round(total * 1000 / visits, 3) if visits else None,
            "fabrication_kg_co2e_per_year": {k: round(v, 3) for k, v in fab_kg.items()},
            "energy_kg_co2e_per_year": {k: round(v, 4) for k, v in energy_kg_.items()},
        },
        "hypotheses": {
            # Weight/duration/split: direct HAR measurement, documentary,
            # do not enter the multi-step calculation (each step has its
            # own JobSpec, cf. spec.py). Kept for the report appendix.
            "page_weight_kb": (job.get("data_transferred_bytes_real")
                               or job.get("data_transferred_bytes", 0)) // 1024,
            "confidence_page_weight": (job.get("confidence_data_transferred_real")
                                       or job.get("confidence_data_transferred", "default")),
            "page_weight_transferred_kb": (job.get("data_transferred_bytes_real") or 0) // 1024,
            "page_weight_uncompressed_kb": job.get("data_transferred_bytes", 0) // 1024,
            "compression_ratio": job.get("compression_ratio"),
            "weight_by_type_transfer_bytes": job.get("weight_by_type_transfer_bytes"),
            "third_party_transfer_bytes": job.get("third_party_transfer_bytes"),
            "third_party_transfer_share": job.get("third_party_transfer_share"),
            "request_duration_ms": job.get("request_duration_ms", 0),
            "confidence_request_duration": job.get("confidence_request_duration", "default"),
            "page_request_count": job.get("request_count"),
            "weight_by_type_bytes": job.get("weight_by_type_bytes"),
            "third_party_bytes": job.get("third_party_bytes"),
            "third_party_requests": job.get("third_party_requests"),
            "third_party_share": job.get("third_party_share"),
            "confidence_breakdown": job.get("confidence_breakdown"),
            "har_facts": job.get("har_facts"),
            "confidence_har_facts": job.get("confidence_har_facts"),
            # Server: DRIVEN BY THE MODEL, so read from the primary server
            # of the spec (the one carrying the most bytes), not from
            # env_data["server"]
            "country": main_server.country.value if main_server and main_server.country else "?",
            "confidence_country": main_server.country.confidence if main_server and main_server.country else "default",
            "carbon_intensity_g_kwh": main_server.carbon_intensity.value if main_server and main_server.carbon_intensity else None,
            "confidence_carbon_intensity": main_server.carbon_intensity.confidence if main_server and main_server.carbon_intensity else "default",
            "provider": main_server.provider.value if main_server and main_server.provider else "unknown",
            "confidence_provider": main_server.provider.confidence if main_server and main_server.provider else "default",
            "instance_type": main_server.instance_type.value if main_server and main_server.instance_type else None,
            "instance_type_manual": bool(main_server and main_server.instance_type
                                          and main_server.instance_type.confidence in ("medium", "unjustified")),
            "instance_type_source": main_server.instance_type.source_name if main_server and main_server.instance_type
                                     and main_server.instance_type.confidence == "medium" else None,
            "instance_type_source_url": main_server.instance_type.source_url if main_server and main_server.instance_type else None,
            # Device/network mix: documentary CrUX measurement, independent of the
            # number of servers.
            "phone_fraction": device.get("phone_fraction", 0.6),
            "desktop_fraction": device.get("desktop_fraction", 0.4),
            "confidence_device_mix": device.get("confidence", "default"),
            "device_mix_source": device.get("source", "default"),
            "phone_fraction_raw": device.get("phone_fraction_raw"),
            "desktop_fraction_raw": device.get("desktop_fraction_raw"),
            "tablet_fraction_raw": device.get("tablet_fraction_raw"),
            "mobile_fraction_raw": device.get("mobile_fraction_raw"),
            "tablet_merged_into_mobile": device.get("tablet_merged_into_mobile", False),
            "ios_share_used": device.get("ios_share_used"),
            "ios_share_source": device.get("ios_share_source"),
            "macos_share_used": device.get("macos_share_used"),
            "macos_share_source": device.get("macos_share_source"),
            "device_scenarios": device.get("scenarios"),
            "device_mix_note": device.get("note"),
            "audience_mix": audience_env.get("mix"),
            "audience_source": audience_env.get("source"),
            "audience_source_url": audience_env.get("source_url"),
            "audience_confidence": audience_env.get("confidence"),
            "audience_per_country": audience_env.get("per_country"),
            "audience_ios_weighted": audience_env.get("ios_share_weighted"),
            "audience_macos_weighted": audience_env.get("macos_share_weighted"),
            "audience_note": audience_env.get("note"),
            "visits_mobile": round(visits * device.get("phone_fraction", 0.6)),
            "visits_desktop": visits - round(visits * device.get("phone_fraction", 0.6)),
            "wifi_fraction": network.get("wifi_fraction", 0.4),
            "mobile_fraction": network.get("mobile_fraction", 0.6),
            "confidence_network_mix": network.get("confidence", "default"),
            "network_note": "Network modeled by pattern: mobile visitors -> mobile network, "
                            "desktop visitors -> wifi.",
            "storage_gb": main_server.storage_gb.value if main_server and main_server.storage_gb else None,
            "servers_note": servers_note(spec),
            "reading_time": reading_time,
        },
        "model": {
            "schema_version": spec.schema_version,
            "archetypes": list(spec.archetypes),
            "servers": [
                {
                    "key": s.key,
                    "role": s.role,
                    "label": s.label,
                    "provider": _traced_dict(s.provider),
                    "instance_type": _traced_dict(s.instance_type),
                    "server_type": _traced_dict(s.server_type),
                    "country": _traced_dict(s.country),
                    "carbon_intensity": _traced_dict(s.carbon_intensity),
                    "storage_gb": _traced_dict(s.storage_gb),
                    "evidence": s.evidence.as_dict() if s.evidence else None,
                    "is_primary": main_server is not None and s.key == main_server.key,
                }
                for s in spec.servers
            ],
            "steps": [
                {
                    "key": step.key,
                    "label": step.label,
                    "url": step.url,
                    "user_time_min": step.user_time.value if step.user_time else None,
                    "user_time_source": step.user_time.source_name if step.user_time else None,
                    "user_time_confidence": step.user_time.confidence if step.user_time else "default",
                    "words": step.words.value if step.words else None,
                    "times_per_journey": step.times_per_journey,
                    # PROPORTIONAL split (not an independent measurement
                    # per step) of the already computed Devices/Network CO2e, cf.
                    # step_impact_shares(): gives a relative contribution benchmark
                    # for reading the report, without replaying the
                    # model once per step.
                    "impact_device_kg": round(impact_shares[step.key]["device_kg"], 4),
                    "impact_network_kg": round(impact_shares[step.key]["network_kg"], 4),
                    "impact_total_kg": round(impact_shares[step.key]["total_kg"], 4),
                    "impact_pct_of_grand_total": round(impact_shares[step.key]["pct_of_grand_total"], 4),
                }
                for step in spec.steps
            ],
            "third_party_hosts": [h.as_dict() for h in spec.third_party_hosts],
            "ranges": {
                "central_kg": round(ranges["central_kg"], 3),
                "infra_range_kg": [round(v, 3) for v in ranges["infra_range_kg"]],
                "usage_range_kg": [round(v, 3) for v in ranges["usage_range_kg"]],
            },
            "consistency": consistency_report(built),
            "reserves_accepted": [{"code": code, "message": message} for code, message in reserves],
            "warnings": list(warnings),
            "sizing": {
                "note": "Internal diagnostic (Lot 6): the annual traffic is spread into a "
                        "UNIFORM timeseries over 24h, never over the site's real hourly profile, "
                        "which artificially MINIMIZES the measured gap. Do not "
                        "present oversizing_ratio as a measurement of the real oversizing "
                        "of a client. Not displayed in the HTML report (decision "
                        "deferred to Lot 9).",
                "servers": servers_sizing(built),
            },
        },
        "sources": collect_sources(spec),
    }

    out_path = source_dir / "efootprint-python-summary.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"  Results serialized: {out_path}")


# ---------------------------------------------------------------------------
# Recommendation scenarios (cumulative prio1 / prio1+2 / prio1+2+3)
# ---------------------------------------------------------------------------

# Qualitative recommendations of the HTML report without a native e-footprint parameter,
# nor a quantifiable EcoIndex/CWV parameter: excluded from the quantified calculation (cf.
# detailed justification per entry), but listed here so that the file
# of gains explicitly explains what it does not quantify rather than
# passing it in silence. Covers both CO2e exclusions (initial
# scope) and EcoIndex/CWV exclusions (LCP/EcoIndex scope).
_EXCLUDED_RECOMMENDATIONS = [
    {
        "recommendation": "cwv",
        "tier": "prio1_2",
        "reason": ("No native e-footprint parameter for LCP/INP/CLS (verified in "
                   "efootprint_model/spec.py, build.py, from_har.py) - excluded from the "
                   "quantified calculation, keeps a qualitative note linking to page weight "
                   "in the report when relevant."),
    },
    {
        "recommendation": "ecoindex",
        "tier": "prio1_2",
        "reason": ("Indicator derived from page weight and element count, not an "
                   "independent e-footprint parameter - the gain it reflects is already "
                   "counted via dead JS/CSS and duplicates."),
    },
    {
        "recommendation": "dom",
        "tier": "prio1_2",
        "reason": ("Number of DOM elements, no direct network link - excluded from the "
                   "quantified calculation, stays qualitative."),
    },
    {
        "recommendation": "cdn_scripts_tiers_qualitatif",
        "tier": "prio3",
        "reason": ("\"CDN already in place\"/\"Third-party scripts detected\" are presence "
                   "detections without a numeric threshold - no byte or percentage "
                   "associated, excluded from the quantified calculation."),
    },
    {
        "recommendation": "many_third_party_domains",
        "tier": "prio3",
        "reason": ("The real third-party weight per page exists (third_party_bytes) but no "
                   "reduction target is measured - setting a percentage would have been "
                   "an invention, excluded from the quantified calculation."),
    },
    {
        "recommendation": "inp",
        "tier": "prio1_2",
        "reason": ("No reliable public rule to estimate an INP delta: the only "
                   "known rule (~1 ms of JS parsing per KB) dates from 2018 and JS engines "
                   "have improved since - excluded from any estimation, not just the "
                   "CO2e calculation."),
    },
    {
        "recommendation": "cls",
        "tier": "prio1_2",
        "reason": ("CLS depends on elements that load late and shift the "
                   "layout, with no structural link to a weight reduction - "
                   "excluded from any estimation, not just the CO2e calculation."),
    },
]

_GENERAL_ASSUMPTIONS = [
    "A single e-footprint lever usable for all quantified recommendations: "
    "JobSpec.data_transferred (transferred/compressed weight per page/Job), applied by "
    "Job/server - not a single site-wide total.",
    "Reductions from different recommendations on the same Job are not "
    "deduplicated against each other (a duplicated file can also contain dead code "
    "counted separately): the cumulative total can slightly overestimate the real gain.",
    "The dead JS/CSS percentage used here comes from "
    "coverage_metrics.py::analyse(), an implementation distinct from the one used directly by "
    "directly by _section_recommendations() in the report (which builds its own "
    "coverage_by_page aggregate from the raw Coverage-*.json) - both measure the "
    "same source data but can diverge slightly on ambiguous cases of "
    "page URL detection.",
    "The tier recalculation is a REAL recalculation of the e-footprint model (build_system() "
    "on a modified SiteSpec), not a simple flat subtraction - necessary "
    "because the calculation is not strictly linear.",
    "The public e-footprint site (model_builder) caps comparisons at 2 models "
    "(MAX_SLOTS=2, verified in the interface code): each scenario is therefore "
    "exported as an individual file, without a pre-built comparison file - explicit decision "
    "by the user, who compares the files herself if needed on the "
    "site.",
]

# (tier from apply_recommendations(), output file suffix)
_TIERS = [
    ("prio1", "prio1"),
    ("prio1_2", "prio1-2"),
    ("prio1_2_3", "prio1-2-3"),
]


def load_coverage_pages(source_dir):
    """Coverage pages (dead JS/CSS) for the per-tier gain calculation, in
    GRADED: empty list (no stopping error) if no Coverage-*.json file
    is found - same logic as the other optional data of the pipeline
    (cf. `cwv = load_cwv(...) if cwv_path.exists()
    else {}` and the equivalent conditional section of
    `generate_report_html.py`)."""
    try:
        coverage = coverage_metrics.analyse(source_dir)
    except FileNotFoundError:
        print("  ⚠ No Coverage data: dead JS/CSS excluded from the per-tier gain calculation.")
        return []
    return coverage.get("pages") or []


def run_recommendation_scenarios(spec, built, env_data, har_path, source_dir):
    """Calculates and exports the 3 cumulative recommendation scenarios
    (prio1, prio1+2, prio1+2+3) from the already computed reference scenario
    (`built`), then writes `efootprint-recommendations-gains.json`
    (summary consumed by a later step of the HTML report).

    The reference scenario (`efootprint-boavizta-model.json`, already written
    by `save_boavizta_model()`) is neither recomputed nor duplicated here: this
    gains file references it by its current name.
    """
    print("[e-footprint] Recommendation scenarios (prio1 / prio1+2 / prio1+2+3)...")

    coverage_pages = load_coverage_pages(source_dir)

    dead = dead_code_reductions(spec, env_data, coverage_pages)
    dup = duplicate_reductions(spec, har_path)
    try:
        brotli = brotli_reductions(spec, env_data, har_path)
    except ImportError:
        print("  ⚠ 'brotli' library missing: Brotli recommendation excluded from the "
              "gain calculation.")
        brotli = []
    all_reductions = dead + dup + brotli

    reference_total = total_kg(built)

    tiers_result = {}
    for tier, suffix in _TIERS:
        tier_spec = apply_recommendations(spec, all_reductions, tier)
        tier_built = build_system(tier_spec)
        tier_total = total_kg(tier_built)

        out_path = source_dir / f"efootprint-scenario-{suffix}.e-f.json"
        export_system_json(palier_built, out_path)

        delta = reference_total - palier_total
        delta_pct = round(delta / reference_total * 100, 2) if reference_total > 0 else None
        print(f"  Scenario {tier}: {tier_total:.2f} kg CO2e/year "
              f"(Δ {delta:+.2f} kg vs reference)")

        tiers_result[tier] = {
            "total_kg_co2e_per_year": round(palier_total, 3),
            "delta_kg_co2e_per_year": round(delta, 3),
            "delta_pct": delta_pct,
            "scenario_file": out_path.name,
        }

    gains = {
        "generated_at": env_data.get("collected_at") or datetime.now().isoformat(),
        "reference": {
            "total_kg_co2e_per_year": round(reference_total, 3),
            "scenario_file": "efootprint-boavizta-model.json",
        },
        "tiers": tiers_result,
        "reductions_detail": [
            {
                "job_key": r.job_key,
                "recommendation": r.recommendation,
                "tier": r.tier,
                "bytes_removed": round(r.bytes_removed, 1),
                "traced": r.traced.as_dict(),
                "page_url": r.page_url,
                "bytes_removed_decompressed": round(r.bytes_removed_decompressed, 1),
                "requests_removed": r.requests_removed,
            }
            for r in all_reductions
        ],
        "excluded_recommendations": _EXCLUDED_RECOMMENDATIONS,
        "hypotheses_generales": _GENERAL_ASSUMPTIONS,
    }

    out_path = source_dir / "efootprint-recommendations-gains.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(gains, f, indent=2, ensure_ascii=False)
    print(f"  Per-tier gains serialized: {out_path}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Hypothetical CO2e estimation via e-footprint",
        epilog="IMPORTANT: all values are hypothetical estimates."
    )
    parser.add_argument("source_dir", help="Source directory containing env-data.json and the .har")
    parser.add_argument("--visits", type=int, default=None,
                        help="Annual traffic (client analytics). Takes precedence over the "
                             "SimilarWeb 'traffic' block written by the agent into env-data.json.")
    parser.add_argument("--instance", default=None,
                        help="Cloud instance type for the PRIMARY server (the one that "
                             "carries the most bytes). A cloud server has only one "
                             "possible instance_type in e-footprint: this setting never "
                             "applies to several servers at once.")
    parser.add_argument("--instance-source", default=None,
                        help="Justification for --instance (e.g. \"confirmed by the client infra team "
                             "ticket #1234\"). Raises confidence to 'estimated'.")
    parser.add_argument("--instance-source-url", default=None,
                        help="Optional link to the proof/source of --instance-source.")
    parser.add_argument("--refresh-data", action="store_true",
                        help="Re-run collect_env_data.py before the calculation")
    args = parser.parse_args()

    source_dir = Path(args.source_dir).resolve()
    if not source_dir.exists():
        print(f"Error: directory not found: {source_dir}")
        sys.exit(1)

    ensure_env_data(source_dir, refresh=args.refresh_data)

    env_data = load_env_data(source_dir)
    if not env_data:
        print(f"Error: env-data.json not found in {source_dir}")
        sys.exit(1)

    har_path = find_har(source_dir)
    if not har_path:
        print(f"Error: no .har found in {source_dir} (nor in "
              f"{RAW_DATA_DIR}/). spec_from_env_data() needs it to "
              "detect infrastructures and split the journey.")
        sys.exit(1)

    audited_domain = infer_audited_domain(env_data, source_dir)

    try:
        spec, warnings = spec_from_env_data(env_data, str(har_path), audited_domain)
    except SpecError as exc:
        print(f"Spec error: {exc}")
        sys.exit(1)

    if warnings:
        print()
        for w in warnings:
            print(f"  ⚠ {w}")

    spec = resolve_visits_override(args.visits, spec)
    spec, instance_target_key = resolve_instance_override(
        args.instance, args.instance_source, args.instance_source_url, spec)

    reserves = calculation_reserves(spec)
    if reserves:
        print_reserves(reserves)
        print("[e-footprint] Calculation stopped: the spec has unassumed reserves.")
        print("Fix the spec (cf. remedies above), then re-run.")
        sys.exit(1)

    print_hypotheses(spec)

    print("[e-footprint] Building the model (hypothetical)...")
    try:
        built = build_system(spec)
    except SpecError as exc:
        print(f"Build error: {exc}")
        sys.exit(1)
    print("[e-footprint] CO2e calculation...")

    print("[e-footprint] Computing ranges (infra/usage)...")
    ranges = footprint_ranges_kg(spec)

    print_results(spec, built, ranges)

    print("[e-footprint] Serializing the model...")
    save_boavizta_model(built, source_dir)
    save_python_summary(spec, built, ranges, source_dir, env_data, warnings, reserves)

    run_recommendation_scenarios(spec, built, env_data, har_path, source_dir)

    # Regenerates the .puml (Step 25) with the per-step impact share (Lot 10),
    # known only now that the calculation has run. The file written at
    # Step 25 (before calculation, without impact share) is therefore replaced by
    # this enriched version: it is THIS version that must be compiled to
    # SVG (`plantuml -tsvg`, cf. skill-steps/45_efootprint.md) for the final report.
    # Writes nothing if the SiteSpec has no journey (archetype only).
    if spec.journeys:
        shares = step_impact_shares(built)
        pct_by_step = {key: v["pct_of_grand_total"] for key, v in shares.items()}
        audience_mix = (env_data.get("audience") or {}).get("mix")
        puml = site_to_plantuml(
            spec, title=audited_domain, audience_mix=audience_mix, step_shares=pct_by_step)
        puml_path = source_dir / f"topology-{audited_domain}.puml"
        puml_path.write_text(puml, encoding="utf-8")
        print(f"  Diagram regenerated (with impact share): {puml_path}")
        # `@startuml <id>` drives the name of the SVG produced by plantuml (cf.
        # to_plantuml.py), never the input .puml name: so we find that name
        # via the same alias rather than renaming the diagram, so as
        # not to duplicate site_to_plantuml()'s logic.
        svg_path = source_dir / f"topology-{audited_domain}.svg"
        try:
            result = subprocess.run(
                ["plantuml", "-tsvg", str(puml_path)], capture_output=True, text=True)
        except FileNotFoundError:
            result = None
        if result is None or result.returncode != 0:
            print("  PlantUML not found or compilation failed: run "
                  f"`plantuml -tsvg {puml_path}` manually, then rename "
                  f"the produced SVG to {svg_path.name}.")
        else:
            diagram_id = _sanitize_alias(f"site_{spec.name}")
            (source_dir / f"{diagram_id}.svg").replace(svg_path)
            print(f"  Diagram compiled to SVG: {svg_path}")
    print()
    visits = spec.audience.visits_per_year.value if spec.audience and spec.audience.visits_per_year else 0
    print(f"  Traffic used: {visits:,.0f} visits/year")
    print("To re-run with other assumptions:")
    _target = f" (--instance targets \"{instance_target_key}\")" if instance_target_key else ""
    print(f"  python3 {Path(__file__).name} {source_dir} --visits 500000 "
          f"--instance <type provider>{_target}")


if __name__ == "__main__":
    main()
