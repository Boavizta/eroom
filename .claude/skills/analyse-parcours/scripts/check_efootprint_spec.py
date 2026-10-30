#!/usr/bin/env python3
"""
Safety net for the e-footprint refactoring: check of the GUARDRAILS of the
specification library.

WHY THIS SCRIPT EXISTS
-------------------------
`efootprint_model/` rests entirely on refusals: a value without
provenance is refused, a key pointing to nothing is refused, a
key collision is refused. These refusals are the only thing preventing an
untraced number from landing in a report.

But a broken guardrail goes unnoticed. It produces no error: it
simply lets things through. A check that only verifies the happy path
would stay green even if all refusals had disappeared.

This script therefore checks BOTH directions:
  - a correct spec builds (happy path) ;
  - each expected fault is REFUSED (failure path).

The second is the only one that proves something.

WHAT IT DOES NOT DO
--------------------
It checks no CO2e figure: the library tested here computes none, it
describes. Numeric non-regression is the job of
`check_efootprint_contract.py`.

It does not prove genericity: that is `check_genericite.py`, and above all
running on a second real site.

Usage:
    python3 check_efootprint_spec.py
    python3 check_efootprint_spec.py --verbose

Exit code: 0 if all guardrails respond, 1 otherwise.
"""

import argparse
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from efootprint_model import (  # noqa: E402  (after sys.path adjustment)
    RESERVE_CODES,
    AudienceSpec,
    Evidence,
    ExternalApiSpec,
    JobSpec,
    JourneySpec,
    ServerSpec,
    SiteSpec,
    SpecError,
    StepSpec,
    ThirdPartyHost,
    Traced,
    arbitrations_for,
    assumed,
    calculation_reserves,
    collect_sources,
    compose,
    estimated,
    measured,
    orphan_steps,
    primary_server,
    require_calculable,
    script_default,
    unused_jobs,
    validate_spec,
)
from efootprint_model.compose import (  # noqa: E402
    confidence_summary,
    reserves_without_arbitration,
    servers_note,
    untraced_fields,
)
from efootprint_model.spec import (  # noqa: E402
    estimated_label,
    measured_label,
    script_default_label,
)
from efootprint_model.user_time import (  # noqa: E402
    is_within_nielsen_domain,
    nielsen_raw_seconds,
    recalibration_factor,
    step_user_time,
)

# ---------------------------------------------------------------------------
# Check log
# ---------------------------------------------------------------------------


class Journal:
    """Accumulates the results. No check interrupts the following ones: a
    complete report is worth more than a first isolated failure."""

    def __init__(self, verbose=False):
        self.verbose = verbose
        self.passed = 0
        self.failures = []

    def ok(self, label):
        self.passed += 1
        if self.verbose:
            print(f"  [ok]     {label}")

    def fail(self, label, detail):
        self.failures.append((label, detail))
        print(f"  [FAIL]   {label}")
        print(f"           {detail}")

    def expect_ok(self, label, thunk):
        """The happy path: the construction must SUCCEED."""
        try:
            result = thunk()
        except Exception as exc:  # noqa: BLE001 - on rapporte, on ne masque pas
            self.fail(label, f"raised {type(exc).__name__}: {exc}")
            return None
        self.ok(label)
        return result

    def expect_refused(self, label, thunk, expect_in_message=None):
        """The failure path: the construction must be REFUSED by SpecError.

        `expect_in_message` checks that the message POINTS TO the cause. A
        refusal in the right place with an incomprehensible message loses the
        benefit of the guardrail: the person who hits it does not know what
        to fix.
        """
        try:
            thunk()
        except SpecError as exc:
            message = str(exc)
            if expect_in_message and expect_in_message not in message:
                self.fail(label,
                          f"refused (correct) but the message does not mention "
                          f"{expect_in_message!r}: {message}")
                return
            self.ok(label)
            return
        except Exception as exc:  # noqa: BLE001
            self.fail(label,
                      f"refused by {type(exc).__name__} instead of SpecError: "
                      f"{exc}. The library's refusals must be "
                      "recognizable by their type.")
            return
        self.fail(label, "ACCEPTED although this case must be refused. "
                         "The guardrail no longer protects anything.")

    def expect_equal(self, label, actual, expected):
        if actual == expected:
            self.ok(label)
        else:
            self.fail(label, f"expected {expected!r}, got {actual!r}")

    def expect_true(self, label, condition, detail=""):
        if condition:
            self.ok(label)
        else:
            self.fail(label, detail or "condition false")


# ---------------------------------------------------------------------------
# Control dataset
# ---------------------------------------------------------------------------
# FICTITIOUS and deliberately round values, unrelated to any real site. This
# script is not an audit case: copying measurements into it would make it the
# exact entry point that `check_genericite.py` tries to close.

