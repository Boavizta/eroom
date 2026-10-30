#!/usr/bin/env python3
"""Generates an SVG radar chart (circular grid) for the synthesis of the EOF reference framework.

Usage:
    python3 generate_radar_svg.py output.svg
        -> generates a two-layer demo radar with fictitious values
           (the 6 axes of the EOF framework, one axis with no answer,
           one declared non-empty layer) to see the full rendering

    from generate_radar_svg import build_radar_from_results
    svg_text = build_radar_from_results(audit_results, "octo.com")

TWO LAYERS, AND WHY THEY EXIST
--------------------------------
An axis at 0% because everything was looked at and everything is fine, and an
axis at 0% because one criterion out of six was looked at, must not look the
same. Measured on a real audit: dimension 4 went from "empty" to 0% the day
ONE criterion out of six got an answer, and a good one. The radar then showed
an exemplary axis where almost nothing had been looked at.

Three elements answer this, and none of them invents a number:

  - the SOLID layer: the RETAINED potential, i.e. everything that is not a
    mere assumption from a weak signal (provenances of
    PROVENANCES_RETENUES: measured, inferred from a magnitude, publicly
    declared by the service, or indicated by the service via the questionnaire);
  - the HATCHED layer: the UNCERTAINTY MARGIN, i.e. the share of the potential
    that rests only on an inference from a weak signal (provenance
    `assumed`, the only one in PROVENANCES_MARGE_INCERTITUDE). The outer
    outline of the figure (solid + hatched added together) remains the global
    estimate of the axis's optimization potential;
  - under each axis, the number of criteria filled in out of its total; and
    under the radar, a gauge of what is filled in at the framework's scale.

A criterion with no answer gets NO default value, neither the best nor the
worst: the gauge says what is missing instead of filling it in.

All coordinates are computed by trigonameetry (math.cos/sin), never estimated
by eye. All text is XML-escaped (xml.sax.saxutils.escape): an unescaped "&" in
a label (e.g. "Storage & Data") breaks XML parsing and can silently make
everything after it disappear in some browsers.
"""
import math
import sys
from xml.sax.saxutils import escape

NAVY = "#2D4675"  # contrast ~9.35:1 on white background (RGAA/WCAG AAA)
GREY = "#5F5F5F"  # contrast ~6.7:1 on white background: color of the absence of an answer,
                   # visibly muted compared to NAVY without dropping below the AA threshold
SCALE = 100  # axis in percent (0-100%), like the radar of the source Google Sheet

# Identifier of the hatch pattern. Distinctive on purpose: the SVG is INLINED in
# the HTML report, among other SVGs. A generic id ("hatch") would be captured by
# the first pattern of the document with the same name, and the uncertainty-margin
# layer would be filled with the hatching of a neighboring diagram.
HACHURE_ID = "eof-radar-declared-layer"

AXES_EOF = [
    "🛖 Product",
    "🗺️ Architecture",
    "🏢 Infrastructure",
    "💾 Storage & Data",
    "👨‍💻 Algo & Code",
    "🛠 Ease of change",
]

# Distribution of provenances between the two layers.
#
# Decided on 2026-09-11 with the user: the solid layer carries the RETAINED
# potential (everything that is not a mere assumption from a weak signal),
# the hatched layer carries the UNCERTAINTY MARGIN (only `assumed`, the
# most fragile provenance of the manifest's precedence axis). Before that
# date, the split opposed "us" (collected/estimated/assumed) to "them"
# (declared/stated); that split mixed the most solid provenance
# (collected) and the most fragile one (assumed) in the same layer, which
# corresponded to no reliability notion useful to the reader.
PROVENANCES_RETENUES = ("collected", "estimated", "declared", "stated")
PROVENANCES_MARGE_INCERTITUDE = ("assumed",)

# Readable labels of the provenances, for the breakdown line under the radar.
# The manifest requires that provenances stay distinguishable on the radar:
# the two layers distinguish their origin, this line gives the detail.
LIBELLES_PROVENANCE = {
    "collected": "collected",
    "estimated": "estimate",
    "declared": "declared",
    "stated": "stated",
    "assumed": "assumed",
}


def _pct(value, decimals=1):
    """Formats a percentage the French way: decimal comma, space before %.

    Never receives None: the caller handles the absence of an answer separately,
    with the label "no answer". A None arriving here would display "None %" in a
    client deliverable, an accident that already happened and is monitored by
    check_report_values.py.
    """
    return f"{value:.{decimals}f}".replace(".", ",") + " %"


