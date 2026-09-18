# Étape 25 — Orchestration DISPATCH (vagues d'analyse)

> Source : skill-steps/25_dispatch-orchestration.md. Déclenché depuis SKILL.md après étape 10.
> Retour : après le merge final, reprendre dans SKILL.md à l'étape 35.

Ce fichier pilote l'exécution des analyses HAR/Coverage/CWV/env-data/sécurité
(Wave 1) et des extracteurs EOF dépendants d'env-data.json (Wave 2) via des
blocs DISPATCH.

-----

## Protocole DISPATCH

### Détection des capacités

Avant de démarrer les vagues, évaluer ta capacité à spawner un sous-agent avec
fenêtre de contexte isolée (Agent tool, subagent API, ou mécanisme équivalent) :

- **OUI (sous-agents disponibles)** : chaque bloc DISPATCH est dispatché dans un contexte
  isolé. Les blocs d'une même vague (5 en Wave 1, 2 en Wave 2) s'exécutent en parallèle.
- **NON (contexte unique)** : exécuter chaque bloc DISPATCH séquentiellement dans le
  contexte courant, en lisant/écrivant les mêmes fichiers disque.

Quel que soit le mode, les sorties disque sont identiques.

### Substitution des variables

**Avant tout dispatch**, substituer dans le texte du bloc :
- `{{SOURCE_DIR}}` par le chemin absolu du dossier source (là où vivent HAR et Coverage)
- `{{AUDIT_DIR}}` par le chemin absolu du dossier d'audit (`SOURCE_DIR/audit/`)
- `{{HAR_FILE}}` par le chemin absolu du fichier `.har` (dans `SOURCE_DIR`)
- `{{COVERAGE_FILES}}` par la liste des chemins de fichiers `Coverage-*.json` (dans `SOURCE_DIR`)

### Convention de rangement des fichiers produits

Deux emplacements coexistent, à respecter exactement (vérifié script par
script, ne pas improviser) :
- **`{{AUDIT_DIR}}`** (`SOURCE_DIR/audit/`) : `har-analysis.json`,
  `coverage-analysis.json`, `cwv.json`
- **`{{SOURCE_DIR}}`** (racine) : `env-data.json`,
  `security-headers-analysis.json`, `html-css-criteria.json`,
  `wellknown-scan.json`

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

→ Afficher : `✅ Wave 0 terminée — lancement Wave 1 (HAR + Coverage + CWV + env-data + Sécurité)`

-----

## Wave 1 — Analyse HAR + Coverage + CWV + env-data + en-têtes sécurité (5 dispatches en parallèle)

