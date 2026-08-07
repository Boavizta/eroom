#!/usr/bin/env python3
"""
Fourchettes infrastructure et usage, calculées à partir d'une SiteSpec déjà
composée (typiquement produite par `from_har.spec_from_env_data()`).

CE QUE CE MODULE FAIT ET NE FAIT PAS
-------------------------------------
Il ne calcule PAS un troisième chiffre : il rejoue le MÊME modèle avec une
seule hypothèse changée à la fois, et lit le total avec `build_system()` /
`total_kg()` (cf. build.py). Chaque fourchette isole une incertitude RÉELLE,
jamais un cumul au pire (cf. mémoire persistante "fourchettes non cumulées") :
les deux fourchettes ne s'additionnent jamais entre elles, et le rapport doit
dire pourquoi.

POURQUOI SEULEMENT DEUX AXES, ET PAS QUATRE COMME AU 06/08/2026
------------------------------------------------------------------
Le plan initial du 06/08/2026 bornait aussi le nombre de serveurs 1st-party et
le stockage. Les deux ont cessé d'être des hypothèses à trancher depuis :
  - le nombre de serveurs est désormais DÉTECTÉ depuis le HAR
    (`from_har.detect_infrastructures()`, Lot 3) : c'est une mesure, plus un
    choix à arbitrer ;
  - le stockage est documenté comme une LIMITE binaire du modèle (cf. handoff
    du 06/08/2026, section C.3 : sous 1 To, e-footprint n'a aucune
    résolution), pas une fourchette exploitable.

Restent deux VRAIES incertitudes, chacune bornée par ce que la bibliothèque
calcule déjà ailleurs, jamais par un chiffre inventé ici :
  - le mode de dimensionnement du serveur (serverless <-> autoscaling) : le
    HAR ne dit pas comment le site est réellement hébergé ;
  - le temps utilisateur (Nielsen recalé <-> Nielsen BRUT) : le recalage
    dépend d'une mesure SimilarWeb qui peut manquer, ou d'un facteur mesuré
    sur un site qui peut être faux pour telle page précise (cf.
    temps_utilisateur.py).

IMPORT DE build.py, PAS D'e-footprint DIRECTEMENT
---------------------------------------------------
Ce fichier ne contient aucun `import efootprint` : il délègue tout calcul à
`build.py` (le seul module qui a besoin de la librairie). C'est pourquoi il
n'a pas besoin d'être exempté du contrôle `check_no_efootprint_import()` de
check_efootprint_spec.py, ni réexporté par `__init__.py` (même raison que
build.py, cf. sa docstring : `import efootprint_model` doit rester possible
sans la librairie installée).
"""

from dataclasses import replace

from .build import build_system, total_kg
from .spec import script_default_label
from .temps_utilisateur import step_user_time


def _variant_total_kg(spec):
    return total_kg(build_system(spec))


def infra_range_kg(spec):
    """Fourchette infrastructure : mode de dimensionnement du serveur.

    Rejoue le modèle en imposant "serverless" puis "autoscaling" à TOUS les
    serveurs du site : l'incertitude porte sur l'hébergement réel, qui est une
    décision unique pour le site, pas serveur par serveur. Retourne
    (bas, haut) en kg CO2e/an, toujours bas <= haut.
    """
    totals = []
    for server_type in ("serverless", "autoscaling"):
        servers = tuple(
            replace(server, server_type=script_default_label(
                server_type,
                "variante de fourchette infra : mode de dimensionnement forcé à "
                f"\"{server_type}\" pour mesurer sa sensibilité (cf. ranges.py). "
                "N'est jamais le mode réellement utilisé pour l'estimation centrale."))
            for server in spec.servers
        )
        totals.append(_variant_total_kg(replace(spec, servers=servers)))
    return min(totals), max(totals)


def usage_range_kg(spec):
    """Fourchette usage : temps de lecture Nielsen, recalé ou BRUT.

    La borne basse est le total ACTUEL de la spec (temps recalé quand un
    recalage est possible, cf. temps_utilisateur.py — c'est aussi
    l'estimation centrale publiée). La borne haute force le temps Nielsen
    BRUT (sans recalage) sur toutes les étapes dont le comptage de mots est
    connu ; les étapes sans comptage de mots (repli Lot 3) ne varient pas,
    cette incertitude ne les concerne pas.

    Si aucune étape n'a de recalage disponible (ex. cas ANTS, SimilarWeb ne
    couvre pas le domaine), la borne haute est identique à la basse : le
    temps BRUT est déjà ce qui est utilisé, il n'y a alors rien à encadrer.
    Ce n'est pas un bug, c'est une fourchette qui se referme faute
    d'incertitude à montrer.
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
    """Les deux fourchettes en un seul appel, plus l'estimation centrale.

    Ne les cumule JAMAIS entre elles (cf. docstring du module) : le rapport
    doit les présenter séparément, avec l'explication de pourquoi.
    """
    return {
        "central_kg": _variant_total_kg(spec),
        "infra_range_kg": infra_range_kg(spec),
        "usage_range_kg": usage_range_kg(spec),
    }
