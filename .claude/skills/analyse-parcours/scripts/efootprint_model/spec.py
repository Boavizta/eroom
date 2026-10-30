#!/usr/bin/env python3
"""
Declarative specifications of a web service, for e-footprint modeling.

ZERO e-footprint import in this file. This is a constraint, not an accident:
these structures must be testable without the library installed and without
network access. Building the e-footprint model is another module's job.

THE CENTRAL PRINCIPLE: THE SOURCE TRAVELS WITH THE VALUE
--------------------------------------------------------
Every quantity that enters the calculation is a `Traced`: the value, its
unit and its provenance are the SAME object. It is therefore impossible to
write a number without saying where it comes from, because there is no field
where a bare number could be placed.

On CRITICAL fields (user time, transferred weight, instance type), a value
without provenance makes the build FAIL. The reasoning: an untraced number
that lands in a report looks like a measurement. Better a loud error at
build time than a false measurement published.

THE CONFIDENCE VOCABULARY IS NOT FREE
-------------------------------------
`CONFIDENCE_LEVELS` reproduces EXACTLY the seven levels recognized by
`_confidence_badge()` in `generate_report_html.py`. A level invented here
would be displayed as-is, as a raw string, in place of the badge. Hence the
validation at construction time.

GENERICITY
----------
No hardcoded numeric default taken from a real site belongs in this file. A
specification that receives nothing must not be able to invent anything:
that is what guarantees a published number comes from the analyzed site's
data. Mechanically checked by `check_genericite.py`.
"""

from dataclasses import dataclass, field
from numbers import Real
from typing import Any, Mapping, Optional, Tuple

# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------

# The seven levels of `_confidence_badge()`, in decreasing order of
# reliability. Do not add one without adding the corresponding badge in the
# report.
#   high               : collected (API, HAR, direct measurement)
#   medium             : estimated (inferred from a collected datum)
#   low                : assumed (argued hypothesis)
#   default            : historical level kept for already-produced JSON
#   default_efootprint : default value of the e-footprint LIBRARY
#   default_script     : value set by OUR scripts — deliberate distinction,
#                        so our choices are not passed off as the tool's
#   unjustified        : set by hand, without verifiable justification
CONFIDENCE_LEVELS = (
    "high",
    "medium",
    "low",
    "default",
    "default_efootprint",
    "default_script",
    "unjustified",
)

# Two natures of value, which will become two distinct e-footprint classes
# (SourceValue for a physical quantity, SourceObject for a categorical label
# such as a provider name or an instance type). The distinction is made HERE,
# in pure Python, so the builder does not have to guess from the Python type.
KINDS = ("value", "object")


class SpecError(ValueError):
    """Invalid specification: structural inconsistency or missing provenance.

    Deliberately an exception, never a warning. An inconsistent specification
    that keeps going produces a number, and a number is believed.
    """


