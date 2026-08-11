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
Écrit efootprint-boavizta-model.json dans source_dir (relançabilité) et
efootprint-synthese-python.json (consommé par generate_report_html.py et
check_efootprint_contract.py).

DEPUIS LE LOT 5 : ce script délègue toute la modélisation à `efootprint_model`
(spec_from_env_data -> build_system -> ranges), au lieu de construire un modèle
mono-page/mono-serveur à la main. Le HAR est donc requis en plus de
env-data.json (spec_from_env_data() en a besoin pour détecter les
infrastructures et découper le parcours en étapes).
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))

from efootprint_model import SpecError, arbitrations_for, calculation_reserves  # noqa: E402
from efootprint_model.from_har import spec_from_env_data  # noqa: E402
from collect_env_data import find_har  # noqa: E402
from efootprint_model.build import (  # noqa: E402
    build_system, consistency_report, energy_kg, fabrication_kg, total_kg)
from efootprint_model.compose import (  # noqa: E402
    collect_sources, primary_server, servers_note)
from efootprint_model.ranges import footprint_ranges_kg  # noqa: E402
from efootprint_model.sizing_report import servers_sizing  # noqa: E402
from efootprint_model.to_plantuml import site_to_plantuml  # noqa: E402
from efootprint_model import topology_overview  # noqa: E402

# Module frère (même dossier) : détection des technologies (stack) par règles
# maison sur le HAR, réutilisée pour la vue d'ensemble avant calcul (Étape 25).
# Import guardé (le reste fonctionne si le module est absent), même pattern
# que collect_env_data.py.
try:
    import detect_tech
except ImportError:
    detect_tech = None

RAW_DATA_DIR = "donnees-brutes-potentiellement-sensibles"


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


def infer_audited_domain(env_data, source_dir):
    """Domaine audité : pages[0].url d'env-data.json, sinon le nom du dossier.

    Même ordre de priorité que `similarweb_api.infer_domain()`, sans dépendre
    de ce module (pas d'appel réseau nécessaire ici, juste un nom de domaine).
    """
    from urllib.parse import urlparse
    pages = env_data.get("pages") or []
    if pages:
        host = urlparse(pages[0].get("url", "")).netloc
        if host:
            return host.removeprefix("www.")
    return source_dir.name


def build_topology_overview(source_dir):
    """Étape 25 (skill efootprint) : construit la vue d'ensemble (texte +
    PlantUML) AVANT tout calcul CO2e. Ne calcule rien (pas de build_system(),
    pas de total kg) : seulement de la lecture/présentation.

    Chaîne volontairement identique au début de main() (load_env_data ->
    find_har -> infer_audited_domain -> spec_from_env_data), pour ne jamais
    diverger de ce que l'Étape 40 verra réellement. Aucune dépendance sur les
    paramètres de l'Étape 30 (visits/instance) : la spec a toujours un défaut
    résolu (100k/an) dès l'Étape 20 (resolve_traffic() dans collect_env_data.py).

    Retourne (spec, overview_text, plantuml_text, warnings). Lève RuntimeError
    (message actionnable, jamais une trace brute) si les préconditions ne sont
    pas réunies : HAR absent, ou env-data.json sans serveur détecté.
    """
    env_data = load_env_data(source_dir)
    if not env_data:
        raise RuntimeError(
            f"env-data.json introuvable dans {source_dir} : lancer l'Étape 20 "
            "(collect_env_data.py) avant de demander la vue d'ensemble.")

    har_path = find_har(source_dir)
    if not har_path:
        raise RuntimeError(
            f"Aucun .har trouvé dans {source_dir} (ni dans {RAW_DATA_DIR}/). "
            "La vue d'ensemble a besoin du HAR pour détecter la topologie "
            "(serveurs, BDD/streaming/IA suspectés).")

    audited_domain = infer_audited_domain(env_data, source_dir)

    try:
        spec, warnings = spec_from_env_data(env_data, str(har_path), audited_domain)
    except (SpecError, ValueError) as exc:
        # ValueError NUE : spec_from_env_data() lève ce type (pas SpecError)
        # quand env_data["servers"] est vide (from_har.py) — piège identifié,
        # `except SpecError` seul ne suffit pas.
        raise RuntimeError(
            f"Impossible de construire la topologie : {exc}. Relancer "
            "l'Étape 20 (collect_env_data.py) si env-data.json est incomplet.")

    tech_result = detect_tech.detect_from_har(har_path) if detect_tech else None
    spec = topology_overview.annotate_third_party_hosts(spec, tech_result)

    text = topology_overview.overview_text(spec, tech_result)
    # Le mix pays d'audience (SimilarWeb) vit dans env-data.json, jamais dans
    # la SiteSpec (AudienceSpec.country_mix existe mais n'est peuplé par aucun
    # adaptateur) : lu ici pour l'afficher dans la note d'hypothèses du diagramme.
    audience_mix = (env_data.get("audience") or {}).get("mix")
    puml = site_to_plantuml(spec, title=audited_domain, audience_mix=audience_mix)

    return spec, text, puml, warnings


