-----
Méthodologie e-footprint (Boavizta) : ce que le calcul mesure, sur quoi il repose, ses limites
-----

Ce document répond à une question simple mais qui ne l'est pas : quand le rapport EROOM
affiche "X kg CO2e/an", qu'est-ce que ce chiffre représente exactement, et jusqu'où
peut-on lui faire confiance ? Tout ce qui suit est vérifié dans le code source installé
localement (`e-footprint` v22.3.1, package Python de Boavizta), pas déduit ni supposé.

Il ne traite QUE de ce que fait la bibliothèque e-footprint elle-même. Ce que le projet
Agent EROOM AJOUTE par-dessus (temps de lecture Nielsen recalé, fourchettes
d'incertitude, détection de topologie...) est documenté ailleurs (voir
`skill-steps/45_efootprint.md` et la mémoire persistante du projet) ; ce document les
mentionne seulement quand ils touchent à un point discuté ici.


-----
Résumé en 7 points (détail et références dans les sections qui suivent)
-----

- **Pas une ACV ISO 14040/14044.** Seulement 2 phases modélisées (fabrication + usage) ;
  transport et fin de vie exclus, jugés négligeables par les auteurs eux-mêmes.
- **Mono-critère.** Uniquement du CO2e. L'eau, les ressources abiotiques, l'acidification
  et compagnie sont annoncées comme une évolution future, pas encore livrées.
- **IA générative : calculée si ajoutée à la main, jamais automatiquement.** Une IA
  tierce (OpenAI, Anthropic...) détectée dans le trafic réseau est SIGNALÉE mais pas
  incluse dans le total CO2e sans intervention manuelle ; un modèle auto-hébergé
  (GPU) est, lui, invisible depuis le HAR et ne peut être ajouté qu'à la main.
- **Sources principales : ADEME (Base Carbone V19) pour la fabrication du matériel,
  Boavizta API pour les instances cloud, Our World in Data (2023-2024) pour l'intensité
  carbone électrique par pays**, plus plusieurs études ponctuelles datées (ARCEP 2022,
  State of Mobile 2022, articles arXiv). Ni ecoinvent, ni GreenIT-ACV, ni ReCiPe/PEF.
- **Hypothèses clés codées en dur : durées de vie 3 à 6 ans selon le matériel, PUE
  datacenter 1,2, intensité carbone électrique générique 400 g CO2/kWh.**
- **Avantages** : calcul traçable formule par formule, granularité fine par composant,
  code ouvert (licence libre), maintenu activement par Boavizta.
- **Limites assumées par les auteurs** : périmètre volontairement restreint, hypothèses
  parfois datées, deux valeurs par défaut (PUE, intensité générique) sans source citée
  dans le code.


-----
1. Est-ce une Analyse de Cycle de Vie (ACV) ?
-----

**Non, pas au sens ISO 14040/14044.** Le code n'utilise jamais les termes "LCA" ou "ACV"
pour se qualifier. Une ACV complète couvre normalement cinq phases : extraction des
matières premières, fabrication, distribution/transport, usage, fin de vie. e-footprint
n'en modélise que **deux** :

- **Fabrication** (`Manufacturing`) : empreinte carbone de la construction du matériel,
  amortie sur sa durée de vie.
- **Usage** (`Usage`) : empreinte carbone de la consommation électrique pendant
  l'utilisation.

(Référence : `efootprint/core/lifecycle_phases.py`, classe `LifeCyclePhases`.)

Le transport du matériel et sa fin de vie (recyclage, déchet) sont **explicitement
exclus**, jugés négligeables par les auteurs eux-mêmes. Citation du README officiel du
package :

> "the lifecycle phases of device transportation and end of life are currently
> considered negligible."

La fabrication du matériel réseau n'est pas non plus modélisée (seule sa consommation en
usage l'est) : "Network fabrication is not modeled" (`efootprint/core/hardware/network.py`).

**Ce que ça veut dire concrètement pour lire un rapport EROOM** : le chiffre CO2e ne
couvre pas tout le cycle de vie du matériel. Il ignore notamment le transport (le
serveur qui arrive du fabricant par bateau/avion) et la fin de vie (démantèlement,
recyclage, déchet électronique). Sur du matériel informatique, ces deux postes sont
généralement documentés comme minoritaires face à la fabrication et à l'usage, ce qui
justifie en partie le choix des auteurs, mais ce n'est pas une couverture exhaustive.


-----
2. Est-ce une analyse multicritère (au-delà du carbone) ?
-----

**Non, pas dans cette version. Le calcul est mono-critère : uniquement du CO2e (gaz à
effet de serre).**

