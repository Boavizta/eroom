# Rejeu contre les données déjà collectées sur octo.com

Objectif : vérifier si l'analyse abstraite (fichiers 01 et 02) tient face aux données réellement collectées sur octo.com, ou si le cas réel révèle des signaux supplémentaires exploitables.

Source : `audits/octo.com/eof-audit-results.json` (lecture seule, aucune modification).

## État réel des 26 critères sur octo.com, aujourd'hui

| Critère | Réponse | Provenance | Indice disponible |
|---|---|---|---|
| 0.1 à 0.3, 0.5 à 0.9, 0.13 à 0.15 | vide | aucune | aucun |
| 0.4 | vide | aucune | "5 domaine(s) tiers détecté(s) lors de la capture : api.analytics.octo.tools, cdn.jsdelivr.net, fonts.googleapis.com, fonts.gstatic.com, swetrix.org" |
| 0.10 | vide | aucune | aucun (sitemap absent sur octo.com : `wellknown-scan.json: sitemap.present = false`) |
| 0.11, 0.12 | vide | aucune | aucun (mécanisme non câblé dans `run_eof.py`, cf. fichier 02) |
| **0.16** | **"2- < 500 gCO2e / kWh"** | **collecte** | `env-data.json: servers[].carbon_intensity_g_kwh = 381 gCO2e/kWh` |
| 6.1 | vide | suppose (indice seul) | `security-headers-analysis.json: worst_page.grade` |
| 6.2, 6.4, 6.5, 6.7, 6.9, 6.10 | vide | aucune | aucun |
| 6.3 | vide | suppose (indice seul) | `*.har`: en-têtes Last-Modified des ressources 1st-party |
| 6.6 | vide | suppose (indice seul) | `cwv.json: best_practices_score_pct` + `security-headers-analysis.json: worst_page.grade` + `wellknown-scan.json: security_txt.present` |
| 6.8 | vide | suppose (indice seul) | `cwv.json: lighthouse_insights['duplicated-javascript']` |

Confirmé par lecture directe du JSON : dimension 6, `repondus: 0`, `total: 10`, `completude_pct: 0.0`. Dimension 0 : 15 des 16 questions ont `reponse: null`. Sur l'ensemble de l'audit octo.com (54 critères détaillés, toutes dimensions), `repondus_par_provenance` = `{collecte: 4, estime: 3, declare: 0, precise: 0, suppose: 0}` : **aucune réponse humaine n'a encore été saisie pour octo.com**, ni sur les 54 critères détaillés, ni sur les 26 critères du présent périmètre.

## Constat du rejeu

**Le réel confirme exactement l'abstrait, sans surprise ni gisement caché :**

- Le seul critère réellement rempli sans intervention humaine est `0.16` (1/26 = 3,8 %), via la même donnée que `3.3`.
- Les 4 indices "partiel" prévus par le mapping (`6.1`, `6.3`, `6.6`, `6.8`) sont bien présents et alimentés par de vraies données octo.com, mais aucun ne remplit `reponse` : conforme à la règle "partiel ne coche jamais seul".
- L'indice de `0.4` est bien alimenté avec les 5 domaines tiers réels d'octo.com.
- L'indice de `0.10` est câblé mais inerte, parce qu'octo.com n'a pas de sitemap.
- Aucune donnée collectée sur octo.com (HAR, CWV, en-têtes de sécurité, CSP, wellknown, e-footprint, topologie) ne permet de trancher un des 20 critères restants sans passer par la case "proxy faible rejeté" déjà écartée dans le fichier 02.

**Conclusion du rejeu : il n'y a pas de gain caché spécifique à octo.com qui n'aurait pas été identifié par l'analyse abstraite sur le référentiel seul.** Le plafond d'automatisation (1 critère sur 26) est le même en abstrait et en réel.

## Avertissement sur ce snapshot

Ce rejeu a été fait sur un instantané de `audits/octo.com/eof-audit-results.json` pris pendant cette session. Un autre agent modifiait en parallèle ce même fichier (et `wellknown-scan.json`, `html-css-criteria.json`) via une nouvelle étape `39b_questionnaire-eof.md` en cours d'écriture. Les chiffres de la dimension 0 et de la dimension 6 (structurellement peu automatisables, cf. fichiers 01-02) ne devraient pas bouger, mais si ce chantier est repris, revérifier l'état du fichier avant de citer ces chiffres comme définitifs.
