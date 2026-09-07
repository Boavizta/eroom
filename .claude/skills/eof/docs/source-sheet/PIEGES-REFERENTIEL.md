-----
-----
# Les pièges du référentiel EOF, relevés verbatim
-----
-----

**Ce fichier ne contient aucune opinion sur EOF.** Il recense les endroits où le référentiel,
tel qu'EROOM le publie, dit autre chose que ce qu'on croit lire. Chaque piège est appuyé sur le
texte exact de la source, pour qu'on puisse le retrouver sans le redécouvrir.

**Pourquoi ce fichier existe** : le même accident s'est produit au moins six fois dans ce projet.
Quelqu'un lit le libellé d'un critère, en déduit ce qu'il faut demander, et se trompe, parce que
le libellé et la méthode d'évaluation ne posent pas la même question. Chaque fois, le résultat est
une réponse fausse dans le livrable, ce qui est pire qu'une case vide.

**LA RÈGLE D'OR, elle explique la moitié de ce document** : c'est la clé `methode` qui définit ce
que le critère mesure. Ni le libellé (`critere`), ni le texte pédagogique (`explication`). Ces
deux-là servent à parler au lecteur, la `methode` sert à trancher.

-----

## Où est la source, et comment revérifier ce fichier

Tout ce qui suit est extrait de :

```
.claude/skills/eof/docs/EOF-V.1.1 (EROOM Optimization Framework) - Template - Français/eof-referentiel.json
```

C'est le seul fichier que le code lit. La copie des 9 onglets de la Google Sheet d'EROOM est dans
`docs/source-sheet/`, et `verifier_source_sheet.sh` dit si EROOM a fait évoluer sa source depuis.

Les libellés d'options sont recopiés **au caractère près**, emojis compris, parce que
`valider_blocs_questionnaire.py` refuse tout libellé qui n'existe pas dans le référentiel. Ne
jamais les retoucher pour les rendre plus jolis.

Pour revérifier un point de ce fichier, la commande générique :

```bash
python3 - <<'PY'
import json
R=".claude/skills/eof/docs/EOF-V.1.1 (EROOM Optimization Framework) - Template - Français/eof-referentiel.json"
d=json.load(open(R))
cr={c["id"]:c for c in d["criteres"]}
dr={q["id"]:q for q in d["diagnostic_rapide"]}
c=cr["5.3"]                       # remplacer par l'id voulu
print(c["critere"]); print(c["explication"]); print(c["methode"])
print(c["options_evaluation_coefficient"])
print(dr["0.13"]["crans"])        # pour une question du diagnostic rapide
PY
```

-----
-----
# Partie 1. Les pièges de structure
-----
-----

## 1.1 Il y a deux vocabulaires de réponse, et même trois façons de répondre

Le référentiel ne pose pas ses questions d'une seule manière. Compter dessus est le premier piège.

**Les 44 critères des dimensions 1 à 5** ont ces 5 options exactement, avec leur coefficient :

| Libellé exact | Coefficient |
|---|---|
| `✅ Point fort confirmé` | 0 |
| `💡 Potentiel d'amélioration identifié` | 1 |
| `🚫 Non applicable` | 0 |
| `🤔 À évaluer` | 0 |
| `⌛️ Évaluation en cours` | 0,5 |

Les ids concernés : 1.1 à 1.16, 2.1 à 2.5, 3.1, 3.2, 3.3, 3.5 à 3.9, 4.1 à 4.6, 5.1 à 5.9.

**Les 10 critères de la dimension 6** ont un vocabulaire complètement différent, et **seulement
trois options** :

| Libellé exact | Coefficient |
|---|---|
| `🟢 Facile à modifier` | 0 |
| `🟡 Effort modéré` | 0,5 |
| `🔴 Difficile à changer` | 1 |

Les ids concernés : 6.1 à 6.10. Il n'y a **ni `🚫 Non applicable`, ni `🤔 À évaluer`, ni
`⌛️ Évaluation en cours`** sur la dimension 6. Un code qui suppose que les 5 options existent
partout plante ou fabrique une réponse inconnue du référentiel.

