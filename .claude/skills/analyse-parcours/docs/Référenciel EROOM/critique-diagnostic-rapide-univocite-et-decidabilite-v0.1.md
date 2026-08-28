# Critique — diagnostic rapide, version univoque (v0.1)

> Ce document critique `diagnostic-rapide-univocite-et-decidabilite-v0.1.md` (même dossier).
> Il ne le remplace pas et n'en corrige aucun contenu : c'est une relecture externe, appuyée
> sur une exploration en lecture seule du dépôt « Agent EROOM ».
>
> Portée : le document source (16 critères, 6 piliers, diagnostic rapide) et son articulation
> avec les audits déjà produits par le skill `analyse-parcours` dans ce même dépôt.
>
> Ce document est une **proposition** — aucun fichier n'a été modifié, aucun arbitrage n'est
> tranché.

---

## Point ouvert n° 8 — « pilier » ou « dimension »

Le référentiel EROOM et le document source retiennent le terme **pilier** pour les six
regroupements de critères (Produit, Architecture, Infrastructure, Stockage & Données,
Algorithme & Code, Facilité de changement). Ce choix n'est cependant pas allé de soi : le
terme **dimension** avait été évoqué dans les échanges avec Tristan comme alternative.

Aucun fichier de ce dépôt ne documente cet arbitrage — ni comme décision prise, ni comme
point en discussion. Il est consigné ici pour ne pas se perdre, à la suite des sept points
d'arbitrage du document source :

| # | Point | Portée |
|---|---|---|
| 8 | « Pilier » (retenu) vs « dimension » (évoqué avec Tristan) pour nommer les six regroupements de critères. Non tranché, non documenté ailleurs dans le dépôt. | 6 piliers, tout futur pont avec l'application ou avec d'autres documents du référentiel |

**Conséquence si le terme changeait** : renommage des six titres de section du document
source, de son tableau récapitulatif, de toute mention dans l'application (si le champ y est
exposé), et de tout document construit par-dessus — dont celui-ci et un futur pont avec les
audits `analyse-parcours` (voir plus bas). Tant que ce n'est pas tranché, ce document utilise
« pilier » par cohérence avec le document source, sans que cela vaille prise de position.

---

## Ce qui est cohérent

Le document source est déjà rigoureux sur son propre périmètre, et le dit lui-même :

- **Axe de l'échelle** (1 = fort potentiel d'optimisation, 5 = rien à gagner) : contrôlé
  critère par critère contre le template EOF V1.1, sur les 16 critères. Aucune inversion
  trouvée, y compris sur `Produit 1` — point sur lequel les fichiers compagnons cités
  induiraient pourtant en erreur.
- **Cohérence libellé bas ↔ explication ↔ recommandation** : contrôlée sur les 16 critères,
  sans contradiction relevée.
- **Mécanisme « Je ne sais pas »** : déjà implémenté côté application (bouton dédié, réponse
  exclue du score, comptée dans le taux de confiance). Le défaut résiduel identifié (dix
  libellés de cran 1 contenant encore « inconnu ») est correctement isolé comme un défaut de
  rédaction, pas de mécanique.
- Le document assume et chiffre ses propres limites (mesure « 53 % → 99 % » explicitement
  qualifiée de trompeuse, cas limites non écrits, classement de décidabilité non confronté à
  un agent réel) — une auto-critique rare et à conserver comme méthode.

## Ce qui interroge

### Vérifiabilité des sources citées

Le document source revendique une **rejouabilité pièce en main** (« pour que le tableau soit
rejouable », section « Décidabilité »). Or l'exploration de ce dépôt ne retrouve aucun des
fichiers qu'il cite comme sources ou compagnons :

- `docs/EOF-V.1.1 …/🏦 0-Diagnostic rapide.html`
- `docs/diagnostic-rapide.csv`
- `docs/questions-diagnostic-comparaison.md`
- `docs/user-tests-march-2026.md`
- `src/data/questionnaire-qd.json`
- `src/lib/computeResults.ts`
- `src/lib/electricityMap.ts`

Aucun tracker d'US, aucun dossier d'arbitrages n'a été trouvé non plus. Le dossier
`docs/Référenciel EROOM/` ne contient que le document source et le classeur
`EROOM-diagnostic-rapide-univoque-v0.1.xlsx` ; le dossier parent `docs/` du skill ne contient
que le guide de capture HAR/Coverage.

Ce n'est probablement pas une erreur du document source : ces fichiers vivent vraisemblablement
dans le dépôt de l'application EROOM elle-même, distinct de « Agent EROOM ». Mais c'est un
angle mort pour quiconque lit ce document depuis ce dépôt sans accès à l'autre : les preuves
citées (US 2.22, `computeResults.ts:77`, `ScaleInput.tsx`, `co2Weight`) ne sont pas à portée de
main ici. À signaler explicitement plutôt que de laisser croire, par la présentation, qu'elles
le sont.

### Deux référentiels parallèles, jamais reliés

Ce dépôt contient déjà des audits réels produits par le skill `analyse-parcours` :
`audits/octo.com`, `audits/audit-30000-octo`, `audits/ants-permis` (ex.
`rapport-parcours-2026-08-11.html`). Ce sont des rapports « Audit EROOM v1.1.0 » : recommandations
priorisées, bonnes pratiques GreenIT-Analysis, impact CO2e/e-footprint, EcoIndex/Core Web
Vitals, trafic réseau, coverage JS/CSS. Exemples de préconisations déjà produites : lazy
loading + tree shaking sur le JS mort, PurgeCSS sur le CSS mort, cache navigateur, Brotli,
limiter les domaines tiers.

