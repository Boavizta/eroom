#!/usr/bin/env python3
"""Inventaire des tiers DÉCLARÉS dans l'en-tête `Content-Security-Policy`.

Pourquoi ce module : le CSP est la liste, écrite par l'équipe du site, de tous
les domaines depuis lesquels le navigateur est autorisé à charger quelque
chose. C'est donc un inventaire d'intention, structurellement **plus large**
que le HAR, qui ne capte que ce qui a réellement été sollicité pendant le
parcours enregistré.

L'écart entre les deux est une information en soi. Cas vérifié sur octo.com
(2026-09-03) : le CSP déclare toute la suite HubSpot et le pixel LinkedIn,
mais le HAR de la capture n'en contient **aucune** trace (seuls
`api.analytics.octo.tools`, `swetrix.org`, jsDelivr et Google Fonts).
L'explication la plus probable est que la capture a été faite sans accepter
le consentement (le site utilise Orejime), donc les traceurs marketing n'ont
jamais démarré — exactement l'angle mort documenté dans la consigne de
capture du projet. Le CSP permet de le voir malgré tout.

Coût : **aucun appel réseau**. La valeur du CSP est déjà stockée dans
`security-headers-analysis.json` (`pages[].detail[]` où
`header == "content-security-policy"`), produit par `analyze_security_headers.py`
depuis les en-têtes du `.har`.

Limite structurelle à ne jamais oublier : un domaine autorisé par le CSP
**n'est pas** un domaine utilisé. Une autorisation peut être un reliquat, une
préparation, ou concerner une autre partie du site que celle auditée. Ce
module ne produit donc jamais de verdict : il produit un inventaire classé,
que les règles EOF croisent avec ce qui est réellement chargé.

Usage comme module :
    from csp_inventory import inventory_from_headers_analysis
    inv = inventory_from_headers_analysis(headers_analysis_dict)

Usage en ligne de commande (inspection) :
    python3 csp_inventory.py <source_dir>
"""

import argparse
import json
import re
import sys
from pathlib import Path

# Mots-clés CSP qui ne sont pas des domaines (à écarter de l'inventaire).
_CSP_KEYWORDS = {
    "'self'", "'none'", "'unsafe-inline'", "'unsafe-eval'", "'strict-dynamic'",
    "'unsafe-hashes'", "'report-sample'", "'wasm-unsafe-eval'",
    "data:", "blob:", "filesystem:", "mediastream:", "about:", "https:", "http:",
    "*",
}

# Directives qui déclarent un chargement de ressource. `report-uri`,
# `report-to`, `upgrade-insecure-requests`, `sandbox`... n'en déclarent pas.
_RESOURCE_DIRECTIVES = {
    "default-src", "script-src", "script-src-elem", "script-src-attr",
    "style-src", "style-src-elem", "style-src-attr", "img-src", "font-src",
    "connect-src", "media-src", "frame-src", "child-src", "worker-src",
    "object-src", "manifest-src", "prefetch-src", "form-action",
}

