# Provisionnement des clés API - Agent EROOM

Ce document explique comment obtenir les clés API nécessaires.

-----

## Sécurité - règle absolue

Les clés API sont des informations privées. Ne jamais les diffuser ni les commiter dans git.

Elles se placent uniquement dans le fichier `.env` à la racine du projet :

```
/Users/pierrick.crepy/Documents/missions/MyAIEnv/Agent EROOM/.env
```

Ce fichier est dans `.gitignore` : il ne sera jamais versionné. Ne jamais copier une clé
dans un `.md`, un script, ou tout autre fichier versionné.

-----

## Format du fichier .env

```
GOOGLE_API_KEY=ta_cle_ici
IPINFO_TOKEN=ton_token_ici   # optionnel : voir section IPInfo
```

Les scripts ne chargent pas le `.env` via `python-dotenv` : ils le parsent eux-mêmes
(fonction `load_env` dans `collect_env_data.py`, lecture ligne à ligne `clé=valeur`).

-----

## Google API Key (PageSpeed Insights + Chrome UX Report)

**Coût** : gratuit (quotas largement suffisants pour un usage ponctuel)
**Utilisé pour** : Core Web Vitals terrain réels (LCP, INP, CLS) via PageSpeed Insights + CrUX

**Une seule clé, deux APIs, deux scripts** : la même `GOOGLE_API_KEY` sert deux scripts distincts.
- `collect_cwv_pagespeed.py` appelle l'**API PageSpeed Insights** (`pagespeedonline/v5/runPagespeed`).
  Les données CrUX qu'il exploite sont extraites de la réponse PageSpeed, il n'interroge pas
  directement l'API Chrome UX Report.
- `collect_env_data.py` appelle l'**API Chrome UX Report** (`chromeuxreport.googleapis.com`)
  en plus de sa collecte HAR / ipinfo.

Les deux APIs doivent donc bien être activées (voir Étape 1), mais elles ne sont pas appelées
par le même script.

### Projet GCP utilisé

Nom du projet : **"Google API Key for Agent EROOM"**
Nom de la clé : **"Clé API pour Agent EROOM"**

### Étape 1 — Activer les deux APIs (AVANT de créer la clé)

1. Aller sur https://console.cloud.google.com
2. Sélectionner le projet "Google API Key for Agent EROOM"
3. Menu gauche : "API et services" → "Bibliothèque"
4. Chercher **"PageSpeed Insights API"** → Activer
5. Revenir à la bibliothèque, chercher **"Chrome UX Report API"** → Activer

### Étape 2 — Créer la clé

6. Menu gauche : "API et services" → "Identifiants"
7. Cliquer "+ Créer des identifiants" → "Clé API"
8. Nommer la clé : `Clé API pour Agent EROOM`
9. Dans "API accessibles à l'aide de cette clé" : cliquer sur "Sélectionner des restrictions d'API"
   - Taper "PageSpeed" dans le filtre → cocher **"PageSpeed Insights API"**
   - Effacer, taper "Chrome UX" → cocher **"Chrome UX Report API"**
   - Cliquer OK
10. Cliquer **"Créer"**
11. Copier la clé affichée dans le pop-up → la coller dans `.env`

### Quotas gratuits

- PageSpeed Insights API : 25 000 requêtes/jour
- Chrome UX Report API : 150 requêtes/minute, pas de limite journalière

### Vérifier que la clé fonctionne

```bash
cd "/Users/pierrick.crepy/Documents/missions/MyAIEnv/Agent EROOM"
.venv/bin/python3 .claude/skills/analyse-parcours/scripts/collect_cwv_pagespeed.py octo.com/audit --check
```

-----

## IPInfo Token (géolocalisation IP) — implémenté, optionnel

**Coût** : gratuit jusqu'à 50 000 requêtes/mois (https://ipinfo.io)
**Utilisé pour** : détecter le pays et le fournisseur d'hébergement depuis l'IP du serveur.
Le pays alimente le mix électrique, donc l'intensité carbone du calcul CO2e ; le provider
fiabilise le choix d'instance Boavizta.

Cette fonctionnalité est **active en production**, pas en attente : `collect_env_data.py`
appelle ipinfo.io à chaque run (étape "[3/3] Géolocalisation serveur (ipinfo.io)", fonctions
`call_ipinfo` / `collect_server_info`).

Le token est **optionnel** : s'il est absent, le script bascule en **mode anonyme** (quota
réduit, 50 000 req/mois partagés par IP publique) et fonctionne quand même, sans crasher.
Le fournir dans `.env` (`IPINFO_TOKEN=ton_token_ici`) débloque le quota nominal du compte.

### Vérifier la clé Google ET le token ipinfo d'un coup

```bash
cd "/Users/pierrick.crepy/Documents/missions/MyAIEnv/Agent EROOM"
.venv/bin/python3 .claude/skills/analyse-parcours/scripts/collect_env_data.py octo.com --check
```

`--check` teste à la fois l'accès CrUX (clé Google) et ipinfo (token).