# ---------------------------------------------------------------------------
# Traced: the traceability unit of the whole library
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Traced:
    """A value and its provenance, inseparable.

    value       : the number (kind="value") or the label (kind="object")
    unit        : e-footprint unit as text ("kB", "ms", "GB_stored",
                  "cpu_core", "g/kWh", "dimensionless"). Mandatory for a
                  quantity, forbidden for a label. Still text: conversion to
                  an e-footprint unit belongs to the builder, not to the
                  specification.
    source_name : where the value comes from, in plain words ("CrUX",
                  "HAR measurement", "script default"). It does not have to
                  be a publication: naming a script default IS a provenance.
    source_url  : verifiable link if the source has one.
    confidence  : one of CONFIDENCE_LEVELS.
    comment     : what the report reader must also know, especially the
                  LIMITS of the value (measurement period, known bias).
    kind        : "value" or "object".
    """

    value: Any
    unit: Optional[str] = None
    source_name: Optional[str] = None
    source_url: Optional[str] = None
    confidence: str = "default"
    comment: Optional[str] = None
    kind: str = "value"

    def __post_init__(self):
        if self.confidence not in CONFIDENCE_LEVELS:
            raise SpecError(
                f"unknown confidence level: {self.confidence!r}. "
                f"Expected one of {', '.join(CONFIDENCE_LEVELS)}. "
                "A level outside the list would be displayed as a raw string "
                "in the report, in place of the badge."
            )
        if self.kind not in KINDS:
            raise SpecError(
                f"unknown value kind: {self.kind!r}. "
                f"Expected one of {', '.join(KINDS)}."
            )

        if self.kind == "value":
            if isinstance(self.value, bool) or not isinstance(self.value, Real):
                raise SpecError(
                    f"a quantity (kind=\"value\") must be a number, "
                    f"got {type(self.value).__name__}: {self.value!r}. "
                    "For a label, use kind=\"object\"."
                )
            if not self.unit:
                raise SpecError(
                    f"missing unit for the quantity {self.value!r}. "
                    "A quantity without a unit is unusable and converts "
                    "silently the wrong way. Use \"dimensionless\" "
                    "for a ratio."
                )
        else:
            if not isinstance(self.value, str) or not self.value:
                raise SpecError(
                    "a label (kind=\"object\") must be a non-empty string, "
                    f"got {self.value!r}."
                )
            if self.unit:
                raise SpecError(
                    f"unit {self.unit!r} on a label {self.value!r}: "
                    "a label has no unit."
                )

    @property
    def has_source(self):
        """Is the provenance filled in? (name mandatory, link optional)"""
        return bool(self.source_name and self.source_name.strip())

    def as_dict(self):
        """Serializable form, for the `sources` block of the results JSON."""
        return {
            "value": self.value,
            "unit": self.unit,
            "source_name": self.source_name,
            "source_url": self.source_url,
            "confidence": self.confidence,
            "comment": self.comment,
            "kind": self.kind,
        }


# --- Factories: the confidence level comes from the MODE of obtaining -------
# Going through these factories avoids the most common mistake: claiming
# "high" on an inferred value. The factory name says what happened.

def measured(value, unit, source_name, source_url=None, comment=None):
    """COLLECTED value: direct measurement (HAR, API, response header)."""
    return Traced(value, unit, source_name, source_url, "high", comment)


def estimated(value, unit, source_name, source_url=None, comment=None):
    """INFERRED value from a collected datum (calculation, weighting)."""
    return Traced(value, unit, source_name, source_url, "medium", comment)


def assumed(value, unit, source_name, source_url=None, comment=None):
    """ASSUMED value: hypothesis whose comment must say why."""
    return Traced(value, unit, source_name, source_url, "low", comment)


def library_default(value, unit, comment=None, source_url=None):
    """Default value of the e-footprint LIBRARY. Provenance: the library."""
    return Traced(value, unit, "e-footprint default", source_url,
                  "default_efootprint", comment)


def script_default(value, unit, comment=None):
    """Default value of OUR scripts. Never to be confused with the previous
    one: confusing them amounts to making the tool endorse our choices."""
    return Traced(value, unit, "audit script default", None,
                  "default_script", comment)


def unjustified(value, unit, comment=None):
    """Value set by hand without verifiable justification: an ACTIVE choice,
    so displayed as such, but unverified."""
    return Traced(value, unit, "set manually, without justification", None,
                  "unjustified", comment)


# "Label" variants of the three useful factories for a categorical field
# (provider, instance type, country, server type).

def measured_label(value, source_name, source_url=None, comment=None):
    """COLLECTED label (e.g. provider inferred from a response header)."""
    return Traced(value, None, source_name, source_url, "high", comment, "object")


def estimated_label(value, source_name, source_url=None, comment=None):
    """INFERRED label (e.g. country inferred from an IP address)."""
    return Traced(value, None, source_name, source_url, "medium", comment, "object")


def assumed_label(value, source_name, source_url=None, comment=None):
    """ASSUMED label, whose comment must say what the hypothesis rests on."""
    return Traced(value, None, source_name, source_url, "low", comment, "object")


def script_default_label(value, comment=None):
    """Label default of OUR scripts (e.g. instance type when nothing better)."""
    return Traced(value, None, "audit script default", None,
                  "default_script", comment, "object")


# ---------------------------------------------------------------------------
# Guard-rail on critical fields
# ---------------------------------------------------------------------------

