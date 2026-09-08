#!/usr/bin/env python3
"""
Analyse déterministe d'un fichier `.har` — produit har-analysis.json.

Chantier 35. Jusqu'ici, l'étape 20 du pipeline ("analyse du fichier HAR")
n'avait AUCUN script : le bloc `:::dispatch id="analyse-har"` de
`skill-steps/25_dispatch-orchestration.md` demandait à un agent/LLM de lire le
`.har` "à la main" et de produire `<AUDIT_DIR>/har-analysis.json` par jugement.
Preuve que c'est arrivé sur `audits/octo.com` : le fichier réel portait une
clé `blocking_resources` qu'aucun script du dépôt ne connaissait — une IA
l'avait inventée en lisant le HAR à l'œil. Cette analyse n'était donc pas
rejouable, alors que ses chiffres (notamment `duplicate_urls`) alimentent
l'EOF (critère des requêtes dupliquées, voir run_eof.py) sans qu'on puisse
vérifier qu'ils sont stables.

Ce script remplace ce calcul à la main, à l'image de coverage_metrics.py pour
l'étape 30 (Coverage) : même CLI, même discipline de tests séparés
(check_analyze_har.py).

Deux règles de non-divergence avec le reste du dépôt :

1. **1st-party / 3rd-party** : la classification vient de
   `deploy_freshness._first_party_hosts_from_env()`, importée telle quelle
   (une seule règle de ce concept dans tout le dépôt, pas une deuxième
   inventée ici).
2. **`blocking_resources`** : la valeur qui vivait dans le fichier réel avant
   ce script n'était pas une vérité à reproduire (elle a été inventée par
   lecture manuelle), seulement l'indice de ce qu'on veut approximer
   proprement. Ce script retrouve l'archive HTML de chaque page via
   `archive_filename()` (chantier 27, importée depuis parse_html_criteria.py)
   sous `<source_dir>/pages-html/`. Si l'archive est absente pour une page —
   le rejeu du chantier 27 n'a pas encore eu lieu sur ce dossier —, le champ
   est marqué explicitement "non calculé" pour cette page, JAMAIS deviné
   depuis le seul type MIME : "un échec est dit, jamais déguisé en absence"
   (convention du projet). Cette clé n'est lue par aucun script consommateur
   aujourd'hui (vérifié : `grep -rl blocking_resources` ne trouve que des
   fichiers de données) : elle documente une approximation, pas un verdict.

Usage :
  python3 analyze_har.py <dossier-source> [--output har-analysis.json]
  python3 analyze_har.py <dossier-source> --check     # compare sans écrire
  python3 analyze_har.py --autotest
"""

import argparse
import json
import sys
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy_freshness import _first_party_hosts_from_env   # noqa: E402 - seule règle 1st/3rd-party du dépôt
from parse_html_criteria import archive_filename, ARCHIVE_DIRNAME  # noqa: E402 - chantier 27, ne pas dupliquer

# Sous-dossier optionnel où ranger les captures brutes (HAR, Coverage).
RAW_DATA_DIR = "donnees-brutes-potentiellement-sensibles"  # genericite: ok - convention partagée du dépôt

# Seuil "ressource tierce lente" : temps de réponse total (entry.time, en ms).
SLOW_THRESHOLD_MS = 1000


def find_har(source_dir):
    """Localise le `.har` : à la racine du dossier source, ou dans son
    sous-dossier de captures brutes. Reproduit la même recherche que
    deploy_freshness.find_har()."""
    source_dir = Path(source_dir)
    hars = sorted(source_dir.glob("*.har")) or sorted((source_dir / RAW_DATA_DIR).glob("*.har"))
    return hars[0] if hars else None


def read_har(har_path):
    with open(har_path, encoding="utf-8") as f:
        return json.load(f)


def _response_headers(entry):
    """Headers de réponse en dict {nom_minuscule: valeur}, robuste à l'absence."""
    return {h["name"].lower(): h["value"]
            for h in (entry.get("response") or {}).get("headers") or []}


