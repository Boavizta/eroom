# Tableau de bord consolidé - 26 critères (diagnostic rapide + facilité de changement)

Ce tableau réunit, critère par critère, ce que l'analyse de parcours et les outils actuels peuvent remplir automatiquement, les doublons entre la partie 0 et la partie 6, et le statut de compression de chaque question. Chiffres corrigés le 2026-09-08 (une synthèse verbale erronée d'un sous-agent avait été reprise sans recalcul dans les premières versions des fichiers 02 et 04 : "16 non automatisables sur 21" au lieu du bon compte ci-dessous).

## Détail par critère

| Critère | Dimension | Libellé court | Automatisation aujourd'hui | Doublon avec | Compressible sans perte |
|---|---|---|---|---|---|
| 0.1 | 0 | Impact de la disparition du service | Non automatisable (structurel) | - | Non |
| 0.2 | 0 | Redondance/doublons dans le SI | Non automatisable (structurel) | - | Non |
| 0.3 | 0 | Haute disponibilité (SLA/SLO/DRP) | Non automatisable (structurel) | **6.10** | **Oui, déjà fait** |
| 0.4 | 0 | Dépendances techniques | Partiel (indice câblé : domaines tiers du HAR) | - | Non |
| 0.5 | 0 | Code source accessible à l'équipe | Non automatisable (structurel) | - | Non |
| 0.6 | 0 | Compétences dispo pour maintenir le service | Non automatisable (structurel) | - | Non |
| 0.7 | 0 | Complexité de l'architecture | Partiel (donnée dispo, pas câblée : CSP + CDN) | - | Non |
| 0.8 | 0 | Taille de l'infrastructure | Non automatisable (proxy faible rejeté) | - | Non |
| 0.9 | 0 | Volume de données stocké | Non automatisable (proxy faible rejeté) | - | Non |
| 0.10 | 0 | Complexité fonctionnelle | Partiel (câblé, inerte sur octo.com : sitemap absent) | - | Non |
| 0.11 | 0 | Fluidité UX/UI | Partiel (donnée dispo, pas câblée : Core Web Vitals) | - | Non |
| 0.12 | 0 | Compatibilité matériel ancien | Partiel (donnée dispo, pas câblée : CWV mobile) | - | Non |
| 0.13 | 0 | Backlog produit (perf/amélioration) | Non automatisable (structurel) | - | Non |
| 0.14 | 0 | Fonctionnalités optimisées | Non automatisable (proxy faible rejeté) | - | Non |
| 0.15 | 0 | Politique de suppression/archivage des données | Non automatisable **avec l'outillage actuel** (gap d'implémentation, pas structurel) | - | Non |
| 0.16 | 0 | Pays d'hébergement / intensité carbone | **Automatisable (déjà coché)** | doublon exact de `3.3` | **Oui, question à retirer** |
| 6.1 | 6 | Dispositif d'observabilité | Partiel (indice câblé : grade sécurité) | - | Non |
| 6.2 | 6 | Revues de code / pair programming | Non automatisable (structurel) | - | Non |
| 6.3 | 6 | Processus CI/CD | Partiel (indice câblé : Last-Modified du HAR) | - | Non |
| 6.4 | 6 | Tests de non-régression | Non automatisable (structurel) | - | Non |
| 6.5 | 6 | Découplage métier/technique | Non automatisable (proxy faible rejeté) | - | Non |
| 6.6 | 6 | Indicateurs de qualité logicielle | Partiel (indice câblé : CWV + sécurité + security.txt) | - | Non |
| 6.7 | 6 | Documentation complète | Non automatisable (structurel) | - | Non |
| 6.8 | 6 | Code dupliqué | Partiel (indice câblé : Lighthouse) | - | Non |
| 6.9 | 6 | Autonomie de déploiement des outils | Non automatisable (structurel) | - | Non |
| 6.10 | 6 | Haute disponibilité (miroir de 0.3) | Non automatisable (proxy faible rejeté) | **0.3** | **Oui, déjà fait** |

## Statistiques globales (26 critères)

| Statut | Nombre | Détail |
|---|---|---|
| Automatisable, case cochée seule | **1** | `0.16` |
| Partiel : indice affiché, réponse humaine toujours requise | **9** | `0.4, 0.7, 0.10, 0.11, 0.12` (dim. 0) + `6.1, 6.3, 6.6, 6.8` (dim. 6) |
| Non automatisable avec l'outillage actuel, mais pas structurellement impossible | **1** | `0.15` |
| Non automatisable structurellement (fait interne à l'équipe) | **15** | 9 en dimension 0 + 6 en dimension 6 |
| **Total** | **26** | |

| Doublons trouvés entre dimension 0 et dimension 6 | Nombre |
|---|---|
| Paires identifiées | **1** (`0.3` ↔ `6.10`, même fait : contraintes de disponibilité) |
| Déjà fusionnées dans le questionnaire actuel | **1 sur 1** (aucune marge restante) |
| Autres doublons recherchés et non trouvés | 0 sur les 24 critères restants |

## Nombre de questions : aujourd'hui vs plancher sans perte

| | Questions posées | Critères couverts | Ratio critère/question |
|---|---|---|---|
| Questionnaire actuel (production) | 25 | 26 | 1,04 |
| Plancher atteignable sans perte de précision | **24** | 26 | **1,083** |

Le seul écart entre les deux (1 question) vient de `0.16` : une question manuelle est encore posée en production alors que le critère est déjà résolu par l'automatique. C'est le seul point de compression identifié sur ce périmètre, une fois le doublon `0.3`/`6.10` retiré du calcul (il est déjà exploité dans les deux lignes).

Aucune autre compression n'est possible sans dégrader une réponse, pour les raisons détaillées dans `04-synthese-et-recommandation.md` : la plupart des critères restants sont des faits internes à l'équipe, et le seul format testé pour aller plus loin (QCM à cases indépendantes) a fait baisser la couverture réelle plutôt que le nombre de questions utiles.
