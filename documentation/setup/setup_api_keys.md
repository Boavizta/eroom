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
```

-----

## Google API Key (PageSpeed Insights + Chrome UX Report)

**Coût** : gratuit (quotas largement suffisants pour un usage ponctuel)
**Utilisé pour** : Core Web Vitals terrain réels (LCP, INP, CLS) via PageSpeed Insights + CrUX

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

## IPInfo Token (géolocalisation IP) — Phase 2, non implémenté

Non nécessaire actuellement. Prévu pour détecter le pays et le fournisseur d'hébergement
depuis l'IP du serveur. Gratuit jusqu'à 50 000 requêtes/mois (https://ipinfo.io).
À ajouter dans `.env` sous la forme `IPINFO_TOKEN=ton_token_ici` quand la Phase 2 sera lancée.
