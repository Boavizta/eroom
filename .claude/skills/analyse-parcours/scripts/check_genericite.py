#!/usr/bin/env python3
"""
Safety net for the e-footprint refactoring: GENERICITY check.

WHY THIS SCRIPT EXISTS
-----------------------
The modeling library must work on ANY site, not
only on the test case. The risk is not theoretical: when moving
code around, it is easy to freeze into the library a value that had been
MEASURED on one specific site. This kind of mistake is invisible on re-reading, because
a bare number looks like a physical constant.

This script fails if the library contains:
  - a literal domain name or IP address
  - a numeric value measured on an audit case (the most sneaky mistake:
    it passes all name greps)
  - a file path specific to an audit case

WHAT IT DOES NOT DO, AND THAT MUST BE SAID
------------------------------------------
It catches COPY-PASTE, not DESIGN BIAS. A function that implicitly assumes
a two-server site, or that assumes complete HTML is served,
will pass this check without a flinch. The only check that proves
genericity is execution on a second real site.

It is deliberately launched EARLY, from lot 0, to fail on the first
copy-paste and not three lots later.

Usage:
    python3 check_genericite.py                      # default target
    python3 check_genericite.py <directory>          # explicit target
    python3 check_genericite.py --list-values        # show forbidden values

Exit code: 0 if the target is generic, 1 otherwise.

WHAT IS EXCLUDED FROM THE ANALYSIS, and why:
  - docstrings and comments: a documented example is legitimate and
    even useful ("e.g. audits/octo.com"). Only EXECUTABLE CODE is checked.
  - `check_efootprint_contract.py` and `tmp/`: the test case values belong
    there, that is their reason to exist.

EXPLICIT EXEMPTIONS
-------------------
Some occurrences are legitimate: a table of known trackers, the
declaration of a path constant, a demo block. They
exempt themselves with a marker that MUST carry its reason:

    RAW_DATA_DIR = "..."          # genericity: ok - constant declaration

    TRACKER_DOMAINS = {           # genericity: ok-start - explicit third-party table
        "google-analytics.com",
    }                             # genericity: ok-end

An exemption without a reason is refused: disabling the net must cost a
sentence, otherwise it empties of meaning line by line. `--audit-exemptions` lists
them all, so they remain reviewable.
"""

import argparse
import ast
import io
import re
import sys
import tokenize
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
SCRIPTS_DIR = Path(__file__).resolve().parent

# Default target: the modeling library, when it exists (lot 1).
DEFAULT_TARGET = SCRIPTS_DIR / "efootprint_model"

# ---------------------------------------------------------------------------
# Values measured on audit cases: FORBIDDEN in the library
# ---------------------------------------------------------------------------
# Each value carries its origin. Without this trace, in six
# months nobody would know why such-and-such a number is banned, and the
# list would become folklore.
#
# Any new measurement published in a report must be ADDED here.

