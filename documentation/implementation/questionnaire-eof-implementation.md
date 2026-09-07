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

**Mesure ultérieure** : La session 19 a montré que ce tri ne fait gagner que 4,5 questions sur 37 par rapport à un tirage au hasard. Le tri est conservé parce qu'il ne coûte rien et qu'il permet à l'interlocuteur de s'arrêter en sachant ce qu'il laisse, mais il ne faut pas en attendre un gain de compaction. Voir la section "Session 19 : le plafond du format actuel, mesuré".

### 4. Case "Je ne sais pas" ajoutée à chaque bloc

**Raison** : Distinguer "on a demandé et personne ne sait" de "personne n'a demandé". Évite de fabriquer un faux zéro qui rend un service ignoré indistinguable d'un service exemplaire.

**Impact** : Le parseur produit un `contexte` mais JAMAIS de `reponse` pour cette case.

### 5. Provenance = "precise", catégorie = "aucune_donnee"

**Raison** : Contrat de lot - une case cochée par le service audité, sans preuve, ne vient d'aucune donnée collectée.

**Impact** : Tous les critères versés portent ces valeurs fixes.

### 6. Format Markdown strict

**Raison** : Consignes de style du projet (TTS macOS lit les séparateurs en signes égal lettre par lettre).

**Impact** :
- Séparateurs en `-----` uniquement
- Guillemets droits `"`
- Pas de tiret long (cadratin)

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

## Session 19, 2026-09-07 : le plafond du format actuel, mesuré

Le but posé par l'utilisatrice : **minimiser le nombre de questions pour maximiser le nombre de critères remplis**, de façon générique, indépendamment du site servant de terrain d'essai.

État après la fusion `0.3` + `6.10` : **62 questions couvrent les 70 critères** et les 80,0 de potentiel, soit **1,13 critère par question**.

Trois mesures qui ferment les fausses pistes. Elles sont là pour éviter qu'une session future les rouvre sur une intuition.

| Mesure | Résultat | Ce qu'elle interdit |
|---|---|---|
| Potentiel par question, phase `porte` contre phase `detail` | 0,60 contre 1,74 | allonger la porte pour raccourcir le détail est un mauvais échange |
| Dispersion du `potentiel_max` des critères détaillés | tous entre 1,0 et 2,0, distribution plate | il n'existe aucun critère lourd qu'on pourrait poser en premier pour couvrir la moitié du radar |
| Questions nécessaires pour couvrir 50 % du potentiel de détail | 14 sur 37, contre 18,5 en tirant au hasard | le tri par potentiel décroissant ne fait gagner que 4,5 questions sur 37 |

## Session 19 : le format à cases indépendantes, évalué et écarté

Une tentative antérieure du projet posait des questions **multi-select** ("coche toutes les affirmations qui s'appliquent"), chaque case remplissant ses propres critères, à raison de 3 à 5 critères par question. Capacité théorique : **3,0 critères par question**, contre 1,13 pour le format actuel à choix unique.

**Ce format est écarté.** Sur le déroulé réel de la tentative, 7 questions visant 21 critères en ont rempli 9 :

| Question | Critères visés | Réellement remplis |
|---|---|---|
| Q1 criticité et disponibilité | 3 | 0, la case cochée ne correspondait à aucun cran du référentiel |
| Q2 complexité et architecture | 3 | 3 |
| Q3 utilité fonctionnelle | 3 | 1 |
| Q4 UX et données | 2 | 2 |
| Q5 maturité d'ingénierie | 5 | 3 |
| Q6 pratiques de développement | 3 | 0 |
| Q7 observabilité | 2 | 0 |
| **Total** | **21, soit 3,0 par question** | **9, soit 1,29 par question** |

