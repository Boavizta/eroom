-----
-----
# Convention : un critère écarté, et les questions filtres
-----
-----

Établie en session 26, 2026-09-08. Ce document est le contrat commun aux trois producteurs et
aux deux consommateurs touchés par les questions filtres. Il fait foi ; en cas de désaccord
avec un commentaire de code, c'est le code qui a tort.

-----

## 1. Le fait de départ, vérifié dans le référentiel

`🚫 Non applicable` est une option de réponse **du référentiel EROOM**, pas une invention de
notre outil. Elle est offerte pour les **44 critères des dimensions 1 à 5**, avec un
`options_evaluation_coefficient` de **0**.

Elle n'est offerte ni pour les **10 critères de la dimension 6** (qui portent l'échelle
`🟢 Facile à modifier` / `🟡 Effort modéré` / `🔴 Difficile à changer`), ni pour les
**16 questions 0.x du diagnostic rapide** (qui portent des crans graduués sans option de
non-applicabilité).

⚠️ Le document `questionnaire-eof-implementation.md` affirmait l'inverse, que les 0.x offraient
"Non applicable" et que les dimensions 1 à 5 ne l'offraient pas. C'était inversé. Corrigé.

**Conséquence : une question filtre ne peut écarter que des critères des dimensions 1 à 5.**
Aucun critère de la dimension 6, aucune question 0.x.

-----

## 2. Ce qu'est un critère écarté

Un critère est **écarté** quand il ne s'applique pas au service audité. Deux chemins mènent
au même état, et ils doivent produire exactement les mêmes chiffres :

- sa `reponse` vaut `🚫 Non applicable` ;
- ou son booléen `sans_objet` vaut vrai.

Il n'y a **pas** de troisième notion à inventer. "Écarté" est le mot de notre outil pour
l'état que le référentiel nomme "Non applicable".

### 2.1 Ce qu'un critère écarté fait aux chiffres

Un critère écarté sort de **tous** les dénominateurs, et ne compte dans aucun numérateur :

| Grandeur | Effet |
|---|---|
| `criteres_repondus` | il n'y compte **pas** |
| `criteres_total` | il en est **retiré** |
| `completude_pct`, `completude_globale_pct` | retiré du dénominateur |
| `potentiel_optimisation_pct`, `potentiel_optimisation_global_pct` | son `potentiel_max` est soustrait du dénominateur |
| `criteres_ecartes` | il y compte, c'est le seul endroit où il est visible |

Raison : un critère hors périmètre n'est ni une réussite ni un manque. Le compter comme
répondu avec un coefficient nul le rendrait **arithmétiquement identique à un
`✅ Point fort confirmé`**, qui porte aussi le coefficient 0. Un service sans base de données
verrait alors la dimension 4 affichée à 0 % de potentiel d'optimisation, c'est-à-dire comme la
dimension la mieux notée de son rapport. C'est le défaut que le chantier 13 a fermé, par une
autre porte.

### 2.2 Le garde-fou, non négociable

Un critère écarté n'est honnête que s'il est **compté à part et affiché**. Sans le compteur
visible, une complétude de 100 % construite sur des exclusions est indiscernable d'un audit
réellement instruit : on fabrique de la complétude.

-----

## 3. Les nouvelles clés du contrat

Écrites par **les deux producteurs**, `run_eof.py` et `processus/fusionner_lots.py`, avec les
mêmes valeurs pour la même entrée.

### 3.1 À la racine de `eof-audit-results.json`

| Clé | Type | Sens |
|---|---|---|
| `criteres_ecartes` | entier | nombre de critères écartés, toutes dimensions confondues |

`criteres_total` devient le nombre de critères **retenus**, soit le total du référentiel moins
les écartés. Le total brut du référentiel se retrouve par `criteres_total + criteres_ecartes`.

### 3.2 Dans chaque entrée de `dimensions[]`

| Clé | Type | Sens |
|---|---|---|
| `ecartes` | entier | nombre de critères écartés de cette dimension |
| `hors_perimetre` | booléen | vrai quand **tous** les critères de la dimension sont écartés |

Quand `hors_perimetre` vaut vrai, `potentiel_optimisation_pct` et `completude_pct` valent
`null`, et `total` vaut 0. La dimension n'a pas de note, parce qu'il n'y a rien à noter.

⚠️ Ne pas confondre `hors_perimetre` avec une dimension sans réponse. Une dimension sans
réponse est une dimension que nous n'avons pas su instruire ; une dimension hors périmètre est
une dimension dont nous savons qu'elle ne concerne pas ce service. Le rapport et le radar
doivent les distinguer.

-----

## 4. Le bloc de questionnaire de type `filtre`

### 4.1 Sa forme dans `questionnaire-blocs.json`

Un troisième `type`, à côté de `direct` et `compose` :

