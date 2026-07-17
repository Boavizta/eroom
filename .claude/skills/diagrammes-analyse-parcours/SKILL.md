---
name: diagrammes-analyse-parcours
description: >
  Génère ou met à jour les diagrammes PlantUML du projet analyse-parcours.
  Registre de tous les diagrammes existants, leur source de vérité et les
  commandes de régénération. Invoquer quand un fichier source change ou
  quand un nouveau diagramme doit être créé.
triggers:
  - "diagramme analyse-parcours"
  - "diagramme séquence analyse"
  - "diagramme eroom"
  - "schéma workflow parcours"
  - "mets à jour les diagrammes"
  - "régénère les diagrammes"
  - "/diagrammes-analyse-parcours"
version: 1.0.0
---

# Skill : Diagrammes — Analyse de parcours web

## Registre des diagrammes

| Diagramme | Fichiers source (`.puml`) | Fichiers produits | Source de vérité | Régénérer si... |
|-----------|--------------------------|-------------------|------------------|-----------------|
| Workflow principal (3 pages) | `analyse-parcours-p1.puml` `analyse-parcours-p2.puml` `analyse-parcours-p3.puml` | `analyse-parcours-workflow.pdf` | `analyse-parcours/SKILL.md` | SKILL.md change (étapes, participants) |
| DISPATCH — flux vagues (activité) | `analyse-parcours-dispatch-activite.puml` | `analyse-parcours-dispatch-activite.pdf` | `skill-steps/25_dispatch-orchestration.md` | `25_dispatch-orchestration.md` change (vagues, dispatches) |

Tous les fichiers `.puml` et les sorties se trouvent dans `diagramme/` à la racine du projet.

-----

## Procédure générale de régénération

Pour chaque diagramme modifié :
1. Modifier le `.puml` dans `diagramme/` en cohérence avec la source de vérité
2. Générer le SVG : `plantuml -tsvg <fichier>.puml`
3. Convertir en PDF via `rsvg-convert`
4. Vérifier + ouvrir

**Ne jamais générer directement en PNG ou PDF depuis plantuml.** Toujours passer par SVG (vecteur) puis `rsvg-convert` pour le PDF.

-----

## Diagramme 1 — Workflow principal (séquence)

**Source de vérité :** `analyse-parcours/SKILL.md` (sections Étape 10 à Étape 40)

### Structure des 3 fichiers

| Fichier | Participants | Étapes couvertes |
|---------|--------------|-----------------|
| `analyse-parcours-p1.puml` | U, C, FS | Étapes 10+15 — Localisation + Capture sessionId |
| `analyse-parcours-p2.puml` | U, C, SA, EI, FS | Étapes 25+35 — DISPATCH + EcoIndex |
| `analyse-parcours-p3.puml` | U, C, GR, FS | Étape 40 — Rapport HTML |

Découpage en 3 fichiers séparés : chaque page n'affiche que les participants actifs
(la technique `newpage` dans un mono-fichier ne réduit pas les colonnes).

### Commandes

```bash
plantuml -tsvg diagramme/analyse-parcours-p1.puml \
         diagramme/analyse-parcours-p2.puml \
         diagramme/analyse-parcours-p3.puml
rsvg-convert -f pdf -o diagramme/analyse-parcours-workflow.pdf \
  diagramme/analyse-parcours-p1.svg \
  diagramme/analyse-parcours-p2.svg \
  diagramme/analyse-parcours-p3.svg
ls -lh diagramme/analyse-parcours-workflow.pdf
open diagramme/analyse-parcours-workflow.pdf
```

### Contenu de référence — analyse-parcours-p1.puml