SRC = "control dataset"


def sample_server(key="web", **overrides):
    fields = dict(
        key=key,
        label="Application server",
        server_type=script_default_label("autoscaling",
                                        "default sizing mode"),
        country=estimated_label("France", SRC, comment="inferred from an IP address"),
        carbon_intensity=measured(50.0, "g/kWh", SRC),
        provider=measured_label("provider-a", SRC),
        instance_type=script_default_label("instance-standard",
                                          "missing hosting information"),
        storage_gb=script_default(20.0, "GB_stored", "assumed order of magnitude"),
        evidence=Evidence(hosts=("main-host",), ips=("10.0.0.1",),
                          request_count=200, transferred_bytes=900_000,
                          cache_hit_ratio=0.5, cache_header_seen=True),
    )
    fields.update(overrides)
    return ServerSpec(**fields)


def sample_job(key="page", server_key="web", **overrides):
    fields = dict(
        key=key,
        server_key=server_key,
        label="Loading a page",
        data_transferred=measured(500.0, "kB", SRC),
        request_duration=measured(400.0, "ms", SRC),
        compute_needed=script_default(0.05, "cpu_core",
                                      "server CPU not inferable from a network capture"),
        ram_needed=script_default(50.0, "MB_ram"),
        data_stored=script_default(0.0, "kB_stored"),
    )
    fields.update(overrides)
    return JobSpec(**fields)


def sample_step(key="home", jobs=None, **overrides):
    fields = dict(
        key=key,
        label="View the homepage",
        intention="to get information",
        user_time=estimated(30.0, "s", SRC,
                            comment="reading-time model, not a measurement"),
        jobs=jobs if jobs is not None else {"page": 1},
        words=measured(200.0, "dimensionless", SRC),
    )
    fields.update(overrides)
    return StepSpec(**fields)


def sample_audience(**overrides):
    fields = dict(
        key="visitors",
        label="Annual visitors",
        visits_per_year=estimated(10_000.0, "dimensionless", SRC),
        phone_fraction=measured(0.5, "dimensionless", SRC),
        desktop_fraction=measured(0.5, "dimensionless", SRC),
        wifi_fraction=assumed(0.5, "dimensionless", SRC,
                              comment="assumed split, not measured"),
        mobile_fraction=assumed(0.5, "dimensionless", SRC,
                                comment="assumed split, not measured"),
        journey_key="visit",
    )
    fields.update(overrides)
    return AudienceSpec(**fields)


def sample_site(**overrides):
    fields = dict(
        name="control-site",
        servers=(sample_server(),),
        jobs=(sample_job(),),
        steps=(sample_step(),),
        journeys=(JourneySpec("visit", "Simple visit", ("home",)),),
        audience=sample_audience(),
    )
    fields.update(overrides)
    return SiteSpec(**fields)


# ---------------------------------------------------------------------------
# Checks: Traced
# ---------------------------------------------------------------------------

def check_traced(journal):
    print("Traced — provenance travels with the value")

    journal.expect_ok("a quantity with unit and source builds",
                      lambda: measured(1.5, "kB", SRC))
    journal.expect_ok("a label without unit builds",
                      lambda: measured_label("fournisseur-a", SRC))

    journal.expect_refused(
        "an invented confidence level is refused",
        lambda: Traced(1.0, "kB", SRC, confidence="very-sure"),
        "unknown confidence level")
    journal.expect_refused(
        "a quantity without unit is refused",
        lambda: Traced(1.0, None, SRC),
        "missing unit")
    journal.expect_refused(
        "a text presented as a quantity is refused",
        lambda: Traced("plenty", "kB", SRC),
        "must be a number")
    journal.expect_refused(
        "a label with unit is refused",
        lambda: Traced("fournisseur-a", "kB", SRC, kind="object"),
        "has no unit")
    journal.expect_refused(
        "an unknown value kind is refused",
        lambda: Traced(1.0, "kB", SRC, kind="quantity"),
        "unknown value kind")

    # A boolean is an int in Python: without an explicit check, True
    # would pass for the value 1 and be converted to "1 kB".
    journal.expect_refused(
        "a boolean is not accepted as a quantity",
        lambda: Traced(True, "kB", SRC),
        "must be a number")

    # The confidence vocabulary must stay that of the report, otherwise the badge
    # displays the raw string instead of the colored label.
    from efootprint_model import CONFIDENCE_LEVELS
    journal.expect_equal(
        "the 7 confidence levels of the report are exactly those of the lib",
        CONFIDENCE_LEVELS,
        ("high", "medium", "low", "default", "default_efootprint",
         "default_script", "unjustified"))

    journal.expect_true("has_source distinguishes an empty source from a real one",
                        not Traced(1.0, "kB", "   ").has_source
                        and measured(1.0, "kB", SRC).has_source)

    # The factories must set the right level: that is their whole point.
    journal.expect_equal("measured() sets \"high\"",
                         measured(1.0, "kB", SRC).confidence, "high")
    journal.expect_equal("estimated() sets \"medium\"",
                         estimated(1.0, "kB", SRC).confidence, "medium")
    journal.expect_equal("assumed() sets \"low\"",
                         assumed(1.0, "kB", SRC).confidence, "low")
    journal.expect_equal("script_default() sets \"default_script\"",
                         script_default(1.0, "kB").confidence, "default_script")
    journal.expect_true(
        "script_default() names the script as source, not e-footprint",
        "script" in (script_default(1.0, "kB").source_name or ""),
        "a script default announced as a library default would make "
        "the tool endorse our choices")
    print()


