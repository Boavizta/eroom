#!/usr/bin/env python3
"""
Construction du modèle e-footprint depuis une spécification déclarative.

SEUL MODULE DE LA BIBLIOTHÈQUE QUI IMPORTE E-FOOTPRINT
-------------------------------------------------------
`spec.py` et `compose.py` restent du Python pur, testables sans la librairie
installée. Ce fichier est le point où cette propriété s'arrête : il a besoin
d'e-footprint pour s'importer. `efootprint_model/__init__.py` ne le réexporte
donc jamais (cf. son garde-fou, contrôlé par check_efootprint_spec.py).

ORDRE D'INSTANCIATION IMPOSÉ
----------------------------
Storage -> Server -> Job -> Step -> Journey -> UsagePattern -> System.
Chaque classe e-footprint référence la précédente ; le respecter évite d'avoir
à reconstruire un objet après coup (un ModelingObject ne se mute pas
proprement une fois lié à un System, cf. handoff du 05/08/2026).

CE QUE `build_system()` NE FAIT PAS
------------------------------------
Il ne choisit aucune valeur : chaque grandeur vient d'un `Traced` de la
spécification, ou du défaut de la LIBRAIRIE (jamais d'un défaut inventé ici).
Un champ structurellement indispensable à e-footprint mais absent de la
spécification (pays de l'audience, volume de trafic, jeu de champs serveur
incomplet) fait échouer la construction avec un message explicite, plutôt que
de deviner.
"""

from dataclasses import dataclass, field

from .spec import SiteSpec, SpecError

# Les 3 niveaux de confiance reconnus par e-footprint, à ne pas confondre avec
# nos 7 niveaux (CONFIDENCE_LEVELS), plus fins et déjà tracés dans la spec.
# Cette table ne fait que renseigner poliment le champ `confidence` interne
# d'e-footprint ; elle n'influence aucun calcul, et la traçabilité complète du
# rapport vient de la spec (collect_sources()), pas d'ici.
_EFOOTPRINT_CONFIDENCE = {"high": "high", "medium": "medium", "low": "low"}


def _efootprint_confidence(traced):
    return _EFOOTPRINT_CONFIDENCE.get(traced.confidence)


def _get_source(source_cache, name, url):
    """Un seul objet Source par (nom, url) : deux Traced qui partagent une
    provenance ne doivent pas en fabriquer deux instances distinctes."""
    from efootprint.abstract_modeling_classes.explainable_object_base_class import Source

    key = (name, url)
    if key not in source_cache:
        source_cache[key] = Source(name, url)
    return source_cache[key]


def to_source_value(traced, source_cache):
    """Traced -> SourceValue (kind="value") ou SourceObject (kind="object").

    SEUL point de passage de la bibliothèque vers les classes source
    d'e-footprint. Le kind a été tranché en Python pur dès `spec.py` :
    ce module n'a pas à redeviner SourceValue vs SourceObject.
    """
    from efootprint.abstract_modeling_classes.source_objects import SourceObject, SourceValue
    from efootprint.constants.units import u

    kwargs = {}
    if traced.comment:
        kwargs["comment"] = traced.comment
    if traced.has_source:
        kwargs["source"] = _get_source(source_cache, traced.source_name, traced.source_url)
    confidence = _efootprint_confidence(traced)
    if confidence is not None:
        kwargs["confidence"] = confidence

    if traced.kind == "object":
        return SourceObject(traced.value, **kwargs)
    return SourceValue(traced.value * u.parse_units(traced.unit), **kwargs)


def _map_country(name):
    """Nom e-footprint du pays -> instance Country.

    Lève plutôt que de retomber sur un pays par défaut : un pays inconnu de
    la librairie qui passerait en silence ferait porter au rapport une
    intensité carbone qui n'est pas celle demandée.
    """
    from efootprint.constants.countries import Countries

    if hasattr(Countries, name):
        return getattr(Countries, name)()
    raise SpecError(
        f"pays inconnu de la librairie e-footprint : {name!r}. "
        f"Valeurs attendues : un attribut de efootprint.constants.countries.Countries."
    )


# ---------------------------------------------------------------------------
# Serveur + stockage
# ---------------------------------------------------------------------------

def _build_storage(server_spec, source_cache):
    from efootprint.core.hardware.storage import Storage

    kwargs = {}
    if server_spec.storage_gb is not None:
        kwargs["base_storage_need"] = to_source_value(server_spec.storage_gb, source_cache)
    return Storage.from_defaults(f"Stockage {server_spec.label}", **kwargs)