def _decompte_criteres(answered, total):
    """Formats "4 criteria filled in out of 16", agreement included, including zero.

    Written to be read aloud: "0 criteria out of 10 filled in" sounds wrong
    and suggests that a null criterion exists.
    """
    if answered == 0:
        return f"no criterion filled in out of {total}"
    if answered == 1:
        return f"1 criterion filled in out of {total}"
    return f"{answered} criteria filled in out of {total}"


def _wrap_text(text):
    """Splits a long text into lines that fit within the radar's width.

    Cuts at spaces without ever cutting a word. 152 characters is the length
    of the original note, which fit on one line without overflowing: a note of
    this length or less is not split, which preserves non-regression.
    Beyond that, wrapping happens at 110 characters per line, which corresponds
    to roughly 880 pixels in 12pt sans-serif, a width that fits comfortably
    within the 1100-pixel canvas with margins.
    """
    # If the text fits on one line (original note), do not split it.
    if len(text) <= 152:
        return [text]

    # Otherwise, wrap at 110 characters per line.
    max_length = 110
    lines = []
    words = text.split()
    current_line = []
    current_length = 0

    for word in words:
        # +1 for the space preceding the word (except for the first word of the line)
        word_length = len(word) + (1 if current_line else 0)
        if current_length + word_length <= max_length:
            current_line.append(word)
            current_length += word_length
        else:
            # The current line is full, close it
            if current_line:
                lines.append(" ".join(current_line))
            current_line = [word]
            current_length = len(word)

    # Add the last line if it exists
    if current_line:
        lines.append(" ".join(current_line))

    return lines


