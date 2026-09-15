#!/usr/bin/env python3
"""
Simulation de l'effet cumulatif de recommandations retenues sur un `SiteSpec`.

CE QUE CE MODULE FAIT, ET NE FAIT PAS
--------------------------------------
Il calcule, pour chaque recommandation retenue (JS mort, CSS mort, ressources
en double, Brotli non activé), combien d'octets `data_transferred` seraient
retranchés d'un `JobSpec` si elle était appliquée - puis il applique ce cumul,
palier par palier, pour produire une NOUVELLE `SiteSpec`. Il ne recalcule PAS
le `System` e-footprint qui en résulte (pas de kg CO2e ici) : c'est le rôle du
code appelant, via `build_system()` sur la `SiteSpec` transformée.

ZÉRO import e-footprint ici, comme `from_har.py` et `compose.py` : ce module
ne construit que des dataclasses de `spec.py`. `archetypes/dynamique_bdd.py`
suit la même règle (`from ..spec import ...` sans jamais toucher la
bibliothèque e-footprint elle-même) ; ce module l'importe en `from .spec`
puisqu'il vit au même niveau que `spec.py`, pas dans un sous-dossier.

POURQUOI UN `Reduction` INTERMÉDIAIRE
--------------------------------------
Chaque fonction de calcul (`dead_code_reductions`, `duplicate_reductions`,
`brotli_reductions`) produit une liste de `Reduction` plutôt que de modifier
directement le `SiteSpec`. Deux raisons : `apply_recommendations()` doit
pouvoir cumuler PLUSIEURS recommandations sur le même traitement avant de
retrancher une seule fois son `data_transferred` (retrancher recommandation
par recommandation ferait dépendre le résultat de l'ordre d'application) ; et
le code appelant a besoin de la liste à plat pour exposer chaque `Traced` en
annexe du rapport, recommandation par recommandation.

TOUT CE QUI EST CALCULÉ ICI EST "ESTIMÉ", JAMAIS "MESURÉ"
-----------------------------------------------------------
Une réduction d'octets est toujours une INFÉRENCE à partir d'une donnée
collectée (un pourcentage de code mort mesuré par Coverage, une occurrence de
requête comptée dans le HAR, une recompression Brotli réelle mais partielle) :
jamais une pure hypothèse externe. D'où l'usage exclusif de `estimated()`
(cf. `spec.py`), jamais `assumed()`, dans ce module.
"""

import base64
import json
from dataclasses import dataclass, replace
from typing import Dict, List, Optional

from .spec import JobSpec, SiteSpec, Traced, estimated

# Préfixe littéral posé par `from_har.py::spec_from_env_data()` sur le label
# de chaque Job "page" (ligne 629 : `label=f"Chargement {url}"`). Les Job
# d'appel IA générative (`_ai_job_specs_for_step()`) portent un autre label
# ("Appel IA (...)") et ne sont donc jamais retenus par `_job_url()` : aucune
# des recommandations de ce module ne les concerne, ils ne portent pas de
# poids de page HTML/JS/CSS.
_CHARGEMENT_PREFIX = "Chargement "

# Les trois paliers cumulatifs acceptés par `apply_recommendations()`.
_TIER_SETS = {
    "prio1": frozenset({"prio1"}),
    "prio1_2": frozenset({"prio1", "prio2"}),
    "prio1_2_3": frozenset({"prio1", "prio2", "prio3"}),
}


@dataclass
class Reduction:
    """Une réduction d'octets calculée pour UN Job, par UNE recommandation.

    `traced` porte la provenance complète (valeur, source, confiance,
    commentaire des limites) : c'est ce que l'appelant exposera en annexe.
    Pas de champ dédupliqué ici : plusieurs `Reduction` peuvent viser le même
    `job_key` (une recommandation JS mort et une recommandation doublons sur
    le même Job, par exemple) ; le cumul est le travail d'`apply_recommendations()`.
    """

    job_key: str
    recommendation: str  # "js_dead" / "css_dead" / "duplicates" / "brotli"
    tier: str            # "prio1" / "prio2" / "prio3"
    bytes_removed: float
    traced: Traced
    page_url: Optional[str] = None
    bytes_removed_decompressed: float = 0.0
    requests_removed: int = 0


# ---------------------------------------------------------------------------
# Aides partagées : décodage du label de Job, octets réseau réels d'une entry
# ---------------------------------------------------------------------------