DEFAULT_VISITS_PER_YEAR = 100_000

# Nom du provider tel qu'il est détecté par collect_env_data.py -> nom attendu par
# e-footprint. Sans cette table, un provider bien détecté fait planter le calcul :
# le script entrait dans la branche Boavizta avec "ovh", qu'e-footprint refuse
# (il attend "ovhcloud"), et le repli "serveur générique" ne se déclenchait jamais.
# Cas rencontré sur un site hébergé chez OVH.
PROVIDER_ALIASES = {"ovh": "ovhcloud"}


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


def resolve_visits_override(cli_visits, spec):
    """--visits (CLI, analytics client) est prioritaire sur le trafic déjà
    résolu par spec_from_env_data() (bloc 'traffic' SimilarWeb, ou rien).

    Retourne une AudienceSpec, éventuellement remplacée si --visits est fourni.
    Contrairement à l'ancien script, il n'y a plus de défaut 100 000/an ici :
    AudienceSpec.visits_per_year n'est pas un champ critique (cf. spec.py), la
    lib le dit déjà à la construction si besoin (build.py:241).
    """
    from dataclasses import replace
    from efootprint_model.spec import measured
    audience = spec.audience
    if cli_visits is None or audience is None:
        return spec
    new_visits = measured(float(cli_visits), "dimensionless", "saisie manuelle (--visits)",
                          comment="Trafic saisi en ligne de commande (analytics client ou "
                                  "hypothèse explicite), prioritaire sur le bloc 'traffic'.")
    return replace(spec, audience=replace(audience, visits_per_year=new_visits))


def resolve_instance_override(cli_instance, cli_instance_source, cli_instance_source_url, spec):
    """--instance ne peut viser qu'UN SEUL serveur : chaque BoaviztaCloudServer porte
    son propre instance_type (confirmé par la doc e-footprint, aucune notion
    d'instance "du site"). Convention retenue : le serveur PRINCIPAL, celui qui
    porte le plus d'octets (primary_server(), déjà utilisé pour les clés
    singulières provider/instance_type du JSON de résultats).
    """
    from dataclasses import replace
    from efootprint_model.spec import estimated_label, unjustified

    if cli_instance is None:
        return spec, None

    target = primary_server(spec)
    if target is None or target.provider is None:
        print("  ⚠ --instance ignoré : aucun serveur cloud (provider Boavizta) "
              "dans le modèle.")
        return spec, None

    if cli_instance_source:
        new_instance = estimated_label(
            cli_instance, cli_instance_source, source_url=cli_instance_source_url)
    else:
        new_instance = unjustified(
            cli_instance,
            comment="Instance précisée en ligne de commande (--instance) sans "
                    "justification vérifiable (--instance-source absent).")

    new_servers = tuple(
        replace(server, instance_type=new_instance) if server.key == target.key else server
        for server in spec.servers
    )
    return replace(spec, servers=new_servers), target.key


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


