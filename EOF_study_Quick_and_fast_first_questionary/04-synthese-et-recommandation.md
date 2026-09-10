# Synthèse : peut-on poser moins de questions pour couvrir la dimension 0 et la dimension 6 ?

## La question posée

Sur les 26 critères EOF de la dimension "0 - Diagnostic rapide" (16 critères) et de la dimension "6 - Facilité de changement" (10 critères), peut-on poser moins de questions à un humain tout en couvrant le maximum de critères, sans changer le référentiel EOF-V.1.1 ni dégrader la précision des réponses ?

## Chiffres de départ

- Questionnaire actuel : **25 questions pour 26 critères, ratio 1,04 critère/question** (fichier 01).
- Automatisation réelle aujourd'hui : **1 critère sur 26** (`0.16`), confirmée à la fois sur le référentiel seul et sur les données réelles d'octo.com (fichiers 02 et 03).
- 9 critères ont un indice "partiel" (donnée affichée en annexe) mais aucun ne dispense de la question humaine, par construction du référentiel.
- 15 critères sont des faits internes à l'équipe (compétences, backlog, pratiques d'ingénierie, gouvernance) : aucune donnée externe ne peut y répondre, quel que soit l'outillage. Un 16e critère (`0.15`) n'est pas structurellement hors de portée mais n'est pas cherché par l'outillage actuel (cf. fichier 02).

## Ce qui a déjà été essayé sur ce périmètre, et qui n'a pas marché

Le 2026-09-07, un format QCM à cases indépendantes a été testé sur un déroulé réel visant 21 critères de ce même périmètre en 7 questions. Résultat réel : **9 critères tranchés sur 21 visés**, moins bien qu'une question directe par critère (qui, elle, peut couvrir jusqu'à 21/21 si le répondant répond à tout). La capture d'écran fournie en amont de cette étude correspond à cet essai. La décision prise à l'époque a été d'écarter ce format pour ce périmètre : il réduit le nombre de questions affichées, mais il réduit encore plus la couverture réelle, ce qui va à l'encontre du but recherché ici (maximiser les critères répondus).

Cette étude ne relance pas cet essai. Elle a en revanche cherché, sans l'avoir trouvé, un autre duplicat sémantique comparable à `0.3`/`6.10` (la seule fusion existante) parmi les 26 critères : aucune autre paire ne recouvre exactement le même fait sous-jacent sans risquer de mélanger deux réponses différentes dans une seule case.

## Le seul gain sûr identifié : une question posée pour rien

Le critère `0.16` est déjà résolu automatiquement (`env-data.json`, provenance `collecte`, doublon exact de `3.3`), mais le questionnaire actuel pose quand même une question manuelle pour ce critère. C'est le seul cas, sur les 26, où l'on peut retirer une question sans perdre la moindre couverture :

- Avant : 25 questions / 26 critères = 1,04
- Après : 24 questions / 26 critères = 1,083

Gain modeste (une question en moins, environ +4 % de ratio) mais réel, sans dégradation, et sans toucher au référentiel. Point de vigilance avant d'agir : vérifier auprès de l'équipe si cette question manuelle sur `0.16` a été maintenue volontairement comme un point de confirmation humaine face à l'automatisation, plutôt que par oubli.

## Deux situations différentes derrière "pas de réponse automatique"

Les critères sans réponse automatique aujourd'hui ne sont pas tous dans la même situation, et la distinction compte pour savoir où chercher un gain :

**Les 9 critères "partiel"** (`0.4, 0.7, 0.10, 0.11, 0.12` en dimension 0 ; `6.1, 6.3, 6.6, 6.8` en dimension 6) ont déjà une vraie donnée mesurée par les outils, mais cette donnée n'est jamais assez fiable pour trancher seule le critère : c'est une corrélation ou un indice indirect, pas une preuve. Exemples : un bon grade de sécurité HTTP (`6.1`) ne prouve pas qu'un dispositif d'observabilité (logs, métriques, traces) est en place, il ne fait que le rendre plus probable. Un score Lighthouse de code dupliqué (`6.8`) ne voit que le JavaScript exécuté côté navigateur, pas le code source réel. La règle du projet est explicite : une donnée "partielle" ne coche jamais une case seule, elle est au mieux affichée en rappel dans la question pour aider l'humain à répondre plus vite et avec plus de confiance. Sur ces 9 critères, la donnée existe déjà "sur le disque" (fichiers `env-data.json`, `cwv.json`, `security-headers-analysis.json`, HAR) mais n'est câblée en rappel que pour 4 d'entre eux (`0.4`, `6.1`, `6.3`, `6.6`, `6.8` - voir détail fichier 02) ; pour `0.7`, `0.11` et `0.12`, la donnée existe mais n'est même pas encore affichée.

