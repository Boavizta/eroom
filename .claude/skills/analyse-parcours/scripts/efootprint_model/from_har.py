#!/usr/bin/env python3
"""
Adaptateur HAR -> SiteSpec. SEUL module de la bibliothèque autorisé à lire des
fichiers (HAR brut, env-data.json).

ZÉRO import e-footprint ICI NON PLUS : ce module ne fait que de la lecture et
de la déduction, il ne construit aucun objet e-footprint (c'est le rôle de
`build.py`). Il peut donc rester testable sans la librairie installée, comme
`spec.py` et `compose.py`.

CE QUE CE MODULE RÉSOUT
------------------------
Un site réel n'a pas toujours un seul serveur. `detect_infrastructures()`
regroupe les hôtes vus dans le HAR en infrastructures 1st-party distinctes
(candidates à un `Server` e-footprint séparé, cf. mémoire persistante
"modéliser les infras distinctes") et en hôtes tiers (réseau seulement).

PIÈGE MESURÉ, À NE PAS OUBLIER : le nom de la PAGE (page.title dans le HAR)
ne dit pas toujours qui la sert. Sur le cas ANTS, une page titrée
"moncompte.ants.gouv.fr/backend/api/..." tire en réalité TOUS ses octets de
predemande-permisdeconduire.ants.gouv.fr (un appel API en coulisses).
L'attribution d'une page à un serveur doit donc se faire sur l'hôte qui porte
le PLUS D'OCTETS dans cette page précise, jamais sur le nom affiché.
"""

import base64
import html as _html
import json
import re
from urllib.parse import urlparse

from .compose import compose
from .spec import (
    AudienceSpec,
    Evidence,
    ExternalApiSpec,
    JobSpec,
    JourneySpec,
    ServerSpec,
    SiteSpec,
    StepSpec,
    ThirdPartyHost,
    measured,
    measured_label,
    script_default,
    script_default_label,
)
from .temps_utilisateur import nielsen_raw_seconds, recalibration_factor, step_user_time

# Alias provider : même correspondance que PROVIDER_ALIASES de
# run_efootprint.py. e-footprint attend "ovhcloud" ; collect_env_data.py (via
# detect_cloud_provider()) détecte "ovh". Dupliqué ici volontairement : les
# deux fichiers lisent des noms de provider à des moments différents du
# pipeline, et faire dépendre from_har.py de run_efootprint.py inverserait le
# sens des imports.
_PROVIDER_ALIASES = {"ovh": "ovhcloud"}

# Gabarit d'instance par défaut par provider, même valeurs que
# DEFAULT_INSTANCE_BY_PROVIDER de run_efootprint.py (2 vCPU / 4 GB). Dupliqué
# pour la même raison que _PROVIDER_ALIASES.
_DEFAULT_INSTANCE_BY_PROVIDER = {
    "aws": "t3.medium",
    "azure": "f2s_v2",
    "gcp": "c2d-highcpu-2",
    "ovhcloud": "c3-4",
    "scaleway": "play2-nano",
}

# ---------------------------------------------------------------------------
# Domaine racine (registrable domain) : suffixes à deux niveaux connus
# ---------------------------------------------------------------------------
# genericite: ok-debut - suffixes publics generiques (aucun cas d'audit)
# Liste volontairement courte : couvre les suffixes à DEUX labels rencontrés
# dans les sites audités jusqu'ici. Un suffixe manquant fait au pire remonter
# un domaine racine trop large (ex. "gouv.fr" au lieu de "ants.gouv.fr"), ce
# qui sur-regroupe plutôt que de rater un regroupement : filet de sécurité
# raisonnable en attendant une vraie liste de suffixes publics (PSL) si le
# besoin se généralise.
_TWO_LABEL_SUFFIXES = frozenset({
    "gouv.fr", "co.uk", "org.uk", "ac.uk", "gov.uk", "com.br", "co.jp",
    "com.au", "co.nz", "com.mx", "co.in", "com.cn",
})
# genericite: ok-fin


