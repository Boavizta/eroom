#!/usr/bin/env python3
"""
Diagramme depuis une `SiteSpec` : parcours utilisateur, traitements et
infrastructure technique, qui parle à qui.

ZÉRO import e-footprint ici, comme spec.py/compose.py/from_har.py : ce module
ne lit que des dataclasses de spec.py, il ne construit aucun objet
e-footprint. Utile pour visualiser une spec AVANT de la calculer (ex. vérifier
qu'un archétype ou une composition a bien le nombre de serveurs attendu).

PALETTE ET DISPOSITION : calquées sur la vraie interface e-footprint
(model_builder, https://e-footprint.boavizta.org/model_builder/) — 3 colonnes
"Parcours" / "Traitements" / "Infrastructure", cartes à coins arrondis,
liens fins sans pointe de flèche. Choix ASSUMÉ (décision explicite de
l'utilisatrice) : ressemblance visuelle à l'outil de référence plutôt que
cohérence avec la palette OCTO des autres diagrammes du projet (usage
ponctuel/pédagogique, pas un livrable permanent). PlantUML ne sachant pas
dessiner de point rond en bout de ligne, le lien reste un trait nu (`--`),
approximation acceptée du rendu LeaderLine de l'interface source.
"""

_HEADER = """@startuml {diagram_id}

skinparam BackgroundColor #FFFFFF
skinparam RoundCorner 12
skinparam ArrowColor #9CA3AF
skinparam ArrowThickness 1
skinparam ComponentBackgroundColor #FFFFFF
skinparam ComponentBorderColor #E5E7EB
skinparam ComponentBorderThickness 2
skinparam ComponentFontColor #111928
skinparam DatabaseBackgroundColor #FFFFFF
skinparam DatabaseBorderColor #E5E7EB
skinparam DatabaseBorderThickness 2
skinparam DatabaseFontColor #111928
skinparam CloudBackgroundColor #FFFFFF
skinparam CloudBorderColor #E5E7EB
skinparam CloudBorderThickness 2
skinparam CloudFontColor #111928
skinparam RectangleBackgroundColor #FFFFFF
skinparam RectangleBorderColor #E5E7EB
skinparam RectangleBorderThickness 2
skinparam RectangleFontColor #111928
skinparam NoteBackgroundColor #F9FAFB
skinparam NoteBorderColor #D1D5DB
skinparam PackageBackgroundColor #F9FAFB
skinparam PackageBorderColor #D1D5DB
skinparam PackageFontColor #2D4675
skinparam PackageFontStyle bold
skinparam defaultFontName Arial
skinparam defaultFontColor #111928

left to right direction

title <color:#2D4675>{title} - Topologie technique</color>
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
    """Génère le texte PlantUML d'une `SiteSpec`, en 3 colonnes reprenant la
    disposition de l'interface e-footprint (model_builder) : "Parcours"
    (JourneySpec/StepSpec) à gauche, "Traitements" (JobSpec, dont les appels
    IA générative) au centre, "Infrastructure" (ServerSpec, hôtes tiers) à
    droite — le flux se lit usage -> infra, de gauche à droite.

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
    step_alias = {step.key: _sanitize_alias(f"step_{step.key}") for step in spec.steps}

    # --- Colonne 1 : Parcours (JourneySpec regroupant des StepSpec) --------
    if spec.journeys:
        lines.append('package "Parcours" {')
        for journey in spec.journeys:
            journey_alias = _sanitize_alias(f"jrn_{journey.key}")
            lines.append(f'  package "{_escape_label(journey.label)}" as {journey_alias} {{')
            for step_key in journey.steps:
                step = spec.step_by_key(step_key)
                alias = step_alias[step.key]
                lines.append(f'    rectangle "{_escape_label(step.label)}" as {alias}')
            lines.append("  }")
        lines.append("}")
        lines.append("")

    # --- Colonne 2 : Traitements (JobSpec, dont appels IA générative) ------
    ai_jobs = [job for job in spec.jobs if job.external_api is not None]
    network_only_jobs = [job for job in spec.jobs if job.external_api is None]

    if network_only_jobs:
        lines.append('package "Traitements" {')
        for job in network_only_jobs:
            alias = job_alias[job.key]
            lines.append(f'  [{_escape_label(job.label)}] as {alias}')
        lines.append("}")
        lines.append("")

    if ai_jobs:
        lines.append('package "Appels IA générative (empreinte calculée via EcoLogits)" {')
        for job in ai_jobs:
            alias = job_alias[job.key]
            api = job.external_api
            label = f"{job.label}\\n{api.provider}/{api.model_name}"
            lines.append(f'  cloud "{_escape_label(label)}" as {alias}')
        lines.append("}")
        lines.append("")

    # --- Colonne 3 : Infrastructure (ServerSpec, hôtes tiers) ---------------
    lines.append('package "Infrastructure" {')
    for server in spec.servers:
        alias = server_alias[server.key]
        lines.append(f'  database "{_escape_label(server.label)}" as {alias}')
    lines.append("}")
    lines.append("")

    if spec.third_party_hosts:
        lines.append('package "Hôtes tiers (réseau seulement)" {')
        for host in spec.third_party_hosts:
            alias = _sanitize_alias(f"tp_{host.host}")
            label = host.host if not host.note else f"{host.host}\\n({host.note})"
            lines.append(f'  cloud "{_escape_label(label)}" as {alias}')
        lines.append("}")
        lines.append("")

    # --- Liens : étape -> traitement déclenché, traitement -> serveur ------
    for step in spec.steps:
        step_a = step_alias[step.key]
        for job_key in step.jobs:
            job_a = job_alias.get(job_key)
            if job_a is None:
                continue
            lines.append(f"{step_a} -- {job_a}")

    for job in spec.jobs:
        job_a = job_alias[job.key]
        server_a = server_alias.get(job.server_key)
        if server_a is None:
            continue
        lines.append(f"{job_a} -- {server_a}")

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
          f"{len(frag.jobs)} traitement(s), {len(frag.steps)} étape(s).")
