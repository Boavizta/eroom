#!/usr/bin/env python3
"""
EOF key consistency validator between producers and consumers.

WHY THIS SCRIPT EXISTS
-----------------------
Two scripts write the same eof-audit-results.json file, two others read it back
to build the deliverables. If the two producers do not write the SAME key
names, the deliverable shows blanks depending on which of the two produced the
file.

Real incident: merge_lots.py wrote "answered_criteria" while run_eof.py still
wrote "auto_answered_criteria", and the report KPI displayed 0/54 instead of
the real number.

The invariant holds today but NO test protects it. This validator is that
safety net.

WHAT IT CHECKS
--------------
1. Canonical keys are written by BOTH producers
2. Each canonical key is read by AT LEAST ONE of the consumers. There are two:
   the HTML report and the radar generator. A key read by only one of them is
   covered: they do not show the same things and do not have to read the same data.
3. No dead name is WRITTEN by a producer (write/read distinction)
4. No invented key name (potential_* / completeness_* / criteria_* families)

Write/read distinction (check 3):
  - Consumers (generate_report_html.py, generate_radar_svg.py) have the RIGHT to
    READ the old names as a fallback so that already-produced audits keep
    displaying.
  - Producers (run_eof.py, merge_lots.py) must NEVER WRITE those old names.
  - Method chosen: search for string literals in dict-assignment contexts
    (quoted keys in the code). This approach catches explicit key writes, which
    are the dominant case in these scripts. It does not cover cases where the
    key would be built dynamically or passed through a variable, but these
    patterns do not exist in the two producers (manual check done). The
    alternative (full AST) would be more robust but complex and fragile to
    structural changes in the code.

Usage:
    python3 validate_key_consistency.py [--test-dir <broken-copies-dir>]

    Without argument: checks the real repo state
    With --test-dir: points at modified copies for negative testing

Exit code: 0 if conforming, 1 otherwise.

Shared contract between run_eof.py and merge_lots.py (authoritative list:
CANONICAL_KEYS, further down in this file):
  - global_completeness_pct
  - completeness_pct (per dimension)
  - answered_criteria
  - total_criteria (the KEPT criteria, discarded ones subtracted)
  - discarded_criteria (out-of-scope criteria, cf. discarded-criterion-convention.md)
  - global_optimization_potential_pct
  - optimization_potential_pct (per dimension)
  - answered_by_provenance (read by the radar since job 13, plus by exemption)
  - provenance (per criterion and per diagnostic question, not at the root)
"""

import argparse
import ast
import re
import sys
from pathlib import Path

# Path resolution relative to the validator's location
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Default paths (real repo state)
DEFAULT_PATHS = {
    "run_eof": PROJECT_ROOT / ".claude/skills/analyse-parcours/scripts/run_eof.py",
    "merge_lots": PROJECT_ROOT / "process/merge_lots.py",
    "generate_report": PROJECT_ROOT / ".claude/skills/analyse-parcours/scripts/generate_report_html.py",
    "generate_radar": PROJECT_ROOT / ".claude/skills/eof/scripts/generate_radar_svg.py",
}

# The canonical keys that both producers must write identically
# (shared contract referenced in memory/project_eof_deux_producteurs_un_contrat.md)
CANONICAL_KEYS = {
    "global_completeness_pct",
    "completeness_pct",
    "answered_criteria",
    "total_criteria",
    "discarded_criteria",
    "global_optimization_potential_pct",
    "optimization_potential_pct",
    "answered_by_provenance",
    # Carried by each criterion and each diagnostic question, not by the root.
    # Added after a real incident: the producers were already writing `provenance`
    # while the report still read `confidence`. Result: a dash instead of each badge,
    # and a hard crash (KeyError) as soon as a diagnostic question carried an answer.
    # No check caught it.
    "provenance",
}

# Dead names: old names that must NO LONGER be WRITTEN by producers
# (the consumer may READ them as a fallback, but producers must not WRITE them)
DEAD_NAMES = {
    "score_pct",
    "auto_answered_criteria",
    "weighted_score",
    "options_evaluation_score",
    "confidence",
    "evidence_nature",
    "allowed_evidences",
    "potential_pct",
    "auto_declared_public",
    "qcm_declared",
}