**Le critère `0.15`** (politique de suppression/archivage des données) est différent : aucune donnée n'est collectée aujourd'hui, ni case cochée ni indice affiché. Mais contrairement aux 15 critères "structurels" (qui demandent un fait interne à l'équipe, invisible depuis l'extérieur quel que soit l'outil, par exemple "fait-on des revues de code ?"), une politique de données est parfois publiée sur une page publique du site (mentions légales, page "protection des données"...), donc observable en principe depuis l'extérieur. La raison pour laquelle rien n'est trouvé aujourd'hui est que l'outil `parse_pages_publiques.py` ne cherche que des motifs environnementaux, pas des motifs de rétention/suppression de données. C'est un manque de configuration de l'outil, pas une impossibilité de fond : contrairement aux 15 critères structurels, qu'aucun développement futur ne rendra automatisables, `0.15` peut progresser vers "partiel" (voire être tranché) avec un changement de code ciblé et peu risqué.

## Chantiers à explorer pour optimiser l'automatisation des réponses

Ces chantiers ne changent pas le nombre de questions posées (ce plancher est déjà atteint, cf. section précédente) : ils augmentent la part de critères où l'humain répond avec un rappel des données déjà collectées "sur le disque", plutôt qu'à l'aveugle.

⚠️ **Mise à jour du 2026-09-10 : les chantiers 1, 2 et 3 ci-dessous sont FAITS** (numérotés 37, 38,
39 dans `tmp/handoff.md`, commits `671b45d`/`3f45a3f`). Contrairement à l'espoir formulé au point 1,
`0.15` n'a progressé que jusqu'au rappel (comme les autres), pas jusqu'à une réponse tranchée :
aucune déclaration de rétention n'a été trouvée sur `audits/octo.com` (comportement attendu, testé
positif sur un cas synthétique). Seul le chantier 4 (`0.10`) reste ouvert, volontairement laissé de
côté : non vérifiable sur octo.com, qui n'a ni `robots.txt` ni `sitemap.xml` du tout.

1. ✅ **FAIT.** ~~Étendre `parse_pages_publiques.py`~~ pour qu'il cherche aussi des motifs de rétention/suppression/archivage de données (ex. "protection des données", "durée de conservation", "droit à l'effacement"), en plus des motifs environnementaux actuels.
2. ✅ **FAIT.** ~~Câbler le rappel de fait mesuré pour `0.7`~~ : la donnée existe déjà (CSP listant les hébergeurs backend type PaaS, CDN détectés dans `tech_stack`), il ne reste qu'à l'afficher dans la question, sur le même principe que ce qui existe déjà pour `0.4`.
3. ✅ **FAIT.** ~~Câbler le rappel de fait mesuré pour `0.11` et `0.12`~~ : les scores Core Web Vitals (accessibilité, bonnes pratiques, LCP/INP/CLS, catégorie CrUX) sont déjà collectés dans `cwv.json` et pourraient être rappelés dans les questions sur la fluidité UX/UI et la compatibilité matériel ancien, avec la réserve explicite que ce sont des indices techniques, pas une mesure directe du ressenti utilisateur.
4. **Vérifier si le sitemap peut être trouvé autrement pour `0.10`** : le mécanisme existe déjà (`diag_context_0_10`) mais reste inerte sur les sites sans `sitemap.xml` déclaré (cas d'octo.com). Pas prioritaire : même quand il fonctionne, c'est un proxy faible de la complexité fonctionnelle (une seule page peut porter une SPA complexe).
5. **Ne pas chercher à automatiser les 15 critères structurels** (`0.1, 0.2, 0.3, 0.5, 0.6, 0.8, 0.9, 0.13, 0.14` et `6.2, 6.4, 6.5, 6.7, 6.9, 6.10`) : ce sont des faits internes à l'équipe, aucune donnée collectable depuis l'extérieur du service ne peut y répondre, quel que soit l'outil développé (cf. mémoire [[reference_eof_maturite_pas_surface]]).

## Piste examinée le 2026-09-10 et écartée en l'état : précocher une case suggérée

Demande initiale : sur les critères "partiel", au lieu d'un simple rappel en prose sous la
question, précocher directement la case que le rappel suggère, la personne n'ayant plus qu'à
confirmer ou corriger. Objectif recherché : accélérer le remplissage (59 questions, ça pèse).

**Pourquoi ce n'est pas juste une automatisation "un peu plus timide"** : un critère est classé
"partiel" précisément parce qu'aucun seuil fiable n'a été trouvé pour transformer l'indice en une
case précise. S'il existait un tel seuil, le critère serait déjà "automatisable" et la case serait
déjà cochée seule (comme `0.16`). Précocher une case reviendrait donc à inventer ce seuil qu'on a
justement refusé d'inventer, avec le même risque qu'une automatisation, pas un risque moindre.

**Deux risques concrets identifiés** :
1. **Biais de défaut** : une case déjà cochée se confirme statistiquement plus souvent qu'elle ne
   se corrige, même quand elle est fausse — biais cognitif documenté, pas une supposition.
2. **Confirmation indiscernable de l'oubli** : `parse_questionnaire.py` ne lit qu'une case cochée
   ou pas. Il ne peut pas distinguer "la personne a réfléchi et confirmé notre proposition" de "la
   personne a renvoyé le fichier sans l'avoir vraiment relu". C'est exactement le type d'échec
   silencieux que ce projet a mis beaucoup d'énergie à éliminer ailleurs (cf. mémoire
   [[feedback_echec_silencieux_vs_absence]]) : une fausse confirmation humaine, indiscernable
   d'une vraie, fabriquerait un chiffre faux avec une apparence de légitimité (une case cochée par
   un humain) supérieure à celle d'un simple "je ne sais pas".

