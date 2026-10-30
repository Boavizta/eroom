#!/usr/bin/env python3
"""
Merging and validation of specifications. ZERO e-footprint import.

THREE RESPONSIBILITIES, AND NOTHING ELSE
-----------------------------------------
1. `compose()`   : merge several specification fragments into one site.
2. `validate_spec()` : check the consistency of key references.
3. `collect_sources()` : gather all provenances for the report.

The e-footprint model construction is NOT here. This file stays pure Python,
so executable and testable without the library installed.

WHY MERGING IS A SEPARATE MODULE
--------------------------------
A real site is rarely a pure archetype: a showcase site with a shop and a
conversational agent is three combined archetypes. Each archetype is a
transformation that produces a fragment; `compose()` reunites them. The
delicate point is key collision: two fragments that both name their server
"web" must produce an ERROR, never a silent overwrite. An overwrite makes a
server disappear from the model without any signal, and the total drops for
a reason that cannot be found.
"""

from dataclasses import replace

from .spec import (
    AudienceSpec,
    JobSpec,
    JourneySpec,
    ServerSpec,
    SiteSpec,
    SpecError,
    StepSpec,
    ThirdPartyHost,
    Traced,
)

# ---------------------------------------------------------------------------
# Merging
# ---------------------------------------------------------------------------

# The merged collections, with the readable name used in error messages.
# The order has no functional importance.
_MERGED = (
    ("servers", "server"),
    ("jobs", "job"),
    ("steps", "step"),
    ("journeys", "journey"),
)


def compose(*fragments, name=None, audience=None, journeys=None,
            third_party_hosts=None, notes=()):
    """Merges specification fragments into a single `SiteSpec`.

    fragments : SiteSpecs, typically produced by archetypes.
    name      : name of the resulting site. Defaults to the first fragment's.
    audience  : audience of the site. If no fragment carries one and none is
                given, the result has none; it is up to the model builder to
                say whether it can do without, not up to the merge.
    journeys  : replaces the fragments' journeys. An archetype describes
                steps; the real sequence is an audit decision, not an
                archetype's.
    third_party_hosts : observed third-party hosts, counted on the network
                only.

    COLLISIONS: two fragments declaring the same key raise SpecError, with
    ONE exception. Two ServerSpecs with the same key whose `evidence` points
    to the same infrastructure are MERGED: that is the normal case when two
    archetypes apply to the same web server. Without this rule, the server
    would have to be duplicated and its manufacturing footprint would be
    counted twice.

    Two ServerSpecs with the same key whose evidence DIFFERS stay an error:
    they are two machines fighting over a name.
    """
    fragments = [f for f in fragments if f is not None]
    for fragment in fragments:
        if not isinstance(fragment, SiteSpec):
            raise SpecError(
                "compose() expects SiteSpec fragments, got "
                f"{type(fragment).__name__}. An archetype must return a "
                "complete specification, not an object fragment."
            )

    if not fragments and name is None:
        raise SpecError("compose() with no fragment and no name: nothing to "
                        "compose. Provide at least `name` to build an empty "
                        "site.")

    resolved_name = name or fragments[0].name

    merged = {attr: [] for attr, _ in _MERGED}
    seen = {attr: {} for attr, _ in _MERGED}

    for fragment in fragments:
        for attr, label in _MERGED:
            for item in getattr(fragment, attr):
                previous = seen[attr].get(item.key)
                if previous is None:
                    seen[attr][item.key] = item
                    merged[attr].append(item)
                    continue
                if attr == "servers" and _same_infrastructure(previous, item):
                    fused = _fuse_servers(previous, item)
                    seen[attr][item.key] = fused
                    merged[attr][merged[attr].index(previous)] = fused
                    continue
                raise SpecError(
                    f"key collision on the {label} \"{item.key}\" between two "
                    f"fragments of \"{resolved_name}\". Rename one of the two "
                    "with a distinct prefix. Merging never chooses for you: "
                    "silently overwriting would make a "
                    f"{label} disappear from the model."
                )

    # The explicit audience wins. Otherwise take the fragments', provided
    # they do not carry two different ones: a site's traffic is unique, two
    # audiences signal a composition error.
    resolved_audience = audience
    if resolved_audience is None:
        candidates = [f.audience for f in fragments if f.audience is not None]
        distinct = {a.key: a for a in candidates}
        if len(distinct) > 1:
            raise SpecError(
                f"\"{resolved_name}\": {len(distinct)} different audiences "
                f"in the fragments ({', '.join(sorted(distinct))}). A site has "
                "a single traffic. Pass the chosen audience to "
                "compose(audience=...)."
            )
        resolved_audience = candidates[0] if candidates else None

    resolved_journeys = tuple(journeys) if journeys is not None \
        else tuple(merged["journeys"])

    resolved_third_party = tuple(third_party_hosts) if third_party_hosts is not None \
        else _merge_third_party(fragments)

    archetypes = []
    for fragment in fragments:
        for archetype in fragment.archetypes:
            if archetype not in archetypes:
                archetypes.append(archetype)

    all_notes = list(notes)
    for fragment in fragments:
        for note in fragment.notes:
            if note not in all_notes:
                all_notes.append(note)

    spec = SiteSpec(
        name=resolved_name,
        servers=tuple(merged["servers"]),
        jobs=tuple(merged["jobs"]),
        steps=tuple(merged["steps"]),
        journeys=resolved_journeys,
        audience=resolved_audience,
        third_party_hosts=resolved_third_party,
        archetypes=tuple(archetypes),
        notes=tuple(all_notes),
    )
    validate_spec(spec)
    return spec