# Produced keys not yet consumed: EXPLICIT and TEMPORARY exemption from
# check 2 (read by a consumer). They must still be written identically by both
# producers; check 1 still applies to them.
#
# EMPTY since job 13: `answered_by_provenance` was there, waiting for the
# two-layer radar. The radar exists and reads the key to write the per-provenance
# breakdown under the figure, so check 2 became blocking on it again, which was
# the goal. Only ever fill this set for a key whose consumer is not written yet,
# never to silence a violation.
PRODUCED_KEYS_NOT_YET_READ = set()

# Watched key families to detect invented keys
KEY_FAMILIES = ["potential_", "completeness_", "criteria_"]


def extract_written_keys(source, filepath):
    """Extract the dictionary keys written in the source code.

    Returns a set of (key, line_number) for each string literal used as a key
    in a dict assignment.

    This string-literal approach catches explicit key writes, which are the
    dominant case in run_eof.py and merge_lots.py. It does not cover dynamic
    key constructions, but these patterns do not exist in these scripts
    (manual check done).
    """
    written = set()
    try:
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError as exc:
        return {("PARSE_ERROR", exc.lineno or 0)}

    for node in ast.walk(tree):
        # Pattern 1: {"key": value} in a dict literal
        if isinstance(node, ast.Dict):
            for key_node in node.keys:
                if isinstance(key_node, ast.Constant) and isinstance(key_node.value, str):
                    written.add((key_node.value, key_node.lineno))

        # Pattern 2: dict["key"] = value or dict.update({"key": value})
        # Captured by ast.Dict above for literals

    return written


def extract_read_keys(source, filepath):
    """Extract the dictionary keys read in the source code.

    Returns a set of (key, line_number) for each string literal used in
    .get("key") or ["key"].
    """
    read = set()
    try:
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError as exc:
        return {("PARSE_ERROR", exc.lineno or 0)}

    for node in ast.walk(tree):
        # Pattern 1: .get("key") or .get("key", default)
        if isinstance(node, ast.Call):
            if (isinstance(node.func, ast.Attribute) and
                node.func.attr == "get" and
                node.args and
                isinstance(node.args[0], ast.Constant) and
                isinstance(node.args[0].value, str)):
                read.add((node.args[0].value, node.func.lineno))

        # Pattern 2: dict["key"]
        elif isinstance(node, ast.Subscript):
            if (isinstance(node.slice, ast.Constant) and
                isinstance(node.slice.value, str)):
                read.add((node.slice.value, node.lineno))

    return read


def check_canonical_keys_written(written_keys, producer_name):
    """Check that all canonical keys are written by the producer.

    Returns a list of violations (missing keys).
    """
    violations = []
    written_key_names = {key for key, lineno in written_keys if key != "PARSE_ERROR"}

    for key in CANONICAL_KEYS:
        if key not in written_key_names:
            violations.append(f"{producer_name}: canonical key missing '{key}'")

    return violations


def check_canonical_keys_read(read_keys_by_consumer):
    """Check that each canonical key is read by at least one consumer.

    `read_keys_by_consumer`: dict {file_name: keys read}.

    A key read by ONE consumer is covered. Requiring each to read everything
    would be wrong: the HTML report and the radar do not show the same thing.
    What the check forbids is a key written by the producers being read by
    NOBODY, the case where a rename goes unnoticed until the deliverable.

    Keys in PRODUCED_KEYS_NOT_YET_READ are exempted, but the exemption is
    displayed: it must stay visible so it can be lifted one day, not become an
    installed silence.

    Returns a pair (violations, reminders).
    """
    violations = []
    reminders = []
    read_by = {}
    for name, read_keys in read_keys_by_consumer.items():
        for key, _lineno in read_keys:
            if key != "PARSE_ERROR":
                read_by.setdefault(key, []).append(name)

    consumers = ", ".join(read_keys_by_consumer)
    for key in sorted(CANONICAL_KEYS):
        if key in read_by:
            continue
        if key in PRODUCED_KEYS_NOT_YET_READ:
            reminders.append(
                f"key '{key}' produced but read by no consumer "
                f"(explicit exemption, cf. PRODUCED_KEYS_NOT_YET_READ)"
            )
        else:
            violations.append(
                f"canonical key '{key}' read by no consumer ({consumers})"
            )

    return violations, reminders


