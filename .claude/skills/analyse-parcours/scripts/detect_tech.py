#!/usr/bin/env python3
"""
Détection des technologies (stack technique) depuis un HAR — règles MAISON.

Moteur de pattern-matching pur Python (stdlib uniquement) sur les signaux déjà
présents dans le HAR : en-têtes de réponse, URLs de requêtes / hosts tiers, HTML
des pages (balise <meta name="generator">, patterns), cookies (Set-Cookie).

POURQUOI des règles maison et pas Wappalyzer/webappanalyzer ?
  La boîte à outils est publiée sous CC BY-SA 4.0, incompatible avec l'intégration
  de données GPL v3 (webappanalyzer). On écrit donc nos propres règles, 100 %
  CC BY-SA compatibles, offline, sans dépendance ni appel réseau.
  Détail complet : documentation/implementation/detection_technologies.md

Portée assumée : ~20-40 technologies courantes (CDN, serveur web, langages,
frameworks, CMS, analytics, fonts). On ne détecte QUE ce qui transparaît côté
client. Le type d'instance (t3.medium…) reste indétectable de l'extérieur.

Usage autonome (relançable seul, comme les autres modules du projet) :
    python3 detect_tech.py <source_dir>     # dossier contenant le .har
    python3 detect_tech.py <fichier.har>    # chemin direct vers un .har
"""

import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

# Sous-dossier optionnel où ranger les captures brutes (HAR, Coverage), dans .gitignore.
RAW_DATA_DIR = "donnees-brutes-potentiellement-sensibles"

# Clés de confiance (alignées sur collect_env_data.py)
CONFIDENCE_HIGH = "high"       # signal distinctif et non ambigu
CONFIDENCE_MEDIUM = "medium"   # signal probable mais partagé / indirect
CONFIDENCE_LOW = "low"         # indice faible (sous-chaîne HTML, etc.)

# Ordre d'affichage des catégories dans le rapport
CATEGORY_ORDER = [
    "CDN",
    "Hébergeur",
    "Serveur web",
    "Langage",
    "Framework",
    "CMS",
    "Analytics",
    "Balise / Tag manager",
    "Polices",
    "Bibliothèque JS",
    "Consentement / RGPD",
    "Backend-as-a-Service / BDD (tiers)",
    "Streaming média",
    "IA générative (tiers)",
]


