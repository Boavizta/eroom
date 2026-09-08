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
   - Génère `questionnaire-eof.md` (un seul fichier)
   - Calcule le résidu (critères sans verdict utile)
   - Ordonnance les blocs par rendement décroissant (nombre de critères couverts), puis phase "porte" avant "detail"

2. **`parse_questionnaire.py`**
   - Lit `questionnaire-eof.md`
   - Produit `lots/relecture-questionnaire.json`
   - Vérifie exactement une case cochée par bloc
   - Respecte le contrat de sortie de lot (5 clés racine, omission des null)
   - Pose un bloc `mesure` conforme à la convention d'état de mesure

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
- Bloc mesure conforme à la convention : fichier absent = `echec_lecture`, fichier vide = `rien_trouve`, fichier répondu = `ok`

## Décisions clés prises

### 1. Le résidu inclut "🤔 À évaluer" et "⌛️ Évaluation en cours"

**Raison** : Ces réponses ont un coefficient 0 et comptent comme des réponses dans le reste du code, mais NE TRANCHENT RIEN. Si on ne les repose pas, le critère reste un faux zéro détectable.

**Impact** : Un critère avec ces réponses est reposé dans le questionnaire.

### 2. Options des blocs "direct" lues dans le référentiel

**Raison** : Éviter toute divergence entre la bibliothèque de blocs et le référentiel. Les options ne sont jamais recopiées.

**Impact** : 
- Critère détaillé : lecture de `options_evaluation`
- Question diagnostic rapide : lecture de `crans`

### 3. Ordonnancement par rendement décroissant sur les critères restants

**Raison** : Axe unique et prioritaire - minimiser le nombre de questions posées, maximiser le nombre de critères répondus, et le plus précisément possible. Les questions qui renseignent PLUSIEURS critères passent d'abord.

**Impact** : Le rendement se calcule sur les critères RESTANTS dans le résidu. Un bloc dont la mesure a déjà tranché une partie redescend automatiquement dans l'ordre. Exemple réel : le bloc "parcours et écrans" tombe en 41e position parce que le critère 1.13 a déjà été tranché par la mesure, il ne rapporte donc plus qu'un critère.

**Structure** : Le questionnaire garde DEUX PARTIES (porte puis détail), avec le tri par rendement décroissant à l'intérieur de chacune. Ce n'est pas un tri global, et c'est délibéré : la porte sert à décider si un diagnostic approfondi vaut la peine.

**Mesure ultérieure** : La session 19 a montré que ce tri ne fait gagner que 4,5 questions sur 37 par rapport à un tirage au hasard. Le tri est conservé parce qu'il ne coûte rien et qu'il permet à l'interlocuteur de s'arrêter en sachant ce qu'il laisse, mais il ne faut pas en attendre un gain de compaction. Voir la section "Session 19 : le plafond du format actuel, mesuré".

### 4. Un seul fichier, le destinataire n'est plus un axe de classement

**Décision** : `questionnaire-eof.md` remplace les deux fichiers `questionnaire-produit-usage.md` et `questionnaire-technique.md`.

**Raison** : Le découpage ne routait rien. Sur 4 destinataires, 3 recevaient des questions dans les DEUX fichiers. Envoyer "le fichier produit" au responsable produit lui cachait 5 questions qui le concernaient et lui en donnait 5 qui ne le concernaient pas. Répartition mesurée des 62 questions par destinataire : équipe de développement 30, responsable produit 16, exploitation de l'infrastructure 12, personne qui gère les données 4.

Le destinataire reste écrit dans le titre de chaque question, sous la forme "à voir avec l'équipe de développement". Classer le document par destinataire a été explicitement ÉCARTÉ : le découpage des rôles dépend trop de l'organisation de chaque client.

### 5. Case "Je ne sais pas" ajoutée à chaque bloc

**Raison** : Distinguer "on a demandé et personne ne sait" de "personne n'a demandé". Évite de fabriquer un faux zéro qui rend un service ignoré indistinguable d'un service exemplaire.

**Impact** : Le parseur produit un `contexte` mais JAMAIS de `reponse` pour cette case.

### 6. Provenance = "precise", catégorie = "aucune_donnee"

**Raison** : Contrat de lot - une case cochée par le service audité, sans preuve, ne vient d'aucune donnée collectée.

