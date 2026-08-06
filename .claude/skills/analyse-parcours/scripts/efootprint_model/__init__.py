"""Bibliothèque de modélisation e-footprint : spécifications déclaratives.

CE QUE CE PAQUET EST
--------------------
Une description INERTE d'un service web, en Python pur. Aucune classe
e-footprint n'est instanciée ici. On décrit des serveurs, des traitements, des
étapes de parcours et une audience ; la construction du modèle e-footprint
proprement dit viendra plus tard, dans un module séparé.

POURQUOI CETTE SÉPARATION
-------------------------
1. La spécification est testable SANS e-footprint installé et sans réseau.
2. La même spécification peut produire DEUX modèles indépendants (référence et
   scénario de réduction), ce qui est impossible si on instancie tout de suite :
   les objets e-footprint portent des caches et des références croisées qui ne
   se recopient pas de façon fiable.
3. Les archétypes deviennent des TRANSFORMATIONS de spécification, donc
   composables. Deux archétypes peuvent s'appliquer au même site.

GARDE-FOU À NE PAS LEVER
------------------------
Ce fichier ne doit JAMAIS réexporter un module qui importe `efootprint`.
Sinon `import efootprint_model` cesse de fonctionner sans la librairie
installée, et le bénéfice 1 ci-dessus est perdu sans que personne ne s'en
aperçoive. Le constructeur du modèle s'importera explicitement, par son nom.
"""

from .spec import (
    CONFIDENCE_LEVELS,
    KINDS,
    AudienceSpec,
    Evidence,
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
    "compose",
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