def radar_svg(axes, title="Radar EROOM", note=None, width=1100, height=None,
               axes_set=None, axes_answered=None, axes_out_of_scope=None,
               axes_discarded=None, coverage=None, provenances=None):
    """axes: list of tuples (name, value 0-100 OR None). Returns the full SVG text.

    A `None` value (dimension with no real data) is rendered at
    r=0 (the polygon pinches on that axis), with a grey ring and the label
    "no answer" instead of a percentage: never assimilated to a real 0%
    (which would mean "confirmed strength everywhere"), an absence of an answer
    is not an answer.

    Optional parameters, all omittable: without them, the function renders the
    single-layer radar from before chantier 13, which keeps old callers valid.

      axes_set      list of values (0-100 or None), SAME ORDER as `axes`,
                       for the solid layer. `axes` then carries the total, which is
                       drawn hatched around it.
      axes_answered  list of tuples (answered, total), same order: displayed
                       under each axis label.
      coverage       tuple (percentage, answered, total) for the gauge.
      provenances      dict {provenance: count} for the breakdown line.

    width generous by default: the longest label ("Ease of
    change") far exceeds the radar's radius. A value too small
    clips it on the edge of the image (observed and corrected after checking
    by real rendering, not by re-reading the code).

    height tight on the contrary, and computed according to what is requested: without
    a caption, the lowest content is the bottom axis's label, whose baseline
    falls at cy + R + 55 + 34 = 669. A value too large clips nothing but
    leaves an empty white band under the radar, clearly visible in the HTML
    report where the SVG is framed (observed at 900, brought back to 720).

    Verification pitfall: checking this rendering with `qlmanage -t` (QuickLook)
    gives a false image. It produces a square thumbnail, shifts the content
    and clips the right-hand labels, which makes it look like an overflow that
    does not exist. Use `rsvg-convert -o output.png file.svg`, which respects
    the viewBox (it does render emojis in black, lacking a color font:
    that is its limit, not the SVG's).
    """
    n = len(axes)
    if axes_set is not None and len(axes_set) != n:
        raise ValueError(
            f"axes_set has {len(axes_set)} values for {n} axes: the two layers "
            "are indexed by position, a shift would attribute one "
            "dimension's measure to its neighbor without the rendering looking wrong"
        )
    if axes_answered is not None and len(axes_answered) != n:
        raise ValueError(
            f"axes_answered has {len(axes_answered)} values for {n} axes"
        )

    footer = coverage is not None or provenances is not None
    if height is None:
        height = 792 if footer else 720

    # Adjust the height if the note needs several lines.
    if note:
        note_lines = _wrap_text(note)
        if len(note_lines) > 1:
            # Line height of 18, first line at y=766, last at y=766 + (n-1)*18
            # We add 22 pixels of margin at the bottom after the last line.
            height_needed = 766 + (len(note_lines) - 1) * 18 + 22
            if height < height_needed:
                height = height_needed

    cx, cy = width / 2, 360
    R = 220

    def point(i, value):
        angle = -math.pi / 2 + i * 2 * math.pi / n
        r = R * ((value or 0) / SCALE)
        return cx + r * math.cos(angle), cy + r * math.sin(angle)

    def axis_end(i):
        angle = -math.pi / 2 + i * 2 * math.pi / n
        return cx + R * math.cos(angle), cy + R * math.sin(angle)

    def label_point(i, offset=55):
        angle = -math.pi / 2 + i * 2 * math.pi / n
        return cx + (R + offset) * math.cos(angle), cy + (R + offset) * math.sin(angle)

    svg = []
    svg.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '  # genericity: ok - XML namespace of the SVG format, not an audited domain
        f'viewBox="0 0 {width} {height}" font-family="sans-serif">'
    )
    # Hatch pattern: no opaque background, otherwise the declared layer would hide
    # the grid and the axes it covers.
    svg.append(
        f'<defs><pattern id="{HACHURE_ID}" width="9" height="9" '
        f'patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
        f'<line x1="0" y1="0" x2="0" y2="9" stroke="{NAVY}" stroke-width="2.5"/>'
        f'</pattern></defs>'
    )
    svg.append(f'<rect width="{width}" height="{height}" fill="white"/>')
    svg.append(
        f'<text x="{width/2:.1f}" y="30" text-anchor="middle" font-size="18" '
        f'font-weight="bold">{escape(title)}</text>'
    )

    # grid = true circles (not hexagons)
    #
    # The graduations are set aside and rendered AFTER the polygons, with a white
    # halo. They are placed on the vertical axis, at the exact spot where the
    # polygon passes: drawn before, the solid layer would cover them. stroke-width
    # must stay thin (1.5): at 3, the halo of a digit like "25 %" becomes a solid
    # block that swallows the text instead of underlining it (seen on the demo
    # rendering, where the "2" disappeared and the graduation read "5 %").
    graduations = []
    for ring in (25, 50, 75, 100):
        color = "#333" if ring == 100 else "#ccc"
        svg.append(
            f'<circle cx="{cx}" cy="{cy}" r="{R*ring/SCALE:.1f}" fill="none" '
            f'stroke="{color}" stroke-width="1"/>'
        )
        lx, ly = cx, cy - R * ring / SCALE
        graduations.append(
            f'<text x="{lx+6:.1f}" y="{ly-4:.1f}" font-size="12" fill="#000" '
            f'paint-order="stroke" stroke="white" stroke-width="1.5">{ring} %</text>'
        )

    # axes = straight lines from the center to the edge
    for i in range(n):
        ex, ey = axis_end(i)
        svg.append(f'<line x1="{cx}" y1="{cy}" x2="{ex:.1f}" y2="{ey:.1f}" stroke="#999" stroke-width="1"/>')

    # Label block of each axis: the name, the value, then the number of criteria
    # filled in.
    #
    # ⚠️ The value is written HERE and not next to its point on the polygon, against
    # the usual radar practice, and it is deliberate. On a real audit, four dimensions
    # out of six were worth almost zero: their four numbers piled up at the
    # center, on top of the markers of the dimensions with no answer, unreadable.
    # Pushing them out to a minimum radius would have been worse: a "0.0 %" placed
    # beyond the 25% circle reads as 28%. The label block, however, is always outside
    # the grid and its axis is named just above: no ambiguity possible.
    #
    # The third line is what prevents reading a 0% axis as an exemplary axis:
    # it says how many criteria actually answered.
    for i, (name, val) in enumerate(axes):
        lx, ly = label_point(i)
        anchor = "middle"
        if lx < cx - 10:
            anchor = "end"
        elif lx > cx + 10:
            anchor = "start"
        svg.append(
            f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}" font-size="14" '
            f'font-weight="bold" fill="#222">{escape(name)}</text>'
        )
        if val is None:
            # Distinguish out of scope (a dimension that does not concern this service)
            # from an absence of an answer (a dimension we failed to assess).
            # The report is read aloud by a speech synthesis, which spells out
            # acronyms, hence "no answer" rather than "N/A". An absence of an answer
            # is never assimilated to 0%, which would mean "confirmed strength
            # everywhere".
            out_of_scope = axes_out_of_scope and i < len(axes_out_of_scope) and axes_out_of_scope[i]
            label = "out of scope" if out_of_scope else "no answer"
            svg.append(
                f'<text x="{lx:.1f}" y="{ly + 18:.1f}" text-anchor="{anchor}" font-size="13" '
                f'font-weight="bold" fill="{GREY}">{escape(label)}</text>'
            )
        else:
            svg.append(
                f'<text x="{lx:.1f}" y="{ly + 18:.1f}" text-anchor="{anchor}" font-size="13" '
                f'font-weight="bold" fill="{NAVY}">{escape(_pct(val))} of potential</text>'
            )
        if axes_answered is not None:
            answered, total = axes_answered[i]
            # For an out-of-scope axis, display the number of excluded criteria
            # instead of the "out of 0" count, which means nothing to a reader.
            out_of_scope = axes_out_of_scope and i < len(axes_out_of_scope) and axes_out_of_scope[i]
            if out_of_scope and axes_discarded is not None and i < len(axes_discarded):
                excluded_count = axes_discarded[i]
                excluded_text = f"{excluded_count} criterion excluded" if excluded_count == 1 else f"{excluded_count} criteria excluded"
                svg.append(
                    f'<text x="{lx:.1f}" y="{ly + 34:.1f}" text-anchor="{anchor}" font-size="12" '
                    f'fill="{GREY}">{excluded_text}</text>'
                )
            else:
                # "filled in" placed right after "criteria", not after the total: the
                # first wording tried, "1 criterion out of 5 filled in", suggested
                # that it was the 5 that was filled in.
                svg.append(
                    f'<text x="{lx:.1f}" y="{ly + 34:.1f}" text-anchor="{anchor}" font-size="12" '
                    f'fill="{GREY}">{_decompte_criteres(answered, total)}</text>'
                )

    # Data polygons (straight lines between points, like the source Sheet).
    # The hatched layer first, the solid one on top: in the other order the
    # hatching would cover the solid layer and the two would blend together.
    def polygone(values, fill, fill_opacity=None, stroke_dash=None, stroke=NAVY):
        pts = [point(i, v) for i, v in enumerate(values)]
        pts_str = " ".join(f"{p[0]:.1f},{p[1]:.1f}" for p in pts)
        opacity = f' fill-opacity="{fill_opacity}"' if fill_opacity else ""
        dash = f' stroke-dasharray="{stroke_dash}"' if stroke_dash else ""
        stroke_attr = f' stroke="{stroke}" stroke-width="2.5"' if stroke else ""
        return f'<polygon points="{pts_str}" fill="{fill}"{opacity}{stroke_attr}{dash}/>'

    def anneau_hachure(outer_values, inner_values):
        # Path with two sub-paths + fill-rule evenodd: the inner sub-path
        # becomes a hole in the fill of the outer one. Fixes a bug observed
        # on 2026-09-11: drawing the hatched area over the WHOLE surface of the total, then the
        # solid layer on top semi-transparent (fill-opacity 0.40), left the
        # hatch texture visible THROUGH TRANSPARENCY even when established == total (zero uncertainty
        # margin) — an axis with no margin at all looked like it had one.
        # The technique works because each axis is a radius from the center:
        # the inside is always <= the outside on that same radius, so it is entirely
        # contained within it, whatever the 6 axes.
        pts_ext = [point(i, v) for i, v in enumerate(outer_values)]
        pts_int = [point(i, v) for i, v in enumerate(inner_values)]
        d_ext = "M" + " L".join(f"{p[0]:.1f},{p[1]:.1f}" for p in pts_ext) + " Z"
        d_int = "M" + " L".join(f"{p[0]:.1f},{p[1]:.1f}" for p in pts_int) + " Z"
        return f'<path d="{d_ext} {d_int}" fill="url(#{HACHURE_ID})" fill-rule="evenodd" stroke="none"/>'

    total_values = [val for _, val in axes]
    if axes_set is None:
        svg.append(polygone(total_values, NAVY, fill_opacity="0.40"))
    else:
        svg.append(polygone(total_values, "none", stroke_dash="7 4"))
        svg.append(anneau_hachure(total_values, axes_set))
        svg.append(polygone(axes_set, NAVY, fill_opacity="0.40"))

    svg.extend(graduations)

    # Markers on the axes. No text here: all numbers are in the label
    # blocks, outside the grid.
    for i, (name, val) in enumerate(axes):
        p = point(i, val)
        if val is None:
            # No answer or out of scope: grey ring at the center. The
            # dimension is still drawn, but muted. The label block
            # distinguishes the two cases.
            out_of_scope = axes_out_of_scope and i < len(axes_out_of_scope) and axes_out_of_scope[i]
            tooltip = f"{name}: out of scope, does not concern this service" if out_of_scope else f"{name}: no answer, this is not a 0%"
            svg.append(
                f'<circle cx="{p[0]:.1f}" cy="{p[1]:.1f}" r="5" fill="white" '
                f'stroke="{GREY}" stroke-width="2"><title>'
                f'{escape(tooltip)}</title></circle>'
            )
            continue
        svg.append(
            f'<circle cx="{p[0]:.1f}" cy="{p[1]:.1f}" r="6" fill="{NAVY}" stroke="white" '
            f'stroke-width="1.5"><title>{escape(name)} : {escape(_pct(val))} '
            f'of optimization potential</title></circle>'
        )
        # Solid layer: a hollow ring where it stops on this axis. Its
        # value is NOT written on the image, it is carried by a <title>,
        # which the browser shows on hover and a screen reader announces.
        #
        # Two placements of the number were tried and rejected after looking
        # at the image: next to the ring, the axes where nothing is established all
        # pinch at the center and their numbers pile up there on top of the
        # "N/A" marker; under the total's value, the number falls back on the edge
        # of the oblique axes' polygon. The numeric value of each layer is
        # anyway in eof-filled.md and in the report: on the radar, what
        # must be seen is the gap between the two layers, and it is seen.
        if axes_set is not None and axes_set[i] is not None and axes_set[i] < val:
            pe = point(i, axes_set[i])
            tooltip = (
                f"{name}: {_pct(val)} of optimization potential in total, "
                f"of which {_pct(val - axes_set[i])} of uncertainty margin "
                f"(inference from a weak signal)"
            )
            svg.append(
                f'<circle cx="{pe[0]:.1f}" cy="{pe[1]:.1f}" r="4.5" fill="white" '
                f'stroke="{NAVY}" stroke-width="2"><title>{escape(tooltip)}</title></circle>'
            )

    # Legend at the top left: the corner is free, and the caption is already
    # busy. Two lines rather than one: the labels exceed 40 characters and
    # side by side they would reach the top axis's label.
    if axes_set is not None:
        # The case where no answer rests on `assumed` is a HEALTHY case (not
        # rare as before 2026-09-11): the two layers overlap and the
        # uncertainty margin is invisible. Say it, rather than displaying a
        # legend for an absent layer: without this note, the reader looks
        # for hatching that does not exist and doubts the figure.
        rien_de_declare = all(
            e == t for e, (_, t) in zip(axes_set, axes)
        )
        margin_label = "hatched: uncertainty margin (inference from a weak signal)"
        if rien_de_declare:
            margin_label = "hatched: uncertainty margin (none to date)"
        for k, (fill, opacity, label) in enumerate([
            (NAVY, ' fill-opacity="0.40"', "solid: retained potential (measured, inferred, or indicated by the service)"),
            (f"url(#{HACHURE_ID})", "", margin_label),
        ]):
            y = 46 + k * 22
            svg.append(
                f'<rect x="24" y="{y}" width="16" height="14" fill="{fill}"{opacity} '
                f'stroke="{NAVY}" stroke-width="1.5"/>'
            )
            svg.append(
                f'<text x="48" y="{y + 12}" font-size="12" fill="#222">{escape(label)}</text>'
            )

    # Caption: gauge of what is filled in, then count by provenance,
    # then the note. The gauge is there so that a low potential does not read as
    # a mature service when it only says "we have hardly looked at anything".
    if coverage is not None:
        # Accept old format (3 elements) and new format (4 elements with excluded)
        if len(coverage) == 4:
            pct, answered, total, excluded = coverage
        else:
            pct, answered, total = coverage
            excluded = None
        bar_w, bar_h, bar_y = 560, 14, 708
        bar_x = (width - bar_w) / 2
        excluded_txt = ""
        if excluded is not None and excluded > 0:
            excluded_txt = f', {excluded} excluded'
        # The denameinator changes depending on whether there are excluded criteria.
        # Without excluded: "of the framework's maximum potential" (the denameinator
        # is indeed the complete framework). With excluded: "of the retained potential"
        # (the excluded are removed from the denameinator).
        denameinator_label = "of the retained potential" if (excluded is not None and excluded > 0) else "of the framework's maximum potential"
        svg.append(
            f'<text x="{width/2:.1f}" y="700" text-anchor="middle" font-size="12" fill="#222">'
            f'Filled in to date: {escape(_pct(pct, 0))} {denameinator_label} '
            f'({answered} criteria out of {total}{excluded_txt})</text>'
        )
        svg.append(
            f'<rect x="{bar_x:.1f}" y="{bar_y}" width="{bar_w}" height="{bar_h}" '
            f'fill="#EEE" stroke="{GREY}" stroke-width="1"/>'
        )
        filled = bar_w * max(0.0, min(100.0, pct)) / 100
        if filled > 0:
            svg.append(
                f'<rect x="{bar_x:.1f}" y="{bar_y}" width="{filled:.1f}" height="{bar_h}" '
                f'fill="{NAVY}"/>'
            )

    if provenances is not None:
        detail = ", ".join(
            f"{LIBELLES_PROVENANCE.get(p, p)} {provenances.get(p, 0)}"
            for p in ("collected", "estimated", "declared", "stated", "assumed")
        )
        svg.append(
            f'<text x="{width/2:.1f}" y="748" text-anchor="middle" font-size="12" '
            f'fill="{GREY}">Provenance of answers: {escape(detail)}</text>'
        )

    if note:
        # Split the note into lines if it is too long. A short note
        # (that fits on one line) is not modified, which preserves
        # non-regression on existing radars.
        note_lines = _wrap_text(note)
        line_height = 18
        # Place the lines after the provenance line (y=748) or at the
        # standard position (height - 22 = 770) if a single line. Line height of 18 pixels.
        if len(note_lines) == 1:
            # Short note: standard position, unchanged
            y_start = height - 22
        else:
            # Long note: start at y=766 (after provenance at 748 + 18)
            # and increase the canvas height if needed so everything fits.
            y_start = 766
        for i, line in enumerate(note_lines):
            y = y_start + i * line_height
            svg.append(
                f'<text x="{width/2:.1f}" y="{y}" text-anchor="middle" font-size="12" '
                f'fill="#666">{escape(line)}</text>'
            )

    svg.append("</svg>")
    return "\n".join(svg)