Les cinq blocs sont mutuellement indépendants : chacun lit uniquement le
`.har` brut et/ou les `Coverage-*.json` bruts et/ou appelle une API externe
— aucun ne lit la sortie d'un autre bloc de cette vague. Deux d'entre eux
(`analyse-har`, `extracteur-security-headers`) lisent *aussi* `env-data.json`
de façon **souple** (dégradation documentée et vérifiée en code si le fichier
n'existe pas encore au moment où ils tournent — jamais un crash) : que
`collecte-env-data` finisse avant ou après eux ne change rien à la validité
du résultat, juste à sa précision (classification de domaines/filtre de
pages un peu moins précis en son absence).

> Afficher : `▶ Wave 1 — Analyse HAR + Coverage + CWV + env-data + Sécurité (5 dispatches en parallèle)`

-----

:::dispatch id="analyse-har" wave="1" parallel_with="analyse-coverage,collecte-cwv,collecte-env-data,extracteur-security-headers"
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

:::dispatch id="analyse-coverage" wave="1" parallel_with="analyse-har,collecte-cwv,collecte-env-data,extracteur-security-headers"
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

:::dispatch id="collecte-cwv" wave="1" parallel_with="analyse-har,analyse-coverage,collecte-env-data,extracteur-security-headers"
OUTPUT_FILE: {{AUDIT_DIR}}/cwv.json
AUDIT_DIR: {{AUDIT_DIR}}
SOURCE_DIR: {{SOURCE_DIR}}
PIPELINE: skill-steps/37_lighthouse.md

Lire et exécuter le pipeline `skill-steps/37_lighthouse.md`, section
"PageSpeed Insights + CrUX". Appeler directement la variante étendue
(catégories accessibility + best-practices déjà incluses dans le script,
`--strategy both` = défaut) pour éviter un second passage :

```bash
.venv/bin/python3 .claude/skills/analyse-parcours/scripts/collect_cwv_pagespeed.py {{AUDIT_DIR}} --strategy both
```

Si `GOOGLE_API_KEY` absente du `.env` ou aucune métrique collectée (quota,
réseau, URLs inconnues de CrUX) : le script bascule lui-même sur le fallback
Lighthouse (`run_lighthouse.sh`), pas besoin de le rappeler manuellement.

Si l'échec persiste (npx absent, pages inaccessibles) : noter l'échec,
continuer sans `cwv.json` — le rapport affichera alors `onLoad` HAR comme
proxy LCP.

Retourner uniquement : "cwv.json écrit — <N> pages, mobile+desktop, sources : <crux/pagespeed_lab/lighthouse>"
:::

-----

:::dispatch id="collecte-env-data" wave="1" parallel_with="analyse-har,analyse-coverage,collecte-cwv,extracteur-security-headers"
OUTPUT_FILE: {{SOURCE_DIR}}/env-data.json
SOURCE_DIR: {{SOURCE_DIR}}
PIPELINE: skill-steps/45_efootprint.md (Étape 20)

Lire et exécuter le pipeline `skill-steps/45_efootprint.md`, section
"Étape 20 - Collecte env-data.json" (collecte HAR + CrUX + ipinfo + mix
pays/trafic SimilarWeb) :

```bash
.venv/bin/python3 .claude/skills/analyse-parcours/scripts/collect_env_data.py {{SOURCE_DIR}}
```

Ne PAS passer `--refresh` ici (première collecte de la vague) : si
`env-data.json` existe déjà (audit relancé sur un dossier déjà traité), le
script le préserve tel quel. Mode dégradé documenté : en l'absence de clé
API (`GOOGLE_API_KEY`/`IPINFO_TOKEN`) ou en cas d'échec réseau, le script
continue avec des champs marqués `confidence: default`, jamais un crash.

Retourner uniquement : "env-data.json écrit — <N> serveurs détectés, mix pays : <source>, trafic : <source>"
:::

-----

:::dispatch id="extracteur-security-headers" wave="1" parallel_with="analyse-har,analyse-coverage,collecte-cwv,collecte-env-data"
OUTPUT_FILE: {{SOURCE_DIR}}/security-headers-analysis.json
SOURCE_DIR: {{SOURCE_DIR}}
PIPELINE: skill-steps/39_eof-audit.md

Lire et exécuter :

```bash
.venv/bin/python3 .claude/skills/analyse-parcours/scripts/analyze_security_headers.py {{SOURCE_DIR}}
```

Le script lit uniquement le `.har` déjà capturé (en-têtes de réponse),
aucun appel réseau. Si `env-data.json` n'est pas encore écrit au moment de
l'exécution (bloc `collecte-env-data` de la même vague, ordre non garanti) :
le script analyse alors TOUTES les pages HTML du HAR au lieu de filtrer sur
la liste `env-data.json["pages"]` — dégradation documentée dans le code
(`analyze_security_headers.py::load_page_urls`), jamais un crash.

Retourner uniquement : "security-headers-analysis.json écrit — page la moins bien notée : <url> (<score>%, grade <grade>)"
:::

-----

> Attendre que `har-analysis.json`, `coverage-analysis.json`, `cwv.json`,
> `env-data.json` et `security-headers-analysis.json` existent (ou soient
> notés en échec explicite) avant de lancer la Wave 2.

-----

## Wave 2 — Extracteurs EOF dépendants d'env-data.json (2 dispatches en parallèle)

Contrairement aux blocs de la Wave 1, ces deux extracteurs ont une
dépendance **dure** (pas une dégradation) sur `{{SOURCE_DIR}}/env-data.json` :
`parse_html_criteria.py::load_page_urls()` (lignes 149-160) et
`main()` (lignes 578-581) font `sys.exit(1)` si le fichier est absent ou
sans page ; `scan_wellknown.py::infer_domain()` (lignes 244-253) et `main()`
(lignes 262-267) font de même. **Ne pas dispatcher ces deux blocs avant
d'avoir confirmé `{{SOURCE_DIR}}/env-data.json` sur disque** (bloc
`collecte-env-data` de la Wave 1 terminé) — un simple retry ne suffit pas à
compenser cette dépendance dure, contrairement aux dégradations douces de la
Wave 1.

