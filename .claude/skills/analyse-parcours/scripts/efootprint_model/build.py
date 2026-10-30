#!/usr/bin/env python3
"""
Building the e-footprint model from a declarative specification.

THE ONLY MODULE OF THE LIBRARY THAT IMPORTS E-FOOTPRINT
-------------------------------------------------------
`spec.py` and `compose.py` stay pure Python, testable without the library
installed. This file is where that property stops: it needs e-footprint to
import. `efootprint_model/__init__.py` therefore never re-exports it (cf.
its guard-rail, checked by check_efootprint_spec.py).

IMPOSED INSTANTIATION ORDER
---------------------------
Storage -> Server -> Job -> Step -> Journey -> UsagePattern -> System.
Each e-footprint class references the previous one; respecting this avoids
having to rebuild an object after the fact (a ModelingObject does not mutate
cleanly once linked to a System, cf. handoff of 05/08/2026).

WHAT `build_system()` DOES NOT DO
----------------------------------
It chooses no value: every quantity comes from a `Traced` of the
specification, or from the LIBRARY's default (never from a default invented
here). A structurally indispensable field for e-footprint but absent from
the specification (audience country, traffic volume, incomplete server field
set) fails the build with an explicit message, rather than being guessed.
"""

from dataclasses import dataclass, field

from .spec import SiteSpec, SpecError

# The 3 confidence levels recognized by e-footprint, not to be confused with
# our 7 levels (CONFIDENCE_LEVELS), finer and already traced in the spec.
# This table only politely fills e-footprint's internal `confidence` field;
# it influences no calculation, and the report's full traceability comes
# from the spec (collect_sources()), not from here.
_EFOOTPRINT_CONFIDENCE = {"high": "high", "medium": "medium", "low": "low"}


def _efootprint_confidence(traced):
    return _EFOOTPRINT_CONFIDENCE.get(traced.confidence)


def _get_source(source_cache, name, url):
    """A single Source object per (name, url): two Traced sharing a
    provenance must not create two distinct instances."""
    from efootprint.abstract_modeling_classes.explainable_object_base_class import Source

    key = (name, url)
    if key not in source_cache:
        source_cache[key] = Source(name, url)
    return source_cache[key]


def to_source_value(traced, source_cache):
    """Traced -> SourceValue (kind="value") or SourceObject (kind="object").

    The ONLY passage point from the library to e-footprint's source classes.
    The kind was decided in pure Python back in `spec.py`: this module does
    not have to guess SourceValue vs SourceObject again.
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
    """e-footprint country name -> Country instance.

    Raises rather than falling back to a default country: a country unknown
    to the library that passed silently would make the report carry a carbon
    intensity that is not the requested one.
    """
    from efootprint.constants.countries import Countries

    if hasattr(Countries, name):
        return getattr(Countries, name)()
    raise SpecError(
        f"country unknown to the e-footprint library: {name!r}. "
        f"Expected values: an attribute of efootprint.constants.countries.Countries."
    )


# ---------------------------------------------------------------------------
# Server + storage
# ---------------------------------------------------------------------------

def _build_storage(server_spec, source_cache):
    from efootprint.core.hardware.storage import Storage

    kwargs = {}
    if server_spec.storage_gb is not None:
        kwargs["base_storage_need"] = to_source_value(server_spec.storage_gb, source_cache)
    return Storage.from_defaults(f"Storage {server_spec.label}", **kwargs)


def _build_server(server_spec, source_cache):
    """Builds the Storage then the Server, in this imposed order.

    Two mutually exclusive field sets, as documented in `ServerSpec`:
    public cloud (provider + instance_type, Boavizta path) or generic
    (power + carbon_footprint_fabrication + pue). Neither complete -> the
    specification does not say enough to choose an e-footprint class, which
    must stop the build, not be guessed.
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
        f"ServerSpec[{server_spec.key}]: neither the cloud set (provider + "
        "instance_type) nor the generic set (power + "
        "carbon_footprint_fabrication + pue) is complete. Impossible to know "
        "which e-footprint class to instantiate."
    )


# ---------------------------------------------------------------------------
# Jobs and steps
# ---------------------------------------------------------------------------