# ---------------------------------------------------------------------------
# Checks: critical fields
# ---------------------------------------------------------------------------

def check_critical_fields(journal):
    print("Critical fields — loud failure rather than an untraced number")

    journal.expect_refused(
        "a missing transferred weight is refused",
        lambda: sample_job(data_transferred=None),
        "data_transferred")
    journal.expect_refused(
        "a transferred weight without provenance is refused",
        lambda: sample_job(data_transferred=Traced(500.0, "kB")),
        "without provenance")
    journal.expect_refused(
        "a missing user time is refused",
        lambda: sample_step(user_time=None),
        "user_time")
    journal.expect_refused(
        "a user time without provenance is refused",
        lambda: sample_step(user_time=Traced(30.0, "s")),
        "without provenance")
    journal.expect_refused(
        "an instance type without provenance is refused",
        lambda: sample_server(instance_type=Traced("instance-x", kind="object")),
        "without provenance")

    # A NON-critical field gets away without provenance: the library must stay
    # usable where data legitimately lacks, without forcing to invent.
    journal.expect_ok(
        "a non-critical field without provenance stays accepted",
        lambda: sample_server(storage_gb=Traced(20.0, "GB_stored")))

    # A server without instance type is valid: that is the case of a
    # generic server, outside public cloud. The model builder will require one or
    # the other field set, the spec does not have to decide.
    journal.expect_ok("a server without instance type stays accepted",
                      lambda: sample_server(instance_type=None))

    journal.expect_refused(
        "a bare value in place of a Traced is refused",
        lambda: sample_job(request_duration=400.0),
        "must be a Traced")
    journal.expect_refused(
        "a label in place of a quantity is refused",
        lambda: sample_job(data_transferred=measured_label("heavy", SRC)),
        "kind")
    print()


# ---------------------------------------------------------------------------
# Checks: structures
# ---------------------------------------------------------------------------

def check_structures(journal):
    print("Structures — rejection of inconsistent states")

    journal.expect_ok("a complete site builds", sample_site)

    journal.expect_refused("an empty key is refused",
                           lambda: sample_job(key="  "), "non-empty text key")

    journal.expect_refused(
        "a null processing weight is refused",
        lambda: sample_step(jobs={"page": 0}),
        "must be removed")
    journal.expect_refused(
        "a negative processing weight is refused",
        lambda: sample_step(jobs={"page": -1}),
        "is -1")
    journal.expect_ok("a fractional weight is accepted",
                      lambda: sample_step(jobs={"page": 0.5}))
    journal.expect_refused(
        "a null times_per_journey is refused",
        lambda: sample_step(times_per_journey=0),
        "strictly positive")

    journal.expect_refused(
        "a step repeated in a journey's list is refused",
        lambda: JourneySpec("visit", "Visit", ("home", "home")),
        "times_per_journey")

    journal.expect_refused(
        "a device split that does not sum to 1 is refused",
        lambda: sample_audience(phone_fraction=measured(0.5, "dimensionless", SRC),
                                desktop_fraction=measured(0.3, "dimensionless", SRC)),
        "sum to")
    journal.expect_refused(
        "a half-split is refused rather than silently completed",
        lambda: sample_audience(desktop_fraction=None),
        "not deduced")
    journal.expect_ok(
        "an audience with no device split at all is accepted",
        lambda: sample_audience(phone_fraction=None, desktop_fraction=None))
    journal.expect_ok(
        "an audience without visit volume is accepted (small sites, intranets)",
        lambda: sample_audience(visits_per_year=None))

    journal.expect_refused(
        "an element of the wrong type in a collection is refused",
        lambda: sample_site(jobs=(sample_step(),)),
        "expects JobSpec")

    journal.expect_refused("a third-party host without a name is refused",
                           lambda: ThirdPartyHost(""), "host")

    # Two distinct situations that would be tempting to confuse: no
    # cache header observed is information about the hosting; an
    # incalculable ratio is an absence of measurement.
    silent = Evidence(hosts=("a",), cache_header_seen=False)
    journal.expect_true(
        "missing cache header and unknown ratio stay distinguishable",
        silent.cache_hit_ratio is None and silent.cache_header_seen is False)
    print()


