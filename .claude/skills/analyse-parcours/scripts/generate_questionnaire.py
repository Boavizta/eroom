#!/usr/bin/env python3
"""
Generation of EOF questionnaires from an existing audit.

Reads eof-audit-results.json, eof-reference.json and questionnaire-blocs.json
to produce a single Markdown file containing the questions still to be
answered, sorted by decreasing yield.

The residual: a criterion is part of the residual if it has no useful verdict.
WARNING: "🤔 To be assessed" and "⌛️ Assessment in progress" count as
answers in the rest of the code (coefficient 0) but DECIDE NOTHING. These
answers must be re-asked. Reason: avoid a criterion never being
asked and remaining a false zero.

Usage:
    python3 generate_questionnaire.py <audit-dir> --output-dir <other-dir>
    python3 generate_questionnaire.py --autotest

Writes questionnaire-eof.md into the directory specified by --output-dir.

By default, REFUSES to write into a path containing "audits" (a blank
questionnaire must never be found in audits/ to avoid the accidental sending
of an unfilled file). Pass --in-audit-dir to force.

NEVER modifies questionnaire-blocs.json nor its validator.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Section separator, never "-----" (read letter by letter by macOS TTS)
SEPARATOR = "-----"

# Answers that decide nothing and must be re-asked
NON_DECISIVE_ANSWERS = {
    "🤔 To be assessed",
    "⌛️ Assessment in progress",
}


def strip_dnk_mention(label):
    """
    Cleans the "I don't know" mention from a quick diagnostic screen label.

    Underlying reason: some screens of the reference contain "I don't know"
    glued to the worst case (e.g. "1 - Very complex / I don't know"). This cleaning
    avoids a respondent who does not know being assigned the worst case by ticking
    this option - we add a separate "I don't know" checkbox that records no
    answer.

    This cleaning is PURELY cosmetic and changes NOTHING about the recorded answer:
    the parser finds the original screen again via the <!-- opt:N --> index and goes
    to re-read it in the reference.

    Examples of mentions to remove (case variants and separators):
    - "/ I don't know"
    - "/ i don't know"
    - "or I don't know"
    - "I don't know" (at the end of the label)

    Returns the cleaned label, or the original label if cleaning would
    empty it completely.
    """
    if not isinstance(label, str):
        return label

    import re

    # Pattern to detect "I don't know" with variants (and the old French form)
    # Capture common separators before the mention
    pattern = r"\s*[/]?\s*(or\s+|ou\s+)?(?:i\s+don'?t\s+know|je\s+ne\s+sais\s+pas)\.?"

    # Clean (case-insensitive)
    cleaned = re.sub(pattern, '', label, flags=re.IGNORECASE).strip()

    # If cleaning empties the label or leaves only the screen number,
    # return the original intact
    if not cleaned or re.match(r'^\d+\s*-?\s*$', cleaned):
        return label

    return cleaned


def find_reference():
    """Finds the EOF reference in the tree."""
    # Search from the script's directory upwards
    current = Path(__file__).resolve().parent
    for _ in range(5):  # Climb up to 5 levels
        matches = list(current.glob("**/eof-reference.json"))
        matches = [m for m in matches if ".venv" not in str(m)]
        if matches:
            return matches[0]
        current = current.parent
    raise FileNotFoundError("eof-reference.json not found")


def load_reference(path):
    """Loads the reference and returns a dict {id: criterion} and {id: question}."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    criteria = {c["id"]: c for c in data["criteria"]}
    quick_diag = {q["id"]: q for q in data["quick_diagnostic"]}

    return criteria, quick_diag


def load_audit_results(audit_dir):
    """Loads the existing audit results and extracts the contexts."""
    path = audit_dir / "eof-audit-results.json"
    if not path.exists():
        raise FileNotFoundError(f"eof-audit-results.json not found in {audit_dir}")

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    # Extract the contexts for fact recall
    # Key = criterion or question id, value = context text
    contexts = {}

    # Detailed criteria (1.x to 6.x)
    for c in data.get("criteria", []):
        cid = c["id"]
        ctx = c.get("context")
        # Pitfall 1: a key can exist and be null
        if ctx is not None and isinstance(ctx, str) and ctx.strip():
            contexts[cid] = ctx.strip()

    # Quick diagnostic questions (0.x)
    diag_overview = data.get("quick_diag_overview", {})
    for q in diag_overview.get("questions", []):
        qid = q["id"]
        indice = q.get("context_index")
        # Pitfall 1: a key can exist and be null
        if indice is not None and isinstance(indice, str) and indice.strip():
            contexts[qid] = indice.strip()

    return data, contexts


def load_blocks(scripts_dir):
    """Loads the block library."""
    path = scripts_dir / "questionnaire-blocs.json"
    if not path.exists():
        raise FileNotFoundError(f"questionnaire-blocs.json not found in {scripts_dir}")

    with open(path, encoding="utf-8") as f:
        return json.load(f)


def compute_residual(audit_results, criteria_ref, quick_diag_ref):
    """
    Computes the set of criteria still in the residual.

    A criterion is in the residual if:
    - it has no answer
    - or its answer is "🤔 To be assessed" or "⌛️ Assessment in progress"

    A quick diagnostic question is in the residual if it has no answer.
    """
    residual = set()

    # Detailed criteria (1.x to 6.x)
    for c in audit_results.get("criteria", []):
        cid = c["id"]
        answer = c.get("answer")

        if answer is None or answer in NON_DECISIVE_ANSWERS:
            residual.add(cid)

    # Quick diagnostic questions (0.x)
    diag_overview = audit_results.get("quick_diag_overview", {})
    for q in diag_overview.get("questions", []):
        qid = q["id"]
        answer = q.get("answer")

        if answer is None or answer in NON_DECISIVE_ANSWERS:
            residual.add(qid)

    return residual


def get_criteria_from_block(block, criteria_ref, quick_diag_ref):
    """Returns the list of criteria covered by a block."""
    if block["type"] == "direct":
        # Direct block: a single criterion
        return [block["criterion"]]
    elif block["type"] == "filter":
        # Filter block: list of discarded criteria
        return block.get("criteria", [])
    else:
        # Composite block: extract all criteria from the options. Sorted order so
        # that the output is deterministic (list(set(...)) depends on the hash-seed of
        # the Python process, so it changed from one replay to the next for no reason).
        criteria = set()
        for option in block.get("options", []):
            for cid in option.get("answers", {}).keys():
                criteria.add(cid)
        return sorted(criteria)


def compute_block_potential(block, residual, criteria_ref, quick_diag_ref):
    """
    Computes the total potential of a block (sum of the max_potential of the criteria
    still in the residual).

    Quick diagnostic questions have no max_potential: count as 0.
    """
    criteria = get_criteria_from_block(block, criteria_ref, quick_diag_ref)
    potential = 0.0

    for cid in criteria:
        if cid not in residual:
            continue

        # Quick diagnostic questions: no max_potential
        if cid.startswith("0."):
            continue

        # Detailed criterion
        if cid in criteria_ref:
            potential += criteria_ref[cid]["max_potential"]

    return potential


def filter_block_must_be_removed(block, audit_results):
    """
    Checks whether a filter block must be removed according to rule 4.2.

    A filter is printed only if NONE of its criteria already carries a
    decisive answer (i.e. an answer absent from NON_DECISIVE_ANSWERS).

    Returns True if the filter must be removed, False otherwise.
    """
    if block.get("type") != "filter":
        return False

    filter_criteria = block.get("criteria", [])

    # Build an index {criterion_id: answer} from audit_results
    answers = {}

    # Detailed criteria
    for c in audit_results.get("criteria", []):
        answers[c["id"]] = c.get("answer")

    # Quick diagnostic questions
    diag_overview = audit_results.get("quick_diag_overview", {})
    for q in diag_overview.get("questions", []):
        answers[q["id"]] = q.get("answer")

    # Check whether at least one criterion of the filter has a decisive answer
    for cid in filter_criteria:
        answer = answers.get(cid)
        if answer is not None and answer not in NON_DECISIVE_ANSWERS:
            # A decisive answer exists: remove the filter
            return True

    return False


def select_and_sort_blocks(blocks_data, residual, criteria_ref, quick_diag_ref, audit_results=None):
    """
    Selects and sorts the blocks to display in the single questionnaire.

    A block is kept if at least one of its criteria is in the residual.
    A filter block is removed if one of its criteria already has a decisive answer.

    Sort: decreasing yield (number of criteria), then phase "gate" before
    "detail", then reference order (0.x, then 1.x to 6.x).
    """
    selected_blocks = []

    for block in blocks_data["blocks"]:
        # Rule 4.2: remove a filter if one of its criteria is already decided
        if audit_results and filter_block_must_be_removed(block, audit_results):
            continue

        criteria = get_criteria_from_block(block, criteria_ref, quick_diag_ref)

        # Keep if at least one criterion is in the residual
        residual_criteria = [c for c in criteria if c in residual]
        if residual_criteria:
            potential = compute_block_potential(block, residual, criteria_ref, quick_diag_ref)
            yield_count = len(residual_criteria)
            selected_blocks.append((block, potential, criteria, yield_count))

    # Special sort: filters at the head of the detail part, sorted among themselves by yield,
    # then all other blocks (gate then detail) sorted by yield/reference order
    def parse_criterion_id(criterion_id):
        """
        Extracts the numeric components of a criterion id for numeric sorting.
        E.g. "0.10" -> (0, 10), "1.5" -> (1, 5)
        """
        import re
        match = re.search(r'(\d+)\.(\d+)', criterion_id)
        if match:
            return (int(match.group(1)), int(match.group(2)))
        return (999, 999)

    def sort_key(item):
        block, potential, criteria, yield_count = item

        # Sort: gate first, then detail filters, then other detail
        # Sort order: (1) phase_order, (2) decreasing yield, (3) ref order
        is_filter = block.get("type") == "filter"

        if block["phase"] == "gate":
            # Gate blocks: (0, decreasing yield, ref order)
            phase_order = 0
        elif is_filter:
            # Detail filters: (1, decreasing yield, ref order)
            phase_order = 1
        else:
            # Other detail blocks: (2, decreasing yield, ref order)
            phase_order = 2

        min_criterion = min(criteria, key=parse_criterion_id) if criteria else "999.999"
        ref_order = parse_criterion_id(min_criterion)

        return (phase_order, -yield_count, ref_order)

    selected_blocks.sort(key=sort_key)

    return selected_blocks


def get_already_decided(block, criteria, audit_results, residual):
    """
    For a composite block, returns the list of already-decided criteria.

    A criterion is already decided if it is NOT in the residual.
    """
    return [c for c in criteria if c not in residual]


def get_options_for_direct_block(block, criteria_ref, quick_diag_ref):
    """
    For a direct block, returns the options from the reference.

    - Detailed criterion: evaluation_options
    - Quick diagnostic question: screens
    """
    cid = block["criterion"]

    if cid.startswith("0."):
        # Quick diagnostic question
        if cid in quick_diag_ref:
            return quick_diag_ref[cid]["screens"]
        else:
            raise ValueError(f"Quick diagnostic question {cid} not found in the reference")
    else:
        # Detailed criterion
        if cid in criteria_ref:
            return criteria_ref[cid]["evaluation_options"]
        else:
            raise ValueError(f"Criterion {cid} not found in the reference")


