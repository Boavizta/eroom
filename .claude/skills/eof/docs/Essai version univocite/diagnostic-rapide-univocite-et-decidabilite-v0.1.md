# EROOM — Diagnostic rapide, version univoque

> **Livrable principal : `EROOM-diagnostic-rapide-univoque-v0.1.xlsx`** (même dossier) — le
> questionnaire au format EOF, prêt à remplir : 16 critères, liste déroulante 1–5 +
> « Je ne sais pas », synthèse calculée, arbitrages. Le présent document est son compagnon :
> il explique chaque choix, chiffre les défauts corrigés et liste ce qui reste ouvert.
>
> Format EOF étendu : `CRITÈRE` · `✏️ ÉVALUATION` · `MÉTHODES D'ÉVALUATION` ·
> `EXPLICATION SUPPLÉMENTAIRE` · `NIVEAU D'IMPACT` · `RECOMMANDATION (RAPPORT)` — plus une
> septième colonne à venir, `CAS LIMITE` (voir « Les sept colonnes »).
>
> Périmètre : **diagnostic rapide, 16 critères, 6 piliers.** Le diagnostic avancé
> (54 critères) n'est pas traité ici.
>
> Sources : le template EOF V1.1 du repo
> (`docs/EOF-V.1.1 …/🏦 0-Diagnostic rapide.html`) comme référence du framework, et
> `src/data/questionnaire-qd.json` v1.2 comme état de l'application.
> ⚠️ Les deux fichiers compagnons `docs/diagnostic-rapide.csv` et
> `docs/questions-diagnostic-comparaison.md` **inversent l'orientation de `Produit 1`
> version v1.1** : ils placent « Impact critique » au cran 1 là où le template EOF le place
> au cran 5. Ne pas s'en servir comme source d'orientation tant qu'ils ne sont pas corrigés
> (US 2.22). Ce document a été établi contre le template.
>
> Ce document est une **proposition** — aucun fichier de données n'a été modifié.

---

## L'axe de l'échelle

> **1 = fort potentiel d'optimisation · 5 = rien à gagner sur ce point**

Le diagnostic rapide est une grille de **qualification** : il identifie les services qui
présentent le plus grand potentiel d'optimisation — c'est la formulation du template EOF
lui-même. Un score bas n'est pas une mauvaise note, c'est un signal de priorité.

Vérifié critère par critère contre le template : **les 16 critères de l'application
respectent cet axe.** Un service critique obtient 5 (son empreinte est une contrainte
assumée) ; un service dont personne ne remarquerait la disparition obtient 1 (candidat à la
suppression).

Le défaut n'est pas une violation de l'axe — c'est qu'il n'est déclaré **ni dans la donnée,
ni dans les types, ni dans l'interface** de l'application. Il vit dans l'intention du
template et dans un commentaire de `computeResults.ts:77` (« 1=mauvais, 5=optimal »). Rien
n'empêche mécaniquement d'ajouter un critère à l'envers, et rien ne l'attraperait (US 2.26).

## Les sept colonnes

| Colonne | Ce qu'elle porte | Existe aujourd'hui ? | À la charge de |
|---|---|---|---|
| **CRITÈRE** | L'énoncé, en question de degré | oui (`text`) | questionnaire |
| **✏️ ÉVALUATION** | Les cinq crans, tous nommés | EOF : oui · app : crans 1/3/5 seulement | questionnaire |
| **CAS LIMITE** | Une situation concrète placée entre deux crans voisins, qui force la règle à être explicite | **non — à écrire (US 2.28)** | questionnaire |
| **EXPLICATION SUPPLÉMENTAIRE** | Pourquoi ce critère est dans EROOM : le mécanisme d'impact environnemental | oui (`hint`) | questionnaire |
| **NIVEAU D'IMPACT** | Déterminant · Significatif · Modéré | EOF : « Déterminant » ×16, donc muet · app : non | questionnaire |
| **RECOMMANDATION (RAPPORT)** | Ce qui sort dans le plan d'action quand le score est bas | oui (`action` ; `Infrastructure 2` via code) | questionnaire |
| **MÉTHODES D'ÉVALUATION** | La règle de décision : ce qu'on compte, où on regarde, ce qui départage deux crans voisins | **non** | **agent** |

### Le partage entre les deux colonnes décisives

`MÉTHODES D'ÉVALUATION` est la colonne qui lève l'équivoque — c'est elle qui fait qu'une même
situation donne le même cran, quelle que soit la personne ou la machine qui répond. **Elle
relève de l'agent**, parce qu'elle dépend de la source d'évidence disponible et du seuil
retenu.

`CAS LIMITE` est son pendant côté questionnaire : une situation concrète, placée volontairement
entre deux crans, qui **oblige la règle à se déclarer**. Le questionnaire pose le cas, l'agent
écrit la règle qui le tranche. Un cas limite qu'aucune règle ne tranche est une équivoque
prouvée, pas soupçonnée. Les 16 cas restent à écrire — c'est l'US 2.28, et c'est la
prochaine étape de ce chantier.