# ---------------------------------------------------------------------------
# Checks: generative AI call (ExternalApiSpec, Lot 7)
# ---------------------------------------------------------------------------

def check_external_api(journal):
    print("Generative AI — ExternalApiSpec rejects what EcoLogits cannot quantify")

    journal.expect_ok(
        "a complete ExternalApiSpec builds",
        lambda: ExternalApiSpec(provider="anthropic", model_name="claude-sonnet-4-5",
                                output_tokens=measured(300.0, "dimensionless", SRC)))

    journal.expect_refused(
        "an empty provider is refused",
        lambda: ExternalApiSpec(provider="", model_name="claude-sonnet-4-5",
                                output_tokens=measured(300.0, "dimensionless", SRC)),
        "provider")
    journal.expect_refused(
        "an empty model_name is refused",
        lambda: ExternalApiSpec(provider="anthropic", model_name="",
                                output_tokens=measured(300.0, "dimensionless", SRC)),
        "model_name")
    journal.expect_refused(
        "missing output_tokens is refused: critical field, drives the EcoLogits calculation",
        lambda: ExternalApiSpec(provider="anthropic", model_name="claude-sonnet-4-5",
                                output_tokens=None),
        "output_tokens")
    journal.expect_refused(
        "output_tokens without provenance is refused",
        lambda: ExternalApiSpec(provider="anthropic", model_name="claude-sonnet-4-5",
                                output_tokens=Traced(300.0, "dimensionless")),
        "provenance")
    journal.expect_refused(
        "a null request_count_per_step is refused",
        lambda: ExternalApiSpec(provider="anthropic", model_name="claude-sonnet-4-5",
                                output_tokens=measured(300.0, "dimensionless", SRC),
                                request_count_per_step=0),
        "strictly positive")
    journal.expect_refused(
        "a negative request_count_per_step is refused",
        lambda: ExternalApiSpec(provider="anthropic", model_name="claude-sonnet-4-5",
                                output_tokens=measured(300.0, "dimensionless", SRC),
                                request_count_per_step=-1),
        "strictly positive")

    journal.expect_ok(
        "a JobSpec with a complete external_api builds",
        lambda: sample_job(
            external_api=ExternalApiSpec(
                provider="anthropic", model_name="claude-sonnet-4-5",
                output_tokens=measured(300.0, "dimensionless", SRC))))
    journal.expect_refused(
        "an external_api of the wrong type is refused (not a bare name)",
        lambda: sample_job(external_api="anthropic"),
        "ExternalApiSpec")
    print()


# ---------------------------------------------------------------------------
# Checks: cross-key validation
# ---------------------------------------------------------------------------

def check_validation(journal):
    print("Cross-validation — no key points to nothing")

    journal.expect_ok("a consistent site passes validation",
                      lambda: validate_spec(sample_site()))

    journal.expect_refused(
        "a job attributed to a nonexistent server is refused",
        lambda: validate_spec(sample_site(jobs=(sample_job(server_key="ghost"),))),
        "does not exist")
    journal.expect_refused(
        "a step triggering a nonexistent job is refused",
        lambda: validate_spec(sample_site(steps=(sample_step(jobs={"ghost": 1}),))),
        "does not exist")
    journal.expect_refused(
        "a journey going through a nonexistent step is refused",
        lambda: validate_spec(sample_site(
            journeys=(JourneySpec("visit", "Visit", ("ghost",)),))),
        "does not exist")
    journal.expect_refused(
        "an audience pointing to a nonexistent journey is refused",
        lambda: validate_spec(sample_site(
            audience=sample_audience(journey_key="ghost"))),
        "does not exist")

    # A step outside any journey is NOT refused here: describing a site by
    # pieces is legitimate. The refusal happens at calculation entry, checked lower
    # by check_reserves().
    journal.expect_ok(
        "a step outside any journey does not block the description",
        lambda: validate_spec(sample_site(
            steps=(sample_step(), sample_step(key="orphan")))))

    # A job that nothing triggers does not distort any total: it is
    # reported without blocking. Blocking would prevent describing a service whose
    # steps are not all modeled yet.
    with_spare = sample_site(jobs=(sample_job(), sample_job(key="unused")))
    journal.expect_ok("an untriggered job does not block",
                      lambda: validate_spec(with_spare))
    journal.expect_equal("an untriggered job is reported",
                         unused_jobs(with_spare), ("unused",))

    journal.expect_refused("a duplicate server key is refused",
                           lambda: validate_spec(sample_site(
                               servers=(sample_server(), sample_server()))),
                           "declared twice")
    print()


