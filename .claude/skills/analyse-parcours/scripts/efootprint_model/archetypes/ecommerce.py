#!/usr/bin/env python3
"""
Archétype "e-commerce" : un site marchand avec un serveur applicatif, une
base de données (catalogue, comptes, commandes) et deux étapes distinctes
(navigation catalogue, tunnel de paiement) qui pèsent différemment.

POURQUOI DEUX ÉTAPES ET PAS UNE COMME dynamique_bdd.py
--------------------------------------------------------
Un site marchand n'a pas un poids uniforme : la navigation catalogue (fiches
produit, images) pèse et dure différemment du tunnel de paiement (formulaire
court, peu d'images). Les regrouper en une seule étape moyenne masquerait
cette différence dans le rapport (cf. StepSpec.intention, agrégation par
intention métier plutôt que par étape technique).

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

ARCHETYPE_KEY = "ecommerce"

# Repli SERVEUR GÉNÉRIQUE, même valeurs que dynamique_bdd.py (cf. sa docstring
# pour l'origine).
_GENERIC_POWER_W = 300.0
_GENERIC_FABRICATION_KG = 600.0
_GENERIC_PUE = 1.2

# Poids relatif catalogue/BDD par étape : les fiches produit et leurs images
# sont majoritairement servies par le serveur applicatif (assets statiques),
# le tunnel de paiement sollicite proportionnellement plus la base de données
# (vérifications de stock, création de commande). Décision de modélisation de
# cet archétype, PAS une mesure : à ajuster aux paramètres réels du site
# décrit, comme documenté dans son __init__ (cf. dynamique_bdd.py).
_CATALOG_WEB_SHARE = 0.85
_CHECKOUT_WEB_SHARE = 0.5


def apply(*, prefix, visits_per_year, catalog_weight_kb, checkout_weight_kb,
          catalog_time_seconds, checkout_time_seconds, catalog_share=0.8,
          country="FRANCE", phone_fraction=0.6, desktop_fraction=0.4,
          source_name, source_url=None):
    """Construit un fragment `SiteSpec` : serveur applicatif + BDD, deux étapes.

    prefix               : préfixe des clés, cf. dynamique_bdd.apply().
    visits_per_year      : trafic annuel du site décrit.
    catalog_weight_kb    : poids transféré d'une page catalogue type (kB).
    checkout_weight_kb   : poids transféré d'une page de paiement type (kB).
    catalog_time_seconds/checkout_time_seconds : temps passé sur chaque étape.
    catalog_share        : part des visites qui parcourent le catalogue SANS
                          aller jusqu'au paiement (entre 0 et 1) : le reste
                          des visites déclenche les deux étapes. Un panier
                          abandonné est donc modélisé comme une visite qui
                          ne compte que l'étape catalogue.
    country/phone_fraction/desktop_fraction : cf. dynamique_bdd.apply().
    source_name/source_url : provenance des paramètres, obligatoire.

    Retourne un SiteSpec à composer avec d'autres fragments, ou à utiliser
    seul. Le parcours retourné traverse les DEUX étapes : `catalog_share`
    influence seulement le poids relatif affiché en annexe (times_per_journey
    reste 1 pour chaque étape déclarée dans le parcours), la nuance
    "abandon de panier" n'est pas encore portée par le calcul lui-même.
    """
    if not (0.0 <= catalog_share <= 1.0):
        raise ValueError(f"catalog_share doit être entre 0 et 1, reçu {catalog_share!r}.")

    web = ServerSpec(
        key=f"{prefix}_web",
        label="Serveur applicatif",
        server_type=assumed_label(
            "autoscaling", source_name, source_url,
            comment="Mode de dimensionnement supposé par l'archétype ecommerce, "
                    "faute de mesure réelle du mode d'hébergement."),
        country=measured_label(country, source_name, source_url),
        power=script_default(_GENERIC_POWER_W, "W"),
        carbon_footprint_fabrication=script_default(_GENERIC_FABRICATION_KG, "kg"),
        pue=script_default(_GENERIC_PUE, "dimensionless"),
    )
    bdd = ServerSpec(
        key=f"{prefix}_bdd",
        label="Base de données (catalogue, comptes, commandes)",
        server_type=assumed_label(
            "autoscaling", source_name, source_url,
            comment="Mode de dimensionnement supposé par l'archétype ecommerce, "
                    "faute de mesure réelle du mode d'hébergement."),
        country=measured_label(country, source_name, source_url),
        power=script_default(_GENERIC_POWER_W, "W"),
        carbon_footprint_fabrication=script_default(_GENERIC_FABRICATION_KG, "kg"),
        pue=script_default(_GENERIC_PUE, "dimensionless"),
    )

    def _split_job(key_suffix, label, weight_kb, web_share):
        job_web = JobSpec(
            key=f"{prefix}_{key_suffix}_web",
            server_key=web.key,
            label=f"{label} (serveur applicatif)",
            data_transferred=measured(weight_kb * web_share, "kB", source_name, source_url),
        )
        job_bdd = JobSpec(
            key=f"{prefix}_{key_suffix}_bdd",
            server_key=bdd.key,
            label=f"{label} (base de données)",
            data_transferred=measured(weight_kb * (1 - web_share), "kB", source_name, source_url),
        )
        return job_web, job_bdd

    catalog_web, catalog_bdd = _split_job(
        "catalogue", "Navigation catalogue", catalog_weight_kb, _CATALOG_WEB_SHARE)
    checkout_web, checkout_bdd = _split_job(
        "paiement", "Tunnel de paiement", checkout_weight_kb, _CHECKOUT_WEB_SHARE)

    step_catalog = StepSpec(
        key=f"{prefix}_etape_catalogue",
        label="Navigation catalogue",
        intention="s'informer / choisir un produit",
        jobs={catalog_web.key: 1.0, catalog_bdd.key: 1.0},
        user_time=assumed(catalog_time_seconds, "s", source_name, source_url),
    )
    step_checkout = StepSpec(
        key=f"{prefix}_etape_paiement",
        label="Tunnel de paiement",
        intention="acheter",
        jobs={checkout_web.key: 1.0, checkout_bdd.key: 1.0},
        user_time=assumed(checkout_time_seconds, "s", source_name, source_url),
    )

    journey = JourneySpec(
        key=f"{prefix}_parcours",
        label="Parcours d'achat",
        steps=(step_catalog.key, step_checkout.key),
        notes=(f"Part des visites qui n'atteignent pas le paiement (panier "
               f"abandonné, non porté par le calcul) : {catalog_share:.0%}, "
               f"fourni par l'appelant à titre documentaire.",),
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
        servers=(web, bdd),
        jobs=(catalog_web, catalog_bdd, checkout_web, checkout_bdd),
        steps=(step_catalog, step_checkout),
        journeys=(journey,),
        audience=audience,
        archetypes=(ARCHETYPE_KEY,),
    )


if __name__ == "__main__":
    from ..build import build_system, total_kg
    from ..compose import collect_sources

    frag = apply(
        prefix="demo",
        visits_per_year=200_000,
        catalog_weight_kb=600,
        checkout_weight_kb=150,
        catalog_time_seconds=90,
        checkout_time_seconds=45,
        catalog_share=0.7,
        source_name="démonstration __main__ (données fictives)",
    )
    built = build_system(frag)
    total = total_kg(built)
    print(f"Archétype {ARCHETYPE_KEY} : System valide, {len(frag.servers)} serveurs, "
          f"{len(frag.steps)} étape(s), total {total:.1f} kg CO2e/an (fictif).")
    assert total > 0, "le total devrait être strictement positif"
    assert len(collect_sources(frag)) > 0, "toute valeur numérique doit être tracée"
    print("OK : démonstration cohérente.")
