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


CRUX_API = "https://chromeuxreport.googleapis.com/v1/records:queryRecord"
IPINFO_API = "https://ipinfo.io/{ip}/json"

# Clés de confiance pour le JSON de sortie
CONFIDENCE_HIGH = "high"       # donnée collectée, fiable
CONFIDENCE_MEDIUM = "medium"   # collectée mais incertaine
CONFIDENCE_LOW = "low"         # estimée ou valeur par défaut
CONFIDENCE_DEFAULT = "default"  # valeur par défaut de la librairie


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
    hars = list(source_dir.glob("*.har"))
    if len(hars) == 1:
        return hars[0]
    if len(hars) > 1:
        print(f"[HAR] Plusieurs .har trouvés, utilisation de : {hars[0].name}")
        return hars[0]
    return None


def extract_har_data(har_path):
    """
    Extrait depuis le HAR :
      - pages : liste de {url, size_bytes, on_load_ms}
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
        size_bytes = sum(
            e.get("response", {}).get("content", {}).get("size", 0)
            for e in page_entries
        )

        pages.append({
            "page_id": pid,
            "url": url,
            "size_bytes": size_bytes,
            "size_kb": round(size_bytes / 1024, 1),
            "on_load_ms": round(on_load_ms),
            "request_count": len(page_entries),
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

    return {
        "pages_count": len(pages),
        "heaviest_page_url": heaviest["url"],
        "heaviest_page_size_bytes": heaviest["size_bytes"],
        "avg_size_bytes": round(avg_size_bytes),
        "avg_size_kb": round(avg_size_bytes / 1024, 1),
        "avg_on_load_ms": round(avg_on_load_ms / n_with_load) if n_with_load else 0,
        # Inputs e-footprint recommandés (page représentative = plus lourde)
        "efootprint": {
            "data_transferred_bytes": heaviest["size_bytes"],
            "request_duration_ms": heaviest["on_load_ms"] or round(avg_on_load_ms / n_with_load) if n_with_load else 1000,
            "confidence_data_transferred": CONFIDENCE_HIGH,
            "confidence_request_duration": CONFIDENCE_HIGH if heaviest["on_load_ms"] > 0 else CONFIDENCE_MEDIUM,
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


def infer_network_mix(device_mix):
    """
    Infère le mix wifi/mobile depuis la répartition device.
    Hypothèse : phones = mobile network, desktop/tablet = wifi.
    """
    if not device_mix:
        return None
    mobile_fraction = device_mix.get("phone", 0.6)
    return {
        "wifi": round(1 - mobile_fraction, 3),
        "mobile": round(mobile_fraction, 3),
        "source": "inferred_from_device_mix",
    }


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


# ---------------------------------------------------------------------------
# Construction env-data.json
# ---------------------------------------------------------------------------

def build_env_data(har_data, device_mix, server_info):
    """
    Assemble env-data.json depuis les données collectées.
    Chaque section indique les inputs e-footprint et leur niveau de confiance.
    """
    pages, _ = har_data if isinstance(har_data, tuple) else (har_data, None)
    har_metrics = aggregate_page_metrics(pages)

    # --- Device mix ---
    if device_mix:
        device_section = {
            "phone_fraction": device_mix["phone"],
            "desktop_fraction": device_mix["desktop"],
            "tablet_fraction": device_mix.get("tablet", 0.0),
            "source": device_mix["source"],
            "confidence": CONFIDENCE_HIGH,
        }
        network_mix = infer_network_mix(device_mix)
    else:
        device_section = {
            "phone_fraction": 0.6,
            "desktop_fraction": 0.4,
            "tablet_fraction": 0.0,
            "source": "default",
            "confidence": CONFIDENCE_DEFAULT,
            "note": "CrUX indisponible - valeurs par défaut (60% mobile, 40% desktop)",
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

    # --- Job e-footprint (depuis HAR) ---
    job_section = har_metrics.get("efootprint", {}) if har_metrics else {
        "data_transferred_bytes": 500 * 1024,
        "request_duration_ms": 1000,
        "confidence_data_transferred": CONFIDENCE_DEFAULT,
        "confidence_request_duration": CONFIDENCE_DEFAULT,
        "note": "HAR indisponible - valeurs par défaut",
    }

    return {
        "schema_version": "1.0",
        "pages": pages if har_metrics else [],
        "har_summary": har_metrics,
        "device_mix": device_section,
        "network_mix": network_section,
        "server": server_section,
        "job": job_section,
    }


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
    args = parser.parse_args()

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

    # --- Assemblage env-data.json ---
    env_data = build_env_data((pages, server_ip), device_mix, server_info)

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
    print(f"  Device phone/desktop  : {device.get('phone_fraction', 0):.0%} / "
          f"{device.get('desktop_fraction', 0):.0%} "
          f"[{device.get('confidence', '?')}]")


if __name__ == "__main__":
    main()
