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

## Utilisation

Deux commandes, dans l'ordre :

```bash
cd "/Users/pierrick.crepy/Documents/missions/MyAIEnv/Agent EROOM"

# 1. Récupère trafic + mix pays et écrit les blocs audience/traffic dans env-data.json
python3 .claude/skills/analyse-parcours/scripts/similarweb_api.py <source_dir> [--domain octo.com]

# 2. Normalise ces blocs et les intègre au calcul CO2e
python3 .claude/skills/analyse-parcours/scripts/collect_env_data.py <source_dir> --refresh
```

Options du premier script :

- `--domain octo.com` : force le domaine. Sinon il est déduit de `env-data.json` (ou du `.har`).
- `--print-only` : affiche le JSON brut renvoyé par l'API et n'écrit rien (utile pour inspecter).

Le script écrit uniquement les blocs `audience` et `traffic` ; il ne touche à rien d'autre dans
`env-data.json` (HAR, device, serveur préservés).

-----

## Repli si l'API échoue

Si l'appel échoue (403 réapparu, domaine inconnu de SimilarWeb, coupure réseau), le script sort
en code d'erreur `2` avec un message explicite, sans rien écrire ni corrompre le fichier existant.

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
- Ordre de priorité des sources : analytics client > API interne SimilarWeb > WebFetch de la page
  > récupération assistée (captcha) > défauts (France 100 %, 100 000 visites/an).
- Si l'API se remet à renvoyer 403 : vérifier l'absence d'en-tête `Origin`, la présence d'un
  User-Agent navigateur, et revalider la valeur de `EXTENSION_VERSION` (installer/mettre à jour
  l'extension, relever la version courante dans `chrome://extensions`).
