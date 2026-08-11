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

DISPOSITION : 3 colonnes côte à côte, PLUS HAUTE QUE LARGE (police agrandie,
texte replié). Une première version "large" (`left to right direction`
classique) a existé puis a été abandonnée après comparaison : l'utilisatrice
a jugé cette disposition-ci nettement plus lisible. Testé réellement
(`plantuml -tsvg` + rendu PNG), pas supposé :
  - `skinparam wrapWidth N` seul, `left to right direction` conservé : quasi
    aucun effet sur la largeur — GraphViz range toujours les composants d'une
    colonne en GRILLE horizontale, jamais empilés verticalement.
  - Liens invisibles (`-[hidden]->`) SANS retirer `left to right direction` :
    contre-productif, fait EXPLOSER la largeur totale (conflit entre le flux
    global gauche-droite et l'empilement local demandé).
  - Solution qui marche (mesurée sur les 2 audits du dépôt, octo.com
    1491x565 -> 1104x1182, ants-permis 2294x346 -> 1120x1098) : RETIRER
    `left to right direction` (c'est elle qui étale en grille), puis forcer la
    disposition avec des liens invisibles `-[hidden]d-` (empilement vertical
    intra-colonne) et `-[hidden]r-` entre packages consécutifs (colonnes
    maintenues côte à côte malgré l'absence de la directive globale), plus une
    police agrandie et un retour à la ligne du texte (`wrapWidth`).
  - LIMITE ACCEPTÉE : au-delà de 3 packages consécutifs chaînés par
    `-[hidden]r-` (cas à 5 packages : IA générative + hôtes tiers en plus des
    3 colonnes de base), un léger effet d'escalier apparaît (décalage vertical
    progressif). Documenté comme défaut esthétique mineur, nettement moins
    pénalisant que l'alternative `left to right direction` classique dans ce
    cas (largeur démesurée).
  - PIÈGE DE RENDU (découvert par test, corrigé) : découper un label en
    tranches de N caractères peut faire commencer une ligne de continuation
    par un caractère creole PlantUML (`=`, notamment issu d'une URL du type
    `?lang=fr` coupée en `lang`/`=fr`), interprété comme un titre H1 (rendu
    gras centré) au lieu du texte attendu. `_wrap_label()` s'en protège, ET
    coupe désormais sur des frontières naturelles (mots, séparateurs d'URL
    `/`, `-`, `_`, `.`, `?`, `&`, `=`) plutôt qu'au caractère près — un mot ou
    un segment de chemin n'est jamais scindé en son milieu.
  - PIÈGE (découvert par test, corrigé) : `skinparam wrapWidth N` était
    utilisé EN PLUS de `_wrap_label()`, en pensant qu'il ne s'appliquerait
    qu'aux textes non encore repliés. Faux : combiné à `*FontSize 16` (police
    agrandie), PlantUML recalcule SES PROPRES césures sur un texte déjà
    replié par notre code, et casse par exemple "~1 s" en deux lignes ("~1"
    puis "s") — un texte identique sans `RectangleFontSize` custom ne casse
    pas, la régression n'apparaît qu'à police modifiée. Retiré du header :
    notre wrap Python suffit, `skinparam wrapWidth` est redondant et devient
    dangereux dès que la taille de police change.

HYPOTHÈSES DE CALCUL AFFICHÉES : demande explicite de l'utilisatrice de
retrouver, DANS le diagramme, les grandes hypothèses qui pilotent le résultat
(pas seulement dans le tableau texte séparé de `print_hypotheses()` /
`_section_efootprint()`). Deux niveaux :
  - une note globale (trafic annuel, mix appareils, mix pays d'audience,
    temps de lecture total cumulé du parcours), rendue en `legend bottom`
    (PAS une `note` flottante : testé, une note sans ancrage reçoit une
    largeur arbitraire bien trop étroite du moteur de layout — un mot par
    ligne, illisible ; `legend bottom` s'étale sur toute la largeur du
    diagramme, une ligne par hypothèse) ;
  - un détail sur chaque composant concerné (temps de l'étape, poids
    transféré du traitement, type d'instance/provider du serveur).
Valeur seule, SANS badge de confiance (décision explicite : le diagramme
reste lisible, le détail source/confiance vit dans le tableau d'hypothèses
du rapport, pas dupliqué ici).
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
skinparam ComponentFontSize 16
skinparam DatabaseBackgroundColor #FFFFFF
skinparam DatabaseBorderColor #E5E7EB
skinparam DatabaseBorderThickness 2
skinparam DatabaseFontColor #111928
skinparam DatabaseFontSize 16
skinparam CloudBackgroundColor #FFFFFF
skinparam CloudBorderColor #E5E7EB
skinparam CloudBorderThickness 2
skinparam CloudFontColor #111928
skinparam CloudFontSize 16
skinparam RectangleBackgroundColor #FFFFFF
skinparam RectangleBorderColor #E5E7EB
skinparam RectangleBorderThickness 2
skinparam RectangleFontColor #111928
skinparam RectangleFontSize 16
skinparam NoteBackgroundColor #F9FAFB
skinparam NoteBorderColor #D1D5DB
skinparam NoteFontColor #111928
skinparam NoteFontSize 15
skinparam PackageBackgroundColor #F9FAFB
skinparam PackageBorderColor #D1D5DB
skinparam PackageFontColor #2D4675
skinparam PackageFontStyle bold
skinparam PackageFontSize 18
skinparam defaultFontName Arial
skinparam defaultFontColor #111928

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


# Caractères après lesquels une URL/un chemin peut être coupé proprement
# (le séparateur reste collé au morceau de GAUCHE, jamais en tête de ligne
# suivante) : segments de chemin (`/`), mots composés (`-`, `_`), requête
# (`?`, `&`, `=`), domaine (`.`).
_URL_BREAK_CHARS = frozenset("/?&=._-")


def _break_long_word(word, width):
    """Découpe un "mot" (sans espace, typiquement une URL) trop long pour
    `width`, en coupant APRÈS le séparateur le plus proche de `width` sans le
    dépasser (jamais au caractère près si un séparateur existe). Coupe brute
    à `width` en dernier recours, si aucun séparateur n'est trouvé dans la
    fenêtre."""
    chunks = []
    remaining = word
    while len(remaining) > width:
        break_at = width
        for i in range(min(width, len(remaining) - 1), 0, -1):
            if remaining[i - 1] in _URL_BREAK_CHARS:
                break_at = i
                break
        chunks.append(remaining[:break_at])
        remaining = remaining[break_at:]
    chunks.append(remaining)
    return chunks


def _wrap_segment(segment, width):
    """Replie une ligne (sans `\\n`) sur des frontières de MOTS (jamais au
    milieu d'un mot, comme un traitement de texte classique) ; un mot seul
    trop long pour `width` (typiquement une URL sans espace) est ensuite
    replié par `_break_long_word()` sur ses séparateurs naturels."""
    lines = []
    current = ""
    for word in segment.split(" "):
        candidate = f"{current} {word}" if current else word
        if len(candidate) <= width:
            current = candidate
            continue
        if current:
            lines.append(current)
        if len(word) <= width:
            current = word
        else:
            broken = _break_long_word(word, width)
            lines.extend(broken[:-1])
            current = broken[-1]
    if current:
        lines.append(current)
    return lines


def _wrap_label(text, width):
    """Replie `text` en lignes d'au plus `width` caractères, laisse `text`
    inchangé si `width` est None. Appeler APRÈS `_escape_label()` (le
    repliement n'introduit jamais de `--`).

    Coupe sur les frontières naturelles (mots séparés par un espace ; à
    défaut, séparateurs d'URL `/`, `-`, `_`, `.`, `?`, `&`, `=`) plutôt qu'au
    caractère près (cf. `_wrap_segment()`/`_break_long_word()`).

    Chaque ligne de continuation (jamais la première) est préfixée d'un
    espace SI elle commence par un caractère creole PlantUML (`=`, `-`, `*`,
    `#`, `_`) : PIÈGE TESTÉ, pas supposé — une ligne commençant par `=`
    (notamment issu d'une URL du type `?lang=fr` coupée en `lang`/`=fr`) est
    interprétée comme un titre H1 (rendu gras centré) au lieu du texte
    littéral attendu. L'espace neutralise l'interprétation sans autre effet
    visuel notable. Le découpage sur séparateurs naturels rend ce cas rare
    (le séparateur reste collé au morceau de gauche), le garde-fou reste
    nécessaire pour la coupe brute de dernier recours."""
    if not text or width is None:
        return text
    wrapped_segments = []
    for segment in text.split("\\n"):
        lines = _wrap_segment(segment, width) if len(segment) > width else [segment]
        safe_lines = [
            line if i == 0 or not line or line[0] not in "=-*#_" else f" {line}"
            for i, line in enumerate(lines)
        ]
        wrapped_segments.append("\\n".join(safe_lines))
    return "\\n".join(wrapped_segments)


def _format_seconds(traced):
    """Temps utilisateur d'une étape, lisible ("~28 s"), ou None si absent.
    Valeur seule, sans source/confiance (cf. docstring du module)."""
    if traced is None or traced.value is None:
        return None
    return f"~{traced.value:.0f} s"


def _format_bytes(traced):
    """Poids transféré d'un traitement, lisible en kB ("~180 kB"), ou None si
    absent. `data_transferred.unit` varie selon l'appelant du modèle ("B" en
    octets depuis from_har.py, "kB" depuis les archétypes de démo) : lire
    l'unité plutôt que supposer un octet fixe, sous peine d'un facteur 1000
    d'erreur silencieuse."""
    if traced is None or traced.value is None:
        return None
    unit = (traced.unit or "").strip().lower()
    if unit in ("b", "byte", "bytes"):
        kb_value = traced.value / 1000
    elif unit in ("kb",):
        kb_value = traced.value
    elif unit in ("mb",):
        kb_value = traced.value * 1000
    else:
        kb_value = traced.value
    return f"~{kb_value:.0f} kB transférés"


def _format_server_infra(server):
    """Type d'instance + provider si connu (cloud public via Boavizta),
    sinon le type de serveur générique (autoscaling/serverless/on_premise).
    Valeur seule, sans source/confiance (cf. docstring du module)."""
    if server.instance_type and server.instance_type.value:
        provider = server.provider.value if server.provider and server.provider.value else None
        return f"{server.instance_type.value} ({provider})" if provider else server.instance_type.value
    if server.server_type and server.server_type.value:
        return server.server_type.value
    return None


def _global_hypotheses_note(spec, audience_mix=None):
    """Lignes d'une note PlantUML récapitulant les hypothèses transverses :
    trafic annuel, mix appareils, mix pays d'audience, temps de lecture total
    cumulé du parcours. Retourne None si aucune de ces hypothèses n'est
    disponible (spec sans AudienceSpec, ex. archétype de démo minimal).

    `audience_mix` (dict {code_pays: part}) est un paramètre SÉPARÉ de
    `spec.audience` : le mix pays d'audience vient de env-data.json
    (SimilarWeb), jamais de la SiteSpec elle-même (AudienceSpec.country_mix
    existe mais n'est peuplé par aucun adaptateur actuellement) — cf.
    run_efootprint.py::build_topology_overview()."""
    lines = []
    audience = spec.audience
    if audience and audience.visits_per_year and audience.visits_per_year.value:
        lines.append(f"Trafic annuel estimé : {audience.visits_per_year.value:,.0f} visites".replace(",", " "))
    if audience and audience.phone_fraction and audience.desktop_fraction:
        lines.append(
            f"Mix appareils : {audience.phone_fraction.value:.0%} mobile / "
            f"{audience.desktop_fraction.value:.0%} desktop")
    if audience_mix:
        top = sorted(audience_mix.items(), key=lambda kv: kv[1], reverse=True)
        lines.append("Mix pays d'audience : " + ", ".join(f"{cc} {w:.0%}" for cc, w in top))
    total_user_time = sum(
        step.user_time.value for step in spec.steps if step.user_time and step.user_time.value)
    if total_user_time:
        lines.append(f"Temps de lecture cumulé du parcours : ~{total_user_time:.0f} s")
    return lines or None


def _build_links(spec, step_alias, job_alias, server_alias):
    """Lignes des liens visibles étape -> traitement déclenché, traitement ->
    serveur."""
    lines = []
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
    return lines


def site_to_plantuml(spec, *, title=None, wrap_width=30, audience_mix=None, step_shares=None):
    """Génère le texte PlantUML d'une `SiteSpec`, en 3 colonnes reprenant la
    disposition de l'interface e-footprint (model_builder) : "Parcours"
    (JourneySpec/StepSpec), "Traitements" (JobSpec, dont les appels IA
    générative), "Infrastructure" (ServerSpec, hôtes tiers) — colonnes côte à
    côte, plus hautes que larges (cf. docstring du module).

    Affiche aussi les grandes hypothèses de calcul : une note globale
    (trafic annuel, mix appareils, mix pays via `audience_mix`, temps de
    lecture cumulé) et un détail par composant (temps de l'étape, poids
    transféré du traitement, instance/provider du serveur).

    step_shares : {step_key: pct_of_grand_total} optionnel, cf.
    `build.py::step_impact_shares()`. Absent AVANT le calcul (Étape 25, vue
    d'ensemble) : la part d'impact n'existe qu'une fois le CO2e effectivement
    calculé. Fourni après (Étape 40) pour afficher, en plus du temps déjà
    présent, la part ESTIMÉE (répartition proportionnelle, pas une mesure
    indépendante) de chaque étape dans le total CO2e du site.

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

    def wrapped(text):
        return _wrap_label(_escape_label(text), wrap_width)

    package_order = []  # alias de chaque package de tête (pour le chaînage -[hidden]r-)

    # --- Colonne 1 : Parcours (JourneySpec regroupant des StepSpec) --------
    if spec.journeys:
        pkg_alias = "pkg_parcours"
        package_order.append(pkg_alias)
        lines.append(f'package "Parcours" as {pkg_alias} {{')
        for journey in spec.journeys:
            journey_alias = _sanitize_alias(f"jrn_{journey.key}")
            lines.append(f'  package "{wrapped(journey.label)}" as {journey_alias} {{')
            step_aliases_in_journey = []
            for step_key in journey.steps:
                step = spec.step_by_key(step_key)
                alias = step_alias[step.key]
                step_aliases_in_journey.append(alias)
                step_label = step.label
                user_time_txt = _format_seconds(step.user_time)
                if user_time_txt:
                    step_label = f"{step_label}\\n{user_time_txt}"
                if step_shares and step.key in step_shares:
                    step_label = f"{step_label}\\n~{step_shares[step.key] * 100:.0f} % du CO2e"
                lines.append(f'    rectangle "{wrapped(step_label)}" as {alias}')
            for a, b in zip(step_aliases_in_journey, step_aliases_in_journey[1:]):
                lines.append(f"    {a} -[hidden]d- {b}")
            lines.append("  }")
        lines.append("}")
        lines.append("")

    # --- Colonne 2 : Traitements (JobSpec, dont appels IA générative) ------
    ai_jobs = [job for job in spec.jobs if job.external_api is not None]
    network_only_jobs = [job for job in spec.jobs if job.external_api is None]

    if network_only_jobs:
        pkg_alias = "pkg_traitements"
        package_order.append(pkg_alias)
        lines.append(f'package "Traitements" as {pkg_alias} {{')
        job_aliases_here = [job_alias[job.key] for job in network_only_jobs]
        for job in network_only_jobs:
            alias = job_alias[job.key]
            job_label = job.label
            weight_txt = _format_bytes(job.data_transferred)
            if weight_txt:
                job_label = f"{job_label}\\n{weight_txt}"
            lines.append(f'  [{wrapped(job_label)}] as {alias}')
        for a, b in zip(job_aliases_here, job_aliases_here[1:]):
            lines.append(f"  {a} -[hidden]d- {b}")
        lines.append("}")
        lines.append("")

    if ai_jobs:
        pkg_alias = "pkg_ia"
        package_order.append(pkg_alias)
        lines.append(f'package "Appels IA générative (empreinte calculée via EcoLogits)" as {pkg_alias} {{')
        job_aliases_here = [job_alias[job.key] for job in ai_jobs]
        for job in ai_jobs:
            alias = job_alias[job.key]
            api = job.external_api
            label = f"{job.label}\\n{api.provider}/{api.model_name}"
            weight_txt = _format_bytes(job.data_transferred)
            if weight_txt:
                label = f"{label}\\n{weight_txt}"
            lines.append(f'  cloud "{wrapped(label)}" as {alias}')
        for a, b in zip(job_aliases_here, job_aliases_here[1:]):
            lines.append(f"  {a} -[hidden]d- {b}")
        lines.append("}")
        lines.append("")

    # --- Colonne 3 : Infrastructure (ServerSpec, hôtes tiers) ---------------
    pkg_alias = "pkg_infra"
    package_order.append(pkg_alias)
    lines.append(f'package "Infrastructure" as {pkg_alias} {{')
    server_aliases_here = [server_alias[server.key] for server in spec.servers]
    for server in spec.servers:
        alias = server_alias[server.key]
        server_label = server.label
        infra_txt = _format_server_infra(server)
        if infra_txt:
            server_label = f"{server_label}\\n{infra_txt}"
        lines.append(f'  database "{wrapped(server_label)}" as {alias}')
    for a, b in zip(server_aliases_here, server_aliases_here[1:]):
        lines.append(f"  {a} -[hidden]d- {b}")
    lines.append("}")
    lines.append("")

    if spec.third_party_hosts:
        pkg_alias = "pkg_tiers"
        package_order.append(pkg_alias)
        lines.append(f'package "Hôtes tiers (réseau seulement)" as {pkg_alias} {{')
        tp_aliases_here = []
        for host in spec.third_party_hosts:
            alias = _sanitize_alias(f"tp_{host.host}")
            tp_aliases_here.append(alias)
            label = host.host if not host.note else f"{host.host}\\n({host.note})"
            lines.append(f'  cloud "{wrapped(label)}" as {alias}')
        for a, b in zip(tp_aliases_here, tp_aliases_here[1:]):
            lines.append(f"  {a} -[hidden]d- {b}")
        lines.append("}")
        lines.append("")

    # --- Liens invisibles entre packages : colonnes côte à côte sans
    # `left to right direction` (cf. docstring du module) -------------------
    for a, b in zip(package_order, package_order[1:]):
        lines.append(f"{a} -[hidden]r- {b}")
    lines.append("")

    # --- Liens visibles : étape -> traitement déclenché, traitement -> serveur
    lines.extend(_build_links(spec, step_alias, job_alias, server_alias))

    # --- Légende globale : hypothèses transverses ---------------------------
    # `legend bottom` (pleine largeur, sous le diagramme), PAS une `note`
    # flottante : testé, une note sans ancrage reçoit une largeur arbitraire
    # bien trop étroite du moteur de layout (un mot par ligne, illisible).
    hyp_lines = _global_hypotheses_note(spec, audience_mix=audience_mix)
    if hyp_lines:
        lines.append("")
        lines.append("legend bottom")
        lines.append("<b>Hypothèses de calcul</b>")
        for hyp_line in hyp_lines:
            escaped = _escape_label(hyp_line)
            lines.append(escaped if not escaped or escaped[0] not in "=-*#_" else f" {escaped}")
        lines.append("end legend")

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
    puml = site_to_plantuml(frag, audience_mix={"FR": 0.8, "BE": 0.2})
    assert "@startuml" in puml and "@enduml" in puml, "diagramme mal formé"
    assert puml.count("database") == len(frag.servers), \
        "un composant database par serveur attendu"
    assert "left to right direction" not in puml, \
        "cette disposition ne doit jamais réintroduire left to right direction"
    assert "Hypothèses de calcul" in puml, "note globale d'hypothèses attendue"
    for line in puml.splitlines():
        stripped = line.strip()
        if stripped and stripped[0] in "=-*#_":
            raise AssertionError(
                f"ligne repliée commençant par un caractère creole PlantUML : {stripped!r}")
    print(puml)
    print()
    print(f"OK : diagramme généré, {len(frag.servers)} serveur(s), "
          f"{len(frag.jobs)} traitement(s), {len(frag.steps)} étape(s).")
