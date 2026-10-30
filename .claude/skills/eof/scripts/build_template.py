#!/usr/bin/env python3
"""Builds the blank Markdown template of the EOF-V.1.1 reference framework (EROOM
Optimization Framework) from the raw data fetched via gviz
(one JSON file per tab, cf. fetch_gviz.py).

This script does NO optimization-potential calculation: the template it produces is
blank (all checkboxes unchecked). Only the calculation method is documented in
text, so that the file remains self-sufficient and can be recalculated by hand
later (cf. the "How to read this framework" section at the top of the document).

Usage:
    python3 build_template.py <json_dir> <output_markdown_file>
"""
import json
import re
import sys
import os

PILLAR_TABS = [
    ("product", "🛖 1 — Product"),
    ("architecture", "🗺️ 2 — Architecture"),
    ("infrastructure", "🏢 3 — Infrastructure"),
    ("storage", "💾 4 — Storage and data"),
    ("algo-code", "👨‍💻 5 — Algorithms & code"),
    ("ease", "🛠 6 — Ease of change"),
]

# READ order of the blank template (table of contents + body), distinct from
# PILLAR_TABS above: 0 - Quick diagnostic (first, outside the list) → 6 -
# Ease of change first (practical prerequisite: is it even possible to act?)
# → then 1,2,3,4,5 in the framework's order. Applies only to this human-facing
# output file: PILLAR_TABS and build_referentiel_json() keep the canonical
# 1..6 order (consumed by run_eof.py on the eof-audit/analyse-parcours side,
# outside the scope of this change).
PILLAR_TABS_TEMPLATE_ORDER = [PILLAR_TABS[5]] + PILLAR_TABS[0:5]

# Dropdown observed on the dimension tabs (5 values, cf. empirical survey
# over the 6 tabs). Observed numeric mapping (coefficient before weighting by
# the potential maximum):
#   ✅ Confirmed strength              -> 0  (nothing to optimize)
#   💡 Improvement potential identified -> 1  (lever identified)
#   🚫 Not applicable                   -> 0  (excluded, still counts in the total potential maximum)
#   🤔 To be assessed                   -> 0  (not looked at yet)
#   ⌛️ Assessment in progress           -> 0.5 (ONE single occurrence observed in
#                                              the whole workbook at generation
#                                              time, to be confirmed if the case
#                                              comes up again, not yet a certain
#                                              rule)
PILLAR_EVAL_OPTIONS = [
    ("✅ Confirmed strength", 0),
    ("💡 Improvement potential identified", 1),
    ("🚫 Not applicable", 0),
    ("🤔 To be assessed", 0),
    ("⌛️ Assessment in progress", 0.5),
]

# Tab 6 (Ease of change) only: a DIFFERENT dropdown from the 5 other
# dimensions, confirmed by the "Read me" tab text (Step 6). Numeric mapping
# not observed in real cells (tab still empty at generation time), to be
# confirmed the day answers exist.
FACILITE_EVAL_OPTIONS = [
    ("🟢 Easy to change", 0),
    ("🟡 Moderate effort", 0.5),
    ("🔴 Hard to change", 1),
]

QUICK_DIAG_LEVELS = ["Moderate", "Significant", "Decisive"]

# 3 hyperlinks of the source Sheet (retrieved from the relations of the
# provided Excel file, because the gviz API only returns the displayed text,
# not the link target). The exact cell coordinates have moved since then
# (criteria were added) — so we link the FIRST occurrence of the word in the
# relevant tab, which achieves the same goal (making the term navigable)
# without depending on a cell reference that has become obsolete.
TAB_HYPERLINKS = {
    "quick-diag": ("SLA", "https://fr.wikipedia.org/wiki/Service-level_agreement"),
    "algo-code": ("Core Web Vitals", "https://developers.google.com/search/docs/appearance/core-web-vitals?hl=fr"),
    "ease": ("CI/CD", "https://fr.wikipedia.org/wiki/CI/CD"),
}


def apply_hyperlink(text, tab_name):
    if tab_name not in TAB_HYPERLINKS:
        return text
    word, url = TAB_HYPERLINKS[tab_name]
    pattern = re.compile(re.escape(word))
    return pattern.sub(f"[{word}]({url})", text, count=1)


