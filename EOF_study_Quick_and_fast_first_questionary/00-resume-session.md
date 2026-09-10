# Résumé de la session - étude diagnostic rapide + facilité de changement

Ce document résume, en une page, ce qui a été fait et trouvé pendant cette session (2026-09-08). Le détail est dans les fichiers 01 à 04 du même dossier.

## Ce qui a été fait

Dossier créé : `EOF_study_Quick_and_fast_first_questionary/`, avec 5 fichiers : `handoff_first_quick_questionaire.md`, `01-inventaire-criteres.md`, `02-inventaire-automatisation.md`, `03-rejeu-octo.com.md`, `04-synthese-et-recommandation.md`, et ce résumé.

Aucun fichier de production n'a été modifié. Tout le travail a été fait en lecture seule sur le référentiel EOF-V.1.1, le questionnaire actuel et les données déjà collectées sur octo.com.

## Conclusion, honnêtement

Sur les 26 critères concernés (16 de la dimension "0 - Diagnostic rapide", 10 de la dimension "6 - Facilité de changement"), il n'y a pas de grosse astuce à trouver pour réduire le nombre de questions. Le ratio actuel (25 questions pour 26 critères, soit 1,04 critère par question) est déjà proche du plancher structurel du référentiel, pour trois raisons qui se recoupent :

1. **16 des 21 critères non automatisés sont des faits purement internes à l'équipe** (compétences disponibles, contenu du backlog, pratiques d'ingénierie, gouvernance des accès). Ils sont invisibles depuis l'extérieur du service, quel que soit l'outil d'audit utilisé.
2. **Le seul recoupement possible sans perte de précision est déjà exploité.** Diagnostic rapide (dimension 0) ne peut se marier proprement qu'avec la dimension 6 (les dimensions 1 à 5 ont un cran "Non applicable" que la dimension 0 n'a pas, ce qui empêcherait de fusionner sans appauvrir le questionnaire). Ce recoupement (`0.3` + `6.10`, la disponibilité) est déjà fusionné en une seule question.
3. **Le format QCM à cases indépendantes a déjà été testé sur presque ce même périmètre** (2026-09-07, 21 critères visés en 7 questions) et a donné un résultat réel moins bon (9 critères tranchés sur 21) qu'une question directe par critère. Voir la section suivante pour le détail du raisonnement.

## Le seul gain sûr trouvé

La question sur `0.16` (pays d'hébergement / intensité carbone) est posée pour rien : elle est déjà résolue par une donnée automatique déjà collectée (`env-data.json`, doublon exact du critère `3.3`). La retirer du questionnaire ferait passer le ratio à 24 questions pour 26 critères, soit 1,083, sans perdre la moindre précision.

Trois autres pistes amélioreraient la qualité des réponses, pas leur nombre : rappeler dans les questions `0.7`, `0.11` et `0.12` les données déjà mesurées (architecture détectée, scores Core Web Vitals), et étendre l'outil de recherche de pages publiques pour chercher une page de politique de données pour le critère `0.15`. Aucune de ces pistes n'a été codée : ce sont des recommandations pour une session ultérieure, pas des changements de production.

## Point de vigilance signalé dans le handoff

En cours de session, un autre agent a modifié des fichiers d'audit EOF de production (`audits/octo.com/eof-audit-results.json`, et une nouvelle étape `39b_questionnaire-eof.md`), en plus de son travail initial sur l'analyse HAR. Aucun conflit avec cette étude (rien n'a été écrit dans ces fichiers ici), mais toute reprise de ce chantier doit d'abord vérifier l'état de `tmp/handoff.md`.

## Pourquoi le format QCM (cases à cocher indépendantes) n'est pas retenu ici

Un bloc QCM présente plusieurs affirmations sur un même écran, chacune reliée à un ou plusieurs critères, et le répondant coche celles qui s'appliquent. Le problème n'est pas de regrouper des questions à l'écran, c'est ce que ce format offre en plus d'une question directe : une **échappatoire groupée**. Sur l'exemple montré en amont de cette étude, chaque écran a une option du type "rien de tout cela ne s'applique" ou "je ne sais pas / à vérifier avec une autre équipe". Une question directe ("Quel est votre niveau de contrainte de disponibilité ?") n'offre pas ce genre d'esquive : le répondant doit choisir un cran précis sur l'échelle, même approximatif.

Ce n'est pas une hypothèse, ça a été testé en réel le 2026-09-07, sur un déroulé qui visait 21 critères de ce même périmètre (diagnostic rapide + facilité de changement) en 7 questions QCM. Résultat réel : **seulement 9 critères sur 21 ont reçu une réponse exploitable**, les 12 autres sont restés à "je ne sais pas" parce que l'échappatoire a été prise plusieurs fois. Une question directe par critère, elle, peut monter jusqu'à 21/21 si le répondant va au bout.

Deux effets aggravent ça avec le QCM :
- **L'échappatoire est groupée** : un seul clic "rien de tout cela" ferme plusieurs critères à la fois, alors qu'avec une question directe, hésiter sur un critère n'affecte pas les critères voisins.
- **Même quand une case est cochée**, elle donne souvent la même réponse à plusieurs critères en même temps. Ça ne marche sans perte de précision que si les critères regroupés portent vraiment sur le même fait (comme `0.3` et `6.10`, qui parlent tous les deux des contraintes de disponibilité). Regrouper des critères qui ne sont pas rigoureusement identiques revient à deviner une réponse plutôt qu'à la mesurer.

Le but du chantier est de maximiser le nombre de critères effectivement répondus, pas de minimiser le nombre d'écrans pour lui-même. Sur ce périmètre précis, les chiffres réels montrent que le QCM perd sur l'objectif qui compte, même s'il gagne sur le nombre d'écrans affichés. C'est pour ça qu'il n'est pas retenu, et que le rouvrir demanderait un mécanisme réellement différent de celui déjà testé (par exemple une case obligatoire par ligne, sans échappatoire), ce qui reviendrait de fait à une question directe déguisée.
