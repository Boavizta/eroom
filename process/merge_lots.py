#!/usr/bin/env python3
"""
Merger for multi-agent EOF audit lots.

WHY THIS SCRIPT EXISTS
-----------------------
The EOF audit process is split into independent lots. Each lot (LLM agent,
script, or human) writes ONE results file conforming to lot-output-schema.json.
This script consolidates all these files into ONE audit result, according to
deterministic precedence rules and with no LLM in the loop.

Rationale: a deterministic aggregation guarantees that lot execution order has
NO effect on the result. Two consecutive runs over the same lots produce the
same file, except for the timestamp field (idempotence).

MERGE RULES (imperative, non-negotiable)
----------------------------------------
1. Precedence by provenance (read from the manifest):
   collected > estimated > stated > declared > assumed
   A higher provenance can NEVER be overwritten by a lower one.

2. Divergence (two DIFFERENT provenances with DIFFERENT answers):
   - Keep the answer of the highest-precedence provenance (with its coefficient)
   - Mark the divergence explicitly
   - Record the discrepancy in the context (which provenances, which answers, which one was kept)

3. Conflict (same provenance, different answers): REFUSE the merge, exit 1.
   The manifest guarantees that each criterion belongs to a single lot. If two
   lots carry the same criterion with the same provenance, that is a design flaw.

4. No data: answer=null, category=no_data, NOTHING invented.

5. Blocking validation: each lot file goes through validate_lot_output.py.
   A non-conforming file is REJECTED, never merged.

6. Enrichment from the reference: max_potential, dimension, criterion label are
   added by THIS SCRIPT from the reference, never read from a lot file.

7. Idempotence: two runs over the same lots = same file (except timestamp).

Usage:
    python3 merge_lots.py audits/<domain>

The audit directory contains:
  - lots/*.json        : lot output files, validated before merging
  - eof-audit-results.json : consolidated output (OVERWRITTEN by this script)
  - eof-radar-<domain>.svg : two-layer radar (OVERWRITTEN by this script)

⚠️ The radar is rewritten HERE, and not only by run_eof.py. Without this, merging
the audited service's answers updated the numbers but left on disk the image of
the automatic audit alone: the hatched layer, the declared one, could never
appear. The reader saw a radar poorer than the data.

Exit code: 0 if the merge succeeded, 1 otherwise.

Style alignment with check_efootprint_contract.py and validate_lot_output.py:
  - Visual banner with separators
  - [OK] / [FAIL] / [info] prefixes
  - Pedagogical final message
  - Structured output: list of violations, then verdict
"""

import argparse
import json
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

# Project root: this script lives in process/
PROJECT_ROOT = Path(__file__).resolve().parents[1]
REFERENCE_PATH = (
    PROJECT_ROOT
    / ".claude/skills/eof/docs/EOF-V.1.1 (EROOM Optimization Framework) - Template - English"
    / "eof-reference.json"
)
MANIFEST_PATH = PROJECT_ROOT / "process" / "lots-manifest.json"
VALIDATOR_PATH = PROJECT_ROOT / "process" / "validate_lot_output.py"

# Import the ownership resolution functions from the shared module
from criteria_ownership import compute_ownership

# The radar is drawn by the same module as the other producer, never copied
# here. This script already reaches into the `eof` skill for its reference:
# the dependency exists, it does not get worse.
sys.path.insert(0, str(PROJECT_ROOT / ".claude/skills/eof/scripts"))
from generate_radar_svg import build_radar_from_results  # noqa: E402


# ---------------------------------------------------------------------------
# Loading reference data
# ---------------------------------------------------------------------------

def load_json_file(path):
    """Load a JSON file, return (data, errors)."""
    if not path.exists():
        return None, [f"File not found: {path}"]
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f), []
    except (json.JSONDecodeError, OSError) as exc:
        return None, [f"Read error {path}: {exc}"]


def load_reference():
    """Load the EOF reference. Returns (criteria_dict, diagnostic_dict, errors)."""
    data, errors = load_json_file(REFERENCE_PATH)
    if errors:
        return None, None, errors

    criteria = {c["id"]: c for c in data.get("criteria", []) if "id" in c}
    diagnostic = {q["id"]: q for q in data.get("quick_diagnostic", []) if "id" in q}

    if not criteria and not diagnostic:
        return None, None, ["Reference empty or malformed"]

    return criteria, diagnostic, []


def load_manifest():
    """Load the lot manifest. Returns (manifest_data, precedence_list, errors)."""
    data, errors = load_json_file(MANIFEST_PATH)
    if errors:
        return None, None, errors

    precedence = data.get("conventions", {}).get("provenance_precedence")
    if not isinstance(precedence, list) or not precedence:
        return None, None, ["Manifest: conventions.provenance_precedence key missing or invalid"]

    return data, precedence, []


# ---------------------------------------------------------------------------
# Validating lot files
# ---------------------------------------------------------------------------