def registrable_domain(host):
    """Le domaine racine d'un hôte : les deux derniers labels, ou les trois
    si les deux derniers forment un suffixe public connu (ex. "gouv.fr").

    But : décider si deux hôtes appartiennent à la même organisation sans
    liste blanche par site. Une IP ne suffit pas (deux hôtes 1st-party
    peuvent partager une IP sans être liés, cf. ANTS ajcb/kntw ; l'inverse
    aussi : deux organisations peuvent partager un hébergeur).
    """
    labels = host.lower().split(".")
    if len(labels) <= 2:
        return host.lower()
    last_two = ".".join(labels[-2:])
    if last_two in _TWO_LABEL_SUFFIXES:
        return ".".join(labels[-3:])
    return last_two


def _same_registrable_domain(host, audited_domain):
    return registrable_domain(host) == registrable_domain(audited_domain)


# ---------------------------------------------------------------------------
# Lecture brute du HAR
# ---------------------------------------------------------------------------

def _load_har(har_path):
    with open(har_path, encoding="utf-8") as f:
        return json.load(f)


def _entries_by_host(har):
    """{host: [entries]}, dans l'ordre de première apparition."""
    grouped = {}
    for entry in har.get("log", {}).get("entries", []):
        host = urlparse(entry.get("request", {}).get("url", "")).netloc
        if not host:
            continue
        grouped.setdefault(host, []).append(entry)
    return grouped


