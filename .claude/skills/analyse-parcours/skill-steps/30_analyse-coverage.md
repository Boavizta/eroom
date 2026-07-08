# Étape 30 — Analyse des fichiers de couverture

> Source : skill-steps/30_analyse-coverage.md. Retour : SKILL.md étape 40.

## Format des fichiers Coverage Chrome

Chaque fichier JSON contient un tableau d'entrées. Deux formats possibles selon la version de Chrome DevTools :

**Format A (tableau direct)** :
```json
[
  {
    "url": "https://example.com/app.js",
    "ranges": [...],
    "text": "..."
  }
]
```

**Format B (enveloppé)** :
```json
{
  "timestamp": 1234567890,
  "entries": [
    {
      "url": "https://example.com/app.js",
      "ranges": [...],
      "text": "..."
    }
  ]
}
```

Détecter le format avant de lire.

## 30a — Métriques par page

Pour chaque fichier Coverage JSON :

1. **Identifier la page** : extraire depuis le nom de fichier (ex: `Coverage-20260328T105137_page 1.json` -> "Page 1") ou depuis les URLs présentes dans les entrées
2. Pour chaque entrée :
   - `tailleTotal` = longueur du texte source (`text.length`)
   - `tailleUtilisee` = somme des plages `ranges` (end - start)
   - `tailleInutilisee` = tailleTotal - tailleUtilisee
3. Agréger par type MIME (JS / CSS / autre)

Tableau par page :
```
Page [N] — [URL ou nom]
  JS  : [X Ko] total, [Y Ko] inutilisé ([Z%])
  CSS : [X Ko] total, [Y Ko] inutilisé ([Z%])
  Total : [X Ko] total, [Y Ko] inutilisé ([Z%])
```

## 30b — Fichiers les plus coûteux

Top 5 fichiers JS par taille inutilisée (nom court + taille) :
```
1. vendor-xxxx.js          1 600 Ko inutilisés
2. chunk.709.js              980 Ko inutilisés
...
```

Top 3 fichiers CSS par taille inutilisée.

Identifier les librairies tierces reconnaissables :
- Analytics : Google Analytics, Matomo, Kameleoon, AT Internet
- Chatbots : tolk.ai, Intercom, Zendesk
- A/B testing : Kameleoon, AB Tasty, Optimizely
- CAPTCHA : reCAPTCHA, hCaptcha, LiveIdentity
- Frameworks UI : Bootstrap, Tailwind, DSFR (Design Système FR)

## 30c — Synthèse multi-pages

Agréger tous les fichiers :

```
Synthèse couverture — [N] pages analysées
-----
Total JS chargé    : [X Mo]
Total JS inutilisé : [Y Mo] ([Z%])
Total CSS chargé   : [X Ko]
Total CSS inutilisé: [Y Ko] ([Z%])
-----
Évolution page à page :
  Page 1 : [X Ko] inutilisés
  Page 2 : [X Ko] inutilisés (+[delta] vs page 1)
  ...
```

Signaler si une page charge significativement plus de code que les autres (outlier > 2x la médiane).
