#!/usr/bin/env python3
"""
Safety net for the e-footprint refactoring: CONTRACT check on the output.

WHY THIS SCRIPT EXISTS
----------------------
The HTML report reads `efootprint-python-summary.json` key by key with
`.get()`. If a key is missing, it does not fail: it shows a hole, or a
default value, WITHOUT ANY ERROR. A refactoring can therefore break the
report silently.

This script compares a FROZEN BASELINE against a fresh output and reports:
  - LOST paths            -> ERROR (the report will lose information)
  - TYPE-CHANGED paths    -> ERROR (e.g. a float turned into str)
  - ADDED paths           -> information only (an addition is legitimate)

WHAT IT DOES NOT DO, AND THAT MATTERS
-------------------------------------
It does NOT check that the values are CORRECT. A total going from 174 to
300 kg with all keys in place would not be detected here. That is the role of
the `--total` option, to be used in addition, not instead.

Usage:
    # 1. Freeze the baseline BEFORE touching the code (do once)
    python3 check_efootprint_contract.py --freeze audits/<site>

    # 2. After each change: compare
    python3 check_efootprint_contract.py audits/<site>

    # 3. Comparison + numeric check of the total
    python3 check_efootprint_contract.py audits/<site> --total 174.076 --tol 1e-3

Useful options:
    --baseline <path>   explicit baseline (default: tmp/baselines/<site>-efootprint-python-summary.json)
    --results <path>    output to check (default: <source_dir>/efootprint-python-summary.json)
    --strict-added      also treat ADDED paths as errors

Exit code: 0 if the contract holds, 1 otherwise. Meant for `&&` chaining
or end-of-batch verification.

Baselines live in `tmp/baselines/`, outside git (`tmp/` is in .gitignore):
they are work artifacts, not deliverables, and they contain the measured
values of the test case.
"""

import argparse
import json
import sys
from pathlib import Path

# Project root: this script lives in .claude/skills/analyse-parcours/scripts/
PROJECT_ROOT = Path(__file__).resolve().parents[4]
BASELINE_DIR = PROJECT_ROOT / "tmp" / "baselines"

SUMMARY_FILENAME = "efootprint-python-summary.json"

# Paths whose value changes on every run without anything being broken.
# Comparing their content would make no sense; their PRESENCE and TYPE still
# do, so they stay in the path inventory.
VOLATILE_PATHS = {
    "/generated_at",
}


# ---------------------------------------------------------------------------
# Flattening into typed paths
# ---------------------------------------------------------------------------

def flatten(obj, prefix=""):
    """Flattens a JSON into {path: type_name}.

    An empty dict and a list are leaves: we do not descend into them. Lists
    change length from one site to another, and their content is not a stable
    contract. The `list` type alone is enough to detect a disappearance.
    """
    out = {}
    if isinstance(obj, dict):
        if not obj:
            out[prefix] = "dict"
        for key, value in obj.items():
            out.update(flatten(value, f"{prefix}/{key}"))
    elif isinstance(obj, list):
        out[prefix] = "list"
    else:
        out[prefix] = type(obj).__name__
    return out


def compatible(type_before, type_after):
    """Is a type change acceptable?

    Two tolerances, and no more:
      - int <-> float: rounding or division can flip one into the other
        without changing the meaning of the value.
      - NoneType -> something else: a field that was null and now carries a
        value is a GAIN. The opposite (a value turned null) is a LOSS and
        stays reported.
    """
    if type_before == type_after:
        return True
    numeric = {"int", "float"}
    if type_before in numeric and type_after in numeric:
        return True
    if type_before == "NoneType":
        return True
    return False


# ---------------------------------------------------------------------------
# File locations
# ---------------------------------------------------------------------------

def default_baseline_path(source_dir):
    """tmp/baselines/<audit-case-name>-efootprint-python-summary.json"""
    return BASELINE_DIR / f"{source_dir.name}-{SUMMARY_FILENAME}"


def load_json(path, label):
    if not path.exists():
        print(f"[error] {label} not found: {path}")
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as exc:
        print(f"[error] {label} is not valid JSON: {path}")
        print(f"         {exc}")
        return None


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------

def freeze(source_dir, results_path, baseline_path):
    """Copies the current output as the reference."""
    data = load_json(results_path, "results file")
    if data is None:
        return 1

    paths = flatten(data)
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    with open(baseline_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"[freeze] Baseline frozen: {baseline_path}")
    print(f"[freeze] {len(paths)} paths under contract.")
    total = data.get("totals", {}).get("total_kg_co2e_per_year")
    if total is not None:
        print(f"[freeze] Reference total: {total} kg CO2e/year")
        print(f"[freeze] To also lock the value: --total {total}")
    return 0