def load_tab(json_dir, name):
    raw = open(os.path.join(json_dir, f"{name}.json"), encoding="utf-8").read()
    m = re.search(r"setResponse\((.*)\);?\s*$", raw, re.S)
    return json.loads(m.group(1))["table"]["rows"]


def cell(row, idx):
    if idx >= len(row["c"]) or row["c"][idx] is None:
        return None
    c = row["c"][idx]
    v = c.get("f", c.get("v"))
    if isinstance(v, str):
        v = v.strip()
    return v if v not in ("", None) else None


def is_id(v):
    return bool(v) and re.match(r"^\d+\.\d+$", str(v))


def checklist(options, checked=None):
    lines = []
    for opt in options:
        mark = "x" if opt == checked else " "
        lines.append(f"- [{mark}] {opt}")
    return "\n".join(lines)


def build_diag_rapide(json_dir):
    rows = load_tab(json_dir, "quick-diag")
    out = ["## 🏦 0 — Quick diagnostic\n"]
    out.append(
        "*Identify the best optimization opportunities. A higher score reflects "
        "greater optimization potential.*\n"
    )
    for r in rows:
        crit_id = cell(r, 1)
        if not is_id(crit_id):
            continue
        criterion = cell(r, 2)
        method = cell(r, 4)  # text of the 5 levels, enumerated "1 - ... \n2 - ..."
        level = cell(r, 5)
        out.append(f"### {crit_id} — {criterion}\n")
        out.append("**Evaluation**")
        if method:
            screens = [c.strip() for c in method.split("\n") if c.strip()]
            for c in screens:
                out.append(f"- [ ] {c}")
        out.append("")
        out.append("**Impact level**")
        out.append(checklist(QUICK_DIAG_LEVELS, checked=level))
        out.append("")
    return "\n".join(out)


def build_pillar(json_dir, tab_name, title):
    rows = load_tab(json_dir, tab_name)
    eval_options = FACILITE_EVAL_OPTIONS if tab_name == "ease" else PILLAR_EVAL_OPTIONS
    out = [f"## {title}\n"]
    # row 1 (index 1 in the rows) carries the short description of the dimension
    if len(rows) > 1:
        desc = cell(rows[1], 2)
        if desc:
            out.append(f"*{desc}*\n")
    for r in rows:
        crit_id = cell(r, 1)
        if not is_id(crit_id):
            continue
        criterion = cell(r, 2)
        explanation = cell(r, 3)
        level = cell(r, 6)
        out.append(f"### {crit_id} — {criterion}\n")
        if explanation:
            out.append(f"**Additional explanation**: {explanation}\n")
        out.append("**Evaluation**")
        out.append(checklist([o for o, _ in eval_options]))
        out.append("")
        out.append("**Impact level**")
        out.append(checklist(QUICK_DIAG_LEVELS, checked=level))
        out.append("")
    return "\n".join(out)


def parse_potential_max(v):
    if v is None:
        return None
    return float(str(v).replace(",", "."))


def build_diag_rapide_json(json_dir):
    """Structured list of the 16 questions of the 0-Quick diagnostic tab,
    for preview display (topo) only — a 1-5 scale different from the
    6 detailed dimensions, never filled automatically by `eof-audit`,
    never mixed into the `criteria` list (54) nor into its radar."""
    rows = load_tab(json_dir, "quick-diag")
    out = []
    for r in rows:
        crit_id = cell(r, 1)
        if not is_id(crit_id):
            continue
        method = cell(r, 4)
        screens = [c.strip() for c in method.split("\n") if c.strip()] if method else []
        out.append({
            "id": crit_id,
            "criterion": cell(r, 2),
            "screens": screens,
            "impact_level": cell(r, 5),
        })
    return out


def build_referentiel_json(json_dir):
    """Builds the structured table of the reference framework:
    - `criteria`: the 54 detailed criteria (6 dimensions), the ones
      `eof-audit` reads to fill in automatically and compute the radar.
    - `quick_diagnostic`: the 16 questions of tab 0, for an overview
      only (different scale, never filled automatically — cf.
      the "How to read this framework" section).
    This file, and only this file, is what the future `eof-audit` process
    must read: never the Google Sheet, never the human-readable Markdown.
    """
    criteria = []
    for key, title in PILLAR_TABS:
        rows = load_tab(json_dir, key)
        eval_options = FACILITE_EVAL_OPTIONS if key == "ease" else PILLAR_EVAL_OPTIONS
        for r in rows:
            crit_id = cell(r, 1)
            if not is_id(crit_id):
                continue
            criteria.append({
                "id": crit_id,
                "pillar": title,
                "criterion": cell(r, 2),
                "explanation": cell(r, 3),
                "method": cell(r, 5),
                "impact_level": cell(r, 6),
                "max_potential": parse_potential_max(cell(r, 9)),
                "evaluation_options": [o for o, _ in eval_options],
                "evaluation_coefficient_options": {o: s for o, s in eval_options},
            })
    return {"criteria": criteria, "quick_diagnostic": build_diag_rapide_json(json_dir)}