def require_traced(value, owner, field_name, *, kind=None, critical=False):
    """Checks that a field is a usable `Traced`.

    `critical=True` additionally requires a PROVENANCE. Critical fields are
    the ones that directly drive a published number: user time, transferred
    weight, instance type. On those, a value without provenance is refused
    at construction.

    Returns the value (or None if the field is absent and not critical).
    """
    if value is None:
        if critical:
            raise SpecError(
                f"{owner}: the critical field \"{field_name}\" is absent. "
                "It drives a published number, it cannot be guessed."
            )
        return None
    if not isinstance(value, Traced):
        raise SpecError(
            f"{owner}: \"{field_name}\" must be a Traced, got "
            f"{type(value).__name__} ({value!r}). A bare value is not "
            "accepted: the provenance and the value are the same object."
        )
    if kind and value.kind != kind:
        raise SpecError(
            f"{owner}: \"{field_name}\" expects kind=\"{kind}\", "
            f"got kind=\"{value.kind}\"."
        )
    if critical and not value.has_source:
        raise SpecError(
            f"{owner}: \"{field_name}\" is {value.value!r} without provenance. "
            "This is a critical field: fill in source_name. Naming a script "
            "default is an acceptable provenance; naming nothing is not."
        )
    return value


def _require_key(value, owner, field_name):
    """A key must be a non-empty string: it serves as identity in the indexes
    and in error messages."""
    if not isinstance(value, str) or not value.strip():
        raise SpecError(f"{owner}: \"{field_name}\" must be a non-empty text "
                        f"key, got {value!r}.")
    return value


# ---------------------------------------------------------------------------
# Evidence: what the site data says about an infrastructure
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Evidence:
    """What the HAR allows us to assert about an infrastructure, and nothing
    more.

    Serves two purposes: justifying in the report why such-and-such server
    was modeled, and letting `compose()` recognize that two fragments talk
    about the same machine.

    `cache_header_seen` is distinguished from `cache_hit_ratio` being None
    because the two situations do not look alike: no cache header observed is
    INFORMATION about the hosting, whereas an uncomputable ratio is an
    absence of measurement. Confusing the two makes a failed detection look
    like a successful one.
    """

    hosts: Tuple[str, ...] = ()
    ips: Tuple[str, ...] = ()
    request_count: Optional[int] = None
    transferred_bytes: Optional[int] = None
    cache_hit_ratio: Optional[float] = None
    cache_header_seen: bool = False
    note: Optional[str] = None

    def __post_init__(self):
        object.__setattr__(self, "hosts", tuple(self.hosts))
        object.__setattr__(self, "ips", tuple(self.ips))

    @property
    def identity(self):
        """Infrastructure signature, to compare two Evidence objects.

        Deliberately HOSTS AND IPs together, as full sets. A shared IP is NOT
        enough to conclude a common infrastructure: a real validation case
        shows two distinct subdomains behind the same address. Requiring both
        sets to be equal avoids merging two servers on too weak a clue.
        """
        return (frozenset(self.hosts), frozenset(self.ips))

    def as_dict(self):
        return {
            "hosts": list(self.hosts),
            "ips": list(self.ips),
            "request_count": self.request_count,
            "transferred_bytes": self.transferred_bytes,
            "cache_hit_ratio": self.cache_hit_ratio,
            "cache_header_seen": self.cache_header_seen,
            "note": self.note,
        }


@dataclass(frozen=True)
class ThirdPartyHost:
    """A third-party host observed in the HAR, counted on the NETWORK ONLY.

    Modeling decision: third-party bytes are counted (they cross the network
    and the visitor's device), but their SERVERS are not. No public source
    gives g CO2e per request for a CDN or a font service; a number there
    would be invented.

    This structure exists so the report can SAY it with numbers specific to
    the analyzed site. The wording matters: it is not "third parties were
    forgotten", it is "their traffic is counted, not their machines". And
    the size of this blind spot varies greatly from one site to another, so
    it cannot be announced as a universal percentage.
    """

    host: str
    request_count: Optional[int] = None
    transferred_bytes: Optional[int] = None
    share_of_requests: Optional[float] = None
    share_of_bytes: Optional[float] = None
    note: Optional[str] = None

    def __post_init__(self):
        _require_key(self.host, "ThirdPartyHost", "host")

    def as_dict(self):
        return {
            "host": self.host,
            "request_count": self.request_count,
            "transferred_bytes": self.transferred_bytes,
            "share_of_requests": self.share_of_requests,
            "share_of_bytes": self.share_of_bytes,
            "note": self.note,
        }