def _build_server(server_spec, source_cache):
    """Construit le Storage puis le Server, dans cet ordre imposé.

    Deux jeux de champs mutuellement exclusifs, comme documenté dans
    `ServerSpec` : cloud public (provider + instance_type, voie Boavizta) ou
    générique (power + carbon_footprint_fabrication + pue). Ni l'un ni
    l'autre complet -> la spécification ne dit pas assez pour choisir une
    classe e-footprint, ce qui doit arrêter la construction, pas la deviner.
    """
    storage = _build_storage(server_spec, source_cache)

    common = {}
    if server_spec.server_type is not None:
        common["server_type"] = to_source_value(server_spec.server_type, source_cache)
    if server_spec.carbon_intensity is not None:
        common["average_carbon_intensity"] = to_source_value(server_spec.carbon_intensity, source_cache)
    if server_spec.base_ram is not None:
        common["base_ram_consumption"] = to_source_value(server_spec.base_ram, source_cache)
    if server_spec.base_compute is not None:
        common["base_compute_consumption"] = to_source_value(server_spec.base_compute, source_cache)

    is_cloud = server_spec.provider is not None and server_spec.instance_type is not None
    is_generic = (server_spec.power is not None
                  and server_spec.carbon_footprint_fabrication is not None
                  and server_spec.pue is not None)

    if is_cloud:
        from efootprint.builders.hardware.boavizta_cloud_server import BoaviztaCloudServer
        return BoaviztaCloudServer.from_defaults(
            server_spec.label,
            provider=to_source_value(server_spec.provider, source_cache),
            instance_type=to_source_value(server_spec.instance_type, source_cache),
            storage=storage,
            **common,
        )
    if is_generic:
        from efootprint.core.hardware.server import Server
        return Server.from_defaults(
            server_spec.label,
            power=to_source_value(server_spec.power, source_cache),
            carbon_footprint_fabrication=to_source_value(server_spec.carbon_footprint_fabrication, source_cache),
            power_usage_effectiveness=to_source_value(server_spec.pue, source_cache),
            storage=storage,
            **common,
        )
    raise SpecError(
        f"ServerSpec[{server_spec.key}] : ni le jeu cloud (provider + instance_type) "
        "ni le jeu générique (power + carbon_footprint_fabrication + pue) ne sont "
        "complets. Impossible de savoir quelle classe e-footprint instancier."
    )


# ---------------------------------------------------------------------------
# Traitements et étapes
# ---------------------------------------------------------------------------

def _build_job(job_spec, servers_by_key, source_cache):
    from efootprint.core.usage.job import Job

    if job_spec.server_key not in servers_by_key:
        # validate_spec() l'aurait déjà refusé plus tôt : filet de second rang,
        # utile seulement si build_system() est appelé sur une spec qui n'est
        # pas passée par require_calculable().
        raise SpecError(
            f"JobSpec[{job_spec.key}] : serveur \"{job_spec.server_key}\" absent "
            "des serveurs construits."
        )

    kwargs = {}
    for field_name, kwarg_name in (
        ("request_duration", "request_duration"),
        ("compute_needed", "compute_needed"),
        ("ram_needed", "ram_needed"),
        ("data_stored", "data_stored"),
    ):
        traced = getattr(job_spec, field_name)
        if traced is not None:
            kwargs[kwarg_name] = to_source_value(traced, source_cache)

    return Job.from_defaults(
        job_spec.label,
        server=servers_by_key[job_spec.server_key],
        data_transferred=to_source_value(job_spec.data_transferred, source_cache),
        **kwargs,
    )


def _build_step(step_spec, jobs_by_key, source_cache):
    from efootprint.core.usage.usage_journey_step import UsageJourneyStep

    jobs = {}
    for job_key, weight in step_spec.jobs.items():
        if job_key not in jobs_by_key:
            raise SpecError(
                f"StepSpec[{step_spec.key}] : traitement \"{job_key}\" absent "
                "des traitements construits."
            )
        jobs[jobs_by_key[job_key]] = weight

    kwargs = {}
    if step_spec.user_time is not None:
        kwargs["user_time_spent"] = to_source_value(step_spec.user_time, source_cache)

    return UsageJourneyStep.from_defaults(step_spec.label, jobs=jobs, **kwargs)


# ---------------------------------------------------------------------------
# Parcours et motifs d'usage
# ---------------------------------------------------------------------------

