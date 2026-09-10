# Ce que les données déjà collectées peuvent (ou ne peuvent pas) apporter aux 21 critères non automatisés

Sur les 26 critères du périmètre (dimension 0 + dimension 6), un seul est aujourd'hui vraiment automatisable (`0.16`, cf. fichier 01). Ce document évalue les 21 critères restants, un par un, à partir des données réellement présentes dans le projet (pas supposées).

Sources inspectées : `audits/octo.com/env-data.json`, `cwv.json`, `security-headers-analysis.json`, `html-css-criteria.json`, `pages-publiques-criteria.json`, `wellknown-scan.json`, `topologie-octo.com.puml`, `efootprint-boavizta-model.json`, `tmp/pagespeed-raw-octo-2026-09-04.json`, ainsi que les scripts `run_eof.py`, `eof_criteria_mapping.py`, `parse_pages_publiques.py`, `deploy_freshness.py`, `csp_inventory.py`, `detect_tech.py`.

## Verdicts

| Critère | Verdict | Justification |
|---|---|---|
| 0.1 | NON AUTOMATISABLE (proxy faible rejeté) | Le volume de trafic (`env-data.json: traffic.visits_per_year`) ne mesure pas la criticité métier : un outil interne critique peut avoir peu de trafic. Jugement de valeur, invisible depuis l'extérieur. |
| 0.2 | NON AUTOMATISABLE | Suppose de connaître les autres systèmes internes de l'organisation. Aucun signal externe possible. |
| 0.3 | NON AUTOMATISABLE (proxy faible rejeté) | Identique à `6.10`. La présence d'un CDN multi-IP ne prouve aucun SLA/SLO réel sur les composants métier. |
| 0.4 | PARTIELLEMENT INFORMATIF (déjà câblé) | `run_eof.py::diag_context_0_4` lit `har-analysis.json: domains.third_party` et affiche la liste en annexe de la question, avec la réserve explicite que ça ne dit rien de l'architecture complète. |
| 0.5 | NON AUTOMATISABLE | Question de droits d'accès à un dépôt interne. |
| 0.6 | NON AUTOMATISABLE | Compétence d'équipe, purement interne. |
| 0.7 | PARTIELLEMENT INFORMATIF (pas câblé) | La donnée existe (CSP : famille `paas_backend`, ex. `herokuapp.com` ; 4 CDN distincts dans `tech_stack.categories.CDN`) mais n'est reliée à aucun `DIAG_CONTEXTS` dans `run_eof.py`. Angle mort structurel sur le backend non exposé au client. |
| 0.8 | NON AUTOMATISABLE (proxy faible rejeté) | `env-data.json: servers[]` ne voit qu'un seul hôte 1st-party côté client ; `efootprint-boavizta-model.json` indique `server_type: "autoscaling"` avec le commentaire "mode de dimensionnement par défaut" (un défaut de script, pas une observation). |
| 0.9 | NON AUTOMATISABLE (proxy faible rejeté) | `efootprint-boavizta-model.json: Storage.storage_capacity = 1.0 TB` a `source: "hypothesis"` : valeur par défaut du modèle CO2e, jamais une mesure réelle du volume stocké. |
| 0.10 | PARTIELLEMENT INFORMATIF (câblé mais inerte sur octo.com) | `run_eof.py::diag_context_0_10` lit `wellknown-scan.json: sitemap.url_count`. Sur octo.com, `sitemap.present: false` donc aucun indice produit actuellement. Même quand disponible, le nombre d'URL reste un proxy faible (une seule page peut porter une SPA complexe). |
| 0.11 | PARTIELLEMENT INFORMATIF (pas câblé) | `cwv.json` montre `accessibility_score_pct=100` (lab), `best_practices_score_pct=81` (lab), et lcp/inp/cls en zone "good" (`source=crux`, terrain réel). Réduit la probabilité de friction technique, mais ne dit rien de la clarté de navigation perçue. |
| 0.12 | PARTIELLEMENT INFORMATIF (pas câblé) | `cwv.json` (`crux_category="FAST"`, mobile) reflète la population réelle de visiteurs, incluant du matériel bas de gamme, mais une seule entrée et aucune notion de "matériel le plus ancien de la flotte cible". Aucun test réel sur un appareil ancien. |
| 0.13 | NON AUTOMATISABLE | Backlog interne (Jira ou équivalent), jamais exposé publiquement. |
| 0.14 | NON AUTOMATISABLE (proxy faible rejeté) | Les indicateurs Lighthouse (`bootup-time`, `render-blocking`...) mesurent l'exécution technique de la page, pas si les fonctionnalités métier sont bien conçues pour l'usage visé. |
| 0.15 | NON AUTOMATISABLE avec l'outillage actuel (mais pas structurellement impossible) | Une page de politique de données publique est en principe observable depuis l'extérieur (cf. `/protection-donnees` documenté dans `tmp/handoff-2026-09-04-couverture-eof-sources-ARCHIVE.md` pour d'autres sites). Mais `parse_pages_publiques.py` est aujourd'hui scopé exclusivement aux motifs environnementaux (`PAGE_NAME_PATTERNS`, `KEYWORDS_SUIVI`) : aucun motif de rétention/suppression de données. C'est un manque d'implémentation, pas un plafond structurel. |
| 6.1 | PARTIEL (déjà câblé, jamais une réponse) | `security-headers-analysis.json: worst_page.grade` affiché en annexe. La règle du mapping est explicite : `categorie: "partiel"` -> jamais de case cochée automatiquement. |
| 6.2 | NON AUTOMATISABLE | Pratique d'équipe interne (revue de code, pair programming), invisible depuis le trafic HTTP audité. |
| 6.3 | PARTIEL (déjà câblé) | En-têtes `Last-Modified` des ressources 1st-party dans le `.har`, comme indice de fraîcheur des déploiements. Toujours un indice, jamais une réponse. |
| 6.4 | NON AUTOMATISABLE | Suite de tests côté dépôt/CI, jamais exposée via le site public. |
| 6.5 | NON AUTOMATISABLE (proxy faible rejeté) | La séparation d'infrastructure visible en CSP est un fait d'infra, pas un découplage du code (architecture hexagonale...), propriété interne au code source. |
| 6.6 | PARTIEL (déjà câblé) | Trois indices combinés en annexe : `cwv.json: best_practices_score_pct`, `security-headers-analysis.json: worst_page.grade`, `wellknown-scan.json: security_txt.present`. Jamais cochés automatiquement. |
| 6.7 | NON AUTOMATISABLE | Aucune page de documentation développeur détectable de l'extérieur ; documentation interne hors de portée d'un audit externe. |
| 6.8 | PARTIEL (déjà câblé) | `cwv.json: lighthouse_insights['duplicated-javascript']`, détection côté client uniquement. Indice, jamais une réponse. |
| 6.9 | NON AUTOMATISABLE | Question de gouvernance/droits internes (accès cloud, permissions). |
| 6.10 | NON AUTOMATISABLE (proxy faible rejeté) | Identique à `0.3`, même bloc de questionnaire partagé. |

## Total sur les 25 critères non encore automatisés (26 critères moins 0.16)

**0 automatisable en plus (case cochée seule), 9 partiellement informatifs (indice affiché, réponse humaine toujours requise : 0.4, 0.7, 0.10, 0.11, 0.12, 6.1, 6.3, 6.6, 6.8), 1 non automatisable avec l'outillage actuel mais pas structurellement impossible (0.15), 15 non automatisables structurellement (fait interne à l'équipe, aucun signal externe possible).**