```json
{
  "id": "filtre-donnees-persistantes",
  "fichier": "technique",
  "phase": "detail",
  "titre": "Données que le service conserve",
  "interlocuteur": "la personne qui exploite l'infrastructure",
  "type": "filtre",
  "criteres": ["4.1", "4.2", "4.3", "4.4", "4.5", "4.6"],
  "question": "...",
  "libelle_ecarte": "...",
  "libelle_applicable": "..."
}
```

- `criteres` : liste des critères que le filtre écarte quand la réponse est "cela ne
  s'applique pas". Tous doivent appartenir aux dimensions 1 à 5.
- `libelle_ecarte` : le libellé de la case qui écarte les critères.
- `libelle_applicable` : le libellé de la case qui dit que le sujet s'applique bien. La cocher
  ne verse **aucune** réponse : les critères restent à poser.
- `critere` (singulier) et `options` sont **interdits** sur un bloc `filtre`.

### 4.2 Quand un filtre est imprimé

Un filtre n'est imprimé que si **aucun** de ses critères ne porte déjà une réponse
**tranchante**, c'est-à-dire une réponse absente de `REPONSES_NON_TRANCHANTES`.

Raison : si la mesure a déjà tranché un seul des critères du filtre, elle a prouvé que le
sujet s'applique, et la question est inutile. Exemple vérifié sur `audits/octo.com` : 1.5 et
1.13 sont tranchés par la collecte, donc le filtre "pas d'interface utilisateur humaine" ne
doit pas être imprimé pour ce site.

Un `🤔 À évaluer` ne prouve rien et ne supprime donc pas le filtre.

### 4.2bis Un filtre est en phase `detail`, jamais en phase `porte`

La porte sert à décider si un diagnostic approfondi est pertinent. Un filtre ne sert pas à
cela : il dit quelle partie du référentiel ne concerne pas le service, et il ne gouverne que
des critères du diagnostic détaillé. Le mettre en porte le ferait poser avant la décision
d'aller plus loin, donc parfois pour rien.

**Les filtres sont placés en tête de la partie détaillée**, avant tous les autres blocs de
cette partie, et triés entre eux par rendement décroissant. Ce n'est pas une préférence de
présentation, c'est une nécessité : la mention de la section 4.2ter renvoie à un numéro de
question, et ce numéro doit toujours désigner une question **déjà lue**. Le tri par rendement
seul ne le garantit pas, deux blocs à égalité de rendement pouvant s'ordonner dans n'importe
quel sens.

### 4.2ter La mention "à ignorer", qui rend l'effort au client

⚠️ **Un filtre ne retire aucune question du document.** Au moment où le générateur écrit le
Markdown, il ne connaît pas la réponse au filtre : il imprime donc le filtre **et** les
questions que ce filtre pourrait rendre inutiles. Sans la mention ci-dessous, le levier
allonge le questionnaire de deux ou trois questions et n'en économise aucune. Il ne rend alors
que de la véracité au rapport, pas de l'effort au client.

**Règle.** Un bloc dont **tous** les critères sont gouvernés par des filtres porte, juste sous
son titre, une mention qui renvoie aux questions de ces filtres :

```
A IGNORER si vous avez repondu "Non" a la question 1 (Stockage de donnees du service).
```

- La condition est une **conjonction**, jamais une disjonction. Un bloc n'est ignorable que si
  **chacun** de ses critères est écarté. Le bloc qui couvre 4.4 et 3.9 relève de deux filtres
  différents : il ne s'ignore que si les deux ont répondu "cela ne s'applique pas", donc la
  mention dit `à la question 1 ET à la question 3`.
- Un bloc **partiellement** gouverné ne porte **aucune** mention. Il reste à remplir, puisque
  l'un de ses critères s'applique encore.
- La mention cite le numéro **et** le titre de la question du filtre. Un numéro seul oblige le
  lecteur à remonter à l'aveugle.
- **Chaque terme de la conjonction porte SON PROPRE `libelle_ecarte`.** Deux filtres n'offrent
  pas la même case : citer un seul libellé puis enchaîner "ET à la question 26" fait comprendre
  au lecteur qu'il doit avoir coché ce même libellé aux deux questions, ce qui est impossible.
  La forme correcte est `"<libellé du filtre 25>" à la question 25 (titre) ET "<libellé du
  filtre 26>" à la question 26 (titre)`. Ce défaut a été livré puis corrigé en session 26 ; un
  cas d'autotest le garde fermé.
- Le libellé est tronqué au premier `(`, sans limite de caractères. C'est pourquoi la mention
  lit "Non, le service ne conserve aucune donnée" et non le libellé complet, qui ajoute
  "(ou seulement en cache temporaire)".

Les questions gouvernées restent **dispersées** dans le document, parce que le tri par
rendement les éparpille. C'est assumé : regrouper les questions sous leur filtre reviendrait à
sacrifier le tri par rendement, et resterait impossible pour les blocs composés qui chevauchent
deux filtres.

