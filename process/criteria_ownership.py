#!/usr/bin/env python3
"""
EOF criteria ownership resolution module.

Extraction of the functions shared between validate_manifest.py and merge_lots.py
to guarantee that criterion ownership is determined by the same logic in
validation AND in merging. Any divergence between these two scripts silently
breaks the guarantee that lot execution order has no effect on the result.

Three forms of ownership defined in the manifest:
  - {"id_prefix": "3."} -> all criteria whose id starts with this prefix
  - {"source": "<path>", "rule": "..."} -> criteria that the mapping table
    (eof_criteria_mapping.py) declares automatable
  - {"rule": "..."} with neither source nor id_prefix -> COMPLEMENT set: all
    criteria that no one else owns (at most one complement lot)

Ownership vs context:
  - Owning a criterion = the right to put an `answer` on it (a firm verdict)
  - Contributing a context = the right to write a `context` there without a verdict
  - A lot may contribute a context on a criterion it does not own

Three-pass resolution convention (to handle `except_lots`):
  1. Resolve ownerships without `except_lots`
  2. Resolve ownerships with `except_lots` (requires partial ownership)
  3. Resolve allowed contexts for all lots
"""

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_mapping():
    """Load the MAPPING from eof_criteria_mapping.py and return (automatable, partial).

    Automatable: criteria settled by script; the lot owns these criteria.
    Partial: criteria where the script provides a context; the verdict stays
    with the dimension lot.
    """
    mapping_path = (
        PROJECT_ROOT / ".claude" / "skills" / "analyse-parcours" / "scripts"
        / "eof_criteria_mapping.py"
    )
    if not mapping_path.exists():
        return None, None

    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("eof_criteria_mapping", mapping_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        mapping = getattr(module, "MAPPING", {})
        automatable = {
            crit_id
            for crit_id, meta in mapping.items()
            if meta.get("category") == "automatable"
        }
        partial = {
            crit_id
            for crit_id, meta in mapping.items()
            if meta.get("category") == "partial"
        }
        return automatable, partial
    except Exception:
        return None, None


def resolve_owned_criteria(lot, all_criteria, automatable, ownership_so_far):
    """Return the set of criteria owned by a lot.

    Returns None if the rule is dynamic (complement), or an empty set if the
    lot owns no criterion (collection, gate, merge, or residual lots).

    Now handles except_lots: {"id_prefix": "1.", "except_lots": ["automatic-judgment"]}
    means "all 1.X criteria minus those owned by automatic-judgment".

    Now handles residual: {"residual": true, ...} means the lot owns no
    criterion exclusively but may answer on any criterion.

    Args:
        lot: lot dict from the manifest
        all_criteria: list of all criterion IDs from the reference
        automatable: set of automatable IDs from eof_criteria_mapping.py
        ownership_so_far: dict {crit_id: [lot_id, ...]} filled by already-resolved lots

    Returns:
        set of owned criteria, or None for a complement rule
    """
    criteria = lot.get("owned_criteria")
    if criteria is None:
        return set()

    # Residual lot: owns no criterion exclusively
    if criteria.get("residual"):
        return set()

    owned = set()

    if "id_prefix" in criteria:
        prefix = criteria["id_prefix"]
        owned = {c for c in all_criteria if c.startswith(prefix)}

        # Subtract the criteria owned by the lots listed in except_lots
        except_lots = criteria.get("except_lots", [])
        for except_lot_id in except_lots:
            for crit_id in list(owned):
                if crit_id in ownership_so_far and except_lot_id in ownership_so_far[crit_id]:
                    owned.discard(crit_id)

        return owned

    if "source" in criteria:
        if automatable is None:
            return set()
        # The lot owns the automatable criteria (settled by script)
        return automatable.copy()

    if "rule" in criteria and "source" not in criteria and "id_prefix" not in criteria:
        return None

    return set()


def resolve_allowed_contexts(lot, all_criteria, partial):
    """Return the set of criteria on which the lot may write a context.

    A lot may write a context on a criterion it does not own.
    For the automatic lot: the partial-category criteria.
    Also handles id_prefix for tests (pathological case).

    Args:
        lot: lot dict from the manifest
        all_criteria: list of all criterion IDs from the reference
        partial: set of partial IDs from eof_criteria_mapping.py

    Returns:
        set of criteria on which the lot may contribute a context
    """
    contexts = lot.get("allowed_contexts")
    if contexts is None:
        return set()

    if "source" in contexts:
        if partial is None:
            return set()
        return partial.copy()

    if "id_prefix" in contexts:
        prefix = contexts["id_prefix"]
        return {c for c in all_criteria if c.startswith(prefix)}

    return set()


def compute_ownership(lots, all_criteria):
    """Compute the full ownership of all criteria from the list of lots.

    Returns (ownership_map, complement_lots, residual_lots, contexts_by_lot, errors) where:
      - ownership_map: dict {crit_id: [lot_id, ...]}
      - complement_lots: list of lots declaring a complement rule
      - residual_lots: dict {lot_id: provenance} of residual lots (no criteria of their own)
      - contexts_by_lot: dict {lot_id: set(crit_ids)}
      - errors: list of error messages (empty if all OK)

    Three-pass resolution to handle except_lots and complements.
    """
    automatable, partial = load_mapping()
    if automatable is None:
        # Do not fail, just signal
        automatable = set()
        partial = set()

    ownership = {}
    complement_lots = []
    residual_lots = {}
    contexts_by_lot = {}
    errors = []

    # First pass: resolve criteria without except_lots and identify residual lots
    for lot in lots:
        criteria = lot.get("owned_criteria")
        if criteria:
            # Detect residual lots
            if criteria.get("residual"):
                provenances = lot.get("allowed_provenances", [])
                if provenances:
                    residual_lots[lot["id"]] = provenances[0]  # First provenance
            elif "except_lots" not in criteria:
                owned = resolve_owned_criteria(lot, all_criteria, automatable, ownership)
                if owned is None:
                    complement_lots.append(lot["id"])
                elif owned:
                    for crit_id in owned:
                        if crit_id not in ownership:
                            ownership[crit_id] = []
                        ownership[crit_id].append(lot["id"])

    # Second pass: resolve criteria with except_lots
    for lot in lots:
        criteria = lot.get("owned_criteria")
        if criteria and "except_lots" in criteria and not criteria.get("residual"):
            owned = resolve_owned_criteria(lot, all_criteria, automatable, ownership)
            if owned is None:
                complement_lots.append(lot["id"])
            elif owned:
                for crit_id in owned:
                    if crit_id not in ownership:
                        ownership[crit_id] = []
                    ownership[crit_id].append(lot["id"])

    # Third pass: resolve allowed contexts
    for lot in lots:
        contexts = resolve_allowed_contexts(lot, all_criteria, partial)
        if contexts:
            contexts_by_lot[lot["id"]] = contexts

    # Resolve the complement lot if there is exactly one
    if len(complement_lots) > 1:
        errors.append(f"{len(complement_lots)} complement lots (ambiguity)")
    elif len(complement_lots) == 1:
        complement_id = complement_lots[0]
        uncovered = set(all_criteria) - set(ownership.keys())
        for crit_id in uncovered:
            ownership[crit_id] = [complement_id]

    return ownership, complement_lots, residual_lots, contexts_by_lot, errors
