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
- `{{AUDIT_DIR}}` par le chemin absolu du dossier d'audit courant
- `{{HAR_FILE}}` par le chemin absolu du fichier `.har`
- `{{COVERAGE_FILES}}` par la liste des chemins de fichiers `Coverage-*.json`

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

20a — Vue d'ensemble du trafic :
- Nombre total de requêtes
- Domaines contactés (first-party / third-party)
- Répartition codes HTTP
- Volume total transféré (Mo)
- Top 10 requêtes les plus lourdes

20b — Performance réseau :
- Requêtes sans cache
- Requêtes dupliquées (URLs identiques)
- Ressources bloquantes (JS/CSS synchrones en <head>)
- Ressources tierces lentes (> 1s)

Note sur les HAR volumineux : lire par lots si > 5 Mo (50 000+ lignes).

Écrire les résultats dans `{{AUDIT_DIR}}/har-analysis.json`.
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
COVERAGE_FILES: {{COVERAGE_FILES}}
PIPELINE: skill-steps/30_analyse-coverage.md

Lire et exécuter le pipeline `skill-steps/30_analyse-coverage.md`.

Pour chaque fichier Coverage-*.json :
- Détecter le format (A : tableau direct / B : objet enveloppé)
- Calculer métriques JS et CSS (taille totale, inutilisée, %)
- Identifier les librairies tierces reconnaissables

Produire :
- Tableau par page (JS/CSS : total Ko, inutilisé Ko, %)
- Top 5 fichiers JS + Top 3 CSS par code non utilisé
- Synthèse multi-pages (totaux, évolution page à page)
- Signaler outliers (page > 2x la médiane)

Écrire les résultats dans `{{AUDIT_DIR}}/coverage-analysis.json`.
Format attendu :
{
  "pages": [
    {
      "name": "Page 1",
      "js_total_kb": N, "js_unused_kb": N, "js_unused_pct": N,
      "css_total_kb": N, "css_unused_kb": N, "css_unused_pct": N,
      "top_js_unused": [...], "top_css_unused": [...]
    }
  ],
  "summary": {
    "total_js_kb": N, "total_js_unused_kb": N,
    "total_css_kb": N, "total_css_unused_kb": N
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