FORBIDDEN_VALUES = {
    # Word counts of the test case pages (measured in the HAR)
    317.0: "word count, test case",
    356.0: "word count, test case",
    153.0: "word count, test case",
    1096.0: "word count, test case",
    591.0: "word count, test case",
    # SimilarWeb audience data of the test case
    2.116: "SimilarWeb audience, test case",
    33.979: "SimilarWeb audience, test case",
    0.460: "SimilarWeb audience, test case",
    36654.0: "SimilarWeb audience, test case",
    16.1: "SimilarWeb visit duration, test case",
    # CO2e totals and derived factors of the test case
    174.139: "total CO2e (own parsing), test case",
    174.076: "total CO2e (published, read by regex), test case",
    146.16: "total CO2e in serverless, test case",
    235.47: "total CO2e, variant measured on the test case",
    203.45: "total CO2e with 2 servers, test case",
    203.454: "total CO2e with 2 servers, test case",
    176.805: "total CO2e, 2nd server without storage, test case",
    0.41: "Nielsen recalibration factor, computed on a SINGLE site",
    38.9: "value measured on the test case, precise origin untraced",
    82.0: "value measured on the test case, precise origin untraced",
    440.0: "annual visits (thousands), test case",
    # Bounds of the published ranges (measured on the test case)
    145.1: "lower bound infrastructure range, test case",
    271.4: "upper bound of the released total, test case",
    45.9: "lower bound of the released total, test case",
    242.1: "upper bound usage range, test case",
    74.9: "lower bound usage range, test case",
    26.6: "CO2e of manufacturing a 1 TB Storage, test case",
    # CO2e per request tested for third-party hosts (no public source)
    306.139: "total CO2e with third-party hosts at 0.2 g/request, test case",
    187.339: "total CO2e with third-party hosts at 0.02 g/request, test case",
    # Full replay of 08/06/2026: re-collection CrUX/SimilarWeb, device
    # mix moved. These totals replace 174.076 in the delivered reports.
    170.856: "total CO2e after replay, test case",
    # Lot 2 (08/07/2026): build_system() + own extraction (without regex) on
    # the replayed env-data.json. Replaces 174.139 as non-regression marker.
    170.904: "total CO2e (own parsing, Lot 2), test case",
    # Lot 3 (08/07/2026): from_har.py, multi-step journey + multiple infras.
    # Validation confirmed: the HAR = one person's journey, so each captured
    # page becomes a step (instead of only the heaviest page).
    853.336: "total CO2e (multi-step, Lot 3), test case octo.com",
    14480.895: "total CO2e (3 servers + 3 steps, Lot 3), test case ANTS",
    4801.2: "total CO2e of the second test case (public site)",
    # Dead code after fixing the versioned URL typing
    975.5: "unused CSS (KB), test case",
    161.9: "unused CSS of one page (KB), test case",
    926.6: "unused CSS (KB), second test case",
    4270.6: "unused CSS (KB), second test case",
    10146.6: "unused JS (KB), second test case",
    # Coverage aggregates recomputed by coverage_metrics.py, which classifies the extension
    # on the URL PATH. The page whose URLs are all versioned was
    # published at zero: these totals replace 17657.4 / 9736.3 / 3491.5 / 3024.2.
    18226.6: "total JS (KB), second test case",
    10146.4: "unused JS (KB), second test case, deterministic computation",
    4840.4: "total CSS (KB), second test case",
    4270.7: "unused CSS (KB), second test case, deterministic computation",
    1349.1: "total CSS of the DSFR-served page (KB), second test case",
    1246.4: "unused CSS of the DSFR-served page (KB), second test case",
    # HAR aggregates of the two test cases
    6987.9: "total HAR weight (KB), test case",
    17674.3: "total HAR weight (KB), second test case",
    # Lot 4 (08/07/2026): user_time.py, Nielsen recalibrated on Engagments
    # SimilarWeb (average of the journey's raw Nielsens, cf. its docstring).
    16.058: "SimilarWeb average time per page (TimeOnSite/PagePerVisit), test case",
    0.250109: "Nielsen recalibration factor (multi-step journey method), test case",
    560.9885: "total CO2e (recalibrated Nielsen, Lot 4), test case octo.com",
    14372.7561: "total CO2e (raw Nielsen, no SimilarWeb recalibration, Lot 4), test case ANTS",
    # Lot 4bis (08/07/2026): ranges.py, infra/usage ranges measured on
    # the two audit cases (cf. tmp/lot2/_verif_lot4bis_fourchettes.py).
    533.0142: "lower bound infra range (serverless), Lot 4bis, test case octo.com",
    881.3057: "upper bound usage range (raw Nielsen), Lot 4bis, test case octo.com",
    14036.2206: "lower bound infra range (serverless), Lot 4bis, test case ANTS",
    # Lot 10 (08/11/2026): fix of the words<->page pairing bug (from_har.py):
    # the word count already existed in the HAR on ANOTHER repetition of
    # the same URL as the one retained for network weight, never read until then.
    # Replaces 560.9885 as non-regression marker for octo.com.
    268.6406: "total CO2e after words/page pairing fix (Lot 10), test case octo.com",
}

