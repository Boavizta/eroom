---
name: eof
description: >
  Génère ou régénère le template Markdown vierge du référentiel EOF-V.1.1
  (EROOM Optimization Framework) à partir de sa Google Sheet source, avec un
  exemple de radar SVG pour la synthèse. S'active quand l'utilisateur
  mentionne "EOF", "EROOM Optimization Framework", "référentiel EOF",
  "template EOF", "radar EOF", ou "/eof". Périmètre actuel : uniquement la
  fabrication du template vierge (pas encore le remplissage d'un audit réel
  ni son intégration au rapport HTML d'analyse-parcours — cf. "Ce que ce
  skill ne fait pas encore").
version: 1.0.0
---

# Skill : EOF (EROOM Optimization Framework)

## Vue d'ensemble

EOF-V.1.1 est un référentiel d'auto-évaluation de la maturité d'optimisation
d'un service numérique (9 onglets : présentation, un diagnostic rapide à 16
critères, 6 piliers détaillés totalisant 54 critères, une synthèse). Il
existe sous forme de **Google Sheet publique**, source de vérité :
https://docs.google.com/spreadsheets/d/1zJkT_5Ck9WKyxHZ7Uf5f03PmsaLh_SUB7LzKToPlcZ0/edit

Ce skill produit un **template Markdown vierge** de ce référentiel, pour
pouvoir y répondre directement dans un fichier texte plutôt que dans
l'interface Google Sheets.

## Ce que ce skill ne fait pas encore

- Remplir le template pour un cas réel (ex. octo.com) à partir de données
  d'audit déjà collectées (analyse-parcours, e-footprint).
- Calculer un radar avec de vraies valeurs.
- S'intégrer au rapport HTML produit par `analyse-parcours` (`generate_report_html.py`).

Ces trois points sont cadrés (cf. `tmp/handoff.md` le plus récent au moment
de la rédaction) mais pas implémentés : à faire dans une session dédiée, le
travail de classification critère par critère est volumineux.

## Invocation

`/eof` ou toute demande de régénérer/mettre à jour le template EOF.

## Étapes

### 1. La source de vérité est versionnée : ne pas la retélécharger sans raison

L'export brut des 9 onglets est conservé dans **`docs/source-sheet/`**, versionné, avec
son propre `README.md`. C'est la photocopie de la Sheet au **2026-09-02**, et c'est le
seul point de comparaison permettant de savoir si EROOM a fait évoluer son référentiel.

Vérifier si la Sheet a bougé, sans rien modifier :

```bash
.claude/skills/eof/scripts/verifier_source_sheet.sh
```

Code de sortie 0 si la Sheet est identique à la photocopie, 1 si un onglet a changé ou si
un téléchargement échoue. Le script détecte aussi une Sheet devenue privée ou un onglet
supprimé, cas qui renvoient du HTML avec un code 200 et se compareraient sinon en silence.

Pour adopter une évolution, puis voir exactement ce qu'EROOM a changé :

```bash
.claude/skills/eof/scripts/verifier_source_sheet.sh --rafraichir
git diff .claude/skills/eof/docs/source-sheet/
```

La Sheet évolue réellement : vérifié le 02/09/2026, elle avait été enrichie de 43 à 54
critères détaillés depuis l'export Excel initialement fourni par EROOM.

Le script porte l'identifiant de la Sheet et les 9 `gid` d'onglets. L'API `gviz` est
obligatoire, les exports CSV et XLSX classiques échouent sur une redirection à jeton à
usage unique. La recette brute, pour mémoire :