# ---------------------------------------------------------------------------
# Checks: calculation reserves
# ---------------------------------------------------------------------------

def check_reserves(journal):
    print("Reserves — free to describe, refused to publish a wrong number")

    site = sample_site()
    journal.expect_equal("a complete site has no reserve",
                         calculation_reserves(site), ())
    journal.expect_ok("a complete site passes the calculation gate",
                      lambda: require_calculable(site))

    orphan = sample_site(steps=(sample_step(), sample_step(key="orphan")))
    journal.expect_equal("a step outside any journey is detected",
                         orphan_steps(orphan), ("orphan",))
    journal.expect_equal(
        "a step outside any journey becomes a calculation reserve",
        [code for code, _ in calculation_reserves(orphan)],
        ["steps_outside_journey"])
    journal.expect_refused(
        "the calculation is refused as long as the reserve is not assumed",
        lambda: require_calculable(orphan),
        "steps_outside_journey")

    # The central point of the mechanism: one can override, but only
    # explicitly, and the assumed reserve is RETURNED to be written in the report.
    accepted = journal.expect_ok(
        "the reserve can be explicitly assumed",
        lambda: require_calculable(orphan,
                                   accepted_reserves=("steps_outside_journey",)))
    journal.expect_true(
        "an assumed reserve is returned to the caller, not swallowed",
        accepted is not None and len(accepted) == 1
        and accepted[0][0] == "steps_outside_journey",
        "without that the arbitration would disappear and the figure would appear without reserve")

    journal.expect_refused(
        "accepting a reserve that does not apply is refused",
        lambda: require_calculable(site,
                                   accepted_reserves=("steps_outside_journey",)),
        "do not apply")
    journal.expect_refused(
        "an invented reserve code is refused",
        lambda: require_calculable(orphan, accepted_reserves=("whatever",)),
        "do not apply")

    # The other reserves: each would make the total empty or null.
    journal.expect_equal(
        "a site with no journey at all is a reserve",
        [code for code, _ in calculation_reserves(
            sample_site(journeys=(), audience=sample_audience(journey_key=None)))],
        ["no_journey"])
    journal.expect_true(
        "a site without audience is a reserve",
        "no_audience" in [code for code, _ in
                              calculation_reserves(sample_site(audience=None))])
    journal.expect_refused(
        "an empty spec cannot produce a figure",
        lambda: require_calculable(SiteSpec(name="empty")),
        "reserve(s)")

    # An untriggered job distorts no total: it must NOT block
    # the calculation. Confusing the two would make the refusal incomprehensible.
    journal.expect_equal(
        "an untriggered job is not a calculation reserve",
        calculation_reserves(sample_site(
            jobs=(sample_job(), sample_job(key="unused")))),
        ())

    # The refusal must always leave a door open: otherwise the person is stuck.
    journal.expect_equal(
        "each reserve offers at least one remedy",
        reserves_without_arbitration(), ())
    journal.expect_true(
        "the proposed remedies start by fixing, and end by assuming",
        arbitrations_for("steps_outside_journey")[0].startswith("attach")
        and "assum" in arbitrations_for("steps_outside_journey")[-1],
        "the display order suggests a preference: fix before assuming")
    journal.expect_equal("an unknown code offers no remedy, without error",
                         arbitrations_for("nonexistent"), ())
    journal.expect_equal(
        "the enumerated reserve codes are those actually emitted",
        sorted(RESERVE_CODES),
        sorted({"steps_outside_journey", "no_journey", "no_step",
                "no_audience"}))
    print()


# ---------------------------------------------------------------------------
# Checks: compose
# ---------------------------------------------------------------------------

