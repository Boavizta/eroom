# Étape 39 - Potentiel d'optimisation (référentiel EOF)

## Vue d'ensemble

Cette étape remplit automatiquement ce qui peut l'être du référentiel
EOF-V.1.1 (EROOM Optimization Framework, Boavizta) pour le site audité, à
partir des données déjà collectées. Elle s'appuie sur :

- `eof-referentiel.json` : produit par le skill `.claude/skills/eof/`
  (54 critères détaillés sur 6 dimensions + 16 questions de
  0-Diagnostic rapide), **jamais régénéré depuis cette étape**
- `.claude/skills/analyse-parcours/scripts/eof_criteria_mapping.py` : table
  de correspondance critère → champ de donnée → règle → confidence
- `.claude/skills/analyse-parcours/scripts/run_eof.py` : évalue chaque
  critère, calcule les scores par dimension, génère le radar
- Trois extracteurs Phase 1 (2026-09-03, plan `eof-questionnaire`), à lancer
  AVANT `run_eof.py` :
  - `parse_html_criteria.py <source_dir>` — re-fetch live des pages déjà
    auditées (le `.har` capturé ne contient pas les corps HTML/CSS) : écrit
    `html-css-criteria.json`
  - `analyze_security_headers.py <source_dir>` — score sécurité local depuis
    les en-têtes déjà dans le `.har` : écrit `security-headers-analysis.json`
  - `scan_wellknown.py <source_dir>` — fetch direct security.txt/robots.txt/
    sitemap.xml : écrit `wellknown-scan.json`
- `collect_cwv_pagespeed.py` étendu (mêmes appels API PageSpeed Insights,
  catégories accessibility + best-practices en plus de performance) :
  ajoute `accessibility_score_pct` / `best_practices_score_pct` dans
  `cwv.json`. Relancer avec `--strategy both` si `cwv.json` a été généré
  avant cette extension.

**Cette étape ne lit JAMAIS la Google Sheet ni le Markdown humain du skill
`eof`** — découplage voulu (cf. `tmp/handoff.md`, plan d'architecture) pour
qu'une resynchronisation du référentiel ne puisse jamais casser la
comparabilité entre deux audits faits à des dates différentes.

-----

## AVERTISSEMENT OBLIGATOIRE

Sur les 54 critères détaillés, une reconnaissance manuelle (2026-09-03) a
montré que seuls **4 sont automatisables** (case cochée) et **6 partiels**
(indice contextuel affiché en annexe, jamais une réponse validée). Les
**44 autres restent "je ne sais pas"** par construction : ce sont des
questions organisationnelles ou produit (revues de code, tests,
documentation, connaissance des utilisateurs cibles...) qu'aucune donnée
technique d'audit ne peut renseigner.

Ce rappel doit apparaître :
- dans le résumé affiché à l'utilisatrice après l'exécution
- dans le bandeau d'avertissement de la section rapport (déjà géré par
  `_section_eof()`, ne pas le retirer)

Les 16 questions de 🏦 0-Diagnostic rapide ne sont **jamais** remplies
automatiquement (échelle 1 à 5 différente, décision explicite du
2026-09-03) : elles apparaissent en aperçu seulement, avant le radar des 6
dimensions détaillées.

-----

## Déclenchement

**Automatique**, pas une commande à taper : après l'Étape 37
(Lighthouse/CWV), avant l'Étape 40 (Rapport HTML) — pour que le premier
rapport généré contienne déjà cette section. Si `eof-referentiel.json` est
absent (skill `eof` jamais lancé), sauter silencieusement cette étape et
continuer vers l'Étape 40 sans section EOF (rapport rétrocompatible).

Relançable à tout moment (ex. après une nouvelle collecte de données) :

```bash
python3 .claude/skills/analyse-parcours/scripts/run_eof.py <source_dir>
```

-----

## Exécution

1. Vérifier la présence de
   `.claude/skills/eof/docs/EOF-V.1.1 (EROOM Optimization Framework) - Template - Français/eof-referentiel.json`.
   Absent -> signaler "référentiel EOF non trouvé, lancer le skill `eof` si
   une section EOF est souhaitée dans le rapport" et sauter l'étape.
2. Lancer `run_eof.py <source_dir>` (source_dir = dossier de l'audit,
   contenant `env-data.json`/`cwv.json`, avec son sous-dossier `audit/`
   pour `har-analysis.json`/`coverage-analysis.json`).
3. Le script écrit dans `<source_dir>/` :
   - `eof-audit-results.json` - résumé léger, consommé par
     `generate_report_html.py::_section_eof()`
   - `eof-rempli.md` - référentiel complet lisible (réponse ou "je ne sais
     pas", confidence, source, pour les 54 + aperçu des 16 de Diagnostic
     rapide)
   - `eof-radar-<domaine>.svg` - radar des 6 dimensions (une dimension sans
     aucune réponse s'affiche "N/A", jamais un faux 0 %)
4. Afficher le résumé stdout du script (nombre de critères répondus
   automatiquement / 54, potentiel d'optimisation global).

-----

## Intégration rapport HTML

`generate_report_html.py` détecte automatiquement `eof-audit-results.json`
et `eof-radar-*.svg` (dans `audit_dir` ou son parent) et insère une section
"Potentiel d'optimisation (référentiel EOF)" entre "Impact environnemental
(CO2e)" et "Annexes". Si `eof-audit-results.json` est absent, la section est
simplement omise.

Contenu de la section :
- Bandeau d'avertissement (ratio réel de couverture automatique)
- Aperçu 🏦 0-Diagnostic rapide (16 questions, jamais rempli, placé AVANT le
  radar)
- KPI : critères répondus / 54, potentiel d'optimisation global (moyenne
  pondérée, sur les réponses réelles uniquement)
- Radar des 6 dimensions détaillées
- Table des scores par dimension

Une **annexe** ("Détail des 54 critères EOF", dans la section Méthodologie
& hypothèses) trace critère par critère : réponse ou "je ne sais pas",
niveau de confiance (badges `_confidence_badge()`, mêmes codes que le reste
du rapport), source/donnée exploitée.

Régénération après changement de données :
```bash
python3 .claude/skills/analyse-parcours/scripts/run_eof.py <source_dir>
python3 .claude/skills/analyse-parcours/scripts/generate_report_html.py <source_dir>/audit
```

-----

## Ce qui reste explicitement HORS de cette étape

- Étendre l'automatisation aux critères "aucune donnée" : nature
  organisationnelle/produit, pas un défaut technique à corriger.
- Remplir automatiquement 🏦 0-Diagnostic rapide : décision explicite de ne
  pas le faire (échelle différente, jamais de donnée assez fiable).
- Modifier `eof-referentiel.json` ou la Google Sheet depuis cette étape :
  strictement réservé au skill `eof`, à la demande explicite seulement.

-----

## Décisions clés (référence)

- Découplage total avec le skill `eof` : cette étape ne lit que
  `eof-referentiel.json`, jamais la Sheet ni le Markdown humain.
- Table de correspondance générique (`eof_criteria_mapping.py`),
  réutilisable pour tout site audité — pas limitée à octo.com.
- Politique stricte anti-fabrication : "automatisable" peut cocher une
  case, "partiel" affiche seulement un indice en annexe (jamais coché),
  l'absence de la table = toujours "je ne sais pas".
- Radar : une dimension sans réponse affiche "N/A", jamais un faux 0 %
  (0 % signifierait "point fort partout", pas "inconnu").
