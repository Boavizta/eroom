# Étape 10 — Localisation des fichiers

> Source : skill-steps/10_localisation.md. Retour : SKILL.md étape 20.

## Convention SOURCE_DIR / AUDIT_DIR

- `SOURCE_DIR` : dossier contenant les fichiers fournis par l'utilisateur (HAR, Coverage, cwv.json optionnel)
- `AUDIT_DIR` : `SOURCE_DIR/audit/` — créé automatiquement si absent, contient uniquement les fichiers produits par l'analyse

Les fichiers d'entrée (`.har`, `Coverage-*.json`, `cwv.json`) sont cherchés dans `SOURCE_DIR`.
Les fichiers de sortie (`har-analysis.json`, `coverage-analysis.json`, rapport HTML, `analyse-cout-agent/`) sont écrits dans `AUDIT_DIR`.

## Cas 1 — Dossier passé en argument

```
/analyse-parcours ./mon-dossier/
```

1. `SOURCE_DIR` = chemin passé en argument
2. `AUDIT_DIR` = `SOURCE_DIR/audit/` (créer avec `mkdir -p` si absent)
3. Lister le contenu de `SOURCE_DIR`
4. Identifier le(s) fichier(s) `.har` dans `SOURCE_DIR`
5. Identifier les fichiers de couverture : `Coverage-*.json` ou `*coverage*.json` ou `*Coverage*.json` dans `SOURCE_DIR`
6. Rechercher un contexte métier : `README.md`, `CONTEXT.md`, `*.txt` dans `SOURCE_DIR`

Si plusieurs fichiers `.har` trouvés : demander lequel utiliser.

## Cas 2 — Fichiers passés directement

```
/analyse-parcours ./capture.har ./cov-page1.json ./cov-page2.json
```

- `SOURCE_DIR` = dossier parent du fichier `.har`
- `AUDIT_DIR` = `SOURCE_DIR/audit/` (créer avec `mkdir -p` si absent)
- Utiliser les fichiers tels quels. Vérifier leur existence avant de continuer.

## Cas 3 — Aucun argument

Demander à l'utilisateur :
> "Quel dossier ou fichiers HAR/Coverage analyser ? (chemin vers le dossier, ou fichier .har + fichiers Coverage-*.json)"

## Synthèse à produire

Avant de passer à l'étape 20, afficher :

```
Fichiers identifiés :
- Source   : <SOURCE_DIR>
- Audit    : <AUDIT_DIR>
- HAR      : <nom-fichier.har> ([N] Ko)
- Coverage : [N] fichier(s) — page 1 : <nom>, page 2 : <nom>, ...
- Contexte : <README.md ou "aucun">
```
