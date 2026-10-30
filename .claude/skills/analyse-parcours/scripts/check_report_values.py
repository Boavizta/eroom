#!/usr/bin/env python3
"""
Guardrail on the VALUES DISPLAYED in a report, not on key names.

WHY THIS SCRIPT EXISTS
----------------------
The project already checked the NAMES of its data (`validate_key_consistency.py`,
`validate_manifest.py`, `validate_lot_output.py`). No check looked at what the
reader sees on screen. Lived consequence: two dimensions of the EOF radar had
received no answer, Python returned its word for "no value", and the report
displayed literally

    <text ... font-weight="bold">None%</text>

in blue, bold, in the center of the image, in a deliverable meant for a client.
The bug went through the whole project control chain: the keys were right, the
badges were present, only the rendering was wrong.

This script fails if the VISIBLE text of the report contains:
  - an internal Python or JavaScript value copied as-is
    (`None`, `NaN`, `null`, `undefined`, `True`, ...) ;
  - a template placeholder never substituted (`{today}`, `{{`, `%s`) ;
  - a trace of internal representation or crash
    (`<class '`, `object at 0x`, `Traceback`, `KeyError`, ...).

WHAT IT DOES NOT DO, AND THAT MUST BE SAID
------------------------------------------
It catches the MISSING or UNSUBSTITUTED value, not the WRONG value. A
percentage computed with the wrong denameinator, a provenance wrongly promoted,
a figure taken on the wrong criterion: all of that passes here silently, because
a plausible number looks like a correct number. The only check that catches
that is recomputing the arithmetic from the data, and reading the produced image.

It does not replace LOOKING at the report either. It proves the absence of a few
known accidents, not the readability of a page.

WHY IT IS NOT BLOCKING IN THE GENERATOR
----------------------------------------
Run alone, it returns exit code 1 when it finds something, like the other
project checks, so it can join a battery. Called from
`generate_report_html.py`, it only WARNS: the report is still produced and the
generation ends normally. The user's decision, and a defensible one: an axis
without an answer is a legitimate state of the framework today, it will become
rarer as coverage progresses.

Usage:
    python3 check_report_values.py <report.html>        # one file
    python3 check_report_values.py <audit-dir>          # most recent report
    python3 check_report_values.py <radar.svg>          # one SVG only
    python3 check_report_values.py --list-motifs        # shows the watched patterns
    python3 check_report_values.py <target> --audit-exemptions

Exit code: 0 if no leak, 1 otherwise.

EXEMPTION
---------
A legitimate occurrence is exempted by a comment on the SAME line, with its
mandatory reason:

    <!-- values: ok - <reason> -->

An exemption without a written reason is rejected and reported. The count of
exempted lines is printed on every run, so an exemption stays a visible choice
and not an installed silence.
"""

import argparse
import html
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# The watched patterns
#
# Each entry: (literal, human-readable reason).
# Everything is CASE-SENSITIVE: `None` is a Python value, `none` is a perfectly
# legitimate CSS value (`border:none`, `fill="none"`). That distinction, plus
# looking only at visible text, is what avoids the noise.
# ---------------------------------------------------------------------------

INTERNAL_VALUES = [
    ("None", "Python missing value displayed as-is"),
    ("NaN", "result of an impossible calculation (JavaScript)"),
    ("nan", "result of an impossible calculation (Python, float)"),
    ("Infinity", "division by zero (JavaScript)"),
    ("inf", "division by zero (Python, float)"),
    ("null", "missing value from JSON or JavaScript"),
    ("undefined", "JavaScript variable never assigned"),
    ("True", "Python boolean not translated for the reader"),
    ("False", "Python boolean not translated for the reader"),
]

# These traces start with `<`, so the browser takes them for an unknown tag and
# does NOT display them. The reader sees nothing at all, which is even more
# treacherous than a visible `None%`: a piece of the page is missing and nobody
# can guess it. Since my visible-text extractor strips tags, it would swallow
# them exactly like the browser does. So they are searched in the RAW file,
# and only there.
MASKED_TRACES = [
    ("<class '", "unescaped Python type: swallowed as a tag, content missing"),
    ("<built-in ", "unescaped Python function: swallowed as a tag"),
    ("<generator object", "unescaped Python generator: swallowed as a tag"),
    ("<function ", "unescaped Python function: swallowed as a tag"),
]

