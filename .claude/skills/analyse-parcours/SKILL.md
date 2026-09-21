---
name: analyse-parcours
description: >
  Ce skill s'active quand l'utilisateur veut "analyser un parcours web", "analyser un HAR",
  "analyser la couverture Chrome", "code mort JS/CSS",
  "coverage DevTools", "analyser le trafic d'un parcours",
  ou mentionne des fichiers .har ou Coverage-*.json issus de Chrome DevTools.
  S'active aussi pour l'estimation CO2e (e-footprint) : "estime l'empreinte carbone",
  "impact CO2", "empreinte environnementale", "efootprint",
  "empreinte écologique du site", "/efootprint", ou mention d'un env-data.json /
  efootprint-boavizta-model.json.
version: 1.2.1
---

# Analyse de parcours web (HAR + Coverage)

## Vue d'ensemble

Ce skill analyse un parcours web complet à partir de :
1. Un fichier **HAR** (HTTP Archive) - export du trafic réseau Chrome DevTools
2. Des fichiers **JSON de couverture** - export Chrome DevTools > Coverage (un fichier par page)

Il produit deux types d'analyse :
- **Trafic réseau** : requêtes, domaines, volumes, codes HTTP, performance
- **Performance/Éco** : EcoIndex (score + grade A-G), code mort JS/CSS, Core Web Vitals

**Documentation utilisateur** : `docs/capturer-har-et-coverage.md` - procédure pas à pas pour capturer un HAR, les fichiers Coverage et le fichier `cwv.json` optionnel.

**Fichier optionnel `cwv.json`** (Core Web Vitals mesurés manuellement) :
```json
[
  {"page": "page_1", "lcp": 0.76, "inp": 8, "cls": 0.06},
  {"page": "page_2", "lcp": 1.9,  "inp": 16, "cls": 0.66}
]
```
Si absent : le rapport affiche `onLoad` HAR comme proxy pour LCP.

---

## Invocation

```
/analyse-parcours <chemin-dossier>
/analyse-parcours <fichier.har> <coverage1.json> <coverage2.json> ...
/efootprint <source_dir>          # étape 45 seule (estimation CO2e)
```

Le skill est aussi déclenché automatiquement quand les triggers du `plugin.json` matchent.

---

## Étape 10 — Localisation des fichiers

→ Voir `skill-steps/10_localisation.md`

Extraire du prompt :
- Un chemin de **dossier** contenant les fichiers HAR et JSON
- Ou des chemins directs : `<fichier.har> [coverage1.json coverage2.json ...]`

Si aucun argument fourni : demander le chemin à l'utilisateur.

---

## Étape 15 — Capture du sessionId

Immédiatement après avoir déterminé SOURCE_DIR et AUDIT_DIR (étape 10), capturer le sessionId pour le calcul de coût du rapport :

```bash
AUDIT_DIR="<SOURCE_DIR>/audit"
mkdir -p "$AUDIT_DIR/analyse-cout-agent"
if [ -f "$HOME/.claude/.current_session_id" ]; then
  cp "$HOME/.claude/.current_session_id" "$AUDIT_DIR/analyse-cout-agent/.cost-session-id"
  date +%s > "$AUDIT_DIR/analyse-cout-agent/.cost-start-ts"
fi
```