@dataclass(frozen=True)
class ExternalApiSpec:
    """A call to a third-party generative AI model (OpenAI, Anthropic...), as
    opposed to a `ThirdPartyHost`: here a public source DOES give a footprint
    per call (the EcoLogits library, already installed with e-footprint), so
    counting it on the network only would under-count the calculation itself.
    Distinct from a `ThirdPartyHost` (CDN, font service) for which no such
    public source exists (cf. its docstring).

    `provider`/`model_name` must be recognized by the EcoLogits catalog
    (e.g. "anthropic" / "claude-sonnet-4-5"): it is `build.py` that checks,
    this dataclass stays zero e-footprint imports.
    `output_tokens` drives the calculation: the more tokens generated, the
    more energy and compute consumed. `request_count_per_step` is the number
    of calls triggered by the step carrying it (e.g. several conversation
    turns).
    """

    provider: str
    model_name: str
    output_tokens: Traced
    request_count_per_step: float = 1.0

    def __post_init__(self):
        owner = "ExternalApiSpec"
        _require_key(self.provider, owner, "provider")
        _require_key(self.model_name, owner, "model_name")
        require_traced(self.output_tokens, owner, "output_tokens", kind="value",
                       critical=True)
        if isinstance(self.request_count_per_step, bool) \
                or not isinstance(self.request_count_per_step, Real) \
                or self.request_count_per_step <= 0:
            raise SpecError(f"{owner}: \"request_count_per_step\" must be a "
                            f"strictly positive number, got "
                            f"{self.request_count_per_step!r}.")
        object.__setattr__(self, "request_count_per_step", float(self.request_count_per_step))


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ServerSpec:
    """A distinct 1st-party infrastructure.

    One server per genuinely distinct infrastructure, never a convenience
    aggregation. Two reasons: aggregating lends the primary server a load it
    does not carry, and above all aggregating makes the item INVISIBLE, hence
    not isolable as a reduction lever. An analytics service that weighs few
    bytes but concentrates many requests would disappear into a single-page
    job.

    `provider` and `instance_type` only matter for a public-cloud server
    modeled via the Boavizta path. A generic server uses `power`,
    `carbon_footprint_fabrication` and `pue` instead. Both sets are optional
    here: it is the model builder that will require one or the other,
    because it alone knows which e-footprint class it instantiates.
    """

    key: str
    label: str
    role: str = "web"
    server_type: Optional[Traced] = None          # autoscaling / serverless / on_premise
    country: Optional[Traced] = None
    carbon_intensity: Optional[Traced] = None
    provider: Optional[Traced] = None
    instance_type: Optional[Traced] = None
    storage_gb: Optional[Traced] = None
    base_ram: Optional[Traced] = None
    base_compute: Optional[Traced] = None
    power: Optional[Traced] = None
    carbon_footprint_fabrication: Optional[Traced] = None
    pue: Optional[Traced] = None
    evidence: Optional[Evidence] = None
    notes: Tuple[str, ...] = ()

    def __post_init__(self):
        _require_key(self.key, "ServerSpec", "key")
        _require_key(self.label, f"ServerSpec[{self.key}]", "label")
        owner = f"ServerSpec[{self.key}]"
        object.__setattr__(self, "notes", tuple(self.notes))

        for name in ("server_type", "country", "provider"):
            require_traced(getattr(self, name), owner, name, kind="object")
        # The instance type is CRITICAL: it alone determines the power and the
        # manufacturing footprint attributed. A t3.medium dropped without
        # justification becomes, in the report, a characteristic of the site.
        require_traced(self.instance_type, owner, "instance_type", kind="object",
                       critical=self.instance_type is not None)
        for name in ("carbon_intensity", "storage_gb", "base_ram", "base_compute",
                     "power", "carbon_footprint_fabrication", "pue"):
            require_traced(getattr(self, name), owner, name, kind="value")

        if self.evidence is not None and not isinstance(self.evidence, Evidence):
            raise SpecError(f"{owner}: \"evidence\" must be an Evidence, "
                            f"got {type(self.evidence).__name__}.")


