# Capturer un fichier HAR et les données de couverture Chrome

**Objectif** : Capturer l'intégralité du trafic réseau et du code chargé lors d'un parcours web,
pour une analyse d'écoresponsabilité et de performance.

## Table des matières

- [Prérequis](#prérequis)
- [Partie 1 - Capturer le fichier HAR](#partie-1---capturer-le-fichier-har)
  - [Étape 1 - Nettoyage préalable](#étape-1---nettoyage-préalable)
  - [Étape 2 - Préparer l'onglet Network](#étape-2---préparer-longlet-network)
  - [Étape 3 - Effectuer le parcours](#étape-3---effectuer-le-parcours)
  - [Étape 4 - Exporter le HAR](#étape-4---exporter-le-har)
  - [Étape 5 - Vérifier le fichier HAR](#étape-5---vérifier-le-fichier-har)
- [Partie 2 - Capturer les données de couverture (Coverage)](#partie-2---capturer-les-données-de-couverture-coverage)
  - [Étape 1 - Ouvrir le panneau Coverage](#étape-1---ouvrir-le-panneau-coverage)
  - [Étape 2 - Capturer une page](#étape-2---capturer-une-page)
  - [Étape 3 - Exporter le fichier Coverage](#étape-3---exporter-le-fichier-coverage)
  - [Étape 4 - Répéter pour chaque page](#étape-4---répéter-pour-chaque-page)
  - [Étape 5 - Vérifier les fichiers Coverage](#étape-5---vérifier-les-fichiers-coverage)

## Table des matières (étendue)

- [Partie 3 - Obtenir les Core Web Vitals (optionnel)](#partie-3---obtenir-les-core-web-vitals-optionnel)
  - [Option A - Lighthouse automatique (recommandé)](#option-a---lighthouse-automatique-recommandé)
  - [Option B - cwv.json manuel (RUM / PageSpeed)](#option-b---cwvjson-manuel-rum--pagespeed)

-----

## Prérequis

- Navigateur Chrome ou Chromium (Brave, Edge...) avec DevTools disponible
- Connexion réseau stable (éviter Wi-Fi instable ou 4G lente)
- 15-30 min sans interruption
- Parcours défini à l'avance : liste des pages et étapes à visiter
- URL de départ connue

-----

## Partie 1 - Capturer le fichier HAR

### Étape 1 - Nettoyage préalable

Ces étapes garantissent une capture fidèle du premier chargement, sans ressources en cache.

**Option A - Nettoyage global (recommandé) :**
1. `Cmd+Shift+Delete` (macOS) ou `Ctrl+Shift+Delete` (Windows/Linux)
2. Cocher : Cookies, Images et fichiers en cache, Données de formulaire
3. Sélectionner "Toutes les périodes"
4. Cliquer "Supprimer les données"
5. Fermer Chrome complètement puis le rouvrir

**Option B - Nettoyage ciblé dans DevTools :**
1. Ouvrir DevTools (`F12` ou `Cmd+Option+I`)
2. Aller dans Application > Storage
3. Cliquer "Clear site data"
4. Recharger la page

-----

### Étape 2 - Préparer l'onglet Network

1. Ouvrir Chrome (aucune autre fenêtre si possible)
2. Appuyer sur `F12` ou `Cmd+Option+I` pour ouvrir DevTools
3. Aller dans l'onglet **Network**
4. Cocher **"Preserve log"** - CRUCIAL : sans cette option, les requêtes s'effacent à chaque navigation
5. Dans Settings (engrenage en haut à droite), cocher **"Disable cache"** - force le rechargement de toutes les ressources

-----

### Étape 3 - Effectuer le parcours

**Phase 1 - Chargement initial :**
1. Saisir l'URL racine dans la barre d'adresse
2. Appuyer sur `Cmd+R` / `Ctrl+R` pour forcer un rechargement complet
3. Attendre 3-5 secondes que la page se stabilise (plus aucune nouvelle requête)

**Phase 2 - Activer les ressources lazy-loaded :**
1. Scroller lentement de haut en bas sur la page entière
2. Interagir avec la page : boutons, menus, accordéons, onglets (sans saisir de données sensibles)
3. Attendre 2-3 secondes après chaque interaction

**Phase 3 - Naviguer entre les pages du parcours :**
1. Pour chaque étape, cliquer le lien ou bouton suivant
2. Attendre 3-5 sec que la page se charge
3. Répéter scroll + interactions (Phase 2)
4. Continuer pour toutes les pages prévues

**Phase 4 - Finalisation :**
1. Rester sur la dernière page 5-10 secondes supplémentaires
   (laisse le temps aux analytics et beacons de s'exécuter)
2. Vérifier que le compteur de requêtes Network est stable

-----

### Étape 4 - Exporter le HAR

1. Clic-droit n'importe où dans la liste des requêtes Network
2. Sélectionner **"Save all as HAR with content"** (ou "Export as HAR")
   - L'option "with content" inclut les payloads complets des réponses - nécessaire pour l'analyse
3. Nommer le fichier : `audit_<nom-site>_YYYY-MM-DD.har`
4. Sauvegarder dans le dossier du projet

-----

### Étape 5 - Vérifier le fichier HAR

Le fichier `.har` est un JSON standard. Ouvrir dans un éditeur texte et vérifier :

- `log.entries` contient bien des centaines d'objets (une requête = un objet)
- Plusieurs types de ressources présents : HTML, JS, CSS, images, requêtes XHR/Fetch, polices
- Les headers HTTP sont complets (`request.headers`, `response.headers`)
- Chaque entrée a ses timings (`blocked`, `dns`, `connect`, `send`, `wait`, `receive`)

Structure JSON attendue :
```json
{
  "log": {
    "version": "1.2",
    "entries": [
      {
        "startedDateTime": "2026-04-09T10:30:45.123Z",
        "request": { "method": "GET", "url": "...", "headers": [...] },
        "response": { "status": 200, "headers": [...], "content": { "size": ..., "text": "..." } },
        "timings": { "blocked": ..., "dns": ..., "connect": ..., "send": ..., "wait": ..., "receive": ... }
      }
    ]
  }
}
```

**Tableau récapitulatif des étapes critiques :**

| Étape | Action | Pourquoi |
|-------|--------|----------|
| 1 - Nettoyage | Vider caches et cookies | Capture fidèle du premier chargement |
| 2 - Preserve log | Cocher en début | Accumule toutes les requêtes du parcours |
| 2 - Disable cache | Cocher dans Settings | Force le re-téléchargement de toutes les ressources |
| 3 - Scroll complet | Lentement, haut en bas | Active les lazy-loads |
| 3 - Attendre | 3-5 sec par page + 5 sec à la fin | Laisse le temps aux requêtes asynchrones |
| 4 - "with content" | Exporter avec payloads | Nécessaire pour analyser les tailles réelles |

-----

## Partie 2 - Capturer les données de couverture (Coverage)

La couverture mesure quelle partie du code JS et CSS est réellement exécutée lors du chargement
d'une page. Un fichier JSON par page.

### Étape 1 - Ouvrir le panneau Coverage

1. Dans DevTools, appuyer sur `Cmd+Shift+P` (macOS) ou `Ctrl+Shift+P` (Windows/Linux)
2. Taper `coverage` et sélectionner **"Show Coverage"**
3. Le panneau Coverage s'ouvre en bas de DevTools

### Étape 2 - Capturer une page

1. Dans le panneau Coverage, cliquer le bouton rond (enregistrement) pour démarrer
2. Recharger la page (`Cmd+R` / `Ctrl+R`)
3. Attendre que la page soit complètement chargée (3-5 secondes)
4. Scroller la page en entier pour déclencher les lazy-loads
5. Cliquer le bouton rond à nouveau pour arrêter l'enregistrement

### Étape 3 - Exporter le fichier Coverage

1. Dans le panneau Coverage, cliquer l'icône de téléchargement (flèche vers le bas)
2. Nommer le fichier : `Coverage-YYYY-MM-DD_page-N.json`
   - Exemple : `Coverage-2026-04-09_page-1.json`
3. Sauvegarder dans le dossier du projet

### Étape 4 - Répéter pour chaque page

Répéter les étapes 2-3 pour chaque page du parcours :
- Cliquer le bouton d'enregistrement
- Naviguer vers la page suivante (ou la recharger)
- Attendre + scroller
- Arrêter + exporter

**Important :** un fichier JSON par page. Ne pas accumuler plusieurs pages dans un seul fichier Coverage.

### Étape 5 - Vérifier les fichiers Coverage

Chaque fichier doit contenir un tableau d'objets avec au minimum :

```json
[
  {
    "url": "https://example.com/app.js",
    "ranges": [
      { "start": 0, "end": 1234 }
    ],
    "text": "/* contenu du fichier JS ou CSS */"
  }
]
```

- `url` : URL de la ressource JS ou CSS
- `ranges` : plages de code effectivement exécutées/utilisées
- `text` : contenu source complet (permet de calculer la taille totale)

Le taux de code inutilisé se calcule ainsi :
```
inutilise = longueur(text) - somme(range.end - range.start)
taux (%)  = inutilise / longueur(text) x 100
```

-----

## Partie 3 - Core Web Vitals

Les Core Web Vitals (LCP, INP, CLS) ne sont pas dans le HAR.

**Automatique :** `/analyse-parcours` lance Lighthouse via `npx` automatiquement si `cwv.json`
est absent. Prérequis : Node.js installé (`node -v` doit répondre). Pages publiques uniquement
(Chrome headless, pas d'authentification).

Pour forcer un re-run : dire "relance Lighthouse" à Claude.

**Données terrain réelles (optionnel) :** si vous avez des données RUM ou PageSpeed Insights,
créer `cwv.json` manuellement dans le dossier d'audit. Le skill détecte le fichier et skippa
Lighthouse.

Format :
```json
[
  {"page": "page_1", "lcp": 0.76, "inp": 8,  "cls": 0.06},
  {"page": "page_2", "lcp": 1.9,  "inp": 16, "cls": 0.66}
]
```
- `page` : ID HAR (`page_1`, `page_2`...)
- `lcp` : secondes, `inp` : millisecondes, `cls` : sans unité