INTERNAL_TRACES = [
    ("dict_keys(", "Python dict view displayed as-is"),
    ("dict_values(", "Python dict view displayed as-is"),
    ("Traceback (most recent call last)", "Python crash traceback"),
    ("KeyError", "missing key, crash copied into the deliverable"),
    ("TypeError", "type error, crash copied into the deliverable"),
    ("ValueError", "value error, crash copied into the deliverable"),
    ("AttributeError", "missing attribute, crash copied into the deliverable"),
    ("IndexError", "index out of range, crash copied into the deliverable"),
    ("ZeroDivisionError", "division by zero, crash copied into the deliverable"),
]

# These traces are not written as literals: their end is variable, and a word
# boundary after a hexadecimal prefix would never match anything (`object at 0x`
# followed by `10f3a2b80`: no boundary between `x` and `1`).
# The embedded negative test caught exactly this bug.
TRACES_REGEX = [
    (r"object at 0x[0-9a-fA-F]+", "memory address of a Python object"),
]

TEMPLATES = [
    (r"\{\{", "escaped Python brace, template never rendered"),
    (r"\}\}", "escaped Python brace, template never rendered"),
    (
        r"\{[A-Za-z_][A-Za-z0-9_.\[\]'\"]*\}",
        "template placeholder never substituted",
    ),
    (r"%[sdr]\b", "printf placeholder never substituted"),
]


def _compile_literal(literal):
    """Escapes a literal and wraps it in word boundaries where useful.

    Without the boundary, `inf` would match `information` and the check would
    become unusable. But `<class '` does not start with a word character, and
    sticking a `\\b` on it would never match anything.
    """
    pattern = re.escape(literal)
    if literal[:1].isalnum() or literal[:1] == "_":
        pattern = r"\b" + pattern
    if literal[-1:].isalnum() or literal[-1:] == "_":
        pattern = pattern + r"\b"
    return re.compile(pattern)


def visible_text_patterns():
    """The patterns searched in the text the reader sees."""
    patterns = []
    for literal, reason in INTERNAL_VALUES + INTERNAL_TRACES + MASKED_TRACES:
        patterns.append((literal, _compile_literal(literal), reason))
    for pattern, reason in TRACES_REGEX + TEMPLATES:
        patterns.append((pattern, re.compile(pattern), reason))
    return patterns


def raw_file_patterns():
    """The patterns searched in the raw file, because they are invisible there.

    An escaped Python trace (`&lt;class 'dict'&gt;`) is properly caught by the
    visible-text check. The same UNescaped trace passes for a tag: the browser
    hides it, my extractor strips it, and the check would see nothing. So it is
    only found in the raw file.
    """
    return [
        (literal, _compile_literal(literal), reason)
        for literal, reason in MASKED_TRACES
    ]


# ---------------------------------------------------------------------------
# Visible text extraction
#
# The principle: NEVER search in the raw file. A report contains CSS
# (`display:none`), JavaScript and SVG attributes (`fill="none"`) that
# legitimately use watched words. Searching the raw file would drown the real
# leak under dozens of false positives.
#
# Removed zones are replaced by the SAME number of newlines they contained, so
# that line numbers stay those of the original file. Without that, every
# reported number would be wrong.
# ---------------------------------------------------------------------------

_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_SCRIPT = re.compile(r"<script\b.*?</script\s*>", re.DOTALL | re.IGNORECASE)
_STYLE = re.compile(r"<style\b.*?</style\s*>", re.DOTALL | re.IGNORECASE)
_BALISE = re.compile(r"<[^>]*>", re.DOTALL)


def _replace_with_newlines(match):
    """Keeps the newlines, drops the rest."""
    return "\n" * match.group(0).count("\n")


def _replace_tag(match):
    """A tag becomes a space, so two neighboring words don't stick together."""
    content = match.group(0)
    return "\n" * content.count("\n") + " "