def build_a_lire(json_dir):
    rows = load_tab(json_dir, "read-me")
    out = ["## 📖 Read me\n"]
    out.append("![Logo Boavizta](logo1.png) ![Licence CC BY-SA](logo2.png)\n")
    out.append(
        "> ⚠️ The Boavizta logo (`logo1.png`) is white on a transparent background: "
        "it does not show on a white-background Markdown render (GitHub, VS Code, "
        "most viewers). Only visible on a dark background, or when opening the file "
        "directly. Not fixed here (graphic retouching out of scope) — flagged so it "
        "is not mistaken for a missing image.\n"
    )
    for r in rows:
        text = cell(r, 1)
        if text:
            if text.startswith(("🎯", "📊", "🧮", "💡")) and len(text) < 60:
                out.append(f"### {text}\n")
            else:
                out.append(f"{text}\n")
    return "\n".join(out)


def build_synthese(json_dir, criteria_counts):
    categories = [
        "🛖 Product", "🗺️ Architecture", "🏢 Infrastructure",
        "💾 Storage & Data", "👨‍💻 Algo & Code", "🛠 Ease of change",
    ]
    total = sum(criteria_counts.values())
    out = ["## 🕸️ 7 — Synthesis\n"]
    out.append(
        "This framework counts **{} detailed criteria** in total, spread over "
        "the 6 dimensions below (excluding the Quick diagnostic, which covers them in "
        "condensed form but is not part of this synthesis).\n".format(total)
    )
    out.append("| Category | Number of criteria | Link |")
    out.append("|---|---|---|")
    keys = ["product", "architecture", "infrastructure", "storage", "algo-code", "ease"]
    for cat, key in zip(categories, keys):
        anchor = cat.split(" ", 1)[1].lower().replace(" ", "-").replace("&", "")
        out.append(f"| {cat} | {criteria_counts[key]} | [See the section](#{anchor}) |")
    out.append("")
    out.append(
        "**Note on the source Sheet's total.** The Google Sheets formula that "
        "counts the total number of criteria references tabs that no longer "
        "exist (`#REF!` + old tab names) — its displayed value is frozen and "
        "wrong. The total above ({}) is recomputed directly from the current "
        "data, one by one.\n".format(total)
    )
    out.append(
        "**Radar.** The source Sheet displays a 6-axis radar which, on inspection, "
        "only draws 5 of them: the *Ease of change* category is missing from the "
        "chart (bug observed, not a deliberate exclusion). As long as this template "
        "is blank, no real radar makes sense here; a rendering example (fictitious "
        "optimization potentials, 6 axes) is available via "
        "`.claude/skills/eof/scripts/generate_radar_svg.py`.\n"
    )
    out.append("### How to read this framework\n")
    out.append(
        "- **Dimensions 1 to 5 (Product, Architecture, Infrastructure, Storage, "
        "Algo & Code)**: each criterion is answered by a single choice among 5 "
        "(`✅ Confirmed strength`, `💡 Improvement potential identified`, "
        "`🚫 Not applicable`, `🤔 To be assessed`, `⌛️ Assessment in progress`), by "
        "checking the corresponding box. Coefficient observed on the source "
        "Sheet: `✅`/`🚫`/`🤔`/empty = 0, `💡` = 1, `⌛️` = 0.5 (this last "
        "value was observed only once in the whole workbook at generation "
        "time, to be confirmed if it occurs elsewhere, it is not yet a certain "
        "rule).\n"
        "- **Dimension 6 (Ease of change)**: a **different** dropdown from the 5 "
        "other dimensions (confirmed by the source Sheet's \"Read me\" tab): "
        "`🟢 Easy to change`, `🟡 Moderate effort`, `🔴 Hard to change`. "
        "No real answer existed on this tab at generation time, so the numeric "
        "mapping (0 / 0.5 / 1 used here) is an assumption by analogy with the "
        "other dimensions, **not verified** on real data.\n"
        "- **Optimization potential of a dimension** = "
        "`Σ (coefficient of the answer × potential maximum of the criterion)` "
        "÷ `Σ (potential maximum of ALL the criteria of the dimension, answered or not)`. "
        "**An unanswered criterion counts 0 in the numerator but its maximum stays "
        "in the denameinator**, so it never penalizes the optimization potential, and a blank "
        "dimension shows 0% optimization potential, not \"unknown\". "
        "This is a methodological bias of the source Sheet, not a correction "
        "made here.\n"
        "- **\"Not applicable\" potential maximum**: the \"Read me\" tab says a criterion can be "
        "excluded entirely by setting its potential maximum to \"Not "
        "applicable\" (not just answering \"Not applicable\" to the evaluation, which "
        "still counts the maximum in the denameinator). No real example of "
        "this setting was observed in the fetched data; the mechanism is "
        "documented here as described by the Sheet, not verified on a concrete "
        "case.\n"
        "- **Tab 0 (Quick diagnostic)**: different logic, a 1-to-5 scale "
        "per criterion (`(5 − answer) ÷ 4 × potential maximum`), does not contribute to this "
        "synthesis table.\n"
        "- **Potential maximum**: each criterion carries its own potential maximum "
        "(visible in the source Sheet, corresponding column), different from one criterion to another, "
        "it is never 1 everywhere.\n"
    )
    return "\n".join(out)


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 build_template.py <json_dir> <output_file.md>")
        sys.exit(1)
    json_dir, out_path = sys.argv[1], sys.argv[2]

    criteria_counts = {}
    for key, _ in PILLAR_TABS:
        rows = load_tab(json_dir, key)
        criteria_counts[key] = sum(1 for r in rows if is_id(cell(r, 1)))

    parts = []
    parts.append("# EOF-V.1.1 (EROOM Optimization Framework) — Full reference\n")
    parts.append(
        "> Generated from the source Google Sheet: "
        "https://docs.google.com/spreadsheets/d/1zJkT_5Ck9WKyxHZ7Uf5f03PmsaLh_SUB7LzKToPlcZ0/edit\n"
        ">\n"
        "> **Blank template** — no answer is pre-filled. The Excel file provided "
        "as a complement was only used for two things that the Sheet's data "
        "API does not provide: the 2 logos of the \"Read me\" section and 3 hyperlink URLs "
        "(see where relevant).\n"
    )
    toc_items = [
        ("Read me", "read-me"),
        ("0 — Quick diagnostic", "0--quick-diagnostic"),
    ]
    for key, title in PILLAR_TABS_TEMPLATE_ORDER:
        anchor = title.lower()
        anchor = re.sub(r"[^\w\s-]", "", anchor).strip().replace(" ", "-")
        toc_items.append((title, anchor))
    toc_items.append(("Synthesis", "🕸️-7--synthesis".lower()))

    parts.append("## Contents\n")
    for label, anchor in toc_items:
        parts.append(f"- [{label}](#{anchor})")
    parts.append("")

    parts.append(build_a_lire(json_dir))
    parts.append("\n-----\n")
    parts.append(apply_hyperlink(build_diag_rapide(json_dir), "quick-diag"))
    parts.append("\n-----\n")
    for key, title in PILLAR_TABS_TEMPLATE_ORDER:
        parts.append(apply_hyperlink(build_pillar(json_dir, key, title), key))
        parts.append("\n-----\n")
    parts.append(build_synthese(json_dir, criteria_counts))

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(parts))

    reference = build_referentiel_json(json_dir)
    referentiel_path = os.path.join(os.path.dirname(out_path) or ".", "eof-reference.json")
    with open(referentiel_path, "w", encoding="utf-8") as f:
        json.dump(reference, f, ensure_ascii=False, indent=2)

    print(f"Template written: {out_path}")
    print(
        f"Structured reference written: {referentiel_path} "
        f"({len(reference['criteria'])} detailed criteria + "
        f"{len(reference['quick_diagnostic'])} quick-diagnostic questions)"
    )
    print("Criteria per dimension:", criteria_counts, "total =", sum(criteria_counts.values()))


if __name__ == "__main__":
    main()