def check_compose(journal):
    print("Compose — never a silent overwrite")

    front = SiteSpec(
        name="control-site",
        servers=(sample_server(),),
        jobs=(sample_job(),),
        steps=(sample_step(),),
        archetypes=("showcase",),
    )
    # Second fragment: SAME server (same evidence), distinct job and step.
    chat = SiteSpec(
        name="control-site",
        servers=(sample_server(provider=None,
                              base_ram=script_default(1.0, "GB_ram")),),
        jobs=(sample_job(key="conversation"),),
        steps=(sample_step(key="dialogue", jobs={"conversation": 3},
                           intention="get help"),),
        archetypes=("conversational-agent",),
    )

    fused = journal.expect_ok(
        "two archetypes compose",
        lambda: compose(front, chat,
                        journeys=(JourneySpec("visit", "Visit",
                                              ("home", "dialogue")),),
                        audience=sample_audience()))
    if fused is not None:
        journal.expect_equal("the common server is shared, not duplicated",
                             len(fused.servers), 1)
        journal.expect_equal("both fragments' jobs are kept",
                             sorted(fused.job_keys), ["conversation", "page"])
        journal.expect_equal("the applied archetypes are traced",
                             fused.archetypes,
                             ("showcase", "conversational-agent"))
        journal.expect_true(
            "the compose fills in the fields missing from the first fragment",
            fused.servers[0].base_ram is not None
            and fused.servers[0].provider is not None,
            "base_ram came from the second fragment, provider from the first")

    # Two servers with the same key on DIFFERENT infrastructures: those are
    # two machines fighting over a name, not one machine described twice.
    other_infra = SiteSpec(
        name="control-site",
        servers=(sample_server(evidence=Evidence(hosts=("other-host",),
                                                 ips=("10.0.0.2",))),),
    )
    journal.expect_refused(
        "two servers with the same key on distinct infrastructures are refused",
        lambda: compose(front, other_infra),
        "key collision")

    # Without evidence, we do not share: two archetypes may have named
    # their server the same by default without talking about the same machine.
    no_evidence = SiteSpec(name="x", servers=(sample_server(evidence=None),))
    journal.expect_refused(
        "without infrastructure evidence, two servers with the same key are refused",
        lambda: compose(no_evidence,
                        SiteSpec(name="x", servers=(sample_server(evidence=None),))),
        "key collision")

    journal.expect_refused(
        "a disagreement on a field of the same server is refused",
        lambda: compose(
            front,
            SiteSpec(name="x", servers=(sample_server(
                provider=measured_label("provider-b", SRC)),))),
        "two different values")

    journal.expect_refused(
        "a job collision is refused",
        lambda: compose(front, SiteSpec(name="x", jobs=(sample_job(),))),
        "key collision")

    journal.expect_refused(
        "two different audiences in the fragments are refused",
        lambda: compose(
            SiteSpec(name="x", audience=sample_audience(journey_key=None)),
            SiteSpec(name="x", audience=sample_audience(key="others",
                                                        journey_key=None))),
        "a single traffic")

    journal.expect_refused("compose() with nothing at all is refused",
                           lambda: compose(), "nothing to compose")
    journal.expect_refused(
        "an object that is not a SiteSpec is refused",
        lambda: compose({"name": "x"}),
        "expects SiteSpec")

    # Immutability: applying a compose must not modify the fragments,
    # otherwise composing twice in the same process would give two results.
    journal.expect_equal("the compose does not modify the fragments",
                         (len(front.servers), len(front.jobs)), (1, 1))

    tiers = compose(
        SiteSpec(name="x", third_party_hosts=(ThirdPartyHost("third-a", 5, 1000),)),
        SiteSpec(name="x", third_party_hosts=(ThirdPartyHost("third-a", 5, 1000),
                                              ThirdPartyHost("third-b", 2, 500))))
    journal.expect_equal(
        "a third-party host seen in two fragments is not counted twice",
        sorted(h.host for h in tiers.third_party_hosts), ["third-a", "third-b"])
    print()


# ---------------------------------------------------------------------------
# Checks: provenances and primary server
# ---------------------------------------------------------------------------

