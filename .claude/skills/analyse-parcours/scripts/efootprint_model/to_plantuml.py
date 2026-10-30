#!/usr/bin/env python3
"""
Diagram from a `SiteSpec`: user journey, jobs and technical infrastructure,
who talks to whom.

ZERO e-footprint import here, like spec.py/compose.py/from_har.py: this module
only reads spec.py dataclasses, it builds no e-footprint object. Useful to
visualize a spec BEFORE calculating it (e.g. check that an archetype or a
composition has the expected number of servers).

PALETTE AND LAYOUT: copied from the real e-footprint interface
(model_builder, https://e-footprint.boavizta.org/model_builder/) — 3 columns
"Journey" / "Jobs" / "Infrastructure", rounded-corner cards, thin links
without arrowheads. ASSUMED choice (explicit decision of the user): visual
resemblance to the reference tool rather than consistency with the OCTO
palette of the project's other diagrams (one-off/pedagogical use, not a
permanent deliverable). PlantUML cannot draw a round dot at the end of a
line, so the link stays a bare line (`--`), an accepted approximation of the
source interface's LeaderLine rendering.

LAYOUT: 3 columns side by side, TALLER THAN WIDE (enlarged font, wrapped
text). A first "wide" version (`left to right direction` classic) existed then
was dropped after comparison: the user judged this layout clearly more
readable. Really tested (`plantuml -tsvg` + PNG render), not assumed:
  - `skinparam wrapWidth N` alone, `left to right direction` kept: almost no
    effect on width — GraphViz still lays out a column's components in a
    horizontal GRID, never stacked vertically.
  - Invisible links (`-[hidden]->`) WITHOUT removing `left to right
    direction`: counterproductive, BLOWS UP the total width (conflict
    between the global left-right flow and the requested local stacking).
  - The solution that works (measured on the repo's 2 audits, octo.com
    1491x565 -> 1104x1182, ants-permis 2294x346 -> 1120x1098): REMOVE
    `left to right direction` (it is what spreads into a grid), then force
    the layout with invisible links `-[hidden]d-` (vertical stacking within a
    column) and `-[hidden]r-` between consecutive packages (columns kept side
    by side despite the absence of the global directive), plus an enlarged
    font and text wrapping (`wrapWidth`).
  - ACCEPTED LIMIT: beyond 3 consecutive packages chained by `-[hidden]r-`
    (the 5-package case: generative AI + third-party hosts on top of the 3
    base columns), a slight staircase effect appears (progressive vertical
    offset). Documented as a minor aesthetic defect, clearly less penalizing
    than the classic `left to right direction` alternative in that case
    (huge width).
  - RENDERING PITFALL (discovered by test, fixed): cutting a label into
    N-character slices can make a continuation line start with a PlantUML
    creole character (`=`, notably from a URL of the type `?lang=fr` cut into
    `lang`/`=fr`), interpreted as an H1 title (bold centered render) instead
    of the expected text. `_wrap_label()` protects against it, AND now cuts
    on natural boundaries (words, URL separators `/`, `-`, `_`, `.`, `?`,
    `&`, `=`) rather than at the exact character — a word or a path segment
    is never split in its middle.
  - PITFALL (discovered by test, fixed): `skinparam wrapWidth N` was used IN
    ADDITION to `_wrap_label()`, thinking it would only apply to not-yet-
    wrapped texts. Wrong: combined with `*FontSize 16` (enlarged font),
    PlantUML recomputes ITS OWN breaks on text already wrapped by our code,
    and splits e.g. "~1 s" into two lines ("~1" then "s") — an identical text
    without a custom `RectangleFontSize` does not split, the regression only
    appears with a modified font size. Removed from the header: our Python
    wrap is enough, `skinparam wrapWidth` is redundant and becomes dangerous
    as soon as the font size changes.

CALCULATION HYPOTHESES DISPLAYED: explicit request of the user to find, IN
the diagram, the big hypotheses driving the result (not only in the separate
text table of `print_hypotheses()` / `_section_efootprint()`). Two levels:
  - one global note (annual traffic, device mix, audience country mix,
    cumulative reading time of the journey), rendered in `legend bottom`
    (NOT a floating `note`: tested, an unanchored note gets an arbitrarily
    too-narrow width from the layout engine — one word per line, unreadable;
    `legend bottom` spreads over the whole diagram width, one line per
    hypothesis);
  - a detail on each concerned component (step time, job transferred weight,
    server instance type/provider).
Value alone, WITHOUT a confidence badge (explicit decision: the diagram stays
readable, the source/confidence detail lives in the report's hypotheses
table, not duplicated here).
"""