def _same_infrastructure(server_a, server_b):
    """Do two ServerSpecs describe the same machine?

    Requires that BOTH carry evidence, and that the evidence agrees. Without
    evidence, no conclusion: merging on key equality alone would fuse two
    distinct servers that an archetype happened to name identically by
    default.
    """
    if server_a.evidence is None or server_b.evidence is None:
        return False
    return server_a.evidence.identity == server_b.evidence.identity


def _fuse_servers(base, other):
    """Completes `base` with the fields that only `other` fills in.

    NEVER replaces a value already present: the first fragment keeps the
    upper hand. A field filled in differently by both is reported, because
    it is a modeling disagreement about the same machine, not a detail to
    arbitrate silently.
    """
    updates = {}
    for field_name in ("server_type", "country", "carbon_intensity", "provider",
                       "instance_type", "storage_gb", "base_ram", "base_compute",
                       "power", "carbon_footprint_fabrication", "pue"):
        mine = getattr(base, field_name)
        theirs = getattr(other, field_name)
        if theirs is None:
            continue
        if mine is None:
            updates[field_name] = theirs
            continue
        if mine.value != theirs.value:
            raise SpecError(
                f"server \"{base.key}\" receives two different values for "
                f"\"{field_name}\": {mine.value!r} and {theirs.value!r}. The "
                "two fragments point to the same infrastructure but disagree. "
                "Decide explicitly before composing."
            )

    notes = list(base.notes) + [n for n in other.notes if n not in base.notes]
    updates["notes"] = tuple(notes)
    return replace(base, **updates)


def _merge_third_party(fragments):
    """Reunites the fragments' third-party hosts, one record per host.

    The first one seen wins: the counts come from the same HAR, adding them
    up would count them twice.
    """
    merged = {}
    for fragment in fragments:
        for host in fragment.third_party_hosts:
            merged.setdefault(host.host, host)
    return tuple(merged.values())


# ---------------------------------------------------------------------------
# Validation of key references
# ---------------------------------------------------------------------------