def _est_critere_ecarte(criterion):
    """Returns true if the criterion is excluded (out of scope).

    A criterion is excluded when it does not apply to the audited service. Two
    paths lead to the same state, as established in session 26 convention:
    - its `answer` is `🚫 Not applicable`;
    - or its `not_applicable` boolean is true.
    """
    return criterion.get("answer") == "🚫 Not applicable" or criterion.get("not_applicable") is True


def build_radar_from_results(audit_results, domain=None, title=None, note=None):
    """Builds the two-layer radar from a loaded `eof-audit-results.json`.

    SINGLE entry point of the two producers of the results file
    (`run_eof.py` and `process/merge_lots.py`). They already have two
    twin arithmetics to keep aligned; leaving them two ways of
    drawing the radar as well guaranteed that one day one of the two would
    show something different from the other on the same data.

    The solid layer is NOT recomputed from a homemade denameinator: it is
    taken as the share of the already displayed potential that comes from our own
    provenances. The producer remains sole master of its denameinator, and since
    session 26 the two producers treat excluded criteria the same
    way. The solid layer cannot come out of the hatched layer.
    """
    dimensions = audit_results.get("dimensions") or []
    criteria = audit_results.get("criteria") or []
    dimension_names = [d.get("name") for d in dimensions]

    # Retained potential per dimension, split by the origin of the answer.
    retained = {name: {"set": 0.0, "total": 0.0} for name in dimension_names}
    max_potential_per_dimension = {name: {"answered": 0.0, "total": 0.0} for name in dimension_names}
    for c in criteria:
        name = c.get("dimension")
        if name not in retained:
            # The quick-diagnostic questions belong to none of the 6
            # detailed dimensions and have no potential: they count
            # neither in the radar nor in the gauge.
            continue
        # An excluded criterion leaves all denameinators and counts in
        # no numerator. It is neither a success nor a miss.
        if _est_critere_ecarte(c):
            continue
        max_pot = c.get("max_potential") or 0.0
        max_potential_per_dimension[name]["total"] += max_pot
        if c.get("answer") is None:
            continue
        max_potential_per_dimension[name]["answered"] += max_pot
        coefficient = c.get("coefficient") or 0.0
        retained[name]["total"] += coefficient * max_pot
        if c.get("provenance") in PROVENANCES_RETENUES:
            retained[name]["set"] += coefficient * max_pot

    axes = []
    axes_set = []
    axes_answered = []
    axes_out_of_scope = []
    axes_discarded = []
    for d in dimensions:
        name = d.get("name")
        total_pct = d.get("optimization_potential_pct")
        out_of_scope = d.get("out_of_scope", False)
        axes.append((name, total_pct))
        axes_out_of_scope.append(out_of_scope)
        axes_discarded.append(d.get("discarded") or 0)
        if total_pct is None:
            axes_set.append(None)
        elif retained[name]["total"] > 0:
            axes_set.append(total_pct * retained[name]["set"] / retained[name]["total"])
        else:
            # Everything that answered carries a zero coefficient: the displayed potential
            # is 0, the two layers merge at the center.
            axes_set.append(total_pct)
        axes_answered.append((d.get("answered") or 0, d.get("total") or 0))

    # Gauge: share of the framework's maximum potential already filled in. Weighted
    # by `potential_max`, as the manifest requires: a criterion at 2.0 that
    # is missing does not leave the same hole as a criterion at 0.5. An excluded criterion
    # (answered "not applicable" or not_applicable=true) leaves the denameinator and
    # counts in no numerator: it is neither a success nor a miss.
    pmax_total = sum(v["total"] for v in max_potential_per_dimension.values())
    pmax_answered = sum(v["answered"] for v in max_potential_per_dimension.values())
    coverage = None
    excluded_criteria = audit_results.get("discarded_criteria")
    if pmax_total > 0:
        dimension_criteria = [
            c for c in criteria
            if c.get("dimension") in retained and not _est_critere_ecarte(c)
        ]
        coverage = (
            pmax_answered / pmax_total * 100,
            sum(1 for c in dimension_criteria if c.get("answer") is not None),
            len(dimension_criteria),
            excluded_criteria,
        )

    if title is None:
        domain_text = domain or audit_results.get("domain") or "audited service"
        title = f"EOF: optimization potential ({domain_text})"
    if note is None:
        note = (
            "The outer edge of each axis gives the global estimate of the optimization "
            "potential (solid and hatched added together). "
            "A dimension whose criteria all have no answer is marked \"no answer\", "
            "never 0%: a 0% would mean confirmed strength across the whole dimension."
        )
        # Add an explanation of "out of scope" if at least one axis is.
        if any(axes_out_of_scope):
            note += (
                " An out-of-scope dimension is a dimension we know "
                "does not concern this service, while a dimension with no answer "
                "is a dimension we failed to assess."
            )

    return radar_svg(
        axes,
        title=title,
        note=note,
        axes_set=axes_set,
        axes_answered=axes_answered,
        axes_out_of_scope=axes_out_of_scope,
        axes_discarded=axes_discarded,
        coverage=coverage,
        provenances=audit_results.get("answered_by_provenance"),
    )