def validate_lot_file(lot_path):
    """Validate a lot file with validate_lot_output.py. Returns (ok, error_text)."""
    if not VALIDATOR_PATH.exists():
        return False, f"Validator not found: {VALIDATOR_PATH}"

    try:
        result = subprocess.run(
            [sys.executable, str(VALIDATOR_PATH), str(lot_path)],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            return True, None
        else:
            return False, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return False, "Validation timeout (> 30s)"
    except OSError as exc:
        return False, f"Error running the validator: {exc}"


# ---------------------------------------------------------------------------
# Merge logic
# ---------------------------------------------------------------------------


def merge_entries(entries_by_id, precedence_list, ref_criteria, ref_diagnostic, ownership_map, residual_lots, known_lot_ids):
    """
    Merge lot entries according to the precedence rules.

    Args:
        entries_by_id: dict {id: [entry1, entry2, ...]}
        precedence_list: ordered list of provenances (highest first)
        ref_criteria: dict {id: full_criterion} from the reference
        ref_diagnostic: dict {id: question} from the quick diagnostic
        ownership_map: dict {crit_id: [lot_id, ...]} for the ownership check
        residual_lots: dict {lot_id: provenance} of residual lots
        known_lot_ids: set of valid lot_id from the manifest

    Returns:
        (merged_entries, errors) where merged_entries is a list of merged criteria
    """
    merged = []
    errors = []

    # Create a provenance -> priority mapping (lower = higher priority)
    provenance_priority = {provenance: idx for idx, provenance in enumerate(precedence_list)}

    for cid, entries in sorted(entries_by_id.items()):
        # Criterion reference
        ref = ref_criteria.get(cid) or ref_diagnostic.get(cid)
        if not ref:
            errors.append(f"Criterion {cid} absent from the reference")
            continue

        # Validate the lot_id values
        for entry in entries:
            lot_id = entry.get("_lot_id")
            if lot_id and lot_id not in known_lot_ids:
                errors.append(f"Criterion {cid}: unknown lot_id '{lot_id}' (known lots: {sorted(known_lot_ids)})")
                continue

        # Ownership check: only owners and residual lots may set answers
        owners = ownership_map.get(cid, [])
        for entry in entries:
            lot_id = entry.get("_lot_id")
            answer = entry.get("answer")
            if answer is not None and lot_id not in owners and lot_id not in residual_lots:
                expected_owner = owners[0] if owners else "none"
                errors.append(
                    f"Criterion {cid}: lot '{lot_id}' set an answer but does not own this criterion "
                    f"(expected owner: {expected_owner})"
                )

        # Filter entries with a non-null answer
        with_answer = [e for e in entries if e.get("answer") is not None]

        # Collect all contexts (including from non-owning lots)
        all_contexts = [e.get("context") for e in entries if e.get("context")]

        if not with_answer:
            # No answer: take the first entry or create an empty one
            if entries:
                base = entries[0].copy()
                # Concatenate contexts if several
                if len(all_contexts) > 1:
                    base["context"] = " ; ".join(all_contexts)
            else:
                base = {
                    "id": cid,
                    "category": "no_data",
                    "answer": None,
                    "coefficient": None,
                    "provenance": None,
                    "source": None,
                    "context": None,
                    "not_applicable": None,
                }
            merged.append(base)
            continue

        # Group by provenance
        by_provenance = defaultdict(list)
        for e in with_answer:
            provenance = e.get("provenance")
            by_provenance[provenance].append(e)

        # Find the highest provenance present
        highest_provenance = None
        for provenance in precedence_list:
            if provenance in by_provenance:
                highest_provenance = provenance
                break

        if highest_provenance is None:
            errors.append(f"Criterion {cid}: no recognized provenance")
            continue

        entries_highest = by_provenance[highest_provenance]

        # Check conflicts at equal provenance
        unique_answers = set(e.get("answer") for e in entries_highest)
        if len(unique_answers) > 1:
            lot_ids = [e.get("_lot_id", "?") for e in entries_highest]
            errors.append(
                f"Criterion {cid}: conflict at equal provenance ({highest_provenance}) - "
                f"divergent answers: {unique_answers} - lots: {lot_ids}"
            )
            continue

        # Take the first entry of the highest provenance
        base = entries_highest[0].copy()

        # Check that the answer belongs to the reference vocabulary. The two
        # vocabularies do not use the same field name: the 54 detailed criteria have
        # `evaluation_options`, the 16 quick-diagnostic questions have `screens`
        # (scale 1 to 5). Reading only the first made the list empty for a
        # diagnostic question, so it rejected ANY answer set on it, 0.16 leading.
        # validate_lot_output.py already distinguishes the two: that is where the gap was.
        valid_options = ref.get("evaluation_options") or ref.get("screens") or []
        if base["answer"] not in valid_options:
            errors.append(
                f"Criterion {cid}: answer '{base['answer']}' absent from the "
                f"reference vocabulary (valid values: {valid_options})"
            )
            continue

        # Check divergences between different provenances
        other_provenances = [p for p in by_provenance if p != highest_provenance]
        if other_provenances:
            # Collect all answers of the other provenances
            other_answers = set()
            for provenance in other_provenances:
                for e in by_provenance[provenance]:
                    other_answers.add(e.get("answer"))

            # Is there a divergence (different answer)?
            if base["answer"] not in other_answers:
                # Divergence detected: keep the answer of the highest provenance
                # and record the discrepancy
                base["divergence"] = True

                # Build the explanatory context
                divergence_details = []
                for provenance in [highest_provenance] + other_provenances:
                    for e in by_provenance[provenance]:
                        divergence_details.append(f"{provenance}: '{e.get('answer')}'")

                base["context"] = (
                    f"Divergence between provenances - {'; '.join(divergence_details)} - "
                    f"retained answer (highest precedence provenance): {highest_provenance}"
                )

        # Concatenate additional contexts from non-owning lots
        if len(all_contexts) > 1 or (len(all_contexts) == 1 and not base.get("context")):
            if base.get("context"):
                base["context"] = base["context"] + " ; " + " ; ".join([c for c in all_contexts if c != base.get("context")])
            else:
                base["context"] = " ; ".join(all_contexts)

        merged.append(base)

    return merged, errors


def enrich_from_reference(entries, ref_criteria, ref_diagnostic):
    """
    Enrich entries with reference data (max_potential, dimension, label).
    Produces ONE entry for EACH criterion of the reference, even those without a lot.

    Args:
        entries: list of merged entries
        ref_criteria: dict {id: full_criterion}
        ref_diagnostic: dict {id: question}

    Returns:
        list of enriched entries for the final output format (54 criteria)
    """
    # Create a mapping of merged entries by ID
    entries_by_id = {e.get("id"): e for e in entries if e.get("id")}

    enriched = []

    # Iterate over ALL reference criteria in order
    for cid in sorted(ref_criteria.keys(), key=lambda x: (int(x.split('.')[0]), int(x.split('.')[1]))):
        ref = ref_criteria[cid]
        entry = entries_by_id.get(cid)

        if entry:
            # Merged entry exists
            enriched_entry = {
                "id": cid,
                "dimension": ref.get("pillar", ""),
                "criterion": ref.get("criterion", ""),
                "max_potential": ref.get("max_potential", 0),
                "category": entry.get("category", "no_data"),
                "answer": entry.get("answer"),
                "coefficient": entry.get("coefficient"),
                "provenance": entry.get("provenance"),
                "source": entry.get("source"),
                "context": entry.get("context"),
                "not_applicable": entry.get("not_applicable"),
            }
            # Add divergence if present
            if entry.get("divergence"):
                enriched_entry["divergence"] = True
        else:
            # No entry: create an empty one
            enriched_entry = {
                "id": cid,
                "dimension": ref.get("pillar", ""),
                "criterion": ref.get("criterion", ""),
                "max_potential": ref.get("max_potential", 0),
                "category": "no_data",
                "answer": None,
                "coefficient": None,
                "provenance": None,
                "source": None,
                "context": None,
                "not_applicable": None,
            }

        enriched.append(enriched_entry)

    return enriched


def compute_metrics(criteria, ref_criteria):
    """
    Compute aggregate metrics from the merged criteria.

    Returns:
        dict with:
          - answered_criteria: number of criteria with an answer (all provenances)
          - criteria_with_partial_evidence: number with a partial index
          - global_optimization_potential_pct: global percentage
          - global_completeness_pct: share of examined criteria over the total
          - dimensions: list of the 6 dimensions with potentials
          - answered_by_provenance: breakdown of answered criteria by provenance
    """
    # Define the 6 dimensions
    dimension_names = [
        "🛖 1 — Product",
        "🗺️ 2 — Architecture",
        "🏢 3 — Infrastructure",
        "💾 4 — Storage and data",
        "👨‍💻 5 — Algorithms & code",
        "🛠 6 — Ease of change",
    ]

    # Compute totals from the reference (ALL criteria)
    dimension_total_potentials = {name: 0.0 for name in dimension_names}
    dimension_counts = {name: 0 for name in dimension_names}

    for cid, ref in ref_criteria.items():
        pillar = ref.get("pillar", "")
        if pillar in dimension_names:
            dimension_counts[pillar] += 1
            dimension_total_potentials[pillar] += ref.get("max_potential", 0)

    # Aggregate potentials and completeness per dimension
    dimension_metrics = {name: {
        "retained_potential": 0.0,
        "total_potential": dimension_total_potentials[name],
        "answered": 0,
        "discarded_count": 0,
        "answered_by_provenance": {"collected": 0, "estimated": 0, "declared": 0, "stated": 0, "assumed": 0}
    } for name in dimension_names}

    criteria_answered = 0
    criteria_with_partial_index = 0
    discarded_criteria_global = 0
    answered_by_provenance_global = {"collected": 0, "estimated": 0, "declared": 0, "stated": 0, "assumed": 0}

    for c in criteria:
        pillar = c.get("dimension", "")
        if pillar not in dimension_names:
            continue

        category = c.get("category")
        answer = c.get("answer")
        coefficient = c.get("coefficient")
        max_potential = c.get("max_potential", 0)
        provenance = c.get("provenance")
        not_applicable = c.get("not_applicable")

        # Discarded-criterion mechanism: remove from BOTH numerator AND denameinator (convention 2.1)
        # Two equivalent paths: not_applicable=true OR answer="🚫 Not applicable" (convention 2)
        is_discarded = not_applicable or answer == "🚫 Not applicable"
        if is_discarded:
            dimension_metrics[pillar]["discarded_count"] += 1
            dimension_metrics[pillar]["total_potential"] -= max_potential
            discarded_criteria_global += 1
            continue

        # ANY answer counts, whatever its provenance or category
        if answer is not None:
            criteria_answered += 1
            dimension_metrics[pillar]["answered"] += 1

            # Count by provenance
            if provenance in answered_by_provenance_global:
                answered_by_provenance_global[provenance] += 1
                dimension_metrics[pillar]["answered_by_provenance"][provenance] += 1

            # Retained potential calculation
            if coefficient is not None:
                retained_potential = coefficient * max_potential
                dimension_metrics[pillar]["retained_potential"] += retained_potential

        if category == "partial" and c.get("context"):
            criteria_with_partial_index += 1

    # Compute percentages per dimension
    dimensions = []
    total_potential_global = 0.0
    retained_potential_global = 0.0
    examined_criteria_global = 0
    # Fix the inconsistency: remove the discarded ones from the global denameinator (convention 2.1)
    total_criteria_global = len(ref_criteria) - discarded_criteria_global

    for name in dimension_names:
        stats = dimension_metrics[name]
        total_potential = stats["total_potential"]
        retained_potential = stats["retained_potential"]
        answered = stats["answered"]
        discarded = stats["discarded_count"]
        total_criteria = dimension_counts[name] - discarded

        # Guardrail: a fully discarded dimension must NEVER output 0% (convention 2, guardrail)
        out_of_scope = (discarded == dimension_counts[name])

        # Optimization potential: denameinator = ALL criteria of the dimension, minus discarded ones.
        # ⚠️ An axis where NOTHING was answered is worth None, never 0.0. The denameinator is always
        # non-null, so testing only it put 0% on empty dimensions: on the radar, a
        # 0% reads as an exemplary service when it only says "nobody looked".
        # This is the rule of compute_dimension_scores() in run_eof.py, whose twin this
        # calculation is (cf. the invariant of the two producers); the gap only became visible
        # once a real merged lot file existed, which had never happened before 2026-09-07.
        if out_of_scope:
            optimization_potential_pct = None
            completeness_pct = None
            total_criteria = 0
        elif answered > 0 and total_potential > 0:
            optimization_potential_pct = (retained_potential / total_potential) * 100
            completeness_pct = (answered / total_criteria) * 100 if total_criteria > 0 else 0
        else:
            optimization_potential_pct = None
            completeness_pct = (answered / total_criteria) * 100 if total_criteria > 0 else 0

        dimensions.append({
            "name": name,
            "optimization_potential_pct": optimization_potential_pct,
            "completeness_pct": completeness_pct,
            "answered": answered,
            "total": total_criteria,
            "answered_by_provenance": stats["answered_by_provenance"],
            "discarded": discarded,
            "out_of_scope": out_of_scope,
        })

        total_potential_global += total_potential
        retained_potential_global += retained_potential
        examined_criteria_global += answered

    # Global calculation
    if total_potential_global > 0:
        global_optimization_potential_pct = (retained_potential_global / total_potential_global) * 100
    else:
        global_optimization_potential_pct = None

    if total_criteria_global > 0:
        global_completeness_pct = (examined_criteria_global / total_criteria_global) * 100
    else:
        global_completeness_pct = None

    return {
        "total_criteria": total_criteria_global,
        "answered_criteria": criteria_answered,
        "criteria_with_partial_evidence": criteria_with_partial_index,
        "discarded_criteria": discarded_criteria_global,
        "global_optimization_potential_pct": global_optimization_potential_pct,
        "global_completeness_pct": global_completeness_pct,
        "answered_by_provenance": answered_by_provenance_global,
        "dimensions": dimensions,
    }


def build_quick_diag_overview(entries_by_id, ref_diagnostic):
    """Build the quick_diag_overview section from the merged entries."""
    questions = []

    for qid in sorted(ref_diagnostic.keys(), key=lambda x: float(x.split(".")[-1])):
        ref = ref_diagnostic[qid]
        entries = entries_by_id.get(qid, [])

        # Take the first entry or create an empty one
        if entries:
            entry = entries[0]
            question = {
                "id": qid,
                "criterion": ref.get("criterion", ""),
                "impact_level": ref.get("impact_level", ""),
                "answer": entry.get("answer"),
                "provenance": entry.get("provenance"),
                "source": entry.get("source"),
                "context_index": entry.get("context"),
            }
        else:
            question = {
                "id": qid,
                "criterion": ref.get("criterion", ""),
                "impact_level": ref.get("impact_level", ""),
                "answer": None,
                "provenance": None,
                "source": None,
                "context_index": None,
            }

        questions.append(question)

    return {
        "total_questions": len(ref_diagnostic),
        "note": (
            "Scale 1 to 5, never filled in automatically — to be assessed by a human. "
            "Exception: 0.16 (exact duplicate of 3.3), cf. eof-question-minimization-analysis.md."
        ),
        "questions": questions,
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def autotest():
    """Replay the embedded test cases on the discarded-criterion arithmetic."""
    import tempfile

    failures = []
    total = 0

    # Minimal reference for the tests
    ref_criteria = {
        "1.1": {"id": "1.1", "pillar": "🛖 1 — Product", "criterion": "Criterion 1.1", "max_potential": 3.0, "evaluation_options": ["✅ Confirmed strength", "💡 Improvement potential identified", "🚫 Not applicable"]},
        "1.2": {"id": "1.2", "pillar": "🛖 1 — Product", "criterion": "Criterion 1.2", "max_potential": 2.5, "evaluation_options": ["✅ Confirmed strength", "💡 Improvement potential identified", "🚫 Not applicable"]},
        "2.1": {"id": "2.1", "pillar": "🗺️ 2 — Architecture", "criterion": "Criterion 2.1", "max_potential": 10.0, "evaluation_options": ["✅ Confirmed strength", "💡 Improvement potential identified", "🚫 Not applicable"]},
        "2.2": {"id": "2.2", "pillar": "🗺️ 2 — Architecture", "criterion": "Criterion 2.2", "max_potential": 10.0, "evaluation_options": ["✅ Confirmed strength", "💡 Improvement potential identified", "🚫 Not applicable"]},
        "2.3": {"id": "2.3", "pillar": "🗺️ 2 — Architecture", "criterion": "Criterion 2.3", "max_potential": 5.0, "evaluation_options": ["✅ Confirmed strength", "💡 Improvement potential identified", "🤔 To be assessed"]},
        "2.4": {"id": "2.4", "pillar": "🗺️ 2 — Architecture", "criterion": "Criterion 2.4", "max_potential": 5.0, "evaluation_options": ["✅ Confirmed strength", "💡 Improvement potential identified", "🤔 To be assessed"]},
        "3.1": {"id": "3.1", "pillar": "🏢 3 — Infrastructure", "criterion": "Criterion 3.1", "max_potential": 2.0, "evaluation_options": ["✅ Confirmed strength", "💡 Improvement potential identified"]},
        "3.2": {"id": "3.2", "pillar": "🏢 3 — Infrastructure", "criterion": "Criterion 3.2", "max_potential": 2.0, "evaluation_options": ["✅ Confirmed strength", "💡 Improvement potential identified", "🚫 Not applicable"]},
        "3.3": {"id": "3.3", "pillar": "🏢 3 — Infrastructure", "criterion": "Criterion 3.3", "max_potential": 2.0, "evaluation_options": ["✅ Confirmed strength", "💡 Improvement potential identified"]},
        "4.1": {"id": "4.1", "pillar": "💾 4 — Storage and data", "criterion": "Criterion 4.1", "max_potential": 4.0, "evaluation_options": ["✅ Confirmed strength", "💡 Improvement potential identified"]},
        "4.2": {"id": "4.2", "pillar": "💾 4 — Storage and data", "criterion": "Criterion 4.2", "max_potential": 4.0, "evaluation_options": ["✅ Confirmed strength", "💡 Improvement potential identified"]},
    }

    # Case 1: a fully discarded dimension must NEVER output 0%
    # WHY 0 would be wrong: "🚫 Not applicable" and "✅ Confirmed strength" share
    # coefficient 0, so a fully discarded dimension displayed at 0% would pass for
    # the BEST-rated one in the report.
    total += 1
    try:
        criteria = [
            {"id": "1.1", "dimension": "🛖 1 — Product", "max_potential": 3.0, "category": "no_data", "answer": "🚫 Not applicable", "coefficient": 0, "provenance": None, "source": None, "context": None, "not_applicable": None},
            {"id": "1.2", "dimension": "🛖 1 — Product", "max_potential": 2.5, "category": "no_data", "answer": "🚫 Not applicable", "coefficient": 0, "provenance": None, "source": None, "context": None, "not_applicable": None},
        ]
        metrics = compute_metrics(criteria, ref_criteria)
        dim = next((d for d in metrics["dimensions"] if d["name"] == "🛖 1 — Product"), None)

        if not dim:
            failures.append(("Fully discarded dimension", "dimension not found"))
        elif not dim["out_of_scope"]:
            failures.append(("Fully discarded dimension", f"out_of_scope should be True, got {dim['out_of_scope']}"))
        elif dim["optimization_potential_pct"] is not None:
            failures.append(("Fully discarded dimension", f"optimization_potential_pct should be None, got {dim['optimization_potential_pct']}"))
        elif dim["optimization_potential_pct"] == 0:
            failures.append(("Fully discarded dimension", "optimization_potential_pct is 0 (should be None) — WHY 0 IS WRONG: coefficient 0 = as good as an ✅ Confirmed strength"))
        elif dim["completeness_pct"] is not None:
            failures.append(("Fully discarded dimension", f"completeness_pct should be None, got {dim['completeness_pct']}"))
        elif dim["total"] != 0:
            failures.append(("Fully discarded dimension", f"total should be 0, got {dim['total']}"))
        elif dim["discarded"] != 2:
            failures.append(("Fully discarded dimension", f"discarded should be 2, got {dim['discarded']}"))
    except Exception as exc:
        failures.append(("Fully discarded dimension", f"Exception: {exc}"))

    # Case 2: partially discarded dimension (discriminating numbers)
    # Choose numbers where the error would show: if we COUNTED the discarded ones,
    # the calculation would be DIFFERENT.
    # Criteria: 2 discarded (max_potential 10 each), 2 kept (max_potential 5 each).
    # One kept criterion has coefficient 0.5, the other 0.2.
    # CORRECT retained potential: (0.5 * 5 + 0.2 * 5) / 10 = 3.5 / 10 = 35 %
    # WRONG retained potential (if we counted the discarded ones): 3.5 / 30 = 11.67 %
    total += 1
    try:
        criteria = [
            {"id": "2.1", "dimension": "🗺️ 2 — Architecture", "max_potential": 10.0, "category": "no_data", "answer": "🚫 Not applicable", "coefficient": 0, "provenance": None, "source": None, "context": None, "not_applicable": None},
            {"id": "2.2", "dimension": "🗺️ 2 — Architecture", "max_potential": 10.0, "category": "no_data", "answer": "🚫 Not applicable", "coefficient": 0, "provenance": None, "source": None, "context": None, "not_applicable": None},
            {"id": "2.3", "dimension": "🗺️ 2 — Architecture", "max_potential": 5.0, "category": "automatable", "answer": "💡 Improvement potential identified", "coefficient": 0.5, "provenance": "collected", "source": "test", "context": None, "not_applicable": None},
            {"id": "2.4", "dimension": "🗺️ 2 — Architecture", "max_potential": 5.0, "category": "automatable", "answer": "🤔 To be assessed", "coefficient": 0.2, "provenance": "estimated", "source": "test", "context": None, "not_applicable": None},
        ]
        metrics = compute_metrics(criteria, ref_criteria)
        dim = next((d for d in metrics["dimensions"] if d["name"] == "🗺️ 2 — Architecture"), None)

        expected = 35.0
        wrong_calculation = 11.67
        if not dim:
            failures.append(("Partially discarded dimension", "dimension not found"))
        elif dim["optimization_potential_pct"] is None:
            failures.append(("Partially discarded dimension", "optimization_potential_pct is None (should be 35.0)"))
        elif abs(dim["optimization_potential_pct"] - expected) > 0.1:
            failures.append(("Partially discarded dimension", f"optimization_potential_pct expected {expected}%, got {dim['optimization_potential_pct']:.2f}% — WRONG calculation would give {wrong_calculation}%"))
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
    # compute_metrics() calculates over ALL reference criteria, so I must pass
    # a complete list (all criteria, even those without an answer)
    total += 1
    try:
        criteria = []
        for cid in ref_criteria.keys():
            if cid == "3.1":
                criteria.append({"id": "3.1", "dimension": "🏢 3 — Infrastructure", "max_potential": 2.0, "category": "automatable", "answer": "✅ Confirmed strength", "coefficient": 0, "provenance": "collected", "source": "test", "context": None, "not_applicable": None})
            elif cid == "3.2":
                criteria.append({"id": "3.2", "dimension": "🏢 3 — Infrastructure", "max_potential": 2.0, "category": "no_data", "answer": "🚫 Not applicable", "coefficient": 0, "provenance": None, "source": None, "context": None, "not_applicable": None})
            else:
                ref = ref_criteria[cid]
                criteria.append({"id": cid, "dimension": ref["pillar"], "max_potential": ref["max_potential"], "category": "no_data", "answer": None, "coefficient": None, "provenance": None, "source": None, "context": None, "not_applicable": None})

        metrics = compute_metrics(criteria, ref_criteria)

        # 1 discarded, 11 - 1 = 10 kept
        if metrics["total_criteria"] != 10:
            failures.append(("total_criteria accounting", f"total_criteria (kept) should be 10, got {metrics['total_criteria']}"))
        elif metrics["discarded_criteria"] != 1:
            failures.append(("total_criteria accounting", f"discarded_criteria should be 1, got {metrics['discarded_criteria']}"))
        elif metrics["total_criteria"] + metrics["discarded_criteria"] != 11:
            failures.append(("total_criteria accounting", f"total_criteria + discarded_criteria should be 11 (reference total), got {metrics['total_criteria'] + metrics['discarded_criteria']}"))
    except Exception as exc:
        failures.append(("total_criteria accounting", f"Exception: {exc}"))

    # Case 4: no discarded criterion = same numbers as before session 26, discarded_criteria == 0
    total += 1
    try:
        criteria = [
            {"id": "4.1", "dimension": "💾 4 — Storage and data", "max_potential": 4.0, "category": "automatable", "answer": "💡 Improvement potential identified", "coefficient": 0.5, "provenance": "collected", "source": "test", "context": None, "not_applicable": None},
            {"id": "4.2", "dimension": "💾 4 — Storage and data", "max_potential": 4.0, "category": "automatable", "answer": "✅ Confirmed strength", "coefficient": 0, "provenance": "collected", "source": "test", "context": None, "not_applicable": None},
        ]
        metrics = compute_metrics(criteria, ref_criteria)
        dim = next((d for d in metrics["dimensions"] if d["name"] == "💾 4 — Storage and data"), None)

        expected = 25.0  # (0.5 * 4) / 8 = 25%
        if not dim:
            failures.append(("No discarded criterion", "dimension not found"))
        elif metrics["discarded_criteria"] != 0:
            failures.append(("No discarded criterion", f"discarded_criteria should be 0, got {metrics['discarded_criteria']}"))
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

    # Case 5: TWO PATHS (not_applicable=true AND answer="🚫 Not applicable") give IDENTICAL numbers
    total += 1
    try:
        # First path: answer="🚫 Not applicable"
        criteria_answer_path = [
            {"id": "1.1", "dimension": "🛖 1 — Product", "max_potential": 3.0, "category": "no_data", "answer": "🚫 Not applicable", "coefficient": 0, "provenance": None, "source": None, "context": None, "not_applicable": None},
            {"id": "1.2", "dimension": "🛖 1 — Product", "max_potential": 2.5, "category": "automatable", "answer": "✅ Confirmed strength", "coefficient": 0, "provenance": "collected", "source": "test", "context": None, "not_applicable": None},
        ]
        # Second path: not_applicable=true
        criteria_not_applicable_path = [
            {"id": "1.1", "dimension": "🛖 1 — Product", "max_potential": 3.0, "category": "no_data", "answer": None, "coefficient": None, "provenance": None, "source": None, "context": None, "not_applicable": True},
            {"id": "1.2", "dimension": "🛖 1 — Product", "max_potential": 2.5, "category": "automatable", "answer": "✅ Confirmed strength", "coefficient": 0, "provenance": "collected", "source": "test", "context": None, "not_applicable": None},
        ]

        metrics_answer = compute_metrics(criteria_answer_path, ref_criteria)
        metrics_not_applicable = compute_metrics(criteria_not_applicable_path, ref_criteria)

        dim_answer = next((d for d in metrics_answer["dimensions"] if d["name"] == "🛖 1 — Product"), None)
        dim_not_applicable = next((d for d in metrics_not_applicable["dimensions"] if d["name"] == "🛖 1 — Product"), None)

        if not dim_answer or not dim_not_applicable:
            failures.append(("Two equivalent paths", "dimension not found"))
        elif metrics_answer["discarded_criteria"] != metrics_not_applicable["discarded_criteria"]:
            failures.append(("Two equivalent paths", f"discarded_criteria differs: answer={metrics_answer['discarded_criteria']}, not_applicable={metrics_not_applicable['discarded_criteria']}"))
        elif dim_answer["discarded"] != dim_not_applicable["discarded"]:
            failures.append(("Two equivalent paths", f"discarded per dimension differs: answer={dim_answer['discarded']}, not_applicable={dim_not_applicable['discarded']}"))
        elif dim_answer["total"] != dim_not_applicable["total"]:
            failures.append(("Two equivalent paths", f"total differs: answer={dim_answer['total']}, not_applicable={dim_not_applicable['total']}"))
        elif dim_answer["optimization_potential_pct"] != dim_not_applicable["optimization_potential_pct"]:
            failures.append(("Two equivalent paths", f"optimization_potential_pct differs: answer={dim_answer['optimization_potential_pct']}, not_applicable={dim_not_applicable['optimization_potential_pct']}"))
        elif dim_answer["completeness_pct"] != dim_not_applicable["completeness_pct"]:
            failures.append(("Two equivalent paths", f"completeness_pct differs: answer={dim_answer['completeness_pct']}, not_applicable={dim_not_applicable['completeness_pct']}"))
    except Exception as exc:
        failures.append(("Two equivalent paths", f"Exception: {exc}"))

    if failures:
        print(f"AUTOTEST FAILED: {len(failures)} case(s) out of {total}")
        for label, error_msg in failures:
            print(f"  - {label}")
            print(f"      {error_msg}")
        return 1

    print(f"Autotest: {total} cases passed.")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Merge EOF multi-agent audit lot files into a single consolidated result. "
                    "Blocking validation, deterministic precedence rules, no LLM."
    )
    parser.add_argument("audit_dir", type=Path, nargs="?",
                        help="Audit directory containing lots/ and where to write eof-audit-results.json")
    parser.add_argument("--autotest", action="store_true", help="replay the embedded test cases and exit 1 if a case fails")
    args = parser.parse_args()

    if args.autotest:
        sys.exit(autotest())

    if not args.audit_dir:
        parser.error("audit_dir is required (or use --autotest)")

    audit_dir = args.audit_dir
    if not audit_dir.exists():
        print(f"[error] Directory not found: {audit_dir}")
        return 1

    lots_dir = audit_dir / "lots"
    if not lots_dir.exists():
        print(f"[error] lots/ subdirectory not found: {lots_dir}")
        return 1

    output_path = audit_dir / "eof-audit-results.json"
    domain = audit_dir.name

    print("-" * 68)
    print(f"  EOF LOT MERGE — {domain}")
    print(f"  directory : {audit_dir}")
    print(f"  lots      : {lots_dir}")
    print(f"  output    : {output_path}")
    print("-" * 68)
    print()

    # Load the reference
    ref_criteria, ref_diagnostic, ref_errors = load_reference()
    if ref_errors:
        print("[FAIL] Unable to load the reference:")
        for err in ref_errors:
            print(f"    {err}")
        return 1

    print(f"[info] Reference loaded: {len(ref_criteria)} criteria, {len(ref_diagnostic)} questions")

    # Load the manifest
    manifest_data, precedence, manifest_errors = load_manifest()
    if manifest_errors:
        print("[FAIL] Unable to load the manifest:")
        for err in manifest_errors:
            print(f"    {err}")
        return 1

    print(f"[info] Provenance precedence: {' > '.join(precedence)}")

    # Compute ownership from the manifest
    lots = manifest_data.get("lots", [])
    all_criteria = list(ref_criteria.keys())
    ownership_map, _, residual_lots, _, ownership_errors = compute_ownership(lots, all_criteria)

    if ownership_errors:
        print("[FAIL] Unable to compute criterion ownership:")
        for err in ownership_errors:
            print(f"    {err}")
        return 1

    known_lot_ids = {lot["id"] for lot in lots}
    print(f"[info] Ownership computed: {len(lots)} lots, {len(known_lot_ids)} known lot_id")
    if residual_lots:
        print(f"[info] Residual lots: {', '.join(residual_lots.keys())}")
    print()

    # List and validate the lot files
    lot_files = sorted(lots_dir.glob("*.json"))
    if not lot_files:
        print(f"[warning] No lot file found in {lots_dir}")
        print("[info] Merge cancelled: impossible to produce a result without lots")
        return 1

    print(f"[info] {len(lot_files)} lot file(s) detected")
    print()

    all_entries_by_id = defaultdict(list)
    validation_failures = []

    for lot_path in lot_files:
        print(f"[validation] {lot_path.name} ... ", end="")
        ok, error_msg = validate_lot_file(lot_path)

        if not ok:
            print("FAIL")
            validation_failures.append((lot_path.name, error_msg))
            continue

        print("OK")

        # Load the lot file
        lot_data, load_errors = load_json_file(lot_path)
        if load_errors:
            validation_failures.append((lot_path.name, f"Load error: {load_errors[0]}"))
            continue

        # Collect entries by ID
        for entry in lot_data.get("criteria", []):
            cid = entry.get("id")
            if cid:
                # Add the lot name for traceability in case of conflict
                entry["_lot_id"] = lot_data.get("lot_id", lot_path.stem)
                all_entries_by_id[cid].append(entry)

    print()

    if validation_failures:
        print(f"[FAIL] {len(validation_failures)} non-conforming file(s):")
        for filename, msg in validation_failures:
            print(f"    {filename} :")
            for line in (msg or "").splitlines()[:10]:  # Limit display
                print(f"        {line}")
        print()
        print("Fix the lot files above and rerun the merge.")
        return 1

    # Merge the entries
    print("[merge] Applying the precedence rules...")
    merged_entries, merge_errors = merge_entries(
        all_entries_by_id, precedence, ref_criteria, ref_diagnostic, ownership_map, residual_lots, known_lot_ids
    )

    if merge_errors:
        print(f"[FAIL] {len(merge_errors)} merge error(s):")
        for err in merge_errors:
            print(f"    {err}")
        print()
        print("Check the manifest and the lot files. The merge is refused.")
        return 1

    print(f"[OK] {len(merged_entries)} entr(ies) merged")

    # Enrichment from the reference
    print("[enrichment] Adding reference data...")
    enriched = enrich_from_reference(merged_entries, ref_criteria, ref_diagnostic)
    print(f"[OK] {len(enriched)} criterion/criteria enriched")

    # Compute the metrics
    print("[metrics] Computing aggregates...")
    metrics = compute_metrics(enriched, ref_criteria)
    print(f"[OK] Answered criteria: {metrics['answered_criteria']}/{len(ref_criteria)}")
    if metrics["global_completeness_pct"] is not None:
        print(f"[OK] Global completeness: {metrics['global_completeness_pct']:.1f}%")
    if metrics["global_optimization_potential_pct"] is not None:
        print(f"[OK] Global optimization potential: {metrics['global_optimization_potential_pct']:.1f}%")

    # Build the quick diagnostic
    diagnostic_overview = build_quick_diag_overview(all_entries_by_id, ref_diagnostic)

    # Assemble the final result
    audit_results = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "domain": domain,
        "total_criteria": metrics["total_criteria"],
        "answered_criteria": metrics["answered_criteria"],
        "discarded_criteria": metrics["discarded_criteria"],
        "criteria_with_partial_evidence": metrics["criteria_with_partial_evidence"],
        "global_completeness_pct": metrics["global_completeness_pct"],
        "global_optimization_potential_pct": metrics["global_optimization_potential_pct"],
        "answered_by_provenance": metrics["answered_by_provenance"],
        "dimensions": metrics["dimensions"],
        "quick_diag_overview": diagnostic_overview,
        "criteria": enriched,
    }

    # Write the output file
    print()
    print(f"[write] {output_path} ... ", end="")
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(audit_results, f, ensure_ascii=False, indent=2)
        print("OK")
    except OSError as exc:
        print("FAIL")
        print(f"[error] Unable to write the file: {exc}")
        return 1

    radar_path = audit_dir / f"eof-radar-{domain}.svg"
    print(f"[write] {radar_path} ... ", end="")
    try:
        radar_path.write_text(
            build_radar_from_results(audit_results, domain), encoding="utf-8"
        )
        print("OK")
    except OSError as exc:
        print("FAIL")
        print(f"[error] Unable to write the radar: {exc}")
        return 1

    print()
    print("-" * 68)
    print("[SUCCESS] Merge completed")
    print(f"  File produced     : {output_path}")
    print(f"  Answered criteria : {metrics['answered_criteria']}/{len(ref_criteria)}")
    if metrics["global_completeness_pct"] is not None:
        print(f"  Global completeness : {metrics['global_completeness_pct']:.1f}%")
    if metrics["global_optimization_potential_pct"] is not None:
        print(f"  Global potential  : {metrics['global_optimization_potential_pct']:.1f}%")
    print("-" * 68)

    return 0


if __name__ == "__main__":
    sys.exit(main())