**Le gain réel est de 14 %, pas de 160 %.** La raison est de conception : le multi-select offre au client une sortie de secours groupée ("aucune de ces affirmations" ou "je ne sais pas" pour cinq critères d'un coup), et il la prend. Le choix unique, lui, force une réponse déterminée par question.

Quatre défauts de cette tentative, à ne pas reproduire :

1. **La plomberie était visible par le lecteur.** Les annotations du genre "0.1 = niveau d'impact élevé si coché" et les mentions "couvre EOF 0.1, 0.3, 6.10" s'adressaient à l'outil, pas au service audité. C'est le défaut que le commit `104e0ec` a corrigé dans le questionnaire actuel.
2. **Des cases contradictoires cochables ensemble.** Une question proposait "une politique de suppression existe" et "pas de politique formelle" dans la même liste ; une autre, "objectif de disponibilité formel" et "un mode dégradé serait acceptable", qui tirent le même critère en sens inverses. Rien n'empêchait de cocher les deux.
3. **Une case collait "aucune de ces pratiques n'est en place" et "je ne sais pas".** Ce sont deux réponses opposées : l'une est un constat, l'autre est l'absence de constat. Le référentiel EOF fait déjà cette faute dans 8 de ses crans, cf. `.claude/skills/eof/docs/source-sheet/PIEGES-REFERENTIEL.md`. Ne pas la refaire.
4. **Perte de résolution structurelle.** 15 des 16 questions du diagnostic rapide ont **5 crans** (`0.13` en a 3) : une case à cocher n'en exprime que 2. Cocher "objectif de disponibilité formel" ne distingue pas 99 % de 99,99 %. Sur la dimension 6, le niveau intermédiaire `🟡 Effort modéré`, de coefficient 0,5, devient inatteignable.

## Session 19 : ce qu'il faut emprunter à cette tentative

Le format est écarté, **la formulation est bonne à prendre**. Trois emprunts, retenus par l'utilisatrice dans cet ordre.

### Emprunt 1 : rappeler dans la question ce que les sondes ont déjà mesuré

Faire lire au service audité le fait mesuré avant qu'il réponde, pour qu'il **confirme ou corrige** au lieu de deviner. Bénéfice secondaire : sa réponse cesse d'être une déclaration en l'air.

**Portée réelle, mesurée : 17 des 62 blocs**, pas la totalité.

| | Nombre | Identifiants |
|---|---|---|
| Critères détaillés avec un `contexte` non vide et sans réponse | 16 | `1.4, 1.9, 1.11, 1.14, 1.15, 1.16, 2.3, 2.5, 3.2, 3.5, 3.7, 5.5, 6.1, 6.3, 6.6, 6.8` |
| Questions du diagnostic rapide avec un `indice_contextuel` non vide et sans réponse | 1 | `0.4` |
| Critères avec un `contexte` mais **déjà** répondus, donc sans question posée | 0 | - |

Les 45 autres blocs n'ont **aucun** fait mesuré à rappeler : l'emprunt améliore un quart du questionnaire. Bonne nouvelle en revanche, ces 17 textes sont **rédigés pour un lecteur humain**, avec unités et nuances, et non des dumps techniques : ils sont réutilisables presque tels quels.

### Emprunt 2 : reformuler les questions en affirmations concrètes sur le service

Remplacer l'intitulé du référentiel par une affirmation que le client peut confirmer. "Disparition du service = impact fort sur l'image, le recrutement, le commerce" se répond ; "Les composants principaux sont-ils soumis à des contraintes de haute disponibilité ?" fait hésiter. **Zéro code**, travail rédactionnel sur les 62 blocs de la bibliothèque.

⚠️ Contrainte non négociable : la reformulation porte sur le champ `question` et le champ `aide`, **jamais** sur les libellés de réponse d'un bloc `type: "direct"`, qui sont lus dans le référentiel, ni sur les valeurs du dictionnaire `reponses` d'un bloc `type: "compose"`, qui doivent rester des libellés exacts du référentiel au caractère près.

### Emprunt 3 : un titre thématique qui dit à qui passer la question

"Maturité d'ingénierie et connaissance du code" indique l'interlocuteur, là où un intitulé de critère ne le fait pas. La coupure `produit-usage` / `technique` existe déjà, l'indication de l'interlocuteur non.

## Session 19 : décision sur la granularité et la provenance

Question posée : accepterait-on une réponse **plus grossière** en échange d'une question qui couvre plus de critères, à condition que ce soit signalé dans la provenance ?

**Réponse : l'axe de provenance ne sait pas l'exprimer, et on ne le modifie pas.**

L'axe est fermé à 5 valeurs par `processus/valider_sortie_lot.py:65`, avec la précédence `collecte > estime > declare > precise > suppose`. Le manifeste dit ce qu'elles veulent dire (`processus/manifeste-lots.json:11`) :

> La provenance 'suppose' designe une deduction depuis un indice faible : elle est placee en derniere position de precedence car une case cochee par le client sans preuve (precise) vaut davantage - le client connait son equipe alors que nous devinons depuis un signal qui parle souvent d'autre chose.

L'axe répond donc à **"qui l'affirme, et sur quelle base ?"**, pas à **"à quel point la réponse est-elle fine ?"**. Y ajouter un 6ᵉ niveau mélangerait deux natures d'incertitude sur un seul axe, ce que la consigne du projet interdit, et casserait l'axe unique partagé avec la table de badges e-footprint.

**Décision de principe, à appliquer le jour où la question se posera vraiment** : la granularité serait un **marqueur séparé**, jamais un niveau de provenance.

La question ne se pose pas aujourd'hui : aucun des trois emprunts retenus ne rend une réponse plus grossière. Elle ne se posait qu'avec le format multi-select, écarté.

## Session 19 : ce que le code fait déjà, et ce qui manque pour l'emprunt 1

État relevé dans `.claude/skills/analyse-parcours/scripts/generate_questionnaire.py` :

| Point | État |
|---|---|
| Clés lues dans `eof-audit-results.json` | `id` et `reponse` **seulement**, lignes 143-153 |
| `contexte` et `indice_contextuel` | **non lus**, c'est tout le manque |
| Condition de rétention d'un bloc | lignes 216-219, retenu si au moins un de ses critères est sans réponse |
| Rendu du champ `aide` | lignes 312-313, rendu **tel quel**, enrobé d'italique, aucune autre mise en forme |

Contrat de lot, dans `processus/valider_sortie_lot.py` : le champ `contexte` est **autorisé** sur une entrée de critère (lignes 159-162), et `provenance` ainsi que `source` sont **requis et non vides** dès que `reponse` **ou** `contexte` est non null (lignes 246-249, règle verbatim `"requis si reponse ou contexte non null"`).

Généricité : le fait mesuré est injecté **au moment de la génération**, depuis le dossier d'audit. La bibliothèque `questionnaire-blocs.json` ne contient donc aucune valeur d'un site particulier et **reste générique**. ⚠️ À savoir sur l'outil de contrôle : `check_genericite.py` vise par défaut les fichiers `.py` de `efootprint_model/`. Pointé explicitement sur la bibliothèque JSON il tourne et passe. **Pointé sur un fichier Markdown il échoue toujours**, y compris sur un fichier intact, parce qu'il parse ses cibles comme du Python. Ce n'est pas une régression : ne pas partir en chasse.

## Session 19 : spécification de l'emprunt 1, pour la session suivante

Travail exécutable par Sonnet à partir de cette seule section.

**Objectif** : quand un bloc est retenu, faire apparaître sous la question le fait déjà mesuré pour le ou les critères que ce bloc couvre, s'il existe.

**Sources à lire dans le dossier d'audit** : `criteres[].contexte` pour les critères détaillés, `diagnostic_rapide_apercu.questions[].indice_contextuel` pour les `0.x`.

**Pièges à traiter explicitement, chacun a déjà coûté au projet** :

1. **Une clé peut exister et valoir `null`.** Un repli du genre `bloc.get("contexte", "")` ne protège de rien : la clé est présente, sa valeur est `None`, et elle s'affiche telle quelle au lecteur. Tester `is not None` **et** la chaîne vide.
2. **Le texte injecté s'adresse au service audité, pas à l'outil.** Interdiction d'y faire figurer un identifiant de critère, un nom de sonde, un nom de fichier ou de fonction. C'est le défaut corrigé par `104e0ec`, et le contrôle est visuel : lire le Markdown généré.
3. **Un bloc `type: "compose"` couvre plusieurs critères**, donc potentiellement plusieurs `contexte`. Décider et documenter ce qu'on fait : les concaténer, n'en garder qu'un, ou ne rien afficher. Ne pas laisser le comportement émerger du hasard de l'itération.
4. **Le rappel ne doit rien affirmer de plus que ce que la sonde a trouvé.** Une sonde qui n'a rien trouvé ne prouve pas l'absence : ne jamais transformer un zéro en constat.
5. **45 blocs sur 62 n'ont aucun fait à rappeler.** L'absence doit être silencieuse : pas d'intitulé orphelin, pas de "Rappel :" suivi de rien.

**Contrôles à passer avant tout commit** :

```bash
cd "/Users/pierrick.crepy/Documents/missions/MyAIEnv/Agent EROOM"
python3 .claude/skills/analyse-parcours/scripts/valider_blocs_questionnaire.py
python3 .claude/skills/analyse-parcours/scripts/valider_blocs_questionnaire.py --autotest
python3 .claude/skills/analyse-parcours/scripts/generate_questionnaire.py --autotest
python3 .claude/skills/analyse-parcours/scripts/parse_questionnaire.py --autotest
python3 .claude/skills/analyse-parcours/scripts/check_valeurs_rapport.py --autotest
python3 processus/valider_manifeste.py
python3 processus/valider_coherence_cles.py
```

⚠️ Ne jamais enchaîner un script avec `| tail` : le code de sortie rendu serait celui de `tail`.

**Nouveaux autotests attendus** : un critère dont `contexte` vaut `null`, un dont il vaut la chaîne vide, un bloc composé dont un seul des deux critères a un contexte, et un audit dont **tous** les contextes sont vides.

**Vérification par le rendu, obligatoire** : générer le questionnaire sur un audit réel **et** sur un audit entièrement vide, puis **lire le Markdown produit**, pas compter des occurrences. L'audit vide se fabrique dans `/tmp`, jamais dans `audits/` :

```bash
mkdir -p /tmp/audit-zero/site-x.fr
jq '.domaine="site-x.fr"
  | .criteres = [.criteres[] | .reponse=null | .coefficient=null | .provenance=null
                 | .source=null | .contexte=null | .categorie="aucune_donnee"]
  | .criteres_repondus=0 | .completude_globale_pct=0
  | .diagnostic_rapide_apercu.questions = [.diagnostic_rapide_apercu.questions[]
      | .reponse=null | .provenance=null | .source=null | .indice_contextuel=null]' \
  audits/octo.com/eof-audit-results.json > /tmp/audit-zero/site-x.fr/eof-audit-results.json
python3 .claude/skills/analyse-parcours/scripts/generate_questionnaire.py /tmp/audit-zero/site-x.fr
```

Attendu sur l'audit vide : **62 blocs posés**, la bibliothèque entière, et **aucun rappel de mesure affiché**.

## Prochaines étapes

1. **Emprunt 1, le rappel des mesures dans la question.** Spécifié ci-dessus, exécutable tel quel. Sonnet suffit.
2. **Emprunt 2, la reformulation des 62 questions en affirmations concrètes.** Zéro code.
3. **Emprunt 3, les titres thématiques avec indication de l'interlocuteur.**

⛔ **Ce qui est clos et ne doit pas être rouvert** :

- **Le regroupement de questions.** Les 5 grappes antérieures plus la fusion `0.3` + `6.10` closent le sujet.
- **Le format multi-select à cases indépendantes.** Écarté sur mesure : 1,29 contre 1,13, cf. la section dédiée.
- **Le tri des questions par potentiel décroissant.** 4,5 questions gagnées sur 37, sans intérêt.
- **La chasse aux recoupements entre diagnostic rapide et critères détaillés.** Les 6 ont été passés au crible, un seul était exploitable.
- **L'espoir d'automatiser davantage.** Le plafond est structurel, pas un défaut d'outillage : les méthodes d'évaluation du référentiel exigent des faits internes à l'équipe, qu'aucune sonde ne peut observer.

Le levier qui reste n'est pas de poser **moins** de questions, c'est de rendre chaque question **plus facile à répondre**.

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