def _demo(output_path):
    """Demo radar: the full rendering, including the rare case.

    The values are fictitious, but each percentage is checked against the
    reference framework's real weights (`eof-reference.json`): a percentage can
    never exceed what the number of answered criteria can carry at
    maximum (canonical formula, `run_eof.py::compute_dimension_scores` —
    sum of the `coefficient × potential_max` of answered criteria ÷ sum of the
    `potential_max` of ALL the retained criteria of the dimension, answered or
    not). Example: Storage & Data weighs 8.0 in total over 6 criteria; the
    2 best-weighted ones weigh only 3.0 together → the maximum reachable with
    2 answered is 3.0 / 8.0 = 37.5%, never 85% (value found in an earlier
    version of this demo, corrected on 2026-09-15 — Architecture
    showed the same defect: 70% announced for a real maximum of 62.5%
    with 3 answered out of 5).

    Since 2026-09-11 (cf. PROVENANCES_RETENUES / PROVENANCES_MARGE_INCERTITUDE
    above), the hatched layer only carries the `assumed` provenance:
    in a normal audit, it stays a minority against the solid layer, because `assumed`
    is the most fragile and least frequent provenance. The values
    below illustrate, in axis order:

      - Product                : no assumption (zero margin);
      - Architecture            : common case, a small minority margin;
      - Infrastructure          : common case, minority margin too;
      - Storage & Data      : non-negligible margin in absolute value,
                                   but always a minority compared to the solid layer;
      - Algo & Code             : RARE and deliberately extreme case where the margin
                                   exceeds the solid layer (a lot of `assumed`), kept
                                   to check that the rendering stays readable even
                                   in this unfavorable case — do not read it as
                                   a representative situation;
      - Ease of change: common case, same profile as Architecture/
                                   Infrastructure (the "no answer" case is
                                   illustrated separately, see `_demo_comparaison`).
    """
    totals = [35, 55, 15, 30, 50, 25]
    established = [35, 48, 12, 25, 10, 22]
    answered_counts = [(16, 16), (3, 5), (8, 8), (2, 6), (5, 9), (4, 10)]
    svg_text = radar_svg(
        list(zip(AXES_EOF, totals)),
        title="EROOM radar: full test (6 axes, fictitious values)",
        note=(
            "The outer edge of each axis gives the global estimate of the optimization "
            "potential (solid and hatched added together). Fictitious values, only "
            "to validate the visual rendering."
        ),
        axes_set=established,
        axes_answered=answered_counts,
        coverage=(34.0, 38, 54),
        provenances={"collected": 16, "estimated": 6, "declared": 9, "stated": 1, "assumed": 6},
    )
    with open(output_path, "w") as f:
        f.write(svg_text)
    print(f"Demo SVG written: {output_path}")