def _entry_bytes(entry):
    """Octets réseau RÉELS (compressés), pas le poids décompressé.

    Même convention que `collect_env_data._entry_transfer_bytes()` (Lot 1) :
    c'est le poids transféré qui pilote l'énergie réseau du calcul e-footprint,
    pas `content.size`. Chaîne de repli identique : _transferSize, puis
    bodySize+headersSize, puis content.size en dernier recours.
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


def _entry_has_cache_header(entry):
    headers = entry.get("response", {}).get("headers", [])
    names = {h.get("name", "").lower() for h in headers}
    return bool(names & {"x-cache", "cf-cache-status", "age", "via"})


def _entry_ip(entry):
    ip = entry.get("serverIPAddress", "")
    return ip if ip and not ip.startswith(("127.", "::1")) else None


# ---------------------------------------------------------------------------
# Regroupement des hôtes en infrastructures
# ---------------------------------------------------------------------------

def _attaches_to(host, known_host):
    """`host` se rattache-t-il à `known_host` (déjà repéré comme infra) ?

    Règle : le nom de `host` se termine par ".{known_host}" (préfixe devant,
    séparé par un point). Rattache "ajcb.moncompte.ants.gouv.fr" à
    "moncompte.ants.gouv.fr". Ne rattache PAS
    "predemande-permisdeconduire.ants.gouv.fr" à
    "permisdeconduire.ants.gouv.fr" : le tiret n'est pas un point, la
    coupure de préfixe exigée n'a pas lieu au bon endroit.
    """
    return host != known_host and host.endswith("." + known_host)


def detect_infrastructures(har_path, audited_domain, first_party_extra=()):
    """Regroupe les hôtes du HAR en infrastructures 1st-party et hôtes tiers.

    audited_domain      : domaine du site audité (ex. "octo.com"), pour la
                          règle par défaut "même domaine racine".
    first_party_extra   : hôtes à traiter comme 1st-party malgré un domaine
                          racine différent (ex. "api.analytics.octo.tools"
                          pour octo.com : un service auto-hébergé par la même
                          entreprise, sous un nom qu'aucun algorithme ne peut
                          déduire du HAR seul — jugement humain, tracé ici).

    Retourne (infrastructures, third_party) :
      infrastructures : liste de dicts {key, hosts, ips, request_count,
                        transferred_bytes, cache_header_seen}, triée par
                        octets décroissants (le premier est l'infra
                        principale). `key` est l'hôte "chef de groupe"
                        (le premier vu par ordre d'octets décroissants).
      third_party     : liste de dicts {host, request_count,
                        transferred_bytes} pour les hôtes non 1st-party.
    """
    har = _load_har(har_path)
    by_host = _entries_by_host(har)
    first_party_extra = set(first_party_extra)

    def is_first_party(host):
        return _same_registrable_domain(host, audited_domain) or host in first_party_extra

    host_totals = {
        host: sum(_entry_bytes(e) for e in entries)
        for host, entries in by_host.items()
    }
    first_party_hosts = sorted(
        (h for h in by_host if is_first_party(h)),
        key=lambda h: -host_totals[h],
    )

    groups = []  # liste de dicts mutable pendant la construction
    group_by_host = {}
    for host in first_party_hosts:
        parent = next((g for g in groups if _attaches_to(host, g["key"])), None)
        if parent is None:
            group = {"key": host, "hosts": [host]}
            groups.append(group)
            group_by_host[host] = group
        else:
            parent["hosts"].append(host)
            group_by_host[host] = parent

    infrastructures = []
    for group in groups:
        entries = [e for h in group["hosts"] for e in by_host[h]]
        ips = {ip for e in entries if (ip := _entry_ip(e))}
        infrastructures.append({
            "key": group["key"],
            "hosts": tuple(group["hosts"]),
            "ips": tuple(sorted(ips)),
            "request_count": len(entries),
            "transferred_bytes": sum(_entry_bytes(e) for e in entries),
            "cache_header_seen": any(_entry_has_cache_header(e) for e in entries),
        })
    infrastructures.sort(key=lambda i: -i["transferred_bytes"])

    third_party = []
    for host, entries in by_host.items():
        if is_first_party(host):
            continue
        third_party.append({
            "host": host,
            "request_count": len(entries),
            "transferred_bytes": sum(_entry_bytes(e) for e in entries),
        })
    third_party.sort(key=lambda h: -h["transferred_bytes"])

    return infrastructures, third_party


def infra_for_host(infrastructures, host):
    """L'infra (dict) dont `host` fait partie, ou None."""
    for infra in infrastructures:
        if host in infra["hosts"]:
            return infra
    return None


# ---------------------------------------------------------------------------
# Contenu des pages : comptage de mots
# ---------------------------------------------------------------------------

_NOISE_TAGS = re.compile(
    r"<(script|style|noscript|template|svg)\b[^>]*>.*?</\1>",
    re.DOTALL | re.IGNORECASE,
)
_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_ANY_TAG = re.compile(r"<[^>]+>")
_HAS_LETTER = re.compile(r"[a-zA-ZÀ-ÿ]")


def _strip_html(text):
    text = _COMMENT.sub(" ", text)
    text = _NOISE_TAGS.sub(" ", text)
    text = _ANY_TAG.sub(" ", text)
    return _html.unescape(text)


def count_words(html_text):
    """Nombre de tokens contenant au moins une lettre, hors script/style/
    balises/commentaires. Mesure directe, pas une estimation."""
    cleaned = _strip_html(html_text)
    return sum(1 for token in cleaned.split() if _HAS_LETTER.search(token))


def _page_html_body(page_entries):
    """Corps HTML de la page, décodé si nécessaire.

    PIÈGE MESURÉ : une entrée HAR peut porter `content.encoding == "base64"`
    même pour du text/html (observé sur une page octo.com). Sans décodage
    explicite, `content.text` est du base64 brut, quasi dépourvu de lettres :
    le comptage tombe silencieusement à ~0 au lieu de la vraie valeur.
    """
    for entry in page_entries:
        content = entry.get("response", {}).get("content", {})
        if "html" not in content.get("mimeType", ""):
            continue
        text = content.get("text", "")
        if not text:
            continue
        if content.get("encoding") == "base64":
            try:
                text = base64.b64decode(text).decode("utf-8", errors="replace")
            except (ValueError, base64.binascii.Error):
                continue
        return text
    return None


def detect_page_content(har_path):
    """Comptage de mots par page, avec repli TRACÉ (jamais silencieux).

    Retourne une liste de dicts {page_id, url, word_count, confidence, note},
    dans l'ordre des pages du HAR (préserve l'ordre du parcours réel).
    confidence="high" (mesure directe) si un corps HTML a été trouvé,
    confidence="low"/note explicite sinon (page rendue côté client, corps non
    capturé, etc. — la cause exacte n'est pas déductible du HAR seul, donc
    non affirmée).
    """
    har = _load_har(har_path)
    entries_by_page = {}
    for entry in har.get("log", {}).get("entries", []):
        entries_by_page.setdefault(entry.get("pageref", ""), []).append(entry)

    results = []
    for i, page in enumerate(har.get("log", {}).get("pages", [])):
        pid = page.get("id", f"page_{i + 1}")
        url = page.get("title", "")
        page_entries = entries_by_page.get(pid, [])
        body = _page_html_body(page_entries)
        if body is not None:
            results.append({
                "page_id": pid, "url": url,
                "word_count": count_words(body),
                "confidence": "high",
                "note": None,
            })
        else:
            results.append({
                "page_id": pid, "url": url,
                "word_count": None,
                "confidence": "low",
                "note": "aucun corps HTML capturé pour cette page (rendu "
                        "client, corps non conservé à la capture, ou page "
                        "non-document) : le comptage de mots est indisponible, "
                        "pas nul.",
            })
    return results


# ---------------------------------------------------------------------------
# Serveur porteur d'une page : par octets réels, jamais par le nom affiché
# ---------------------------------------------------------------------------

def _page_dominant_infra_key(page_entries, infrastructures, third_party_hosts):
    """L'infra (clé) qui porte le PLUS D'OCTETS RÉELS dans cette page.

    PIÈGE MESURÉ (cf. docstring du module) : le nom de la page ne suffit pas.
    Une page peut être nommée d'après un hôte alors que tous ses octets
    viennent d'un autre. Seule la mesure directe tranche.

    Retourne (infra_key, is_first_party). Si l'hôte dominant est un tiers
    (aucune infra 1st-party n'a porté le plus d'octets), retourne (None,
    False) : la page n'a alors pas de serveur 1st-party à lui attribuer, ce
    qui doit être signalé plutôt que deviné.
    """
    by_host = {}
    for entry in page_entries:
        host = urlparse(entry.get("request", {}).get("url", "")).netloc
        if host:
            by_host[host] = by_host.get(host, 0) + _entry_bytes(entry)
    if not by_host:
        return None, False

    dominant_host = max(by_host, key=by_host.get)
    infra = infra_for_host(infrastructures, dominant_host)
    if infra is not None:
        return infra["key"], True
    return dominant_host, False


# ---------------------------------------------------------------------------
# Assemblage complet : env-data.json + HAR -> SiteSpec
# ---------------------------------------------------------------------------

_SRC = "env-data.json + HAR (mesure directe)"


def _normalize_provider(detected):
    if not detected:
        return None
    return _PROVIDER_ALIASES.get(detected, detected)


def _server_spec_from_info(server_info, key):
    """Un ServerSpec depuis une entrée de env-data.json["servers"].

    Reprend le même gabarit que run_efootprint.py (base_ram/base_compute/
    storage en script_default, cf. sa docstring PROVIDER_ALIASES /
    DEFAULT_INSTANCE_BY_PROVIDER) : ce n'est pas une régression de
    modélisation, c'est le même défaut appliqué à plusieurs serveurs au lieu
    d'un seul.

    PROVIDER NON DÉTECTÉ (hébergeur mutualisé, ex. "Orange S.A.", pas un cloud
    public) : repli sur le jeu de champs SERVEUR GÉNÉRIQUE (power/
    carbon_footprint_fabrication/pue), mêmes valeurs que le repli de
    `run_efootprint.py:build_efootprint_model()` (300 W, 600 kg, PUE 1,2).
    Sans ce repli, un serveur sans provider ferait échouer build_system()
    (ni le jeu cloud ni le jeu générique complets).
    """
    provider = _normalize_provider(server_info.get("detected_provider"))
    country = server_info.get("efootprint_country") or "FRANCE"
    carbon_intensity = server_info.get("carbon_intensity_g_kwh")

    fields = dict(
        key=key,
        label=f"Serveur {server_info['host']}",
        server_type=script_default_label("autoscaling", "mode de dimensionnement par défaut"),
        country=measured_label(country, _SRC) if server_info.get("country_code")
                else script_default_label(country, "pays non résolu, défaut France"),
        storage_gb=script_default(50.0, "GB_stored"),
        evidence=Evidence(
            hosts=tuple(server_info.get("hosts") or [server_info["host"]]),
            ips=tuple([server_info["ip"]]) if server_info.get("ip") else (),
            request_count=server_info.get("request_count"),
            transferred_bytes=server_info.get("transferred_bytes"),
            cache_header_seen=bool(server_info.get("cache_header_seen")),
        ),
    )
    if carbon_intensity is not None:
        fields["carbon_intensity"] = measured(carbon_intensity, "g/kWh", _SRC)

    if provider:
        fields["base_ram"] = script_default(1.0, "GB_ram")
        fields["base_compute"] = script_default(0.1, "cpu_core")
        fields["provider"] = measured_label(provider, _SRC)
        instance_type = _DEFAULT_INSTANCE_BY_PROVIDER.get(provider, "t3.medium")
        fields["instance_type"] = script_default_label(
            instance_type, "gabarit 2 vCPU/4 GB, hypothèse de petite production")
    else:
        fields["power"] = script_default(300.0, "W")
        fields["carbon_footprint_fabrication"] = script_default(600.0, "kg")
        fields["pue"] = script_default(1.2, "dimensionless")
    return ServerSpec(**fields)


# Hypothèse par défaut si l'utilisatrice ne connaît pas la longueur type d'une
# réponse (décision QCM du 28/08/2026, cf. plan piste 1) : ~150 mots ("réponse
# moyenne", même ordre de grandeur que l'option "Moyenne" de la question posée
# à l'Étape 30), converti en tokens via le ratio ~1,3 token/mot documenté au
# même endroit.
_DEFAULT_OUTPUT_TOKENS = 195.0


def _ai_job_specs_for_step(step_index, page_entries, ai_external_apis, server_key):
    """JobSpec(s) portant un appel IA générative tierce détecté sur CETTE page.

    `ai_external_apis` : bloc env-data.json::ai_external_apis (host ->
    {provider, model_name, output_tokens, resolved}), écrit par
    collect_env_data.py (détection) et complété par l'orchestration du skill
    (réponses de l'utilisatrice, cf. collect_env_data.py --set-ai-model). Un
    host non "resolved" ou sans model_name connu (réponse "je ne sais pas" à
    la question sur le MODÈLE) ne produit AUCUN job : il reste dans
    l'affichage documentaire actuel, jamais de valeur inventée pour le
    modèle — EcoLogits n'a aucun défaut raisonnable à proposer entre
    fournisseurs/tailles de modèle très différents.

    `output_tokens` absent (réponse "je ne sais pas" à la question sur la
    LONGUEUR, décision QCM du 28/08/2026) : PAS d'exclusion cette fois-ci —
    une hypothèse par défaut documentée ("réponse moyenne", cf.
    `_DEFAULT_OUTPUT_TOKENS`) est utilisée à la place, visible comme telle
    dans l'annexe hypothèses du rapport. Différence avec le modèle : un ordre
    de grandeur de longueur de réponse est un défaut raisonnable une fois le
    modèle connu, contrairement à deviner QUEL modèle est appelé.

    `data_transferred=0` sur le job retourné : les octets de cet appel sont
    déjà comptés dans `total_bytes` du job de page (qui somme TOUS les hôtes
    de la page, tiers compris). Ce job existe UNIQUEMENT pour porter le calcul
    EcoLogits (`external_api`) sans compter une seconde fois le réseau.
    `compute_needed`/`ram_needed` volontairement absents (None) : ce job ne
    consomme aucune ressource du serveur 1st-party auquel il est rattaché
    (`server_key`, le même que le job de page — jamais un serveur fictif, cf.
    plan piste 1 sur le double comptage identifié dans l'archétype
    `ia_streaming.py`), seul EcoLogits calcule la compute du FOURNISSEUR tiers.
    """
    if not ai_external_apis:
        return []
    jobs = []
    for host, info in ai_external_apis.items():
        if not info.get("resolved") or not info.get("model_name"):
            continue
        output_tokens = info.get("output_tokens")
        request_count = sum(
            1 for e in page_entries
            if urlparse(e.get("request", {}).get("url", "")).netloc == host
        )
        if request_count == 0:
            continue
        host_key = re.sub(r"[^a-z0-9]+", "_", host.lower()).strip("_")
        output_tokens_traced = (
            measured(output_tokens, "dimensionless", _SRC)
            if output_tokens is not None
            else script_default(
                _DEFAULT_OUTPUT_TOKENS, "dimensionless",
                comment="Aucune longueur de réponse fournie par l'utilisatrice "
                        "(question posée à l'Étape 30, sans réponse) : hypothèse "
                        "par défaut d'une réponse \"moyenne\" (~150 mots).")
        )
        jobs.append(JobSpec(
            key=f"job_ia_{step_index}_{host_key}",
            server_key=server_key,
            label=f"Appel IA ({info.get('rule_name') or host})",
            data_transferred=script_default(
                0.0, "B",
                comment="Octets déjà comptés dans le job de page ; ce job ne "
                        "porte que le calcul EcoLogits (external_api)."),
            external_api=ExternalApiSpec(
                provider=info["provider"],
                model_name=info["model_name"],
                output_tokens=output_tokens_traced,
                request_count_per_step=float(request_count),
            ),
        ))
    return jobs


def spec_from_env_data(env_data, har_path, audited_domain, *,
                       first_party_extra=(), name=None):
    """Assemble une SiteSpec complète depuis env-data.json + le HAR brut.

    Une étape par page distincte capturée dans le HAR (dédupliquée par URL,
    en gardant la capture la plus lourde en octets réels), attribuée au
    serveur qui porte réellement le plus d'octets DANS cette page (jamais au
    nom affiché — cf. piège ANTS page_3). Parcours dans l'ordre de première
    apparition des pages, ce qui reflète l'ordre réel de navigation capturé.

    user_time vient de `temps_utilisateur.step_user_time()` (Lot 4, Nielsen
    2008 recalé) pour chaque étape dont le comptage de mots est connu. Le
    facteur de recalage se calcule UNE FOIS pour tout le site, à partir de
    `env_data["traffic"]["avg_time_on_page_s"]` (SimilarWeb Engagments, cf.
    similarweb_api.py) comparé à la moyenne des Nielsen bruts des étapes du
    parcours (cf. docstring de `temps_utilisateur.py` sur pourquoi une moyenne
    contre une moyenne). Étape sans comptage de mots (repli Lot 3) : défaut de
    script explicite, jamais deviné par Nielsen.

    Retourne (SiteSpec, warnings) où warnings liste les pages dont le serveur
    dominant est un hôte tiers (page non attribuable à une infra 1st-party) :
    à signaler, jamais à masquer.
    """
    servers_info = env_data.get("servers") or []
    if not servers_info:
        raise ValueError(
            "spec_from_env_data() : env-data.json ne contient aucune entrée "
            "\"servers\". Lancer collect_env_data.py (Lot 3) pour la produire."
        )

    infrastructures, third_party = detect_infrastructures(
        har_path, audited_domain, first_party_extra=first_party_extra)

    servers = tuple(_server_spec_from_info(info, info["host"]) for info in servers_info)

    har = _load_har(har_path)
    entries_by_page = {}
    for entry in har.get("log", {}).get("entries", []):
        entries_by_page.setdefault(entry.get("pageref", ""), []).append(entry)

    word_counts = {p["page_id"]: p for p in detect_page_content(har_path)}

    # Déduplication par URL : la page la plus lourde en octets réels
    # représente chaque URL distincte (plusieurs captures d'une même URL sont
    # des rechargements, pas des étapes différentes du parcours).
    best_by_url = {}
    order = []
    pids_by_url = {}
    for i, page in enumerate(har.get("log", {}).get("pages", [])):
        pid = page.get("id", f"page_{i + 1}")
        url = page.get("title", "")
        page_entries = entries_by_page.get(pid, [])
        total_bytes = sum(_entry_bytes(e) for e in page_entries)
        pids_by_url.setdefault(url, []).append(pid)
        if url not in best_by_url or total_bytes > best_by_url[url][1]:
            if url not in best_by_url:
                order.append(url)
            best_by_url[url] = (pid, total_bytes, page_entries)

    # Première passe : ne garde que les pages attribuables à une infra
    # 1st-party (les autres deviennent un warning, jamais une étape), et
    # relève leur comptage de mots. Nécessaire AVANT de construire les étapes :
    # le facteur de recalage Nielsen (ci-dessous) se calcule sur l'ensemble du
    # parcours retenu, pas étape par étape.
    kept, warnings = [], []
    for step_index, url in enumerate(order):
        pid, total_bytes, page_entries = best_by_url[url]
        infra_key, is_first_party = _page_dominant_infra_key(
            page_entries, infrastructures, third_party)
        if not is_first_party:
            warnings.append(
                f"page {url!r} : le serveur qui porte le plus d'octets "
                f"({infra_key!r}) n'est pas une infra 1st-party détectée. "
                "Étape ignorée : aucun serveur du modèle ne peut la porter."
            )
            continue
        # Le comptage de mots peut avoir été mesuré sur une AUTRE répétition
        # de cette URL que celle retenue pour le poids (ex. un rechargement
        # servi depuis le cache HTTP porte le corps HTML, celui qui porte le
        # plus d'octets réels ne le porte pas). Les deux mesures viennent du
        # même HAR ; ne retenir que le pid du poids perdrait un comptage
        # disponible et retomberait à tort sur le défaut de script plus bas.
        word_count = next(
            (wc for other_pid in pids_by_url[url]
             if (wc := word_counts.get(other_pid, {}).get("word_count")) is not None),
            None,
        )
        kept.append((step_index, url, infra_key, total_bytes, word_count))

    avg_time_on_page_s = (env_data.get("traffic") or {}).get("avg_time_on_page_s")
    nielsen_raws = [nielsen_raw_seconds(wc) for _, _, _, _, wc in kept if wc is not None]
    factor = recalibration_factor(avg_time_on_page_s, nielsen_raws)

    ai_external_apis = env_data.get("ai_external_apis") or {}

    jobs, steps = [], []
    for step_index, url, infra_key, total_bytes, word_count in kept:
        job_key = f"job_{step_index}"
        step_key = f"step_{step_index}"
        jobs.append(JobSpec(
            key=job_key,
            server_key=infra_key,
            label=f"Chargement {url}",
            data_transferred=measured(total_bytes, "B", _SRC),
            compute_needed=script_default(0.05, "cpu_core"),
            ram_needed=script_default(50.0, "MB_ram"),
            data_stored=script_default(0.0, "kB_stored"),
        ))
        step_jobs = {job_key: 1}

        # Appel(s) IA générative tierce détecté(s) sur cette page (piste 1,
        # cf. plan) : jamais un serveur/job en plus qui doublerait le poids
        # réseau, cf. docstring de _ai_job_specs_for_step().
        page_entries = best_by_url[url][2]
        for ai_job in _ai_job_specs_for_step(step_index, page_entries, ai_external_apis, infra_key):
            jobs.append(ai_job)
            step_jobs[ai_job.key] = 1

        user_time = step_user_time(word_count, factor) if word_count is not None else None
        step_fields = dict(
            key=step_key,
            label=url,
            user_time=user_time or script_default(
                1.0, "min",
                "aucun comptage de mots pour cette page (repli Lot 3) : "
                "Nielsen inapplicable, défaut de script en attendant une "
                "mesure de contenu."
            ),
            jobs=step_jobs,
            url=url,
        )
        if word_count is not None:
            step_fields["words"] = measured(float(word_count), "dimensionless", _SRC)
        steps.append(StepSpec(**step_fields))

    journey_key = "parcours"
    journey = JourneySpec(
        key=journey_key, label="Parcours capturé",
        steps=tuple(s.key for s in steps),
    )

    third_party_specs = tuple(
        ThirdPartyHost(
            host=h["host"],
            request_count=h["request_count"],
            transferred_bytes=h["transferred_bytes"],
        )
        for h in third_party
    )

    audience = _audience_spec_from_env_data(env_data, journey_key)

    base = SiteSpec(
        name=name or audited_domain,
        servers=servers,
        jobs=tuple(jobs),
        steps=tuple(steps),
        journeys=(journey,),
    )
    spec = compose(base, audience=audience)
    return spec, warnings


def _audience_spec_from_env_data(env_data, journey_key):
    """AudienceSpec depuis les blocs device_mix/network_mix/traffic/server de
    env-data.json. Reprend les mêmes clés que run_efootprint.py:resolve_visits
    et build_efootprint_model, généralisées à N serveurs."""
    device = env_data.get("device_mix") or {}
    network = env_data.get("network_mix") or {}
    traffic = env_data.get("traffic") or {}
    server = env_data.get("server") or {}

    visits = traffic.get("visits_per_year")
    country = server.get("efootprint_country") or "FRANCE"

    fields = dict(
        key="audience",
        label="Visiteurs annuels",
        country=measured_label(country, _SRC),
        journey_key=journey_key,
    )
    if visits is not None:
        fields["visits_per_year"] = measured(float(visits), "dimensionless", _SRC)
    if device.get("phone_fraction") is not None and device.get("desktop_fraction") is not None:
        fields["phone_fraction"] = measured(device["phone_fraction"], "dimensionless", _SRC)
        fields["desktop_fraction"] = measured(device["desktop_fraction"], "dimensionless", _SRC)
    if network.get("wifi_fraction") is not None and network.get("mobile_fraction") is not None:
        fields["wifi_fraction"] = measured(network["wifi_fraction"], "dimensionless", _SRC)
        fields["mobile_fraction"] = measured(network["mobile_fraction"], "dimensionless", _SRC)
    return AudienceSpec(**fields)
