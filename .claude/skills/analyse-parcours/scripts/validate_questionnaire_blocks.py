#!/usr/bin/env python3
"""
Validator for the EOF questionnaire block library.

This script validates questionnaire-blocs.json against eof-reference.json.

It checks:
- the JSON structure and mandatory/forbidden keys
- the values of enumerated fields (file, phase, type, interviewee)
- the coherence between the block type and its keys (direct vs composite)
- the existence of the referenced criteria in the reference
- the exact match of answer labels with the reference
- the absence of duplicates (block id, identical options within the same block)
- the coherence of criteria in a composite block (same criteria in all options)
- non-empty fields (title, question)
- the ban on the label "🤔 To be assessed" in composite blocks
- the absence of overlap (a criterion covered by several blocks)

What it does NOT check:
- the faithfulness of the question to the criterion's method (human judgment required)
- the relevance of grouping criteria into a composite block
- the balanced distribution between files or phases

Usage:
    python3 validate_questionnaire_blocks.py [--blocks PATH] [--reference PATH] [--autotest]

Exit codes:
    0 : validation successful
    1 : validation errors detected
    2 : file reading error or other system error
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple


# Closed vocabulary of interviewees, displayed as-is to the audited service after
# "to check with". Adding an entry here is a substantive decision: each entry
# must name a person the audited service can identify without hesitation.
INTERVIEWEES = {
    "the product manager",
    "the development team",
    "the person who operates the infrastructure",
    "the person who manages the data",
}


# Forbidden label in composite blocks: this label has a coefficient of 0,
# exactly like "✅ Confirmed strength", so the respondent who ticks this box
# raises the completeness and places a point at 0% on the radar, displaying an
# exemplary service when nobody knows anything. The generator already adds
# its own "I don't know" checkbox which records no answer.
# Note: "⌛️ Assessment in progress" (coefficient 0.5) is deliberately excluded from
# this lock, because the respondent who ticks it states something true.
FORBIDDEN_LABEL_COMPOSITE_BLOCK = "🤔 To be assessed"


# Default paths, resolved from THIS file's location and not from the current
# directory: otherwise the script only works when launched from the repo
# root, and returns a misleading "file not found" error everywhere else.
_SCRIPTS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPTS_DIR.parents[3]

DEFAULT_BLOCS = str(_SCRIPTS_DIR / "questionnaire-blocs.json")
DEFAULT_REFERENCE = str(
    _REPO_ROOT
    / ".claude/skills/eof/docs"
    / "EOF-V.1.1 (EROOM Optimization Framework) - Template - English"
    / "eof-reference.json"
)


class Validator:
    """Validates the block library against the EOF reference."""

    def __init__(self, blocks_data: Dict[str, Any], reference_data: Dict[str, Any]):
        self.blocks_data = blocks_data
        self.reference_data = reference_data
        self.errors: List[str] = []

        # Build the reference criteria index
        self.detailed_criteria = {c["id"]: c for c in reference_data.get("criteria", [])}
        self.quick_diag_criteria = {c["id"]: c for c in reference_data.get("quick_diagnostic", [])}
        self.all_criteria = {**self.detailed_criteria, **self.quick_diag_criteria}

    def validate(self) -> bool:
        """Runs all validations. Returns True if everything is valid."""
        self._validate_root_structure()

        if "blocks" not in self.blocks_data:
            return len(self.errors) == 0

        blocks = self.blocks_data["blocks"]
        if not isinstance(blocks, list):
            self.errors.append("The 'blocks' key must be a list")
            return False

        seen_ids = set()

        for i, block in enumerate(blocks):
            block_id = block.get("id", f"<block {i}>")

            # 1. Check duplicate ids
            if "id" in block:
                if block["id"] in seen_ids:
                    self.errors.append(f"{block_id}: duplicate block id")
                seen_ids.add(block["id"])

            # 2. Check keys
            self._validate_block_keys(block, block_id)

            # 3. Check enums
            self._validate_enums(block, block_id)

            # 4. Check type/keys coherence
            self._validate_type_coherence(block, block_id)

            # 5. Check criteria existence
            self._validate_criteria_existence(block, block_id)

            # 6. Check answer labels
            self._validate_answer_labels(block, block_id)

            # 7. Check the absence of forbidden labels in composite blocks
            self._validate_forbidden_labels(block, block_id)

            # 8 & 9. For composite blocks: identical options and criteria coherence
            if block.get("type") == "composite":
                self._validate_composite_block(block, block_id)

            # 10. Check non-empty fields
            self._validate_non_empty_fields(block, block_id)

        # 11. Check that a criterion is not covered by several blocks
        self._validate_criteria_uniqueness(blocks)

        return len(self.errors) == 0

    def _validate_root_structure(self):
        """Validates the top-level structure."""
        mandatory_keys = {"version", "blocks"}
        allowed_keys = mandatory_keys

        for key in mandatory_keys:
            if key not in self.blocks_data:
                self.errors.append(f"Missing mandatory key at root: {key}")

        for key in self.blocks_data:
            if key not in allowed_keys:
                self.errors.append(f"Unknown key at root: {key}")

    def _validate_block_keys(self, block: Dict[str, Any], block_id: str):
        """Validates a block's keys."""
        # "title" and "interviewee" are RENDERED at the top of the block in the questionnaire:
        # "## 3 of 41 - Legacy devices (to check with the product manager)".
        # The interviewee is mandatory so that no block goes out without saying who
        # the question is for: a question asked to the wrong person comes back unanswered,
        # and an unanswered block fills no criterion.
        mandatory_keys = {"id", "file", "phase", "title", "type", "question",
                          "interviewee"}
        # "note" is RENDERED in the questionnaire, so it is read by the audited person:
        # it addresses them, never the tool's developer. Put nothing in it that talks
        # about generation, filtering or a future job.
        # Addition for filters: "criteria", "discarded_label", "applicable_label"
        optional_keys = {"criterion", "options", "help", "note", "criteria",
                         "discarded_label", "applicable_label"}
        allowed_keys = mandatory_keys | optional_keys

        for key in mandatory_keys:
            if key not in block:
                self.errors.append(f"{block_id}: missing mandatory key: {key}")

        for key in block:
            if key not in allowed_keys:
                self.errors.append(f"{block_id}: unknown key: {key}")

    def _validate_enums(self, block: Dict[str, Any], block_id: str):
        """Validates the enumerated fields."""
        if "file" in block and block["file"] not in {"product-usage", "technical"}:
            self.errors.append(f"{block_id}: invalid file: {block['file']}")

        if "phase" in block and block["phase"] not in {"gate", "detail"}:
            self.errors.append(f"{block_id}: invalid phase: {block['phase']}")

        if "type" in block and block["type"] not in {"direct", "composite", "filter"}:
            self.errors.append(f"{block_id}: invalid type: {block['type']}")

        # Closed vocabulary: the interviewee is displayed as-is to the audited service,
        # after "to check with". A free list would let formulations drift from one
        # block to the next and make the questionnaire unreadable aloud.
        if "interviewee" in block and block["interviewee"] not in INTERVIEWEES:
            self.errors.append(
                f"{block_id}: invalid interviewee: {block['interviewee']}")

    def _validate_type_coherence(self, block: Dict[str, Any], block_id: str):
        """Validates the coherence between the type and the present keys."""
        if block.get("type") == "direct":
            if "criterion" not in block:
                self.errors.append(f"{block_id}: direct block without 'criterion' key")
            if "options" in block:
                self.errors.append(f"{block_id}: direct block must not have an 'options' key")
            if "criteria" in block:
                self.errors.append(f"{block_id}: direct block must not have a 'criteria' key")

        elif block.get("type") == "composite":
            if "criterion" in block:
                self.errors.append(f"{block_id}: composite block must not have a 'criterion' key")
            if "options" not in block:
                self.errors.append(f"{block_id}: composite block without 'options' key")
            if "criteria" in block:
                self.errors.append(f"{block_id}: composite block must not have a 'criteria' key")

        elif block.get("type") == "filter":
            if "criteria" not in block:
                self.errors.append(f"{block_id}: filter block without 'criteria' key")
            if "discarded_label" not in block:
                self.errors.append(f"{block_id}: filter block without 'discarded_label' key")
            if "applicable_label" not in block:
                self.errors.append(f"{block_id}: filter block without 'applicable_label' key")
            if "criterion" in block:
                self.errors.append(f"{block_id}: filter block must not have a 'criterion' (singular) key")
            if "options" in block:
                self.errors.append(f"{block_id}: filter block must not have an 'options' key")

    def _validate_criteria_existence(self, block: Dict[str, Any], block_id: str):
        """Validates that the referenced criteria exist in the reference."""
        if block.get("type") == "direct" and "criterion" in block:
            criterion_id = block["criterion"]
            if criterion_id not in self.all_criteria:
                self.errors.append(f"{block_id}: nonexistent criterion: {criterion_id}")

        elif block.get("type") == "composite" and "options" in block:
            for i, option in enumerate(block["options"]):
                if not isinstance(option, dict):
                    continue
                answers = option.get("answers", {})
                for criterion_id in answers:
                    if criterion_id not in self.all_criteria:
                        self.errors.append(f"{block_id}, option {i}: nonexistent criterion: {criterion_id}")

        elif block.get("type") == "filter" and "criteria" in block:
            filter_criteria = block["criteria"]
            if not isinstance(filter_criteria, list):
                self.errors.append(f"{block_id}: 'criteria' must be a list")
            else:
                for criterion_id in filter_criteria:
                    if criterion_id not in self.all_criteria:
                        self.errors.append(f"{block_id}: nonexistent criterion: {criterion_id}")
                        continue

                    # Check that the criterion is indeed from dimensions 1 to 5
                    # Dimension 6 criteria start with "6.", diagnostic questions with "0."
                    if criterion_id.startswith("6.") or criterion_id.startswith("0."):
                        self.errors.append(f"{block_id}: criterion {criterion_id} is not a detailed criterion (filters can only discard criteria from dimensions 1 to 5)")
                        continue

                    # Check that the criterion offers "🚫 Not applicable"
                    if criterion_id in self.detailed_criteria:
                        criterion = self.detailed_criteria[criterion_id]
                        options_coeff = criterion.get("evaluation_coefficient_options", {})
                        if "🚫 Not applicable" not in options_coeff:
                            self.errors.append(f"{block_id}: criterion {criterion_id} does not offer the option '🚫 Not applicable'")

    def _validate_answer_labels(self, block: Dict[str, Any], block_id: str):
        """Validates that answer labels match the reference."""
        if block.get("type") != "composite" or "options" not in block:
            return

        for i, option in enumerate(block["options"]):
            if not isinstance(option, dict):
                continue

            answers = option.get("answers", {})
            for criterion_id, answer_label in answers.items():
                if criterion_id not in self.all_criteria:
                    continue  # Already reported by _validate_criteria_existence

                criterion = self.all_criteria[criterion_id]

                # Determine the valid options according to the criterion type
                if criterion_id in self.quick_diag_criteria:
                    # Quick diagnostic: uses "screens"
                    valid_options = set(criterion.get("screens", []))
                else:
                    # Detailed criterion: uses "evaluation_coefficient_options"
                    valid_options = set(criterion.get("evaluation_coefficient_options", {}).keys())

                if answer_label not in valid_options:
                    self.errors.append(
                        f"{block_id}, option {i}: invalid answer label for {criterion_id}: '{answer_label}'"
                    )

    def _validate_forbidden_labels(self, block: Dict[str, Any], block_id: str):
        """Validates that no forbidden label is used in composite blocks."""
        if block.get("type") != "composite" or "options" not in block:
            return

        for i, option in enumerate(block["options"]):
            if not isinstance(option, dict):
                continue

            answers = option.get("answers", {})
            for criterion_id, answer_label in answers.items():
                if answer_label == FORBIDDEN_LABEL_COMPOSITE_BLOCK:
                    self.errors.append(
                        f"{block_id}, option {i}, criterion {criterion_id}: forbidden label "
                        f"'{FORBIDDEN_LABEL_COMPOSITE_BLOCK}' - this label has a coefficient of 0 "
                        f"and raises completeness without adding information"
                    )

    def _validate_composite_block(self, block: Dict[str, Any], block_id: str):
        """Validates the constraints specific to composite blocks."""
        if "options" not in block:
            return

        options = block["options"]
        if not isinstance(options, list):
            return

        # 7. Check that there are no two identical options
        seen_answers = []
        for i, option in enumerate(options):
            if not isinstance(option, dict):
                continue

            answers = option.get("answers", {})
            # Convert to a sorted tuple to be able to compare
            answers_tuple = tuple(sorted(answers.items()))

            if answers_tuple in seen_answers:
                self.errors.append(f"{block_id}, option {i}: option identical to another (same answers)")
            seen_answers.append(answers_tuple)

        # 8. Check that all options answer exactly the same criteria
        criteria_sets_per_option = []
        for i, option in enumerate(options):
            if not isinstance(option, dict):
                continue

            answers = option.get("answers", {})
            criteria_set = set(answers.keys())
            criteria_sets_per_option.append((i, criteria_set))

        if criteria_sets_per_option:
            first_set = criteria_sets_per_option[0][1]
            for i, criteria_set in criteria_sets_per_option[1:]:
                if criteria_set != first_set:
                    missing = first_set - criteria_set
                    extra = criteria_set - first_set
                    msg_parts = [f"{block_id}: options do not answer the same criteria"]
                    if missing:
                        msg_parts.append(f"option {i} missing: {missing}")
                    if extra:
                        msg_parts.append(f"option {i} extra: {extra}")
                    self.errors.append(" - ".join(msg_parts))

    def _validate_non_empty_fields(self, block: Dict[str, Any], block_id: str):
        """Validates that text fields are not empty."""
        for field in ["title", "question"]:
            if field in block:
                value = block[field]
                if not isinstance(value, str) or not value.strip():
                    self.errors.append(f"{block_id}: {field} empty")

    def _validate_criteria_uniqueness(self, blocks: List[Dict[str, Any]]):
        """
        Validates that a criterion is not covered by several blocks.

        Rule 4.4: the uniqueness rule does not apply to filter blocks versus
        direct/composite blocks, but applies between filters themselves.
        """
        # Two separate indexes: one for non-filter blocks, one for filters
        criterion_to_non_filter_blocks: Dict[str, List[str]] = {}
        criterion_to_filter_blocks: Dict[str, List[str]] = {}

        for block in blocks:
            if not isinstance(block, dict):
                continue

            block_id = block.get("id", "<no id>")
            block_type = block.get("type")

            # Collect the criteria covered by this block
            covered_criteria = set()

            if block_type == "direct" and "criterion" in block:
                covered_criteria.add(block["criterion"])

            elif block_type == "composite" and "options" in block:
                for option in block["options"]:
                    if isinstance(option, dict) and "answers" in option:
                        covered_criteria.update(option["answers"].keys())

            elif block_type == "filter" and "criteria" in block:
                covered_criteria.update(block["criteria"])

            # Register this block for each criterion it covers
            if block_type == "filter":
                for criterion_id in covered_criteria:
                    if criterion_id not in criterion_to_filter_blocks:
                        criterion_to_filter_blocks[criterion_id] = []
                    criterion_to_filter_blocks[criterion_id].append(block_id)
            else:
                for criterion_id in covered_criteria:
                    if criterion_id not in criterion_to_non_filter_blocks:
                        criterion_to_non_filter_blocks[criterion_id] = []
                    criterion_to_non_filter_blocks[criterion_id].append(block_id)

        # Report criteria covered by several non-filter blocks (direct/composite)
        for criterion_id, block_ids in criterion_to_non_filter_blocks.items():
            if len(block_ids) > 1:
                blocks_str = ", ".join(block_ids)
                self.errors.append(
                    f"Criterion {criterion_id} covered by several blocks (non-filter): {blocks_str}"
                )

        # Report criteria covered by several filter blocks
        for criterion_id, block_ids in criterion_to_filter_blocks.items():
            if len(block_ids) > 1:
                blocks_str = ", ".join(block_ids)
                self.errors.append(
                    f"Criterion {criterion_id} covered by several filter blocks: {blocks_str}"
                )

    def print_status_summary(self):
        """Prints a summary of the library."""
        if "blocks" not in self.blocks_data:
            return

        blocks = self.blocks_data["blocks"]

        # Count by file and phase
        file_counts = {}
        phase_counts = {}

        for block in blocks:
            file = block.get("file", "unknown")
            phase = block.get("phase", "unknown")

            file_counts[file] = file_counts.get(file, 0) + 1
            phase_counts[phase] = phase_counts.get(phase, 0) + 1

        # Count covered criteria and potential
        covered_criteria = set()
        total_potential = 0.0

        for block in blocks:
            if block.get("type") == "direct" and "criterion" in block:
                criterion_id = block["criterion"]
                covered_criteria.add(criterion_id)

                # Add the potential if it is a detailed criterion
                if criterion_id in self.detailed_criteria:
                    total_potential += self.detailed_criteria[criterion_id].get("max_potential", 0)

            elif block.get("type") == "composite" and "options" in block:
                for option in block["options"]:
                    if isinstance(option, dict) and "answers" in option:
                        for criterion_id in option["answers"]:
                            covered_criteria.add(criterion_id)

                            # Add the potential if it is a detailed criterion (only once)
                            if criterion_id in self.detailed_criteria:
                                total_potential += self.detailed_criteria[criterion_id].get("max_potential", 0)

        # Remove potential duplicates (if a criterion appears in several composite blocks)
        # Recompute properly
        covered_detailed_criteria = covered_criteria & set(self.detailed_criteria.keys())
        total_potential = sum(
            self.detailed_criteria[c].get("max_potential", 0)
            for c in covered_detailed_criteria
        )

        print("\n----- LIBRARY STATUS -----")
        print(f"Version: {self.blocks_data.get('version', 'not specified')}")
        print(f"Total number of blocks: {len(blocks)}")
        print(f"\nBreakdown by file:")
        for file, count in sorted(file_counts.items()):
            print(f"  {file}: {count} blocks")
        print(f"\nBreakdown by phase:")
        for phase, count in sorted(phase_counts.items()):
            print(f"  {phase}: {count} blocks")
        print(f"\nCovered criteria: {len(covered_criteria)} / {len(self.all_criteria)}")
        print(f"  - Quick diagnostic: {len(covered_criteria & set(self.quick_diag_criteria.keys()))} / {len(self.quick_diag_criteria)}")
        print(f"  - Detailed criteria: {len(covered_detailed_criteria)} / {len(self.detailed_criteria)}")
        print(f"\nCovered potential (detailed criteria only): {total_potential:.1f}")
        print(f"  Note: quick diagnostic questions have no max_potential.")
        print("---------------------------------------------\n")