# ---------------------------------------------------------------------------
# Règles de détection MAISON
# ---------------------------------------------------------------------------
# Format d'une règle (tous les champs sont optionnels sauf "cat") :
#   "cat"            : catégorie (une de CATEGORY_ORDER)
#   "headers"        : {nom_header_minuscule: regex} — match si la valeur du header
#                      matche la regex (au moins un header suffit)
#   "url"            : regex testée sur chaque URL de requête (host + chemin)
#   "meta_generator" : regex testée sur le contenu de <meta name="generator">
#   "html"           : regex testée sur le HTML des pages (indice faible)
#   "cookie"         : regex testée sur les noms de cookies (Set-Cookie)
#   "content_type"   : regex testée sur le mimeType de chaque réponse (utile pour
#                      le streaming média quand l'URL ne révèle rien, ex. flux
#                      servi derrière un chemin opaque) — confiance MEDIUM
#   "confidence"     : confiance de base si un signal "fort" matche (défaut medium)
#
# Un signal via "headers", "meta_generator" ou "cookie" est considéré FORT
# (confiance de la règle). Un signal via "url" est MEDIUM, via "content_type"
# est MEDIUM, via "html" est LOW.
TECH_RULES = {
    # --- CDN -----------------------------------------------------------------
    "Amazon CloudFront": {
        "cat": "CDN", "confidence": CONFIDENCE_HIGH,
        "headers": {"via": r"cloudfront", "x-amz-cf-id": r".+", "x-cache": r"cloudfront"},
    },
    "Cloudflare": {
        "cat": "CDN", "confidence": CONFIDENCE_HIGH,
        "headers": {"server": r"^cloudflare$", "cf-ray": r".+", "cf-cache-status": r".+"},
    },
    "Fastly": {
        "cat": "CDN", "confidence": CONFIDENCE_HIGH,
        "headers": {"x-served-by": r"cache-[a-z]{3}", "x-fastly-request-id": r".+"},
    },
    "Akamai": {
        "cat": "CDN", "confidence": CONFIDENCE_HIGH,
        "headers": {"x-akamai-transformed": r".+", "server": r"AkamaiGHost"},
    },
    "jsDelivr": {
        "cat": "CDN", "confidence": CONFIDENCE_HIGH,
        "url": r"cdn\.jsdelivr\.net",
    },
    "unpkg": {
        "cat": "CDN", "confidence": CONFIDENCE_MEDIUM,
        "url": r"//unpkg\.com",
    },
    "cdnjs (Cloudflare)": {
        "cat": "CDN", "confidence": CONFIDENCE_MEDIUM,
        "url": r"cdnjs\.cloudflare\.com",
    },

    # --- Hébergeur (signaux cloud) ------------------------------------------
    "Amazon S3": {
        "cat": "Hébergeur", "confidence": CONFIDENCE_HIGH,
        "headers": {"x-amz-request-id": r".+", "server": r"AmazonS3"},
    },
    "GitHub Pages": {
        "cat": "Hébergeur", "confidence": CONFIDENCE_HIGH,
        "headers": {"server": r"GitHub\.com"},
    },
    "Vercel": {
        "cat": "Hébergeur", "confidence": CONFIDENCE_HIGH,
        "headers": {"server": r"Vercel", "x-vercel-id": r".+"},
    },
    "Netlify": {
        "cat": "Hébergeur", "confidence": CONFIDENCE_HIGH,
        "headers": {"server": r"Netlify", "x-nf-request-id": r".+"},
    },

    # --- Serveur web ---------------------------------------------------------
    "nginx": {
        "cat": "Serveur web", "confidence": CONFIDENCE_HIGH,
        "headers": {"server": r"nginx"},
    },
    "Apache": {
        "cat": "Serveur web", "confidence": CONFIDENCE_HIGH,
        "headers": {"server": r"apache"},
    },
    "Microsoft IIS": {
        "cat": "Serveur web", "confidence": CONFIDENCE_HIGH,
        "headers": {"server": r"Microsoft-IIS"},
    },
    "LiteSpeed": {
        "cat": "Serveur web", "confidence": CONFIDENCE_HIGH,
        "headers": {"server": r"LiteSpeed"},
    },
    "Google Frontend": {
        "cat": "Serveur web", "confidence": CONFIDENCE_MEDIUM,
        "headers": {"server": r"^(gws|sffe|ESF|GSE)$"},
    },

    # --- Langage serveur -----------------------------------------------------
    "PHP": {
        "cat": "Langage", "confidence": CONFIDENCE_HIGH,
        "headers": {"x-powered-by": r"PHP", "set-cookie": r"^PHPSESSID="},
    },
    "ASP.NET": {
        "cat": "Langage", "confidence": CONFIDENCE_HIGH,
        "headers": {"x-powered-by": r"ASP\.NET", "x-aspnet-version": r".+"},
    },
    "Express (Node.js)": {
        "cat": "Langage", "confidence": CONFIDENCE_HIGH,
        "headers": {"x-powered-by": r"Express"},
    },
    "Ruby on Rails": {
        "cat": "Framework", "confidence": CONFIDENCE_MEDIUM,
        "headers": {"x-powered-by": r"Phusion Passenger"},
        "cookie": r"^_session_id=",
    },

    # --- Frameworks front / SSR ---------------------------------------------
    "Next.js": {
        "cat": "Framework", "confidence": CONFIDENCE_HIGH,
        "headers": {"x-powered-by": r"Next\.js"},
        "url": r"/_next/static/",
        "html": r"id=[\"']__NEXT_DATA__[\"']",
    },
    "Nuxt.js": {
        "cat": "Framework", "confidence": CONFIDENCE_MEDIUM,
        "html": r"window\.__NUXT__|id=[\"']__nuxt[\"']",
    },
    "Gatsby": {
        "cat": "Framework", "confidence": CONFIDENCE_MEDIUM,
        "html": r"id=[\"']___gatsby[\"']",
    },
    "Astro": {
        "cat": "Framework", "confidence": CONFIDENCE_MEDIUM,
        "headers": {"x-powered-by": r"Astro"},
        "html": r"<astro-island",
    },
    "React": {
        "cat": "Framework", "confidence": CONFIDENCE_MEDIUM,
        "html": r"data-reactroot|data-reactid|__REACT_DEVTOOLS",
    },
    "Vue.js": {
        "cat": "Framework", "confidence": CONFIDENCE_MEDIUM,
        "html": r"data-v-[0-9a-f]{8}|id=[\"']__vue|__VUE__",
    },

    # --- CMS -----------------------------------------------------------------
    "WordPress": {
        "cat": "CMS", "confidence": CONFIDENCE_HIGH,
        "url": r"/wp-(content|includes|json)/",
        "meta_generator": r"WordPress",
    },
    "Drupal": {
        "cat": "CMS", "confidence": CONFIDENCE_HIGH,
        "headers": {"x-generator": r"Drupal", "x-drupal-cache": r".+"},
        "meta_generator": r"Drupal",
    },
    "Joomla": {
        "cat": "CMS", "confidence": CONFIDENCE_HIGH,
        "meta_generator": r"Joomla",
    },
    "Webflow": {
        "cat": "CMS", "confidence": CONFIDENCE_HIGH,
        "meta_generator": r"Webflow",
        "html": r"data-wf-page|data-wf-site",
    },
    "Shopify": {
        "cat": "CMS", "confidence": CONFIDENCE_HIGH,
        "headers": {"x-shopify-stage": r".+"},
        "url": r"cdn\.shopify\.com",
    },

    # --- Analytics -----------------------------------------------------------
    "Google Analytics (GA4)": {
        "cat": "Analytics", "confidence": CONFIDENCE_HIGH,
        "url": r"google-analytics\.com|/gtag/js|/g/collect",
    },
    "Matomo": {
        "cat": "Analytics", "confidence": CONFIDENCE_HIGH,
        "url": r"matomo\.(js|php)|piwik\.(js|php)",
    },
    "Swetrix": {
        "cat": "Analytics", "confidence": CONFIDENCE_HIGH,
        "url": r"(//|\.)swetrix\.(org|com)|/swetrix\.js",
    },
    "Plausible": {
        "cat": "Analytics", "confidence": CONFIDENCE_HIGH,
        "url": r"plausible\.io",
    },
    "Hotjar": {
        "cat": "Analytics", "confidence": CONFIDENCE_HIGH,
        "url": r"(//|\.)hotjar\.com",
    },

    # --- Tag manager ---------------------------------------------------------
    "Google Tag Manager": {
        "cat": "Balise / Tag manager", "confidence": CONFIDENCE_HIGH,
        "url": r"googletagmanager\.com/gtm\.js",
    },

    # --- Polices -------------------------------------------------------------
    "Google Fonts": {
        "cat": "Polices", "confidence": CONFIDENCE_HIGH,
        "url": r"fonts\.(googleapis|gstatic)\.com",
    },
    "Font Awesome": {
        "cat": "Polices", "confidence": CONFIDENCE_MEDIUM,
        "url": r"fontawesome|font-awesome",
    },

    # --- Bibliothèques JS ----------------------------------------------------
    "jQuery": {
        "cat": "Bibliothèque JS", "confidence": CONFIDENCE_MEDIUM,
        "url": r"/jquery[.-]",
    },

    # --- Consentement / RGPD -------------------------------------------------
    "Orejime (RGPD)": {
        "cat": "Consentement / RGPD", "confidence": CONFIDENCE_MEDIUM,
        "url": r"/orejime[.-]",
    },
    "Axeptio": {
        "cat": "Consentement / RGPD", "confidence": CONFIDENCE_HIGH,
        "url": r"axeptio\.(eu|imgix\.net)",
    },
    "Didomi": {
        "cat": "Consentement / RGPD", "confidence": CONFIDENCE_HIGH,
        "url": r"(//|\.)didomi\.io",
    },

    # --- Backend-as-a-Service / BDD (tiers) -----------------------------------
    # SEUL signal HAR honnête pour une "base de données" : un BaaS/DBaaS exposé
    # DIRECTEMENT au navigateur. Une BDD auto-hébergée derrière un serveur
    # applicatif n'émet AUCUN signal réseau visible côté client — son absence
    # ici ne prouve jamais son absence réelle (cf. topology_overview.py).
    "Firebase / Firestore": {
        "cat": "Backend-as-a-Service / BDD (tiers)", "confidence": CONFIDENCE_HIGH,
        "url": r"(firebaseio\.com|firestore\.googleapis\.com)",
    },
    "Supabase": {
        "cat": "Backend-as-a-Service / BDD (tiers)", "confidence": CONFIDENCE_HIGH,
        "url": r"\.supabase\.co",
    },
    "MongoDB Atlas (Data API)": {
        "cat": "Backend-as-a-Service / BDD (tiers)", "confidence": CONFIDENCE_MEDIUM,
        "url": r"data\.mongodb-api\.com",
    },
    "Airtable (API)": {
        "cat": "Backend-as-a-Service / BDD (tiers)", "confidence": CONFIDENCE_MEDIUM,
        "url": r"api\.airtable\.com",
    },

    # --- Streaming média -------------------------------------------------------
    # Deux vecteurs : URL/extension (m3u8/mpd, CDN vidéo connus) et content-type
    # de réponse (clé "content_type", cf. _match_rule() — utile quand l'URL ne
    # révèle rien, ex. flux servi derrière un chemin opaque).
    "Flux HLS (.m3u8)": {
        "cat": "Streaming média", "confidence": CONFIDENCE_MEDIUM,
        "url": r"\.m3u8(\?|$)",
        "content_type": r"application/(vnd\.apple\.mpegurl|x-mpegurl)",
    },
    "Flux DASH (.mpd)": {
        "cat": "Streaming média", "confidence": CONFIDENCE_MEDIUM,
        "url": r"\.mpd(\?|$)",
        "content_type": r"application/dash\+xml",
    },
    "Ressource vidéo/audio (content-type)": {
        "cat": "Streaming média", "confidence": CONFIDENCE_LOW,
        "content_type": r"^(video|audio)/",
    },
    "Mux (streaming vidéo)": {
        "cat": "Streaming média", "confidence": CONFIDENCE_HIGH,
        "url": r"(//|\.)(stream\.mux\.com|mux\.com)",
    },
    "Cloudflare Stream": {
        "cat": "Streaming média", "confidence": CONFIDENCE_HIGH,
        "url": r"(//|\.)cloudflarestream\.com|videodelivery\.net",
    },

    # --- IA générative (tiers) --------------------------------------------------
    # Domaine d'API exact reconnu = signal quasi certain, mais _match_rule()
    # plafonne tout match "url" à MEDIUM (cohérence avec les autres règles
    # url-only du fichier) : la nuance "quasi certain" se porte dans le texte
    # de présentation (topology_overview.py), pas dans ce badge générique.
    "OpenAI (API)": {
        "cat": "IA générative (tiers)", "confidence": CONFIDENCE_HIGH,
        "url": r"(//|\.)api\.openai\.com",
    },
    "Anthropic (API Claude)": {
        "cat": "IA générative (tiers)", "confidence": CONFIDENCE_HIGH,
        "url": r"(//|\.)api\.anthropic\.com",
    },
    "Google Generative AI (Gemini)": {
        "cat": "IA générative (tiers)", "confidence": CONFIDENCE_HIGH,
        "url": r"generativelanguage\.googleapis\.com",
    },
    "Mistral AI (API)": {
        "cat": "IA générative (tiers)", "confidence": CONFIDENCE_HIGH,
        "url": r"(//|\.)api\.mistral\.ai",
    },
    "Cohere (API)": {
        "cat": "IA générative (tiers)", "confidence": CONFIDENCE_HIGH,
        "url": r"(//|\.)api\.cohere\.(ai|com)",
    },
    "Azure OpenAI": {
        "cat": "IA générative (tiers)", "confidence": CONFIDENCE_MEDIUM,
        "url": r"openai\.azure\.com",
    },
    "Hugging Face Inference API": {
        "cat": "IA générative (tiers)", "confidence": CONFIDENCE_MEDIUM,
        "url": r"api-inference\.huggingface\.co",
    },
}


