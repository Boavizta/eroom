#!/usr/bin/env python3
"""Automatically fills what can be filled of the EOF framework for an
audited site, from ONLY `eof-reference.json` (produced by the
`eof` skill) and the data already collected by `analyse-parcours`
(`env-data.json`, `audit/har-analysis.json`, `audit/coverage-analysis.json`,
`cwv.json`, `security-headers-analysis.json`, `wellknown-scan.json`,
`html-css-criteria.json`, `public-pages-criteria.json`). NEVER reads the Google Sheet nor the
human Markdown — that is the intended decoupling between "sync the reference" and
"audit a site" (cf. architecture plan, `tmp/handoff.md`).

Of the 54 detailed criteria (6 dimensions), an initial manual
review (2026-09-03) had shown that 10 were usable (4
"automatable", 6 "partial"). Phase 1 extension (same day, plan
`eof-questionnaire`): 18 usable (7 "automatable" with a ticked box:
1.12, 2.1, 3.3, 5.4, 1.5, 1.6, 1.13 ; 11 "partial" with a contextual hint
never ticked). Phase 2 extension (2026-09-07, public pages): 23
usable (7 "automatable" unchanged ; 16 "partial", including 3.2 added by
this phase and 4 already present since Phase 1 without this comment having
been updated). The other 31 remain "I don't know" by construction,
cf. `eof_criteria_mapping.py`.
⚠️ These figures cover the 54 detailed criteria and REMAIN correct after
adding 0.16 to the MAPPING on 2026-09-07: 0.16 is a quick diagnostic
question, not one of the 54. The MAPPING therefore counts 8 automatable when this
comment announces 7, and both are exact in their scope. Do not
"fix" one from the other.
The 16 questions of 🏦
0-Quick diagnostic are NEVER filled automatically (different 1-5
scale, explicit decision), EXCEPT 0.16: they appear in the overview,
with for 0.4, 0.7, 0.10, 0.11, 0.12 and 0.15 a contextual hint displayed as
indicative (never a ticked answer).

Usage:
    python3 run_eof.py <source_dir>

Writes into <source_dir>/:
    eof-audit-results.json  - light summary, consumed by generate_report_html.py
    eof-filled.md           - complete readable framework, answers + provenance + source
    eof-radar-<domain>.svg - radar of the 6 dimensions in two layers (what we have
        established solidly, what the audited service declared hatched), with the number of
        filled-in criteria under each axis and a gauge of what is filled in overall.
        A dimension with no answer at all is marked "no answer", never 0%.
    lots/automatic-judgment.json - the lot output declared by process/lots-manifest.json,
        consumed by process/merge_lots.py and checked by
        process/validate_lot_output.py. Only the criteria this lot has
        ruled on appear there, never the criteria without data.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from eof_criteria_mapping import MAPPING  # noqa: E402
from csp_inventory import inventory_from_headers_analysis, tracking_summary  # noqa: E402
from deploy_freshness import analyze_har_freshness, find_har, summarise  # noqa: E402

sys.path.insert(0, str(SCRIPT_DIR.parent.parent / "eof" / "scripts"))
from generate_radar_svg import build_radar_from_results  # noqa: E402

REFERENCE_PATH = (
    SCRIPT_DIR.parent.parent / "eof" / "docs"
    / "EOF-V.1.1 (EROOM Optimization Framework) - Template - English"
    / "eof-reference.json"
)

CWV_GOOD = {"lcp": 2.5, "inp": 200, "cls": 0.1}
CWV_POOR = {"lcp": 4.0, "inp": 500, "cls": 0.25}


def load_json(path):
    if path and Path(path).exists():
        return json.loads(Path(path).read_text(encoding="utf-8"))
    return None


def find_first(*candidates):
    for c in candidates:
        if c and Path(c).exists():
            return Path(c)
    return None


def load_audit_data(source_dir):
    """Loads the audit data. COST: parses the whole .har (heavy file)
    for deploy_freshness, whereas today only the JSON summaries were read.

    Also records the paths of the files ACTUALLY found, under the key
    `loaded_files`. This feeds the `inputs` field of the lot file:
    it must say what was read, not what could have been. Paths relative to
    source_dir, to stay correct when the audit is replayed from another directory.
    The order of candidates per key is the previous one, it carries the search priority.
    """
    audit_dir = source_dir / "audit"
    candidates = {
        "env": (source_dir / "env-data.json", audit_dir / "env-data.json"),
        "har": (audit_dir / "har-analysis.json", source_dir / "har-analysis.json"),
        "coverage": (audit_dir / "coverage-analysis.json", source_dir / "coverage-analysis.json"),
        "cwv": (source_dir / "cwv.json", audit_dir / "cwv.json"),
        "headers": (source_dir / "security-headers-analysis.json", audit_dir / "security-headers-analysis.json"),
        "wellknown": (source_dir / "wellknown-scan.json", audit_dir / "wellknown-scan.json"),
        "htmlcss": (source_dir / "html-css-criteria.json", audit_dir / "html-css-criteria.json"),
        "public_pages": (source_dir / "public-pages-criteria.json", audit_dir / "public-pages-criteria.json"),
    }
    found = {key: find_first(*paths) for key, paths in candidates.items()}
    data = {key: load_json(path) for key, path in found.items()}
    data["loaded_files"] = [
        str(path.relative_to(source_dir)) for path in found.values() if path is not None
    ]
    data["source_dir"] = source_dir  # exposed for deploy_freshness (needs the .har path, not the JSON)
    return data


# ---------------------------------------------------------------------------
# "automatable" rules: return (answer, provenance, source) or (None, None, reason)
# ---------------------------------------------------------------------------

def rule_1_12(data):
    """Distinguishes tracking (marketing, ad pixels, behavioral analytics)
    from lean analytics (no cookie, no profiling).

    Provenance: estimated (taxonameic classification of domains into tracking/lean families).
    """
    headers = data["headers"]
    har = data["har"]
    inv = inventory_from_headers_analysis(headers)

    # If no CSP available, fall back on the old tech_stack heuristic
    if inv is None:
        env = data["env"]
        categories = ((env or {}).get("tech_stack") or {}).get("categories") or {}
        analytics = categories.get("Analytics")
        if not analytics:
            return "✅ Confirmed strength", "estimated", "env-data.json: tech_stack.categories — no 'Analytics' technology detected"
        tp_share = ((env or {}).get("har_summary") or {}).get("efootprint", {}).get("third_party_share")
        extra = f", third_party_share={tp_share:.1%}" if tp_share is not None else ""
        return ("💡 Improvement potential identified", "estimated",
                f"env-data.json: tech_stack.categories['Analytics'] = {', '.join(analytics)}{extra} (no CSP: old heuristic)")

    summary = tracking_summary(inv, har)
    if summary is None or not summary["loaded_connu"]:
        return (None, None,
                "security-headers-analysis.json: CSP present but har-analysis.json missing — "
                "cannot distinguish declared/loaded")

    trackers = summary["load_tracking"]
    declared_only_trackers = summary["declared_not_loaded"]
    lean_analytics = summary["analytics_sobre_charge"]

    # Tracking effectively loaded -> problem identified
    if trackers:
        return ("💡 Improvement potential identified", "estimated",
                f"security-headers-analysis.json + har-analysis.json: tracking effectively loaded: {', '.join(trackers)}")

    # Tracking declared but absent from the HAR -> gap (probably capture without consent)
    if declared_only_trackers:
        return ("🤔 To be assessed", "estimated",
                f"security-headers-analysis.json + har-analysis.json: tracking declared in the CSP but absent from the HAR "
                f"({', '.join(declared_only_trackers)}) — probable capture without accepting consent")

    # Only lean analytics -> strength
    if lean_analytics:
        return ("✅ Confirmed strength", "estimated",
                f"security-headers-analysis.json + har-analysis.json: only lean analytics loaded ({', '.join(lean_analytics)}), "
                "no marketing/ad/behavioral tracking")

    # Neither tracking nor lean analytics
    return ("✅ Confirmed strength", "estimated",
            "security-headers-analysis.json + har-analysis.json: no tracking or analytics detected")


def rule_2_1(data):
    """Detection of AI and blockchain technologies.

    Provenance: estimated. Technology detection is a footprint, not a
    measurement: the absence of an AI footprint does not prove the absence of AI, and the
    attachment of a technology to the "AI" category comes from the detection tool's
    catalog, not from the audited service.
    """
    env = data["env"]
    ai = (env or {}).get("ai_external_apis") or {}
    techs = ((env or {}).get("tech_stack") or {}).get("technologies") or []
    flagged = [t["name"] for t in techs if t.get("category", "").lower() in ("ia", "intelligence artificielle", "blockchain")]
    if not ai and not flagged:
        return "✅ Confirmed strength", "estimated", "env-data.json: ai_external_apis empty, no AI/blockchain technology detected"
    detail = list(ai.keys()) + flagged
    return "💡 Improvement potential identified", "estimated", f"env-data.json: ai_external_apis/tech_stack = {detail}"


def rule_3_3(data):
    """Carbon intensity of the hosting.

    Provenance: collected (ipinfo API + reference table of carbon intensity by country).
    """
    env = data["env"]
    servers = (env or {}).get("servers")
    if not servers and (env or {}).get("server"):
        servers = [env["server"]]
    if not servers:
        return None, None, "env-data.json: servers[] missing"
    threshold = 250
    detail = "; ".join(
        f"{s.get('host') or '?'} ({s.get('country_code') or '?'}, {s.get('carbon_intensity_g_kwh') or '?'} gCO2/kWh)"
        for s in servers
    )
    over = [s for s in servers if (s.get("carbon_intensity_g_kwh") or 0) > threshold]
    if over:
        return "💡 Improvement potential identified", "collected", f"env-data.json: servers[] = {detail} (threshold {threshold} gCO2/kWh exceeded)"
    return "✅ Confirmed strength", "collected", f"env-data.json: servers[] = {detail} (below the {threshold} gCO2/kWh threshold)"


def rule_5_4(data):
    """Core Web Vitals (LCP, INP, CLS).

    Provenance: collected (field data Chrome UX Report via the CrUX API).
    """
    cwv = data["cwv"]
    if not cwv:
        return None, None, "cwv.json missing"
    poor_pages, all_good = [], True
    for entry in cwv:
        lcp, inp, cls = entry.get("lcp"), entry.get("inp"), entry.get("cls")
        label = entry.get("url") or entry.get("page") or "?"
        if (lcp is not None and lcp > CWV_POOR["lcp"]) or \
           (inp is not None and inp > CWV_POOR["inp"]) or \
           (cls is not None and cls > CWV_POOR["cls"]):
            poor_pages.append(label)
        if not ((lcp is None or lcp <= CWV_GOOD["lcp"]) and
                (inp is None or inp <= CWV_GOOD["inp"]) and
                (cls is None or cls <= CWV_GOOD["cls"])):
            all_good = False
    if poor_pages:
        return "💡 Improvement potential identified", "collected", f"cwv.json: page(s) in the 'poor' zone: {', '.join(sorted(set(poor_pages)))}"
    if all_good:
        return "✅ Confirmed strength", "collected", "cwv.json: all pages under the CWV 'good' thresholds"
    return "🤔 To be assessed", "collected", "cwv.json: intermediate zone ('needs improvement'), no 'poor' page"


# --- Phase 1 extension (2026-09-03) ---------------------------------------

def rule_1_5(data):
    """Detection of auto-playing media (autoplay).

    Provenance: collected (HTML parsing, autoplay attribute search on <video>/<audio>).
    """
    htmlcss = data["htmlcss"]
    pages = (htmlcss or {}).get("pages")
    if not pages:
        return None, None, "html-css-criteria.json missing"
    offenders = [p["url"] for p in pages if p.get("has_autoplay_media")]
    if offenders:
        return "💡 Improvement potential identified", "collected", f"html-css-criteria.json: autoplay detected on {offenders}"
    return "✅ Confirmed strength", "collected", "html-css-criteria.json: no <video|audio autoplay> tag detected on the audited pages"


def rule_1_6(data):
    """Adaptation of resources (responsive images, CSS media queries).

    Provenance: estimated. The counts are measured, but the verdict rests on
    thresholds of our own invention (adaptive image ratio >= 0.5 and at least
    3 @media queries) that neither the EOF framework nor any public source sets.
    The figure is collected, the conclusion is deduced.
    """
    htmlcss = data["htmlcss"]
    pages = (htmlcss or {}).get("pages")
    css = (htmlcss or {}).get("css")
    if not pages or css is None:
        return None, None, "html-css-criteria.json missing"
    ratios = [p["adaptive_img_ratio"] for p in pages if p.get("adaptive_img_ratio") is not None]
    has_any_adaptive_img = any(r > 0 for r in ratios)
    all_pages_adaptive = bool(ratios) and all(r >= 0.5 for r in ratios)
    has_media_queries = (css.get("media_query_count") or 0) >= 3
    source = f"html-css-criteria.json: adaptive_img_ratio per page = {ratios} ; media_query_count = {css.get('media_query_count')}"
    if all_pages_adaptive and has_media_queries:
        return "✅ Confirmed strength", "estimated", source
    if not has_any_adaptive_img and not has_media_queries:
        return "💡 Improvement potential identified", "estimated", source
    return "🤔 To be assessed", "estimated", source + " (conflicting signals between pages/CSS, deterministic constraint: do not decide)"


def rule_1_13(data):
    """Journey optimization (proxy: Lighthouse accessibility score).

    Provenance: collected (PageSpeed Insights API, accessibility category).
    """
    cwv = data["cwv"]
    if not cwv:
        return None, None, "cwv.json missing"
    accessibility_scores = [e["accessibility_score_pct"] for e in cwv if e.get("accessibility_score_pct") is not None]
    if not accessibility_scores:
        return None, None, "cwv.json: no accessibility_score_pct available"
    worst = min(accessibility_scores)
    source = f"cwv.json: accessibility_score_pct (PageSpeed Insights) — worst page/strategy = {worst}, values = {accessibility_scores}"
    if worst < 60:
        return "💡 Improvement potential identified", "collected", source
    if worst >= 90:
        return "✅ Confirmed strength", "collected", source
    return "🤔 To be assessed", "collected", source + " (60-90 zone, ambiguous)"


RULES = {
    "1.12": rule_1_12, "2.1": rule_2_1, "3.3": rule_3_3, "5.4": rule_5_4,
    "1.5": rule_1_5, "1.6": rule_1_6, "1.13": rule_1_13,
}


# ---------------------------------------------------------------------------
# Quick diagnostic: NEVER automated, except 0.16 — near-exact duplicate of
# 3.3 (same data: servers[].carbon_intensity_g_kwh), with a more precise
# numeric scale. Explicit decision of 2026-09-03 (analysis
# eof-question-minimization-analysis.md, section 1): the only exception to the
# principle "Quick diagnostic = overview, never filled automatically".
# ---------------------------------------------------------------------------

# (exclusive_upper_bound, screen_rank) of screens 2 to 5 ("< X gCO2e/kWh"), from
# best to worst. Screen 1 ("> 750") is the fallback if no threshold is
# met. Zone [500, 750] not covered by the source Sheet scale
# (known bias, cf. eof-question-minimization-analysis.md): fallback to
# screen 1 with provenance degraded to "estimated" instead of "collected", so as not to
# claim a precision the source scale does not have there.
_CARBON_BUCKETS = [(100, 5), (200, 4), (300, 3), (500, 2)]


def rule_diag_0_16(data, screens):
    """Quick diagnostic 0.16: hosting carbon intensity (duplicate of 3.3).

    Provenance: collected (same source as 3.3, ipinfo API + carbon table),
    degraded to estimated for the [500, 750] gCO2/kWh zone not covered by the scale.
    """
    env = data["env"]
    servers = (env or {}).get("servers")
    if not servers and (env or {}).get("server"):
        servers = [env["server"]]
    if not servers:
        return None, None, "env-data.json: servers[] missing"
    # Most unfavorable screen among all detected 1st-party servers.
    worst_rank, worst_value = 1, None
    for s in servers:
        v = s.get("carbon_intensity_g_kwh")
        if v is None:
            continue
        rank = next((r for upper, r in _CARBON_BUCKETS if v < upper), 1)
        if worst_value is None or rank < worst_rank:
            worst_rank, worst_value = rank, v
    if worst_value is None:
        return None, None, "env-data.json: servers[].carbon_intensity_g_kwh missing"
    # Provenance degradation for the [500, 750] zone not covered by the EOF scale
    provenance = "estimated" if (worst_rank == 1 and worst_value <= 750) else "collected"
    answer = next((c for c in screens if c.strip().startswith(f"{worst_rank}")), screens[worst_rank - 1] if len(screens) >= worst_rank else None)
    source_suffix = " (scale fallback, uncovered zone [500, 750])" if provenance == "estimated" else ""
    source = f"env-data.json: servers[].carbon_intensity_g_kwh = {worst_value} gCO2e/kWh (duplicate of 3.3, same data){source_suffix}"
    return answer, provenance, source


# ---------------------------------------------------------------------------
# "partial" contexts: hint displayed in the appendix, never a ticked answer
# ---------------------------------------------------------------------------

def context_1_9(data):
    env = data["env"]
    v = ((env or {}).get("har_summary") or {}).get("efootprint", {}).get("data_transferred_bytes_real")
    # The measurement covers the HEAVIEST page of the capture, not the home page:
    # cf. collect_env_data.py, which feeds this field from the heaviest variable.
    return f"Actually transferred data (heaviest page): {v / 1024:.0f} KB" if v else None


def context_1_14(data):
    env = data["env"]
    pages = [(p.get("url", "?"), p.get("size_kb")) for p in ((env or {}).get("pages") or []) if p.get("size_kb") is not None]
    if not pages:
        return None
    pages.sort(key=lambda x: -x[1])
    # Omit the lightest page if its weight rounds to 0 (measurement failure, not a result)
    heaviest = f"{pages[0][0]} ({pages[0][1]:.0f} KB)"
    if pages[-1][1] >= 0.5:
        lightest = f"{pages[-1][0]} ({pages[-1][1]:.0f} KB)"
        return f"Heaviest page: {heaviest} ; lightest: {lightest}"
    else:
        return f"Heaviest page: {heaviest}"


def context_1_15(data):
    env = data["env"]
    t = (env or {}).get("traffic") or {}
    v = t.get("visits_per_year")
    if v:
        # French thousands separator (non-breaking space), not English (comma)
        formatted = f"{v:,}".replace(",", " ")
        return f"Estimated traffic: {formatted} visits/year ({t.get('source', '?')})"
    return None


def context_5_5(data):
    coverage = data["coverage"]
    pages = (coverage or {}).get("pages") or []
    worst = sorted(pages, key=lambda p: -(p.get("js_unused_pct") or 0))[:2]
    if not worst:
        return None
    return " ; ".join(f"{p.get('url', '?')} : unused JavaScript {p.get('js_unused_pct', '?')}%" for p in worst)


def context_2_3(data):
    """Hint of separated backend components (distinct PaaS declared in the CSP)."""
    headers = data["headers"]
    inv = inventory_from_headers_analysis(headers)
    if not inv:
        return None
    families = inv["families"]
    paas = families.get("paas_backend") or []
    if not paas:
        return None
    return f"Several distinct hosting components detected ({', '.join(paas)}), which suggests an architecture separating responsibilities. We cannot assess from the outside the efficiency of their coupling nor the optimization of their communication."


def context_2_5(data):
    har = data["har"]
    dups = sorted((har or {}).get("duplicate_urls") or [], key=lambda d: -d.get("count", 0))[:3]
    if not dups:
        return None
    return " ; ".join(f"{d['url']} loaded {d['count']} times" for d in dups)


# --- Phase 1 extension (2026-09-03) ---------------------------------------

def context_1_4(data):
    htmlcss = data["htmlcss"]
    pages = (htmlcss or {}).get("pages") or []
    native = sum(p.get("native_buttons") or 0 for p in pages)
    custom = sum(p.get("custom_role_buttons") or 0 for p in pages)
    if native + custom == 0:
        return None
    return f"Native HTML buttons detected: {native} ; buttons with role='button' attribute: {custom} (across all pages)"


def context_1_11(data):
    htmlcss = data["htmlcss"]
    css = (htmlcss or {}).get("css")
    if css is None:
        return None
    return ("@media rules (prefers-reduced-motion or prefers-color-scheme) detected in the stylesheets"
            if css.get("has_prefers_reduced_or_scheme")
            else "No @media rule (prefers-reduced-motion or prefers-color-scheme) detected in the stylesheets")


def context_6_1(data):
    headers = data["headers"]
    worst = (headers or {}).get("worst_page")
    if not worst:
        return None
    return f"HTTP security headers score: {worst['score_pct']}% (grade {worst['grade']}) on {worst['url']} - one indicator among others of production maturity"


def context_3_5(data):
    """Hint of shared infrastructure (PaaS/CDN/cloud declared in the CSP)."""
    headers = data["headers"]
    inv = inventory_from_headers_analysis(headers)
    if not inv:
        return None
    families = inv["families"]
    paas = families.get("paas_backend") or []
    cdn = families.get("cdn_bibliotheques") or []
    cloud = families.get("infra_cloud_generique") or []
    all_shared = paas + cdn + cloud
    if not all_shared:
        return None
    return f"Your service uses {len(all_shared)} external infrastructure service(s) (hosting, content delivery, cloud): {', '.join(all_shared[:5])}{'...' if len(all_shared) > 5 else ''}"


def context_3_7(data):
    """Hint of a platform supporting elasticity (PaaS declared in the CSP)."""
    headers = data["headers"]
    inv = inventory_from_headers_analysis(headers)
    if not inv:
        return None
    families = inv["families"]
    paas = families.get("paas_backend") or []
    if not paas:
        return None
    return f"Your service relies on a hosting platform ({', '.join(paas)}) capable of automatically adjusting its resources. We cannot see from the outside whether this adjustment is enabled on your side, nor whether your load varies enough to justify it."


def context_6_3(data):
    """Hint of deployment freshness and atomicity (Last-Modified of the .har)."""
    source_dir = data.get("source_dir")
    if not source_dir:
        return None
    har_path = find_har(source_dir)
    if not har_path:
        return None
    env = data["env"]
    first_party_hosts = set()
    for page in (env or {}).get("pages") or []:
        url = page.get("url")
        if url:
            from urllib.parse import urlparse
            host = urlparse(url).netloc.lower()
            if host:
                first_party_hosts.add(host)
    info = analyze_har_freshness(har_path, first_party_hosts or None)
    # summarise() already writes its text for the audited service: do not rework it here
    # by word substitution, that would fabricate incorrect sentences ("avoid
    # cache parameter"). Any rewording happens in deploy_freshness.summarise().
    return summarise(info)


def context_6_6(data):
    cwv = data["cwv"]
    headers = data["headers"]
    wellknown = data["wellknown"]
    parts = []
    if cwv:
        bp_scores = [e["best_practices_score_pct"] for e in cwv if e.get("best_practices_score_pct") is not None]
        if bp_scores:
            parts.append(f"Lighthouse audit - Best Practices (worst page): {min(bp_scores)}%")
    if headers and headers.get("worst_page"):
        parts.append(f"security headers (worst page): grade {headers['worst_page']['grade']}")
    if wellknown is not None:
        txt = (wellknown.get("security_txt") or {})
        parts.append(f"security.txt file: {'present and well-formed' if txt.get('well_formed') else ('present but malformed' if txt.get('present') else 'missing')}")
    return " ; ".join(parts) if parts else None


def context_6_8(data):
    """Hint of JS bundle duplication (Lighthouse duplicated-javascript audit).
    Tolerant of both formats: logical_name ("duplicated-javascript") or raw key
    ("duplicated-javascript-insight" or "duplicated-javascript").
    """
    cwv = data["cwv"]
    if not cwv:
        return None
    # Look for the audit in all entries (pages/strategies)
    for entry in cwv:
        insights = entry.get("lighthouse_insights")
        if not insights:
            continue
        # Look by logical_name (new format) or by raw keys (old format)
        dup = (insights.get("duplicated-javascript") or
               insights.get("duplicated-javascript-insight"))
        if dup is None:
            continue
        score = dup.get("score")
        item_count = dup.get("itemCount", 0)
        if score == 1 and item_count == 0:
            return "No JavaScript code duplication detected by the Lighthouse audit (perfect score). This does not prove that your dependency management is optimal, only that no obvious duplication was spotted."
        elif score is not None:
            return f"Lighthouse JavaScript duplication audit: score {score:.2f}, {item_count} item(s) detected - hint of potential duplication"
        else:
            return "Lighthouse JavaScript duplication audit: present but without a score (content not analyzable)"
    return None


def context_3_2(data):
    """Hint of a public declaration of environmental impact monitoring."""
    public_pages = data["public_pages"]
    if not public_pages:
        return None

    status = public_pages.get("status")
    if status == "no_directory":
        return None

    if status == "no_files":
        patterns = ", ".join(public_pages.get("files_searched", []))
        return f"No public eco-design page found (patterns searched: {patterns})"

    # Compile all declarations found
    all_declarations = []

    for file_analysis in public_pages.get("files_analyzed", []):
        if not file_analysis.get("read_success"):
            continue
        decl = file_analysis.get("declarations")
        if not decl or not decl.get("parse_success"):
            continue

        all_declarations.extend(decl.get("tracking_declarations", []))

    if not all_declarations:
        return "Public eco-design page found, but no impact monitoring declaration detected"

    # Take the first declaration (full sentence, original case)
    first_decl = all_declarations[0]["phrase"]

    # If the sentence is very long (> 200 characters), cut at a word boundary
    if len(first_decl) > 200:
        cut = first_decl[:197].rfind(' ')
        if cut > 100:  # Only cut if we keep at least 100 characters
            first_decl = first_decl[:cut] + "..."

    filename = public_pages.get("files_found", ["public page"])[0]
    return f"Declaration on {filename}: \"{first_decl}\""


CONTEXTS = {
    "1.9": context_1_9, "1.14": context_1_14,
    "1.15": context_1_15, "1.16": context_1_15,  # same traffic field
    "5.5": context_5_5, "2.3": context_2_3, "2.5": context_2_5,
    "3.2": context_3_2,
    "3.5": context_3_5, "3.7": context_3_7,
    "1.4": context_1_4, "1.11": context_1_11,
    "6.1": context_6_1, "6.3": context_6_3, "6.6": context_6_6, "6.8": context_6_8,
}

# Contextual hints for 🏦 0-Quick diagnostic — never a ticked answer
# (only 0.16 is entitled to an automatic answer, cf. above), just a
# piece of data displayed next to the question in the overview.

def diag_context_0_4(data):
    har = data["har"]
    third_party = (har or {}).get("domains", {}).get("third_party")
    if third_party is None:
        return None
    return f"{len(third_party)} third-party domain(s) detected during the capture (list observed from the outside, says nothing about the complete technical architecture): {', '.join(third_party)}"


def diag_context_0_10(data):
    wellknown = data["wellknown"]
    sitemap = (wellknown or {}).get("sitemap") or {}
    if not sitemap.get("present") or not sitemap.get("url_count"):
        return None
    import math
    n = sitemap["url_count"]
    return f"{n} URL(s) in the sitemap (logarithmic order of magnitude: about {math.log2(n):.1f})"


def diag_context_0_7(data):
    """Hint of architectural complexity (distinct hosting/distribution components declared in the CSP)."""
    headers = data["headers"]
    inv = inventory_from_headers_analysis(headers)
    if not inv:
        return None
    families = inv["families"]
    paas = families.get("paas_backend") or []
    cdn = families.get("cdn_bibliotheques") or []
    components = paas + cdn
    if not components:
        return None
    return (
        f"{len(components)} distinct hosting/distribution component(s) declared in the CSP "
        f"({', '.join(components)}), which suggests several separate building blocks rather than a single block. "
        "This is only an indirect and partial hint: it sees neither the number of internal microservices, "
        "nor the real coupling between these blocks, nor the functional complexity of the site."
    )


_CRUX_CATEGORY_RANK = {"SLOW": 2, "AVERAGE": 1, "FAST": 0}


def _cwv_status_rank(entry):
    """0 = 'good', 1 = intermediate zone, 2 = 'poor' (same thresholds as rule_5_4)."""
    lcp, inp, cls = entry.get("lcp"), entry.get("inp"), entry.get("cls")
    if (lcp is not None and lcp > CWV_POOR["lcp"]) or \
       (inp is not None and inp > CWV_POOR["inp"]) or \
       (cls is not None and cls > CWV_POOR["cls"]):
        return 2
    if not ((lcp is None or lcp <= CWV_GOOD["lcp"]) and
            (inp is None or inp <= CWV_GOOD["inp"]) and
            (cls is None or cls <= CWV_GOOD["cls"])):
        return 1
    return 0


def _cwv_worst_entry(entries):
    if not entries:
        return None
    def sort_key(e):
        return (_cwv_status_rank(e), _CRUX_CATEGORY_RANK.get(e.get("crux_category"), -1))
    return max(entries, key=sort_key)


def _describe_cwv_entry(entry):
    label = entry.get("url") or entry.get("page") or "?"
    strategy = entry.get("strategy") or "?"
    lcp, inp, cls = entry.get("lcp"), entry.get("inp"), entry.get("cls")
    category = entry.get("crux_category")
    bits = []
    if lcp is not None:
        bits.append(f"LCP {lcp}s")
    if inp is not None:
        bits.append(f"INP {inp}ms")
    if cls is not None:
        bits.append(f"CLS {cls}")
    metrics = ", ".join(bits) if bits else "metrics unavailable"
    cat_txt = f", CrUX category '{category}'" if category else ""
    return f"{label} ({strategy}) : {metrics}{cat_txt}"


def diag_context_0_11(data):
    cwv = data["cwv"]
    if not cwv:
        return None
    worst = _cwv_worst_entry(cwv)
    if worst is None:
        return None
    return (f"Worst page across all strategies (Core Web Vitals field/lab): {_describe_cwv_entry(worst)}. "
            "These are technical loading, responsiveness and visual stability scores, not a direct measure of the user's feeling.")


def diag_context_0_12(data):
    cwv = data["cwv"]
    if not cwv:
        return None
    mobile_entries = [e for e in cwv if e.get("strategy") == "mobile"]
    if not mobile_entries:
        return None
    worst = _cwv_worst_entry(mobile_entries)
    if worst is None:
        return None
    return (f"Worst page in mobile strategy (proxy for low-end/old hardware): {_describe_cwv_entry(worst)}. "
            "Mobile field CrUX mixes all device types, it is not an isolated measurement on specifically old hardware.")


def diag_context_0_15(data):
    """Hint of a public declaration of data retention/deletion/archiving."""
    public_pages = data["public_pages"]
    if not public_pages:
        return None
    if public_pages.get("status") in ("no_directory", "no_files"):
        return None

    for file_analysis in public_pages.get("files_analyzed", []):
        if not file_analysis.get("read_success"):
            continue
        decl = file_analysis.get("declarations")
        if not decl or not decl.get("parse_success"):
            continue
        retention = decl.get("retention_declarations") or []
        if not retention:
            continue
        phrase = retention[0]["phrase"]
        filename = file_analysis.get("filename", "public page")
        if len(phrase) > 200:
            cut = phrase[:197].rfind(" ")
            if cut > 100:
                phrase = phrase[:cut] + "..."
        return (
            f"Declaration on {filename}: \"{phrase}\". "
            "A public declaration of data retention does not prove that a formalized "
            "and actually applied policy exists internally, nor that it covers all "
            "the service's processing: it is only a hint that a deletion and "
            "archiving policy potentially exists."
        )
    return None


DIAG_CONTEXTS = {
    "0.4": diag_context_0_4, "0.7": diag_context_0_7, "0.10": diag_context_0_10,
    "0.11": diag_context_0_11, "0.12": diag_context_0_12, "0.15": diag_context_0_15,
}


# ---------------------------------------------------------------------------
# Evaluating a criterion
# ---------------------------------------------------------------------------

def evaluate_criterion(criterion, data):
    entry = MAPPING.get(criterion["id"])
    result = {
        "id": criterion["id"], "dimension": criterion["pillar"], "criterion": criterion["criterion"],
        "max_potential": criterion["max_potential"], "category": "no_data",
        "answer": None, "coefficient": None, "provenance": None, "source": None, "context": None,
    }
    if not entry:
        return result

    result["category"] = entry["category"]
    if entry["category"] == "automatable":
        rule = RULES.get(criterion["id"])
        answer, provenance, source = rule(data) if rule else (None, None, "rule not implemented")
        result["source"] = source
        if answer is not None:
            result["answer"] = answer
            result["coefficient"] = criterion["evaluation_coefficient_options"].get(answer)
            result["provenance"] = provenance
    elif entry["category"] == "partial":
        ctx_fn = CONTEXTS.get(criterion["id"])
        context = ctx_fn(data) if ctx_fn else None
        if context:
            result["context"] = context
            result["provenance"] = entry["max_provenance"]
            result["source"] = entry["data_field"]
    return result


def build_quick_diag_overview(reference, data):
    questions = []
    for q in reference["quick_diagnostic"]:
        entry = {"id": q["id"], "criterion": q["criterion"], "impact_level": q["impact_level"],
                 "answer": None, "provenance": None, "source": None, "context_index": None}
        if q["id"] == "0.16":
            answer, provenance, source = rule_diag_0_16(data, q["screens"])
            if answer is not None:
                entry.update(answer=answer, provenance=provenance, source=source)
        ctx_fn = DIAG_CONTEXTS.get(q["id"])
        if ctx_fn:
            entry["context_index"] = ctx_fn(data)
        questions.append(entry)
    return questions


# ---------------------------------------------------------------------------
# Lot output, consumed by process/merge_lots.py
# ---------------------------------------------------------------------------

LOT_ID = "automatic-judgment"

# The fields the process layer refuses in a lot file: they come from the
# reference and the merge adds them back. Cf. FORBIDDEN_FIELDS in
# process/validate_lot_output.py. The lot says ONLY what it has ruled on.
LOT_FIELDS = ("answer", "coefficient", "provenance", "source", "context")


def _lot_entry(criterion_id, category, values):
    """A lot entry: `id` and `category` always, the rest only if it has
    a value. Omitting rather than setting `null` avoids writing a `coefficient: null`
    next to an answer where the contract requires a non-null one, and reads better.
    """
    entry = {"id": criterion_id, "category": category}
    for key in LOT_FIELDS:
        if values.get(key) is not None:
            entry[key] = values[key]
    return entry


def build_lot_output(results, diag_questions, loaded_files, generated_at):
    """Builds what this lot has to say, in the format that process/validate_lot_output.py
    enforces: root with exactly 4 keys, strict rejection of any other.

    Writes ONLY the criteria the lot has ruled on, i.e. those that carry
    an answer or a context. A criterion without data is not information:
    staying silent avoids passing 31 silences off as work.

    Quick diagnostic questions (prefix `0.`) are written only if they are in the
    MAPPING, so today the only 0.16. It is a matter of ownership: the contextual hint
    of 0.4 belongs to the `quick-diagnostic-judgment` lot, and it has neither
    provenance nor source anyway, which the contract requires as soon as a context is set.
    """
    criteria = []
    for r in results:
        if r["answer"] is None and not r["context"]:
            continue
        criteria.append(_lot_entry(r["id"], r["category"], r))
    for q in diag_questions:
        entry = MAPPING.get(q["id"])
        if not entry:
            continue
        if q["answer"] is None and not q["context_index"]:
            continue
        criteria.append(_lot_entry(q["id"], entry["category"], {
            "answer": q["answer"],
            # Never a coefficient on the quick diagnostic: the reference does not define
            # one for its screens, and the validator rejects it. It is not an oversight.
            "coefficient": None,
            "provenance": q["provenance"],
            "source": q["source"],
            "context": q["context_index"],
        }))
    return {
        "lot_id": LOT_ID,
        "generated_at": generated_at,
        "inputs": loaded_files,
        "criteria": criteria,
    }


def compute_dimension_scores(criteria_results):
    by_dim = {}
    for c in criteria_results:
        by_dim.setdefault(c["dimension"], []).append(c)
    dimensions = []
    for dim, items in by_dim.items():
        # Identify the discarded criteria (discarded-criterion convention, section 2)
        discarded = [c for c in items if c["answer"] == "🚫 Not applicable"]
        nb_discarded = len(discarded)

        # Discarded criteria leave all denameinators (convention 2.1)
        kept_items = [c for c in items if c["answer"] != "🚫 Not applicable"]
        answered = [c for c in kept_items if c["answer"] is not None]

        # Guard: a fully discarded dimension must NEVER come out at 0%
        out_of_scope = (nb_discarded == len(items))

        # Canonical formula: sum of potentials kept ÷ sum of max_potential of the KEPT criteria
        # (discarded criteria are removed from the denameinator, convention 2.1)
        total_max_potential = sum(c["max_potential"] for c in kept_items) or 1e-9
        if out_of_scope:
            optimization_pct = None
            completeness_pct = None
            total = 0
        elif answered:
            optimization_pct = sum(c["coefficient"] * c["max_potential"] for c in answered) / total_max_potential * 100
            completeness_pct = len(answered) / len(kept_items) * 100 if kept_items else 0
            total = len(kept_items)
        else:
            optimization_pct = None
            completeness_pct = len(answered) / len(kept_items) * 100 if kept_items else 0
            total = len(kept_items)

        # Count by provenance
        # The 5 provenances of conventions.precedence_provenance, in order. `assumed` is
        # in it since 2026-09-07: without it, the `if prov in ...` test just below
        # would discard without a word an answer set in `assumed`. A zero counter is
        # information, a lost answer is not.
        answered_by_provenance = {"collected": 0, "estimated": 0, "declared": 0, "stated": 0, "assumed": 0}
        for c in answered:
            prov = c.get("provenance")
            if prov in answered_by_provenance:
                answered_by_provenance[prov] += 1
        dimensions.append({
            "name": dim, "optimization_potential_pct": optimization_pct,
            "answered": len(answered), "total": total,
            "completeness_pct": completeness_pct,
            "answered_by_provenance": answered_by_provenance,
            "discarded": nb_discarded,
            "out_of_scope": out_of_scope,
        })
    return dimensions


def build_eof_filled_md(reference, results_by_id, dimensions, diag_overview):
    lines = ["# EOF — Automatically filled-in framework (partial)\n"]
    lines.append(
        "> Generated by `run_eof.py`, from the available audit data. "
        "**The vast majority of criteria cannot be deduced automatically** "
        "(organizational/product questions): they stay \"I don't know\", to "
        "be completed by a human in the blank template of the `eof` skill.\n"
    )
    lines.append(
        "## 🏦 0 — Quick diagnostic (overview, never filled automatically — "
        "EXCEPT 0.16, exact duplicate of 3.3, cf. `eof-question-minimization-analysis.md`)\n"
    )
    for q in diag_overview:
        if q["answer"]:
            lines.append(
                f"- **{q['id']}** — {q['criterion']} → **{q['answer']}** "
                f"_(automatic, provenance {q['provenance']} — {q['source']})_"
            )
        elif q.get("context_index"):
            lines.append(
                f"- **{q['id']}** — {q['criterion']} _(impact level: {q['impact_level']})_ "
                f"— indicative data: {q['context_index']}"
            )
        else:
            lines.append(f"- **{q['id']}** — {q['criterion']} _(impact level: {q['impact_level']})_")
    lines.append("")
    current_dim = None
    for crit in reference["criteria"]:
        r = results_by_id[crit["id"]]
        if crit["pillar"] != current_dim:
            current_dim = crit["pillar"]
            dim_info = next(d for d in dimensions if d["name"] == current_dim)
            potential_txt = f"{dim_info['optimization_potential_pct']:.0f}%" if dim_info["optimization_potential_pct"] is not None else "no data"
            lines.append(f"\n## {current_dim} — optimization potential: {potential_txt} ({dim_info['answered']}/{dim_info['total']} answered)\n")
        lines.append(f"### {crit['id']} — {crit['criterion']}\n")
        if r["answer"]:
            lines.append(f"**Answer (automatic)**: {r['answer']}")
            lines.append(f"**Provenance**: {r['provenance']} — **Source**: {r['source']}")
        elif r["context"]:
            lines.append("**Answer**: I don't know (no rule reliable enough to decide)")
            lines.append(f"**Indicative data** ({r['provenance']}): {r['context']} — _field: {r['source']}_")
        else:
            lines.append("**Answer**: I don't know (no audit data available — organizational/product criterion)")
        lines.append("")
    return "\n".join(lines)


def autotest():
    """Replays the embedded test cases on the discarded-criterion arithmetic."""
    import tempfile

    failures = []
    total = 0

    # Case 1: A fully discarded dimension must NEVER come out at 0%
    # WHY 0 would be wrong: "🚫 Not applicable" and "✅ Confirmed strength" share the
    # coefficient 0, so a fully discarded dimension displayed at 0% would pass for
    # the BEST rated in the report.
    total += 1
    try:
        criteria = [
            {"id": "1.1", "dimension": "🛖 1 — Product", "max_potential": 3.0, "answer": "🚫 Not applicable", "coefficient": 0},
            {"id": "1.2", "dimension": "🛖 1 — Product", "max_potential": 2.5, "answer": "🚫 Not applicable", "coefficient": 0},
        ]
        dimensions = compute_dimension_scores(criteria)
        dim = next((d for d in dimensions if d["name"] == "🛖 1 — Product"), None)

        if not dim:
            failures.append(("Fully discarded dimension", "dimension not found"))
        elif not dim["out_of_scope"]:
            failures.append(("Fully discarded dimension", f"out_of_scope should be True, got {dim['out_of_scope']}"))
        elif dim["optimization_potential_pct"] is not None:
            failures.append(("Fully discarded dimension", f"optimization_potential_pct should be None, got {dim['optimization_potential_pct']}"))
        elif dim["optimization_potential_pct"] == 0:
            failures.append(("Fully discarded dimension", "optimization_potential_pct is 0 (should be None) — WHY 0 IS WRONG: coefficient 0 = as good as a ✅ Confirmed strength"))
        elif dim["completeness_pct"] is not None:
            failures.append(("Fully discarded dimension", f"completeness_pct should be None, got {dim['completeness_pct']}"))
        elif dim["total"] != 0:
            failures.append(("Fully discarded dimension", f"total should be 0, got {dim['total']}"))
        elif dim["discarded"] != 2:
            failures.append(("Fully discarded dimension", f"discarded should be 2, got {dim['discarded']}"))
    except Exception as exc:
        failures.append(("Fully discarded dimension", f"Exception: {exc}"))

    # Case 2: Partially discarded dimension (discriminating numbers)
    # Choose numbers where the error would show: if the discarded ones were COUNTED,
    # the computation would be DIFFERENT.
    # Criteria: 2 discarded (max_potential 10 each), 2 kept (max_potential 5 each).
    # One kept criterion has coefficient 0.5, the other 0.2.
    # CORRECT kept potential: (0.5 * 5 + 0.2 * 5) / 10 = 3.5 / 10 = 35 %
    # WRONG potential (if discarded were counted): 3.5 / 30 = 11.67 %
    total += 1
    try:
        criteria = [
            {"id": "2.1", "dimension": "🗺️ 2 — Architecture", "max_potential": 10.0, "answer": "🚫 Not applicable", "coefficient": 0},
            {"id": "2.2", "dimension": "🗺️ 2 — Architecture", "max_potential": 10.0, "answer": "🚫 Not applicable", "coefficient": 0},
            {"id": "2.3", "dimension": "🗺️ 2 — Architecture", "max_potential": 5.0, "answer": "💡 Improvement potential identified", "coefficient": 0.5, "provenance": "collected"},
            {"id": "2.4", "dimension": "🗺️ 2 — Architecture", "max_potential": 5.0, "answer": "🤔 To be assessed", "coefficient": 0.2, "provenance": "estimated"},
        ]
        dimensions = compute_dimension_scores(criteria)
        dim = next((d for d in dimensions if d["name"] == "🗺️ 2 — Architecture"), None)

        expected = 35.0
        wrong_calc = 11.67
        if not dim:
            failures.append(("Partially discarded dimension", "dimension not found"))
        elif dim["optimization_potential_pct"] is None:
            failures.append(("Partially discarded dimension", "optimization_potential_pct is None (should be 35.0)"))
        elif abs(dim["optimization_potential_pct"] - expected) > 0.1:
            failures.append(("Partially discarded dimension", f"optimization_potential_pct expected {expected}%, got {dim['optimization_potential_pct']:.2f}% — WRONG computation would give {wrong_calc}%"))
        elif dim["total"] != 2:
            failures.append(("Partially discarded dimension", f"total should be 2 (kept), got {dim['total']}"))
        elif dim["discarded"] != 2:
            failures.append(("Partially discarded dimension", f"discarded should be 2, got {dim['discarded']}"))
        elif dim["completeness_pct"] is None:
            failures.append(("Partially discarded dimension", "completeness_pct is None (should be 100.0)"))
        elif abs(dim["completeness_pct"] - 100.0) > 0.1:
            failures.append(("Partially discarded dimension", f"completeness_pct should be 100%, got {dim['completeness_pct']:.2f}%"))
    except Exception as exc:
        failures.append(("Partially discarded dimension", f"Exception: {exc}"))

    # Case 3: total_criteria = kept, total_criteria + discarded_criteria = reference total
    total += 1
    try:
        criteria = [
            {"id": "3.1", "dimension": "🏢 3 — Infrastructure", "max_potential": 2.0, "answer": "✅ Confirmed strength", "coefficient": 0, "provenance": "collected"},
            {"id": "3.2", "dimension": "🏢 3 — Infrastructure", "max_potential": 2.0, "answer": "🚫 Not applicable", "coefficient": 0},
            {"id": "3.3", "dimension": "🏢 3 — Infrastructure", "max_potential": 2.0, "answer": None, "coefficient": None},
        ]
        dimensions = compute_dimension_scores(criteria)
        dim = next((d for d in dimensions if d["name"] == "🏢 3 — Infrastructure"), None)

        if not dim:
            failures.append(("total_criteria accounting", "dimension not found"))
        elif dim["total"] != 2:
            failures.append(("total_criteria accounting", f"total (kept) should be 2, got {dim['total']}"))
        elif dim["discarded"] != 1:
            failures.append(("total_criteria accounting", f"discarded should be 1, got {dim['discarded']}"))
        elif dim["total"] + dim["discarded"] != 3:
            failures.append(("total_criteria accounting", f"total + discarded should be 3 (reference total), got {dim['total'] + dim['discarded']}"))
    except Exception as exc:
        failures.append(("total_criteria accounting", f"Exception: {exc}"))

    # Case 4: No discarded criterion = same numbers as before session 26, discarded_criteria == 0
    total += 1
    try:
        criteria = [
            {"id": "4.1", "dimension": "💾 4 — Storage and data", "max_potential": 4.0, "answer": "💡 Improvement potential identified", "coefficient": 0.5, "provenance": "collected"},
            {"id": "4.2", "dimension": "💾 4 — Storage and data", "max_potential": 4.0, "answer": "✅ Confirmed strength", "coefficient": 0, "provenance": "collected"},
        ]
        dimensions = compute_dimension_scores(criteria)
        dim = next((d for d in dimensions if d["name"] == "💾 4 — Storage and data"), None)

        expected = 25.0  # (0.5 * 4) / 8 = 25%
        if not dim:
            failures.append(("No discarded criterion", "dimension not found"))
        elif dim["discarded"] != 0:
            failures.append(("No discarded criterion", f"discarded should be 0, got {dim['discarded']}"))
        elif dim["optimization_potential_pct"] is None:
            failures.append(("No discarded criterion", "optimization_potential_pct is None (should be 25.0)"))
        elif abs(dim["optimization_potential_pct"] - expected) > 0.1:
            failures.append(("No discarded criterion", f"optimization_potential_pct expected {expected}%, got {dim['optimization_potential_pct']:.2f}%"))
        elif dim["total"] != 2:
            failures.append(("No discarded criterion", f"total should be 2, got {dim['total']}"))
        elif dim["out_of_scope"]:
            failures.append(("No discarded criterion", f"out_of_scope should be False, got {dim['out_of_scope']}"))
    except Exception as exc:
        failures.append(("No discarded criterion", f"Exception: {exc}"))

    if failures:
        print(f"AUTOTEST FAILED: {len(failures)} case(s) out of {total}")
        for label, error in failures:
            print(f"  - {label}")
            print(f"      {error}")
        return 1

    print(f"Autotest: {total} cases passed.")
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source_dir", nargs="?")
    parser.add_argument("--domain", default=None, help="Short name used for eof-radar-<domain>.svg (derived from the directory otherwise)")
    parser.add_argument("--autotest", action="store_true", help="replays the embedded test cases and exits 1 if a case fails")
    args = parser.parse_args()

    if args.autotest:
        sys.exit(autotest())

    if not args.source_dir:
        parser.error("source_dir is required (or use --autotest)")

    source_dir = Path(args.source_dir).resolve()

    domain = args.domain or source_dir.name

    if not REFERENCE_PATH.exists():
        print(f"ERROR: reference not found ({REFERENCE_PATH}). Run the eof skill first.")
        sys.exit(1)
    reference = json.loads(REFERENCE_PATH.read_text(encoding="utf-8"))

    data = load_audit_data(source_dir)
    # Real data keys (excludes source_dir, which is always non-None)
    data_keys = ("env", "har", "coverage", "cwv", "headers", "wellknown", "htmlcss", "public_pages")
    if not any(data[k] for k in data_keys):
        print("⚠ No audit data found (env-data.json / har-analysis.json / coverage-analysis.json / "
              "cwv.json / security-headers-analysis.json / wellknown-scan.json / html-css-criteria.json / "
              "public-pages-criteria.json) — all criteria will stay 'I don't know'.")

    results = [evaluate_criterion(c, data) for c in reference["criteria"]]
    results_by_id = {r["id"]: r for r in results}
    dimensions = compute_dimension_scores(results)
    diag_overview = build_quick_diag_overview(reference, data)

    # Identify the discarded criteria (discarded-criterion convention, section 2)
    discarded_global = [r for r in results if r["answer"] == "🚫 Not applicable"]
    discarded_count = len(discarded_global)

    # Discarded criteria leave all denameinators (convention 2.1)
    kept_results = [r for r in results if r["answer"] != "🚫 Not applicable"]

    auto_answered = [r for r in kept_results if r["category"] == "automatable" and r["answer"] is not None]
    all_answered = [r for r in kept_results if r["answer"] is not None]
    partial_with_context = [r for r in kept_results if r["category"] == "partial" and r["context"] is not None]

    # Global computation: same formula as per dimension, applied to the KEPT criteria
    # (discarded criteria are removed from the denameinator, convention 2.1)
    total_max_potential_global = sum(r["max_potential"] for r in kept_results) or None
    optimization_potential_global_pct = (
        sum(r["coefficient"] * r["max_potential"] for r in all_answered) / total_max_potential_global * 100
        if total_max_potential_global else None
    )
    completeness_global_pct = len(all_answered) / len(kept_results) * 100 if kept_results else 0
    # Global count by provenance — same 5 provenances as in compute_dimension_scores(),
    # `assumed` included, otherwise an answer set in `assumed` would disappear from the count.
    answered_by_provenance = {"collected": 0, "estimated": 0, "declared": 0, "stated": 0, "assumed": 0}
    for r in all_answered:
        prov = r.get("provenance")
        if prov in answered_by_provenance:
            answered_by_provenance[prov] += 1

    # A single timestamp for both artifacts: the lot file and the audit summary
    # come out of the same pass, two different instants would suggest the opposite.
    generated_at = datetime.now(timezone.utc).isoformat()

    audit_results = {
        "generated_at": generated_at,
        "domain": domain,
        "total_criteria": len(kept_results),
        "answered_criteria": len(all_answered),
        "discarded_criteria": discarded_count,
        "criteria_with_partial_evidence": len(partial_with_context),
        "global_completeness_pct": completeness_global_pct,
        "global_optimization_potential_pct": optimization_potential_global_pct,
        "answered_by_provenance": answered_by_provenance,
        "dimensions": dimensions,
        "quick_diag_overview": {
            "total_questions": len(reference["quick_diagnostic"]),
            "note": (
                "1 to 5 scale, never filled automatically — to be assessed by a human. "
                "Exception: 0.16 (exact duplicate of 3.3), cf. eof-question-minimization-analysis.md."
            ),
            "questions": diag_overview,
        },
        "criteria": results,
    }

    results_path = source_dir / "eof-audit-results.json"
    results_path.write_text(json.dumps(audit_results, ensure_ascii=False, indent=2), encoding="utf-8")

    # Two-layer radar, built from the audit result itself and not
    # from this script's local variables: it is the same entry point as
    # that of `process/merge_lots.py`, the other producer of the same file.
    # Both already had twin arithmetics; leaving them two ways
    # to draw guaranteed that one day one would show something different from the other.
    radar_path = source_dir / f"eof-radar-{domain}.svg"
    radar_path.write_text(build_radar_from_results(audit_results, domain), encoding="utf-8")

    md_text = build_eof_filled_md(reference, results_by_id, dimensions, diag_overview)
    md_path = source_dir / "eof-filled.md"
    md_path.write_text(md_text, encoding="utf-8")

    lot_output = build_lot_output(results, diag_overview, data["loaded_files"], generated_at)
    lot_dir = source_dir / "lots"
    lot_dir.mkdir(parents=True, exist_ok=True)
    lot_path = lot_dir / f"{LOT_ID}.json"
    lot_path.write_text(json.dumps(lot_output, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"eof-audit-results.json written: {results_path}")
    print(f"eof-filled.md written: {md_path}")
    print(f"eof-radar-{domain}.svg written: {radar_path}")
    print(f"lots/{LOT_ID}.json written: {lot_path} ({len(lot_output['criteria'])} criteria)")
    # The potential is reported against ALL criteria, not only the answered ones: without
    # the completeness displayed right next to it, a low figure reads as a mature service
    # when it only says "we hardly looked at anything".
    print(f"Automatically answered criteria: {len(auto_answered)}/{len(reference['criteria'])}"
          f" (completeness {completeness_global_pct:.1f} %)"
          + (f" — global optimization potential, reported against the {len(reference['criteria'])} criteria:"
             f" {optimization_potential_global_pct:.2f} %" if optimization_potential_global_pct is not None else ""))


if __name__ == "__main__":
    main()