**Aucun de ces audits ne référence les 16 critères ou les 6 piliers** du diagnostic rapide.
Ce sont deux référentiels qui coexistent dans le même dépôt sans pont documenté, alors que le
document source parle explicitement d'un futur agent qui pré-remplirait le questionnaire à
partir d'une évidence externe (section « Décidabilité par un agent »). L'agent qui produit
aujourd'hui des évidences externes comparables (`analyse-parcours`) ne nourrit pas ce
questionnaire, et réciproquement. Voir plus bas la piste la plus immédiate pour combler cet
écart.

### Chiffres cités sans source vérifiable dans ce dépôt

La comparaison « le diagnostic avancé est à 30 % / 57 %, tous accès confondus » (section
« Décidabilité ») n'a pas de document ou de calcul retrouvable dans ce dépôt. À traiter comme
une affirmation à vérifier, pas comme un fait établi, tant que sa source n'est pas localisée
(probablement dans le dépôt de l'application, comme les fichiers ci-dessus).

### Limites déjà admises, confirmées par l'exploration

L'exploration ne contredit aucune des six limites listées en fin de document source ; elle en
confirme au moins deux avec plus de force : le classement de décidabilité n'a effectivement
jamais été confronté à un agent réel (aucune trace d'implémentation dans ce dépôt), et aucun
des huit tests de mesure n'est vérifié par une machine ici.

---

## Couverture par pilier — ce qu'un audit externe peut déjà nourrir

Rappel des trois classes de décidabilité, sous contrainte **URL seule, sans accès au dépôt, à
l'IaC ni à l'observabilité** (définition reprise du document source) :

- **AUTO** — une source machine accessible depuis l'URL suffit à déterminer le cran, sans
  info supplémentaire que la machine n'ait pas. L'agent tranche seul.
- **SEMI** — la source existe mais ne couvre qu'une partie de ce que la méthode exige : elle
  fonde une proposition, pas une décision. L'agent propose, un humain confirme.
- **HUMAIN** — la méthode exige une information contractuelle, organisationnelle ou
  d'intention, qu'aucune mesure externe ne produit.

En agrégeant par pilier le tableau de décidabilité du document source (colonne « boîte noire,
URL seule ») :

| Pilier | AUTO | SEMI | HUMAIN | % couvert (AUTO + SEMI) |
|---|---|---|---|---|
| 1 — Produit | 0 | 1 (1.3) | 2 | 33 % |
| 2 — Architecture | 0 | 1 (2.2, fiabilité **faible**) | 2 | 33 % (fragile) |
| 3 — Infrastructure | 1 (3.2) | 0 | 2 | 33 % (le seul AUTO fiable du référentiel) |
| 4 — Stockage & Données | 0 | 0 | 2 | 0 % |
| 5 — Algorithme & Code | 0 | 2 (5.2, 5.3) | 1 | 67 % |
| 6 — Facilité de changement | 0 | 0 | 2 | 0 % |

Lecture : le pilier 5 est le mieux couvert par un audit externe, mais entièrement en SEMI
(propositions à confirmer, jamais une décision automatique) ; le pilier 3 porte le seul
critère réellement automatisable (3.2, région d'hébergement) et c'est aussi celui à l'impact
carbone le plus direct ; les piliers 4 et 6 sont hors de portée de tout audit externe — ce sont
des critères d'entretien, pas de mesure.

## Pilier à explorer en priorité : Algorithme & Code, en pont avec Infrastructure (3.2)

Deux raisons convergent vers le pilier **5 — Algorithme & Code**, avec le critère **3.2 —
région d'hébergement** comme extension naturelle :

1. **C'est le pilier le mieux couvert par de l'évidence externe** (67 %), et les critères
   concernés (5.2 friction des parcours, 5.3 confort sur appareils anciens) portent sur des
   grandeurs que les audits `analyse-parcours` mesurent déjà : Core Web Vitals mobile, poids
   du JavaScript, nombre de requêtes et de rechargements par parcours.
2. **Les audits déjà réalisés produisent déjà ces données**, sans qu'elles soient reliées au
   référentiel : les rapports `ants-permis`, `octo.com` et `audit-30000-octo` documentent JS
   mort, CSS mort, cache, compression et domaines tiers — de quoi alimenter une première
   estimation SEMI de 5.2 et 5.3, et une réserve chiffrée sur 3.2 dès que l'origine réseau /
   CDN est connue du HAR.

**Préconisation générale, peu coûteuse, généralisable à tout audit déjà produit** : construire
un mapping explicite « champ de sortie d'audit HAR/Coverage → cran du critère » pour ce
sous-ensemble (5.2, 5.3, 3.2) avant de viser les 16 critères. C'est le sous-ensemble où le
gain — pré-remplissage SEMI fiable, cohérence entre audits déjà produits et référentiel de
piliers — est le plus immédiat au regard du travail déjà fait, sans attendre l'écriture des
cas limites (US 2.28) sur les 13 autres critères.

À l'inverse, les piliers 4 (Stockage & Données) et 6 (Facilité de changement) ne gagneront
rien d'un travail sur les audits HAR/Coverage : ce sont des entretiens à mener, pas des mesures
à automatiser.

---

## Ce que ce document ne fait pas

- Il ne tranche aucun arbitrage, y compris le point n° 8 ajouté ici.
- Il ne vérifie pas le contenu du classeur `EROOM-diagnostic-rapide-univoque-v0.1.xlsx`.
- Il ne propose ni code ni modification du questionnaire : uniquement une lecture croisée
  entre le document source et l'état réel de ce dépôt (fichiers présents, audits déjà
  produits).
- Il ne localise pas les fichiers manquants (probablement dans le dépôt de l'application
  EROOM) : leur absence ici est constatée, pas expliquée.