# ---------------------------------------------------------------------------
# Extraction des signaux depuis le HAR
# ---------------------------------------------------------------------------

def find_har(source_dir):
    """Trouve le .har dans un dossier (même logique que collect_env_data.find_har)."""
    source_dir = Path(source_dir)
    hars = list(source_dir.glob("*.har")) or list(
        (source_dir / RAW_DATA_DIR).glob("*.har"))
    if len(hars) >= 1:
        return hars[0]
    return None


def load_har_signals(har_path):
    """
    Parcourt les entries du HAR et agrège tous les signaux exploitables.

    Réutilise la même logique de parsing que collect_env_data.extract_har_data()
    (json.load puis itération sur log["entries"]).

    Retourne un dict :
      - "headers"        : liste de (nom_minuscule, valeur) de tous les response headers
      - "urls"           : liste des URLs de requêtes (host + chemin)
      - "hosts"          : ensemble des hosts distincts
      - "main_host"      : host le plus fréquent (domaine principal présumé)
      - "third_party"    : hosts distincts != main_host
      - "meta_generators": valeurs des <meta name="generator"> trouvées dans le HTML
      - "html_blobs"     : liste des corps HTML (pour patterns "html")
      - "cookies"        : noms de cookies vus (Set-Cookie)
      - "content_types"  : liste de (host, mimeType) de chaque réponse — le host
                           est indispensable pour router une détection "content_type"
                           vers le bon ThirdPartyHost (cf. topology_overview.py)
      - "request_count"  : nombre d'entries
    """
    with open(har_path, encoding="utf-8") as f:
        har = json.load(f)

    entries = har.get("log", {}).get("entries", [])

    headers = []
    urls = []
    host_counts = {}
    meta_generators = []
    html_blobs = []
    cookies = set()
    content_types = []

    meta_gen_re = re.compile(
        r'<meta[^>]+name=["\']generator["\'][^>]+content=["\']([^"\']+)["\']',
        re.IGNORECASE,
    )

    for e in entries:
        url = e.get("request", {}).get("url", "")
        netloc = ""
        if url:
            urls.append(url)
            netloc = urlparse(url).netloc
            if netloc:
                host_counts[netloc] = host_counts.get(netloc, 0) + 1

        resp = e.get("response", {})
        for h in resp.get("headers", []):
            name = h.get("name", "").lower()
            value = h.get("value", "")
            headers.append((name, value))
            if name == "set-cookie" and value:
                cookies.add(value.split("=", 1)[0].strip())

        content = resp.get("content", {})
        mime = content.get("mimeType", "")
        if mime:
            content_types.append((netloc, mime))
        text = content.get("text", "")
        if text and "html" in mime:
            html_blobs.append(text)
            for m in meta_gen_re.findall(text):
                meta_generators.append(m)

    main_host = max(host_counts, key=host_counts.get) if host_counts else ""
    third_party = {h for h in host_counts if h != main_host}

    return {
        "headers": headers,
        "urls": urls,
        "hosts": set(host_counts),
        "main_host": main_host,
        "third_party": sorted(third_party),
        "meta_generators": meta_generators,
        "html_blobs": html_blobs,
        "cookies": sorted(cookies),
        "content_types": content_types,
        "request_count": len(entries),
    }


