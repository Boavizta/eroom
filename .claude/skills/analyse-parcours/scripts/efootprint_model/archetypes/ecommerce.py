#!/usr/bin/env python3
"""
Archetype "e-commerce": a merchant site with an application server, a database
(catalog, accounts, orders) and two distinct steps (catalog browsing, checkout
tunnel) that weigh differently.

WHY TWO STEPS AND NOT ONE LIKE dynamic_db.py
--------------------------------------------
A merchant site does not have a uniform weight: catalog browsing (product
sheets, images) weighs and lasts differently from the checkout tunnel (short
form, few images). Grouping them into a single average step would hide this
difference in the report (cf. StepSpec.intention, aggregation by business
intention rather than by technical step).

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

ARCHETYPE_KEY = "ecommerce"

# GENERIC SERVER fallback, same values as dynamic_db.py (cf. its docstring for
# the origin).
_GENERIC_POWER_W = 300.0
_GENERIC_FABRICATION_KG = 600.0
_GENERIC_PUE = 1.2

# Relative catalog/DB weight per step: product sheets and their images are
# mostly served by the application server (static assets), the checkout tunnel
# solicits the database proportionally more (stock checks, order creation).
# A modeling decision of this archetype, NOT a measurement: to be adjusted to
# the described site's real parameters, as documented in its __init__ (cf.
# dynamic_db.py).
_CATALOG_WEB_SHARE = 0.85
_CHECKOUT_WEB_SHARE = 0.5


def apply(*, prefix, visits_per_year, catalog_weight_kb, checkout_weight_kb,
          catalog_time_seconds, checkout_time_seconds, catalog_share=0.8,
          country="FRANCE", phone_fraction=0.6, desktop_fraction=0.4,
          source_name, source_url=None):
    """Builds a `SiteSpec` fragment: application server + DB, two steps.

    prefix               : key prefix, cf. dynamic_db.apply().
    visits_per_year      : annual traffic of the described site.
    catalog_weight_kb    : transferred weight of a typical catalog page (kB).
    checkout_weight_kb   : transferred weight of a typical checkout page (kB).
    catalog_time_seconds/checkout_time_seconds : time spent on each step.
    catalog_share        : share of visits that browse the catalog WITHOUT
                           going to checkout (between 0 and 1): the rest of
                           the visits triggers both steps. An abandoned cart
                           is thus modeled as a visit that only counts the
                           catalog step.
    country/phone_fraction/desktop_fraction : cf. dynamic_db.apply().
    source_name/source_url : provenance of the parameters, mandatory.

    Returns a SiteSpec to compose with other fragments, or to use alone. The
    returned journey traverses BOTH steps: `catalog_share` only influences the
    relative weight displayed in an appendix (times_per_journey stays 1 for
    each step declared in the journey), the "abandoned cart" nuance is not yet
    carried by the calculation itself.
    """
    if not (0.0 <= catalog_share <= 1.0):
        raise ValueError(f"catalog_share must be between 0 and 1, got {catalog_share!r}.")

    web = ServerSpec(
        key=f"{prefix}_web",
        label="Application server",
        server_type=assumed_label(
            "autoscaling", source_name, source_url,
            comment="Sizing mode assumed by the ecommerce archetype, "
                    "in the absence of a real measurement of the hosting mode."),
        country=measured_label(country, source_name, source_url),
        power=script_default(_GENERIC_POWER_W, "W"),
        carbon_footprint_fabrication=script_default(_GENERIC_FABRICATION_KG, "kg"),
        pue=script_default(_GENERIC_PUE, "dimensionless"),
    )
    db = ServerSpec(
        key=f"{prefix}_db",
        label="Database (catalog, accounts, orders)",
        server_type=assumed_label(
            "autoscaling", source_name, source_url,
            comment="Sizing mode assumed by the ecommerce archetype, "
                    "in the absence of a real measurement of the hosting mode."),
        country=measured_label(country, source_name, source_url),
        power=script_default(_GENERIC_POWER_W, "W"),
        carbon_footprint_fabrication=script_default(_GENERIC_FABRICATION_KG, "kg"),
        pue=script_default(_GENERIC_PUE, "dimensionless"),
    )

    def _split_job(key_suffix, label, weight_kb, web_share):
        job_web = JobSpec(
            key=f"{prefix}_{key_suffix}_web",
            server_key=web.key,
            label=f"{label} (application server)",
            data_transferred=measured(weight_kb * web_share, "kB", source_name, source_url),
        )
        job_db = JobSpec(
            key=f"{prefix}_{key_suffix}_db",
            server_key=db.key,
            label=f"{label} (database)",
            data_transferred=measured(weight_kb * (1 - web_share), "kB", source_name, source_url),
        )
        return job_web, job_db

    catalog_web, catalog_db = _split_job(
        "catalog", "Catalog browsing", catalog_weight_kb, _CATALOG_WEB_SHARE)
    checkout_web, checkout_db = _split_job(
        "checkout", "Checkout tunnel", checkout_weight_kb, _CHECKOUT_WEB_SHARE)

    step_catalog = StepSpec(
        key=f"{prefix}_step_catalog",
        label="Catalog browsing",
        intention="browse / choose a product",
        jobs={catalog_web.key: 1.0, catalog_db.key: 1.0},
        user_time=assumed(catalog_time_seconds, "s", source_name, source_url),
    )
    step_checkout = StepSpec(
        key=f"{prefix}_step_checkout",
        label="Checkout tunnel",
        intention="buy",
        jobs={checkout_web.key: 1.0, checkout_db.key: 1.0},
        user_time=assumed(checkout_time_seconds, "s", source_name, source_url),
    )

    journey = JourneySpec(
        key=f"{prefix}_journey",
        label="Purchase journey",
        steps=(step_catalog.key, step_checkout.key),
        notes=(f"Share of visits that do not reach checkout (abandoned cart, "
               f"not carried by the calculation): {catalog_share:.0%}, "
               f"provided by the caller for documentation only.",),
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
        jobs=(catalog_web, catalog_db, checkout_web, checkout_db),
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
        source_name="__main__ demo (fictional data)",
    )
    built = build_system(frag)
    total = total_kg(built)
    print(f"Archetype {ARCHETYPE_KEY}: valid System, {len(frag.servers)} servers, "
          f"{len(frag.steps)} step(s), total {total:.1f} kg CO2e/year (fictional).")
    assert total > 0, "the total should be strictly positive"
    assert len(collect_sources(frag)) > 0, "every numeric value must be traced"
    print("OK: consistent demo.")
