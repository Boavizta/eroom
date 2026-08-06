#!/usr/bin/env python3
"""
Contrôles de coverage_metrics.py — le défaut corrigé reste-t-il corrigé ?

Le défaut : l'extension était testée sur l'URL entière. Une URL versionnée
(dsfr.min.css?version=39.2.0) ne se termine pas par son extension, elle tombait
en "autre", et une page dont TOUTES les URLs sont versionnées était publiée à
zéro Ko de JS et de CSS. Le zéro ne ressemble pas à une erreur : il ressemble à
une page sans code. C'est pourquoi ce contrôle existe.

Usage :
  python3 check_coverage_metrics.py [-v]
"""

import argparse
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from coverage_metrics import (          # noqa: E402
    aggregate, analyse, classify, detect_libraries, measure, page_label, read_entries,
)

_checks = []


def check(label):
    def deco(fn):
        _checks.append((label, fn))
        return fn
    return deco


def _entry(url, text, used=0):
    """Une entrée Coverage : `used` octets utilisés à partir du début."""
    return {"url": url, "text": "x" * text,
            "ranges": ([{"start": 0, "end": used}] if used else [])}


# ── Le défaut corrigé ─────────────────────────────────────────────────────────

@check("une URL versionnée reste du CSS")
def _():
    assert classify("https://h/a/dsfr.min.css?version=39.2.0") == "css"


@check("une URL versionnée reste du JS")
def _():
    assert classify("https://h/a/jquery-ui.min.js?version=39.2.0") == "javascript"


@check("un fragment ne masque pas l'extension")
def _():
    assert classify("https://h/app.js#module") == "javascript"


@check("plusieurs paramètres ne masquent pas l'extension")
def _():
    assert classify("https://h/s.css?v=1&theme=dark&x=.js") == "css"


@check("une redirection VERS un .css n'est pas du CSS")
def _():
    # Cas négatif : sans lui, un test trop permissif passerait aussi.
    assert classify("https://h/redirect?target=/style.css") == "other"


@check("une URL sans extension n'est ni JS ni CSS")
def _():
    assert classify("https://h/ihm-spd/csrfguard.action") == "other"


@check("une page entièrement versionnée n'est PAS publiée à zéro")
def _():
    entries = [_entry("https://h/a/dsfr.min.css?version=39.2.0", 4096, 1024),
               _entry("https://h/a/dsfr.module.min.js?version=39.2.0", 2048, 512)]
    res = measure(entries)
    assert aggregate(res, "css")["total_kb"] == 4.0
    assert aggregate(res, "javascript")["total_kb"] == 2.0


@check("le calcul naïf, lui, publierait bien zéro (le défaut est réel)")
def _():
    urls = ["https://h/a/dsfr.min.css?version=39.2.0",
            "https://h/a/dsfr.module.min.js?version=39.2.0"]
    assert not any(u.endswith((".css", ".js")) for u in urls)


# ── Mesure ────────────────────────────────────────────────────────────────────

@check("les octets non utilisés valent total moins utilisé")
def _():
    res = measure([_entry("https://h/a.js", 1000, 400)])
    assert res[0]["unused_bytes"] == 600


@check("une ressource sans plage utilisée est comptée 100 % non utilisée")
def _():
    res = measure([_entry("https://h/a.js", 1000)])
    assert res[0]["unused_bytes"] == 1000
    assert aggregate(res, "javascript")["unused_pct"] == 100.0


@check("un type absent donne zéro, pas une division par zéro")
def _():
    assert aggregate(measure([_entry("https://h/a.js", 10)]), "css") == {
        "total_kb": 0.0, "unused_kb": 0.0, "unused_pct": 0.0}


@check("les plages incomplètes sont ignorées sans planter")
def _():
    res = measure([{"url": "https://h/a.js", "text": "x" * 100,
                    "ranges": [{"start": 0}, {"end": 50}, {"start": 0, "end": 10}]}])
    assert res[0]["unused_bytes"] == 90


# ── Libellé de page ───────────────────────────────────────────────────────────

@check("le HAR tranche entre deux URLs sans extension")
def _():
    entries = [_entry("https://h/ihm-spd/csrfguard.action?version=1", 10),
               _entry("https://h/ihm-spd/pages/premotifdemandeform.action", 10)]
    url, prov = page_label(entries, {"https://h/ihm-spd/pages/premotifdemandeform.action"})
    assert url.endswith("premotifdemandeform.action"), url
    assert "HAR" in prov


@check("sans HAR, le libellé est marqué non corroboré")
def _():
    entries = [_entry("https://h/ihm-spd/csrfguard.action", 10)]
    url, prov = page_label(entries, set())
    assert url.endswith("csrfguard.action")
    assert "non confirmée" in prov


@check("aucune URL de page identifiable est dit, pas inventé")
def _():
    url, prov = page_label([_entry("https://h/a.js", 10)], set())
    assert url == ""
    assert "aucune" in prov.lower()


