# Inventaire des 26 critères : dimension 0 (diagnostic rapide) et dimension 6 (facilité de changement)

Périmètre de l'étude : les 16 critères `0.1` à `0.16` (dimension "0 - Diagnostic rapide") et les 10 critères `6.1` à `6.10` (dimension "6 - Facilité de changement") du référentiel EOF-V.1.1.

Sources consultées (lecture seule, aucune modification) :
- `.claude/skills/eof/docs/EOF-V.1.1 (EROOM Optimization Framework) - Template - Français/eof-referentiel.json`
- `.claude/skills/analyse-parcours/scripts/questionnaire-blocs.json`
- `.claude/skills/analyse-parcours/scripts/eof_criteria_mapping.py`

## Dimension 0 - Diagnostic rapide (0.1 à 0.16)

Particularité de cette dimension : les critères 0.x n'ont ni `methode`, ni `potentiel_max`, ni coefficient. Chacun n'a qu'un intitulé, une échelle de réponse à 5 crans (parfois 3), et un `niveau_impact` toujours égal à "Déterminant".

| Critère | Libellé | Bloc(s) actuel(s) | Type | Regroupé avec | Automatisé aujourd'hui |
|---|---|---|---|---|---|
| 0.1 | La disparition du service numérique aurait-elle un impact important ? | porte-diag-0.1 | direct | aucun | Non |
| 0.2 | Y a-t-il des fonctionnalités redondantes ou des applications en double dans le système ? | porte-diag-0.2 | direct | aucun | Non |
| 0.3 | Les composants principaux sont-ils soumis à des contraintes de haute disponibilité ? | porte-compose-haute-dispo-0.3 | compose | 6.10 | Non |
| 0.4 | Dépendances : combien de liens techniques vers d'autres systèmes sont en place ? | porte-diag-0.4 | direct | aucun | Non (indice contextuel câblé, cf. fichier 02) |
| 0.5 | Le code source du projet est-il entièrement ou partiellement accessible à l'équipe ? | porte-diag-0.5 | direct | aucun | Non |
| 0.6 | Les compétences nécessaires pour mettre à jour le service sont-elles disponibles ? | porte-diag-0.6 | direct | aucun | Non |
| 0.7 | La complexité de l'architecture est-elle élevée ? | porte-diag-0.7 | direct | aucun | Non |
| 0.8 | L'infrastructure (nombre et taille des composants) est-elle très importante ? | porte-diag-0.8 | direct | aucun | Non |
| 0.9 | Un volume important de données est-il stocké ? | porte-diag-0.9 | direct | aucun | Non |
| 0.10 | La complexité fonctionnelle est-elle élevée ? | porte-diag-0.10 | direct | aucun | Non (indice contextuel câblé mais inerte sur octo.com, cf. fichier 02) |
| 0.11 | Les parcours utilisateurs sont-ils fluides, intuitifs et sans friction UX/UI ? | porte-diag-0.11 | direct | aucun | Non |
| 0.12 | Le produit est-il compatible avec le matériel le plus ancien de la flotte cible ? | porte-diag-0.12 | direct | aucun | Non |
| 0.13 | Le backlog produit contient-il des problèmes de performance et des améliorations ? | porte-diag-0.13 | direct | aucun | Non |
| 0.14 | Les principales fonctionnalités sont-elles optimisées et efficaces ? | porte-diag-0.14 | direct | aucun | Non |
| 0.15 | Existe-t-il une politique relative à la suppression et à l'archivage des données ? | porte-diag-0.15 | direct | aucun | Non |
| 0.16 | Le service est-il hébergé dans un pays dont le mix électrique a un impact significatif ? | porte-diag-0.16 | direct | aucun | **Oui** - `eof_criteria_mapping.py`, categorie `automatisable`, champ `env-data.json: servers[].carbon_intensity_g_kwh` (doublon exact de `3.3`). Un bloc question manuel subsiste quand même dans le questionnaire actuel. |

## Dimension 6 - Facilité de changement (6.1 à 6.10)

Chaque critère 6.x a un `methode`, un `niveau_impact`, un `potentiel_max`, et la même échelle à 3 crans (🟢 facile / 🟡 effort modéré / 🔴 difficile, coefficients 0 / 0,5 / 1).

| Critère | Libellé | Potentiel max | Bloc(s) actuel(s) | Type | Regroupé avec | Catégorie mapping |
|---|---|---|---|---|---|---|
| 6.1 | Existe-t-il un dispositif d'observabilité efficace pour le produit ? | 2.0 | porte-dim6-6.1 | direct | aucun | `partiel` (indice jamais coché seul) |
| 6.2 | Existe-t-il des revues de code et/ou du pair programming ? | 1.5 | porte-dim6-6.2 | direct | aucun | absent du mapping |
| 6.3 | Existe-t-il un processus CI/CD efficace ? | 1.5 | porte-dim6-6.3 | direct | aucun | `partiel` |
| 6.4 | Existe-t-il des tests de non-régression ? | 2.0 | porte-dim6-6.4 | direct | aucun | absent du mapping |
| 6.5 | Y a-t-il un fort découplage entre le domaine métier et l'intégration technique ? | 1.5 | porte-dim6-6.5 | direct | aucun | absent du mapping |
| 6.6 | Existe-t-il des indicateurs de qualité logicielle ? | 2.0 | porte-dim6-6.6 | direct | aucun | `partiel` |
| 6.7 | Existe-t-il une documentation complète ? | 1.5 | porte-dim6-6.7 | direct | aucun | absent du mapping |
| 6.8 | Y a-t-il du code dupliqué dans l'application ? | 1.0 | porte-dim6-6.8 | direct | aucun | `partiel` |
| 6.9 | L'équipe a-t-elle l'autonomie de déployer les outils dont elle a besoin ? | 1.0 | porte-dim6-6.9 | direct | aucun | absent du mapping |
| 6.10 | Les composants principaux sont-ils soumis à des contraintes de haute disponibilité ? | 1.5 | porte-compose-haute-dispo-0.3 | compose | 0.3 | absent du mapping (réponse déduite du même bloc que 0.3) |

## Trous de couverture

Vérification exhaustive (grep sur toutes les occurrences `0.x`/`6.x` dans `questionnaire-blocs.json`) : **les 26 critères sont tous couverts par au moins un bloc du questionnaire actuel.** Aucun trou. Un seul regroupement dans ce périmètre : `0.3` + `6.10`, dans le bloc `porte-compose-haute-dispo-0.3` (un seul jeu de réponses qui remplit les deux critères à la fois, parce qu'il s'agit du même fait sous-jacent : les contraintes de disponibilité). Tous les autres blocs sont `direct`, un par critère.

**Total : 25 questions posées pour 26 critères couverts. Ratio actuel : 1,04 critère/question.**
