# Étape 25 — Orchestration DISPATCH (vague d'analyse)

> Source : skill-steps/25_dispatch-orchestration.md. Déclenché depuis SKILL.md après étape 10.
> Retour : après le merge final, reprendre dans SKILL.md à l'étape 35.

Ce fichier pilote l'exécution des analyses HAR et Coverage via des blocs DISPATCH.

-----

## Protocole DISPATCH

### Détection des capacités

Avant de démarrer les vagues, évaluer ta capacité à spawner un sous-agent avec
fenêtre de contexte isolée (Agent tool, subagent API, ou mécanisme équivalent) :

- **OUI (sous-agents disponibles)** : chaque bloc DISPATCH est dispatché dans un contexte
  isolé. Les deux dispatches de la Wave 1 s'exécutent en parallèle.
- **NON (contexte unique)** : exécuter chaque bloc DISPATCH séquentiellement dans le
  contexte courant, en lisant/écrivant les mêmes fichiers disque.

Quel que soit le mode, les sorties disque sont identiques.

### Substitution des variables

**Avant tout dispatch**, substituer dans le texte du bloc :
- `{{SOURCE_DIR}}` par le chemin absolu du dossier source (là où vivent HAR et Coverage)
- `{{AUDIT_DIR}}` par le chemin absolu du dossier d'audit (`SOURCE_DIR/audit/`)
- `{{HAR_FILE}}` par le chemin absolu du fichier `.har` (dans `SOURCE_DIR`)
- `{{COVERAGE_FILES}}` par la liste des chemins de fichiers `Coverage-*.json` (dans `SOURCE_DIR`)

### Condition de réussite d'un bloc DISPATCH

Un bloc est considéré terminé quand son `OUTPUT_FILE` existe sur disque avec des données.
Si le fichier est absent après exécution, relancer le bloc une fois.
Si toujours absent : noter l'échec, signaler à l'utilisateur et continuer en mode dégradé.

-----

## Wave 0 — Localisation (contexte principal — obligatoire)

Wave 0 s'exécute intégralement dans le contexte principal AVANT tout DISPATCH.
Le fichier `.har` et les `Coverage-*.json` doivent être identifiés et vérifiés
(étape 10 déjà exécutée).

Vérifier que les fichiers identifiés sont accessibles :
```
ls -lh {{HAR_FILE}}
ls -lh {{COVERAGE_FILES}}
ls -d {{AUDIT_DIR}}
```

→ Afficher : `✅ Wave 0 terminée — lancement Wave 1 (analyse HAR + Coverage)`

-----

## Wave 1 — Analyse HAR + Coverage (2 dispatches en parallèle)

Les deux analyses sont strictement indépendantes :
- Dispatch A lit uniquement le `.har`
- Dispatch B lit uniquement les `Coverage-*.json`

> Afficher : `▶ Wave 1/1 — Analyse HAR + Analyse Coverage (en parallèle)`

-----

:::dispatch id="analyse-har" wave="1" parallel_with="analyse-coverage"
OUTPUT_FILE: {{AUDIT_DIR}}/har-analysis.json
AUDIT_DIR: {{AUDIT_DIR}}
HAR_FILE: {{HAR_FILE}}
PIPELINE: skill-steps/20_analyse-har.md

Lire et exécuter le pipeline `skill-steps/20_analyse-har.md`.

Le calcul est fait par un script, PAS à la main. Une lecture manuelle du `.har`
avait déjà produit une clé (`blocking_resources`) inventée en lisant le HTML à
l'œil, non rejouable :

```bash
.venv/bin/python3 .claude/skills/analyse-parcours/scripts/analyze_har.py {{SOURCE_DIR}} --output {{AUDIT_DIR}}/har-analysis.json
```

Le script classe les domaines 1st-party/3rd-party depuis `env-data.json`,
déduplique par URL avant le top10 des ressources les plus lourdes, détecte les
requêtes sans cache, les doublons d'URL et les ressources tierces lentes
(> 1 s), et calcule les ressources bloquantes du `<head>` uniquement pour les
pages dont l'archive HTML (chantier 27, `<source_dir>/pages-html/`) est
disponible — sinon le champ est marqué non calculé, jamais deviné depuis le
seul type MIME.

Format attendu :
{
  "total_requests": N,
  "domains": {"first_party": [...], "third_party": [...]},
  "http_codes": {"200": N, "304": N, ...},
  "total_size_kb": N,
  "top10_heaviest": [...],
  "uncached_requests": N,
  "duplicate_urls": [...],
  "slow_third_party": [...]
}
Retourner uniquement : "har-analysis.json écrit — <N> requêtes, <N> domaines, <X> Mo"
:::

-----

:::dispatch id="analyse-coverage" wave="1" parallel_with="analyse-har"
OUTPUT_FILE: {{AUDIT_DIR}}/coverage-analysis.json
AUDIT_DIR: {{AUDIT_DIR}}
SOURCE_DIR: {{SOURCE_DIR}}
COVERAGE_FILES: {{COVERAGE_FILES}}
PIPELINE: skill-steps/30_analyse-coverage.md

Lire et exécuter le pipeline `skill-steps/30_analyse-coverage.md`.

Le calcul est fait par un script, PAS à la main. Un test d'extension sur l'URL
entière a déjà publié une page à zéro Ko (URLs versionnées) :

```bash
.venv/bin/python3 .claude/skills/analyse-parcours/scripts/coverage_metrics.py {{SOURCE_DIR}} --output {{AUDIT_DIR}}/coverage-analysis.json
```

Le script détecte le format des fichiers Coverage, classe JS/CSS sur le chemin de
l'URL, libelle chaque page depuis le document HTML corroboré par le HAR,
identifie les bibliothèques tierces et signale les outliers.

Vérifier ensuite la sortie : toute page marquée `no_js_no_css` est à signaler à
l'utilisateur, c'est le symptôme d'un mauvais classement, pas d'une page sans code.

Format produit :
{
  "pages": [
    {
      "name": "Page 1",
      "source_file": "Coverage-....json",
      "url": "https://...", "url_provenance": "document HTML confirmé par le HAR",
      "js_total_kb": N, "js_unused_kb": N, "js_unused_pct": N,
      "css_total_kb": N, "css_unused_kb": N, "css_unused_pct": N,
      "resources_count": N, "no_js_no_css": false,
      "top_js_unused": [...], "top_css_unused": [...]
    }
  ],
  "summary": {
    "pages_count": N,
    "total_js_kb": N, "total_js_unused_kb": N, "total_js_unused_pct": N,
    "total_css_kb": N, "total_css_unused_kb": N, "total_css_unused_pct": N,
    "third_party_libraries": [...], "outlier_pages": [...],
    "har_reference": "....har"
  }
}
Retourner uniquement : "coverage-analysis.json écrit — <N> pages, JS inutilisé : <X> Mo (<Y>%), CSS inutilisé : <X> Ko (<Y>%)"
:::

-----

> Attendre que `har-analysis.json` ET `coverage-analysis.json` existent avant le merge.

-----

## Merge final

Toutes les vagues sont terminées. Lire :
- `{{AUDIT_DIR}}/har-analysis.json`
- `{{AUDIT_DIR}}/coverage-analysis.json`

Valider leur présence et leur contenu minimal (clé `total_requests` pour HAR,
clé `pages` pour Coverage). En cas d'absence : afficher avertissement.

→ Puis retourner dans SKILL.md à l'**Étape 35** (calcul EcoIndex).
