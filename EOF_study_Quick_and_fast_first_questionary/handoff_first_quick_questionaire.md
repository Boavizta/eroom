# Handoff - Étude "Optimisation du diagnostic rapide et de la facilité de changement"

Session du 2026-09-08. Ce handoff est spécifique à ce chantier et vit dans son propre dossier `EOF_study_Quick_and_fast_first_questionary/`, séparé du handoff principal `tmp/handoff.md` (utilisé par un autre agent en parallèle sur un sujet différent, l'analyse HAR). Ne pas fusionner les deux.

## Contexte de la demande

L'utilisateur a demandé un chantier isolé, sur de nouveaux fichiers, pour ne pas interférer avec l'agent qui travaille en parallèle sur `tmp/handoff.md`. Constat en cours de session (`git status`) : cet autre agent a d'abord touché l'analyse HAR (`analyze_har.py`, étapes 20/25, `processus/CONTROLES.md`, `processus/manifeste-lots.json`), puis, plus tard dans la même fenêtre de temps, une nouvelle étape `.claude/skills/analyse-parcours/skill-steps/39b_questionnaire-eof.md` est apparue et `audits/octo.com/eof-audit-results.json`, `eof-rempli.md`, `wellknown-scan.json`, `html-css-criteria.json`, `lots/jugement-automatique.json` ont été modifiés (rejeu de `run_eof.py`). Le périmètre de l'autre agent touche donc bien, lui aussi, la zone questionnaire EOF. Ce chantier n'a écrit dans aucun de ces fichiers (lecture seule), mais toute reprise doit vérifier l'état de `tmp/handoff.md` avant d'aller plus loin, le sujet n'est peut-être plus seulement le HAR.

Objectif du chantier, tel que clarifié avec l'utilisateur au fil de la session (plusieurs allers-retours de cadrage, voir décisions ci-dessous) : sur les 26 critères EOF de la dimension "0 - Diagnostic rapide" et de la dimension "6 - Facilité de changement", trouver une stratégie qui permette de répondre au maximum de critères en posant le minimum de questions à un humain, en s'appuyant d'abord sur les données déjà mesurées automatiquement par les outils du projet (HAR, Core Web Vitals, Lighthouse/PageSpeed, technologies détectées, en-têtes de sécurité, empreinte carbone...), sans changer le référentiel EOF-V.1.1 ni le questionnaire de production actuel.

## Décisions validées avec l'utilisateur pendant cette session

1. Le référentiel EOF-V.1.1 (Google Sheet) ne change pas. Aucun fichier de production n'est modifié dans ce chantier (`questionnaire-blocs.json`, `run_eof.py`, `eof_criteria_mapping.py`, `parse_pages_publiques.py` restent intacts).
2. Nouveaux fichiers dans un dossier dédié à la racine du projet : `EOF_study_Quick_and_fast_first_questionary/`, avec ce handoff nommé `handoff_first_quick_questionaire.md` à l'intérieur (nom donné explicitement par l'utilisateur).
3. Étape 1 (analyse abstraite sur le référentiel + inventaire des outils) et étape 2 (rejeu contre les données déjà collectées sur octo.com) sont faites dans la même session, à la demande explicite de l'utilisateur.
4. Modèle utilisé : Sonnet 5, confirmé par l'utilisateur, cohérent avec sa préférence par défaut (tâche bornée, pas d'architecture ni de débogage long).
5. Sous-agents utilisés pour la recherche factuelle (extraction du référentiel, inventaire des données automatiques) afin de préserver le contexte de la session principale. Un premier essai de fork a échoué silencieusement (0 outil appelé, a juste renvoyé du texte) ; les recherches ont ensuite été relancées avec des agents `general-purpose` frais et des consignes à l'impératif, avec succès.

## Ce qui a été trouvé (détail dans les fichiers 00 à 05 de ce dossier)