# Familles de tiers. Ordre significatif : le premier motif qui matche gagne,
# donc les familles les plus spécifiques doivent précéder les plus génériques
# (ex. `hs-analytics` avant un éventuel motif large sur "analytics").
#
# Le découpage sépare volontairement l'analytics SOBRE (sans cookie, sans
# profilage publicitaire, souvent auto-hébergeable) du reste : c'est
# exactement la distinction que le critère EOF 1.12 suppose, et qu'un simple
# "une techno Analytics est détectée" ne fait pas.
_FAMILIES = [
    ("analytics_sobre", [
        r"\bswetrix\b", r"\bplausible\b", r"\bmatomo\b", r"\bpiwik\b",
        r"\bumami\b", r"\bfathom\b", r"goatcounter", r"simpleanalytics",
        r"\bpirsch\b", r"counter\.dev", r"\bcabin\b", r"\btinylytics\b",
    ]),
    ("marketing_crm", [
        r"\bhubspot\b", r"\bhubapi\b", r"\bhs-\w+", r"hsforms", r"hsappstatic",
        r"hs-sites", r"hsadspixel", r"\bmarketo\b", r"\bpardot\b",
        r"\bsalesforce\b", r"\bintercom\b", r"\bdrift\b", r"\bklaviyo\b",
        r"\bmailchimp\b", r"list-manage", r"activecampaign", r"\bbraze\b",
        r"\biterable\b", r"\bcustomer\.io\b", r"\bsendinblue\b", r"\bbrevo\b",
    ]),
    ("pixels_publicitaires_sociaux", [
        r"doubleclick", r"googlesyndication", r"googleadservices",
        r"connect\.facebook", r"facebook\.net", r"\blicdn\b", r"linkedin",
        r"\bcriteo\b", r"\btaboola\b", r"\boutbrain\b", r"\btiktok\b",
        r"snapchat", r"\bsc-static\b", r"pinterest", r"\bpinimg\b",
        r"\bbat\.bing\b", r"clarity\.ms", r"\bads-twitter\b", r"\bt\.co\b",
        r"\badnxs\b", r"rubiconproject", r"pubmatic", r"\badform\b",
    ]),
    ("analytics_comportemental", [
        r"google-analytics", r"googletagmanager", r"analytics\.google",
        r"\bomniture\b", r"\bdemdex\b", r"\b2o7\.net\b", r"adobedtm",
        r"\bsegment\.(io|com)\b", r"\bmixpanel\b", r"\bamplitude\b",
        r"\bheap(analytics)?\.", r"fullstory", r"\bhotjar\b",
        r"contentsquare", r"\bquantcast\b", r"chartbeat", r"\bmouseflow\b",
        r"\bsmartlook\b", r"\bluckyorange\b", r"\bcrazyegg\b",
    ]),
    ("paas_backend", [
        r"herokuapp", r"\bappspot\b", r"azurewebsites", r"\bvercel\.app\b",
        r"netlify\.app", r"\bworkers\.dev\b", r"\brun\.app\b",
        r"elasticbeanstalk", r"\bfly\.dev\b", r"\brailway\.app\b",
        r"\bonrender\.com\b", r"\bcloudfunctions\b", r"\blambda-url\b",
    ]),
    ("captcha_antibot", [
        r"recaptcha", r"\bhcaptcha\b", r"challenges\.cloudflare",
        r"\bturnstile\b", r"\bdatadome\b", r"\bperimeterx\b",
        r"\bfriendlycaptcha\b", r"\barkoselabs\b",
    ]),
    ("cdn_bibliotheques", [
        r"\bjsdelivr\b", r"\bcdnjs\b", r"\bunpkg\b", r"\bcloudfront\b",
        r"\bakamai\w*", r"\bfastly\b", r"cdn\.cloudflare", r"\bbootstrapcdn\b",
        r"\bskypack\b", r"\besm\.sh\b",
    ]),
    ("polices", [
        r"fonts\.googleapis", r"fonts\.gstatic", r"use\.typekit",
        r"\bfonts\.net\b", r"\bfontawesome\b", r"\bcloud\.typography\b",
    ]),
    ("cartes_media_embed", [
        r"\byoutube(-nocookie)?\.com\b", r"\bytimg\b", r"\bvimeo\b",
        r"maps\.googleapis", r"\bmapbox\b", r"openstreetmap",
        r"\bdailymotion\b", r"\bsoundcloud\b", r"\bspotify\b",
        r"\bdeezer\b", r"\btwitch\b",
    ]),
    ("consentement_rgpd", [
        r"\borejime\b", r"cookiebot", r"onetrust", r"\baxeptio\b",
        r"\btarteaucitron\b", r"\bdidomi\b", r"\bsirdata\b", r"\bquantcast\.mgr\b",
        r"\bklaro\b", r"\btrustarc\b",
    ]),
    ("infra_cloud_generique", [
        r"amazonaws", r"\bgstatic\b", r"\bgoogleapis\b", r"\bblob\.core\b",
        r"\bstorage\.googleapis\b",
    ]),
]

