#!/usr/bin/env python3
"""
Extraction of public environmental-impact tracking declarations from the
HTML pages archived in audits/<domain>/public-pages/.

Produces public-pages-criteria.json, consumed by run_eof.py to build a
contextual index at criterion 3.2 (never an automatically checked answer).

Critical constraint: distinguish "I found nothing because it is absent" from
"I found nothing because extraction failed" — the two must produce DIFFERENT
and recognizable outputs. A silent failure fabricates a false figure.

Usage:
    python3 parse_public_pages.py <source_dir>
    python3 parse_public_pages.py --autotest

Writes <source_dir>/public-pages-criteria.json.
"""

import argparse
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

# File-name patterns to look for (without extension), in priority order.
# Generic: no site-specific name.
PAGE_NAME_PATTERNS = [
    "eco-conception",
    "ecoconception",
    "numérique-responsable",
    "numerique-responsable",
    "rse-numerique",
    "declaration-environnementale",
    "empreinte-environnementale",
]

# Search keywords for impact tracking/measurement declarations.
# Case-insensitive search.
KEYWORDS_SUIVI = [
    "système de suivi",
    "systeme de suivi",
    "mesure de l'impact environnemental",
    "mesure de l impact environnemental",
    "suivi de l'impact",
    "suivi de l impact",
    "surveillance des émissions",
    "surveillance des emissions",
    "consommation d'énergie",
    "consommation d energie",
    "empreinte carbone",
    "empreinte environnementale",
    "mesure de la consommation",
]

# Search keywords for retention/deletion/archiving/right-to-erasure
# declarations. Case-insensitive search. No overlap with KEYWORDS_SUIVI
# (checked by hand).
KEYWORDS_RETENTION = [
    "durée de conservation",
    "duration de conservation",
    "droit à l'effacement",
    "droit a l effacement",
    "politique de suppression",
    "politique d'archivage",
    "politique d archivage",
    "suppression des données",
    "suppression des donnees",
    "conservation des données",
    "conservation des donnees",
    "droit à l'oubli",
    "droit a l oubli",
    "durée de rétention",
    "duration de retention",
    "période de rétention",
    "periode de retention",
    "purge des données",
    "purge des donnees",
    "archivage des données",
    "archivage des donnees",
]