- Questionnaire actuel : 25 questions pour 26 critères couverts (ratio 1,04 critère/question). Aucun trou de couverture.
- Un seul regroupement existant et légitime : `0.3` + `6.10` (même fait sous-jacent, disponibilité). C'est le seul recoupement structurel propre entre la dimension 0 et une autre dimension (les dimensions 1 à 5 ont un cran "Non applicable" que la dimension 0 n'a pas, ce qui interdit tout croisement avec elles sans appauvrir le questionnaire).
- Automatisation réelle : 1 critère sur 26 (`0.16`), confirmée identique en abstrait et sur les données réelles d'octo.com. 9 critères ont un indice "partiel" (jamais une réponse automatique, juste un rappel affiché). 15 critères sont des faits internes à l'équipe, aucune donnée externe ne peut y répondre. 1 critère (`0.15`) n'est pas structurellement hors de portée mais n'est pas cherché par l'outillage actuel.
- Un format QCM à cases indépendantes a déjà été testé sur presque ce même périmètre (2026-09-07, 21 critères visés en 7 questions) et a donné un résultat réel de 9/21 critères tranchés, moins bon qu'une question directe par critère. Ne pas relancer cette piste sans un changement de méthode clairement différent de l'essai déjà fait.
- Le seul gain sûr et sans perte de précision identifié : retirer la question manuelle sur `0.16`, déjà résolue par l'automatique. Ratio passerait de 1,04 à 1,083 (24 questions pour 26 critères).

## Conclusion de l'étude

Sur ce périmètre précis, le nombre de questions est déjà proche du plancher structurel du référentiel (25 posées aujourd'hui, 24 atteignables sans perte). Le detail est dans `04-synthese-et-recommandation.md` et le tableau chiffré complet dans `05-tableau-de-bord.md`.

## Chantiers à explorer pour optimiser l'automatisation des réponses (à prioriser si ce chantier est repris)

Ces chantiers ne réduisent pas le nombre de questions (le plancher est déjà atteint, à une exception près : le retrait de la question redondante sur `0.16`, cf. plus bas). Leur principe : quand on ne peut pas répondre avec certitude à un critère, au moins **assister** la réponse humaine avec les données déjà collectées "sur le disque" (fichiers `env-data.json`, `cwv.json`, `security-headers-analysis.json`, `wellknown-scan.json`, HAR, CSP...), plutôt que de laisser la question sans aucun repère. Détail complet et justification dans `04-synthese-et-recommandation.md`, section "Chantiers à explorer pour optimiser l'automatisation des réponses".

1. **Étendre `parse_pages_publiques.py`** avec des motifs de recherche sur la rétention/suppression/archivage de données, pour faire progresser `0.15` au-delà de "aucune donnée". Seul chantier qui peut faire gagner un critère au-delà du simple rappel.
2. **Câbler un rappel de fait mesuré pour `0.7`** (CSP + CDN déjà détectés).
3. **Câbler un rappel de fait mesuré pour `0.11` et `0.12`** (scores Core Web Vitals déjà collectés dans `cwv.json`).
4. Vérifier si une source alternative au sitemap existe pour `0.10` (mécanisme déjà câblé mais inerte sur les sites sans `sitemap.xml`, pas prioritaire).
5. Ne pas chercher à automatiser les 15 critères structurels (faits internes à l'équipe) : aucun outil ne pourra jamais y répondre depuis l'extérieur du service.

Ces chantiers nécessitent de toucher des fichiers de production (`run_eof.py`, `eof_criteria_mapping.py`, `parse_pages_publiques.py`), donc une décision et une session dédiées, hors du périmètre de cette étude.

## État à la fin de cette session

Terminé : les 6 fichiers de ce dossier (`00-resume-session.md`, `01` à `05`) et ce handoff. Aucun fichier de production touché. Aucune donnée octo.com modifiée (lecture seule).

## Si quelqu'un reprend ce chantier

- Ne pas relancer la recherche d'un autre regroupement QCM sur ce périmètre sans une méthode réellement nouvelle : c'est déjà documenté comme testé et écarté (fichier 04).
- Prioriser les 5 chantiers d'automatisation listés ci-dessus, plus le retrait de la question redondante sur `0.16` (gain sûr de 1 question, sous réserve de confirmer que ce n'est pas une confirmation volontaire).
- Avant de toucher `processus/manifeste-lots.json` ou `processus/CONTROLES.md` pour enregistrer un lot officiel, vérifier que l'autre agent a bien terminé et commité ses changements sur ces mêmes fichiers, y compris ceux touchant l'EOF (`eof-audit-results.json`, `39b_questionnaire-eof.md`, pas seulement le HAR).