```plantuml
@startuml analyse-parcours-p1
title Workflow Analyse de parcours web — Page 1/3 : Étapes 10+15 Localisation + SessionId

skinparam backgroundColor #FFFFFF
skinparam participant {
  BackgroundColor #E0F0F4
  BorderColor #5BA1BC
  FontColor #1C2856
}
skinparam actor {
  BackgroundColor #E0F0F4
  BorderColor #5BA1BC
  FontColor #1C2856
}
skinparam ArrowColor #5BA1BC
skinparam SequenceLifeLineBorderColor #5BA1BC
skinparam SequenceGroupBodyBackgroundColor #ECECF2
skinparam SequenceGroupBorderColor #5BA1BC
skinparam NoteBackgroundColor #E0F0F4
skinparam NoteBorderColor #9BD0DD
skinparam sequenceMessageAlign center
skinparam maxMessageSize 200
skinparam responseMessageBelowArrow true

actor "Utilisateur" as U #82C1DD
participant "Claude\n(skill analyse-parcours)" as C #82C1DD
database "dossier-audit/" as FS #9BD0DD

== Étape 10 — Localisation des fichiers ==

U -> C : /analyse-parcours <dossier> ou <fichier.har> [coverage.json ...]
C -> C : Extraire chemin(s) du prompt

alt Dossier fourni
  C -> FS : Lister contenu
  FS -> C : Fichiers trouvés
  C -> C : Identifier .har + Coverage-*.json + cwv.json (optionnel)
  alt Plusieurs .har trouvés
    C -> U : Lequel utiliser ?
    U -> C : Choix
  end
else Fichiers directs fournis
  C -> FS : Vérifier existence de chaque fichier
  FS -> C : OK / erreur
else Aucun argument
  C -> U : Quel dossier ou fichiers HAR/Coverage analyser ?
  U -> C : Chemin(s)
end

C -> U : Synthèse fichiers identifiés :\n- HAR : <nom> ([N] Ko)\n- Coverage : [N] fichier(s)\n- cwv.json : présent / absent

note over C, FS
  Sécurité HAR :
  Ne jamais afficher credentials ni tokens en clair.
  Masquer : {"password":"***"}, token=****...abc
  Tronquer les UIDs : uid=8116...92
end note

== Étape 15 — Capture sessionId (silencieux) ==

C -> FS : mkdir -p <HAR_DIR>/analyse-interne-agent
C -> FS : cp ~/.claude/.current_session_id\nanalyse-interne-agent/.session_id

note over C, FS
  Utilisé par patch-audit-cost.sh (Étape 40)
  pour calculer le coût exact de la session
  au lieu d'une estimation par fenêtre temporelle.
end note

@enduml
```

### Contenu de référence — analyse-parcours-p2.puml

```plantuml
@startuml analyse-parcours-p2
title Workflow Analyse de parcours web — Page 2/3 : DISPATCH + EcoIndex

skinparam backgroundColor #FFFFFF
skinparam participant {
  BackgroundColor #E0F0F4
  BorderColor #5BA1BC
  FontColor #1C2856
}
skinparam actor {
  BackgroundColor #E0F0F4
  BorderColor #5BA1BC
  FontColor #1C2856
}
skinparam ArrowColor #5BA1BC
skinparam SequenceLifeLineBorderColor #5BA1BC
skinparam SequenceGroupBodyBackgroundColor #ECECF2
skinparam SequenceGroupBorderColor #5BA1BC
skinparam NoteBackgroundColor #E0F0F4
skinparam NoteBorderColor #9BD0DD
skinparam sequenceMessageAlign center
skinparam maxMessageSize 200
skinparam responseMessageBelowArrow true

actor "Utilisateur" as U #82C1DD
participant "Claude\n(skill analyse-parcours)" as C #82C1DD
participant "Sous-agents\n(HAR / Coverage)" as SA #C8E6C9
participant "har_metrics.py" as EI #DBDDE5
database "dossier-audit/" as FS #9BD0DD

== Étape 25 — Détection capacités DISPATCH ==

C -> C : Sous-agents disponibles ?\n(Claude Code -> OUI, autres -> séquentiel)

== Wave 1 — Analyse HAR + Coverage (en parallèle) ==

par
  C -> SA : :::dispatch analyse-har\n(20_analyse-har.md)
  SA -> FS : Lire .har\n(par lots si > 5 Mo)
  SA -> SA : 20a — trafic (requêtes, domaines,\ncodes HTTP, volume)
  SA -> SA : 20b — performance (cache,\ndoublons, ressources bloquantes)
  SA -> FS : har-analysis.json
else
  C -> SA : :::dispatch analyse-coverage\n(30_analyse-coverage.md)
  SA -> FS : Lire Coverage-*.json
  SA -> SA : Détecter format A ou B
  SA -> SA : Métriques JS/CSS par page\n(total, inutilisé, %)
  SA -> SA : Synthèse multi-pages + outliers
  SA -> FS : coverage-analysis.json
end

note over C, SA
  Mode plateforme :
  Claude Code -> sous-agents natifs (fenêtres contexte isolées)
  Autres plateformes -> exécution séquentielle inline
  Résultat disque identique dans les deux cas
end note

== Merge Wave 1 ==

C -> FS : Lire har-analysis.json
FS -> C : Données trafic réseau
C -> FS : Lire coverage-analysis.json
FS -> C : Données code mort JS/CSS

== Étape 35 — Calcul EcoIndex (contexte principal) ==

C -> EI : python3 har_metrics.py <har> [cwv.json]
EI -> EI : Extraire DOM HTML depuis\nresponse.content.text
EI -> EI : Compter requêtes + poids\npar page (pageref)
EI -> C : Tableau : score/grade/req/Ko/DOM\npar page + onLoad

note over C, EI
  Limites :
  - DOM=0 si HAR sans corps HTML\n    (response.content.text absent)
  - SPA : DOM = état initial seulement\n    (pas après hydratation JS)
  Ces cas sont documentés dans le rapport.
end note

@enduml
```