# Familles considérées comme du pistage non essentiel au fonctionnement du
# service, au sens du critère EOF 1.12. L'analytics sobre en est volontairement
# exclu : c'est la mesure d'audience minimale, pas du pistage.
TRACKING_FAMILIES = (
    "marketing_crm", "pixels_publicitaires_sociaux", "analytics_comportemental",
)


def parse_csp(csp_value):
    """Découpe un CSP en {directive: [sources]}. Tolérant aux CSP mal formés."""
    directives = {}
    if not csp_value:
        return directives
    for chunk in csp_value.split(";"):
        parts = chunk.strip().split()
        if not parts:
            continue
        directives[parts[0].lower()] = parts[1:]
    return directives


def _normalise_host(source):
    """'*.hs-scripts.com' -> 'hs-scripts.com' ; 'https://a.b/c' -> 'a.b'.

    Retourne None si la source n'est pas un domaine (mot-clé CSP, schéma nu,
    hash/nonce inline).
    """
    s = source.strip()
    if not s or s.lower() in _CSP_KEYWORDS:
        return None
    if s.startswith("'"):  # 'nonce-...', 'sha256-...', autres mots-clés quotés
        return None
    s = re.sub(r"^[a-z][a-z0-9+.-]*://", "", s, flags=re.IGNORECASE)
    s = s.split("/")[0]
    s = s.lstrip("*.")
    s = s.split(":")[0]  # retire un éventuel port
    if not s or "." not in s:
        return None
    return s.lower()


def classify_host(host):
    """Retourne la famille d'un domaine, ou 'non_classe' si aucun motif ne matche."""
    for family, patterns in _FAMILIES:
        for pattern in patterns:
            if re.search(pattern, host, re.IGNORECASE):
                return family
    return "non_classe"


def extract_csp_value(headers_analysis):
    """Récupère la valeur du CSP depuis security-headers-analysis.json.

    Prend le CSP de la première page qui en déclare un. Si plusieurs pages ont
    des CSP différents, l'union serait trompeuse (on ne saurait plus quelle
    page autorise quoi) : on préfère la valeur d'une page réelle, et on signale
    le nombre de pages concernées.
    """
    pages = (headers_analysis or {}).get("pages") or []
    values = []
    for page in pages:
        for item in page.get("detail") or []:
            if item.get("header") == "content-security-policy" and item.get("valeur"):
                values.append((page.get("url"), item["valeur"]))
                break
    if not values:
        return None, 0, None
    url, value = values[0]
    return value, len(values), url


def inventory_from_headers_analysis(headers_analysis):
    """Inventaire classé des tiers déclarés. None si aucun CSP disponible."""
    csp_value, pages_with_csp, source_url = extract_csp_value(headers_analysis)
    if not csp_value:
        return None

    directives = parse_csp(csp_value)
    hosts_by_directive = {}
    all_hosts = set()
    for directive, sources in directives.items():
        if directive not in _RESOURCE_DIRECTIVES:
            continue
        hosts = set()
        for source in sources:
            host = _normalise_host(source)
            if host:
                hosts.add(host)
        if hosts:
            hosts_by_directive[directive] = sorted(hosts)
            all_hosts |= hosts

    families = {}
    for host in sorted(all_hosts):
        families.setdefault(classify_host(host), []).append(host)

    return {
        "source": "security-headers-analysis.json (en-tête Content-Security-Policy)",
        "page_source": source_url,
        "pages_avec_csp": pages_with_csp,
        "hosts_declares": sorted(all_hosts),
        "familles": families,
        "par_directive": hosts_by_directive,
        "note": (
            "Inventaire DÉCLARÉ, pas observé : un domaine autorisé par le CSP "
            "n'est pas nécessairement sollicité. À croiser avec le HAR pour "
            "distinguer 'prévu' de 'réellement chargé'."
        ),
    }