def check_sources_and_primary(journal):
    print("Provenances and primary server")

    site = sample_site()
    sources = collect_sources(site)
    journal.expect_true("each provenance carries its path and its field",
                        all("path" in s and "field" in s for s in sources),
                        "without the path, we do not know which parameter comes "
                        "from which source")
    journal.expect_true("the provenances cover server, job, step "
                        "and audience",
                        {s["path"].split(":")[0] for s in sources}
                        >= {"server", "job", "step", "audience"})

    counts = confidence_summary(site)
    journal.expect_true("the confidence summary counts values per level",
                        sum(counts.values()) == len(sources) and "high" in counts)

    journal.expect_equal(
        "an untraced value on a non-critical field is reported",
        len(untraced_fields(sample_site(
            servers=(sample_server(storage_gb=Traced(20.0, "GB_stored")),)))),
        1)
    journal.expect_equal("a fully traced site reports nothing",
                         untraced_fields(site), ())

    # Primary server: the one carrying the most bytes.
    heavy = sample_server(key="heavy", evidence=Evidence(
        hosts=("h1",), ips=("10.0.0.1",), request_count=10,
        transferred_bytes=900_000))
    light = sample_server(key="light", evidence=Evidence(
        hosts=("h2",), ips=("10.0.0.2",), request_count=500,
        transferred_bytes=2_000))
    multi = sample_site(servers=(light, heavy),
                        jobs=(sample_job(server_key="light"),))
    journal.expect_equal(
        "the primary server is the one carrying the most bytes",
        primary_server(multi).key, "heavy")
    journal.expect_true(
        "many requests are not enough to designate the primary server",
        primary_server(multi).key != "light",
        "an analytics service concentrates requests without carrying the traffic")

    # On a tie in bytes, the choice must be STABLE. Arbitrary is acceptable,
    # changing from one run to another is not.
    tie_a = sample_server(key="bbb", evidence=Evidence(hosts=("h1",),
                                                       transferred_bytes=100))
    tie_b = sample_server(key="aaa", evidence=Evidence(hosts=("h2",),
                                                       transferred_bytes=100))
    journal.expect_equal(
        "on a byte tie, the tie-break is stable and reproducible",
        (primary_server(sample_site(servers=(tie_a, tie_b),
                                    jobs=(sample_job(server_key="bbb"),))).key,
         primary_server(sample_site(servers=(tie_b, tie_a),
                                    jobs=(sample_job(server_key="bbb"),))).key),
        ("aaa", "aaa"))

    journal.expect_true("a server without evidence does not break the tie-break",
                        primary_server(sample_site()).key == "web")
    journal.expect_equal("a site without server returns None, without error",
                         primary_server(SiteSpec(name="x")), None)

    journal.expect_equal("a single-server site has no note to add",
                         servers_note(site), None)
    note = servers_note(multi)
    journal.expect_true(
        "the multi-server note names the primary and the others",
        note is not None and "heavy" in note and "light" in note,
        "without it, singular keys suggest a single machine")
    print()


# ---------------------------------------------------------------------------
# Check: the library stays independent of e-footprint
# ---------------------------------------------------------------------------

def check_nielsen_user_time(journal):
    print("User time — recalibrated Nielsen, never silent outside the domain")

    # Validity domain published by Nielsen (30-1250 words): correctly
    # recognized at both bounds and inside.
    journal.expect_true(
        "150 words is within the Nielsen domain (30-1250)",
        is_within_nielsen_domain(150.0))
    journal.expect_true(
        "30 words (lower bound included) is within the Nielsen domain",
        is_within_nielsen_domain(30.0))
    journal.expect_true(
        "1250 words (upper bound included) is within the Nielsen domain",
        is_within_nielsen_domain(1250.0))
    journal.expect_true(
        "10 words is OUTSIDE the Nielsen domain",
        not is_within_nielsen_domain(10.0))
    journal.expect_true(
        "2000 words is OUTSIDE the Nielsen domain",
        not is_within_nielsen_domain(2000.0))

    # The formula itself: 25 s base + 4.4 s per 100 words.
    journal.expect_equal(
        "raw Nielsen at 0 words equals the base alone (25 s)",
        nielsen_raw_seconds(0.0), 25.0)
    journal.expect_equal(
        "raw Nielsen at 100 words equals 25 + 4.4 s",
        nielsen_raw_seconds(100.0), 29.4)

    # Recalibration: SimilarWeb average / average of the journey's raw Nielsen values.
    # Two pages at 100 and 200 words -> raw Nielsen 29.4 and 33.8, average 31.6.
    raws = [nielsen_raw_seconds(100.0), nielsen_raw_seconds(200.0)]
    factor = recalibration_factor(15.8, raws)
    journal.expect_true(
        "the recalibration factor is the measurement divided by the average of raw Nielsen values",
        factor is not None and abs(factor - 0.5) < 1e-9,
        f"expected 0.5, got {factor!r}")

    journal.expect_true(
        "recalibration impossible without a SimilarWeb measurement (avg_time_on_page_s=None)",
        recalibration_factor(None, raws) is None)
    journal.expect_true(
        "recalibration impossible without any page with a known Nielsen value",
        recalibration_factor(15.8, []) is None)
    journal.expect_true(
        "recalibration impossible if all journey pages are None (Lot 3 fallback)",
        recalibration_factor(15.8, [None, None]) is None)

    # step_user_time(): the four combinations degrade confidence
    # (never silently) exactly when expected.
    in_domain_recalibrated = step_user_time(150.0, factor)
    journal.expect_true(
        "page in domain + recalibration available -> confidence medium",
        in_domain_recalibrated is not None and in_domain_recalibrated.confidence == "medium",
        f"confidence obtained: {in_domain_recalibrated.confidence if in_domain_recalibrated else None!r}")
    journal.expect_true(
        "medium: no degradation reason in the comment",
        "outside the Nielsen validity domain" not in in_domain_recalibrated.comment
        and "WITHOUT recalibration" not in in_domain_recalibrated.comment)

    out_of_domain = step_user_time(10.0, factor)
    journal.expect_true(
        "page outside domain (10 words) -> degraded confidence (low)",
        out_of_domain is not None and out_of_domain.confidence == "low")
    journal.expect_true(
        "the out-of-domain reason is WRITTEN in the comment, never silent",
        "Nielsen validity domain" in out_of_domain.comment)

    no_recalage = step_user_time(150.0, None)
    journal.expect_true(
        "no SimilarWeb measurement -> degraded confidence (low), RAW Nielsen applied",
        no_recalage is not None and no_recalage.confidence == "low"
        and abs(no_recalage.value - nielsen_raw_seconds(150.0)) < 1e-9)
    journal.expect_true(
        "the missing-recalibration reason is WRITTEN in the comment, never silent",
        "no SimilarWeb measurement" in no_recalage.comment)

    both_degraded = step_user_time(10.0, None)
    journal.expect_true(
        "outside domain AND without recalibration -> BOTH reasons are written, not just one",
        both_degraded is not None
        and "Nielsen validity domain" in both_degraded.comment
        and "no SimilarWeb measurement" in both_degraded.comment)

    journal.expect_true(
        "no word count (Lot 3 fallback) -> no guessed Traced, explicit None",
        step_user_time(None, factor) is None)

    journal.expect_true(
        "the produced Traced is properly traced (source_name set): "
        "a Nielsen time must never look like a provenance-less measurement",
        in_domain_recalibrated.has_source)
    print()


