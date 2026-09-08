#!/usr/bin/env python3
"""
Parsing HTML + CSS statique des pages déjà auditées, pour des critères EOF
déterministes (autoplay, images adaptatives, media queries, viewport...).

Écart assumé par rapport au plan initial : le .har capturé pour ce projet ne
contient PAS les corps de réponse HTML/CSS (vérifié sur audits/octo.com :
46/311 entrées avec un body, aucune n'étant du HTML/CSS de page — capture
DevTools sans "response bodies"). Ce script refait donc un fetch HTTP direct
des MÊMES URLs de pages déjà listées dans env-data.json (aucune page
nouvelle), plus leurs feuilles de style liées — pas un nouveau périmètre
d'audit, seulement une source de donnée différente pour le même périmètre.

Le HTML est lu par html.parser (bibliothèque standard, aucune dépendance),
PAS par des expressions régulières : voir _HtmlFacts et autotest().

CHANTIER 27 — archivage pour reproductibilité. Le .har capturé ne contient pas
les corps de réponse (voir plus haut), donc ce script re-télécharge en direct ;
mais retélécharger à CHAQUE exécution casse la reproductibilité (deux passages
peuvent rendre des résultats différents si le site a changé). Chaque page/CSS
récupéré est donc archivé tel quel sous <source_dir>/pages-html/, avec un nom
de fichier déterministe (voir archive_filename()). Par défaut, une exécution
relit l'archive existante au lieu de refaire une requête réseau ; --refresh
force un nouveau téléchargement. Un futur script (hors périmètre ici) pourra
retrouver le fichier archivé à partir d'une URL en appelant archive_filename()
lui-même, sans jamais avoir à "dérivider" un nom de fichier.

Usage :
    python3 parse_html_criteria.py <source_dir>
    python3 parse_html_criteria.py <source_dir> --refresh
    python3 parse_html_criteria.py --autotest

Écrit <source_dir>/html-css-criteria.json et archive les pages/CSS récupérés
sous <source_dir>/pages-html/.
"""

import argparse
import contextlib
import hashlib
import io
import json
import re
import sys
import tempfile
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

TIMEOUT = 10
USER_AGENT = "Mozilla/5.0 (compatible; eof-audit-scan/1.0)"
MAX_CSS_PER_PAGE = 8
ARCHIVE_DIRNAME = "pages-html"


def archive_filename(url, is_css):
    """Nom de fichier d'archive déterministe pour une URL.

    Propriété essentielle, exploitée par un futur script (chantier 35) : la
    MÊME url donne TOUJOURS le même nom, et deux urls différentes (même si
    elles ne diffèrent que par la query string) donnent des noms différents.
    Le slug rend le nom lisible (déboguage), le hachage SHA1 tranche toute
    ambiguïté — y compris entre deux urls dont seule la query string diffère,
    puisque le slug seul l'ignorerait.
    """
    parsed = urlparse(url)
    slug = (parsed.netloc + parsed.path).strip("/").replace("/", "_") or "index"
    slug = slug[:80]  # évite les noms de fichier absurdement longs
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:10]
    ext = ".css" if is_css else ".html"
    return f"{slug}__{digest}{ext}"


def fetch_text(url):
    """Récupère le contenu textuel d'une URL par requête réseau directe.

    Retourne un dict avec :
    - content : str|None (contenu si succès)
    - status : "ok" | "rien_trouve" | "echec_reseau" | "echec_lecture"
    - error_detail : str|None (description de l'erreur si échec)
    """
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            try:
                content = resp.read().decode("utf-8", errors="replace")
                return {"content": content, "status": "ok", "error_detail": None}
            except Exception as exc:
                return {"content": None, "status": "echec_lecture",
                       "error_detail": f"Erreur de décodage: {type(exc).__name__}"}
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return {"content": None, "status": "rien_trouve",
                   "error_detail": f"HTTP {exc.code}"}
        return {"content": None, "status": "echec_reseau",
               "error_detail": f"HTTP {exc.code}"}
    except urllib.error.URLError as exc:
        return {"content": None, "status": "echec_reseau",
               "error_detail": f"URLError: {exc.reason}"}
    except Exception as exc:
        return {"content": None, "status": "echec_reseau",
               "error_detail": f"{type(exc).__name__}: {str(exc)}"}