**Les 16 questions du diagnostic rapide** (ids `0.1` à `0.16`) n'ont pas d'options du tout : elles
ont des `crans`, une échelle rédigée, **différente pour chaque question**, et **sans aucun
coefficient**. Elles ne pèsent donc rien dans le potentiel d'optimisation. Le contrat de sortie de
lot l'impose d'ailleurs : une réponse posée sur une question `0.x` doit partir **sans** clé
`coefficient`, alors qu'un critère détaillé en exige une.

## 1.2 Le critère 3.4 n'existe pas

La dimension 3 va de `3.1` à `3.9` mais ne compte que **8 critères** : `3.4` est absent de la
source. Ce n'est pas une perte de données de notre côté, c'est un trou de numérotation chez EROOM.
Toutes les autres dimensions sont complètes.

Conséquence pratique : ne jamais générer une liste d'ids par une boucle sur un intervalle. Toujours
itérer sur ce que la source contient.

## 1.3 L'échelle de 1 à 5 du diagnostic rapide n'a pas de sens constant

**C'est le piège le plus dangereux pour le répondant, et il est invisible.** Les 16 questions
utilisent toutes une échelle numérotée de 1 à 5, mais **le sens du chiffre change d'une question à
l'autre**. Trois familles cohabitent.

**Famille A, 9 questions : le cran 1 est la situation défavorable, le cran 5 la favorable.**
`0.2`, `0.3`, `0.7`, `0.10`, `0.11`, `0.12`, `0.14`, `0.15`, `0.16`.

Exemple, `0.7` : cran 1 = `Très complexe / Je ne sais pas`, cran 5 = `Très simple`.

**Famille B, 3 questions : c'est l'inverse, le cran 1 est la situation favorable.**
`0.5`, `0.6`, `0.13`.

Exemple, `0.6` : cran 1 = `L'équipe maîtrise bien la conception fonctionnelle et technique du
projet et peut travailler en toute confiance.`, cran 5 = `Personne ne connaît le projet.`

Exemple, `0.5` : cran 1 = `Le code source est entièrement disponible (open source ou entièrement
accessible à l'organisation).`, cran 5 = `Non, le code source n'est pas disponible / Je ne sais
pas.`

**Famille C, 4 questions : l'échelle ne mesure pas un mérite mais une taille.** Ni bon ni mauvais.
`0.1`, `0.4`, `0.8`, `0.9`.

Exemple, `0.8` : cran 1 = `L'une des plus grandes infrastructures de l'organisation`, cran 5 =
`Très petite (par exemple, quelques machines virtuelles ou conteneurs)`.

**Conséquences, les deux comptent** :

1. Un répondant qui a compris que 5 est la bonne note se trompera sur `0.5`, `0.6` et `0.13`. Notre
   questionnaire affiche le libellé complet de chaque cran, ce qui protège, **à condition de ne
   jamais afficher le seul numéro et de ne jamais réordonner les crans**.
2. **On ne peut pas additionner ni moyenner les crans du diagnostic rapide.** Une note globale de
   la porte serait dénuée de sens. C'est cohérent avec ce que fait le code aujourd'hui : le
   diagnostic rapide n'a pas de score, on stocke le libellé du cran et rien d'autre.

## 1.4 La question 0.13 n'a que 3 crans, numérotés 1, 3 et 5

Toutes les autres questions ont 5 crans numérotés 1 à 5. `0.13` en a **trois**, et ils portent les
numéros **1, 3 et 5**, comme si deux crans avaient été retirés sans renuméroter.

Verbatim des trois crans :

```
1 - Dans le backlog et discussion récurrente
3 - Quelques améliorations sont possibles
5 - Aucun problème de performance identifié
```

Conséquence pour le code : **ne jamais déduire le rang d'un cran de son numéro imprimé.** Le
parseur retrouve la réponse par l'indice de la case cochée (`<!-- opt:N -->`, en base 0) et relit
le cran d'origine dans le référentiel. C'est la seule méthode sûre.

## 1.5 Huit crans collent un aveu d'ignorance à un cran extrême

**C'est le pire cas par défaut sur un inconnu, et il est dans la source.** Huit crans mélangent
une situation précise et la mention "je ne sais pas". Un répondant honnête qui ne sait pas se fait
donc attribuer un cran extrême.

Verbatim des huit, avec le numéro du cran tel qu'imprimé :

