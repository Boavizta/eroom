# Étape 20 — Analyse du fichier HAR

> Source : skill-steps/20_analyse-har.md. Retour : SKILL.md étape 30.

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
