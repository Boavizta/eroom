# EOF-V.1.1 (EROOM Optimization Framework) — Référentiel complet

> Généré depuis la Google Sheet source : https://docs.google.com/spreadsheets/d/1zJkT_5Ck9WKyxHZ7Uf5f03PmsaLh_SUB7LzKToPlcZ0/edit
>
> **Template vierge** — aucune réponse n'est pré-remplie. Le fichier Excel fourni en complément n'a servi qu'à deux choses que l'API de données du Sheet ne fournit pas : les 2 logos de la section "À lire" et 3 URLs de liens hypertexte (voir aux endroits concernés).

## Sommaire

- [À lire](#à-lire)
- [0 — Diagnostic rapide](#0--diagnostic-rapide)
- [🛠 6 — Facilité de changement](#6--facilité-de-changement)
- [🛖 1 — Produit](#1--produit)
- [🗺️ 2 — Architecture](#2--architecture)
- [🏢 3 — Infrastructure](#3--infrastructure)
- [💾 4 — Stockage et données](#4--stockage-et-données)
- [👨‍💻 5 — Algo & Code](#5--algo--code)
- [Synthèse](#🕸️-7--synthèse)

## 📖 À lire

![Logo Boavizta](logo1.png) ![Licence CC BY-SA](logo2.png)

> ⚠️ Le logo Boavizta (`logo1.png`) est en blanc sur fond transparent : il ne s'affiche pas sur un rendu Markdown à fond blanc (GitHub, VS Code, la plupart des visionneuses). Visible seulement sur fond sombre, ou en ouvrant le fichier directement. Non corrigé ici (retouche graphique hors périmètre) — signalé pour ne pas laisser croire à une image manquante.

### 🎯 Objectif du cadre d'optimisation EROOM

Ce diagnostic évalue la maturité d'un service numérique afin d'identifier ses principaux leviers d'optimisation : algorithme, code, architecture, opérations, données, hébergement, etc.

Chaque question porte sur un facteur influençant la performance, l'efficacité ou la maintenabilité.

Le diagnostic n'est pas une note de performance : il aide à déterminer les priorités d'action. Il n'y a pas de « bonnes » ou de « mauvaises » notes, seulement des possibilités d'amélioration.

### 📊 Échelle de notation

Pour chaque critère, attribuez une note de 1 à 5 en fonction du niveau actuel de maîtrise.

1 = non maîtrisé / inconnu

5 = maîtrisé et mesuré

Chaque question contribue de manière égale au score global, qui est ensuite converti en pourcentage de potentiel d'optimisation (0 % à 100 %).

Ce pourcentage reflète la marge d'amélioration restante pour le service.

Un score individuel faible met en évidence une possibilité d'amélioration, tandis qu'un score élevé indique que de bonnes pratiques sont déjà en place.

### 🧮 Interprétation des scores

Le score total est exprimé en pourcentage du potentiel d'optimisation.

• Pourcentage élevé → fort potentiel d'amélioration (technique, organisationnel ou environnemental).

• Faible pourcentage → service déjà mature ou efficace.

Le diagnostic n'attribue pas de note de performance.

Il est conçu pour hiérarchiser les actions et identifier les domaines dans lesquels les efforts d'amélioration auront le plus d'impact.

Il n'y a pas de « bons » ou de « mauvais » résultats, seulement des occasions d'agir.

### 💡 Pour qui ?

Le diagnostic rapide EROOM est conçu pour être léger et accessible, mais il nécessite une compréhension minimale du contexte technique.

Cela peut être réalisée par :

• une personne familiarisée avec l'environnement technique, capable d'évaluer la maturité des pratiques actuelles ;

• un duo technique-produit, pour croiser les points de vue et assurer l'alignement entre les priorités techniques et fonctionnelles ;

• un duo technique-produit, pour croiser les points de vue et assurer l'alignement entre les priorités techniques et fonctionnelles ;

### 💡 Comment utiliser

Un diagnostic correspond à un seul service numérique.

Une organisation peut donc effectuer plusieurs diagnostics rapides afin de dresser une cartographie complète de son système d'information et d'identifier les domaines dans lesquels il convient d'agir en priorité.

Étape 1 - Dupliquez le fichier

Cet outil est fourni sous forme de feuille de calcul Google Sheets.

Commencez par dupliquer le fichier pour votre usage personnel afin de pouvoir saisir vos réponses sans modifier le modèle original.

Étape 2 - Définir le périmètre

Le diagnostic est effectué pour un service numérique, une plateforme ou l'ensemble du système d'information.

Chaque service évalué doit disposer de sa propre fiche dédiée.

Étape 4 - Répondez aux questions - 0 - Diagnostic rapide

Attribuez une note de 1 à 5 à chaque question, en fonction des informations disponibles.

1 = non maîtrisé / inconnu

5 = mastered, measured, optimised

En cas de doute, sélectionnez 1 (« Je ne sais pas ») ou choisissez une note prudente, et notez le point à clarifier ultérieurement.

Vous pouvez ignorer n'importe quel critère en définissant son poids sur « Sans objet ».

Si le score du diagnostic rapide est très faible, il n'est pas nécessaire de poursuivre les étapes détaillées. Le potentiel d'optimisation est soit déjà faible, soit trop difficile à atteindre, il est donc plus efficace de se concentrer sur d'autres services.

Étape 5 - Répondez aux questions - 1 - Produit à  - 5 - Algo&Code

✅ Force confirmée = déjà traitée, aucune amélioration potentielle possible.

💡 Potentiel d'amélioration identifié = pas entièrement exploité, une marge d'amélioration significative subsiste.

Vous pouvez ignorer n'importe quel critère en définissant son poids sur « Sans objet ».

Étape 6 - Répondez aux questions - 6 - Facilité du changement

🟢 Facile à modifier = peut être mis à jour avec un minimum d'obstacles.

🟡 Effort modéré = apporter un changement serait un défi réalisable.

🔴 Difficile à changer = la mise en œuvre du changement serait difficile.

Vous pouvez ignorer n'importe quel critère en définissant son poids sur « Sans objet ».

Étape 7 - Collaborer entre les différents rôles

Réalisez le diagnostic avec les représentants techniques, produits et développement durable (RSE) afin de parvenir à une compréhension commune, et non pour noter les équipes.

L'objectif est de parvenir à une compréhension commune, et non d'attribuer une note de performance.

Faible score → service mature, déjà efficace.

Score élevé → fort potentiel d'optimisation (technique, organisationnelle ou environnementale).

Étape 7 - Utilisez les résultats

Comparez les résultats entre les différents services.

Ceux qui obtiennent les meilleurs scores deviennent les candidats prioritaires pour une analyse plus approfondie dans le cadre du programme EROOM.

Licence CC-BY-SA

« Cette licence permet aux réutilisateurs de distribuer, remixer, adapter et développer le contenu sur tout support ou format, à condition que le créateur soit mentionné.

La licence autorise l'utilisation commerciale. Si vous remixez, adaptez ou développez le contenu, vous devez accorder une licence au contenu modifié selon des conditions identiques. »


-----

## 🏦 0 — Diagnostic rapide

*Identifiez les meilleures opportunités d'optimisation. Un score plus élevé reflète un potentiel d'optimisation plus important.*

### 0.1 — La disparition du service numérique aurait-elle un impact important ?

**Évaluation**
- [ ] 1 - Impact nul ou négligeable
- [ ] 2 - Impact limité sur un petit groupe d'utilisateurs ou de processus
- [ ] 3 - Impact modéré, mais des solutions de contournement existent
- [ ] 4 - Impact significatif sur les activités principales
- [ ] 5 - Impact critique (opérations bloquées, risque majeur pour l'entreprise ou l'infrastructure informatique)

**Niveau d'impact**
- [ ] Modéré
- [ ] Significatif
- [x] Déterminant

### 0.2 — Y a-t-il des fonctionnalités redondantes ou des applications en double dans le système ?

**Évaluation**
- [ ] 1 - Quelque chose de très similaire existe déjà ailleurs (même fonctionnalité ou même code).
- [ ] 2 - Une partie existe déjà ailleurs.
- [ ] 3 - Il existe de petites similitudes, mais rien de majeur.
- [ ] 4 - Presque aucune similitude avec d'autres produits ou codes.
- [ ] 5 - Totalement unique ; rien de similaire n'existe.

**Niveau d'impact**
- [ ] Modéré
- [ ] Significatif
- [x] Déterminant

### 0.3 — Les composants principaux sont-ils soumis à des contraintes de haute disponibilité ?

**Évaluation**
- [ ] 1 - 7 jours sur 7, 24 heures sur 24 - 99,99 % - Couverture internationale
- [ ] 2 - 7 jours sur 7, 24 heures sur 24 - 99 %
- [ ] 3 - Certains [SLA](https://fr.wikipedia.org/wiki/Service-level_agreement).
- [ ] 4 - 5 jours sur 7, 8 heures sur 24 - Pas de SLA - Pas de Plan de reprise d'activité (DRP)
- [ ] 5 - Pas de SLA/SLO

**Niveau d'impact**
- [ ] Modéré
- [ ] Significatif
- [x] Déterminant

### 0.4 — Dépendances : combien de liens techniques vers d'autres systèmes sont en place ?

**Évaluation**
- [ ] 1 - Le produit n'est connecté à aucun autre système
- [ ] 2 - Le produit est connecté à quelques autres systèmes
- [ ] 3 - Le produit est connecté à certains autres systèmes et la connexion est importante (valeur commerciale et/ou couplage technique)
- [ ] 4 - Le produit est connecté à de nombreux autres systèmes
- [ ] 5 - Le produit est connecté à la plupart des autres systèmes du SI (par exemple : authentification et autorisation)

**Niveau d'impact**
- [ ] Modéré
- [ ] Significatif
- [x] Déterminant

### 0.5 — Le code source du projet est-il entièrement ou partiellement accessible à l'équipe ?

**Évaluation**
- [ ] 1 - Le code source est entièrement disponible (open source ou entièrement accessible à l'organisation).
- [ ] 2 - Le code source est principalement disponible (code accessible en interne, mais pas au public).
- [ ] 3 - Le code source est partiellement disponible (certains composants ou modules sont accessibles).
- [ ] 4 - L'accès est limité à un très petit groupe ou au fournisseur uniquement.
- [ ] 5 - Non, le code source n'est pas disponible / Je ne sais pas.

**Niveau d'impact**
- [ ] Modéré
- [ ] Significatif
- [x] Déterminant

### 0.6 — Les compétences nécessaires pour mettre à jour le service sont-elles disponibles ?

**Évaluation**
- [ ] 1 - L'équipe maîtrise bien la conception fonctionnelle et technique du projet et peut travailler en toute confiance.
- [ ] 2 - L'équipe connaît la majeure partie du projet et peut y travailler avec prudence.
- [ ] 3 - La connaissance du projet est insuffisante.
- [ ] 4 - Certaines personnes ont une connaissance partielle du projet.
- [ ] 5 - Personne ne connaît le projet.

**Niveau d'impact**
- [ ] Modéré
- [ ] Significatif
- [x] Déterminant

### 0.7 — La complexité de  l'architecture est-elle élevée ?

**Évaluation**
- [ ] 1 - Très complexe / Je ne sais pas
- [ ] 2 - Complexe
- [ ] 3 - Moyen
- [ ] 4 - Simple
- [ ] 5 - Très simple

**Niveau d'impact**
- [ ] Modéré
- [ ] Significatif
- [x] Déterminant

### 0.8 — L'infrastructure (nombre et taille des composants tels que les machines virtuelles et les conteneurs) est-elle très importante ?

**Évaluation**
- [ ] 1 - L'une des plus grandes infrastructures de l'organisation
- [ ] 2 - Plus grande que la plupart des services
- [ ] 3 - Comparable à la moyenne de l'organisation
- [ ] 4 - Plus petite que la plupart des services
- [ ] 5 - Très petite (par exemple, quelques machines virtuelles ou conteneurs)

**Niveau d'impact**
- [ ] Modéré
- [ ] Significatif
- [x] Déterminant

### 0.9 — Un volume important de données est-il stocké ?

**Évaluation**
- [ ] 1 - Le produit dispose de l'un des plus grands volumes de stockage de données dans le SI / Je ne sais pas.
- [ ] 2 - Le produit stocke un volume important de données dans le SI par rapport à la plupart des systèmes.
- [ ] 3 - Le produit stocke une quantité moyenne de données par rapport au reste du SI.
- [ ] 4 - Le produit stocke une quantité limitée de données.
- [ ] 5 - Le produit stocke très peu de données.

**Niveau d'impact**
- [ ] Modéré
- [ ] Significatif
- [x] Déterminant

### 0.10 — La complexité fonctionnelle est-elle élevée ?

**Évaluation**
- [ ] 1 - Très complexe / Je ne sais pas
- [ ] 2 - Complexe
- [ ] 3 - Moyen
- [ ] 4 - Simple
- [ ] 5 - Facile

**Niveau d'impact**
- [ ] Modéré
- [ ] Significatif
- [x] Déterminant

### 0.11 — « Les parcours utilisateurs sont-ils fluides, intuitifs et exempts de frictions UX/UI susceptibles d'être améliorées ? »

**Évaluation**
- [ ] 1 - L'UX/UI est très médiocre, les utilisateurs se plaignent et/ou il y a des éléments en attente pour le modifier / Je ne sais pas
- [ ] 2 - L'UX/UI présente des points de friction récurrents ou des problèmes d'utilisabilité
- [ ] 3 - L'UX/UI est fonctionnelle, mais certains aspects pourraient être améliorés
- [ ] 4 - L'UX/UI est claire et agréable à utiliser, seules des améliorations mineures ont été identifiées
- [ ] 5 - L'UX/UI est bien conçue, testée par les utilisateurs et offre une expérience fluide et cohérente

**Niveau d'impact**
- [ ] Modéré
- [ ] Significatif
- [x] Déterminant

### 0.12 — Le produit est-il compatible avec le matériel le plus ancien de la flotte cible et offre-t-il une expérience fluide sur celui-ci ?

**Évaluation**
- [ ] 1 - Incompatible ou inconnu
- [ ] 2 - Compatible mais avec une dégradation significative (irritant ou frustrant pour l'utilisateur)
- [ ] 3 - Compatible et utilisable mais pas confortable (ralentissement notable)
- [ ] 4 - Compatible et généralement fluide (ralentissements mineurs)
- [ ] 5 - Compatible et fluide (confortable et réactif même sur du matériel ancien)

**Niveau d'impact**
- [ ] Modéré
- [ ] Significatif
- [x] Déterminant

### 0.13 — Le backlog produit contient-il des problèmes de performance et des améliorations ?

**Évaluation**
- [ ] 1 - Dans le backlog et discussion récurrente
- [ ] 3 - Quelques améliorations sont possibles
- [ ] 5 - Aucun problème de performance identifié

**Niveau d'impact**
- [ ] Modéré
- [ ] Significatif
- [x] Déterminant

### 0.14 — Les principales fonctionnalités sont-elles optimisées et efficaces ?

**Évaluation**
- [ ] 1 - Pas assez optimisé / ne sais pas
- [ ] 2 - Certaines fonctionnalités principales sont inefficaces ou redondantes
- [ ] 3 - Les fonctionnalités principales sont fonctionnelles mais pourraient être optimisées
- [ ] 4 - La plupart des fonctionnalités principales sont bien implémentées et fonctionnent efficacement
- [ ] 5 - Toutes les fonctionnalités principales sont pleinement efficaces, rationalisées et régulièrement revues à des fins d'optimisation

**Niveau d'impact**
- [ ] Modéré
- [ ] Significatif
- [x] Déterminant

### 0.15 — Existe-t-il une politique relative à la suppression et à l'archivage des données ?

**Évaluation**
- [ ] 1 - Aucune politique / ne sais pas
- [ ] 2 - Pratiques informelles ou ponctuelles de suppression et d'archivage
- [ ] 3 - Une politique existe, mais n'est pas appliquée de manière cohérente
- [ ] 4 - Une politique claire est en place et partiellement automatisée
- [ ] 5 - Une politique stricte, appliquée et régulièrement contrôlée en matière de suppression et d'archivage des données

**Niveau d'impact**
- [ ] Modéré
- [ ] Significatif
- [x] Déterminant

### 0.16 — Le service est-il hébergé dans un pays dont le mix électrique a un impact significatif ? (en fonction de l'emplacement)

**Évaluation**
- [ ] 1 - > 750 gCO2e / kWh
- [ ] 2- < 500 gCO2e / kWh
- [ ] 3- < 300 gCO2e / kWh
- [ ] 4- < 200 gCO2e / kWh
- [ ] 5- < 100 gCO2e / kWh

**Niveau d'impact**
- [ ] Modéré
- [ ] Significatif
- [x] Déterminant


-----

## 🛠 6 — Facilité de changement

*Identifiez les meilleures opportunités d'optimisation.*

### 6.1 — Existe-t-il un dispositif d'observabilité efficace pour le produit ?

**Explication supplémentaire** : Sans un minimum de connaissances sur le comportement du produit en cours d'exécution, il est difficile d'identifier les optimisations possibles. L'absence de surveillance implique un faible potentiel d'optimisation.

**Évaluation**
- [ ] 🟢 Facile à modifier
- [ ] 🟡 Effort modéré
- [ ] 🔴 Difficile à changer

**Niveau d'impact**
- [ ] Modéré
- [ ] Significatif
- [x] Déterminant

### 6.2 — Existe-t-il des revues de code et/ou une programmation en binôme  ( pair programming)?

**Explication supplémentaire** : Les revues de code et la programmation en binôme garantissent un niveau minimum de connaissances communes sur la base de code et une qualité minimale.

**Évaluation**
- [ ] 🟢 Facile à modifier
- [ ] 🟡 Effort modéré
- [ ] 🔴 Difficile à changer

**Niveau d'impact**
- [ ] Modéré
- [x] Significatif
- [ ] Déterminant

### 6.3 — Existe-t-il un processus [CI/CD](https://fr.wikipedia.org/wiki/CI/CD) efficace ?

**Explication supplémentaire** : La présence d'un CI/CD est un bon indicateur de la facilité avec laquelle il sera possible de travailler sur l'application en toute confiance.

**Évaluation**
- [ ] 🟢 Facile à modifier
- [ ] 🟡 Effort modéré
- [ ] 🔴 Difficile à changer

**Niveau d'impact**
- [ ] Modéré
- [x] Significatif
- [ ] Déterminant

### 6.4 — Existe-t-il des tests de non-régression (tests unitaires, tests d'intégration, tests de bout en bout) ?

**Explication supplémentaire** : La présence de tests de non-régression permet aux programmeurs de modifier le logiciel tout en étant assurés de l'absence de problèmes induits par leur travail.

**Évaluation**
- [ ] 🟢 Facile à modifier
- [ ] 🟡 Effort modéré
- [ ] 🔴 Difficile à changer

**Niveau d'impact**
- [ ] Modéré
- [ ] Significatif
- [x] Déterminant

### 6.5 — Y a-t-il un fort découplage entre le domaine métier et l'intégration technique ?

**Explication supplémentaire** : Les pratiques de découplage telles que l'injection de dépendances ou l'architecture hexagonale/propre/en oignon permettent des changements techniques plus efficaces et ambitieux.
C'est le « D » (inversion des dépendances) des 5 principes fondamentaux.

**Évaluation**
- [ ] 🟢 Facile à modifier
- [ ] 🟡 Effort modéré
- [ ] 🔴 Difficile à changer

**Niveau d'impact**
- [ ] Modéré
- [x] Significatif
- [ ] Déterminant

### 6.6 — Existe-t-il des indicateurs permettant de suivre la qualité des logiciels ?

**Explication supplémentaire** : Comme la couverture de code, la complexité cyclomatique, le nombre de problèmes, le nombre de problèmes de livraison, le nombre de retours en arrière, le délai de modification, la fréquence de déploiement, le pourcentage d'échecs de modification, le temps de récupération après un déploiement échoué.

**Évaluation**
- [ ] 🟢 Facile à modifier
- [ ] 🟡 Effort modéré
- [ ] 🔴 Difficile à changer

**Niveau d'impact**
- [ ] Modéré
- [ ] Significatif
- [x] Déterminant

### 6.7 — Existe-t-il une documentation complète ?

**Explication supplémentaire** : La présence d'une documentation pertinente permet des changements plus ambitieux.

**Évaluation**
- [ ] 🟢 Facile à modifier
- [ ] 🟡 Effort modéré
- [ ] 🔴 Difficile à changer

**Niveau d'impact**
- [ ] Modéré
- [x] Significatif
- [ ] Déterminant

### 6.8 — Y a-t-il du code dupliqué dans l'application ?

**Explication supplémentaire** : Le code dupliqué peut être supprimé afin de simplifier la maintenance des produits.

**Évaluation**
- [ ] 🟢 Facile à modifier
- [ ] 🟡 Effort modéré
- [ ] 🔴 Difficile à changer

**Niveau d'impact**
- [x] Modéré
- [ ] Significatif
- [ ] Déterminant

### 6.9 — L'équipe dispose-t-elle d'une autonomie suffisante pour déployer les outils dont elle a besoin pour observer, mesurer ou optimiser le système ?

**Explication supplémentaire** : La facilité de changement augmente lorsque les équipes peuvent compter sur les outils dont elles ont besoin pour surveiller les performances, mesurer l'impact ou analyser les comportements.
Cette autonomie peut provenir de la possibilité d'installer des outils personnalisés ou de s'appuyer sur des outils intégrés complets fournis par la plateforme.
Ce qui importe, ce n'est pas l'endroit où l'infrastructure est hébergée, mais la capacité de l'équipe à l'utiliser efficacement pour soutenir l'optimisation.

**Évaluation**
- [ ] 🟢 Facile à modifier
- [ ] 🟡 Effort modéré
- [ ] 🔴 Difficile à changer

**Niveau d'impact**
- [x] Modéré
- [ ] Significatif
- [ ] Déterminant

### 6.10 — Les composants principaux sont-ils soumis à des contraintes de haute disponibilité ?

**Explication supplémentaire** : Les exigences de haute disponibilité peuvent réduire la capacité de l'équipe à modifier, migrer ou optimiser les composants.
Les services qui doivent maintenir une disponibilité stricte laissent moins de possibilités pour les fenêtres de maintenance, les changements architecturaux ou l'optimisation des ressources.
Comprendre ces contraintes aide à évaluer la facilité avec laquelle le système peut évoluer vers un impact environnemental moindre.

**Évaluation**
- [ ] 🟢 Facile à modifier
- [ ] 🟡 Effort modéré
- [ ] 🔴 Difficile à changer

**Niveau d'impact**
- [ ] Modéré
- [x] Significatif
- [ ] Déterminant


-----

## 🛖 1 — Produit

*Identifiez les meilleures opportunités d'optimisation.*

### 1.1 — Existe-t-il un moyen simple pour réaliser cette action ?

**Explication supplémentaire** : S'il existe déjà un moyen de le faire, le moyen numérique apporte-t-il une valeur ajoutée à l'utilisateur ?

**Évaluation**
- [ ] ✅ Point fort confirmé
- [ ] 💡 Potentiel d'amélioration identifié
- [ ] 🚫 Non applicable
- [ ] 🤔 À évaluer
- [ ] ⌛️ Évaluation en cours

**Niveau d'impact**
- [ ] Modéré
- [ ] Significatif
- [x] Déterminant

### 1.2 — Les utilisateurs cibles, avec leurs besoins professionnels, leurs appareils types et leurs attentes en matière d'ergonomie, sont-ils bien connus ?

**Explication supplémentaire** : Le produit risque de ne pas être bien conçu si les utilisateurs cibles ne sont pas bien connus, ou mieux encore, impliqués dans le projet. Par exemple, les parcours utilisateurs pourraient être fastidieux ou la stratégie de compatibilité pourrait être inadéquate.

**Évaluation**
- [ ] ✅ Point fort confirmé
- [ ] 💡 Potentiel d'amélioration identifié
- [ ] 🚫 Non applicable
- [ ] 🤔 À évaluer
- [ ] ⌛️ Évaluation en cours

**Niveau d'impact**
- [ ] Modéré
- [ ] Significatif
- [x] Déterminant

### 1.3 — Les mises à jour des nouvelles fonctionnalités sont-elles obligatoires pour tous les appareils, quel que soit leur système d'exploitation ou leur navigateur ?

**Explication supplémentaire** : Les nouvelles fonctionnalités alourdissent l'application. Sur les appareils plus anciens, les utilisateurs peuvent préférer conserver un produit plus simple, plus performant et moins gourmand en ressources.

**Évaluation**
- [ ] ✅ Point fort confirmé
- [ ] 💡 Potentiel d'amélioration identifié
- [ ] 🚫 Non applicable
- [ ] 🤔 À évaluer
- [ ] ⌛️ Évaluation en cours

**Niveau d'impact**
- [ ] Modéré
- [x] Significatif
- [ ] Déterminant

### 1.4 — La conception comprend-elle des composants personnalisés plutôt que des composants natifs ?

**Explication supplémentaire** : Les composants système (boutons, menus, formulaires, etc.) sont presque toujours plus efficaces que ceux créés sur mesure. Sans parler de leur accessibilité et de leur compatibilité.

**Évaluation**
- [ ] ✅ Point fort confirmé
- [ ] 💡 Potentiel d'amélioration identifié
- [ ] 🚫 Non applicable
- [ ] 🤔 À évaluer
- [ ] ⌛️ Évaluation en cours

**Niveau d'impact**
- [x] Modéré
- [ ] Significatif
- [ ] Déterminant

### 1.5 — Y a-t-il des animations, des vidéos, des sons, des cartes (...) qui sont lus automatiquement ?

**Explication supplémentaire** : La lecture de ce type de contenu sans aucune action de la part de l'utilisateur est gênante et utilise des ressources telles que la bande passante et le processeur graphique.

**Évaluation**
- [ ] ✅ Point fort confirmé
- [ ] 💡 Potentiel d'amélioration identifié
- [ ] 🚫 Non applicable
- [ ] 🤔 À évaluer
- [ ] ⌛️ Évaluation en cours

**Niveau d'impact**
- [x] Modéré
- [ ] Significatif
- [ ] Déterminant

### 1.6 — Est-il possible d'adapter les ressources utilisées par l'application à la configuration matérielle de l'utilisateur ?

**Explication supplémentaire** : Tout le monde ne dispose pas d'un appareil capable d'exécuter des contenus gourmands en ressources informatiques (comme les contenus multimédias, etc.).
Que se passe-t-il si un utilisateur tente d'exécuter un contenu gourmand en ressources informatiques sur un appareil inadapté ? Dans ce cas, idéalement, le service ne devrait pas bloquer l'accès et devrait exécuter les fonctions de base.

**Évaluation**
- [ ] ✅ Point fort confirmé
- [ ] 💡 Potentiel d'amélioration identifié
- [ ] 🚫 Non applicable
- [ ] 🤔 À évaluer
- [ ] ⌛️ Évaluation en cours

**Niveau d'impact**
- [x] Modéré
- [ ] Significatif
- [ ] Déterminant

### 1.7 — Toutes les fonctionnalités sont-elles utiles, utilisables et utilisées ?

**Explication supplémentaire** : Simplifier le produit en supprimant les fonctionnalités inutilisées permettra de réduire la consommation de ressources.

**Évaluation**
- [ ] ✅ Point fort confirmé
- [ ] 💡 Potentiel d'amélioration identifié
- [ ] 🚫 Non applicable
- [ ] 🤔 À évaluer
- [ ] ⌛️ Évaluation en cours

**Niveau d'impact**
- [ ] Modéré
- [x] Significatif
- [ ] Déterminant

### 1.8 — Le support des applications est-il médiocre sur les appareils les plus anciens ciblés ?

**Explication supplémentaire** : La plupart des impacts des services numériques se font sentir du côté des appareils clients. Il est très important de ne pas pousser ces appareils à l'obsolescence en rompant leur compatibilité.

**Évaluation**
- [ ] ✅ Point fort confirmé
- [ ] 💡 Potentiel d'amélioration identifié
- [ ] 🚫 Non applicable
- [ ] 🤔 À évaluer
- [ ] ⌛️ Évaluation en cours

**Niveau d'impact**
- [ ] Modéré
- [x] Significatif
- [ ] Déterminant

### 1.9 — Faut-il un réseau à haut débit pour utiliser l'application ?

**Explication supplémentaire** : Une bande passante élevée implique une utilisation importante des ressources. Cela indique que certaines optimisations sont possibles pour réduire le nombre et/ou la taille des requêtes.

**Évaluation**
- [ ] ✅ Point fort confirmé
- [ ] 💡 Potentiel d'amélioration identifié
- [ ] 🚫 Non applicable
- [ ] 🤔 À évaluer
- [ ] ⌛️ Évaluation en cours

**Niveau d'impact**
- [ ] Modéré
- [x] Significatif
- [ ] Déterminant

### 1.10 — Le produit utilise-t-il des designs manupulateurs (UX dark patterns) qui augmentent l'utilisation des ressources ?

**Explication supplémentaire** : Les mauvaises pratiques en matière d'expérience utilisateur comprennent le défilement infini, les abonnements pré-cochés, la difficulté à se désabonner, etc.

**Évaluation**
- [ ] ✅ Point fort confirmé
- [ ] 💡 Potentiel d'amélioration identifié
- [ ] 🚫 Non applicable
- [ ] 🤔 À évaluer
- [ ] ⌛️ Évaluation en cours

**Niveau d'impact**
- [ ] Modéré
- [x] Significatif
- [ ] Déterminant

### 1.11 — Est-il possible de modifier les valeurs par défaut (nombre d'éléments affichés, qualité, fréquence de rafraîchissement, etc.) afin de réduire l'utilisation des ressources ?

**Explication supplémentaire** : Les utilisateurs ne modifient généralement pas les valeurs par défaut. Définir des valeurs par défaut plus sobres peut permettre de réduire la consommation de ressources.

**Évaluation**
- [ ] ✅ Point fort confirmé
- [ ] 💡 Potentiel d'amélioration identifié
- [ ] 🚫 Non applicable
- [ ] 🤔 À évaluer
- [ ] ⌛️ Évaluation en cours

**Niveau d'impact**
- [ ] Modéré
- [x] Significatif
- [ ] Déterminant

### 1.12 — Y a-t-il beaucoup de pisteurs (trackers) sur le produit ?

**Explication supplémentaire** : Les outils d'analyse et de suivi marketing sont souvent responsables de plus d'un tiers des requêtes sur les sites web. Limiter le nombre d'outils et de partenaires permettrait de réduire l'utilisation des ressources et d'améliorer la confidentialité.

**Évaluation**
- [ ] ✅ Point fort confirmé
- [ ] 💡 Potentiel d'amélioration identifié
- [ ] 🚫 Non applicable
- [ ] 🤔 À évaluer
- [ ] ⌛️ Évaluation en cours

**Niveau d'impact**
- [ ] Modéré
- [x] Significatif
- [ ] Déterminant

### 1.13 — Les principaux parcours utilisateurs sont-ils optimisés pour être fluides et efficaces ?

**Explication supplémentaire** : Des parcours utilisateur efficaces avec peu d'écrans réduisent l'utilisation des ressources et améliorent la satisfaction et la productivité des utilisateurs.

**Évaluation**
- [ ] ✅ Point fort confirmé
- [ ] 💡 Potentiel d'amélioration identifié
- [ ] 🚫 Non applicable
- [ ] 🤔 À évaluer
- [ ] ⌛️ Évaluation en cours

**Niveau d'impact**
- [ ] Modéré
- [x] Significatif
- [ ] Déterminant

### 1.14 — Les écrans principaux sont-ils clairs et bien conçus ?

**Explication supplémentaire** : Les écrans les plus utilisés doivent être légers en termes d'informations affichées et de supports afin de réduire l'utilisation des ressources.

**Évaluation**
- [ ] ✅ Point fort confirmé
- [ ] 💡 Potentiel d'amélioration identifié
- [ ] 🚫 Non applicable
- [ ] 🤔 À évaluer
- [ ] ⌛️ Évaluation en cours

**Niveau d'impact**
- [ ] Modéré
- [x] Significatif
- [ ] Déterminant

### 1.15 — Ce service est-il fréquemment utilisé ?

**Explication supplémentaire** : Un service rarement utilisé mais fonctionnant en continu peut avoir un impact environnemental inutile.
À l'inverse, un service fréquemment utilisé justifie sa consommation de ressources.
Comprendre la fréquence d'utilisation permet d'évaluer si le service doit rester tel quel, être simplifié, être partiellement mis hors service ou passer à une exécution à la demande.

**Évaluation**
- [ ] ✅ Point fort confirmé
- [ ] 💡 Potentiel d'amélioration identifié
- [ ] 🚫 Non applicable
- [ ] 🤔 À évaluer
- [ ] ⌛️ Évaluation en cours

**Niveau d'impact**
- [ ] Modéré
- [x] Significatif
- [ ] Déterminant

### 1.16 — Volume (nombre d'utilisateurs)

**Explication supplémentaire** : Connaître le nombre d'utilisateurs actifs permet de contextualiser l'impact environnemental et de déterminer si l'ampleur du service correspond à son audience réelle.
Une infrastructure importante desservant une population réduite peut indiquer un surdimensionnement, tandis qu'une utilisation élevée peut justifier pleinement les ressources allouées.

**Évaluation**
- [ ] ✅ Point fort confirmé
- [ ] 💡 Potentiel d'amélioration identifié
- [ ] 🚫 Non applicable
- [ ] 🤔 À évaluer
- [ ] ⌛️ Évaluation en cours

**Niveau d'impact**
- [ ] Modéré
- [x] Significatif
- [ ] Déterminant


-----

## 🗺️ 2 — Architecture

*Identifiez les meilleures opportunités d'optimisation.*

### 2.1 — Le produit utilise-t-il des technologies gourmandes ?

**Explication supplémentaire** : Si le produit utilise des technologies lourdes telles que l'IA générative ou la blockchain, il peut être possible de le remplacer ou d'utiliser des implémentations plus efficaces.

**Évaluation**
- [ ] ✅ Point fort confirmé
- [ ] 💡 Potentiel d'amélioration identifié
- [ ] 🚫 Non applicable
- [ ] 🤔 À évaluer
- [ ] ⌛️ Évaluation en cours

**Niveau d'impact**
- [ ] Modéré
- [x] Significatif
- [ ] Déterminant

### 2.2 — Il n'y a pas de stratégie de compatibilité.

**Explication supplémentaire** : Le service doit être compatible avec tous les appareils dont disposent les utilisateurs afin d'éviter que ces appareils ne deviennent obsolètes.

**Évaluation**
- [ ] ✅ Point fort confirmé
- [ ] 💡 Potentiel d'amélioration identifié
- [ ] 🚫 Non applicable
- [ ] 🤔 À évaluer
- [ ] ⌛️ Évaluation en cours

**Niveau d'impact**
- [ ] Modéré
- [ ] Significatif
- [x] Déterminant

### 2.3 — Est-il possible d'optimiser la séparation et la communication entre les composants ?

**Explication supplémentaire** : Les choix architecturaux peuvent permettre une stratégie de mise à l'échelle efficace qui réduit l'utilisation des ressources, mais peuvent également entraîner une certaine surcharge si la séparation et le couplage des composants ne sont pas bien optimisés.

**Évaluation**
- [ ] ✅ Point fort confirmé
- [ ] 💡 Potentiel d'amélioration identifié
- [ ] 🚫 Non applicable
- [ ] 🤔 À évaluer
- [ ] ⌛️ Évaluation en cours

**Niveau d'impact**
- [ ] Modéré
- [x] Significatif
- [ ] Déterminant

### 2.4 — Le pic de charge peut-il être lissé sur une échelle de temps ?

**Explication supplémentaire** : Le déplacement des tâches dans le temps à l'aide du traitement par lots ou de courtiers de messages permet de lisser la charge et d'alléger l'infrastructure, car la charge maximale est moins importante.

**Évaluation**
- [ ] ✅ Point fort confirmé
- [ ] 💡 Potentiel d'amélioration identifié
- [ ] 🚫 Non applicable
- [ ] 🤔 À évaluer
- [ ] ⌛️ Évaluation en cours

**Niveau d'impact**
- [ ] Modéré
- [x] Significatif
- [ ] Déterminant

### 2.5 — Y a-t-il des calculs ou des requêtes lourds dont les résultats peuvent être mis en cache ?

**Explication supplémentaire** : Si, au sein du système, certains calculs et requêtes lourds renvoient plusieurs fois les mêmes résultats, il peut être possible de les mettre en cache. Cela permettra d'économiser des ressources et d'améliorer les performances.

**Évaluation**
- [ ] ✅ Point fort confirmé
- [ ] 💡 Potentiel d'amélioration identifié
- [ ] 🚫 Non applicable
- [ ] 🤔 À évaluer
- [ ] ⌛️ Évaluation en cours

**Niveau d'impact**
- [ ] Modéré
- [x] Significatif
- [ ] Déterminant


-----

## 🏢 3 — Infrastructure

*Identifiez les meilleures opportunités d'optimisation.*

### 3.1 — La facture peut-elle être réduite ?

**Explication supplémentaire** : Le déploiement d'une stratégie FinOps/GreenOps permettra au produit d'utiliser moins de ressources.
Presque toutes les pratiques FinOps (localisation des composants sous-utilisés, utilisation d'instances spot, ajustement de la taille des composants, utilisation de services gérés, etc.) permettent de réduire l'utilisation des ressources et, par conséquent, l'impact environnemental. Une stratégie visant à réduire l'impact environnemental est appelée GreenOps.

**Évaluation**
- [ ] ✅ Point fort confirmé
- [ ] 💡 Potentiel d'amélioration identifié
- [ ] 🚫 Non applicable
- [ ] 🤔 À évaluer
- [ ] ⌛️ Évaluation en cours

**Niveau d'impact**
- [ ] Modéré
- [x] Significatif
- [ ] Déterminant

### 3.2 — Il n'existe aucun système de suivi de l'impact environnemental.

**Explication supplémentaire** : Surveillance des émissions de carbone et de l'intensité carbone ? Connaissez-vous les indices PUE et WUE de votre centre de données ? Envisagez-vous de déménager vers des sites plus écologiques ?

**Évaluation**
- [ ] ✅ Point fort confirmé
- [ ] 💡 Potentiel d'amélioration identifié
- [ ] 🚫 Non applicable
- [ ] 🤔 À évaluer
- [ ] ⌛️ Évaluation en cours

**Niveau d'impact**
- [ ] Modéré
- [x] Significatif
- [ ] Déterminant

### 3.3 — Le service est-il hébergé dans une région où le mix électrique a un impact important ?

**Explication supplémentaire** : Le mix électrique local est très important : le choix de la bonne région a un effet considérable sur les impacts liés à l'utilisation du service.

**Évaluation**
- [ ] ✅ Point fort confirmé
- [ ] 💡 Potentiel d'amélioration identifié
- [ ] 🚫 Non applicable
- [ ] 🤔 À évaluer
- [ ] ⌛️ Évaluation en cours

**Niveau d'impact**
- [ ] Modéré
- [x] Significatif
- [ ] Déterminant

### 3.5 — L'infrastructure peut-elle être mutualisée ?

**Explication supplémentaire** : L'utilisation d'un hébergement mutualisé (via VM, conteneurs, services gérés, *aaS) permet de réduire l'utilisation des ressources, car celles-ci sont partagées avec d'autres produits.

**Évaluation**
- [ ] ✅ Point fort confirmé
- [ ] 💡 Potentiel d'amélioration identifié
- [ ] 🚫 Non applicable
- [ ] 🤔 À évaluer
- [ ] ⌛️ Évaluation en cours

**Niveau d'impact**
- [ ] Modéré
- [x] Significatif
- [ ] Déterminant

### 3.6 — Les composants de déploiement (VM, serveur, conteneurs) sont-ils surdimensionnés ?

**Explication supplémentaire** : Utilisez des outils/méthodologies d'observabilité pour vérifier la charge des machines virtuelles/serveurs (CPU/RAM). Elle doit être d'au moins 70 %.

**Évaluation**
- [ ] ✅ Point fort confirmé
- [ ] 💡 Potentiel d'amélioration identifié
- [ ] 🚫 Non applicable
- [ ] 🤔 À évaluer
- [ ] ⌛️ Évaluation en cours

**Niveau d'impact**
- [ ] Modéré
- [x] Significatif
- [ ] Déterminant

### 3.7 — Des outils et des stratégies d'élasticité/d’auto-scaling peuvent-ils être déployés pour réduire la taille de l'infrastructure ?

**Explication supplémentaire** : Grâce à des outils tels que les tâches cron, les orchestrateurs, les conteneurs ou les fonctions en tant que service, il est possible d'ajuster le nombre de composants déployés.
Ainsi, si la charge est faible, le nombre de composants est faible.

**Évaluation**
- [ ] ✅ Point fort confirmé
- [ ] 💡 Potentiel d'amélioration identifié
- [ ] 🚫 Non applicable
- [ ] 🤔 À évaluer
- [ ] ⌛️ Évaluation en cours

**Niveau d'impact**
- [ ] Modéré
- [x] Significatif
- [ ] Déterminant

### 3.8 — Tous les environnements sont-ils toujours activés ?

**Explication supplémentaire** : Les environnements qui ne sont pas utilisés (par exemple ceux qui ne sont pas en production la nuit ou le week-end) peuvent être désactivés.

**Évaluation**
- [ ] ✅ Point fort confirmé
- [ ] 💡 Potentiel d'amélioration identifié
- [ ] 🚫 Non applicable
- [ ] 🤔 À évaluer
- [ ] ⌛️ Évaluation en cours

**Niveau d'impact**
- [ ] Modéré
- [x] Significatif
- [ ] Déterminant

### 3.9 — Les environnements de test sont-ils aussi grands que ceux de production ?

**Explication supplémentaire** : Il n'est généralement pas nécessaire d'avoir autant de composants (VM, conteneurs) dans les environnements de test, sauf pour les tests de charge.

**Évaluation**
- [ ] ✅ Point fort confirmé
- [ ] 💡 Potentiel d'amélioration identifié
- [ ] 🚫 Non applicable
- [ ] 🤔 À évaluer
- [ ] ⌛️ Évaluation en cours

**Niveau d'impact**
- [ ] Modéré
- [x] Significatif
- [ ] Déterminant


-----

## 💾 4 — Stockage et données

*Identifiez les meilleures opportunités d'optimisation.*

### 4.1 — Des mécanismes de suppression et d'archivage sont-ils mis en place ?

**Explication supplémentaire** : Sans suppression ou archivage automatisés, les données s'accumulent inutilement et augmentent l'utilisation de l'espace de stockage. Les règles de conservation et les politiques d'archivage limitent la croissance des données et réduisent l'impact environnemental.

**Évaluation**
- [ ] ✅ Point fort confirmé
- [ ] 💡 Potentiel d'amélioration identifié
- [ ] 🚫 Non applicable
- [ ] 🤔 À évaluer
- [ ] ⌛️ Évaluation en cours

**Niveau d'impact**
- [ ] Modéré
- [x] Significatif
- [ ] Déterminant

### 4.2 — Les meilleures pratiques en matière de bases de données sont-elles mises en place ?

**Explication supplémentaire** : Une base de données non optimisée nécessite davantage de ressources CPU, de mémoire ou d'E/S pour fournir le même niveau de service, ce qui augmente la consommation d'énergie. Un indexage approprié, une bonne modélisation des données et une maintenance régulière contribuent à réduire l'utilisation inutile des ressources.

**Évaluation**
- [ ] ✅ Point fort confirmé
- [ ] 💡 Potentiel d'amélioration identifié
- [ ] 🚫 Non applicable
- [ ] 🤔 À évaluer
- [ ] ⌛️ Évaluation en cours

**Niveau d'impact**
- [ ] Modéré
- [x] Significatif
- [ ] Déterminant

### 4.3 — Le produit utilise-t-il les technologies de base de données/stockage adaptées aux utilisations prévues ?

**Explication supplémentaire** : Si les besoins en stockage de produits sont importants, il peut être avantageux de spécialiser les technologies de stockage :
- PG/MYSQL/Oracle/SQLServer ou relationnel-objet
- MongoDB pour les documents orientés.
- Base de données en colonnes pour l'analyse.
- Base de données spécialisée (vecteur, séries chronologiques).

**Évaluation**
- [ ] ✅ Point fort confirmé
- [ ] 💡 Potentiel d'amélioration identifié
- [ ] 🚫 Non applicable
- [ ] 🤔 À évaluer
- [ ] ⌛️ Évaluation en cours

**Niveau d'impact**
- [ ] Modéré
- [x] Significatif
- [ ] Déterminant

### 4.4 — Les bases de données de test sont-elles aussi volumineuses que celles de production ?

**Explication supplémentaire** : En général, il n'est pas nécessaire d'avoir autant de données dans les environnements de test qu'en production.

**Évaluation**
- [ ] ✅ Point fort confirmé
- [ ] 💡 Potentiel d'amélioration identifié
- [ ] 🚫 Non applicable
- [ ] 🤔 À évaluer
- [ ] ⌛️ Évaluation en cours

**Niveau d'impact**
- [ ] Modéré
- [x] Significatif
- [ ] Déterminant

### 4.5 — Y a-t-il des doublons dans les données ?

**Explication supplémentaire** : Si les données sont dupliquées et que cela ne fait pas partie de la stratégie produit en matière de haute disponibilité, cela indique généralement une opportunité d'optimisation, sauf lorsque la duplication résulte d'une dénormalisation intentionnelle motivée par des considérations de performance.

**Évaluation**
- [ ] ✅ Point fort confirmé
- [ ] 💡 Potentiel d'amélioration identifié
- [ ] 🚫 Non applicable
- [ ] 🤔 À évaluer
- [ ] ⌛️ Évaluation en cours

**Niveau d'impact**
- [x] Modéré
- [ ] Significatif
- [ ] Déterminant

### 4.6 — Existe-t-il des données qui sont très rarement utilisées dans le service et qui pourraient être transférées vers un stockage à froid ?

**Explication supplémentaire** : Les données rarement consultées peuvent être transférées vers un niveau de stockage plus économe en énergie, mais plus lent (« stockage à froid »).
Par exemple, les transactions datant de plus de trois mois dans un service bancaire peuvent être supprimées de la base de données principale et archivées.
L'utilisateur peut toujours les récupérer, mais via un processus plus lent, ce qui est acceptable compte tenu de leur utilisation peu fréquente.
Par exemple : les SSD ont un impact carbone 2 à 3 fois plus élevé que les disques durs mécaniques (HDD) de capacité équivalente

**Évaluation**
- [ ] ✅ Point fort confirmé
- [ ] 💡 Potentiel d'amélioration identifié
- [ ] 🚫 Non applicable
- [ ] 🤔 À évaluer
- [ ] ⌛️ Évaluation en cours

**Niveau d'impact**
- [x] Modéré
- [ ] Significatif
- [ ] Déterminant


-----

## 👨‍💻 5 — Algo & Code

*Identifiez les meilleures opportunités d'optimisation.*

### 5.1 — Existe-t-il des outils d'analyse statistique permettant de mettre en évidence des améliorations potentielles en matière d'efficacité  ?

**Explication supplémentaire** : L'analyse statique permet d'identifier les problèmes de performance et d'efficacité.
Elle contribue également à améliorer la qualité et facilite la modification des produits.

**Évaluation**
- [ ] ✅ Point fort confirmé
- [ ] 💡 Potentiel d'amélioration identifié
- [ ] 🚫 Non applicable
- [ ] 🤔 À évaluer
- [ ] ⌛️ Évaluation en cours

**Niveau d'impact**
- [x] Modéré
- [ ] Significatif
- [ ] Déterminant

### 5.2 — Une campagne de tests de charge ou de résistance a-t-elle révélé des problèmes d'efficacité ?

**Explication supplémentaire** : Si une campagne de tests de charge ou de résistance a révélé des problèmes d'efficacité, il peut être possible d'améliorer le produit.

**Évaluation**
- [ ] ✅ Point fort confirmé
- [ ] 💡 Potentiel d'amélioration identifié
- [ ] 🚫 Non applicable
- [ ] 🤔 À évaluer
- [ ] ⌛️ Évaluation en cours

**Niveau d'impact**
- [ ] Modéré
- [x] Significatif
- [ ] Déterminant

### 5.3 — L'équipe a-t-elle identifié des domaines à améliorer en termes de performance/efficacité et les a-t-elle ajoutés au backlog ?

**Explication supplémentaire** : Une amélioration est identifiée si l'équipe a identifié des gains d'efficacité.

**Évaluation**
- [ ] ✅ Point fort confirmé
- [ ] 💡 Potentiel d'amélioration identifié
- [ ] 🚫 Non applicable
- [ ] 🤔 À évaluer
- [ ] ⌛️ Évaluation en cours

**Niveau d'impact**
- [ ] Modéré
- [x] Significatif
- [ ] Déterminant

### 5.4 — Les indicateurs de performance sont-ils médiocres ?

**Explication supplémentaire** : Une mauvaise performance implique un potentiel d'optimisation. Les indicateurs de performance comprennent la latence, les requêtes par seconde, les indicateurs [Core Web Vitals](https://developers.google.com/search/docs/appearance/core-web-vitals?hl=fr), etc.

**Évaluation**
- [ ] ✅ Point fort confirmé
- [ ] 💡 Potentiel d'amélioration identifié
- [ ] 🚫 Non applicable
- [ ] 🤔 À évaluer
- [ ] ⌛️ Évaluation en cours

**Niveau d'impact**
- [x] Modéré
- [ ] Significatif
- [ ] Déterminant

### 5.5 — Les cas d'utilisation les plus critiques (parcours utilisateurs les plus fréquents) sont-ils optimisés ?

**Explication supplémentaire** : Les parcours utilisateur les plus fréquents sont essentiels pour l'ensemble des ressources utilisées par l'application. L'application d'optimisations sur ces chemins de code devrait donner de bons résultats.

**Évaluation**
- [ ] ✅ Point fort confirmé
- [ ] 💡 Potentiel d'amélioration identifié
- [ ] 🚫 Non applicable
- [ ] 🤔 À évaluer
- [ ] ⌛️ Évaluation en cours

**Niveau d'impact**
- [ ] Modéré
- [x] Significatif
- [ ] Déterminant

### 5.6 — La pile technique (Java, JS, Python, PHP, etc.)est-elle pas à jour ?

**Explication supplémentaire** : La mise à jour des outils (tels que la machine virtuelle Java) permet d'améliorer àmoindre coût les performances et l'efficacité.

**Évaluation**
- [ ] ✅ Point fort confirmé
- [ ] 💡 Potentiel d'amélioration identifié
- [ ] 🚫 Non applicable
- [ ] 🤔 À évaluer
- [ ] ⌛️ Évaluation en cours

**Niveau d'impact**
- [ ] Modéré
- [x] Significatif
- [ ] Déterminant

### 5.7 — Les composants peuvent-ils être réglés pour améliorer l'efficacité ?

**Explication supplémentaire** : Les composants d'optimisation (tels que la  machine virtuelle Java) permettent d'améliorer les performances et l'efficacité.

**Évaluation**
- [ ] ✅ Point fort confirmé
- [ ] 💡 Potentiel d'amélioration identifié
- [ ] 🚫 Non applicable
- [ ] 🤔 À évaluer
- [ ] ⌛️ Évaluation en cours

**Niveau d'impact**
- [x] Modéré
- [ ] Significatif
- [ ] Déterminant

### 5.8 — Les dépendances du projet sont-elles à jour ?

**Explication supplémentaire** : La mise à jour des dépendances du projet (comme le Spring Framework en Java) peut permettre d'améliorer les performances et l'efficacité.

**Évaluation**
- [ ] ✅ Point fort confirmé
- [ ] 💡 Potentiel d'amélioration identifié
- [ ] 🚫 Non applicable
- [ ] 🤔 À évaluer
- [ ] ⌛️ Évaluation en cours

**Niveau d'impact**
- [ ] Modéré
- [ ] Significatif
- [x] Déterminant

### 5.9 — Des problèmes de compatibilité ont-ils été identifiés pour les appareils ciblés ?

**Explication supplémentaire** : Le service doit être compatible avec tous les appareils dont disposent les utilisateurs afin d'éviter que ces appareils ne deviennent obsolètes.

**Évaluation**
- [ ] ✅ Point fort confirmé
- [ ] 💡 Potentiel d'amélioration identifié
- [ ] 🚫 Non applicable
- [ ] 🤔 À évaluer
- [ ] ⌛️ Évaluation en cours

**Niveau d'impact**
- [ ] Modéré
- [ ] Significatif
- [x] Déterminant


-----

## 🕸️ 7 — Synthèse

Ce référentiel compte **54 critères détaillés** au total, répartis sur les 6 dimensions ci-dessous (hors Diagnostic rapide, qui les recouvre en version condensée mais n'entre pas dans cette synthèse).

| Catégorie | Nombre de critères | Renvoi |
|---|---|---|
| 🛖 Produit | 16 | [Voir la section](#produit) |
| 🗺️ Architecture | 5 | [Voir la section](#architecture) |
| 🏢 Infrastructure | 8 | [Voir la section](#infrastructure) |
| 💾 Stockage & Données | 6 | [Voir la section](#stockage--données) |
| 👨‍💻 Algo & Code | 9 | [Voir la section](#algo--code) |
| 🛠 Facilité de changement | 10 | [Voir la section](#facilité-de-changement) |

**Note sur le total du Sheet source.** La formule Google Sheets qui compte le nombre total de critères référence des onglets qui n'existent plus (`#REF!` + anciens noms d'onglets) — sa valeur affichée est figée et fausse. Le total ci-dessus (54) est recompté directement depuis les données actuelles, un par un.

**Radar.** Le Sheet source affiche un radar à 6 axes qui, à l'examen, n'en trace que 5 : la catégorie *Facilité de changement* est absente du graphique (bug constaté, pas une exclusion volontaire). Tant que ce template est vierge, aucun radar réel n'a de sens ici, un exemple de rendu (potentiels d'optimisation fictifs, 6 axes) est disponible via `.claude/skills/eof/scripts/generate_radar_svg.py`.

### Comment ce référentiel se lit

- **Dimensions 1 à 5 (Produit, Architecture, Infrastructure, Stockage, Algo & Code)** : chaque critère se répond par un choix unique parmi 5 (`✅ Point fort confirmé`, `💡 Potentiel d'amélioration identifié`, `🚫 Non applicable`, `🤔 À évaluer`, `⌛️ Évaluation en cours`), en cochant la case correspondante. Coefficient observé sur le Sheet source : `✅`/`🚫`/`🤔`/vide = 0, `💡` = 1, `⌛️` = 0,5 (cette dernière valeur n'a été observée qu'une seule fois dans tout le classeur au moment de la génération, à confirmer si elle se reproduit ailleurs, ce n'est pas encore une règle certaine).
- **Dimension 6 (Facilité de changement)** : dropdown **différent** des 5 autres dimensions (confirmé par l'onglet "À lire" du Sheet source) : `🟢 Facile à modifier`, `🟡 Effort modéré`, `🔴 Difficile à changer`. Aucune réponse réelle n'existait sur cet onglet au moment de la génération, le mapping numérique (0 / 0,5 / 1 retenu ici) est une supposition par analogie avec les autres dimensions, **non vérifiée** sur une donnée réelle.
- **Potentiel d'optimisation d'une dimension** = `Σ (coefficient de la réponse × maximum de potentiel du critère)` ÷ `Σ (maximum de potentiel de TOUS les critères de la dimension, répondus ou non)`. **Un critère non répondu compte 0 au numérateur mais son maximum reste au dénominateur**, il ne pénalise donc jamais le potentiel d'optimisation, et une dimension vierge affiche 0 % de potentiel d'optimisation, pas "inconnu". C'est un biais méthodologique du Sheet source, pas une correction faite ici.
- **Maximum de potentiel "Sans objet"** : l'onglet "À lire" indique qu'on peut exclure complètement un critère en réglant son maximum de potentiel sur "Sans objet" (pas juste répondre "Non applicable" à l'évaluation, qui elle laisse le maximum compter au dénominateur). Aucun exemple réel de ce réglage n'a été observé dans les données récupérées, mécanisme documenté ici tel que décrit par le Sheet, non vérifié sur un cas concret.
- **Onglet 0 (Diagnostic rapide)** : logique différente, une échelle 1 à 5 par critère (`(5 − réponse) ÷ 4 × maximum de potentiel`), ne contribue pas à ce tableau de synthèse.
- **Maximum de potentiel** : chaque critère porte son propre maximum de potentiel (visible dans le Sheet source, colonne correspondante), différent d'un critère à l'autre, ce n'est jamais 1 partout.