# A short integer (82, 440, 317) is a COMMON number: it can legitimately
# denote a count, a size, a status code. Measured on the existing
# code, `82` thus appeared in a perfectly legitimate EcoIndex validation
# block of `har_metrics.py`. Reporting these values is still useful, but
# announcing them with the same confidence as a `174.139` would lie about the
# precision of the check. They are therefore marked "to verify" in the report.
#
# A multi-decimal float, on the other hand, does not appear by chance.
COLLISION_PRONE_MAX = 1000.0


def collision_prone(value):
    """Is the value a common number, likely to appear legitimately?"""
    return value.is_integer() and abs(value) < COLLISION_PRONE_MAX

# Values allowed despite their possible presence in the lists above:
# they are conversion constants or universal quantities.
ALLOWED_VALUES = {
    0.0, 1.0, 2.0, 3.0, 100.0, 1000.0,
    8760.0,     # hours in a year
    24.0, 60.0, 365.0,
    1024.0,
}

# Comparison tolerance: a 174.0761 hand-copied must be caught.
VALUE_TOLERANCE = 1e-4

# ---------------------------------------------------------------------------
# Forbidden textual patterns in executable code
# ---------------------------------------------------------------------------

FORBIDDEN_PATTERNS = [
    (
        re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
        "literal IP address",
    ),
    (
        # Domain name. The listed extensions are those likely
        # to appear in an audit case; the list is deliberately short
        # to avoid catching Python module names (`os.path`).
        re.compile(
            r"\b[a-z0-9][a-z0-9-]*(?:\.[a-z0-9-]+)*"
            r"\.(?:com|fr|org|net|io|gouv\.fr|tools|ai|dev|co)\b"
        ),
        "literal domain name",
    ),
    (
        re.compile(r"\baudits?/[A-Za-z0-9._-]+"),
        "path to an audit case",
    ),
    (
        re.compile(r"raw-data-potentially-sensitive"),
        "hardcoded raw capture path (use the RAW_DATA_DIR constant)",
    ),
]


# ---------------------------------------------------------------------------
# Explicit exemptions
# ---------------------------------------------------------------------------
# The marker is looked for in the ORIGINAL source (comments included), while
# violations are looked for in code only. The two passes share the
# line numbering, which makes the correspondence direct.

EXEMPT_LINE = re.compile(r"#\s*genericity:\s*ok\b\s*-?\s*(?P<reason>.*)$")
EXEMPT_START = re.compile(r"#\s*genericity:\s*ok-start\b\s*-?\s*(?P<reason>.*)$")
EXEMPT_END = re.compile(r"#\s*genericity:\s*ok-end\b")


def parse_exemptions(source):
    """Returns ({exempted_line: reason}, [(line, problem)]).

    The second element lists MALFORMED exemptions: marker without reason, or
    block opened and never closed. These are errors, not warnings: a
    silent exemption is exactly what this script exists to prevent.
    """
    exempt = {}
    malformed = []
    block_start = None
    block_reason = None

    for lineno, line in enumerate(source.splitlines(), start=1):
        if EXEMPT_END.search(line):
            if block_start is None:
                malformed.append((lineno, "ok-end marker without ok-start"))
            else:
                for row in range(block_start, lineno + 1):
                    exempt[row] = block_reason
                block_start = None
                block_reason = None
            continue

        match_start = EXEMPT_START.search(line)
        if match_start:
            reason = match_start.group("reason").strip()
            if not reason:
                malformed.append((lineno, "block exemption without a written reason"))
                continue
            if block_start is not None:
                malformed.append((lineno, "ok-start nested inside an already open block"))
                continue
            block_start = lineno
            block_reason = reason
            continue

        # ok-start also matches EXEMPT_LINE; the order of the tests already excludes it.
        match_line = EXEMPT_LINE.search(line)
        if match_line:
            reason = match_line.group("reason").strip()
            if not reason:
                malformed.append((lineno, "line exemption without a written reason"))
            else:
                exempt[lineno] = reason

    if block_start is not None:
        malformed.append((block_start, "ok-start block never closed by ok-end"))

    return exempt, malformed