def loaded_hosts_from_har_analysis(har_analysis):
    """Domaines réellement sollicités, d'après har-analysis.json.

    Retourne None (et non un ensemble vide) si l'information est absente :
    un ensemble vide signifierait à tort "aucun tiers chargé".
    """
    domains = (har_analysis or {}).get("domains") or {}
    first = domains.get("first_party") or []
    third = domains.get("third_party") or []
    if not first and not third:
        return None
    return {h.lower() for h in list(first) + list(third)}


def _host_matches(host, loaded):
    """Un domaine CSP est considéré chargé si lui-même ou un sous-domaine l'est."""
    return any(h == host or h.endswith("." + host) for h in loaded)


def tracking_summary(inventory, har_analysis):
    """Croise l'inventaire déclaré et les domaines réellement chargés.

    Retourne un dict décrivant les traceurs par famille, en distinguant
    déclarés-et-chargés / déclarés-seulement. Ne rend aucun verdict.
    """
    if not inventory:
        return None
    loaded = loaded_hosts_from_har_analysis(har_analysis)
    familles = inventory["familles"]

    tracking_declared, sober_declared = [], []
    for family, hosts in familles.items():
        if family in TRACKING_FAMILIES:
            tracking_declared.extend(hosts)
        elif family == "analytics_sobre":
            sober_declared.extend(hosts)

    def split(hosts):
        if loaded is None:
            return sorted(hosts), []
        charges = sorted(h for h in hosts if _host_matches(h, loaded))
        declares_seulement = sorted(h for h in hosts if not _host_matches(h, loaded))
        return charges, declares_seulement

    tracking_loaded, tracking_only_declared = split(tracking_declared)
    sober_loaded, sober_only_declared = split(sober_declared)

    return {
        "loaded_connu": loaded is not None,
        "pistage_charge": tracking_loaded,
        "pistage_declare_non_charge": tracking_only_declared,
        "analytics_sobre_charge": sober_loaded,
        "analytics_sobre_declare_non_charge": sober_only_declared,
        "familles_pistage_retenues": list(TRACKING_FAMILIES),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source_dir")
    args = parser.parse_args()
    source_dir = Path(args.source_dir).resolve()

    headers_path = source_dir / "security-headers-analysis.json"
    if not headers_path.exists():
        print(f"Erreur : {headers_path} absent. Lancer analyze_security_headers.py d'abord.")
        sys.exit(1)
    headers_analysis = json.loads(headers_path.read_text(encoding="utf-8"))

    inv = inventory_from_headers_analysis(headers_analysis)
    if inv is None:
        print("Aucun en-tête Content-Security-Policy dans les pages analysées : "
              "aucun inventaire de tiers déclarés possible.")
        sys.exit(0)

    har_analysis = None
    for candidate in (source_dir / "audit" / "har-analysis.json", source_dir / "har-analysis.json"):
        if candidate.exists():
            har_analysis = json.loads(candidate.read_text(encoding="utf-8"))
            break

    print(f"CSP lu sur : {inv['page_source']} ({inv['pages_avec_csp']} page(s) avec CSP)")
    print(f"{len(inv['hosts_declares'])} domaine(s) déclaré(s), par famille :")
    for family, hosts in sorted(inv["familles"].items()):
        print(f"  - {family} ({len(hosts)}) : {', '.join(hosts)}")

    summary = tracking_summary(inv, har_analysis)
    if summary:
        print("\nCroisement avec les domaines réellement chargés (har-analysis.json) :")
        if not summary["loaded_connu"]:
            print("  har-analysis.json indisponible : impossible de distinguer déclaré/chargé.")
        else:
            print(f"  pistage effectivement chargé      : {summary['pistage_charge'] or 'aucun'}")
            print(f"  pistage déclaré mais NON chargé    : {summary['pistage_declare_non_charge'] or 'aucun'}")
            print(f"  analytics sobre chargé             : {summary['analytics_sobre_charge'] or 'aucun'}")


if __name__ == "__main__":
    main()