def build_filters_index(sorted_blocks):
    """
    Builds an index {criterion_id: [(filter_id, question_num, title, discarded_label), ...]}
    for all criteria governed by filters.

    sorted_blocks is the sorted list of kept blocks (with their metadata).
    """
    index = {}
    num = 1

    for block, potential, criteria, yield_count in sorted_blocks:
        if block.get("type") == "filter":
            filter_id = block["id"]
            title = block["title"]
            discarded_label = block["discarded_label"]

            for criterion_id in block.get("criteria", []):
                if criterion_id not in index:
                    index[criterion_id] = []
                index[criterion_id].append((filter_id, num, title, discarded_label))

        num += 1

    return index


def format_block_markdown(block, criteria, num, total, criteria_ref, quick_diag_ref,
                         audit_results, residual, contexts, filters_index):
    """
    Formats a block as Markdown.

    Follows the style rules: separators as "-----", straight quotes,
    no em dash.

    Parameter contexts: dict {criterion_id: context_text} for fact recall.
    Parameter filters_index: dict {criterion_id: [(filter_id, question_num, title, discarded_label), ...]}
    """
    lines = []

    # Block title: the subject of the question, plus the person to ask it to.
    # "Block 3 of 41" alone said nothing about the subject, so the reader had to read the
    # whole question to know whether it was for them, and a questionnaire that
    # circulates badly comes back unanswered.
    title_line = f"## {num} of {total} - {block['title']}"
    if block.get("interviewee"):
        title_line += f" (to check with {block['interviewee']})"
    lines.append(title_line)
    lines.append("")

    # "DO NOT ANSWER" mention if all the block's criteria are governed by filters
    # Section 4.2ter of the convention
    if block.get("type") != "filter":
        residual_criteria = [c for c in criteria if c in residual]

        # Check whether all criteria are governed
        governing_filters = {}  # {filter_id: (num, title, discarded_label)}
        all_governed = True

        for cid in residual_criteria:
            if cid not in filters_index or not filters_index[cid]:
                all_governed = False
                break
            # Collect all filters that govern this criterion
            for filter_id, q_num, f_title, f_label in filters_index[cid]:
                if filter_id not in governing_filters:
                    governing_filters[filter_id] = (q_num, f_title, f_label)

        if all_governed and governing_filters:
            # Build the mention with a conjunction if several filters
            # Sort by question number to get the order of appearance in the questionnaire
            sorted_filters = sorted(governing_filters.items(), key=lambda item: item[1][0])

            if len(sorted_filters) == 1:
                # A single filter: extract its label and build the mention
                filter_id, (q_num, f_title, f_label) = sorted_filters[0]
                label_start = f_label.split('(')[0].strip()
                condition = f"if you answered \"{label_start}\" to question {q_num} ({f_title})"
            else:
                # Several filters: each term carries its own label
                terms = []
                for filter_id, (q_num, f_title, f_label) in sorted_filters:
                    label_start = f_label.split('(')[0].strip()
                    terms.append(f"\"{label_start}\" to question {q_num} ({f_title})")
                condition = f"if you answered {' AND '.join(terms)}"

            lines.append(f"**DO NOT ANSWER** {condition}.")
            lines.append("")

    # Machine marker
    lines.append(f"<!-- block:{block['id']} -->")
    lines.append("")

    # Question in bold
    lines.append(f"**{block['question']}**")
    lines.append("")

    # Help in italics if present
    if block.get("help"):
        lines.append(f"*{block['help']}*")
        lines.append("")

    # Fact recall: reminder of measured facts
    # Inserted after the question and the help, before the note and the checkboxes
    # Pitfall 3 (composite block): display ALL non-empty measured facts,
    # merging strictly identical duplicates
    measured_facts = []
    for cid in criteria:
        if cid in contexts:
            fact = contexts[cid]
            # Merge duplicates: only add if not already present
            if fact not in measured_facts:
                measured_facts.append(fact)

    if measured_facts:
        # Pitfall 5: absence must be silent, but here we have at least one fact
        lines.append("> **What we measured:**")
        if len(measured_facts) == 1:
            # A single fact: no bullet
            lines.append(f"> {measured_facts[0]}")
        else:
            # Several facts: as bullets
            for fact in measured_facts:
                lines.append(f"> - {fact}")
        lines.append(">")
        lines.append("> Confirm, or correct if our measurement is incomplete.")
        lines.append("")

    # Note in bold blockquote if present
    if block.get("note"):
        lines.append(f"> **Note:** {block['note']}")
        lines.append("")

    # Covered criteria and potential: internal plumbing, in HTML comments.
    # These two pieces of information are for us, never for the audited service: a
    # criterion identifier and a point count do not help them answer and give them
    # a read on how our tool works. They stay in the file, invisible when
    # reading, to remain traceable.
    residual_criteria = [c for c in criteria if c in residual]
    potential = compute_block_potential(block, residual, criteria_ref, quick_diag_ref)

    lines.append(f"<!-- criteria:{','.join(residual_criteria)} -->")
    if potential > 0:
        lines.append(f"<!-- potential:{potential:.1f} -->")
    lines.append("")

    # Options
    if block["type"] == "direct":
        options = get_options_for_direct_block(block, criteria_ref, quick_diag_ref)
        # For direct blocks on the quick diagnostic, clean the "I don't know" mentions
        cid = block["criterion"]
        if cid.startswith("0."):
            options = [strip_dnk_mention(opt) for opt in options]

        for i, opt_label in enumerate(options):
            lines.append(f"- [ ] {opt_label}  <!-- opt:{i} -->")

    elif block["type"] == "filter":
        # Filter block: two options (discarded and applicable)
        lines.append(f"- [ ] {block['discarded_label']}  <!-- opt:discarded -->")
        lines.append(f"- [ ] {block['applicable_label']}  <!-- opt:applicable -->")

    else:
        # Composite block
        options = [opt["label"] for opt in block["options"]]
        for i, opt_label in enumerate(options):
            lines.append(f"- [ ] {opt_label}  <!-- opt:{i} -->")

    # "I don't know" checkbox
    lines.append(f"- [ ] I don't know  <!-- opt:dnk -->")
    lines.append("")

    # Already-decided criteria (for composite blocks)
    if block["type"] == "composite":
        already_decided = get_already_decided(block, criteria, audit_results, residual)
        if already_decided:
            lines.append(f"<!-- already-decided:{','.join(already_decided)} -->")
            lines.append("")

    return "\n".join(lines)


def generate_questionnaire_unique(blocks_data, audit_results, criteria_ref,
                                   quick_diag_ref, output_dir, contexts):
    """Generates the single questionnaire sorted by decreasing yield."""
    residual = compute_residual(audit_results, criteria_ref, quick_diag_ref)
    sorted_blocks = select_and_sort_blocks(blocks_data, residual, criteria_ref,
                                        quick_diag_ref, audit_results)

    if not sorted_blocks:
        # No block to display: do not create the file
        return None

    lines = []

    # File header
    lines.append(SEPARATOR)
    lines.append("Questionnaire EOF")
    lines.append(SEPARATOR)
    lines.append("")

    # Instructions
    lines.append("**How to fill in this questionnaire:**")
    lines.append("")
    lines.append("- Tick EXACTLY ONE box per block using the `- [x]` syntax.")
    lines.append("- A box left empty stays empty and will never be guessed.")
    lines.append("- Each question states in its title who to ask.")
    lines.append("- Questions are ordered so that the first ones cover the most criteria.")
    lines.append("- You can stop halfway: the effort spent will have covered the maximum of criteria.")
    lines.append("- If you don't know, tick the \"I don't know\" box.")
    lines.append("")

    # Machine markers
    lines.append(f"<!-- questionnaire: eof -->")
    lines.append(f"<!-- version-blocks: {blocks_data['version']} -->")
    lines.append("")

    # Build the filters index for the "DO NOT ANSWER" mention
    filters_index = build_filters_index(sorted_blocks)

    # Separate gate and detail
    gate_blocks = [(b, p, c, r) for b, p, c, r in sorted_blocks if b["phase"] == "gate"]
    detail_blocks = [(b, p, c, r) for b, p, c, r in sorted_blocks if b["phase"] == "detail"]

    total_blocks = len(sorted_blocks)
    num = 1

    if gate_blocks:
        lines.append(SEPARATOR)
        # "Gate" is our internal label for this phase, it means nothing to a
        # client reader: the printed title uses ordinary words.
        lines.append("Part 1: Initial screening")
        lines.append(SEPARATOR)
        lines.append("")
        lines.append("This initial screening quickly decides whether an in-depth diagnostic is relevant.")
        lines.append("")

        for block, potential, criteria, yield_count in gate_blocks:
            lines.append(format_block_markdown(block, criteria, num, total_blocks,
                                             criteria_ref, quick_diag_ref,
                                             audit_results, residual, contexts, filters_index))
            num += 1

    if detail_blocks:
        lines.append(SEPARATOR)
        lines.append("Part 2: Detailed questions")
        lines.append(SEPARATOR)
        lines.append("")

        for block, potential, criteria, yield_count in detail_blocks:
            lines.append(format_block_markdown(block, criteria, num, total_blocks,
                                             criteria_ref, quick_diag_ref,
                                             audit_results, residual, contexts, filters_index))
            num += 1

    # Write the file
    output_path = output_dir / "questionnaire-eof.md"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return output_path