def compare(baseline, results, strict_added):
    """Compares two outputs. Returns (nb_errors, nb_added)."""
    before = flatten(baseline)
    after = flatten(results)

    lost = sorted(set(before) - set(after))
    added = sorted(set(after) - set(before))
    retyped = sorted(
        (p, before[p], after[p])
        for p in set(before) & set(after)
        if not compatible(before[p], after[p])
    )

    print(f"[contract] {len(before)} paths in baseline, {len(after)} in the output.")
    print()

    if lost:
        print(f"[ERROR] {len(lost)} LOST path(s) — the report will lose this information:")
        for path in lost:
            print(f"    - {path}   (was {before[path]})")
        print()
    else:
        print("[OK] 0 missing keys.")

    if retyped:
        print(f"[ERROR] {len(retyped)} path(s) that CHANGED TYPE:")
        for path, type_before, type_after in retyped:
            print(f"    - {path}   {type_before} -> {type_after}")
        print()
    else:
        print("[OK] 0 incompatible type changes.")

    if added:
        marker = "ERROR" if strict_added else "info"
        print(f"[{marker}] {len(added)} ADDED path(s):")
        for path in added:
            print(f"    + {path}   ({after[path]})")
        print()
    else:
        print("[info] 0 paths added.")

    errors = len(lost) + len(retyped) + (len(added) if strict_added else 0)
    return errors, len(added)


def check_total(results, expected, tolerance):
    """Checks the annual total. Complements the contract check, does not replace it."""
    actual = results.get("totals", {}).get("total_kg_co2e_per_year")
    if actual is None:
        print("[ERROR] /totals/total_kg_co2e_per_year missing: total cannot be verified.")
        return 1

    delta = abs(actual - expected)
    if delta <= tolerance:
        print(f"[OK] Total {actual} kg CO2e/year (expected {expected}, delta {delta:.2e}).")
        return 0

    print(f"[ERROR] Total {actual} kg CO2e/year, expected {expected} "
           f"(delta {delta:.4f} > tolerance {tolerance}).")
    return 1


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Contract check on efootprint-python-summary.json "
                    "(keys present and typed, not correct values).",
    )
    parser.add_argument("source_dir", type=Path,
                        help="Audit case, e.g. audits/octo.com")
    parser.add_argument("--freeze", action="store_true",
                        help="Freezes the current output as baseline, then stops.")
    parser.add_argument("--baseline", type=Path, default=None,
                        help="Explicit baseline (default: tmp/baselines/<site>-...json).")
    parser.add_argument("--results", type=Path, default=None,
                        help="Output to check (default: <source_dir>/efootprint-python-summary.json).")
    parser.add_argument("--strict-added", action="store_true",
                        help="Treats added paths as errors.")
    parser.add_argument("--total", type=float, default=None,
                        help="Expected total in kg CO2e/year (numeric check).")
    parser.add_argument("--tol", type=float, default=1e-3,
                        help="Tolerance on --total (default: 1e-3).")
    args = parser.parse_args()

    source_dir = args.source_dir
    if not source_dir.is_dir():
        print(f"[error] Audit case not found: {source_dir}")
        return 1

    results_path = args.results or (source_dir / SUMMARY_FILENAME)
    baseline_path = args.baseline or default_baseline_path(source_dir)

    if args.freeze:
        return freeze(source_dir, results_path, baseline_path)

    baseline = load_json(baseline_path, "baseline")
    if baseline is None:
        print()
        print("No baseline. Freeze it first, BEFORE any code change:")
        print(f"    python3 {Path(__file__).name} {source_dir} --freeze")
        return 1

    results = load_json(results_path, "results file")
    if results is None:
        print()
        print("Generate the output first:")
        print(f"    python3 run_efootprint.py {source_dir}")
        return 1

    print("-" * 68)
    print(f"  e-footprint CONTRACT — {source_dir.name}")
    print(f"  baseline: {baseline_path}")
    print(f"  output  : {results_path}")
    print("-" * 68)
    print()

    errors, _ = compare(baseline, results, args.strict_added)

    if args.total is not None:
        errors += check_total(results, args.total, args.tol)
        print()

    if errors:
        print(f"[FAIL] {errors} problem(s). The contract does not hold.")
        return 1

    print("[SUCCESS] Contract holds.")
    print("Reminder: the keys are present and typed. This does NOT prove that the")
    print("values are correct (except for the total, if --total was provided).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
