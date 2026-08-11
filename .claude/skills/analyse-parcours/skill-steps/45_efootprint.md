# Étape 45 - Estimation CO2e (e-footprint)

## Vue d'ensemble

Cette étape orchestre le calcul d'une estimation CO2e du site analysé,
via la librairie e-footprint (Boavizta). Elle s'appuie sur les scripts
existants dans `.claude/skills/analyse-parcours/scripts/` :

- `collect_env_data.py` : collecte HAR + CrUX + ipinfo -> `env-data.json`
- `run_efootprint.py` : calcul CO2e + sérialisation -> `efootprint-model.json`

**Cette étape ne duplique pas la logique** : elle détecte, questionne, appelle.

-----

## AVERTISSEMENT OBLIGATOIRE

Toutes les valeurs produites sont des **estimations hypothétiques**.
Elles reposent sur des données collectées automatiquement (HAR, CrUX, ipinfo)
et sur de nombreuses hypothèses par défaut (trafic, instance, mix électrique).

Ces résultats **ne constituent pas une mesure réelle** de l'impact
environnemental. Ils donnent un ordre de grandeur pour comparer des
scénarios ou identifier les postes dominants.

Ce rappel doit apparaître :
- au démarrage de l'étape (avant de demander les paramètres)
- sur chaque paramètre saisi (`hypothèse` ou `paramètre`)
- dans le résumé final des résultats

-----

## Invocation

```
/efootprint <source_dir>
/efootprint                       # source_dir déduit du contexte analyse-parcours
```

Déclencheurs textuels :
- "estime l'empreinte du site"
- "calcule l'impact CO2"
- "e-footprint sur ce parcours"
- "impact environnemental"

-----

## Principe architectural : chaque étape est relançable

```
Étape 10 -> source_dir           (détection ou saisie)
Étape 20 -> env-data.json        (collect_env_data.py, cache permanent)
Étape 25 -> vue d'ensemble (topologie + BDD/streaming/IA suspectés, PlantUML)
Étape 30 -> paramètres utilisateur (AskUserQuestion sur trafic + instance)
Étape 40 -> efootprint-model.json (run_efootprint.py, recalcul à chaque run)
Étape 50 -> synthèse + propositions
```

Chaque étape peut être relancée indépendamment :
- Relancer étape 20 : passer `--refresh` à `collect_env_data.py`
- Relancer étape 25 : rappeler `build_topology_overview()` (aucun paramètre,
  relit env-data.json + le HAR tels qu'ils sont au moment de l'appel)
- Relancer étape 40 : rappeler `run_efootprint.py` avec d'autres `--visits` ou `--instance`

-----

## Étape 10 - Localisation du source_dir

Objectif : déterminer le dossier contenant le HAR (ou au moins un `env-data.json`).

Ordre de résolution :
1. **Argument explicite** : `/efootprint <chemin>` -> utiliser tel quel
2. **Contexte analyse-parcours** : si un HAR a été analysé récemment dans la
   conversation, proposer son dossier parent en confirmation à l'utilisateur
3. **Fichier ouvert** : si un `.har` est visible dans le contexte, proposer son parent
4. **Défaut** : demander via AskUserQuestion avec une liste des dossiers
   contenant un `.har` ou un `env-data.json` à la racine du projet

Vérifier ensuite que `source_dir` existe et contient soit un `.har`, soit un
`env-data.json`. Sinon : signaler mode dégradé et proposer d'abandonner ou
de créer manuellement `env-data.json`.

-----

## Étape 20 - Collecte env-data.json

Vérifier la présence de `<source_dir>/env-data.json` :

- **Absent** : lancer `collect_env_data.py <source_dir>` (sans `--refresh`)
- **Présent** : proposer via AskUserQuestion :
  - "Utiliser le cache existant" (défaut, rapide)
  - "Recollecte fraîche (--refresh)" (utile si HAR mis à jour)

**Mode dégradé** : si `collect_env_data.py` échoue (pas de HAR, pas de clé API),
l'étape continue avec ce qui existe. Signaler explicitement les champs
en `confidence: default` -- ils auront le plus fort impact sur la précision.

