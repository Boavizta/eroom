# Outils CLI - analyse-parcours

## Lighthouse CLI

Utilisé pour calculer les Core Web Vitals (LCP, INP, CLS) à l'étape 37 du skill.

### Install initiale (une seule fois)

    npm install --prefix .claude/skills/analyse-parcours/scripts/

Installe Lighthouse localement dans `scripts/node_modules/`.
La version installée est tracée dans `package-lock.json`.

### Vérifier la version installée

    scripts/node_modules/.bin/lighthouse --version

### Vérifier si une mise à jour est disponible

    npm outdated --prefix .claude/skills/analyse-parcours/scripts/

Exemple de sortie :

    Package     Current  Wanted  Latest
    lighthouse  12.3.0   12.3.0  12.5.1

### Mettre à jour Lighthouse

    npm update lighthouse --prefix .claude/skills/analyse-parcours/scripts/

Ou demander à Claude : "vérifie si Lighthouse est à jour" / "mets à jour Lighthouse".

### Fonctionnement dans le skill

`run_lighthouse.sh` utilise en priorité le binaire local (`node_modules/.bin/lighthouse`).
Si l'install locale est absente, il bascule sur `npx` (version non fixée) et propose
de lancer `npm install` pour fixer la version.

La version utilisée est affichée dans les logs :

    [Étape 37] Lighthouse 12.3.0 (install locale)

-----

## PageSpeed Insights + CrUX (données terrain)

Alternative à Lighthouse pour obtenir des données **terrain réelles** (CrUX P75).
Nécessite `GOOGLE_API_KEY` dans `.env` à la racine du projet.

### Vérifier la clé API

    .venv/bin/python3 .claude/skills/analyse-parcours/scripts/collect_cwv_pagespeed.py <dossier-audit> --check

### Collecter les CWV terrain

    .venv/bin/python3 .claude/skills/analyse-parcours/scripts/collect_cwv_pagespeed.py <dossier-audit>

Options :
- `--strategy desktop` : métriques desktop (défaut : mobile)
- `--urls https://... https://...` : URLs explicites (sinon extraites du .har)

### Obtenir la clé API

Voir `documentation/setup/setup_api_keys.md`.
APIs à activer sur Google Cloud : PageSpeed Insights API + Chrome UX Report API.
Quota gratuit : 25 000 req/jour (PageSpeed), pas de limite journalière (CrUX).
