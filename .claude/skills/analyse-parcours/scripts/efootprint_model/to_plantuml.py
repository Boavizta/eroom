#!/usr/bin/env python3
"""
Diagramme de composants PlantUML depuis une `SiteSpec` : topologie technique
(serveurs 1st-party + traitements, qui parle à qui), pas le parcours
utilisateur (cf. les diagrammes de séquence du skill diagrammes-analyse-
parcours pour ça).

ZÉRO import e-footprint ici, comme spec.py/compose.py/from_har.py : ce module
ne lit que des dataclasses de spec.py, il ne construit aucun objet
e-footprint. Utile pour visualiser une spec AVANT de la calculer (ex. vérifier
qu'un archétype ou une composition a bien le nombre de serveurs attendu).

PALETTE ET RÈGLES ANTI-CROISEMENT : reprend le skill global
`diagramme-de-composants` (~/.claude/skills/diagramme-de-composants/SKILL.md) :
palette OCTO, `top to bottom direction`, flèches directionnelles, un package
par nature de composant (serveurs, traitements, hôtes tiers, appels IA).
"""

_HEADER = """@startuml {diagram_id}

skinparam BackgroundColor #FFFFFF
skinparam ComponentBackgroundColor #E0F0F4
skinparam ComponentBorderColor #5BA1BC
skinparam ComponentFontColor #1C2856
skinparam ArrowColor #5BA1BC
skinparam DatabaseBackgroundColor #82C1DD
skinparam DatabaseBorderColor #5BA1BC
skinparam DatabaseFontColor #1C2856
skinparam CloudBackgroundColor #ECECF2
skinparam CloudBorderColor #888FA8
skinparam CloudFontColor #1C2856
skinparam NoteBackgroundColor #ECECF2
skinparam NoteBorderColor #5BA1BC
skinparam PackageBorderColor #5BA1BC
skinparam PackageFontColor #1C2856
skinparam defaultFontName Arial
skinparam defaultFontColor #1C2856

top to bottom direction

title <color:#1C2856>{title} - Topologie technique</color>
"""


def _sanitize_alias(key):
    """Alias PlantUML valide : ASCII lettres/chiffres/underscore seulement,
    jamais vide. ASCII strict (pas juste `isalnum()`, qui accepte l'Unicode
    accentué) : cet alias devient aussi un nom de fichier de sortie pour
    `@startuml <id>` (cf. site_to_plantuml()), et un nom de fichier accentué
    est fragile selon la plateforme/l'outil de build."""
    cleaned = "".join(c if c.isascii() and (c.isalnum() or c == "_") else "_" for c in key)
    return cleaned if cleaned and cleaned[0].isalpha() else f"c_{cleaned}"


def _escape_label(text):
    """Échappe les guillemets d'un label PlantUML, jamais les doubles tirets
    (cf. règle rédactionnelle du skill diagrammes-analyse-parcours : `--` est
    interprété comme du texte barré par PlantUML)."""
    escaped = (text or "").replace('"', "'")
    return escaped.replace("--", "- -")


def site_to_plantuml(spec, *, title=None):
    """Génère le texte PlantUML (diagramme de composants) d'une `SiteSpec`.

    Un package "Serveurs 1st-party" (un composant par ServerSpec), un package
    "Traitements" (un composant par JobSpec, relié à son serveur), un package
    "Hôtes tiers (réseau seulement)" si `third_party_hosts` est renseigné, et
    des appels IA générative isolés en cloud si un JobSpec porte un
    `external_api` (cf. spec.py::ExternalApiSpec).

    Retourne une chaîne, à écrire dans un fichier `.puml` par l'appelant
    (ce module ne touche jamais au disque, comme spec.py/compose.py).
    """
    diagram_title = title or spec.name
    # `@startuml <id>` PILOTE LE NOM DU FICHIER DE SORTIE quand plantuml
    # génère depuis un .puml multi-diagrammes ou sans -o explicite : un titre
    # avec espaces/accents/parenthèses (nom de site réel) produirait un nom de
    # fichier fragile. L'identifiant reste un alias technique, le TITRE AFFICHÉ
    # (ligne `title`, plus bas) porte le nom lisible du site.
    diagram_id = _sanitize_alias(f"site_{spec.name}")
    lines = [_HEADER.format(diagram_id=diagram_id, title=_escape_label(diagram_title))]

    server_alias = {server.key: _sanitize_alias(f"srv_{server.key}") for server in spec.servers}
    job_alias = {job.key: _sanitize_alias(f"job_{job.key}") for job in spec.jobs}

    lines.append(f'package "Serveurs 1st-party" #E0F0F4 {{')
    for server in spec.servers:
        alias = server_alias[server.key]
        lines.append(f'  database "{_escape_label(server.label)}" as {alias} #82C1DD')
    lines.append("}")
    lines.append("")

    ai_jobs = [job for job in spec.jobs if job.external_api is not None]
    network_only_jobs = [job for job in spec.jobs if job.external_api is None]

    if network_only_jobs:
        lines.append(f'package "Traitements" #ECECF2 {{')
        for job in network_only_jobs:
            alias = job_alias[job.key]
            lines.append(f'  [{_escape_label(job.label)}] as {alias} #DBDDE5')
        lines.append("}")
        lines.append("")

    if ai_jobs:
        lines.append(f'package "Appels IA générative (empreinte calculée via EcoLogits)" #ECECF2 {{')
        for job in ai_jobs:
            alias = job_alias[job.key]
            api = job.external_api
            label = f"{job.label}\\n{api.provider}/{api.model_name}"
            lines.append(f'  cloud "{_escape_label(label)}" as {alias} #DBDDE5')
        lines.append("}")
        lines.append("")

    if spec.third_party_hosts:
        lines.append(f'package "Hôtes tiers (réseau seulement)" #ECECF2 {{')
        for host in spec.third_party_hosts:
            alias = _sanitize_alias(f"tp_{host.host}")
            lines.append(f'  cloud "{_escape_label(host.host)}" as {alias} #888FA8')
        lines.append("}")
        lines.append("")

    for job in spec.jobs:
        job_a = job_alias[job.key]
        server_a = server_alias.get(job.server_key)
        if server_a is None:
            continue
        lines.append(f"{job_a} -down-> {server_a}")

    lines.append("")
    lines.append("@enduml")
    return "\n".join(lines)


if __name__ == "__main__":
    from .archetypes import dynamique_bdd

    frag = dynamique_bdd.apply(
        prefix="demo",
        visits_per_year=50_000,
        page_weight_kb=250,
        user_time_seconds=45,
        source_name="démonstration __main__ (données fictives)",
    )
    puml = site_to_plantuml(frag)
    assert "@startuml" in puml and "@enduml" in puml, "diagramme mal formé"
    assert puml.count("database") == len(frag.servers), \
        "un composant database par serveur attendu"
    print(puml)
    print()
    print(f"OK : diagramme généré, {len(frag.servers)} serveur(s), "
          f"{len(frag.jobs)} traitement(s).")