def _build_external_api(external_api_spec, label, source_cache):
    """Builds the generative AI call IN ADDITION to the usual network Job
    (never in its place): `_build_job()` stays responsible for
    data_transferred/request_duration, this module adds the EcoLogits
    calculation separately.

    Provider/model_name go as raw SourceObjects, never through
    `to_source_value()`: EcoLogits itself validates their existence in its
    catalog (`_get_model_or_raise()`), a wrong value must fail the build with
    the library's message, not be swallowed upstream.
    """
    from efootprint.builders.external_apis.ecologits.ecologits_external_api import (
        EcoLogitsGenAIExternalAPI, EcoLogitsGenAIExternalAPIJob)
    from efootprint.abstract_modeling_classes.source_objects import SourceObject

    api = EcoLogitsGenAIExternalAPI.from_defaults(
        f"{label} (generative AI)",
        provider=SourceObject(external_api_spec.provider),
        model_name=SourceObject(external_api_spec.model_name),
    )
    job = EcoLogitsGenAIExternalAPIJob.from_defaults(
        f"AI call {label}",
        external_api=api,
        output_token_count=to_source_value(external_api_spec.output_tokens, source_cache),
    )
    return job


def _build_job(job_spec, servers_by_key, source_cache):
    from efootprint.core.usage.job import Job

    if job_spec.server_key not in servers_by_key:
        # validate_spec() would already have refused it earlier: second-rank
        # net, only useful if build_system() is called on a spec that did not
        # go through require_calculable().
        raise SpecError(
            f"JobSpec[{job_spec.key}]: server \"{job_spec.server_key}\" absent "
            "from the built servers."
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

    network_job = Job.from_defaults(
        job_spec.label,
        server=servers_by_key[job_spec.server_key],
        data_transferred=to_source_value(job_spec.data_transferred, source_cache),
        **kwargs,
    )

    if job_spec.external_api is None:
        return (network_job,)
    return (network_job, _build_external_api(job_spec.external_api, job_spec.label, source_cache))


def _build_step(step_spec, jobs_by_key, source_cache):
    from efootprint.core.usage.usage_journey_step import UsageJourneyStep

    jobs = {}
    for job_key, weight in step_spec.jobs.items():
        if job_key not in jobs_by_key:
            raise SpecError(
                f"StepSpec[{step_spec.key}]: job \"{job_key}\" absent "
                "from the built jobs."
            )
        # `_build_job()` returns a tuple (network job, possibly an EcoLogits
        # AI job): both count at the same weight, the step triggers them
        # together, never one without the other.
        for built_job in jobs_by_key[job_key]:
            jobs[built_job] = weight

    kwargs = {}
    if step_spec.user_time is not None:
        kwargs["user_time_spent"] = to_source_value(step_spec.user_time, source_cache)

    return UsageJourneyStep.from_defaults(step_spec.label, jobs=jobs, **kwargs)


# ---------------------------------------------------------------------------
# Journey and usage patterns
# ---------------------------------------------------------------------------

# Device/network paired with each branch of the device mix. Convention of the
# historical script (run_efootprint.py): mobile is modeled on a mobile
# network, desktop on wifi. `wifi_fraction`/`mobile_fraction` of AudienceSpec
# stay informational for now, as in the current calculation: generalizing
# them into a real 2x2 cross is a later-lot topic, not this one (the
# non-regression requires reproducing the current behavior).
_DEVICE_MIX = ("phone_fraction", "desktop_fraction")


def _build_usage_patterns(spec, journey, servers_by_key, source_cache):
    from efootprint.builders.timeseries import ExplainableHourlyQuantitiesFromFormInputs
    from efootprint.constants.sources import Sources
    from efootprint.core.hardware.device import Device
    from efootprint.core.hardware.network import Network
    from efootprint.core.usage.usage_pattern import UsagePattern

    audience = spec.audience
    if audience is None:
        raise SpecError(f"SiteSpec[{spec.name}]: no audience, impossible to "
                        "build a usage pattern. Go through require_calculable() "
                        "before build_system() for a more readable refusal.")
    if audience.visits_per_year is None:
        raise SpecError(
            f"AudienceSpec[{audience.key}]: \"visits_per_year\" absent. "
            "An audience without a volume cannot feed a usage pattern: "
            "fill in the traffic, even approximate and flagged as such."
        )
    if audience.country is None:
        raise SpecError(
            f"AudienceSpec[{audience.key}]: \"country\" absent. An e-footprint "
            "usage pattern requires a country (it drives the local carbon "
            "intensity of the visitor's devices)."
        )
    if audience.phone_fraction is None or audience.desktop_fraction is None:
        raise SpecError(
            f"AudienceSpec[{audience.key}]: the device mix (phone_fraction/"
            "desktop_fraction) is required to build the usage patterns. "
            "A missing mix has no generic fallback: which device would "
            "represent the audience?"
        )

    country = _map_country(audience.country.value)
    visits = audience.visits_per_year.value
    visits_mobile = round(visits * audience.phone_fraction.value)
    visits_desktop = visits - visits_mobile  # guarantees the sum = visits

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
            f"Visitors {label} ({volume:,} visits/year)".replace(",", " "),
            journey,
            [device],
            network,
            country,
            _hourly_volume(volume),
        ))
    return patterns