> Afficher : `▶ Wave 2 — Extracteurs HTML/CSS + well-known (2 dispatches en parallèle)`

-----

:::dispatch id="extracteur-html-css" wave="2" depends_on="collecte-env-data" parallel_with="extracteur-wellknown"
OUTPUT_FILE: {{SOURCE_DIR}}/html-css-criteria.json
SOURCE_DIR: {{SOURCE_DIR}}

Lire et exécuter :

```bash
.venv/bin/python3 .claude/skills/analyse-parcours/scripts/parse_html_criteria.py {{SOURCE_DIR}}
```

Re-fetch live des pages déjà auditées (le `.har` capturé ne contient pas les
corps HTML/CSS). Archive les pages sous `{{SOURCE_DIR}}/pages-html/`
(chantier 27) — cette archive, si elle existe déjà AVANT que le bloc
`analyse-har` de la Wave 1 ne tourne, permet à `analyze_har.py` de calculer
`blocking_resources` ; comme `analyse-har` tourne toujours avant cette
Wave 2 dans ce découpage, ce champ secondaire restera "non calculé" au
premier passage complet sur un nouveau dossier — limite connue, pas une
erreur à corriger.

Retourner uniquement : "html-css-criteria.json écrit — <N> pages, <N> feuilles CSS analysées"
:::

-----

:::dispatch id="extracteur-wellknown" wave="2" depends_on="collecte-env-data" parallel_with="extracteur-html-css"
OUTPUT_FILE: {{SOURCE_DIR}}/wellknown-scan.json
SOURCE_DIR: {{SOURCE_DIR}}

Lire et exécuter :

```bash
.venv/bin/python3 .claude/skills/analyse-parcours/scripts/scan_wellknown.py {{SOURCE_DIR}}
```

Fetch direct de `security.txt`/`robots.txt`/`sitemap.xml` sur le domaine
déduit d'`env-data.json` (2-3 requêtes HTTP publiques, aucune authentification).

Retourner uniquement : "wellknown-scan.json écrit — security.txt: <présent/absent>, robots.txt: <présent/absent>, sitemap: <présent/absent>"
:::

-----

> Attendre que `html-css-criteria.json` ET `wellknown-scan.json` existent (ou
> soient notés en échec explicite) avant le merge.

-----

## Merge final

Les Waves 1 et 2 sont terminées (ou notées en échec explicite, best-effort —
un échec sur `collecte-cwv`/`collecte-env-data`/les deux extracteurs de
Wave 2 dégrade la suite, il ne la bloque pas). Vérifier la présence de :
- `{{AUDIT_DIR}}/har-analysis.json` — clé `total_requests` (obligatoire)
- `{{AUDIT_DIR}}/coverage-analysis.json` — clé `pages` (obligatoire)
- `{{AUDIT_DIR}}/cwv.json` (optionnel — absence signalée, pas bloquante)
- `{{SOURCE_DIR}}/env-data.json` (optionnel)
- `{{SOURCE_DIR}}/security-headers-analysis.json` (optionnel)
- `{{SOURCE_DIR}}/html-css-criteria.json` (optionnel)
- `{{SOURCE_DIR}}/wellknown-scan.json` (optionnel)

Afficher un récapitulatif court (fichier / présent / absent) pour les 7. Les
deux premiers sont obligatoires (avertissement bloquant si absents, cf.
étape 20/30 de SKILL.md) ; les cinq autres sont des enrichissements
best-effort consommés plus loin par l'étape 39 (EOF) et l'étape 40
(rapport) — leur absence n'empêche jamais la suite du pipeline, elle réduit
seulement la couverture (EOF : critères en "je ne sais pas" ; rapport :
sections omises).

→ Puis retourner dans SKILL.md à l'**Étape 35** (calcul EcoIndex).
