-----
Questionnaire EOF
-----

**Comment remplir ce questionnaire :**

- Cochez UNE SEULE case par bloc en utilisant la syntaxe `- [x]`.
- Une case laissée vide reste vide et ne sera jamais devinée.
- Chaque question indique dans son titre à qui la poser.
- Les questions sont classées pour que les premières rapportent le plus de critères.
- Vous pouvez vous arrêter en cours de route : l'effort fourni aura couvert le maximum de critères.
- Si vous ne savez pas, cochez la case "Je ne sais pas".

<!-- questionnaire: eof -->
<!-- version-blocs: 1 -->

-----
Partie 1 : Premier tri
-----

Ce premier tri permet de décider rapidement si un diagnostic approfondi est pertinent.

## 1 sur 59 - Contraintes de disponibilité du service (à voir avec la personne qui exploite l'infrastructure)

<!-- bloc:porte-compose-haute-dispo-0.3 -->

**Quelles sont les contraintes de disponibilité qui s'appliquent à votre service ?**

*Engagements de temps de disponibilité, plans de reprise d'activité, horaires de fonctionnement garantis. Des contraintes strictes réduisent les occasions de modifier, migrer ou optimiser l'infrastructure.*

<!-- criteres:0.3,6.10 -->
<!-- potentiel:1.5 -->

- [ ] Disponibilité 24 heures sur 24, 7 jours sur 7, avec un engagement à 99,99 % et une couverture internationale  <!-- opt:0 -->
- [ ] Disponibilité 24 heures sur 24, 7 jours sur 7, avec un engagement à 99 %  <!-- opt:1 -->
- [ ] Quelques engagements de service, sans exigence de disponibilité permanente  <!-- opt:2 -->
- [ ] Disponibilité en heures ouvrées seulement, sans engagement de service ni plan de reprise d'activité  <!-- opt:3 -->
- [x] Aucun engagement de disponibilité  <!-- opt:4 -->
- [ ] Je ne sais pas  <!-- opt:jnsp -->

## 2 sur 59 - Impact d'une panne (à voir avec le responsable produit)

<!-- bloc:porte-diag-0.1 -->

**Si ce service s'arrêtait demain matin, qu'est-ce que cela changerait concrètement pour vous ?**

*Regardez ce qui se bloque vraiment : des clients qui ne peuvent plus commander, une équipe qui ne peut plus travailler, une réputation abîmée.*

<!-- criteres:0.1 -->

- [ ] 1 - Impact nul ou négligeable  <!-- opt:0 -->
- [ ] 2 - Impact limité sur un petit groupe d'utilisateurs ou de processus  <!-- opt:1 -->
- [x] 3 - Impact modéré, mais des solutions de contournement existent  <!-- opt:2 -->
- [ ] 4 - Impact significatif sur les activités principales  <!-- opt:3 -->
- [ ] 5 - Impact critique (opérations bloquées, risque majeur pour l'entreprise ou l'infrastructure informatique)  <!-- opt:4 -->
- [ ] Je ne sais pas  <!-- opt:jnsp -->

## 3 sur 59 - Doublons avec d'autres services (à voir avec le responsable produit)

<!-- bloc:porte-diag-0.2 -->

**Est-ce que d'autres services ou applications dans votre organisation font la même chose ou quelque chose de similaire ?**

*Cherchez les fonctionnalités qui se recouvrent ou du code qui fait le même travail ailleurs dans votre organisation.*

<!-- criteres:0.2 -->

- [ ] 1 - Quelque chose de très similaire existe déjà ailleurs (même fonctionnalité ou même code).  <!-- opt:0 -->
- [ ] 2 - Une partie existe déjà ailleurs.  <!-- opt:1 -->
- [ ] 3 - Il existe de petites similitudes, mais rien de majeur.  <!-- opt:2 -->
- [ ] 4 - Presque aucune similitude avec d'autres produits ou codes.  <!-- opt:3 -->
- [x] 5 - Totalement unique ; rien de similaire n'existe.  <!-- opt:4 -->
- [ ] Je ne sais pas  <!-- opt:jnsp -->

## 4 sur 59 - Connexions avec d'autres systèmes (à voir avec l'équipe de développement)

<!-- bloc:porte-diag-0.4 -->

**À combien d'autres systèmes ce service est-il techniquement relié ?**

*Comptez les connexions actives : API que vous appelez, bases de données partagées, services d'authentification, flux de données entrants ou sortants.*

> **Ce que nous avons mesuré :**
> 5 domaine(s) tiers détecté(s) lors de la capture (liste observée depuis l'extérieur, ne dit rien de l'architecture technique complète) : api.analytics.octo.tools, cdn.jsdelivr.net, fonts.googleapis.com, fonts.gstatic.com, swetrix.org
>
> Confirmez, ou corrigez si notre mesure est incomplète.

<!-- criteres:0.4 -->

- [ ] 1 - Le produit n'est connecté à aucun autre système  <!-- opt:0 -->
- [x] 2 - Le produit est connecté à quelques autres systèmes  *(proposition depuis la mesure, à confirmer)*  <!-- opt:1 -->
- [ ] 3 - Le produit est connecté à certains autres systèmes et la connexion est importante (valeur commerciale et/ou couplage technique)  <!-- opt:2 -->
- [ ] 4 - Le produit est connecté à de nombreux autres systèmes  <!-- opt:3 -->
- [ ] 5 - Le produit est connecté à la plupart des autres systèmes du SI (par exemple : authentification et autorisation)  <!-- opt:4 -->
- [ ] Je ne sais pas  <!-- opt:jnsp -->

## 5 sur 59 - Disponibilité du code source (à voir avec l'équipe de développement)

<!-- bloc:porte-diag-0.5 -->

**Dans quelle mesure avez-vous accès au code source de ce service ?**

*Code complètement accessible à l'équipe, code ouvert au public, code fermé fourni par un éditeur, ou accès limité à certains modules seulement.*

<!-- criteres:0.5 -->