# Device/réseau associés à chaque branche du mix appareils. Convention du
# script historique (run_efootprint.py) : le mobile est modélisé sur réseau
# mobile, le desktop sur wifi. `wifi_fraction`/`mobile_fraction` d'AudienceSpec
# restent informatifs pour l'instant, comme dans le calcul actuel : les
# généraliser en un vrai croisement 2x2 est un sujet de lot ultérieur, pas de
# celui-ci (la non-régression exige de reproduire le comportement actuel).
_DEVICE_MIX = ("phone_fraction", "desktop_fraction")


def _build_usage_patterns(spec, journey, servers_by_key, source_cache):
    from efootprint.builders.timeseries import ExplainableHourlyQuantitiesFromFormInputs
    from efootprint.constants.sources import Sources
    from efootprint.core.hardware.device import Device
    from efootprint.core.hardware.network import Network
    from efootprint.core.usage.usage_pattern import UsagePattern

    audience = spec.audience
    if audience is None:
        raise SpecError(f"SiteSpec[{spec.name}] : aucune audience, impossible de "
                        "construire un motif d'usage. Passer par require_calculable() "
                        "avant build_system() pour un refus plus lisible.")
    if audience.visits_per_year is None:
        raise SpecError(
            f"AudienceSpec[{audience.key}] : \"visits_per_year\" absent. "
            "Une audience sans volume ne peut pas alimenter un motif d'usage : "
            "renseigner le trafic, même approximatif et signalé comme tel."
        )
    if audience.country is None:
        raise SpecError(
            f"AudienceSpec[{audience.key}] : \"country\" absent. Un motif d'usage "
            "e-footprint exige un pays (il pilote l'intensité carbone locale des "
            "appareils du visiteur)."
        )
    if audience.phone_fraction is None or audience.desktop_fraction is None:
        raise SpecError(
            f"AudienceSpec[{audience.key}] : le mix appareils (phone_fraction/"
            "desktop_fraction) est requis pour construire les motifs d'usage. "
            "Un mix absent n'a pas de repli générique : quel appareil "
            "représenterait l'audience ?"
        )

    country = _map_country(audience.country.value)
    visits = audience.visits_per_year.value
    visits_mobile = round(visits * audience.phone_fraction.value)
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

    patterns = []
    for label, device, network, volume in (
        ("mobile", Device.smartphone(), Network.mobile_network(), visits_mobile),
        ("desktop", Device.laptop(), Network.wifi_network(), visits_desktop),
    ):
        if volume <= 0:
            continue
        patterns.append(UsagePattern(
            f"Visiteurs {label} ({volume:,} visites/an)".replace(",", " "),
            journey,
            [device],
            network,
            country,
            _hourly_volume(volume),
        ))
    return patterns


# ---------------------------------------------------------------------------
# Assemblage complet
# ---------------------------------------------------------------------------

@dataclass
class BuiltModel:
    """Le modèle construit, avec les index nécessaires à l'attribution.

    Sans `servers_by_key`/`jobs_by_key`/`steps_by_key`, les résultats
    d'attribution reviendraient indexés par objet e-footprint, sans moyen de
    les rattacher à l'intention métier qui les a produits.
    """

    spec: SiteSpec
    system: "System"  # noqa: F821 - annotation textuelle, e-footprint non importé au chargement du module
    servers_by_key: dict = field(default_factory=dict)
    jobs_by_key: dict = field(default_factory=dict)
    steps_by_key: dict = field(default_factory=dict)


def build_system(spec, *, accepted_reserves=()):
    """Construit un System e-footprint depuis une SiteSpec.

    Appelle `require_calculable()` en premier : construire un modèle depuis
    une spécification qui a des réserves non assumées produirait un chiffre
    faux sans le dire. `accepted_reserves` se transmet tel quel.
    """
    from .compose import require_calculable
    from efootprint.core.system import System
    from efootprint.core.usage.usage_journey import UsageJourney

    require_calculable(spec, accepted_reserves=accepted_reserves)

    source_cache = {}

    servers_by_key = {server.key: _build_server(server, source_cache) for server in spec.servers}
    jobs_by_key = {job.key: _build_job(job, servers_by_key, source_cache) for job in spec.jobs}
    steps_by_key = {step.key: _build_step(step, jobs_by_key, source_cache) for step in spec.steps}

    audience = spec.audience
    journey_key = audience.journey_key if audience.journey_key else _sole_journey_key(spec)
    journey_spec = spec.journey_by_key(journey_key)

    # Un seul UsageJourney, PARTAGÉ entre les motifs mobile et desktop : vérifié
    # possible (handoff du 05/08/2026), et c'est la seule façon de ne pas
    # dupliquer le graphe. L'ordre des étapes du parcours doit être préservé
    # (il porte le délai cumulé entre étapes) : construit par itération sur
    # `journey_spec.steps`, jamais via un dict non ordonné.
    uj_steps = {steps_by_key[step_key]: journey_spec_step(spec, step_key).times_per_journey
                for step_key in journey_spec.steps}
    journey = UsageJourney(journey_spec.label, uj_steps=uj_steps)

    usage_patterns = _build_usage_patterns(spec, journey, servers_by_key, source_cache)
    system = System(f"Estimation CO2e : {spec.name}", usage_patterns, edge_usage_patterns=[])

    return BuiltModel(spec=spec, system=system, servers_by_key=servers_by_key,
                      jobs_by_key=jobs_by_key, steps_by_key=steps_by_key)