# ---------------------------------------------------------------------------
# Application des règles
# ---------------------------------------------------------------------------

def _match_rule(name, rule, signals):
    """
    Teste une règle contre les signaux. Retourne (confidence, evidence) si match,
    sinon (None, None).

    La confiance retenue est la plus forte des signaux ayant matché :
      - headers / meta_generator / cookie -> confiance de base de la règle
      - url                               -> plafonnée à MEDIUM
      - html                              -> plafonnée à LOW
    """
    base_conf = rule.get("confidence", CONFIDENCE_MEDIUM)
    best = None  # tuple (rang, conf, evidence)
    rank = {CONFIDENCE_HIGH: 3, CONFIDENCE_MEDIUM: 2, CONFIDENCE_LOW: 1}

    def _consider(conf, evidence):
        nonlocal best
        if best is None or rank[conf] > best[0]:
            best = (rank[conf], conf, evidence)

    # 1. Headers (signal fort)
    for hdr_name, pattern in rule.get("headers", {}).items():
        rx = re.compile(pattern, re.IGNORECASE)
        for name_h, value_h in signals["headers"]:
            if name_h == hdr_name and rx.search(value_h):
                _consider(base_conf, f'header {hdr_name}: "{value_h[:60]}"')
                break

    # 2. meta generator (signal fort)
    if "meta_generator" in rule:
        rx = re.compile(rule["meta_generator"], re.IGNORECASE)
        for gen in signals["meta_generators"]:
            if rx.search(gen):
                _consider(base_conf, f'<meta generator> = "{gen[:60]}"')
                break

    # 3. cookie (signal fort)
    if "cookie" in rule:
        rx = re.compile(rule["cookie"], re.IGNORECASE)
        for ck in signals["cookies"]:
            if rx.search(ck):
                _consider(base_conf, f'cookie "{ck}"')
                break

    # 4. URL (plafonné MEDIUM)
    if "url" in rule:
        rx = re.compile(rule["url"], re.IGNORECASE)
        for u in signals["urls"]:
            if rx.search(u):
                conf = base_conf if rank[base_conf] < rank[CONFIDENCE_MEDIUM] else CONFIDENCE_MEDIUM
                # Un host tiers dédié est un signal fiable ; on garde MEDIUM par prudence.
                short = urlparse(u).netloc + urlparse(u).path
                _consider(conf, f'requête {short[:60]}')
                break

    # 4bis. content-type de réponse (plafonné MEDIUM : un mimeType vidéo/audio
    # est un fait sur LA RESSOURCE, pas sur le SITE — une page peut charger
    # une seule vidéo promo sans être un site de streaming).
    if "content_type" in rule:
        rx = re.compile(rule["content_type"], re.IGNORECASE)
        for host_ct, ct in signals["content_types"]:
            if rx.search(ct):
                _consider(CONFIDENCE_MEDIUM, f'content-type "{ct[:40]}" chez {host_ct}')
                break

    # 5. HTML (plafonné LOW — sous-chaîne, sujette aux faux positifs)
    if "html" in rule:
        rx = re.compile(rule["html"], re.IGNORECASE)
        for blob in signals["html_blobs"]:
            if rx.search(blob):
                _consider(CONFIDENCE_LOW, "motif dans le HTML")
                break

    if best is None:
        return None, None
    return best[1], best[2]


