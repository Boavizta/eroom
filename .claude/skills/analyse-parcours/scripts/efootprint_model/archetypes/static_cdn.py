#!/usr/bin/env python3
"""
Archetype "static + CDN": a showcase site whose pages are ready-made files
(HTML/CSS/JS/images), served by a CDN, with no business code executed per visit
(no database, cf. dynamic_db.py for that case).

WHAT THIS MODULE CAPTURES, AND WHAT IT DOES NOT
------------------------------------------------
A single server (the one hosting the origin files): a CDN has no own
datacenter attributable to the site (cf. spec.py::
ThirdPartyHost, decision already taken for from_har.py). Fonts, trackers and
other third-party hosts observable on a real showcase site can be added via
`third_party_hosts` on the returned SiteSpec (they stay NETWORK ONLY).

ZERO e-footprint import here, like the other archetypes.
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

ARCHETYPE_KEY = "static_cdn"

# GENERIC SERVER fallback, same values as dynamic_db.py (cf. its docstring for
# the origin).
_GENERIC_POWER_W = 300.0
_GENERIC_FABRICATION_KG = 600.0
_GENERIC_PUE = 1.2


def apply(*, prefix, visits_per_year, page_weight_kb, user_time_seconds,
          country="FRANCE", phone_fraction=0.6, desktop_fraction=0.4,
          source_name, source_url=None):
    """Builds a `SiteSpec` fragment: a static origin server.

    prefix          : key prefix, cf. dynamic_db.apply().
    visits_per_year : annual traffic of the described site.
    page_weight_kb  : transferred weight of a typical page (kB), static files
                      included (HTML/CSS/JS/images).
    user_time_seconds : time spent by the visitor on this step.
    country/phone_fraction/desktop_fraction : cf. dynamic_db.apply().
    source_name/source_url : provenance of the parameters, mandatory.

    Returns a SiteSpec to compose with other fragments, or to use alone. To
    add observed third-party hosts (CDN, fonts, trackers), then compose with
    `compose(frag, third_party_hosts=(...))`.
    """
    origin = ServerSpec(
        key=f"{prefix}_origin",
        label="Origin server (static files)",
        server_type=assumed_label(
            "autoscaling", source_name, source_url,
            comment="Sizing mode assumed by the static_cdn archetype, "
                    "in the absence of a real measurement of the hosting mode."),
        country=measured_label(country, source_name, source_url),
        power=script_default(_GENERIC_POWER_W, "W"),
        carbon_footprint_fabrication=script_default(_GENERIC_FABRICATION_KG, "kg"),
        pue=script_default(_GENERIC_PUE, "dimensionless"),
    )

    job = JobSpec(
        key=f"{prefix}_request",
        server_key=origin.key,
        label="Page request (static files)",
        data_transferred=measured(page_weight_kb, "kB", source_name, source_url,
                                   comment="Transferred weight, as served by the CDN: "
                                           "no business processing server-side."),
    )

    step = StepSpec(
        key=f"{prefix}_visit",
        label="Typical visit",
        jobs={job.key: 1.0},
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
        source_name="__main__ demo (fictional data)",
    )
    built = build_system(frag)
    total = total_kg(built)
    print(f"Archetype {ARCHETYPE_KEY}: valid System, {len(frag.servers)} server(s), "
          f"{len(frag.steps)} step(s), total {total:.1f} kg CO2e/year (fictional).")
    assert total > 0, "the total should be strictly positive"
    assert len(collect_sources(frag)) > 0, "every numeric value must be traced"
    print("OK: consistent demo.")
