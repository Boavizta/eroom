#!/usr/bin/env python3
"""
Infrastructure and usage ranges, computed from an already-composed SiteSpec
(typically produced by `from_har.spec_from_env_data()`).

WHAT THIS MODULE DOES AND DOES NOT DO
-------------------------------------
It does NOT compute a third number: it replays the SAME model with a single
hypothesis changed at a time, and reads the total with `build_system()` /
`total_kg()` (cf. build.py). Each range isolates a REAL uncertainty, never a
worst-case pile-up (cf. persistent memory "non-cumulative ranges"): the two
ranges are never added together, and the report must say why.

WHY ONLY TWO AXES, AND NOT FOUR AS ON 06/08/2026
-------------------------------------------------
The initial plan of 06/08/2026 also bounded the number of 1st-party servers
and the storage. Both stopped being hypotheses to arbitrate since then:
  - the number of servers is now DETECTED from the HAR
    (`from_har.detect_infrastructures()`, Lot 3): it is a measurement, no
    longer a choice to arbitrate;
  - storage is documented as a binary LIMIT of the model (cf. handoff of
    06/08/2026, section C.3: below 1 TB, e-footprint has no resolution), not
    a usable range.

Two REAL uncertainties remain, each bounded by what the library already
computes elsewhere, never by a number invented here:
  - the server sizing mode (serverless <-> autoscaling): the HAR does not
    say how the site is actually hosted;
  - the user time (recalibrated Nielsen <-> RAW Nielsen): the recalibration
    depends on a SimilarWeb measurement that may be missing, or on a factor
    measured on a site that may be wrong for such-and-such a precise page
    (cf. user_time.py).

IMPORT OF build.py, NOT OF e-footprint DIRECTLY
-----------------------------------------------
This file contains no `import efootprint`: it delegates all calculation to
`build.py` (the only module that needs the library). That is why it does not
need to be exempted from the `check_no_efootprint_import()` check of
check_efootprint_spec.py, nor re-exported by `__init__.py` (same reason as
build.py, cf. its docstring: `import efootprint_model` must stay possible
without the library installed).
"""

from dataclasses import replace

from .build import build_system, total_kg
from .spec import script_default_label
from .user_time import step_user_time


def _variant_total_kg(spec):
    return total_kg(build_system(spec))


def infra_range_kg(spec):
    """Infrastructure range: server sizing mode.

    Replays the model forcing "serverless" then "autoscaling" on ALL the
    site's servers: the uncertainty is about the real hosting, which is a
    single decision for the site, not server by server. Returns
    (low, high) in kg CO2e/year, always low <= high.
    """
    totals = []
    for server_type in ("serverless", "autoscaling"):
        servers = tuple(
            replace(server, server_type=script_default_label(
                server_type,
                "infra range variant: sizing mode forced to "
                f"\"{server_type}\" to measure its sensitivity (cf. ranges.py). "
                "Never the mode actually used for the central estimate."))
            for server in spec.servers
        )
        totals.append(_variant_total_kg(replace(spec, servers=servers)))
    return min(totals), max(totals)


def usage_range_kg(spec):
    """Usage range: Nielsen reading time, recalibrated or RAW.

    The low bound is the spec's CURRENT total (recalibrated time when a
    recalibration is possible, cf. user_time.py — this is also the published
    central estimate). The high bound forces the RAW Nielsen time (without
    recalibration) on all steps whose word count is known; steps without a
    word count (Lot 3 fallback) do not vary, this uncertainty does not
    concern them.

    If no step has a recalibration available (e.g. ANTS case, SimilarWeb
    does not cover the domain), the high bound is identical to the low one:
    the RAW time is already what is used, there is then nothing to bound.
    That is not a bug, it is a range closing for lack of uncertainty to show.
    """
    current_total = _variant_total_kg(spec)

    raw_steps = tuple(
        replace(step, user_time=step_user_time(step.words.value, None))
        if step.words is not None else step
        for step in spec.steps
    )
    raw_total = _variant_total_kg(replace(spec, steps=raw_steps))

    return min(current_total, raw_total), max(current_total, raw_total)


def footprint_ranges_kg(spec):
    """The two ranges in a single call, plus the central estimate.

    NEVER add them together (cf. module docstring): the report must present
    them separately, with the explanation of why.
    """
    return {
        "central_kg": _variant_total_kg(spec),
        "infra_range_kg": infra_range_kg(spec),
        "usage_range_kg": usage_range_kg(spec),
    }