def fetch_text_cached(url, source_dir, is_css, refresh=False):
    """Récupère le contenu d'une URL via l'archive locale <source_dir>/pages-html/,
    en repli sur le réseau — c'est la fonction à appeler à la place de
    fetch_text() partout où le résultat doit être archivé.

    Comportement :
    - --refresh actif : ignore toute archive existante, télécharge toujours
      en réseau.
    - Sinon, si le fichier d'archive existe et se lit correctement : le
      rendre tel quel, statut "ok", SANS requête réseau.
    - Sinon (archive absente, ou présente mais illisible/vide) : télécharger
      en réseau comme fetch_text(), puis, SEULEMENT en cas de succès, écrire
      (ou réécrire) l'archive. Choix assumé : un échec réseau ponctuel ne
      doit jamais écraser une bonne archive déjà sur disque ; seul un succès
      la remplace.
    """
    archive_dir = source_dir / ARCHIVE_DIRNAME
    archive_path = archive_dir / archive_filename(url, is_css)

    if not refresh and archive_path.exists():
        try:
            content = archive_path.read_text(encoding="utf-8")
            if not content:
                raise ValueError("fichier d'archive vide")
            return {"content": content, "status": "ok", "error_detail":
                    "lu depuis l'archive locale (pages-html/), aucune requête réseau"}
        except Exception as exc:
            print(f"  [parse_html] archive illisible pour {url} "
                  f"({archive_path.name}) : {type(exc).__name__}: {exc} "
                  f"— repli sur le réseau")
            # Pas de return ici : on tombe dans le fetch réseau ci-dessous.

    result = fetch_text(url)
    if result["status"] == "ok":
        try:
            archive_dir.mkdir(parents=True, exist_ok=True)
            archive_path.write_text(result["content"], encoding="utf-8")
        except Exception as exc:
            print(f"  [parse_html] écriture de l'archive impossible pour "
                  f"{url} : {type(exc).__name__}: {exc}")
    return result


def load_page_urls(source_dir):
    env_path = source_dir / "env-data.json"
    if not env_path.exists():
        return []
    env = json.loads(env_path.read_text(encoding="utf-8"))
    seen, urls = set(), []
    for p in env.get("pages", []):
        u = p.get("url")
        if u and u not in seen:
            seen.add(u)
            urls.append(u)
    return urls


# ---------------------------------------------------------------------------
# Règles HTML
# ---------------------------------------------------------------------------