def autotest():
    """Replays the embedded test cases."""
    import tempfile
    import subprocess

    failures = []
    total = 0

    # Cases 24 to 26 are grouped here because they are the only ones to re-run the
    # script via subprocess: they exercise main() and its guard, not an
    # internal function. They therefore work with the REAL reference and the REAL
    # block library, which the script finds from its own directory
    # (find_reference) and not from the audit directory passed to it.

    # Case 24: Refusal to write into audits/ without the flag
    total += 1
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Create a tree with audits/
            audit_dir = tmpdir / "audits" / "test.com"
            audit_dir.mkdir(parents=True)

            audit_data = {"criteria": [{"id": "1.1", "answer": None}], "quick_diag_overview": {"questions": []}}
            audit_path = audit_dir / "eof-audit-results.json"
            audit_path.write_text(json.dumps(audit_data, ensure_ascii=False), encoding="utf-8")

            # Call the script without the flag
            result = subprocess.run(
                [sys.executable, __file__, str(audit_dir)],
                capture_output=True,
                text=True
            )

            if result.returncode != 2:
                failures.append(("Refusal to write into audits without flag", f"Expected exit code 2, got {result.returncode}"))
            elif "audits" not in result.stderr:
                failures.append(("Refusal to write into audits without flag", "Error message does not mention 'audits'"))
    except Exception as exc:
        failures.append(("Refusal to write into audits without flag", f"Exception: {exc}"))

    # Case 25: Acceptance with --in-audit-dir
    total += 1
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            audit_dir = tmpdir / "audits" / "test.com"
            audit_dir.mkdir(parents=True)

            audit_data = {"criteria": [{"id": "1.1", "answer": None}], "quick_diag_overview": {"questions": []}}
            audit_path = audit_dir / "eof-audit-results.json"
            audit_path.write_text(json.dumps(audit_data, ensure_ascii=False), encoding="utf-8")

            # Call the script with the flag
            result = subprocess.run(
                [sys.executable, __file__, str(audit_dir), "--in-audit-dir"],
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                failures.append(("Acceptance with explicit flag", f"Expected exit code 0, got {result.returncode}. stderr: {result.stderr}"))
            elif not (audit_dir / "questionnaire-eof.md").exists():
                failures.append(("Acceptance with explicit flag", "File questionnaire-eof.md not created"))
    except Exception as exc:
        failures.append(("Acceptance with explicit flag", f"Exception: {exc}"))

    # Case 26: Acceptance without flag outside audits/
    total += 1
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            audit_dir = tmpdir / "test.com"
            audit_dir.mkdir(parents=True)
            output_dir = tmpdir / "output"
            output_dir.mkdir()

            audit_data = {"criteria": [{"id": "1.1", "answer": None}], "quick_diag_overview": {"questions": []}}
            audit_path = audit_dir / "eof-audit-results.json"
            audit_path.write_text(json.dumps(audit_data, ensure_ascii=False), encoding="utf-8")

            # Call the script without the flag but with output-dir outside audits/
            result = subprocess.run(
                [sys.executable, __file__, str(audit_dir), "--output-dir", str(output_dir)],
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                failures.append(("Acceptance without flag outside audits", f"Expected exit code 0, got {result.returncode}. stderr: {result.stderr}"))
            elif not (output_dir / "questionnaire-eof.md").exists():
                failures.append(("Acceptance without flag outside audits", "File questionnaire-eof.md not created"))
    except Exception as exc:
        failures.append(("Acceptance without flag outside audits", f"Exception: {exc}"))

    # Case 1: Direct block on a detailed criterion
    total += 1
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Create a minimal reference
            ref_data = {
                "criteria": [
                    {
                        "id": "1.1",
                        "pillar": "🛖 1 — Product",
                        "criterion": "Test criterion",
                        "max_potential": 2.0,
                        "evaluation_options": ["✅ Confirmed strength", "💡 Improvement potential identified"],
                        "evaluation_coefficient_options": {"✅ Confirmed strength": 0, "💡 Improvement potential identified": 1}
                    }
                ],
                "quick_diagnostic": []
            }
            ref_path = tmpdir / "eof-reference.json"
            ref_path.write_text(json.dumps(ref_data, ensure_ascii=False), encoding="utf-8")

            # Create a block library
            blocks_data = {
                "version": 1,
                "blocks": [
                    {
                        "id": "test-direct-11",
                        "file": "product-usage",
                        "phase": "detail",
                        "title": "Test",
                        "type": "direct",
                        "criterion": "1.1",
                        "question": "Test question?",
                        "help": "Test help"
                    }
                ]
            }
            blocks_path = tmpdir / "questionnaire-blocs.json"
            blocks_path.write_text(json.dumps(blocks_data, ensure_ascii=False), encoding="utf-8")

            # Create audit results with 1.1 in the residual
            audit_data = {
                "criteria": [{"id": "1.1", "answer": None}],
                "quick_diag_overview": {"questions": []}
            }
            audit_path = tmpdir / "eof-audit-results.json"
            audit_path.write_text(json.dumps(audit_data, ensure_ascii=False), encoding="utf-8")

            # Generate
            criteria_ref, diag_ref = load_reference(ref_path)
            audit, contexts = load_audit_results(tmpdir)
            blocks = load_blocks(tmpdir)

            result = generate_questionnaire_unique(blocks, audit,
                                                   criteria_ref, diag_ref, tmpdir, contexts)

            if result is None:
                failures.append(("Direct block detailed criterion", "No file generated"))
            else:
                content = result.read_text(encoding="utf-8")
                if "Test question?" not in content:
                    failures.append(("Direct block detailed criterion", "Question missing"))
                if "<!-- block:test-direct-11 -->" not in content:
                    failures.append(("Direct block detailed criterion", "block marker missing"))
                if "<!-- opt:0 -->" not in content:
                    failures.append(("Direct block detailed criterion", "option marker missing"))
                if "<!-- opt:dnk -->" not in content:
                    failures.append(("Direct block detailed criterion", "'I don't know' box missing"))
    except Exception as exc:
        failures.append(("Direct block detailed criterion", f"Exception: {exc}"))

    # Case 2: Direct block on a quick diagnostic question (check absence of coefficient)
    total += 1
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            ref_data = {
                "criteria": [],
                "quick_diagnostic": [
                    {
                        "id": "0.1",
                        "criterion": "Diagnostic question",
                        "screens": ["Screen 1", "Screen 2"],
                        "impact_level": "Decisive"
                    }
                ]
            }
            ref_path = tmpdir / "eof-reference.json"
            ref_path.write_text(json.dumps(ref_data, ensure_ascii=False), encoding="utf-8")

            blocks_data = {
                "version": 1,
                "blocks": [
                    {
                        "id": "test-direct-01",
                        "file": "product-usage",
                        "phase": "gate",
                        "title": "Test",
                        "type": "direct",
                        "criterion": "0.1",
                        "question": "Question 0.1?"
                    }
                ]
            }
            blocks_path = tmpdir / "questionnaire-blocs.json"
            blocks_path.write_text(json.dumps(blocks_data, ensure_ascii=False), encoding="utf-8")

            audit_data = {
                "criteria": [],
                "quick_diag_overview": {"questions": [{"id": "0.1", "answer": None}]}
            }
            audit_path = tmpdir / "eof-audit-results.json"
            audit_path.write_text(json.dumps(audit_data, ensure_ascii=False), encoding="utf-8")

            criteria_ref, diag_ref = load_reference(ref_path)
            audit, contexts = load_audit_results(tmpdir)
            blocks = load_blocks(tmpdir)

            result = generate_questionnaire_unique(blocks, audit,
                                                criteria_ref, diag_ref, tmpdir, contexts)

            if result is None:
                failures.append(("Bloc direct diagnostic rapide", "No file generated"))
            else:
                content = result.read_text(encoding="utf-8")
                if "Screen 1" not in content:
                    failures.append(("Direct block quick diagnostic", "Reference options missing"))
    except Exception as exc:
        failures.append(("Direct block quick diagnostic", f"Exception: {exc}"))

    # Case 3: Criterion with "🤔 To be assessed" must be in the residual
    total += 1
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            ref_data = {
                "criteria": [
                    {
                        "id": "2.1",
                        "pillar": "🗺️ 2 — Architecture",
                        "criterion": "Test",
                        "max_potential": 1.5,
                        "evaluation_options": ["✅ Confirmed strength", "💡 Improvement potential identified"],
                        "evaluation_coefficient_options": {"✅ Confirmed strength": 0, "💡 Improvement potential identified": 1}
                    }
                ],
                "quick_diagnostic": []
            }
            ref_path = tmpdir / "eof-reference.json"
            ref_path.write_text(json.dumps(ref_data, ensure_ascii=False), encoding="utf-8")

            blocks_data = {
                "version": 1,
                "blocks": [
                    {
                        "id": "test-a-evaluer",
                        "file": "technical",
                        "phase": "detail",
                        "title": "Test",
                        "type": "direct",
                        "criterion": "2.1",
                        "question": "Question 2.1?"
                    }
                ]
            }
            blocks_path = tmpdir / "questionnaire-blocs.json"
            blocks_path.write_text(json.dumps(blocks_data, ensure_ascii=False), encoding="utf-8")

            # Criterion with answer "🤔 To be assessed": must be re-asked
            audit_data = {
                "criteria": [{"id": "2.1", "answer": "🤔 To be assessed", "coefficient": 0}],
                "quick_diag_overview": {"questions": []}
            }
            audit_path = tmpdir / "eof-audit-results.json"
            audit_path.write_text(json.dumps(audit_data, ensure_ascii=False), encoding="utf-8")

            criteria_ref, diag_ref = load_reference(ref_path)
            audit, contexts = load_audit_results(tmpdir)
            blocks = load_blocks(tmpdir)

            result = generate_questionnaire_unique(blocks, audit,
                                                criteria_ref, diag_ref, tmpdir, contexts)

            # The criterion must be in the residual and the block must be generated
            if result is None:
                failures.append(("Criterion '🤔 To be assessed' in residual", "No file generated (block should have been kept)"))
    except Exception as exc:
        failures.append(("Criterion '🤔 To be assessed' in residual", f"Exception: {exc}"))

    # Case 4: Composite block with already-decided criteria
    total += 1
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            ref_data = {
                "criteria": [
                    {
                        "id": "3.1",
                        "pillar": "🏢 3 — Infrastructure",
                        "criterion": "Test 3.1",
                        "max_potential": 1.0,
                        "evaluation_options": ["✅ Confirmed strength"],
                        "evaluation_coefficient_options": {"✅ Confirmed strength": 0}
                    },
                    {
                        "id": "3.2",
                        "pillar": "🏢 3 — Infrastructure",
                        "criterion": "Test 3.2",
                        "max_potential": 1.5,
                        "evaluation_options": ["✅ Confirmed strength"],
                        "evaluation_coefficient_options": {"✅ Confirmed strength": 0}
                    }
                ],
                "quick_diagnostic": []
            }
            ref_path = tmpdir / "eof-reference.json"
            ref_path.write_text(json.dumps(ref_data, ensure_ascii=False), encoding="utf-8")

            blocks_data = {
                "version": 1,
                "blocks": [
                    {
                        "id": "test-compose",
                        "file": "technical",
                        "phase": "detail",
                        "title": "Test composite",
                        "type": "composite",
                        "question": "Composite question?",
                        "options": [
                            {"label": "Option A", "answers": {"3.1": "✅ Confirmed strength", "3.2": "✅ Confirmed strength"}},
                            {"label": "Option B", "answers": {"3.1": "💡 Improvement potential identified"}}
                        ]
                    }
                ]
            }
            blocks_path = tmpdir / "questionnaire-blocs.json"
            blocks_path.write_text(json.dumps(blocks_data, ensure_ascii=False), encoding="utf-8")

            # 3.1 already decided, 3.2 in the residual
            audit_data = {
                "criteria": [
                    {"id": "3.1", "answer": "✅ Confirmed strength", "coefficient": 0},
                    {"id": "3.2", "answer": None}
                ],
                "quick_diag_overview": {"questions": []}
            }
            audit_path = tmpdir / "eof-audit-results.json"
            audit_path.write_text(json.dumps(audit_data, ensure_ascii=False), encoding="utf-8")

            criteria_ref, diag_ref = load_reference(ref_path)
            audit, contexts = load_audit_results(tmpdir)
            blocks = load_blocks(tmpdir)

            result = generate_questionnaire_unique(blocks, audit,
                                                criteria_ref, diag_ref, tmpdir, contexts)

            if result is None:
                failures.append(("Composite block with already decided", "No file generated"))
            else:
                content = result.read_text(encoding="utf-8")
                if "<!-- already-decided:3.1 -->" not in content:
                    failures.append(("Composite block with already decided", "already-decided marker missing or incorrect"))
    except Exception as exc:
        failures.append(("Composite block with already decided", f"Exception: {exc}"))

    # Case 5: Cleaning "I don't know" in the quick diagnostic screens
    total += 1
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            ref_data = {
                "criteria": [],
                "quick_diagnostic": [
                    {
                        "id": "0.10",
                        "criterion": "Functional complexity",
                        "screens": [
                            "5 - Very simple",
                            "1 - Very complex / I don't know"
                        ],
                        "impact_level": "Decisive"
                    }
                ]
            }
            ref_path = tmpdir / "eof-reference.json"
            ref_path.write_text(json.dumps(ref_data, ensure_ascii=False), encoding="utf-8")

            blocks_data = {
                "version": 1,
                "blocks": [
                    {
                        "id": "test-jnsp-nettoyage",
                        "file": "product-usage",
                        "phase": "gate",
                        "title": "Test",
                        "type": "direct",
                        "criterion": "0.10",
                        "question": "Question test ?"
                    }
                ]
            }
            blocks_path = tmpdir / "questionnaire-blocs.json"
            blocks_path.write_text(json.dumps(blocks_data, ensure_ascii=False), encoding="utf-8")

            audit_data = {
                "criteria": [],
                "quick_diag_overview": {"questions": [{"id": "0.10", "answer": None}]}
            }
            audit_path = tmpdir / "eof-audit-results.json"
            audit_path.write_text(json.dumps(audit_data, ensure_ascii=False), encoding="utf-8")

            criteria_ref, diag_ref = load_reference(ref_path)
            audit, contexts = load_audit_results(tmpdir)
            blocks = load_blocks(tmpdir)

            result = generate_questionnaire_unique(blocks, audit,
                                                criteria_ref, diag_ref, tmpdir, contexts)

            if result is None:
                failures.append(("I don't know cleaning", "No file generated"))
            else:
                content = result.read_text(encoding="utf-8")
                # Check that "I don't know" was removed from screen 1
                if "1 - Very complex / I don't know" in content:
                    failures.append(("I don't know cleaning", "Mention 'I don't know' not cleaned in the screen"))
                # Check that the cleaned screen appears
                if "- [ ] 1 - Very complex  <!-- opt:1 -->" not in content:
                    failures.append(("I don't know cleaning", "Cleaned screen missing from the questionnaire"))
                # Check that the opt:1 index is present for the parser
                if "<!-- opt:1 -->" not in content:
                    failures.append(("I don't know cleaning", "opt:1 marker missing"))
    except Exception as exc:
        failures.append(("I don't know cleaning", f"Exception: {exc}"))

    # Case 6: Gate-before-detail ordering
    total += 1
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            ref_data = {
                "criteria": [
                    {"id": "1.1", "max_potential": 2.0, "evaluation_options": [], "evaluation_coefficient_options": {}},
                    {"id": "0.1"}
                ],
                "quick_diagnostic": [
                    {"id": "0.1", "criterion": "Test", "screens": ["Screen 1"], "impact_level": "Decisive"}
                ]
            }
            ref_path = tmpdir / "eof-reference.json"
            ref_path.write_text(json.dumps(ref_data, ensure_ascii=False), encoding="utf-8")

            blocks_data = {
                "version": 1,
                "blocks": [
                    {"id": "block-detail", "file": "product-usage", "phase": "detail", "title": "Test", "interviewee": "the product manager", "type": "direct", "criterion": "1.1", "question": "Detail?"},
                    {"id": "block-porte", "file": "product-usage", "phase": "gate", "title": "Test", "interviewee": "the product manager", "type": "direct", "criterion": "0.1", "question": "Gate?"}
                ]
            }
            blocks_path = tmpdir / "questionnaire-blocs.json"
            blocks_path.write_text(json.dumps(blocks_data, ensure_ascii=False), encoding="utf-8")

            audit_data = {
                "criteria": [{"id": "1.1", "answer": None}],
                "quick_diag_overview": {"questions": [{"id": "0.1", "answer": None}]}
            }
            audit_path = tmpdir / "eof-audit-results.json"
            audit_path.write_text(json.dumps(audit_data, ensure_ascii=False), encoding="utf-8")

            criteria_ref, diag_ref = load_reference(ref_path)
            audit, contexts = load_audit_results(tmpdir)
            blocks = load_blocks(tmpdir)

            result = generate_questionnaire_unique(blocks, audit,
                                                criteria_ref, diag_ref, tmpdir, contexts)

            if result:
                content = result.read_text(encoding="utf-8")
                # The gate must appear before the detail
                pos_porte = content.find("block-porte")
                pos_detail = content.find("block-detail")
                if pos_porte == -1 or pos_detail == -1:
                    failures.append(("Gate-before-detail ordering", "Blocks missing"))
                elif pos_porte > pos_detail:
                    failures.append(("Gate-before-detail ordering", "Gate after detail (expected: gate first)"))
    except Exception as exc:
        failures.append(("Ordonnancement porte avant detail", f"Exception: {exc}"))

    # Case 7: Numeric sort of criterion ids (0.2 before 0.10)
    total += 1
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            ref_data = {
                "criteria": [],
                "quick_diagnostic": [
                    {"id": "0.2", "criterion": "Test 0.2", "screens": ["Screen"], "impact_level": "Decisive"},
                    {"id": "0.10", "criterion": "Test 0.10", "screens": ["Screen"], "impact_level": "Decisive"}
                ]
            }
            ref_path = tmpdir / "eof-reference.json"
            ref_path.write_text(json.dumps(ref_data, ensure_ascii=False), encoding="utf-8")

            blocks_data = {
                "version": 1,
                "blocks": [
                    {"id": "gate-diag-0.10", "file": "product-usage", "phase": "gate", "title": "Test", "type": "direct", "criterion": "0.10", "question": "Question 0.10?"},
                    {"id": "gate-diag-0.2", "file": "product-usage", "phase": "gate", "title": "Test", "type": "direct", "criterion": "0.2", "question": "Question 0.2?"}
                ]
            }
            blocks_path = tmpdir / "questionnaire-blocs.json"
            blocks_path.write_text(json.dumps(blocks_data, ensure_ascii=False), encoding="utf-8")

            audit_data = {
                "criteria": [],
                "quick_diag_overview": {"questions": [{"id": "0.2", "answer": None}, {"id": "0.10", "answer": None}]}
            }
            audit_path = tmpdir / "eof-audit-results.json"
            audit_path.write_text(json.dumps(audit_data, ensure_ascii=False), encoding="utf-8")

            criteria_ref, diag_ref = load_reference(ref_path)
            audit, contexts = load_audit_results(tmpdir)
            blocks = load_blocks(tmpdir)

            result = generate_questionnaire_unique(blocks, audit,
                                                criteria_ref, diag_ref, tmpdir, contexts)

            if result:
                content = result.read_text(encoding="utf-8")
                # 0.2 must appear before 0.10
                pos_02 = content.find("gate-diag-0.2")
                pos_010 = content.find("gate-diag-0.10")
                if pos_02 == -1 or pos_010 == -1:
                    failures.append(("Numeric sort 0.2 before 0.10", "Blocks missing"))
                elif pos_02 > pos_010:
                    failures.append(("Numeric sort 0.2 before 0.10", f"0.2 after 0.10 (positions: {pos_02} > {pos_010})"))
    except Exception as exc:
        failures.append(("Numeric sort 0.2 before 0.10", f"Exception: {exc}"))

    # Case 8: Rendering of the `note` key
    total += 1
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            ref_data = {
                "criteria": [
                    {
                        "id": "4.1",
                        "pillar": "🔍 4 — Observability",
                        "criterion": "Test 4.1",
                        "max_potential": 1.0,
                        "evaluation_options": ["✅ Confirmed strength"],
                        "evaluation_coefficient_options": {"✅ Confirmed strength": 0}
                    },
                    {
                        "id": "4.2",
                        "pillar": "🔍 4 — Observability",
                        "criterion": "Test 4.2",
                        "max_potential": 1.0,
                        "evaluation_options": ["✅ Confirmed strength"],
                        "evaluation_coefficient_options": {"✅ Confirmed strength": 0}
                    }
                ],
                "quick_diagnostic": []
            }
            ref_path = tmpdir / "eof-reference.json"
            ref_path.write_text(json.dumps(ref_data, ensure_ascii=False), encoding="utf-8")

            blocks_data = {
                "version": 1,
                "blocks": [
                    {
                        "id": "test-avec-note",
                        "file": "technical",
                        "phase": "detail",
                        "title": "Test with note",
                        "type": "direct",
                        "criterion": "4.1",
                        "question": "Question with note?",
                        "help": "Test help",
                        "note": "To validate with the product manager"
                    },
                    {
                        "id": "test-sans-note",
                        "file": "technical",
                        "phase": "detail",
                        "title": "Test without note",
                        "type": "direct",
                        "criterion": "4.2",
                        "question": "Question without note?"
                    }
                ]
            }
            blocks_path = tmpdir / "questionnaire-blocs.json"
            blocks_path.write_text(json.dumps(blocks_data, ensure_ascii=False), encoding="utf-8")

            audit_data = {
                "criteria": [
                    {"id": "4.1", "answer": None},
                    {"id": "4.2", "answer": None}
                ],
                "quick_diag_overview": {"questions": []}
            }
            audit_path = tmpdir / "eof-audit-results.json"
            audit_path.write_text(json.dumps(audit_data, ensure_ascii=False), encoding="utf-8")

            criteria_ref, diag_ref = load_reference(ref_path)
            audit, contexts = load_audit_results(tmpdir)
            blocks = load_blocks(tmpdir)

            result = generate_questionnaire_unique(blocks, audit,
                                                criteria_ref, diag_ref, tmpdir, contexts)

            if result is None:
                failures.append(("note key rendering", "No file generated"))
            else:
                content = result.read_text(encoding="utf-8")
                # Check that the note appears for block test-avec-note
                if "> **Note:** To validate with the product manager" not in content:
                    failures.append(("note key rendering", "Note missing for block with note"))
                # Check that no note appears for block test-sans-note
                # We look between the block marker and the criteria line
                pos_no_note = content.find("<!-- block:test-sans-note -->")
                if pos_no_note != -1:
                    section_no_note = content[pos_no_note:pos_no_note + 500]
                    if "> **Note:**" in section_no_note:
                        failures.append(("note key rendering", "Note present for block without note (should not)"))
    except Exception as exc:
        failures.append(("note key rendering", f"Exception: {exc}"))

    # Case 9: Fact recall - criterion with null context
    total += 1
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            ref_data = {
                "criteria": [
                    {
                        "id": "5.1",
                        "pillar": "👨‍💻 5 — Algorithms & code",
                        "criterion": "Test 5.1",
                        "max_potential": 1.0,
                        "evaluation_options": ["✅ Confirmed strength"],
                        "evaluation_coefficient_options": {"✅ Confirmed strength": 0}
                    }
                ],
                "quick_diagnostic": []
            }
            ref_path = tmpdir / "eof-reference.json"
            ref_path.write_text(json.dumps(ref_data, ensure_ascii=False), encoding="utf-8")

            blocks_data = {
                "version": 1,
                "blocks": [
                    {
                        "id": "test-contexte-null",
                        "file": "technical",
                        "phase": "detail",
                        "title": "Test",
                        "type": "direct",
                        "criterion": "5.1",
                        "question": "Question 5.1?"
                    }
                ]
            }
            blocks_path = tmpdir / "questionnaire-blocs.json"
            blocks_path.write_text(json.dumps(blocks_data, ensure_ascii=False), encoding="utf-8")

            # Criterion with context = null
            audit_data = {
                "criteria": [{"id": "5.1", "answer": None, "context": None}],
                "quick_diag_overview": {"questions": []}
            }
            audit_path = tmpdir / "eof-audit-results.json"
            audit_path.write_text(json.dumps(audit_data, ensure_ascii=False), encoding="utf-8")

            criteria_ref, diag_ref = load_reference(ref_path)
            audit, contexts = load_audit_results(tmpdir)
            blocks = load_blocks(tmpdir)

            result = generate_questionnaire_unique(blocks, audit,
                                                criteria_ref, diag_ref, tmpdir, contexts)

            if result is None:
                failures.append(("Emprunt 1 - contexte null", "No file generated"))
            else:
                content = result.read_text(encoding="utf-8")
                # No reminder must be displayed
                if "> **What we measured:**" in content:
                    failures.append(("Fact recall - null context", "Reminder displayed although context is null"))
    except Exception as exc:
        failures.append(("Emprunt 1 - contexte null", f"Exception: {exc}"))

    # Case 10: Fact recall - criterion with empty context
    total += 1
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            ref_data = {
                "criteria": [
                    {
                        "id": "5.2",
                        "pillar": "👨‍💻 5 — Algorithms & code",
                        "criterion": "Test 5.2",
                        "max_potential": 1.0,
                        "evaluation_options": ["✅ Confirmed strength"],
                        "evaluation_coefficient_options": {"✅ Confirmed strength": 0}
                    }
                ],
                "quick_diagnostic": []
            }
            ref_path = tmpdir / "eof-reference.json"
            ref_path.write_text(json.dumps(ref_data, ensure_ascii=False), encoding="utf-8")

            blocks_data = {
                "version": 1,
                "blocks": [
                    {
                        "id": "test-contexte-vide",
                        "file": "technical",
                        "phase": "detail",
                        "title": "Test",
                        "type": "direct",
                        "criterion": "5.2",
                        "question": "Question 5.2?"
                    }
                ]
            }
            blocks_path = tmpdir / "questionnaire-blocs.json"
            blocks_path.write_text(json.dumps(blocks_data, ensure_ascii=False), encoding="utf-8")

            # Criterion with context = "   " (spaces only)
            audit_data = {
                "criteria": [{"id": "5.2", "answer": None, "context": "   "}],
                "quick_diag_overview": {"questions": []}
            }
            audit_path = tmpdir / "eof-audit-results.json"
            audit_path.write_text(json.dumps(audit_data, ensure_ascii=False), encoding="utf-8")

            criteria_ref, diag_ref = load_reference(ref_path)
            audit, contexts = load_audit_results(tmpdir)
            blocks = load_blocks(tmpdir)

            result = generate_questionnaire_unique(blocks, audit,
                                                criteria_ref, diag_ref, tmpdir, contexts)

            if result is None:
                failures.append(("Emprunt 1 - contexte vide", "No file generated"))
            else:
                content = result.read_text(encoding="utf-8")
                # No reminder must be displayed
                if "> **What we measured:**" in content:
                    failures.append(("Fact recall - empty context", "Reminder displayed although context is empty"))
    except Exception as exc:
        failures.append(("Emprunt 1 - contexte vide", f"Exception: {exc}"))

    # Case 11: Fact recall - composite block with a single context
    total += 1
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            ref_data = {
                "criteria": [
                    {
                        "id": "2.1",
                        "pillar": "🗺️ 2 — Architecture",
                        "criterion": "Test 2.1",
                        "max_potential": 1.0,
                        "evaluation_options": ["✅ Confirmed strength"],
                        "evaluation_coefficient_options": {"✅ Confirmed strength": 0}
                    },
                    {
                        "id": "2.2",
                        "pillar": "🗺️ 2 — Architecture",
                        "criterion": "Test 2.2",
                        "max_potential": 1.5,
                        "evaluation_options": ["✅ Confirmed strength"],
                        "evaluation_coefficient_options": {"✅ Confirmed strength": 0}
                    }
                ],
                "quick_diagnostic": []
            }
            ref_path = tmpdir / "eof-reference.json"
            ref_path.write_text(json.dumps(ref_data, ensure_ascii=False), encoding="utf-8")

            blocks_data = {
                "version": 1,
                "blocks": [
                    {
                        "id": "test-composite-un-contexte",
                        "file": "technical",
                        "phase": "detail",
                        "title": "Test composite",
                        "type": "composite",
                        "question": "Composite question?",
                        "options": [
                            {"label": "Option A", "answers": {"2.1": "✅ Confirmed strength", "2.2": "✅ Confirmed strength"}},
                            {"label": "Option B", "answers": {"2.1": "💡 Improvement potential identified"}}
                        ]
                    }
                ]
            }
            blocks_path = tmpdir / "questionnaire-blocs.json"
            blocks_path.write_text(json.dumps(blocks_data, ensure_ascii=False), encoding="utf-8")

            # 2.1 with context, 2.2 without context
            audit_data = {
                "criteria": [
                    {"id": "2.1", "answer": None, "context": "Measured fact for 2.1"},
                    {"id": "2.2", "answer": None, "context": None}
                ],
                "quick_diag_overview": {"questions": []}
            }
            audit_path = tmpdir / "eof-audit-results.json"
            audit_path.write_text(json.dumps(audit_data, ensure_ascii=False), encoding="utf-8")

            criteria_ref, diag_ref = load_reference(ref_path)
            audit, contexts = load_audit_results(tmpdir)
            blocks = load_blocks(tmpdir)

            result = generate_questionnaire_unique(blocks, audit,
                                                criteria_ref, diag_ref, tmpdir, contexts)

            if result is None:
                failures.append(("Fact recall - composite block single context", "No file generated"))
            else:
                content = result.read_text(encoding="utf-8")
                # A reminder with the single fact must be displayed (no bullet since there is only one)
                if "> **What we measured:**" not in content:
                    failures.append(("Fact recall - composite block single context", "No reminder displayed"))
                elif "> Measured fact for 2.1" not in content:
                    failures.append(("Fact recall - composite block single context", "Fact 2.1 missing from the reminder"))
                # Check there is no bullet (a single fact)
                elif "> - Measured fact for 2.1" in content:
                    failures.append(("Fact recall - composite block single context", "Bullet present although a single fact (expected: no bullet)"))
    except Exception as exc:
        failures.append(("Fact recall - composite block single context", f"Exception: {exc}"))

    # Case 12: Fact recall - composite block with two identical contexts (merge)
    total += 1
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            ref_data = {
                "criteria": [
                    {
                        "id": "3.1",
                        "pillar": "🏢 3 — Infrastructure",
                        "criterion": "Test 3.1",
                        "max_potential": 1.0,
                        "evaluation_options": ["✅ Confirmed strength"],
                        "evaluation_coefficient_options": {"✅ Confirmed strength": 0}
                    },
                    {
                        "id": "3.2",
                        "pillar": "🏢 3 — Infrastructure",
                        "criterion": "Test 3.2",
                        "max_potential": 1.5,
                        "evaluation_options": ["✅ Confirmed strength"],
                        "evaluation_coefficient_options": {"✅ Confirmed strength": 0}
                    }
                ],
                "quick_diagnostic": []
            }
            ref_path = tmpdir / "eof-reference.json"
            ref_path.write_text(json.dumps(ref_data, ensure_ascii=False), encoding="utf-8")

            blocks_data = {
                "version": 1,
                "blocks": [
                    {
                        "id": "test-composite-merge",
                        "file": "technical",
                        "phase": "detail",
                        "title": "Test composite merge",
                        "type": "composite",
                        "question": "Composite question?",
                        "options": [
                            {"label": "Option A", "answers": {"3.1": "✅ Confirmed strength", "3.2": "✅ Confirmed strength"}},
                            {"label": "Option B", "answers": {"3.1": "💡 Improvement potential identified"}}
                        ]
                    }
                ]
            }
            blocks_path = tmpdir / "questionnaire-blocs.json"
            blocks_path.write_text(json.dumps(blocks_data, ensure_ascii=False), encoding="utf-8")

            # 3.1 and 3.2 with the SAME context
            audit_data = {
                "criteria": [
                    {"id": "3.1", "answer": None, "context": "Identical fact for both"},
                    {"id": "3.2", "answer": None, "context": "Identical fact for both"}
                ],
                "quick_diag_overview": {"questions": []}
            }
            audit_path = tmpdir / "eof-audit-results.json"
            audit_path.write_text(json.dumps(audit_data, ensure_ascii=False), encoding="utf-8")

            criteria_ref, diag_ref = load_reference(ref_path)
            audit, contexts = load_audit_results(tmpdir)
            blocks = load_blocks(tmpdir)

            result = generate_questionnaire_unique(blocks, audit,
                                                criteria_ref, diag_ref, tmpdir, contexts)

            if result is None:
                failures.append(("Fact recall - composite block merge", "No file generated"))
            else:
                content = result.read_text(encoding="utf-8")
                # The fact must appear only once (duplicate merge)
                if "> **What we measured:**" not in content:
                    failures.append(("Fact recall - composite block merge", "No reminder displayed"))
                elif content.count("Identical fact for both") > 1:
                    failures.append(("Fact recall - composite block merge", f"Duplicate not merged (appears {content.count('Identical fact for both')} times)"))
                # Check there is no bullet (a single fact after merge)
                elif "> - Identical fact for both" in content:
                    failures.append(("Fact recall - composite block merge", "Bullet present although a single fact after merge (expected: no bullet)"))
    except Exception as exc:
        failures.append(("Fact recall - composite block merge", f"Exception: {exc}"))

    # Case 13: Fact recall - 0.x question with context_index
    total += 1
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            ref_data = {
                "criteria": [],
                "quick_diagnostic": [
                    {
                        "id": "0.5",
                        "criterion": "Test diagnostic",
                        "screens": ["Screen 1", "Screen 2"],
                        "impact_level": "Decisive"
                    }
                ]
            }
            ref_path = tmpdir / "eof-reference.json"
            ref_path.write_text(json.dumps(ref_data, ensure_ascii=False), encoding="utf-8")

            blocks_data = {
                "version": 1,
                "blocks": [
                    {
                        "id": "test-diag-indice",
                        "file": "product-usage",
                        "phase": "gate",
                        "title": "Test",
                        "type": "direct",
                        "criterion": "0.5",
                        "question": "Question 0.5?"
                    }
                ]
            }
            blocks_path = tmpdir / "questionnaire-blocs.json"
            blocks_path.write_text(json.dumps(blocks_data, ensure_ascii=False), encoding="utf-8")

            # Question 0.5 with context_index
            audit_data = {
                "criteria": [],
                "quick_diag_overview": {
                    "questions": [
                        {"id": "0.5", "answer": None, "context_index": "Context hint for 0.5"}
                    ]
                }
            }
            audit_path = tmpdir / "eof-audit-results.json"
            audit_path.write_text(json.dumps(audit_data, ensure_ascii=False), encoding="utf-8")

            criteria_ref, diag_ref = load_reference(ref_path)
            audit, contexts = load_audit_results(tmpdir)
            blocks = load_blocks(tmpdir)

            result = generate_questionnaire_unique(blocks, audit,
                                                criteria_ref, diag_ref, tmpdir, contexts)

            if result is None:
                failures.append(("Fact recall - 0.x question with hint", "No file generated"))
            else:
                content = result.read_text(encoding="utf-8")
                # The reminder must be displayed
                if "> **What we measured:**" not in content:
                    failures.append(("Fact recall - 0.x question with hint", "No reminder displayed"))
                elif "Context hint for 0.5" not in content:
                    failures.append(("Fact recall - 0.x question with hint", "Context hint missing from the reminder"))
    except Exception as exc:
        failures.append(("Fact recall - 0.x question with hint", f"Exception: {exc}"))

    # Case 14: Fact recall - audit with all contexts empty
    total += 1
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            ref_data = {
                "criteria": [
                    {
                        "id": "1.1",
                        "pillar": "🛖 1 — Product",
                        "criterion": "Test 1.1",
                        "max_potential": 2.0,
                        "evaluation_options": ["✅ Confirmed strength"],
                        "evaluation_coefficient_options": {"✅ Confirmed strength": 0}
                    },
                    {
                        "id": "1.2",
                        "pillar": "🛖 1 — Product",
                        "criterion": "Test 1.2",
                        "max_potential": 1.5,
                        "evaluation_options": ["✅ Confirmed strength"],
                        "evaluation_coefficient_options": {"✅ Confirmed strength": 0}
                    }
                ],
                "quick_diagnostic": [
                    {
                        "id": "0.1",
                        "criterion": "Test 0.1",
                        "screens": ["Screen 1"],
                        "impact_level": "Decisive"
                    }
                ]
            }
            ref_path = tmpdir / "eof-reference.json"
            ref_path.write_text(json.dumps(ref_data, ensure_ascii=False), encoding="utf-8")

            blocks_data = {
                "version": 1,
                "blocks": [
                    {
                        "id": "test-vide-1",
                        "file": "product-usage",
                        "phase": "detail",
                        "title": "Test",
                        "type": "direct",
                        "criterion": "1.1",
                        "question": "Question 1.1?"
                    },
                    {
                        "id": "test-vide-2",
                        "file": "product-usage",
                        "phase": "detail",
                        "title": "Test",
                        "type": "direct",
                        "criterion": "1.2",
                        "question": "Question 1.2?"
                    },
                    {
                        "id": "test-vide-3",
                        "file": "product-usage",
                        "phase": "gate",
                        "title": "Test",
                        "type": "direct",
                        "criterion": "0.1",
                        "question": "Question 0.1?"
                    }
                ]
            }
            blocks_path = tmpdir / "questionnaire-blocs.json"
            blocks_path.write_text(json.dumps(blocks_data, ensure_ascii=False), encoding="utf-8")

            # All contexts are null or empty
            audit_data = {
                "criteria": [
                    {"id": "1.1", "answer": None, "context": None},
                    {"id": "1.2", "answer": None, "context": ""}
                ],
                "quick_diag_overview": {
                    "questions": [
                        {"id": "0.1", "answer": None, "context_index": None}
                    ]
                }
            }
            audit_path = tmpdir / "eof-audit-results.json"
            audit_path.write_text(json.dumps(audit_data, ensure_ascii=False), encoding="utf-8")

            criteria_ref, diag_ref = load_reference(ref_path)
            audit, contexts = load_audit_results(tmpdir)
            blocks = load_blocks(tmpdir)

            result = generate_questionnaire_unique(blocks, audit,
                                                criteria_ref, diag_ref, tmpdir, contexts)

            if result is None:
                failures.append(("Emprunt 1 - audit vide", "No file generated"))
            else:
                content = result.read_text(encoding="utf-8")
                # No reminder must be displayed anywhere
                if "> **What we measured:**" in content:
                    failures.append(("Fact recall - empty audit", "Reminder displayed although all contexts are empty"))
    except Exception as exc:
        failures.append(("Emprunt 1 - audit vide", f"Exception: {exc}"))

    # Case 15: The block title carries the subject and the interviewee
    total += 1
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            ref_data = {
                "criteria": [
                    {"id": "1.1", "pillar": "🛖 1 — Product", "criterion": "C", "max_potential": 2.0,
                     "evaluation_options": ["✅ Confirmed strength", "💡 Improvement potential identified"],
                     "evaluation_coefficient_options": {"✅ Confirmed strength": 0,
                                                        "💡 Improvement potential identified": 1}}
                ],
                "quick_diagnostic": []
            }
            (tmpdir / "eof-reference.json").write_text(
                json.dumps(ref_data, ensure_ascii=False), encoding="utf-8")

            blocks_data = {"version": 1, "blocks": [
                {"id": "b-titre", "file": "product-usage", "phase": "detail",
                 "title": "Legacy devices",
                 "interviewee": "the product manager",
                 "type": "direct", "criterion": "1.1", "question": "Q?"}
            ]}
            (tmpdir / "questionnaire-blocs.json").write_text(
                json.dumps(blocks_data, ensure_ascii=False), encoding="utf-8")

            (tmpdir / "eof-audit-results.json").write_text(
                json.dumps({"criteria": [{"id": "1.1", "answer": None, "context": None}],
                            "quick_diag_overview": {"questions": []}},
                           ensure_ascii=False), encoding="utf-8")

            criteria_ref, diag_ref = load_reference(tmpdir / "eof-reference.json")
            audit, contexts = load_audit_results(tmpdir)
            blocks = load_blocks(tmpdir)

            result = generate_questionnaire_unique(blocks, audit,
                                                criteria_ref, diag_ref, tmpdir, contexts)
            if result is None:
                failures.append(("Block title", "No file generated"))
            else:
                content = result.read_text(encoding="utf-8")
                expected = "## 1 of 1 - Legacy devices (to check with the product manager)"
                if expected not in content:
                    failures.append(("Block title",
                                   f"Title line missing: {expected}"))
                # The internal plumbing must not come back in front of the reader
                if "**Covered EOF criteria" in content or "**Unlocked potential" in content:
                    failures.append(("Block title",
                                   "Internal plumbing shown to the reader"))
    except Exception as exc:
        failures.append(("Block title", f"Exception: {exc}"))

    # Case 16: Filter block printed (no criterion decided)
    total += 1
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            ref_data = {
                "criteria": [
                    {"id": "4.1", "max_potential": 1.5, "evaluation_options": ["✅ Confirmed strength"], "evaluation_coefficient_options": {"✅ Confirmed strength": 0}},
                    {"id": "4.2", "max_potential": 1.5, "evaluation_options": ["✅ Confirmed strength"], "evaluation_coefficient_options": {"✅ Confirmed strength": 0}}
                ],
                "quick_diagnostic": []
            }
            ref_path = tmpdir / "eof-reference.json"
            ref_path.write_text(json.dumps(ref_data, ensure_ascii=False), encoding="utf-8")

            blocks_data = {
                "version": 1,
                "blocks": [
                    {
                        "id": "filter-test",
                        "file": "technical",
                        "phase": "gate",
                        "title": "Test filter",
                        "interviewee": "the person who manages the data",
                        "type": "filter",
                        "criteria": ["4.1", "4.2"],
                        "question": "Question filter?",
                        "discarded_label": "Not applicable",
                        "applicable_label": "It applies"
                    }
                ]
            }
            blocks_path = tmpdir / "questionnaire-blocs.json"
            blocks_path.write_text(json.dumps(blocks_data, ensure_ascii=False), encoding="utf-8")

            # No criterion decided: the filter must be printed
            audit_data = {
                "criteria": [
                    {"id": "4.1", "answer": None},
                    {"id": "4.2", "answer": None}
                ],
                "quick_diag_overview": {"questions": []}
            }
            audit_path = tmpdir / "eof-audit-results.json"
            audit_path.write_text(json.dumps(audit_data, ensure_ascii=False), encoding="utf-8")

            criteria_ref, diag_ref = load_reference(ref_path)
            audit, contexts = load_audit_results(tmpdir)
            blocks = load_blocks(tmpdir)

            result = generate_questionnaire_unique(blocks, audit,
                                                criteria_ref, diag_ref, tmpdir, contexts)

            if result is None:
                failures.append(("Filter block printed", "No file generated"))
            else:
                content = result.read_text(encoding="utf-8")
                if "<!-- block:filter-test -->" not in content:
                    failures.append(("Filter block printed", "filter block marker missing"))
                if "<!-- opt:discarded -->" not in content:
                    failures.append(("Filter block printed", "opt:discarded marker missing"))
                if "<!-- opt:applicable -->" not in content:
                    failures.append(("Filter block printed", "opt:applicable marker missing"))
                if "Not applicable" not in content:
                    failures.append(("Filter block printed", "Discarded label missing"))
    except Exception as exc:
        failures.append(("Filter block printed", f"Exception: {exc}"))

    # Case 17: Filter block removed by rule 4.2 (a criterion already decided)
    total += 1
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            ref_data = {
                "criteria": [
                    {"id": "1.5", "max_potential": 1.0, "evaluation_options": ["✅ Confirmed strength"], "evaluation_coefficient_options": {"✅ Confirmed strength": 0}},
                    {"id": "1.13", "max_potential": 1.5, "evaluation_options": ["✅ Confirmed strength"], "evaluation_coefficient_options": {"✅ Confirmed strength": 0}},
                    {"id": "2.1", "max_potential": 1.5, "evaluation_options": ["✅ Confirmed strength"], "evaluation_coefficient_options": {"✅ Confirmed strength": 0}}
                ],
                "quick_diagnostic": []
            }
            ref_path = tmpdir / "eof-reference.json"
            ref_path.write_text(json.dumps(ref_data, ensure_ascii=False), encoding="utf-8")

            blocks_data = {
                "version": 1,
                "blocks": [
                    {
                        "id": "filter-interface",
                        "file": "product-usage",
                        "phase": "gate",
                        "title": "User interface",
                        "interviewee": "the product manager",
                        "type": "filter",
                        "criteria": ["1.5", "1.13"],
                        "question": "Does the service have an interface?",
                        "discarded_label": "No, no interface",
                        "applicable_label": "Yes, there is an interface"
                    },
                    {
                        "id": "block-autre",
                        "file": "technical",
                        "phase": "detail",
                        "title": "Other block",
                        "interviewee": "the development team",
                        "type": "direct",
                        "criterion": "2.1",
                        "question": "Question other?"
                    }
                ]
            }
            blocks_path = tmpdir / "questionnaire-blocs.json"
            blocks_path.write_text(json.dumps(blocks_data, ensure_ascii=False), encoding="utf-8")

            # 1.5 is decided: the filter must be removed, but the other block remains
            audit_data = {
                "criteria": [
                    {"id": "1.5", "answer": "✅ Confirmed strength", "coefficient": 0},
                    {"id": "1.13", "answer": None},
                    {"id": "2.1", "answer": None}
                ],
                "quick_diag_overview": {"questions": []}
            }
            audit_path = tmpdir / "eof-audit-results.json"
            audit_path.write_text(json.dumps(audit_data, ensure_ascii=False), encoding="utf-8")

            criteria_ref, diag_ref = load_reference(ref_path)
            audit, contexts = load_audit_results(tmpdir)
            blocks = load_blocks(tmpdir)

            result = generate_questionnaire_unique(blocks, audit,
                                                criteria_ref, diag_ref, tmpdir, contexts)

            if result is None:
                failures.append(("Filter block removed rule 4.2", "No file generated"))
            else:
                content = result.read_text(encoding="utf-8")
                if "<!-- block:filter-interface -->" in content:
                    failures.append(("Filter block removed rule 4.2", "Filter present although it should be removed"))
                if "<!-- block:block-autre -->" not in content:
                    failures.append(("Filter block removed rule 4.2", "Other block missing"))
    except Exception as exc:
        failures.append(("Filter block removed rule 4.2", f"Exception: {exc}"))

    # Case 18: Filter block with answer "🤔 To be assessed" (does not remove the filter)
    total += 1
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            ref_data = {
                "criteria": [
                    {"id": "3.8", "max_potential": 1.5, "evaluation_options": ["✅ Confirmed strength"], "evaluation_coefficient_options": {"✅ Confirmed strength": 0}},
                    {"id": "3.9", "max_potential": 1.5, "evaluation_options": ["✅ Confirmed strength"], "evaluation_coefficient_options": {"✅ Confirmed strength": 0}}
                ],
                "quick_diagnostic": []
            }
            ref_path = tmpdir / "eof-reference.json"
            ref_path.write_text(json.dumps(ref_data, ensure_ascii=False), encoding="utf-8")

            blocks_data = {
                "version": 1,
                "blocks": [
                    {
                        "id": "filter-env-test",
                        "file": "technical",
                        "phase": "gate",
                        "title": "Test environment",
                        "interviewee": "the person who operates the infrastructure",
                        "type": "filter",
                        "criteria": ["3.8", "3.9"],
                        "question": "Do you have test environments?",
                        "discarded_label": "No",
                        "applicable_label": "Yes"
                    }
                ]
            }
            blocks_path = tmpdir / "questionnaire-blocs.json"
            blocks_path.write_text(json.dumps(blocks_data, ensure_ascii=False), encoding="utf-8")

            # 3.8 has a non-decisive answer: the filter must be printed
            audit_data = {
                "criteria": [
                    {"id": "3.8", "answer": "🤔 To be assessed", "coefficient": 0},
                    {"id": "3.9", "answer": None}
                ],
                "quick_diag_overview": {"questions": []}
            }
            audit_path = tmpdir / "eof-audit-results.json"
            audit_path.write_text(json.dumps(audit_data, ensure_ascii=False), encoding="utf-8")

            criteria_ref, diag_ref = load_reference(ref_path)
            audit, contexts = load_audit_results(tmpdir)
            blocks = load_blocks(tmpdir)

            result = generate_questionnaire_unique(blocks, audit,
                                                criteria_ref, diag_ref, tmpdir, contexts)

            if result is None:
                failures.append(("Filter block with 🤔 To be assessed", "No file generated"))
            else:
                content = result.read_text(encoding="utf-8")
                if "<!-- block:filter-env-test -->" not in content:
                    failures.append(("Filter block with 🤔 To be assessed", "Filter missing although it should be printed (non-decisive answer)"))
    except Exception as exc:
        failures.append(("Filter block with 🤔 To be assessed", f"Exception: {exc}"))

    # Case 19: Fully governed block that gets the "DO NOT ANSWER" mention
    total += 1
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            ref_data = {
                "criteria": [
                    {"id": "4.1", "max_potential": 1.5, "evaluation_options": ["✅ Confirmed strength", "🚫 Not applicable"], "evaluation_coefficient_options": {"✅ Confirmed strength": 0, "🚫 Not applicable": 0}},
                    {"id": "4.2", "max_potential": 1.5, "evaluation_options": ["✅ Confirmed strength", "🚫 Not applicable"], "evaluation_coefficient_options": {"✅ Confirmed strength": 0, "🚫 Not applicable": 0}}
                ],
                "quick_diagnostic": []
            }
            ref_path = tmpdir / "eof-reference.json"
            ref_path.write_text(json.dumps(ref_data, ensure_ascii=False), encoding="utf-8")

            blocks_data = {
                "version": 1,
                "blocks": [
                    {
                        "id": "filter-donnees",
                        "file": "technical",
                        "phase": "detail",
                        "title": "Service data storage",
                        "interviewee": "the person who manages the data",
                        "type": "filter",
                        "criteria": ["4.1", "4.2"],
                        "question": "Do you have data?",
                        "discarded_label": "No, the service retains no data",
                        "applicable_label": "Yes"
                    },
                    {
                        "id": "block-4.1",
                        "file": "technical",
                        "phase": "detail",
                        "title": "Criterion 4.1",
                        "interviewee": "the person who manages the data",
                        "type": "direct",
                        "criterion": "4.1",
                        "question": "Question 4.1?"
                    }
                ]
            }
            blocks_path = tmpdir / "questionnaire-blocs.json"
            blocks_path.write_text(json.dumps(blocks_data, ensure_ascii=False), encoding="utf-8")

            audit_data = {
                "criteria": [
                    {"id": "4.1", "answer": None},
                    {"id": "4.2", "answer": None}
                ],
                "quick_diag_overview": {"questions": []}
            }
            audit_path = tmpdir / "eof-audit-results.json"
            audit_path.write_text(json.dumps(audit_data, ensure_ascii=False), encoding="utf-8")

            criteria_ref, diag_ref = load_reference(ref_path)
            audit, contexts = load_audit_results(tmpdir)
            blocks = load_blocks(tmpdir)

            result = generate_questionnaire_unique(blocks, audit,
                                                criteria_ref, diag_ref, tmpdir, contexts)

            if result is None:
                failures.append(("Fully governed block with mention", "No file generated"))
            else:
                content = result.read_text(encoding="utf-8")
                if "**DO NOT ANSWER**" not in content:
                    failures.append(("Fully governed block with mention", "Mention 'DO NOT ANSWER' missing"))
                elif "question 1 (Service data storage)" not in content:
                    failures.append(("Fully governed block with mention", "Reference to the filter missing or incorrect"))
    except Exception as exc:
        failures.append(("Fully governed block with mention", f"Exception: {exc}"))

    # Case 20: Partially governed block that does not get the mention
    total += 1
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            ref_data = {
                "criteria": [
                    {"id": "4.1", "max_potential": 1.5, "evaluation_options": ["✅ Confirmed strength", "🚫 Not applicable"], "evaluation_coefficient_options": {"✅ Confirmed strength": 0, "🚫 Not applicable": 0}},
                    {"id": "5.1", "max_potential": 1.0, "evaluation_options": ["✅ Confirmed strength"], "evaluation_coefficient_options": {"✅ Confirmed strength": 0}}
                ],
                "quick_diagnostic": []
            }
            ref_path = tmpdir / "eof-reference.json"
            ref_path.write_text(json.dumps(ref_data, ensure_ascii=False), encoding="utf-8")

            blocks_data = {
                "version": 1,
                "blocks": [
                    {
                        "id": "filter-donnees",
                        "file": "technical",
                        "phase": "detail",
                        "title": "Storage",
                        "interviewee": "the person who manages the data",
                        "type": "filter",
                        "criteria": ["4.1"],
                        "question": "Do you have data?",
                        "discarded_label": "No",
                        "applicable_label": "Yes"
                    },
                    {
                        "id": "block-compose",
                        "file": "technical",
                        "phase": "detail",
                        "title": "Composite block",
                        "interviewee": "the development team",
                        "type": "composite",
                        "question": "Question?",
                        "options": [
                            {"label": "Option A", "answers": {"4.1": "✅ Confirmed strength", "5.1": "✅ Confirmed strength"}}
                        ]
                    }
                ]
            }
            blocks_path = tmpdir / "questionnaire-blocs.json"
            blocks_path.write_text(json.dumps(blocks_data, ensure_ascii=False), encoding="utf-8")

            audit_data = {
                "criteria": [
                    {"id": "4.1", "answer": None},
                    {"id": "5.1", "answer": None}
                ],
                "quick_diag_overview": {"questions": []}
            }
            audit_path = tmpdir / "eof-audit-results.json"
            audit_path.write_text(json.dumps(audit_data, ensure_ascii=False), encoding="utf-8")

            criteria_ref, diag_ref = load_reference(ref_path)
            audit, contexts = load_audit_results(tmpdir)
            blocks = load_blocks(tmpdir)

            result = generate_questionnaire_unique(blocks, audit,
                                                criteria_ref, diag_ref, tmpdir, contexts)

            if result is None:
                failures.append(("Bloc partiellement gouverne sans mention", "No file generated"))
            else:
                content = result.read_text(encoding="utf-8")
                # Find the composite block in the content
                if "block-compose" in content:
                    # Extract the composite block section
                    block_start = content.find("<!-- block:block-compose -->")
                    block_end = content.find("##", block_start + 1) if block_start >= 0 else -1
                    bloc_section = content[block_start:block_end] if block_end > block_start else content[block_start:]

                    if "**DO NOT ANSWER**" in bloc_section:
                        failures.append(("Partially governed block without mention", "Mention present although it should not (partially governed block)"))
    except Exception as exc:
        failures.append(("Bloc partiellement gouverne sans mention", f"Exception: {exc}"))

    # Case 21: Block governed by two filters with AND conjunction
    total += 1
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            ref_data = {
                "criteria": [
                    {"id": "3.8", "max_potential": 1.5, "evaluation_options": ["✅ Confirmed strength", "🚫 Not applicable"], "evaluation_coefficient_options": {"✅ Confirmed strength": 0, "🚫 Not applicable": 0}},
                    {"id": "3.9", "max_potential": 1.5, "evaluation_options": ["✅ Confirmed strength", "🚫 Not applicable"], "evaluation_coefficient_options": {"✅ Confirmed strength": 0, "🚫 Not applicable": 0}},
                    {"id": "4.4", "max_potential": 1.5, "evaluation_options": ["✅ Confirmed strength", "🚫 Not applicable"], "evaluation_coefficient_options": {"✅ Confirmed strength": 0, "🚫 Not applicable": 0}}
                ],
                "quick_diagnostic": []
            }
            ref_path = tmpdir / "eof-reference.json"
            ref_path.write_text(json.dumps(ref_data, ensure_ascii=False), encoding="utf-8")

            blocks_data = {
                "version": 1,
                "blocks": [
                    {
                        "id": "filter-env",
                        "file": "technical",
                        "phase": "detail",
                        "title": "Test environments",
                        "interviewee": "the person who operates the infrastructure",
                        "type": "filter",
                        "criteria": ["3.8", "3.9"],
                        "question": "Question env?",
                        "discarded_label": "No",
                        "applicable_label": "Yes"
                    },
                    {
                        "id": "filter-donnees",
                        "file": "technical",
                        "phase": "detail",
                        "title": "Persistent data",
                        "interviewee": "the person who manages the data",
                        "type": "filter",
                        "criteria": ["4.4"],
                        "question": "Question data?",
                        "discarded_label": "No",
                        "applicable_label": "Yes"
                    },
                    {
                        "id": "block-compose",
                        "file": "technical",
                        "phase": "detail",
                        "title": "Test environments",
                        "interviewee": "the person who operates the infrastructure",
                        "type": "composite",
                        "question": "Question composite?",
                        "options": [
                            {"label": "Option A", "answers": {"3.9": "✅ Confirmed strength", "4.4": "✅ Confirmed strength"}}
                        ]
                    }
                ]
            }
            blocks_path = tmpdir / "questionnaire-blocs.json"
            blocks_path.write_text(json.dumps(blocks_data, ensure_ascii=False), encoding="utf-8")

            audit_data = {
                "criteria": [
                    {"id": "3.8", "answer": None},
                    {"id": "3.9", "answer": None},
                    {"id": "4.4", "answer": None}
                ],
                "quick_diag_overview": {"questions": []}
            }
            audit_path = tmpdir / "eof-audit-results.json"
            audit_path.write_text(json.dumps(audit_data, ensure_ascii=False), encoding="utf-8")

            criteria_ref, diag_ref = load_reference(ref_path)
            audit, contexts = load_audit_results(tmpdir)
            blocks = load_blocks(tmpdir)

            result = generate_questionnaire_unique(blocks, audit,
                                                criteria_ref, diag_ref, tmpdir, contexts)

            if result is None:
                failures.append(("Block governed by two filters with AND", "No file generated"))
            else:
                content = result.read_text(encoding="utf-8")
                if " AND " not in content:
                    failures.append(("Block governed by two filters with AND", "Conjunction 'AND' missing from the mention"))
    except Exception as exc:
        failures.append(("Block governed by two filters with AND", f"Exception: {exc}"))

    # Case 22: Filter always placed before the blocks it governs
    total += 1
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            ref_data = {
                "criteria": [
                    {"id": "4.1", "max_potential": 1.5, "evaluation_options": ["✅ Confirmed strength", "🚫 Not applicable"], "evaluation_coefficient_options": {"✅ Confirmed strength": 0, "🚫 Not applicable": 0}},
                    {"id": "4.2", "max_potential": 1.5, "evaluation_options": ["✅ Confirmed strength", "🚫 Not applicable"], "evaluation_coefficient_options": {"✅ Confirmed strength": 0, "🚫 Not applicable": 0}}
                ],
                "quick_diagnostic": []
            }
            ref_path = tmpdir / "eof-reference.json"
            ref_path.write_text(json.dumps(ref_data, ensure_ascii=False), encoding="utf-8")

            blocks_data = {
                "version": 1,
                "blocks": [
                    {
                        "id": "filter-donnees",
                        "file": "technical",
                        "phase": "detail",
                        "title": "Storage",
                        "interviewee": "the person who manages the data",
                        "type": "filter",
                        "criteria": ["4.1", "4.2"],
                        "question": "Do you have data?",
                        "discarded_label": "No",
                        "applicable_label": "Yes"
                    },
                    {
                        "id": "block-4.1",
                        "file": "technical",
                        "phase": "detail",
                        "title": "Criterion 4.1",
                        "interviewee": "the person who manages the data",
                        "type": "direct",
                        "criterion": "4.1",
                        "question": "Question 4.1?"
                    }
                ]
            }
            blocks_path = tmpdir / "questionnaire-blocs.json"
            blocks_path.write_text(json.dumps(blocks_data, ensure_ascii=False), encoding="utf-8")

            audit_data = {
                "criteria": [
                    {"id": "4.1", "answer": None},
                    {"id": "4.2", "answer": None}
                ],
                "quick_diag_overview": {"questions": []}
            }
            audit_path = tmpdir / "eof-audit-results.json"
            audit_path.write_text(json.dumps(audit_data, ensure_ascii=False), encoding="utf-8")

            criteria_ref, diag_ref = load_reference(ref_path)
            audit, contexts = load_audit_results(tmpdir)
            blocks = load_blocks(tmpdir)

            result = generate_questionnaire_unique(blocks, audit,
                                                criteria_ref, diag_ref, tmpdir, contexts)

            if result is None:
                failures.append(("Filter before governed blocks", "No file generated"))
            else:
                content = result.read_text(encoding="utf-8")
                pos_filter = content.find("<!-- block:filter-donnees -->")
                pos_bloc = content.find("<!-- block:block-4.1 -->")
                if pos_filter == -1 or pos_bloc == -1:
                    failures.append(("Filter before governed blocks", "Blocks missing"))
                elif pos_filter > pos_bloc:
                    failures.append(("Filter before governed blocks", f"Filter after the governed block (positions: {pos_filter} > {pos_block})"))
    except Exception as exc:
        failures.append(("Filter before governed blocks", f"Exception: {exc}"))

    # Case 23: "DO NOT ANSWER" mention with two filters carries the two distinct labels
    total += 1
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            ref_data = {
                "criteria": [
                    {"id": "3.9", "max_potential": 1.5, "evaluation_options": ["✅ Confirmed strength", "🚫 Not applicable"], "evaluation_coefficient_options": {"✅ Confirmed strength": 0, "🚫 Not applicable": 0}},
                    {"id": "4.4", "max_potential": 2.0, "evaluation_options": ["✅ Confirmed strength", "🚫 Not applicable"], "evaluation_coefficient_options": {"✅ Confirmed strength": 0, "🚫 Not applicable": 0}}
                ],
                "quick_diagnostic": []
            }
            ref_path = tmpdir / "eof-reference.json"
            ref_path.write_text(json.dumps(ref_data, ensure_ascii=False), encoding="utf-8")

            blocks_data = {
                "version": 1,
                "blocks": [
                    {
                        "id": "filter-donnees",
                        "file": "technical",
                        "phase": "detail",
                        "title": "Service data storage",
                        "interviewee": "the person who manages the data",
                        "type": "filter",
                        "criteria": ["4.4"],
                        "question": "Question data?",
                        "discarded_label": "No, the service retains no data (neither database nor object storage)",
                        "applicable_label": "Yes"
                    },
                    {
                        "id": "filter-env",
                        "file": "technical",
                        "phase": "detail",
                        "title": "Test environments",
                        "interviewee": "the person who operates the infrastructure",
                        "type": "filter",
                        "criteria": ["3.9"],
                        "question": "Question env?",
                        "discarded_label": "No, no distinct pre-production environment (all tests run locally or in production)",
                        "applicable_label": "Yes"
                    },
                    {
                        "id": "block-compose",
                        "file": "technical",
                        "phase": "detail",
                        "title": "Test environment management",
                        "interviewee": "the person who operates the infrastructure",
                        "type": "composite",
                        "question": "Question composite?",
                        "options": [
                            {"label": "Option A", "answers": {"3.9": "✅ Confirmed strength", "4.4": "✅ Confirmed strength"}}
                        ]
                    }
                ]
            }
            blocks_path = tmpdir / "questionnaire-blocs.json"
            blocks_path.write_text(json.dumps(blocks_data, ensure_ascii=False), encoding="utf-8")

            audit_data = {
                "criteria": [
                    {"id": "3.9", "answer": None},
                    {"id": "4.4", "answer": None}
                ],
                "quick_diag_overview": {"questions": []}
            }
            audit_path = tmpdir / "eof-audit-results.json"
            audit_path.write_text(json.dumps(audit_data, ensure_ascii=False), encoding="utf-8")

            criteria_ref, diag_ref = load_reference(ref_path)
            audit, contexts = load_audit_results(tmpdir)
            blocks = load_blocks(tmpdir)

            result = generate_questionnaire_unique(blocks, audit,
                                                criteria_ref, diag_ref, tmpdir, contexts)

            if result is None:
                failures.append(("Mention two filters two labels", "No file generated"))
            else:
                content = result.read_text(encoding="utf-8")
                # Check that both labels appear in the mention
                data_label = "No, the service retains no data"
                env_label = "No, no distinct pre-production environment"

                if data_label not in content:
                    failures.append(("Mention two filters two labels", f"Data filter label missing: {data_label}"))
                if env_label not in content:
                    failures.append(("Mention two filters two labels", f"Env filter label missing: {env_label}"))
                # Check that the AND conjunction is present
                if " AND " not in content:
                    failures.append(("Mention two filters two labels", "Conjunction 'AND' missing"))
    except Exception as exc:
        failures.append(("Mention two filters two labels", f"Exception: {exc}"))

    if failures:
        print(f"AUTOTEST FAILED: {len(failures)} case(s) out of {total}")
        for label, error in failures:
            print(f"  - {label}")
            print(f"      {error}")
        return 1

    print(f"Autotest: {total} cases passed.")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Generates an EOF questionnaire from an existing audit")
    parser.add_argument("audit_dir", nargs="?",
                        help="audit directory containing eof-audit-results.json")
    parser.add_argument("--output-dir",
                        help="output directory (default: audit_dir)")
    parser.add_argument("--in-audit-dir", action="store_true",
                        help="allows writing into a path containing 'audits'")
    parser.add_argument("--autotest", action="store_true",
                        help="replays the embedded test cases and exits 1 if a case fails")
    args = parser.parse_args()

    if args.autotest:
        sys.exit(autotest())

    if not args.audit_dir:
        parser.error("audit_dir is required (or use --autotest)")

    audit_dir = Path(args.audit_dir).resolve()
    output_dir = Path(args.output_dir).resolve() if args.output_dir else audit_dir

    # Guard: refuse to write into audits/ without an explicit flag
    if "audits" in output_dir.parts and not args.in_audit_dir:
        print(
            "ERROR: This script refuses to write into a path containing 'audits'.\n"
            "\n"
            "REASON: A generated questionnaire is BLANK, all its boxes remain to be ticked.\n"
            "Only a questionnaire returned FILLED-IN by the client may exist in\n"
            "audits/<domain>/. A blank questionnaire in this directory can be sent\n"
            "to the client as if it were up to date, when it contains no answer.\n"
            "\n"
            "SOLUTION:\n"
            "  - To generate safely: --output-dir /tmp/questionnaire-<domain>\n"
            "  - To force (if you know what you are doing): --in-audit-dir\n",
            file=sys.stderr
        )
        sys.exit(2)

    # Load the data
    ref_path = find_reference()
    criteria_ref, quick_diag_ref = load_reference(ref_path)
    audit_results, contexts = load_audit_results(audit_dir)

    # Find the block library
    scripts_dir = Path(__file__).resolve().parent
    blocks_data = load_blocks(scripts_dir)

    # Generate the single questionnaire
    result = generate_questionnaire_unique(blocks_data, audit_results,
                                          criteria_ref, quick_diag_ref, output_dir, contexts)
    if result:
        print(f"Generated: {result}")
    else:
        print("No block to display (empty residual)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