**Impact** : Tous les critères versés portent ces valeurs fixes.

### 7. Format Markdown strict

**Raison** : Consignes de style du projet (TTS macOS lit les séparateurs en signes égal lettre par lettre).

**Impact** :
- Séparateurs en `-----` uniquement
- Guillemets droits `"`
- Pas de tiret long (cadratin)

### 8. Coefficient obligatoire pour critères détaillés, absent pour diagnostic rapide

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
      "fichier": "produit-usage" | "technique",  (vestigial, n'est plus utilisé)
      "phase": "porte" | "detail",
      "titre": "...",
      "interlocuteur": "..." (facultatif),
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

Racine : exactement 5 clés `lot_id`, `genere_le`, `entrees`, `criteres`, `mesure`.

La clé `mesure` est la dernière arrivée. Elle porte l'état de lecture du questionnaire, décrit plus
bas dans "Le bloc mesure sur le lot de relecture".

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
- Branchement dans le pipeline d'audit (voir section dédiée ci-après)

## Traçabilité des bugs corrigés en autotest

1. **Bug regex** : `[^-\s]+` n'acceptait pas les tirets dans les IDs de blocs (ex: `test-11`). Corrigé en `[^\s]+?`.
2. **Bug JSON Python** : `null` au lieu de `None` dans les autotests. Corrigé dans 5 endroits.
3. **Bug fichier absent** : autotests du parseur ne créaient pas `questionnaire-eof.md`. Corrigé en créant le fichier dans le répertoire temporaire de test.

## Vérifications effectuées

- **Aucune trace d'audit spécifique** : pas de "octo.com", pas d'IP, pas de chemin `audits/quelquechose` dans le code (vérifié par `grep -i "octo|192\.|audits/"`)
- **Autotests exécutés et validés** : codes de sortie 0 pour les deux scripts
- **Commentaires en français** : conformément aux consignes du projet
- **Style respecté** : séparateurs `-----`, guillemets droits, pas de tiret long

## Commandes de référence

```bash
# Générer le questionnaire
python3 .claude/skills/analyse-parcours/scripts/generate_questionnaire.py <repertoire-audit>

# Parser le questionnaire rempli
python3 .claude/skills/analyse-parcours/scripts/parse_questionnaire.py <repertoire-audit>

# Lancer les autotests
python3 .claude/skills/analyse-parcours/scripts/generate_questionnaire.py --autotest
python3 .claude/skills/analyse-parcours/scripts/parse_questionnaire.py --autotest

# Fusionner les lots (OBLIGATOIRE après parse_questionnaire.py ou run_eof.py)
python3 processus/fusionner_lots.py <repertoire-audit>

# Contrôler la santé des sondes (détecte les échecs de mesure)
python3 processus/valider_sante_sondes.py <repertoire-audit>
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

## Les trois emprunts sont faits

| Emprunt | Commit | Ce que le client voit |
|---|---|---|
| 1, le rappel des mesures | `9ba4f5b`, textes réécrits pour lui en `e091e98` | sous la question, le fait déjà mesuré, à confirmer ou corriger |
| 2, les questions en affirmations | `2f4205d`, relu en `009a647` | les 62 questions écrites dans ses mots, sans aucun acronyme interne |
| 3, les titres et l'interlocuteur | `431e127`, relu en `009a647` | `## 3 sur 41 - Disponibilité du code source (à voir avec l'équipe de développement)` |

La plomberie interne du Markdown (`Critères EOF couverts`, `Potentiel débloqué`) est passée en
commentaires HTML en `f28bf8e` : elle n'est plus lue par le client.

⚠️ **Les textes de mesure viennent du dossier d'audit, pas du code de génération.** Un dossier
d'audit produit avant `e091e98` publie donc encore les anciens textes, avec leurs acronymes
internes. Les rafraîchir se fait **sans appel réseau**, en rejouant `run_eof.py` sur une copie du
dossier : il ne relit que des fichiers déjà sur le disque. Vérifié, aucun verdict ne change et le
radar reste identique à l'octet ; seuls les 16 textes de contexte sont réécrits.

-----

## Session 25, 2026-09-08 : l'axe unique, et ce qu'il donne quand on le suit

Tout ce qui suit relève d'un seul axe, posé par l'utilisatrice et prioritaire sur tout le reste :
**poser le moins de questions possible pour faire répondre le plus grand nombre de critères, et le
plus précisément possible.** Le contenu des questions et leur ordre découlent de cet axe, et de rien
d'autre. En particulier, ni le destinataire ni le confort de lecture ne sont des axes de classement.

Deux conséquences valent d'être dites tout de suite, parce qu'elles ferment des pistes qui reviennent
naturellement à l'esprit. La redondance apparente entre questions n'est presque pas exploitable, et
gagner des questions en remplaçant une question par un indice technique approximatif est un recul,
pas un gain : cela fait baisser le compteur en fabriquant de l'imprécision.

### Les comptes réels

70 critères au référentiel (54 détaillés sur 6 dimensions + 16 questions de diagnostic rapide).

62 blocs de questions dans la bibliothèque, ce qui est un PLAFOND et non le nombre posé : `generate_questionnaire.py` ne garde que les critères restés sans réponse.

Sur un audit réel, 57 questions ont été produites, contre 16 + 41 = 57 avec l'ancien code : le regroupement ne coûte aucune question.

8 critères sont tranchés par la mesure seule (1.5, 1.6, 1.12, 1.13, 2.1, 3.3, 5.4 et 0.16).

16 critères reçoivent un contexte affiché mais JAMAIS de réponse.

46 critères qu'aucune sonde n'atteint.

### La fusion est épuisée

Les 8 blocs de type composé couvrent 16 critères à eux seuls. Une recherche exhaustive a conclu qu'AUCUNE fusion supplémentaire n'est possible sans perte.

Une seule paire nouvelle a été proposée, 1.1 avec 1.7, et elle a été rejetée : 1.1 demande si une solution non numérique a été écartée preuve en main, 1.7 si chaque fonctionnalité est réellement utilisée, et une réponse "potentiel d'amélioration" ne dirait plus lequel des deux manque.

Dix fusions tentantes ont été examinées et rejetées, toutes sur le même mécanisme : DEUX PRATIQUES DÉCOUPLÉES DANS LA VRAIE VIE. Liste à ne pas rouvrir : 1.2 avec 2.2, 1.5 avec 1.10, 1.3 avec 1.6, 3.1 avec 3.2, 4.2 avec 4.3, 6.1 avec 6.6, 6.2 avec 6.4, 6.3 avec 6.4, 1.11 avec 1.12, 2.3 avec 2.4. Exemples parlants : un CI/CD peut tourner sans tests, on peut faire du FinOps sans GreenOps, une base mal choisie peut être correctement optimisée.

### La contrainte des deux vocabulaires

⚠️ **Ce paragraphe affirmait l'inverse de ce que dit le référentiel, et il a été corrigé en session 26 après lecture directe de `eof-referentiel.json`. Le référentiel fait foi.**

Les 44 critères des dimensions 1 à 5 offrent "🚫 Non applicable", coefficient 0, ainsi que "🤔 À évaluer". Les 16 questions de diagnostic rapide 0.x n'offrent NI l'un NI l'autre : elles portent des crans graduués, sans option de non-applicabilité. Les 10 critères de la dimension 6 portent leur propre échelle à trois crans, "🟢 Facile à modifier" / "🟡 Effort modéré" / "🔴 Difficile à changer", et n'offrent pas non plus "Non applicable".

Conséquence, inchangée : fusionner une 0.x avec un critère des dimensions 1 à 5 rend une réponse INEXPRIMABLE. C'est le "🚫 Non applicable" du critère détaillé qui devient impossible à cocher, puisque les crans de la 0.x ne le proposent pas.

C'est pour cela que le seul bloc composé touchant une 0.x associe 0.3 et 6.10.

Conséquence pratique : sur 5 groupes de questions redondantes repérés, 4 traversent cette frontière et ne sont donc pas fusionnables ; seul 0.7 avec 0.10 l'est, pour un gain d'une seule question. La redondance apparente n'est PAS le levier.

### "Non applicable" et sans_objet sont désormais UN SEUL mécanisme, le critère écarté

⚠️ **Réunifiés en session 26. Contrat complet dans `convention-critere-ecarte.md`, qui fait foi. Ce qui suit résume, et décrit au passage l'état d'AVANT, parce que c'est ce défaut-là qui a été fermé.**

Un critère est **écarté** quand il ne s'applique pas au service. Deux chemins mènent au même état et produisent exactement les mêmes chiffres : sa `reponse` vaut "🚫 Non applicable", ou son booléen `sans_objet` vaut vrai. Un critère écarté sort de TOUS les dénominateurs, ne compte dans aucun numérateur, et n'est visible que dans la nouvelle clé `criteres_ecartes`.

**L'état d'avant, à ne pas restaurer.** La réponse "🚫 Non applicable" comptait dans `criteres_repondus` et ne retirait le critère d'aucun dénominateur. Elle se comportait donc exactement comme "🤔 À évaluer" : les deux gonflaient la complétude sans rien apporter au potentiel. Démonstration : 10 critères dont 3 répondus, passer les 7 autres à "Non applicable" donnait `criteres_repondus` 3 vers 10, `completude_pct` 30 % vers 100 %, et `potentiel_optimisation_pct` 15 % vers 15 %, INCHANGÉ.

**Le piège de fond, qui a décidé du reste.** "🚫 Non applicable" et "✅ Point fort confirmé" portent le MÊME coefficient 0. Compter un critère écarté comme répondu le rend donc arithmétiquement identique à un point fort : un service sans base de données aurait vu sa dimension 4 affichée à 0 % de potentiel d'optimisation, c'est-à-dire comme la dimension la mieux notée de son rapport. D'où le troisième état `hors_perimetre` par dimension, qui sort `null` et jamais 0 %.

**La divergence entre les deux producteurs est corrigée** : `run_eof.py` et `fusionner_lots.py` traitent désormais les deux chemins de la même façon. Au passage, une incohérence interne de `fusionner_lots.py` a été fermée : son total par dimension soustrayait déjà les écartés, son total global non.

### Un levier apparent, refusé : remplacer une question par un indice technique

Six questions pourraient être approchées par un signal que nous mesurons déjà : 0.4 par le nombre de
domaines tiers, 0.10 par le nombre d'URL du sitemap, 1.9 et 1.14 par le poids de page, 2.5 par les
codes HTTP 304, 6.3 par la fraîcheur des déploiements.

Ce sont des proxys faibles. Un déploiement récent ne prouve pas qu'un pipeline existe, un poids de
page ne dit rien de la clarté d'un écran. Les transformer en réponses gagnerait 6 questions **en
dégradant la précision**, c'est-à-dire l'inverse du but. Refusé.

### Les questions filtres, implémentées en session 26

Une question filtre ne fait pas répondre 2 critères, elle en fait répondre dix quand la réponse est "ça ne s'applique pas chez nous" : un service sans base de données propre règle la dimension 4 d'un coup, sans perte de précision puisque "Non applicable" est une réponse légitime du référentiel pour les dimensions 1 à 5.

**Contrat complet dans `convention-critere-ecarte.md`. Ce qui suit ne dit que ce qu'il faut savoir en lisant le code.**

Un troisième `type` de bloc, `filtre`, à côté de `direct` et `compose`. Il porte une liste `criteres` au lieu d'un `critere` au singulier, plus un `libelle_ecarte` et un `libelle_applicable`. Cocher `libelle_ecarte` verse une entrée "🚫 Non applicable" par critère, sans promotion de provenance ; cocher `libelle_applicable` ne verse RIEN, les critères restent à poser.

Les trois filtres livrés :

| Filtre | Critères gouvernés | Potentiel |
|---|---|---|
| Pas d'interface utilisateur humaine | 1.4, 1.5, 1.8, 1.9, 1.10, 1.11, 1.13, 1.14, 5.9 | 12,5 |
| Pas de données persistantes propres | 4.1 à 4.6 | 8,0 |
| Pas d'environnement de test distinct | 3.8, 3.9 | 4,5 |

4.4 est volontairement laissé au filtre "données persistantes" seul : `valider_blocs_questionnaire.py` interdit le recouvrement entre deux filtres, alors qu'il tolère celui d'un filtre avec un bloc `direct`, qui est le principe même du levier.

Trois règles qu'on ne devine pas en lisant le code :

1. **Un filtre n'est imprimé que si aucun de ses critères ne porte déjà une réponse tranchante.** Si la mesure a tranché un seul de ses critères, elle a prouvé que le sujet s'applique. Sur `audits/octo.com`, le filtre "pas d'interface utilisateur" n'est donc PAS imprimé, parce que 1.5 et 1.13 sont tranchés par la collecte.
2. **Un filtre est en phase `detail`, en tête de la partie détaillée**, jamais en phase `porte` : il ne gouverne que des critères du diagnostic détaillé, et le mettre en porte le ferait poser avant même la décision d'aller plus loin.
3. ⚠️ **Un filtre ne RETIRE aucune question du document.** Le générateur ne connaît pas la réponse au filtre au moment où il écrit. Sans correctif, le levier allonge le questionnaire et n'économise rien : il ne rend que de la véracité au rapport, pas de l'effort au client. D'où la mention "À IGNORER" portée par tout bloc dont TOUS les critères sont gouvernés, avec une condition en **conjonction, jamais en disjonction**.

**Ce levier n'est pas une réduction garantie.** Pour un site web classique, les filtres reçoivent "cela s'applique" et n'écartent rien : le questionnaire s'allonge alors de deux questions. Le gain n'existe que pour les services dont une partie du référentiel ne parle pas. C'est un pari sur la diversité des services audités, à présenter comme tel.

**GARDE-FOU, tenu** : le rapport affiche À PART le nombre de critères écartés, via un KPI `Écartés` lisant `criteres_ecartes`. Sans lui, une complétude de 100 % construite sur des exclusions serait indiscernable d'un audit réellement instruit : on fabriquerait de la complétude.

### Le bloc mesure sur le lot de relecture

`parse_questionnaire.py` produit un bloc `mesure` conforme à `documentation/implementation/convention-etat-de-mesure.md`, avec trois statuts :

- `echec_lecture` si le fichier est absent ou illisible
- `rien_trouve` s'il est lu mais qu'aucune case n'est cochée
- `ok` sinon

Vérifié par les trois tests de convention : fichier absent, `valider_sante_sondes.py` sort en 1 et nomme l'échec ; fichier présent et vide, il sort en 0 sans faux positif ; fichier répondu, il sort en 0.

Un questionnaire revenu entièrement vide est un résultat d'audit légitime, pas un échec de notre outil : c'est `rien_trouve`, jamais `ok` ni `echec_*`.

Sur un dossier sans questionnaire, `parse_questionnaire.py` écrivait un lot indistinguable d'un questionnaire revenu entièrement vide. Le lot porte désormais un bloc mesure qui distingue les deux cas.

### Le questionnaire n'est branché nulle part dans le pipeline

Établi par `grep` sur `SKILL.md` et les 9 fichiers de skill-steps : le mot "questionnaire" n'apparaît qu'une fois, dans une parenthèse de nom de plan à `39_eof-audit.md` ligne 16. Aucune étape n'appelle `generate_questionnaire.py`. Aucune échéance de retour n'est encodée nulle part.

Le circuit complet est dessiné dans `documentation/diagrammes/eof-questionnaire-sequence.pdf`, 3 pages : ce que l'audit lance seul, générer et envoyer hors pipeline, relire et fusionner.

### Le piège de manipulation

`run_eof.py` réécrit `eof-audit-results.json` sans relire les lots. Le relancer seul après une fusion fait donc disparaître du rapport, EN SILENCE, toutes les réponses du questionnaire. Il faut toujours relancer `fusionner_lots.py` derrière lui.

### Une leçon de méthode à ne pas oublier

La fusion en un seul fichier a d'abord été commitée après `py_compile` et `valider_coherence_cles.py`, SANS lancer `parse_questionnaire.py --autotest`. Cet autotest fabriquait ses fixtures sous les deux anciens noms de fichier : 6 cas sur 7 tombaient, et la fusion était donc livrée avec son propre filet de sécurité crevé. Corrigé, 7 sur 7.

La batterie de `processus/CONTROLES.md` ne suffit donc pas : **un script qui porte un `--autotest`
doit voir son `--autotest` rejoué avant tout commit.** Cette règle est désormais inscrite dans
`processus/CONTROLES.md`, avec la liste des **six** scripts concernés et la commande pour la
retrouver plutôt que de lui faire confiance.

## Chantiers livrés

1. **Chantier 13, le radar à deux couches** : livré. Le script `generate_radar_svg.py` produit un radar distinguant les provenances par deux couches.
2. **Chantier 31, séparateurs accessibles** : livré. Les séparateurs fabriqués dynamiquement ont été corrigés.

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