# ---------------------------------------------------------------------------
# Executable code only extraction
# ---------------------------------------------------------------------------

def strip_comments_and_docstrings(source):
    """Returns the source stripped of its comments and docstrings.

    Two passes, because neither suffices alone:
      - `tokenize` removes comments (`ast` does not see them at all).
      - `ast` identifies docstrings (`tokenize` does not distinguish a docstring
        from an ordinary string literal).

    Removed lines are replaced by empty lines rather than
    deleted, so that reported line numbers remain EXACT and
    clickable.

    SUBTLETY THAT ONCE PUNCHED A HOLE IN THE NET (fixed at lot 1): a class
    or function whose body is ONLY a docstring ends up with
    an empty body after cleaning, which makes the result syntactically
    invalid. `numeric_literals()` then returned an empty list and ALL the
    measured-value check of the file was silently disabled, without any
    message. The docstring is therefore replaced by a properly indented
    `pass`, and `numeric_literals()` now reports its failure instead of staying silent.
    """
    lines = source.splitlines()

    # Pass 1: neutralize comments.
    try:
        tokens = tokenize.generate_tokens(io.StringIO(source).readline)
        for token in tokens:
            if token.type == tokenize.COMMENT:
                row, col = token.start
                lines[row - 1] = lines[row - 1][:col]
    except (tokenize.TokenError, IndentationError):
        # Non-tokenizable source: continue without this pass rather than
        # abandoning the file. The check remains useful, just less precise.
        pass

    # Pass 2: neutralize docstrings.
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return "\n".join(lines)

    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.FunctionDef,
                                 ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        body = getattr(node, "body", None)
        if not body:
            continue
        first = body[0]
        if not (isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)):
            continue
        for row in range(first.lineno, (first.end_lineno or first.lineno) + 1):
            lines[row - 1] = ""
        # If the docstring was the whole body, it must be replaced by a
        # `pass` at the right indentation, otherwise the cleaned file no longer parses
        # and the value check silently deactivates.
        if len(body) == 1 and not isinstance(node, ast.Module):
            indent = " " * first.col_offset
            lines[first.lineno - 1] = f"{indent}pass"

    return "\n".join(lines)


def numeric_literals(source):
    """Returns the numeric literals of the code, as (line, value).

    Goes through the syntax tree: a number written inside a string
    is not a numeric literal and must not trigger an alert.

    Raises SyntaxError if the cleaned source does not parse. It used to be
    a silent `return []`, hence a check that cancelled itself while
    staying green. A net that disables itself without saying so is worse than an
    absent net: you believe you are protected.
    """
    tree = ast.parse(source)
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            if isinstance(node.value, bool):
                continue
            found.append((node.lineno, float(node.value)))
    return found


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def check_file(path):
    """Analyzes a file. Returns (violations, exemptions_used).

    violations : list of (line, pattern)
    exemptions_used : list of (line, reason)
    """
    try:
        source = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as exc:
        return [(0, f"unreadable file ({exc})")], []

    exempt, malformed = parse_exemptions(source)
    code = strip_comments_and_docstrings(source)

    violations = [(lineno, f"invalid exemption: {problem}")
                  for lineno, problem in malformed]

    # A non-analyzable source is reported as a VIOLATION, not ignored:
    # without syntactic analysis, the measured-value check does not run at
    # all, and the file would be declared compliant without having been examined.
    try:
        literals = numeric_literals(code)
    except SyntaxError as exc:
        return sorted(violations + [(
            exc.lineno or 0,
            "code not analyzable after removing comments and docstrings "
            f"({exc.msg}). The measured-value check could NOT run "
            "on this file: declaring it compliant would be false."
        )]), sorted((lineno, reason) for lineno, reason in exempt.items())

    for lineno, value in literals:
        if value in ALLOWED_VALUES or lineno in exempt:
            continue
        for forbidden, origin in FORBIDDEN_VALUES.items():
            if abs(value - forbidden) <= VALUE_TOLERANCE:
                prefix = ("value TO VERIFY (common number, may be a false positive)"
                          if collision_prone(value) else "hardcoded measured value")
                violations.append((lineno, f"{prefix} : {value} ({origin})"))
                break

    for lineno, line in enumerate(code.splitlines(), start=1):
        if lineno in exempt:
            continue
        for pattern, label in FORBIDDEN_PATTERNS:
            match = pattern.search(line)
            if match:
                violations.append((lineno, f"{label} : {match.group(0)}"))

    used = sorted((lineno, reason) for lineno, reason in exempt.items())
    return sorted(violations), used