class _PagePubliqueParser(HTMLParser):
    """Extracts the visible text from an HTML page.

    Judges nothing, infers nothing: extracts only the visible textual
    content, preserving the original case.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text_fragments = []
        self.in_script_or_style = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.in_script_or_style = True

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.in_script_or_style = False

    def handle_data(self, data):
        if not self.in_script_or_style:
            self.text_fragments.append(data)

    def get_text(self):
        """Returns the visible text of the page, original case preserved."""
        return " ".join(self.text_fragments)


def split_into_sentences(text):
    """Splits a text into sentences, preserving the original case.

    Returns a list of complete sentences (with their final punctuation).
    """
    # Normalize multiple spaces
    text = re.sub(r'\s+', ' ', text).strip()

    # Split on . ! ? followed by a space and an uppercase letter, or at the end of the text
    # Use a lookahead to not consume the start of the next sentence
    sentences = re.split(r'([.!?])\s+(?=[A-Z])', text)

    result = []
    i = 0
    while i < len(sentences):
        sentence = sentences[i].strip()
        if not sentence:
            i += 1
            continue

        # Append the separator if it exists
        if i + 1 < len(sentences) and sentences[i + 1] in '.!?':
            sentence += sentences[i + 1]
            i += 2
        else:
            # Last fragment, may have no punctuation
            if not sentence[-1] in '.!?':
                sentence += '.'
            i += 1

        result.append(sentence)

    return result


def extract_declarations(html_text):
    """Extracts the public declarations from an HTML: environmental-impact
    tracking, and data retention/deletion/archiving.

    Returns a dict with:
    - tracking_declarations: list[dict] with full sentence, original case
    - retention_declarations: list[dict] with full sentence, original case
    - parse_success: bool (True if the HTML parsing succeeded)
    - parse_error: str|None (error message on failure)
    """
    result = {
        "tracking_declarations": [],
        "retention_declarations": [],
        "parse_success": False,
        "parse_error": None,
    }

    parser = _PagePubliqueParser()
    try:
        parser.feed(html_text)
        parser.close()
        result["parse_success"] = True
    except Exception as exc:
        result["parse_error"] = str(exc)
        return result

    text = parser.get_text()
    sentences = split_into_sentences(text)

    # Search for tracking/measurement and retention declarations — a single
    # pass over the already-split sentences, extracting the whole sentence
    seen_monitoring = set()
    seen_retention = set()
    for sentence in sentences:
        sentence_lower = sentence.lower()

        for keyword in KEYWORDS_SUIVI:
            if keyword in sentence_lower:
                # Whole sentence, original case, never cut in the middle of a word
                if sentence not in seen_monitoring:
                    result["tracking_declarations"].append({
                        "phrase": sentence,
                        "keyword_found": keyword,
                    })
                    seen_monitoring.add(sentence)
                break  # One match per sentence

        for keyword in KEYWORDS_RETENTION:
            if keyword in sentence_lower:
                if sentence not in seen_retention:
                    result["retention_declarations"].append({
                        "phrase": sentence,
                        "keyword_found": keyword,
                    })
                    seen_retention.add(sentence)
                break

    return result


def find_page_files(public_pages_dir):
    """Looks for the public-page HTML files.

    Returns a dict:
    - found: list[Path] of found files
    - searched_patterns: list[str] of searched patterns
    """
    if not public_pages_dir.exists():
        return {"found": [], "searched_patterns": PAGE_NAME_PATTERNS}

    found = []
    for pattern in PAGE_NAME_PATTERNS:
        path = public_pages_dir / f"{pattern}.html"
        if path.exists():
            found.append(path)

    return {"found": found, "searched_patterns": PAGE_NAME_PATTERNS}


def analyze_public_pages(source_dir):
    """Analyzes the public-pages/ folder of an audit.

    Returns a dict with:
    - status: "success" | "no_directory" | "no_files" | "partial_success" | "all_failed"
    - public_pages_dir_exists: bool
    - files_searched: list[str] searched patterns
    - files_found: list[str] found paths
    - files_analyzed: list[dict] per-file results, each with its own
      "measurement" block (status/target/detail, measurement-state convention)
    - measurement: top-level block ONLY in the "no_directory"/"no_files" cases
      (nothing_found: the probe did look at the expected location and really
      found nothing there — it is not a failure of our tool).
    """
    public_pages_dir = source_dir / "public-pages"
    result = {
        "public_pages_dir_exists": public_pages_dir.exists(),
        "files_searched": PAGE_NAME_PATTERNS,
        "files_found": [],
        "files_analyzed": [],
    }

    target_dir = str(public_pages_dir.relative_to(source_dir))

    if not public_pages_dir.exists():
        result["status"] = "no_directory"
        result["measurement"] = {
            "status": "not_found",
            "target": target_dir,
            "detail": "public-pages/ folder absent from this audit",
        }
        return result

    search_result = find_page_files(public_pages_dir)
    result["files_found"] = [str(p.name) for p in search_result["found"]]

    if not search_result["found"]:
        result["status"] = "no_files"
        result["measurement"] = {
            "status": "not_found",
            "target": target_dir,
            "detail": f"no file among the searched patterns: {', '.join(PAGE_NAME_PATTERNS)}",
        }
        return result

    # Analyze each found file
    any_success = False
    any_failure = False
    for path in search_result["found"]:
        target_file = str(path.relative_to(source_dir))
        file_result = {
            "filename": path.name,
            "read_success": False,
            "read_error": None,
            "declarations": None,
        }

        try:
            html_content = path.read_text(encoding="utf-8")
            file_result["read_success"] = True
            decl = extract_declarations(html_content)
            file_result["declarations"] = decl
            if decl["parse_success"]:
                any_success = True
                file_result["measurement"] = {"status": "ok", "target": target_file, "detail": None}
            else:
                any_failure = True
                file_result["measurement"] = {
                    "status": "analysis_error",
                    "target": target_file,
                    "detail": decl.get("parse_error") or "HTML parsing failed without a message",
                }
        except Exception as exc:
            file_result["read_error"] = str(exc)
            any_failure = True
            file_result["measurement"] = {
                "status": "read_error",
                "target": target_file,
                "detail": str(exc),
            }

        result["files_analyzed"].append(file_result)

    if any_success and not any_failure:
        result["status"] = "success"
    elif any_success and any_failure:
        result["status"] = "partial_success"
    else:
        result["status"] = "all_failed"

    return result


# ---------------------------------------------------------------------------
# Autotest: each case covers a different HTML construct or a failure
# scenario. A case marked "regression" is a situation the tool must
# distinguish so as not to fabricate a false positive.
# ---------------------------------------------------------------------------

_AUTOTEST_CASES = [
    # --- Tracking declarations ---
    ("explicit tracking declaration",
     "<p>Nous avons mis en place un système de suivi de l'impact environnemental.</p>",
     lambda r: len(r["declarations"]["tracking_declarations"]) == 1 and
              r["declarations"]["tracking_declarations"][0]["phrase"].startswith("Nous avons"),
     False),

    ("consumption measurement",
     "<div>Le système permet de connaître la mesure de la consommation de chaque page.</div>",
     lambda r: len(r["declarations"]["tracking_declarations"]) >= 1,
     False),

    ("full sentence, never cut in the middle of a word",
     "<p>Réduire l'empreinte environnementale de notre site internet en diminuant la consommation d'énergie nécessaire à son fonctionnement.</p>",
     lambda r: (len(r["declarations"]["tracking_declarations"]) == 1 and
               r["declarations"]["tracking_declarations"][0]["phrase"].startswith("Réduire") and
               "empreinte environnementale" in r["declarations"]["tracking_declarations"][0]["phrase"] and
               not r["declarations"]["tracking_declarations"][0]["phrase"].startswith("ntale")),
     True),

    ("original case preserved",
     "<p>Nous avons fixé plusieurs Objectifs pour Réduire l'Empreinte Carbone.</p>",
     lambda r: (len(r["declarations"]["tracking_declarations"]) >= 1 and
               "Objectifs" in r["declarations"]["tracking_declarations"][0]["phrase"] and
               "Empreinte Carbone" in r["declarations"]["tracking_declarations"][0]["phrase"]),
     False),

    ("keyword in an attribute does not count",
     '<img alt="système de suivi" src="x.png"><p>Aucune déclaration réelle.</p>',
     lambda r: len(r["declarations"]["tracking_declarations"]) == 0,
     True),

    ("keyword in a comment does not count",
     '<!-- système de suivi --><p>Aucune déclaration réelle.</p>',
     lambda r: len(r["declarations"]["tracking_declarations"]) == 0,
     True),

    ("empty text",
     "<html><body></body></html>",
     lambda r: len(r["declarations"]["tracking_declarations"]) == 0 and
              r["declarations"]["parse_success"],
     False),

    # --- HTML robustness ---
    ("HTML with entities",
     "<p>Système de suivi de l&amp;apos;impact environnemental.</p>",
     lambda r: len(r["declarations"]["tracking_declarations"]) >= 1,
     False),

    ("malformed HTML (unclosed tag)",
     "<p>système de suivi<div>suite",
     lambda r: r["declarations"]["parse_success"] or r["declarations"]["parse_error"] is not None,
     False),

    ("uppercase text",
     "<P>SYSTÈME DE SUIVI DE L'IMPACT ENVIRONNEMENTAL</P>",
     lambda r: len(r["declarations"]["tracking_declarations"]) >= 1,
     False),

    ("multiple spaces",
     "<p>système   de    suivi    de  l'impact</p>",
     lambda r: len(r["declarations"]["tracking_declarations"]) >= 1,
     False),

    # --- Retention/deletion/archiving declarations (work item 37) ---
    ("explicit retention declaration",
     "<p>Nous avons fixé une durée de conservation des données limitée à 24 mois.</p>",
     lambda r: len(r["declarations"]["retention_declarations"]) == 1 and
              r["declarations"]["retention_declarations"][0]["phrase"].startswith("Nous avons"),
     False),

    ("right to erasure",
     "<p>Vous disposez d'un droit à l'effacement de vos données à tout moment.</p>",
     lambda r: len(r["declarations"]["retention_declarations"]) >= 1,
     False),

    ("tracking and retention distinguished in the same page",
     "<p>Nous avons mis en place un système de suivi de l'impact environnemental.</p>"
     "<p>Notre politique de suppression des données est appliquée chaque année.</p>",
     lambda r: len(r["declarations"]["tracking_declarations"]) == 1 and
              len(r["declarations"]["retention_declarations"]) == 1,
     False),

    ("no retention declaration",
     "<p>Nous mesurons notre empreinte carbone chaque trimestre.</p>",
     lambda r: len(r["declarations"]["retention_declarations"]) == 0,
     False),

    ("retention keyword in an attribute does not count",
     '<img alt="durée de conservation" src="x.png"><p>Aucune déclaration réelle.</p>',
     lambda r: len(r["declarations"]["retention_declarations"]) == 0,
     True),
]


def autotest():
    """Replays the embedded test cases."""
    failures = []
    fixed_count = 0

    for label, html, check, regression in _AUTOTEST_CASES:
        try:
            result = {
                "filename": "test.html",
                "read_success": True,
                "read_error": None,
                "declarations": extract_declarations(html),
            }

            if not check(result):
                failures.append((label, "Assertion failed", result))
            elif regression:
                fixed_count += 1
        except Exception as exc:
            failures.append((label, f"Exception: {exc}", None))

    total = len(_AUTOTEST_CASES)
    if failures:
        print(f"AUTOTEST FAILED: {len(failures)} of {total} cases")
        for label, error, result in failures:
            print(f"  - {label}")
            print(f"      {error}")
            if result:
                print(f"      Result obtained: {json.dumps(result['declarations'], ensure_ascii=False, indent=2)}")
        return 1

    print(f"Autotest: {total} cases passed, including {fixed_count} situations "
          f"the tool must distinguish (false positives avoided).")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Extracts public environmental-impact tracking declarations from public-pages/")
    parser.add_argument("source_dir", nargs="?",
                        help="audit folder containing public-pages/")
    parser.add_argument("--autotest", action="store_true",
                        help="replays the embedded test cases and exits 1 if a case fails")
    args = parser.parse_args()

    if args.autotest:
        sys.exit(autotest())
    if not args.source_dir:
        parser.error("source_dir is required (or use --autotest)")

    source_dir = Path(args.source_dir).resolve()
    result = analyze_public_pages(source_dir)

    out_path = source_dir / "public-pages-criteria.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"public-pages-criteria.json written: {out_path}")
    print(f"Status: {result['status']}")
    if result["status"] == "no_directory":
        print(f"  The public-pages/ folder does not exist in {source_dir}")
    elif result["status"] == "no_files":
        print(f"  No file found among the patterns: {', '.join(result['files_searched'])}")
    elif result["files_analyzed"]:
        for file_entry in result["files_analyzed"]:
            if file_entry["read_success"] and file_entry["declarations"]["parse_success"]:
                n_monitoring = len(file_entry["declarations"]["tracking_declarations"])
                print(f"  {file_entry['filename']} : {n_monitoring} impact tracking declaration(s) detected")
            elif not file_entry["read_success"]:
                print(f"  {file_entry['filename']} : read failure ({file_entry['read_error']})")
            else:
                print(f"  {file_entry['filename']} : parsing failure ({file_entry['declarations']['parse_error']})")


if __name__ == "__main__":
    main()
