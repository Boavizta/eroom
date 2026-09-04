#!/usr/bin/env python3
"""
Phase 2 - Collecte des données environnementales pour e-footprint.

Collecte automatiquement les données nécessaires à l'estimation CO2e :
  - HAR        : poids de page, durée requête, IP serveur principale
  - CrUX API   : répartition mobile/desktop/tablet (mix Device + Network)
  - ipinfo.io  : pays + provider hébergeur depuis l'IP du serveur

Stocke le résultat dans env-data.json à côté du HAR.
Ce fichier est le point d'entrée pour la Phase 3 (boucle interactive e-footprint).

Usage :
    python3 collect_env_data.py <source_dir>          # Lit le .har dans source_dir
    python3 collect_env_data.py <source_dir> --refresh  # Recollecte même si env-data.json existe
    python3 collect_env_data.py <source_dir> --check    # Vérifie les clés API sans analyser

Lit depuis .env à la racine du projet :
    GOOGLE_API_KEY  (optionnel — dégradé si absent)
    IPINFO_TOKEN    (optionnel — dégradé si absent)
"""

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# Module frère (même dossier) : récupération trafic + mix pays via l'API interne
# SimilarWeb. Import guardé pour que collect_env_data.py reste utilisable même si
# le module est absent (on retombe alors sur la saisie assistée / le défaut).
try:
    import similarweb_api
except ImportError:
    similarweb_api = None

# Module frère (même dossier) : détection des technologies (stack) par règles
# maison sur le HAR. Import guardé (le reste fonctionne si le module est absent).
try:
    import detect_tech
except ImportError:
    detect_tech = None

# efootprint_model/ n'importe jamais e-footprint dans from_har.py (garde-fou
# vérifié par check_efootprint_spec.py) : cet import reste donc sans risque
# même si la librairie e-footprint n'est pas installée. Import guardé quand
# même, par cohérence avec les autres modules frères.
try:
    from efootprint_model.from_har import detect_infrastructures
except ImportError:
    detect_infrastructures = None


CRUX_API = "https://chromeuxreport.googleapis.com/v1/records:queryRecord"
IPINFO_API = "https://ipinfo.io/{ip}/json"

# Sous-dossier optionnel où ranger les captures brutes (HAR, Coverage). Il est dans
# .gitignore : un HAR de parcours authentifié peut contenir des identifiants ou des
# jetons de session. Les fichiers y sont cherchés en repli, si rien à plat.
RAW_DATA_DIR = "donnees-brutes-potentiellement-sensibles"

# Clés de confiance pour le JSON de sortie
CONFIDENCE_HIGH = "high"       # donnée collectée, fiable
CONFIDENCE_MEDIUM = "medium"   # collectée mais incertaine
CONFIDENCE_LOW = "low"         # estimée ou valeur par défaut
CONFIDENCE_DEFAULT = "default"  # valeur par défaut de la librairie


# ---------------------------------------------------------------------------
# Correction du mix appareils : iOS (mobile) ET macOS (desktop) absents de CrUX
# ---------------------------------------------------------------------------
# CrUX ne mesure QUE Chrome (moteur Blink). Deux angles morts symétriques :
#   - MOBILE : les iPhone/iPad (Safari), et même Chrome sur iOS (WebKit imposé
#     par Apple), ne remontent pas. La part "phone" de CrUX ne reflète donc
#     quasiment que les Android. On regonfle le mobile via la part iOS du parc.
#   - DESKTOP : les Mac sous Safari ne remontent pas. On regonfle le desktop via
#     la part macOS du parc desktop, par symétrie avec la correction iOS.
# Hypothèse assumée (miroir) : on traite iOS et macOS comme intégralement absents
# de CrUX. C'est une légère sur-correction (Chrome-sur-Mac est en réalité mesuré),
# cohérente avec l'hypothèse déjà faite côté mobile.
#
# Valeurs = part iOS du parc MOBILE et part macOS du parc DESKTOP, source
# StatCounter "Mobile Operating System Market Share" et "Desktop Operating System
# Market Share" (snapshot indicatif : 2025-06, à rafraîchir périodiquement).
# Large couverture (Europe + Amériques + Asie + Afrique du Nord/Ouest).
IOS_MOBILE_SHARE = {
    "FR": 0.35, "DE": 0.35, "GB": 0.52, "IE": 0.55, "NL": 0.55, "BE": 0.45,
    "CH": 0.55, "AT": 0.35, "ES": 0.30, "IT": 0.30, "PT": 0.30, "PL": 0.25,
    "SE": 0.55, "NO": 0.60, "DK": 0.65, "FI": 0.50, "RU": 0.30,
    "US": 0.57, "CA": 0.57, "MX": 0.25, "BR": 0.15,
    "JP": 0.69, "KR": 0.30, "CN": 0.22, "IN": 0.04, "AU": 0.55,
    "ZA": 0.18, "SN": 0.10, "TN": 0.15, "MA": 0.15,
    "default": 0.30,
}
MACOS_DESKTOP_SHARE = {
    "FR": 0.17, "DE": 0.15, "GB": 0.28, "IE": 0.25, "NL": 0.13, "BE": 0.13,
    "CH": 0.28, "AT": 0.13, "ES": 0.12, "IT": 0.13, "PT": 0.12, "PL": 0.08,
    "SE": 0.25, "NO": 0.28, "DK": 0.25, "FI": 0.20, "RU": 0.10,
    "US": 0.30, "CA": 0.28, "MX": 0.10, "BR": 0.08,
    "JP": 0.20, "KR": 0.10, "CN": 0.15, "IN": 0.04, "AU": 0.28,
    "ZA": 0.12, "SN": 0.06, "TN": 0.08, "MA": 0.08,
    "default": 0.15,
}
IOS_SHARE_SOURCE = "StatCounter Mobile OS Market Share (snapshot 2025-06, indicatif)"
MACOS_SHARE_SOURCE = "StatCounter Desktop OS Market Share (snapshot 2025-06, indicatif)"

# Bornes de la fourchette de scénarios (part iOS du mobile) affichée en annexe.
IOS_SCENARIO_LOW = 0.25    # conservateur (peu d'iOS -> faible correction)
IOS_SCENARIO_HIGH = 0.55   # audience très Apple


def correct_device_mix(mobile_raw, desktop_raw, ios_share, macos_share):
    """Regonfle mobile (iOS absents de CrUX) ET desktop (macOS/Safari absents),
    puis renormalise à 1.

    mobile_raw / desktop_raw : proportions issues de Chrome (tablette déjà
    fusionnée dans mobile_raw, somme = 1).
    ios_share   : part iOS du parc mobile (0-1). La part Android = 1 - ios_share
                  est seule pleinement visible dans CrUX.
    macos_share : part macOS du parc desktop (0-1). Symétrique : la part non-macOS
                  (Windows/Linux/ChromeOS) est seule pleinement visible.
    Retourne (mobile_fraction, desktop_fraction) renormalisés (somme = 1).
    """
    android_share = 1.0 - ios_share
    non_macos_share = 1.0 - macos_share
    mobile_corr = mobile_raw / android_share if android_share > 0 else mobile_raw
    desktop_corr = desktop_raw / non_macos_share if non_macos_share > 0 else desktop_raw
    total = mobile_corr + desktop_corr
    if total <= 0:
        return round(mobile_raw, 3), round(desktop_raw, 3)
    return round(mobile_corr / total, 3), round(desktop_corr / total, 3)


# ---------------------------------------------------------------------------
# Mix pays d'audience -> pondération iOS / macOS
# ---------------------------------------------------------------------------
# CrUX ne connaît pas le pays des visiteurs (aucune dimension géo). Le mix pays
# d'audience sert UNIQUEMENT à pondérer les parts iOS (mobile) et macOS (desktop)
# de la correction ci-dessus : une audience très "Apple" (US, JP, UK) regonfle
# plus fortement mobile+desktop qu'une audience Android-dominante (IN, BR, SN).
#
# Provenance possible du mix (ordre de priorité, résolu dans main()) :
#   1. --audience saisi (analytics client GA/Matomo, le plus fiable) ;
#   2. audience_mix écrit par l'AGENT dans env-data.json (estimation SimilarWeb,
#      via WebFetch — le script ne scrape jamais) ;
#   3. défaut France (100 % FR) + avertissement console.

def parse_audience_spec(spec):
    """Parse la valeur de --audience. Formats acceptés :
      - liste pondérée : 'FR:0.7,US:0.3'  -> {'FR': 0.7, 'US': 0.3}
      - raccourci pays unique : 'FR'      -> {'FR': 1.0}
    Les poids sont renormalisés pour sommer à 1.
    Retourne (mix_dict, error_msg) ; mix_dict est None en cas d'erreur."""
    spec = (spec or "").strip()
    if not spec:
        return None, "valeur vide"

    # Raccourci pays unique (ni ':' ni ',')
    if ":" not in spec and "," not in spec:
        cc = spec.upper()
        if not cc.isalpha() or len(cc) != 2:
            return None, f"code pays invalide : '{spec}' (attendu ISO-2, ex. FR)"
        return {cc: 1.0}, None

    mix = {}
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if ":" not in part:
            return None, f"segment invalide : '{part}' (attendu PAYS:poids, ex. FR:0.7)"
        cc, w = part.split(":", 1)
        cc = cc.strip().upper()
        if not cc.isalpha() or len(cc) != 2:
            return None, f"code pays invalide : '{cc}' (attendu ISO-2)"
        try:
            w = float(w.strip())
        except ValueError:
            return None, f"poids invalide pour {cc} : '{w.strip()}'"
        if w < 0:
            return None, f"poids négatif pour {cc}"
        mix[cc] = mix.get(cc, 0.0) + w

    total = sum(mix.values())
    if total <= 0:
        return None, "somme des poids nulle"
    return {cc: round(w / total, 4) for cc, w in mix.items()}, None


