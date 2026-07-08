# Étape 10 — Localisation des fichiers

> Source : skill-steps/10_localisation.md. Retour : SKILL.md étape 20.

## Cas 1 — Dossier passé en argument

```
/analyse-parcours ./mon-dossier/
```

1. Lister le contenu du dossier
2. Identifier le(s) fichier(s) `.har`
3. Identifier les fichiers de couverture : `Coverage-*.json` ou `*coverage*.json` ou `*Coverage*.json`
4. Rechercher un contexte métier : `README.md`, `CONTEXT.md`, `*.txt`

Si plusieurs fichiers `.har` trouvés : demander lequel utiliser.

## Cas 2 — Fichiers passés directement

```
/analyse-parcours ./capture.har ./cov-page1.json ./cov-page2.json
```

Utiliser les fichiers tels quels. Vérifier leur existence avant de continuer.

## Cas 3 — Aucun argument

Demander à l'utilisateur :
> "Quel dossier ou fichiers HAR/Coverage analyser ? (chemin vers le dossier, ou fichier .har + fichiers Coverage-*.json)"

## Synthèse à produire

Avant de passer à l'étape 20, afficher :

```
Fichiers identifiés :
- HAR      : <nom-fichier.har> ([N] Ko)
- Coverage : [N] fichier(s) — page 1 : <nom>, page 2 : <nom>, ...
- Contexte : <README.md ou "aucun">
```