def detect(signals, rules=None):
    """
    Applique les règles aux signaux. Retourne un dict :
      {
        "technologies": [{"name", "category", "confidence", "evidence"}, ...],
        "categories": {cat: [names]},
        "third_party_hosts": [...],
        "request_count": int,
      }
    """
    rules = rules or TECH_RULES
    technologies = []
    for name, rule in rules.items():
        conf, evidence = _match_rule(name, rule, signals)
        if conf:
            technologies.append({
                "name": name,
                "category": rule["cat"],
                "confidence": conf,
                "evidence": evidence,
            })

    # Tri : par ordre de catégorie puis confiance décroissante puis nom
    conf_rank = {CONFIDENCE_HIGH: 3, CONFIDENCE_MEDIUM: 2, CONFIDENCE_LOW: 1}

    def _cat_index(cat):
        return CATEGORY_ORDER.index(cat) if cat in CATEGORY_ORDER else len(CATEGORY_ORDER)

    technologies.sort(key=lambda t: (_cat_index(t["category"]),
                                     -conf_rank[t["confidence"]],
                                     t["name"]))

    categories = {}
    for t in technologies:
        categories.setdefault(t["category"], []).append(t["name"])

    return {
        "technologies": technologies,
        "categories": categories,
        "third_party_hosts": signals["third_party"],
        "request_count": signals["request_count"],
    }


