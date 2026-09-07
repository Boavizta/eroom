# Analyse — Minimiser les questions humaines pour maximiser les réponses EOF

> **v2 (2026-09-03, seconde passe)**. La v1 (même fichier, cf. git) cherchait
> uniquement à regrouper les questions entre elles. Cette v2 ajoute deux
> choses que la v1 n'avait pas faites : (a) mesurer la couverture en **poids
> de score** et non en nombre de critères, (b) chercher de **nouvelles
> sources de données** capables de répondre à des critères aujourd'hui
> classés "aucune donnée".
>
> Fichier intermédiaire d'analyse : pas consommé par du code.
>
> Méthode de cette v2 : sondes réelles exécutées sur `octo.com` le
> 2026-09-03 (DNS, HTTP, headers, CSS, JS, API tierces). Chaque piste est
> étiquetée **vérifié en réel**, **non vérifié**, ou **écarté après test**.
> Aucune piste n'est présentée comme acquise sans test.

-----
-----

## 1. Le vrai problème n'est pas le nombre de critères, c'est le poids

Le référentiel pondère chaque critère (`poids` : 1.0 Modéré, 1.5 Significatif,
2.0 Déterminant). **Poids total des 54 critères détaillés : 80.0.**

| | Critères | Poids | % du score |
|---|---|---|---|
| Répondus automatiquement (aujourd'hui) | 7 | 9.0 | **11.3 %** |
| dont réellement tranchés (hors 1.6 = "🤔 À évaluer") | 6 | 8.0 | **10.0 %** |
| Indices "partiels" (jamais cochés) | 11 | 16.5 | 20.6 % |
| Aucune donnée | 36 | 54.5 | 68.1 % |

**Constat central** : les 8 critères **Déterminants** (poids 2.0, soit 16.0 =
**20 % du score à eux seuls**) sont **tous les 8 non répondus** : `1.1`, `1.2`,
`2.2`, `5.8`, `5.9`, `6.1`, `6.4`, `6.6`.

Conséquence directe pour la stratégie : optimiser le nombre de questions posées
sans regarder les poids fait rater l'essentiel. Une question qui débloque
`6.4` + `6.6` + `6.1` (3 Déterminants, 6.0 de poids) vaut plus que six
questions sur des critères Modérés (6.0 aussi, mais six interactions).

**Métrique à retenir désormais : poids de score couvert par interaction
humaine.** C'est la formulation opérationnelle de "minimum de questions,
maximum de réponses".

-----

## 2. Poids couvert par cluster (classement des questions à poser en premier)

Reprise des clusters de la v1, chiffrés :

| Cluster | Critères | Poids | Dont Déterminants |
|---|---|---|---|
| **D — Maturité d'ingénierie** (6.1→6.9) | 9 | **14.0** | 6.1, 6.4, 6.6 (3) |
| **A — Infrastructure / FinOps** (3.1,3.2,3.5→3.9) | 7 | **10.5** | 0 |
| **G — Conception UX / compatibilité** (1.2→1.6,1.10,1.11) | 7 | **9.5** | 1.2 (1) |
| **C — Dette technique / perf** (5.1,5.2,5.6→5.9) | 6 | **9.0** | 5.8, 5.9 (2) |
| **B — Stockage et données** (4.2→4.6) | 5 | 6.5 | 0 |
| **E — Architecture** (2.2,2.3,2.4) | 3 | 5.0 | 2.2 (1) |
| **F — Nécessité du produit** (1.1,1.7) | 2 | 3.5 | 1.1 (1) |

**4 questions composées (D + A + G + C) = 43.0 de poids = 54 % du score**,
et 6 des 8 Déterminants. C'est le meilleur rapport réponses/questions
disponible, et c'est très supérieur à ce que toute automatisation
supplémentaire peut apporter (cf. section 4 : plafond réaliste ~+5 points).

-----

## 3. Levier le plus fort : demander des artefacts, pas des réponses

L'angle de la v1 était "regrouper les questions". Angle manqué : **une même
interaction peut demander un document plutôt qu'une réponse**, et un document
se lit sans mobiliser l'attention de l'interlocuteur sur 9 questions.

### 3.a Accès en lecture au dépôt de code = le plus gros gain unitaire

Un accès en lecture (ou même une simple capture de l'arborescence + quelques
fichiers) permet de répondre factuellement, sans interprétation :

| Critère | Poids | Ce qu'on lit dans le dépôt |
|---|---|---|
| `6.3` CI/CD | 1.5 | `.github/workflows/`, `.gitlab-ci.yml`, `Jenkinsfile` |
| **`6.4` tests non-régression** | **2.0** | répertoires de tests, config Jest/Pytest/Playwright |
| **`6.6` indicateurs qualité** | **2.0** | `sonar-project.properties`, config lint, badges CI |
| **`6.1` observabilité** | **2.0** | dépendances OpenTelemetry / Datadog / Sentry |
| `6.2` revues de code | 1.5 | `CODEOWNERS`, template de PR, règles de branche |
| `6.7` documentation | 1.5 | `README`, `docs/`, ADR |
| `6.8` code dupliqué | 1.0 | mesurable (`jscpd`) sur le dépôt |
| `6.9` autonomie outillage | 1.0 | diversité des outils déjà intégrés par l'équipe |
| **`5.8` dépendances à jour** | **2.0** | lockfile + Dependabot/Renovate, versions vs dernières |
| `5.6` pile technique à jour | 1.5 | `engines`, `.python-version`, `pom.xml` |
| `5.1` analyse statique | 1.0 | config linter / analyseur |
| `6.5` découplage métier/technique | 1.5 | structure des dossiers (hexagonal, DDD) |

**12 critères, 18.5 de poids (23 % du score), 5 des 8 Déterminants, pour
UNE seule demande.** À comparer aux 9.0 que produit tout le pipeline
automatique actuel. C'est la piste à prioriser avant toute nouvelle
automatisation technique.

Limite honnête : `6.8` et `5.8` demandent de faire tourner un outil sur le
dépôt (pas juste le lire) ; et un dépôt accessible ne dit rien de la
**qualité** des tests, seulement de leur existence. `6.4` peut donc passer
de "aucune donnée" à un cran plausible, pas à une certitude.

### 3.b Deux autres artefacts, même logique

- **Facture cloud détaillée ou export IaC (Terraform/CloudFormation)** →
  cluster A quasi entier (`3.1`, `3.5`, `3.6`, `3.7`, `3.8`, `3.9`) + `4.3`,
  `4.4`. Soit ~13.5 de poids pour une demande. L'IaC donne le
  dimensionnement réel, ce qui corrige le point noir connu (`instance_type`
  / `storage_gb` d'e-footprint ne sont que des défauts de script).
- **Export du backlog filtré sur "perf"** → `5.3` + `0.13`, et confirme
  `5.2`. Faible poids (3.0) mais coût quasi nul si l'outil est accessible.

-----

## 4. Nouvelles sources automatiques : ce que les sondes du 2026-09-03 donnent

### 4.a VÉRIFIÉ EN RÉEL — environnements non productifs exposés (`3.8`, `3.9`)

```
dig +short staging.octo.com  ->  d3cowsu17vt1rf.cloudfront.net / 3.164.163.68
curl -sI https://staging.octo.com/  ->  HTTP/2 200, 27947 octets,
                                        last-modified Tue 01 Sep 2026 01:00:41
prod https://octo.com/       ->  HTTP/2 200, 27748 octets,
                                        last-modified Thu 03 Sep 2026 01:01:31
```

ETag et last-modified **différents** de la prod : ce n'est pas un alias
wildcard, c'est bien un environnement distinct, servi publiquement, avec un
contenu quasi identique en volume à la prod.

- `3.8` "Tous les environnements sont-ils toujours activés ?" →
  **automatisable** (💡 Potentiel d'amélioration : un env non productif
  répond en permanence).
- `3.9` "Les environnements de test sont-ils aussi grands que la prod ?" →
  **indice** (volume de contenu comparable, mais le volume HTML ne dit rien
  du dimensionnement de l'infra derrière).

Gain : +1.5 tranché, +1.5 en indice.

⚠️ **Piège méthodologique découvert au passage, à traiter avant d'implémenter** :
octo.com renvoie **HTTP 200 + la page d'accueil** pour n'importe quelle URL
inexistante (`/package.json`, `/scripts/home.js.map` → 200, 27748 octets, la
homepage). Toute sonde qui conclut "le fichier existe" sur la base du code
HTTP produira des **faux positifs**. Il faut valider par signature de contenu
(taille + `content-type` + empreinte du corps), jamais par le statut seul.

⚠️ **Décision de posture nécessaire** : sonder des sous-domaines d'un client
est de la reconnaissance légère. À cadrer explicitement (liste fixe et
courte, DNS + HEAD uniquement, aucune tentative d'authentification, jamais de
chemins sensibles type `/.git` ou `/.env`) et à faire valider avant d'être
mis dans le pipeline par défaut.

### 4.b VÉRIFIÉ EN RÉEL — le header CSP est un inventaire de tiers déclaré

Le CSP de la prod (**déjà collecté** par `analyze_security_headers.py`, mais
seul son `grade` est exploité aujourd'hui) liste ~30 domaines autorisés :

```
*.herokuapp.com  *.hsforms.net  *.hsforms.com  *.hs-scripts.com
*.hs-analytics.net  *.hubspot.com  *.hs-banner.com  *.hsadspixel.net
*.hubapi.com  *.licdn.com  *.linkedin.com  cdnjs.cloudflare.com
swetrix.org  cdn.jsdelivr.net  challenges.cloudflare.com  ...
```

C'est **plus large que ce que le HAR capte** (le HAR ne voit que les tiers
sollicités sur le parcours capturé ; le CSP déclare tout ce qui est prévu).
Coût : **zéro appel réseau supplémentaire**. Meilleur rapport gain/effort de
toute cette analyse.

Exploitations possibles :
- `2.3` séparation/communication des composants → `*.herokuapp.com` révèle
  une plateforme applicative distincte du site statique → **indice**.
- `3.5` mutualisation → PaaS (Heroku) + CDN mutualisé → **indice**.
- `3.7` élasticité → dynos Heroku / CloudFront sont élastiques par nature →
  **indice** (jamais une preuve que l'élasticité est configurée).
- `1.12` trackers → **corrige une erreur de fond**, cf. 5.a.

### 4.c VÉRIFIÉ EN RÉEL — fraîcheur de déploiement (`6.3`)

L'indice `6.3` actuel repose sur `sitemap.days_since_lastmod`. Or **octo.com
n'a pas de `sitemap.xml`** (vérifié : 0 balise `<loc>`, `wellknown-scan.json`
ne contient que `domain` et `note`). L'indice est donc **vide en pratique**.

Substitut vérifié, bien plus fiable : le paramètre de cache-busting
`/style.css?v=2026-8-3-1-1`. Décodé avec un mois indexé à 0 (comportement de
`Date.getMonth()` en JS) : 2026, mois 8 = septembre, jour 3, 01h01. Ce qui
correspond **exactement** au `last-modified` de la prod (Thu 03 Sep 2026
01:01:31 GMT). Autrement dit : build automatisé, daté du jour, lancé vers
01h00 → **indice fort de pipeline automatisé nocturne**, là où le sitemap ne
donnait rien.

Généralisable : croiser `last-modified` / `ETag` / paramètres `?v=` des
assets. Deux audits espacés donneraient en plus une **cadence** de déploiement.

### 4.d NON VÉRIFIÉ — Lighthouse `legacy-javascript` pour `1.3` / `1.8` / `5.9`

`run_lighthouse.sh` existe déjà. Lighthouse expose un audit
`legacy-javascript` (polyfills et transpilation ciblant les vieux
navigateurs) et `third-party-summary`. C'est le proxy le plus direct
disponible pour "support médiocre sur appareils anciens" (`1.8`, 1.5) et
"problèmes de compatibilité identifiés" (`5.9`, **2.0 Déterminant**) — la v1
avait à raison écarté CrUX pour cet usage, mais n'avait pas examiné
Lighthouse.

**Je n'ai pas lancé Lighthouse pour le confirmer.** À tester avant d'y
compter : gain potentiel jusqu'à 5.0 de poids, gain réel inconnu.

### 4.e ÉCARTÉ APRÈS TEST — versions de dépendances par sondage externe (`5.6`, `5.8`)

Testé sur octo.com, tout est négatif : aucun `<meta name="generator">`, aucun
`sourceMappingURL` dans le HTML ni dans `/scripts/home.js` (3771 octets),
`/scripts/home.js.map` et `/package.json` inexistants (les 200 observés sont
le soft-404 décrit en 4.a).

La conclusion de la v1 ("pas de version détectable") est donc **confirmée pour
ce site**. À nuancer quand même : sur un site WordPress/Drupal (`meta
generator` versionné) ou livrant ses source maps, la détection marcherait. À
garder comme **sonde opportuniste** (coût quasi nul, gain nul ici, gain réel
ailleurs), jamais comme une source sur laquelle compter. `5.8` (2.0
Déterminant) reste à couvrir par le dépôt (3.a).

### 4.f Marginal — Green Web Foundation

`api.thegreenwebfoundation.org/api/v3/greencheck/octo.com` → `green: false`
(vérifié). Le référentiel n'a **pas** de critère "hébergement renouvelable"
(la numérotation saute de `3.3` à `3.5`, cf. section 6). Utilisable seulement
pour corroborer `3.3`, déjà répondu. Gain : 0. Mentionné pour clore la piste.

-----

## 5. Corrections de qualité trouvées en chemin (indépendantes du comptage)

### 5.a `1.12` pénalise aujourd'hui la sobriété — à corriger

`env-data.json` détecte `Analytics: ["Swetrix"]`, et la règle actuelle
("au moins un Analytics détecté → 💡") a donc classé octo.com en potentiel
d'amélioration. Or **Swetrix est justement l'option sobre** (sans cookie,
sans profilage). Et dans le même temps la vraie pile de tracking marketing
est **invisible** pour la règle : le HTML charge `hs-scripts` (HubSpot) et le
CSP autorise `hs-analytics`, `hsadspixel`, `licdn`, `linkedin`.

La réponse "💡" est juste par accident, avec un motif faux. Correction :
classer les traceurs par nature (mesure d'audience sobre / auto-hébergée
d'un côté, marketing-CRM-pixels publicitaires de l'autre) et fonder la
réponse sur la seconde catégorie. Source additionnelle : le CSP (4.b) + le
HTML déjà re-fetché.

### 5.b Bug latent dans `parse_html_criteria.py` : attributs non quotés — ✅ CORRIGÉ le 2026-09-07

⚠️ **Cette section décrit un état dépassé, elle est conservée pour son constat
sur octo.com, qui reste vrai et qui a servi à mesurer l'impact.** Le défaut
est corrigé : `parse_html_criteria.py` ne lit plus le HTML par expressions
régulières mais par `html.parser` (bibliothèque standard). L'ordre des
attributs, les guillemets, la casse, les entités et les chevrons dans une
valeur d'attribut ont cessé d'être un sujet. La correction embarque son test :
`python3 parse_html_criteria.py --autotest`, 32 cas, dont 13 écritures HTML
que l'ancienne version lisait faux en silence.

**La correction dépasse le périmètre décrit ci-dessous** : le défaut ne
touchait pas 2 expressions mais 4, et la plus grave n'était pas celle-ci.
`_AUTOPLAY_RE` prenait `<video class="no-autoplay">` et
`<video data-autoplay="false">` pour des vidéos à lecture automatique, ce qui
alimentait le critère `1.5` en provenance **`collecte`**, donc présenté au
lecteur comme une mesure. Vérifié sur les données déjà sur le disque :
`has_autoplay_media` vaut `False` sur les 6 pages d'octo.com, ce faux positif
ne s'est donc **pas** déclenché ici.

**Le texte d'origine suit. Sa dernière phrase, "à corriger (rendre le
guillemet fermant optionnel)", est périmée** : rapiécer l'expression aurait
laissé passer l'ordre des attributs et les trois autres formes d'écriture.

-----


octo.com sert du HTML minifié à attributs non quotés
(`<script src=/scripts/home.js defer>`, `<link rel=stylesheet
href=/assets/orejime.css>`). Or les regex du script exigent des guillemets :

```python
_STYLESHEET_LINK_RE = ... rel=["']?stylesheet["']?[^>]*\bhref=["']([^"']+)["']
_DIV_ROLE_BUTTON_RE = re.compile(r"role=[\"']button[\"']", re.IGNORECASE)
```

`href=` et `role=` non quotés ne matchent pas. Conséquence : feuilles de
style ignorées (→ `media_query_count`, `has_prefers_reduced_or_scheme`
sous-évalués, critères `1.6` et `1.11`) et boutons `role=button` non quotés
non comptés (`1.4`).

**Impact réel sur octo.com : nul, vérifié.** La seule CSS ignorée
(`/assets/orejime.css`, 5654 octets) ne contient ni `@media` ni `prefers-*`,
et la CSS principale (172 796 octets, bien lue) n'a pas de `prefers-*` non
plus : `has_prefers_reduced_or_scheme: false` est un résultat correct. Le bug
est donc **latent**, pas actif ici — mais il produira un faux négatif
silencieux sur le premier site minifié qui déclare `prefers-reduced-motion`
dans une CSS à `href` non quoté. À corriger (rendre le guillemet fermant
optionnel), sans urgence.

-----

## 6. Point à lever sur le référentiel lui-même

La numérotation des critères **saute `3.4`** (`3.1`, `3.2`, `3.3`, puis
`3.5`...). Le total fait bien 54 (16+5+8+6+9+10), donc rien n'est "perdu" par
rapport au compte attendu, mais un trou de numérotation peut signaler soit un
critère retiré côté Google Sheet, soit une ligne sautée à l'export. À vérifier
lors de la prochaine synchronisation du skill `eof` : si un critère "3.4"
existe dans la Sheet, l'export en perd un silencieusement.

-----

## 7. Bilan chiffré de cette v2

Couverture du poids (base 80.0) :

| Scénario | Poids tranché | % | Interactions humaines |
|---|---|---|---|
| Aujourd'hui | 9.0 | 11 % | 0 |
| + sondes vérifiées (4.a, 4.b, 4.c) | 10.5 tranché + ~7.5 d'indices | 13 % tranché | 0 |
| + Lighthouse **si confirmé** (4.d) | ~13 | ~16 % | 0 |
| **+ accès dépôt (3.a)** | **~31.5** | **~39 %** | **1 demande** |
| + IaC / facture cloud (3.b) | ~45 | ~56 % | 2 demandes |
| + 4 questions composées D/A/G/C | ~65 | ~81 % | 6 |

Lecture : **le plafond de l'automatisation pure est autour de 16 % du poids.**
Tout le reste passe par de l'humain ou des artefacts. Deux demandes
d'artefacts valent plus (56 %) que six questions posées à froid, et coûtent
moins d'attention à l'interlocuteur.

Révision du chiffre de la v1 : "23 interactions" reste valable comme
borne haute si on veut les 70 critères. Mais si l'objectif est
"maximum de réponses pour un minimum de questions", la bonne cible est
**2 artefacts + 4 questions composées ≈ 6 interactions pour ~81 % du poids**,
au lieu de 23 pour 100 %.

-----

## 8. Ce qui reste à décider (rien n'est implémenté)

Par ordre décroissant de gain par unité d'effort :

1. **Exploiter le CSP déjà collecté** (4.b) — zéro appel réseau, +3 indices
   et corrige `1.12`. Aucun risque de posture. À faire en premier.
2. **Substituer la fraîcheur d'assets au sitemap pour `6.3`** (4.c) — l'indice
   actuel est vide sur octo.com, celui-ci est vérifié.
3. **Corriger `1.12`** (5.a) — corrige un motif faux, pas un comptage.
4. **Formaliser la demande d'artefacts** (3.a/3.b) : c'est le vrai levier
   (+28 points de poids), mais c'est un changement de nature du pipeline
   (il devient collaboratif, plus seulement observationnel). À valider.
5. **Tester Lighthouse `legacy-javascript`** (4.d) avant d'y compter.
6. **Sondage de sous-domaines** (4.a) — gain net et vérifié, mais demande une
   décision de posture explicite + une validation par signature de contenu
   pour éviter les faux positifs du soft-404.
7. **Corriger les regex non quotées** (5.b) — bug latent, impact nul
   aujourd'hui, à faire quand on touchera le fichier.
8. **Vérifier `3.4`** à la prochaine synchro (section 6).
