-----
Détection des technologies (stack technique) par règles maison
-----

Ce document explique POURQUOI et COMMENT l'agent EROOM détecte la stack technique
d'un site (CDN, serveur web, langage, framework, CMS, analytics, polices) sans
utiliser Wappalyzer ni aucune API externe. Il sert aussi de guide de maintenance
pour ajouter ou corriger une règle de détection.

Le module concerné est `.claude/skills/analyse-parcours/scripts/detect_tech.py`.
Il est relançable seul et intégré à la collecte (`collect_env_data.py`) et au
rapport (`generate_report_html.py`).


-----
1. Le raisonnement sur les licences (pourquoi PAS Wappalyzer)
-----

La détection de technologies "de référence" repose sur le projet open source
**webappanalyzer** (fork communautaire de Wappalyzer, ~2500 technologies),
distribué sous licence **GPL v3**.

La boîte à outils EROOM est destinée à être publiée sous **CC BY-SA 4.0**. Or ces
deux licences sont **incompatibles dans ce sens** :

- CC BY-SA 4.0 -> GPL v3 : possible (une clause de compatibilité unidirectionnelle
  existe côté Creative Commons).
- GPL v3 -> CC BY-SA 4.0 : **impossible**. Intégrer les données GPL de
  webappanalyzer dans notre dépôt contaminerait l'ensemble et interdirait la
  publication sous CC BY-SA.

Conclusion : **on n'embarque PAS webappanalyzer**. On écrit nos propres règles de
détection, 100 % originales, donc 100 % compatibles CC BY-SA, hors-ligne, sans
dépendance ni appel réseau.

Note annexe (à garder en tête pour la boîte à outils globale) : CC BY-SA 4.0 est
une licence pensée pour les **œuvres et les données**, pas idéale pour du **code
exécutable**. Creative Commons le déconseille explicitement pour du logiciel. Le
choix de licence de la boîte à outils dans son ensemble mériterait d'être
reconsidéré (ex. une licence logicielle type MIT/GPL pour le code, CC BY-SA pour
la documentation et les données), mais cela dépasse le périmètre de ce module.


-----
2. Le constat qui rend les règles maison suffisantes
-----

Wappalyzer ne fait rien de magique : c'est du **pattern-matching** sur des signaux
déjà présents dans une capture réseau. Or l'agent EROOM collecte déjà un **HAR**
complet (`<site>/<site>.har`) qui contient toute la matière première :

- les **en-têtes de réponse** de chaque requête (`server`, `via`, `x-powered-by`,
  `cf-ray`, `x-amz-cf-id`, `x-served-by`, `set-cookie`…) ;
- les **URLs** de toutes les requêtes (scripts, polices, analytics, CDN tiers) ;
- le **HTML** des pages (balise `<meta name="generator">`, motifs de frameworks) ;
- les **cookies** posés (`Set-Cookie`).

Aucune API, aucune extension, aucun navigateur piloté ne sont nécessaires : on
relit le HAR et on applique nos règles.


-----
3. Ce qu'on peut / ne peut pas récupérer
-----

RÉCUPÉRABLE (le cœur de la stack, suffisant pour le CO2e et le rapport) :

- CDN (CloudFront, Cloudflare, Fastly, jsDelivr…) via en-têtes et hosts.
- Hébergeur cloud (S3, Vercel, Netlify, GitHub Pages…) via en-têtes ; croisé avec
  ipinfo pour fiabiliser le provider (voir section 5).
- Serveur web (nginx, Apache, IIS, LiteSpeed…) via `server`.
- Langage serveur annoncé (PHP, ASP.NET, Node/Express…) via `x-powered-by` / cookies.
- Frameworks front / SSR (Next.js, Nuxt, Gatsby, Astro, React, Vue) via HTML / URLs.
- CMS (WordPress, Drupal, Joomla, Webflow, Shopify) via `<meta generator>` / URLs.
- Analytics et tag managers (GA4, Matomo, Swetrix, Plausible, Hotjar, GTM).
- Polices (Google Fonts, Font Awesome) et bandeaux de consentement (Orejime, Axeptio…).

NON RÉCUPÉRABLE de l'extérieur :

- **Type d'instance serveur** (t3.medium, e2-standard…) : totalement invisible
  côté client. Reste une **question à poser à l'utilisateur** (elle influence le
  calcul e-footprint via le choix d'instance Boavizta dans `run_efootprint.py`).
- Backend caché : base de données, langage serveur non annoncé, framework serveur
  sans en-tête distinctif.
- Signaux masqués : certains sites vident ou falsifient leurs en-têtes (sur
  octo.com, `server:` renvoie parfois `-`). La détection est alors partielle.
- Tout ce qui ne transparaît pas dans une capture réseau standard (logique
  purement côté serveur, feature flags, etc.).

Ce que webappanalyzer ajouterait s'il était un jour branché (voir section 6) :
versions précises des libs, pixels marketing, outils A/B testing, micro-librairies
JS. **Inutile au CO2e** (le poids et les requêtes sont déjà mesurés dans le HAR),
et surtout facultatif pour le rapport documentaire visé.


-----
4. Format des règles et fonctionnement du moteur
-----