### Contenu de référence — analyse-parcours-p3.puml

```plantuml
@startuml analyse-parcours-p3
title Workflow Analyse de parcours web — Page 3/3 : Rapport HTML

skinparam backgroundColor #FFFFFF
skinparam participant {
  BackgroundColor #E0F0F4
  BorderColor #5BA1BC
  FontColor #1C2856
}
skinparam actor {
  BackgroundColor #E0F0F4
  BorderColor #5BA1BC
  FontColor #1C2856
}
skinparam ArrowColor #5BA1BC
skinparam SequenceLifeLineBorderColor #5BA1BC
skinparam SequenceGroupBodyBackgroundColor #ECECF2
skinparam SequenceGroupBorderColor #5BA1BC
skinparam NoteBackgroundColor #E0F0F4
skinparam NoteBorderColor #9BD0DD
skinparam sequenceMessageAlign center
skinparam maxMessageSize 200
skinparam responseMessageBelowArrow true

actor "Utilisateur" as U #82C1DD
participant "Claude\n(skill analyse-parcours)" as C #82C1DD
participant "generate_report_html.py" as GR #DBDDE5
database "dossier-audit/" as FS #9BD0DD

== Étape 40 — Rapport HTML ==

C -> GR : python3 generate_report_html.py <dossier-audit>
GR -> FS : Lire .har
FS -> GR : Trafic réseau brut
GR -> FS : Lire coverage-analysis.json
FS -> GR : Métriques code mort JS/CSS
GR -> FS : Lire cwv.json (si présent)
FS -> GR : LCP / INP / CLS par page

note over GR, FS
  Sections du rapport (dans l'ordre) :
  1. En-tête : date, domaines, nb pages, fichiers source
  2. Tableau de bord EcoIndex (grade A-G, score, req, Ko, DOM)
  3. Trafic réseau (KPIs, domaines, codes HTTP, top 10, doublons)
  4. Code mort (jauges JS/CSS par page, top 8 fichiers)
  5. Core Web Vitals (si cwv.json — LCP/INP/CLS avec seuils Google)
  6. Recommandations priorisées (P1 rouge / P2 orange / P3 vert)
  Si cwv.json absent : LCP affiche onLoad HAR avec note explicite.
end note

GR -> C : rapport-parcours-YYYY-MM-DD.html
C -> C : open rapport-parcours-YYYY-MM-DD.html
C -> U : Rapport livré :\n<dossier-audit>/rapport-parcours-YYYY-MM-DD.html

@enduml
```

-----

## Diagramme 2 — DISPATCH (flux vagues d'analyse)

**Source de vérité :** `skill-steps/25_dispatch-orchestration.md`

### Description

Diagramme d'activité (syntaxe beta PlantUML) avec `fork` / `fork again` / `end fork`.
Représente le flux vertical des vagues avec les branches parallèles.
Mono-fichier, une seule page.

### Structure

```
Wave 0  — Localisation (contexte principal)
Wave 1  — Analyse HAR + Analyse Coverage en parallèle (2 sous-agents)
Merge   — lecture har-analysis.json + coverage-analysis.json
Suite   — Étape 35 EcoIndex + Étape 40 Rapport HTML (contexte principal)
```

### Commandes

```bash
plantuml -tsvg diagramme/analyse-parcours-dispatch-activite.puml
rsvg-convert -f pdf -o diagramme/analyse-parcours-dispatch-activite.pdf \
  diagramme/analyse-parcours-dispatch-activite.svg
ls -lh diagramme/analyse-parcours-dispatch-activite.pdf
open diagramme/analyse-parcours-dispatch-activite.pdf
```

### Contenu de référence — analyse-parcours-dispatch-activite.puml

