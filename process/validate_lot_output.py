#!/usr/bin/env python3
"""
Contract validator for multi-agent EOF audit lot outputs.

WHY THIS SCRIPT EXISTS
-----------------------
The EOF audit process becomes multi-agent: each lot (agent, script, human)
writes ONE results file, which a merge script then consolidates. For this to
hold, a strict output contract is needed, validated BEFORE the merge. A
malformed output skews a deliverable figure without visibly breaking anything:
the EOF radar aggregates verdicts, and an out-of-vocabulary value or an
inconsistent score propagates silently all the way to the client PDF.

This script refuses the non-conforming instead of merging it. Zero tolerance:
a lot that does not respect the contract does not pass. Rationale: an incomplete
report is better than a wrong report.

WHAT IT VALIDATES, EXHAUSTIVELY
--------------------------------
  - JSON structure: root metadata (lot_id, generated_at, inputs, criteria)
  - Required fields and forbidden fields (weight, max_potential, dimension, criterion)
  - `id` exists in the EOF reference (54 criteria) or in the quick diagnostic (16 questions)
  - `answer` belongs to the reference vocabulary FOR THIS CRITERION
  - `coefficient` consistent with the reference's evaluation_coefficient_options
  - `answer`/`coefficient` consistency: null together or non-null together
  - `provenance`/`source` consistency: required if answer or context is non-null
  - No duplicate `id` within the same file
  - No unknown fields (strict validation)

Technical constraint: standard library only, no jsonschema or pyyaml.
Rationale: portability. Another harness must be able to read the schema and apply
this validator without external dependencies.

Usage:
    python3 validate_lot_output.py <lot-file.json>

Exit code: 0 if conforming, 1 otherwise.

Style alignment with check_efootprint_contract.py and check_genericite.py:
  - Visual banner with separator
  - [OK] / [FAIL] / [info] prefixes
  - Pedagogical final message
  - Structured output: list of violations, then verdict
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_probe_health import VALID_STATUSES  # noqa: E402

# Project root: this script lives in process/
PROJECT_ROOT = Path(__file__).resolve().parents[1]
REFERENCE_PATH = (
    PROJECT_ROOT
    / ".claude/skills/eof/docs/EOF-V.1.1 (EROOM Optimization Framework) - Template - English"
    / "eof-reference.json"
)
SCHEMA_PATH = PROJECT_ROOT / "process" / "lot-output-schema.json"

# Forbidden fields in a criterion entry (they come from the reference, not from the lot)
FORBIDDEN_FIELDS = {"weight", "max_potential", "dimension", "criterion", "pillar"}

# Closed vocabularies, inherited from the project
PROVENANCE_VALUES = {"collected", "estimated", "declared", "stated", "assumed", None}
CATEGORY_VALUES = {"automatable", "partial", "no_data"}


# ---------------------------------------------------------------------------
# Loading the reference
# ---------------------------------------------------------------------------

def load_reference():
    """Load the EOF reference and return a dict {id: full_criterion}.

    Returns (criteria_dict, diagnostic_dict, errors).
    """
    if not REFERENCE_PATH.exists():
        return None, None, [f"Reference not found: {REFERENCE_PATH}"]

    try:
        with open(REFERENCE_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        return None, None, [f"Reference unreadable: {exc}"]

    criteria = {}
    for c in data.get("criteria", []):
        cid = c.get("id")
        if cid:
            criteria[cid] = c

    diagnostic = {}
    for q in data.get("quick_diagnostic", []):
        qid = q.get("id")
        if qid:
            diagnostic[qid] = q

    if not criteria and not diagnostic:
        return None, None, ["Reference empty or malformed"]

    return criteria, diagnostic, []


# ---------------------------------------------------------------------------
# Structure validation
# ---------------------------------------------------------------------------

def validate_measurement_block(measurement, prefix):
    """Validate a `measurement` block (measurement-state convention: status/target/detail)."""
    violations = []
    if not isinstance(measurement, dict):
        return [(prefix, f"must be an object, found {type(measurement).__name__}")]

    required = {"status", "target", "detail"}
    missing = required - set(measurement.keys())
    if missing:
        violations.append((prefix, f"missing required fields: {', '.join(sorted(missing))}"))
    extra = set(measurement.keys()) - required
    if extra:
        violations.append((prefix, f"unknown fields (strict rejection): {', '.join(sorted(extra))}"))

    if "status" in measurement and measurement["status"] not in VALID_STATUSES:
        violations.append((f"{prefix}.status", f"value '{measurement['status']}' out of vocabulary (allowed: {', '.join(sorted(VALID_STATUSES))})"))
    if "target" in measurement and not isinstance(measurement["target"], str):
        violations.append((f"{prefix}.target", f"must be a string, found {type(measurement['target']).__name__}"))
    if "detail" in measurement and measurement["detail"] is not None and not isinstance(measurement["detail"], str):
        violations.append((f"{prefix}.detail", f"must be a string or null, found {type(measurement['detail']).__name__}"))

    return violations


def validate_root_structure(data):
    """Validate the root metadata. Returns (violations, fields_to_validate)."""
    violations = []

    if not isinstance(data, dict):
        return [("root", "the file is not a JSON object")], None

    required = {"lot_id", "generated_at", "inputs", "criteria"}
    missing = required - set(data.keys())
    if missing:
        violations.append(("root", f"missing required fields: {', '.join(sorted(missing))}"))

    # "measurement" is optional at the root: measurement-state convention (cf.
    # documentation/implementation/measurement-state-convention.md), for a lot
    # whose SOURCE itself (not an individual criterion) may fail to be
    # read (ex. questionnaire file absent or unreadable).
    allowed = required | {"measurement"}
    extra = set(data.keys()) - allowed
    if extra:
        violations.append(("root", f"unknown fields (strict rejection): {', '.join(sorted(extra))}"))

    if "measurement" in data:
        violations.extend(validate_measurement_block(data["measurement"], "measurement"))

    if "lot_id" in data and not isinstance(data["lot_id"], str):
        violations.append(("lot_id", f"must be a string, found {type(data['lot_id']).__name__}"))
    elif "lot_id" in data and not data["lot_id"].strip():
        violations.append(("lot_id", "empty string"))

    if "generated_at" in data and not isinstance(data["generated_at"], str):
        violations.append(("generated_at", f"must be an ISO 8601 string, found {type(data['generated_at']).__name__}"))
    elif "generated_at" in data:
        try:
            datetime.fromisoformat(data["generated_at"].replace("Z", "+00:00"))
        except ValueError:
            violations.append(("generated_at", f"invalid ISO 8601 format: {data['generated_at']}"))

    if "inputs" in data and not isinstance(data["inputs"], list):
        violations.append(("inputs", f"must be a list, found {type(data['inputs']).__name__}"))

    if "criteria" in data and not isinstance(data["criteria"], list):
        violations.append(("criteria", f"must be a list, found {type(data['criteria']).__name__}"))

    if violations:
        return violations, None

    return [], data.get("criteria", [])


def validate_entry_fields(entry, index):
    """Validate the fields of an entry. Returns violations."""
    violations = []
    prefix = f"criteria[{index}]"

    if not isinstance(entry, dict):
        return [(prefix, f"must be an object, found {type(entry).__name__}")]

    required = {"id", "category"}
    allowed = {
        "id", "answer", "coefficient", "provenance", "source",
        "context", "category", "not_applicable"
    }

    missing = required - set(entry.keys())
    if missing:
        violations.append((prefix, f"missing required fields: {', '.join(sorted(missing))}"))

    # Forbidden fields
    forbidden_present = FORBIDDEN_FIELDS & set(entry.keys())
    if forbidden_present:
        violations.append((
            prefix,
            f"forbidden fields detected (they come from the reference, not from the lot): {', '.join(sorted(forbidden_present))}"
        ))

    # Unknown fields
    extra = set(entry.keys()) - allowed
    if extra:
        violations.append((prefix, f"unknown fields (strict rejection): {', '.join(sorted(extra))}"))

    # Base type for id
    if "id" in entry and not isinstance(entry["id"], str):
        violations.append((f"{prefix}.id", f"must be a string, found {type(entry['id']).__name__}"))

    # Closed vocabularies
    if "category" in entry and entry["category"] not in CATEGORY_VALUES:
        violations.append((
            f"{prefix}.category",
            f"value out of vocabulary: '{entry['category']}' (expected: {', '.join(sorted(str(v) for v in CATEGORY_VALUES))})"
        ))

    if "provenance" in entry and entry["provenance"] not in PROVENANCE_VALUES:
        # Build the list of expected values from PROVENANCE_VALUES
        expected_values = sorted([str(v) if v is not None else "null" for v in PROVENANCE_VALUES if v is not None]) + ["null"]
        violations.append((
            f"{prefix}.provenance",
            f"value out of vocabulary: '{entry['provenance']}' (expected: {', '.join(expected_values)})"
        ))

    return violations


def validate_coherence(entry, index, ref_criteria, ref_diagnostic):
    """Validate the semantic coherence of an entry. Returns violations."""
    violations = []
    prefix = f"criteria[{index}]"

    cid = entry.get("id")
    if not cid:
        return violations  # already reported by validate_entry_fields

    # Does the id exist in the reference?
    ref = ref_criteria.get(cid) or ref_diagnostic.get(cid)
    if not ref:
        violations.append((
            f"{prefix}.id",
            f"identifier '{cid}' absent from the EOF reference (54 criteria 1.1-6.10 + 16 questions 0.1-0.16)"
        ))
        return violations  # impossible to validate answer/score without the reference

    answer = entry.get("answer")
    coefficient = entry.get("coefficient")
    context = entry.get("context")
    provenance = entry.get("provenance")
    source = entry.get("source")

    # answer / coefficient consistency (depends on the criterion type)
    is_diagnostic = cid in ref_diagnostic

    if answer is None and coefficient is not None:
        violations.append((f"{prefix}.coefficient", "must be null if answer is null"))

    if answer is not None:
        # For the quick diagnostic, coefficient must be null (no coefficient in the reference)
        # For reference criteria, coefficient must be non-null
        if is_diagnostic and coefficient is not None:
            violations.append((
                f"{prefix}.coefficient",
                "must be null for a quick-diagnostic question (no coefficient defined in the reference)"
            ))
        elif not is_diagnostic and coefficient is None:
            violations.append((f"{prefix}.coefficient", "must be non-null if answer is non-null"))

    # answer / provenance / source consistency
    if answer is not None or context:
        if provenance is None:
            violations.append((f"{prefix}.provenance", "required if answer or context is non-null"))
        if not source:
            violations.append((f"{prefix}.source", "required and non-empty if answer or context is non-null"))

    # Answer vocabulary validation (if non-null)
    if answer is not None:
        # Reference criteria (1.1-6.10): evaluation_options
        if cid in ref_criteria:
            options = ref_criteria[cid].get("evaluation_options", [])
            if answer not in options:
                violations.append((
                    f"{prefix}.answer",
                    f"'{answer}' out of vocabulary for this criterion (expected: {', '.join(options)})"
                ))

            # Coefficient validation
            coefficient_map = ref_criteria[cid].get("evaluation_coefficient_options", {})
            expected_coefficient = coefficient_map.get(answer)
            if expected_coefficient is not None and coefficient != expected_coefficient:
                violations.append((
                    f"{prefix}.coefficient",
                    f"inconsistent with evaluation_coefficient_options: expected {expected_coefficient}, found {coefficient}"
                ))

        # Quick-diagnostic questions (0.1-0.16): screens
        elif cid in ref_diagnostic:
            screens = ref_diagnostic[cid].get("screens", [])
            if answer not in screens:
                violations.append((
                    f"{prefix}.answer",
                    f"'{answer}' out of vocabulary for this question (expected: {', '.join(screens)})"
                ))

    return violations


def validate_no_duplicates(entries):
    """Check the absence of duplicate ids. Returns violations."""
    violations = []
    seen = {}
    for i, entry in enumerate(entries):
        cid = entry.get("id")
        if not cid:
            continue
        if cid in seen:
            violations.append((
                f"criteria[{i}].id",
                f"duplicate detected: '{cid}' already present at index {seen[cid]}"
            ))
        else:
            seen[cid] = i
    return violations


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Validate the output contract of an EOF audit lot. "
                    "Reject any non-conforming file instead of merging it."
    )
    parser.add_argument("file", type=Path,
                        help="Lot output file to validate (JSON).")
    args = parser.parse_args()

    file = args.file
    if not file.exists():
        print(f"[error] File not found: {file}")
        return 1

    try:
        with open(file, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        print(f"[error] Invalid JSON: {file}")
        print(f"         {exc}")
        return 1
    except OSError as exc:
        print(f"[error] Unreadable file: {exc}")
        return 1

    # Load the reference
    ref_criteria, ref_diagnostic, ref_errors = load_reference()
    if ref_errors:
        print("[error] Unable to load the EOF reference:")
        for err in ref_errors:
            print(f"         {err}")
        return 1

    print("-" * 68)
    print(f"  EOF LOT OUTPUT VALIDATION — {file.name}")
    print(f"  file      : {file}")
    print(f"  reference : {REFERENCE_PATH.relative_to(PROJECT_ROOT)}")
    print("-" * 68)
    print()

    violations = []

    # 1. Root structure
    root_violations, entries = validate_root_structure(data)
    violations.extend(root_violations)

    if entries is None:
        print(f"[FAIL] Invalid root structure ({len(root_violations)} error(s)):")
        for loc, msg in violations:
            print(f"    {loc} : {msg}")
        print()
        print("Impossible to continue without a valid structure.")
        return 1

    # 2. Validation of each entry
    for i, entry in enumerate(entries):
        violations.extend(validate_entry_fields(entry, i))
        violations.extend(validate_coherence(entry, i, ref_criteria, ref_diagnostic))

    # 3. Duplicate ids
    violations.extend(validate_no_duplicates(entries))

    # Report
    if violations:
        print(f"[FAIL] {len(violations)} violation(s) detected:")
        for loc, msg in violations:
            print(f"    {loc} : {msg}")
        print()
        print("The contract is not respected. This file cannot be merged.")
        print("Fix the violations above before rerunning the merge.")
        return 1

    print(f"[OK] {len(entries)} entry/entries validated, 0 violations.")
    print()
    print("[SUCCESS] Contract respected. This file can be merged.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
