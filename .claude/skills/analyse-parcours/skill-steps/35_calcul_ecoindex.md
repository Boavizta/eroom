# Étape 35 — Calcul EcoIndex

> Source : skill-steps/35_calcul_ecoindex.md. Retour : SKILL.md étape 40.

## Principe

L'EcoIndex est calculé entièrement depuis le HAR, sans saisie manuelle :
- **Requêtes** : comptées depuis `log.entries` par page (`pageref`)
- **Poids** : somme `response.content.size` par page
- **DOM** : compté en parsant le corps HTML de la première réponse `text/html` de chaque page (`response.content.text`)

La formule officielle (cnumr/ecoindex_reference) avec quantiles est implémentée dans `scripts/ecoindex_utils.py`.

## Exécution

```bash
python3 .claude/skills/analyse-parcours/scripts/ecoindex_utils.py <fichier.har> [cwv.json]
```

Le script affiche un tableau par page et valide automatiquement sur les valeurs ANTS connues
(dom=483, req=82, poids=1930 Ko → score attendu 53/100, grade D).

## Résultat produit

Pour chaque page du HAR :

```
Page             Req    Ko    DOM  Score  Grade  onLoad
----------------------------------------------------- ...
Page 1 - [URL]    82  1930    483     53      D   1374ms
Page 2 - [URL]    53  2664    383     61      C    678ms
...
```

Grades : A (≥80) · B (≥70) · C (≥55) · D (≥40) · E (≥25) · F (≥10) · G (<10)

## Cas particuliers

### DOM = 0 après parse

Si le HAR ne contient pas le corps HTML (champ `response.content.text` absent ou vide pour les entrées `text/html`), le DOM sera 0 et le score surestimé.

Dans ce cas : afficher un avertissement et noter dans le rapport que le DOM n'a pas pu être extrait automatiquement.

### Pages SPA (Single Page Application)

Pour les SPA, une seule entrée `text/html` initiale existe. Le DOM mesuré correspond à l'état initial, pas au DOM après exécution JS. C'est cohérent avec la méthode GreenIT-Analysis (mesure à la fin du chargement), mais légèrement différent si la SPA hydrate massivement.

Mentionner cette limite dans le rapport si plusieurs pages partagent le même document HTML.

## Intégration dans le workflow

Les métriques calculées à cette étape alimentent directement :
- Le tableau de bord du rapport HTML (étape 40)
- La section EcoIndex du tableau de bord
- Les recommandations priorisées (score < 40 → PRIORITÉ 1)