| Question | Cran concerné | Verbatim |
|---|---|---|
| `0.5` | cran **5** | `5 - Non, le code source n'est pas disponible / Je ne sais pas.` |
| `0.7` | cran 1 | `1 - Très complexe / Je ne sais pas` |
| `0.9` | cran 1 | `1 - Le produit dispose de l'un des plus grands volumes de stockage de données dans le SI / Je ne sais pas.` |
| `0.10` | cran 1 | `1 - Très complexe / Je ne sais pas` |
| `0.11` | cran 1 | `1 - L'UX/UI est très médiocre, les utilisateurs se plaignent et/ou il y a des éléments en attente pour le modifier / Je ne sais pas` |
| `0.12` | cran 1 | `1 - Incompatible ou inconnu` |
| `0.14` | cran 1 | `1 - Pas assez optimisé / ne sais pas` |
| `0.15` | cran 1 | `1 - Aucune politique / ne sais pas` |

Noter que `0.5` est le seul où l'aveu est collé au cran **5** et non au cran 1 : c'est une
conséquence directe de son orientation inversée, décrite en 1.3.

**Ce que notre code en fait, et pourquoi c'est sûr** : le générateur retire la mention du libellé
**affiché**, pour que le répondant ne se voie pas noté "très complexe" parce qu'il a dit ne pas
savoir. Le lot écrit, lui, porte toujours le cran d'origine mention comprise, parce que le parseur
retrouve la réponse par l'indice de la case et jamais par comparaison de texte. **Ne jamais faire
dépendre le parseur du texte affiché**, sinon ce nettoyage cesse d'être un confort de lecture et
devient une falsification.

Le répondant qui ne sait pas dispose par ailleurs d'une case "Je ne sais pas" à part, ajoutée par
notre générateur sur tous les blocs, qui ne pose aucune réponse et n'ajoute rien au radar.

-----
-----
# Partie 2. Le libellé ne dit pas ce que la méthode demande
-----
-----

C'est la famille de pièges qui a coûté le plus cher au projet. Elle se décline en quatre formes.

## 2.1 Environ vingt critères sont formulés à l'envers, et `✅ Point fort confirmé` répond à la méthode, pas au libellé

Une bonne moitié des critères pose une question dont la **bonne** réponse est "non". Exemples de
libellés : `Y a-t-il beaucoup de pisteurs (trackers) sur le produit ?`, `Le support des
applications est-il médiocre sur les appareils les plus anciens ciblés ?`, `Y a-t-il du code
dupliqué dans l'application ?`, `Les composants de déploiement (VM, serveur, conteneurs) sont-ils
surdimensionnés ?`, `Les indicateurs de performance sont-ils médiocres ?`.

Sur un critère comme celui-là, cocher `✅ Point fort confirmé` **ne veut pas dire "oui"**. Ça veut
dire "le critère de validation exprimé dans la `methode` est satisfait", donc ici "il n'y a pas
beaucoup de pisteurs".

**Conséquence, à ne jamais oublier en rédigeant une question** : le libellé d'une option ne
s'interprète que par rapport à la `methode`, jamais par rapport au libellé du critère. C'est pour
ça que les blocs de type `direct` de notre questionnaire n'écrivent pas leurs options à la main :
elles sont lues dans le référentiel, ce qui rend impossible une divergence.

## 2.2 Deux critères sont carrément rédigés comme une affirmation négative

Ce ne sont même pas des questions.

**`2.2`**, Déterminant, potentiel 2,0 :

```
critere : Il n'y a pas de stratégie de compatibilité.
```

**`3.2`**, potentiel 1,5 :

```
critere  : Il n'existe aucun système de suivi de l'impact environnemental.
methode  : Le point fort est confirmée si un suivi satisfaisant est en place, sinon il existe un
           potentiel d'amélioration.
```