def check_dead_names_written(written_keys, producer_name):
    """Check that no dead name is written by the producer.

    EXEMPTIONS: some occurrences are legitimate and are not in the EOF
    perimeter (ex. score_pct of a third-party tool in run_eof.py line ~403).
    These exemptions are filtered by an explicit list.

    Returns a list of violations.
    """
    violations = []

    # Explicit exemptions: (file_name, key, approximate_line_number)
    # These occurrences are legitimate (non-EOF) and must not be flagged.
    exemptions = {
        ("run_eof.py", "score_pct", 403),  # security-headers score of a third-party tool
    }

    for key, lineno in written_keys:
        if key == "PARSE_ERROR":
            continue
        if key in DEAD_NAMES:
            # Check whether it is an exemption
            file_name = producer_name.split()[0]  # Extract the file name
            is_exempt = any(
                file_name.endswith(ex_file) and key == ex_key and abs(lineno - ex_line) < 5
                for ex_file, ex_key, ex_line in exemptions
            )
            if not is_exempt:
                violations.append(
                    f"{producer_name} line {lineno}: dead name WRITTEN '{key}' "
                    f"(obsolete vocabulary, must no longer be written)"
                )

    return violations


def check_invented_keys(written_keys, producer_name):
    """Check that no invented key is written by the producer.

    An invented key is a key of the potential_* / completeness_* / criteria_*
    family that is neither in the canonical list nor in the allowed extensions.

    Returns a list of violations.
    """
    violations = []
    written_key_names = {key for key, lineno in written_keys if key != "PARSE_ERROR"}

    for key, lineno in written_keys:
        if key == "PARSE_ERROR":
            continue
        for family in KEY_FAMILIES:
            if key.startswith(family) and key not in CANONICAL_KEYS:
                # Keys allowed outside the canonical ones:
                # - criteria_with_partial_evidence: in the merged output contract
                # - max_potential: added by merge_lots.py from the reference (cf. line 36 docstring)
                # - retained_potential, total_potential: internal calculation variables
                # - discarded, out_of_scope: new keys of the discarded-criterion contract (convention section 3.2)
                allowed_extra = {
                    "criteria_with_partial_evidence",
                    "max_potential",
                    "retained_potential",
                    "total_potential",
                    "discarded",
                    "out_of_scope",
                }
                if key not in allowed_extra:
                    violations.append(
                        f"{producer_name} line {lineno}: invented key '{key}' "
                        f"(family {family}*, non-canonical)"
                    )

    return violations