class _HtmlFacts(HTMLParser):
    """Relève, en une passe, les faits HTML dont les critères EOF ont besoin.

    POURQUOI un parseur et pas des expressions régulières. En HTML, l'ordre
    des attributs ne veut rien dire, les guillemets sont facultatifs, la casse
    est libre, une valeur d'attribut peut contenir un chevron, et un attribut
    peut porter une entité (&amp;). Une expression régulière qui suppose une
    seule de ces formes rend un résultat FAUX sans lever d'erreur : le compte
    tombe à zéro, ce qui est indistinguable d'une absence légitime. Quatre
    défauts de ce type ont réellement vécu ici, chacun est un cas d'autotest().

    Attributs répétés : le premier gagne, comme dans un navigateur.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.has_autoplay_media = False
        self.img_count = 0
        self.img_with_srcset = 0
        self.picture_count = 0
        self.native_buttons = 0
        self.custom_role_buttons = 0
        self.viewport_content = None
        self.stylesheet_hrefs = []

    def handle_starttag(self, tag, attrs):
        noms = {nom.lower() for nom, _ in attrs}
        valeurs = {}
        for nom, valeur in attrs:
            nom = nom.lower()
            if nom not in valeurs:
                valeurs[nom] = valeur if valeur is not None else ""

        if tag in ("video", "audio"):
            # "autoplay" doit être un attribut à lui seul : ni data-autoplay,
            # ni une classe CSS qui contient le mot.
            if "autoplay" in noms:
                self.has_autoplay_media = True
        elif tag == "img":
            self.img_count += 1
            if "srcset" in noms:
                self.img_with_srcset += 1
        elif tag == "picture":
            self.picture_count += 1
        elif tag == "button":
            self.native_buttons += 1
        elif tag == "meta":
            if valeurs.get("name", "").strip().lower() == "viewport":
                if self.viewport_content is None:
                    self.viewport_content = valeurs.get("content")
        elif tag == "link":
            # rel est une liste de mots séparés par des espaces : rel="stylesheet
            # preload" est bien une feuille de style, rel="preload" non.
            if "stylesheet" in valeurs.get("rel", "").lower().split():
                href = valeurs.get("href", "").strip()
                if href:
                    self.stylesheet_hrefs.append(href)

        if valeurs.get("role", "").strip().lower() == "button":
            self.custom_role_buttons += 1


# CSS : ces deux motifs cherchent une présence dans du CSS, pas dans du HTML.
# Ni ordre d'attributs ni guillemets en jeu, une expression régulière est ici
# le bon outil.
_MEDIA_QUERY_RE = re.compile(r"@media\b", re.IGNORECASE)
_PREFERS_RE = re.compile(r"@media[^{]*prefers-(reduced-motion|color-scheme)", re.IGNORECASE)


def analyze_html(html, page_url):
    faits = _HtmlFacts()
    try:
        faits.feed(html)
        faits.close()
    except Exception as exc:
        # Lecture interrompue : les faits relevés jusque-là sont conservés,
        # mais l'échec est DIT, il ne se déguise pas en absence de donnée.
        print(f"  [parse_html] lecture HTML interrompue sur {page_url} : {exc}")

    adaptive_img_ratio = None
    if faits.img_count:
        adaptive_img_ratio = round(
            (faits.img_with_srcset + faits.picture_count) / faits.img_count, 2)

    viewport_content = faits.viewport_content
    viewport_ok = bool(viewport_content
                       and "width=device-width" in viewport_content.lower())

    stylesheet_hrefs = faits.stylesheet_hrefs[:MAX_CSS_PER_PAGE]
    return {
        "url": page_url,
        "has_autoplay_media": faits.has_autoplay_media,
        "img_count": faits.img_count,
        "adaptive_img_ratio": adaptive_img_ratio,
        "native_buttons": faits.native_buttons,
        "custom_role_buttons": faits.custom_role_buttons,
        "viewport_content": viewport_content,
        "viewport_ok": viewport_ok,
        "stylesheet_urls": [urljoin(page_url, href) for href in stylesheet_hrefs],
    }


def analyze_css(css_texts):
    media_query_count = sum(len(_MEDIA_QUERY_RE.findall(css)) for css in css_texts)
    has_prefers = any(_PREFERS_RE.search(css) for css in css_texts)
    return {"media_query_count": media_query_count, "has_prefers_reduced_or_scheme": has_prefers}


# ---------------------------------------------------------------------------
# Autotest : chaque cas est un HTML qu'un navigateur lit d'une seule façon.
# Un cas marqué "regression" est une écriture que la version à expressions
# régulières lisait FAUX, en silence. Ne pas les retirer.
# ---------------------------------------------------------------------------

_URL_TEST = "https://exemple.test/p/"
_A_CSS = "https://exemple.test/a.css"

CAS_AUTOTEST = [
    # --- feuille de style : alimente le CSS téléchargé, donc les critères 1.6 et 1.11
    ("stylesheet, ordre rel puis href",
     '<link rel="stylesheet" href="/a.css">', "stylesheet_urls", [_A_CSS], False),
    ("stylesheet, ordre INVERSE href puis rel",
     '<link href="/a.css" rel="stylesheet">', "stylesheet_urls", [_A_CSS], True),
    ("stylesheet, sans guillemets (page minifiee)",
     "<link rel=stylesheet href=/a.css>", "stylesheet_urls", [_A_CSS], True),
    ("stylesheet, href en premier et attribut intercale",
     '<link href="/a.css" type="text/css" rel="stylesheet">',
     "stylesheet_urls", [_A_CSS], True),
    ("stylesheet, entite &amp; dans l'URL",
     '<link rel="stylesheet" href="/a.css?x=1&amp;y=2">',
     "stylesheet_urls", ["https://exemple.test/a.css?x=1&y=2"], True),
    ("stylesheet, majuscules",
     '<LINK REL="STYLESHEET" HREF="/a.css">', "stylesheet_urls", [_A_CSS], False),
    ("stylesheet, balise auto-fermante",
     '<link rel="stylesheet" href="/a.css" />', "stylesheet_urls", [_A_CSS], False),
    ("stylesheet, rel a plusieurs mots",
     '<link rel="stylesheet preload" href="/a.css">', "stylesheet_urls", [_A_CSS], False),
    ("rel=preload n'est PAS une feuille de style",
     '<link rel="preload" href="/a.css">', "stylesheet_urls", [], False),
    ("aucune feuille de style",
     "<html><body>rien</body></html>", "stylesheet_urls", [], False),

    # --- autoplay : critere 1.5, provenance "collecte", donc presente comme mesure
    ("autoplay, attribut nu",
     "<video autoplay></video>", "has_autoplay_media", True, False),
    ("autoplay sur audio",
     '<audio autoplay src="a.mp3"></audio>', "has_autoplay_media", True, False),
    ("data-autoplay n'est PAS autoplay",
     '<video data-autoplay="false"></video>', "has_autoplay_media", False, True),
    ("une classe CSS nommee no-autoplay n'est PAS autoplay",
     '<video class="no-autoplay"></video>', "has_autoplay_media", False, True),
    ("autoplay apres une valeur d'attribut contenant un chevron",
     '<video title="a > b" autoplay></video>', "has_autoplay_media", True, True),
    ("video sans autoplay",
     '<video src="a.mp4"></video>', "has_autoplay_media", False, False),

    # --- role=button : critere 1.4
    ("role=button, guillemets doubles",
     '<div role="button">x</div>', "custom_role_buttons", 1, False),
    ("role=button, sans guillemets (page minifiee)",
     "<div role=button>x</div>", "custom_role_buttons", 1, True),
    ("role=button, guillemets simples",
     "<div role='button'>x</div>", "custom_role_buttons", 1, False),
    ("role=button, espaces autour du signe egal",
     '<div role = "button">x</div>', "custom_role_buttons", 1, True),
    ("role=buttonbar n'est PAS role=button",
     '<div role="buttonbar">x</div>', "custom_role_buttons", 0, False),
    ("role=button dans un commentaire ne compte pas",
     '<!-- <div role="button"> --><p>x</p>', "custom_role_buttons", 0, True),
    ("bouton natif",
     "<button>x</button>", "native_buttons", 1, False),

    # --- viewport : collecte aujourd'hui lue par aucun critere, corrigee quand meme
    ("viewport, ordre name puis content",
     '<meta name="viewport" content="width=device-width, initial-scale=1">',
     "viewport_ok", True, False),
    ("viewport, ordre INVERSE content puis name",
     '<meta content="width=device-width" name="viewport">', "viewport_ok", True, True),
    ("viewport, name sans guillemets",
     '<meta name=viewport content="width=device-width">', "viewport_ok", True, False),
    ("viewport, majuscules dans la valeur",
     '<meta name="VIEWPORT" content="WIDTH=DEVICE-WIDTH">', "viewport_ok", True, True),
    ("viewport absent",
     "<html><head></head></html>", "viewport_ok", False, False),

    # --- images adaptatives : critere 1.6
    ("img avec srcset",
     '<img src="a.png" srcset="a.png 1x">', "adaptive_img_ratio", 1.0, False),
    ("img sans srcset",
     '<img src="a.png">', "adaptive_img_ratio", 0.0, False),
    ("srcset apres une valeur d'attribut contenant un chevron",
     '<img alt="a > b" srcset="a.png 1x">', "adaptive_img_ratio", 1.0, True),
    ("aucune image",
     "<p>rien</p>", "adaptive_img_ratio", None, False),
]


# ---------------------------------------------------------------------------
# Autotest — chantier 27 : archivage sous pages-html/ pour reproductibilité.
# Chaque cas est une fonction sans argument qui rend True si elle passe. Ils
# utilisent un dossier temporaire (jamais audits/*) et monkeypatchent
# urllib.request.urlopen pour prouver l'absence — ou la présence — d'un appel
# réseau, sans jamais en faire un vrai.
# ---------------------------------------------------------------------------

class _FakeReponseReseau:
    """Réponse HTTP factice, juste assez pour le `with ... as resp: resp.read()`
    utilisé par fetch_text()."""

    def __init__(self, data: bytes):
        self._data = data

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def read(self):
        return self._data


def _reseau_interdit(*_args, **_kwargs):
    raise AssertionError("réseau appelé alors que l'archive locale existait")


def _test_nommage_meme_url_meme_nom():
    url = "https://exemple.test/a/b.css"
    return archive_filename(url, True) == archive_filename(url, True)


def _test_nommage_query_string_distingue():
    a = archive_filename("https://exemple.test/a.css?x=1", True)
    b = archive_filename("https://exemple.test/a.css?x=2", True)
    return a != b


def _test_archive_lue_sans_reseau():
    with tempfile.TemporaryDirectory() as tmp:
        source_dir = Path(tmp)
        url = "https://exemple.test/page-en-cache.html"
        archive_dir = source_dir / ARCHIVE_DIRNAME
        archive_dir.mkdir()
        nom = archive_filename(url, False)
        (archive_dir / nom).write_text("<html>depuis l'archive</html>", encoding="utf-8")

        original = urllib.request.urlopen
        urllib.request.urlopen = _reseau_interdit
        try:
            resultat = fetch_text_cached(url, source_dir, is_css=False, refresh=False)
        finally:
            urllib.request.urlopen = original

        return (resultat["status"] == "ok"
                and resultat["content"] == "<html>depuis l'archive</html>"
                and "archive locale" in (resultat["error_detail"] or ""))


def _test_refresh_force_le_reseau():
    with tempfile.TemporaryDirectory() as tmp:
        source_dir = Path(tmp)
        url = "https://exemple.test/page-a-rafraichir.html"
        archive_dir = source_dir / ARCHIVE_DIRNAME
        archive_dir.mkdir()
        nom = archive_filename(url, False)
        (archive_dir / nom).write_text("<html>ancienne version</html>", encoding="utf-8")

        appels = []

        def _reseau_ok(*_args, **_kwargs):
            appels.append(1)
            return _FakeReponseReseau(b"<html>fraiche du reseau</html>")

        original = urllib.request.urlopen
        urllib.request.urlopen = _reseau_ok
        try:
            resultat = fetch_text_cached(url, source_dir, is_css=False, refresh=True)
        finally:
            urllib.request.urlopen = original

        contenu_archive = (archive_dir / nom).read_text(encoding="utf-8")
        return (len(appels) == 1
                and resultat["content"] == "<html>fraiche du reseau</html>"
                and contenu_archive == "<html>fraiche du reseau</html>")


def _test_archive_vide_replie_sur_reseau():
    with tempfile.TemporaryDirectory() as tmp:
        source_dir = Path(tmp)
        url = "https://exemple.test/page-archive-vide.html"
        archive_dir = source_dir / ARCHIVE_DIRNAME
        archive_dir.mkdir()
        nom = archive_filename(url, False)
        (archive_dir / nom).write_text("", encoding="utf-8")  # archive vide = corrompue

        appels = []

        def _reseau_ok(*_args, **_kwargs):
            appels.append(1)
            return _FakeReponseReseau(b"<html>reparee</html>")

        original = urllib.request.urlopen
        urllib.request.urlopen = _reseau_ok
        sortie = io.StringIO()
        try:
            with contextlib.redirect_stdout(sortie):
                resultat = fetch_text_cached(url, source_dir, is_css=False, refresh=False)
        finally:
            urllib.request.urlopen = original

        message_affiche = "archive illisible" in sortie.getvalue()
        contenu_reecrit = (archive_dir / nom).read_text(encoding="utf-8")
        return (len(appels) == 1
                and resultat["status"] == "ok"
                and resultat["content"] == "<html>reparee</html>"
                and message_affiche
                and contenu_reecrit == "<html>reparee</html>")


def _test_archive_indecodable_replie_sur_reseau():
    with tempfile.TemporaryDirectory() as tmp:
        source_dir = Path(tmp)
        url = "https://exemple.test/page-archive-indecodable.html"
        archive_dir = source_dir / ARCHIVE_DIRNAME
        archive_dir.mkdir()
        nom = archive_filename(url, False)
        # Octets invalides en UTF-8 strict : provoque une UnicodeDecodeError
        # à la lecture, pas un simple contenu vide.
        (archive_dir / nom).write_bytes(b"\xff\xfe\x00garbage")

        appels = []

        def _reseau_ok(*_args, **_kwargs):
            appels.append(1)
            return _FakeReponseReseau(b"<html>reparee 2</html>")

        original = urllib.request.urlopen
        urllib.request.urlopen = _reseau_ok
        sortie = io.StringIO()
        try:
            with contextlib.redirect_stdout(sortie):
                resultat = fetch_text_cached(url, source_dir, is_css=False, refresh=False)
        finally:
            urllib.request.urlopen = original

        message_affiche = "archive illisible" in sortie.getvalue()
        return (len(appels) == 1
                and resultat["status"] == "ok"
                and resultat["content"] == "<html>reparee 2</html>"
                and message_affiche)


CAS_AUTOTEST_ARCHIVE = [
    ("nommage : la même URL donne toujours le même nom", _test_nommage_meme_url_meme_nom),
    ("nommage : une query string différente change le nom", _test_nommage_query_string_distingue),
    ("archive présente : lue sans requête réseau", _test_archive_lue_sans_reseau),
    ("--refresh : force le réseau même si l'archive existe", _test_refresh_force_le_reseau),
    ("archive vide : message + repli réseau + réécriture", _test_archive_vide_replie_sur_reseau),
    ("archive indécodable : message + repli réseau", _test_archive_indecodable_replie_sur_reseau),
]


def autotest():
    echecs = []
    corriges = 0
    for libelle, html, champ, attendu, regression in CAS_AUTOTEST:
        obtenu = analyze_html(html, _URL_TEST).get(champ)
        if obtenu != attendu:
            echecs.append((libelle, champ, attendu, obtenu))
        elif regression:
            corriges += 1

    for libelle, fonction_test in CAS_AUTOTEST_ARCHIVE:
        try:
            ok = fonction_test()
        except Exception as exc:
            ok = False
            libelle = f"{libelle} (exception : {type(exc).__name__}: {exc})"
        if not ok:
            echecs.append((libelle, "archive", True, False))

    total = len(CAS_AUTOTEST) + len(CAS_AUTOTEST_ARCHIVE)
    if echecs:
        print(f"AUTOTEST EN ÉCHEC : {len(echecs)} cas sur {total}")
        for libelle, champ, attendu, obtenu in echecs:
            print(f"  - {libelle}")
            print(f"      {champ} : attendu {attendu!r}, obtenu {obtenu!r}")
        return 1

    print(f"Autotest : {total} cas passés, dont {corriges} écritures HTML "
          f"que la version à expressions régulières lisait faux.")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Relève les faits HTML/CSS des pages auditées pour les critères EOF.")
    parser.add_argument("source_dir", nargs="?",
                        help="dossier d'audit contenant env-data.json")
    parser.add_argument("--autotest", action="store_true",
                        help="rejoue les cas de lecture HTML embarqués et sort 1 si un cas échoue")
    parser.add_argument("--refresh", action="store_true",
                        help="ignore l'archive locale pages-html/ et retélécharge tout en réseau")
    args = parser.parse_args()

    if args.autotest:
        sys.exit(autotest())
    if not args.source_dir:
        parser.error("source_dir est requis (ou utiliser --autotest)")
    source_dir = Path(args.source_dir).resolve()

    urls = load_page_urls(source_dir)
    if not urls:
        print(f"Erreur : aucune page trouvée dans {source_dir}/env-data.json.")
        sys.exit(1)

    pages_result = []
    stylesheets_failed = []
    all_css_texts = []
    for url in urls:
        fetch_result = fetch_text_cached(url, source_dir, is_css=False, refresh=args.refresh)
        if fetch_result["status"] != "ok":
            # Page non récupérée : créer une entrée avec bloc mesure
            page_entry = {
                "url": url,
                "mesure": {
                    "statut": fetch_result["status"],
                    "cible": url,
                    "detail": fetch_result["error_detail"]
                }
            }
            pages_result.append(page_entry)
            print(f"  [parse_html] échec fetch page : {url} — {fetch_result['status']}: {fetch_result['error_detail']}")
            continue

        # Page récupérée : analyser
        html = fetch_result["content"]
        page_data = analyze_html(html, url)
        # Ajouter le bloc mesure pour indiquer succès (detail précise si le
        # contenu vient de l'archive locale ou d'une requête réseau fraîche)
        page_data["mesure"] = {
            "statut": "ok",
            "cible": url,
            "detail": fetch_result["error_detail"]
        }

        # Récupérer les CSS
        for css_url in page_data["stylesheet_urls"]:
            css_result = fetch_text_cached(css_url, source_dir, is_css=True, refresh=args.refresh)
            if css_result["status"] == "ok":
                all_css_texts.append(css_result["content"])
            else:
                # CSS non récupéré : tracer l'échec
                stylesheets_failed.append({
                    "url": css_url,
                    "source_page": url,
                    "mesure": {
                        "statut": css_result["status"],
                        "cible": f"feuille de style {css_url} (liée depuis {url})",
                        "detail": css_result["error_detail"]
                    }
                })
                print(f"  [parse_html] échec fetch CSS : {css_url} — {css_result['status']}: {css_result['error_detail']}")

        pages_result.append(page_data)
        print(f"  [parse_html] {url} — autoplay={page_data['has_autoplay_media']} "
              f"adaptive_img_ratio={page_data['adaptive_img_ratio']} viewport_ok={page_data['viewport_ok']}")

    # Vérifier combien de pages ont été mesurées avec succès
    pages_ok = [p for p in pages_result if p.get("mesure", {}).get("statut") == "ok"]
    if not pages_ok:
        print("Attention : aucune page n'a pu être récupérée avec succès (réseau indisponible ?). "
              "Les entrées en échec seront tracées dans le fichier de sortie.")

    css_result = analyze_css(all_css_texts)

    result = {
        "pages": pages_result,
        "css": css_result,
        "note": "HTML/CSS re-fetchés en direct sur les mêmes URLs déjà listées dans "
                "env-data.json (le .har capturé ne contient pas les corps de réponse "
                "HTML/CSS) — pas de nouveau périmètre de pages.",
    }

    if stylesheets_failed:
        result["stylesheets_failed"] = stylesheets_failed

    out_path = source_dir / "html-css-criteria.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"html-css-criteria.json écrit : {out_path}")


if __name__ == "__main__":
    main()