```bash
BASE="https://docs.google.com/spreadsheets/d/1zJkT_5Ck9WKyxHZ7Uf5f03PmsaLh_SUB7LzKToPlcZ0/gviz/tq?tqx=out:json"
curl -sL -A "Mozilla/5.0" "${BASE}&gid=1677462955" -o .claude/skills/eof/docs/source-sheet/a-lire.json
curl -sL -A "Mozilla/5.0" "${BASE}&gid=296916801"  -o .claude/skills/eof/docs/source-sheet/diag-rapide.json
curl -sL -A "Mozilla/5.0" "${BASE}&gid=2022239731" -o .claude/skills/eof/docs/source-sheet/produit.json
curl -sL -A "Mozilla/5.0" "${BASE}&gid=615231881"  -o .claude/skills/eof/docs/source-sheet/architecture.json
curl -sL -A "Mozilla/5.0" "${BASE}&gid=1603246930" -o .claude/skills/eof/docs/source-sheet/infrastructure.json
curl -sL -A "Mozilla/5.0" "${BASE}&gid=31675448"   -o .claude/skills/eof/docs/source-sheet/stockage.json
curl -sL -A "Mozilla/5.0" "${BASE}&gid=1046049603" -o .claude/skills/eof/docs/source-sheet/algo-code.json
curl -sL -A "Mozilla/5.0" "${BASE}&gid=24436077"   -o .claude/skills/eof/docs/source-sheet/facilite.json
curl -sL -A "Mozilla/5.0" "${BASE}&gid=958616182"  -o .claude/skills/eof/docs/source-sheet/synthese.json
```

⚠️ Ces JSON étaient auparavant dans `tmp/eof-gviz/`, dossier ignoré par git, donc
sauvegardés nulle part. Il en reste une copie à cet endroit, sans valeur : la référence
est désormais `docs/source-sheet/`. Ne jamais réintroduire un chemin sous `tmp/` ici, ce
serait perdre le point de comparaison avec la Sheet d'EROOM.

### 2. Construire le template Markdown

```bash
python3 .claude/skills/eof/scripts/build_template.py \
  ".claude/skills/eof/docs/source-sheet" \
  ".claude/skills/eof/docs/EOF-V.1.1 (EROOM Optimization Framework) - Template - Français/EOF-V.1.1 (EROOM Optimization Framework) - Référentiel complet.md"
```

Le script est déterministe (aucun calcul ni transcription par un modèle) :
il lit les 9 JSON, détecte automatiquement le format d'évaluation par onglet
(3 formats différents existent — cf. `build_template.py` en tête de fichier),
et écrit un template **100 % vierge** (aucune case pré-cochée, sauf "Niveau
d'impact" qui porte une donnée fixe du référentiel, pas une réponse).

### 3. (Optionnel) Régénérer un exemple de radar

```bash
python3 .claude/skills/eof/scripts/generate_radar_svg.py sortie.svg
```

Produit un radar SVG à 6 axes (grille circulaire, bleu marine `#2D4675`,
contraste ~9,35:1 conforme RGAA) avec des valeurs fictives — utile pour
prévisualiser le rendu avant de calculer un vrai radar sur un cas réel.

## Fichiers

- `scripts/build_template.py` — génère le template Markdown depuis les JSON gviz
- `scripts/generate_radar_svg.py` — génère un radar SVG (fonction `radar_svg()` réutilisable)
- `docs/EOF-V.1.1 (EROOM Optimization Framework) - Template - Français/`
  - `EOF-V.1.1 ... (1).xlsx` — Excel fourni en secours (partiellement périmé, cf. § récupération)
  - `EOF-V.1.1 ... Référentiel complet.md` — le template vierge livré
  - `logo1.png` / `logo2.png` — logos extraits de l'Excel (logo1 blanc/transparent, invisible sur fond blanc, signalé dans le .md)
- `docs/Essai version univocite/` — ancien doc "diagnostic rapide univoque", **hors périmètre**, ne pas retravailler

## Diagramme

`documentation/diagrammes/eof-pipeline-outils.puml/.svg/.pdf` (2 pages) — registre
dans `.claude/skills/diagrammes-analyse-parcours/SKILL.md`, section "Diagramme 5".