def print_hypotheses(spec):
    """Résumé des hypothèses lu directement sur la SiteSpec (Traced), plus
    fidèle que l'ancien tableau (qui relisait env-data.json en parallèle du
    calcul et pouvait diverger de ce qui est réellement utilisé)."""
    print()
    print("=" * 65)
    print("  AVERTISSEMENT : ESTIMATION HYPOTHÉTIQUE")
    print("  Les valeurs ci-dessous sont des hypothèses de calcul.")
    print("  Elles ne constituent pas une mesure réelle.")
    print("=" * 65)
    print()
    print(f"  {'Paramètre':<35} {'Valeur':<18} {'Source'}")
    print(f"  {'-'*35} {'-'*18} {'-'*12}")

    print(f"  {'Nombre de serveurs 1st-party':<35} {len(spec.servers):<18}{'détecté HAR'}")
    for server in spec.servers:
        label = f"{server.key} ({server.provider.value if server.provider else 'générique'})"
        instance = server.instance_type.value if server.instance_type else "-"
        conf = fmt_conf(server.instance_type.confidence) if server.instance_type else "-"
        print(f"    {label:<33} {instance:<18}{conf}")

    steps_label = "Nombre d'étapes du parcours"
    print(f"  {steps_label:<35} {len(spec.steps):<18}{'détecté HAR'}")

    audience = spec.audience
    if audience and audience.visits_per_year:
        v = audience.visits_per_year
        print(f"  {'Trafic annuel estimé':<35} "
              f"{int(v.value):,} visites".ljust(20) + " "
              f"{fmt_conf(v.confidence)}")
    else:
        print(f"  {'Trafic annuel estimé':<35} {'non renseigné':<18}{'-'}")
    if audience and audience.phone_fraction:
        print(f"  {'Mix device (phone / desktop)':<35} "
              f"{audience.phone_fraction.value:.0%} / {audience.desktop_fraction.value:.0%}"
              .ljust(20) + " " + fmt_conf(audience.phone_fraction.confidence))
    print()
    print("  Légende : collecté = API/HAR  |  estimé = inféré  |  supposé = valeur par défaut")
    print()


def print_reserves(reserves):
    print()
    print("=" * 65)
    print("  RÉSERVES DE CALCUL — la spécification ne peut pas être publiée telle quelle")
    print("=" * 65)
    for code, message in reserves:
        print(f"\n  [{code}] {message}")
        options = arbitrations_for(code)
        if options:
            print("  Issues possibles :")
            for option in options:
                print(f"    - {option}")
    print()


def print_results(spec, built, ranges):
    fab_kg = fabrication_kg(built)
    energy_kg_ = energy_kg(built)
    total = total_kg(built)
    visits = spec.audience.visits_per_year.value if spec.audience and spec.audience.visits_per_year else 0

    print()
    print("=" * 65)
    print("  RÉSULTATS — ESTIMATION HYPOTHÉTIQUE CO2e")
    if visits:
        print(f"  Base : {visits:,.0f} visites/an")
    print("=" * 65)
    print()
    print(f"  Total annuel estimé  : ~{total:.1f} kg CO2e/an")
    if visits:
        print(f"  Par visite estimée   : ~{total * 1000 / visits:.2f} g CO2e/visite")
    print()

    print("  Fabrication (amortie sur durée de vie) :")
    for cat, kg in sorted(fab_kg.items(), key=lambda kv: -kv[1]):
        if kg > 0:
            print(f"    {cat:<14} {kg:>8.2f} kg CO2e/an  (hypothèse)")
    print(f"    {'TOTAL':<14} {sum(fab_kg.values()):>8.2f} kg CO2e/an")
    print()

    print("  Énergie (usage annuel) :")
    for cat, kg in sorted(energy_kg_.items(), key=lambda kv: -kv[1]):
        if kg > 0:
            print(f"    {cat:<14} {kg:>8.4f} kg CO2e/an  (hypothèse)")
    print(f"    {'TOTAL':<14} {sum(energy_kg_.values()):>8.4f} kg CO2e/an")
    print()

    infra_lo, infra_hi = ranges["infra_range_kg"]
    usage_lo, usage_hi = ranges["usage_range_kg"]
    print("  Fourchettes (incertitudes non cumulées, cf. rapport) :")
    print(f"    infra (mode de dimensionnement) : {infra_lo:.1f} - {infra_hi:.1f} kg CO2e/an")
    print(f"    usage (temps utilisateur Nielsen) : {usage_lo:.1f} - {usage_hi:.1f} kg CO2e/an")
    print()

    print("  Ces valeurs sont des ordres de grandeur hypothétiques.")
    print("  Pour affiner : relancer avec --visits et --instance ajustés.")
    print()


# ---------------------------------------------------------------------------
# Sérialisation
# ---------------------------------------------------------------------------