> Le contenu de la colonne `MÉTHODES D'ÉVALUATION` dans les tableaux ci-dessous est une
> **amorce**, proposée pour que les futures fiches aient un point de départ à contester.
> Elle n'a pas vocation à être la version retenue.

## Les quatre règles appliquées ici

1. **Un critère est une question de degré**, jamais une question fermée ni une alternative.
   « Ce service stocke-t-il beaucoup de données ? » appelle oui ou non ; on ne peut pas y
   répondre sur cinq crans sans une conversion mentale que personne n'a écrite. → « Quel volume
   de données ce service stocke-t-il ? » **14 critères sur 16** sont dans ce cas : 11
   questions fermées et 3 alternatives (« X, ou Y ? »). Seuls `Architecture 2` et
   `Infrastructure 2` sont bien formés. Défaut hérité de l'EOF, dont les énoncés sont
   également fermés.
2. **Un critère porte une seule dimension.** Pas de « rapide *et* sans surcharger ».
   **3 critères** en cumulent plusieurs : `Produit 3` (temps de réponse + charge machine),
   `Algo 2` (étapes superflues + allers-retours + rechargements), `Stockage 2` (effacement +
   archivage).
3. **Les cinq crans sont nommés.** Le template EOF nomme les cinq crans des 16 critères ;
   la v1.2 de l'application n'en a conservé que trois (1, 3, 5), et n'en **affiche que
   deux** — le champ `midLabel` existe dans la donnée et n'est lu par aucun composant
   (`ScaleInput.tsx` ne rend que `lowLabel` et `highLabel`). Les crans 2 et 4 proposés
   ci-dessous s'appuient sur les libellés EOF, adaptés au langage d'usage de la v1.2 ; leur
   réconciliation fine avec le template fait partie de l'US 2.27.
4. **« Je ne sais pas » est une réponse à part, exclue du score — et une seule.**
   L'application le fait déjà : le questionnaire rapide a un bouton dédié
   (`DontKnowButton`, réponse `null`, exclue du score, comptée dans le taux de confiance).
   Le défaut est le **double chemin concurrent** : dix libellés de cran 1 disent encore
   « (ou inconnu) ». La personne qui suit le libellé obtient la pire note ; celle qui
   utilise le bouton est exclue du score. Deux personnes ignorantes de la même chose,
   deux résultats différents. Ce défaut vient de l'EOF lui-même, dont cinq critères
   embarquent « Je ne sais pas » dans le libellé du cran 1 — point à remonter (E2-9).

## Colonne NIVEAU D'IMPACT

Le template EOF du diagnostic rapide **porte** la colonne — remplie « Déterminant » sur les
16 lignes, ce qui la rend muette : elle ne différencie rien.

Les valeurs proposées ci-dessous sont **dérivées** du champ `co2Weight` de la donnée
applicative : `5 ou 4 → Déterminant` · `3 → Significatif` · `2 ou 1 → Modéré`. C'est une
proposition de différenciation, pas une donnée EROOM.

