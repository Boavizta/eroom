#!/usr/bin/env python3
"""
Phase 3 - Estimation CO2e d'un site web via e-footprint (Boavizta).

IMPORTANT : Toutes les valeurs affichées sont des ESTIMATIONS HYPOTHÉTIQUES.
Elles sont calculées à partir de données collectées automatiquement (HAR, CrUX,
ipinfo) et de nombreuses hypothèses par défaut. Ces résultats ne constituent
pas une mesure réelle de l'impact environnemental du site.

Usage :
    python3 run_efootprint.py <source_dir>
    python3 run_efootprint.py <source_dir> --visits 500000      # trafic annuel
    python3 run_efootprint.py <source_dir> --instance t3.large  # instance (nom propre
                                                                # au provider détecté)
    python3 run_efootprint.py <source_dir> --refresh-data       # recollecte env-data.json

Lit env-data.json dans source_dir (produit par collect_env_data.py).
Écrit efootprint-model.json dans source_dir (relançabilité).
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent


# ---------------------------------------------------------------------------
# Chargement données
# ---------------------------------------------------------------------------

def load_env_data(source_dir):
    path = source_dir / "env-data.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def ensure_env_data(source_dir, refresh=False):
    """Lance collect_env_data.py si env-data.json absent ou --refresh-data."""
    collect_script = SCRIPTS_DIR / "collect_env_data.py"
    cmd = [sys.executable, str(collect_script), str(source_dir)]
    if refresh:
        cmd.append("--refresh")

    env_data_path = source_dir / "env-data.json"
    if not env_data_path.exists() or refresh:
        print("[collect] Lancement collect_env_data.py...")
        result = subprocess.run(cmd)
        if result.returncode != 0:
            print("[collect] Échec de la collecte, arrêt.")
            sys.exit(1)


DEFAULT_VISITS_PER_YEAR = 100_000

# Nom du provider tel qu'il est détecté par collect_env_data.py -> nom attendu par
# e-footprint. Sans cette table, un provider bien détecté fait planter le calcul :
# le script entrait dans la branche Boavizta avec "ovh", qu'e-footprint refuse
# (il attend "ovhcloud"), et le repli "serveur générique" ne se déclenchait jamais.
# Cas rencontré sur un site hébergé chez OVH.
PROVIDER_ALIASES = {"ovh": "ovhcloud"}

# Instance à supposer quand aucune n'est fournie, PAR PROVIDER. Un seul défaut
# global est impossible : les noms d'instances sont propres à chaque provider
# ("t3.medium" n'existe pas chez ovhcloud, qui attend "c3-4" ou "b3-8").
# Gabarit retenu : 2 vCPU / 4 GB, hypothèse de petite production. Chaque valeur
# est l'instance du catalogue Boavizta du provider la plus proche de ce gabarit,
# égalité tranchée par ordre alphabétique (aucun sens physique, mais stable).
# EXCEPTION ASSUMÉE pour aws : "t3.medium", le choix historique du script, fait
# exactement 2 vCPU / 4 GB et satisfait donc la règle. L'alphabétique aurait
# désigné "a1.large", du matériel ARM metal dont la fabrication est 3,5 fois
# plus lourde (9,49 contre 2,66 kg CO2e/an sur le cas de test) : cela aurait
# déplacé un total déjà publié sans rien mesurer de mieux.
# La confiance associée reste "défaut script" : c'est une hypothèse, pas une mesure.
DEFAULT_INSTANCE_BY_PROVIDER = {
    "aws":      "t3.medium",      # 2 vCPU / 4 GB
    "azure":    "f2s_v2",         # 2 vCPU / 4 GB
    "gcp":      "c2d-highcpu-2",  # 2 vCPU / 4 GB
    "ovhcloud": "c3-4",           # 2 vCPU / 4 GB
    "scaleway": "play2-nano",     # 2 vCPU / 4 GB
}


def normalize_provider(detected):
    """Nom e-footprint du provider détecté, ou None si non modélisable en cloud.

    Ne renvoie un nom que si e-footprint le connaît RÉELLEMENT : la liste est lue
    dans la librairie, pas recopiée, pour qu'elle ne se périme pas en silence.
    L'appelant retombe sur un serveur générique quand la réponse est None.
    """
    if not detected:
        return None
    name = PROVIDER_ALIASES.get(detected, detected)
    try:
        from efootprint.builders.hardware.boavizta_cloud_server import (
            all_boavizta_cloud_providers)
    except ImportError:
        return None
    return name if name in {p.value for p in all_boavizta_cloud_providers} else None


def resolve_instance_type(cli_instance, provider):
    """(type d'instance, fourni_par_l_utilisateur).

    Une instance passée en ligne de commande est retenue telle quelle : c'est une
    information sur l'hébergement réel, le script n'a pas à la corriger. Sinon la
    valeur vient de la table par provider.
    """
    if cli_instance:
        return cli_instance, True
    return DEFAULT_INSTANCE_BY_PROVIDER.get(provider, "t3.medium"), False


def resolve_visits(cli_visits, env_data):
    """Résout le trafic annuel et sa provenance selon l'ordre de priorité :
      1. --visits saisi en CLI (analytics client, le plus fiable) ;
      2. bloc 'traffic' d'env-data.json (estimation SimilarWeb écrite par l'agent) ;
      3. baseline 100 000 visites/an + avertissement.

    Retourne (visits, meta) où meta = {source, source_url, snapshot, confidence,
    note, warning?} pour la traçabilité (console, JSON, rapport HTML).

    Cas particulier : si --visits reprend exactement la valeur déjà tracée dans le
    bloc 'traffic' (ex. proposée par défaut à l'utilisateur puis validée telle quelle),
    on hérite de sa provenance (source/source_url/snapshot) au lieu de l'écraser par
    le libellé générique "saisie manuelle" — sinon le lien "↗ source" SimilarWeb
    disparaît du rapport alors que la valeur en vient réellement.
    """
    traffic = (env_data or {}).get("traffic") or {}
    traffic_visits = traffic.get("visits_per_year")
    traffic_is_sourced = bool(traffic_visits) and traffic.get("source") not in (None, "default")

    def _meta_from_traffic_block():
        return {
            "source": traffic.get("source", "SimilarWeb (estimation)"),
            "source_url": traffic.get("source_url"),
            "snapshot": traffic.get("snapshot"),
            "confidence": traffic.get("confidence", "medium"),
            "note": traffic.get("note"),
            "warning": None,
        }

    if cli_visits is not None:
        if traffic_is_sourced and int(traffic_visits) == int(cli_visits):
            return cli_visits, _meta_from_traffic_block()
        return cli_visits, {
            "source": "saisie manuelle (--visits)",
            "source_url": None,
            "snapshot": None,
            "confidence": "medium",
            "note": "Trafic saisi en ligne de commande (analytics client ou hypothèse explicite). "
                    "Le CO2e total croît avec le trafic (au-dessus d'un socle fixe fabrication serveur + stockage) ; le CO2e/visite diminue quand le trafic augmente.",
            "warning": None,
        }

    if traffic_is_sourced:
        return int(traffic_visits), _meta_from_traffic_block()

    return DEFAULT_VISITS_PER_YEAR, {
        "source": "default",
        "source_url": None,
        "snapshot": None,
        "confidence": "default",
        "note": "Aucune source de trafic fournie : baseline 100 000 visites/an. "
                "Le CO2e total croît avec le trafic (au-dessus d'un socle fixe fabrication serveur + stockage) ; le CO2e/visite diminue quand le trafic augmente.",
        "warning": ("Trafic non fourni : baseline 100 000 visites/an par défaut. "
                    "Passer --visits (analytics client) ou laisser l'agent écrire un bloc "
                    "'traffic' SimilarWeb dans env-data.json pour une estimation sourcée."),
    }


# ---------------------------------------------------------------------------
# Affichage résumé des hypothèses
# ---------------------------------------------------------------------------

CONFIDENCE_LABELS = {
    "high":               "collecté  ",
    "medium":             "estimé    ",
    "low":                "supposé   ",
    "default":            "défaut lib",
    "default_efootprint": "défaut lib",
    "default_script":     "défaut script",
    "unjustified":        "précisé (non justifié)",
}


def fmt_conf(conf):
    return CONFIDENCE_LABELS.get(conf, conf or "?")


def instance_type_confidence(manual, source):
    """Niveau de confiance du type d'instance :
    - jamais précisé (--instance non fourni) : "default_script" (valeur fixée
      par CE script via DEFAULT_INSTANCE_BY_PROVIDER, pas par la librairie
      e-footprint, qui n'a pas de défaut propre).
    - précisé (--instance fourni) sans justification (--instance-source
      absent) : "unjustified" — choix actif mais non vérifié.
    - précisé ET justifié (--instance-source fourni) : "medium" ("estimé")."""
    if not manual:
        return "default_script"
    if not source:
        return "unjustified"
    return "medium"


def print_hypotheses(env_data, visits, instance_type, traffic_meta=None,
                      instance_manual=False, instance_source=None):
    job = env_data.get("job", {})
    server = env_data.get("server", {})
    device = env_data.get("device_mix", {})
    network = env_data.get("network_mix", {})

    print()
    print("=" * 65)
    print("  AVERTISSEMENT : ESTIMATION HYPOTHÉTIQUE")
    print("  Les valeurs ci-dessous sont des hypothèses de calcul.")
    print("  Elles ne constituent pas une mesure réelle.")
    print("=" * 65)
    print()
    print(f"  {'Paramètre':<35} {'Valeur':<18} {'Source'}")
    print(f"  {'-'*35} {'-'*18} {'-'*12}")
    # LOT 1 : poids transféré (réseau réel) = valeur d'entrée ; décompressé en repère.
    _kb_real = (job.get('data_transferred_bytes_real') or job.get('data_transferred_bytes', 0)) // 1024
    _conf_real = job.get('confidence_data_transferred_real') or job.get('confidence_data_transferred')
    print(f"  {'Poids page transféré (réseau réel)':<35} "
          f"{_kb_real} kB           "
          f"{fmt_conf(_conf_real)}")
    if job.get('data_transferred_bytes_real'):
        _kb_unc = job.get('data_transferred_bytes', 0) // 1024
        _ratio = job.get('compression_ratio')
        _ratio_str = f" (ratio {_ratio})" if _ratio else ""
        print(f"  {'  dont décompressé (repère)':<35} "
              f"{_kb_unc} kB{_ratio_str}")
    print(f"  {'Durée chargement':<35} "
          f"{job.get('request_duration_ms', 0)} ms            "
          f"{fmt_conf(job.get('confidence_request_duration'))}")
    print(f"  {'Pays hébergement':<35} "
          f"{server.get('efootprint_country', '?'):<18}"
          f"{fmt_conf(server.get('confidence_country'))}")
    print(f"  {'Intensité carbone électricité':<35} "
          f"{server.get('carbon_intensity_g_kwh', '?')} g/kWh         "
          f"{fmt_conf(server.get('confidence_carbon_intensity'))}")
    print(f"  {'Provider hébergeur':<35} "
          f"{server.get('detected_provider') or 'inconnu':<18}"
          f"{fmt_conf(server.get('confidence_provider'))}")
    _instance_conf = instance_type_confidence(instance_manual, instance_source)
    print(f"  {'Instance type':<35} "
          f"{instance_type:<18}"
          f"{fmt_conf(_instance_conf)}")
    if instance_source:
        print(f"  {'  justification':<35} {instance_source}")
    print(f"  {'Mix device (phone / desktop)':<35} "
          f"{device.get('phone_fraction', 0):.0%} / {device.get('desktop_fraction', 0):.0%}        "
          f"{fmt_conf(device.get('confidence'))}")
    print(f"  {'Mix réseau (wifi / mobile)':<35} "
          f"{network.get('wifi_fraction', 0):.0%} / {network.get('mobile_fraction', 0):.0%}        "
          f"{fmt_conf(network.get('confidence'))}")
    traffic_source = (traffic_meta or {}).get("source", "paramètre")
    _traffic_label = {
        "default": "défaut     ",
    }.get(traffic_source, traffic_source[:11].ljust(11))
    print(f"  {'Trafic annuel estimé':<35} "
          f"{visits:,} visites".ljust(20) + " "
          f"{_traffic_label}")
    print(f"  {'Stockage serveur':<35} "
          f"{'50 GB':<18}"
          f"{'défaut lib'}")
    print()
    print("  Légende : collecté = API/HAR  |  estimé = inféré  |  supposé = valeur par défaut")
    print()


# ---------------------------------------------------------------------------
# Construction du modèle e-footprint
# ---------------------------------------------------------------------------

def map_country(name):
    """Retourne la constante Countries.XXX depuis le nom e-footprint."""
    from efootprint.constants.countries import Countries
    if hasattr(Countries, name):
        return getattr(Countries, name)()
    return Countries.FRANCE()


def build_efootprint_model(env_data, visits, instance_type):
    from efootprint.abstract_modeling_classes.source_objects import SourceObject, SourceValue
    from efootprint.builders.hardware.boavizta_cloud_server import BoaviztaCloudServer
    from efootprint.builders.timeseries import ExplainableHourlyQuantitiesFromFormInputs
    from efootprint.constants.sources import Sources
    from efootprint.constants.units import u
    from efootprint.core.hardware.device import Device
    from efootprint.core.hardware.network import Network
    from efootprint.core.hardware.server_base import ServerTypes
    from efootprint.core.hardware.storage import Storage
    from efootprint.core.system import System
    from efootprint.core.usage.job import Job
    from efootprint.core.usage.usage_journey import UsageJourney
    from efootprint.core.usage.usage_journey_step import UsageJourneyStep
    from efootprint.core.usage.usage_pattern import UsagePattern

    job_data = env_data.get("job", {})
    server_data = env_data.get("server", {})
    device_data = env_data.get("device_mix", {})

    # --- Stockage ---
    storage = Storage.from_defaults(
        "Stockage web (hypothèse : 50 GB)",
        base_storage_need=SourceValue(50 * u.GB_stored)
    )

    # --- Serveur ---
    country_name = server_data.get("efootprint_country", "FRANCE")
    carbon_intensity = server_data.get("carbon_intensity_g_kwh", 400)

    # normalize_provider() interroge e-footprint : elle ne renvoie un nom que si
    # la librairie sait vraiment modéliser ce provider. Un nom inconnu donne None
    # et fait basculer sur le serveur générique, au lieu de lever une exception au
    # milieu du calcul.
    provider = normalize_provider(server_data.get("detected_provider"))
    if provider:
        server = BoaviztaCloudServer.from_defaults(
            f"Serveur {provider} (hypothèse : {instance_type})",
            server_type=ServerTypes.autoscaling(),
            provider=SourceObject(provider),
            instance_type=SourceObject(instance_type),
            base_ram_consumption=SourceValue(1 * u.GB_ram),
            base_compute_consumption=SourceValue(0.1 * u.cpu_core),
            average_carbon_intensity=SourceValue(carbon_intensity * u.g / u.kWh),
            storage=storage
        )
    else:
        from efootprint.core.hardware.server import Server
        server = Server.from_defaults(
            "Serveur générique (provider inconnu)",
            power=SourceValue(300 * u.W),
            carbon_footprint_fabrication=SourceValue(600 * u.kg),
            power_usage_effectiveness=SourceValue(1.2 * u.dimensionless),
            average_carbon_intensity=SourceValue(carbon_intensity * u.g / u.kWh),
            server_type=ServerTypes.autoscaling(),
            storage=storage
        )

    # --- Job ---
    # LOT 1 : on privilégie le poids TRANSFÉRÉ (réseau réel, compressé) qui pilote
    # justement l'énergie réseau. Rétro-compat : un env-data.json <1.4 n'a pas ce
    # champ -> on retombe sur data_transferred_bytes (poids décompressé, historique).
    data_bytes = job_data.get("data_transferred_bytes_real") \
        or job_data.get("data_transferred_bytes", 500 * 1024)
    duration_ms = job_data.get("request_duration_ms", 1000)

    page_job = Job(
        "Chargement page (hypothèse : page la plus lourde du parcours)",
        server=server,
        request_duration=SourceValue(duration_ms * u.ms),
        compute_needed=SourceValue(0.05 * u.cpu_core),
        ram_needed=SourceValue(50 * u.MB_ram),
        data_transferred=SourceValue(data_bytes * u.B),
        data_stored=SourceValue(0 * u.kB_stored)
    )

    # --- Pays ---
    country = map_country(country_name)

    # --- Mix appareils : pondération réelle via DEUX UsagePattern ---
    # La lib efootprint ne pondère PAS l'usage entre les devices d'une même liste :
    # [smartphone, laptop] dans un seul pattern facturerait 100% du trafic sur CHAQUE
    # appareil (surcompte). Le seul mécanisme correct est deux UsagePattern distincts,
    # avec des volumes proportionnels qui s'additionnent (le serveur/job voit bien le
    # total). Chaque pattern porte aussi son propre réseau (mobile vs wifi), ce qui
    # corrige au passage l'ancienne limite "réseau dominant unique".
    # Le mix est déjà corrigé iOS + tablette→mobile en amont (collect_env_data.py).
    mobile_frac = device_data.get("phone_fraction", 0.6)
    desktop_frac = device_data.get("desktop_fraction", 0.4)
    visits_mobile = round(visits * mobile_frac)
    visits_desktop = visits - visits_mobile  # garantit la somme = visits

    def _hourly_volume(volume):
        return ExplainableHourlyQuantitiesFromFormInputs({
            "start_date": "2025-01-01",
            "modeling_duration_value": 1,
            "modeling_duration_unit": "year",
            "initial_volume": volume,
            "initial_volume_timespan": "year",
            "net_growth_rate_in_percentage": 0,
            "net_growth_rate_timespan": "year",
        }, source=Sources.USER_DATA)

    usage_patterns = []
    if visits_mobile > 0:
        step_mobile = UsageJourneyStep.from_defaults("Visite page (mobile)", jobs=[page_job])
        journey_mobile = UsageJourney("Parcours visiteur mobile", uj_steps=[step_mobile])
        usage_patterns.append(UsagePattern(
            f"Visiteurs mobile ({mobile_frac:.0%}, {visits_mobile:,} visites/an)",
            journey_mobile,
            [Device.smartphone()],
            Network.mobile_network(),
            country,
            _hourly_volume(visits_mobile),
        ))
    if visits_desktop > 0:
        step_desktop = UsageJourneyStep.from_defaults("Visite page (desktop)", jobs=[page_job])
        journey_desktop = UsageJourney("Parcours visiteur desktop", uj_steps=[step_desktop])
        usage_patterns.append(UsagePattern(
            f"Visiteurs desktop ({desktop_frac:.0%}, {visits_desktop:,} visites/an)",
            journey_desktop,
            [Device.laptop()],
            Network.wifi_network(),
            country,
            _hourly_volume(visits_desktop),
        ))

    from urllib.parse import urlparse
    first_url = env_data.get("pages", [{}])[0].get("url", "") if env_data.get("pages") else ""
    system_name = urlparse(first_url).netloc or "site"
    return System(f"Estimation CO2e : {system_name} (hypothèse)", usage_patterns, edge_usage_patterns=[])


# ---------------------------------------------------------------------------
# Affichage résultats
# ---------------------------------------------------------------------------

def _parse_qty(s):
    """Extrait (valeur_float, unité) depuis une string e-footprint comme '2.66 kg' ou '26.6 mg'."""
    parts = str(s).strip().split()
    if len(parts) >= 2:
        try:
            return float(parts[0]), parts[1]
        except ValueError:
            pass
    return None, str(s)


def _to_g_co2(val, unit):
    """Convertit en grammes CO2e."""
    conv = {"g": 1.0, "kg": 1000.0, "mg": 0.001, "t": 1_000_000.0}
    return val * conv.get(unit, 1.0)


def _fmt_fab_dict(d):
    """Formate un dict fabrication_footprints en lignes lisibles."""
    lines = []
    for cat, obj in d.items():
        # L'objet peut être un objet e-footprint complexe — on cherche instances_fabrication_footprint
        # ou on lit sa repr et on extrait la valeur `first=`
        s = str(obj)
        # Chercher "first=X unit" dans la repr
        import re
        m = re.search(r'first=([\d.]+)\s+(\w+)', s)
        if m:
            val, unit = float(m.group(1)), m.group(2)
            # Convertir en kg/an (8760 heures)
            val_g = _to_g_co2(val, unit) * 8760
            val_kg = val_g / 1000
            lines.append(f"    {str(cat):<12} {val_kg:>8.2f} kg CO2e/an  (hypothèse)")
        else:
            lines.append(f"    {str(cat):<12} {s[:40]}")
    return lines


def _fmt_energy_dict(d):
    """Formate un dict energy_footprints en lignes lisibles."""
    lines = []
    import re
    for cat, obj in d.items():
        s = str(obj)
        m = re.search(r'first=([\d.]+)\s+(\w+)', s)
        if m:
            val, unit = float(m.group(1)), m.group(2)
            val_g = _to_g_co2(val, unit) * 8760
            val_kg = val_g / 1000
            lines.append(f"    {str(cat):<12} {val_kg:>8.4f} kg CO2e/an  (hypothèse)")
        else:
            # Peut être "no value"
            if "no value" in s or not s.strip():
                continue
            lines.append(f"    {str(cat):<12} {s[:40]}")
    return lines


def extract_results(system):
    """Extrait un dict structuré (kg CO2e/an par catégorie fab + énergie) depuis le System."""
    import re

    fab_sum = system.total_fabrication_footprint_sum_over_period
    energy_sum = system.total_energy_footprint_sum_over_period

    def parse_sum_dict(obj):
        rows = {}
        s = str(obj)
        for m in re.finditer(r'(\w+):\s*([\d.]+)\s*(\w+)', s):
            cat, val, unit = m.group(1), float(m.group(2)), m.group(3)
            if cat not in ("from", "to", "first", "last", "mean", "min", "max", "std"):
                rows[cat] = (val, unit)
        return rows

    fab_rows = parse_sum_dict(fab_sum)
    energy_rows = parse_sum_dict(energy_sum)

    fab_kg = {cat: _to_g_co2(val, unit) / 1000 for cat, (val, unit) in fab_rows.items()}
    energy_kg = {cat: _to_g_co2(val, unit) / 1000 for cat, (val, unit) in energy_rows.items()}

    return fab_kg, energy_kg


def print_results(system, visits):
    fab_kg, energy_kg = extract_results(system)
    total_kg = sum(fab_kg.values()) + sum(energy_kg.values())
    total_g = total_kg * 1000

    print()
    print("=" * 65)
    print("  RÉSULTATS — ESTIMATION HYPOTHÉTIQUE CO2e")
    print(f"  Base : {visits:,} visites/an")
    print("=" * 65)
    print()
    print(f"  Total annuel estimé  : ~{total_kg:.1f} kg CO2e/an")
    if visits > 0:
        print(f"  Par visite estimée   : ~{total_g / visits:.2f} g CO2e/visite")
    print()

    print("  Fabrication (amortie sur durée de vie) :")
    fab_total_kg = 0.0
    for cat, kg in fab_kg.items():
        fab_total_kg += kg
        if kg > 0:
            print(f"    {cat:<14} {kg:>8.2f} kg CO2e/an  (hypothèse)")
    print(f"    {'TOTAL':<14} {fab_total_kg:>8.2f} kg CO2e/an")
    print()

    print("  Énergie (usage annuel) :")
    energy_total_kg = 0.0
    for cat, kg in energy_kg.items():
        energy_total_kg += kg
        if kg > 0:
            print(f"    {cat:<14} {kg:>8.4f} kg CO2e/an  (hypothèse)")
    print(f"    {'TOTAL':<14} {energy_total_kg:>8.4f} kg CO2e/an")
    print()

    print("  Ces valeurs sont des ordres de grandeur hypothétiques.")
    print("  Pour affiner : relancer avec --visits et --instance ajustés.")
    print()


# ---------------------------------------------------------------------------
# Sérialisation
# ---------------------------------------------------------------------------

def save_model(system, source_dir):
    from efootprint.api_utils.system_to_json import system_to_json
    out_path = source_dir / "efootprint-model.json"
    system_to_json(system, save_calculated_attributes=False, output_filepath=str(out_path))
    print(f"  Modèle sérialisé : {out_path}")


def save_results(system, source_dir, env_data, visits, instance_type, traffic_meta=None,
                  instance_manual=False, instance_source=None, instance_source_url=None):
    """Écrit un JSON léger (totaux + hypothèses) pour consommation par le rapport HTML."""
    fab_kg, energy_kg = extract_results(system)
    total_kg = sum(fab_kg.values()) + sum(energy_kg.values())

    job = env_data.get("job", {})
    server = env_data.get("server", {})
    device = env_data.get("device_mix", {})
    network = env_data.get("network_mix", {})
    audience = env_data.get("audience", {})

    traffic_meta = traffic_meta or {}
    results = {
        "generated_at": env_data.get("collected_at"),
        "visits_per_year": visits,
        "traffic": {
            "visits_per_year": visits,
            "monthly_visits": (env_data.get("traffic") or {}).get("monthly_visits"),
            "source": traffic_meta.get("source", "paramètre"),
            "source_url": traffic_meta.get("source_url"),
            "snapshot": traffic_meta.get("snapshot"),
            "confidence": traffic_meta.get("confidence", "default"),
            "note": traffic_meta.get("note"),
        },
        "totals": {
            "total_kg_co2e_per_year": round(total_kg, 3),
            "per_visit_g_co2e": round(total_kg * 1000 / visits, 3) if visits > 0 else None,
            "fabrication_kg_co2e_per_year": {k: round(v, 3) for k, v in fab_kg.items()},
            "energy_kg_co2e_per_year": {k: round(v, 4) for k, v in energy_kg.items()},
        },
        "hypotheses": {
            # LOT 1 : le poids retenu pour le calcul = transféré (réseau réel) si dispo,
            # sinon décompressé (rétro-compat). On trace les deux + le ratio pour l'annexe.
            "page_weight_kb": (job.get("data_transferred_bytes_real")
                               or job.get("data_transferred_bytes", 0)) // 1024,
            "confidence_page_weight": (job.get("confidence_data_transferred_real")
                                       or job.get("confidence_data_transferred", "default")),
            "page_weight_transferred_kb": (job.get("data_transferred_bytes_real") or 0) // 1024,
            "page_weight_uncompressed_kb": job.get("data_transferred_bytes", 0) // 1024,
            "compression_ratio": job.get("compression_ratio"),
            "weight_by_type_transfer_bytes": job.get("weight_by_type_transfer_bytes"),
            "third_party_transfer_bytes": job.get("third_party_transfer_bytes"),
            "third_party_transfer_share": job.get("third_party_transfer_share"),
            "request_duration_ms": job.get("request_duration_ms", 0),
            "confidence_request_duration": job.get("confidence_request_duration", "default"),
            # Volet B : composition du poids de la page représentative (documentaire,
            # mesure directe HAR). N'entre pas dans le calcul ; explique data_transferred.
            "page_request_count": job.get("request_count"),
            "weight_by_type_bytes": job.get("weight_by_type_bytes"),
            "third_party_bytes": job.get("third_party_bytes"),
            "third_party_requests": job.get("third_party_requests"),
            "third_party_share": job.get("third_party_share"),
            "confidence_breakdown": job.get("confidence_breakdown"),
            # LOT 2/3 : signaux serveur/réseau factuels annexés (documentaire, mesure
            # directe HAR). N'entrent pas dans le calcul CO2e.
            "har_facts": job.get("har_facts"),
            "confidence_har_facts": job.get("confidence_har_facts"),
            "country": server.get("efootprint_country", "?"),
            "confidence_country": server.get("confidence_country", "default"),
            "carbon_intensity_g_kwh": server.get("carbon_intensity_g_kwh", None),
            "confidence_carbon_intensity": server.get("confidence_carbon_intensity", "default"),
            "provider": server.get("detected_provider") or "inconnu",
            "confidence_provider": server.get("confidence_provider", "default"),
            "instance_type": instance_type,
            "instance_type_manual": instance_manual,
            "instance_type_source": instance_source,
            "instance_type_source_url": instance_source_url,
            # Mix appareils retenu (mobile = phone+tablet, corrigé iOS)
            "phone_fraction": device.get("phone_fraction", 0.6),
            "desktop_fraction": device.get("desktop_fraction", 0.4),
            "confidence_device_mix": device.get("confidence", "default"),
            # Détail méthodologique du mix (pour l'annexe)
            "device_mix_source": device.get("source", "default"),
            "phone_fraction_raw": device.get("phone_fraction_raw"),
            "desktop_fraction_raw": device.get("desktop_fraction_raw"),
            "tablet_fraction_raw": device.get("tablet_fraction_raw"),
            "mobile_fraction_raw": device.get("mobile_fraction_raw"),
            "tablet_merged_into_mobile": device.get("tablet_merged_into_mobile", False),
            "ios_share_used": device.get("ios_share_used"),
            "ios_share_source": device.get("ios_share_source"),
            "macos_share_used": device.get("macos_share_used"),
            "macos_share_source": device.get("macos_share_source"),
            "device_scenarios": device.get("scenarios"),
            "device_mix_note": device.get("note"),
            # Mix pays d'audience (pondération iOS/macOS) — pour l'annexe
            "audience_mix": audience.get("mix"),
            "audience_source": audience.get("source"),
            "audience_source_url": audience.get("source_url"),
            "audience_confidence": audience.get("confidence"),
            "audience_per_country": audience.get("per_country"),
            "audience_ios_weighted": audience.get("ios_share_weighted"),
            "audience_macos_weighted": audience.get("macos_share_weighted"),
            "audience_note": audience.get("note"),
            # Split du trafic entre patterns mobile/desktop
            "visits_mobile": round(visits * device.get("phone_fraction", 0.6)),
            "visits_desktop": visits - round(visits * device.get("phone_fraction", 0.6)),
            # Réseau (un par pattern : mobile->mobile_network, desktop->wifi)
            "wifi_fraction": network.get("wifi_fraction", 0.4),
            "mobile_fraction": network.get("mobile_fraction", 0.6),
            "confidence_network_mix": network.get("confidence", "default"),
            "network_note": "Réseau modélisé par pattern : visiteurs mobile -> réseau mobile, "
                            "visiteurs desktop -> wifi.",
            "storage_gb": 50,
        },
    }

    out_path = source_dir / "efootprint-results.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"  Résultats sérialisés : {out_path}")


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Estimation CO2e hypothétique via e-footprint",
        epilog="IMPORTANT : toutes les valeurs sont des estimations hypothétiques."
    )
    parser.add_argument("source_dir", help="Dossier source contenant env-data.json (ou le .har)")
    parser.add_argument("--visits", type=int, default=None,
                        help="Trafic annuel (analytics client). Prioritaire sur le bloc "
                             "'traffic' SimilarWeb écrit par l'agent dans env-data.json. "
                             "Défaut : bloc 'traffic' s'il existe, sinon 100 000 visites/an.")
    parser.add_argument("--instance", default=None,
                        help="Type d'instance cloud. Défaut : la plus proche de "
                             "2 vCPU / 4 GB chez le provider détecté (hypothèse de "
                             "petite production, non vérifiée) ; les noms sont propres "
                             "à chaque provider. Si précisé, la confiance reste basse "
                             "('précisé (non justifié)') sauf si --instance-source est "
                             "aussi fourni.")
    parser.add_argument("--instance-source", default=None,
                        help="Justification de --instance (ex. \"confirmé par l'équipe infra "
                             "client, ticket #1234\"). Fait passer la confiance à 'estimé'.")
    parser.add_argument("--instance-source-url", default=None,
                        help="Lien optionnel vers la preuve/source de --instance-source.")
    parser.add_argument("--refresh-data", action="store_true",
                        help="Relancer collect_env_data.py avant le calcul")
    args = parser.parse_args()

    source_dir = Path(args.source_dir).resolve()
    if not source_dir.exists():
        print(f"Erreur : dossier introuvable : {source_dir}")
        sys.exit(1)

    # Collecte si nécessaire
    ensure_env_data(source_dir, refresh=args.refresh_data)

    env_data = load_env_data(source_dir)
    if not env_data:
        print(f"Erreur : env-data.json introuvable dans {source_dir}")
        sys.exit(1)

    # Résolution du trafic : --visits > bloc 'traffic' (SimilarWeb) > baseline 100k
    visits, traffic_meta = resolve_visits(args.visits, env_data)
    if traffic_meta.get("warning"):
        print(f"  ⚠ {traffic_meta['warning']}")

    # Le type d'instance dépend du provider : il doit donc être résolu APRÈS la
    # lecture de env-data.json, et avant l'affichage des hypothèses (qui l'annonce).
    provider = normalize_provider(env_data.get("server", {}).get("detected_provider"))
    instance_type, instance_manual = resolve_instance_type(args.instance, provider)
    if args.instance_source is not None:
        instance_manual = True

    # Résumé des hypothèses
    print_hypotheses(env_data, visits, instance_type, traffic_meta=traffic_meta,
                      instance_manual=instance_manual, instance_source=args.instance_source)

    # Calcul
    print("[e-footprint] Construction du modèle (hypothétique)...")
    system = build_efootprint_model(env_data, visits, instance_type)
    print("[e-footprint] Calcul CO2e...")

    # Résultats
    print_results(system, visits)

    # Sauvegarde modèle + résultats légers
    print("[e-footprint] Sérialisation du modèle...")
    save_model(system, source_dir)
    save_results(system, source_dir, env_data, visits, instance_type, traffic_meta=traffic_meta,
                 instance_manual=instance_manual, instance_source=args.instance_source,
                 instance_source_url=args.instance_source_url)
    print()
    print(f"  Trafic retenu : {visits:,} visites/an (source : {traffic_meta['source']})")
    print("Pour relancer avec d'autres hypothèses :")
    # Le nom d'instance dépend du provider : afficher celui retenu ici plutôt
    # qu'un exemple figé, qui serait refusé chez un autre hébergeur.
    _prov = provider or "le provider détecté"
    print(f"  python3 {Path(__file__).name} {source_dir} --visits 500000 "
          f"--instance <type {_prov}>   (actuel : {instance_type})")


if __name__ == "__main__":
    main()
