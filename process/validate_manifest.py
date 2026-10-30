#!/usr/bin/env python3
"""
Lot manifest validation: integrity check of the EOF audit process.

WHY THIS SCRIPT EXISTS
-----------------------
The manifest is the orchestration contract of the audit process. If it is
inconsistent (criterion owned by two lots, cyclic dependency, duplicate output
file), the whole process drifts silently. This script detects violations
BEFORE running the first lot.

Checks implemented:
  1. Uniqueness of lot identifiers
  2. Valid dependency graph (existing IDs, acyclic)
  3. Consistency of waves with the graph
  4. Disjoint ownership of criteria (the most important one)
  5. Reference exists and criterion count
  6. Valid provenance values
  7. Unique lot outputs
  8. Referenced files exist
  9. Valid executors and states

CHECK #4: DISJOINT OWNERSHIP OF CRITERIA
----------------------------------------
Each criterion of the reference must be owned by EXACTLY ONE judgment lot.
Two lots owning the same criterion can contradict each other, and execution
order becomes decisive on the result (violation of the idempotence property).
A criterion owned by no lot is an orphan and will never be judged.

Three forms of ownership:
  - {"id_prefix": "3."} -> all reference criteria whose id starts with this prefix
  - {"source": "<path>", "rule": "..."} -> criteria that the mapping table
    (eof_criteria_mapping.py) declares automatable or partial
  - {"rule": "..."} with neither source nor id_prefix -> COMPLEMENT set: all
    criteria that no one else owns

Usage:
    python3 validate_manifest.py                        # default
    python3 validate_manifest.py process/lots-manifest.json

Exit code: 0 if the manifest is valid, 1 otherwise.
"""

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = PROJECT_ROOT / "process" / "lots-manifest.json"

# Import the ownership resolution functions from the shared module
from criteria_ownership import (
    load_mapping,
    resolve_owned_criteria,
    resolve_allowed_contexts,
    compute_ownership,
)


# ---------------------------------------------------------------------------
# Cycle detection in the dependency graph
# ---------------------------------------------------------------------------

def detect_cycle(lots):
    """Returns (is_acyclic, cycle_if_found).

    Uses three-color marking to detect cycles in a directed graph:
    white (unvisited), gray (being visited), black (visited).
    A gray node reached from a gray node signals a cycle.
    """
    deps_by_id = {lot["id"]: lot.get("depends_on", []) for lot in lots}

    WHITE, GRAY, BLACK = 0, 1, 2
    color = {lot_id: WHITE for lot_id in deps_by_id}
    parent = {}

    def visit(node, path):
        if color[node] == BLACK:
            return True, []
        if color[node] == GRAY:
            cycle_start = path.index(node)
            return False, path[cycle_start:] + [node]

        color[node] = GRAY
        path.append(node)

        for dep in deps_by_id[node]:
            if dep not in deps_by_id:
                continue
            acyclic, cycle = visit(dep, path)
            if not acyclic:
                return False, cycle

        path.pop()
        color[node] = BLACK
        return True, []

    for lot_id in deps_by_id:
        if color[lot_id] == WHITE:
            acyclic, cycle = visit(lot_id, [])
            if not acyclic:
                return False, cycle

    return True, []


# ---------------------------------------------------------------------------
# Criterion ownership resolution
# ---------------------------------------------------------------------------

def load_reference(path):
    """Load the reference and return the list of criterion IDs."""
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return [c["id"] for c in data.get("criteria", [])]
    except (json.JSONDecodeError, KeyError, OSError):
        return None


# ---------------------------------------------------------------------------
# Main checks
# ---------------------------------------------------------------------------

