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

Usage :
    python3 parse_html_criteria.py <source_dir>
    python3 parse_html_criteria.py --autotest

Écrit <source_dir>/html-css-criteria.json.
"""

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

TIMEOUT = 10
USER_AGENT = "Mozilla/5.0 (compatible; eof-audit-scan/1.0)"
MAX_CSS_PER_PAGE = 8


def fetch_text(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception:
        return None


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


def autotest():
    echecs = []
    corriges = 0
    for libelle, html, champ, attendu, regression in CAS_AUTOTEST:
        obtenu = analyze_html(html, _URL_TEST).get(champ)
        if obtenu != attendu:
            echecs.append((libelle, champ, attendu, obtenu))
        elif regression:
            corriges += 1

    total = len(CAS_AUTOTEST)
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
    all_css_texts = []
    for url in urls:
        html = fetch_text(url)
        if html is None:
            print(f"  [parse_html] échec fetch : {url}")
            continue
        page_data = analyze_html(html, url)
        css_texts = []
        for css_url in page_data["stylesheet_urls"]:
            css = fetch_text(css_url)
            if css:
                css_texts.append(css)
        all_css_texts.extend(css_texts)
        pages_result.append(page_data)
        print(f"  [parse_html] {url} — autoplay={page_data['has_autoplay_media']} "
              f"adaptive_img_ratio={page_data['adaptive_img_ratio']} viewport_ok={page_data['viewport_ok']}")

    if not pages_result:
        print("Erreur : aucune page n'a pu être récupérée (réseau indisponible ?).")
        sys.exit(1)

    css_result = analyze_css(all_css_texts)

    result = {
        "pages": pages_result,
        "css": css_result,
        "note": "HTML/CSS re-fetchés en direct sur les mêmes URLs déjà listées dans "
                "env-data.json (le .har capturé ne contient pas les corps de réponse "
                "HTML/CSS) — pas de nouveau périmètre de pages.",
    }

    out_path = source_dir / "html-css-criteria.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"html-css-criteria.json écrit : {out_path}")


if __name__ == "__main__":
    main()