def save_boavizta_model(built, source_dir):
    """Écrit efootprint-boavizta-model.json : sérialisation NATIVE de la
    bibliothèque e-footprint (Boavizta) via `system_to_json`, indépendante de
    ce projet. Utile pour recharger le modèle dans la vraie interface web
    e-footprint (model_builder) ou via `json_to_system`, jamais lu par
    `generate_report_html.py` ni `check_efootprint_contract.py` (cf.
    `save_synthese_python()` pour le format consommé par ce projet)."""
    from efootprint.api_utils.system_to_json import system_to_json
    out_path = source_dir / "efootprint-boavizta-model.json"
    system_to_json(built.system, save_calculated_attributes=False, output_filepath=str(out_path))
    print(f"  Modèle sérialisé : {out_path}")


def save_synthese_python(spec, built, ranges, source_dir, env_data, warnings, reserves):
    """Écrit efootprint-synthese-python.json : résumé applicatif propre à ce
    projet (PAS un format e-footprint), consommé par deux scripts Python :
    `generate_report_html.py` (alimente le rapport HTML) et
    `check_efootprint_contract.py` (garde-fou de non-régression, comparé à
    une baseline). Jamais destiné à être ouvert directement ni rechargé dans
    la bibliothèque e-footprint (cf. `save_boavizta_model()` pour ça).

    Additif STRICT par rapport à l'ancien format (cf. handoff du 05/08/2026,
    section F.3) : les ~60 clés `hypotheses` historiques, DOCUMENTAIRES (poids
    par type, har_facts, mix d'audience par pays, scénarios device...),
    restent lues depuis `env_data` comme avant, au même endroit, avec le même
    sens — elles décrivent des mesures HAR/CrUX/SimilarWeb indépendantes du
    modèle e-footprint. Les clés PILOTÉES PAR LE MODÈLE (provider,
    instance_type, country, carbon_intensity, storage_gb) viennent en
    revanche de `primary_server(spec)`, pas de `env_data["server"]` : avec
    plusieurs infras 1st-party, ce n'est plus forcément le même serveur
    (vérifié sur ants-permis, où `env_data["server"]` désigne un hôte
    différent du serveur qui porte réellement le plus d'octets).
    Le nouveau contenu (fourchettes, plusieurs serveurs, sources tracées) va
    dans un bloc `model` de niveau 1, ignoré par le rapport actuel tant que
    `_section_model()` n'existe pas (Lot 9).
    """
    fab_kg = fabrication_kg(built)
    energy_kg_ = energy_kg(built)
    total = total_kg(built)
    audience = spec.audience
    visits = audience.visits_per_year.value if audience and audience.visits_per_year else 0

    main_server = primary_server(spec)
    job = env_data.get("job", {})
    device = env_data.get("device_mix", {})
    network = env_data.get("network_mix", {})
    audience_env = env_data.get("audience", {})

    def _traced_dict(traced):
        return traced.as_dict() if traced is not None else None

    traffic_env = env_data.get("traffic") or {}
    # spec_from_env_data() ne trace pas source_url/note pour visits_per_year
    # (from_har.py:605, mesure simple) : ils viennent du bloc 'traffic' brut
    # d'env-data.json, sauf si --visits (CLI) a remplacé la valeur, auquel cas
    # le Traced de la spec porte le comment "saisie manuelle" à restituer.
    _cli_override = bool(audience and audience.visits_per_year
                          and audience.visits_per_year.source_name == "saisie manuelle (--visits)")
    results = {
        "generated_at": env_data.get("collected_at"),
        "visits_per_year": visits,
        "traffic": {
            "visits_per_year": visits,
            "monthly_visits": traffic_env.get("monthly_visits"),
            "source": audience.visits_per_year.source_name if audience and audience.visits_per_year else "default",
            "source_url": (None if _cli_override else traffic_env.get("source_url")),
            "snapshot": traffic_env.get("snapshot"),
            "confidence": audience.visits_per_year.confidence if audience and audience.visits_per_year else "default",
            "note": (audience.visits_per_year.comment if _cli_override else traffic_env.get("note")),
        },
        "totals": {
            "total_kg_co2e_per_year": round(total, 3),
            "per_visit_g_co2e": round(total * 1000 / visits, 3) if visits else None,
            "fabrication_kg_co2e_per_year": {k: round(v, 3) for k, v in fab_kg.items()},
            "energy_kg_co2e_per_year": {k: round(v, 4) for k, v in energy_kg_.items()},
        },
        "hypotheses": {
            # Poids/durée/répartition : mesure directe HAR, documentaire,
            # n'entrent pas dans le calcul multi-étapes (chaque étape a son
            # propre JobSpec, cf. spec.py). Conservées pour l'annexe du rapport.
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
            "page_request_count": job.get("request_count"),
            "weight_by_type_bytes": job.get("weight_by_type_bytes"),
            "third_party_bytes": job.get("third_party_bytes"),
            "third_party_requests": job.get("third_party_requests"),
            "third_party_share": job.get("third_party_share"),
            "confidence_breakdown": job.get("confidence_breakdown"),
            "har_facts": job.get("har_facts"),
            "confidence_har_facts": job.get("confidence_har_facts"),
            # Serveur : PILOTÉ PAR LE MODÈLE, donc lu sur le serveur principal
            # de la spec (celui qui porte le plus d'octets), pas sur
            # env_data["server"].
            "country": main_server.country.value if main_server and main_server.country else "?",
            "confidence_country": main_server.country.confidence if main_server and main_server.country else "default",
            "carbon_intensity_g_kwh": main_server.carbon_intensity.value if main_server and main_server.carbon_intensity else None,
            "confidence_carbon_intensity": main_server.carbon_intensity.confidence if main_server and main_server.carbon_intensity else "default",
            "provider": main_server.provider.value if main_server and main_server.provider else "inconnu",
            "confidence_provider": main_server.provider.confidence if main_server and main_server.provider else "default",
            "instance_type": main_server.instance_type.value if main_server and main_server.instance_type else None,
            "instance_type_manual": bool(main_server and main_server.instance_type
                                          and main_server.instance_type.confidence in ("medium", "unjustified")),
            "instance_type_source": main_server.instance_type.source_name if main_server and main_server.instance_type
                                     and main_server.instance_type.confidence == "medium" else None,
            "instance_type_source_url": main_server.instance_type.source_url if main_server and main_server.instance_type else None,
            # Mix appareils/réseau : mesure CrUX documentaire, indépendante du
            # nombre de serveurs.
            "phone_fraction": device.get("phone_fraction", 0.6),
            "desktop_fraction": device.get("desktop_fraction", 0.4),
            "confidence_device_mix": device.get("confidence", "default"),
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
            "audience_mix": audience_env.get("mix"),
            "audience_source": audience_env.get("source"),
            "audience_source_url": audience_env.get("source_url"),
            "audience_confidence": audience_env.get("confidence"),
            "audience_per_country": audience_env.get("per_country"),
            "audience_ios_weighted": audience_env.get("ios_share_weighted"),
            "audience_macos_weighted": audience_env.get("macos_share_weighted"),
            "audience_note": audience_env.get("note"),
            "visits_mobile": round(visits * device.get("phone_fraction", 0.6)),
            "visits_desktop": visits - round(visits * device.get("phone_fraction", 0.6)),
            "wifi_fraction": network.get("wifi_fraction", 0.4),
            "mobile_fraction": network.get("mobile_fraction", 0.6),
            "confidence_network_mix": network.get("confidence", "default"),
            "network_note": "Réseau modélisé par pattern : visiteurs mobile -> réseau mobile, "
                            "visiteurs desktop -> wifi.",
            "storage_gb": main_server.storage_gb.value if main_server and main_server.storage_gb else None,
            "servers_note": servers_note(spec),
        },
        "model": {
            "schema_version": spec.schema_version,
            "archetypes": list(spec.archetypes),
            "servers": [
                {
                    "key": s.key,
                    "role": s.role,
                    "label": s.label,
                    "provider": _traced_dict(s.provider),
                    "instance_type": _traced_dict(s.instance_type),
                    "server_type": _traced_dict(s.server_type),
                    "country": _traced_dict(s.country),
                    "carbon_intensity": _traced_dict(s.carbon_intensity),
                    "storage_gb": _traced_dict(s.storage_gb),
                    "evidence": s.evidence.as_dict() if s.evidence else None,
                    "is_primary": main_server is not None and s.key == main_server.key,
                }
                for s in spec.servers
            ],
            "steps": [
                {
                    "key": step.key,
                    "label": step.label,
                    "url": step.url,
                    "user_time_min": step.user_time.value if step.user_time else None,
                    "user_time_source": step.user_time.source_name if step.user_time else None,
                    "user_time_confidence": step.user_time.confidence if step.user_time else "default",
                    "words": step.words.value if step.words else None,
                    "times_per_journey": step.times_per_journey,
                }
                for step in spec.steps
            ],
            "third_party_hosts": [h.as_dict() for h in spec.third_party_hosts],
            "ranges": {
                "central_kg": round(ranges["central_kg"], 3),
                "infra_range_kg": [round(v, 3) for v in ranges["infra_range_kg"]],
                "usage_range_kg": [round(v, 3) for v in ranges["usage_range_kg"]],
            },
            "consistency": consistency_report(built),
            "reserves_accepted": [{"code": code, "message": message} for code, message in reserves],
            "warnings": list(warnings),
            "sizing": {
                "note": "Diagnostic interne (Lot 6) : le trafic annuel est réparti en "
                        "timeseries UNIFORME sur 24h, jamais sur le vrai profil horaire du "
                        "site, ce qui MINIMISE artificiellement l'écart mesuré. Ne pas "
                        "présenter oversizing_ratio comme une mesure du surdimensionnement "
                        "réel d'un client. Non affiché dans le rapport HTML (décision "
                        "reportée au Lot 9).",
                "servers": servers_sizing(built),
            },
        },
        "sources": collect_sources(spec),
    }

    out_path = source_dir / "efootprint-synthese-python.json"
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
    parser.add_argument("source_dir", help="Dossier source contenant env-data.json et le .har")
    parser.add_argument("--visits", type=int, default=None,
                        help="Trafic annuel (analytics client). Prioritaire sur le bloc "
                             "'traffic' SimilarWeb écrit par l'agent dans env-data.json.")
    parser.add_argument("--instance", default=None,
                        help="Type d'instance cloud pour le SERVEUR PRINCIPAL (celui qui "
                             "porte le plus d'octets). Un serveur cloud n'a qu'un seul "
                             "instance_type possible chez e-footprint : ce réglage ne "
                             "s'applique jamais à plusieurs serveurs à la fois.")
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

    ensure_env_data(source_dir, refresh=args.refresh_data)

    env_data = load_env_data(source_dir)
    if not env_data:
        print(f"Erreur : env-data.json introuvable dans {source_dir}")
        sys.exit(1)

    har_path = find_har(source_dir)
    if not har_path:
        print(f"Erreur : aucun .har trouvé dans {source_dir} (ni dans "
              f"{RAW_DATA_DIR}/). spec_from_env_data() en a besoin pour "
              "détecter les infrastructures et découper le parcours.")
        sys.exit(1)

    audited_domain = infer_audited_domain(env_data, source_dir)

    try:
        spec, warnings = spec_from_env_data(env_data, str(har_path), audited_domain)
    except SpecError as exc:
        print(f"Erreur de spécification : {exc}")
        sys.exit(1)

    if warnings:
        print()
        for w in warnings:
            print(f"  ⚠ {w}")

    spec = resolve_visits_override(args.visits, spec)
    spec, instance_target_key = resolve_instance_override(
        args.instance, args.instance_source, args.instance_source_url, spec)

    reserves = calculation_reserves(spec)
    if reserves:
        print_reserves(reserves)
        print("[e-footprint] Calcul arrêté : la spécification a des réserves non assumées.")
        print("Corriger la spécification (cf. issues ci-dessus), puis relancer.")
        sys.exit(1)

    print_hypotheses(spec)

    print("[e-footprint] Construction du modèle (hypothétique)...")
    try:
        built = build_system(spec)
    except SpecError as exc:
        print(f"Erreur de construction : {exc}")
        sys.exit(1)
    print("[e-footprint] Calcul CO2e...")

    print("[e-footprint] Calcul des fourchettes (infra/usage)...")
    ranges = footprint_ranges_kg(spec)

    print_results(spec, built, ranges)

    print("[e-footprint] Sérialisation du modèle...")
    save_boavizta_model(built, source_dir)
    save_synthese_python(spec, built, ranges, source_dir, env_data, warnings, reserves)
    print()
    visits = spec.audience.visits_per_year.value if spec.audience and spec.audience.visits_per_year else 0
    print(f"  Trafic retenu : {visits:,.0f} visites/an")
    print("Pour relancer avec d'autres hypothèses :")
    _target = f" (--instance vise \"{instance_target_key}\")" if instance_target_key else ""
    print(f"  python3 {Path(__file__).name} {source_dir} --visits 500000 "
          f"--instance <type provider>{_target}")


if __name__ == "__main__":
    main()