def main():
    parser = argparse.ArgumentParser(
        description="Genericity check: the library must contain "
                    "no trace of a particular audit case.",
    )
    parser.add_argument("target", type=Path, nargs="?", default=DEFAULT_TARGET,
                        help=f"Directory or file to check "
                             f"(default: {DEFAULT_TARGET.name}/).")
    parser.add_argument("--list-values", action="store_true",
                        help="Show the forbidden values and their origin, then stop.")
    parser.add_argument("--audit-exemptions", action="store_true",
                        help="List the exemptions in force with their reason. "
                             "To review periodically: a forgotten exemption is "
                             "a hole in the net.")
    args = parser.parse_args()

    if args.list_values:
        print(f"{len(FORBIDDEN_VALUES)} forbidden values in the library:")
        for value, origin in sorted(FORBIDDEN_VALUES.items()):
            print(f"    {value:>12}  {origin}")
        print()
        print("Legitimate however in check_efootprint_contract.py and in tmp/.")
        return 0

    target = args.target
    if not target.exists():
        # Normal case before lot 1: the library does not exist yet. This
        # is not a failure, and saying so clearly avoids believing in a breakdown.
        print(f"[info] Target missing: {target}")
        print("[info] Nothing to check. Normal as long as the library does not exist.")
        return 0

    files = sorted(target.rglob("*.py")) if target.is_dir() else [target]
    files = [f for f in files if "__pycache__" not in f.parts]

    if not files:
        print(f"[info] No Python file under {target}. Nothing to check.")
        return 0

    print("-" * 68)
    print(f"  GENERICITY — {target}")
    print(f"  {len(files)} file(s), {len(FORBIDDEN_VALUES)} forbidden values")
    print("-" * 68)
    print()

    total = 0
    total_exempt = 0
    for path in files:
        violations, exemptions = check_file(path)
        try:
            shown = path.relative_to(PROJECT_ROOT)
        except ValueError:
            shown = path

        total_exempt += len(exemptions)
        if args.audit_exemptions:
            if exemptions:
                print(f"{shown} — {len(exemptions)} exempted line(s):")
                for lineno, reason in exemptions:
                    print(f"    {shown}:{lineno}  {reason}")
            continue

        suffix = f"  ({len(exemptions)} exempted line(s))" if exemptions else ""
        if not violations:
            print(f"[OK] {shown}{suffix}")
            continue
        total += len(violations)
        print(f"[FAIL] {shown} — {len(violations)} violation(s){suffix} :")
        for lineno, reason in violations:
            print(f"    {shown}:{lineno}  {reason}")
        print()

    if args.audit_exemptions:
        print()
        print(f"{total_exempt} exempted line(s) in total.")
        print("Each is a place where the check sees nothing. Verify that the")
        print("reason still holds.")
        return 0

    print()
    if total:
        print(f"[FAIL] {total} violation(s). The target is not generic.")
        print("These values and these names must come from the DATA of the analyzed site,")
        print("not from the code. Three options, in this order of preference:")
        print("  1. take the value from the site data (the right reflex);")
        print("  2. if it is really universal, add it to ALLOWED_VALUES;")
        print("  3. if the occurrence is legitimate, exempt it with its reason:")
        print("     # genericity: ok - <reason>")
        return 1

    print("[SUCCESS] No trace of a particular audit case.")
    if total_exempt:
        print(f"({total_exempt} exempted line(s) — review them with --audit-exemptions.)")
    print("Reminder: this check catches copy-paste, NOT design")
    print("bias. Only execution on a second real site proves it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