Les règles vivent dans le dict `TECH_RULES` de `detect_tech.py`. Chaque entrée :

    "Nom de la techno": {
        "cat": "CDN",                       # catégorie (cf CATEGORY_ORDER)
        "confidence": "high",               # confiance de base si signal fort
        "headers": {"via": r"cloudfront"},  # regex sur la valeur d'un en-tête
        "url": r"cdn\.jsdelivr\.net",       # regex sur les URLs de requêtes
        "meta_generator": r"WordPress",     # regex sur <meta name=generator>
        "html": r"id=[\"']__NEXT_DATA__",   # regex sur le HTML (indice faible)
        "cookie": r"^PHPSESSID=",           # regex sur un nom de cookie
    }

Hiérarchie de confiance appliquée par le moteur (`_match_rule`) :

- Un match sur `headers`, `meta_generator` ou `cookie` est un **signal fort** :
  il prend la `confidence` de base de la règle (souvent `high`).
- Un match sur `url` est **plafonné à `medium`** (un host tiers peut être partagé).
- Un match sur `html` est **plafonné à `low`** (sous-chaîne, faux positifs
  possibles ; ex. le mot "vue" apparaît dans du texte sans que Vue.js soit utilisé).

La confiance retenue pour une techno est la **plus forte** des signaux qui matchent.

Le résultat (`detect()`) est un dict :

    {
      "technologies": [{"name", "category", "confidence", "evidence"}, ...],
      "categories": {cat: [names]},
      "third_party_hosts": [...],   # hosts distincts du domaine principal
      "request_count": int
    }

Il est écrit tel quel dans `env-data.json` sous la clé `tech_stack`
(schema_version >= "1.3").


-----
5. Croisement avec ipinfo (fiabilisation du provider CO2e)
-----

Dans `build_env_data()` (`collect_env_data.py`), un croisement a lieu APRÈS ipinfo :

- Si ipinfo a conclu un provider (ex. `aws`), il fait autorité : le CDN détecté ne
  l'écrase pas.
- Si ipinfo n'a **rien conclu** mais qu'un CDN / hébergeur cloud est détecté, on
  ajoute `provider_from_tech` au bloc `server` et on remonte
  `confidence_provider` de `low`/`default` à `medium`.

Effet aval : le provider influence le choix d'instance Boavizta dans
`run_efootprint.py`, donc le CO2e de fabrication.


-----
6. Options non retenues, mais encore possibles (pour un futur mainteneur)
-----

Si le besoin de détail se confirme un jour, plusieurs pistes existent. Classées de
la plus recommandée à la moins recommandée :

a) **Téléchargement à la volée (opt-in) — évolution naturelle.**
   Récupérer les ~2500 règles de webappanalyzer **au runtime, côté utilisateur**,
   sur activation explicite (flag). Les données GPL ne sont **jamais commitées**
   dans le dépôt : elles sont téléchargées et mises en cache localement. La boîte à
   outils reste CC BY-SA (elle ne distribue pas de GPL).
   Coût : réimplémenter le moteur de matching Wappalyzer complet (headers, cookies,
   js, dom, meta, scriptSrc, html, plus les relations `implies` / `excludes` et
   l'extraction de versions), plus le download + cache + fallback si indisponible.
   C'est l'option à privilégier si on veut un jour la couverture complète.

b) **Submodule Git.**
   Pointer un submodule figé vers le dépôt GPL, séparé de notre code. L'argument
   juridique ("mere aggregation") est **fragile** dès que notre code dépend
   fonctionnellement des données : le risque de contamination réapparaît. Peu
   recommandé.

c) **Publier tout l'agent sous GPL v3.**
   Techniquement le plus simple, mais **écarté** : incompatible avec la cible
   CC BY-SA de la boîte à outils.


-----
7. Maintenance des règles
-----

Ajouter ou corriger une règle :

1. Ouvrir `detect_tech.py`, éditer le dict `TECH_RULES`.
2. Choisir le bon type de signal (préférer `headers` / `cookie` / `meta_generator`,
   plus fiables que `url`, elle-même plus fiable que `html`).
3. Écrire une regex ciblée. Attention aux ancres : pour un host, ne PAS utiliser
   `(^|\.)` (les URLs commencent par `https://`) ; utiliser un motif comme
   `cdn\.jsdelivr\.net` ou `(//|\.)mondomaine\.com`.
4. Ajuster la `confidence` de base (`high` seulement si le signal est distinctif
   et non partagé).

Tester sur le site de contrôle (octo.com) :

    python3 .claude/skills/analyse-parcours/scripts/detect_tech.py octo.com

Détection attendue sur octo.com (référence de non-régression) : Amazon CloudFront,
Cloudflare, Fastly, jsDelivr (CDN) ; Google Frontend (serveur) ; Swetrix
(analytics) ; Google Fonts (polices) ; Orejime (consentement). Le mot "vue" présent
dans le HTML ne doit PAS déclencher un faux positif Vue.js (règle `html` plafonnée
à `low` et motif exigeant `data-v-xxxxxxxx` / `__VUE__`, pas la simple sous-chaîne).

Vérifier ensuite l'intégration complète :

    python3 collect_env_data.py octo.com --refresh   # bloc tech_stack, schema 1.3
    # puis régénérer le rapport HTML -> section "Stack technique" en annexe

Si on active un jour l'enrichissement à la volée (section 6a), suivre le format
amont de webappanalyzer et NE PAS committer ses données dans le dépôt.
