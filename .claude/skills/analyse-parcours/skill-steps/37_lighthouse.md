# Étape 37 — CWV via Lighthouse ou PageSpeed Insights

**Quand :** après l'étape 35, avant l'étape 40.

## Choix de la source CWV

| Source | Commande | Données | Avantages |
|--------|----------|---------|-----------|
| PageSpeed + CrUX | `collect_cwv_pagespeed.py` | Terrain P75 réels | Reflète les vrais utilisateurs ; nécessite `GOOGLE_API_KEY` |
| Lighthouse (fallback) | `run_lighthouse.sh` | Lab (simulation) | Fonctionne sans clé API, même sur pages auth |

`collect_cwv_pagespeed.py` est le point d'entrée principal. Il déclenche automatiquement le fallback Lighthouse dans deux cas :
- `GOOGLE_API_KEY` absente du `.env`
- Aucune métrique collectée via l'API (quota dépassé, réseau, URLs inconnues de CrUX)

-----

---

## Flux automatique

### Cas 1 : cwv.json absent

1. Lancer le script sans URLs : il extrait lui-même toutes les URLs uniques depuis le HAR.

```bash
bash .claude/skills/analyse-parcours/scripts/run_lighthouse.sh <dossier-audit>
```

Le script déduplique les URLs (`log.pages[].title`) avant de lancer Lighthouse, donc chaque page n'est analysée qu'une seule fois même si elle apparaît plusieurs fois dans le parcours.

3. Afficher la progression :
```
[Étape 37] Lighthouse CWV — analyse de N page(s) via npx...
  -> page_1 : https://...
  -> page_2 : https://...
[Étape 37] cwv.json généré.
```

4. Continuer vers l'étape 40.

### Cas 2 : cwv.json déjà présent

Afficher :
```
[Étape 37] cwv.json déjà présent — Lighthouse skippé.
```
Passer directement à l'étape 40.

### Cas 3 : l'utilisateur demande "relance Lighthouse"

Supprimer `cwv.json` du dossier d'audit, puis reprendre depuis le Cas 1.

---

## Si Lighthouse échoue

Afficher un warning et continuer sans CWV :
```
[Étape 37] Lighthouse indisponible (npx absent ou pages inaccessibles).
Le rapport continuera sans CWV. Pour relancer : "relance Lighthouse".
```

Causes possibles :
- `npx` absent (Node.js non installé)
- Pages derrière authentification (Chrome headless sans session)
- Réseau bloqué

---

## Limites

- Mesures "lab" (simulation réseau), pas données terrain réelles
- Pages derrière login non supportées
- Résultats peuvent différer du terrain selon la connexion

Pour des données terrain réelles, utiliser `collect_cwv_pagespeed.py` (voir section ci-dessus) ou fournir un `cwv.json` manuel (voir docs/capturer-har-et-coverage.md).

-----

## PageSpeed Insights + CrUX (données terrain)

### Prérequis

- `GOOGLE_API_KEY` dans `.env` à la racine du projet (voir `documentation/setup/setup_api_keys.md`)
- APIs activées sur Google Cloud : PageSpeed Insights API + Chrome UX Report API

### Vérifier la clé API

```bash
.venv/bin/python3 .claude/skills/analyse-parcours/scripts/collect_cwv_pagespeed.py <dossier-audit> --check
```

### Collecter les CWV

```bash
.venv/bin/python3 .claude/skills/analyse-parcours/scripts/collect_cwv_pagespeed.py <dossier-audit>
```

Par défaut (`--strategy both`) : collecte **mobile ET desktop** en une seule commande, conservés côte à côte dans `cwv.json` (une entrée par couple url/stratégie). Restreindre au besoin avec `--strategy mobile` ou `--strategy desktop`.

### Résultats dans cwv.json

- `"strategy"` : `"mobile"` ou `"desktop"` (une entrée par appareil, plus d'écrasement entre passages)
- `"source": "crux"` : données terrain CrUX P75 (réels utilisateurs) - prioritaire
- `"source": "pagespeed_lab"` : données lab Lighthouse via API (si CrUX absent pour cette URL)
- `"crux_category"` : `"FAST"` / `"AVERAGE"` / `"SLOW"` (classification globale CrUX)

Le rapport affiche mobile et desktop séparément, avec un badge de source (terrain / lab / lab local).

### Note méthodologique

Les données CrUX sont des percentiles P75 sur les 28 derniers jours d'utilisation réelle. Elles ne sont disponibles que pour les URLs avec suffisamment de trafic dans la base CrUX Google. Pour les pages peu visitées ou les pages derrière authentification, le script retombe automatiquement sur les données lab.