def detect_from_har(har_path):
    """Point d'entrée programmatique : HAR -> résultat de détection (dict) ou None."""
    if not har_path or not Path(har_path).exists():
        return None
    signals = load_har_signals(har_path)
    return detect(signals)


# ---------------------------------------------------------------------------
# IA générative tierce : détection PAR HOST (pas par catégorie agrégée)
# ---------------------------------------------------------------------------
# detect()/detect_from_har() ci-dessus servent la présentation (Étape 25,
# topology_overview.py) : ils agrègent par catégorie et ne portent pas le host
# exact. efootprint_model/from_har.py a besoin, lui, du host exact pour savoir
# À QUEL job réseau rattacher un calcul EcoLogits (cf. collect_env_data.py qui
# appelle la fonction ci-dessous et écrit son résultat dans
# env-data.json::ai_external_apis). Réutilise les mêmes règles "url" de
# TECH_RULES, jamais une redécouverte de pattern.

AI_PROVIDER_BY_RULE_NAME = {
    # Nom de règle (TECH_RULES) -> clé provider du catalogue EcoLogits
    # (efootprint_model/build.py::_build_external_api). Azure OpenAI route vers
    # les mêmes modèles qu'OpenAI : même catalogue EcoLogits, pas un provider
    # distinct.
    "OpenAI (API)": "openai",
    "Anthropic (API Claude)": "anthropic",
    "Google Generative AI (Gemini)": "google_genai",
    "Mistral AI (API)": "mistralai",
    "Cohere (API)": "cohere",
    "Azure OpenAI": "openai",
    "Hugging Face Inference API": "huggingface_hub",
}