_HEADER = """@startuml {diagram_id}

skinparam BackgroundColor #FFFFFF
skinparam RoundCorner 12
skinparam ArrowColor #9CA3AF
skinparam ArrowThickness 1
skinparam ComponentBackgroundColor #FFFFFF
skinparam ComponentBorderColor #E5E7EB
skinparam ComponentBorderThickness 2
skinparam ComponentFontColor #111928
skinparam ComponentFontSize 16
skinparam DatabaseBackgroundColor #FFFFFF
skinparam DatabaseBorderColor #E5E7EB
skinparam DatabaseBorderThickness 2
skinparam DatabaseFontColor #111928
skinparam DatabaseFontSize 16
skinparam CloudBackgroundColor #FFFFFF
skinparam CloudBorderColor #E5E7EB
skinparam CloudBorderThickness 2
skinparam CloudFontColor #111928
skinparam CloudFontSize 16
skinparam RectangleBackgroundColor #FFFFFF
skinparam RectangleBorderColor #E5E7EB
skinparam RectangleBorderThickness 2
skinparam RectangleFontColor #111928
skinparam RectangleFontSize 16
skinparam NoteBackgroundColor #F9FAFB
skinparam NoteBorderColor #D1D5DB
skinparam NoteFontColor #111928
skinparam NoteFontSize 15
skinparam PackageBackgroundColor #F9FAFB
skinparam PackageBorderColor #D1D5DB
skinparam PackageFontColor #2D4675
skinparam PackageFontStyle bold
skinparam PackageFontSize 18
skinparam defaultFontName Arial
skinparam defaultFontColor #111928

title <color:#2D4675>{title} - Technical topology</color>
"""


def _sanitize_alias(key):
    """Valid PlantUML alias: ASCII letters/digits/underscore only, never
    empty. Strict ASCII (not just `isalnum()`, which accepts accented Unicode):
    this alias also becomes an output file name for `@startuml <id>` (cf.
    site_to_plantuml()), and an accented file name is fragile depending on the
    platform/build tool."""
    cleaned = "".join(c if c.isascii() and (c.isalnum() or c == "_") else "_" for c in key)
    return cleaned if cleaned and cleaned[0].isalpha() else f"c_{cleaned}"


def _escape_label(text):
    """Escapes the quotes of a PlantUML label, never the double dashes
    (cf. the writing rule of the diagrammes-analyse-parcours skill: `--` is
    interpreted as strikethrough text by PlantUML)."""
    escaped = (text or "").replace('"', "'")
    return escaped.replace("--", "- -")


# Characters after which a URL/path can be cut cleanly (the separator stays
# glued to the LEFT chunk, never at the head of the next line): path segments
# (`/`), compound words (`-`, `_`), query (`?`, `&`, `=`), domain (`.`).
_URL_BREAK_CHARS = frozenset("/?&=._-")


def _break_long_word(word, width):
    """Splits a "word" (no space, typically a URL) too long for `width`, by
    cutting AFTER the separator closest to `width` without exceeding it (never
    at the exact character if a separator exists). Brute cut at `width` as a
    last resort, if no separator is found in the window."""
    chunks = []
    remaining = word
    while len(remaining) > width:
        break_at = width
        for i in range(min(width, len(remaining) - 1), 0, -1):
            if remaining[i - 1] in _URL_BREAK_CHARS:
                break_at = i
                break
        chunks.append(remaining[:break_at])
        remaining = remaining[break_at:]
    chunks.append(remaining)
    return chunks


def _wrap_segment(segment, width):
    """Wraps a line (without `\\n`) on WORD boundaries (never in the middle
    of a word, like a classic word processor); a single word too long for
    `width` (typically a space-less URL) is then wrapped by
    `_break_long_word()` on its natural separators."""
    lines = []
    current = ""
    for word in segment.split(" "):
        candidate = f"{current} {word}" if current else word
        if len(candidate) <= width:
            current = candidate
            continue
        if current:
            lines.append(current)
        if len(word) <= width:
            current = word
        else:
            broken = _break_long_word(word, width)
            lines.extend(broken[:-1])
            current = broken[-1]
    if current:
        lines.append(current)
    return lines