def _job_url(job: JobSpec) -> Optional[str]:
    """URL de page portée par ce Job, ou None si ce n'est pas un Job "page"
    (ex. un Job d'appel IA générative, cf. `_CHARGEMENT_PREFIX`)."""
    if not job.label.startswith(_CHARGEMENT_PREFIX):
        return None
    return job.label[len(_CHARGEMENT_PREFIX):]


def _url_to_job_key(site_spec: SiteSpec) -> Dict[str, str]:
    """Index URL de page -> clé du Job qui la porte, à partir des labels déjà
    posés par `spec_from_env_data()`. Ne dépend d'aucun recalcul de
    `job_key = f"job_{step_index}"` : on part du `SiteSpec` déjà construit,
    comme demandé (l'index par step_index n'est pas reproduit ici)."""
    mapping: Dict[str, str] = {}
    for job in site_spec.jobs:
        url = _job_url(job)
        if url is not None:
            mapping[url] = job.key
    return mapping


def _job_key_to_url(site_spec: SiteSpec) -> Dict[str, str]:
    """Inverse de `_url_to_job_key` : clé du Job -> URL de page qu'il porte.

    Injectif par construction (`_job_url()` ne retient qu'un Job "page" par
    URL) : utile pour reconstituer `page_url` sur une `Reduction` construite à
    partir d'un `job_key` (doublons, Brotli) plutôt que d'une URL directe.
    """
    return {job_key: url for url, job_key in _url_to_job_key(site_spec).items()}


def _entry_transfer_bytes(entry: dict) -> float:
    """Octets réseau RÉELS (compressés) d'une entrée HAR.

    Copie volontaire de `collect_env_data.py::_entry_transfer_bytes()`
    (et de son équivalent `from_har.py::_entry_bytes()`) : reproduire ces
    quelques lignes évite une dépendance circulaire vers `collect_env_data.py`
    (qui, lui, importe des choses de plus haut niveau dans le pipeline).
    Même chaîne de repli : _transferSize (mesure directe), puis
    bodySize+headersSize, puis content.size (décompressé, dernier recours).
    """
    resp = entry.get("response", {})
    transfer_size = resp.get("_transferSize")
    if transfer_size is not None and transfer_size >= 0:
        return transfer_size
    body = resp.get("bodySize", -1)
    if body is not None and body >= 0:
        headers = resp.get("headersSize", -1)
        return body + (headers if headers and headers > 0 else 0)
    return resp.get("content", {}).get("size", 0) or 0


def _pageref_to_url(har: dict) -> Dict[str, str]:
    """Index pageref (id de page HAR) -> URL de page (titre HAR), pour
    résoudre à quelle page appartient une entry (via `entry["pageref"]`)."""
    return {
        page["id"]: page.get("title", "")
        for page in har.get("log", {}).get("pages", [])
        if "id" in page
    }


