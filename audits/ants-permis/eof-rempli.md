# EOF — Référentiel rempli automatiquement (partiel)

> Généré par `run_eof.py`, depuis les données d'audit disponibles. **La grande majorité des critères ne peut pas être déduite automatiquement** (questions organisationnelles/produit) : ils restent "je ne sais pas", à compléter humainement dans le template vierge du skill `eof`.

## 🏦 0 — Diagnostic rapide (aperçu, jamais rempli automatiquement — SAUF 0.16, doublon exact de 3.3, cf. `eof-analyse-minimisation-questions.md`)

- **0.1** — La disparition du service numérique aurait-elle un impact important ? _(niveau d'impact : Déterminant)_
- **0.2** — Y a-t-il des fonctionnalités redondantes ou des applications en double dans le système ? _(niveau d'impact : Déterminant)_
- **0.3** — Les composants principaux sont-ils soumis à des contraintes de haute disponibilité ? _(niveau d'impact : Déterminant)_
- **0.4** — Dépendances : combien de liens techniques vers d'autres systèmes sont en place ? _(niveau d'impact : Déterminant)_ — donnée indicative : 7 domaine(s) tiers détecté(s) lors de la capture (liste observée depuis l'extérieur, ne dit rien de l'architecture technique complète) : cake.cdn.s.woopic.com, captcha.liveidentity.com, fonts.googleapis.com, genii-api.tolk.ai, genii-script.tolk.ai, predemande-permisdeconduire.ants.gouv.fr, storage.googleapis.com
- **0.5** — Le code source du projet est-il entièrement ou partiellement accessible à l'équipe ? _(niveau d'impact : Déterminant)_
- **0.6** — Les compétences nécessaires pour mettre à jour le service sont-elles disponibles ? _(niveau d'impact : Déterminant)_
- **0.7** — La complexité de  l'architecture est-elle élevée ? _(niveau d'impact : Déterminant)_
- **0.8** — L'infrastructure (nombre et taille des composants tels que les machines virtuelles et les conteneurs) est-elle très importante ? _(niveau d'impact : Déterminant)_
- **0.9** — Un volume important de données est-il stocké ? _(niveau d'impact : Déterminant)_
- **0.10** — La complexité fonctionnelle est-elle élevée ? _(niveau d'impact : Déterminant)_
- **0.11** — « Les parcours utilisateurs sont-ils fluides, intuitifs et exempts de frictions UX/UI susceptibles d'être améliorées ? » _(niveau d'impact : Déterminant)_ — donnée indicative : Pire page toutes stratégies confondues (Core Web Vitals terrain/lab) : https://moncompte.ants.gouv.fr/connexion?lang=fr (mobile) : LCP 2.737s, INP 127.0ms, CLS 0.18, catégorie CrUX 'AVERAGE'. Ce sont des scores techniques de chargement, réactivité et stabilité visuelle, pas une mesure directe du ressenti utilisateur.
- **0.12** — Le produit est-il compatible avec le matériel le plus ancien de la flotte cible et offre-t-il une expérience fluide sur celui-ci ? _(niveau d'impact : Déterminant)_ — donnée indicative : Pire page en stratégie mobile (proxy matériel bas de gamme/ancien) : https://moncompte.ants.gouv.fr/connexion?lang=fr (mobile) : LCP 2.737s, INP 127.0ms, CLS 0.18, catégorie CrUX 'AVERAGE'. Le CrUX mobile terrain mélange tous types d'appareils, ce n'est pas une mesure isolée sur du matériel ancien spécifiquement.
- **0.13** — Le backlog produit contient-il des problèmes de performance et des améliorations ? _(niveau d'impact : Déterminant)_
- **0.14** — Les principales fonctionnalités sont-elles optimisées et efficaces ? _(niveau d'impact : Déterminant)_
- **0.15** — Existe-t-il une politique relative à la suppression et à l'archivage des données ? _(niveau d'impact : Déterminant)_
- **0.16** — Le service est-il hébergé dans un pays dont le mix électrique a un impact significatif ? (en fonction de l'emplacement) → **5- < 100 gCO2e / kWh** _(automatique, provenance collecte — env-data.json: servers[].carbon_intensity_g_kwh = 56 gCO2e/kWh (doublon de 3.3, même donnée))_


## 🛖 1 — Produit — potentiel d'optimisation : 4% (4/16 répondus)

### 1.1 — Existe-t-il un moyen simple pour réaliser cette action ?

**Réponse** : je ne sais pas (aucune donnée d'audit disponible — critère organisationnel/produit)

### 1.2 — Les utilisateurs cibles, avec leurs besoins professionnels, leurs appareils types et leurs attentes en matière d'ergonomie, sont-ils bien connus ?

**Réponse** : je ne sais pas (aucune donnée d'audit disponible — critère organisationnel/produit)

### 1.3 — Les mises à jour des nouvelles fonctionnalités sont-elles obligatoires pour tous les appareils, quel que soit leur système d'exploitation ou leur navigateur ?

**Réponse** : je ne sais pas (aucune donnée d'audit disponible — critère organisationnel/produit)

### 1.4 — La conception comprend-elle des composants personnalisés plutôt que des composants natifs ?

**Réponse** : je ne sais pas (aucune donnée d'audit disponible — critère organisationnel/produit)

### 1.5 — Y a-t-il des animations, des vidéos, des sons, des cartes (...) qui sont lus automatiquement ?

**Réponse (automatique)** : ✅ Point fort confirmé
**Provenance** : collecte — **Source** : html-css-criteria.json: aucune balise <video|audio autoplay> détectée sur les pages auditées

### 1.6 — Est-il possible d'adapter les ressources utilisées par l'application à la configuration matérielle de l'utilisateur ?

**Réponse (automatique)** : 💡 Potentiel d'amélioration identifié
**Provenance** : estime — **Source** : html-css-criteria.json: adaptive_img_ratio par page = [] ; media_query_count = 0

### 1.7 — Toutes les fonctionnalités sont-elles utiles, utilisables et utilisées ?

**Réponse** : je ne sais pas (aucune donnée d'audit disponible — critère organisationnel/produit)

### 1.8 — Le support des applications est-il médiocre sur les appareils les plus anciens ciblés ?

**Réponse** : je ne sais pas (aucune donnée d'audit disponible — critère organisationnel/produit)

### 1.9 — Faut-il un réseau à haut débit pour utiliser l'application ?

**Réponse** : je ne sais pas (aucune règle assez fiable pour trancher)
**Donnée indicative** (suppose) : Données réellement transférées (page la plus lourde) : 2628 Ko — _champ : env-data.json: har_summary.efootprint.data_transferred_bytes_real (poids réel transféré)_

### 1.10 — Le produit utilise-t-il des designs manupulateurs (UX dark patterns) qui augmentent l'utilisation des ressources ?

**Réponse** : je ne sais pas (aucune donnée d'audit disponible — critère organisationnel/produit)

### 1.11 — Est-il possible de modifier les valeurs par défaut (nombre d'éléments affichés, qualité, fréquence de rafraîchissement, etc.) afin de réduire l'utilisation des ressources ?

**Réponse** : je ne sais pas (aucune règle assez fiable pour trancher)
**Donnée indicative** (suppose) : Aucune règle @media (prefers-reduced-motion ou prefers-color-scheme) détectée dans les feuilles de style — _champ : html-css-criteria.json: css.has_prefers_reduced_or_scheme_

### 1.12 — Y a-t-il beaucoup de pisteurs (trackers) sur le produit ?

**Réponse (automatique)** : ✅ Point fort confirmé
**Provenance** : estime — **Source** : security-headers-analysis.json + har-analysis.json: aucun pistage ni analytics détecté

### 1.13 — Les principaux parcours utilisateurs sont-ils optimisés pour être fluides et efficaces ?

**Réponse (automatique)** : ✅ Point fort confirmé
**Provenance** : collecte — **Source** : cwv.json: accessibility_score_pct (PageSpeed Insights) — pire page/stratégie = 91, valeurs = [91, 93, 100]

### 1.14 — Les écrans principaux sont-ils clairs et bien conçus ?

**Réponse** : je ne sais pas (aucune règle assez fiable pour trancher)
**Donnée indicative** (suppose) : Page la plus lourde : https://moncompte.ants.gouv.fr/connexion?lang=fr (9380 Ko) ; la plus légère : https://moncompte.ants.gouv.fr/backend/api/procedure/start?procedureKey=driverLicence (2126 Ko) — _champ : env-data.json: pages[].size_kb (comparaison entre pages du même parcours)_

### 1.15 — Ce service est-il fréquemment utilisé ?

**Réponse** : je ne sais pas (aucune règle assez fiable pour trancher)
**Donnée indicative** (estime) : Trafic estimé : 30 066 000 visites/an (SimilarWeb (estimation)) — _champ : env-data.json: traffic.visits_per_year / traffic.monthly_visits (estimation SimilarWeb)_

### 1.16 — Volume (nombre d'utilisateurs)

**Réponse** : je ne sais pas (aucune règle assez fiable pour trancher)
**Donnée indicative** (estime) : Trafic estimé : 30 066 000 visites/an (SimilarWeb (estimation)) — _champ : env-data.json: traffic.visits_per_year_


## 🗺️ 2 — Architecture — potentiel d'optimisation : 0% (1/5 répondus)

### 2.1 — Le produit utilise-t-il des technologies gourmandes ?

**Réponse (automatique)** : ✅ Point fort confirmé
**Provenance** : estime — **Source** : env-data.json: ai_external_apis vide, aucune techno IA/blockchain détectée

### 2.2 — Il n'y a pas de stratégie de compatibilité.

**Réponse** : je ne sais pas (aucune donnée d'audit disponible — critère organisationnel/produit)

### 2.3 — Est-il possible d'optimiser la séparation et la communication entre les composants ?

**Réponse** : je ne sais pas (aucune donnée d'audit disponible — critère organisationnel/produit)

### 2.4 — Le pic de charge peut-il être lissé sur une échelle de temps ?

**Réponse** : je ne sais pas (aucune donnée d'audit disponible — critère organisationnel/produit)

### 2.5 — Y a-t-il des calculs ou des requêtes lourds dont les résultats peuvent être mis en cache ?

**Réponse** : je ne sais pas (aucune règle assez fiable pour trancher)
**Donnée indicative** (suppose) : https://storage.googleapis.com/genii-public/project-5e05e2c5-2a6c-401f-b529-77b6aeeb5435/css/%20//cdn.jsdelivr.net/npm/@gouvfr/dsfr@1.11/dist/fonts/Marianne-Light.woff2 chargé 6 fois ; https://storage.googleapis.com/genii-public/project-5e05e2c5-2a6c-401f-b529-77b6aeeb5435/css/%20//cdn.jsdelivr.net/npm/@gouvfr/dsfr@1.11/dist/fonts/Marianne-Regular.woff2 chargé 6 fois ; https://storage.googleapis.com/genii-public/project-5e05e2c5-2a6c-401f-b529-77b6aeeb5435/css/%20//cdn.jsdelivr.net/npm/@gouvfr/dsfr@1.11/dist/fonts/Marianne-Medium.woff2 chargé 6 fois — _champ : har-analysis.json: duplicate_urls (liste {url, count}) ; http_codes (part de 304)_


## 🏢 3 — Infrastructure — potentiel d'optimisation : 0% (1/8 répondus)

### 3.1 — La facture peut-elle être réduite ?

**Réponse** : je ne sais pas (aucune donnée d'audit disponible — critère organisationnel/produit)

### 3.2 — Il n'existe aucun système de suivi de l'impact environnemental.

**Réponse** : je ne sais pas (aucune donnée d'audit disponible — critère organisationnel/produit)

### 3.3 — Le service est-il hébergé dans une région où le mix électrique a un impact important ?

**Réponse (automatique)** : ✅ Point fort confirmé
**Provenance** : collecte — **Source** : env-data.json: servers[] = moncompte.ants.gouv.fr (FR, 56 gCO2/kWh); permisdeconduire.ants.gouv.fr (FR, 56 gCO2/kWh); predemande-permisdeconduire.ants.gouv.fr (FR, 56 gCO2/kWh) (sous le seuil 250 gCO2/kWh)

### 3.5 — L'infrastructure peut-elle être mutualisée ?

**Réponse** : je ne sais pas (aucune donnée d'audit disponible — critère organisationnel/produit)

### 3.6 — Les composants de déploiement (VM, serveur, conteneurs) sont-ils surdimensionnés ?

**Réponse** : je ne sais pas (aucune donnée d'audit disponible — critère organisationnel/produit)

### 3.7 — Des outils et des stratégies d'élasticité/d’auto-scaling peuvent-ils être déployés pour réduire la taille de l'infrastructure ?

**Réponse** : je ne sais pas (aucune donnée d'audit disponible — critère organisationnel/produit)

### 3.8 — Tous les environnements sont-ils toujours activés ?

**Réponse** : je ne sais pas (aucune donnée d'audit disponible — critère organisationnel/produit)

### 3.9 — Les environnements de test sont-ils aussi grands que ceux de production ?

**Réponse** : je ne sais pas (aucune donnée d'audit disponible — critère organisationnel/produit)


## 💾 4 — Stockage et données — potentiel d'optimisation : sans donnée (0/6 répondus)

### 4.1 — Des mécanismes de suppression et d'archivage sont-ils mis en place ?

**Réponse** : je ne sais pas (aucune donnée d'audit disponible — critère organisationnel/produit)

### 4.2 — Les meilleures pratiques en matière de bases de données sont-elles mises en place ?

**Réponse** : je ne sais pas (aucune donnée d'audit disponible — critère organisationnel/produit)

### 4.3 — Le produit utilise-t-il les technologies de base de données/stockage adaptées aux utilisations prévues ?

**Réponse** : je ne sais pas (aucune donnée d'audit disponible — critère organisationnel/produit)

### 4.4 — Les bases de données de test sont-elles aussi volumineuses que celles de production ?

**Réponse** : je ne sais pas (aucune donnée d'audit disponible — critère organisationnel/produit)

### 4.5 — Y a-t-il des doublons dans les données ?

**Réponse** : je ne sais pas (aucune donnée d'audit disponible — critère organisationnel/produit)

### 4.6 — Existe-t-il des données qui sont très rarement utilisées dans le service et qui pourraient être transférées vers un stockage à froid ?

**Réponse** : je ne sais pas (aucune donnée d'audit disponible — critère organisationnel/produit)


## 👨‍💻 5 — Algo & Code — potentiel d'optimisation : 0% (1/9 répondus)

### 5.1 — Existe-t-il des outils d'analyse statistique permettant de mettre en évidence des améliorations potentielles en matière d'efficacité  ?

**Réponse** : je ne sais pas (aucune donnée d'audit disponible — critère organisationnel/produit)

### 5.2 — Une campagne de tests de charge ou de résistance a-t-elle révélé des problèmes d'efficacité ?

**Réponse** : je ne sais pas (aucune donnée d'audit disponible — critère organisationnel/produit)

### 5.3 — L'équipe a-t-elle identifié des domaines à améliorer en termes de performance/efficacité et les a-t-elle ajoutés au backlog ?

**Réponse** : je ne sais pas (aucune donnée d'audit disponible — critère organisationnel/produit)

### 5.4 — Les indicateurs de performance sont-ils médiocres ?

**Réponse (automatique)** : 🤔 À évaluer
**Provenance** : collecte — **Source** : cwv.json: zone intermédiaire ('needs improvement'), aucune page 'poor'

### 5.5 — Les cas d'utilisation les plus critiques (parcours utilisateurs les plus fréquents) sont-ils optimisés ?

**Réponse** : je ne sais pas (aucune règle assez fiable pour trancher)
**Donnée indicative** (suppose) : https://predemande-permisdeconduire.ants.gouv.fr/ihm-spd/pages/premotifdemandeform.action : JavaScript inutilisé 76.55% ; https://moncompte.ants.gouv.fr/connexion?lang=fr : JavaScript inutilisé 62.55% — _champ : coverage-analysis.json (JS/CSS inutilisé par page) ; cwv.json (par page)_

### 5.6 — La pile technique (Java, JS, Python, PHP, etc.)est-elle pas à jour ?

**Réponse** : je ne sais pas (aucune donnée d'audit disponible — critère organisationnel/produit)

### 5.7 — Les composants peuvent-ils être réglés pour améliorer l'efficacité ?

**Réponse** : je ne sais pas (aucune donnée d'audit disponible — critère organisationnel/produit)

### 5.8 — Les dépendances du projet sont-elles à jour ?

**Réponse** : je ne sais pas (aucune donnée d'audit disponible — critère organisationnel/produit)

### 5.9 — Des problèmes de compatibilité ont-ils été identifiés pour les appareils ciblés ?

**Réponse** : je ne sais pas (aucune donnée d'audit disponible — critère organisationnel/produit)


## 🛠 6 — Facilité de changement — potentiel d'optimisation : sans donnée (0/10 répondus)

### 6.1 — Existe-t-il un dispositif d'observabilité efficace pour le produit ?

**Réponse** : je ne sais pas (aucune règle assez fiable pour trancher)
**Donnée indicative** (suppose) : Score en-têtes de sécurité HTTP : 90% (grade A) sur https://moncompte.ants.gouv.fr/connexion?lang=fr - indicateur parmi d'autres de la maturité en production — _champ : security-headers-analysis.json: worst_page.grade (score sécurité local, proxy de maturité prod)_

### 6.2 — Existe-t-il des revues de code et/ou une programmation en binôme  ( pair programming)?

**Réponse** : je ne sais pas (aucune donnée d'audit disponible — critère organisationnel/produit)

### 6.3 — Existe-t-il un processus CI/CD efficace ?

**Réponse** : je ne sais pas (aucune règle assez fiable pour trancher)
**Donnée indicative** (suppose) : ressource de votre site la plus récente : 23.4 jour(s) avant la capture (publiée à 13:33 UTC) ; dispersion des publications de code : 21.1 jour(s) (mises en ligne échelonnées) — _champ : *.har: en-têtes Last-Modified des ressources 1st-party (code HTML/CSS/JS)_

### 6.4 — Existe-t-il des tests de non-régression (tests unitaires, tests d'intégration, tests de bout en bout) ?

**Réponse** : je ne sais pas (aucune donnée d'audit disponible — critère organisationnel/produit)

### 6.5 — Y a-t-il un fort découplage entre le domaine métier et l'intégration technique ?

**Réponse** : je ne sais pas (aucune donnée d'audit disponible — critère organisationnel/produit)

### 6.6 — Existe-t-il des indicateurs permettant de suivre la qualité des logiciels ?

**Réponse** : je ne sais pas (aucune règle assez fiable pour trancher)
**Donnée indicative** (suppose) : Audit Lighthouse - Bonnes Pratiques (pire page) : 73% ; en-têtes de sécurité (pire page) : grade A ; fichier security.txt : absent — _champ : cwv.json: best_practices_score_pct ; security-headers-analysis.json: worst_page.grade ; wellknown-scan.json: security_txt.present_

### 6.7 — Existe-t-il une documentation complète ?

**Réponse** : je ne sais pas (aucune donnée d'audit disponible — critère organisationnel/produit)

### 6.8 — Y a-t-il du code dupliqué dans l'application ?

**Réponse** : je ne sais pas (aucune règle assez fiable pour trancher)
**Donnée indicative** (suppose) : Aucune duplication de code JavaScript détectée par l'audit Lighthouse (score parfait). Cela ne prouve pas que votre gestion des dépendances soit optimale, seulement qu'aucune duplication évidente n'a été repérée. — _champ : cwv.json: lighthouse_insights['duplicated-javascript'] (audit Lighthouse)_

### 6.9 — L'équipe dispose-t-elle d'une autonomie suffisante pour déployer les outils dont elle a besoin pour observer, mesurer ou optimiser le système ?

**Réponse** : je ne sais pas (aucune donnée d'audit disponible — critère organisationnel/produit)

### 6.10 — Les composants principaux sont-ils soumis à des contraintes de haute disponibilité ?

**Réponse** : je ne sais pas (aucune donnée d'audit disponible — critère organisationnel/produit)