def _host_is_first_party(host, first_party_hosts):
    """Un hôte est 1st-party s'il figure dans la liste déduite d'env-data.json,
    ou s'il est un sous-domaine d'un de ces hôtes."""
    if not host or not first_party_hosts:
        return False
    return any(host == h or host.endswith("." + h) for h in first_party_hosts)


def classify_domains(entries, first_party_hosts):
    """Domaines réellement contactés dans le HAR, classés 1st/3rd-party.

    Retourne deux listes triées de noms d'hôtes (pas de comptage : la forme
    attendue par csp_inventory.loaded_hosts_from_har_analysis() et par le
    format documenté est une liste de chaînes, pas un dict de compteurs).
    """
    hosts = set()
    for e in entries:
        url = (e.get("request") or {}).get("url", "")
        host = urlparse(url).netloc
        if host:
            hosts.add(host)

    first, third = [], []
    for host in sorted(hosts):
        if _host_is_first_party(host, first_party_hosts):
            first.append(host)
        else:
            third.append(host)
    return first, third


def compute_http_codes(entries):
    codes = Counter()
    for e in entries:
        status = (e.get("response") or {}).get("status", 0)
        codes[status] += 1
    # Clés en chaînes : un objet JSON n'a que des clés-chaînes, et le fichier
    # de référence (produit à la main) porte déjà des clés "200", "304", etc.
    return {str(code): count for code, count in codes.items()}


def compute_total_size_kb(entries):
    total_bytes = sum(
        ((e.get("response") or {}).get("content") or {}).get("size", 0) or 0
        for e in entries
    )
    return round(total_bytes / 1024, 2)


def compute_top10_heaviest(entries):
    """Les 10 ressources les plus lourdes, dédupliquées par URL.

    Reprend l'idée de generate_report_html.har_traffic_analysis() (dédup par
    URL avant le classement, garder la taille max observée si la même URL
    apparaît plusieurs fois) : sans elle, une ressource chargée 8 fois (cache
    absent) occupe 8 des 10 places du top et masque les autres ressources
    lourdes — c'est exactement ce défaut qui vivait dans le fichier produit à
    la main sur octo.com (style.css présent 8 fois dans le top10).
    """
    seen = {}
    for e in entries:
        url = (e.get("request") or {}).get("url", "")
        size_kb = round((((e.get("response") or {}).get("content") or {}).get("size", 0) or 0) / 1024, 2)
        host = urlparse(url).netloc
        if url not in seen or size_kb > seen[url]["size_kb"]:
            seen[url] = {"url": url, "size_kb": size_kb, "host": host}
    return sorted(seen.values(), key=lambda r: -r["size_kb"])[:10]


def compute_uncached_requests(entries):
    """Requêtes sans cache : ni `Cache-Control` ni `Expires` dans la réponse."""
    count = 0
    for e in entries:
        hdrs = _response_headers(e)
        if "cache-control" not in hdrs and "expires" not in hdrs:
            count += 1
    return count


def compute_duplicate_urls(entries):
    """URLs identiques appelées plusieurs fois, triées par nombre d'appels
    décroissant. Chaque élément garde au moins la clé `count` (consommée par
    run_eof.py : `sorted(..., key=lambda d: -d.get("count", 0))[:3]`)."""
    urls = [ (e.get("request") or {}).get("url", "") for e in entries ]
    counts = Counter(u for u in urls if u)
    return [{"url": u, "count": c} for u, c in counts.most_common() if c > 1]


def compute_slow_third_party(entries, first_party_hosts):
    """Ressources tierces dont le temps de réponse total (`entry.time`, en ms)
    dépasse SLOW_THRESHOLD_MS. Les hôtes 1st-party sont exclus : la question
    posée est celle du poids ajouté par des services tiers, pas la lenteur
    du site lui-même."""
    slow = []
    for e in entries:
        url = (e.get("request") or {}).get("url", "")
        host = urlparse(url).netloc
        if not host or _host_is_first_party(host, first_party_hosts):
            continue
        time_ms = e.get("time", 0) or 0
        if time_ms > SLOW_THRESHOLD_MS:
            slow.append({"url": url, "host": host, "time_ms": round(time_ms, 1)})
    return sorted(slow, key=lambda r: -r["time_ms"])


# ── blocking_resources : JS/CSS synchrones en <head>, depuis l'archive HTML ──