def _wrap_label(text, width):
    """Wraps `text` into lines of at most `width` characters, leaves `text`
    unchanged if `width` is None. Call AFTER `_escape_label()` (the wrapping
    never introduces `--`).

    Cuts on natural boundaries (words separated by a space; failing that, URL
    separators `/`, `-`, `_`, `.`, `?`, `&`, `=`) rather than at the exact
    character (cf. `_wrap_segment()`/`_break_long_word()`).

    Each continuation line (never the first) is prefixed with a space IF it
    starts with a PlantUML creole character (`=`, `-`, `*`, `#`, `_`): a TESTED
    pitfall, not assumed — a line starting with `=` (notably from a URL of the
    type `?lang=fr` cut into `lang`/`=fr`) is interpreted as an H1 title (bold
    centered render) instead of the literal expected text. The space
    neutralizes the interpretation without any other notable visual effect.
    Cutting on natural separators makes this case rare (the separator stays
    glued to the left chunk), the guard-rail remains necessary for the brute
    last-resort cut."""
    if not text or width is None:
        return text
    wrapped_segments = []
    for segment in text.split("\\n"):
        lines = _wrap_segment(segment, width) if len(segment) > width else [segment]
        safe_lines = [
            line if i == 0 or not line or line[0] not in "=-*#_" else f" {line}"
            for i, line in enumerate(lines)
        ]
        wrapped_segments.append("\\n".join(safe_lines))
    return "\\n".join(wrapped_segments)


def _format_seconds(traced):
    """User time of a step, readable ("~28 s"), or None if absent. Value
    alone, without source/confidence (cf. module docstring)."""
    if traced is None or traced.value is None:
        return None
    return f"~{traced.value:.0f} s"


def _format_bytes(traced):
    """Transferred weight of a job, readable in kB ("~180 kB"), or None if
    absent. `data_transferred.unit` varies with the model's caller ("B" in
    bytes from from_har.py, "kB" from the demo archetypes): read the unit
    rather than assume a fixed byte, on pain of a silent factor-1000 error."""
    if traced is None or traced.value is None:
        return None
    unit = (traced.unit or "").strip().lower()
    if unit in ("b", "byte", "bytes"):
        kb_value = traced.value / 1000
    elif unit in ("kb",):
        kb_value = traced.value
    elif unit in ("mb",):
        kb_value = traced.value * 1000
    else:
        kb_value = traced.value
    return f"~{kb_value:.0f} kB transferred"


def _format_server_infra(server):
    """Instance type + provider if known (public cloud via Boavizta), else the
    generic server type (autoscaling/serverless/on_premise). Value alone,
    without source/confidence (cf. module docstring)."""
    if server.instance_type and server.instance_type.value:
        provider = server.provider.value if server.provider and server.provider.value else None
        return f"{server.instance_type.value} ({provider})" if provider else server.instance_type.value
    if server.server_type and server.server_type.value:
        return server.server_type.value
    return None


def _global_hypotheses_note(spec, audience_mix=None):
    """Lines of a PlantUML note recapping the cross-cutting hypotheses: annual
    traffic, device mix, audience country mix, cumulative reading time of the
    journey. Returns None if none of these hypotheses is available (spec
    without AudienceSpec, e.g. minimal demo archetype).

    `audience_mix` (dict {country_code: share}) is a parameter SEPARATE from
    `spec.audience`: the audience country mix comes from env-data.json
    (SimilarWeb), never from the SiteSpec itself (AudienceSpec.country_mix
    exists but is not populated by any adapter at the moment) — cf.
    run_efootprint.py::build_topology_overview()."""
    lines = []
    audience = spec.audience
    if audience and audience.visits_per_year and audience.visits_per_year.value:
        lines.append(f"Estimated annual traffic: {audience.visits_per_year.value:,.0f} visits".replace(",", " "))
    if audience and audience.phone_fraction and audience.desktop_fraction:
        lines.append(
            f"Device mix: {audience.phone_fraction.value:.0%} mobile / "
            f"{audience.desktop_fraction.value:.0%} desktop")
    if audience_mix:
        top = sorted(audience_mix.items(), key=lambda kv: kv[1], reverse=True)
        lines.append("Audience country mix: " + ", ".join(f"{cc} {w:.0%}" for cc, w in top))
    total_user_time = sum(
        step.user_time.value for step in spec.steps if step.user_time and step.user_time.value)
    if total_user_time:
        lines.append(f"Total journey reading time: ~{total_user_time:.0f} s")
    return lines or None


def _build_links(spec, step_alias, job_alias, server_alias):
    """Lines of the visible links step -> triggered job, job -> server."""
    lines = []
    for step in spec.steps:
        step_a = step_alias[step.key]
        for job_key in step.jobs:
            job_a = job_alias.get(job_key)
            if job_a is None:
                continue
            lines.append(f"{step_a} -- {job_a}")

    for job in spec.jobs:
        job_a = job_alias[job.key]
        server_a = server_alias.get(job.server_key)
        if server_a is None:
            continue
        lines.append(f"{job_a} -- {server_a}")
    return lines