Ces fichiers seront lus par `patch-audit-cost.sh` (appelé en fin d'étape 40) : `.cost-session-id` pour identifier la session, `.cost-start-ts` pour borner la durée au début réel de l'analyse (et non au début de la session complète).

---

## Étape 20 — Analyse du fichier HAR

→ Voir `skill-steps/20_analyse-har.md`

Extraire du HAR :
- Vue d'ensemble du trafic (requêtes, domaines, codes HTTP, volume)
- Métriques de performance réseau (cache, doublons, ressources lourdes)

---

## Étape 25 — Orchestration DISPATCH

→ Voir `skill-steps/25_dispatch-orchestration.md`

Deux vagues parallèles via le mécanisme DISPATCH. Si les sous-agents sont
disponibles (Claude Code), les blocs d'une même vague s'exécutent dans des
contextes isolés simultanément. Sinon, ils s'enchaînent inline. Sorties
identiques dans les deux cas.

- **Wave 1** (5 dispatches en parallèle) : analyse HAR (étape 20), analyse
  Coverage (étape 30), collecte CWV (étape 37), collecte env-data (étape 45
  Étape 20), extraction en-têtes sécurité (étape 39) → produit
  `har-analysis.json`, `coverage-analysis.json`, `cwv.json`, `env-data.json`,
  `security-headers-analysis.json`.
- **Wave 2** (2 dispatches en parallèle, dépend de `env-data.json` produit en
  Wave 1) : extraction critères HTML/CSS + well-known (étape 39) → produit
  `html-css-criteria.json`, `wellknown-scan.json`.

Seuls `har-analysis.json` et `coverage-analysis.json` sont obligatoires pour
poursuivre ; les 5 autres fichiers sont des enrichissements best-effort
(EOF/rapport dégradés mais non bloqués en leur absence).

---

## Étape 30 — Analyse des fichiers de couverture

→ Voir `skill-steps/30_analyse-coverage.md`

Exécutée automatiquement par l'étape 25 (Wave 1, bloc `analyse-coverage`) —
cette section documente le traitement et sa commande CLI pour un
relancement manuel isolé.

Pour chaque fichier JSON de couverture :
- Métriques par page (taille totale, code non utilisé, taux %)
- Fichiers les plus coûteux (JS + CSS)
- Synthèse multi-pages

---

## Étape 35 — Calcul EcoIndex

→ Voir `skill-steps/35_calcul_ecoindex.md`

Calcul automatique depuis le HAR (formule officielle) :
- DOM extrait du corps HTML (`response.content.text`)
- Requêtes et poids agrégés par page
- Score 0-100 + grade A-G avec code couleur

```bash
python3 .claude/skills/analyse-parcours/scripts/har_metrics.py <fichier.har> [cwv.json]
```

---

## Étape 37 — CWV via Lighthouse

→ Voir `skill-steps/37_lighthouse.md`

Exécutée automatiquement par l'étape 25 (Wave 1, bloc `collecte-cwv`) —
cette section documente le traitement et sa commande CLI pour un
relancement manuel isolé (ex. "relance Lighthouse").

Si `cwv.json` est absent : lancer automatiquement Lighthouse CLI via `npx` en extrayant
les URLs du HAR. Génère `cwv.json` avec LCP, INP, CLS mesurés en mode lab.
Si déjà présent : skippé. Si échec : warning et rapport sans CWV.
L'utilisateur peut forcer un re-run en disant "relance Lighthouse".

---

## Étape 39 — Potentiel d'optimisation (référentiel EOF)

→ Voir `skill-steps/39_eof-audit.md`

Étape **automatique** (pas une commande), séquentielle : attendre que
`har-analysis.json` et `coverage-analysis.json` existent (Wave 1/2 de
l'étape 25) avant de la lancer, avant le rapport. Les trois extracteurs
qu'elle consomme (`security-headers-analysis.json`, `html-css-criteria.json`,
`wellknown-scan.json`) sont désormais produits automatiquement par les
Waves 1/2 de l'étape 25, plus besoin de les lancer manuellement au préalable.
Remplit ce qui peut l'être du référentiel EOF-V.1.1 depuis
`eof-referentiel.json` (skill `eof`) et les données déjà collectées — jamais
la Google Sheet. Sur 54 critères détaillés, seuls ~10 sont exploitables
(4 automatisables, 6 indices partiels) ; les autres restent "je ne sais pas"
par construction. Si `eof-referentiel.json` est absent : étape sautée,
rapport sans section EOF.

---

## Étape 39b — Questionnaire EOF (génération et relecture)

→ Voir `skill-steps/39b_questionnaire-eof.md`

Étape **manuelle** (décision de mission, pas un calcul automatique), possible
dès que l'Étape 39 a écrit `eof-audit-results.json`. Pose au service audité
les critères que l'Étape 39 n'a pas pu trancher automatiquement :

```bash
python3 .claude/skills/analyse-parcours/scripts/generate_questionnaire.py <dossier-audit> --output-dir /tmp/questionnaire-<domaine>
```

**Ne jamais générer directement dans `audits/<domaine>/`** (le script le
refuse par défaut, sortie 2) : un questionnaire généré est vierge, et
`--dans-le-dossier-audit` ne doit être utilisé qu'au moment où il part
réellement vers le client. Une fois le fichier revenu rempli, la relecture se
fait avec `parse_questionnaire.py` (écrit `lots/relecture-questionnaire.json`) ;
voir le fichier d'étape pour la suite (fusion des lots, avertissement sur
`run_eof.py`).

