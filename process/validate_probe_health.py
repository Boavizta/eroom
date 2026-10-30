#!/usr/bin/env python3
"""
Health validator for extraction probes in an audit directory.

WHY THIS SCRIPT EXISTS
-----------------------
Extractors confuse two things: a service that does not have the thing being
looked for (a legitimate audit result) and a failure of our tool (network
timeout, unreadable file, API quota exceeded). This conmerge produces wrong
numbers for the reader: a timeout on robots.txt yields `present: False`,
exactly like a real 404. A DOM with zero tags (capture without an HTML body)
fabricates an artificially flattering EcoIndex.

The measurement-state convention (documentation/implementation/measurement-state-convention.md)
solves this by separating the two destinations:
  - Internal: `measurement` block with `status` (`ok`, `not_found`, `network_error`...)
  - Client: `answer: null` on failure, never an invented number

This script checks the health of a complete audit directory: it re-reads all
the JSON files produced, collects all the `measurement` blocks, and **exits 1
if a single extractor failure is present**. A probe failure signals that we
do not know, so the deliverable cannot be published as is.

`not_found` is NOT a failure: the probe did search properly, the thing is
really absent, it is an audit result.

WHAT IT CHECKS
--------------
1. Recursively walks all JSON files of an audit directory
2. Finds all `measurement` blocks (at any depth)
3. Counts by status: global and per file
4. Detailed list of the `network_error`/`read_error`/`analysis_error` only (not the `not_found`)
5. Signals (without failing): invalid status, block without `target`
6. Invalid JSON = exit 1 (a broken audit is a health problem)

ALLOWED STATUS VALUES
---------------------
  ok             - measured successfully
  not_found      - the probe searched properly, the thing is absent (AUDIT RESULT)
  network_error  - timeout, DNS, connection refused, API quota
  read_error     - file absent, broken encoding, invalid JSON
  analysis_error - resource read but unusable (expected field absent)

Usage:
    python3 validate_probe_health.py audits/<domain>
    python3 validate_probe_health.py audits/<domain> --list-files

Exit code: 0 if no failure, 1 if at least one failure or structural anamealy.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple


# Allowed status values (cf. convention section 3)
VALID_STATUSES = {"ok", "not_found", "network_error", "read_error", "analysis_error"}

# Statuses that constitute failures (the probe did not succeed)
FAILURE_STATUSES = {"network_error", "read_error", "analysis_error"}


def find_measurement_blocks(data, path="", file_path=""):
    """Recursively walk a JSON structure and find all `measurement` blocks.

    Returns a list of (file, path, status, target, detail).

    This function does not assume where the blocks are: they can be at any
    depth, in dicts or lists.
    """
    results = []

    if isinstance(data, dict):
        # If it is a measurement block (contains the 'status' key directly in 'measurement')
        if "measurement" in data and isinstance(data["measurement"], dict) and "status" in data["measurement"]:
            measurement = data["measurement"]
            status = measurement.get("status")
            target = measurement.get("target")
            detail = measurement.get("detail")
            results.append((file_path, path + ".measurement", status, target, detail))

        # Continue the search in all fields
        for key, value in data.items():
            new_path = f"{path}.{key}" if path else key
            results.extend(find_measurement_blocks(value, new_path, file_path))

    elif isinstance(data, list):
        for i, item in enumerate(data):
            new_path = f"{path}[{i}]"
            results.extend(find_measurement_blocks(item, new_path, file_path))

    return results


def validate_audit_directory(audit_dir: Path, list_files: bool = False):
    """Validate the probe health in an audit directory.

    Returns a tuple (exit_code, report_text).
    """
    if not audit_dir.exists():
        return 1, f"[ERROR] Audit directory not found: {audit_dir}"

    if not audit_dir.is_dir():
        return 1, f"[ERROR] The path is not a directory: {audit_dir}"

    # Find all JSON files recursively
    json_files = sorted(audit_dir.rglob("*.json"))

    if not json_files:
        return 0, f"[info] No JSON file found in {audit_dir}\n"

    # --list-files option
    if list_files:
        output = []
        output.append(f"[info] {len(json_files)} JSON file(s) found in {audit_dir}")
        output.append("")
        total_blocks = 0
        for json_file in json_files:
            try:
                with open(json_file, encoding="utf-8") as f:
                    data = json.load(f)
                blocks = find_measurement_blocks(data, file_path=str(json_file.relative_to(audit_dir)))
                total_blocks += len(blocks)
                output.append(f"    {json_file.relative_to(audit_dir)} : {len(blocks)} measurement block(s)")
            except (json.JSONDecodeError, OSError) as exc:
                output.append(f"    {json_file.relative_to(audit_dir)} : ERROR ({type(exc).__name__})")
        output.append("")
        output.append(f"[info] Total: {total_blocks} measurement block(s) found")
        return 0, "\n".join(output)

    # Collect all measurement blocks
    all_measurements = []
    json_errors = []

    for json_file in json_files:
        try:
            with open(json_file, encoding="utf-8") as f:
                data = json.load(f)
            blocks = find_measurement_blocks(data, file_path=str(json_file.relative_to(audit_dir)))
            all_measurements.extend(blocks)
        except json.JSONDecodeError as exc:
            json_errors.append((json_file.relative_to(audit_dir), f"Invalid JSON line {exc.lineno}"))
        except OSError as exc:
            json_errors.append((json_file.relative_to(audit_dir), f"Read impossible: {exc}"))

    # If JSON files are broken, it is an immediate failure
    if json_errors:
        output = []
        output.append(f"[FAIL] {len(json_errors)} unreadable JSON file(s):")
        for file_path, error in json_errors:
            output.append(f"    - {file_path} : {error}")
        output.append("")
        output.append("A broken JSON in an audit directory is a health problem.")
        return 1, "\n".join(output)

    # If no measurement block found
    if not all_measurements:
        output = []
        output.append(f"[info] {len(json_files)} JSON file(s) analyzed")
        output.append("")
        output.append("[WARNING] No measurement block found.")
        output.append("")
        output.append("Either the extractors have not been rerun with the convention yet,")
        output.append("or this directory predates the measurement-state convention.")
        output.append("")
        output.append("Use --list-files to see which files were analyzed.")
        return 0, "\n".join(output)

    # Counts and analyses
    status_counts: Dict[str, int] = {}
    status_by_file: Dict[str, Dict[str, int]] = {}
    failures: List[Tuple[str, str, str, str, str]] = []  # (file, path, status, target, detail)
    invalid_statuses: List[Tuple[str, str, str]] = []  # (file, path, status)
    missing_targets: List[Tuple[str, str]] = []  # (file, path)

    for file_path, path, status, target, detail in all_measurements:
        # Global count
        status_counts[status] = status_counts.get(status, 0) + 1

        # Count per file
        if file_path not in status_by_file:
            status_by_file[file_path] = {}
        status_by_file[file_path][status] = status_by_file[file_path].get(status, 0) + 1

        # Check valid status
        if status not in VALID_STATUSES:
            invalid_statuses.append((file_path, path, status))

        # Check target presence
        if target is None:
            missing_targets.append((file_path, path))

        # Collect failures
        if status in FAILURE_STATUSES:
            failures.append((file_path, path, status, target or "?", detail or ""))

    # Build the report
    output = []
    output.append("-" * 70)
    output.append("  EXTRACTION PROBE HEALTH")
    output.append(f"  Directory: {audit_dir.name}")
    output.append("-" * 70)
    output.append("")

    # Global count
    output.append(f"[info] {len(json_files)} JSON file(s), {len(all_measurements)} measurement block(s)")
    output.append("")
    output.append("Global count by status:")
    for status in sorted(status_counts.keys()):
        count = status_counts[status]
        output.append(f"    {status:20} : {count:4}")
    output.append("")

    # Count per file
    output.append("Count by file:")
    for file_path in sorted(status_by_file.keys()):
        counts = status_by_file[file_path]
        counts_str = ", ".join(f"{s}={c}" for s, c in sorted(counts.items()))
        output.append(f"    {file_path} : {counts_str}")
    output.append("")

    # Shape anamealies (do not fail)
    has_form_anamealies = False

    if invalid_statuses:
        has_form_anamealies = True
        output.append(f"[WARNING] {len(invalid_statuses)} invalid status(es) detected:")
        for file_path, path, status in invalid_statuses:
            output.append(f"    - {file_path} > {path}")
            output.append(f"      status = '{status}' (allowed values: {', '.join(sorted(VALID_STATUSES))})")
        output.append("")

    if missing_targets:
        has_form_anamealies = True
        output.append(f"[WARNING] {len(missing_targets)} measurement block(s) without target:")
        for file_path, path in missing_targets:
            output.append(f"    - {file_path} > {path}")
        output.append("")

    if has_form_anamealies:
        output.append("These anamealies signal a badly placed extractor, but do not constitute")
        output.append("a health failure (the distinction matters for orchestration).")
        output.append("")

    # Probe failures (fail)
    if failures:
        output.append(f"[FAIL] {len(failures)} probe(s) in failure:")
        output.append("")
        for file_path, path, status, target, detail in failures:
            output.append(f"    File   : {file_path}")
            output.append(f"    Path   : {path}")
            output.append(f"    Status : {status}")
            output.append(f"    Target : {target}")
            if detail:
                output.append(f"    Detail : {detail}")
            output.append("")
        output.append("An extractor failure signals that we do not know. The deliverable cannot")
        output.append("be published as is: either rerun the extractor, or mark the")
        output.append("criterion as unanswered in the questionnaire.")
        return 1, "\n".join(output)

    # Success
    not_found_count = status_counts.get("not_found", 0)
    ok_count = status_counts.get("ok", 0)

    output.append(f"[OK] No probe failure detected")
    if ok_count > 0:
        output.append(f"[OK] {ok_count} successful measurement(s)")
    if not_found_count > 0:
        output.append(f"[OK] {not_found_count} confirmed absence(s) (legitimate audit results)")
    output.append("")
    output.append("[SUCCESS] Probe health is good. The audit directory can be published.")

    return 0, "\n".join(output)


def main():
    parser = argparse.ArgumentParser(
        description="Validate the health of extraction probes in an audit directory. "
                    "Exits 1 if a single probe failure is present.",
        epilog="Reminder: 'not_found' is NOT a failure (it is an audit result).",
    )
    parser.add_argument(
        "audit_dir",
        type=Path,
        nargs="?",
        help="Path of the audit directory to check",
    )
    parser.add_argument(
        "--list-files",
        action="store_true",
        help="List the JSON files found and their number of measurement blocks",
    )
    args = parser.parse_args()

    if not args.audit_dir:
        parser.print_help()
        print()
        print("Error: an audit directory is required.")
        print()
        print("Examples:")
        print("    python3 validate_probe_health.py audits/octo.com")
        print("    python3 validate_probe_health.py audits/example.org --list-files")
        return 2

    exit_code, report = validate_audit_directory(args.audit_dir, args.list_files)
    print(report)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
