#!/usr/bin/env python3
"""
Récupération trafic + mix pays via l'API interne de l'extension SimilarWeb.

Contrairement au scraping de la page publique (bloquée par captcha AWS WAF),
l'extension Chrome/Firefox SimilarWeb interroge une API interne qui répond sans
authentification : ni cookie, ni compte, ni session. Il suffit d'envoyer les
mêmes en-têtes que l'extension (un vrai User-Agent de navigateur + la version
d'extension) et de NE PAS envoyer d'en-tête Origin (CloudFront la rejette -> 403).

Diagnostic validé en juillet 2026 : le 403 documenté auparavant venait d'un
mauvais en-tête (`Origin: chrome-extension://...`) et d'un User-Agent non
navigateur, pas d'un manque de cookies. Corrigés, l'appel répond 200 depuis un
simple client HTTP.

Ce module est SÉPARÉ de collect_env_data.py à dessein : ce dernier ne récupère
jamais lui-même le trafic ni le mix pays (il ne fait que valider/normaliser les
blocs 'audience' et 'traffic' présents dans env-data.json). Ce module écrit ces
deux blocs dans env-data.json, au format exact attendu par resolve_audience() et
resolve_traffic(), puis on relance `collect_env_data.py <dir> --refresh` pour
qu'ils soient normalisés et intégrés au calcul CO2e.

Usage :
    python3 similarweb_api.py <source_dir>                  # domaine déduit de env-data.json/HAR
    python3 similarweb_api.py <source_dir> --domain octo.com
    python3 similarweb_api.py <source_dir> --print-only     # affiche le JSON API, n'écrit rien

Voie de repli : si l'API échoue (403 réapparu, réseau, domaine inconnu de
SimilarWeb), le module sort en code != 0 avec un message clair. L'appelant
retombe alors sur la récupération assistée (SKILL.md Étape 20d).
"""

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


# Endpoint interne de l'extension (cf. background.js décompilé du .crx).
# Pour refaire la découverte si l'extension change (endpoint/en-tête/version),
# voir documentation/implementation/similarweb_reconstitution.md
DATA_API = "https://data.similarweb.com/api/v1/data"

# Sous-dossier optionnel où ranger les captures brutes (HAR, Coverage), dans .gitignore.
RAW_DATA_DIR = "donnees-brutes-potentiellement-sensibles"

# Version d'extension envoyée dans l'en-tête X-Extension-Version. À revalider si
# l'API se met à renvoyer 403 : installer/mettre à jour l'extension, recapturer
# la version courante (chrome://extensions -> carte SimilarWeb).
EXTENSION_VERSION = "6.12.21"

# User-Agent d'un vrai navigateur : indispensable. Sans lui (ou avec l'UA par
# défaut d'un client HTTP), CloudFront répond 403.
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
)

CONFIDENCE_MEDIUM = "medium"

_MONTHS_FR = {
    1: "janvier", 2: "février", 3: "mars", 4: "avril", 5: "mai", 6: "juin",
    7: "juillet", 8: "août", 9: "septembre", 10: "octobre", 11: "novembre",
    12: "décembre",
}


# ---------------------------------------------------------------------------
# Appel API
# ---------------------------------------------------------------------------