Après collecte, afficher un résumé court des données collectées (2-3 lignes).

### Étape 20b - Mix pays d'audience (pondération iOS/macOS)

Le mix pays sert **uniquement** à pondérer les parts iOS (mobile) et macOS (desktop)
de la correction CrUX (CrUX = Chrome only ; voir Étape 30). Il ne touche pas aux CWV.
Ordre de priorité (résolu par `collect_env_data.py`) :

1. **`--audience` saisi** (le plus fiable) : si l'utilisatrice dispose de l'analytics
   du site (GA/Matomo), lui demander la répartition pays et la passer en
   `--audience "FR:0.7,US:0.3"` (ou raccourci pays unique `--audience FR`).
2. **API interne SimilarWeb** (automatique, voir Étape 20e) : `collect_env_data.py`
   interroge lui-même l'API quand le bloc `audience` manque et qu'aucun `--audience`
   n'est fourni. C'est la voie normale à défaut d'analytics client.
3. **Récupération assistée** (Étape 20d) : si l'API échoue (403, domaine non suivi).
4. **Défaut France (100 %)** + avertissement : dernier recours.

Le bloc `audience` écrit (par l'API ou en assisté) a ce format :
```json
"audience": {
  "mix": {"FR": 0.61, "SN": 0.105, "US": 0.041},
  "source": "SimilarWeb (estimation)",
  "source_url": "https://www.similarweb.com/website/<domaine>/",
  "confidence": "medium"
}
```
`source_url` est repris tel quel dans le rapport comme lien "↗ source" à côté du
libellé de provenance du mix. `collect_env_data.py --refresh` **préserve** un bloc
`audience` déjà présent avec une vraie source (sauf si `--audience` est fourni, qui
prime), le renormalise et calcule les parts iOS/macOS pondérées.

**Caveat obligatoire** : SimilarWeb est une estimation grossière, source non
officielle, usage limite CGU. Le caveat figure aussi dans l'annexe du rapport.

### Étape 20c - Volume de trafic annuel (visites/an)

Même logique que le mix pays : **aucune API publique** (PageSpeed, CrUX) ne donne de
volume d'audience (uniquement des distributions, jamais de compteurs). Le trafic est
donc résolu par ordre de priorité :

1. **`--visits` saisi** (le plus fiable, dans `run_efootprint.py`) : analytics du site
   (GA4/Matomo/logs serveur).
2. **API interne SimilarWeb** (automatique, voir Étape 20e) : `collect_env_data.py`
   remplit le bloc `traffic` quand il manque. Voie normale à défaut d'analytics.
3. **Récupération assistée** (Étape 20d) : si l'API échoue.
4. **Défaut 100 000 visites/an** + avertissement : dernier recours.

Le bloc `traffic` écrit a ce format :
```json
"traffic": {
  "visits_per_year": 440000,
  "monthly_visits": 36700,
  "source": "SimilarWeb (estimation)",
  "source_url": "https://www.similarweb.com/website/<domaine>/",
  "snapshot": "juin 2026",
  "confidence": "medium"
}
```

- `visits_per_year` = `monthly_visits × 12` (annualisation). Renseigner `monthly_visits`
  et `snapshot` (mois de la mesure) permet au rapport d'afficher la dérivation.
- `collect_env_data.py <source_dir> --refresh` **préserve** ce bloc `traffic` (comme
  `audience`) ; `run_efootprint.py` le lit automatiquement si `--visits` n'est pas passé.
- `source_url` est repris comme lien "↗ source" dans le rapport (corps + annexe D).
- **Caveat obligatoire** : estimation tierce à **marge large**, pas une mesure. Seuls
  les analytics du site donnent un chiffre exact. Rappeler aussi que le CO2e **total**
  croît avec le trafic (au-dessus d'un socle fixe fabrication serveur + stockage) alors
  que le CO2e **par visite** diminue quand le trafic augmente (relation affine).

### Étape 20d - Récupération assistée si l'API SimilarWeb échoue (captcha / challenge WAF)

SimilarWeb sert régulièrement un **captcha à sélection d'images** ou un challenge AWS WAF
aux accès automatisés. **Ne jamais inventer de chiffres, ne pas contourner le
captcha** : la donnée doit transiter par l'utilisatrice. Deux voies, à lui proposer
**toutes les deux**.

**Déclencheur** : l'appel automatique à l'API interne (Étape 20e, lancé par
`collect_env_data.py`) échoue — 403 CloudFront, domaine peu/pas suivi (message
`⚠ SimilarWeb : …`), ou réseau. Ne PAS enchaîner silencieusement sur le défaut :
proposer d'abord cette récupération assistée.

Message à afficher (adapter `<domaine>` et l'URL exacte) :

> 🔒 **SimilarWeb me bloque (captcha). J'ai besoin de ton aide pour récupérer le trafic
> et le mix pays d'audience.**
>
> 1. Ouvre cette URL dans ton navigateur : `https://www.similarweb.com/website/<domaine>/`
> 2. Passe le captcha (sélection d'images).
> 3. Repère ces **deux** informations sur la page :
>    - **Total Visits** : le gros chiffre du trafic mensuel (ex. "36.7K") **+ la période
>      affichée** (ex. "Jun 2026").
>    - Le bloc **"Top Countries"** : les 3-5 premiers pays avec leurs pourcentages
>      (ex. FR 61 %, SN 10 %, US 4 %, TN 3 %, BR 3 %).
> 4. Transmets-les moi **au choix** :
>    - **Voie A - dictée** : colle-moi directement ces valeurs en chat (le plus rapide).
>    - **Voie B - capture d'écran** : fais une ou deux captures montrant clairement ces
>      deux blocs, dépose-les dans le dossier `<source_dir>/` et nomme-les
>      `similarweb-<domaine>.png` (ou `.jpg`), puis dis-moi "c'est fait".

Précisions pour bien "mâcher" la demande, quelle que soit la voie :
- **Toujours nommer les deux blocs** attendus (Total Visits **+ période**, Top Countries) :
  ne pas demander "toute la page", demander ces zones précises.
- **Voie A (dictée)** : après réception, relire à l'utilisatrice ce que tu as compris
  (chiffre mensuel, période, liste pays %) avant d'écrire, pour rattraper une faute de
  frappe. `source` = `"SimilarWeb (saisie assistée après captcha)"`.
- **Voie B (capture)** : formats lisibles = **PNG, JPG/JPEG, WebP, PDF**. **Éviter le
  HTML enregistré** (Cmd+S) : les chiffres SimilarWeb sont chargés en JavaScript, le HTML
  brut est souvent vide. La seule contrainte réelle est la **lisibilité** (chiffres nets,
  présents dans l'image). Lire le fichier déposé avec l'outil Read, extraire les valeurs.
  `source` = `"SimilarWeb (capture après captcha)"`.
- **Écriture** : dans les deux cas, écrire les blocs `audience` (Étape 20b) **et**
  `traffic` (Étape 20c) dans `env-data.json`, avec `source_url` = l'URL consultée et
  `snapshot` = la période lue, puis relancer `collect_env_data.py <source_dir> --refresh`
  (qui préserve les deux blocs). Le libellé de source et le lien "↗ source" remontent
  tels quels dans le rapport (corps + annexe D) : distincts d'un vrai analytics client.
- **Dernier recours** : si l'utilisatrice ne peut pas fournir la donnée (pas d'accès,
  page indisponible), alors seulement retomber sur les défauts (France 100 % + 100 000/an)
  avec l'avertissement `⚠`, en le signalant explicitement dans le rapport.

### Étape 20e - Automatisation via l'API interne SimilarWeb (voie principale, intégrée)

**Contexte :** L'extension Chrome/Firefox SimilarWeb (`hoklmmgfnpapgjgcpechhaamimifchmp`) interroge
une API interne (endpoint extrait du `.crx`) qui répond **sans authentification** : ni cookie, ni
compte, ni session. Le module `similarweb_api.py` reproduit cet appel et construit les blocs
`audience` (20b) et `traffic` (20c). C'est la **voie principale** : elle évite le captcha et la
saisie assistée dans la plupart des cas.

**Intégration (nouveau) :** `collect_env_data.py` appelle **lui-même** ce module, automatiquement,
quand un bloc `audience` ou `traffic` manque. Plus besoin de lancer deux commandes : une seule
suffit.
```bash
python3 .claude/skills/analyse-parcours/scripts/collect_env_data.py <source_dir> --refresh
```
Options associées :
- `--sw-domain <domaine>` : force le domaine interrogé (sinon déduit de `env-data.json`/HAR).
- `--no-similarweb` : désactive l'appel (mode hors-ligne / éviter le réseau).
- Le module reste utilisable en **standalone** pour inspection : `similarweb_api.py <dir>
  [--domain octo.com] [--print-only]`.

**Déclenchement et garde-fous** (l'ordre de priorité reste sacré) :
- Appel lancé **seulement** si le bloc visé manque (absent, ou `source` = `default`/`None`).
- `--audience` fourni → la saisie manuelle prime, l'API **n'écrit pas** le mix pays (elle peut
  toujours compléter le trafic s'il manque).
- Bloc déjà présent avec une vraie source → **jamais écrasé** (idempotent sur `--refresh`).
- Blocs écrits avec `source = "SimilarWeb (estimation)"` (libellé neutre, la méthode API reste doc
  interne), `source_url` (page lisible `www.similarweb.com/website/<domaine>/` pour vérification) et
  `snapshot`. Ne touche à rien d'autre dans `env-data.json`.

**Ce qui a été validé (juillet 2026) :**
- Endpoint : `https://data.similarweb.com/api/v1/data?domain=<domaine>` (GET)
- En-têtes **suffisants** : `Content-Type: application/json`, `X-Extension-Version: 6.12.21`,
  et **un vrai `User-Agent` de navigateur**.
- Retourne `TopCountryShares` (mix pays), `EstimatedMonthlyVisits` (visites/mois),
  `Engagments`, `GlobalRank`, `TrafficSources`… : tout ce dont 20b/20c ont besoin.

**Diagnostic du 403 (corrigé) :** le blocage documenté auparavant ne venait **pas** d'un manque
de cookies (hypothèse fausse), mais de deux erreurs dans la requête de test :
1. En-tête `Origin: chrome-extension://...` → CloudFront le rejette (403). **Ne pas l'envoyer.**
2. User-Agent non navigateur (défaut d'un client HTTP) → 403. **Envoyer un UA navigateur.**
Sans `Origin` et avec un UA navigateur, l'appel répond **200** depuis un simple client HTTP.

**En cas d'échec** (403 réapparu, domaine peu/pas suivi, réseau), `collect_env_data.py` affiche un
message `⚠ SimilarWeb : …` puis **continue sans crasher** : retomber alors sur la **récupération
assistée (Étape 20d)**, pas sur le défaut silencieux. Note : l'API répond 200 même pour un domaine
inconnu, mais sans `TopCountryShares` ni visites → les blocs ne sont pas construits (message
explicite).

**Ordre de priorité global des sources** (mix pays ET trafic) :
1. Analytics client (`--audience` / `--visits`) : le plus fiable.
2. **API interne SimilarWeb** (automatique, intégrée à `collect_env_data.py`) : voie principale.
3. Récupération assistée (20d) : si l'API échoue (captcha/WAF/domaine non suivi).
4. Défauts France 100 % + 100 000/an + `⚠` : dernier recours.

**Robustesse à surveiller :** si l'API se remet à renvoyer 403, revalider la version d'extension
(`EXTENSION_VERSION` dans `similarweb_api.py`) et l'absence d'en-tête `Origin`. Caveat inchangé :
SimilarWeb reste une **estimation tierce à marge large**, source non officielle (usage limite CGU),
distincte d'un vrai analytics client : le caveat figure dans l'annexe du rapport.

-----

## Étape 25 - Vue d'ensemble du système avant calcul

**AVERTISSEMENT (rappel obligatoire) :** ce qui suit est une hypothèse de
topologie construite depuis le HAR, pas une architecture confirmée. La
détection BDD/streaming/IA est une SUSPICION (heuristique sur signaux réseau
visibles côté client), jamais une mesure — sauf pour un provider IA/BaaS
reconnu par son nom de domaine exact, où le signal est quasi certain.

Objectif : avant de lancer le calcul CO2e (Étape 40), présenter à
l'utilisatrice le système que l'agent a "en tête" — serveurs détectés,
services tiers, suspicions BDD/streaming/IA — et converger avec elle par
QCM sur cette vue avant de poursuivre.

### Étape 25a - Construction de la vue d'ensemble

Appeler `run_efootprint.py::build_topology_overview(source_dir)` (chaîne :
`load_env_data` -> `find_har` -> `infer_audited_domain` -> `spec_from_env_data`
-> `detect_tech.detect_from_har` -> annotation des hôtes tiers suspects ->
`site_to_plantuml`). Ne dépend d'AUCUN paramètre de l'Étape 30 : le trafic a
toujours un défaut résolu (100 000/an) dès l'Étape 20.

**Préconditions** (si non réunies, informer et proposer de relancer l'Étape 20
avant de continuer) :
- un `.har` doit exister dans `source_dir` (ou son sous-dossier
  `donnees-brutes-potentiellement-sensibles/`)
- `env-data.json` doit contenir au moins un serveur détecté (`servers` non
  vide) — sinon `collect_env_data.py` n'a pas encore tourné avec ce HAR

`build_topology_overview()` lève `RuntimeError` avec un message actionnable
si une précondition manque : afficher ce message et proposer de relancer
l'Étape 20, jamais laisser remonter une trace brute.

### Étape 25b - Présentation texte

Afficher, dans cet ordre :
1. Le rappel "estimation hypothétique" (cf. AVERTISSEMENT OBLIGATOIRE en tête
   de fichier).
2. `print_hypotheses(spec)` (résumé des serveurs détectés, nombre d'étapes,
   trafic par défaut) — déjà existant, réutilisé À L'IDENTIQUE, AVANT tout
   ajustement --visits/--instance.
3. Le résumé de topologie (deuxième élément retourné par
   `build_topology_overview()`) :
   - Nombre et libellé des serveurs 1st-party détectés.
   - Services Backend-as-a-Service / BDD tiers suspectés (domaine exact
     reconnu -> "identifié" ; sinon -> "suspecté").
   - Streaming média suspecté (extension .m3u8/.mpd ou content-type
     vidéo/audio observé).
   - IA générative tierce identifiée (domaine d'API reconnu : OpenAI,
     Anthropic, Google Generative AI, Mistral AI, Cohere, Azure OpenAI,
     Hugging Face).
   - **Rappel honnête et systématique**, déjà inclus dans le texte généré :
     "une base de données ou un service auto-hébergé DERRIÈRE le serveur
     applicatif n'émet aucun signal visible depuis le trafic réseau
     capturé. Cette section ne peut donc JAMAIS conclure à son absence."
4. Toute réserve de calcul (`calculation_reserves(spec)`), à titre
   INFORMATIF uniquement à ce stade (jamais bloquant ici — elle ne bloque
   qu'à l'Étape 40).

### Étape 25c - Présentation graphique (PlantUML)

Priorité annoncée à l'utilisatrice : **d'abord l'interface web e-footprint**
(https://e-footprint.boavizta.org/model_builder/), qui reste la référence
visuelle si elle souhaite l'utiliser directement. **À défaut** (pour rester
autonome, sans dépendance lourde type Playwright), proposer le diagramme
PlantUML généré automatiquement (troisième élément retourné par
`build_topology_overview()`) :

1. Écrire le texte PlantUML dans `<source_dir>/topologie-<domaine>.puml`
   (fichier généré, non commité — cf. `.gitignore`).
2. Si `plantuml`/`rsvg-convert` sont disponibles dans l'environnement :
   générer le SVG puis le PDF (mêmes commandes que le skill
   `diagrammes-analyse-parcours`), et le montrer à l'utilisatrice.
   **PIÈGE** : `plantuml -tsvg` nomme le fichier de sortie d'après l'identifiant
   `@startuml <id>` du diagramme (ex. `site_octo_com.svg`), JAMAIS d'après le
   nom du fichier `.puml` d'entrée. Toujours renommer le SVG produit en
   `topologie-<domaine>.svg` juste après la génération (sinon
   `load_topology_svg()` dans `generate_report_html.py`, qui ne cherche que
   `topologie-*.svg`, ne le trouve pas et le rapport HTML retombe sur un SVG
   périmé ou reste sans diagramme).
3. Sinon : présenter le texte PlantUML brut dans la conversation (elle peut
   le coller dans https://www.plantuml.com/plantuml/uml/ pour un rendu
   ponctuel sans installation).

Contenu du diagramme (composants) : serveurs 1st-party (`database`),
traitements réseau, hôtes tiers — dont ceux annotés d'une suspicion
BDD/streaming/IA affichent leur note dans le label du composant.

### Étape 25d - Validation par QCM avant de poursuivre

Toujours converger avec l'utilisatrice avant l'Étape 30, via `AskUserQuestion` :

```
Question : "Voici le système que j'ai identifié à partir du parcours capturé.
            Correspond-il à ce que vous connaissez du site ?"
Header   : "Topologie détectée"
Options  :
  - Oui, cette topologie est correcte, on peut continuer - Recommandé
  - Non, il manque un serveur ou une infrastructure (préciser en réponse)
  - Non, une suspicion (BDD/streaming/IA) est fausse (préciser laquelle)
  - Je ne sais pas / je veux vérifier sur l'interface e-footprint avant
```

- **"Oui"** -> poursuivre vers l'Étape 30.
- **"Il manque une infrastructure"** -> noter l'infrastructure manquante
  (elle ne pourra pas être ajoutée automatiquement par ce lot, mais la
  garder en note pour un futur archétype manuel, ou signaler qu'elle sera
  absente du calcul).
- **"Suspicion fausse"** -> retirer/corriger la mention dans le résumé
  affiché à l'utilisatrice (ne PAS modifier le modèle e-footprint : cette
  étape s'arrête à la présentation, jamais à la construction automatique
  d'un `ExternalApiSpec` — cf. limite ci-dessous).
- **"Vérifier sur l'interface"** -> rappeler l'URL de l'interface web
  e-footprint et attendre son retour avant de poursuivre.

**Limite explicite de cette étape (à rappeler si l'utilisatrice s'attend à
plus) :** elle affiche des SUSPICIONS, elle ne construit JAMAIS
automatiquement un `ExternalApiSpec` ni un serveur BDD dédié dans le modèle
e-footprint (ce sera un lot ultérieur, distinct, non planifié). Le calcul
de l'Étape 40 reste, à ce stade, strictement identique à ce qu'il était
avant cette étape.

-----

## Étape 30 - Paramètres utilisateur

Les paramètres non auto-détectables sont demandés via `AskUserQuestion`.
**Toujours** rappeler qu'il s'agit d'hypothèses.

### Trafic annuel

**Priorité : réutiliser le volume déjà résolu à l'Étape 20c** (analytics client via
`--visits`, ou estimation SimilarWeb du bloc `traffic`). Ne poser la question ci-dessous
que si aucune source n'est disponible et qu'on doit tomber sur une hypothèse manuelle.

```
Question : "Quel trafic annuel hypothétique retenir pour l'estimation ?"
Header   : "Trafic estimé"
Options  :
  - 10 000 visites/an   (site vitrine, faible trafic)
  - 100 000 visites/an  (site actif, ordre de grandeur médian) - Recommandé
  - 500 000 visites/an  (site de contenu à trafic soutenu)
  - 1 000 000 visites/an (site à fort trafic)
```

Autoriser "Other" pour valeur libre. La valeur retenue est passée en `--visits`
(prioritaire sur le bloc `traffic`). Toujours rappeler qu'il s'agit d'une estimation.

### Type d'instance (uniquement si provider cloud détecté)

Si `env-data.json` contient un `server.detected_provider` dans
[aws, gcp, azure, scaleway, ovh] : demander l'instance.

```
Question : "Quelle taille d'instance {provider} supposer ?"
Header   : "Instance"
Options AWS :
  - t3.medium    (défaut, hypothèse petite prod) - Recommandé
  - t3.large
  - m5.large
  - m5.xlarge
```

Adapter la liste au provider détecté. Si provider inconnu ou non supporté :
`run_efootprint.py` bascule automatiquement sur `Server` générique
(pas de question à poser).

### Autres paramètres

Les autres paramètres (durée requête, poids page, mix device, pays)
sont **imposés par `env-data.json`**. Ne pas les demander -- si l'utilisateur
veut les modifier, il édite `env-data.json` puis relance.

**Mix appareils (mobile/desktop).** Collecté via CrUX (`form_factors`), puis :
- la **tablette est rattachée au mobile** ;
- **correction CrUX symétrique** (CrUX = Chrome only) : le mobile est regonflé de
  l'absence d'iOS (`mobile / (1 − part_iOS)`) ET le desktop de l'absence de macOS/Safari
  (`desktop / (1 − part_macOS)`), puis l'ensemble est renormalisé. Corriger aussi le
  desktop supprime le biais "pro-mobile" de l'ancienne correction unilatérale ;
- les parts iOS et macOS sont **pondérées par le mix pays d'audience** (Étape 20b).
  Override avancé de la seule part iOS : `collect_env_data.py --ios-mobile-share 0.45`.

Le mix pondère **réellement** le CO2e : le trafic est réparti en deux profils d'usage
(mobile → smartphone/réseau mobile, desktop → laptop/wifi). Le brut CrUX, les parts
iOS/macOS, le mix pays et sa provenance, la fourchette de scénarios et le split de
trafic sont tracés dans l'annexe du rapport.

-----

## Étape 40 - Calcul e-footprint

Lancer le script :

```bash
python3 .claude/skills/analyse-parcours/scripts/run_efootprint.py \
    <source_dir> \
    --visits <visits> \
    --instance <instance>
```

Le script :
1. Affiche le tableau des hypothèses (déjà géré, ne pas dupliquer)
2. Construit le modèle e-footprint
3. Affiche les résultats CO2e (fabrication + énergie)
4. Sérialise dans `<source_dir>/efootprint-model.json`

Capturer stdout pour le renvoyer à l'utilisateur en bloc, puis synthétiser.

-----

## Étape 50 - Synthèse et itération

Après affichage brut, produire une synthèse en 3 lignes :

```
Estimation CO2e (hypothèse {visits} visites/an, {instance}) :
- ~{total_kg} kg CO2e/an
- ~{per_visit_g} g CO2e/visite
- Poste dominant : {devices|server|network|storage}
```

Puis proposer via AskUserQuestion :
- **Relancer avec d'autres hypothèses** (nouveau trafic ou nouvelle instance)
- **Recollecte des données** (`--refresh` sur `collect_env_data.py`)
- **Regénérer le rapport HTML** (voir section "Intégration rapport HTML" ci-dessous)
- **Terminer**

Ne pas lancer d'itération automatique : c'est une boucle humain-dans-la-boucle.

-----

## Mode dégradé (sans HAR)

Si `source_dir` ne contient pas de HAR mais que l'utilisateur veut quand même
une estimation :

1. Signaler explicitement les champs qui vont être en défaut :
   - Poids de page : 500 kB (défaut lib)
   - Durée requête : 1000 ms (défaut lib)
   - Provider : inconnu -> Server générique
   - Mix device : 60/40 phone/desktop (défaut)
2. Demander confirmation avant de lancer
3. Ne pas prétendre à la précision : le résultat est un ordre de grandeur
   très grossier

-----

## Récapitulatif : commandes CLI équivalentes

Pour l'utilisateur qui préfère lancer les scripts en direct :

```bash
# Collecte (une fois, puis --refresh manuel)
python3 .claude/skills/analyse-parcours/scripts/collect_env_data.py <source_dir>
python3 .claude/skills/analyse-parcours/scripts/collect_env_data.py <source_dir> --refresh
python3 .claude/skills/analyse-parcours/scripts/collect_env_data.py <source_dir> --check
# Mix pays d'audience (pondère les parts iOS/macOS de la correction CrUX) :
python3 .claude/skills/analyse-parcours/scripts/collect_env_data.py <source_dir> --audience "FR:0.7,US:0.3"
python3 .claude/skills/analyse-parcours/scripts/collect_env_data.py <source_dir> --audience FR
# Override avancé de la seule part iOS (debug) :
python3 .claude/skills/analyse-parcours/scripts/collect_env_data.py <source_dir> --ios-mobile-share 0.45

# Calcul (relançable à volonté)
# Sans --visits : lit le bloc 'traffic' (SimilarWeb) d'env-data.json, sinon baseline 100k/an.
python3 .claude/skills/analyse-parcours/scripts/run_efootprint.py <source_dir>
# Avec --visits : force le trafic (analytics client), prioritaire sur le bloc 'traffic'.
python3 .claude/skills/analyse-parcours/scripts/run_efootprint.py <source_dir> --visits 500000 --instance t3.large
python3 .claude/skills/analyse-parcours/scripts/run_efootprint.py <source_dir> --refresh-data
```

-----

## Fichiers produits

Dans `<source_dir>/` :
- `env-data.json` - Données collectées (cache permanent, --refresh manuel)
- `efootprint-model.json` - Modèle e-footprint sérialisé complet (recréé à chaque run)
- `efootprint-results.json` - Totaux CO2e + hypothèses, format léger consommé par le rapport HTML

Ces fichiers **ne doivent pas être commités** dans git.

-----

## Intégration rapport HTML

Le générateur `generate_report_html.py` détecte automatiquement
`efootprint-results.json` (dans `audit_dir` ou son parent) et insère une
section "Impact environnemental (estimation CO2e)" dans le rapport, entre
"Analyse Core Web Vitals" et "Annexes". Si le fichier est absent, la section
est simplement omise (rapport rétro-compatible).

Contenu de la section :
- KPI en tête : total kg CO2e/an, g CO2e/visite, split fab/énergie
- Bandeau d'avertissement "estimation hypothétique"
- Décomposition par poste (Devices, Storage, Servers, Network, ...) avec barres
- Tableau des hypothèses d'entrée avec niveau de confiance
  (collecté / estimé / supposé / défaut lib)

Une **annexe méthodologique** (section "Méthodologie & hypothèses", dans les Annexes)
trace en plus, par domaine (A: CO2e, B: CWV, C: EcoIndex, D: trafic), toutes les données
et hypothèses : mix brut CrUX, parts iOS ET macOS avec leurs sources, mix pays d'audience
et sa provenance (SimilarWeb estimé / saisie / défaut FR) avec détail par pays,
rattachement tablette→mobile, fourchette de scénarios, split du trafic mobile/desktop,
et pour les CWV la stratégie "pire des deux" par métrique. Formules appliquées incluses.

Régénération après changement d'hypothèses :
```bash
python3 .claude/skills/analyse-parcours/scripts/run_efootprint.py <source_dir> --visits N
python3 .claude/skills/analyse-parcours/scripts/generate_report_html.py <source_dir>/audit
```

-----

## Décisions clés (référence)

- e-footprint : librairie Python uniquement (pas d'API REST), sortie CO2e uniquement
- Approche générique : pas limité à octo.com, applicable à tout site web
- Cache `env-data.json` : jamais expiré automatiquement (--refresh manuel)
- Trafic annuel : résolu par priorité `--visits` (analytics) > bloc `traffic` SimilarWeb
  (écrit par l'agent, jamais scrapé par le script) > baseline 100 000/an + avertissement
  (voir Étape 20c). Le total CO2e croît avec le trafic ; le CO2e/visite en dépend peu.
- Rappel "estimation hypothétique" obligatoire sur chaque paramètre et sur les résultats
- IPINFO_TOKEN pas provisionné : mode anonyme accepté (50k req/mois)
