#!/usr/bin/env python3
"""
Archétype "statique + CDN" : un site vitrine dont les pages sont des fichiers
déjà prêts (HTML/CSS/JS/images), servis par un CDN, sans code métier exécuté
par visite (pas de base de données, cf. dynamique_bdd.py pour ce cas).

CE QUE CE MODULE CAPTURE, ET CE QU'IL NE CAPTURE PAS
------------------------------------------------------
Un seul serveur (celui qui héberge les fichiers d'origine) : un CDN ne
possède pas de datacenter propre attribuable au site (cf. spec.py::
ThirdPartyHost, décision déjà prise pour from_har.py). Les polices de
caractères, trackers et autres hôtes tiers observables sur un vrai site vitrine
peuvent être ajoutés via `third_party_hosts` sur le SiteSpec retourné (ils
restent RÉSEAU SEULEMENT).

ZÉRO import e-footprint ici, comme les autres archétypes.
"""

from ..spec import (
    AudienceSpec,
    JobSpec,
    JourneySpec,
    ServerSpec,
    SiteSpec,
    StepSpec,
    assumed,
    assumed_label,
    measured,
    measured_label,
    script_default,
)

ARCHETYPE_KEY = "statique_cdn"

# Repli SERVEUR GÉNÉRIQUE, même valeurs que dynamique_bdd.py (cf. sa docstring
# pour l'origine).
_GENERIC_POWER_W = 300.0
_GENERIC_FABRICATION_KG = 600.0
_GENERIC_PUE = 1.2


def apply(*, prefix, visits_per_year, page_weight_kb, user_time_seconds,
          country="FRANCE", phone_fraction=0.6, desktop_fraction=0.4,
          source_name, source_url=None):
    """Construit un fragment `SiteSpec` : un serveur d'origine statique.

    prefix          : préfixe des clés, cf. dynamique_bdd.apply().
    visits_per_year : trafic annuel du site décrit.
    page_weight_kb  : poids transféré d'une page type (kB), fichiers statiques
                      compris (HTML/CSS/JS/images).
    user_time_seconds : temps passé par le visiteur sur cette étape.
    country/phone_fraction/desktop_fraction : cf. dynamique_bdd.apply().
    source_name/source_url : provenance des paramètres, obligatoire.

    Retourne un SiteSpec à composer avec d'autres fragments, ou à utiliser
    seul. Pour ajouter des hôtes tiers observés (CDN, polices, trackers),
    composer ensuite avec `compose(frag, third_party_hosts=(...))`.
    """
    origin = ServerSpec(
        key=f"{prefix}_origin",
        label="Serveur d'origine (fichiers statiques)",
        server_type=assumed_label(
            "autoscaling", source_name, source_url,
            comment="Mode de dimensionnement supposé par l'archétype "
                    "statique_cdn, faute de mesure réelle du mode d'hébergement."),
        country=measured_label(country, source_name, source_url),
        power=script_default(_GENERIC_POWER_W, "W"),
        carbon_footprint_fabrication=script_default(_GENERIC_FABRICATION_KG, "kg"),
        pue=script_default(_GENERIC_PUE, "dimensionless"),
    )

    job = JobSpec(
        key=f"{prefix}_requete",
        server_key=origin.key,
        label="Requête page (fichiers statiques)",
        data_transferred=measured(page_weight_kb, "kB", source_name, source_url,
                                   comment="Poids transféré, tel que servi par le CDN : "
                                           "pas de traitement métier côté serveur."),
    )

    step = StepSpec(
        key=f"{prefix}_visite",
        label="Visite type",
        jobs={job.key: 1.0},
        user_time=assumed(user_time_seconds, "s", source_name, source_url,
                           comment="Temps utilisateur fourni directement à l'archétype "
                                   "(pas de page HTML à mesurer, contrairement à "
                                   "from_har.py)."),
    )
    journey = JourneySpec(
        key=f"{prefix}_parcours",
        label="Parcours type",
        steps=(step.key,),
    )
    audience = AudienceSpec(
        key=f"{prefix}_audience",
        label="Audience",
        visits_per_year=measured(visits_per_year, "dimensionless", source_name, source_url),
        phone_fraction=assumed(phone_fraction, "dimensionless", source_name, source_url),
        desktop_fraction=assumed(desktop_fraction, "dimensionless", source_name, source_url),
        country=measured_label(country, source_name, source_url),
        journey_key=journey.key,
    )

    return SiteSpec(
        name=f"Archétype {ARCHETYPE_KEY} ({prefix})",
        servers=(origin,),
        jobs=(job,),
        steps=(step,),
        journeys=(journey,),
        audience=audience,
        archetypes=(ARCHETYPE_KEY,),
    )


if __name__ == "__main__":
    from ..build import build_system, total_kg
    from ..compose import collect_sources

    frag = apply(
        prefix="demo",
        visits_per_year=100_000,
        page_weight_kb=800,
        user_time_seconds=20,
        source_name="démonstration __main__ (données fictives)",
    )
    built = build_system(frag)
    total = total_kg(built)
    print(f"Archétype {ARCHETYPE_KEY} : System valide, {len(frag.servers)} serveur(s), "
          f"{len(frag.steps)} étape(s), total {total:.1f} kg CO2e/an (fictif).")
    assert total > 0, "le total devrait être strictement positif"
    assert len(collect_sources(frag)) > 0, "toute valeur numérique doit être tracée"
    print("OK : démonstration cohérente.")
