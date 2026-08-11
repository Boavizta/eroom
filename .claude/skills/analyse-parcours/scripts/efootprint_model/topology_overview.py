#!/usr/bin/env python3
"""
Vue d'ensemble de la topologie détectée, à présenter à l'utilisateur AVANT
tout calcul CO2e (Étape 25 du skill efootprint).

ZÉRO import e-footprint ici (comme le reste de efootprint_model/) : ce module
ne fait que de la LECTURE croisée entre une `SiteSpec` déjà construite et le
résultat de `detect_tech.detect_from_har()` (détection heuristique HAR, hors
e-footprint). Il ne construit ni ne modifie aucun objet e-footprint.

POURQUOI UN MODULE SÉPARÉ, PLUTÔT QUE D'ENRICHIR from_har.py :
from_har.py construit la SiteSpec qui pilote le calcul CO2e (contrat vérifié
numériquement par check_efootprint_contract.py) et porte l'historique de
pièges déjà corrigés (attribution par octets réels, pas par nom de page). Ce
module-ci ne pilote AUCUN chiffre : il produit une PRÉSENTATION dérivée
(annotations de suspicion, résumé texte), jamais consommée par build.py.
Séparer les deux garantit que cette étape de présentation ne peut jamais,
même par erreur future, faire dévier un total CO2e publié.

VOCABULAIRE : "suspecté", jamais "détecté" au sens ferme — sauf pour un
provider IA/BaaS reconnu par nom de domaine EXACT (signal quasi certain), où
le texte peut dire "identifié". Une absence de signal ne prouve JAMAIS
l'absence de la technologie : une base de données auto-hébergée derrière le
serveur applicatif n'émet aucun signal réseau visible côté client, elle est
structurellement invisible depuis le seul trafic capturé.
"""

from dataclasses import replace

# Catégories issues de detect_tech.py routées vers une note ThirdPartyHost.
# Table de correspondance, pas une redécouverte de règles : ce module ne fait
# QUE router un résultat déjà produit par detect_tech.py, jamais sa propre
# détection.
_SUSPICION_LABELS = {
    "IA générative (tiers)": "IA générative tierce (identifié par domaine)",
    "Streaming média": "streaming média (suspecté)",
    "Backend-as-a-Service / BDD (tiers)": "BDD/BaaS tiers (identifié par domaine)",
}

_SUSPICION_CATEGORIES = tuple(_SUSPICION_LABELS)


def _spec_hosts(spec):
    """Les hosts tiers de la spec, pour le routage evidence->host ci-dessous."""
    return tuple(h.host for h in spec.third_party_hosts)


def annotate_third_party_hosts(spec, tech_result):
    """Retourne une COPIE de `spec` dont les `ThirdPartyHost` portent une
    `note` de suspicion quand `tech_result` (detect_tech.detect_from_har())
    a rattaché ce host à une des catégories suivies.

    Ne modifie jamais `spec` en place (cohérent avec le reste de la
    bibliothèque : une transformation en retourne une nouvelle plutôt que de
    modifier celle qu'on lui passe). Si `tech_result` est None (HAR absent,
    illisible, ou module detect_tech indisponible), retourne `spec`
    inchangée.

    LIMITE CONNUE : le routage host<-evidence est BEST-EFFORT. `evidence` est
    un texte tronqué à 60 caractères construit par detect_tech.py pour
    l'affichage humain, pas pour un ré-appariement programmatique garanti à
    100 % (host tronqué ou requête sans host reconnaissable dans l'evidence
    ne sera pas routé). Accepté pour ce lot : mieux vaut un routage partiel
    honnête qu'un contrat de sortie élargi sur detect_tech.detect() pour un
    gain marginal.
    """
    if not tech_result:
        return spec

    hosts = _spec_hosts(spec)
    host_to_labels = {}
    for tech in tech_result.get("technologies", []):
        label = _SUSPICION_LABELS.get(tech["category"])
        if not label:
            continue
        evidence = tech.get("evidence") or ""
        for host in hosts:
            if host in evidence:
                host_to_labels.setdefault(host, []).append(label)

    if not host_to_labels:
        return spec

    new_hosts = tuple(
        replace(h, note=", ".join(dict.fromkeys(host_to_labels[h.host])))
        if h.host in host_to_labels else h
        for h in spec.third_party_hosts
    )
    return replace(spec, third_party_hosts=new_hosts)


def overview_text(spec, tech_result):
    """Résumé texte de la topologie détectée, pour l'Étape 25 (avant calcul).

    Combine : nombre de serveurs 1st-party (spec.servers, déjà fiable —
    cf. from_har.py::detect_infrastructures()), technologies détectées
    groupées par catégorie suivie (BDD/BaaS, streaming, IA), et le rappel
    honnête qu'une BDD auto-hébergée reste invisible depuis le HAR.
    """
    lines = []
    lines.append(f"Serveurs 1st-party détectés : {len(spec.servers)}")
    for server in spec.servers:
        lines.append(f"  - {server.label}")

    if tech_result:
        categories = tech_result.get("categories") or {}
        for cat in _SUSPICION_CATEGORIES:
            names = categories.get(cat) or []
            if names:
                lines.append(f"{cat} suspecté(s) : {', '.join(names)}")

    lines.append(
        "Note : une base de données ou un service auto-hébergé DERRIÈRE le "
        "serveur applicatif n'émet aucun signal visible depuis le trafic "
        "réseau capturé. Cette section ne peut donc JAMAIS conclure à son "
        "absence — seulement signaler les services tiers directement "
        "exposés au navigateur."
    )
    return "\n".join(lines)