def journey_spec_step(spec, step_key):
    return spec.step_by_key(step_key)


def _sole_journey_key(spec):
    """Le parcours à utiliser quand l'audience n'en désigne aucun explicitement.

    N'accepte que le cas sans ambiguïté (un seul parcours déclaré) : deviner
    parmi plusieurs parcours inventerait une donnée d'audience que personne
    n'a mesurée.
    """
    if len(spec.journeys) == 1:
        return spec.journeys[0].key
    raise SpecError(
        f"SiteSpec[{spec.name}] : l'audience ne désigne aucun parcours "
        f"(journey_key) et {len(spec.journeys)} parcours sont déclarés. "
        "Renseigner AudienceSpec.journey_key pour lever l'ambiguïté."
    )


# ---------------------------------------------------------------------------
# Extraction propre des résultats (sans regex)
# ---------------------------------------------------------------------------

def fabrication_kg(built):
    """Empreinte de fabrication par catégorie, en kg CO2e/an, lue directement
    sur les grandeurs e-footprint (magnitude convertie), jamais par regex sur
    une représentation texte."""
    from efootprint.constants.units import u
    return {category: value.value.to(u.kg).magnitude
            for category, value in built.system.total_fabrication_footprint_sum_over_period.items()}


def energy_kg(built):
    """Empreinte d'énergie par catégorie, en kg CO2e/an. Même principe que
    `fabrication_kg()`."""
    from efootprint.constants.units import u
    return {category: value.value.to(u.kg).magnitude
            for category, value in built.system.total_energy_footprint_sum_over_period.items()}


def total_kg(built):
    """Total CO2e/an, somme des deux catégories ci-dessus."""
    fab = fabrication_kg(built)
    energy = energy_kg(built)
    return sum(fab.values()) + sum(energy.values())


def consistency_report(built, tolerance_kg=1e-3, relative_tolerance=1e-6):
    """Vérifie que notre somme par catégorie retombe sur la somme PAR OBJET
    que la librairie calcule (`fabrication_footprint_sum_over_period` /
    `energy_footprint_sum_over_period`), objet par objet plutôt que par
    catégorie agrégée.

    Ce n'est pas une preuve que le CHIFFRE est juste : c'est une preuve que
    notre lecture par catégorie n'a PERDU ni DOUBLÉ aucune contribution en
    route. Un écart ici signale un bug d'extraction, pas un désaccord de
    modélisation.

    NE PAS comparer à `system.total_footprint` : cet attribut arrondit à 4
    décimales CHAQUE HEURE avant de sommer 8760 valeurs (bien vu en pratique :
    170,82 kg contre 170,904 kg ici), un artefact de précision de la
    librairie, pas un désaccord sur le modèle.

    Tolérance ABSOLUE et RELATIVE : un modèle à plus d'objets (plusieurs
    serveurs/jobs) accumule davantage d'arrondis flottants sans qu'il y ait
    de bug (mesuré : 0,0026 kg d'écart sur un total de 14 481 kg à 3 serveurs,
    soit 1,8e-7 en relatif — largement sous tolerance_kg en absolu mais visible
    si on ne regardait que l'absolu sur un total nettement plus petit).
    """
    from efootprint.constants.units import u

    our_total = total_kg(built)
    per_object_total = sum(
        value.value.to(u.kg).magnitude
        for objs in built.system.fabrication_footprint_sum_over_period.values()
        for value in objs.values()
    ) + sum(
        value.value.to(u.kg).magnitude
        for objs in built.system.energy_footprint_sum_over_period.values()
        for value in objs.values()
    )
    delta = abs(our_total - per_object_total)
    allowed = max(tolerance_kg, relative_tolerance * abs(per_object_total))
    return {
        "total_kg": round(our_total, 4),
        "per_object_total_kg": round(per_object_total, 4),
        "max_delta_kg": round(delta, 6),
        "ok": delta <= allowed,
    }
