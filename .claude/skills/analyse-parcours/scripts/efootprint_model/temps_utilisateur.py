#!/usr/bin/env python3
"""
Temps utilisateur par étape : Nielsen 2008, recalé sur une mesure du site.

ZÉRO import e-footprint ici non plus : ce module ne fait que du calcul, il
retourne des `Traced` (cf. spec.py), jamais un objet e-footprint.

LA FORMULE, VÉRIFIÉE À LA SOURCE (05 et 07/08/2026)
----------------------------------------------------
Nielsen, "How Little Do Users Read?", Nielsen Norman Group, 5 mai 2008 :
    "a fixed time of about 25 seconds, plus an additional 4.4 seconds
    per 100 words"
Domaine de validité publié : "30 and 1,250 words" ; au-delà, l'article dit
que "reading became quite erratic".
URL : https://www.nngroup.com/articles/how-little-do-users-read/

Étude sous-jacente, dont la formule est un ajustement statistique : Weinreich,
Obendorf, Herder & Mayer, "Not Quite the Average: An Empirical Study of Web
Use", ACM Transactions on the Web 2(1), art. 5, février 2008. 25 personnes
instrumentées en usage NORMAL, 59 573 pages vues au départ, 45 237 après
filtrage. FAIBLESSE À ÉCRIRE DANS LE RAPPORT : données de 2005, avant le
smartphone (iPhone 2007).

POURQUOI LE RECALAGE COMPARE DEUX MOYENNES, JAMAIS UN POINT À UNE MOYENNE
---------------------------------------------------------------------------
SimilarWeb ne renvoie qu'un agrégat par site (TimeOnSite / PagePerVisit,
toutes pages et toutes visites confondues), jamais un temps par page. Pour lui
trouver un vis-à-vis Nielsen cohérent, il faut donc aussi une moyenne de
pages, pas une seule page. Vérifié à la source le 07/08/2026 (p. 5:19 de
Weinreich et al.) : "these results are based on nearly 60,000 first-page
visits [...] the average number of words per page [...] was 551 words" —
l'étude elle-même calcule le temps de lecture PAR PAGE VUE INDIVIDUELLE,
jamais par session ni par site, puis en tire des moyennes. Comparer
moyenne(Nielsen brut des pages du parcours) à la moyenne SimilarWeb est donc
la seule correspondance méthodologique défendable ; comparer la seule page
d'accueil (fait sur le premier site testé, à une seule étape) ne l'est plus
dès qu'un parcours a plusieurs étapes.

RÉSERVE À RÉPÉTER DANS LE RAPPORT, quelle que soit la voie retenue :
- le facteur de recalage est calculé sur UN SEUL site, non générique
  (cf. check_genericite.py : 0,41 est une valeur interdite dans ce fichier) ;
- le parcours capturé n'est qu'un sous-ensemble des pages que SimilarWeb
  moyenne sur le site ENTIER.

DEUX DÉGRADATIONS DE CONFIANCE, ÉCRITES, JAMAIS SILENCIEUSES
--------------------------------------------------------------
1. Page hors du domaine de validité Nielsen (30-1250 mots) : la formule est
   appliquée quand même (mieux qu'une absence de chiffre), mais la confiance
   descend et le motif est écrit dans le commentaire du `Traced`.
2. Aucune mesure SimilarWeb disponible pour recaler (site ignoré par
   SimilarWeb, intranet, Engagments absent) : le temps Nielsen BRUT est
   utilisé, confiance dégradée, motif écrit (le brut est structurellement
   surestimé pour un site avec un usage mobile important, cf. C.6 du plan).
"""

from .spec import assumed, estimated

_SOURCE_NAME = "Nielsen 2008 (nngroup.com), formule ajustée sur Weinreich et al. 2008 (ACM ToWeb)"  # genericite: ok - source universelle de la methode, pas un cas d'audit
_SOURCE_URL = "https://www.nngroup.com/articles/how-little-do-users-read/"  # genericite: ok - source universelle de la methode, pas un cas d'audit

NIELSEN_BASE_SECONDS = 25.0
NIELSEN_SECONDS_PER_100_WORDS = 4.4
NIELSEN_DOMAIN_MIN_WORDS = 30.0
NIELSEN_DOMAIN_MAX_WORDS = 1250.0