def site_to_plantuml(spec, *, title=None, wrap_width=30, audience_mix=None, step_shares=None):
    """Generates the PlantUML text of a `SiteSpec`, in 3 columns mimicking the
    e-footprint interface (model_builder) layout: "Journey"
    (JourneySpec/StepSpec), "Jobs" (JobSpec, including generative AI calls),
    "Infrastructure" (ServerSpec, third-party hosts) — columns side by side,
    taller than wide (cf. module docstring).

    Also displays the big calculation hypotheses: one global note (annual
    traffic, device mix, countries via `audience_mix`, cumulative reading
    time) and a detail per component (step time, job transferred weight,
    server instance/provider).

    step_shares : {step_key: pct_of_grand_total} optional, cf.
    `build.py::step_impact_shares()`. Absent BEFORE the calculation (Step 25,
    overview): the impact share only exists once the CO2e has actually been
    computed. Provided after (Step 40) to display, in addition to the time
    already present, the ESTIMATED share (proportional distribution, not an
    independent measurement) of each step in the site's total CO2e.

    Returns a string, to be written into a `.puml` file by the caller (this
    module never touches the disk, like spec.py/compose.py).
    """
    diagram_title = title or spec.name
    # `@startuml <id>` DRIVES THE OUTPUT FILE NAME when plantuml generates
    # from a multi-diagram .puml or without an explicit -o: a title with
    # spaces/accents/parentheses (real site name) would produce a fragile file
    # name. The identifier stays a technical alias, the DISPLAYED TITLE
    # (`title` line, below) carries the readable site name.
    diagram_id = _sanitize_alias(f"site_{spec.name}")
    lines = [_HEADER.format(diagram_id=diagram_id, title=_escape_label(diagram_title))]

    server_alias = {server.key: _sanitize_alias(f"srv_{server.key}") for server in spec.servers}
    job_alias = {job.key: _sanitize_alias(f"job_{job.key}") for job in spec.jobs}
    step_alias = {step.key: _sanitize_alias(f"step_{step.key}") for step in spec.steps}

    def wrapped(text):
        return _wrap_label(_escape_label(text), wrap_width)

    package_order = []  # alias of each top-level package (for the -[hidden]r- chaining)

    # --- Column 1: Journey (JourneySpec grouping StepSpecs) ----------------
    if spec.journeys:
        pkg_alias = "pkg_journey"
        package_order.append(pkg_alias)
        lines.append(f'package "Journey" as {pkg_alias} {{')
        for journey in spec.journeys:
            journey_alias = _sanitize_alias(f"jrn_{journey.key}")
            lines.append(f'  package "{wrapped(journey.label)}" as {journey_alias} {{')
            step_aliases_in_journey = []
            for step_key in journey.steps:
                step = spec.step_by_key(step_key)
                alias = step_alias[step.key]
                step_aliases_in_journey.append(alias)
                step_label = step.label
                user_time_txt = _format_seconds(step.user_time)
                if user_time_txt:
                    step_label = f"{step_label}\\n{user_time_txt}"
                if step_shares and step.key in step_shares:
                    step_label = f"{step_label}\\n~{step_shares[step.key] * 100:.0f} % of CO2e"
                lines.append(f'    rectangle "{wrapped(step_label)}" as {alias}')
            for a, b in zip(step_aliases_in_journey, step_aliases_in_journey[1:]):
                lines.append(f"    {a} -[hidden]d- {b}")
            lines.append("  }")
        lines.append("}")
        lines.append("")

    # --- Column 2: Jobs (JobSpec, including generative AI calls) -----------
    ai_jobs = [job for job in spec.jobs if job.external_api is not None]
    network_only_jobs = [job for job in spec.jobs if job.external_api is None]

    if network_only_jobs:
        pkg_alias = "pkg_jobs"
        package_order.append(pkg_alias)
        lines.append(f'package "Jobs" as {pkg_alias} {{')
        job_aliases_here = [job_alias[job.key] for job in network_only_jobs]
        for job in network_only_jobs:
            alias = job_alias[job.key]
            job_label = job.label
            weight_txt = _format_bytes(job.data_transferred)
            if weight_txt:
                job_label = f"{job_label}\\n{weight_txt}"
            lines.append(f'  [{wrapped(job_label)}] as {alias}')
        for a, b in zip(job_aliases_here, job_aliases_here[1:]):
            lines.append(f"  {a} -[hidden]d- {b}")
        lines.append("}")
        lines.append("")

    if ai_jobs:
        pkg_alias = "pkg_ai"
        package_order.append(pkg_alias)
        lines.append(f'package "Generative AI calls (footprint computed via EcoLogits)" as {pkg_alias} {{')
        job_aliases_here = [job_alias[job.key] for job in ai_jobs]
        for job in ai_jobs:
            alias = job_alias[job.key]
            api = job.external_api
            label = f"{job.label}\\n{api.provider}/{api.model_name}"
            weight_txt = _format_bytes(job.data_transferred)
            if weight_txt:
                label = f"{label}\\n{weight_txt}"
            lines.append(f'  cloud "{wrapped(label)}" as {alias}')
        for a, b in zip(job_aliases_here, job_aliases_here[1:]):
            lines.append(f"  {a} -[hidden]d- {b}")
        lines.append("}")
        lines.append("")

    # --- Column 3: Infrastructure (ServerSpec, third-party hosts) ----------
    pkg_alias = "pkg_infra"
    package_order.append(pkg_alias)
    lines.append(f'package "Infrastructure" as {pkg_alias} {{')
    server_aliases_here = [server_alias[server.key] for server in spec.servers]
    for server in spec.servers:
        alias = server_alias[server.key]
        server_label = server.label
        infra_txt = _format_server_infra(server)
        if infra_txt:
            server_label = f"{server_label}\\n{infra_txt}"
        lines.append(f'  database "{wrapped(server_label)}" as {alias}')
    for a, b in zip(server_aliases_here, server_aliases_here[1:]):
        lines.append(f"  {a} -[hidden]d- {b}")
    lines.append("}")
    lines.append("")

    if spec.third_party_hosts:
        pkg_alias = "pkg_third_party"
        package_order.append(pkg_alias)
        lines.append(f'package "Third-party hosts (network only)" as {pkg_alias} {{')
        tp_aliases_here = []
        for host in spec.third_party_hosts:
            alias = _sanitize_alias(f"tp_{host.host}")
            tp_aliases_here.append(alias)
            label = host.host if not host.note else f"{host.host}\\n({host.note})"
            lines.append(f'  cloud "{wrapped(label)}" as {alias}')
        for a, b in zip(tp_aliases_here, tp_aliases_here[1:]):
            lines.append(f"  {a} -[hidden]d- {b}")
        lines.append("}")
        lines.append("")

    # --- Invisible links between packages: columns side by side without
    # `left to right direction` (cf. module docstring) ----------------------
    for a, b in zip(package_order, package_order[1:]):
        lines.append(f"{a} -[hidden]r- {b}")
    lines.append("")

    # --- Visible links: step -> triggered job, job -> server
    lines.extend(_build_links(spec, step_alias, job_alias, server_alias))

    # --- Global legend: cross-cutting hypotheses ----------------------------
    # `legend bottom` (full width, under the diagram), NOT a floating `note`:
    # tested, an unanchored note gets an arbitrarily too-narrow width from the
    # layout engine (one word per line, unreadable).
    hyp_lines = _global_hypotheses_note(spec, audience_mix=audience_mix)
    if hyp_lines:
        lines.append("")
        lines.append("legend bottom")
        lines.append("<b>Calculation assumptions</b>")
        for hyp_line in hyp_lines:
            escaped = _escape_label(hyp_line)
            lines.append(escaped if not escaped or escaped[0] not in "=-*#_" else f" {escaped}")
        lines.append("end legend")

    lines.append("")
    lines.append("@enduml")
    return "\n".join(lines)


if __name__ == "__main__":
    from .archetypes import dynamic_db

    frag = dynamic_db.apply(
        prefix="demo",
        visits_per_year=50_000,
        page_weight_kb=250,
        user_time_seconds=45,
        source_name="__main__ demo (fictional data)",
    )
    puml = site_to_plantuml(frag, audience_mix={"FR": 0.8, "BE": 0.2})
    assert "@startuml" in puml and "@enduml" in puml, "malformed diagram"
    assert puml.count("database") == len(frag.servers), \
        "one database component per server expected"
    assert "left to right direction" not in puml, \
        "this layout must never reintroduce left to right direction"
    assert "Calculation assumptions" in puml, "expected global assumptions note"
    for line in puml.splitlines():
        stripped = line.strip()
        if stripped and stripped[0] in "=-*#_":
            raise AssertionError(
                f"wrapped line starting with a PlantUML creole character: {stripped!r}")
    print(puml)
    print()
    print(f"OK: diagram generated, {len(frag.servers)} server(s), "
          f"{len(frag.jobs)} job(s), {len(frag.steps)} step(s).")