def ai_generative_hosts_from_har(har_path):
    """Hosts appelant une IA générative tierce, détectés par domaine exact.

    Retourne {host: {"rule_name": ..., "provider": clé_ecologits}}, un host par
    domaine d'API vu dans le HAR (pas d'agrégation par catégorie). None si le
    HAR est absent/illisible.
    """
    if not har_path or not Path(har_path).exists():
        return None
    signals = load_har_signals(har_path)
    rules = {name: rule for name, rule in TECH_RULES.items()
             if rule["cat"] == "IA générative (tiers)"}

    result = {}
    for url in signals["urls"]:
        host = urlparse(url).netloc
        if not host or host in result:
            continue
        for name, rule in rules.items():
            rx = re.compile(rule["url"], re.IGNORECASE)
            if rx.search(url):
                provider = AI_PROVIDER_BY_RULE_NAME.get(name)
                if provider:
                    result[host] = {"rule_name": name, "provider": provider}
                break
    return result


# ---------------------------------------------------------------------------
# Point d'entrée autonome
# ---------------------------------------------------------------------------

def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        print(__doc__)
        return 1

    target = Path(argv[0])
    if target.is_dir():
        har_path = find_har(target)
        if not har_path:
            print(f"[ERREUR] Aucun .har trouvé dans {target}")
            return 1
    elif target.suffix == ".har" and target.exists():
        har_path = target
    else:
        print(f"[ERREUR] Cible invalide : {target} (attendu : dossier ou fichier .har)")
        return 1

    print(f"[HAR] {har_path.name}")
    result = detect_from_har(har_path)
    if not result:
        print("[ERREUR] HAR illisible")
        return 1

    print(f"[HAR] {result['request_count']} requêtes, "
          f"{len(result['third_party_hosts'])} host(s) tiers\n")

    if not result["technologies"]:
        print("Aucune technologie détectée par les règles maison.")
        return 0

    print(f"Technologies détectées ({len(result['technologies'])}) :")
    current_cat = None
    for t in result["technologies"]:
        if t["category"] != current_cat:
            current_cat = t["category"]
            print(f"\n  {current_cat}")
        print(f"    - {t['name']:<28} [{t['confidence']:<6}] {t['evidence']}")

    if result["third_party_hosts"]:
        print("\nHosts tiers :")
        for h in result["third_party_hosts"]:
            print(f"    - {h}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