def _demo_comparaison(output_path):
    """Demo radar: "no answer" vs "out of scope".

    Reuses the same axes as `_demo`, corrected on 2026-09-15, except two:

      - Storage & Data      : here OUT OF SCOPE (the 6 criteria of the
                                   dimension are excluded, `axes_out_of_scope`);
      - Ease of change: here NO ANSWER (0 criteria answered out of 10),
                                   unlike `_demo` where this axis now
                                   carries a real value (25%, 4/10) —
                                   deliberately different, to isolate the
                                   "no answer" case on a dedicated axis rather than
                                   pretending to reuse "the same empty axis of the
                                   reference radar" (false claim in
                                   the previous version: Storage & Data
                                   was never empty there, it already carried 2
                                   answered criteria).
    """
    totals = [35, 55, 15, None, 50, None]
    established = [35, 48, 12, None, 10, None]
    answered_counts = [(16, 16), (3, 5), (8, 8), (0, 6), (5, 9), (0, 10)]
    svg_text = radar_svg(
        list(zip(AXES_EOF, totals)),
        title="EROOM radar: no answer vs out of scope (fictitious values)",
        note=(
            "Two different ways of not filling an axis: \"Storage & Data\" "
            "is out of scope (the 6 criteria are excluded, the dimension does "
            "not concern this service), \"Ease of change\" stays with no answer (we "
            "failed to assess it). The other axes reuse the "
            "corrected values of the reference radar. Fictitious values, only to "
            "compare the visual rendering."
        ),
        axes_set=established,
        axes_answered=answered_counts,
        axes_out_of_scope=[False, False, False, True, False, False],
        axes_discarded=[None, None, None, 6, None, None],
        # Storage & Data is out of scope: its 6 criteria (potential_max
        # total 8.0) leave the denameinator, as the real calculation
        # would do (`criteria_des_dimensions` excludes an excluded dimension as a block in
        # `run_eof.py`). Hence 48 criteria (54 - 6) and a percentage different
        # from `_demo` (29.1% here vs 34.0% on the reference side): the
        # two gauges are NOT comparable term by term, only the
        # radar figure is, axis by axis.
        coverage=(29.1, 32, 48),
        provenances={"collected": 13, "estimated": 6, "declared": 8, "stated": 1, "assumed": 4},
    )
    with open(output_path, "w") as f:
        f.write(svg_text)
    print(f"Demo SVG (comparison) written: {output_path}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 generate_radar_svg.py <output_file.svg>")
        sys.exit(1)
    if sys.argv[1].startswith("-"):
        print("Usage: python3 generate_radar_svg.py <output_file.svg>")
        sys.exit(1)
    _demo(sys.argv[1])
