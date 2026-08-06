# Étape 30 — Analyse des fichiers de couverture

> Source : skill-steps/30_analyse-coverage.md. Retour : SKILL.md étape 40.

## Exécution — un script, pas un calcul à la main

```bash
.venv/bin/python3 .claude/skills/analyse-parcours/scripts/coverage_metrics.py <dossier-source>
```

Le script écrit `<dossier-source>/audit/coverage-analysis.json`. Option `--check`
pour comparer à la sortie existante sans rien réécrire.

**Ne pas recalculer ces agrégats à la main.** Deux fautes en sont venues :

1. L'extension se lit sur le **chemin** de l'URL, jamais sur l'URL entière. Une
   URL versionnée (`dsfr.min.css?version=39.2.0`) ne se termine pas par son
   extension : un test `url.endswith(".css")` la classe en "autre". Une page dont
   *toutes* les URLs sont versionnées est alors publiée à **zéro Ko**, ce qui ne
   ressemble pas à une erreur mais à une page sans code. C'est arrivé sur la 4e
   page d'une téléprocédure, celle qui chargeait le plus de CSS.
2. Le libellé d'une page vient de l'URL du **document réellement servi en
   `text/html`**, corroborée par le HAR. Sans cela, la première URL sans
   extension d'asset l'emporte : sur une téléprocédure, c'est souvent une URL
   technique (jeton anti-CSRF), et la page s'affiche sous un nom qui n'est pas
   celui de l'écran vu par l'usager.

Les contrôles de non-régression : `check_coverage_metrics.py` (28 contrôles).

La section ci-dessous documente le **format** des fichiers lus et la **forme** de
la sortie attendue. Elle ne redevient une consigne de calcul que si le script est
indisponible.

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
