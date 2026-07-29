# Récupération SimilarWeb via l'API interne - Agent EROOM

Ce document explique comment le projet récupère le trafic et le mix pays d'audience
d'un site, sans passer par le site web SimilarWeb (bloqué par captcha).

-----

## But

Deux données ne sont fournies par aucune API publique (ni PageSpeed, ni CrUX) :

- le **volume de trafic** (visites par mois / par an) ;
- le **mix pays d'audience** (répartition des visiteurs par pays).

SimilarWeb les estime. La page web publique `https://www.similarweb.com/website/<domaine>/`
est protégée par un captcha à sélection d'images (challenge AWS WAF), qui bloque tout accès
automatisé. On récupère donc ces données autrement.

-----

## Méthode retenue

Le script `similarweb_api.py` appelle directement l'**API interne de l'extension Chrome/Firefox
SimilarWeb**, en imitant les requêtes que l'extension fait en arrière-plan. On ne scrape plus
la page web : on rejoue l'appel API en Python.

- Endpoint : `https://data.similarweb.com/api/v1/data?domain=<domaine>` (GET)
- En-têtes suffisants :
  - `Content-Type: application/json`
  - `X-Extension-Version: 6.12.21` (version de l'extension, cf. constante `EXTENSION_VERSION`)
  - un vrai `User-Agent` de navigateur

Point important : **aucun cookie, aucun compte, aucune session** n'est nécessaire. L'API répond
directement en JSON, d'où on extrait `TopCountryShares` (mix pays), `EstimatedMonthlyVisits`
et `Engagments` (visites).

-----

## Diagnostic du 403 (piège historique)

Une première investigation avait conclu à tort qu'il fallait des cookies de session : l'API
renvoyait un 403. En réalité, le 403 venait de deux erreurs dans la requête de test, pas d'un
manque d'authentification :

1. Un en-tête `Origin: chrome-extension://...` : CloudFront le rejette. **Ne pas l'envoyer.**
2. L'absence d'un vrai `User-Agent` de navigateur (le User-Agent par défaut d'un client HTTP
   est bloqué). **Toujours envoyer un User-Agent navigateur.**

Sans en-tête `Origin` et avec un User-Agent navigateur, l'appel répond 200 depuis un simple
client HTTP.

-----

## Comment ce module a été construit (via HAR)

Le module n'a pas été deviné : il a été bâti en **observant l'extension SimilarWeb en
fonctionnement**, en capturant son appel réseau (export HAR), puis en rejouant cette requête
en Python. L'extension étant en Manifest V3, l'appel part de son **service worker** : on le
capture via `chrome://extensions` (mode développeur > "service worker" > Network), pas dans le
Network de l'onglet du site. C'est le HAR qui a révélé l'URL, les en-têtes (dont l'absence
d'`Origin`) et la forme du JSON de réponse, d'où sont tirés les champs parsés
(`TopCountryShares`, `EstimatedMonthlyVisits`, `Engagments`).

Récit de genèse détaillé + procédure de capture pas-à-pas : voir
`similarweb_reconstitution.md` (Méthode B - Capture HAR).

-----

## Utilisation

L'appel est **intégré à `collect_env_data.py`** : une seule commande suffit. Quand un bloc
`audience` ou `traffic` manque dans `env-data.json`, le script interroge lui-même l'API interne
SimilarWeb (via le module frère `similarweb_api.py`), écrit les blocs manquants, puis les normalise
et les intègre au calcul CO2e.

```bash
cd "/Users/pierrick.crepy/Documents/missions/MyAIEnv/Agent EROOM"

# Une commande : collecte HAR/CrUX/ipinfo + appel auto SimilarWeb si audience/traffic manquent
python3 .claude/skills/analyse-parcours/scripts/collect_env_data.py <source_dir> --refresh
```

Options associées (sur `collect_env_data.py`) :

- `--sw-domain octo.com` : force le domaine interrogé. Sinon déduit de `env-data.json` (ou du `.har`).
- `--no-similarweb` : désactive l'appel automatique (mode hors-ligne / éviter le réseau).
- `--audience "FR:0.7,US:0.3"` : saisie manuelle du mix pays ; **prime** sur SimilarWeb (l'API
  n'écrit alors pas le mix, mais peut toujours compléter le trafic).

Déclenchement et garde-fous :

- L'appel n'a lieu que si le bloc visé **manque** (absent, ou `source` = `default`/`None`).
- Un bloc déjà présent avec une vraie source n'est **jamais écrasé** (idempotent sur `--refresh`).
- L'appel écrit uniquement les blocs `audience`/`traffic` manquants ; il ne touche à rien d'autre
  dans `env-data.json` (HAR, device, serveur préservés).

Le module `similarweb_api.py` reste utilisable **en standalone** pour inspection :

```bash
python3 .claude/skills/analyse-parcours/scripts/similarweb_api.py <source_dir> [--domain octo.com] [--print-only]
```

- `--domain octo.com` : force le domaine. Sinon déduit de `env-data.json` (ou du `.har`).
- `--print-only` : affiche le JSON brut renvoyé par l'API et n'écrit rien (utile pour inspecter).

-----

## Repli si l'API échoue

Si l'appel échoue (403 réapparu, domaine peu/pas suivi par SimilarWeb, coupure réseau),
`collect_env_data.py` affiche un message `⚠ SimilarWeb : …` puis **continue sans crasher** : il
n'écrit pas le bloc concerné et poursuit avec les blocs disponibles ou les défauts.

Note : l'API répond 200 même pour un domaine inconnu (elle fait écho au nom), mais sans
`TopCountryShares` ni visites exploitables → les blocs ne sont pas construits, avec un message
explicite (pas de repli silencieux). En standalone, `similarweb_api.py` sort en code `2` dans ce cas.

Dans ce cas, basculer sur la **récupération assistée** (skill efootprint, Étape 20d) : l'agent
demande à l'utilisatrice d'ouvrir la page SimilarWeb, de passer le captcha et de lui transmettre
les chiffres (dictée ou capture d'écran).

-----

## Libellé et vérification dans le rapport

- Le rapport affiche la source sous le libellé neutre **"SimilarWeb (estimation)"** : il n'expose
  pas la méthode technique (API interne). La description technique reste dans cette doc et le code.
- Le rapport fournit un lien de vérification "↗ source" vers la **page web lisible**
  `https://www.similarweb.com/website/<domaine>/`, pour que le lecteur puisse contrôler les
  chiffres lui-même. Ce n'est jamais l'URL de l'API (qui renvoie du JSON illisible).

-----

## Caveats et robustesse

- SimilarWeb est une **estimation tierce à marge large**, source non officielle, dont l'usage
  automatisé est à la limite des CGU. Seuls les analytics du site (GA4, Matomo, logs serveur)
  donnent des chiffres exacts ; ils sont prioritaires (`--audience` / `--visits`).
- Ordre de priorité des sources : analytics client (`--audience`/`--visits`) > API interne
  SimilarWeb (automatique) > récupération assistée après captcha (Étape 20d) > défauts
  (France 100 %, 100 000 visites/an). La voie WebFetch de la page publique a été retirée
  (systématiquement bloquée par le captcha, rendue inutile par l'API interne).
- Si l'API se remet à renvoyer 403 : vérifier l'absence d'en-tête `Origin`, la présence d'un
  User-Agent navigateur, et revalider la valeur de `EXTENSION_VERSION` (installer/mettre à jour
  l'extension, relever la version courante dans `chrome://extensions`).
- Si une simple revalidation de version ne suffit pas (endpoint ou en-têtes changés), refaire la
  découverte de zéro : voir le guide de reconstitution `similarweb_reconstitution.md`
  (récupération de l'extension, extraction de l'endpoint/en-têtes/version, vérification).