def _load_har(har_path) -> dict:
    with open(har_path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# 1. Code mort JS / CSS
# ---------------------------------------------------------------------------

_DEAD_CODE_COMMENT = (
    "Approximation : le pourcentage de code mort est mesuré sur le poids "
    "DÉCOMPRESSÉ (Coverage), appliqué tel quel au poids TRANSFÉRÉ/compressé de "
    "la page - ratio supposé comparable, non mesuré directement sur le réseau."
)


def _best_env_page_by_url(env_data: dict) -> Dict[str, dict]:
    """Page `env_data["pages"]` la plus lourde en octets transférés, par URL.

    `env_data["pages"]` (collect_env_data.py::extract_har_data()) contient UNE
    entrée par page HAR (par pageref), PAS dédupliquée par URL : plusieurs
    rechargements de la même URL y figurent. `spec_from_env_data()` retient
    pour chaque URL la répétition la PLUS LOURDE en octets transférés comme
    page canonique (celle qui porte le `data_transferred` du Job). Reproduire
    ce même choix ici est nécessaire : sans lui, on peut apparier un Job à un
    rechargement quasi vide (ex. une répétition à 0 octet) plutôt qu'à la
    capture réellement comptée, et fabriquer un breakdown JS/CSS incohérent
    avec le poids du Job.
    """
    best: Dict[str, dict] = {}
    for page in env_data.get("pages") or []:
        url = page.get("url", "")
        transfer = page.get("size_transfer_bytes", 0) or 0
        current = best.get(url)
        if current is None or transfer > (current.get("size_transfer_bytes", 0) or 0):
            best[url] = page
    return best


def _page_weight_by_type_transfer_bytes(page: dict) -> dict:
    """Octets transférés par type de ressource pour une page `env_data`.

    Champ attendu au premier niveau : `weight_by_type_transfer_bytes`. Dans
    `env_data["pages"]` tel qu'écrit aujourd'hui par
    `collect_env_data.py::extract_har_data()`, ce détail vit en réalité sous
    `page["breakdown"]["by_type_transfer_bytes"]` (le nom
    `weight_by_type_transfer_bytes` n'apparaît, lui, que dans l'agrégat
    `env_data["job"]["efootprint"]`, pour la seule page la plus lourde du
    site). On essaie donc le nom au premier niveau, avec repli sur
    `breakdown.by_type_transfer_bytes` - ce qui couvre le schéma actuel sans
    rien changer si un futur format expose directement le premier nom.
    """
    direct = page.get("weight_by_type_transfer_bytes")
    if direct is not None:
        return direct
    return (page.get("breakdown") or {}).get("by_type_transfer_bytes", {}) or {}


def _page_weight_by_type_bytes(page: dict) -> dict:
    """Octets DÉCOMPRESSÉS par type de ressource pour une page `env_data`.

    Même repli que `_page_weight_by_type_transfer_bytes` : direct au premier
    niveau (`weight_by_type_bytes`), sinon `breakdown.by_type_bytes`
    (`collect_env_data.py::_page_breakdown()`, lignes 601/622). Contrairement
    au poids transféré, ce calcul est DIRECT (pas de transposition) : Coverage
    mesure déjà le code mort sur le poids décompressé.
    """
    direct = page.get("weight_by_type_bytes")
    if direct is not None:
        return direct
    return (page.get("breakdown") or {}).get("by_type_bytes", {}) or {}


def _entry_decompressed_bytes(entry: dict) -> float:
    """Octets DÉCOMPRESSÉS d'une entrée HAR (`content.size`, jamais transposé)."""
    return entry.get("response", {}).get("content", {}).get("size", 0) or 0


def dead_code_reductions(site_spec: SiteSpec, env_data: dict,
                          coverage_pages: List[dict]) -> List[Reduction]:
    """Réduction de `data_transferred` liée au JS et au CSS mort, par page.

    Seuils repris tels quels de `generate_report_html.py::_section_recommandations()` :
      - JS mort  : > 70 % -> palier "prio1" ; entre 50 % (exclu) et 70 % (inclus)
        -> "prio2" ; <= 50 % -> aucune réduction.
      - CSS mort : > 80 % -> palier "prio2" (jamais de palier prio1 pour le CSS,
        c'est la règle exacte du rapport) ; <= 80 % -> aucune réduction.

    Un Job sans page `env_data` correspondante ou sans page `coverage_pages`
    correspondante (même URL exacte) est silencieusement ignoré : pas toutes
    les pages capturées ont forcément une mesure Coverage.
    """
    best_env_page = _best_env_page_by_url(env_data)
    coverage_by_url: Dict[str, dict] = {}
    for cov_page in coverage_pages or []:
        url = cov_page.get("url", "")
        if url and url not in coverage_by_url:
            coverage_by_url[url] = cov_page

    reductions: List[Reduction] = []
    for job in site_spec.jobs:
        url = _job_url(job)
        if url is None:
            continue
        env_page = best_env_page.get(url)
        cov_page = coverage_by_url.get(url)
        if env_page is None or cov_page is None:
            continue

        weight_by_type = _page_weight_by_type_transfer_bytes(env_page)
        js_bytes = weight_by_type.get("js", 0) or 0
        css_bytes = weight_by_type.get("css", 0) or 0

        # Poids DÉCOMPRESSÉ : même page canonique `env_page` (choisie sur le
        # critère transféré par `_best_env_page_by_url()`), lue une seconde
        # fois sous son angle décompressé - une seule répétition canonique
        # pour les deux poids, pas une sélection séparée.
        weight_by_type_decompressed = _page_weight_by_type_bytes(env_page)
        js_bytes_decompressed = weight_by_type_decompressed.get("js", 0) or 0
        css_bytes_decompressed = weight_by_type_decompressed.get("css", 0) or 0

        js_pct = cov_page.get("js_unused_pct", 0.0) or 0.0
        css_pct = cov_page.get("css_unused_pct", 0.0) or 0.0

        js_tier = None
        if js_pct > 70:
            js_tier = "prio1"
        elif js_pct > 50:
            js_tier = "prio2"
        if js_tier is not None:
            removed = js_bytes * (js_pct / 100.0)
            if removed > 0:
                reductions.append(Reduction(
                    job_key=job.key,
                    recommendation="js_dead",
                    tier=js_tier,
                    bytes_removed=removed,
                    traced=estimated(
                        removed, "B",
                        "code mort JS (Coverage Chrome DevTools)",
                        comment=_DEAD_CODE_COMMENT,
                    ),
                    page_url=url,
                    # Calcul DIRECT (pas de transposition) : Coverage mesure
                    # déjà le code mort sur le poids décompressé.
                    bytes_removed_decompressed=js_bytes_decompressed * (js_pct / 100.0),
                ))

        if css_pct > 80:
            removed = css_bytes * (css_pct / 100.0)
            if removed > 0:
                reductions.append(Reduction(
                    job_key=job.key,
                    recommendation="css_dead",
                    tier="prio2",
                    bytes_removed=removed,
                    traced=estimated(
                        removed, "B",
                        "code mort CSS (Coverage Chrome DevTools)",
                        comment=_DEAD_CODE_COMMENT,
                    ),
                    page_url=url,
                    bytes_removed_decompressed=css_bytes_decompressed * (css_pct / 100.0),
                ))

    return reductions


# ---------------------------------------------------------------------------
# 2. Ressources en double
# ---------------------------------------------------------------------------

def duplicate_reductions(site_spec: SiteSpec, har_path) -> List[Reduction]:
    """Réduction de `data_transferred` liée aux ressources chargées en double.

    Palier "prio2" inconditionnel dès qu'au moins un doublon est trouvé (règle
    exacte de `_section_recommandations()`). Calcul NOUVEAU : ni
    `analyze_har.py::compute_duplicate_urls()` (ne donne ni taille ni page) ni
    aucun autre code existant n'est réutilisé.

    Pour chaque URL de requête HAR, la PREMIÈRE occurrence rencontrée (ordre
    des entries) est jugée nécessaire. Chaque occurrence SUIVANTE est un
    doublon, dont les octets transférés sont attribués au Job de la page où
    elle est survenue - si cette page ne correspond à aucun Job du modèle
    (page non canonique ou hors périmètre 1st-party), ses octets sont ignorés :
    ce calcul est volontairement un PLANCHER, pas un total exhaustif.

    `bytes_removed` (octets TRANSFÉRÉS) compte TOUTES les occurrences 2e+,
    y compris les revalidations HTTP 304 (coût réseau réel, mais minime :
    seulement les en-têtes). `bytes_removed_decompressed`, lui, EXCLUT les
    304 : leur corps n'est jamais retransféré ni redécodé (le navigateur
    réutilise le contenu déjà en cache), donc leur poids décompressé compte
    déjà dans le poids EcoIndex de la page qu'on retire le doublon ou pas -
    seul un vrai re-téléchargement complet (200) libère ce poids.
    """
    har = _load_har(har_path)
    log = har.get("log", {})
    pageref_to_url = _pageref_to_url(har)
    url_to_job = _url_to_job_key(site_spec)
    job_key_to_url = _job_key_to_url(site_spec)

    totals: Dict[str, float] = {}
    decompressed_totals: Dict[str, float] = {}
    counts: Dict[str, int] = {}
    seen_urls = set()
    for entry in log.get("entries", []):
        req_url = entry.get("request", {}).get("url", "")
        if req_url not in seen_urls:
            seen_urls.add(req_url)
            continue

        pageref = entry.get("pageref", "")
        page_url = pageref_to_url.get(pageref)
        job_key = url_to_job.get(page_url) if page_url is not None else None
        if job_key is None:
            continue

        totals[job_key] = totals.get(job_key, 0.0) + _entry_transfer_bytes(entry)
        # Une revalidation 304 ne redécode jamais le corps de la ressource :
        # son poids DÉCOMPRESSÉ compte déjà dans le poids EcoIndex de la page
        # (le navigateur réutilise le contenu déjà en cache) - le retirer ne
        # l'enlève pas réellement. Seul un vrai re-téléchargement complet
        # (200) libère ce poids. Les octets TRANSFÉRÉS (déjà minimes pour une
        # 304) et le compte de requêtes, eux, restent inchangés : la requête
        # de revalidation elle-même disparaîtrait bien avec un cache plus
        # long (Cache-Control max-age), et son coût réseau réel est déjà
        # correctement compté ci-dessus.
        if (entry.get("response", {}) or {}).get("status") != 304:
            decompressed_totals[job_key] = (
                decompressed_totals.get(job_key, 0.0) + _entry_decompressed_bytes(entry)
            )
        counts[job_key] = counts.get(job_key, 0) + 1

    reductions: List[Reduction] = []
    for job_key, total in totals.items():
        if total <= 0:
            continue
        reductions.append(Reduction(
            job_key=job_key,
            recommendation="duplicates",
            tier="prio2",
            bytes_removed=total,
            traced=estimated(
                total, "B",
                "calcul doublons HAR (nouveau, pas de code existant réutilisé)",
                comment=(
                    "Octets des occurrences 2e+ d'une même URL dans le HAR, "
                    "attribués à la page où elles sont survenues ; les occurrences "
                    "sur une page non retenue comme canonique (repli 1st-party ou "
                    "dédup HAR) sont ignorées - ce chiffre est un plancher, pas un "
                    "total exhaustif des doublons."
                ),
            ),
            page_url=job_key_to_url.get(job_key),
            bytes_removed_decompressed=decompressed_totals.get(job_key, 0.0),
            # Seule des 3 fonctions de réduction où une requête entière
            # disparaît (JS/CSS mort et Brotli ne suppriment jamais une
            # requête, seulement la taille d'une requête déjà comptée).
            requests_removed=counts.get(job_key, 0),
        ))
    return reductions


# ---------------------------------------------------------------------------
# 3. Brotli non activé
# ---------------------------------------------------------------------------

def brotli_reductions(site_spec: SiteSpec, env_data: dict, har_path,
                       quality: int = 11) -> List[Reduction]:
    """Réduction de `data_transferred` liée à l'absence de compression Brotli.

    Palier "prio3" inconditionnel (toujours déclenché dans
    `_section_recommandations()`). C'est une MESURE RÉELLE, mais partielle :
    seules les entries HAR dont le corps de réponse a été capturé peuvent être
    recompressées pour de vrai ; le reste est EXTRAPOLÉ à partir du ratio
    d'économie observé sur l'échantillon mesurable de la même page. Aucune
    extrapolation n'est produite pour une page sans aucune entry mesurable
    (pas de ratio par défaut inventé).

    `env_data` n'est actuellement pas utilisé par ce calcul : le poids actuel
    de chaque entry et sa recompressibilité viennent entièrement du HAR
    (nécessaire pour accéder au corps de réponse capturé, absent d'env-data.json).
    Le paramètre est conservé pour une signature homogène avec les deux autres
    fonctions de réduction et un usage futur éventuel.
    """
    try:
        import brotli
    except ImportError as exc:
        raise ImportError(
            "brotli_reductions() nécessite le paquet Python 'brotli' "
            "(pip install brotli), introuvable dans l'environnement courant."
        ) from exc

    har = _load_har(har_path)
    log = har.get("log", {})
    pageref_to_url = _pageref_to_url(har)
    url_to_job = _url_to_job_key(site_spec)
    job_key_to_url = _job_key_to_url(site_spec)

    measured_bytes: Dict[str, float] = {}   # octets actuels, entries mesurées
    saved_bytes: Dict[str, float] = {}      # octets économisés, entries mesurées
    unsampled_bytes: Dict[str, float] = {}  # octets actuels, entries hors échantillon

    for entry in log.get("entries", []):
        resp = entry.get("response", {}) or {}
        content = resp.get("content", {}) or {}
        mime = (content.get("mimeType", "") or "").lower()
        if "javascript" not in mime and "css" not in mime:
            continue

        headers = resp.get("headers", []) or []
        encoding_header = next(
            (h.get("value", "") for h in headers
             if (h.get("name", "") or "").lower() == "content-encoding"),
            "",
        )
        if (encoding_header or "").strip().lower() == "br":
            continue

        pageref = entry.get("pageref", "")
        page_url = pageref_to_url.get(pageref)
        job_key = url_to_job.get(page_url) if page_url is not None else None
        if job_key is None:
            continue

        current_bytes = _entry_transfer_bytes(entry)
        text = content.get("text")
        if text is None:
            unsampled_bytes[job_key] = unsampled_bytes.get(job_key, 0.0) + current_bytes
            continue

        if content.get("encoding") == "base64":
            body_bytes = base64.b64decode(text)
        else:
            body_bytes = text.encode("utf-8")

        compressed = brotli.compress(body_bytes, quality=quality)
        saved = max(0.0, current_bytes - len(compressed))

        measured_bytes[job_key] = measured_bytes.get(job_key, 0.0) + current_bytes
        saved_bytes[job_key] = saved_bytes.get(job_key, 0.0) + saved

    reductions: List[Reduction] = []
    for job_key, mesures in measured_bytes.items():
        if mesures <= 0:
            continue
        economise = saved_bytes.get(job_key, 0.0)
        hors_echantillon = unsampled_bytes.get(job_key, 0.0)
        ratio = economise / mesures
        extrapole = hors_echantillon * ratio
        total = economise + extrapole
        if total <= 0:
            continue

        if hors_echantillon > 0:
            comment = (
                f"Mesuré réellement sur {mesures:.0f} octets JS/CSS non-Brotli dont "
                f"le corps était capturé dans le HAR (ratio observé {ratio:.1%}) ; "
                f"extrapolé sur {hors_echantillon:.0f} octets restants dont le corps "
                "n'était pas capturé - PAS mesuré sur cette partie, c'est une "
                "extrapolation du ratio observé, pas un calcul indépendant."
            )
        else:
            comment = (
                f"Mesuré réellement sur {mesures:.0f} octets JS/CSS non-Brotli dont "
                f"le corps était capturé dans le HAR (ratio observé {ratio:.1%}) ; "
                "aucune extrapolation : la totalité des ressources JS/CSS non-Brotli "
                "de cette page avait un corps capturé."
            )

        reductions.append(Reduction(
            job_key=job_key,
            recommendation="brotli",
            tier="prio3",
            bytes_removed=total,
            traced=estimated(
                total, "B",
                "recompression Brotli réelle (bibliothèque brotli, quality=11) sur "
                "l'échantillon capturé, extrapolée au reste",
                comment=comment,
            ),
            page_url=job_key_to_url.get(job_key),
            # Zéro EXACT, pas une approximation : Brotli ne change jamais
            # `content.size` (poids décompressé) ni le nombre de requêtes.
            bytes_removed_decompressed=0.0,
            requests_removed=0,
        ))
    return reductions


# ---------------------------------------------------------------------------
# 4. Application cumulative à un palier
# ---------------------------------------------------------------------------

def apply_recommendations(site_spec: SiteSpec, reductions: List[Reduction],
                           palier: str) -> SiteSpec:
    """Retourne une NOUVELLE `SiteSpec` où `data_transferred` de chaque Job
    concerné est réduit du cumul des `Reduction` dont le palier appartient à
    l'ensemble de paliers désigné par `palier` ("prio1" -> {prio1} ;
    "prio1_2" -> {prio1, prio2} ; "prio1_2_3" -> {prio1, prio2, prio3}).

    SIMPLIFICATION ASSUMÉE : les réductions de recommandations différentes ne
    sont pas dédupliquées entre elles (un fichier dupliqué peut aussi contenir
    du code mort compté séparément) : le cumul peut légèrement surestimer le
    gain réel.

    Un Job sans `data_transferred` est ignoré (rien à réduire). Les Jobs sans
    réduction calculée pour ce palier restent inchangés.
    """
    tiers = _TIER_SETS.get(palier)
    if tiers is None:
        raise ValueError(
            f"palier inconnu : {palier!r}. Attendu un de "
            f"{sorted(_TIER_SETS)}."
        )

    totals: Dict[str, float] = {}
    for reduction in reductions:
        if reduction.tier in tiers:
            totals[reduction.job_key] = (
                totals.get(reduction.job_key, 0.0) + reduction.bytes_removed
            )

    new_jobs = []
    for job in site_spec.jobs:
        total_reduction = totals.get(job.key)
        if not total_reduction or job.data_transferred is None:
            new_jobs.append(job)
            continue

        original_bytes = job.data_transferred.value
        new_bytes = max(0.0, original_bytes - total_reduction)
        new_traced = estimated(
            new_bytes, job.data_transferred.unit,
            f"palier {palier} : recommandations appliquées",
            comment=(
                f"Poids transféré original {original_bytes:.0f} B réduit de "
                f"{original_bytes - new_bytes:.0f} B par l'application "
                "cumulative des recommandations retenues pour ce palier."
            ),
        )
        new_jobs.append(replace(job, data_transferred=new_traced))

    return replace(site_spec, jobs=tuple(new_jobs))