def nielsen_raw_seconds(word_count):
    """Temps de lecture brut, formule Nielsen 2008 : 25 s + 4,4 s / 100 mots.

    Pure fonction de `word_count`, sans provenance : c'est aux appelants
    (`step_user_time`) d'envelopper le résultat dans un `Traced`, une fois
    qu'ils savent si le domaine de validité et le recalage s'appliquent.
    """
    return NIELSEN_BASE_SECONDS + NIELSEN_SECONDS_PER_100_WORDS * (word_count / 100.0)


def is_within_nielsen_domain(word_count):
    """Le comptage de mots tombe-t-il dans le domaine publié (30-1250) ?"""
    return NIELSEN_DOMAIN_MIN_WORDS <= word_count <= NIELSEN_DOMAIN_MAX_WORDS


def recalibration_factor(avg_time_on_page_s, nielsen_raw_seconds_by_step):
    """Facteur de recalage : temps moyen mesuré (SimilarWeb) / moyenne des
    Nielsen bruts des pages du parcours ayant un comptage de mots.

    avg_time_on_page_s        : TimeOnSite / PagePerVisit du bloc SimilarWeb
                                 Engagments (moyenne du site ENTIER), ou None
                                 si indisponible (cf. similarweb_api.py).
    nielsen_raw_seconds_by_step : Nielsen bruts (nielsen_raw_seconds()) des
                                 étapes du parcours ayant un comptage de mots
                                 mesuré, y compris celles hors domaine (30-1250) :
                                 le domaine de validité concerne la CONFIANCE
                                 à afficher par étape, pas l'admissibilité
                                 d'une page dans cette moyenne de référence.

    Retourne None si le recalage est IMPOSSIBLE (pas de mesure SimilarWeb, ou
    aucune page du parcours n'a de comptage de mots) : une absence de mesure,
    pas un facteur nul qui écraserait tous les temps à zéro.
    """
    if avg_time_on_page_s is None:
        return None
    raws = [r for r in nielsen_raw_seconds_by_step if r is not None]
    if not raws:
        return None
    mean_raw = sum(raws) / len(raws)
    if mean_raw <= 0:
        return None
    return avg_time_on_page_s / mean_raw


def step_user_time(word_count, factor):
    """`Traced` du temps utilisateur d'une étape, formule Nielsen + recalage.

    word_count : comptage de mots mesuré de la page (cf. from_har.py), ou None
                 si indisponible (repli Lot 3 : corps HTML non capturé). Dans
                 ce cas la fonction retourne None : c'est à l'appelant de
                 garder SON propre repli, explicite, plutôt que d'en deviner
                 un ici.
    factor      : facteur de `recalibration_factor()`, ou None si le recalage
                 est indisponible pour ce site.

    Confiance "medium" (estimated) SEULEMENT si les DEUX conditions sont
    réunies : page dans le domaine de validité ET recalage disponible. Sinon
    "low" (assumed), avec le motif écrit dans le commentaire — jamais un badge
    dégradé sans explication.
    """
    if word_count is None:
        return None

    raw = nielsen_raw_seconds(word_count)
    within_domain = is_within_nielsen_domain(word_count)
    recalibrated = factor is not None
    value = raw * factor if recalibrated else raw

    reasons = []
    if not within_domain:
        reasons.append(
            f"page hors du domaine de validité Nielsen (30 à 1250 mots ; "
            f"mesuré {word_count:.0f}) : au-delà, l'article documente une "
            "lecture \"quite erratic\", la formule est appliquée mais moins fiable."
        )
    if not recalibrated:
        reasons.append(
            "aucune mesure SimilarWeb (TimeOnSite/PagePerVisit) disponible "
            "pour ce site : temps Nielsen BRUT, non recalé, probablement "
            "SURESTIMÉ (étude sous-jacente de 2005, avant smartphone)."
        )

    base = (
        f"Nielsen 2008 : 25 s + 4,4 s/100 mots ({word_count:.0f} mots), "
        f"recalé par un facteur {factor:.3f} mesuré sur ce site (temps moyen "
        "SimilarWeb TimeOnSite/PagePerVisit divisé par la moyenne des Nielsen "
        "bruts des pages du parcours)."
        if recalibrated else
        f"Nielsen 2008 : 25 s + 4,4 s/100 mots ({word_count:.0f} mots), SANS recalage."
    )
    comment = " ".join([base] + reasons)

    factory = estimated if (within_domain and recalibrated) else assumed
    return factory(value, "s", _SOURCE_NAME, _SOURCE_URL, comment)
