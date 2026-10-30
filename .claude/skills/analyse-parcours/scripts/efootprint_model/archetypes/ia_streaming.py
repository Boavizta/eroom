#!/usr/bin/env python3
"""
Archetype "AI/streaming": a site that calls a third-party generative AI model
(chatbot, assistant, content generation), in addition to its usual application
server.

WHAT THE AI CALCULATION COVERS, AND WHAT IT DOES NOT
----------------------------------------------------
The transferred weight (prompt sent, response received) is counted like any
network job (JobSpec.data_transferred), AND the footprint of the model's
COMPUTATION at the provider is counted IN ADDITION via EcoLogits
(JobSpec.external_api, cf. spec.py::ExternalApiSpec and
build.py::_build_external_api()). The two do not measure the same thing: the
first is the traffic, the second is the chip running at the provider to produce
the response.

EcoLogits requires a model RECOGNIZED in its catalog (provider + model_name):
a name not in it fails the build with the library's own message
(`_get_model_or_raise()`), never an invented fallback value.

ZERO e-footprint import here: like the other archetypes, this module only
builds spec.py dataclasses.
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

# GENERIC SERVER fallback, same values as dynamic_db.py (cf. its docstring for
# the origin: the default of e-footprint's own Server class).
_GENERIC_POWER_W = 300.0
_GENERIC_FABRICATION_KG = 600.0
_GENERIC_PUE = 1.2


def apply(*, prefix, visits_per_year, page_weight_kb, user_time_seconds,
          ai_provider, ai_model_name, ai_output_tokens, ai_calls_per_visit=1.0,
          country="FRANCE", phone_fraction=0.6, desktop_fraction=0.4,
          source_name, source_url=None):
    """Builds a `SiteSpec` fragment: application server + AI call.

    prefix             : key prefix, cf. dynamic_db.apply().
    visits_per_year     : annual traffic of the described site.
    page_weight_kb       : transferred weight (kB) of the prompt sent and the
                           response received, PER AI call.
    user_time_seconds   : time spent by the visitor on the step.
    ai_provider          : provider recognized in the EcoLogits catalog (e.g.
                           "anthropic", "openai", "mistralai").
    ai_model_name        : model name recognized for this provider (e.g.
                           "claude-sonnet-4-5"). An unknown value fails the
                           build (EcoLogits, not a hypothesis of this module).
    ai_output_tokens     : average number of tokens generated per call: drives
                           the EcoLogits calculation (energy + manufacturing).
    ai_calls_per_visit   : number of AI calls triggered by a typical visit
                           (e.g. several conversation turns).
    country/phone_fraction/desktop_fraction : cf. dynamic_db.apply().
    source_name/source_url : provenance of the parameters, mandatory.

    Returns a SiteSpec to compose with other fragments, or to use alone.
    """
    web = ServerSpec(
        key=f"{prefix}_web",
        label="Application server",
        server_type=assumed_label(
            "autoscaling", source_name, source_url,
            comment="Sizing mode assumed by the ia_streaming archetype, "
                    "in the absence of a real measurement of the hosting mode."),
        country=measured_label(country, source_name, source_url),
        power=script_default(_GENERIC_POWER_W, "W"),
        carbon_footprint_fabrication=script_default(_GENERIC_FABRICATION_KG, "kg"),
        pue=script_default(_GENERIC_PUE, "dimensionless"),
    )

    job_web = JobSpec(
        key=f"{prefix}_web_request",
        server_key=web.key,
        label="Page request (application server)",
        data_transferred=measured(page_weight_kb, "kB", source_name, source_url,
                                   comment="Page weight excluding the AI prompt/response, "
                                           "counted separately by the AI job."),
    )
    job_ai = JobSpec(
        key=f"{prefix}_ai_call",
        server_key=web.key,
        label=f"AI call ({ai_provider}/{ai_model_name})",
        data_transferred=measured(page_weight_kb * 0.1, "kB", source_name, source_url,
                                   comment="Estimate of the network weight of the sent "
                                           "prompt and received response (text), distinct "
                                           "from the model's computation counted via "
                                           "external_api."),
        external_api=ExternalApiSpec(
            provider=ai_provider,
            model_name=ai_model_name,
            output_tokens=measured(ai_output_tokens, "dimensionless", source_name, source_url),
            request_count_per_step=ai_calls_per_visit,
        ),
    )

    step = StepSpec(
        key=f"{prefix}_visit",
        label="Typical visit",
        jobs={job_web.key: 1.0, job_ai.key: ai_calls_per_visit},
        user_time=assumed(user_time_seconds, "s", source_name, source_url,
                           comment="User time passed directly to the archetype "
                                   "(no HTML page to measure, unlike "
                                   "from_har.py)."),
    )
    journey = JourneySpec(
        key=f"{prefix}_journey",
        label="Typical journey",
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
        name=f"Archetype {ARCHETYPE_KEY} ({prefix})",
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
        source_name="__main__ demo (fictional data)",
    )
    built = build_system(frag)
    fab = fabrication_kg(built)
    energy = energy_kg(built)
    total = total_kg(built)
    print(f"Archetype {ARCHETYPE_KEY}: valid System, {len(frag.servers)} server(s), "
          f"{len(frag.steps)} step(s), total {total:.1f} kg CO2e/year (fictional).")
    print(f"  of which ExternalAPIs: fabrication {fab.get('ExternalAPIs', 0):.4f} kg, "
          f"energy {energy.get('ExternalAPIs', 0):.4f} kg.")
    assert total > 0, "the total should be strictly positive"
    assert fab.get("ExternalAPIs", 0) > 0 or energy.get("ExternalAPIs", 0) > 0, \
        "the AI calculation should produce a non-zero footprint"
    assert len(collect_sources(frag)) > 0, "every numeric value must be traced"
    print("OK: consistent demo.")