def check_manifest(manifest_path):
    """Validate the manifest. Returns the number of errors."""
    try:
        with open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        print(f"[ERROR] Manifest unreadable: {exc}")
        return 1

    lots = manifest.get("lots", [])
    waves = manifest.get("waves", [])
    conventions = manifest.get("conventions", {})
    reference_path = PROJECT_ROOT / manifest.get("reference", "")

    errors = 0

    print()
    print(f"[info] {len(lots)} lots declared, {len(waves)} waves.")
    print()

    # -----------------------------------------------------------------------
    # Check 1: Uniqueness of lot identifiers
    # -----------------------------------------------------------------------
    lot_ids = [lot["id"] for lot in lots]
    duplicates = [lot_id for lot_id in set(lot_ids) if lot_ids.count(lot_id) > 1]

    if duplicates:
        print(f"[ERROR] {len(duplicates)} duplicate lot identifier(s):")
        for lot_id in sorted(duplicates):
            print(f"    - {lot_id}")
        print()
        errors += len(duplicates)
    else:
        print("[OK] All lot identifiers are unique.")

    # -----------------------------------------------------------------------
    # Check 1b: Strict validation of the keys of each lot
    # -----------------------------------------------------------------------
    ALLOWED_LOT_KEYS = {
        "id", "wave", "label", "executor", "state", "scripts", "scripts_to_write",
        "prompt", "arguments", "verified_arguments", "depends_on", "inputs",
        "data_outputs", "lot_output", "allowed_provenances", "owned_criteria",
        "allowed_contexts", "replayable_alone", "human_prerequisite", "constraint",
        "note", "expected_output", "type", "decision"
    }

    unknown_keys_violations = []
    for lot in lots:
        lot_id = lot.get("id", "?")
        unknown_keys = set(lot.keys()) - ALLOWED_LOT_KEYS
        if unknown_keys:
            for key in sorted(unknown_keys):
                unknown_keys_violations.append((lot_id, key))

    if unknown_keys_violations:
        print(f"[ERROR] {len(unknown_keys_violations)} unknown key(s) in lots (strict validation):")
        for lot_id, key in unknown_keys_violations:
            print(f"    - lot '{lot_id}': unknown key '{key}'")
        print()
        errors += len(unknown_keys_violations)
    else:
        print("[OK] All lot keys are recognized.")

    # -----------------------------------------------------------------------
    # Check 2: Valid dependency graph
    # -----------------------------------------------------------------------
    lot_ids_set = set(lot_ids)
    missing_deps = []
    for lot in lots:
        for dep in lot.get("depends_on", []):
            if dep not in lot_ids_set:
                missing_deps.append((lot["id"], dep))

    if missing_deps:
        print(f"[ERROR] {len(missing_deps)} dependenc(ies) towards non-existent lots:")
        for lot_id, dep in missing_deps:
            print(f"    - lot '{lot_id}' depends on '{dep}' (not found)")
        print()
        errors += len(missing_deps)
    else:
        print("[OK] All dependencies point to existing lots.")

    acyclic, cycle = detect_cycle(lots)
    if not acyclic:
        print(f"[ERROR] Cycle detected in the dependency graph:")
        print(f"    {' -> '.join(cycle)}")
        print()
        errors += 1
    else:
        print("[OK] The dependency graph is acyclic.")

    # -----------------------------------------------------------------------
    # Check 3: Consistency of waves with the graph
    # -----------------------------------------------------------------------
    wave_order = {v["id"]: i for i, v in enumerate(waves)}
    wave_violations = []

    for lot in lots:
        lot_wave = lot.get("wave")
        if lot_wave not in wave_order:
            wave_violations.append((lot["id"], lot_wave, "unknown wave"))
            continue

        lot_order = wave_order[lot_wave]
        for dep in lot.get("depends_on", []):
            dep_lot = next((l for l in lots if l["id"] == dep), None)
            if dep_lot is None:
                continue
            dep_wave = dep_lot.get("wave")
            if dep_wave not in wave_order:
                continue
            dep_order = wave_order[dep_wave]
            if dep_order > lot_order:
                wave_violations.append(
                    (lot["id"], dep, f"wave {lot_wave} depends on later wave {dep_wave}")
                )

    if wave_violations:
        print(f"[ERROR] {len(wave_violations)} inconsistenc(ies) between waves and dependencies:")
        for lot_id, dep_or_reason, reason in wave_violations:
            if reason == "unknown wave":
                print(f"    - lot '{lot_id}' : {reason} ({dep_or_reason})")
            else:
                print(f"    - lot '{lot_id}' -> '{dep_or_reason}' : {reason}")
        print()
        errors += len(wave_violations)
    else:
        print("[OK] The waves are consistent with the dependency graph.")

    # -----------------------------------------------------------------------
    # Check 4: Disjoint ownership of criteria
    # -----------------------------------------------------------------------
    all_criteria = load_reference(reference_path)
    if all_criteria is None:
        print(f"[ERROR] Reference unreadable or absent: {reference_path}")
        print()
        errors += 1
        all_criteria = []

    # Use the shared module to compute ownership
    ownership, complement_lots, residual_lots, contexts_by_lot, ownership_errors = compute_ownership(lots, all_criteria)

    # Check ownership errors
    if ownership_errors:
        for err in ownership_errors:
            print(f"[ERROR] {err}")
        print()
        errors += len(ownership_errors)

    # Display the mapping if available
    automatable, partial = load_mapping()
    if automatable is None:
        print("[WARNING] eof_criteria_mapping.py unreadable, partial ownership check.")
        print()
        automatable = set()
        partial = set()

    collisions = {crit_id: owners for crit_id, owners in ownership.items() if len(owners) > 1}
    orphans = [c for c in all_criteria if c not in ownership]

    if collisions:
        print(f"[ERROR] {len(collisions)} criterion/criteria owned by several lots:")
        for crit_id in sorted(collisions.keys()):
            owners = collisions[crit_id]
            print(f"    - {crit_id} : {', '.join(owners)}")
        print()
        errors += len(collisions)
    else:
        print("[OK] No criterion owned by several lots.")

    if orphans:
        print(f"[ERROR] {len(orphans)} orphan criterion/criteria (never judged):")
        for crit_id in sorted(orphans):
            print(f"    - {crit_id}")
        print()
        errors += len(orphans)
    else:
        print("[OK] No orphan criterion.")

    # Additional check: a criterion in allowed_contexts must not be owned by the same lot
    context_conflicts = []
    for lot_id, contexts in contexts_by_lot.items():
        lot_owned = [c for c, owners in ownership.items() if lot_id in owners]
        conflicts = contexts & set(lot_owned)
        if conflicts:
            for crit_id in sorted(conflicts):
                context_conflicts.append((lot_id, crit_id))

    if context_conflicts:
        print(f"[ERROR] {len(context_conflicts)} criterion/criteria both owned AND in allowed_contexts of the same lot:")
        for lot_id, crit_id in context_conflicts:
            print(f"    - lot '{lot_id}': criterion {crit_id}")
        print()
        errors += len(context_conflicts)
    else:
        print("[OK] No context/ownership conflict within the same lot.")

    # -----------------------------------------------------------------------
    # Check 4b: except_lots validation
    # -----------------------------------------------------------------------
    except_lots_violations = []
    for lot in lots:
        criteria = lot.get("owned_criteria")
        if criteria and "except_lots" in criteria:
            for except_lot_id in criteria["except_lots"]:
                if except_lot_id not in lot_ids_set:
                    except_lots_violations.append((lot["id"], except_lot_id))

    if except_lots_violations:
        print(f"[ERROR] {len(except_lots_violations)} except_lots pointing to non-existent lots:")
        for lot_id, except_id in except_lots_violations:
            print(f"    - lot '{lot_id}': except_lots cites '{except_id}' (not found)")
        print()
        errors += len(except_lots_violations)
    else:
        print("[OK] All except_lots cite existing lots.")

    # -----------------------------------------------------------------------
    # Check 4c: presence of conventions.context_contribution
    # -----------------------------------------------------------------------
    if "context_contribution" not in conventions:
        print("[ERROR] conventions.context_contribution missing from the manifest.")
        print()
        errors += 1
    else:
        print("[OK] conventions.context_contribution present.")

    # -----------------------------------------------------------------------
    # Check 5: Reference
    # -----------------------------------------------------------------------
    if all_criteria:
        print(f"[OK] Reference loaded: {len(all_criteria)} criteria.")

    # Display the automatable/partial counts for verification
    if automatable or partial:
        print(f"[info] MAPPING: {len(automatable)} automatable, {len(partial)} partial.")

    # Display the residual lots
    if residual_lots:
        print(f"[info] {len(residual_lots)} residual lot(s): {', '.join(residual_lots.keys())}")

    # -----------------------------------------------------------------------
    # Check 4d: Uniqueness of residual lots per provenance
    # -----------------------------------------------------------------------
    residual_by_provenance = {}
    for lot_id, provenance in residual_lots.items():
        if provenance not in residual_by_provenance:
            residual_by_provenance[provenance] = []
        residual_by_provenance[provenance].append(lot_id)

    residual_collisions = {provenance: lots for provenance, lots in residual_by_provenance.items() if len(lots) > 1}
    if residual_collisions:
        print(f"[ERROR] {len(residual_collisions)} provenance(s) with several residual lots (order ambiguity):")
        for provenance, lot_ids in residual_collisions.items():
            print(f"    - provenance '{provenance}' : {', '.join(lot_ids)}")
        print()
        errors += len(residual_collisions)
    else:
        if residual_lots:
            print("[OK] Each provenance has at most one residual lot.")

    # -----------------------------------------------------------------------
    # Check 6: Provenances
    # -----------------------------------------------------------------------
    precedence = conventions.get("provenance_precedence", [])
    provenance_violations = []

    for lot in lots:
        provenances = lot.get("allowed_provenances", [])
        for provenance in provenances:
            if provenance not in precedence:
                provenance_violations.append((lot["id"], provenance))

        output = lot.get("lot_output")
        if output and not provenances:
            provenance_violations.append((lot["id"], "no provenance declared for a judgment lot"))

    if provenance_violations:
        print(f"[ERROR] {len(provenance_violations)} invalid provenance(s):")
        for lot_id, provenance in provenance_violations:
            print(f"    - lot '{lot_id}' : {provenance}")
        print()
        errors += len(provenance_violations)
    else:
        print("[OK] All provenances are valid.")

    # -----------------------------------------------------------------------
    # Check 7: Unique lot outputs
    # -----------------------------------------------------------------------
    outputs = [lot["lot_output"] for lot in lots if lot.get("lot_output")]
    duplicate_outputs = [s for s in set(outputs) if outputs.count(s) > 1]

    if duplicate_outputs:
        print(f"[ERROR] {len(duplicate_outputs)} duplicate lot output(s):")
        for output in sorted(duplicate_outputs):
            lots_with_output = [lot["id"] for lot in lots if lot.get("lot_output") == output]
            print(f"    - {output} : {', '.join(lots_with_output)}")
        print()
        errors += len(duplicate_outputs)
    else:
        print("[OK] All lot outputs are unique.")

    # -----------------------------------------------------------------------
    # Check 8: Referenced files
    # -----------------------------------------------------------------------
    missing_files = []
    files_to_write = []

    for lot in lots:
        state = lot.get("state")

        if state == "existing":
            for script in lot.get("scripts", []):
                script_path = PROJECT_ROOT / script
                if not script_path.exists():
                    missing_files.append((lot["id"], script))

            if lot.get("executor") == "llm":
                prompt_path_str = lot.get("prompt")
                if prompt_path_str:
                    prompt_path = PROJECT_ROOT / prompt_path_str
                    if not prompt_path.exists():
                        missing_files.append((lot["id"], prompt_path_str))

        elif state in ("to_write", "partially_written"):
            files_to_write.extend(lot.get("scripts_to_write", []))
            if lot.get("executor") == "llm" and lot.get("prompt"):
                files_to_write.append(lot.get("prompt"))

    if missing_files:
        print(f"[ERROR] {len(missing_files)} missing file(s) for 'existing' lots:")
        for lot_id, file_path in missing_files:
            print(f"    - lot '{lot_id}' : {file_path}")
        print()
        errors += len(missing_files)
    else:
        print("[OK] All files declared 'existing' are present.")

    if files_to_write:
        print(f"[info] {len(files_to_write)} file(s) / script(s) to write (normal).")

    schema_output_path = PROJECT_ROOT / manifest.get("lot_output_schema", "")
    if schema_output_path.exists():
        print(f"[info] Lot output schema present: {schema_output_path.name}")
    else:
        print(f"[info] Lot output schema absent (to write): {schema_output_path.name}")

    # -----------------------------------------------------------------------
    # Check 9: Executors and states
    # -----------------------------------------------------------------------
    valid_executors = {"script", "llm", "human"}
    valid_states = {"existing", "to_write", "partially_written"}
    exec_violations = []

    for lot in lots:
        executor = lot.get("executor")
        if executor not in valid_executors:
            exec_violations.append((lot["id"], f"invalid executor: {executor}"))

        state = lot.get("state")
        if state not in valid_states:
            exec_violations.append((lot["id"], f"invalid state: {state}"))

        if executor == "llm" and not lot.get("prompt"):
            exec_violations.append((lot["id"], "llm executor without prompt"))

        if executor == "script":
            scripts = lot.get("scripts", []) + lot.get("scripts_to_write", [])
            if not scripts:
                exec_violations.append((lot["id"], "script executor without scripts"))

    if exec_violations:
        print(f"[ERROR] {len(exec_violations)} executor/state violation(s):")
        for lot_id, violation in exec_violations:
            print(f"    - lot '{lot_id}' : {violation}")
        print()
        errors += len(exec_violations)
    else:
        print("[OK] All executors and states are valid.")

    print()
    return errors


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Validation of the lot manifest of the EOF audit process.",
    )
    parser.add_argument(
        "manifest",
        type=Path,
        nargs="?",
        default=DEFAULT_MANIFEST,
        help=f"Path of the manifest (default: {DEFAULT_MANIFEST.relative_to(PROJECT_ROOT)})",
    )
    args = parser.parse_args()

    manifest_path = args.manifest
    if not manifest_path.exists():
        print(f"[ERROR] Manifest not found: {manifest_path}")
        return 1

    print("-" * 68)
    print(f"  LOT MANIFEST VALIDATION")
    print(f"  {manifest_path}")
    print("-" * 68)

    errors = check_manifest(manifest_path)

    if errors:
        print(f"[FAIL] {errors} problem(s) detected.")
        print()
        print("The manifest is not valid. Fix the violations above before")
        print("running the audit process.")
        return 1

    print("[SUCCESS] The manifest is valid.")
    print()
    print("All integrity checks passed. The audit process can")
    print("be orchestrated from this manifest.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
