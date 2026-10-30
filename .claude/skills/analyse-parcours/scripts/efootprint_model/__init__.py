"""e-footprint modeling library: declarative specifications.

WHAT THIS PACKAGE IS
--------------------
An INERT description of a web service, in pure Python. No e-footprint
class is instantiated here. We describe servers, jobs, journey steps and
an audience; building the actual e-footprint model comes later, in a
separate module.

WHY THIS SEPARATION
--------------------
1. The specification is testable WITHOUT e-footprint installed and without
   network access.
2. The same specification can produce TWO independent models (reference and
   reduction scenario), which is impossible if we instantiate right away:
   e-footprint objects carry caches and cross-references that do not copy
   reliably.
3. Archetypes become specification TRANSFORMATIONS, hence composable. Two
   archetypes can apply to the same site.

GUARD-RAIL NOT TO LIFT
----------------------
This file must NEVER re-export a module that imports `efootprint`.
Otherwise `import efootprint_model` stops working without the library
installed, and benefit 1 above is lost without anyone noticing. The model
builder will be imported explicitly, by name.
"""

from .spec import (
    CONFIDENCE_LEVELS,
    KINDS,
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
    assumed,
    estimated,
    library_default,
    measured,
    script_default,
)
from .compose import (
    RESERVE_ARBITRATIONS,
    RESERVE_CODES,
    arbitrations_for,
    calculation_reserves,
    collect_sources,
    compose,
    iter_traced,
    orphan_steps,
    primary_server,
    require_calculable,
    unused_jobs,
    validate_spec,
)

__all__ = [
    "CONFIDENCE_LEVELS",
    "KINDS",
    "RESERVE_ARBITRATIONS",
    "RESERVE_CODES",
    "AudienceSpec",
    "Evidence",
    "ExternalApiSpec",
    "JobSpec",
    "JourneySpec",
    "ServerSpec",
    "SiteSpec",
    "SpecError",
    "StepSpec",
    "ThirdPartyHost",
    "Traced",
    "arbitrations_for",
    "assumed",
    "calculation_reserves",
    "collect_sources",
    "composite",
    "estimated",
    "iter_traced",
    "library_default",
    "measured",
    "orphan_steps",
    "primary_server",
    "require_calculable",
    "script_default",
    "unused_jobs",
    "validate_spec",
]