def visible_text(source):
    """Returns the text the reader sees, with the original line numbers."""
    text = _SCRIPT.sub(_replace_with_newlines, source)
    text = _STYLE.sub(_replace_with_newlines, text)
    text = _HTML_COMMENT.sub(_replace_with_newlines, text)
    text = _BALISE.sub(_replace_tag, text)
    return html.unescape(text)


# ---------------------------------------------------------------------------
# Exemptions
# ---------------------------------------------------------------------------

_EXEMPTION = re.compile(r"<!--\s*values:\s*ok\b\s*-?\s*(?P<reason>.*?)\s*-->")


def read_exemptions(source):
    """Returns ({line_no: reason}, [(line_no, problem)]).

    The exemption is searched in the ORIGINAL source, comments included,
    since visible-text extraction removes them precisely.
    """
    exempted = {}
    malformed = []
    for line_no, line in enumerate(source.splitlines(), start=1):
        match = _EXEMPTION.search(line)
        if not match:
            continue
        reason = match.group("reason").strip()
        if not reason:
            malformed.append((line_no, "exemption without a written reason"))
            continue
        exempted[line_no] = reason
    return exempted, malformed


# ---------------------------------------------------------------------------
# Checking one file
# ---------------------------------------------------------------------------

EXTRACT_WIDTH = 90