def load_json(path: Path) -> Dict[str, Any]:
    """Loads a JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def autotest() -> bool:
    """Runs the autotests. Returns True if all tests pass."""
    print("----- AUTOTESTS -----")

    # Minimal test reference
    test_reference = {
        "criteria": [
            {
                "id": "1.1",
                "max_potential": 2.0,
                "evaluation_coefficient_options": {
                    "✅ Confirmed strength": 0,
                    "💡 Improvement potential identified": 1,
                    "🤔 To be assessed": 0,
                    "⌛️ Assessment in progress": 0.5
                }
            },
            {
                "id": "1.2",
                "max_potential": 1.5,
                "evaluation_coefficient_options": {
                    "✅ Confirmed strength": 0,
                    "💡 Improvement potential identified": 1
                }
            },
            {
                "id": "4.1",
                "max_potential": 1.5,
                "evaluation_coefficient_options": {
                    "✅ Confirmed strength": 0,
                    "💡 Improvement potential identified": 1,
                    "🚫 Not applicable": 0
                }
            },
            {
                "id": "4.2",
                "max_potential": 1.5,
                "evaluation_coefficient_options": {
                    "✅ Confirmed strength": 0,
                    "💡 Improvement potential identified": 1,
                    "🚫 Not applicable": 0
                }
            },
            {
                "id": "6.1",
                "max_potential": 2.0,
                "evaluation_coefficient_options": {
                    "🟢 Easy to change": 0,
                    "🟡 Moderate effort": 0.5,
                    "🔴 Hard to change": 1
                }
            }
        ],
        "quick_diagnostic": [
            {
                "id": "0.1",
                "screens": [
                    "1 - No impact",
                    "5 - Critical impact"
                ]
            }
        ]
    }

    tests_passed = 0
    total_tests = 0

    # Test 1: Valid direct block
    total_tests += 1
    valid_blocks = {
        "version": 1,
        "blocks": [
            {
                "id": "test-1",
                "file": "product-usage",
                "phase": "gate",
                "title": "Test", "interviewee": "the product manager",
                "type": "direct",
                "criterion": "0.1",
                "question": "Test question?"
            }
        ]
    }
    v = Validator(valid_blocks, test_reference)
    if v.validate():
        tests_passed += 1
        print("✓ Test 1: Valid direct block")
    else:
        print(f"✗ Test 1: Valid direct block - FAILED: {v.errors}")

    # Test 2: Duplicate ID (must fail)
    total_tests += 1
    duplicate_blocks = {
        "version": 1,
        "blocks": [
            {"id": "test-1", "file": "technical", "phase": "gate", "title": "A", "interviewee": "the product manager", "type": "direct", "criterion": "0.1", "question": "Q1"},
            {"id": "test-1", "file": "technical", "phase": "gate", "title": "B", "interviewee": "the product manager", "type": "direct", "criterion": "0.1", "question": "Q2"}
        ]
    }
    v = Validator(duplicate_blocks, test_reference)
    if not v.validate() and any("duplicate" in e for e in v.errors):
        tests_passed += 1
        print("✓ Test 2: Duplicate id detection")
    else:
        print(f"✗ Test 2: Duplicate id detection - FAILED")

    # Test 3: Missing mandatory key (must fail)
    total_tests += 1
    incomplete_blocks = {
        "version": 1,
        "blocks": [
            {"id": "test-3", "file": "technical", "phase": "gate", "type": "direct", "criterion": "0.1", "question": "Q"}
            # Missing "title"
        ]
    }
    v = Validator(incomplete_blocks, test_reference)
    if not v.validate() and any("title" in e and "missing" in e for e in v.errors):
        tests_passed += 1
        print("✓ Test 3: Missing mandatory key detection")
    else:
        print(f"✗ Test 3: Missing mandatory key detection - FAILED")

    # Test 4: Invalid file (must fail)
    total_tests += 1
    invalid_file_blocks = {
        "version": 1,
        "blocks": [
            {"id": "test-4", "file": "INVALID", "phase": "gate", "title": "T", "interviewee": "the product manager", "type": "direct", "criterion": "0.1", "question": "Q"}
        ]
    }
    v = Validator(invalid_file_blocks, test_reference)
    if not v.validate() and any("invalid file" in e for e in v.errors):
        tests_passed += 1
        print("✓ Test 4: Invalid file detection")
    else:
        print(f"✗ Test 4: Invalid file detection - FAILED")

    # Test 5: Direct block with options (must fail)
    total_tests += 1
    direct_with_options_blocks = {
        "version": 1,
        "blocks": [
            {
                "id": "test-5",
                "file": "technical",
                "phase": "gate",
                "title": "T", "interviewee": "the product manager",
                "type": "direct",
                "criterion": "0.1",
                "question": "Q",
                "options": []
            }
        ]
    }
    v = Validator(direct_with_options_blocks, test_reference)
    if not v.validate() and any("direct" in e and "options" in e for e in v.errors):
        tests_passed += 1
        print("✓ Test 5: Direct block with options detection")
    else:
        print(f"✗ Test 5: Direct block with options detection - FAILED")

    # Test 6: Composite block without options (must fail)
    total_tests += 1
    composite_without_options_blocks = {
        "version": 1,
        "blocks": [
            {
                "id": "test-6",
                "file": "technical",
                "phase": "detail",
                "title": "T", "interviewee": "the product manager",
                "type": "composite",
                "question": "Q"
            }
        ]
    }
    v = Validator(composite_without_options_blocks, test_reference)
    if not v.validate() and any("composite" in e and "options" in e for e in v.errors):
        tests_passed += 1
        print("✓ Test 6: Composite block without options detection")
    else:
        print(f"✗ Test 6: Composite block without options detection - FAILED")

    # Test 7: Nonexistent criterion (must fail)
    total_tests += 1
    nonexistent_criterion_blocks = {
        "version": 1,
        "blocks": [
            {
                "id": "test-7",
                "file": "technical",
                "phase": "gate",
                "title": "T", "interviewee": "the product manager",
                "type": "direct",
                "criterion": "99.99",
                "question": "Q"
            }
        ]
    }
    v = Validator(nonexistent_criterion_blocks, test_reference)
    if not v.validate() and any("nonexistent" in e for e in v.errors):
        tests_passed += 1
        print("✓ Test 7: Nonexistent criterion detection")
    else:
        print(f"✗ Test 7: Nonexistent criterion detection - FAILED")

    # Test 8: Invalid answer label (must fail)
    total_tests += 1
    invalid_label_blocks = {
        "version": 1,
        "blocks": [
            {
                "id": "test-8",
                "file": "technical",
                "phase": "detail",
                "title": "T", "interviewee": "the product manager",
                "type": "composite",
                "question": "Q",
                "options": [
                    {
                        "label": "Option 1",
                        "answers": {
                            "1.1": "INVALID ANSWER"
                        }
                    }
                ]
            }
        ]
    }
    v = Validator(invalid_label_blocks, test_reference)
    if not v.validate() and any("invalid answer label" in e for e in v.errors):
        tests_passed += 1
        print("✓ Test 8: Invalid answer label detection")
    else:
        print(f"✗ Test 8: Invalid answer label detection - FAILED")

    # Test 9: Identical options in a composite block (must fail)
    total_tests += 1
    identical_options_blocks = {
        "version": 1,
        "blocks": [
            {
                "id": "test-9",
                "file": "technical",
                "phase": "detail",
                "title": "T", "interviewee": "the product manager",
                "type": "composite",
                "question": "Q",
                "options": [
                    {
                        "label": "Option 1",
                        "answers": {"1.1": "✅ Confirmed strength"}
                    },
                    {
                        "label": "Option 2",
                        "answers": {"1.1": "✅ Confirmed strength"}
                    }
                ]
            }
        ]
    }
    v = Validator(identical_options_blocks, test_reference)
    if not v.validate() and any("option identical" in e for e in v.errors):
        tests_passed += 1
        print("✓ Test 9: Identical options detection")
    else:
        print(f"✗ Test 9: Identical options detection - FAILED")

    # Test 10: Inconsistent criteria between options of a composite block (must fail)
    total_tests += 1
    inconsistent_criteria_blocks = {
        "version": 1,
        "blocks": [
            {
                "id": "test-10",
                "file": "technical",
                "phase": "detail",
                "title": "T", "interviewee": "the product manager",
                "type": "composite",
                "question": "Q",
                "options": [
                    {
                        "label": "Option 1",
                        "answers": {
                            "1.1": "✅ Confirmed strength",
                            "1.2": "✅ Confirmed strength"
                        }
                    },
                    {
                        "label": "Option 2",
                        "answers": {
                            "1.1": "💡 Improvement potential identified"
                            # Missing 1.2
                        }
                    }
                ]
            }
        ]
    }
    v = Validator(inconsistent_criteria_blocks, test_reference)
    if not v.validate() and any("same criteria" in e for e in v.errors):
        tests_passed += 1
        print("✓ Test 10: Inconsistent criteria between options detection")
    else:
        print(f"✗ Test 10: Inconsistent criteria between options detection - FAILED")

    # Test 11: Empty field (must fail)
    total_tests += 1
    empty_field_blocks = {
        "version": 1,
        "blocks": [
            {
                "id": "test-11",
                "file": "technical",
                "phase": "gate",
                "title": "", "interviewee": "the product manager",
                "type": "direct",
                "criterion": "0.1",
                "question": "Q"
            }
        ]
    }
    v = Validator(empty_field_blocks, test_reference)
    if not v.validate() and any("title empty" in e for e in v.errors):
        tests_passed += 1
        print("✓ Test 11: Empty field detection")
    else:
        print(f"✗ Test 11: Empty field detection - FAILED")

    # Test 12: Valid composite block
    total_tests += 1
    valid_composite_blocks = {
        "version": 1,
        "blocks": [
            {
                "id": "test-12",
                "file": "technical",
                "phase": "detail",
                "title": "Test composite", "interviewee": "the product manager",
                "type": "composite",
                "question": "Question?",
                "options": [
                    {
                        "label": "Option A",
                        "answers": {
                            "1.1": "✅ Confirmed strength",
                            "1.2": "✅ Confirmed strength"
                        }
                    },
                    {
                        "label": "Option B",
                        "answers": {
                            "1.1": "💡 Improvement potential identified",
                            "1.2": "💡 Improvement potential identified"
                        }
                    }
                ]
            }
        ]
    }
    v = Validator(valid_composite_blocks, test_reference)
    if v.validate():
        tests_passed += 1
        print("✓ Test 12: Valid composite block")
    else:
        print(f"✗ Test 12: Valid composite block - FAILED: {v.errors}")

    # Test 13: Composite block with forbidden label "🤔 To be assessed" (must fail)
    total_tests += 1
    forbidden_label_blocks = {
        "version": 1,
        "blocks": [
            {
                "id": "test-13",
                "file": "technical",
                "phase": "detail",
                "title": "Test forbidden", "interviewee": "the product manager",
                "type": "composite",
                "question": "Question?",
                "options": [
                    {
                        "label": "Option A",
                        "answers": {
                            "1.1": "🤔 To be assessed"
                        }
                    }
                ]
            }
        ]
    }
    v = Validator(forbidden_label_blocks, test_reference)
    if not v.validate() and any("forbidden label" in e and "🤔 To be assessed" in e for e in v.errors):
        tests_passed += 1
        print("✓ Test 13: Forbidden label detection in composite block")
    else:
        print(f"✗ Test 13: Forbidden label detection in composite block - FAILED")

    # Test 14: Composite block with "⌛️ Assessment in progress" (must pass)
    total_tests += 1
    assessment_in_progress_blocks = {
        "version": 1,
        "blocks": [
            {
                "id": "test-14",
                "file": "technical",
                "phase": "detail",
                "title": "Test assessment in progress", "interviewee": "the product manager",
                "type": "composite",
                "question": "Question?",
                "options": [
                    {
                        "label": "Option A",
                        "answers": {
                            "1.1": "⌛️ Assessment in progress"
                        }
                    }
                ]
            }
        ]
    }
    v = Validator(assessment_in_progress_blocks, test_reference)
    if v.validate():
        tests_passed += 1
        print("✓ Test 14: Acceptance of '⌛️ Assessment in progress'")
    else:
        print(f"✗ Test 14: Acceptance of '⌛️ Assessment in progress' - FAILED: {v.errors}")

    # Test 15: Criterion covered by several blocks (must fail)
    total_tests += 1
    duplicated_criterion_blocks = {
        "version": 1,
        "blocks": [
            {
                "id": "test-15a",
                "file": "technical",
                "phase": "gate",
                "title": "Block A", "interviewee": "the product manager",
                "type": "direct",
                "criterion": "1.1",
                "question": "Q1"
            },
            {
                "id": "test-15b",
                "file": "technical",
                "phase": "detail",
                "title": "Block B", "interviewee": "the product manager",
                "type": "direct",
                "criterion": "1.1",
                "question": "Q2"
            }
        ]
    }
    v = Validator(duplicated_criterion_blocks, test_reference)
    if not v.validate() and any("several blocks" in e and "1.1" in e for e in v.errors):
        tests_passed += 1
        print("✓ Test 15: Criterion covered by several blocks detection")
    else:
        print(f"✗ Test 15: Criterion covered by several blocks detection - FAILED")

    # Test 16: Missing interviewee (must fail)
    # A block without an interviewee goes out without saying who the question is for.
    total_tests += 1
    missing_interviewee_blocks = {
        "version": 1,
        "blocks": [
            {
                "id": "test-16",
                "file": "technical",
                "phase": "gate",
                "title": "Block without interviewee",
                "type": "direct",
                "criterion": "1.1",
                "question": "Q"
            }
        ]
    }
    v = Validator(missing_interviewee_blocks, test_reference)
    if not v.validate() and any("interviewee" in e and "missing" in e for e in v.errors):
        tests_passed += 1
        print("✓ Test 16: Missing interviewee detection")
    else:
        print(f"✗ Test 16: Missing interviewee detection - FAILED: {v.errors}")

    # Test 17: Interviewee outside the closed vocabulary (must fail)
    # A free formulation would drift from one block to the next and make the
    # questionnaire unreadable aloud.
    total_tests += 1
    free_interviewee_blocks = {
        "version": 1,
        "blocks": [
            {
                "id": "test-17",
                "file": "technical",
                "phase": "gate",
                "title": "Free interviewee block",
                "interviewee": "the CTO",
                "type": "direct",
                "criterion": "1.1",
                "question": "Q"
            }
        ]
    }
    v = Validator(free_interviewee_blocks, test_reference)
    if not v.validate() and any("invalid interviewee" in e for e in v.errors):
        tests_passed += 1
        print("✓ Test 17: Interviewee outside closed vocabulary detection")
    else:
        print(f"✗ Test 17: Interviewee outside closed vocabulary detection - FAILED")

    # Test 18: Valid filter block
    total_tests += 1
    valid_filter_blocks = {
        "version": 1,
        "blocks": [
            {
                "id": "filter-donnees",
                "file": "technical",
                "phase": "gate",
                "title": "Persistent data",
                "interviewee": "the person who manages the data",
                "type": "filter",
                "criteria": ["4.1", "4.2"],
                "question": "Do you have data?",
                "discarded_label": "No",
                "applicable_label": "Yes"
            }
        ]
    }
    v = Validator(valid_filter_blocks, test_reference)
    if v.validate():
        tests_passed += 1
        print("✓ Test 18: Valid filter block")
    else:
        print(f"✗ Test 18: Valid filter block - FAILED: {v.errors}")

    # Test 19: Filter block with a criterion that does not offer "🚫 Not applicable" (must fail)
    total_tests += 1
    filter_criterion_without_na_blocks = {
        "version": 1,
        "blocks": [
            {
                "id": "filter-test",
                "file": "technical",
                "phase": "gate",
                "title": "Test",
                "interviewee": "the person who manages the data",
                "type": "filter",
                "criteria": ["1.1", "1.2"],
                "question": "Question?",
                "discarded_label": "No",
                "applicable_label": "Yes"
            }
        ]
    }
    v = Validator(filter_criterion_without_na_blocks, test_reference)
    if not v.validate() and any("does not offer the option" in e and "🚫 Not applicable" in e for e in v.errors):
        tests_passed += 1
        print("✓ Test 19: Criterion without '🚫 Not applicable' in filter detection")
    else:
        print(f"✗ Test 19: Criterion without '🚫 Not applicable' in filter detection - FAILED: {v.errors}")

    # Test 20: Filter block with a dimension 6 criterion (must fail)
    total_tests += 1
    filter_dim6_blocks = {
        "version": 1,
        "blocks": [
            {
                "id": "filter-dim6",
                "file": "technical",
                "phase": "gate",
                "title": "Test dim 6",
                "interviewee": "the development team",
                "type": "filter",
                "criteria": ["6.1"],
                "question": "Question?",
                "discarded_label": "No",
                "applicable_label": "Yes"
            }
        ]
    }
    v = Validator(filter_dim6_blocks, test_reference)
    if not v.validate() and any("dimensions 1 to 5" in e for e in v.errors):
        tests_passed += 1
        print("✓ Test 20: Dimension 6 criterion in filter detection")
    else:
        print(f"✗ Test 20: Dimension 6 criterion in filter detection - FAILED")

    # Test 21: Filter block + direct block on the same criterion (must pass - rule 4.4)
    total_tests += 1
    filter_and_direct_blocks = {
        "version": 1,
        "blocks": [
            {
                "id": "filter-donnees",
                "file": "technical",
                "phase": "gate",
                "title": "Data",
                "interviewee": "the person who manages the data",
                "type": "filter",
                "criteria": ["4.1", "4.2"],
                "question": "Do you have data?",
                "discarded_label": "No",
                "applicable_label": "Yes"
            },
            {
                "id": "direct-4.1",
                "file": "technical",
                "phase": "detail",
                "title": "Criterion 4.1",
                "interviewee": "the person who manages the data",
                "type": "direct",
                "criterion": "4.1",
                "question": "Question about 4.1?"
            }
        ]
    }
    v = Validator(filter_and_direct_blocks, test_reference)
    if v.validate():
        tests_passed += 1
        print("✓ Test 21: Filter + direct on the same criterion accepted")
    else:
        print(f"✗ Test 21: Filter + direct on the same criterion accepted - FAILED: {v.errors}")

    # Test 22: Two filter blocks with the same criterion (must fail - rule 4.4)
    total_tests += 1
    two_filters_same_criterion_blocks = {
        "version": 1,
        "blocks": [
            {
                "id": "filter-1",
                "file": "technical",
                "phase": "gate",
                "title": "Filter 1",
                "interviewee": "the person who manages the data",
                "type": "filter",
                "criteria": ["4.1"],
                "question": "Question 1?",
                "discarded_label": "No",
                "applicable_label": "Yes"
            },
            {
                "id": "filter-2",
                "file": "technical",
                "phase": "gate",
                "title": "Filter 2",
                "interviewee": "the person who manages the data",
                "type": "filter",
                "criteria": ["4.1"],
                "question": "Question 2?",
                "discarded_label": "No",
                "applicable_label": "Yes"
            }
        ]
    }
    v = Validator(two_filters_same_criterion_blocks, test_reference)
    if not v.validate() and any("several filter blocks" in e and "4.1" in e for e in v.errors):
        tests_passed += 1
        print("✓ Test 22: Two filters on the same criterion detection")
    else:
        print(f"✗ Test 22: Two filters on the same criterion detection - FAILED: {v.errors}")

    print(f"\n{tests_passed}/{total_tests} tests passed")
    print("---------------------\n")

    return tests_passed == total_tests


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Validates the EOF questionnaire block library")
    parser.add_argument("--blocks", type=str, default=DEFAULT_BLOCS, help="Path to questionnaire-blocs.json")
    parser.add_argument("--reference", type=str, default=DEFAULT_REFERENCE, help="Path to eof-reference.json")
    parser.add_argument("--autotest", action="store_true", help="Run the autotests")

    args = parser.parse_args()

    if args.autotest:
        if not autotest():
            return 2
        return 0

    # Normal validation
    try:
        blocks_path = Path(args.blocks)
        reference_path = Path(args.reference)

        if not blocks_path.exists():
            print(f"ERROR: File not found: {blocks_path}", file=sys.stderr)
            return 2

        if not reference_path.exists():
            print(f"ERROR: File not found: {reference_path}", file=sys.stderr)
            return 2

        print(f"Loading {blocks_path}...")
        blocks_data = load_json(blocks_path)

        print(f"Loading {reference_path}...")
        reference_data = load_json(reference_path)

        print("Validating...\n")

        validator = Validator(blocks_data, reference_data)
        valid = validator.validate()

        if not valid:
            print("----- VALIDATION ERRORS -----")
            for error in validator.errors:
                print(f"  ✗ {error}")
            print("---------------------------------\n")

            validator.print_status_summary()

            return 1

        print("✓ Validation successful: no error detected.\n")

        validator.print_status_summary()

        return 0

    except json.JSONDecodeError as e:
        print(f"ERROR: invalid JSON: {e}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