Sur `3.2`, le libellé affirme l'absence d'un suivi et l'option `✅ Point fort confirmé` signifie
**qu'un suivi est en place**. Le libellé et l'option se contredisent littéralement. Seule la
`methode` permet de trancher, et elle est explicite ici, ce qui en fait un cas facile malgré les
apparences (elle porte au passage une faute d'accord, "est confirmée", recopiée telle quelle).

## 2.3 La méthode de 2.2 contient un morceau qui appartient à un autre critère

C'est le défaut le plus sérieux du référentiel dans cette liste, et il porte sur un **Déterminant
à 2,0**, soit 2,5 % du potentiel total à lui seul.

```
critere : Il n'y a pas de stratégie de compatibilité.
methode : Il existe un potentiel d'amélioration si le projet n'utilise pas d'outils d'élasticité
          et si la charge n'est pas constante. Le service n'est pas compatible avec tous les
          appareils ciblés ou la liste des appareils ciblés n'est pas connue.
```

La première phrase parle **d'élasticité et de charge**, ce qui est le sujet de `2.4` et de `3.7`,
et n'a aucun rapport avec une stratégie de compatibilité. La seconde phrase, elle, correspond bien
au libellé.

**Lecture retenue** : seule la seconde phrase est la méthode de `2.2`. La première est
vraisemblablement un reste de copier-coller dans la source EROOM. ⚠️ C'est une **interprétation**,
pas un fait : elle est écrite ici pour être discutable, pas pour être crue. Si `2.2` doit être
tranché un jour, s'appuyer sur la compatibilité et la connaissance de la liste des appareils
ciblés, et le dire dans le champ `source`.

## 2.4 Le libellé et la méthode posent parfois deux questions différentes

Cinq cas relevés, tous vérifiés verbatim. Dans chacun, une question rédigée d'après le libellé
**renseignerait le mauvais fait**.

**`1.12`**, potentiel 1,5 :

```
critere : Y a-t-il beaucoup de pisteurs (trackers) sur le produit ?
methode : Le suivi est strictement limité au strict nécessaire, le nombre de traceurs/outils est
          réduit au minimum et chaque demande de suivi est justifiée.
```

Le libellé fait croire à un comptage. La méthode demande une **justification**. Un seul traceur
non justifié échoue, vingt traceurs justifiés passent. Aucune sonde ne peut établir la
justification : c'est ce qui rend ce critère non automatisable, quelle que soit la qualité de la
capture réseau.

**`1.3`**, potentiel 1,5 :

```
critere : Les mises à jour des nouvelles fonctionnalités sont-elles obligatoires pour tous les
          appareils, quel que soit leur système d'exploitation ou leur navigateur ?
methode : Les tests montrent que la mise à jour ne dégrade pas les performances sur les appareils
          plus anciens ou modestes, et que le produit propose des modes optionnels ou allégés
          lorsque cela est nécessaire.
```

Le libellé parle du caractère obligatoire d'une mise à jour, la méthode parle de dégradation de
performance et de modes allégés. Ce ne sont pas les mêmes faits.

**`5.4`**, potentiel 1,0 :

```
critere : Les indicateurs de performance sont-ils médiocres ?
methode : Une amélioration est identifiée si les indicateurs de performance ne correspondent pas à
          l'ambition du projet (par exemple, plus de 2 secondes pour afficher une page web).
```

Il n'y a **pas de seuil absolu**. Le "2 secondes" est un exemple, pas une règle. Le fait
discriminant est l'écart à l'ambition du projet, que seule l'équipe produit connaît. C'est
pourquoi ce critère porte une mention "à valider avec le responsable produit" dans notre
questionnaire.

**`5.6`**, potentiel 1,5 :

```
critere : La pile technique (Java, JS, Python, PHP, etc.)est-elle pas à jour ?
methode : Une amélioration est identifiée si la base technique du projet n'est pas à jour au moins
          jusqu'à la dernière version LTS.
```

Le libellé est en français cassé et ambigu. La méthode fixe le seuil précis : **la dernière version
LTS**, ce qui n'est pas la dernière version stable. C'est ce qui distingue `5.6` de `5.8`, qui porte
sur les **dépendances** et demande la dernière version stable. Un socle Java 21 LTS avec un
framework de quatre ans satisfait `5.6` et échoue `5.8` : les deux critères sont bien distincts, il
ne faut pas les faire répondre par une seule case forcée.

**`5.1`**, potentiel 1,0 :

```
critere : Existe-t-il des outils d'analyse statistique permettant de mettre en évidence des
          améliorations potentielles en matière d'efficacité ?
```

Le référentiel dit **statistique**, pas "statique". Il est tentant d'y lire "analyse statique de
code", ce qui serait un autre sujet. ⚠️ Rien dans la source ne permet de trancher : ne pas
"corriger" ce mot, et rédiger la question de façon à couvrir ce que la méthode dit, à savoir des
outils en place qui ont mis en évidence des gains d'efficacité.

## 2.5 Quatre critères sont validés par l'absence de découverte, ce qui récompense l'inaction

Famille de pièges à part, et elle produit un faux service exemplaire si on la prend au mot.

```
5.1 methode : Une amélioration est identifiée si les outils d'analyse statistique en place ont
              révélé des gains d'efficacité potentiels.
5.2 methode : Une amélioration est identifiée si une campagne de tests de charge ou de résistance
              a révélé des problèmes d'efficacité.
5.3 methode : Le critère est validé si les tâches identifiées par l'équipe (problèmes, tickets,
              etc.) comportent des points permettant d'améliorer les performances/l'efficacité.
5.9 methode : Une amélioration est identifiée si l'équipe a détecté des problèmes de
              compatibilité.
```

Lues littéralement, `5.1`, `5.2` et `5.9` sont satisfaites quand **rien n'a été révélé**. Or une
équipe qui n'a **aucun** outil, **aucune** campagne et **aucun** test de compatibilité n'a
effectivement rien révélé : elle passerait pour exemplaire alors qu'elle n'a jamais regardé.

**Ce que le projet a décidé, et qui ne se rouvre pas** : l'absence de la pratique est traitée
comme un `💡 Potentiel d'amélioration identifié`, ce qui est l'intention manifeste du critère. Les
options de nos questions sont rédigées ainsi.

`5.3` est le cas symétrique et il est instructif : il est validé quand l'équipe **a** identifié des
sujets de performance. Voir la partie 4, croisement `0.13` et `5.3`.

-----
-----
# Partie 3. Les pièges de comptage
-----
-----

## 3.1 Trois options pèsent 0, et elles ne disent pas du tout la même chose

Sur les 44 critères des dimensions 1 à 5, **trois options ont le coefficient 0** :

```
✅ Point fort confirmé   coefficient 0   il n'y a rien à optimiser, et on l'a vérifié
🚫 Non applicable        coefficient 0   le sujet ne concerne pas ce service
🤔 À évaluer             coefficient 0   personne n'en sait rien
```

Une fois posées dans le fichier de résultats, **elles sont indistinguables dans tous les
pourcentages** : chacune compte comme une réponse et pose un point à 0 % sur son axe du radar.

**`🤔 À évaluer` est donc un aveu d'ignorance qui imite un service exemplaire.** C'est le seul
mécanisme du projet qui fabriquait activement une contrevérité, et non un simple trou. Il est
maintenant verrouillé : un bloc de question composé ne peut plus mapper vers `🤔 À évaluer`, et un
autotest le prouve.

**`⌛️ Évaluation en cours` (coefficient 0,5) reste autorisée dans une question composée, et cette
distinction est volontaire.** "À évaluer" veut dire "je n'ai aucune idée", d'où le 0. "Évaluation
en cours" veut dire "on regarde, et on s'attend à trouver du potentiel", d'où le 0,5. La seconde ne
fabrique pas un point fort, et le répondant l'affirme exprès. ⚠️ Ne pas "harmoniser" en ajoutant
`⌛️ Évaluation en cours` au verrou : un cas d'autotest existe pour empêcher ça.

**`🚫 Non applicable` est un sujet ouvert et distinct.** Elle pèse 0 aussi, donc elle pose aussi un
point à 0 %, **mais elle affirme quelque chose de vrai** : il n'y a rien à optimiser puisque le
sujet ne s'applique pas. La bonne question est celle du dénominateur : si trois critères sur six
sont réellement sans objet, le potentiel réel porte sur les trois autres. Le contrat de sortie de
lot a un champ `sans_objet` prévu pour ça, **jamais utilisé à ce jour**.

## 3.2 La dimension 6 n'offre aucune échappatoire

Comme dit en 1.1, la dimension 6 n'a que trois options et **aucune** ne permet de dire "je ne sais
pas" ni "sans objet". Un répondant qui ignore si un dispositif d'observabilité existe n'a rien à
cocher qui soit vrai.

C'est ce qui rend la case "Je ne sais pas" de notre générateur indispensable sur ces dix critères :
elle pose un contexte et aucune réponse, donc elle ne bouge pas le radar.

## 3.3 Le potentiel est plat, il n'y a pas de critère qui domine

Mesuré sur la source : les 54 critères pèsent entre **1,0 et 2,0**, pour un total de **80,0**.
Répartition par dimension : dimension 1, 16 critères pour 23,5 ; dimension 2, 5 pour 8,0 ;
dimension 3, 8 pour 12,0 ; dimension 4, 6 pour 8,0 ; dimension 5, 9 pour 13,0 ; dimension 6, 10
pour 15,5.

**Conséquence à connaître avant de proposer de raccourcir le questionnaire par ordre
d'importance** : il faut 14 questions sur 37 pour couvrir la moitié du potentiel détaillé, contre
18,5 en tirant au hasard. Le gain est trop faible pour justifier un tri par importance. Il n'y a
pas de longue traîne à couper.

Les **8 Déterminants** valent 2,0 chacun, soit 16,0 sur 80,0, un cinquième du potentiel :
`1.1`, `1.2`, `2.2`, `5.8`, `5.9`, `6.1`, `6.4`, `6.6`.

-----
-----
# Partie 4. Les recoupements entre le diagnostic rapide et les critères détaillés
-----
-----

Le référentiel pose parfois **le même fait deux fois**, une fois dans le diagnostic rapide et une
fois dans un critère détaillé. Le questionnaire posait donc deux fois la question au même client.

Cette partie recense tous les recoupements examinés, avec le verdict et son motif, pour qu'on ne
refasse pas l'analyse et surtout qu'on ne rouvre pas ceux qui ont été refusés.

## 4.1 `0.3` et `6.10` : le libellé est identique mot pour mot. RETENU

```
0.3  critere : Les composants principaux sont-ils soumis à des contraintes de haute disponibilité ?
6.10 critere : Les composants principaux sont-ils soumis à des contraintes de haute disponibilité ?
```

Il n'y a rien à interpréter, c'est la même phrase. Seule la façon de répondre diffère.

Les 5 crans de `0.3` :

```
1 - 7 jours sur 7, 24 heures sur 24 - 99,99 % - Couverture internationale
2 - 7 jours sur 7, 24 heures sur 24 - 99 %
3 - Certains SLA.
4 - 5 jours sur 7, 8 heures sur 24 - Pas de SLA - Pas de Plan de reprise d'activité (DRP)
5 - Pas de SLA/SLO
```

La méthode de `6.10` : `Le critère est validé si les contraintes de disponibilité du système
permettent encore à l'équipe de modifier ou d'optimiser les composants sans difficulté majeure.`

Le sens va dans le même sens sur toute l'échelle : plus la disponibilité exigée est stricte, plus
il est difficile de modifier. La correspondance est monotone et ne demande aucun jugement.

**Et ce recoupement est faisable techniquement, ce qui n'est pas le cas des autres** : les trois
options de la dimension 6 n'ont ni "non applicable" ni "à évaluer", donc il n'y a aucune option à
caser qui n'aurait pas d'équivalent parmi les crans. Voir 4.6 pour l'obstacle qui bloque les
critères des dimensions 1 à 5.

## 4.2 `0.12`, `1.8` et `5.9` : même sujet, mais le recoupement ne rapporte rien. ÉCARTÉ

```
0.12 critere : Le produit est-il compatible avec le matériel le plus ancien de la flotte cible et
               offre-t-il une expérience fluide sur celui-ci ?
1.8  critere : Le support des applications est-il médiocre sur les appareils les plus anciens
               ciblés ?
1.8  methode : L'application fonctionne correctement sur les appareils les plus anciens du groupe
               cible, sans imposer de mises à niveau inutiles ni causer de problèmes de
               performances qui accélèrent l'obsolescence.
5.9  critere : Des problèmes de compatibilité ont-ils été identifiés pour les appareils ciblés ?
5.9  methode : Une amélioration est identifiée si l'équipe a détecté des problèmes de
               compatibilité.
```

Sur le fond, `0.12` et `1.8` mesurent bien le même fait, et `5.9` en mesure un troisième distinct :
l'équipe a-t-elle **détecté**, pas les problèmes existent-ils.

**Motif du refus, et il est technique, pas de fond** : `1.8` et `5.9` sont déjà couverts ensemble
par une seule question de notre questionnaire, dont l'une des options est
`Notre service ne cible aucun appareil ancien : le parc utilisateur est récent et maîtrisé`, qui
pose `🚫 Non applicable` sur les deux. Or **aucun des 5 crans de `0.12` ne peut exprimer un "sans
objet"**, et le validateur exige que toutes les options d'une question composée renseignent
exactement le même ensemble de critères. Faire entrer `0.12` dans cette question obligerait donc à
supprimer l'option "sans objet", qui est une réponse légitime.

Et le compte ne bouge même pas : aujourd'hui deux questions couvrent trois critères, après ce
serait encore deux questions. **Gain nul, perte réelle.**

## 4.3 `0.13` et `5.3` : le référentiel compte à l'envers entre ses deux parties. ÉCARTÉ

**C'est le cas le plus révélateur du document.** Les deux portent sur le même sujet.

```
0.13 critere : Le backlog produit contient-il des problèmes de performance et des améliorations ?
0.13 crans   : 1 - Dans le backlog et discussion récurrente
               3 - Quelques améliorations sont possibles
               5 - Aucun problème de performance identifié

5.3  critere : L'équipe a-t-elle identifié des domaines à améliorer en termes de performance /
               efficacité et les a-t-elle ajoutés au backlog ?
5.3  methode : Le critère est validé si les tâches identifiées par l'équipe (problèmes, tickets,
               etc.) comportent des points permettant d'améliorer les performances / l'efficacité.
```

Dans le diagnostic rapide, **5 est présenté comme la bonne note**. Donc `Aucun problème de
performance identifié` est le cran le plus flatteur.

Pour `5.3`, c'est exactement l'inverse : une équipe qui n'a rien identifié n'a rien regardé, elle
prend `💡 Potentiel d'amélioration identifié`, coefficient 1, le **maximum** de potentiel. Et
l'équipe qui a des tickets de performance dans son backlog prend `✅ Point fort confirmé`,
coefficient 0.

**Le cran le plus flatteur de la porte donne la pire note du critère, et réciproquement.**

**Motif du refus** : le recoupement est faisable, mais il faudrait écrire la correspondance à
l'envers du sens intuitif, et **aucun contrôle automatique ne peut détecter une inversion**. Le
validateur vérifie que le libellé de réponse existe bien dans le référentiel, il ne sait rien du
sens. Une relecture distraite remettrait la correspondance "dans le bon sens" et fabriquerait une
réponse fausse, sans que rien ne s'allume. Le gain était d'une question sur soixante-trois.

## 4.4 `0.14` et `5.5` : deux faits différents. REFUSÉ

```
0.14 critere : Les principales fonctionnalités sont-elles optimisées et efficaces ?
5.5  critere : Les cas d'utilisation les plus critiques (parcours utilisateurs les plus fréquents)
               sont-ils optimisés ?
5.5  methode : Une amélioration est identifiée si aucune étude n'a été menée pour améliorer les
               performances / l'efficacité des chemins de code les plus utilisés.
```

`0.14` demande si les fonctionnalités **sont** optimisées. La méthode de `5.5` demande si **une
étude a été menée**. Sur les 5 crans de `0.14`, un seul parle d'étude ("régulièrement revues à des
fins d'optimisation"). Les quatre autres ne renseignent pas `5.5`.

## 4.5 `0.11` et `1.13` : erreur classique du libellé contre la méthode. REFUSÉ

```
0.11 critere : Les parcours utilisateurs sont-ils fluides, intuitifs et exempts de frictions
               UX/UI susceptibles d'être améliorées ?
1.13 critere : Les principaux parcours utilisateurs sont-ils optimisés pour être fluides et
               efficaces ?
1.13 methode : Les principaux flux de travail nécessitent un nombre minimal d'étapes / d'écrans,
               sans navigation redondante, ce qui améliore l'efficacité et réduit le nombre de
               requêtes serveur ou client.
```

Les deux libellés se ressemblent beaucoup, et c'est exactement le piège. Les crans de `0.11`
parlent de friction ressentie, de plaintes utilisateurs et de tests utilisateurs. La méthode de
`1.13` parle du **nombre d'étapes et d'écrans**. Une interface agréable peut très bien comporter
huit écrans redondants.

## 4.6 `0.15` et `4.1` : recoupement solide sur le fond, gain nul. ÉCARTÉ

```
0.15 critere : Existe-t-il une politique relative à la suppression et à l'archivage des données ?
0.15 crans   : 1 - Aucune politique / ne sais pas
               2 - Pratiques informelles ou ponctuelles de suppression et d'archivage
               3 - Une politique existe, mais n'est pas appliquée de manière cohérente
               4 - Une politique claire est en place et partiellement automatisée
               5 - Une politique stricte, appliquée et régulièrement contrôlée en matière de
                   suppression et d'archivage des données

4.1  critere : Des mécanismes de suppression et d'archivage sont-ils mis en place ?
4.1  methode : Le critère est validé si des mécanismes automatiques de suppression et d'archivage
               existent et sont effectivement appliqués.
```

La correspondance est bonne et monotone : les crans 4 et 5 décrivent une politique automatisée et
appliquée, ce qui est exactement la méthode de `4.1`.

**Motif de l'écart** : `4.1` est déjà couvert avec `4.6` par une seule question. Le défaire pour le
rattacher à `0.15` remettrait `4.6` en question séparée, donc le compte de questions ne changerait
pas. Le seul bénéfice serait de remplir `4.1` (potentiel 1,5) **avant** la décision d'aller au
détail. À reconsidérer si le séquencement devient le sujet, pas avant.

## 4.7 Les autres rapprochements examinés et écartés d'emblée

| Rapprochement | Pourquoi il ne tient pas |
|---|---|
| `0.6` compétences disponibles, et `6.9` autonomie de l'équipe | disposer des compétences n'est pas avoir le droit de déployer un outil |
| `0.7` complexité de l'architecture, et `6.5` découplage métier / technique | la méthode de `6.5` demande si on peut modifier la technique sans toucher au fonctionnel, ce qu'une architecture simple ne garantit pas |
| `0.2` fonctionnalités redondantes, et `6.8` code dupliqué | des fonctionnalités en double dans le système d'information, ce n'est pas du code dupliqué dans une application |
| `0.16` pays du mix électrique, et `3.3` région du mix électrique | doublon réel, **déjà traité** : les deux se lisent dans la même donnée collectée et `0.16` appartient au lot du jugement automatique |

-----
-----
# Partie 5. Ce que le référentiel implique pour l'automatisation
-----
-----

Ce n'est pas un piège de rédaction, mais c'est la conclusion qui commande le plus de décisions, et
elle est régulièrement oubliée.

**Sur les 16 critères des dimensions 4 et 6, la méthode d'aucun ne peut être satisfaite par une
observation de l'extérieur.** Établi en lisant les 16 verbatim. Les méthodes disent, mot pour mot,
"si l'équipe a identifié", "si une stratégie est appliquée", "si le projet dispose d'un ensemble
complet de tests", "si des outils d'observabilité sont en place". Ce sont des états internes et des
pratiques d'équipe. Aucune requête HTTP, aucun en-tête, aucun enregistrement DNS, aucun fichier
public ne les établit.

Ces deux dimensions pèsent 23,5 sur 80, soit 29,4 % du potentiel total.

**EOF interroge la maturité d'une équipe, pas la surface technique d'un site.** Le plafond de
l'automatisation est donc une propriété du référentiel, pas un défaut de notre outillage. Les
seuls leviers qui déplacent les chiffres sont de demander un artefact (le dépôt de code, puis
l'infrastructure as code ou la facture cloud) ou de poser une question. Toute sonde publique
supplémentaire sur ces dimensions ne peut produire qu'un indice partiel, donc un `contexte`, donc
jamais un point sur le radar.

-----
-----
# Faut-il le signaler à EROOM ?
-----
-----

**Question ouverte, non tranchée.** Plusieurs points de ce document sont des défauts de la source
et non des subtilités : le trou de `3.4`, les huit crans qui attribuent un cran extrême à qui dit
ne pas savoir, la méthode de `2.2` qui contient un morceau étranger, la contradiction entre le
libellé de `3.2` et son option, les trois crans de `0.13` numérotés 1, 3, 5.

Les remonter servirait tous les utilisateurs du référentiel. À décider avec l'utilisatrice.