---

## Étape 40 — Rapport HTML

→ Voir `skill-steps/40_rapport.md`

Étape séquentielle : attendre que `cwv.json`, `env-data.json` et
`eof-audit-results.json` existent (ou soient notés absents/dégradés) avant
de la lancer — sections correspondantes simplement omises si absents,
jamais un blocage.

Génère `rapport-parcours-YYYY-MM-DD.html` dans le dossier audit :

```bash
python3 .claude/skills/analyse-parcours/scripts/generate_report_html.py <dossier-audit>
```

Sections : EcoIndex | Trafic réseau | Code mort | CWV (si cwv.json) | Recommandations

---

## Étape 45 — Estimation CO2e (e-footprint)

→ Voir `skill-steps/45_efootprint.md`

Étape **optionnelle**, déclenchée par `/efootprint <source_dir>` ou par des phrases
comme "estime l'empreinte carbone" / "impact CO2". Réutilise `env-data.json` (HAR +
CrUX + mix pays/trafic SimilarWeb) pour calculer une estimation CO2e hypothétique via
la librairie e-footprint (Boavizta), puis insère une section "Impact environnemental"
dans le rapport HTML (Étape 40) si `efootprint-synthese-python.json` est présent.

Si `/analyse-parcours` a déjà tourné sur ce dossier, `env-data.json` existe
probablement déjà (produit par la Wave 1 de l'étape 25, bloc
`collecte-env-data`) : sa propre Étape 20 (§ci-dessous, `skill-steps/45_efootprint.md`)
se limite alors à proposer `--refresh` si les données doivent être rafraîchies.
Le flux `/efootprint <source_dir>` autonome, sans `/analyse-parcours`
préalable, reste inchangé : il relance lui-même `collect_env_data.py` si
nécessaire.

---

## Maintenance des outils CLI

→ Voir `scripts/README-outils.md`

### Install initiale de Lighthouse (une seule fois)

```bash
npm install --prefix .claude/skills/analyse-parcours/scripts/
```

### Vérifier si Lighthouse est à jour

```bash
npm outdated --prefix .claude/skills/analyse-parcours/scripts/
```

### Mettre à jour Lighthouse

```bash
npm update lighthouse --prefix .claude/skills/analyse-parcours/scripts/
```

L'utilisateur peut dire à Claude "vérifie si Lighthouse est à jour" ou "mets à jour Lighthouse".
Claude exécute `npm outdated`, lit la sortie et propose ou exécute `npm update`.

---

## Règles transversales

### Taille des fichiers HAR

Les HAR peuvent dépasser 5 Mo (50 000+ lignes). Procéder par lecture sélective :
- Lire l'entête JSON pour connaître le nombre d'entrées
- Traiter les entrées par lots si nécessaire
- Ne pas charger l'intégralité en une seule passe

### Données sensibles

Si le HAR contient des credentials ou tokens :
- Ne **jamais** les afficher en clair
- Masquer : `{"password":"***"}`, `token=****...abc`
- Tronquer les UIDs : `uid=8116...92`

### Progression

Afficher une ligne de progression à chaque étape :
```
▶ Étape 10 — Localisation des fichiers
▶ Étape 15 — Capture sessionId (silencieux)
▶ Wave 1 — Analyse HAR + Coverage + CWV + env-data + Sécurité (5 dispatches en parallèle)
▶ Wave 2 — Extracteurs HTML/CSS + well-known (2 dispatches en parallèle)
▶ Étape 39 — Audit EOF
▶ Étape 40 — Rapport de synthèse
```