### 4.3 Ce que la relecture verse

Quand la case `libelle_ecarte` est cochée, `parse_questionnaire.py` verse **une entrée par
critère** de `criteres`, chacune avec :

- `reponse` : `🚫 Non applicable`
- `provenance` : la même que celle des blocs `direct`, sans promotion d'aucune sorte
- `source` : la mention qui dit que la réponse vient du filtre, avec l'id du bloc

Quand la case `libelle_applicable` est cochée, rien n'est versé. Le bloc compte comme répondu
pour le bloc `mesure`, mais aucun critère n'en sort.

Les règles existantes ne changent pas : zéro case cochée ou deux cases cochées ne versent rien
et sont signalées.

### 4.4 Ce que le validateur doit tolérer

`valider_blocs_questionnaire.py` impose qu'un critère ne soit couvert que par un seul bloc.
Un filtre recouvre par construction des critères qui ont **aussi** leur bloc individuel, et
c'est voulu : le filtre les écarte d'un coup, sinon on les pose un par un.

**Cette règle d'unicité ne doit donc pas s'appliquer aux blocs `filtre`.** Elle reste entière
entre blocs `direct` et `compose`. En revanche, deux blocs `filtre` ne doivent pas se
recouvrir entre eux, et chaque critère cité par un filtre doit exister dans le référentiel et
offrir `🚫 Non applicable`.

-----

## 5. Les trois filtres livrés

| Filtre | Critères écartés | Potentiel concerné |
|---|---|---|
| Pas d'interface utilisateur humaine | 1.4, 1.5, 1.8, 1.9, 1.10, 1.11, 1.13, 1.14, 5.9 | 12,5 |
| Pas de données persistantes propres | 4.1 à 4.6 | 8,0 |
| Pas d'environnement de test distinct | 3.8, 3.9, 4.4 | 4,5 |

⚠️ 4.4 apparaît dans deux filtres. Comme un filtre ne verse que `🚫 Non applicable` et que
les deux versent la même chose, le recouvrement est inoffensif ; mais la règle 4.4 du
validateur interdit le recouvrement entre filtres. **4.4 est donc porté par le filtre
"données persistantes" seul**, et le filtre "environnement de test" ne cite que 3.8 et 3.9.

### 5.1 Ce que ces filtres coûtent et rapportent

Ils ne sont pas une réduction garantie. Pour un site web classique, ils reçoivent "cela
s'applique" et n'écartent rien : le questionnaire s'allonge alors de deux questions, le
troisième étant supprimé par la règle 4.2. Le gain n'existe que pour les services dont une
partie du référentiel ne parle pas, un service sans interface, sans base propre, sans
pré-production. C'est un pari sur la diversité des services audités, et il faut le présenter
comme tel.

-----

## 6. Ce que l'affichage doit dire

### 6.1 Rapport HTML

- Un KPI `Écartés` à côté de `Complétude` et `Critères répondus`, lisant `criteres_ecartes`.
- Dans le tableau des dimensions, une dimension `hors_perimetre` affiche `hors périmètre` à la
  place de son pourcentage, suivie du nombre de critères écartés. Elle n'affiche **jamais**
  `0 %`.
- Une dimension partiellement écartée affiche son pourcentage, puis le nombre d'écartés.

### 6.2 Radar

- Un axe `hors_perimetre` est neutralisé comme l'est déjà un axe sans réponse, mais porte la
  mention `hors périmètre` et non `aucune réponse`.
- La jauge de couverture calcule son pourcentage sur le potentiel **retenu**, et énonce à sa
  suite le nombre de critères écartés. Un service dont rien n'est écarté lit la même phrase
  qu'avant.

⚠️ **Le piège qui a été payé une fois.** Un critère écarté porte une `reponse` **non nulle**,
à savoir `🚫 Non applicable`. Tout code qui reconnaît un critère renseigné par
`reponse is not None` le compte donc **au numérateur ET au dénominateur** sans le vouloir. Le
premier jet du radar a fait exactement cela : sur 54 critères dont 6 écartés et 7 répondus
ailleurs, la jauge annonçait "13 critères sur 54, 6 écartés" au lieu de "7 critères sur 48,
6 écartés". Afficher le compteur d'écartés ne corrige pas l'arithmétique qui le nourrit : ce
sont deux chantiers, et le second est le seul qui compte.

-----

## 7. Contrôles

En plus de la batterie de `processus/CONTROLES.md` :

- `valider_coherence_cles.py` doit connaître `criteres_ecartes`, qui appartient à la famille
  surveillée `criteres_*`.
- Les `--autotest` de **tous** les scripts touchés doivent être rejoués, pas seulement celui
  auquel on pense. Cette erreur a été payée deux fois en session 25.
- Un cas d'autotest doit vérifier qu'une dimension entièrement écartée ne sort **jamais** un
  `potentiel_optimisation_pct` de 0.