def weighted_os_shares(audience_mix):
    """Pondère part iOS (mobile) ET part macOS (desktop) par le mix pays.

    audience_mix : {country_code: weight} (somme ≈ 1).
    Retourne (ios_share, macos_share, per_country_detail) où per_country_detail
    liste, par pays, le poids et les parts iOS/macOS utilisées (pour l'annexe).
    Un pays absent des tables retombe sur la valeur 'default'."""
    ios = 0.0
    macos = 0.0
    detail = []
    for cc, w in audience_mix.items():
        cc = cc.upper()
        i = IOS_MOBILE_SHARE.get(cc, IOS_MOBILE_SHARE["default"])
        mth = MACOS_DESKTOP_SHARE.get(cc, MACOS_DESKTOP_SHARE["default"])
        known = cc in IOS_MOBILE_SHARE
        ios += w * i
        macos += w * mth
        detail.append({
            "country": cc,
            "weight": round(w, 4),
            "ios_share": i,
            "macos_share": mth,
            "in_table": known,
        })
    return round(ios, 3), round(macos, 3), detail


def resolve_audience(cli_audience, existing_audience, ios_override=None):
    """Résout le mix pays d'audience selon l'ordre de priorité et calcule les
    parts iOS/macOS pondérées.

    cli_audience     : valeur brute de --audience (ou None).
    existing_audience: bloc 'audience' déjà présent dans env-data.json, écrit par
                       l'agent (SimilarWeb) ou un run précédent (ou None).
    ios_override     : valeur de --ios-mobile-share (écrase la part iOS calculée).

    Retourne un dict 'audience' prêt à stocker dans env-data.json :
        {mix, source, ios_share, macos_share, ios_share_source,
         macos_share_source, per_country, confidence, warning?}
    """
    warning = None
    source_url = None

    if cli_audience:
        mix, err = parse_audience_spec(cli_audience)
        if err:
            return {"error": f"--audience : {err}"}
        source = "saisie manuelle"
        confidence = CONFIDENCE_MEDIUM
    elif existing_audience and existing_audience.get("mix") \
            and existing_audience.get("source") not in (None, "default"):
        mix = {k.upper(): float(v) for k, v in existing_audience["mix"].items()}
        total = sum(mix.values()) or 1.0
        mix = {k: round(v / total, 4) for k, v in mix.items()}
        source = existing_audience.get("source", "SimilarWeb (estimation)")
        confidence = existing_audience.get("confidence", CONFIDENCE_MEDIUM)
        source_url = existing_audience.get("source_url")
    else:
        mix = {"FR": 1.0}
        source = "default"
        confidence = CONFIDENCE_DEFAULT
        warning = ("Aucun mix pays d'audience fourni : France (100 %) par défaut. "
                   "Fournir --audience \"FR:0.7,US:0.3\" (analytics client) ou laisser "
                   "l'agent écrire un mix SimilarWeb dans env-data.json.")

    ios_share, macos_share, per_country = weighted_os_shares(mix)
    ios_share_source = f"pondéré par mix pays ({source}), d'après {IOS_SHARE_SOURCE}"
    macos_share_source = f"pondéré par mix pays ({source}), d'après {MACOS_SHARE_SOURCE}"

    if ios_override is not None:
        ios_share = round(ios_override, 3)
        ios_share_source = f"saisie manuelle (--ios-mobile-share {ios_override})"

    return {
        "mix": mix,
        "source": source,
        "source_url": source_url,
        "ios_share": ios_share,
        "macos_share": macos_share,
        "ios_share_source": ios_share_source,
        "macos_share_source": macos_share_source,
        "per_country": per_country,
        "confidence": confidence,
        "warning": warning,
    }


# ---------------------------------------------------------------------------
# Volume de trafic annuel (visites/an)
# ---------------------------------------------------------------------------
# Ni PageSpeed ni CrUX ne fournissent de volume d'audience (leurs API ne
# renvoient que des distributions, jamais de compteurs de visites). Le trafic
# est donc soit saisi (analytics client), soit estimé par une source tierce
# (SimilarWeb) que l'AGENT écrit dans env-data.json via WebFetch — le script ne
# scrape jamais. À défaut : baseline 100 000 visites/an + avertissement.
#
# Provenance possible (ordre de priorité, résolu dans run_efootprint.py) :
#   1. --visits saisi (analytics client GA/Matomo, le plus fiable) ;
#   2. bloc 'traffic' écrit par l'agent dans env-data.json (estimation SimilarWeb) ;
#   3. défaut 100 000 visites/an + avertissement.

DEFAULT_VISITS_PER_YEAR = 100_000


def resolve_traffic(existing_traffic):
    """Résout le bloc 'traffic' à stocker dans env-data.json.

    existing_traffic : bloc 'traffic' déjà présent dans env-data.json, écrit par
                       l'agent (SimilarWeb) ou un run précédent (ou None).

    Le script ne collecte JAMAIS le trafic lui-même (aucune API publique fiable) :
    il ne fait que valider et normaliser le bloc écrit par l'agent, ou poser un
    défaut explicite. La saisie manuelle passe par --visits dans run_efootprint.py.

    Retourne un dict prêt à stocker : {visits_per_year, monthly_visits?, source,
    source_url, snapshot?, confidence, note, warning?}.
    """
    if existing_traffic and existing_traffic.get("visits_per_year") \
            and existing_traffic.get("source") not in (None, "default"):
        try:
            visits = int(round(float(existing_traffic["visits_per_year"])))
        except (TypeError, ValueError):
            visits = None
        if visits and visits > 0:
            monthly = existing_traffic.get("monthly_visits")
            resolved = {
                "visits_per_year": visits,
                "monthly_visits": int(round(float(monthly))) if monthly else None,
                "source": existing_traffic.get("source", "SimilarWeb (estimation)"),
                "source_url": existing_traffic.get("source_url"),
                "snapshot": existing_traffic.get("snapshot"),
                "confidence": existing_traffic.get("confidence", CONFIDENCE_MEDIUM),
                "note": existing_traffic.get(
                    "note",
                    "Volume d'audience estimé par une source tierce (marge large). "
                    "Le CO2e total croît avec le trafic (au-dessus d'un socle fixe fabrication serveur + stockage) ; le CO2e/visite diminue quand le trafic augmente."),
                "warning": None,
            }
            # Temps moyen par page (TimeOnSite/PagePerVisit) : sert au recalage
            # Nielsen (efootprint_model/temps_utilisateur.py, Lot 4). Additif,
            # absent si SimilarWeb ne le fournit pas (cf. similarweb_api.py).
            avg_time = existing_traffic.get("avg_time_on_page_s")
            if avg_time is not None:
                resolved["avg_time_on_page_s"] = avg_time
            return resolved

    return {
        "visits_per_year": DEFAULT_VISITS_PER_YEAR,
        "monthly_visits": None,
        "source": "default",
        "source_url": None,
        "snapshot": None,
        "confidence": CONFIDENCE_DEFAULT,
        "note": "Aucune source de trafic fournie : baseline 100 000 visites/an. "
                "Le CO2e total croît avec le trafic (au-dessus d'un socle fixe fabrication serveur + stockage) ; le CO2e/visite diminue quand le trafic augmente.",
        "warning": ("Aucun volume de trafic fourni : baseline 100 000 visites/an par défaut. "
                    "Fournir --visits (analytics client) ou laisser l'agent écrire un bloc "
                    "'traffic' SimilarWeb dans env-data.json."),
    }


# ---------------------------------------------------------------------------
# Récupération automatique SimilarWeb (API interne)
# ---------------------------------------------------------------------------
# Quand un bloc 'audience' ou 'traffic' manque (absent, ou source 'default'), on
# interroge automatiquement l'API interne SimilarWeb via le module frère
# similarweb_api.py et on écrit les blocs manquants dans env-data.json AVANT la
# résolution audience/trafic. C'est la voie principale (remplace l'ancien WebFetch).
#
# Garde-fous — l'ordre de priorité existant reste sacré :
#   - une saisie manuelle (--audience) prime : on n'écrit alors PAS le bloc audience ;
#   - un bloc déjà présent avec une vraie source n'est JAMAIS écrasé ;
#   - échec API (403, domaine inconnu, réseau) → message clair, on continue
#     (l'appelant retombe sur la récupération assistée 20d, puis le défaut).

def _block_missing(block):
    """Un bloc audience/traffic est 'manquant' s'il est absent, sans mix/visites,
    ou marqué source 'default'/None (donc à (re)remplir par SimilarWeb)."""
    if not block:
        return True
    if block.get("source") in (None, "default"):
        return True
    return not (block.get("mix") or block.get("visits_per_year"))