def main():
    parser = argparse.ArgumentParser(
        description="Validate EOF key consistency between producers and consumers. "
                    "Reject any naming divergence that would display blanks in the report."
    )
    parser.add_argument("--test-dir", type=Path,
                        help="Directory containing modified copies for negative testing. "
                             "If absent, checks the real repo state.")
    args = parser.parse_args()

    # Determine the paths to check
    if args.test_dir:
        paths = {
            "run_eof": args.test_dir / "run_eof.py",
            "merge_lots": args.test_dir / "merge_lots.py",
            "generate_report": args.test_dir / "generate_report_html.py",
            "generate_radar": args.test_dir / "generate_radar_svg.py",
        }
        # In negative testing, only the file we want to break is copied. A
        # consumer absent from the test directory is taken from the real repo
        # state: otherwise the test could only target one file at a time.
        for name, path in paths.items():
            if not path.exists():
                paths[name] = DEFAULT_PATHS[name]
    else:
        paths = DEFAULT_PATHS

    # Check that all files exist
    for name, path in paths.items():
        if not path.exists():
            print(f"[error] File not found: {path}")
            return 1

    print("-" * 70)
    print("  EOF KEY CONSISTENCY")
    print(f"  Producer 1   : {paths['run_eof'].name}")
    print(f"  Producer 2   : {paths['merge_lots'].name}")
    print(f"  Consumer 1 : {paths['generate_report'].name}")
    print(f"  Consumer 2 : {paths['generate_radar'].name}")
    print(f"  {len(CANONICAL_KEYS)} canonical keys to check")
    print("-" * 70)
    print()

    violations = []

    # Load the sources
    try:
        source_run_eof = paths["run_eof"].read_text(encoding="utf-8")
        source_merge_lots = paths["merge_lots"].read_text(encoding="utf-8")
        source_generate = paths["generate_report"].read_text(encoding="utf-8")
        source_radar = paths["generate_radar"].read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print(f"[error] Unable to read the files: {exc}")
        return 1

    # Extract written and read keys
    written_run_eof = extract_written_keys(source_run_eof, paths["run_eof"])
    written_merge_lots = extract_written_keys(source_merge_lots, paths["merge_lots"])
    read_keys_by_consumer = {
        paths["generate_report"].name: extract_read_keys(source_generate, paths["generate_report"]),
        paths["generate_radar"].name: extract_read_keys(source_radar, paths["generate_radar"]),
    }

    # Check for parsing errors
    if any(key == "PARSE_ERROR" for key, _ in written_run_eof):
        violations.append("run_eof.py: parsing error, check impossible")
    if any(key == "PARSE_ERROR" for key, _ in written_merge_lots):
        violations.append("merge_lots.py: parsing error, check impossible")
    for name, read_keys in read_keys_by_consumer.items():
        if any(key == "PARSE_ERROR" for key, _ in read_keys):
            violations.append(f"{name}: parsing error, check impossible")

    if violations:
        print("[FAIL] Parsing errors:")
        for v in violations:
            print(f"    {v}")
        print()
        print("Impossible to continue without analyzable source.")
        return 1

    # Check 1: canonical keys are written by BOTH producers
    violations.extend(check_canonical_keys_written(written_run_eof, "run_eof.py"))
    violations.extend(check_canonical_keys_written(written_merge_lots, "merge_lots.py"))

    # Check 2: each canonical key is read by at least one consumer, except
    # those explicitly exempted because their consumer does not exist yet.
    read_violations, reminders = check_canonical_keys_read(read_keys_by_consumer)
    violations.extend(read_violations)

    # Check 3: no dead name is WRITTEN by a producer
    violations.extend(check_dead_names_written(written_run_eof, "run_eof.py"))
    violations.extend(check_dead_names_written(written_merge_lots, "merge_lots.py"))

    # Check 4: no invented key name
    violations.extend(check_invented_keys(written_run_eof, "run_eof.py"))
    violations.extend(check_invented_keys(written_merge_lots, "merge_lots.py"))

    # Report
    if violations:
        print(f"[FAIL] {len(violations)} violation(s) detected:")
        for v in violations:
            print(f"    {v}")
        print()
        print("The shared contract is not respected. These naming divergences would")
        print("display blanks in the report depending on which of the two producers")
        print("generated the eof-audit-results.json file.")
        print()
        print("Fix the violations above to restore consistency.")
        return 1

    nb_keys = len(CANONICAL_KEYS)
    nb_read = nb_keys - len(PRODUCED_KEYS_NOT_YET_READ)
    consumer_names = " and ".join(read_keys_by_consumer)
    print(f"[OK] Producer 1 (run_eof.py) writes the {nb_keys} canonical keys")
    print(f"[OK] Producer 2 (merge_lots.py) writes the {nb_keys} canonical keys")
    print(f"[OK] The {nb_read} expected keys are read by {consumer_names}")
    print("[OK] No dead name written by the producers")
    print("[OK] No invented key")
    for reminder in reminders:
        print(f"[REMINDER] {reminder}")
    print()
    print("[SUCCESS] Consistency preserved. The shared contract is respected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
