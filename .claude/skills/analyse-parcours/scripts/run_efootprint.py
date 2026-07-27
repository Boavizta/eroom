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
    python3 run_efootprint.py <source_dir> --instance t3.large  # instance AWS
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


# ---------------------------------------------------------------------------
# Affichage résumé des hypothèses
# ---------------------------------------------------------------------------

CONFIDENCE_LABELS = {
    "high":    "collecté  ",
    "medium":  "estimé    ",
    "low":     "supposé   ",
    "default": "défaut lib",
}


def fmt_conf(conf):
    return CONFIDENCE_LABELS.get(conf, conf or "?")


def print_hypotheses(env_data, visits, instance_type):
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
    print(f"  {'Poids de page (représentative)':<35} "
          f"{job.get('data_transferred_bytes', 0) // 1024} kB           "
          f"{fmt_conf(job.get('confidence_data_transferred'))}")
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
    print(f"  {'Instance type':<35} "
          f"{instance_type:<18}"
          f"{'supposé   ' if instance_type == 't3.medium' else 'paramètre '}")
    print(f"  {'Mix device (phone / desktop)':<35} "
          f"{device.get('phone_fraction', 0):.0%} / {device.get('desktop_fraction', 0):.0%}        "
          f"{fmt_conf(device.get('confidence'))}")
    print(f"  {'Mix réseau (wifi / mobile)':<35} "
          f"{network.get('wifi_fraction', 0):.0%} / {network.get('mobile_fraction', 0):.0%}        "
          f"{fmt_conf(network.get('confidence'))}")
    print(f"  {'Trafic annuel estimé':<35} "
          f"{visits:,} visites     "
          f"{'paramètre '}")
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
    network_data = env_data.get("network_mix", {})

    # --- Stockage ---
    storage = Storage.from_defaults(
        "Stockage web (hypothèse : 50 GB)",
        base_storage_need=SourceValue(50 * u.GB_stored)
    )

    # --- Serveur ---
    provider = server_data.get("detected_provider")
    country_name = server_data.get("efootprint_country", "FRANCE")
    carbon_intensity = server_data.get("carbon_intensity_g_kwh", 400)

    supported_boavizta = ["aws", "gcp", "azure", "scaleway", "ovh"]
    if provider and provider in supported_boavizta:
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
    data_bytes = job_data.get("data_transferred_bytes", 500 * 1024)
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

    step = UsageJourneyStep.from_defaults("Visite page", jobs=[page_job])
    journey = UsageJourney("Parcours visiteur", uj_steps=[step])

    # --- Devices ---
    phone_frac = device_data.get("phone_fraction", 0.6)
    desktop_frac = device_data.get("desktop_fraction", 0.4)
    # On passe une liste - la lib pondère par le temps occupé (fraction_of_usage_time)
    # Pour représenter le mix, on crée 2 patterns séparés ou on utilise les 2 devices
    # L'API prend une liste, chaque device contribue proportionnellement à son usage_time
    # Approche simple : 2 devices dans la liste, proportions dans l'affichage seulement
    devices = [Device.smartphone(), Device.laptop()]

    # --- Réseau ---
    wifi_frac = network_data.get("wifi_fraction", 0.4)
    # La lib ne supporte pas un mix réseau natif - on choisit le réseau dominant
    if wifi_frac >= 0.5:
        network = Network.wifi_network()
        network_label = f"wifi (dominant à {wifi_frac:.0%})"
    else:
        network = Network.mobile_network()
        network_label = f"mobile (dominant à {1-wifi_frac:.0%})"

    # --- Pays ---
    country = map_country(country_name)

    # --- Trafic horaire ---
    usage_pattern = UsagePattern(
        f"Visiteurs (hypothèse : {visits:,} visites/an)",
        journey,
        devices,
        network,
        country,
        ExplainableHourlyQuantitiesFromFormInputs({
            "start_date": "2025-01-01",
            "modeling_duration_value": 1,
            "modeling_duration_unit": "year",
            "initial_volume": visits,
            "initial_volume_timespan": "year",
            "net_growth_rate_in_percentage": 0,
            "net_growth_rate_timespan": "year",
        }, source=Sources.USER_DATA)
    )

    from urllib.parse import urlparse
    first_url = env_data.get("pages", [{}])[0].get("url", "") if env_data.get("pages") else ""
    system_name = urlparse(first_url).netloc or "site"
    return System(f"Estimation CO2e — {system_name} (hypothèse)", [usage_pattern], edge_usage_patterns=[])


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


def save_results(system, source_dir, env_data, visits, instance_type):
    """Écrit un JSON léger (totaux + hypothèses) pour consommation par le rapport HTML."""
    fab_kg, energy_kg = extract_results(system)
    total_kg = sum(fab_kg.values()) + sum(energy_kg.values())

    job = env_data.get("job", {})
    server = env_data.get("server", {})
    device = env_data.get("device_mix", {})
    network = env_data.get("network_mix", {})

    results = {
        "generated_at": env_data.get("collected_at"),
        "visits_per_year": visits,
        "totals": {
            "total_kg_co2e_per_year": round(total_kg, 3),
            "per_visit_g_co2e": round(total_kg * 1000 / visits, 3) if visits > 0 else None,
            "fabrication_kg_co2e_per_year": {k: round(v, 3) for k, v in fab_kg.items()},
            "energy_kg_co2e_per_year": {k: round(v, 4) for k, v in energy_kg.items()},
        },
        "hypotheses": {
            "page_weight_kb": job.get("data_transferred_bytes", 0) // 1024,
            "confidence_page_weight": job.get("confidence_data_transferred", "default"),
            "request_duration_ms": job.get("request_duration_ms", 0),
            "confidence_request_duration": job.get("confidence_request_duration", "default"),
            "country": server.get("efootprint_country", "?"),
            "confidence_country": server.get("confidence_country", "default"),
            "carbon_intensity_g_kwh": server.get("carbon_intensity_g_kwh", None),
            "confidence_carbon_intensity": server.get("confidence_carbon_intensity", "default"),
            "provider": server.get("detected_provider") or "inconnu",
            "confidence_provider": server.get("confidence_provider", "default"),
            "instance_type": instance_type,
            "phone_fraction": device.get("phone_fraction", 0.6),
            "desktop_fraction": device.get("desktop_fraction", 0.4),
            "confidence_device_mix": device.get("confidence", "default"),
            "wifi_fraction": network.get("wifi_fraction", 0.4),
            "mobile_fraction": network.get("mobile_fraction", 0.6),
            "confidence_network_mix": network.get("confidence", "default"),
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
    parser.add_argument("--visits", type=int, default=100_000,
                        help="Trafic annuel estimé (défaut : 100 000 visites/an)")
    parser.add_argument("--instance", default="t3.medium",
                        help="Type d'instance cloud (défaut : t3.medium)")
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

    # Résumé des hypothèses
    print_hypotheses(env_data, args.visits, args.instance)

    # Calcul
    print("[e-footprint] Construction du modèle (hypothétique)...")
    system = build_efootprint_model(env_data, args.visits, args.instance)
    print("[e-footprint] Calcul CO2e...")

    # Résultats
    print_results(system, args.visits)

    # Sauvegarde modèle + résultats légers
    print("[e-footprint] Sérialisation du modèle...")
    save_model(system, source_dir)
    save_results(system, source_dir, env_data, args.visits, args.instance)
    print()
    print("Pour relancer avec d'autres hypothèses :")
    print(f"  python3 {Path(__file__).name} {source_dir} --visits 500000 --instance t3.large")


if __name__ == "__main__":
    main()