def maybe_fetch_similarweb(source_dir, existing_audience, existing_traffic,
                           cli_audience=None, sw_domain=None):
    """Tente de compléter les blocs audience/traffic manquants via l'API SimilarWeb.

    Retourne (audience_block, traffic_block) : les blocs construits pour ce qui
    manquait, ou les blocs existants inchangés sinon. Ne touche PAS au disque : ces
    blocs sont ensuite passés à resolve_audience/resolve_traffic puis réécrits en
    une seule fois par build_env_data. Ne lève jamais : tout échec est loggé et on
    renvoie les blocs d'origine.

    cli_audience : si fourni, la saisie manuelle prime → on n'écrit pas le mix pays.
    sw_domain    : force le domaine SimilarWeb (sinon déduit de env-data.json/HAR).
    """
    if similarweb_api is None:
        print("  ⚠ module similarweb_api indisponible — appel automatique ignoré.")
        return existing_audience, existing_traffic

    # Que manque-t-il ? Le mix pays n'est visé que si aucune saisie manuelle (--audience).
    need_audience = (not cli_audience) and _block_missing(existing_audience)
    need_traffic = _block_missing(existing_traffic)
    if not need_audience and not need_traffic:
        return existing_audience, existing_traffic

    domain = sw_domain or similarweb_api.infer_domain(source_dir)
    if not domain:
        print("  ⚠ SimilarWeb : domaine introuvable (préciser --sw-domain) — appel ignoré.")
        return existing_audience, existing_traffic

    print(f"  [similarweb] Interrogation de l'API interne pour : {domain} …")
    data, err = similarweb_api.fetch_domain_data(domain)
    if err:
        print(f"  ⚠ SimilarWeb : {err}")
        print("     Repli attendu : récupération assistée (SKILL.md Étape 20d), puis défaut.")
        return existing_audience, existing_traffic

    source_url = f"https://www.similarweb.com/website/{domain}/"
    audience_block = existing_audience
    traffic_block = existing_traffic
    got_audience = got_traffic = False
    if need_audience:
        built = similarweb_api.build_audience_block(data, source_url)
        if built:
            audience_block = built
            got_audience = True
            mix_str = ", ".join(f"{cc} {w:.0%}" for cc, w in built["mix"].items())
            print(f"     Mix pays : {mix_str}")
    if need_traffic:
        built = similarweb_api.build_traffic_block(data, source_url)
        if built:
            traffic_block = built
            got_traffic = True
            snap = built.get("snapshot") or "?"
            print(f"     Trafic : {built['monthly_visits']:,}/mois ({snap}) "
                  f"→ {built['visits_per_year']:,}/an")

    # L'API peut répondre 200 sans donnée exploitable (domaine peu/pas suivi par
    # SimilarWeb : pas de TopCountryShares, visites nulles). On le signale au lieu
    # de retomber en silence sur les défauts.
    if (need_audience and not got_audience) or (need_traffic and not got_traffic):
        manque = []
        if need_audience and not got_audience:
            manque.append("mix pays")
        if need_traffic and not got_traffic:
            manque.append("trafic")
        print(f"  ⚠ SimilarWeb : pas de {' ni de '.join(manque)} exploitable pour "
              f"{domain} (domaine peu suivi ?).")
        print("     Repli attendu : récupération assistée (SKILL.md Étape 20d), puis défaut.")

    return audience_block, traffic_block


# ---------------------------------------------------------------------------
# Chargement .env
# ---------------------------------------------------------------------------

def load_env(project_root):
    """Lit GOOGLE_API_KEY et IPINFO_TOKEN depuis .env."""
    env_path = project_root / ".env"
    keys = {}
    if not env_path.exists():
        return keys
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                keys[k.strip()] = v.strip()
    return keys


def find_project_root(start):
    """Remonte jusqu'à trouver .env ou .git."""
    p = Path(start).resolve()
    for _ in range(8):
        if (p / ".env").exists() or (p / ".git").exists():
            return p
        p = p.parent
    return Path(start).resolve()


# ---------------------------------------------------------------------------
# HAR : extraction poids + durée + IP serveur
# ---------------------------------------------------------------------------

def find_har(source_dir):
    hars = list(source_dir.glob("*.har")) or list(
        (source_dir / RAW_DATA_DIR).glob("*.har"))
    if len(hars) == 1:
        return hars[0]
    if len(hars) > 1:
        print(f"[HAR] Plusieurs .har trouvés, utilisation de : {hars[0].name}")
        return hars[0]
    return None


def _entry_transfer_bytes(entry):
    """Octets réseau RÉELS (compressés) d'une entrée HAR, pour e-footprint UNIQUEMENT.

    Le vrai octet qui transite sur le réseau est le corps COMPRESSÉ (brotli/gzip),
    pas le content.size (décompressé). data_transferred pilote l'énergie réseau du
    calcul CO2e : c'est donc le poids transféré qui doit l'alimenter.

    Chaîne de repli robuste (le champ _transferSize, préfixé _, est une extension
    Chrome non standardisée ; toujours présent dans notre pipeline Chrome, le repli
    ne couvre que le cas dégradé d'un HAR appauvri) :
      1. response._transferSize (mesure directe, en-têtes + corps compressé) ;
      2. sinon bodySize (+ headersSize si connu) ;
      3. sinon content.size (dernier recours, DÉCOMPRESSÉ, surestime).

    GARDE-FOU : EcoIndex (har_metrics.py) garde content.size (poids décompressé,
    exigé par la formule cnumr). Cette fonction ne concerne QUE le chemin e-footprint.
    """
    resp = entry.get("response", {})
    ts = resp.get("_transferSize")
    if ts is not None and ts >= 0:
        return ts
    body = resp.get("bodySize", -1)
    if body is not None and body >= 0:
        headers = resp.get("headersSize", -1)
        return body + (headers if headers and headers > 0 else 0)
    return resp.get("content", {}).get("size", 0) or 0


def _resource_category(mime, url):
    """Classe une ressource par type, pour le breakdown de poids (Volet B).

    Combine le mimeType (fiable) et l'extension d'URL (fallback). Catégories :
    html, css, js, image, font, autre. Mesure directe depuis le HAR (bonne confiance)."""
    m = (mime or "").lower()
    u = url.lower().split("?")[0]
    if "html" in m:
        return "html"
    if "css" in m or u.endswith(".css"):
        return "css"
    if "javascript" in m or u.endswith(".js") or u.endswith(".mjs"):
        return "js"
    if "image" in m or "svg" in m or u.endswith((".png", ".jpg", ".jpeg", ".gif",
                                                  ".webp", ".svg", ".ico", ".avif")):
        return "image"
    if "font" in m or u.endswith((".woff", ".woff2", ".ttf", ".otf", ".eot")):
        return "font"
    return "autre"


def _page_breakdown(page_entries, page_url):
    """Décompose le poids d'une page par type de ressource et part tierce (Volet B).

    Métriques documentaires (mesure directe, bonne confiance). N'entrent PAS dans le
    calcul e-footprint : elles EXPLIQUENT le data_transferred déjà utilisé (poids de
    la page représentative). Le nombre de requêtes est affiché comme indice, mais le
    CPU serveur (compute_needed) reste indéductible du HAR côté client.

    part tierce : octets/requêtes vers un host différent de celui de la page.
    """
    main_host = urllib.parse.urlparse(page_url).netloc if page_url else ""
    by_type = {}                # octets DÉCOMPRESSÉS (content.size) — documentaire/EcoIndex
    by_type_transfer = {}       # octets TRANSFÉRÉS (réseau réel) — e-footprint (LOT 1)
    third_party_bytes = 0
    third_party_transfer_bytes = 0
    third_party_requests = 0
    for e in page_entries:
        url = e.get("request", {}).get("url", "")
        content = e.get("response", {}).get("content", {})
        size = content.get("size", 0) or 0
        transfer = _entry_transfer_bytes(e)
        cat = _resource_category(content.get("mimeType", ""), url)
        by_type[cat] = by_type.get(cat, 0) + size
        by_type_transfer[cat] = by_type_transfer.get(cat, 0) + transfer
        netloc = urllib.parse.urlparse(url).netloc
        if main_host and netloc and netloc != main_host:
            third_party_bytes += size
            third_party_transfer_bytes += transfer
            third_party_requests += 1
    total = sum(by_type.values())
    total_transfer = sum(by_type_transfer.values())
    return {
        "by_type_bytes": by_type,
        "total_bytes": total,
        "third_party_bytes": third_party_bytes,
        "third_party_requests": third_party_requests,
        "third_party_share": round(third_party_bytes / total, 3) if total else 0.0,
        # --- LOT 1 : mêmes décomptes en octets réseau RÉELS (compressés) ---
        "by_type_transfer_bytes": by_type_transfer,
        "total_transfer_bytes": total_transfer,
        "third_party_transfer_bytes": third_party_transfer_bytes,
        "third_party_transfer_share": round(third_party_transfer_bytes / total_transfer, 3) if total_transfer else 0.0,
    }


def _median(values):
    if not values:
        return 0
    s = sorted(values)
    n = len(s)
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2


def _percentile(values, pct):
    if not values:
        return 0
    s = sorted(values)
    k = (len(s) - 1) * pct
    f = int(k)
    c = min(f + 1, len(s) - 1)
    if f == c:
        return s[f]
    return s[f] + (s[c] - s[f]) * (k - f)