```plantuml
@startuml analyse-parcours-dispatch-activite
title Mécanisme DISPATCH — Flux des vagues d'analyse de parcours

skinparam backgroundColor #FFFFFF
skinparam activity {
  BackgroundColor #E0F0F4
  BorderColor #5BA1BC
  FontColor #1C2856
  DiamondBackgroundColor #E0F0F4
  DiamondBorderColor #5BA1BC
}
skinparam ArrowColor #5BA1BC
skinparam ActivityBarColor #5BA1BC
skinparam NoteBackgroundColor #E0F0F4
skinparam NoteBorderColor #9BD0DD
skinparam PartitionBackgroundColor #ECECF2
skinparam PartitionBorderColor #5BA1BC

|#E0F0F4| Contexte principal |
start

:SKILL.md -> lit 25_dispatch-orchestration.md;

note right
  Détection plateforme :
  - Claude Code -> sous-agents isolés (parallèle)
  - Autres -> exécution séquentielle inline
end note

partition "**Wave 0 — Localisation** (contexte principal)" {
  :Lire args : dossier ou fichiers directs;
  :Identifier .har + Coverage-*.json + cwv.json (optionnel);
  :Vérifier existence + taille HAR\n(lecture sélective si > 5 Mo);
}

note right #C8E6C9
  ✅ Wave 0 terminée — fichiers prêts
  Les dispatches suivants lisent les fichiers disque.
end note

partition "**Wave 1 — HAR + Coverage** (2 sous-agents en parallèle)" {
  fork
    :Dispatch A — Analyse HAR
    (20_analyse-har.md)
    20a — trafic (requêtes, domaines,
    codes HTTP, volume Mo)
    20b — performance (cache,
    doublons, ressources bloquantes)
    -> har-analysis.json;
  fork again
    :Dispatch B — Analyse Coverage
    (30_analyse-coverage.md)
    Format A ou B détecté
    Métriques JS/CSS par page
    (total Ko, inutilisé Ko, %)
    Top 5 JS + Top 3 CSS inutilisés
    Synthèse multi-pages + outliers
    -> coverage-analysis.json;
  end fork
}

note right
  Condition de réussite :
  har-analysis.json et coverage-analysis.json
  doivent exister avec données valides.
  Sinon : relancer le dispatch une fois.
end note

partition "**Merge + suite** (contexte principal)" {
  :Lire har-analysis.json + coverage-analysis.json;
  :Étape 35 — har_metrics.py
  Calcul score/grade A-G par page
  (formule officielle cnumr/ecoindex);

  note right
    Limites :
    DOM=0 si HAR sans corps HTML
    SPA : DOM = état initial seulement
    -> documenté dans le rapport
  end note

  :Étape 40 — generate_report_html.py
  Sections : EcoIndex, Trafic réseau,
  Code mort, CWV (si cwv.json),
  Recommandations P1/P2/P3
  -> rapport-parcours-YYYY-MM-DD.html;

  :open rapport + livrer chemin à l'utilisateur;
}

stop

@enduml
```

-----

## Palette de couleurs OCTO

| Nom           | Hex       | Usage                                  |
|---------------|-----------|----------------------------------------|
| OctoDark      | `#1C2856` | Titre, texte FontColor                 |
| OctoWhite     | `#FFFFFF` | Fond général                           |
| OctoLightGrey | `#DBDDE5` | Scripts Python (ecoindex, generate)    |
| OctoPaleGrey  | `#ECECF2` | Fond groupes / partitions              |
| OctoPaleBlue  | `#E0F0F4` | Participants par défaut                |
| OctoLightBlue | `#9BD0DD` | dossier-audit (database)              |
| OctoBlue      | `#82C1DD` | Utilisateur, Claude                    |
| OctoDarkBlue  | `#5BA1BC` | Flèches, bordures, lifelines           |
| OctoDarkGrey  | `#67708E` | (non utilisé ici)                      |
| OctoGrey      | `#888FA8` | Notes secondaires                      |
| (extra)       | `#C8E6C9` | Sous-agents DISPATCH (vert pâle)       |

### Skinparam obligatoire

```plantuml
skinparam backgroundColor #FFFFFF
skinparam participant {
  BackgroundColor #E0F0F4
  BorderColor #5BA1BC
  FontColor #1C2856
}
skinparam actor {
  BackgroundColor #E0F0F4
  BorderColor #5BA1BC
  FontColor #1C2856
}
skinparam ArrowColor #5BA1BC
skinparam SequenceLifeLineBorderColor #5BA1BC
skinparam SequenceGroupBodyBackgroundColor #ECECF2
skinparam SequenceGroupBorderColor #5BA1BC
skinparam NoteBackgroundColor #E0F0F4
skinparam NoteBorderColor #9BD0DD
skinparam sequenceMessageAlign center
skinparam maxMessageSize 200
skinparam responseMessageBelowArrow true
```

-----

## Règles rédactionnelles

- Conserver les accents français (é, è, ê, à, ç...).
- Labels de messages courts (< 60 caractères si possible).
- `alt` / `loop` / `note` / `partition` en français.
- **Interdire les doubles tirets `--` dans les labels.** PlantUML interprète `--texte--`
  comme du texte barré. Utiliser un seul tiret `-`.
  Vérifier : `grep "\-\-" diagramme/*.puml` doit retourner 0 occurrence dans les lignes `-> ... :`.
