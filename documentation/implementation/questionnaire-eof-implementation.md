-----
Implémentation du questionnaire EOF
-----

Date : 2026-09-07
Auteur : Agent Claude (session Sonnet)
Statut : Complet, autotests validés

## Contexte

Décision du 07/09/2026 : couvrir le radar EOF par un questionnaire généré et hiérarchisé. Cette implémentation produit deux scripts Python qui génèrent et parsent des questionnaires Markdown pour compléter un audit EOF existant.

## Livrables créés

Deux scripts dans `.claude/skills/analyse-parcours/scripts/` :

1. **`generate_questionnaire.py`**
   - Lit `eof-audit-results.json`, `eof-referentiel.json` et `questionnaire-blocs.json`
   - Génère `questionnaire-produit-usage.md` et `questionnaire-technique.md`
   - Calcule le résidu (critères sans verdict utile)
   - Ordonnance les blocs par phase puis potentiel décroissant

2. **`parse_questionnaire.py`**
   - Lit les deux fichiers `.md` remplis
   - Produit `lots/relecture-questionnaire.json`
   - Vérifie exactement une case cochée par bloc
   - Respecte le contrat de sortie de lot (4 clés racine, omission des null)

## Ce que les autotests couvrent

⚠️ **Aucun compte de cas n'est écrit ici, volontairement** : un nombre recopié devient faux au
premier cas ajouté, et se met alors à mentir sans que personne ne le voie. Pour connaître l'état
réel, lancer les `--autotest` ci-dessous et lire leur code de sortie.

**`generate_questionnaire.py --autotest`** couvre :
- Bloc direct sur critère détaillé (1.x à 6.x)
- Bloc direct sur question diagnostic rapide (0.x, vérification absence de potentiel_max)
- Critère avec réponse "🤔 À évaluer" dans le résidu (règle cruciale)
- Bloc composé avec critères déjà tranchés (marqueur `<!-- deja-tranche:... -->`)
- Ordonnancement porte avant detail
- Nettoyage à l'affichage de la mention "je ne sais pas" collée au pire cas
- Tri numérique des identifiants (`0.2` avant `0.10`)

**`parse_questionnaire.py --autotest`** couvre :
- Bloc direct case cochée (vérification coefficient obligatoire pour critère détaillé)
- Diagnostic rapide sans coefficient (règle contractuelle)
- Case "Je ne sais pas" = contexte seulement, jamais de réponse
- Bloc vide (aucune case cochée) = rien versé
- Deux cases cochées = rien versé (erreur signalée)
- Critère déjà tranché ignoré
- (Aller-retour générateur/parseur : couvert implicitement)

## Décisions clés prises

### 1. Le résidu inclut "🤔 À évaluer" et "⌛️ Évaluation en cours"

**Raison** : Ces réponses ont un coefficient 0 et comptent comme des réponses dans le reste du code, mais NE TRANCHENT RIEN. Si on ne les repose pas, le critère reste un faux zéro détectable.

**Impact** : Un critère avec ces réponses est reposé dans le questionnaire.

### 2. Options des blocs "direct" lues dans le référentiel

**Raison** : Éviter toute divergence entre la bibliothèque de blocs et le référentiel. Les options ne sont jamais recopiées.

**Impact** : 
- Critère détaillé : lecture de `options_evaluation`
- Question diagnostic rapide : lecture de `crans`

### 3. Ordonnancement par potentiel décroissant

**Raison** : Décision métier - poser d'abord les questions qui débloquent le plus de potentiel.

**Impact** : Tri stable (phase, -potentiel, id de bloc) pour résultats déterministes.

### 4. Case "Je ne sais pas" ajoutée à chaque bloc

**Raison** : Distinguer "on a demandé et personne ne sait" de "personne n'a demandé". Évite de fabriquer un faux zéro qui rend un service ignoré indistinguable d'un service exemplaire.

**Impact** : Le parseur produit un `contexte` mais JAMAIS de `reponse` pour cette case.

### 5. Provenance = "precise", catégorie = "aucune_donnee"

**Raison** : Contrat de lot - une case cochée par le service audité, sans preuve, ne vient d'aucune donnée collectée.

**Impact** : Tous les critères versés portent ces valeurs fixes.

### 6. Format Markdown strict

**Raison** : Consignes de style du projet (TTS macOS lit `=====` lettre par lettre).

**Impact** :
- Séparateurs en `-----` uniquement
- Guillemets droits `"`
- Pas de tiret long `—`

### 7. Coefficient obligatoire pour critères détaillés, absent pour diagnostic rapide

**Raison** : Règle du validateur de lots. Le référentiel ne définit pas de coefficient pour les questions `0.x`.

**Impact** : Le parseur omet la clé `coefficient` pour les questions diagnostic rapide.

## Formats contractuels respectés