# ---------------------------------------------------------------------------
# Full assembly
# ---------------------------------------------------------------------------

@dataclass
class BuiltModel:
    """The built model, with the indexes needed for attribution.

    Without `servers_by_key`/`jobs_by_key`/`steps_by_key`, attribution
    results would come back indexed by e-footprint object, with no way to
    attach them to the business intention that produced them.
    """

    spec: SiteSpec
    system: "System"  # noqa: F821 - textual annotation, e-footprint not imported at module load
    servers_by_key: dict = field(default_factory=dict)
    jobs_by_key: dict = field(default_factory=dict)
    steps_by_key: dict = field(default_factory=dict)


def build_system(spec, *, accepted_reserves=()):
    """Builds an e-footprint System from a SiteSpec.

    Calls `require_calculable()` first: building a model from a specification
    that has unassumed reserves would produce a false number without saying
    so. `accepted_reserves` is passed through as-is.
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

    # A single UsageJourney, SHARED between the mobile and desktop patterns:
    # verified possible (handoff of 05/08/2026), and the only way not to
    # duplicate the graph. The journey's step order must be preserved (it
    # carries the cumulative delay between steps): built by iterating over
    # `journey_spec.steps`, never via an unordered dict.
    uj_steps = {steps_by_key[step_key]: journey_spec_step(spec, step_key).times_per_journey
                for step_key in journey_spec.steps}
    journey = UsageJourney(journey_spec.label, uj_steps=uj_steps)

    usage_patterns = _build_usage_patterns(spec, journey, servers_by_key, source_cache)
    system = System(f"CO2e estimate: {spec.name}", usage_patterns, edge_usage_patterns=[])

    return BuiltModel(spec=spec, system=system, servers_by_key=servers_by_key,
                      jobs_by_key=jobs_by_key, steps_by_key=steps_by_key)


def journey_spec_step(spec, step_key):
    return spec.step_by_key(step_key)


def _sole_journey_key(spec):
    """The journey to use when the audience does not designate one explicitly.

    Only accepts the unambiguous case (a single declared journey): guessing
    among several journeys would invent an audience datum nobody measured.
    """
    if len(spec.journeys) == 1:
        return spec.journeys[0].key
    raise SpecError(
        f"SiteSpec[{spec.name}]: the audience designates no journey "
        f"(journey_key) and {len(spec.journeys)} journeys are declared. "
        "Fill in AudienceSpec.journey_key to lift the ambiguity."
    )


# ---------------------------------------------------------------------------
# Clean result extraction (no regex)
# ---------------------------------------------------------------------------

def fabrication_kg(built):
    """Manufacturing footprint per category, in kg CO2e/year, read directly
    from the e-footprint quantities (converted magnitude), never by regex on
    a text representation."""
    from efootprint.constants.units import u
    return {category: value.value.to(u.kg).magnitude
            for category, value in built.system.total_fabrication_footprint_sum_over_period.items()}


def energy_kg(built):
    """Energy footprint per category, in kg CO2e/year. Same principle as
    `fabrication_kg()`."""
    from efootprint.constants.units import u
    return {category: value.value.to(u.kg).magnitude
            for category, value in built.system.total_energy_footprint_sum_over_period.items()}


def total_kg(built):
    """Total CO2e/year, sum of the two categories above."""
    fab = fabrication_kg(built)
    energy = energy_kg(built)
    return sum(fab.values()) + sum(energy.values())


def step_impact_shares(built):
    """PROPORTIONAL distribution (not an independent recalculation per step)
    of the Devices and Network footprint per journey step, to give a
    relative contribution reference without replaying the model N times.

    METHOD, DELIBERATELY SIMPLE AND TO BE NAMED AS SUCH IN THE REPORT:
    - Devices (fabrication + energy) distributed pro rata to each step's
      weighted user time (`user_time * times_per_journey`): it is the time
      spent by the visitor that drives the consumption of THEIR device.
    - Network (energy) distributed pro rata to the weighted transferred
      weight (sum of the jobs attached to the step, job weight × the step's
      times_per_journey): it is the transferred volume that drives network
      energy.
    - Servers / Storage / ExternalAPIs: NOT distributed here. A server or a
      storage is an infra cost that does not slice cleanly by step (it runs
      for the WHOLE journey); a generative AI call already has an exact
      attribution via its own job (ExternalApiSpec), no need for an
      approximate distribution. These items stay only in the site's global
      totals.

    Returns {step_key: {"device_kg", "network_kg", "total_kg",
    "pct_of_grand_total"}}. `pct_of_grand_total` is relative to the site's
    TOTAL CO2e/year (all items, fabrication + energy), not only to
    Devices+Network: a step never weighs 100% of the real total, even if it
    concentrates all the Devices/Network distributed here.
    """
    from efootprint.constants.units import u

    spec = built.spec
    fab = fabrication_kg(built)
    energy = energy_kg(built)
    grand_total = sum(fab.values()) + sum(energy.values())

    device_pool_kg = fab.get("Devices", 0.0) + energy.get("Devices", 0.0)
    network_pool_kg = energy.get("Network", 0.0)

    time_weights, weight_weights = {}, {}
    for step in spec.steps:
        time_weights[step.key] = (
            (step.user_time.value if step.user_time else 0.0) * step.times_per_journey
        )
        transferred_bytes = 0.0
        for job_key, job_weight in step.jobs.items():
            data_transferred = spec.job_by_key(job_key).data_transferred
            if data_transferred is None:
                continue
            quantity = data_transferred.value * u.parse_units(data_transferred.unit)
            transferred_bytes += quantity.to(u.byte).magnitude * job_weight
        weight_weights[step.key] = transferred_bytes * step.times_per_journey

    total_time = sum(time_weights.values()) or 1e-9
    total_weight = sum(weight_weights.values()) or 1e-9

    shares = {}
    for step in spec.steps:
        device_kg = device_pool_kg * (time_weights[step.key] / total_time)
        network_kg = network_pool_kg * (weight_weights[step.key] / total_weight)
        step_total = device_kg + network_kg
        shares[step.key] = {
            "device_kg": device_kg,
            "network_kg": network_kg,
            "total_kg": step_total,
            "pct_of_grand_total": (step_total / grand_total) if grand_total else 0.0,
        }
    return shares


def consistency_report(built, tolerance_kg=1e-3, relative_tolerance=1e-6):
    """Checks that our sum by category lands back on the sum PER OBJECT that
    the library computes (`fabrication_footprint_sum_over_period` /
    `energy_footprint_sum_over_period`), object by object rather than by
    aggregated category.

    This is not proof that the NUMBER is right: it is proof that our
    category-wise reading neither LOST nor DOUBLED any contribution along the
    way. A discrepancy here signals an extraction bug, not a modeling
    disagreement.

    DO NOT compare to `system.total_footprint`: that attribute rounds to 4
    decimals EACH HOUR before summing 8760 values (seen in practice: 170.82
    kg vs 170.904 kg here), a library precision artifact, not a disagreement
    about the model.

    ABSOLUTE and RELATIVE tolerance: a model with more objects (several
    servers/jobs) accumulates more floating-point roundings without any bug
    (measured: 0.0026 kg of difference on a 14,481 kg total with 3 servers,
    i.e. 1.8e-7 relative — well under tolerance_kg in absolute terms but
    visible if only the absolute were watched on a clearly smaller total).
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