# ---------------------------------------------------------------------------
# Job
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class JobSpec:
    """A network exchange attributed to a server.

    `data_transferred` is the TRANSFERRED weight (compressed, as it travels),
    not the decompressed weight: it is the real traffic that drives network
    energy. The decompressed weight remains a useful reference for the
    report, but it does not enter the calculation.

    `external_api` carries an `ExternalApiSpec` if this job calls a
    third-party generative AI model (OpenAI, Anthropic...) whose footprint is
    computed via EcoLogits (cf. its docstring), IN ADDITION to the usual
    `data_transferred`: the network traffic of the prompt/response and the
    model's computation at the provider are two distinct quantities, they
    add up.
    """

    key: str
    server_key: str
    label: str
    data_transferred: Optional[Traced] = None
    request_duration: Optional[Traced] = None
    compute_needed: Optional[Traced] = None
    ram_needed: Optional[Traced] = None
    data_stored: Optional[Traced] = None
    external_api: Optional[ExternalApiSpec] = None
    notes: Tuple[str, ...] = ()

    def __post_init__(self):
        _require_key(self.key, "JobSpec", "key")
        owner = f"JobSpec[{self.key}]"
        _require_key(self.server_key, owner, "server_key")
        _require_key(self.label, owner, "label")
        object.__setattr__(self, "notes", tuple(self.notes))

        # The transferred weight is CRITICAL: it is the main input of the
        # calculation.
        require_traced(self.data_transferred, owner, "data_transferred",
                       kind="value", critical=True)
        for name in ("request_duration", "compute_needed", "ram_needed", "data_stored"):
            require_traced(getattr(self, name), owner, name, kind="value")

        if self.external_api is not None and not isinstance(self.external_api, ExternalApiSpec):
            raise SpecError(f"{owner}: \"external_api\" must be an "
                            f"ExternalApiSpec, got {type(self.external_api).__name__}.")


# ---------------------------------------------------------------------------
# Journey step
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class StepSpec:
    """A user-journey step, with the jobs it triggers.

    `jobs` maps a job key to a WEIGHT: the number of times this job runs
    during the step. A weight, not a boolean, because a step can trigger the
    same call several times.

    `intention` is the business grouping used for PRESENTATION (to get
    informed, to contact, to apply...). The calculation stays at step
    level; the intention is only an aggregation of results, which guarantees
    totals are preserved.

    `words` and `images` serve to estimate reading time. On a
    client-rendered page, the count drops to zero; this fallback must stay
    VISIBLE in the Traced's confidence, never silent.
    """

    key: str
    label: str
    intention: Optional[str] = None
    user_time: Optional[Traced] = None
    jobs: Mapping[str, float] = field(default_factory=dict)
    times_per_journey: float = 1.0
    words: Optional[Traced] = None
    images: Optional[Traced] = None
    url: Optional[str] = None
    notes: Tuple[str, ...] = ()

    def __post_init__(self):
        _require_key(self.key, "StepSpec", "key")
        owner = f"StepSpec[{self.key}]"
        _require_key(self.label, owner, "label")
        object.__setattr__(self, "notes", tuple(self.notes))

        # The user time is CRITICAL: it drives the footprint of the visitor's
        # device, which weighs heavily in the total. A duration dropped without
        # provenance is the kind of number that gets believed to be measured.
        require_traced(self.user_time, owner, "user_time", kind="value", critical=True)
        for name in ("words", "images"):
            require_traced(getattr(self, name), owner, name, kind="value")

        if not isinstance(self.jobs, Mapping):
            raise SpecError(f"{owner}: \"jobs\" must map a job key to a "
                            f"number of executions, got "
                            f"{type(self.jobs).__name__}.")
        cleaned = {}
        for job_key, weight in self.jobs.items():
            _require_key(job_key, owner, "jobs (key)")
            if isinstance(weight, bool) or not isinstance(weight, Real):
                raise SpecError(f"{owner}: the weight of job "
                                f"\"{job_key}\" must be a number, got "
                                f"{weight!r}.")
            if weight <= 0:
                raise SpecError(f"{owner}: the weight of job "
                                f"\"{job_key}\" is {weight}. A job "
                                "that does not run must be removed from "
                                "the step, not set to zero: at zero it stays "
                                "listed in the model and suggests it is "
                                "counted.")
            cleaned[job_key] = float(weight)
        object.__setattr__(self, "jobs", cleaned)

        if isinstance(self.times_per_journey, bool) \
                or not isinstance(self.times_per_journey, Real) \
                or self.times_per_journey <= 0:
            raise SpecError(f"{owner}: \"times_per_journey\" must be a "
                            f"strictly positive number, got "
                            f"{self.times_per_journey!r}.")
        object.__setattr__(self, "times_per_journey", float(self.times_per_journey))