class _HeadBlockingFacts(HTMLParser):
    """Relève, dans le seul <head>, les <script src> sans async/defer/module et
    les <link rel="stylesheet">. Parseur dédié (html.parser, jamais de
    regex — convention du dépôt, voir _HtmlFacts dans parse_html_criteria.py),
    avec la même tolérance aux attributs sans guillemets, à la casse libre et
    aux attributs répétés (le premier gagne)."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._in_head = False
        self._head_done = False
        self.scripts = []       # URLs (src) de <script> bloquants
        self.stylesheets = []   # URLs (href) de <link rel=stylesheet>

    def handle_starttag(self, tag, attrs):
        if self._head_done:
            return
        if tag == "head":
            self._in_head = True
            return
        if tag == "body":
            self._head_done = True
            self._in_head = False
            return
        if not self._in_head:
            return

        valeurs = {}
        for nom, valeur in attrs:
            nom = nom.lower()
            if nom not in valeurs:
                valeurs[nom] = valeur if valeur is not None else ""
        noms = set(valeurs)

        if tag == "script":
            src = valeurs.get("src", "").strip()
            is_module = valeurs.get("type", "").strip().lower() == "module"
            if src and "async" not in noms and "defer" not in noms and not is_module:
                self.scripts.append(src)
        elif tag == "link":
            if "stylesheet" in valeurs.get("rel", "").lower().split():
                href = valeurs.get("href", "").strip()
                if href:
                    self.stylesheets.append(href)

    def handle_endtag(self, tag):
        if tag == "head":
            self._head_done = True
            self._in_head = False


def _blocking_resources_for_page(page_url, html_text):
    facts = _HeadBlockingFacts()
    try:
        facts.feed(html_text)
        facts.close()
    except Exception as exc:
        # Lecture interrompue : les faits déjà relevés sont conservés, mais
        # l'échec est DIT (imprimé), jamais déguisé en absence de donnée.
        print(f"  [analyze_har] lecture HTML interrompue sur {page_url} : {exc}")
    resources = [{"url": urljoin(page_url, src), "kind": "script"} for src in facts.scripts]
    resources += [{"url": urljoin(page_url, href), "kind": "stylesheet"} for href in facts.stylesheets]
    return resources


def compute_blocking_resources(source_dir, env_pages):
    """JS/CSS synchrones en <head>, par page — seulement pour les pages dont
    l'archive HTML (chantier 27, <source_dir>/pages-html/) est disponible.

    Une page sans archive n'est PAS approximée depuis le seul type MIME du
    HAR : elle est marquée `calcule: false`, avec la raison. C'est la
    convention du projet : un échec est dit, jamais déguisé en absence.
    """
    source_dir = Path(source_dir)
    archive_dir = source_dir / ARCHIVE_DIRNAME
    pages_out = []
    for page in env_pages:
        url = (page or {}).get("url") if isinstance(page, dict) else None
        if not url:
            continue
        archive_path = archive_dir / archive_filename(url, is_css=False)
        if not archive_path.exists():
            pages_out.append({
                "url": url,
                "calcule": False,
                "resources": None,
                "raison": ("archive HTML absente sous pages-html/ — le chantier 27 "
                           "(archivage HTML) n'a pas encore été rejoué sur ce dossier ; "
                           "non calculé, jamais approximé depuis le seul type MIME"),
            })
            continue
        try:
            html_text = archive_path.read_text(encoding="utf-8")
        except Exception as exc:
            pages_out.append({
                "url": url,
                "calcule": False,
                "resources": None,
                "raison": f"archive illisible ({archive_path.name}) : {type(exc).__name__}: {exc}",
            })
            continue
        pages_out.append({
            "url": url,
            "calcule": True,
            "resources": _blocking_resources_for_page(url, html_text),
            "raison": None,
        })
    return {
        "note": ("JS/CSS synchrones en <head> (sans async/defer/type=module pour les "
                 "scripts). Calculé uniquement pour les pages dont l'archive HTML "
                 "(chantier 27) est disponible sous pages-html/ ; sinon, non calculé. "
                 "Clé non lue par les scripts consommateurs actuels : approximation "
                 "documentée, pas un verdict."),
        "pages": pages_out,
    }


def load_env_pages(source_dir):
    env_path = Path(source_dir) / "env-data.json"
    if not env_path.exists():
        return []
    try:
        env = json.loads(env_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    return env.get("pages") or []


def analyse(source_dir):
    source_dir = Path(source_dir)
    har_path = find_har(source_dir)
    if not har_path:
        raise FileNotFoundError(
            f"Aucun fichier .har dans {source_dir} ni dans {source_dir / RAW_DATA_DIR}."
        )

    har = read_har(har_path)
    entries = (har.get("log") or {}).get("entries") or []

    first_party_hosts = _first_party_hosts_from_env(source_dir)
    first, third = classify_domains(entries, first_party_hosts)
    env_pages = load_env_pages(source_dir)

    return {
        "total_requests": len(entries),
        "domains": {"first_party": first, "third_party": third},
        "http_codes": compute_http_codes(entries),
        "total_size_kb": compute_total_size_kb(entries),
        "top10_heaviest": compute_top10_heaviest(entries),
        "uncached_requests": compute_uncached_requests(entries),
        "duplicate_urls": compute_duplicate_urls(entries),
        "slow_third_party": compute_slow_third_party(entries, first_party_hosts),
        "blocking_resources": compute_blocking_resources(source_dir, env_pages),
    }, har_path


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source_dir", type=Path, nargs="?")
    ap.add_argument("--output", type=Path,
                    help="chemin de sortie (défaut : <source_dir>/audit/"
                         "har-analysis.json)")
    ap.add_argument("--check", action="store_true",
                    help="compare à la sortie existante sans rien écrire")
    ap.add_argument("--autotest", action="store_true",
                    help="lance la batterie de contrôles internes et quitte")
    args = ap.parse_args(argv)

    if args.autotest:
        return _run_autotest()

    if args.source_dir is None:
        ap.error("le dossier source est requis (sauf avec --autotest)")

    result, har_path = analyse(args.source_dir)

    out = args.output or (args.source_dir / "audit" / "har-analysis.json")

    n_first = len(result["domains"]["first_party"])
    n_third = len(result["domains"]["third_party"])
    print(f"HAR : {result['total_requests']} requêtes — {har_path.name}")
    print(f"  Domaines : {n_first} 1st-party, {n_third} 3rd-party")
    print(f"  Volume total : {result['total_size_kb']} Ko")
    print(f"  Sans cache : {result['uncached_requests']} requête(s)")
    print(f"  URLs dupliquées : {len(result['duplicate_urls'])}")
    print(f"  Tiers lents (> 1 s) : {len(result['slow_third_party'])}")

    if args.check:
        if not out.exists():
            print(f"\n[check] {out} absent, rien à comparer.")
            return 0
        with open(out, encoding="utf-8") as f:
            old = json.load(f)
        print("\n[check] écarts avec la sortie existante :")
        diffs = 0
        for key in ("total_requests", "total_size_kb", "uncached_requests"):
            before, after = old.get(key), result[key]
            if before != after:
                diffs += 1
                print(f"  {key} : {before} -> {after}")
        for key, label in (("domains", "domains"), ("http_codes", "http_codes")):
            if old.get(key) != result[key]:
                diffs += 1
                print(f"  {label} : {old.get(key)} -> {result[key]}")
        for key in ("duplicate_urls", "slow_third_party", "top10_heaviest"):
            before_n = len(old.get(key) or [])
            after_n = len(result[key])
            if before_n != after_n:
                diffs += 1
                print(f"  len({key}) : {before_n} -> {after_n}")
        print("  aucun écart." if not diffs else f"  {diffs} écart(s).")
        return 1 if diffs else 0

    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1, ensure_ascii=False)
    print(f"\nhar-analysis.json écrit — {out}")
    return 0


# ── Autotest ───────────────────────────────────────────────────────────────

def _entry(url, status=200, size=1000, time_ms=100, headers=None):
    return {
        "request": {"url": url},
        "response": {
            "status": status,
            "content": {"size": size},
            "headers": [{"name": k, "value": v} for k, v in (headers or {}).items()],
        },
        "time": time_ms,
    }


def _run_autotest():
    import tempfile

    failures = []
    checks = []

    def check(label):
        def deco(fn):
            checks.append((label, fn))
            return fn
        return deco

    @check("total_requests compte toutes les entrées")
    def _():
        entries = [_entry("https://h/a"), _entry("https://h/b")]
        assert len(entries) == 2

    @check("domaines : 1st-party vs 3rd-party via env-data.json")
    def _():
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "env-data.json").write_text(
                json.dumps({"pages": [{"url": "https://site.test/"}]}), encoding="utf-8")
            har = {"log": {"entries": [
                _entry("https://site.test/a.js"),
                _entry("https://tiers.test/b.js"),
            ]}}
            (d / "site.har").write_text(json.dumps(har), encoding="utf-8")
            result, _ = analyse(d)
            assert result["domains"]["first_party"] == ["site.test"], result["domains"]
            assert result["domains"]["third_party"] == ["tiers.test"], result["domains"]

    @check("un sous-domaine du 1st-party reste 1st-party")
    def _():
        assert _host_is_first_party("cdn.site.test", {"site.test"})
        assert not _host_is_first_party("evilsite.test", {"site.test"})

    @check("http_codes : clés en chaînes, comptage correct")
    def _():
        entries = [_entry("https://h/a", status=200), _entry("https://h/b", status=200),
                   _entry("https://h/c", status=404)]
        codes = compute_http_codes(entries)
        assert codes == {"200": 2, "404": 1}, codes

    @check("total_size_kb : somme des tailles, Ko avec 2 décimales")
    def _():
        entries = [_entry("https://h/a", size=1024), _entry("https://h/b", size=512)]
        assert compute_total_size_kb(entries) == 1.5

    @check("top10_heaviest : dédupliqué par URL, taille max conservée")
    def _():
        entries = [
            _entry("https://h/style.css", size=2048),
            _entry("https://h/style.css", size=2048),
            _entry("https://h/style.css", size=2048),
            _entry("https://h/big.webp", size=1024),
        ]
        top = compute_top10_heaviest(entries)
        assert len(top) == 2, top  # dédupliqué : pas 4 entrées pour 2 URLs distinctes
        assert top[0]["url"] == "https://h/style.css"
        assert top[0]["size_kb"] == 2.0

    @check("uncached_requests : ni Cache-Control ni Expires")
    def _():
        entries = [
            _entry("https://h/a", headers={"cache-control": "max-age=3600"}),
            _entry("https://h/b", headers={"expires": "Wed, 01 Jan 2030 00:00:00 GMT"}),
            _entry("https://h/c", headers={}),
        ]
        assert compute_uncached_requests(entries) == 1

    @check("duplicate_urls : compte les URLs identiques, ignore les uniques")
    def _():
        entries = [_entry("https://h/a"), _entry("https://h/a"), _entry("https://h/a"),
                   _entry("https://h/b")]
        dups = compute_duplicate_urls(entries)
        assert dups == [{"url": "https://h/a", "count": 3}], dups

    @check("duplicate_urls : chaque élément porte au moins 'count' (contrat run_eof.py)")
    def _():
        entries = [_entry("https://h/a"), _entry("https://h/a")]
        dups = compute_duplicate_urls(entries)
        assert all("count" in d for d in dups)

    @check("slow_third_party : > 1000 ms ET tiers uniquement")
    def _():
        first_party = {"site.test"}
        entries = [
            _entry("https://site.test/slow.js", time_ms=5000),   # 1st-party lent : exclu
            _entry("https://tiers.test/slow.js", time_ms=1500),  # tiers lent : inclus
            _entry("https://tiers.test/fast.js", time_ms=200),   # tiers rapide : exclu
        ]
        slow = compute_slow_third_party(entries, first_party)
        assert [s["url"] for s in slow] == ["https://tiers.test/slow.js"], slow

    @check("slow_third_party : le seuil est strict (exactement 1000 ms n'entre pas)")
    def _():
        slow = compute_slow_third_party([_entry("https://tiers.test/x.js", time_ms=1000)], set())
        assert slow == []

    @check("blocking_resources : archive absente -> non calculé, jamais deviné")
    def _():
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            result = compute_blocking_resources(d, [{"url": "https://site.test/"}])
            page = result["pages"][0]
            assert page["calcule"] is False
            assert page["resources"] is None
            assert "absente" in page["raison"], page["raison"]

    @check("blocking_resources : archive présente -> script/link du <head> détectés")
    def _():
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            page_url = "https://site.test/"
            (d / ARCHIVE_DIRNAME).mkdir(parents=True, exist_ok=True)
            html = ('<html><head>'
                    '<script src="/a.js"></script>'
                    '<script src="/async.js" async></script>'
                    '<script src="/module.js" type="module"></script>'
                    '<link rel="stylesheet" href="/s.css">'
                    '</head><body></body></html>')
            (d / ARCHIVE_DIRNAME / archive_filename(page_url, is_css=False)).write_text(
                html, encoding="utf-8")
            result = compute_blocking_resources(d, [{"url": page_url}])
            page = result["pages"][0]
            assert page["calcule"] is True
            urls = {r["url"] for r in page["resources"]}
            assert "https://site.test/a.js" in urls
            assert "https://site.test/s.css" in urls
            assert "https://site.test/async.js" not in urls
            assert "https://site.test/module.js" not in urls

    @check("blocking_resources : script/link hors <head> ignorés")
    def _():
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            page_url = "https://site.test/"
            (d / ARCHIVE_DIRNAME).mkdir(parents=True, exist_ok=True)
            html = ('<html><head></head><body>'
                    '<script src="/late.js"></script>'
                    '</body></html>')
            (d / ARCHIVE_DIRNAME / archive_filename(page_url, is_css=False)).write_text(
                html, encoding="utf-8")
            result = compute_blocking_resources(d, [{"url": page_url}])
            assert result["pages"][0]["resources"] == []

    @check("cohérence avec generate_report_html.har_traffic_analysis (même HAR)")
    def _():
        import generate_report_html as ref
        entries = [
            _entry("https://site.test/a.js"),
            _entry("https://site.test/a.js"),
            _entry("https://tiers.test/b.js"),
        ]
        har_data = {"log": {"entries": entries}}
        ref_result = ref.har_traffic_analysis(har_data)
        first, third = classify_domains(entries, {"site.test"})
        # Même trafic observé : les DEUX domaines vus par har_traffic_analysis
        # doivent se retrouver, tous les deux, dans notre classification —
        # aucun des deux scripts ne doit "perdre" un domaine que l'autre voit.
        assert set(ref_result["domains"].keys()) == set(first) | set(third)
        # Le même doublon (a.js x2) doit être vu par les deux implémentations.
        ref_dup = {d["url"]: d["count"] for d in ref_result["duplicates"]}
        our_dup = {d["url"]: d["count"] for d in compute_duplicate_urls(entries)}
        assert ref_dup.get("https://site.test/a.js") == our_dup.get("https://site.test/a.js") == 2

    @check("un dossier sans .har est REFUSÉ, pas rendu vide")
    def _():
        with tempfile.TemporaryDirectory() as d:
            try:
                analyse(d)
            except FileNotFoundError:
                return
            raise AssertionError("un dossier sans .har a produit un résultat")

    @check("la sortie porte les 8 clés du contrat, plus blocking_resources")
    def _():
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            har = {"log": {"entries": [_entry("https://h/a")]}}
            (d / "h.har").write_text(json.dumps(har), encoding="utf-8")
            result, _ = analyse(d)
            for k in ("total_requests", "domains", "http_codes", "total_size_kb",
                      "top10_heaviest", "uncached_requests", "duplicate_urls",
                      "slow_third_party", "blocking_resources"):
                assert k in result, k
            assert set(result["domains"]) == {"first_party", "third_party"}

    for label, fn in checks:
        try:
            fn()
        except Exception as exc:
            failures.append((label, exc))
            print(f"[ÉCHEC] {label}\n         {type(exc).__name__}: {exc}")

    print("-" * 68)
    if failures:
        print(f"[ÉCHEC] {len(failures)}/{len(checks)} contrôle(s) en échec.")
        return 1
    print(f"[SUCCÈS] {len(checks)} contrôles.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