- [ ] 1 - Le code source est entièrement disponible (open source ou entièrement accessible à l'organisation).  <!-- opt:0 -->
- [x] 2 - Le code source est principalement disponible (code accessible en interne, mais pas au public).  <!-- opt:1 -->
- [ ] 3 - Le code source est partiellement disponible (certains composants ou modules sont accessibles).  <!-- opt:2 -->
- [ ] 4 - L'accès est limité à un très petit groupe ou au fournisseur uniquement.  <!-- opt:3 -->
- [ ] 5 - Non, le code source n'est pas disponible  <!-- opt:4 -->
- [ ] Je ne sais pas  <!-- opt:jnsp -->

## 6 sur 59 - Maîtrise du service par l'équipe (à voir avec l'équipe de développement)

<!-- bloc:porte-diag-0.6 -->

**Votre équipe connaît-elle suffisamment ce service pour le modifier en toute confiance ?**

*Regardez si l'équipe maîtrise la conception fonctionnelle et technique, si elle peut travailler sereinement ou avec prudence, ou si la connaissance est trop fragmentée.*

<!-- criteres:0.6 -->

- [x] 1 - L'équipe maîtrise bien la conception fonctionnelle et technique du projet et peut travailler en toute confiance.  <!-- opt:0 -->
- [ ] 2 - L'équipe connaît la majeure partie du projet et peut y travailler avec prudence.  <!-- opt:1 -->
- [ ] 3 - La connaissance du projet est insuffisante.  <!-- opt:2 -->
- [ ] 4 - Certaines personnes ont une connaissance partielle du projet.  <!-- opt:3 -->
- [ ] 5 - Personne ne connaît le projet.  <!-- opt:4 -->
- [ ] Je ne sais pas  <!-- opt:jnsp -->

## 7 sur 59 - Complexité de l'architecture (à voir avec l'équipe de développement)

<!-- bloc:porte-diag-0.7 -->

**Comment jugez-vous la complexité de l'architecture de ce service ?**

*Pensez au nombre de composants, à leurs interactions, aux technologies différentes utilisées, à la facilité de comprendre le fonctionnement d'ensemble.*

> **Ce que nous avons mesuré :**
> 3 composant(s) d'hébergement/diffusion distinct(s) déclaré(s) au CSP (herokuapp.com, cdn.jsdelivr.net, cdnjs.cloudflare.com), ce qui suggère plusieurs briques séparées plutôt qu'un bloc unique. Ce n'est qu'un indice indirect et partiel : il ne voit ni le nombre de microservices internes, ni le couplage réel entre ces briques, ni la complexité fonctionnelle du site.
>
> Confirmez, ou corrigez si notre mesure est incomplète.

<!-- criteres:0.7 -->

- [ ] 1 - Très complexe  <!-- opt:0 -->
- [ ] 2 - Complexe  <!-- opt:1 -->
- [x] 3 - Moyen  *(proposition depuis la mesure, à confirmer)*  <!-- opt:2 -->
- [ ] 4 - Simple  <!-- opt:3 -->
- [ ] 5 - Très simple  <!-- opt:4 -->
- [ ] Je ne sais pas  <!-- opt:jnsp -->

## 8 sur 59 - Taille de l'infrastructure (à voir avec la personne qui exploite l'infrastructure)

<!-- bloc:porte-diag-0.8 -->

**Quelle est la taille de l'infrastructure de ce service par rapport à vos autres services ?**

*Comparez le nombre et la taille des serveurs, machines virtuelles, conteneurs ou autres composants hébergés à ce que vous avez ailleurs dans l'organisation.*

<!-- criteres:0.8 -->

- [ ] 1 - L'une des plus grandes infrastructures de l'organisation  <!-- opt:0 -->
- [ ] 2 - Plus grande que la plupart des services  <!-- opt:1 -->
- [ ] 3 - Comparable à la moyenne de l'organisation  <!-- opt:2 -->
- [x] 4 - Plus petite que la plupart des services  <!-- opt:3 -->
- [ ] 5 - Très petite (par exemple, quelques machines virtuelles ou conteneurs)  <!-- opt:4 -->
- [ ] Je ne sais pas  <!-- opt:jnsp -->

## 9 sur 59 - Volume de données stockées (à voir avec la personne qui gère les données)

<!-- bloc:porte-diag-0.9 -->

**Quel volume de données ce service stocke-t-il par rapport à vos autres services ?**

*Regardez les bases de données, les fichiers, les archives, les sauvegardes. Comparez à ce que vous avez ailleurs dans l'organisation.*

<!-- criteres:0.9 -->

- [ ] 1 - Le produit dispose de l'un des plus grands volumes de stockage de données dans le SI  <!-- opt:0 -->
- [ ] 2 - Le produit stocke un volume important de données dans le SI par rapport à la plupart des systèmes.  <!-- opt:1 -->
- [ ] 3 - Le produit stocke une quantité moyenne de données par rapport au reste du SI.  <!-- opt:2 -->
- [x] 4 - Le produit stocke une quantité limitée de données.  <!-- opt:3 -->
- [ ] 5 - Le produit stocke très peu de données.  <!-- opt:4 -->
- [ ] Je ne sais pas  <!-- opt:jnsp -->

## 10 sur 59 - Complexité du service (à voir avec le responsable produit)

<!-- bloc:porte-diag-0.10 -->

**Comment décririez-vous la complexité de ce service ?**

*Pensez au nombre de fonctionnalités, aux règles métier, aux différents cas d'usage que vous gérez.*

<!-- criteres:0.10 -->

- [ ] 1 - Très complexe  <!-- opt:0 -->
- [ ] 2 - Complexe  <!-- opt:1 -->
- [ ] 3 - Moyen  <!-- opt:2 -->
- [x] 4 - Simple  <!-- opt:3 -->
- [ ] 5 - Facile  <!-- opt:4 -->
- [ ] Je ne sais pas  <!-- opt:jnsp -->

## 11 sur 59 - Fluidité de l'expérience utilisateur (à voir avec le responsable produit)

<!-- bloc:porte-diag-0.11 -->

**Comment évaluez-vous la fluidité et l'intuitivité des parcours utilisateurs ?**

*Regardez ce que disent vos utilisateurs, les endroits où ils butent, les améliorations que vous avez en liste d'attente.*

> **Ce que nous avons mesuré :**
> Pire page toutes stratégies confondues (Core Web Vitals terrain/lab) : https://octo.com/ (desktop) : LCP 1.407s, INP 39.0ms, CLS 0.0, catégorie CrUX 'FAST'. Ce sont des scores techniques de chargement, réactivité et stabilité visuelle, pas une mesure directe du ressenti utilisateur.
>
> Confirmez, ou corrigez si notre mesure est incomplète.

<!-- criteres:0.11 -->

- [ ] 1 - L'UX/UI est très médiocre, les utilisateurs se plaignent et/ou il y a des éléments en attente pour le modifier  <!-- opt:0 -->
- [ ] 2 - L'UX/UI présente des points de friction récurrents ou des problèmes d'utilisabilité  <!-- opt:1 -->
- [ ] 3 - L'UX/UI est fonctionnelle, mais certains aspects pourraient être améliorés  *(proposition depuis la mesure, à confirmer)*  <!-- opt:2 -->
- [x] 4 - L'UX/UI est claire et agréable à utiliser, seules des améliorations mineures ont été identifiées  <!-- opt:3 -->
- [ ] 5 - L'UX/UI est bien conçue, testée par les utilisateurs et offre une expérience fluide et cohérente  <!-- opt:4 -->
- [ ] Je ne sais pas  <!-- opt:jnsp -->

## 12 sur 59 - Appareils anciens (à voir avec l'équipe de développement)

<!-- bloc:porte-diag-0.12 -->

**Ce service fonctionne-t-il bien sur les appareils les plus anciens que vos utilisateurs utilisent encore ?**

*Vérifiez s'il y a des ralentissements, des incompatibilités, ou si l'expérience reste confortable.*

> **Ce que nous avons mesuré :**
> Pire page en stratégie mobile (proxy matériel bas de gamme/ancien) : https://octo.com/recrutement/offers/consultant-ai-engineer-senior-fhn (mobile) : LCP 1.331s, INP 82.0ms, CLS 0.0, catégorie CrUX 'FAST'. Le CrUX mobile terrain mélange tous types d'appareils, ce n'est pas une mesure isolée sur du matériel ancien spécifiquement.
>
> Confirmez, ou corrigez si notre mesure est incomplète.

<!-- criteres:0.12 -->

- [ ] 1 - Incompatible ou inconnu  <!-- opt:0 -->
- [ ] 2 - Compatible mais avec une dégradation significative (irritant ou frustrant pour l'utilisateur)  <!-- opt:1 -->
- [ ] 3 - Compatible et utilisable mais pas confortable (ralentissement notable)  <!-- opt:2 -->
- [ ] 4 - Compatible et généralement fluide (ralentissements mineurs)  *(proposition depuis la mesure, à confirmer)*  <!-- opt:3 -->
- [x] 5 - Compatible et fluide (confortable et réactif même sur du matériel ancien)  <!-- opt:4 -->
- [ ] Je ne sais pas  <!-- opt:jnsp -->

## 13 sur 59 - Problèmes de performance connus (à voir avec le responsable produit)

<!-- bloc:porte-diag-0.13 -->

**Votre backlog contient-il des problèmes de performance ou des besoins d'optimisation ?**

*Tickets ouverts sur la lenteur du service, discussions récurrentes sur l'efficacité, améliorations techniques identifiées mais non encore traitées.*

<!-- criteres:0.13 -->

- [ ] 1 - Dans le backlog et discussion récurrente  <!-- opt:0 -->
- [ ] 3 - Quelques améliorations sont possibles  <!-- opt:1 -->
- [x] 5 - Aucun problème de performance identifié  <!-- opt:2 -->
- [ ] Je ne sais pas  <!-- opt:jnsp -->

## 14 sur 59 - Efficacité des fonctionnalités (à voir avec l'équipe de développement)

<!-- bloc:porte-diag-0.14 -->

**Les fonctionnalités principales de ce service sont-elles bien implémentées et performantes ?**

*Cherchez les fonctionnalités qui font double emploi ou qui pourraient être plus efficaces.*

<!-- criteres:0.14 -->

- [ ] 1 - Pas assez optimisé / ne sais pas  <!-- opt:0 -->
- [ ] 2 - Certaines fonctionnalités principales sont inefficaces ou redondantes  <!-- opt:1 -->
- [ ] 3 - Les fonctionnalités principales sont fonctionnelles mais pourraient être optimisées  <!-- opt:2 -->
- [x] 4 - La plupart des fonctionnalités principales sont bien implémentées et fonctionnent efficacement  <!-- opt:3 -->
- [ ] 5 - Toutes les fonctionnalités principales sont pleinement efficaces, rationalisées et régulièrement revues à des fins d'optimisation  <!-- opt:4 -->
- [ ] Je ne sais pas  <!-- opt:jnsp -->

## 15 sur 59 - Suppression et archivage des données (à voir avec la personne qui gère les données)

<!-- bloc:porte-diag-0.15 -->

**Disposez-vous d'une politique de suppression et d'archivage des données pour ce service ?**

*Regardez s'il existe des règles formalisées, si elles sont appliquées de manière cohérente, si des automatismes sont en place, et si des contrôles réguliers vérifient leur respect.*

<!-- criteres:0.15 -->

- [ ] 1 - Aucune politique / ne sais pas  <!-- opt:0 -->
- [ ] 2 - Pratiques informelles ou ponctuelles de suppression et d'archivage  <!-- opt:1 -->
- [ ] 3 - Une politique existe, mais n'est pas appliquée de manière cohérente  <!-- opt:2 -->
- [ ] 4 - Une politique claire est en place et partiellement automatisée  <!-- opt:3 -->
- [ ] 5 - Une politique stricte, appliquée et régulièrement contrôlée en matière de suppression et d'archivage des données  <!-- opt:4 -->
- [ ] Je ne sais pas  <!-- opt:jnsp -->

## 16 sur 59 - Facilité d'observer le comportement (à voir avec l'équipe de développement)

<!-- bloc:porte-dim6-6.1 -->

**Est-il facile de mettre en place et d'exploiter des outils pour suivre le comportement de ce service en production ?**

*Pensez à la possibilité d'ajouter des métriques, des logs, des traces, des alertes, des tableaux de bord. Regardez si des outils sont déjà en place et s'ils sont simples à faire évoluer.*

> **Ce que nous avons mesuré :**
> Score en-têtes de sécurité HTTP : 70% (grade B) sur https://octo.com/recrutement/offers/consultant-mlops-engineer-confirmesenior-fhn - indicateur parmi d'autres de la maturité en production
>
> Confirmez, ou corrigez si notre mesure est incomplète.

<!-- criteres:6.1 -->
<!-- potentiel:2.0 -->

- [ ] 🟢 Facile à modifier  <!-- opt:0 -->
- [x] 🟡 Effort modéré  *(proposition depuis la mesure, à confirmer)*  <!-- opt:1 -->
- [ ] 🔴 Difficile à changer  <!-- opt:2 -->
- [ ] Je ne sais pas  <!-- opt:jnsp -->

## 17 sur 59 - Facilité des revues de code (à voir avec l'équipe de développement)

<!-- bloc:porte-dim6-6.2 -->

**Est-il facile d'organiser des revues de code ou de la programmation en binôme sur ce projet ?**

*Regardez si des processus sont déjà en place, si l'équipe a le temps et les habitudes pour cela, si des obstacles organisationnels ou techniques compliquent leur mise en oeuvre.*

<!-- criteres:6.2 -->
<!-- potentiel:1.5 -->

- [ ] 🟢 Facile à modifier  <!-- opt:0 -->
- [x] 🟡 Effort modéré  <!-- opt:1 -->
- [ ] 🔴 Difficile à changer  <!-- opt:2 -->
- [ ] Je ne sais pas  <!-- opt:jnsp -->

## 18 sur 59 - Facilité de mettre en place un CI/CD (à voir avec l'équipe de développement)

<!-- bloc:porte-dim6-6.3 -->

**Est-il facile de mettre en place ou de faire évoluer un processus de construction et de déploiement automatisé pour ce projet ?**

*Regardez si des automatisations existent déjà, si l'infrastructure le permet, si l'équipe a les compétences et les accès nécessaires pour construire et tester automatiquement le code.*

> **Ce que nous avons mesuré :**
> ressource de votre site la plus récente : 0.5 jour(s) avant la capture (publiée à 01:01 UTC) ; les 24 ressources de code (HTML/CSS/JS) sont publiées en 13 s (mise en ligne en un seul bloc) ; les adresses de vos fichiers portent une date (v=2026-6-10-1-1) qui concorde à 19 s près avec la date de dernière modification déclarée par votre serveur, donc produite par votre chaîne de fabrication
>
> Confirmez, ou corrigez si notre mesure est incomplète.

<!-- criteres:6.3 -->
<!-- potentiel:1.5 -->

- [x] 🟢 Facile à modifier  *(proposition depuis la mesure, à confirmer)*  <!-- opt:0 -->
- [ ] 🟡 Effort modéré  <!-- opt:1 -->
- [ ] 🔴 Difficile à changer  <!-- opt:2 -->
- [ ] Je ne sais pas  <!-- opt:jnsp -->

## 19 sur 59 - Facilité d'ajouter des tests (à voir avec l'équipe de développement)

<!-- bloc:porte-dim6-6.4 -->

**Est-il facile d'ajouter ou de faire évoluer des tests automatisés sur ce projet ?**

*Pensez aux tests unitaires, tests d'intégration, tests de bout en bout. Regardez si une infrastructure de tests existe déjà, si le code se prête à être testé, si l'équipe a les compétences et le temps pour écrire des tests.*

<!-- criteres:6.4 -->
<!-- potentiel:2.0 -->

- [ ] 🟢 Facile à modifier  <!-- opt:0 -->
- [ ] 🟡 Effort modéré  <!-- opt:1 -->
- [ ] 🔴 Difficile à changer  <!-- opt:2 -->
- [x] Je ne sais pas  <!-- opt:jnsp -->

## 20 sur 59 - Facilité de changer la technique (à voir avec l'équipe de développement)

<!-- bloc:porte-dim6-6.5 -->

**Est-il facile de modifier les aspects techniques de ce service sans toucher au code fonctionnel ?**

*Regardez si le code métier est bien séparé de l'intégration technique. Par exemple, pouvez-vous changer de base de données, de service d'authentification ou de framework sans réécrire la logique fonctionnelle ?*

<!-- criteres:6.5 -->
<!-- potentiel:1.5 -->

- [ ] 🟢 Facile à modifier  <!-- opt:0 -->
- [ ] 🟡 Effort modéré  <!-- opt:1 -->
- [x] 🔴 Difficile à changer  <!-- opt:2 -->
- [ ] Je ne sais pas  <!-- opt:jnsp -->

## 21 sur 59 - Facilité de suivre la qualité (à voir avec l'équipe de développement)

<!-- bloc:porte-dim6-6.6 -->

**Est-il facile de mettre en place et de suivre des indicateurs de qualité pour ce logiciel ?**

*Pensez à la couverture de code, à la complexité, au nombre de bugs, au délai de modification, à la fréquence de déploiement. Regardez si des outils existent déjà ou s'il est simple d'en ajouter.*

> **Ce que nous avons mesuré :**
> Audit Lighthouse - Bonnes Pratiques (pire page) : 73% ; en-têtes de sécurité (pire page) : grade B ; fichier security.txt : absent
>
> Confirmez, ou corrigez si notre mesure est incomplète.

<!-- criteres:6.6 -->
<!-- potentiel:2.0 -->

- [ ] 🟢 Facile à modifier  <!-- opt:0 -->
- [x] 🟡 Effort modéré  *(proposition depuis la mesure, à confirmer)*  <!-- opt:1 -->
- [ ] 🔴 Difficile à changer  <!-- opt:2 -->
- [ ] Je ne sais pas  <!-- opt:jnsp -->

## 22 sur 59 - Facilité de documenter le projet (à voir avec l'équipe de développement)

<!-- bloc:porte-dim6-6.7 -->

**Est-il facile de maintenir une documentation complète et à jour pour ce projet ?**

*Regardez si une documentation existe déjà, si l'équipe a les outils et le temps pour la tenir à jour, si le projet s'y prête. Pensez à l'architecture, aux guides de développement, aux explications des choix techniques.*

<!-- criteres:6.7 -->
<!-- potentiel:1.5 -->

- [ ] 🟢 Facile à modifier  <!-- opt:0 -->
- [x] 🟡 Effort modéré  <!-- opt:1 -->
- [ ] 🔴 Difficile à changer  <!-- opt:2 -->
- [ ] Je ne sais pas  <!-- opt:jnsp -->

## 23 sur 59 - Facilité d'éliminer les duplications (à voir avec l'équipe de développement)

<!-- bloc:porte-dim6-6.8 -->

**Est-il facile de repérer et de supprimer le code dupliqué dans ce projet ?**

*Regardez si du code copié-collé ou des logiques répétées existent, si l'équipe a les outils pour les détecter, et si l'architecture permet de les factoriser sans risque.*

> **Ce que nous avons mesuré :**
> Aucune duplication de code JavaScript détectée par l'audit Lighthouse (score parfait). Cela ne prouve pas que votre gestion des dépendances soit optimale, seulement qu'aucune duplication évidente n'a été repérée.
>
> Confirmez, ou corrigez si notre mesure est incomplète.

<!-- criteres:6.8 -->
<!-- potentiel:1.0 -->

- [x] 🟢 Facile à modifier  *(proposition depuis la mesure, à confirmer)*  <!-- opt:0 -->
- [ ] 🟡 Effort modéré  <!-- opt:1 -->
- [ ] 🔴 Difficile à changer  <!-- opt:2 -->
- [ ] Je ne sais pas  <!-- opt:jnsp -->

## 24 sur 59 - Autonomie pour déployer des outils (à voir avec l'équipe de développement)

<!-- bloc:porte-dim6-6.9 -->

**Est-il facile pour votre équipe de déployer les outils dont elle a besoin pour observer, mesurer et optimiser ce système ?**

*Regardez si l'équipe peut installer des outils personnalisés, accéder aux données de performance, utiliser des outils fournis par la plateforme, sans avoir à demander d'autorisations lourdes.*

<!-- criteres:6.9 -->
<!-- potentiel:1.0 -->

- [ ] 🟢 Facile à modifier  <!-- opt:0 -->
- [x] 🟡 Effort modéré  <!-- opt:1 -->
- [ ] 🔴 Difficile à changer  <!-- opt:2 -->
- [ ] Je ne sais pas  <!-- opt:jnsp -->

-----
Partie 2 : Questions détaillées
-----

## 25 sur 59 - Stockage de données du service (à voir avec la personne qui gère les données)

<!-- bloc:filtre-donnees-persistantes -->

**Votre service conserve-t-il des données dans une base de données ou un stockage qui lui est propre ?**

*Des données persistantes sont conservées même après un redémarrage du service. Un cache temporaire en mémoire n'est pas du stockage persistant.*

<!-- criteres:4.1,4.2,4.3,4.4,4.5,4.6 -->
<!-- potentiel:8.0 -->

- [ ] Non, le service ne conserve aucune donnée (ou seulement en cache temporaire)  <!-- opt:ecarte -->
- [ ] Oui, le service conserve des données persistantes (base de données, fichiers, etc.)  <!-- opt:applicable -->
- [ ] Je ne sais pas  <!-- opt:jnsp -->

## 26 sur 59 - Environnements de test (à voir avec la personne qui exploite l'infrastructure)

<!-- bloc:filtre-environnement-test -->

**Disposez-vous d'environnements de test ou de développement distincts de la production ?**

*Un environnement de test est une infrastructure séparée où vous pouvez tester vos modifications avant de les déployer en production.*

<!-- criteres:3.8,3.9 -->
<!-- potentiel:3.0 -->

- [ ] Non, nous n'avons pas d'environnement de test distinct  <!-- opt:ecarte -->
- [ ] Oui, nous avons des environnements de test ou de développement  <!-- opt:applicable -->
- [ ] Je ne sais pas  <!-- opt:jnsp -->

## 27 sur 59 - Tests sur les appareils anciens (à voir avec le responsable produit)

<!-- bloc:detail-compose-appareils-anciens -->

**Que se passe-t-il quand vous testez votre service sur les appareils les plus anciens que vous vous engagez à supporter ?**

*C'est-à-dire les appareils que vous promettez de supporter, même s'ils ont plusieurs années.*

> **Note :** Le périmètre des appareils ciblés est une décision produit : à valider avec le responsable produit.

<!-- criteres:1.8,5.9 -->
<!-- potentiel:3.5 -->

- [ ] Nous testons sur les appareils les plus anciens de notre cible, et aucun problème de compatibilité n'a été détecté  <!-- opt:0 -->
- [ ] Nous avons détecté des problèmes de compatibilité, mais le service reste utilisable sur ces appareils  <!-- opt:1 -->
- [ ] Nous avons détecté des problèmes de compatibilité qui dégradent réellement l'usage sur ces appareils  <!-- opt:2 -->
- [ ] Notre service ne cible aucun appareil ancien : le parc utilisateur est récent et maîtrisé  <!-- opt:3 -->
- [ ] Je ne sais pas  <!-- opt:jnsp -->

## 28 sur 59 - Dimensionnement et élasticité (à voir avec la personne qui exploite l'infrastructure)

<!-- bloc:detail-compose-dimensionnement -->

**Vos composants tournent-ils à au moins 70 % de charge, et leur nombre s'ajuste-t-il quand la charge varie ?**

*Regardez la charge processeur ou mémoire de vos serveurs et conteneurs. L'ajustement automatique doit avoir une limite haute pour éviter les emballements.*

> **Ce que nous avons mesuré :**
> Votre service s'appuie sur une plate-forme d'hébergement (herokuapp.com) capable d'ajuster automatiquement ses ressources. Nous ne pouvons pas voir de l'extérieur si cet ajustement est activé chez vous, ni si votre charge varie assez pour le justifier.
>
> Confirmez, ou corrigez si notre mesure est incomplète.

<!-- criteres:3.6,3.7 -->
<!-- potentiel:3.0 -->

- [ ] Nos composants tournent à au moins 70 % de charge CPU ou RAM, et un auto-scaling borné est en place (ou la charge est constante)  <!-- opt:0 -->
- [ ] Nos composants tournent à au moins 70 % de charge, mais il n'y a pas d'auto-scaling alors que la charge varie  <!-- opt:1 -->
- [ ] Nos composants tournent en dessous de 70 % de charge, mais un auto-scaling borné est en place (ou la charge est constante)  <!-- opt:2 -->
- [ ] Nos composants tournent en dessous de 70 % de charge, et il n'y a pas d'auto-scaling alors que la charge varie  <!-- opt:3 -->
- [x] Je ne sais pas  *(la mesure confirme seulement que la plate-forme PEUT ajuster ses ressources, pas si c'est activé ni si la charge le justifie)*  <!-- opt:jnsp -->

## 29 sur 59 - Environnements de test (à voir avec la personne qui exploite l'infrastructure)

**A IGNORER** si vous avez repondu "Non, le service ne conserve aucune donnée" a la question 25 (Stockage de données du service) ET "Non, nous n'avons pas d'environnement de test distinct" a la question 26 (Environnements de test).

<!-- bloc:detail-compose-environnements-test -->

**Quelle est la taille de vos environnements de test par rapport à la production ?**

*Regardez le nombre et la taille de vos machines virtuelles, conteneurs, et le volume de vos bases de données.*

<!-- criteres:3.9,4.4 -->
<!-- potentiel:3.0 -->

- [ ] Infrastructure réduite ET bases de données réduites  <!-- opt:0 -->
- [ ] Infrastructure réduite MAIS bases de données aussi volumineuses qu'en production  <!-- opt:1 -->
- [ ] Infrastructure identique à la production MAIS bases de données réduites  <!-- opt:2 -->
- [ ] Infrastructure ET bases de données identiques à la production  <!-- opt:3 -->
- [ ] Nous n'avons pas d'environnements de test  <!-- opt:4 -->
- [ ] Je ne sais pas  <!-- opt:jnsp -->

## 30 sur 59 - Gestion des données anciennes (à voir avec la personne qui gère les données)

**A IGNORER** si vous avez repondu "Non, le service ne conserve aucune donnée" a la question 25 (Stockage de données du service).

<!-- bloc:detail-compose-donnees-anciennes -->

**Que se passe-t-il quand une donnée devient inutile ou rarement consultée ?**

*Par exemple : une règle qui supprime ou archive automatiquement les anciennes factures, ou un transfert vers un disque plus lent mais moins énergivore pour les données rarement demandées.*

> **Note :** Le caractère acceptable d'un accès plus lent pour l'utilisateur est une décision produit : à valider avec le responsable produit.

<!-- criteres:4.1,4.6 -->
<!-- potentiel:2.5 -->

- [ ] Des mécanismes automatiques de suppression et d'archivage sont appliqués, ET les données rarement consultées ont déjà été basculées vers un stockage à froid  <!-- opt:0 -->
- [ ] Des mécanismes automatiques de suppression et d'archivage sont appliqués, mais tout reste sur le stockage principal  <!-- opt:1 -->
- [ ] Aucun mécanisme automatique, mais les données rarement consultées ont déjà été basculées vers un stockage à froid  <!-- opt:2 -->
- [ ] Aucun mécanisme automatique, et tout reste sur le stockage principal  <!-- opt:3 -->
- [ ] Je ne sais pas  <!-- opt:jnsp -->

## 31 sur 59 - Ce que vos outils ont révélé (à voir avec l'équipe de développement)

<!-- bloc:detail-compose-outils-efficacite -->

**Vos outils d'analyse du code et vos tests de charge ont-ils révélé des points à améliorer ?**

*Les outils d'analyse automatique du code et les tests sous forte charge permettent de détecter des inefficacités. L'absence de ces pratiques compte aussi comme un potentiel d'amélioration.*

<!-- criteres:5.1,5.2 -->
<!-- potentiel:2.5 -->

- [ ] Les deux pratiques sont en place et n'ont révélé aucun problème d'efficacité  <!-- opt:0 -->
- [ ] L'analyse statique n'a rien révélé, mais la campagne de charge a révélé des problèmes, ou nous n'en menons pas  <!-- opt:1 -->
- [ ] L'analyse statique a révélé des gains possibles, ou nous n'en faisons pas, mais la campagne de charge n'a rien révélé  <!-- opt:2 -->
- [ ] Les deux ont révélé des problèmes, ou au moins l'une des deux pratiques est absente  <!-- opt:3 -->
- [ ] Je ne sais pas  <!-- opt:jnsp -->

## 32 sur 59 - Pile technique et dépendances à jour (à voir avec l'équipe de développement)

<!-- bloc:detail-compose-a-jour -->

**Votre plateforme et vos bibliothèques principales sont-elles à jour ?**

*La plateforme, c'est par exemple Node, Python, Java, PHP : vérifiez que vous êtes au moins sur la version que l'éditeur s'engage à maintenir longtemps. Les bibliothèques, ce sont les frameworks et modules que vous importez dans votre code.*

<!-- criteres:5.6,5.8 -->
<!-- potentiel:3.5 -->

- [ ] Le socle est au moins sur la dernière version LTS ET les principales dépendances sont à jour  <!-- opt:0 -->
- [ ] Le socle est au moins sur la dernière version LTS, mais des dépendances importantes sont en retard  <!-- opt:1 -->
- [ ] Le socle est en retard sur la dernière version LTS, mais les principales dépendances sont à jour  <!-- opt:2 -->
- [ ] Le socle est en retard ET des dépendances importantes le sont aussi  <!-- opt:3 -->
- [ ] Je ne sais pas  <!-- opt:jnsp -->

## 33 sur 59 - Valeur ajoutée du numérique (à voir avec le responsable produit)

<!-- bloc:detail-dim1-1.1 -->

**Avez-vous identifié une solution non numérique et démontré que votre version numérique apporte une valeur ajoutée claire ?**

*Cherchez les gains de temps, d'accessibilité ou de réduction d'impact matériel par rapport à ce qui existait avant.*

<!-- criteres:1.1 -->
<!-- potentiel:2.0 -->

- [ ] ✅ Point fort confirmé  <!-- opt:0 -->
- [ ] 💡 Potentiel d'amélioration identifié  <!-- opt:1 -->
- [ ] 🚫 Non applicable  <!-- opt:2 -->
- [ ] 🤔 À évaluer  <!-- opt:3 -->
- [ ] ⌛️ Évaluation en cours  <!-- opt:4 -->
- [ ] Je ne sais pas  <!-- opt:jnsp -->

## 34 sur 59 - Connaissance des utilisateurs (à voir avec le responsable produit)

<!-- bloc:detail-dim1-1.2 -->

**Documentez-vous les besoins, les contextes d'usage et les appareils de vos utilisateurs cibles ?**

*Regardez si vous avez des personas, des entretiens, des analyses d'utilisation, ou une liste des appareils couramment utilisés.*

<!-- criteres:1.2 -->
<!-- potentiel:2.0 -->

- [ ] ✅ Point fort confirmé  <!-- opt:0 -->
- [ ] 💡 Potentiel d'amélioration identifié  <!-- opt:1 -->
- [ ] 🚫 Non applicable  <!-- opt:2 -->
- [ ] 🤔 À évaluer  <!-- opt:3 -->
- [ ] ⌛️ Évaluation en cours  <!-- opt:4 -->
- [ ] Je ne sais pas  <!-- opt:jnsp -->

## 35 sur 59 - Impact des mises à jour (à voir avec le responsable produit)

<!-- bloc:detail-dim1-1.3 -->

**Vous testez que vos nouvelles fonctionnalités restent performantes sur les appareils anciens ou modestes, et vous proposez des modes allégés quand c'est nécessaire.**

*Regardez si vous testez réellement sur ces appareils, et si vous offrez un mode simplifié quand les performances baissent.*

<!-- criteres:1.3 -->
<!-- potentiel:1.5 -->

- [ ] ✅ Point fort confirmé  <!-- opt:0 -->
- [ ] 💡 Potentiel d'amélioration identifié  <!-- opt:1 -->
- [ ] 🚫 Non applicable  <!-- opt:2 -->
- [ ] 🤔 À évaluer  <!-- opt:3 -->
- [ ] ⌛️ Évaluation en cours  <!-- opt:4 -->
- [ ] Je ne sais pas  <!-- opt:jnsp -->

## 36 sur 59 - Composants natifs ou personnalisés (à voir avec l'équipe de développement)

<!-- bloc:detail-dim1-1.4 -->

**Vous utilisez les composants natifs du système, ou vous justifiez chaque composant personnalisé par une vraie nécessité.**

*Les boutons, menus et formulaires du système sont plus performants et accessibles que ceux créés sur mesure, sauf exception justifiée.*

> **Ce que nous avons mesuré :**
> Boutons HTML natifs détectés : 14 ; boutons avec attribut role='button' : 1 (sur l'ensemble des pages)
>
> Confirmez, ou corrigez si notre mesure est incomplète.

<!-- criteres:1.4 -->
<!-- potentiel:1.0 -->

- [x] ✅ Point fort confirmé  *(proposition depuis la mesure, à confirmer)*  <!-- opt:0 -->
- [ ] 💡 Potentiel d'amélioration identifié  <!-- opt:1 -->
- [ ] 🚫 Non applicable  <!-- opt:2 -->
- [ ] 🤔 À évaluer  <!-- opt:3 -->
- [ ] ⌛️ Évaluation en cours  <!-- opt:4 -->
- [ ] Je ne sais pas  <!-- opt:jnsp -->

## 37 sur 59 - Adaptation au matériel (à voir avec l'équipe de développement)

<!-- bloc:detail-dim1-1.6 -->

**Votre application détecte les appareils à configuration limitée et passe automatiquement en mode allégé.**

*Par exemple : qualité d'image réduite, rendu simplifié, ou désactivation automatique des fonctions lourdes.*

<!-- criteres:1.6 -->
<!-- potentiel:1.0 -->

- [ ] ✅ Point fort confirmé  <!-- opt:0 -->
- [ ] 💡 Potentiel d'amélioration identifié  <!-- opt:1 -->
- [ ] 🚫 Non applicable  <!-- opt:2 -->
- [ ] 🤔 À évaluer  <!-- opt:3 -->
- [ ] ⌛️ Évaluation en cours  <!-- opt:4 -->
- [ ] Je ne sais pas  <!-- opt:jnsp -->

## 38 sur 59 - Utilité des fonctionnalités (à voir avec le responsable produit)

<!-- bloc:detail-dim1-1.7 -->

**Chaque fonctionnalité de votre service est-elle réellement utilisée et apporte-t-elle de la valeur ?**

*Regardez vos analyses d'usage, les commentaires utilisateurs, et vérifiez si vous avez supprimé les fonctionnalités redondantes ou inutilisées.*

<!-- criteres:1.7 -->
<!-- potentiel:1.5 -->

- [ ] ✅ Point fort confirmé  <!-- opt:0 -->
- [ ] 💡 Potentiel d'amélioration identifié  <!-- opt:1 -->
- [ ] 🚫 Non applicable  <!-- opt:2 -->
- [ ] 🤔 À évaluer  <!-- opt:3 -->
- [ ] ⌛️ Évaluation en cours  <!-- opt:4 -->
- [ ] Je ne sais pas  <!-- opt:jnsp -->

## 39 sur 59 - Compatibilité basse bande passante (à voir avec l'équipe de développement)

<!-- bloc:detail-dim1-1.9 -->

**Votre application reste utilisable sur une connexion à faible débit, grâce à des requêtes optimisées, des fichiers allégés et de la mise en cache.**

*Regardez si vous limitez le nombre et la taille des requêtes, si vous réduisez les images et vidéos, et si vous mettez en cache les contenus.*

> **Ce que nous avons mesuré :**
> Données réellement transférées (page la plus lourde) : 702 Ko
>
> Confirmez, ou corrigez si notre mesure est incomplète.

<!-- criteres:1.9 -->
<!-- potentiel:1.5 -->

- [ ] ✅ Point fort confirmé  <!-- opt:0 -->
- [ ] 💡 Potentiel d'amélioration identifié  <!-- opt:1 -->
- [ ] 🚫 Non applicable  <!-- opt:2 -->
- [x] 🤔 À évaluer  *(le poids seul ne dit rien sur les requêtes/le cache, pas de seuil établi pour trancher)*  <!-- opt:3 -->
- [ ] ⌛️ Évaluation en cours  <!-- opt:4 -->
- [ ] Je ne sais pas  <!-- opt:jnsp -->

## 40 sur 59 - Pratiques manipulatrices (à voir avec le responsable produit)

<!-- bloc:detail-dim1-1.10 -->

**Votre conception évite-t-elle les pratiques qui poussent artificiellement l'utilisateur à consommer plus ?**

*Cherchez le défilement infini, la lecture automatique forcée, les désabonnements cachés, les cases pré-cochées.*

<!-- criteres:1.10 -->
<!-- potentiel:1.5 -->

- [ ] ✅ Point fort confirmé  <!-- opt:0 -->
- [ ] 💡 Potentiel d'amélioration identifié  <!-- opt:1 -->
- [ ] 🚫 Non applicable  <!-- opt:2 -->
- [ ] 🤔 À évaluer  <!-- opt:3 -->
- [ ] ⌛️ Évaluation en cours  <!-- opt:4 -->
- [ ] Je ne sais pas  <!-- opt:jnsp -->

## 41 sur 59 - Valeurs par défaut sobres (à voir avec le responsable produit)

<!-- bloc:detail-dim1-1.11 -->

**Vos valeurs par défaut sont-elles sobres et les utilisateurs peuvent-ils facilement les ajuster ?**

*Regardez le nombre d'éléments affichés, la qualité des médias, la fréquence de rafraîchissement.*

> **Ce que nous avons mesuré :**
> Aucune règle @media (prefers-reduced-motion ou prefers-color-scheme) détectée dans les feuilles de style
>
> Confirmez, ou corrigez si notre mesure est incomplète.

<!-- criteres:1.11 -->
<!-- potentiel:1.5 -->

- [ ] ✅ Point fort confirmé  <!-- opt:0 -->
- [x] 💡 Potentiel d'amélioration identifié  *(proposition depuis la mesure, à confirmer)*  <!-- opt:1 -->
- [ ] 🚫 Non applicable  <!-- opt:2 -->
- [ ] 🤔 À évaluer  <!-- opt:3 -->
- [ ] ⌛️ Évaluation en cours  <!-- opt:4 -->
- [ ] Je ne sais pas  <!-- opt:jnsp -->

## 42 sur 59 - Limitation des traceurs (à voir avec le responsable produit)

<!-- bloc:detail-dim1-1.12 -->

**Vous limitez le nombre de traceurs au strict nécessaire, et chaque outil de suivi est justifié.**

*Les outils marketing et d'analyse sont souvent responsables d'un tiers du trafic : supprimez ceux qui font doublon.*

> **Note :** La justification de chaque traceur est une décision produit ou marketing : à valider avec le responsable produit.

<!-- criteres:1.12 -->
<!-- potentiel:1.5 -->

- [ ] ✅ Point fort confirmé  <!-- opt:0 -->
- [ ] 💡 Potentiel d'amélioration identifié  <!-- opt:1 -->
- [ ] 🚫 Non applicable  <!-- opt:2 -->
- [ ] 🤔 À évaluer  <!-- opt:3 -->
- [ ] ⌛️ Évaluation en cours  <!-- opt:4 -->
- [ ] Je ne sais pas  <!-- opt:jnsp -->

## 43 sur 59 - Parcours et écrans principaux (à voir avec le responsable produit)

<!-- bloc:detail-compose-parcours-ecrans -->

**Comment sont organisés vos parcours utilisateurs principaux et qu'est-ce qui s'affiche à l'écran ?**

*Comptez les étapes pour réaliser les actions courantes, et regardez combien d'informations et de médias vous affichez sur les écrans les plus visités.*

> **Ce que nous avons mesuré :**
> Page la plus lourde : https://octo.com/publications (1003 Ko)
>
> Confirmez, ou corrigez si notre mesure est incomplète.

<!-- criteres:1.14 -->
<!-- potentiel:1.5 -->

- [ ] Parcours courts avec peu d'étapes ET écrans légers avec informations essentielles uniquement  <!-- opt:0 -->
- [ ] Parcours courts avec peu d'étapes MAIS écrans chargés (beaucoup de contenu, médias lourds)  <!-- opt:1 -->
- [ ] Parcours longs ou redondants MAIS écrans légers  <!-- opt:2 -->
- [ ] Parcours longs ou redondants ET écrans chargés  <!-- opt:3 -->
- [x] Je ne sais pas  *(la mesure ne porte que sur le poids de la page, pas sur le nombre d'étapes du parcours)*  <!-- opt:jnsp -->

<!-- deja-tranche:1.13 -->

## 44 sur 59 - Fréquence d'utilisation (à voir avec le responsable produit)

<!-- bloc:detail-dim1-1.15 -->

**Ce service présente-t-il une utilisation régulière et significative ?**

*Vérifiez que la fréquence d'usage est en rapport avec ce que le service coûte en ressources.*

> **Ce que nous avons mesuré :**
> Trafic estimé : 293 000 visites/an (SimilarWeb (estimation))
>
> Confirmez, ou corrigez si notre mesure est incomplète.

<!-- criteres:1.15 -->
<!-- potentiel:1.5 -->

- [x] ✅ Point fort confirmé  *(proposition depuis la mesure : ~800 visites/jour, usage réel et non négligeable)*  <!-- opt:0 -->
- [ ] 💡 Potentiel d'amélioration identifié  <!-- opt:1 -->
- [ ] 🚫 Non applicable  <!-- opt:2 -->
- [ ] 🤔 À évaluer  <!-- opt:3 -->
- [ ] ⌛️ Évaluation en cours  <!-- opt:4 -->
- [ ] Je ne sais pas  <!-- opt:jnsp -->

## 45 sur 59 - Volume d'utilisateurs (à voir avec la personne qui exploite l'infrastructure)

<!-- bloc:detail-dim1-1.16 -->

**Le volume d'utilisateurs actifs justifie-t-il l'architecture et les ressources allouées ?**

*Regardez si le nombre d'utilisateurs est en rapport avec la taille de votre infrastructure.*

> **Ce que nous avons mesuré :**
> Trafic estimé : 293 000 visites/an (SimilarWeb (estimation))
>
> Confirmez, ou corrigez si notre mesure est incomplète.

<!-- criteres:1.16 -->
<!-- potentiel:1.5 -->

- [x] ✅ Point fort confirmé  *(proposition incertaine : trafic modeste et infra à un seul serveur semblent cohérents entre eux, mais aucun seuil établi pour en juger)*  <!-- opt:0 -->
- [ ] 💡 Potentiel d'amélioration identifié  <!-- opt:1 -->
- [ ] 🚫 Non applicable  <!-- opt:2 -->
- [ ] 🤔 À évaluer  <!-- opt:3 -->
- [ ] ⌛️ Évaluation en cours  <!-- opt:4 -->
- [ ] Je ne sais pas  <!-- opt:jnsp -->

## 46 sur 59 - Stratégie de compatibilité (à voir avec l'équipe de développement)

<!-- bloc:detail-dim2-2.2 -->

**Avez-vous défini une stratégie de compatibilité avec les appareils de vos utilisateurs ?**

*Vérifiez si vous avez une liste des appareils ciblés, si vous faites des tests de compatibilité, et si vous supportez les appareils anciens.*

<!-- criteres:2.2 -->
<!-- potentiel:2.0 -->

- [ ] ✅ Point fort confirmé  <!-- opt:0 -->
- [ ] 💡 Potentiel d'amélioration identifié  <!-- opt:1 -->
- [ ] 🚫 Non applicable  <!-- opt:2 -->
- [ ] 🤔 À évaluer  <!-- opt:3 -->
- [ ] ⌛️ Évaluation en cours  <!-- opt:4 -->
- [ ] Je ne sais pas  <!-- opt:jnsp -->

## 47 sur 59 - Communication entre composants (à voir avec l'équipe de développement)

<!-- bloc:detail-dim2-2.3 -->

**Vos composants sont faiblement couplés, et leur communication ne provoque pas de ralentissements ni de complexité inutile.**

*Regardez si un composant peut changer sans casser les autres, et si la communication entre eux est rapide et fiable.*

> **Ce que nous avons mesuré :**
> Plusieurs composants d'hébergement distincts détectés (herokuapp.com), ce qui suggère une architecture séparant les responsabilités. Nous ne pouvons pas évaluer de l'extérieur l'efficacité de leur couplage ni l'optimisation de leur communication.
>
> Confirmez, ou corrigez si notre mesure est incomplète.

<!-- criteres:2.3 -->
<!-- potentiel:1.5 -->

- [ ] ✅ Point fort confirmé  <!-- opt:0 -->
- [ ] 💡 Potentiel d'amélioration identifié  <!-- opt:1 -->
- [ ] 🚫 Non applicable  <!-- opt:2 -->
- [x] 🤔 À évaluer  *(la mesure le dit elle-même : on ne peut pas juger le couplage depuis l'extérieur)*  <!-- opt:3 -->
- [ ] ⌛️ Évaluation en cours  <!-- opt:4 -->
- [ ] Je ne sais pas  <!-- opt:jnsp -->

## 48 sur 59 - Lissage des pics de charge (à voir avec l'équipe de développement)

<!-- bloc:detail-dim2-2.4 -->

**Vous lissez vos pics de charge en différant les tâches qui n'ont pas besoin d'être exécutées immédiatement.**

*Par exemple : traiter les exports ou les notifications par lots, ou utiliser des files d'attente pour répartir le travail.*

<!-- criteres:2.4 -->
<!-- potentiel:1.5 -->

- [ ] ✅ Point fort confirmé  <!-- opt:0 -->
- [ ] 💡 Potentiel d'amélioration identifié  <!-- opt:1 -->
- [ ] 🚫 Non applicable  <!-- opt:2 -->
- [ ] 🤔 À évaluer  <!-- opt:3 -->
- [ ] ⌛️ Évaluation en cours  <!-- opt:4 -->
- [ ] Je ne sais pas  <!-- opt:jnsp -->

## 49 sur 59 - Mise en cache (à voir avec l'équipe de développement)

<!-- bloc:detail-dim2-2.5 -->

**Vous mettez en cache les résultats de vos calculs et requêtes coûteux quand ils sont réutilisés plusieurs fois.**

*Regardez si vous recalculez les mêmes choses plusieurs fois, ou si vous gardez le résultat en mémoire pour le réutiliser.*

> **Ce que nous avons mesuré :**
> https://api.analytics.octo.tools/log/hb chargé 54 fois ; https://api.analytics.octo.tools/log/ chargé 18 fois ; https://octo.com/style.css?v=2026-6-10-1-1 chargé 11 fois
>
> Confirmez, ou corrigez si notre mesure est incomplète.

<!-- criteres:2.5 -->
<!-- potentiel:1.5 -->

- [ ] ✅ Point fort confirmé  <!-- opt:0 -->
- [ ] 💡 Potentiel d'amélioration identifié  <!-- opt:1 -->
- [ ] 🚫 Non applicable  <!-- opt:2 -->
- [x] 🤔 À évaluer  *(les URLs les plus répétées sont des balises de mesure d'audience, normal en soi ; le style.css chargé 11 fois peut juste refléter 11 pages visitées, pas un défaut de cache)*  <!-- opt:3 -->
- [ ] ⌛️ Évaluation en cours  <!-- opt:4 -->
- [ ] Je ne sais pas  <!-- opt:jnsp -->

## 50 sur 59 - Optimisation des coûts (à voir avec la personne qui exploite l'infrastructure)

<!-- bloc:detail-dim3-3.1 -->

**Vous avez mis en place une stratégie pour optimiser vos coûts d'infrastructure.**

*Par exemple : repérer les composants sous-utilisés, ajuster leur taille, ou basculer vers des services mieux dimensionnés.*

<!-- criteres:3.1 -->
<!-- potentiel:1.5 -->

- [ ] ✅ Point fort confirmé  <!-- opt:0 -->
- [ ] 💡 Potentiel d'amélioration identifié  <!-- opt:1 -->
- [ ] 🚫 Non applicable  <!-- opt:2 -->
- [ ] 🤔 À évaluer  <!-- opt:3 -->
- [ ] ⌛️ Évaluation en cours  <!-- opt:4 -->
- [ ] Je ne sais pas  <!-- opt:jnsp -->

## 51 sur 59 - Suivi de l'impact environnemental (à voir avec la personne qui exploite l'infrastructure)

<!-- bloc:detail-dim3-3.2 -->

**Vous suivez l'impact environnemental de votre infrastructure.**

*Par exemple : émissions de carbone de vos serveurs, efficacité énergétique et consommation d'eau de votre centre de données.*

> **Ce que nous avons mesuré :**
> Déclaration sur eco-conception.html : "Nous avons fixé plusieurs objectifs à notre démarche, notamment : Réduire l'empreinte environnementale de notre site internet en diminuant la consommation d'énergie nécessaire à son fonctionnement."
>
> Confirmez, ou corrigez si notre mesure est incomplète.

<!-- criteres:3.2 -->
<!-- potentiel:1.5 -->

- [ ] ✅ Point fort confirmé  <!-- opt:0 -->
- [ ] 💡 Potentiel d'amélioration identifié  <!-- opt:1 -->
- [ ] 🚫 Non applicable  <!-- opt:2 -->
- [x] 🤔 À évaluer  *(la déclaration parle des pages du site, pas explicitement du suivi carbone/énergie/eau de l'infrastructure que demande ce critère)*  <!-- opt:3 -->
- [ ] ⌛️ Évaluation en cours  <!-- opt:4 -->
- [ ] Je ne sais pas  <!-- opt:jnsp -->

## 52 sur 59 - Mutualisation de l'infrastructure (à voir avec la personne qui exploite l'infrastructure)

<!-- bloc:detail-dim3-3.5 -->

**Votre infrastructure est mutualisée.**

*Par exemple : machines virtuelles, conteneurs, ou services gérés qui partagent les ressources avec d'autres projets.*

> **Ce que nous avons mesuré :**
> Votre service fait appel à 6 service(s) d'infrastructure externe(s) (hébergement, diffusion de contenu, cloud) : herokuapp.com, cdn.jsdelivr.net, cdnjs.cloudflare.com, amazonaws.com, googleapis.com...
>
> Confirmez, ou corrigez si notre mesure est incomplète.

<!-- criteres:3.5 -->
<!-- potentiel:1.5 -->

- [x] ✅ Point fort confirmé  *(proposition depuis la mesure : usage confirmé de PaaS/CDN/cloud mutualisés)*  <!-- opt:0 -->
- [ ] 💡 Potentiel d'amélioration identifié  <!-- opt:1 -->
- [ ] 🚫 Non applicable  <!-- opt:2 -->
- [ ] 🤔 À évaluer  <!-- opt:3 -->
- [ ] ⌛️ Évaluation en cours  <!-- opt:4 -->
- [ ] Je ne sais pas  <!-- opt:jnsp -->

## 53 sur 59 - Extinction des environnements (à voir avec la personne qui exploite l'infrastructure)

**A IGNORER** si vous avez repondu "Non, nous n'avons pas d'environnement de test distinct" a la question 26 (Environnements de test).

<!-- bloc:detail-dim3-3.8 -->

**Vous éteignez vos environnements non productifs quand personne ne les utilise.**

*Par exemple : environnements de développement ou de test éteints la nuit, le week-end, ou entre deux campagnes de tests.*

<!-- criteres:3.8 -->
<!-- potentiel:1.5 -->

- [ ] ✅ Point fort confirmé  <!-- opt:0 -->
- [ ] 💡 Potentiel d'amélioration identifié  <!-- opt:1 -->
- [ ] 🚫 Non applicable  <!-- opt:2 -->
- [ ] 🤔 À évaluer  <!-- opt:3 -->
- [ ] ⌛️ Évaluation en cours  <!-- opt:4 -->
- [ ] Je ne sais pas  <!-- opt:jnsp -->

## 54 sur 59 - Optimisation des bases de données (à voir avec l'équipe de développement)

**A IGNORER** si vous avez repondu "Non, le service ne conserve aucune donnée" a la question 25 (Stockage de données du service).

<!-- bloc:detail-dim4-4.2 -->

**Avez-vous une stratégie pour optimiser les performances de vos bases de données ?**

*Par exemple : choisir les bons index, modéliser les tables pour limiter les requêtes coûteuses, nettoyer régulièrement la base.*

<!-- criteres:4.2 -->
<!-- potentiel:1.5 -->

- [ ] ✅ Point fort confirmé  <!-- opt:0 -->
- [ ] 💡 Potentiel d'amélioration identifié  <!-- opt:1 -->
- [ ] 🚫 Non applicable  <!-- opt:2 -->
- [ ] 🤔 À évaluer  <!-- opt:3 -->
- [ ] ⌛️ Évaluation en cours  <!-- opt:4 -->
- [ ] Je ne sais pas  <!-- opt:jnsp -->

## 55 sur 59 - Technologies de stockage adaptées (à voir avec l'équipe de développement)

**A IGNORER** si vous avez repondu "Non, le service ne conserve aucune donnée" a la question 25 (Stockage de données du service).

<!-- bloc:detail-dim4-4.3 -->

**Vos technologies de stockage correspondent-elles vraiment à ce que vous en faites ?**

*Par exemple : une base relationnelle classique pour les données structurées, une base orientée document pour du contenu flexible, une base en colonnes pour de l'analyse, ou une base spécialisée pour des cas précis.*

<!-- criteres:4.3 -->
<!-- potentiel:1.5 -->

- [ ] ✅ Point fort confirmé  <!-- opt:0 -->
- [ ] 💡 Potentiel d'amélioration identifié  <!-- opt:1 -->
- [ ] 🚫 Non applicable  <!-- opt:2 -->
- [ ] 🤔 À évaluer  <!-- opt:3 -->
- [ ] ⌛️ Évaluation en cours  <!-- opt:4 -->
- [ ] Je ne sais pas  <!-- opt:jnsp -->

## 56 sur 59 - Duplication de données (à voir avec la personne qui gère les données)

**A IGNORER** si vous avez repondu "Non, le service ne conserve aucune donnée" a la question 25 (Stockage de données du service).

<!-- bloc:detail-dim4-4.5 -->

**Avez-vous repéré les données dupliquées et vérifié si c'est voulu ?**

*Certaines duplications sont utiles : pour garantir que le service reste accessible même en cas de panne, ou pour accélérer certaines requêtes. D'autres sont accidentelles et coûtent de l'espace pour rien.*

<!-- criteres:4.5 -->
<!-- potentiel:1.0 -->

- [ ] ✅ Point fort confirmé  <!-- opt:0 -->
- [ ] 💡 Potentiel d'amélioration identifié  <!-- opt:1 -->
- [ ] 🚫 Non applicable  <!-- opt:2 -->
- [ ] 🤔 À évaluer  <!-- opt:3 -->
- [ ] ⌛️ Évaluation en cours  <!-- opt:4 -->
- [ ] Je ne sais pas  <!-- opt:jnsp -->

## 57 sur 59 - Backlog d'optimisations (à voir avec l'équipe de développement)

<!-- bloc:detail-dim5-5.3 -->

**Votre backlog contient-il des tâches d'optimisation ?**

*Par exemple : des tickets ou issues qui visent à accélérer une page, réduire la consommation mémoire, ou améliorer le temps de réponse.*

<!-- criteres:5.3 -->
<!-- potentiel:1.5 -->

- [ ] ✅ Point fort confirmé  <!-- opt:0 -->
- [ ] 💡 Potentiel d'amélioration identifié  <!-- opt:1 -->
- [ ] 🚫 Non applicable  <!-- opt:2 -->
- [ ] 🤔 À évaluer  <!-- opt:3 -->
- [ ] ⌛️ Évaluation en cours  <!-- opt:4 -->
- [ ] Je ne sais pas  <!-- opt:jnsp -->

## 58 sur 59 - Optimisation des parcours fréquents (à voir avec l'équipe de développement)

<!-- bloc:detail-dim5-5.5 -->

**Les parcours utilisateurs les plus fréquents ont-ils fait l'objet d'une étude d'optimisation ?**

*Regardez si vous avez analysé et amélioré les chemins de code les plus empruntés.*

> **Ce que nous avons mesuré :**
> https://octo.com/ : JavaScript inutilisé 79.02% ; https://octo.com/recrutement : JavaScript inutilisé 71.68%
>
> Confirmez, ou corrigez si notre mesure est incomplète.

<!-- criteres:5.5 -->
<!-- potentiel:1.5 -->

- [ ] ✅ Point fort confirmé  <!-- opt:0 -->
- [x] 💡 Potentiel d'amélioration identifié  *(proposition depuis la mesure : 70 à 80 % de JS inutilisé sur les pages les plus visitées)*  <!-- opt:1 -->
- [ ] 🚫 Non applicable  <!-- opt:2 -->
- [ ] 🤔 À évaluer  <!-- opt:3 -->
- [ ] ⌛️ Évaluation en cours  <!-- opt:4 -->
- [ ] Je ne sais pas  <!-- opt:jnsp -->

## 59 sur 59 - Configuration des composants (à voir avec la personne qui exploite l'infrastructure)

<!-- bloc:detail-dim5-5.7 -->

**Avez-vous vérifié si vos composants pourraient être mieux configurés ?**

*Par exemple : ajuster les paramètres de la machine virtuelle Java, les pools de connexion d'une base de données, ou les limites mémoire d'un serveur.*

<!-- criteres:5.7 -->
<!-- potentiel:1.0 -->

- [ ] ✅ Point fort confirmé  <!-- opt:0 -->
- [ ] 💡 Potentiel d'amélioration identifié  <!-- opt:1 -->
- [ ] 🚫 Non applicable  <!-- opt:2 -->
- [ ] 🤔 À évaluer  <!-- opt:3 -->
- [ ] ⌛️ Évaluation en cours  <!-- opt:4 -->
- [ ] Je ne sais pas  <!-- opt:jnsp -->