def validate_spec(spec):
    """Checks that no key points into the void and none is duplicated.

    These checks cannot live in the dataclasses: a `StepSpec` only knows job
    keys, it has no way to know whether the job exists. Only the whole site
    knows.

    Raises SpecError on the first problem. Returns the site unchanged, so
    `spec = validate_spec(spec)` can be written.
    """
    if not isinstance(spec, SiteSpec):
        raise SpecError(f"validate_spec() expects a SiteSpec, got "
                        f"{type(spec).__name__}.")

    owner = f"SiteSpec[{spec.name}]"

    for attr, label in _MERGED:
        _check_unique_keys(getattr(spec, attr), owner, label)
    _check_unique_hosts(spec.third_party_hosts, owner)

    server_keys = set(spec.server_keys)
    job_keys = set(spec.job_keys)
    step_keys = set(spec.step_keys)
    journey_keys = set(spec.journey_keys)

    for job in spec.jobs:
        if job.server_key not in server_keys:
            raise SpecError(
                f"{owner}: job \"{job.key}\" is assigned to server "
                f"\"{job.server_key}\", which does not exist. "
                f"Declared servers: {_listing(server_keys)}."
            )

    for step in spec.steps:
        for job_key in step.jobs:
            if job_key not in job_keys:
                raise SpecError(
                    f"{owner}: step \"{step.key}\" triggers job "
                    f"\"{job_key}\", which does not exist. "
                    f"Declared jobs: {_listing(job_keys)}."
                )

    for journey in spec.journeys:
        for step_key in journey.steps:
            if step_key not in step_keys:
                raise SpecError(
                    f"{owner}: journey \"{journey.key}\" goes through step "
                    f"\"{step_key}\", which does not exist. "
                    f"Declared steps: {_listing(step_keys)}."
                )

    if spec.audience is not None and spec.audience.journey_key is not None:
        if spec.audience.journey_key not in journey_keys:
            raise SpecError(
                f"{owner}: audience \"{spec.audience.key}\" refers to "
                f"journey \"{spec.audience.journey_key}\", which does not exist. "
                f"Declared journeys: {_listing(journey_keys)}."
            )

    # Steps outside any journey are NOT handled here: see orphan_steps() and
    # require_calculable() right below, as well as the note that precedes them.
    return spec


# ---------------------------------------------------------------------------
# Reserves: what does not prevent describing, but prevents publishing
# ---------------------------------------------------------------------------
# A step attached to no journey is visited by nobody: its footprint enters
# no total. The model still builds and the number is simply lower, without
# saying anything.
#
# The refusal therefore does happen, but NOT at the same time as the others:
# describing a site in pieces (the pages first, the journeys later) is a
# legitimate use, and blocking at description time would forbid it. The
# risk, however, only exists once a number is calculated, hence publishable.
#
# Hence the separation:
#   validate_spec()      -> says nothing, the description stays free
#   orphan_steps()       -> lists the reserves, to display them
#   require_calculable() -> refuses, at the entrance of the calculation
#
# Decision of the user running the audit, to be respected downstream: at
# calculation time, the person launching the audit must be able to ARBITRATE
# live (attach the step, remove it, or proceed knowingly) rather than suffer
# a hard refusal. Two constraints on this interaction:
#   - with no possible answer (automatic execution, no keyboard), the default
#     is the REFUSAL. A favorable default would publish an incomplete total.
#   - the retained arbitration must be TRACED in the report (block
#     model.decisions), otherwise it is a silent fix, exactly what we want to
#     avoid.


def orphan_steps(spec):
    """Declared steps that no journey traverses.

    Empty if the site declares no journey yet: at that stage nothing is
    orphan, the description is simply in progress. Distinguishing the two
    matters, otherwise a site under construction would show all its steps as
    reserves.
    """
    if not spec.journeys:
        return ()
    used = {key for journey in spec.journeys for key in journey.steps}
    return tuple(sorted(set(spec.step_keys) - used))


def unused_jobs(spec):
    """Declared jobs triggered by no step.

    Unlike an orphan step, it distorts no total: it is only dead weight in
    the model. To be reported, never to be refused.
    """
    triggered = {job_key for step in spec.steps for job_key in step.jobs}
    return tuple(sorted(set(spec.job_keys) - triggered))


# All existing reserve codes, enumerated once. Source of truth for the
# "every reserve offers an exit" check: deriving it from an example
# specification would not work, no specification triggering all four at once
# (an empty specification has no step, hence no orphan step).
RESERVE_CODES = (
    "steps_outside_journey",
    "no_journey",
    "no_step",
    "no_audience",
)


def calculation_reserves(spec):
    """Reserves that make a published number false, as (code, message).

    What the function does NOT return is just as important: an untriggered
    job is not in there, because it changes no total.

    Returning codes rather than text alone lets the caller offer the
    arbitration adapted to each reserve, instead of a single message.
    """
    reserves = []

    orphans = orphan_steps(spec)
    if orphans:
        reserves.append((
            "steps_outside_journey",
            f"{len(orphans)} step(s) appear in no journey: "
            f"{_listing(orphans)}. They will be visited by nobody, so "
            "their footprint will not enter the total. The published "
            "number would be lower than the described reality."
        ))

    if not spec.journeys:
        reserves.append((
            "no_journey",
            "no journey is declared. Without a journey, no step is "
            "visited and the total would be empty of any usage."
        ))

    if not spec.steps:
        reserves.append((
            "no_step",
            "no step is declared. The model would have no usage to "
            "calculate."
        ))

    if spec.audience is None:
        reserves.append((
            "no_audience",
            "no audience is declared. Without a traffic volume, there is "
            "nothing to multiply: the total would be zero."
        ))

    return tuple(reserves)