def _har_facts(page_entries):
    """Signaux serveur/réseau factuels annexés (LOT 3, mesure directe HAR).

    Purement documentaire : n'entre PAS dans le calcul e-footprint (compute_needed
    reste figé, cf. Volet B). Sert à tracer en annexe méthodologique le cache
    navigateur, les timings serveur, les méthodes/statuts et la version HTTP.
    """
    total = len(page_entries)
    cached = [e for e in page_entries if e.get("response", {}).get("status") == 304]
    n_cached = len(cached)
    cached_transfer_bytes = sum(_entry_transfer_bytes(e) for e in cached)
    cached_uncompressed_bytes = sum(
        e.get("response", {}).get("content", {}).get("size", 0) or 0 for e in cached
    )

    waits = [
        e.get("timings", {}).get("wait", -1)
        for e in page_entries
        if e.get("timings", {}).get("wait", -1) is not None and e.get("timings", {}).get("wait", -1) >= 0
    ]

    methods = {}
    statuses = {}
    http_versions = {}
    for e in page_entries:
        m = e.get("request", {}).get("method", "?")
        methods[m] = methods.get(m, 0) + 1
        s = e.get("response", {}).get("status")
        if s is not None:
            statuses[s] = statuses.get(s, 0) + 1
        v = e.get("response", {}).get("httpVersion", "?")
        http_versions[v] = http_versions.get(v, 0) + 1

    dominant_http_version = max(http_versions, key=http_versions.get) if http_versions else "?"

    return {
        "request_count": total,
        "cache_304_count": n_cached,
        "cache_304_share": round(n_cached / total, 3) if total else 0.0,
        "cache_304_transfer_bytes": cached_transfer_bytes,
        "cache_304_uncompressed_bytes": cached_uncompressed_bytes,
        "wait_ms_median": round(_median(waits), 1),
        "wait_ms_p95": round(_percentile(waits, 0.95), 1),
        "methods": methods,
        "statuses": statuses,
        "http_versions": http_versions,
        "dominant_http_version": dominant_http_version,
        "note": "Documentaire (mesure directe HAR), n'entre pas dans le calcul e-footprint.",
    }


def extract_har_data(har_path):
    """
    Extrait depuis le HAR :
      - pages : liste de {url, size_bytes, on_load_ms, breakdown}
      - server_ip : IP du serveur principal (première requête document)
    """
    with open(har_path, encoding="utf-8") as f:
        har = json.load(f)

    log = har.get("log", {})
    pages_raw = log.get("pages", [])
    entries = log.get("entries", [])

    # Index entries par pageref
    entries_by_page = {}
    for e in entries:
        ref = e.get("pageref", "")
        entries_by_page.setdefault(ref, []).append(e)

    pages = []
    server_ip = None

    for i, page in enumerate(pages_raw):
        pid = page.get("id", f"page_{i+1}")
        url = page.get("title", "")
        timings = page.get("pageTimings", {})
        on_load_ms = timings.get("onLoad") or 0

        page_entries = entries_by_page.get(pid, [])
        # Poids DÉCOMPRESSÉ (content.size) : documentaire, aligné sur EcoIndex.
        size_bytes = sum(
            e.get("response", {}).get("content", {}).get("size", 0)
            for e in page_entries
        )
        # Poids TRANSFÉRÉ (réseau réel, compressé) : alimente e-footprint (LOT 1).
        size_transfer_bytes = sum(_entry_transfer_bytes(e) for e in page_entries)

        pages.append({
            "page_id": pid,
            "url": url,
            "size_bytes": size_bytes,
            "size_kb": round(size_bytes / 1024, 1),
            "size_transfer_bytes": size_transfer_bytes,
            "size_transfer_kb": round(size_transfer_bytes / 1024, 1),
            "on_load_ms": round(on_load_ms),
            "request_count": len(page_entries),
            "breakdown": _page_breakdown(page_entries, url),
            "har_facts": _har_facts(page_entries),
        })

        # IP serveur : depuis la première entrée HTML de cette page
        if server_ip is None:
            for e in page_entries:
                mime = e.get("response", {}).get("content", {}).get("mimeType", "")
                if "html" in mime:
                    ip = e.get("serverIPAddress", "")
                    if ip and not ip.startswith("127.") and not ip.startswith("::1"):
                        server_ip = ip
                    break

    # Fallback IP : première entrée du HAR avec IP non-locale
    if server_ip is None:
        for e in entries:
            ip = e.get("serverIPAddress", "")
            if ip and not ip.startswith("127.") and not ip.startswith("::1"):
                server_ip = ip
                break

    return pages, server_ip


def aggregate_page_metrics(pages):
    """
    Agrège les métriques HAR sur l'ensemble des pages pour e-footprint.
    Retourne les valeurs moyennes pondérées par la taille.
    """
    if not pages:
        return {}

    # On utilise la page la plus lourde comme représentante du parcours
    heaviest = max(pages, key=lambda p: p["size_bytes"])
    avg_size_bytes = sum(p["size_bytes"] for p in pages) / len(pages)
    avg_on_load_ms = sum(p["on_load_ms"] for p in pages if p["on_load_ms"] > 0)
    n_with_load = sum(1 for p in pages if p["on_load_ms"] > 0)

    # Breakdown de la page représentative (page la plus lourde = celle utilisée par
    # data_transferred). Métriques documentaires qui EXPLIQUENT l'input, sans le
    # modifier. Le nombre de requêtes est un indice ; il ne sert PAS à déduire
    # compute_needed (le CPU serveur reste indéductible du HAR côté client).
    breakdown = heaviest.get("breakdown", {})

    return {
        "pages_count": len(pages),
        "heaviest_page_url": heaviest["url"],
        "heaviest_page_size_bytes": heaviest["size_bytes"],
        "avg_size_bytes": round(avg_size_bytes),
        "avg_size_kb": round(avg_size_bytes / 1024, 1),
        "avg_on_load_ms": round(avg_on_load_ms / n_with_load) if n_with_load else 0,
        # Inputs e-footprint recommandés (page représentative = plus lourde)
        "efootprint": {
            # Poids DÉCOMPRESSÉ (content.size) : conservé pour rétro-compat et
            # comparaison ; NE sert plus d'input principal côté run_efootprint.
            "data_transferred_bytes": heaviest["size_bytes"],
            # Poids TRANSFÉRÉ (réseau réel, compressé) : NOUVEL input e-footprint
            # (LOT 1). data_transferred pilote l'énergie réseau -> doit être le
            # poids réellement transmis, pas le décompressé.
            "data_transferred_bytes_real": heaviest.get("size_transfer_bytes", heaviest["size_bytes"]),
            "compression_ratio": (
                round(heaviest["size_transfer_bytes"] / heaviest["size_bytes"], 3)
                if heaviest.get("size_transfer_bytes") and heaviest["size_bytes"] else None
            ),
            "request_duration_ms": heaviest["on_load_ms"] or round(avg_on_load_ms / n_with_load) if n_with_load else 1000,
            "confidence_data_transferred": CONFIDENCE_HIGH,
            "confidence_data_transferred_real": CONFIDENCE_HIGH,  # mesure directe (_transferSize)
            "confidence_request_duration": CONFIDENCE_HIGH if heaviest["on_load_ms"] > 0 else CONFIDENCE_MEDIUM,
            # --- Volet B : transparence sur la composition du poids (documentaire) ---
            "request_count": heaviest.get("request_count", 0),
            "weight_by_type_bytes": breakdown.get("by_type_bytes", {}),
            "weight_by_type_transfer_bytes": breakdown.get("by_type_transfer_bytes", {}),
            "third_party_bytes": breakdown.get("third_party_bytes", 0),
            "third_party_transfer_bytes": breakdown.get("third_party_transfer_bytes", 0),
            "third_party_requests": breakdown.get("third_party_requests", 0),
            "third_party_share": breakdown.get("third_party_share", 0.0),
            "third_party_transfer_share": breakdown.get("third_party_transfer_share", 0.0),
            "confidence_breakdown": CONFIDENCE_HIGH,  # mesure directe HAR
            # --- LOT 2/3 : signaux serveur/réseau factuels annexés (documentaire) ---
            "har_facts": heaviest.get("har_facts", {}),
            "confidence_har_facts": CONFIDENCE_HIGH,  # mesure directe HAR
            # compute_needed reste figé côté run_efootprint (0.05 cpu_core) : le HAR
            # ne mesure pas le CPU serveur. Documenté, pas déduit.
            "compute_needed_note": "CPU serveur indéductible du HAR (signal côté client). "
                                   "compute_needed reste une valeur type (confiance faible).",
        }
    }


# ---------------------------------------------------------------------------
# CrUX : répartition mobile/desktop/tablet
# ---------------------------------------------------------------------------