**Ce qui existe déjà et couvre une partie du besoin, sans ce risque** : le rappel en prose *dit*
déjà ce que la mesure suggère (ex. pour `0.7` : "3 composants détectés... ce qui suggère plusieurs
briques séparées"). La personne n'a pas à chercher l'information, seulement à la lire et choisir.
Le gain de vitesse de lecture est déjà acquis ; ce qui manquerait, c'est seulement le geste physique
de cocher, pas la réflexion.

**Décision** : idée non implémentée, pas rejetée définitivement. Si elle est reprise, elle a besoin
d'un garde-fou de conception avant tout code : par exemple afficher la suggestion visuellement à
part des cases à cocher (jamais dans une case déjà cochée), pour que cocher reste un geste actif
et vérifiable, jamais un état par défaut qu'on n'aurait qu'à laisser filer.

## Conclusion honnête

Sur ce périmètre précis, **le nombre de questions posées est déjà proche du plancher structurel du référentiel**, pour trois raisons qui se cumulent :

1. La quasi-totalité des critères non couverts par l'automatique (15 sur 25) porte sur des faits internes à l'équipe, par construction invisibles depuis l'extérieur du service.
2. La seule fusion possible sans perte de précision (`0.3` + `6.10`, le seul recoupement structurel propre du référentiel entre diagnostic rapide et dimension 6) est déjà en place.
3. Le format qui promettait de réduire le nombre de questions (QCM à cases indépendantes) a été testé sur presque ce même périmètre et a dégradé la couverture réelle plutôt que de l'améliorer.

Le levier qui reste n'est donc pas la réduction du nombre de questions (déjà proche de son plancher, hors le gain de 1 question ci-dessus), mais l'amélioration de la qualité de réponse à chaque question posée, pour éviter qu'un répondant hésitant laisse un critère à "je ne sais pas" alors qu'il aurait pu répondre.

## Recommandations pour la suite (non implémentées dans cette étude)

Cette étude n'a modifié aucun fichier de production, conformément au périmètre demandé. Les 5 chantiers listés plus haut ("Chantiers à explorer pour optimiser l'automatisation des réponses") nécessiteraient de toucher `run_eof.py`, `eof_criteria_mapping.py` et `parse_pages_publiques.py`, donc une décision et une session dédiées. En complément :

1. ✅ **DÉJÀ ACQUIS, pas un chantier.** ~~Retirer la question redondante sur `0.16`~~ : vérifié le
   2026-09-10 en rejouant `generate_questionnaire.py` pour de vrai sur `audits/octo.com`, `0.16`
   n'apparaît déjà plus dans le questionnaire produit. Un mécanisme général déjà en place (pas
   spécifique à `0.16`) retire automatiquement toute question dont le critère a déjà une réponse
   tranchée. Le "25 questions" annoncé plus haut était donc déjà périmé au moment de l'écrire.
2. **Ne pas rouvrir le regroupement QCM** sur ce périmètre : déjà testé, déjà écarté, le résultat réel (9/21 en 7 questions) est documenté ci-dessus et dans la mémoire du projet.