def require_calculable(spec, *, accepted_reserves=()):
    """Entrance gate of the calculation: refuses a specification that would
    produce a false number, except EXPLICITLY accepted reserves.

    accepted_reserves : reserve codes that the person launching the audit
    chose to assume. Acceptance is a voluntary act, never a default: calling
    this function without passing anything refuses every reserve.

    Returns the accepted reserves, as (code, message), so the caller can
    write them into the report. Returning them rather than hiding them is the
    important point: an assumed reserve must stay visible in the deliverable,
    otherwise the arbitration disappears and the number looks reserve-free.
    """
    validate_spec(spec)

    reserves = calculation_reserves(spec)
    accepted_codes = set(accepted_reserves)

    unknown = accepted_codes - {code for code, _ in reserves}
    if unknown:
        # Accepting a reserve that does not apply is almost always a code
        # copied by mistake. Reporting it prevents an acceptance from lingering
        # in a command and later covering a real reserve.
        raise SpecError(
            f"accepted reserve(s) that do not apply to "
            f"\"{spec.name}\": {_listing(unknown)}. "
            f"Current reserves: {_listing(code for code, _ in reserves)}."
        )

    blocking = [(code, message) for code, message in reserves
                if code not in accepted_codes]
    if blocking:
        details = "\n".join(f"  - [{code}] {message}" for code, message in blocking)
        raise SpecError(
            f"SiteSpec[{spec.name}]: {len(blocking)} reserve(s) prevent a "
            f"publishable calculation:\n{details}\n"
            "Fix the specification, or assume the reserve by passing its "
            "code to accepted_reserves — in which case it will be written in "
            "the report, not passed in silence."
        )

    return tuple((code, message) for code, message in reserves
                 if code in accepted_codes)


# Proposable arbitrations for each reserve, in the order to present them.
# These labels live here, next to the reserve definitions, so that adding a
# reserve without proposing an exit is visible right away: a blocking
# reserve without arbitration leaves the person with a refusal without a
# door.
#
# The command line will draw on them to ask the question live (lot 5). The
# last choice of each list is the acceptance, never the first: the display
# order suggests a preference, and correcting is better than assuming.
RESERVE_ARBITRATIONS = {
    "steps_outside_journey": (
        "attach these steps to a journey (the total will count them)",
        "remove them from the specification (they do not describe this site)",
        "calculate without them, assuming it (the total will be lower, and "
        "the report will say so)",
    ),
    "no_journey": (
        "declare the journey followed by the visitors",
        "give up on the calculation for now",
    ),
    "no_step": (
        "describe at least one visited page",
        "give up on the calculation for now",
    ),
    "no_audience": (
        "fill in the annual traffic, even approximate and flagged as such",
        "give up on the calculation for now",
    ),
}


def arbitrations_for(code):
    """Proposable exits for a reserve, or () if the reserve proposes none.

    Returns an empty tuple rather than raising: a reserve without arbitration
    stays blocking and that is the safe behavior. But it must be detectable,
    hence `reserves_without_arbitration()`.
    """
    return RESERVE_ARBITRATIONS.get(code, ())


def reserves_without_arbitration():
    """Reserve codes that no arbitration covers.

    Serves as a check: a reserve added without a proposed exit leaves the
    person facing a refusal without a solution. Checked by
    check_efootprint_spec.py.
    """
    return tuple(sorted(set(RESERVE_CODES) - set(RESERVE_ARBITRATIONS)))


def _check_unique_keys(items, owner, label):
    seen = set()
    for item in items:
        if item.key in seen:
            raise SpecError(f"{owner}: the {label} \"{item.key}\" is declared "
                            "twice.")
        seen.add(item.key)


def _check_unique_hosts(hosts, owner):
    seen = set()
    for host in hosts:
        if host.host in seen:
            raise SpecError(f"{owner}: the third-party host \"{host.host}\" is "
                            "declared twice.")
        seen.add(host.host)


def _listing(keys):
    """Sorted, readable list, or an explicit mention when there is nothing.

    "none" rather than an empty list: on a key error, knowing that NOTHING is
    declared points to a different cause than a typo.
    """
    keys = sorted(keys)
    return ", ".join(f"\"{k}\"" for k in keys) if keys else "none"