Correction de comptage : la première version de cette étude reprenait tel quel un total verbal ("16 non automatisables sur 21") donné par un sous-agent, sans le recalculer à partir du tableau ci-dessus. Le bon compte, recalculé ligne à ligne sur les 26 critères (1 automatisable + 9 partiel + 1 cas particulier + 15 structurel = 26), est celui de ce paragraphe. Le tableau consolidé de `00-resume-session.md` reprend ce chiffre corrigé.

Point particulier : `0.15` n'est pas structurellement hors de portée (une page de politique de données publique est un fait observable), mais l'outil actuel ne la cherche pas. C'est un manque d'implémentation identifié, pas un verdict définitif.

Trois pièges à proxy faible ont été explicitement écartés et documentés ci-dessus : le trafic pour juger la criticité (`0.1`), les valeurs par défaut du modèle e-footprint pour juger la taille de l'infra ou le volume de données (`0.8`, `0.9`), et un score Lighthouse technique pour juger l'efficacité fonctionnelle métier (`0.14`).

**Aucun de ces 9 indices partiels ne réduit le nombre de questions à poser** (la règle du mapping l'interdit explicitement : `partiel` ne coche jamais une case seul). Leur seul usage possible est de rendre la question plus facile et plus fiable à répondre pour l'humain, en rappelant dans la question ce qui a déjà été mesuré.