@check("un tiers majoritaire ne devient pas le domaine de la page")
def _():
    # Le domaine principal est celui qui porte le plus de ressources.
    entries = [_entry("https://cdn.tiers/a.js", 10), _entry("https://cdn.tiers/b.js", 10),
               _entry("https://cdn.tiers/c.js", 10), _entry("https://site/page", 10)]
    url, _ = page_label(entries, set())
    assert url == "", url  # aucune URL de page sur le domaine majoritaire


# ── Formats et refus ──────────────────────────────────────────────────────────

@check("le format tableau direct est lu")
def _():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "c.json"
        p.write_text(json.dumps([_entry("https://h/a.js", 10)]), encoding="utf-8")
        assert len(read_entries(p)) == 1


@check("le format enveloppé est lu")
def _():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "c.json"
        p.write_text(json.dumps({"entries": [_entry("https://h/a.js", 10)]}), encoding="utf-8")
        assert len(read_entries(p)) == 1


@check("un format inconnu est REFUSÉ, pas lu comme vide")
def _():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "c.json"
        p.write_text(json.dumps({"coverage": []}), encoding="utf-8")
        try:
            read_entries(p)
        except ValueError as e:
            assert "entries" in str(e)
            return
        raise AssertionError("un format inconnu a été accepté")


@check("un dossier sans Coverage est REFUSÉ, pas rendu vide")
def _():
    with tempfile.TemporaryDirectory() as d:
        try:
            analyse(d)
        except FileNotFoundError:
            return
        raise AssertionError("un dossier sans Coverage a produit un résultat")


@check("une page non vide sans JS ni CSS est SIGNALÉE")
def _():
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "Coverage-1.json").write_text(
            json.dumps([_entry("https://h/data.bin", 4096)]), encoding="utf-8")
        res = analyse(d)
        assert res["pages"][0]["no_js_no_css"] is True


@check("une page normale n'est pas signalée à tort")
def _():
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "Coverage-1.json").write_text(
            json.dumps([_entry("https://h/a.css?v=2", 4096, 1024)]), encoding="utf-8")
        res = analyse(d)
        assert res["pages"][0]["no_js_no_css"] is False


# ── Bibliothèques ─────────────────────────────────────────────────────────────

@check("une bibliothèque est nommée avec son rôle")
def _():
    libs = detect_libraries([{"url": "https://swetrix.org/swetrix.js"}])
    assert libs == ["Swetrix (analytics)"], libs


@check("le DSFR versionné est reconnu")
def _():
    libs = detect_libraries([{"url": "https://h/assets/dsfr/dsfr.min.css?version=39.2.0"}])
    assert any("DSFR" in x for x in libs), libs


@check("aucune bibliothèque connue donne une liste vide, pas une invention")
def _():
    assert detect_libraries([{"url": "https://h/assets/maison.js"}]) == []


# ── Sortie ────────────────────────────────────────────────────────────────────

@check("la sortie porte les clés attendues par le rapport")
def _():
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "Coverage-1.json").write_text(
            json.dumps([_entry("https://h/a.js?v=1", 2048, 512)]), encoding="utf-8")
        res = analyse(d)
        for k in ("total_js_kb", "total_js_unused_kb", "total_css_kb",
                  "total_css_unused_kb", "third_party_libraries", "outlier_pages",
                  "pages_count"):
            assert k in res["summary"], k
        for k in ("name", "url", "url_provenance", "js_total_kb", "css_total_kb",
                  "top_js_unused", "top_css_unused", "source_file"):
            assert k in res["pages"][0], k


@check("le total est la somme des pages, aucun octet perdu")
def _():
    with tempfile.TemporaryDirectory() as d:
        for i in (1, 2):
            (Path(d) / f"Coverage-{i}.json").write_text(
                json.dumps([_entry(f"https://h/a{i}.js?v=1", 1024 * i, 256)]),
                encoding="utf-8")
        res = analyse(d)
        assert abs(res["summary"]["total_js_kb"]
                   - sum(p["js_total_kb"] for p in res["pages"])) < 0.11


@check("chaque page nomme son fichier source")
def _():
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "Coverage-abc.json").write_text(
            json.dumps([_entry("https://h/a.js", 10)]), encoding="utf-8")
        assert analyse(d)["pages"][0]["source_file"] == "Coverage-abc.json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    failures = []
    for label, fn in _checks:
        try:
            fn()
        except Exception as e:
            failures.append((label, e))
            print(f"[ÉCHEC] {label}\n         {type(e).__name__}: {e}")
        else:
            if args.verbose:
                print(f"[ok] {label}")

    print("-" * 68)
    if failures:
        print(f"[ÉCHEC] {len(failures)}/{len(_checks)} contrôle(s) en échec.")
        return 1
    print(f"[SUCCÈS] {len(_checks)} contrôles. Le typage des URL versionnées tient.")
    print()
    print("Rappel de portée : ces contrôles portent sur le CLASSEMENT et le")
    print("LIBELLÉ, pas sur la justesse des octets rapportés par Chrome.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