⚠️ **Cette dérivation est discutable et doit être validée.** `co2Weight` note le gain
qu'apporte le **traitement** du critère ; `NIVEAU D'IMPACT` note l'importance du critère
lui-même. Les deux coïncident souvent, pas toujours : `Facilité de changement 1` (accès au
code) porte `co2Weight: 1`, donc « Modéré » par dérivation, alors que sans accès au code
aucune optimisation n'est possible. C'est un prérequis, pas un critère modéré.

## Portée des critères — un écart de comparabilité

`Algo 2` et `Algo 3` ne sont posés qu'aux services `fullstack` et `frontend`. Pour un service
`backend`, le pilier Algorithme & Code ne compte qu'**un seul critère** au lieu de trois.

Or le score d'un pilier est la moyenne de ses critères visibles **ayant reçu une réponse
numérique**. Un pilier noté sur un critère et un pilier noté sur trois ne portent pas la même
information, et rien ne le signale dans le rapport. Défaut de congruence du résultat, pas de
l'énoncé (US 2.30).

---

## Pilier 1 — Produit

| CRITÈRE | ✏️ ÉVALUATION | MÉTHODES D'ÉVALUATION | EXPLICATION SUPPLÉMENTAIRE | NIVEAU D'IMPACT | RECOMMANDATION (RAPPORT) |
|---|---|---|---|---|---|
| **1.1** — Quel serait l'impact sur les utilisateurs si ce service disparaissait demain ? | **1** Personne ne le remarquerait<br>**2** Quelques utilisateurs gênés — alternatives immédiates<br>**3** Impact modéré — des alternatives existent, mais coûtent du temps<br>**4** Forte gêne sur les activités principales<br>**5** Blocage immédiat — les équipes ne peuvent plus travailler | Se placer du point de vue des utilisateurs finaux, pas de l'équipe qui exploite le service. Évaluer la situation 24 h après la disparition. Retenir 1 si le service peut être coupé sans que personne ne le signale ; 5 si aucune alternative n'existe et que l'activité s'arrête. Source : responsable produit ou métier. | Un service dont l'absence passerait inaperçue est un candidat direct à la suppression ou à la mutualisation — l'un des gains les plus faciles. À l'inverse, un service critique est justifié : son empreinte est une contrainte assumée, pas un gaspillage. | Modéré | Évaluer si ce service peut être simplifié en périmètre, mutualisé ou supprimé. |
| **1.2** — Dans quelle mesure les fonctionnalités de ce service sont-elles déjà couvertes ailleurs dans l'organisation ? | **1** Totalement dupliqué — plusieurs outils font exactement la même chose<br>**2** Large recouvrement — la majorité des fonctions existent ailleurs<br>**3** Quelques similitudes, sans recouvrement fonctionnel réel<br>**4** Recouvrement limité à une fonction secondaire<br>**5** Totalement unique dans l'organisation | Comparer aux applications du même périmètre métier, pas à l'ensemble du SI. Compter le recouvrement en **fonctionnalités principales**, pas en écrans. Retenir 1 si un autre outil pourrait remplacer celui-ci sans perte fonctionnelle. Source : cartographie applicative ou urbaniste SI. | Chaque doublon multiplie les ressources consommées : serveurs, données, énergie. Les redondances fonctionnelles sont souvent les premiers gains à faible risque. | Modéré | Identifier et éliminer les fonctionnalités dupliquées avec d'autres services de l'organisation. |
| **1.3** — Comment se comportent les fonctions principales de ce service en temps de réponse ? | **1** Lentes et visiblement défaillantes, sans raison identifiée<br>**2** Lenteurs fréquentes, aucune action engagée<br>**3** Fonctionnel, mais des améliorations évidentes restent à faire<br>**4** Correct — des optimisations ponctuelles ont déjà été faites<br>**5** Efficace et régulièrement passé en revue | **Temps de réponse uniquement.** Cumuler temps et charge machine force à noter d'un chiffre unique deux constats qui divergent souvent : un service rapide parce que surdimensionné. Mesure : Lighthouse / Core Web Vitals côté affichage, temps de réponse d'API côté serveur. Le cran 5 exige une **revue régulière documentée**, pas une absence de plainte. ⚠️ Cette découpe perd une information : l'efficacité par requête n'est plus captée nulle part — arbitrage n° 1. | Un code inefficace peut consommer 2 à 10× plus de CPU qu'un code bien écrit pour le même résultat. L'efficacité fonctionnelle est le levier d'impact le plus direct. | Significatif | Auditer et optimiser les fonctions lentes ou sous-performantes du service. |

**Note sur `Produit 1`.** Contrôlé contre le template EOF : l'orientation de l'application est
**conforme** (EOF : « 1 - Impact nul ou négligeable » → « 5 - Impact critique »). Les fichiers
`docs/diagnostic-rapide.csv` et `docs/questions-diagnostic-comparaison.md` documentent la
v1.1 à l'envers et sont à corriger (US 2.22) — toute relecture qui s'appuierait sur eux
conclurait à tort que ce critère a été retourné.

---

## Pilier 2 — Architecture

| CRITÈRE | ✏️ ÉVALUATION | MÉTHODES D'ÉVALUATION | EXPLICATION SUPPLÉMENTAIRE | NIVEAU D'IMPACT | RECOMMANDATION (RAPPORT) |
|---|---|---|---|---|---|
| **2.1** — Quel niveau de disponibilité ce service doit-il tenir ? | **1** Disponibilité permanente mondiale — la moindre coupure a des conséquences graves<br>**2** Haute disponibilité 24/7 exigée<br>**3** Des engagements de disponibilité existent, sans exigence permanente<br>**4** Disponibilité attendue en heures ouvrées seulement<br>**5** Peut s'arrêter sans conséquence — aucune contrainte | Retenir la disponibilité **exigée**, pas celle constatée. Un service qui tourne en 99,99 % sans que personne ne l'exige se note sur l'exigence. Source : contrat de service, engagement écrit ; à défaut, le niveau que l'équipe déclare tenir, en le signalant. ⚠️ Même question que `ease-advanced-10` du diagnostic avancé — arbitrage n° 6. | Les SLA élevés (99,99 %) exigent une redondance matérielle permanente, souvent sous-utilisée. Chaque « 9 » supplémentaire a un coût carbone quasi exponentiel. | Significatif | Réviser les exigences de disponibilité et supprimer la redondance matérielle non justifiée. |
| **2.2** — Combien d'autres systèmes ou services doivent fonctionner pour que celui-ci marche correctement ? | **1** Interconnecté avec la quasi-totalité de l'organisation (accès, identité…)<br>**2** Nombreuses dépendances, dont plusieurs critiques<br>**3** Connecté à plusieurs systèmes, avec des dépendances importantes<br>**4** Une ou deux dépendances, non critiques<br>**5** Aucune connexion — fonctionne seul | Compter les dépendances **dont l'indisponibilité dégrade le service**, pas tous les appels réseau. Inclure l'authentification et les bases partagées. Une dépendance est critique si son arrêt rend le service inutilisable. Source : schéma d'architecture ou entretien avec l'équipe. | Un système fortement couplé est difficile à optimiser en isolation. Chaque dépendance ajoute des appels réseau, de la latence et une consommation induite difficilement contrôlable. | Modéré | Réduire le nombre de dépendances inter-services et limiter les appels réseau inutiles. |
| **2.3** — Quel effort faut-il à une personne nouvelle pour comprendre l'architecture de ce service ? | **1** Très complexe — même les créateurs peinent à l'expliquer<br>**2** Plusieurs semaines d'accompagnement nécessaires<br>**3** Environ une semaine d'accompagnement<br>**4** Un ou deux jours de prise en main suffisent<br>**5** Très simple — explicable en quelques minutes | Critère formulé en **effort de prise en main** plutôt qu'en jugement sur la complexité : c'est un fait observable dans l'équipe, pas une opinion. Prendre le délai réel constaté sur la dernière arrivée, si elle existe. Source : équipe de développement. | Les architectures complexes consomment plus de ressources pour fonctionner et coûtent plus à maintenir. La simplicité est le meilleur allié de l'écoconception. | Modéré | Simplifier l'architecture — découper en modules indépendants et documenter les flux. |

---

## Pilier 3 — Infrastructure

| CRITÈRE | ✏️ ÉVALUATION | MÉTHODES D'ÉVALUATION | EXPLICATION SUPPLÉMENTAIRE | NIVEAU D'IMPACT | RECOMMANDATION (RAPPORT) |
|---|---|---|---|---|---|
| **3.1** — Quelle est l'empreinte matérielle de ce service — serveurs, conteneurs, puissance de calcul ? | **1** Parmi les plus gourmandes de l'organisation<br>**2** Nettement au-dessus de la moyenne<br>**3** Dans la moyenne de l'organisation<br>**4** Légère — en dessous de la moyenne<br>**5** Très légère — quelques serveurs ou un petit service cloud | Compter **tous les environnements**, production et hors production. Échelle **relative à l'organisation** : le même dimensionnement se note différemment selon le contexte — les scores ne sont donc pas comparables d'une organisation à l'autre (arbitrage n° 3). Source : inventaire d'infrastructure ou facture cloud. | Les machines surdimensionnées tournent souvent à 10–15 % de charge. Réduire la taille de l'infrastructure est l'un des leviers d'impact carbone les plus immédiats. | Déterminant | Rightsizer l'infrastructure à la charge réelle — supprimer ou réduire les ressources surdimensionnées. |
| **3.2** — Dans quel pays ou quelle région ce service est-il hébergé ? ⚠️ | *Saisie libre : pays ou région cloud.*<br>Score dérivé de l'intensité carbone, table **implémentée** (`electricityMap.ts`) :<br>**1** > 500 gCO₂e/kWh<br>**2** 300 – 500<br>**3** 150 – 300<br>**4** 50 – 150<br>**5** ≤ 50 gCO₂e/kWh | Retenir la région d'hébergement de la **production**. Si le service est multi-région, retenir la plus carbonée. Conversion région → intensité carbone par `src/lib/electricityMap.ts`. ⚠️ Ces seuils divergent de l'EOF V1.1 — encadré ci-dessous. | L'intensité carbone de l'électricité varie de 1 à 10 selon le pays. Héberger en Europe du Nord plutôt qu'en Asie du Sud-Est peut diviser l'empreinte carbone par 5 à coût quasi identique. | Déterminant | Migrer l'hébergement vers une zone à électricité moins carbonée (la zone détectée et son intensité sont citées dans le texte généré). |
| **3.3** — Où en êtes-vous du traitement des problèmes de lenteur ou de consommation identifiés sur ce service ? | **1** Sujet récurrent dans l'équipe, jamais traité<br>**2** Problèmes identifiés, aucun n'est entré au backlog<br>**3** Quelques améliorations identifiées et backloguées<br>**4** Traitement engagé, corrections en cours<br>**5** Aucun problème connu | Le critère porte sur le **traitement**, pas sur l'existence de problèmes. Une équipe qui connaît ses problèmes et les traite se note mieux qu'une équipe qui n'en voit aucun faute de mesure — si aucune mesure de performance n'existe, le signaler avec la réponse. Source : backlog produit. | Les tickets de performance ignorés représentent du gaspillage de ressources documenté et quantifiable. Chaque ticket en attente est un surcoût énergétique continu. | Déterminant | Traiter les tickets de performance et de gaspillage identifiés — chaque ticket en attente coûte de l'énergie. |

**`Infrastructure 2` — dans le plan d'action, absent du score.** Sa réponse est un texte
libre, et `computeResults.ts` ne calcule les scores de pilier que sur les réponses
numériques. Ce critère n'entre donc **ni dans le score du pilier, ni dans le score global**
— alors qu'il porte `co2Weight: 5`, la pondération la plus forte du questionnaire. Il n'est
pas absent partout : `computeResults.ts:79` convertit la zone en score 1–5 et injecte une
recommandation dans le plan d'action. **Seul critère traité par un chemin de code dédié
plutôt que par la donnée** — invisible à qui lit le questionnaire sans lire le code.
Arbitrage n° 2.

**Divergence de seuils entre le framework et son implémentation.** Le template EOF V1.1
pose cinq bornes : `1 > 750` · `2 < 500` · `3 < 300` · `4 < 200` · `5 < 100` gCO₂e/kWh —
avec un **trou entre 500 et 750** : une région à 600 gCO₂e/kWh ne tombe dans aucune bande.
`electricityMap.ts` applique `500 / 300 / 150 / 50`, continu mais différent partout. Aucune
trace de la décision. À remonter (E2-9) et à trancher (arbitrage n° 2).

---

## Pilier 4 — Stockage & Données

*(nommé « Storage & Data » dans l'application — arbitrage n° 5.)*

| CRITÈRE | ✏️ ÉVALUATION | MÉTHODES D'ÉVALUATION | EXPLICATION SUPPLÉMENTAIRE | NIVEAU D'IMPACT | RECOMMANDATION (RAPPORT) |
|---|---|---|---|---|---|
| **4.1** — Quel volume de données ce service stocke-t-il ? | **1** Massif — plusieurs téraoctets<br>**2** Important — centaines de gigaoctets<br>**3** Dans la moyenne de l'organisation<br>**4** Modeste — quelques gigaoctets<br>**5** Très peu — quelques mégaoctets | Compter le volume **utile**, hors réplication et hors sauvegardes, et le préciser si la mesure disponible les inclut. Additionner tous les environnements. Source : console de base de données ou facture de stockage. ⚠️ L'échelle mélange des repères absolus et un repère relatif au cran 3, et laisse des trous entre les ordres de grandeur (où tombent 40 Go ?) — arbitrage n° 3, et premier candidat aux cas limites (US 2.28). | Stocker des données a un coût énergétique permanent. 1 To représente environ 20 kWh/an, souvent multiplié par 3 pour la redondance — avant même de compter les sauvegardes. | Déterminant | Auditer le volume de données stockées et purger ce qui ne sert plus. |
| **4.2** — Quel est le niveau d'automatisation du cycle de vie des données de ce service ? | **1** Aucune règle — les données s'accumulent indéfiniment<br>**2** Règles envisagées, jamais écrites<br>**3** Des règles existent, rarement suivies<br>**4** Règles appliquées, partiellement automatisées<br>**5** Cycle de vie strict, entièrement automatisé et contrôlé | Le critère couvre **purge et archivage ensemble**, sous l'angle de l'automatisation — l'énoncé actuel demande « efface **ou** archive », ce à quoi une équipe qui archive sans jamais purger ne peut pas répondre. Retenir 4 si les règles tournent mais nécessitent une intervention ; 5 si elles tournent seules et sont contrôlées. Source : politique de rétention, tâches planifiées. | Sans politique d'archivage, les données s'accumulent indéfiniment. L'automatisation du cycle de vie est l'un des gains les plus durables et les moins risqués. | Significatif | Mettre en place une politique de cycle de vie des données avec archivage et purge automatiques. |

---

## Pilier 5 — Algorithme & Code

*(nommé « Algo & Code » dans l'application **et** dans le diagnostic avancé — arbitrage n° 5.)*

| CRITÈRE | ✏️ ÉVALUATION | MÉTHODES D'ÉVALUATION | EXPLICATION SUPPLÉMENTAIRE | NIVEAU D'IMPACT | RECOMMANDATION (RAPPORT) |
|---|---|---|---|---|---|
| **5.1** — Quelle est l'intensité des traitements que ce service effectue ? | **1** Très lourds — calculs intensifs sur de grandes masses de données<br>**2** Traitements lourds réguliers<br>**3** Quelques traitements significatifs<br>**4** Traitements légers, ponctuels<br>**5** Minimaux — affichage ou transmission seulement | Porte sur les **traitements métier** : calculs, agrégations, transformations, entraînements. Un service qui ne fait que lire et afficher se note 5, même s'il sert un fort trafic — le volume matériel est traité en 3.1. « Lourd » vs « significatif » reste à borner par cas limite (US 2.28). Source : équipe de développement, profil CPU si disponible. | Un algorithme en O(n²) peut consommer 100× plus de CPU qu'un O(n log n) sur des données réelles. La complexité algorithmique a un impact direct et mesurable sur la consommation. | Déterminant | Réviser les algorithmes coûteux et réduire la complexité computationnelle des traitements. |
| **5.2** — Quel est le niveau de friction des parcours utilisateurs principaux ? *(fullstack, frontend)* | **1** Les utilisateurs se perdent ou se plaignent — problèmes connus, non corrigés<br>**2** Frictions fréquentes, jamais mesurées<br>**3** Fonctionnel, quelques irritants connus<br>**4** Parcours revus — irritants résiduels mineurs<br>**5** Testé avec les utilisateurs — fluide et cohérent | Se limiter aux **parcours principaux**, ceux qui portent l'essentiel des usages. Indices mesurables : nombre d'étapes, allers-retours, rechargements de page par tâche accomplie. Le cran 5 exige un **test utilisateur réalisé**, pas une conviction interne. | Les frictions UX génèrent des requêtes inutiles, des rechargements de pages et des sessions prolongées par frustration. Une UX fluide réduit le nombre d'interactions, donc la consommation. | Modéré | Améliorer l'UX pour éliminer les rechargements inutiles et les parcours en erreur. |
| **5.3** — Quel est le niveau de confort d'usage sur les appareils les plus anciens de vos utilisateurs ? *(fullstack, frontend)* | **1** Incompatible — les utilisateurs ne peuvent pas s'en servir<br>**2** Utilisable au prix d'attentes très longues<br>**3** Utilisable, mais les tâches simples prennent plusieurs secondes<br>**4** Correct — ralentissements ponctuels<br>**5** Rapide et confortable, même sur les appareils de plus de 5 ans | Évaluer sur le **parc réel des utilisateurs**, pas sur un appareil de test choisi par l'équipe. À défaut, définir un profil matériel de référence et le nommer dans la réponse. Mesure : Lighthouse en throttling CPU/réseau, poids du JavaScript. ⚠️ Le seuil « plus de 5 ans » n'est adossé à aucun profil matériel — arbitrage n° 4. | Forcer le renouvellement des terminaux est l'un des impacts les plus lourds du numérique. La compatibilité avec le matériel ancien prolonge sa durée de vie et évite sa fabrication anticipée. | Significatif | Optimiser la compatibilité avec les appareils anciens pour prolonger leur durée de vie. |

---

## Pilier 6 — Facilité de changement

*(nommé « Ease of Change » dans l'application — arbitrage n° 5.)*

| CRITÈRE | ✏️ ÉVALUATION | MÉTHODES D'ÉVALUATION | EXPLICATION SUPPLÉMENTAIRE | NIVEAU D'IMPACT | RECOMMANDATION (RAPPORT) |
|---|---|---|---|---|---|
| **6.1** — Quel est le niveau d'accès de votre équipe au code de ce service ? | **1** Aucun accès — boîte noire totale<br>**2** Accès en lecture seule<br>**3** Accès partiel — certains modules seulement<br>**4** Accès complet, mais modification soumise à une validation externe<br>**5** Accès total — code entièrement ouvert et modifiable | Le critère porte sur l'accès **en modification**, pas en lecture : c'est le prérequis de toute optimisation. Un progiciel configurable sans accès au source : retenir 1 si rien n'est modifiable, 2 si le paramétrage est le seul levier. Source : équipe de développement, contrat éditeur. | Sans accès au code, aucune optimisation n'est possible. Le contrôle du source est le prérequis absolu de tout projet d'écoconception. | Modéré | Récupérer l'accès complet au code source — prérequis à toute optimisation. |
| **6.2** — Quel est le niveau d'autonomie technique de votre équipe sur ce service ? | **1** Personne ne peut intervenir sur ce service<br>**2** Une seule personne sait intervenir<br>**3** Connaissance partielle — intervention risquée, possible avec accompagnement<br>**4** Plusieurs personnes autonomes sur la majorité du service<br>**5** Équipe autonome — maîtrise complète, intervention en confiance | Évaluer les compétences **effectivement disponibles aujourd'hui**, pas celles recrutables. Le cran 2 — une seule personne — est un point de fragilité à distinguer du cran 3 : il ne se traite pas de la même façon (transfert de connaissance plutôt que formation). Source : équipe et sa hiérarchie. | La connaissance implicite d'un seul développeur parti bloque toute évolution. La disponibilité des compétences détermine concrètement la capacité à agir. | Modéré | Former l'équipe ou recruter les compétences pour maîtriser et faire évoluer ce service. |

---

## Réponse « Je ne sais pas »

Le mécanisme existe déjà dans l'application (bouton dédié, réponse exclue du score, comptée
dans le taux de confiance `confidencePercent`). Le travail restant est de **supprimer le
chemin concurrent** : aucun libellé de l'échelle 1–5 ne doit contenir « inconnu » — dix en
contiennent aujourd'hui, héritage direct du template EOF (US 2.23, E2-9).

Le taux de réponses connues — `confidencePercent` : réponses exploitables sur questions
visibles — est l'**indicateur de confiance du diagnostic**, distinct du score. Un service
dont l'équipe ignore la moitié des réponses est un constat en soi.

---

## Décidabilité par un agent — diagnostic rapide en boîte noire

Classement sous la contrainte **URL seule**, sans accès au dépôt, à l'IaC ni à
l'observabilité. Convention du triage de l'avancé : **AUTO** (l'agent tranche seul),
**SEMI** (il propose, un humain confirme), **HUMAIN**.

**Règle de classement appliquée**, pour que le tableau soit rejouable :

- **AUTO** — une source machine accessible depuis l'URL suffit à déterminer le cran, et la
  méthode d'évaluation ne demande aucune information que la machine n'ait pas.
- **SEMI** — la source existe mais ne couvre qu'une partie de ce que la méthode exige : elle
  fonde une proposition, pas une décision. Chaque ligne SEMI nomme ce qui manque.
- **HUMAIN** — la méthode exige une information contractuelle, organisationnelle ou
  d'intention, qu'aucune mesure externe ne produit.

Le classement se déduit de la colonne MÉTHODES D'ÉVALUATION, pas de l'énoncé seul.

**Format de sortie attendu de l'agent** — celui du contrat de pré-remplissage (E3-1) :
`{ questionId, answer (cran 1–5 ou abstention), confidence, evidence[] }`. Une proposition
sans preuve est refusée à l'import. L'exploitation de l'écart déclaré ↔ mesuré est
spécifiée à part (E3-5), pas ici.

| Critère | Classe | Source d'évidence |
|---|---|---|
| **3.2** région d'hébergement | AUTO | IP / CDN → région → intensité carbone. **Réserve :** derrière un CDN, l'origine peut être masquée, et le multi-région invisible — si la région d'origine n'est pas identifiable avec certitude, s'abstenir plutôt que noter la région du point d'entrée. |
| **1.3** temps de réponse | SEMI | CWV, Lighthouse — l'affichage seulement, rien du back-office. |
| **2.2** dépendances | SEMI **faible** | Domaines tiers au HAR. **Proxy trompeur** : aveugle aux dépendances internes (SSO, bus, base partagée), précisément celles que le critère vise. S'abstenir plutôt que proposer un chiffre bas par cécité. |
| **5.2** friction des parcours | SEMI | Requêtes et rechargements par parcours. La perception utilisateur reste hors de portée. |
| **5.3** appareils anciens | SEMI | CWV mobile, poids JS, throttling. Le parc réel des utilisateurs est inconnu de l'agent. |
| Les 11 autres | HUMAIN | Criticité métier, SLA contractuel, volume stocké, politique de rétention, accès au code, autonomie de l'équipe, duplication applicative, backlog de performance. |

**1 AUTO · 4 SEMI · 11 HUMAIN** — 6 % en AUTO, 31 % en AUTO+SEMI. Le diagnostic avancé est à
30 % / 57 %, tous accès confondus.

Ce n'est pas un défaut : c'est la nature du diagnostic rapide. Il porte sur le **contexte**
d'un service — à quoi il sert, ce qu'il coûte à l'organisation, qui peut y toucher — et non
sur son comportement observable. **Conséquence :** sur le rapide, le pré-remplissage
automatique n'est pas l'usage utile. Les deux usages qui le sont : mener l'entretien sans
ambiguïté — d'où les colonnes de ce document — et confronter la réponse déclarée à la mesure
sur les cinq critères AUTO/SEMI.

---

## Mesure — avant / après

Huit tests binaires, appliqués aux 16 critères : **128 points**. Chaque test est vérifiable
sur pièces — donnée, code ou interface — sans jugement : n'importe qui doit retrouver le
même chiffre. **« Avant » = l'état actuel de l'application. « Après » = une fois la
proposition de ce document appliquée, donnée et interface comprises** (les tests U3 et U5
supposent les US 2.27 et les fiches de méthodes livrées).

| # | Test | Passe si… | Avant | Après |
|---|---|---|---|---|
| **U1** | Énoncé de degré | L'énoncé n'est ni une question fermée ni une alternative | **2** | 16 |
| **U2** | Dimension unique | L'énoncé ne cumule pas deux constats évaluables séparément | **13** | 16 |
| **U3** | Cinq crans nommés | Les crans 1 à 5 portent chacun un libellé, et il est affiché | **0** | 16 |
| **U4** | Ignorance en réponse unique | Aucun libellé de l'échelle ne contient « inconnu » | **6** | 16 |
| **U5** | Méthode d'évaluation écrite | Une règle dit ce qu'on compte et ce qui départage deux crans voisins | **0** | 16 |
| **U6** | Orientation conforme à l'axe | Le cran 1 correspond bien au fort potentiel d'optimisation | **16** | 16 |
| **C1** | La réponse entre dans le score | La réponse alimente le score de pilier et le score global | **15** | 15 |
| **C2** | Recommandation présente et cohérente | Une recommandation existe et vise bien le cran bas | **16** | 16 |
| | | **Total** | **68 / 128** | **127 / 128** |

> ### **53 % → 99 %**

Le seul échec persistant : `Infrastructure 2` en **C1** — sa réponse alimente le plan
d'action mais pas le score de pilier, et ce document propose la correction sans la trancher
(arbitrage n° 2).

Note sur le plan d'action, qui fonde C2 : `computeResults.ts` ne retient que les critères
dont le cran est **strictement inférieur à 5**, puis trie par `(5 − score) × co2Weight`. Les
recommandations des 16 critères visent bien les crans bas — contrôlé un par un.

### Pourquoi ce 99 % est trompeur

**La grille teste exactement les défauts que ce document corrige.** Construite à partir de
ses propres constats, elle ne peut que bien noter son propre travail. Le chiffre mesure la
complétude du correctif rédactionnel, pas l'univocité réelle.

Deux mesures plus dures :

**1. Combien de critères sont clos, sans réserve ni arbitrage ouvert ?**

| Critère | Réserve |
|---|---|
| `Produit 3` | arbitrage 1 — découpe, perte d'information |
| `Architecture 1` | arbitrage 6 — doublon avec l'avancé |
| `Infrastructure 1` | arbitrage 3 — échelle relative |
| `Infrastructure 2` | arbitrages 2 et 6 — score, seuils, doublon |
| `Stockage 1` | arbitrages 3 et 5 |
| `Stockage 2`, `Algo 1`, `Algo 2`, `Ease 1`, `Ease 2` | arbitrage 5 — nom de pilier |
| `Algo 3` | arbitrages 4 et 5 |
| **`Produit 1`, `Produit 2`, `Architecture 2`, `Architecture 3`, `Infrastructure 3`** | **aucune** |

> ### **5 critères sur 16 sont clos — 31 %**

*(L'arbitrage n° 7 — 5 ou 3 crans — porte sur les 16 et n'est pas compté : choix de forme
global, pas une réserve par critère.)*

**2. Combien de cas limites la règle de décision tranche-t-elle ?** `0 / 16` aujourd'hui —
les cas limites ne sont pas écrits (US 2.28). C'est la mesure qui remplacera les deux autres :
elle seule peut échouer contre le réel, et elle sert directement l'agent.

Lecture d'ensemble : **53 % → 99 %** dit que les défauts mécaniques d'écriture sont traités.
**31 %** dit que onze critères portent encore une question de fond posée sans être tranchée.
Le premier chiffre monte par la rédaction, seul. Le second ne monte que par des décisions —
dont plusieurs engagent le framework, donc Boavizta, pas seulement l'implémentation.
**Le chiffre à suivre est le second, puis le troisième dès que les cas limites existent.**

---

## Points d'arbitrage

Aucun n'est tranché. Chacun est signalé à l'endroit concerné.

| # | Point | Portée |
|---|---|---|
| 1 | `Produit 3` : la découpe « temps de réponse seul » perd l'efficacité par requête (un service sobre en matériel mais gourmand par appel n'est plus capté). Assumer, ou scinder — le rapide passerait à 17 critères. | 1 critère |
| 2 | `Infrastructure 2` : faire entrer sa réponse dans le score du pilier et le score global, ou assumer qu'elle n'alimente que le plan d'action ? Et trancher les seuils : l'EOF pose 750/500/300/200/100 **avec un trou entre 500 et 750** ; l'app applique 500/300/150/50. | 1 critère |
| 3 | `Stockage 1` et `Infrastructure 1` : échelle absolue ou relative à l'organisation ? En l'état, le cran 3 n'est pas comparable aux autres crans, et les ordres de grandeur laissent des trous. | 2 critères |
| 4 | `Algo 3` : quel profil matériel de référence derrière « appareils de plus de 5 ans » ? | 1 critère |
| 5 | Noms de piliers : trois en anglais dans le rapide (`Storage & Data`, `Algo & Code`, `Ease of Change`), un dans l'avancé (`Algo & Code`) — et les traductions ne coïncident pas entre profondeurs. Harmoniser, y compris `Algo & Code`. | 3 piliers |
| 6 | Doublons entre rapide et avancé : `Architecture 1` ≡ `ease-advanced-10` (haute disponibilité) et `Infrastructure 2` ≡ `infrastructure-advanced-3` (région). Même question, deux piliers, deux échelles. Dédupliquer, ou écrire une règle de cohérence entre les deux réponses ? | 2 critères |
| 7 | Échelle : reprendre les cinq libellés EOF adaptés au langage d'usage (proposition de ce document), ou réduire à trois crans nommés ? | 16 critères |

---

## Ce qui a été vérifié et se révèle conforme

- **Orientation de l'échelle : les 16 critères contrôlés un à un contre le template EOF
  V1.1.** Aucun n'est retourné — y compris `Produit 1`, contrairement à ce que les fichiers
  compagnons CSV et comparaison laissent croire (ils inversent la v1.1 de ce critère, US 2.22).
- **Cohérence libellé bas ↔ explication ↔ recommandation** : contrôlée sur les 16, aucune
  contradiction. Les recommandations ne se déclenchent que sur les scores bas et visent bien
  la situation basse.
- **« Je ne sais pas »** : le mécanisme applicatif existe (bouton, exclusion du score, taux
  de confiance) — le défaut restant est dans les libellés, pas dans le code.

## Limites de ce document

1. **Les reformulations n'ont été testées sur personne.** Elles corrigent des défauts
   vérifiables, mais la preuve qu'elles sont mieux comprises se fait en passation
   (`docs/user-tests-march-2026.md` existe pour ça).
2. **Les libellés des crans 2 et 4 sont adaptés, pas validés.** Le template EOF nomme les
   cinq crans ; les propositions ci-dessus s'en inspirent en langage d'usage mais n'ont pas
   été réconciliées ligne à ligne avec lui (US 2.27).
3. **La colonne `NIVEAU D'IMPACT` est dérivée d'un champ qui ne mesure pas la même chose** —
   voir la réserve dans la section « Colonne NIVEAU D'IMPACT ».
4. **Le classement de décidabilité n'a pas été confronté à un agent réel.** Les quatre SEMI
   et la réserve CDN sur 3.2 sont les plus susceptibles de bouger à l'usage.
5. **Plusieurs échelles mêlent constat technique et maturité de traitement** (`1.3`, `3.3`,
   `5.2`) — hérité de l'EOF, assumé pour un questionnaire déclaratif. Les cas limites
   (US 2.28) devront borner ces crans-là en premier.
6. **Rien n'empêche la dérive de recommencer.** Aucun des huit tests n'est vérifié par une
   machine. U3, U4 et U6 sont mécaniquement testables (US 2.26) ; U1, U2 et U5 restent des
   revues humaines. Sans test, ce document décrit un état, il ne le tient pas.
