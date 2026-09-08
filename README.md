DISCLAIMER : CECI EST UN TRAVAIL EN COURS ET N’A PAS ÉTÉ VALIDÉ PAR LA COMMUNAUTÉ BOAVIZTA. 

# Agent EROOM

Outils et référentiels pour diagnostiquer l'impact environnemental d'un service numérique, à partir de données réelles plutôt que de moyennes génériques.

## Pourquoi ce projet existe

La plupart des estimations d'empreinte numérique reposent sur des hypothèses génériques : un "poids de page moyen", un "temps de visite moyen", un mix d'appareils moyen. Ces moyennes masquent ce qui se passe réellement pour un utilisateur donné, sur un parcours donné.

EROOM part d'un principe simple : mesurer d'abord ce qui se passe vraiment (le trafic réseau réellement capturé, le code réellement exécuté, les hôtes tiers réellement contactés), puis construire l'estimation par-dessus cette mesure, jamais à sa place. Quand une hypothèse générique est malgré tout nécessaire (durée de vie du matériel, intensité carbone électrique, longueur de réponse d'une IA générative...), elle est explicitée : sa valeur, sa source, son niveau de confiance sont tracés et affichés, jamais noyés dans un chiffre final présenté comme certain.

Deux autres principes guident les choix du projet :

- **Multi-critère plutôt que mono-critère.** Un parcours web se regarde sous plusieurs angles à la fois : trafic réseau, code mort, performance perçue (Core Web Vitals), empreinte carbone. Aucun de ces angles ne remplace les autres.
- **Un humain garde la main.** Les estimations produites nourrissent une décision humaine (prioriser, arbitrer, alerter), elles ne l'automatisent pas. Aucune boucle n'agit seule sur la base d'un résultat.

## Ce que contient le dépôt

Le projet regroupe trois familles d'outils, complémentaires mais indépendantes :

### `analyse-parcours` : diagnostic technique d'un parcours web

À partir d'une capture HAR (trafic réseau, export Chrome DevTools) et de fichiers de couverture JS/CSS, ce skill produit un rapport HTML avec :

- le détail du trafic réseau (requêtes, domaines, volumes, codes HTTP) ;
- le score EcoIndex (0 à 100, grade A à G) et le code mort JS/CSS ;
- les Core Web Vitals (mesurés ou estimés via Lighthouse) ;
- des recommandations croisées avec la stack technique détectée.

→ `.claude/skills/analyse-parcours/`

### `efootprint` : estimation CO2e du parcours

Étape optionnelle du même skill, qui réutilise les données déjà capturées (HAR, mix d'appareils CrUX, trafic annuel SimilarWeb) pour construire un modèle avec la bibliothèque [e-footprint](https://github.com/Boavizta/e-footprint) de Boavizta, et insère une section "Impact environnemental" dans le rapport.

Ce que la bibliothèque e-footprint mesure, sur quoi elle repose et où sont ses limites est documenté sans détour dans `documentation/implementation/methodologie_efootprint.md`.

→ `.claude/skills/analyse-parcours/scripts/efootprint_model/`

### Référentiel EROOM : diagnostic rapide d'éco-conception

Une grille de qualification à 16 critères / 6 piliers, dérivée du référentiel EOF, revue pour que chaque critère soit une vraie question de degré et que chaque évaluation soit reproductible d'une personne (ou d'un agent) à l'autre.

→ `.claude/skills/analyse-parcours/docs/Référenciel EROOM/`

## Démarrage rapide

Ces outils s'utilisent depuis [Claude Code](https://claude.com/claude-code), sous forme de skills invoqués en langage naturel ou par commande explicite :

```
/analyse-parcours <dossier-contenant-le-har-et-les-fichiers-de-couverture>
/efootprint <même-dossier>          # estimation CO2e seule
```

Prérequis : Python 3 (bibliothèque `e-footprint`), Node.js (Lighthouse, installé une seule fois via `npm install --prefix .claude/skills/analyse-parcours/scripts/`).

Procédure de capture du HAR et des fichiers de couverture : `.claude/skills/analyse-parcours/docs/capturer-har-et-coverage.md`.

## Statut

Projet actif, développé au fil des audits réels. Les décisions structurantes et les limites connues sont documentées dans `documentation/` ; l'historique détaillé des choix vit dans les messages de commit.

## Licence

Ce dépôt est distribué sous licence [Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0)](https://creativecommons.org/licenses/by-sa/4.0/). Voir `LICENSE`.
