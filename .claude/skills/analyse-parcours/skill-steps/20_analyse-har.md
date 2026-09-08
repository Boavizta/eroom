# Étape 20 — Analyse du fichier HAR

> Source : skill-steps/20_analyse-har.md. Retour : SKILL.md étape 30.

## Exécution — un script, pas un calcul à la main

```bash
.venv/bin/python3 .claude/skills/analyse-parcours/scripts/analyze_har.py <dossier-source>
```

Le script écrit `<dossier-source>/audit/har-analysis.json`. Option `--check`
pour comparer à la sortie existante sans rien réécrire.

**Ne pas recalculer ces agrégats à la main.** Chantier 35 : cette étape n'avait
aucun script jusqu'ici, et une lecture manuelle du `.har` avait produit une
clé `blocking_resources` non rejouable (inventée en lisant le HTML à l'œil,
sans archive à l'appui) — impossible de vérifier que les chiffres qui
alimentent l'EOF (critère des requêtes dupliquées) sont stables.

Le script classe 1st-party/3rd-party depuis `env-data.json` (règle canonique
partagée avec `deploy_freshness.py`), déduplique par URL avant le top10 des
ressources les plus lourdes (sans quoi une ressource sans cache, chargée
8 fois, peut occuper 8 des 10 places), et calcule les ressources bloquantes du
`<head>` uniquement pour les pages dont l'archive HTML (chantier 27,
`<source_dir>/pages-html/`) est disponible — sinon le champ est marqué "non
calculé", jamais deviné depuis le seul type MIME.

Les contrôles de non-régression : `analyze_har.py --autotest` (17 cas).

La section ci-dessous documente le **format** des fichiers lus et la **forme**
de la sortie attendue. Elle ne redevient une consigne de calcul que si le
script est indisponible.

## 20a — Vue d'ensemble du trafic

Lire le HAR (format JSON, clé `log.entries[]`). Extraire :

- Nombre total de requêtes (`log.entries.length`)
- Domaines contactés (extraire host depuis `request.url`, grouper : first-party / third-party)
- Répartition des codes HTTP (200, 301, 302, 404, 5xx...)
- Volume total transféré (somme `response.content.size` en octets, convertir en Mo)
- Top 10 requêtes les plus lourdes (par `response.content.size`)

## 20b — Performance réseau

- Requêtes sans cache (absence `Cache-Control` ou `Expires` dans la réponse)
- Requêtes vers des URLs identiques (doublons)
- Ressources bloquantes (JS/CSS synchrones en `<head>` - déduire des types MIME)
- Ressources tierces lentes (temps de réponse > 1s)