def check_no_efootprint_import(journal):
    print("Independence — the spec does not import e-footprint")

    # build.py is the DOCUMENTED EXCEPTION: it is the only module whose
    # purpose is to instantiate e-footprint (cf. its header). Exempting it
    # here by name, not by ignoring it silently: if a second file
    # starts importing e-footprint one day, this check must still see it.
    EXEMPT_FILES = {"build.py"}

    library = SCRIPTS_DIR / "efootprint_model"
    offenders = []
    build_py_imports_efootprint = False
    for path in sorted(library.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        imports_here = []
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(),
                                      start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if stripped.startswith(("import efootprint", "from efootprint")):
                imports_here.append(lineno)
        if not imports_here:
            continue
        if path.name in EXEMPT_FILES:
            build_py_imports_efootprint = True
            continue
        offenders.extend(f"{path.name}:{lineno}" for lineno in imports_here)

    journal.expect_true(
        "no module of the spec (except build.py) imports e-footprint",
        not offenders,
        f"imported in {', '.join(offenders)}. The spec must stay "
        "testable without the library installed; this property is lost at the "
        "first import and goes unnoticed as long as it is installed.")

    journal.expect_true(
        "build.py does import e-footprint (the exemption did not become "
        "obsolete silently)",
        build_py_imports_efootprint,
        "if this check fails, either build.py has been emptied of its role, or "
        "the exemption no longer targets the right file: in both cases, "
        "the exemption must be reviewed, not left lying around without purpose.")

    # The check above is textual. This one is real: we verify that
    # importing the PACKAGE (hence __init__.py, spec.py, compose.py) did
    # actually NOT load e-footprint. build.py is not imported by
    # __init__.py (cf. its own guardrail) so it stays outside this test.
    journal.expect_true(
        "importing the spec does not load e-footprint into memory",
        not any(name == "efootprint" or name.startswith("efootprint.")
                for name in sys.modules),
        "an indirect import is enough to make the library dependent")
    print()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Check of the efootprint_model/ guardrails: a "
                    "correct spec passes, each expected fault is "
                    "refused.")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Also shows the passed checks.")
    args = parser.parse_args()

    journal = Journal(verbose=args.verbose)

    print("-" * 68)
    print("  GUARDRAILS — efootprint_model/")
    print("-" * 68)
    print()

    check_traced(journal)
    check_critical_fields(journal)
    check_structures(journal)
    check_external_api(journal)
    check_validation(journal)
    check_reserves(journal)
    check_compose(journal)
    check_sources_and_primary(journal)
    check_nielsen_user_time(journal)
    check_no_efootprint_import(journal)

    total = journal.passed + len(journal.failures)
    print("-" * 68)
    if journal.failures:
        print(f"[FAIL] {len(journal.failures)} check(s) out of {total}:")
        for label, detail in journal.failures:
            print(f"  - {label}")
            print(f"    {detail}")
        print()
        print("A failing check on an expected REFUSAL is the serious case: the")
        print("guardrail lets things through, so an untraced value can reach")
        print("the report without anything flagging it.")
        return 1

    print(f"[SUCCESS] {total} checks. The guardrails respond.")
    print()
    print("Scope reminder: this check verifies REFUSALS, not figures.")
    print("Numeric non-regression is check_efootprint_contract.py's job,")
    print("and genericity will only be proven by a second real site.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