Aucune sortie du modèle ne porte sur l'épuisement des ressources abiotiques (ADP),
l'acidification, l'eutrophisation, l'écotoxicité ou la consommation d'eau. Toutes les
unités de sortie du code sont du carbone ; tous les attributs s'appellent
`carbon_footprint_*`, jamais `water_footprint` ou `adp_footprint`.

Le README du package le confirme et annonce une évolution future, pas encore livrée :

> "Other environmental impacts (water, rare earth metals, etc.) will be added soon
> through an integration with the Boavizta API."

Point à noter, pour la précision : pour les appels à des API d'IA générative
(OpenAI, Anthropic, etc.), e-footprint s'appuie sur une bibliothèque tierce
(**EcoLogits**) qui, elle, calcule *en interne* trois indicateurs supplémentaires
(épuisement de ressources abiotiques, énergie primaire, consommation d'eau). Mais le
code d'e-footprint filtre volontairement ces trois valeurs avant de les exposer : elles
sont mises en cache "pour une future intégration Boavizta" mais restent, à ce jour,
hors du périmètre carbone affiché (`efootprint/builders/external_apis/ecologits/`).

**Ce que ça veut dire concrètement** : un rapport EROOM ne dit rien sur l'eau
consommée, les métaux rares extraits, ou l'acidification des sols liée à la
fabrication du matériel. Une analyse multicritère (type PEF à 16 catégories, ou
ReCiPe) demanderait un autre outil, ou d'attendre l'intégration Boavizta annoncée.


-----
3. Composants d'intelligence artificielle : comment le calcul les traite (ou pas)
-----

Un site peut faire appel à de l'IA générative de deux façons différentes, et
e-footprint ne les traite pas du tout de la même manière.

**3.1. Appel à une IA générative tierce (API externe, ex. un chatbot qui interroge
GPT/Claude/Gemini/Mistral)**

e-footprint a une classe dédiée, `ExternalApiSpec`/`EcoLogitsGenAIExternalAPI`
(`efootprint/builders/external_apis/ecologits/`), qui s'appuie sur une bibliothèque
tierce, **EcoLogits** (projet "genai-impact"). Le catalogue couvre 6 fournisseurs :
**Anthropic, OpenAI, Google Generative AI, Mistral AI, Cohere, Hugging Face**. Pour un
modèle donné, EcoLogits fournit le nombre de paramètres, le débit, la localisation du
datacenter et l'intensité carbone du réseau électrique local, pour calculer une
empreinte par appel (fonction du nombre de tokens générés en sortie).

**C'est un calcul, pas une estimation réseau.** La raison documentée dans le code
(`spec.py`, classe `ExternalApiSpec`) : contrairement à un CDN ou une police de
caractères qui livre un fichier déjà prêt, un appel à un modèle génératif déclenche un
vrai calcul (le modèle produit le texte mot par mot) — le compter uniquement en octets
transférés sous-estimerait largement son empreinte réelle.

**Mais ce composant n'est JAMAIS ajouté automatiquement au calcul par l'agent EROOM.**
L'Étape 25 du skill efootprint (vue d'ensemble avant calcul) *détecte* qu'un appel à
une IA générative tierce a eu lieu — par reconnaissance du nom de domaine exact dans le
HAR (`detect_tech.py`, catégories "OpenAI (API)", "Anthropic (API Claude)", "Google
Generative AI (Gemini)", "Mistral AI (API)", "Cohere (API)", "Azure OpenAI", "Hugging
Face Inference API") — et l'affiche comme "identifié" à l'utilisatrice. Mais elle
s'arrête à la présentation : elle ne construit **jamais** automatiquement un
`ExternalApiSpec` dans le modèle de calcul (limite documentée dans
`skill-steps/45_efootprint.md`). Concrètement : si un site audité appelle une IA
générative en coulisses, le rapport le SIGNALE, mais le total CO2e affiché ne l'inclut
PAS tant que ce composant n'a pas été ajouté à la main au modèle. C'est un lot futur,
non planifié à ce jour.

Concrètement, "ajouté à la main" veut dire : quelqu'un doit ouvrir le script Python qui
construit le modèle de calcul et écrire une ligne comme celle-ci, avec les bonnes
valeurs pour le site audité (fournisseur, nom du modèle, nombre de réponses générées
par an) :

```python
ExternalApiSpec(provider="anthropic", model_name="claude-3-5-sonnet", output_tokens=800)
```

Personne ne fait ce geste aujourd'hui dans l'agent EROOM : ni l'agent, ni un script
automatique. Il faudrait connaître ces valeurs (souvent non visibles depuis le trafic
réseau capturé) et les saisir soi-même dans le code, à chaque nouvel audit. C'est la
différence entre "on a vu passer une IA" (automatique, fait aujourd'hui) et "on a
compté son empreinte" (manuel, jamais fait à ce jour).

**3.2. Serveur d'IA auto-hébergé (le site fait tourner lui-même un modèle sur ses
propres machines, type GPU dédié)**

Là, e-footprint a une classe différente, `GPUServer`
(`efootprint/core/hardware/gpu_server.py`), qui modélise un serveur équipé de GPU :
puissance dédiée (400 W par GPU, source article arXiv "Estimating the Carbon Footprint
of BLOOM"), fabrication (150 kg CO2e par GPU), durée de vie 6 ans, PUE 1,2 (mêmes
hypothèses par défaut qu'un serveur classique, cf. section 5).

**Cette voie n'est, elle non plus, jamais activée automatiquement.** Un GPUServer ne
peut être détecté depuis un simple trafic réseau capturé (HAR) : par nature, l'inférence
tourne côté serveur, invisible depuis le navigateur. Un modèle auto-hébergé derrière
l'API applicative d'un site n'émet aucun signal réseau distinctif — comme n'importe
quelle base de données auto-hébergée (cf. la mise en garde systématique de l'Étape 25 :
"une base de données ou un service auto-hébergé derrière le serveur applicatif n'émet
aucun signal visible depuis le trafic réseau capturé"). Un `GPUServer` ne peut donc être
ajouté qu'à la main, sur la base d'une information transmise par l'équipe qui exploite
le site (jamais déduit du HAR).

**Ce que ça veut dire concrètement pour lire un rapport EROOM** : si le rapport ne
mentionne aucune IA générative, cela peut vouloir dire soit qu'il n'y en a pas, soit
qu'elle est invisible depuis le trafic réseau capturé (serveur auto-hébergé). Si le
rapport SIGNALE une IA générative tierce identifiée, le total CO2e affiché ne l'inclut
pas pour autant tant qu'elle n'a pas été ajoutée manuellement au modèle : distinguer
"détecté dans la topologie" de "compté dans le calcul" est essentiel pour ne pas
sous-estimer l'empreinte réelle du site.


-----
4. Sur quelles données le calcul s'appuie-t-il ?
-----

Le référentiel des sources est centralisé dans le code
(`efootprint/constants/sources.py`, classe `Sources`). Résumé de ce qui alimente
réellement un calcul :

| Donnée modélisée | Source | Millésime observé |
|---|---|---|
| Fabrication carbone du matériel générique (serveur, smartphone, laptop, écran, box) | Base Carbone® ADEME, version "V19" | Non précisé en clair dans le nom de la source ; commentaires du code datés 2018-2023 |
| Fabrication + caractéristiques des instances cloud (AWS, GCP, Azure, OVH, Scaleway) | API Boavizta (`api.boavizta.org/v1/cloud/instance`), avec un instantané embarqué | Instantané figé dans le package, non redaté à chaque appel |
| Intensité carbone de l'électricité, par pays | Our World in Data | 2023 ou 2024 selon le pays (varie ligne par ligne dans le fichier fourni) |
| Fabrication SSD/HDD | Article arXiv "Dirty secret of SSDs: embodied carbon" | Étude ponctuelle, pas de millésime officiel de référentiel |
| Réseau mobile (énergie par Go) | Observatoire ARCEP | 3ᵉ trimestre 2022 |
| Temps d'usage quotidien smartphone/laptop | data.ai, "State of Mobile" | 2022 |
| Énergie Wifi/mobile (kWh/Go) | Étude Traficom (Finlande) | Non précisé |
| Fabrication et puissance des GPU serveurs | Article arXiv "Estimating the Carbon Footprint of BLOOM" | Étude ponctuelle |
| Empreinte des appels à une IA générative tierce | Bibliothèque EcoLogits | Dépend des mises à jour de cette dépendance |

**Ce qui n'est PAS utilisé** (vérifié par recherche dans le code, absence confirmée) :
ecoinvent, GreenIT-Analyse de Cycle de Vie, ReCiPe, PEF. Ce sont des bases/méthodes
reconnues en ACV, mais elles n'interviennent nulle part dans e-footprint.

**Ce que ça veut dire concrètement** : les données ne sont pas toutes de la même
fraîcheur ni de la même nature. Certaines sont des bases officielles régulièrement
mises à jour (ADEME, Boavizta), d'autres sont des études ponctuelles figées dans le
temps (ARCEP 2022, State of Mobile 2022, l'article sur BLOOM). Un rapport généré en
2026 s'appuie donc, pour une partie de ses hypothèses, sur des mesures qui ont
plusieurs années.


-----
5. Quelles sont les hypothèses structurantes du calcul ?
-----

Ce sont des valeurs codées en dur dans la bibliothèque, appliquées par défaut à tout
calcul sauf si l'utilisateur les override explicitement.

**Durée de vie du matériel** (période sur laquelle la fabrication est amortie) :

| Équipement | Durée de vie par défaut |
|---|---|
| Smartphone | 3 ans |
| Laptop / Box internet / Écran | 6 ans |
| Serveur (générique ou GPU) | 6 ans |
| Stockage SSD | 6 ans |
| Stockage HDD | 4 ans |

**Autres hypothèses par défaut :**
- PUE (surcoût énergétique du datacenter, climatisation etc.) : **1,2** (valeur codée
  en dur, sans source citée dans le code).
- Intensité carbone électrique générique (si aucun pays n'est précisé) :
  **400 g CO2/kWh**.
- Taux d'usage quotidien : smartphone 3,6 h/jour, laptop/écran 7 h/jour, box 24 h/jour
  (source State of Mobile 2022).
- Puissance des appareils : smartphone 1 W, laptop 50 W, box 10 W, écran 30 W, serveur
  300 W (50 W à vide).
- Taux d'utilisation ("remplissage") d'un serveur par défaut : 0,9 (90 %).
- Facteur de réplication des données stockées : 3 copies, durée de rétention par
  défaut 5 ans.

**Ce que ça veut dire concrètement** : chaque calcul repose sur une dizaine
d'hypothèses par défaut qui ne sont PAS mesurées sur le site audité, mais issues de
moyennes sectorielles. Le rapport EROOM les documente une par une, avec un badge de
confiance, précisément pour rendre visible cette part d'hypothèse (voir l'annexe
"Méthodologie & hypothèses" de chaque rapport).


-----
6. Avantages
-----

- **Traçabilité du calcul.** Chaque valeur calculée reste reliée à la formule et aux
  entrées qui l'ont produite (mécanisme interne `ExplainableObject`). L'outil peut
  générer un graphe de calcul qui montre, valeur par valeur, d'où elle vient.
- **Granularité fine.** Le modèle distingue serveurs, stockage, réseau, appareils
  utilisateurs, avec des paramètres propres à chacun (au lieu d'un chiffre global
  agrégé).
- **Ouvert et vérifiable.** Licence libre (AGPL v3), code et hypothèses lisibles,
  contrairement à un calculateur propriétaire en boîte noire.
- **Actif et documenté.** Maintenu par Boavizta (association reconnue dans l'écosystème
  numérique responsable), avec une interface graphique et une documentation en ligne.
- **Extensible.** Permet d'ajouter des instances cloud spécifiques via l'API Boavizta,
  des appels IA générative via EcoLogits, et récemment des "edge devices" (consoles,
  objets connectés) avec des regroupements hiérarchiques.


-----
7. Limites (les leurs, assumées dans leur propre documentation)
-----

- **Périmètre restreint du cycle de vie.** Ni transport ni fin de vie modélisés
  (jugés négligeables, hypothèse des auteurs, non démontrée dans le code lui-même).
- **Mono-critère.** Aucun indicateur au-delà du carbone à ce jour ; le multicritère
  (eau, ressources abiotiques...) est annoncé mais pas livré.
- **Hypothèses figées et parfois datées.** Certaines études sources ont plusieurs
  années (ARCEP 2022, State of Mobile 2022) et ne sont pas automatiquement
  actualisées par une mise à jour de version.
- **PUE et intensité carbone générique sans source citée.** Ces deux valeurs par
  défaut (1,2 et 400 g/kWh) ne sont pas rattachées à une référence dans le code : à
  utiliser comme un ordre de grandeur, pas une mesure.
- **Le réseau n'a pas d'empreinte de fabrication.** Seule sa consommation d'usage est
  comptée ; les infrastructures télécoms (câbles, antennes, routeurs) sont absentes
  du calcul de fabrication.


-----
8. Ce que le projet Agent EROOM ajoute (rappel, détaillé ailleurs)
-----

Ces points ne sont PAS natifs à e-footprint : ils sont propres à l'intégration faite
dans ce projet, pour compenser ou documenter certaines limites ci-dessus.

- **Temps de lecture utilisateur (Nielsen 2008 recalé)** : e-footprint attend un temps
  d'usage par étape du parcours en entrée, il ne le calcule pas lui-même. Le projet le
  dérive du contenu réel des pages capturées (comptage de mots), recalé sur une mesure
  d'engagement SimilarWeb. Voir `efootprint_model/temps_utilisateur.py` et l'annexe
  "Temps de lecture par étape" de chaque rapport.
- **Fourchettes d'incertitude non cumulées** (infrastructure vs usage) : ajout du
  projet pour visualiser la sensibilité du résultat à deux hypothèses distinctes,
  sans jamais les additionner (voir mémoire persistante "fourchettes non cumulées").
- **Traçabilité valeur/source/confiance par ligne** dans l'annexe HTML : convention du
  projet, pas d'e-footprint lui-même (qui trace la formule mais n'affiche pas de badge
  de confiance dans son propre output).