def fetch_domain_data(domain, version=EXTENSION_VERSION, timeout=15):
    """Interroge l'API interne SimilarWeb pour un domaine.

    Retourne (data_dict, None) en cas de succès, (None, message_erreur) sinon.
    N'envoie AUCUN en-tête Origin et un vrai User-Agent navigateur (les deux
    conditions du succès). Aucun cookie n'est nécessaire.
    """
    domain = (domain or "").strip().lower()
    if not domain:
        return None, "domaine vide"
    # Nettoyage : on veut un domaine nu (pas d'URL, pas de www.)
    if "://" in domain:
        domain = urllib.parse.urlparse(domain).netloc or domain
    domain = domain.split("/")[0]
    if domain.startswith("www."):
        domain = domain[4:]

    url = DATA_API + "?" + urllib.parse.urlencode({"domain": domain})
    req = urllib.request.Request(
        url,
        headers={
            "Content-Type": "application/json",
            "X-Extension-Version": version,
            "User-Agent": BROWSER_USER_AGENT,
            "Accept": "*/*",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        if e.code == 403:
            return None, ("403 CloudFront : en-têtes rejetés ou API durcie. "
                          "Vérifier User-Agent navigateur + absence d'en-tête Origin, "
                          "ou revalider la version d'extension. Repli : Étape 20d assistée.")
        return None, f"HTTP {e.code} : {e.reason}"
    except Exception as e:
        return None, f"erreur réseau : {e}"

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None, f"réponse non-JSON (extrait : {raw[:120]!r})"

    if not isinstance(data, dict) or not data.get("SiteName"):
        return None, "domaine absent de SimilarWeb ou réponse vide (pas de SiteName)"
    return data, None


# ---------------------------------------------------------------------------
# Transformation -> blocs env-data.json
# ---------------------------------------------------------------------------

def build_audience_block(data, source_url):
    """Construit le bloc 'audience' au format attendu par resolve_audience().

    Reprend TopCountryShares (part de trafic par pays). Retourne None si absent.
    """
    shares = data.get("TopCountryShares") or []
    mix = {}
    for entry in shares:
        cc = (entry.get("CountryCode") or "").upper()
        val = entry.get("Value")
        if cc and isinstance(val, (int, float)) and val > 0:
            mix[cc] = mix.get(cc, 0.0) + float(val)
    if not mix:
        return None
    # Renormalise (les Top Countries ne somment pas à 1 : reste du monde ignoré).
    total = sum(mix.values())
    mix = {cc: round(w / total, 4) for cc, w in mix.items()}
    return {
        "mix": mix,
        # Libellé neutre affiché dans le rapport (n'expose pas la méthode technique
        # d'accès, cf. documentation/implementation/similarweb_api.md).
        "source": "SimilarWeb (estimation)",
        "source_url": source_url,
        "confidence": CONFIDENCE_MEDIUM,
    }


def _snapshot_label(data):
    """Libellé lisible du mois de référence, ex. 'juin 2026'. None si absent."""
    eng = data.get("Engagments") or {}
    try:
        month = int(eng.get("Month"))
        year = int(eng.get("Year"))
    except (TypeError, ValueError):
        return None
    return f"{_MONTHS_FR.get(month, str(month))} {year}"


def build_traffic_block(data, source_url):
    """Construit le bloc 'traffic' au format attendu par resolve_traffic().

    Base : le mois le plus récent d'EstimatedMonthlyVisits (repli Engagments.Visits),
    annualisé x12 pour rester cohérent avec monthly_visits (visits_per_year =
    monthly_visits x 12). Retourne None si aucune donnée de visites.
    """
    monthly = None
    emv = data.get("EstimatedMonthlyVisits") or {}
    if isinstance(emv, dict) and emv:
        # Clés = dates 'YYYY-MM-01' ; on prend la plus récente.
        latest_key = max(emv.keys())
        try:
            monthly = int(round(float(emv[latest_key])))
        except (TypeError, ValueError):
            monthly = None
    if not monthly:
        try:
            monthly = int(round(float((data.get("Engagments") or {}).get("Visits"))))
        except (TypeError, ValueError):
            monthly = None
    if not monthly or monthly <= 0:
        return None

    visits_per_year = int(round(monthly * 12 / 1000.0)) * 1000  # arrondi au millier
    return {
        "visits_per_year": visits_per_year,
        "monthly_visits": monthly,
        # Libellé neutre (voir build_audience_block).
        "source": "SimilarWeb (estimation)",
        "source_url": source_url,
        "snapshot": _snapshot_label(data),
        "confidence": CONFIDENCE_MEDIUM,
    }


# ---------------------------------------------------------------------------
# Déduction du domaine + fusion env-data.json
# ---------------------------------------------------------------------------

def _host_from_url(url):
    if not url:
        return None
    if "://" not in url:
        url = "http://" + url
    host = urllib.parse.urlparse(url).netloc
    if host.startswith("www."):
        host = host[4:]
    return host or None


def infer_domain(source_dir):
    """Déduit le domaine audité depuis env-data.json (pages[0].url) puis le HAR.
    Retourne le domaine nu (sans www.) ou None."""
    env_path = source_dir / "env-data.json"
    if env_path.exists():
        try:
            with open(env_path, encoding="utf-8") as f:
                env = json.load(f)
            pages = env.get("pages") or []
            if pages:
                host = _host_from_url(pages[0].get("url"))
                if host:
                    return host
        except (json.JSONDecodeError, OSError):
            pass
    # Repli : premier .har du dossier, title de la première page.
    hars = list(source_dir.glob("*.har")) or list(
        (source_dir / RAW_DATA_DIR).glob("*.har"))
    if hars:
        try:
            with open(hars[0], encoding="utf-8") as f:
                har = json.load(f)
            for page in har.get("log", {}).get("pages", []):
                host = _host_from_url(page.get("title"))
                if host:
                    return host
        except (json.JSONDecodeError, OSError):
            pass
    return None


def merge_into_env_data(source_dir, audience_block, traffic_block):
    """Écrit/actualise les blocs 'audience' et 'traffic' dans env-data.json.

    Si le fichier existe, on préserve tout le reste (HAR, device, serveur…) et on
    ne remplace que ces deux blocs. Sinon on crée un fichier minimal : le run
    `collect_env_data.py --refresh` suivant complétera HAR/CrUX/ipinfo tout en
    relisant ces blocs (resolve_audience/resolve_traffic).
    """
    env_path = source_dir / "env-data.json"
    if env_path.exists():
        with open(env_path, encoding="utf-8") as f:
            env = json.load(f)
    else:
        env = {}
    if audience_block:
        env["audience"] = audience_block
    if traffic_block:
        env["traffic"] = traffic_block
    with open(env_path, "w", encoding="utf-8") as f:
        json.dump(env, f, ensure_ascii=False, indent=2)
    return env_path


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Récupère trafic + mix pays via l'API interne SimilarWeb "
                    "et écrit les blocs audience/traffic dans env-data.json.")
    parser.add_argument("source_dir", help="Dossier source (contenant env-data.json et/ou le .har)")
    parser.add_argument("--domain", default=None,
                        help="Domaine à interroger (ex. octo.com). Déduit de "
                             "env-data.json/HAR si omis.")
    parser.add_argument("--version", default=EXTENSION_VERSION,
                        help=f"Version d'extension (en-tête X-Extension-Version). "
                             f"Défaut : {EXTENSION_VERSION}.")
    parser.add_argument("--print-only", action="store_true",
                        help="Affiche le JSON brut de l'API et n'écrit rien.")
    args = parser.parse_args()

    source_dir = Path(args.source_dir).resolve()
    if not source_dir.exists():
        print(f"Erreur : dossier introuvable : {source_dir}")
        sys.exit(1)

    domain = args.domain or infer_domain(source_dir)
    if not domain:
        print("Erreur : domaine introuvable. Préciser --domain (ex. --domain octo.com).")
        sys.exit(1)

    print(f"[similarweb] Interrogation API interne pour : {domain}")
    data, err = fetch_domain_data(domain, version=args.version)
    if err:
        print(f"  ECHEC : {err}")
        print("  -> Repli attendu : récupération assistée (SKILL.md Étape 20d).")
        sys.exit(2)

    if args.print_only:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return

    source_url = f"https://www.similarweb.com/website/{domain}/"
    audience_block = build_audience_block(data, source_url)
    traffic_block = build_traffic_block(data, source_url)

    if not audience_block and not traffic_block:
        print("  ECHEC : réponse API sans TopCountryShares ni visites exploitables.")
        print("  -> Repli attendu : récupération assistée (SKILL.md Étape 20d).")
        sys.exit(2)

    if audience_block:
        mix_str = ", ".join(f"{cc} {w:.0%}" for cc, w in audience_block["mix"].items())
        print(f"  Mix pays : {mix_str}")
    else:
        print("  ⚠ Pas de mix pays (TopCountryShares absent) : bloc audience non écrit.")

    if traffic_block:
        snap = traffic_block.get("snapshot") or "?"
        print(f"  Trafic : {traffic_block['monthly_visits']:,}/mois ({snap}) "
              f"-> {traffic_block['visits_per_year']:,}/an")
    else:
        print("  ⚠ Pas de volume de visites : bloc traffic non écrit.")

    env_path = merge_into_env_data(source_dir, audience_block, traffic_block)
    print(f"\n[OK] Blocs écrits dans : {env_path}")
    print(f"     Relancer ensuite : python3 collect_env_data.py \"{source_dir}\" --refresh")


if __name__ == "__main__":
    main()
