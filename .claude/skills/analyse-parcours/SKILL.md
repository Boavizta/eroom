---
name: analyse-parcours
description: >
  Ce skill s'active quand l'utilisateur veut "analyser un parcours web", "analyser un HAR",
  "analyser la couverture Chrome", "code mort JS/CSS",
  "coverage DevTools", "analyser le trafic d'un parcours",
  ou mentionne des fichiers .har ou Coverage-*.json issus de Chrome DevTools.
version: 1.0.0
---

# Analyse de parcours web (HAR + Coverage)

## Vue d'ensemble

Ce skill analyse un parcours web complet à partir de :
1. Un fichier **HAR** (HTTP Archive) - export du trafic réseau Chrome DevTools
2. Des fichiers **JSON de couverture** - export Chrome DevTools > Coverage (un fichier par page)

Il produit deux types d'analyse :
- **Trafic réseau** : requêtes, domaines, volumes, codes HTTP, performance
- **Performance/Éco** : EcoIndex (score + grade A-G), code mort JS/CSS, Core Web Vitals

**Documentation utilisateur** : `docs/capturer-har-et-coverage.md` - procédure pas à pas pour capturer un HAR, les fichiers Coverage et le fichier `cwv.json` optionnel.

**Fichier optionnel `cwv.json`** (Core Web Vitals mesurés manuellement) :
```json
[
  {"page": "page_1", "lcp": 0.76, "inp": 8, "cls": 0.06},
  {"page": "page_2", "lcp": 1.9,  "inp": 16, "cls": 0.66}
]
```
Si absent : le rapport affiche `onLoad` HAR comme proxy pour LCP.

---

## Invocation

```
/analyse-parcours <chemin-dossier>
/analyse-parcours <fichier.har> <coverage1.json> <coverage2.json> ...
```

Le skill est aussi déclenché automatiquement quand les triggers du `plugin.json` matchent.

---

## Étape 10 — Localisation des fichiers

→ Voir `skill-steps/10_localisation.md`

Extraire du prompt :
- Un chemin de **dossier** contenant les fichiers HAR et JSON
- Ou des chemins directs : `<fichier.har> [coverage1.json coverage2.json ...]`

Si aucun argument fourni : demander le chemin à l'utilisateur.

---

## Étape 20 — Analyse du fichier HAR

→ Voir `skill-steps/20_analyse-har.md`

Extraire du HAR :
- Vue d'ensemble du trafic (requêtes, domaines, codes HTTP, volume)
- Métriques de performance réseau (cache, doublons, ressources lourdes)

---

## Étape 25 — Orchestration DISPATCH

→ Voir `skill-steps/25_dispatch-orchestration.md`

Les étapes 20 (analyse HAR) et 30 (analyse Coverage) sont orchestrées en parallèle
via le mécanisme DISPATCH. Si les sous-agents sont disponibles (Claude Code), elles
s'exécutent dans des contextes isolés simultanément. Sinon, elles s'enchaînent inline.

Les sorties produites : `har-analysis.json` et `coverage-analysis.json` dans le dossier audit.

---

## Étape 30 — Analyse des fichiers de couverture

→ Voir `skill-steps/30_analyse-coverage.md`

Pour chaque fichier JSON de couverture :
- Métriques par page (taille totale, code non utilisé, taux %)
- Fichiers les plus coûteux (JS + CSS)
- Synthèse multi-pages

---

## Étape 35 — Calcul EcoIndex

→ Voir `skill-steps/35_calcul_ecoindex.md`

Calcul automatique depuis le HAR (formule officielle) :
- DOM extrait du corps HTML (`response.content.text`)
- Requêtes et poids agrégés par page
- Score 0-100 + grade A-G avec code couleur

```bash
python3 .claude/skills/analyse-parcours/scripts/har_metrics.py <fichier.har> [cwv.json]
```

---

## Étape 37 — CWV via Lighthouse

→ Voir `skill-steps/37_lighthouse.md`

Si `cwv.json` est absent : lancer automatiquement Lighthouse CLI via `npx` en extrayant
les URLs du HAR. Génère `cwv.json` avec LCP, INP, CLS mesurés en mode lab.
Si déjà présent : skippé. Si échec : warning et rapport sans CWV.
L'utilisateur peut forcer un re-run en disant "relance Lighthouse".

---

## Étape 40 — Rapport HTML

→ Voir `skill-steps/40_rapport.md`

Génère `rapport-parcours-YYYY-MM-DD.html` dans le dossier audit :

```bash
python3 .claude/skills/analyse-parcours/scripts/generate_report_html.py <dossier-audit>
```

Sections : EcoIndex | Trafic réseau | Code mort | CWV (si cwv.json) | Recommandations

---

## Maintenance des outils CLI

→ Voir `scripts/README-outils.md`

### Install initiale de Lighthouse (une seule fois)

```bash
npm install --prefix .claude/skills/analyse-parcours/scripts/
```

### Vérifier si Lighthouse est à jour

```bash
npm outdated --prefix .claude/skills/analyse-parcours/scripts/
```

### Mettre à jour Lighthouse

```bash
npm update lighthouse --prefix .claude/skills/analyse-parcours/scripts/
```

L'utilisateur peut dire à Claude "vérifie si Lighthouse est à jour" ou "mets à jour Lighthouse".
Claude exécute `npm outdated`, lit la sortie et propose ou exécute `npm update`.

---

## Règles transversales

### Taille des fichiers HAR

Les HAR peuvent dépasser 5 Mo (50 000+ lignes). Procéder par lecture sélective :
- Lire l'entête JSON pour connaître le nombre d'entrées
- Traiter les entrées par lots si nécessaire
- Ne pas charger l'intégralité en une seule passe

### Données sensibles

Si le HAR contient des credentials ou tokens :
- Ne **jamais** les afficher en clair
- Masquer : `{"password":"***"}`, `token=****...abc`
- Tronquer les UIDs : `uid=8116...92`

### Progression

Afficher une ligne de progression à chaque étape :
```
▶ Étape 10 — Localisation des fichiers
▶ Étape 20 — Analyse HAR ([N] requêtes)
▶ Étape 30 — Analyse Coverage ([N] pages)
▶ Étape 40 — Rapport de synthèse
```
