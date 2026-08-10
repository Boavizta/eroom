#!/usr/bin/env python3
"""
Archétype "dynamique + BDD" : un site qui exécute du code métier à chaque
visite (formulaire, compte utilisateur, back-office), avec un serveur
applicatif et une base de données séparée.

CE QU'EST UN ARCHÉTYPE ICI
---------------------------
Un second moyen de produire un `SiteSpec` (spec.py), en plus de `from_har.py`.
`from_har.py` LIT un HAR déjà capturé ; un archétype ne lit rien : il PREND des
paramètres déjà connus (nombre de visites, poids d'une page, nombre de
serveurs...) et retourne un fragment de spécification prêt à composer. Utile
quand il n'y a pas encore de capture réseau, par exemple pendant un entretien
client avant tout audit.

Ni un cas figé ni un menu à cocher : un point de départ à ajuster aux
paramètres réels du site décrit, comme n'importe quel autre `SiteSpec`
(immuable, donc `dataclasses.replace()` fonctionne dessus normalement).

ZÉRO import e-footprint ici : comme `from_har.py`, ce module ne fait que
construire des dataclasses de `spec.py`, jamais d'objet e-footprint.

GÉNÉRICITÉ : aucun défaut chiffré tiré d'un site réel. Tous les paramètres
numériques sont des arguments obligatoires ou None (pas de valeur qui
ressemblerait à une mesure), conformément à `check_genericite.py`.
"""

from ..spec import (
    AudienceSpec,
    JobSpec,
    JourneySpec,
    ServerSpec,
    SiteSpec,
    StepSpec,
    assumed,
    measured,
    measured_label,
    script_default,
)

ARCHETYPE_KEY = "dynamique_bdd"

# Repli SERVEUR GÉNÉRIQUE, faute de provider cloud connu : mêmes valeurs que
# le repli déjà établi dans from_har.py::_server_spec_from_info() (300 W,
# 600 kg, PUE 1,2). Pas une mesure du site décrit : la valeur par défaut de la
# classe Server d'e-footprint elle-même (server.py:34-37), reprise ici plutôt
# qu'inventée à nouveau.
_GENERIC_POWER_W = 300.0
_GENERIC_FABRICATION_KG = 600.0
_GENERIC_PUE = 1.2


def apply(*, prefix, visits_per_year, page_weight_kb, user_time_seconds, country="FRANCE",
          phone_fraction=0.6, desktop_fraction=0.4, source_name, source_url=None):
    """Construit un fragment `SiteSpec` : serveur applicatif + base de données.

    prefix          : préfixe des clés (serveur/traitement/étape/parcours), pour
                      pouvoir appliquer cet archétype plusieurs fois dans le
                      même site sans collision (cf. compose.py).
    visits_per_year : trafic annuel du site décrit (nombre de visites).
    page_weight_kb  : poids transféré d'une visite type (kB), toutes requêtes
                      confondues (page + appels API qu'elle déclenche).
    user_time_seconds : temps passé par le visiteur sur cette étape (secondes).
                      Champ critique (cf. StepSpec) : sans HAR à mesurer, cet
                      archétype ne peut pas en déduire un temps de lecture
                      Nielsen (temps_utilisateur.py, réservé à from_har.py) ;
                      il faut le fournir, même comme hypothèse assumée.
    country         : pays d'hébergement (nom reconnu par e-footprint, ex.
                      "FRANCE", "GERMANY").
    phone_fraction / desktop_fraction : mix appareils de l'audience, doit
                      sommer à 1 (cf. AudienceSpec._check_pair()).
    source_name/source_url : provenance des paramètres numériques (ex.
                      "entretien client du 12/08/2026", "hypothèse de brief").
                      Obligatoire : un archétype ne peut pas produire un
                      chiffre sans provenance (cf. require_traced()).

    Retourne un SiteSpec à composer avec d'autres fragments via `compose()`,
    ou à utiliser seul.
    """
    generic_hardware = dict(
        power=script_default(_GENERIC_POWER_W, "W"),
        carbon_footprint_fabrication=script_default(_GENERIC_FABRICATION_KG, "kg"),
        pue=script_default(_GENERIC_PUE, "dimensionless"),
    )
    web = ServerSpec(
        key=f"{prefix}_web",
        label="Serveur applicatif",
        server_type=assumed_label_or_default("autoscaling", source_name, source_url),
        country=measured_label(country, source_name, source_url),
        **generic_hardware,
    )
    bdd = ServerSpec(
        key=f"{prefix}_bdd",
        label="Base de données",
        server_type=assumed_label_or_default("autoscaling", source_name, source_url),
        country=measured_label(country, source_name, source_url),
        **generic_hardware,
    )

    job_web = JobSpec(
        key=f"{prefix}_requete_web",
        server_key=web.key,
        label="Requête page (serveur applicatif)",
        data_transferred=measured(page_weight_kb * 0.8, "kB", source_name, source_url,
                                   comment="80 % du poids de la visite : page + assets "
                                           "servis par le serveur applicatif."),
    )
    job_bdd = JobSpec(
        key=f"{prefix}_requete_bdd",
        server_key=bdd.key,
        label="Requête base de données",
        data_transferred=measured(page_weight_kb * 0.2, "kB", source_name, source_url,
                                   comment="20 % du poids de la visite : réponses de "
                                           "requêtes vers la base de données."),
    )

    step = StepSpec(
        key=f"{prefix}_visite",
        label="Visite type",
        jobs={job_web.key: 1.0, job_bdd.key: 1.0},
        user_time=assumed(user_time_seconds, "s", source_name, source_url,
                           comment="Temps utilisateur fourni directement à l'archétype "
                                   "(pas de page HTML à mesurer, contrairement à "
                                   "from_har.py) : à remplacer par une mesure du site "
                                   "réel dès qu'elle existe."),
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
        servers=(web, bdd),
        jobs=(job_web, job_bdd),
        steps=(step,),
        journeys=(journey,),
        audience=audience,
        archetypes=(ARCHETYPE_KEY,),
    )


def assumed_label_or_default(value, source_name, source_url):
    """Mode de dimensionnement : SUPPOSÉ tant que l'archétype ne reçoit pas de
    mesure réelle (aucune capture réseau ne le révèle, à la différence de
    `from_har.py`). Passe par `assumed_label`, jamais un défaut du script :
    c'est un choix actif de l'archétype, pas une valeur inventée en silence."""
    from ..spec import assumed_label
    return assumed_label(
        value, source_name, source_url,
        comment="Mode de dimensionnement supposé par l'archétype dynamique_bdd, "
                "faute de mesure réelle du mode d'hébergement.")


if __name__ == "__main__":
    from ..build import build_system, total_kg
    from ..compose import collect_sources

    frag = apply(
        prefix="demo",
        visits_per_year=50_000,
        page_weight_kb=250,
        user_time_seconds=45,
        source_name="démonstration __main__ (données fictives)",
    )
    built = build_system(frag)
    total = total_kg(built)
    print(f"Archétype {ARCHETYPE_KEY} : System valide, {len(frag.servers)} serveurs, "
          f"{len(frag.steps)} étape(s), total {total:.1f} kg CO2e/an (fictif).")
    assert total > 0, "le total devrait être strictement positif"
    assert len(collect_sources(frag)) > 0, "toute valeur numérique doit être tracée"
    print("OK : démonstration cohérente.")
