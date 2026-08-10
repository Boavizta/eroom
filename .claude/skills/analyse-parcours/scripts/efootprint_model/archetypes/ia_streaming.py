#!/usr/bin/env python3
"""
Archétype "IA/streaming" : un site qui appelle un modèle d'IA générative
tiers (chatbot, assistant, génération de contenu), en plus de son serveur
applicatif habituel.

CE QUE LE CALCUL IA COUVRE, ET CE QU'IL NE COUVRE PAS
-------------------------------------------------------
Le poids transféré (prompt envoyé, réponse reçue) est compté comme n'importe
quel traitement réseau (JobSpec.data_transferred), ET l'empreinte du CALCUL
du modèle chez le fournisseur est comptée EN PLUS via EcoLogits
(JobSpec.external_api, cf. spec.py::ExternalApiSpec et
build.py::_build_external_api()). Les deux ne mesurent pas la même chose :
le premier est le trafic, le second est la puce qui tourne chez le
fournisseur pour produire la réponse.

EcoLogits exige un modèle RECONNU dans son catalogue (provider + model_name) :
un nom qui n'y figure pas fait échouer la construction avec le message de la
librairie elle-même (`_get_model_or_raise()`), jamais une valeur inventée en
repli.

ZÉRO import e-footprint ici : comme les autres archétypes, ce module ne
construit que des dataclasses de spec.py.
"""

from ..spec import (
    AudienceSpec,
    ExternalApiSpec,
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

ARCHETYPE_KEY = "ia_streaming"

# Repli SERVEUR GÉNÉRIQUE, même valeurs que dynamique_bdd.py (cf. sa docstring
# pour l'origine : défaut de la classe Server d'e-footprint elle-même).
_GENERIC_POWER_W = 300.0
_GENERIC_FABRICATION_KG = 600.0
_GENERIC_PUE = 1.2


def apply(*, prefix, visits_per_year, page_weight_kb, user_time_seconds,
          ai_provider, ai_model_name, ai_output_tokens, ai_calls_per_visit=1.0,
          country="FRANCE", phone_fraction=0.6, desktop_fraction=0.4,
          source_name, source_url=None):
    """Construit un fragment `SiteSpec` : serveur applicatif + appel IA.

    prefix             : préfixe des clés, cf. dynamique_bdd.apply().
    visits_per_year     : trafic annuel du site décrit.
    page_weight_kb       : poids transféré (kB) du prompt envoyé et de la
                          réponse reçue, PAR appel IA.
    user_time_seconds   : temps passé par le visiteur sur l'étape.
    ai_provider          : provider reconnu du catalogue EcoLogits (ex.
                          "anthropic", "openai", "mistralai").
    ai_model_name        : nom de modèle reconnu de ce provider (ex.
                          "claude-sonnet-4-5"). Une valeur inconnue fait
                          échouer la construction (EcoLogits, pas une
                          hypothèse de ce module).
    ai_output_tokens     : nombre moyen de tokens générés par appel : pilote
                          le calcul EcoLogits (énergie + fabrication).
    ai_calls_per_visit   : nombre d'appels IA déclenchés par une visite type
                          (ex. plusieurs tours de conversation).
    country/phone_fraction/desktop_fraction : cf. dynamique_bdd.apply().
    source_name/source_url : provenance des paramètres, obligatoire.

    Retourne un SiteSpec à composer avec d'autres fragments, ou à utiliser
    seul.
    """
    web = ServerSpec(
        key=f"{prefix}_web",
        label="Serveur applicatif",
        server_type=assumed_label(
            "autoscaling", source_name, source_url,
            comment="Mode de dimensionnement supposé par l'archétype "
                    "ia_streaming, faute de mesure réelle du mode d'hébergement."),
        country=measured_label(country, source_name, source_url),
        power=script_default(_GENERIC_POWER_W, "W"),
        carbon_footprint_fabrication=script_default(_GENERIC_FABRICATION_KG, "kg"),
        pue=script_default(_GENERIC_PUE, "dimensionless"),
    )

    job_web = JobSpec(
        key=f"{prefix}_requete_web",
        server_key=web.key,
        label="Requête page (serveur applicatif)",
        data_transferred=measured(page_weight_kb, "kB", source_name, source_url,
                                   comment="Poids de la page hors prompt/réponse IA, "
                                           "compté séparément par le traitement IA."),
    )
    job_ai = JobSpec(
        key=f"{prefix}_appel_ia",
        server_key=web.key,
        label=f"Appel IA ({ai_provider}/{ai_model_name})",
        data_transferred=measured(page_weight_kb * 0.1, "kB", source_name, source_url,
                                   comment="Estimation du poids réseau du prompt envoyé "
                                           "et de la réponse reçue (texte), distinct du "
                                           "calcul du modèle compté via external_api."),
        external_api=ExternalApiSpec(
            provider=ai_provider,
            model_name=ai_model_name,
            output_tokens=measured(ai_output_tokens, "dimensionless", source_name, source_url),
            request_count_per_step=ai_calls_per_visit,
        ),
    )

    step = StepSpec(
        key=f"{prefix}_visite",
        label="Visite type",
        jobs={job_web.key: 1.0, job_ai.key: ai_calls_per_visit},
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
        servers=(web,),
        jobs=(job_web, job_ai),
        steps=(step,),
        journeys=(journey,),
        audience=audience,
        archetypes=(ARCHETYPE_KEY,),
    )


if __name__ == "__main__":
    from ..build import build_system, energy_kg, fabrication_kg, total_kg
    from ..compose import collect_sources

    frag = apply(
        prefix="demo",
        visits_per_year=1_000,
        page_weight_kb=10,
        user_time_seconds=60,
        ai_provider="anthropic",
        ai_model_name="claude-sonnet-4-5",
        ai_output_tokens=300,
        source_name="démonstration __main__ (données fictives)",
    )
    built = build_system(frag)
    fab = fabrication_kg(built)
    energy = energy_kg(built)
    total = total_kg(built)
    print(f"Archétype {ARCHETYPE_KEY} : System valide, {len(frag.servers)} serveur(s), "
          f"{len(frag.steps)} étape(s), total {total:.1f} kg CO2e/an (fictif).")
    print(f"  dont ExternalAPIs : fabrication {fab.get('ExternalAPIs', 0):.4f} kg, "
          f"énergie {energy.get('ExternalAPIs', 0):.4f} kg.")
    assert total > 0, "le total devrait être strictement positif"
    assert fab.get("ExternalAPIs", 0) > 0 or energy.get("ExternalAPIs", 0) > 0, \
        "le calcul IA devrait produire une empreinte non nulle"
    assert len(collect_sources(frag)) > 0, "toute valeur numérique doit être tracée"
    print("OK : démonstration cohérente.")