# ---------------------------------------------------------------------------
# Journey
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class JourneySpec:
    """A sequence of steps. The order is preserved: it carries meaning for
    reading the report, even though the calculation does not depend on the
    order."""

    key: str
    label: str
    steps: Tuple[str, ...] = ()
    notes: Tuple[str, ...] = ()

    def __post_init__(self):
        _require_key(self.key, "JourneySpec", "key")
        owner = f"JourneySpec[{self.key}]"
        _require_key(self.label, owner, "label")
        object.__setattr__(self, "steps", tuple(self.steps))
        object.__setattr__(self, "notes", tuple(self.notes))
        for step_key in self.steps:
            _require_key(step_key, owner, "steps (element)")
        if len(set(self.steps)) != len(self.steps):
            # Repeating a step is legitimate, but is expressed through
            # times_per_journey. Two identical entries in the list make the
            # count ambiguous when reading the model.
            raise SpecError(f"{owner}: a step appears twice in "
                            "\"steps\". For a repeated step, use "
                            "times_per_journey on the StepSpec.")


# ---------------------------------------------------------------------------
# Audience
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AudienceSpec:
    """The volume and composition of the traffic.

    Device and network fractions are separated because they will give two
    distinct usage patterns. The e-footprint library does NOT weight usage
    across several devices of the same list: putting phone and computer
    together bills the whole traffic on EACH. Two patterns with proportional
    volumes are the only correct setup.

    `visits_per_year` is not a critical field in the guard-rail sense, and
    that is deliberate: audience data is missing for small sites and
    intranets. The model must stay usable without it, with a default shown
    as such.
    """

    key: str
    label: str
    visits_per_year: Optional[Traced] = None
    phone_fraction: Optional[Traced] = None
    desktop_fraction: Optional[Traced] = None
    wifi_fraction: Optional[Traced] = None
    mobile_fraction: Optional[Traced] = None
    country: Optional[Traced] = None
    country_mix: Tuple[Tuple[str, float], ...] = ()
    journey_key: Optional[str] = None
    notes: Tuple[str, ...] = ()

    # The fractions must sum to 1. Tight tolerance: it absorbs a
    # serialization rounding, not a lopsided split.
    FRACTION_TOLERANCE = 1e-6

    def __post_init__(self):
        _require_key(self.key, "AudienceSpec", "key")
        owner = f"AudienceSpec[{self.key}]"
        _require_key(self.label, owner, "label")
        object.__setattr__(self, "notes", tuple(self.notes))
        object.__setattr__(self, "country_mix",
                           tuple((str(name), float(share))
                                 for name, share in self.country_mix))

        require_traced(self.visits_per_year, owner, "visits_per_year", kind="value")
        require_traced(self.country, owner, "country", kind="object")
        for name in ("phone_fraction", "desktop_fraction",
                     "wifi_fraction", "mobile_fraction"):
            require_traced(getattr(self, name), owner, name, kind="value")

        self._check_pair(owner, "phone_fraction", self.phone_fraction,
                         "desktop_fraction", self.desktop_fraction)
        self._check_pair(owner, "wifi_fraction", self.wifi_fraction,
                         "mobile_fraction", self.mobile_fraction)

        if self.journey_key is not None:
            _require_key(self.journey_key, owner, "journey_key")

    def _check_pair(self, owner, name_a, traced_a, name_b, traced_b):
        """Refuses a split that does not sum to 1, and also refuses half a
        split.

        No automatic renormalization: silently completing the missing
        fraction would fabricate an audience datum nobody measured.
        """
        if (traced_a is None) != (traced_b is None):
            missing = name_b if traced_a is not None else name_a
            raise SpecError(
                f"{owner}: \"{missing}\" is missing while the other part of "
                "the split is provided. The complement is not deduced "
                "automatically: that would invent an audience datum."
            )
        if traced_a is None:
            return
        total = traced_a.value + traced_b.value
        if abs(total - 1.0) > self.FRACTION_TOLERANCE:
            raise SpecError(
                f"{owner}: \"{name_a}\" ({traced_a.value}) and \"{name_b}\" "
                f"({traced_b.value}) sum to {total}, not to 1. An "
                "incomplete split under-counts the traffic; an "
                "excessive split over-counts it."
            )


