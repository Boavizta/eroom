-----
Project skills tree (registry + recalculation)
-----

This file plays, for the skills tree, the same role as
`diagrammes-analyse-parcours/SKILL.md` for the diagrams: it is a REGISTRY.
It describes what is measured, the source of truth, and above all the RECALCULATION
COMMAND. The tree below is a snapshot; it can be recalculated at any time (section
"Recalculate"), so never adjust it by hand without rerunning the command.

Units: sizes in kilobytes (KB) for all files. The line count is only shown for Markdown
files (`.md`), where it reflects the reading effort; it is NOT shown for other types
(`.py`, `.sh`, `.json`, `.gitignore`), where only the size in KB matters.


-----
1. Registry
-----

| What is measured | Location | Source of truth | Recalculate if... |
|-------------------|-------------|------------------|------------------|
| Project skills | `<project>/.claude/skills/` | the files themselves | a skill/step/script is added, or a notable edit |

`<project>` = `~/Documents/missions/MyAIEnv/Agent EROOM`.

Scope: this registry covers **only the project skills**. Global skills
(`~/.claude/skills/`) are out of scope: they are shared across all projects and
are not part of this repository.

Exclusions: `__pycache__/` (regenerated Python cache) and `.DS_Store` (macOS metadata).


-----
2. Recalculate (single command, pure Bash)
-----

List each project skill file with its size in KB and its line count, with a total. Rerun it,
then report the result in the tree of section 3.

```bash
ROOT="$HOME/Documents/missions/MyAIEnv/Agent EROOM/.claude/skills"
find "$ROOT" -type f -not -path '*__pycache__*' -not -name '.DS_Store' -print0 \
| sort -z | while IFS= read -r -d '' f; do
    b=$(wc -c <"$f"); l=$(wc -l <"$f")
    awk -v b="$b" -v l="$l" -v f="$f" 'BEGIN{printf "%8.1f KB  %6d lines  %s\n", b/1024, l, f}'
  done
# project total
find "$ROOT" -type f -not -path '*__pycache__*' -not -name '.DS_Store' -print0 \
| xargs -0 wc -c | tail -1 \
| awk '{printf "  -> project total: %.1f KB\n", $1/1024}'
```

Reading notes for the result:
- The "lines" column is only kept, in the tree, for `.md` files.
- For a non-Markdown file (`.py`, `.sh`, `.json`, `.gitignore`), keep only the KB.
- A file under ~0.05 KB (e.g. `.gitignore`) displays "0.0 KB": still note it in KB,
  it is not an error.


-----
3. Reference tree (snapshot)
-----

Last recalculation: 2026-07-30.

Convention: `.md` → `KB · N lines` ; other types → `KB` only.

```
PROJECT SKILLS  (Agent EROOM/.claude/skills/)
│
├── analyse-parcours/
│   ├── SKILL.md ......................... 6.7 KB · 218 lines
│   ├── skill-steps/                       [all .md]
│   │   ├── 10_location.md .......... 2.0 KB ·  54 lines
│   │   ├── 20_har-analysis.md ........... 0.8 KB ·  20 lines
│   │   ├── 25_dispatch-orchestration.md  5.3 KB · 160 lines
│   │   ├── 30_coverage-analysis.md ...... 2.3 KB ·  91 lines
│   │   ├── 35_ecoindex-calculation.md ....... 2.2 KB ·  56 lines
│   │   ├── 37_lighthouse.md ............ 3.9 KB · 113 lines
│   │   ├── 40_report.md ............... 1.8 KB ·  54 lines
│   │   └── 45_efootprint.md ........... 22.1 KB · 473 lines
│   ├── docs/
│   │   └── capture-har-and-coverage.md . 8.6 KB · 231 lines
│   └── scripts/                           [code + config: KB only]
│       ├── generate_report_html.py ... 136.5 KB  ⚠️ the largest (~37% of the total)
│       ├── collect_env_data.py ........ 61.4 KB
│       ├── run_efootprint.py .......... 27.9 KB
│       ├── detect_tech.py ............. 18.7 KB
│       ├── similarweb_api.py .......... 13.1 KB
│       ├── collect_cwv_pagespeed.py ... 12.5 KB
│       ├── har_metrics.py ............. 6.3 KB
│       ├── run_lighthouse.sh .......... 4.6 KB
│       ├── README-tools.md ........... 2.2 KB · 68 lines   (.md)
│       ├── package.json ............... 0.2 KB
│       └── .gitignore ................. 0.0 KB
│                     └─ analyse-parcours subtotal: 339.3 KB
│
└── diagrammes-analyse-parcours/SKILL.md . 25.6 KB · 737 lines

TOTAL project: 364.9 KB  (excluding __pycache__ and .DS_Store)
```


-----
4. Reading: how the skills fit together
-----

Two project skills.

- `analyse-parcours`: the main skill. It has a `skill-steps/` folder (steps 10 to 45)
  and a `scripts/` folder (the Python/Bash tools). It is the one that produces the HTML report.
  Step 45 (`skill-steps/45_efootprint.md`) carries the CO2e calculation (ex-`efootprint`
  skill, merged on 2026-07-30: it had no script of its own and depended entirely on
  analyse-parcours' scripts and data, it did not deserve to be a separate skill).
- `diagrammes-analyse-parcours`: tool skill that generates the analyse-parcours PlantUML diagrams.

At step 40, `generate_report_html.py` DISPLAYS a CO2e section if an
`efootprint-python-summary.json` already exists; it does not TRIGGER it (step 45 remains
optional, invoked via `/efootprint`).
See also `documentation/implementation/` for the script details.
