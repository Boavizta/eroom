#!/usr/bin/env python3
"""
Sizing report (Lot 6): compares, server by server, the REAL demand
(raw_nb_of_instances, fractional) to the number of instances actually
BILLED (nb_of_instances, rounded according to the sizing mode).

WHAT THIS REPORT MEASURES, AND WHAT IT DOES NOT MEASURE
-------------------------------------------------------
The billed/real ratio MAY look like a client over-sizing indicator, but that
is NOT what it measures here: the annual traffic is spread as a UNIFORM
timeseries over 24 h (build.py:_hourly_volume), never over the site's real
hourly profile. A uniform traffic smooths out the peaks that a real traffic
would concentrate on a few hours, which ARTIFICIALLY MINIMIZES the measured
gap. NEVER present this number as a measurement of a client's real
over-sizing (cf. handoff of 06/08/2026, plan H, Lot 6).

For now it is only an INTERNAL diagnostic (written into the JSON, not yet
rendered in the HTML report): the display decision belongs to Lot 9, which
will have to carry the warning above if it chooses to show it.

NO EFOOTPRINT IMPORT HERE
-------------------------
This module only reads attributes already computed by `build_system()`
(build.py): `raw_nb_of_instances`/`nb_of_instances`, already numpy arrays
via `.magnitude`. Like `ranges.py`, it therefore does not need to be exempted
from the `check_no_efootprint_import()` check.
"""

import numpy as np


def server_sizing(key, server, server_spec):
    """Sizing of a single built server.

    `server_spec` may be None (defensive) if the key is no longer aligned with
    `built.spec.servers`; the report then falls back to the technical key as
    label rather than failing.

    A server with no transferred byte at all (e.g. a host observed only on
    0-byte requests) can make `.magnitude` degenerate to a scalar rather
    than a numpy array: `np.atleast_1d` uniformizes both cases without
    changing the result for an already-normal array.
    """
    raw = np.atleast_1d(server.raw_nb_of_instances.magnitude)
    billed = np.atleast_1d(server.nb_of_instances.magnitude)

    real_instance_hours = float(raw.sum())
    billed_instance_hours = float(billed.sum())
    oversizing_ratio = (billed_instance_hours / real_instance_hours
                         if real_instance_hours > 0 else None)

    return {
        "key": key,
        "label": server_spec.label if server_spec else key,
        "server_type": server.server_type.value,
        "real_instance_hours": round(real_instance_hours, 4),
        "billed_instance_hours": round(billed_instance_hours, 4),
        "oversizing_ratio": round(oversizing_ratio, 4) if oversizing_ratio is not None else None,
        "peak_real_instances": round(float(raw.max()), 4),
        "peak_billed_instances": round(float(billed.max()), 4),
    }


def servers_sizing(built):
    """Sizing of all the servers of a `BuiltModel` (build.py)."""
    server_specs = {s.key: s for s in built.spec.servers}
    return [
        server_sizing(key, server, server_specs.get(key))
        for key, server in built.servers_by_key.items()
    ]