# ---------------------------------------------------------------------------
# The site: the library's contract
# ---------------------------------------------------------------------------

# Specification contract version. Increment as soon as a field changes
# MEANING (adding an optional field is not a change of meaning).
SCHEMA_VERSION = "1.0"


@dataclass(frozen=True)
class SiteSpec:
    """The complete description of a service, ready to be built.

    It is the ONLY contract of the library: it knows neither the HAR format
    nor the environment-data file. An adapter translates them into SiteSpec,
    which will later allow modeling a service from an architecture diagram
    or a technical interview, without a network capture.

    The collections are tuples: a specification is immutable, and a
    transformation (an archetype) returns a new one rather than modifying the
    one it is given. Otherwise applying two archetypes to the same site would
    produce a result depending on the order of the calls.
    """

    name: str
    servers: Tuple[ServerSpec, ...] = ()
    jobs: Tuple[JobSpec, ...] = ()
    steps: Tuple[StepSpec, ...] = ()
    journeys: Tuple[JourneySpec, ...] = ()
    audience: Optional[AudienceSpec] = None
    third_party_hosts: Tuple[ThirdPartyHost, ...] = ()
    archetypes: Tuple[str, ...] = ()
    notes: Tuple[str, ...] = ()
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self):
        _require_key(self.name, "SiteSpec", "name")
        for attr, expected in (("servers", ServerSpec), ("jobs", JobSpec),
                               ("steps", StepSpec), ("journeys", JourneySpec),
                               ("third_party_hosts", ThirdPartyHost)):
            items = tuple(getattr(self, attr))
            for item in items:
                if not isinstance(item, expected):
                    raise SpecError(
                        f"SiteSpec[{self.name}]: \"{attr}\" expects "
                        f"{expected.__name__} items, got "
                        f"{type(item).__name__}.")
            object.__setattr__(self, attr, items)
        object.__setattr__(self, "archetypes", tuple(self.archetypes))
        object.__setattr__(self, "notes", tuple(self.notes))

        if self.audience is not None and not isinstance(self.audience, AudienceSpec):
            raise SpecError(f"SiteSpec[{self.name}]: \"audience\" must be an "
                            f"AudienceSpec, got {type(self.audience).__name__}.")

    # --- Index by key: essential downstream --------------------------------
    # Without these indexes, attribution results come back indexed by
    # e-footprint object and there is no way to attach them to the business
    # intention that produced them.

    def server_by_key(self, key):
        return _index(self.servers)[key]

    def job_by_key(self, key):
        return _index(self.jobs)[key]

    def step_by_key(self, key):
        return _index(self.steps)[key]

    def journey_by_key(self, key):
        return _index(self.journeys)[key]

    @property
    def server_keys(self):
        return tuple(server.key for server in self.servers)

    @property
    def job_keys(self):
        return tuple(job.key for job in self.jobs)

    @property
    def step_keys(self):
        return tuple(step.key for step in self.steps)

    @property
    def journey_keys(self):
        return tuple(journey.key for journey in self.journeys)


def _index(items):
    """Index key -> element. Duplicates are impossible at this stage:
    `compose()` and `validate_spec()` reject them upstream."""
    return {item.key: item for item in items}