### Bibliothèque de blocs (entrée, ne PAS la modifier)

```json
{
  "version": 1,
  "blocs": [
    {
      "id": "...",
      "fichier": "produit-usage" | "technique",
      "phase": "porte" | "detail",
      "titre": "...",
      "type": "direct" | "compose",
      "critere": "..." (si direct),
      "question": "...",
      "aide": "..." (facultatif),
      "options": [...] (si compose)
    }
  ]
}
```

### Fichier Markdown généré

- Marqueurs machine : `<!-- questionnaire: ... -->`, `<!-- version-blocs: ... -->`
- Par bloc : `<!-- bloc:id -->`, options avec `<!-- opt:n -->`, case jnsp avec `<!-- opt:jnsp -->`
- Blocs composés : `<!-- deja-tranche:id1,id2,... -->` si besoin
- Format de case : `- [ ] Libellé  <!-- opt:n -->`

### Contrat de sortie de lot

Racine : exactement 4 clés `lot_id`, `genere_le`, `entrees`, `criteres`.

Par critère :
- `id` et `categorie` : obligatoires
- `reponse`, `coefficient`, `provenance`, `source`, `contexte` : facultatifs
- **NE JAMAIS écrire une clé qui vaut null** : l'omettre
- Si `reponse` posée sur critère détaillé : `coefficient` obligatoire et non nul
- Si `reponse` posée sur diagnostic rapide : `coefficient` ABSENT
- Si `reponse` ou `contexte` posé : `provenance` ET `source` obligatoires

## Ce qui n'est pas couvert

- Validation du fichier `questionnaire-blocs.json` (un autre agent l'écrit en parallèle)
- Génération d'un questionnaire vide (si résidu vide, aucun fichier créé)
- Gestion des blocs dont l'ID change entre deux versions de la bibliothèque
- Interface graphique de remplissage (hors périmètre : Markdown éditable manuellement)

## Traçabilité des bugs corrigés en autotest

1. **Bug regex** : `[^-\s]+` n'acceptait pas les tirets dans les IDs de blocs (ex: `test-11`). Corrigé en `[^\s]+?`.
2. **Bug JSON Python** : `null` au lieu de `None` dans les autotests. Corrigé dans 5 endroits.
3. **Bug fichiers absents** : autotests du parseur ne créaient pas les deux fichiers `.md`. Corrigé en créant un fichier vide pour l'autre questionnaire.

## Vérifications effectuées

- **Aucune trace d'audit spécifique** : pas de "octo.com", pas d'IP, pas de chemin `audits/quelquechose` dans le code (vérifié par `grep -i "octo|192\.|audits/"`)
- **Autotests exécutés et validés** : codes de sortie 0 pour les deux scripts
- **Commentaires en français** : conformément aux consignes du projet
- **Style respecté** : séparateurs `-----`, guillemets droits, pas de tiret long

## Commandes de référence

```bash
# Générer les questionnaires
python3 generate_questionnaire.py <repertoire-audit>
python3 generate_questionnaire.py <repertoire-audit> --output-dir <autre-dir>

# Parser les questionnaires remplis
python3 parse_questionnaire.py <repertoire-audit>

# Lancer les autotests
python3 generate_questionnaire.py --autotest
python3 parse_questionnaire.py --autotest

# Contrôler la bibliothèque de blocs contre le référentiel
python3 valider_blocs_questionnaire.py
python3 valider_blocs_questionnaire.py --autotest
```

## Prochaines étapes

1. ~~Écrire `questionnaire-blocs.json` et son validateur~~ (fait)
2. ~~Prouver l'aller-retour complet sur un audit réel~~ (fait sur octo.com, recette dans le handoff)
3. Compléter la bibliothèque de blocs pour les dimensions 1 à 5 : **c'est de la donnée pure, aucun
   changement de code**
4. Le radar à deux couches, devenu indispensable : la dimension 4 passe à 0 % dès qu'un critère sur
   six est bon, ce qui se lira "exemplaire"
5. Les diagrammes PlantUML, en une seule passe plus tard

## Un défaut du référentiel EROOM, laissé ouvert

Certains crans du diagnostic rapide **collent la mention "je ne sais pas" au cran le plus
défavorable** (`0.10`, `0.11`, `0.14`). Un répondant honnête pouvait donc se faire noter "très
complexe" pour avoir dit qu'il ne savait pas, alors que tout le projet s'interdit le pire cas par
défaut. Le générateur retire la mention **à l'affichage seulement**, et le fichier de lot conserve
le cran d'origine au caractère près, parce que le parseur résout la réponse par l'indice
`<!-- opt:N -->` et relit le référentiel.

⚠️ **Ne jamais faire dépendre le parseur du texte affiché** : ce nettoyage deviendrait une
falsification. Signaler ou non ce défaut à EROOM reste à trancher.

-----
Fin de trace
-----