def _excerpt(line, start, end):
    """A piece of line centered on the finding, on a single line."""
    margin = max(0, (EXTRACT_WIDTH - (end - start)) // 2)
    left = max(0, start - margin)
    right = min(len(line), end + margin)
    excerpt = re.sub(r"\s+", " ", line[left:right]).strip()
    if left > 0:
        excerpt = "..." + excerpt
    if right < len(line):
        excerpt = excerpt + "..."
    return excerpt


def _scan(lines, patterns, exempted, seen, leaks):
    """Searches each pattern in each line, once per pair.

    One leak per pattern per line: the goal is to alert, not to count. A line
    carrying three is fixed in one go.
    """
    for line_no, line in enumerate(lines, start=1):
        if line_no in exempted:
            continue
        for name, regex, reason in patterns:
            if (line_no, name) in seen:
                continue
            match = regex.search(line)
            if match:
                seen.add((line_no, name))
                leaks.append(
                    (line_no, name, reason, _excerpt(line, match.start(), match.end()))
                )


def check(source):
    """Returns ([(line_no, pattern, reason, excerpt)], exempted, malformed)."""
    exempted, malformed = read_exemptions(source)
    leaks = []
    seen = set()
    _scan(
        visible_text(source).splitlines(),
        visible_text_patterns(),
        exempted,
        seen,
        leaks,
    )
    _scan(source.splitlines(), raw_file_patterns(), exempted, seen, leaks)
    leaks.sort(key=lambda leak: (leak[0], leak[1]))
    return leaks, exempted, malformed


# ---------------------------------------------------------------------------
# Target resolution
# ---------------------------------------------------------------------------

REPORT_PATTERNS = ("journey-report-*.html", "*.html")
EXTENSIONS = {".html", ".htm", ".xhtml", ".svg"}


def resolve_targets(path):
    """Returns the list of files to check, or raises ValueError.

    A directory yields the most recent report in alphabetical order, because
    report names carry their ISO date and therefore sort chronologically.
    """
    path = Path(path)
    if path.is_file():
        return [path]
    if not path.is_dir():
        raise ValueError(f"target not found: {path}")
    for pattern in REPORT_PATTERNS:
        candidates = sorted(path.glob(pattern))
        if candidates:
            return [candidates[-1]]
    raise ValueError(f"no HTML report in {path}")


# ---------------------------------------------------------------------------
# Negative test, embedded in the script
#
# A guardrail whose negative test does not break is worth nothing. The cases
# live here, and not in a throwaway /tmp file, so they can be replayed months
# later by someone who did not attend their writing.
#
# Two families, both equally important:
#   - MUST_ALERT: the known accidents. If they pass, the net has a hole.
#   - MUST_NOT_ALERT: the legitimate usages. If they alert, the check becomes
#     noisy, we will ignore it, and it will be useless.
# ---------------------------------------------------------------------------

MUST_ALERT = [
    ("the None% of the EOF radar", '<text font-weight="bold">None%</text>'),
    ("a None in a table", "<td>Instance type</td><td>None</td>"),
    ("a nan from a Python float", "<p>Emissions: nan gCO2e</p>"),
    ("a NaN from JavaScript", "<p>Total: NaN kg</p>"),
    ("a null from JSON", "<td>Server country</td><td>null</td>"),
    ("an undefined from JavaScript", "<span>undefined</span>"),
    ("an Infinity from JavaScript", "<td>Infinity</td>"),
    ("an inf from a Python float", "<td>inf</td>"),
    ("an untranslated Python boolean", "<td>Consent</td><td>True</td>"),
    ("an unsubstituted template placeholder", "<footer>Report generated on {today}</footer>"),
    ("an escaped Python brace", "<p>Total {{ value }}</p>"),
    ("an unsubstituted printf placeholder", "<p>Analyzed domain: %s</p>"),
    ("an escaped Python trace", "<td>&lt;class 'dict'&gt;</td>"),
    ("an UNescaped Python trace", "<td><class 'dict'></td>"),
    ("a copied crash", "<pre>Traceback (most recent call last)</pre>"),
    ("a copied missing key", "<p>KeyError: 'provenance'</p>"),
    ("a memory address", "<td>&lt;Server object at 0x10f3a2b80&gt;</td>"),
]

MUST_NOT_ALERT = [
    ("CSS none", "<style>.tuile{border:none;display:none}</style>"),
    ("SVG attribute none", '<path fill="none" stroke="none" d="M0 0"/>'),
    ("JavaScript null and undefined", "<script>var x=null;if(y===undefined){}</script>"),
    ("a None in an HTML comment", "<!-- old label: None -->"),
    ("French containing the letters", "<p>Trivial information, no inference</p>"),
    ("a percentage followed by a word", "<p>12.5% of criteria, 90% of the total</p>"),
    ("the radar placeholder label", '<text fill="#5F5F5F">no answer</text>'),
    ("a lone brace in text", "<p>Dimension {5} does not exist</p>"),
    (
        "an exempted None with its reason",
        "<td>None</td> <!-- values: ok - raw value rendered by the provider -->",
    ),
]


def autotest():
    """Replays the textbook cases. Returns 0 if the net does exactly its job."""
    failures = []

    for description, fragment in MUST_ALERT:
        leaks, _exempted, _malformed = check(fragment)
        if not leaks:
            failures.append(f"NOT DETECTED - {description} : {fragment}")

    for description, fragment in MUST_NOT_ALERT:
        leaks, _exempted, _malformed = check(fragment)
        if leaks:
            patterns = ", ".join(sorted({leak[1] for leak in leaks}))
            failures.append(f"FALSE ALERT - {description} : pattern(s) {patterns}")

    # An exemption without a reason must be rejected, otherwise the exemption
    # becomes a silent switch that we will put everywhere.
    _leaks, _exempted, malformed = check("<td>None</td> <!-- values: ok -->")
    if not malformed:
        failures.append("NOT DETECTED - an exemption without a written reason is accepted")

    # The reported line number must be that of the FILE, not of the extracted
    # text. That is what breaks first if the extraction changes.
    source = "<style>\n.a{color:red}\n</style>\n<p>x</p>\n<td>None</td>\n"
    leaks, _exempted, _malformed = check(source)
    if not leaks or leaks[0][0] != 5:
        got = leaks[0][0] if leaks else "no leak"
        failures.append(f"WRONG LINE NUMBER - expected 5, got {got}")

    total = len(MUST_ALERT) + len(MUST_NOT_ALERT) + 2
    if failures:
        print(f"[FAIL] {len(failures)} cases out of {total}:")
        for failure in failures:
            print(f"    {failure}")
        print()
        print("The guardrail does not do what it claims. Do not commit it as is.")
        return 1

    print(f"[SUCCESS] {total} cases passed:")
    print(f"    {len(MUST_ALERT)} known accident(s) correctly detected")
    print(f"    {len(MUST_NOT_ALERT)} legitimate usage(s) correctly ignored")
    print("    the exemption without a reason is rejected")
    print("    the reported line number is that of the file")
    return 0


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Checks the values displayed in an already generated report.",
    )
    parser.add_argument(
        "target",
        nargs="?",
        help="an HTML report, an SVG, or an audit directory (most recent report)",
    )
    parser.add_argument(
        "--list-motifs",
        action="store_true",
        help="lists the watched patterns and exits",
    )
    parser.add_argument(
        "--audit-exemptions",
        action="store_true",
        help="lists the exemptions in force instead of checking",
    )
    parser.add_argument(
        "--autotest",
        action="store_true",
        help="replays the guardrail's textbook cases and exits",
    )
    args = parser.parse_args(argv)

    if args.autotest:
        return autotest()

    if args.list_motifs:
        visible = visible_text_patterns()
        raw = raw_file_patterns()
        print(f"{len(visible)} pattern(s) in the VISIBLE TEXT, case-sensitive:")
        for name, _regex, reason in visible:
            print(f"    {name:38s} {reason}")
        print()
        print("The <script> and <style> blocks, comments and tag attributes are")
        print("removed before searching. That is what allows keeping `None` without")
        print("being drowned by the SVG `fill=\"none\"` and the CSS `border:none`.")
        print()
        print(f"{len(raw)} pattern(s) in the RAW FILE, because an unescaped trace")
        print("passes for a tag and disappears from the screen:")
        for name, _regex, reason in raw:
            print(f"    {name:38s} {reason}")
        return 0

    if not args.target:
        parser.print_usage()
        print("[error] provide a report, an SVG or an audit directory.")
        return 1

    try:
        targets = resolve_targets(args.target)
    except ValueError as error:
        print(f"[error] {error}")
        return 1

    total_leaks = 0
    total_exempted = 0
    total_malformed = 0

    for target in targets:
        if target.suffix.lower() not in EXTENSIONS:
            print(f"[info] {target.name} skipped: unsupported extension.")
            continue
        source = target.read_text(encoding="utf-8", errors="replace")
        leaks, exempted, malformed = check(source)
        total_exempted += len(exempted)
        total_malformed += len(malformed)

        if args.audit_exemptions:
            if exempted:
                print(f"{target.name} - {len(exempted)} exempted line(s):")
                for line_no, reason in sorted(exempted.items()):
                    print(f"    {target.name}:{line_no}  {reason}")
            continue

        for line_no, problem in malformed:
            print(f"[FAIL] {target.name}:{line_no}  {problem}")

        suffix = f"  ({len(exempted)} exempted line(s))" if exempted else ""
        if not leaks:
            print(f"[OK] {target.name}{suffix}")
            continue
        total_leaks += len(leaks)
        print(f"[FAIL] {target.name} - {len(leaks)} leak(s){suffix}:")
        for line_no, name, reason, excerpt in leaks:
            print(f"    {target.name}:{line_no}  {name} - {reason}")
            print(f"        {excerpt}")
        print()

    if args.audit_exemptions:
        print()
        print(f"{total_exempted} exempted line(s) in total.")
        print("Each one is a place where the check sees nothing. Verify that the")
        print("reason still holds.")
        return 0

    print()
    if total_leaks or total_malformed:
        if total_leaks:
            print(f"[FAIL] {total_leaks} value leak(s) in the visible text.")
            print("The report reader sees these characters on screen. Three remedies,")
            print("in this order of preference:")
            print("  1. handle the missing case at the source, with a readable label")
            print("     (the radar shows \"no answer\" instead of a false 0%);")
            print("  2. fix the template if the placeholder was never substituted;")
            print("  3. if the occurrence is legitimate, exempt it with its reason:")
            print("     <!-- values: ok - <reason> -->")
        if total_malformed:
            print(f"[FAIL] {total_malformed} exemption(s) without a written reason.")
            print("An exemption without a reason becomes a silence again in six months.")
        return 1

    print("[SUCCESS] No internal value in the visible text of the report.")
    if total_exempted:
        print(f"({total_exempted} exempted line(s) - review them with --audit-exemptions.)")
    print("Reminder: this check catches the MISSING or UNSUBSTITUTED value, NOT the")
    print("WRONG value. A plausible but wrongly computed number passes here without")
    print("flinching. Looking at the produced image is still mandatory.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