# ---------------------------------------------------------------------------
# Provenance collection
# ---------------------------------------------------------------------------

# Where to look for Traced, and under which path to announce them. The path
# serves to find the value back in the model from the report:
# "server:web.storage_gb" reads without documentation.
_TRACED_SCOPES = (
    ("servers", "server"),
    ("jobs", "job"),
    ("steps", "step"),
)


def iter_traced(spec):
    """Walks all `Traced` of the site, as (path, field, traced).

    Walks the SPECIFICATION, not the built model: so usable without
    e-footprint and without having launched any calculation. This is what
    allows checking traceability BEFORE producing a number.
    """
    for attr, prefix in _TRACED_SCOPES:
        for item in getattr(spec, attr):
            for field_name, value in vars(item).items():
                if isinstance(value, Traced):
                    yield f"{prefix}:{item.key}", field_name, value

    if spec.audience is not None:
        for field_name, value in vars(spec.audience).items():
            if isinstance(value, Traced):
                yield f"audience:{spec.audience.key}", field_name, value


def collect_sources(spec):
    """Gathers the provenances for the `sources` block of the results JSON.

    One entry per (path, field), in walk order. No deduplication by source:
    the report must be able to say which PARAMETER comes from which source,
    and grouping by source would lose exactly that link.
    """
    entries = []
    for path, field_name, traced in iter_traced(spec):
        entry = {"path": path, "field": field_name}
        entry.update(traced.as_dict())
        entries.append(entry)
    return entries


def untraced_fields(spec):
    """Fields carrying a value without provenance, as (path, field, value).

    The dataclass guard-rail covers CRITICAL fields. This function covers the
    rest: it does not block, it makes visible. Without it, we would not know
    how many untraced values a model contains, and the report would show
    "default" badges without knowing which are avoidable.
    """
    return tuple(
        (path, field_name, traced.value)
        for path, field_name, traced in iter_traced(spec)
        if not traced.has_source
    )


def confidence_summary(spec):
    """Counts the Traced per confidence level.

    Gives in one line the global solidity of a model. Useful as a
    non-regression marker: a refactoring that shifts values from "high" to
    "default" has lost traceability along the way, which no total in kilos
    would reveal.
    """
    counts = {}
    for _, _, traced in iter_traced(spec):
        counts[traced.confidence] = counts.get(traced.confidence, 0) + 1
    return counts


# ---------------------------------------------------------------------------
# Primary server
# ---------------------------------------------------------------------------

def primary_server(spec):
    """The server that feeds the historical singular keys of the JSON.

    The results file has carried singular keys since the beginning
    (provider, instance_type, storage_gb). When the model contains several
    servers, one must decide WHICH one they describe, otherwise the report
    would show an arbitrary server, changing from one run to the next.

    Criterion: the most transferred bytes, measured in the HAR. That is the
    server carrying the traffic, hence the one spontaneously described as
    "the" site's server.

    Explicit tie-break when bytes are unknown or equal: the number of
    requests, then the alphabetical order of the key. Alphabetical order has
    no physical meaning, but it is STABLE, and that is all we ask of it: on
    a tie, an arbitrary but reproducible choice is better than a choice
    depending on the HAR read order.

    Returns None if the site has no server.
    """
    if not spec.servers:
        return None

    def sort_key(server):
        evidence = server.evidence
        transferred = (evidence.transferred_bytes or 0) if evidence else 0
        requests = (evidence.request_count or 0) if evidence else 0
        return (-transferred, -requests, server.key)

    return sorted(spec.servers, key=sort_key)[0]


def servers_note(spec):
    """Sentence to write in the JSON when the model contains several servers.

    Without it, a reader sees `provider` and `instance_type` in the singular
    and concludes the site fits on one machine. The note says what these keys
    really describe and what they leave out.
    """
    if len(spec.servers) <= 1:
        return None
    main = primary_server(spec)
    others = [s.key for s in spec.servers if s.key != main.key]
    return (
        f"The model contains {len(spec.servers)} servers. The singular keys "
        f"above describe the primary server "
        f"(\"{main.key}\", the one carrying the most bytes). The others "
        f"({_listing(others)}) are modeled separately and appear in the "
        "\"model\" block, with their own footprint."
    )
