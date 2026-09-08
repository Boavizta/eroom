# Provisionnement des clés API - Agent EROOM

Ce document explique comment obtenir les clés API nécessaires.

**Chaque personne qui reprend le projet crée sa propre clé, dans son propre compte Google
personnel.** Rien n'est partagé : `.env` est local à chaque machine et jamais versionné (voir
section Sécurité). Il ne s'agit donc pas de demander l'accès au projet GCP existant de qui a
travaillé avant, mais de refaire les étapes ci-dessous depuis zéro, avec son propre compte.

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

### Projet GCP à créer

Nom de projet suggéré : **"Google API Key for Agent EROOM"** (ou tout autre nom, c'est un
projet perso, le nom n'est pas structurant). Nom de clé suggéré : **"Clé API GOOGLE pour Agent
EROOM"**.

### ⚠️ Piège fréquent — mauvais compte Google connecté

Si tu utilises Chrome/un navigateur avec plusieurs comptes Google (perso + pro/organisation),
la console peut s'ouvrir sur ton compte **professionnel** par défaut. Symptômes observés :
- le sélecteur de projet ("Aucune organisation" / nom d'organisation) ne montre que des projets
  d'entreprise sans rapport avec ce besoin ;
- cliquer "Activer" déclenche "Nous avons essayé de créer un projet... vous ne disposez pas des
  autorisations nécessaires pour créer un projet dans cette organisation" ;
- sur un projet existant de l'organisation, la fiche API affiche "Vous ne disposez pas des
  autorisations nécessaires pour vérifier l'état d'activation de ce produit."

**Changer de profil Chrome ne suffit pas forcément** (le profil peut rester connecté au même
compte Google). La solution qui fonctionne : cliquer sur l'avatar en haut à droite de
`console.cloud.google.com` → choisir explicitement ton **compte Google personnel** (ou ouvrir
une fenêtre de navigation privée et te connecter avec ce compte). Une fois sur le bon compte, le
sélecteur de projet doit proposer de créer un nouveau projet perso sans blocage d'organisation.

### Étape 1 — Activer les deux APIs (AVANT de créer la clé)

1. Aller sur https://console.cloud.google.com, connecté avec ton compte Google **personnel**
   (voir piège ci-dessus si le bon compte n'apparaît pas)
2. Créer un nouveau projet (ou sélectionner celui déjà créé pour ce besoin)
3. Menu gauche : "API et services" → "Bibliothèque"
4. Chercher **"PageSpeed Insights API"** → Activer
5. Revenir à la bibliothèque, chercher **"Chrome UX Report API"** → Activer

### Étape 2 — Créer la clé

6. Menu gauche : "API et services" → "Identifiants"
7. Cliquer "+ Créer des identifiants" → "Clé API"
8. Nommer la clé : `Clé API GOOGLE pour Agent EROOM` (ou tout autre nom, libre)
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
.venv/bin/python3 .claude/skills/analyse-parcours/scripts/collect_cwv_pagespeed.py audits/octo.com/audit --check
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
.venv/bin/python3 .claude/skills/analyse-parcours/scripts/collect_env_data.py audits/octo.com --check
```

`--check` teste à la fois l'accès CrUX (clé Google) et ipinfo (token).
