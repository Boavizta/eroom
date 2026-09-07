-----
-----
# Photocopie de la Google Sheet source du référentiel EOF
-----
-----

Ces 9 fichiers sont **l'export brut de la Google Sheet EOF-V.1.1 d'EROOM**, un fichier
par onglet. Ce n'est pas de la documentation : c'est la **source de vérité** à partir de
laquelle `eof-referentiel.json` est fabriqué.

**Date de la photocopie : 2026-09-02.** Vérifiée encore identique à la Sheet vivante le
2026-09-07.

## Pourquoi ces fichiers sont versionnés

Ils étaient auparavant dans `tmp/eof-gviz/`, un dossier ignoré par git, donc sauvegardés
nulle part. Le lien vers la Sheet, lui, a toujours été versionné dans `../../SKILL.md`.
La distinction compte :

| | Où | Perdable |
|---|---|---|
| L'adresse de la Sheet et la recette de téléchargement | `../../SKILL.md` | non |
| **La photocopie, c'est-à-dire le point de comparaison** | **ici** | **plus maintenant** |

Sans point de comparaison, retélécharger la Sheet n'apprend rien : on obtient son état
du jour, sans pouvoir dire ce qui a changé. Le seul intérêt de garder cette photocopie
est donc de **détecter une évolution du référentiel chez EROOM**.

Ce n'est pas théorique : la Sheet a déjà été enrichie de **43 à 54 critères détaillés**
depuis l'export Excel initialement fourni par EROOM, découverte faite le 2026-09-02.
Elle bougera encore.

C'est aussi en relisant cette source qu'on a établi que le code appliquait la **mauvaise
formule** du potentiel d'optimisation : le dénominateur porte sur **tous** les critères
d'une dimension, répondus ou non. Ces fichiers sont la pièce à conviction de cette
correction.

## Vérifier si EROOM a modifié le référentiel

```bash
.claude/skills/eof/scripts/verifier_source_sheet.sh
```

Aucun effet de bord, ne touche à rien, code de sortie 0 si rien n'a bougé, 1 sinon.
Détecte aussi une Sheet devenue privée ou un onglet supprimé, qui renvoient du HTML avec
un code 200 et se compareraient sinon en silence.

Pour adopter une évolution :

```bash
.claude/skills/eof/scripts/verifier_source_sheet.sh --rafraichir
git diff .claude/skills/eof/docs/source-sheet/   # voir exactement ce qu'EROOM a changé
```

Puis régénérer le référentiel, cf. étape 2 de `../../SKILL.md`, et rejouer
`processus/valider_coherence_cles.py`.

## Format des fichiers

Ce sont des réponses de l'interface `gviz` de Google, pas du JSON pur : chaque fichier
commence par `/*O_o*/` puis `google.visualization.Query.setResponse({...})`. Il faut
retirer cette enveloppe avant de parser, ce que fait déjà
`../../scripts/build_template.py`. Les exports CSV et XLSX classiques ne sont pas
utilisables ici : ils passent par une redirection à jeton à usage unique.

## Correspondance des fichiers et des onglets

| Fichier | Onglet | Contenu | Critères |
|---|---|---|---|
| `a-lire.json` | À lire | mode d'emploi du référentiel | - |
| `diag-rapide.json` | Diagnostic rapide | échelle 1 à 5, logique propre | 16 questions |
| `produit.json` | dimension 1, Produit | | 16 |
| `architecture.json` | dimension 2, Architecture | | 5 |
| `infrastructure.json` | dimension 3, Infrastructure | | 8 |
| `stockage.json` | dimension 4, Stockage et données | | 6 |
| `algo-code.json` | dimension 5, Algorithme et code | | 9 |
| `facilite.json` | dimension 6, Facilité de changement | vocabulaire 🟢 / 🟡 / 🔴 | 10 |
| `synthese.json` | Synthèse | | - |

Total **54 critères** détaillés, sommes de `potentiel_max` par dimension
**23,5 / 8,0 / 12,0 / 8,0 / 13,0 / 15,5**, total **80,0**.

Deux pièges du référentiel, lisibles dans ces fichiers :

- Le critère **`3.4` n'existe pas**, la numérotation saute de 3.3 à 3.5. C'est normal.
- **Deux vocabulaires de réponse** : 44 critères en `✅ / 💡 / 🚫 / 🤔 / ⌛️`, et les 10
  critères de la dimension 6 en `🟢 / 🟡 / 🔴`, **sans option "À évaluer"**. Toujours lire
  `options_evaluation` du critère, ne jamais coder ces libellés en dur.
