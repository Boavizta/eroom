# Étape 40 — Rapport de synthèse HTML

> Source : skill-steps/40_rapport.md. Retour : SKILL.md (fin).

## Génération du rapport HTML

Appeler le script Python :

```bash
python3 .claude/skills/analyse-parcours/scripts/generate_report_html.py <dossier-audit>
```

Le script lit le `.har`, les `Coverage-*.json` et le `cwv.json` optionnel depuis le dossier.
Il produit `rapport-parcours-YYYY-MM-DD.html` dans ce même dossier.

## Structure du rapport HTML (sections dans l'ordre)

### En-tête (couverture)
- Titre, date, domaines analysés, nb pages, fichiers source

### Tableau de bord EcoIndex
Tableau par page avec : grade coloré (A-G), score /100, requêtes, poids (Ko), DOM, LCP/onLoad, INP, CLS
- Source : `har_metrics.py` (étape 35)
- Si `cwv.json` absent : LCP affiché = onLoad HAR avec note explicite

### Section 1 — Trafic réseau
- KPIs : requêtes totales, volume transféré, nb domaines
- Domaines contactés (tags visuels)
- Codes HTTP (colorés : vert/orange/rouge)
- Top 10 ressources les plus lourdes
- Requêtes dupliquées (si présentes)

### Section 2 — Code mort (Coverage)
Par page Coverage :
- Jauges visuelles JS et CSS (barre rouge/vert)
- Tableau top 8 fichiers par code non utilisé (taille totale, Ko inutilisés, %, barre)

### Section 3 — Core Web Vitals
Affiché uniquement si `cwv.json` fourni.
- Tableau par page : LCP, INP, CLS avec code couleur (vert/orange/rouge selon seuils Google)

### Section 4 — Recommandations
- PRIORITÉ 1 (fond rouge) : EcoIndex < 40, DOM > 1500, code mort JS > 70%
- PRIORITÉ 2 (fond orange) : EcoIndex 40-55, DOM 800-1500, doublons, code mort JS 50-70%
- PRIORITÉ 3 (fond vert) : Brotli, CDN, librairies tierces légères

## Fichier de sortie

Le script génère :
```
<dossier-audit>/rapport-parcours-YYYY-MM-DD.html
```

Indiquer le chemin du fichier généré en fin de réponse.
