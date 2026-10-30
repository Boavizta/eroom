#!/usr/bin/env python3
"""
Archetype "dynamic + DB": a site that runs business code on every visit
(form, user account, back office), with an application server and a separate
database.

WHAT AN ARCHETYPE IS HERE
------------------------
A second way to produce a `SiteSpec` (spec.py), besides `from_har.py`.
`from_har.py` READS an already-captured HAR; an archetype reads nothing: it
TAKES already-known parameters (number of visits, page weight, number of
servers...) and returns a ready-to-compose specification fragment. Useful
when there is no network capture yet, e.g. during a client interview before
any audit.

Neither a fixed case nor a checkbox menu: a starting point to adjust to the
described site's real parameters, like any other `SiteSpec` (immutable, so
`dataclasses.replace()` works on it normally).

ZERO e-footprint import here: like `from_har.py`, this module only builds
`spec.py` dataclasses, never an e-footprint object.

GENERICITY: no hardcoded numeric default taken from a real site. All numeric
parameters are mandatory arguments or None (no value that would look like a
measurement), in accordance with `check_genericite.py`.
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

ARCHETYPE_KEY = "dynamic_db"

# GENERIC SERVER fallback, when no cloud provider is known: same values as the
# fallback already established in from_har.py::_server_spec_from_info() (300 W,
# 600 kg, PUE 1.2). Not a measurement of the described site: the default value
# of e-footprint's own Server class (server.py:34-37), reused here rather than
# invented again.
_GENERIC_POWER_W = 300.0
_GENERIC_FABRICATION_KG = 600.0
_GENERIC_PUE = 1.2


def apply(*, prefix, visits_per_year, page_weight_kb, user_time_seconds, country="FRANCE",
          phone_fraction=0.6, desktop_fraction=0.4, source_name, source_url=None):
    """Builds a `SiteSpec` fragment: application server + database.

    prefix          : key prefix (server/job/step/journey), so this archetype
                      can be applied several times in the same site without
                      collision (cf. compose.py).
    visits_per_year : annual traffic of the described site (number of visits).
    page_weight_kb  : transferred weight of a typical visit (kB), all requests
                      mixed (page + API calls it triggers).
    user_time_seconds : time spent by the visitor on this step (seconds).
                      Critical field (cf. StepSpec): without a HAR to measure,
                      this archetype cannot deduce a Nielsen reading time
                      (user_time.py, reserved to from_har.py); it must be
                      provided, even as an assumed hypothesis.
    country         : hosting country (name recognized by e-footprint, e.g.
                      "FRANCE", "GERMANY").
    phone_fraction / desktop_fraction : audience device mix, must sum to 1
                      (cf. AudienceSpec._check_pair()).
    source_name/source_url : provenance of the numeric parameters (e.g.
                      "client interview of 12/08/2026", "brief hypothesis").
                      Mandatory: an archetype cannot produce a number without
                      provenance (cf. require_traced()).

    Returns a SiteSpec to compose with other fragments via `compose()`, or to
    use alone.
    """
    generic_hardware = dict(
        power=script_default(_GENERIC_POWER_W, "W"),
        carbon_footprint_fabrication=script_default(_GENERIC_FABRICATION_KG, "kg"),
        pue=script_default(_GENERIC_PUE, "dimensionless"),
    )
    web = ServerSpec(
        key=f"{prefix}_web",
        label="Application server",
        server_type=assumed_label_or_default("autoscaling", source_name, source_url),
        country=measured_label(country, source_name, source_url),
        **generic_hardware,
    )
    db = ServerSpec(
        key=f"{prefix}_db",
        label="Database",
        server_type=assumed_label_or_default("autoscaling", source_name, source_url),
        country=measured_label(country, source_name, source_url),
        **generic_hardware,
    )

    job_web = JobSpec(
        key=f"{prefix}_web_request",
        server_key=web.key,
        label="Page request (application server)",
        data_transferred=measured(page_weight_kb * 0.8, "kB", source_name, source_url,
                                   comment="80% of the visit's weight: page + assets "
                                           "served by the application server."),
    )
    job_db = JobSpec(
        key=f"{prefix}_db_query",
        server_key=db.key,
        label="Database query",
        data_transferred=measured(page_weight_kb * 0.2, "kB", source_name, source_url,
                                   comment="20% of the visit's weight: responses of "
                                           "queries to the database."),
    )

    step = StepSpec(
        key=f"{prefix}_visit",
        label="Typical visit",
        jobs={job_web.key: 1.0, job_db.key: 1.0},
        user_time=assumed(user_time_seconds, "s", source_name, source_url,
                           comment="User time passed directly to the archetype "
                                   "(no HTML page to measure, unlike "
                                   "from_har.py): to be replaced by a real site "
                                   "measurement as soon as one exists."),
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
        servers=(web, db),
        jobs=(job_web, job_db),
        steps=(step,),
        journeys=(journey,),
        audience=audience,
        archetypes=(ARCHETYPE_KEY,),
    )


def assumed_label_or_default(value, source_name, source_url):
    """Sizing mode: ASSUMED as long as the archetype receives no real
    measurement (no network capture reveals it, unlike `from_har.py`). Goes
    through `assumed_label`, never a script default: it is an ACTIVE choice
    of the archetype, not a value invented in silence."""
    from ..spec import assumed_label
    return assumed_label(
        value, source_name, source_url,
        comment="Sizing mode assumed by the dynamic_db archetype, "
                "in the absence of a real measurement of the hosting mode.")


if __name__ == "__main__":
    from ..build import build_system, total_kg
    from ..compose import collect_sources

    frag = apply(
        prefix="demo",
        visits_per_year=50_000,
        page_weight_kb=250,
        user_time_seconds=45,
        source_name="__main__ demo (fictional data)",
    )
    built = build_system(frag)
    total = total_kg(built)
    print(f"Archetype {ARCHETYPE_KEY}: valid System, {len(frag.servers)} servers, "
          f"{len(frag.steps)} step(s), total {total:.1f} kg CO2e/year (fictional).")
    assert total > 0, "the total should be strictly positive"
    assert len(collect_sources(frag)) > 0, "every numeric value must be traced"
    print("OK: consistent demo.")