def call_crux(url, api_key):
    """
    Interroge l'API CrUX pour obtenir la répartition de formulaire d'utilisation.
    Retourne le JSON brut ou None.
    """
    params = urllib.parse.urlencode({"key": api_key})
    full_url = CRUX_API + "?" + params
    body = json.dumps({"url": url, "metrics": ["form_factors"]}).encode("utf-8")
    req = urllib.request.Request(
        full_url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body_err = e.read().decode("utf-8", errors="replace")
        try:
            msg = json.loads(body_err).get("error", {}).get("message", body_err[:200])
        except Exception:
            msg = body_err[:200]
        print(f"  [CrUX] Erreur HTTP {e.code} : {msg}")
        return None
    except Exception as e:
        print(f"  [CrUX] Erreur réseau : {e}")
        return None


def extract_device_mix(crux_data):
    """
    Extrait la répartition mobile/desktop/tablet depuis la réponse CrUX.
    Retourne un dict avec fractions (0-1) ou None si données indisponibles.
    """
    if not crux_data:
        return None
    record = crux_data.get("record", {})
    metrics = record.get("metrics", {})
    ff = metrics.get("form_factors", {})
    fractions = ff.get("fractions", {})
    if not fractions:
        return None

    phone = fractions.get("phone", 0.0)
    desktop = fractions.get("desktop", 0.0)
    tablet = fractions.get("tablet", 0.0)

    total = phone + desktop + tablet
    if total == 0:
        return None

    return {
        "phone": round(phone / total, 3),
        "desktop": round(desktop / total, 3),
        "tablet": round(tablet / total, 3),
        "source": "crux",
    }


def collect_device_mix(url, api_key):
    """Collecte la répartition device pour une URL depuis CrUX."""
    # Essai avec l'URL exacte, puis avec l'origine
    from urllib.parse import urlparse
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"

    print(f"  [CrUX] {url}")
    data = call_crux(url, api_key)
    mix = extract_device_mix(data)

    if mix is None and url != origin:
        print(f"  [CrUX] Pas de données pour l'URL, essai avec l'origine : {origin}")
        data = call_crux(origin, api_key)
        mix = extract_device_mix(data)
        if mix:
            mix["source"] = "crux_origin"

    return mix


# ---------------------------------------------------------------------------
# ipinfo.io : pays + provider depuis IP
# ---------------------------------------------------------------------------

def call_ipinfo(ip, token=None):
    """Interroge ipinfo.io pour une IP. Retourne le JSON ou None."""
    url = IPINFO_API.format(ip=ip)
    if token:
        url += f"?token={token}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"  [ipinfo] Erreur pour {ip} : {e}")
        return None


def detect_cloud_provider(org_field):
    """
    Détecte le provider cloud depuis le champ 'org' d'ipinfo.
    Ex: "AS16509 Amazon.com, Inc." -> "aws"
    """
    if not org_field:
        return None
    org_lower = org_field.lower()

    if "amazon" in org_lower or "aws" in org_lower:
        return "aws"
    if "google" in org_lower or "gcloud" in org_lower:
        return "gcp"
    if "microsoft" in org_lower or "azure" in org_lower:
        return "azure"
    if "ovh" in org_lower:
        return "ovh"
    if "scaleway" in org_lower or "online s.a.s" in org_lower:
        return "scaleway"
    if "cloudflare" in org_lower:
        return "cloudflare"  # CDN, pas un cloud à proprement parler
    if "akamai" in org_lower or "limelight" in org_lower:
        return "cdn"
    if "hetzner" in org_lower:
        return "hetzner"

    return None


_COUNTRY_CARBON_INTENSITY = {
    # g CO2eq/kWh, source : electricitymaps.com 2023 moyennes annuelles
    "FR": 56,
    "DE": 381,
    "GB": 239,
    "NL": 295,
    "BE": 148,
    "ES": 192,
    "IT": 371,
    "PL": 774,
    "SE": 45,
    "NO": 29,
    "DK": 154,
    "FI": 128,
    "US": 428,
    "CA": 130,
    "AU": 545,
    "JP": 462,
    "KR": 415,
    "SG": 432,
    "IN": 713,
    "CN": 581,
    "BR": 114,
    "ZA": 840,
}
_DEFAULT_CARBON_INTENSITY = 400  # g/kWh (valeur mondiale moyenne)


def country_to_efootprint(country_code):
    """
    Retourne le nom de la constante e-footprint pour un code pays ISO 2.
    Fallback vers WORLD si pays inconnu.
    """
    mapping = {
        "FR": "FRANCE",
        "DE": "GERMANY",
        "GB": "GREAT_BRITAIN",
        "NL": "NETHERLANDS",
        "BE": "BELGIUM",
        "ES": "SPAIN",
        "IT": "ITALY",
        "PL": "POLAND",
        "SE": "SWEDEN",
        "NO": "NORWAY",
        "US": "USA",
        "CA": "CANADA",
        "AU": "AUSTRALIA",
        "JP": "JAPAN",
        "SG": "SINGAPORE",
        "BR": "BRAZIL",
        "CN": "CHINA",
    }
    return mapping.get(country_code.upper(), "WORLD") if country_code else "WORLD"


def collect_server_info(ip, token=None):
    """
    Collecte pays + provider depuis l'IP du serveur via ipinfo.io.
    Retourne un dict avec les infos ou None si échec.
    """
    if not ip:
        return None

    print(f"  [ipinfo] {ip}")
    data = call_ipinfo(ip, token)
    if not data or "bogon" in data:
        return None

    country_code = data.get("country", "")
    org = data.get("org", "")
    hostname = data.get("hostname", "")
    city = data.get("city", "")

    provider = detect_cloud_provider(org)
    carbon_intensity = _COUNTRY_CARBON_INTENSITY.get(country_code.upper(), _DEFAULT_CARBON_INTENSITY)

    return {
        "ip": ip,
        "country_code": country_code,
        "city": city,
        "org": org,
        "hostname": hostname,
        "detected_provider": provider,
        "carbon_intensity_g_kwh": carbon_intensity,
        "efootprint_country": country_to_efootprint(country_code),
        "source": "ipinfo",
    }


def collect_multi_server_info(har_path, audited_domain, first_party_extra=(), token=None):
    """Géolocalise CHAQUE infrastructure 1st-party détectée dans le HAR, pas
    seulement le serveur principal (Lot 3 : sites à plusieurs infras
    distinctes, ex. ANTS avec 3 serveurs 1st-party).

    Retourne une liste de dicts (même forme que `collect_server_info()`, plus
    `host`, `hosts`, `request_count`, `transferred_bytes`, `cache_header_seen`,
    `is_primary`), triée comme `detect_infrastructures()` (octets décroissants,
    la première est l'infra principale). Une IP non résolue par ipinfo est
    incluse quand même (host/hosts/octets connus, reste des champs à None) :
    un échec réseau sur un serveur secondaire ne doit pas faire disparaître
    l'infra elle-même du modèle.

    Retourne [] si `detect_infrastructures` est indisponible (import guardé)
    ou si le HAR n'a révélé aucune infra 1st-party.
    """
    if detect_infrastructures is None or not har_path:
        return []

    infrastructures, _ = detect_infrastructures(har_path, audited_domain,
                                                 first_party_extra=first_party_extra)
    results = []
    for i, infra in enumerate(infrastructures):
        ip = infra["ips"][0] if infra["ips"] else None
        info = collect_server_info(ip, token) or {}
        results.append({
            "host": infra["key"],
            "hosts": list(infra["hosts"]),
            "ip": ip,
            "country_code": info.get("country_code"),
            "city": info.get("city"),
            "org": info.get("org"),
            "detected_provider": info.get("detected_provider"),
            "carbon_intensity_g_kwh": info.get("carbon_intensity_g_kwh"),
            "efootprint_country": info.get("efootprint_country"),
            "confidence_country": CONFIDENCE_HIGH if info.get("country_code") else CONFIDENCE_DEFAULT,
            "confidence_provider": CONFIDENCE_MEDIUM if info.get("detected_provider") else CONFIDENCE_LOW,
            "request_count": infra["request_count"],
            "transferred_bytes": infra["transferred_bytes"],
            "cache_header_seen": infra["cache_header_seen"],
            "is_primary": i == 0,
        })
    return results


# ---------------------------------------------------------------------------
# Construction env-data.json
# ---------------------------------------------------------------------------

def build_env_data(har_data, device_mix, server_info, audience=None, traffic=None,
                   tech_stack=None, servers_info=None, ai_external_apis=None):
    """
    Assemble env-data.json depuis les données collectées.
    Chaque section indique les inputs e-footprint et leur niveau de confiance.

    servers_info : liste optionnelle produite par `collect_multi_server_info()`,
    UNE ENTRÉE PAR INFRASTRUCTURE 1st-party détectée dans le HAR (Lot 3). Écrite
    dans la clé "servers" (pluriel), qui coexiste avec "server" (singulier,
    INCHANGÉE) : "server" continue de décrire l'infra principale exactement
    comme avant (non-régression), "servers" est une ADDITION que le rapport
    actuel ignore tant qu'il ne la lit pas.

    audience : dict résolu par resolve_audience() portant le mix pays d'audience
    et les parts iOS/macOS pondérées servant à corriger le mix appareils. Si None,
    on retombe sur France (100 %) via resolve_audience(None, None).

    traffic : dict résolu par resolve_traffic() portant le volume d'audience annuel
    et sa provenance (SimilarWeb / saisie / défaut). Si None, baseline 100 000/an.

    tech_stack : dict de détection techno (detect_tech.detect_from_har). Écrit tel
    quel dans la clé "tech_stack". Si None, la clé vaut None (non-régression : le
    rapport et le calcul restent valides sans détection).

    ai_external_apis : dict {host: {rule_name, provider, resolved, model_name,
    output_tokens}} fusionné par merge_ai_external_apis() — PERSISTÉ (jamais
    redemandé une fois "resolved", contrairement à tech_stack recalculé à chaque
    run). Si None, la clé vaut {} (non-régression : from_har.py ignore un bloc
    absent, aucun appel IA générative ajouté au calcul).
    """
    pages, _ = har_data if isinstance(har_data, tuple) else (har_data, None)
    har_metrics = aggregate_page_metrics(pages)

    if audience is None:
        audience = resolve_audience(None, None)
    if traffic is None:
        traffic = resolve_traffic(None)
    ios_share = audience["ios_share"]
    macos_share = audience["macos_share"]
    ios_share_source = audience["ios_share_source"]
    macos_share_source = audience["macos_share_source"]

    # --- Device mix ---
    # Décision projet : la tablette est rattachée au mobile (logique tactile /
    # portable). Le corps du rapport n'affiche que desktop/mobile ; le détail
    # (fractions brutes phone/tablet, corrections iOS+macOS, fourchette) va en annexe.
    if device_mix:
        phone_raw = device_mix["phone"]
        desktop_raw = device_mix["desktop"]
        tablet_raw = device_mix.get("tablet", 0.0)
        # Tablette rattachée au mobile
        mobile_raw = round(phone_raw + tablet_raw, 3)
        crux_source = device_mix["source"]

        # Correction symétrique : iOS (mobile) ET macOS (desktop). La fourchette
        # fait varier la part iOS (sensibilité principale) à part macOS constante.
        mobile_central, desktop_central = correct_device_mix(mobile_raw, desktop_raw, ios_share, macos_share)
        mobile_low, desktop_low = correct_device_mix(mobile_raw, desktop_raw, IOS_SCENARIO_LOW, macos_share)
        mobile_high, desktop_high = correct_device_mix(mobile_raw, desktop_raw, IOS_SCENARIO_HIGH, macos_share)

        device_section = {
            # Valeurs retenues pour le calcul (mobile = phone+tablet, corrigé iOS+macOS)
            "phone_fraction": mobile_central,
            "desktop_fraction": desktop_central,
            "tablet_fraction": 0.0,
            "tablet_merged_into_mobile": True,
            "source": crux_source,
            "confidence": CONFIDENCE_MEDIUM,  # corrigé (estimations iOS/macOS) => medium
            # Brut CrUX (Chrome only, avant fusion tablette et corrections)
            "phone_fraction_raw": phone_raw,
            "desktop_fraction_raw": desktop_raw,
            "tablet_fraction_raw": tablet_raw,
            "mobile_fraction_raw": mobile_raw,
            # Corrections iOS (mobile) + macOS (desktop)
            "ios_share_used": round(ios_share, 3),
            "ios_share_source": ios_share_source,
            "macos_share_used": round(macos_share, 3),
            "macos_share_source": macos_share_source,
            "mobile_fraction_corrected": mobile_central,
            "desktop_fraction_corrected": desktop_central,
            # Fourchette pour l'annexe (part iOS variable, part macOS constante)
            "scenarios": {
                "conservateur": {"ios_share": IOS_SCENARIO_LOW, "mobile": mobile_low, "desktop": desktop_low},
                "central": {"ios_share": round(ios_share, 3), "mobile": mobile_central, "desktop": desktop_central},
                "apple_heavy": {"ios_share": IOS_SCENARIO_HIGH, "mobile": mobile_high, "desktop": desktop_high},
            },
            "note": "CrUX = Chrome uniquement (iOS/Safari non mesurés). Mobile regonflé via "
                    "part iOS, desktop via part macOS (pondérées par le mix pays d'audience) ; "
                    "tablette rattachée au mobile.",
        }
        # Réseau basé sur le mobile corrigé (phones+tablet = mobile ; desktop = wifi)
        network_mix = {
            "wifi": desktop_central,
            "mobile": mobile_central,
            "source": "inferred_from_corrected_device_mix",
        }
    else:
        device_section = {
            "phone_fraction": 0.6,
            "desktop_fraction": 0.4,
            "tablet_fraction": 0.0,
            "tablet_merged_into_mobile": True,
            "source": "default",
            "confidence": CONFIDENCE_DEFAULT,
            "note": "CrUX indisponible - valeurs par défaut (60% mobile, 40% desktop). "
                    "Pas de correction iOS/macOS appliquée (aucune donnée à corriger).",
        }
        network_mix = {"wifi": 0.4, "mobile": 0.6, "source": "default"}

    # --- Réseau ---
    network_section = {
        "wifi_fraction": network_mix["wifi"],
        "mobile_fraction": network_mix["mobile"],
        "source": network_mix["source"],
        "confidence": CONFIDENCE_MEDIUM if network_mix["source"] != "default" else CONFIDENCE_DEFAULT,
    }

    # --- Serveur ---
    if server_info:
        server_section = {
            "ip": server_info["ip"],
            "country_code": server_info["country_code"],
            "org": server_info["org"],
            "detected_provider": server_info["detected_provider"],
            "carbon_intensity_g_kwh": server_info["carbon_intensity_g_kwh"],
            "efootprint_country": server_info["efootprint_country"],
            "source": "ipinfo",
            "confidence_country": CONFIDENCE_HIGH,
            "confidence_provider": CONFIDENCE_MEDIUM if server_info["detected_provider"] else CONFIDENCE_LOW,
            "confidence_carbon_intensity": CONFIDENCE_HIGH if server_info["country_code"] in _COUNTRY_CARBON_INTENSITY else CONFIDENCE_MEDIUM,
        }
    else:
        server_section = {
            "ip": None,
            "country_code": "FR",
            "detected_provider": None,
            "carbon_intensity_g_kwh": 56,
            "efootprint_country": "FRANCE",
            "source": "default",
            "confidence_country": CONFIDENCE_DEFAULT,
            "confidence_provider": CONFIDENCE_DEFAULT,
            "confidence_carbon_intensity": CONFIDENCE_DEFAULT,
            "note": "ipinfo indisponible - France par défaut",
        }

    # --- Détection CDN et ajustement de la confiance pays ---
    # Quand le service est derrière un CDN, l'IP observée est un point de présence
    # (PoP) proche de l'auditeur, pas l'origine du service. Le pays déduit d'ipinfo
    # ne reflète alors pas le vrai pays d'hébergement -> confiance dégradée.
    cdn_detected = False
    cdn_sources = []

    # Signal 1 : catégorie CDN dans la stack technique
    if tech_stack:
        cdn_list = tech_stack.get("categories", {}).get("CDN", [])
        if cdn_list:
            cdn_detected = True
            cdn_sources.append(f"CDN détecté(s) : {', '.join(cdn_list)}.")

    # Signal 2 : en-têtes de cache observés dans le HAR (servers_info multi-infra)
    if servers_info:
        cache_seen_hosts = [s["host"] for s in servers_info if s.get("cache_header_seen")]
        if cache_seen_hosts:
            cdn_detected = True
            cdn_sources.append(f"En-têtes de cache vus ({len(cache_seen_hosts)} host(s)).")

    if cdn_detected:
        server_section["confidence_country"] = CONFIDENCE_LOW
        note_parts = [
            "IP observée probablement un PoP CDN (point de présence proche de l'auditeur), "
            "pas l'origine du service."
        ]
        note_parts.extend(cdn_sources)
        if server_section.get("org"):
            note_parts.append(f"ASN : {server_section['org']}.")
        server_section["country_note"] = " ".join(note_parts)

    # --- Job e-footprint (depuis HAR) ---
    job_section = har_metrics.get("efootprint", {}) if har_metrics else {
        "data_transferred_bytes": 500 * 1024,
        "request_duration_ms": 1000,
        "confidence_data_transferred": CONFIDENCE_DEFAULT,
        "confidence_request_duration": CONFIDENCE_DEFAULT,
        "note": "HAR indisponible - valeurs par défaut",
    }

    # --- Audience (mix pays -> pondération iOS/macOS) ---
    audience_section = {
        "mix": audience["mix"],
        "source": audience["source"],
        "source_url": audience.get("source_url"),
        "confidence": audience["confidence"],
        "ios_share_weighted": audience["ios_share"],
        "macos_share_weighted": audience["macos_share"],
        "per_country": audience["per_country"],
        "ios_share_source": IOS_SHARE_SOURCE,
        "macos_share_source": MACOS_SHARE_SOURCE,
        "note": "Mix pays d'audience utilisé UNIQUEMENT pour pondérer les parts iOS "
                "(mobile) et macOS (desktop) de la correction CrUX. CrUX n'a pas de "
                "dimension géographique ; ce mix ne modifie pas les CWV.",
    }

    # --- Trafic (volume d'audience annuel) ---
    traffic_section = {
        "visits_per_year": traffic["visits_per_year"],
        "monthly_visits": traffic.get("monthly_visits"),
        "source": traffic["source"],
        "source_url": traffic.get("source_url"),
        "snapshot": traffic.get("snapshot"),
        "confidence": traffic["confidence"],
        "note": traffic.get("note"),
    }
    if traffic.get("avg_time_on_page_s") is not None:
        traffic_section["avg_time_on_page_s"] = traffic["avg_time_on_page_s"]

    # --- Croisement techno -> serveur (fiabilisation provider CO2e) ---
    # Si ipinfo n'a pas conclu de provider mais que la détection techno révèle un
    # CDN/hébergeur cloud, on l'utilise comme signal secondaire pour remonter la
    # confiance provider. Le CDN n'écrase pas un provider déjà déterminé par ipinfo.
    if tech_stack and not server_section.get("detected_provider"):
        _cdn_names = [t["name"] for t in tech_stack.get("technologies", [])
                      if t["category"] in ("CDN", "Hébergeur")]
        if _cdn_names:
            server_section["provider_from_tech"] = _cdn_names
            if server_section.get("confidence_provider") in (CONFIDENCE_LOW, CONFIDENCE_DEFAULT):
                server_section["confidence_provider"] = CONFIDENCE_MEDIUM
            server_section["note_provider"] = (
                "Provider non conclu par ipinfo ; CDN/hébergeur détecté(s) via la "
                "stack technique : " + ", ".join(_cdn_names) + "."
            )

    return {
        "schema_version": "1.7",
        "pages": pages if har_metrics else [],
        "har_summary": har_metrics,
        "device_mix": device_section,
        "network_mix": network_section,
        "server": server_section,
        "servers": servers_info or [],
        "audience": audience_section,
        "traffic": traffic_section,
        "job": job_section,
        "tech_stack": tech_stack,
        "ai_external_apis": ai_external_apis or {},
    }


def merge_ai_external_apis(detected, existing, refresh):
    """Fusionne les hosts IA générative détectés avec les réponses déjà données
    par l'utilisatrice (persistées, jamais expirées sauf --refresh explicite).

    `detected` : {host: {"rule_name", "provider"}}, cf.
    detect_tech.ai_generative_hosts_from_har(). `existing` : bloc
    "ai_external_apis" du précédent env-data.json, ou None.

    Une entrée "resolved" (l'utilisatrice a répondu, même "je ne sais pas" ->
    model_name=None) n'est JAMAIS redemandée sauf --refresh : c'est le contrat
    qui permet à l'orchestration du skill de savoir quels hosts questionner
    (resolved=False) sans reposer une question déjà tranchée.
    """
    existing = existing or {}
    merged = {} if refresh else dict(existing)
    for host, info in (detected or {}).items():
        if host in merged:
            merged[host]["rule_name"] = info["rule_name"]
            merged[host]["provider"] = info["provider"]
        else:
            merged[host] = {
                "rule_name": info["rule_name"],
                "provider": info["provider"],
                "resolved": False,
                "model_name": None,
                "output_tokens": None,
            }
    return merged


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Collecte données environnementales pour e-footprint")
    parser.add_argument("source_dir", help="Dossier source contenant le .har")
    parser.add_argument("--refresh", action="store_true",
                        help="Recollecte même si env-data.json existe déjà")
    parser.add_argument("--check", action="store_true",
                        help="Vérifie les clés API sans analyser")
    parser.add_argument("--audience", default=None,
                        help="Mix pays d'audience pour pondérer les parts iOS/macOS de la "
                             "correction CrUX. Formats : liste pondérée 'FR:0.7,US:0.3' ou "
                             "raccourci pays unique 'FR'. Prioritaire sur le mix SimilarWeb "
                             "écrit par l'agent dans env-data.json. Défaut : France (100 %%).")
    parser.add_argument("--ios-mobile-share", type=float, default=None,
                        help="Force la part iOS du parc mobile (0-1), écrase la valeur "
                             "pondérée par --audience. Usage avancé/debug.")
    parser.add_argument("--sw-domain", default=None,
                        help="Force le domaine interrogé sur SimilarWeb (ex. octo.com). "
                             "Sinon déduit de env-data.json/HAR.")
    parser.add_argument("--no-similarweb", action="store_true",
                        help="Désactive l'appel automatique à l'API SimilarWeb "
                             "(mode hors-ligne / éviter le réseau).")
    parser.add_argument("--first-party-host", action="append", default=[],
                        help="Hôte à traiter comme 1st-party même si son domaine "
                             "diffère du site audité (ex. un service auto-hébergé "
                             "sous un autre nom de domaine). Répétable.")
    parser.add_argument("--set-ai-model", nargs=2, metavar=("HOST", "MODEL_NAME"),
                        action="append", default=[],
                        help="Enregistre le modèle IA générative choisi par "
                             "l'utilisatrice pour un host IA détecté (ex. "
                             "--set-ai-model api.anthropic.com claude-sonnet-4-5). "
                             "Utiliser MODEL_NAME=unknown si elle ne connaît pas le "
                             "modèle exact (le host reste alors hors calcul). Répétable.")
    parser.add_argument("--set-ai-output-tokens", nargs=2, metavar=("HOST", "TOKENS"),
                        action="append", default=[],
                        help="Longueur type d'une réponse de ce host, en tokens "
                             "générés (ex. --set-ai-output-tokens api.anthropic.com 300). "
                             "Répétable.")
    args = parser.parse_args()

    # Validation précoce du format --audience (fail fast avant toute collecte réseau)
    if args.audience is not None:
        _mix, _err = parse_audience_spec(args.audience)
        if _err:
            print(f"Erreur : --audience : {_err}")
            sys.exit(1)
    if args.ios_mobile_share is not None and not 0.0 <= args.ios_mobile_share < 1.0:
        print(f"Erreur : --ios-mobile-share doit être dans [0, 1[ (reçu : {args.ios_mobile_share})")
        sys.exit(1)

    source_dir = Path(args.source_dir).resolve()
    if not source_dir.exists():
        print(f"Erreur : dossier introuvable : {source_dir}")
        sys.exit(1)

    project_root = find_project_root(source_dir)
    env = load_env(project_root)
    google_key = env.get("GOOGLE_API_KEY")
    ipinfo_token = env.get("IPINFO_TOKEN")

    # --- Mode --check ---
    if args.check:
        print("[check] Vérification des clés API disponibles...")
        print(f"  GOOGLE_API_KEY : {'OK' if google_key else 'ABSENTE (CrUX désactivé)'}")
        print(f"  IPINFO_TOKEN   : {'OK' if ipinfo_token else 'ABSENTE (mode anonyme, 50k/mois max)'}")

        if google_key:
            from urllib.parse import urlparse
            test_url = "https://www.google.com"
            print(f"\n[check] Test CrUX sur {test_url}...")
            mix = collect_device_mix(test_url, google_key)
            if mix:
                print(f"  -> OK : desktop={mix['desktop']:.0%} phone={mix['phone']:.0%}")
            else:
                print("  -> ECHEC : vérifier que Chrome UX Report API est activée")
                print("    https://console.cloud.google.com/apis/library/chromeuxreport.googleapis.com")

        if ipinfo_token:
            print("\n[check] Test ipinfo.io...")
            info = call_ipinfo("8.8.8.8", ipinfo_token)
            if info:
                print(f"  -> OK : {info.get('org', '')} ({info.get('country', '')})")
            else:
                print("  -> ECHEC : vérifier le token ipinfo.io")
        return

    # --- Vérification cache ---
    env_data_path = source_dir / "env-data.json"
    if env_data_path.exists() and not args.refresh:
        print(f"[collect_env_data] env-data.json existe déjà dans {source_dir.name}/")
        print("  Utiliser --refresh pour forcer la recollecte.")
        with open(env_data_path, encoding="utf-8") as f:
            existing = json.load(f)
        print(f"  Pages : {len(existing.get('pages', []))}")
        s = existing.get("server", {})
        print(f"  Serveur : {s.get('country_code', '?')} / {s.get('detected_provider', 'inconnu')}")
        d = existing.get("device_mix", {})
        print(f"  Device mix : desktop={d.get('desktop_fraction', '?'):.0%} "
              f"phone={d.get('phone_fraction', '?'):.0%} (source: {d.get('source', '?')})")
        return

    # --- Collecte HAR ---
    print("[1/3] Extraction HAR...")
    har_path = find_har(source_dir)
    if not har_path:
        print(f"  AVERTISSEMENT : aucun .har trouvé dans {source_dir}")
        print("  Les métriques de page seront remplacées par des valeurs par défaut.")
        pages, server_ip = [], None
    else:
        print(f"  Fichier : {har_path.name}")
        pages, server_ip = extract_har_data(har_path)
        print(f"  Pages : {len(pages)}")
        for p in pages:
            print(f"    [{p['page_id']}] {p['url'][:60]} — {p['size_kb']} Ko, {p['on_load_ms']} ms")
        if server_ip:
            print(f"  IP serveur principale : {server_ip}")

    # --- Collecte CrUX ---
    print("\n[2/3] Collecte répartition device (CrUX)...")
    device_mix = None
    if google_key and pages:
        # Utiliser l'URL de la première page comme représentante de l'origine
        first_url = pages[0]["url"] if pages else None
        if first_url:
            device_mix = collect_device_mix(first_url, google_key)
            if device_mix:
                print(f"  -> desktop={device_mix['desktop']:.0%} "
                      f"phone={device_mix['phone']:.0%} "
                      f"tablet={device_mix.get('tablet', 0):.0%} "
                      f"(source: {device_mix['source']})")
            else:
                print("  -> Aucune donnée CrUX disponible — valeurs par défaut utilisées")
    elif not google_key:
        print("  GOOGLE_API_KEY absente — valeurs par défaut (60% mobile, 40% desktop)")
        print(f"  (Pour activer : ajouter GOOGLE_API_KEY dans {project_root}/.env)")
    else:
        print("  Pas d'URL disponible depuis le HAR")

    # --- Collecte ipinfo ---
    print("\n[3/3] Géolocalisation serveur (ipinfo.io)...")
    server_info = None
    if server_ip:
        if not ipinfo_token:
            print("  IPINFO_TOKEN absent — mode anonyme (limite 50k req/mois)")
            print(f"  (Pour activer : ajouter IPINFO_TOKEN dans {project_root}/.env)")
        server_info = collect_server_info(server_ip, ipinfo_token)
        if server_info:
            provider = server_info["detected_provider"] or "inconnu"
            print(f"  -> {server_info['country_code']} ({server_info['city']}) "
                  f"/ {provider} — {server_info['carbon_intensity_g_kwh']} g CO2/kWh")
        else:
            print("  -> Echec ipinfo — France / provider inconnu par défaut")
    else:
        print("  Aucune IP serveur détectée dans le HAR")

    # --- Géolocalisation de CHAQUE infrastructure 1st-party (Lot 3) ---
    # Un site peut révéler plusieurs infras 1st-party distinctes dans le HAR
    # (ex. ANTS : 3 serveurs). server_info ci-dessus ne géolocalise que la
    # principale ; ce bloc complète pour les autres.
    print("\n[infras] Géolocalisation de chaque infrastructure 1st-party...")
    servers_info = []
    audited_domain = similarweb_api.infer_domain(source_dir) if similarweb_api else None
    if har_path and audited_domain and detect_infrastructures:
        servers_info = collect_multi_server_info(
            har_path, audited_domain,
            first_party_extra=args.first_party_host, token=ipinfo_token)
        if len(servers_info) > 1:
            for s in servers_info:
                tag = "principale" if s["is_primary"] else "secondaire"
                provider = s["detected_provider"] or "inconnu"
                print(f"  -> [{tag}] {s['host']} : {s['country_code'] or '?'} / "
                      f"{provider} ({s['transferred_bytes']:,} octets, "
                      f"{s['request_count']} requêtes)".replace(",", " "))
        elif servers_info:
            print("  -> une seule infra 1st-party détectée (identique à la principale)")
        else:
            print("  -> détection indisponible (HAR absent ou domaine introuvable)")
    else:
        print("  -> ignoré (HAR, domaine audité ou détection d'infras indisponible)")

    # --- Détection de la stack technique (règles maison sur le HAR) ---
    print("\n[techno] Détection de la stack technique (règles maison)...")
    tech_stack = None
    if har_path and detect_tech:
        tech_stack = detect_tech.detect_from_har(har_path)
        if tech_stack and tech_stack.get("technologies"):
            cats = tech_stack.get("categories", {})
            print(f"  -> {len(tech_stack['technologies'])} technologie(s) "
                  f"dans {len(cats)} catégorie(s) : "
                  + ", ".join(f"{c} ({len(names)})" for c, names in cats.items()))
        else:
            print("  -> Aucune technologie détectée")
    elif not detect_tech:
        print("  Module detect_tech absent — détection ignorée")
    else:
        print("  Pas de HAR — détection ignorée")

    # --- Détection des hosts IA générative tierce (résolution : voir plus bas) ---
    print("\n[ia] Détection des hosts IA générative tierce (règles maison)...")
    ai_hosts_detected = {}
    if har_path and detect_tech:
        ai_hosts_detected = detect_tech.ai_generative_hosts_from_har(har_path) or {}
        if ai_hosts_detected:
            print(f"  -> {len(ai_hosts_detected)} host(s) IA détecté(s) : "
                  + ", ".join(f"{h} ({i['rule_name']})" for h, i in ai_hosts_detected.items()))
        else:
            print("  -> Aucun host IA générative détecté")
    else:
        print("  -> ignoré (HAR ou module detect_tech indisponible)")

    # --- Résolution du mix pays d'audience (points 4a/4b) ---
    # Ordre : --audience > audience_mix déjà écrit par l'agent (SimilarWeb) > défaut FR.
    # Sur --refresh on préserve le bloc audience de l'agent s'il existe déjà.
    print("\n[audience] Résolution du mix pays (pondération iOS/macOS)...")
    existing_audience = None
    existing_traffic = None
    existing_ai_external_apis = None
    if env_data_path.exists():
        try:
            with open(env_data_path, encoding="utf-8") as f:
                _prev = json.load(f)
            existing_audience = _prev.get("audience")
            existing_traffic = _prev.get("traffic")
            existing_ai_external_apis = _prev.get("ai_external_apis")
        except (json.JSONDecodeError, OSError):
            existing_audience = None
            existing_traffic = None
            existing_ai_external_apis = None

    ai_external_apis = merge_ai_external_apis(
        ai_hosts_detected, existing_ai_external_apis, refresh=args.refresh)

    # Réponses de l'utilisatrice, collectées par l'orchestration du skill via
    # AskUserQuestion PUIS repassées ici en CLI (même mécanisme que --audience/
    # --ios-mobile-share ci-dessus) : ce script ne pose jamais de question lui-même.
    for host, model_name in args.set_ai_model:
        entry = ai_external_apis.setdefault(
            host, {"rule_name": None, "provider": None, "output_tokens": None})
        entry["model_name"] = None if model_name.lower() == "unknown" else model_name
        entry["resolved"] = True
    for host, tokens in args.set_ai_output_tokens:
        entry = ai_external_apis.setdefault(
            host, {"rule_name": None, "provider": None, "model_name": None, "resolved": False})
        entry["output_tokens"] = float(tokens)
    if ai_external_apis:
        _resolved = sum(1 for v in ai_external_apis.values() if v.get("resolved"))
        print(f"\n[ia] {len(ai_external_apis)} host(s) IA suivis, {_resolved} résolu(s) "
              f"(modèle connu ou explicitement inconnu)")

    # Voie principale : compléter les blocs manquants via l'API interne SimilarWeb.
    # La saisie manuelle (--audience) prime et bloque l'écriture du mix pays.
    if not args.no_similarweb:
        existing_audience, existing_traffic = maybe_fetch_similarweb(
            source_dir, existing_audience, existing_traffic,
            cli_audience=args.audience, sw_domain=args.sw_domain)

    audience = resolve_audience(args.audience, existing_audience, ios_override=args.ios_mobile_share)
    if audience.get("error"):
        print(f"  Erreur : {audience['error']}")
        sys.exit(1)
    if audience.get("warning"):
        print(f"  ⚠ {audience['warning']}")
    mix_str = ", ".join(f"{cc} {w:.0%}" for cc, w in audience["mix"].items())
    print(f"  Mix pays : {mix_str}  (source : {audience['source']})")
    print(f"  -> part iOS pondérée {audience['ios_share']:.0%}, "
          f"macOS pondérée {audience['macos_share']:.0%}")

    # --- Résolution du volume de trafic (préserve le bloc écrit par l'agent) ---
    # Le script ne collecte jamais le trafic (aucune API publique fiable) : il
    # préserve le bloc 'traffic' SimilarWeb écrit par l'agent, ou pose la baseline.
    print("\n[trafic] Résolution du volume d'audience annuel...")
    traffic = resolve_traffic(existing_traffic)
    if traffic.get("warning"):
        print(f"  ⚠ {traffic['warning']}")
    print(f"  Trafic : {traffic['visits_per_year']:,} visites/an  (source : {traffic['source']})")

    # --- Assemblage env-data.json ---
    env_data = build_env_data((pages, server_ip), device_mix, server_info,
                              audience=audience, traffic=traffic,
                              tech_stack=tech_stack, servers_info=servers_info,
                              ai_external_apis=ai_external_apis)

    with open(env_data_path, "w", encoding="utf-8") as f:
        json.dump(env_data, f, ensure_ascii=False, indent=2)

    print(f"\n[OK] env-data.json écrit : {env_data_path}")

    # Résumé des inputs e-footprint
    job = env_data.get("job", {})
    server = env_data.get("server", {})
    device = env_data.get("device_mix", {})
    print("\nRésumé inputs e-footprint :")
    print(f"  Job.data_transferred  : {job.get('data_transferred_bytes', 0) // 1024} kB "
          f"[{job.get('confidence_data_transferred', '?')}]")
    print(f"  Job.request_duration  : {job.get('request_duration_ms', 0)} ms "
          f"[{job.get('confidence_request_duration', '?')}]")
    print(f"  Country               : {server.get('efootprint_country', '?')} "
          f"({server.get('carbon_intensity_g_kwh', '?')} g/kWh) "
          f"[{server.get('confidence_country', '?')}]")
    print(f"  Provider              : {server.get('detected_provider') or 'non détecté'} "
          f"[{server.get('confidence_provider', '?')}]")
    print(f"  Device mobile/desktop : {device.get('phone_fraction', 0):.0%} / "
          f"{device.get('desktop_fraction', 0):.0%} "
          f"[{device.get('confidence', '?')}]")
    if device.get("mobile_fraction_raw") is not None:
        print(f"    (brut CrUX mobile={device.get('mobile_fraction_raw', 0):.0%}, "
              f"corrigé iOS {device.get('ios_share_used', 0):.0%} "
              f"+ macOS {device.get('macos_share_used', 0):.0%} "
              f"-> mobile={device.get('mobile_fraction_corrected', 0):.0%})")


if __name__ == "__main__":
    main()
