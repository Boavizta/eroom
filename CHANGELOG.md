# Changelog — Agent EROOM

Format inspiré de [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/). Les dates correspondent aux commits qui font évoluer le champ `version:` dans `.claude/skills/analyse-parcours/SKILL.md` (source de vérité de la version affichée dans le footer des rapports générés).

## [1.2.1] - 2026-09-21 — Stabilisation

Pas de nouvelle fonctionnalité majeure : ce point de version consolide le référentiel EOF et le pipeline d'audit après l'extension du 1.2.0.

- Questionnaire EOF consolidé en un seul fichier, couvrant les 70 critères du référentiel, doublons de questions retirés
- Fiabilisation des sondes : distinction entre un échec de sonde et une absence réelle chez le service audité, correction du décodage base64 EcoIndex, dégradation de la confiance sur le pays serveur quand un CDN est détecté
- Corrections d'affichage du rapport et du radar EOF (valeurs "None"/"N/A", inversion de précédence precise/declare, hachure limitée à la marge d'incertitude)
- Ajout du gain CO2e et du gain EcoIndex/LCP par palier de recommandations (prio 1 / 1+2 / 1+2+3)
- Extension du dispatch parallèle (Core Web Vitals, env-data, sécurité, extracteurs EOF) et correction d'un masquage silencieux des échecs de mesure CWV
- Nettoyage et complément du README (licences des projets/services tiers) et des diagrammes

## [1.2.0] - 2026-09-03

- Extension de l'automatisation de la Phase 1 du référentiel EOF (4 → 7 critères automatisables, 6 → 11 indices)
- Dernières sondes OSINT / boîte noire : lecture des pages publiques déclarées par l'organisation auditée (RSE, éco-conception), introduction du niveau de provenance "declare"
- Introduction du référentiel EOF (EROOM Optimization Framework) la veille (2026-09-02) : skill dédié, template vierge, radar SVG

## [1.1.0] - 2026-07-30

- Fusion du skill "efootprint" (jusque-là autonome) dans "analyse-parcours" : plus de skill séparé, intégré comme étape (`skill-steps/45_efootprint.md`)

## [1.0.2] - 2026-07-13

- Renommage de l'outil en "Agent EROOM" dans le footer des rapports générés
- Introduction d'e-footprint (calcul de l'empreinte environnementale du site audité, bibliothèque Boavizta) le 2026-07-27, sous cette version

## [1.0.0] - 2026-07-08

- Création initiale du skill analyse-parcours
