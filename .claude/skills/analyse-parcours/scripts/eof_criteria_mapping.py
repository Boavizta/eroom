"""Table de correspondance générique entre les 54 critères détaillés du
référentiel EOF (`eof-referentiel.json`, produit par le skill `eof`) et les
données d'audit déjà collectées par `analyse-parcours`
(`env-data.json`, `audit/har-analysis.json`, `audit/coverage-analysis.json`,
`cwv.json`, `efootprint-synthese-python.json`).

Construite une fois, réutilisable pour tout site audité (même principe que
`run_efootprint.py` : générique, pas limité à octo.com). Les chemins de champs
et les exemples de valeurs ci-dessous ont été vérifiés sur `audits/octo.com/`
au moment de l'écriture (2026-09-03) ; à revalider si la structure de ces
fichiers change.

Reconnaissance de départ (54 critères passés en revue un par un) : 4 sont
automatisables depuis les données déjà collectées, 6 donnent un indice
faible/indirect (jamais une validation), et 44 sont des questions
organisationnelles ou produit qu'aucune donnée technique d'audit ne peut
renseigner (+ 0.16, seule exception "🏦 0-Diagnostic rapide", traitée à part
dans run_eof.py). Ce n'est pas un défaut de ce fichier : c'est la nature du
référentiel EOF, largement humain par construction.

Extension Phase 1 (2026-09-03, cf. plan `eof-questionnaire`) : +3
automatisables (1.5, 1.6, 1.13, via `parse_html_criteria.py` et l'extension
accessibility/best-practices de `collect_cwv_pagespeed.py`) et +5 indices
(1.4, 1.11, 6.1, 6.3, 6.6, via `parse_html_criteria.py`,
`analyze_security_headers.py`, `scan_wellknown.py`). Deux volets prévus par
le plan initial se sont révélés irréalisables en pratique et ont été
abandonnés (jamais de valeur inventée à la place) :
- 1.1 (Lighthouse a11y/Best Practices) supposait des données déjà collectées
  dans `audit/lighthouse-*.json` — inexistant : ni `run_lighthouse.sh` ni
  `collect_cwv_pagespeed.py` ne demandaient ces catégories. Corrigé en
  étendant `collect_cwv_pagespeed.py` (même appel API, catégories
  supplémentaires, aucun coût réseau additionnel) plutôt qu'abandonné.
- 1.2/1.8 (réseau CrUX "effective_connection_type", "phone_lowend") :
  l'API CrUX (`chromeuxreport.googleapis.com`) n'expose PAS ces dimensions
  (erreur HTTP 400 "invalid metric" testée en conditions réelles) — ce
  n'est pas un chantier "faible effort", la donnée n'existe simplement pas
  via cette API. 1.8 et 1.9 restent donc "partiel" comme avant Phase 1.
- 1.4/1.5 (parsing HTML/CSS) supposait de lire les corps HTML/CSS déjà
  présents dans le `.har` — vérifié : 46/311 entrées seulement ont un body
  capturé (aucune n'étant du HTML/CSS de page). `parse_html_criteria.py`
  refait donc un fetch HTTP direct des mêmes URLs déjà auditées (pas un
  nouveau périmètre de pages, juste une source de contenu différente).

Politique de sortie, stricte, pour ne jamais fabriquer un score :
- "automatisable" -> la règle peut cocher une option précise du menu à 5
  (`options_evaluation` de `eof-referentiel.json`). Si le signal est ambigu
  au moment de l'exécution (ex. valeur pile au seuil), retomber sur
  "🤔 À évaluer", jamais deviner.
- "partiel"        -> JAMAIS de case cochée automatiquement. La donnée n'est
  qu'un indice contextuel affiché en annexe ("donnée indicative : ...",
  confidence toujours "low" ou "medium", jamais "high"), le critère reste
  "je ne sais pas" dans le référentiel rempli.
- absent de MAPPING -> "aucune_donnee" par défaut : aucun champ ne le
  renseigne, le critère reste "je ne sais pas", sans entrée dédiée ici (44
  critères dans ce cas — lister leurs ids un par un n'apporterait rien).

Ce module ne contient QUE la table de correspondance (données), pas la
logique d'exécution des règles : celle-ci est prévue dans `run_eof.py`, pas
encore écrit (cf. plan d'architecture, section "Ce qui reste explicitement
HORS de ce plan").
"""

MAPPING = {
    "1.12": {
        "critere_court": "Le produit exploite-t-il des données inutiles (tracking non essentiel) ?",
        "categorie": "automatisable",
        "champ_donnee": "env-data.json: tech_stack.categories['Analytics'] (liste des technos détectées) ; har_summary.efootprint.third_party_share",
        "regle": (
            "Si aucune techno de catégorie 'Analytics' n'est détectée -> "
            "'✅ Point fort confirmé'. Si au moins une est détectée -> "
            "'💡 Potentiel d'amélioration identifié' (jamais '✅' dans ce cas : "
            "la détection ne dit rien de la finalité du traceur - mesure "
            "d'audience légitime vs marketing tiers -, seulement de sa présence)."
        ),
        "confidence_max": "medium",
        "note": "Détecte uniquement ce qui transite côté client (HAR) ; un tracking côté serveur (ex. logs) est invisible.",
    },
    "2.1": {
        "critere_court": "Le produit utilise-t-il des technologies dont l'impact environnemental est significatif (IA générative, blockchain) sans justification claire ?",
        "categorie": "automatisable",
        "champ_donnee": "env-data.json: ai_external_apis (dict, vide si aucun host IA détecté) ; tech_stack.technologies[].category",
        "regle": (
            "Si ai_external_apis est vide ET aucune techno de category "
            "IA/Blockchain listée -> '✅ Point fort confirmé'. Si au moins un "
            "host IA ou une techno blockchain est détecté -> "
            "'💡 Potentiel d'amélioration identifié' (la détection ne juge pas "
            "si l'usage est justifié, seulement sa présence - jamais '🚫 Non "
            "applicable' automatique)."
        ),
        "confidence_max": "medium",
        "note": "Un appel IA fait côté backend (jamais visible dans le HAR client) est invisible à cette règle - un 'aucun signal' n'est jamais une preuve d'absence.",
    },
    "2.5": {
        "critere_court": "Les résultats de calculs ou de requêtes coûteux sont-ils mis en cache plutôt que recalculés à chaque fois ?",
        "categorie": "partiel",
        "champ_donnee": "audit/har-analysis.json: duplicate_urls (liste {url, count}) ; http_codes (part de 304)",
        "regle": (
            "Une URL à fort 'count' dans duplicate_urls, avec une faible part "
            "de réponses 304 dans http_codes, est un indice de requête répétée "
            "potentiellement non cachée - jamais une preuve : un beacon "
            "analytics appelé à chaque interaction produit le même motif sans "
            "être un problème de cache."
        ),
        "confidence_max": "low",
        "note": "Risque réel de confondre un beacon de mesure d'audience (comportement normal) avec un calcul serveur recalculé par erreur - afficher l'URL et le count en annexe, jamais cocher automatiquement.",
    },
    "3.3": {
        "critere_court": "L'hébergement est-il situé dans une région où le mix électrique est fortement carboné ?",
        "categorie": "automatisable",
        "champ_donnee": "env-data.json: servers[].carbon_intensity_g_kwh, servers[].country_code (itérer TOUS les serveurs 1st-party de la liste, pas seulement le premier - cf. un host 1st-party à l'infra différente est un serveur distinct)",
        "regle": (
            "Si au moins un serveur de la liste a carbon_intensity_g_kwh au-dessus "
            "d'un seuil (repère : ~250 gCO2/kWh, mix électrique européen moyen) -> "
            "'💡 Potentiel d'amélioration identifié'. Si tous sont en dessous -> "
            "'✅ Point fort confirmé'."
        ),
        "confidence_max": "high",
        "note": "La donnée carbon_intensity (ipinfo + table carbone) est déjà confidence 'high' en source ; ne couvre que les serveurs identifiés depuis le HAR, jamais une infra invisible (BDD/service auto-hébergé derrière l'applicatif).",
    },
    "5.4": {
        "critere_court": "Les indicateurs de performance (Core Web Vitals) sont-ils bons ?",
        "categorie": "automatisable",
        "champ_donnee": "cwv.json (liste par page : lcp, inp, cls, strategy mobile/desktop, source='crux')",
        "regle": (
            "Seuils officiels Google : LCP > 4s, INP > 500ms, ou CLS > 0.25 "
            "sur AU MOINS une page -> '💡 Potentiel d'amélioration identifié' "
            "('poor', sans ambiguïté). Toutes les pages sous les seuils "
            "'good' (LCP<=2.5s, INP<=200ms, CLS<=0.1) -> "
            "'✅ Point fort confirmé'. Zone intermédiaire ('needs improvement') "
            "sans aucune page 'poor' -> '🤔 À évaluer' (ambigu, ne pas trancher)."
        ),
        "confidence_max": "high",
        "note": "Données CrUX terrain réelles (source='crux'), pas un lab test - déjà la mesure la plus fiable de tout le mapping.",
    },
    "1.9": {
        "critere_court": "Le produit nécessite-t-il une connexion à haut débit ?",
        "categorie": "partiel",
        "champ_donnee": "env-data.json: har_summary.efootprint.data_transferred_bytes_real (poids réel transféré)",
        "regle": "Un poids de page élevé est un indice indirect de besoin de bande passante - une page lourde n'implique pas forcément un besoin de haut débit (dépend aussi de la tolérance au temps de chargement de l'usage).",
        "confidence_max": "low",
        "note": "Proxy de poids, pas une mesure du besoin réel de débit.",
    },
    "1.14": {
        "critere_court": "Les écrans/pages principaux sont-ils conçus de façon légère ?",
        "categorie": "partiel",
        "champ_donnee": "env-data.json: pages[].size_kb (comparaison entre pages du même parcours)",
        "regle": "Une page nettement plus lourde que les autres du même parcours est un indice de conception moins légère - ne juge pas la qualité de conception elle-même (contenu justifié vs superflu).",
        "confidence_max": "low",
        "note": "Proxy de poids, pas de \"clarté de conception\".",
    },
    "1.15": {
        "critere_court": "Le service est-il fréquemment utilisé au regard de sa consommation de ressources ?",
        "categorie": "partiel",
        "champ_donnee": "env-data.json: traffic.visits_per_year / traffic.monthly_visits (estimation SimilarWeb)",
        "regle": "Donne un ordre de grandeur de fréquentation, pas un jugement de proportionnalité entre usage et ressources consommées (qui suppose de connaître l'architecture déployée).",
        "confidence_max": "medium",
        "note": "Source tierce à marge large (cf. étape 20c d'efootprint) - un chiffre, pas une comparaison.",
    },
    "1.16": {
        "critere_court": "Le volume d'utilisateurs justifie-t-il l'infrastructure déployée ?",
        "categorie": "partiel",
        "champ_donnee": "env-data.json: traffic.visits_per_year",
        "regle": "Même champ que 1.15 : donne le chiffre de trafic, pas la comparaison à l'infrastructure réellement déployée (dimensionnement serveur non mesuré de façon fiable, cf. efootprint-synthese-python.json où server_type/instance_type sont souvent des défauts de script, pas des observations).",
        "confidence_max": "medium",
        "note": "Ne jamais croiser avec server_type/instance_type d'efootprint-synthese-python.json si leur source est 'default_script' - ce serait fabriquer un jugement à partir d'un défaut technique, pas d'une mesure.",
    },
    "1.5": {
        "critere_court": "Y a-t-il des animations/vidéos/sons lus automatiquement ?",
        "categorie": "automatisable",
        "champ_donnee": "html-css-criteria.json: pages[].has_autoplay_media (HTML re-fetché en direct, cf. note du script — le .har ne contient pas les corps HTML)",
        "regle": (
            "Aucune page avec <video autoplay> ni <audio autoplay> -> "
            "'✅ Point fort confirmé'. Au moins une page concernée -> "
            "'💡 Potentiel d'amélioration identifié'."
        ),
        "confidence_max": "high",
        "note": "Ne détecte que l'attribut HTML autoplay au chargement, pas un autoplay déclenché en JS après coup (angle mort connu).",
    },
    "1.6": {
        "critere_court": "Est-il possible d'adapter les ressources à la configuration matérielle de l'utilisateur ?",
        "categorie": "automatisable",
        "champ_donnee": "html-css-criteria.json: pages[].adaptive_img_ratio (srcset/<picture>) ET css.media_query_count",
        "regle": (
            "'✅' seulement si AUCUNE page n'a un adaptive_img_ratio à 0 (avec des "
            "images) ET qu'au moins 3 media queries CSS distinctes existent. "
            "'💡' seulement si NI srcset/<picture> NI media query ne sont trouvés nulle "
            "part. Sinon (signal mixte : ex. media queries nombreuses mais une page "
            "sans image adaptative) -> '🤔 À évaluer' (contrainte déterministe : deux "
            "signaux discordants ne sont jamais tranchés au doigt mouillé)."
        ),
        "confidence_max": "medium",
        "note": "Deux proxys distincts (images responsive, CSS adaptative) fusionnés prudemment ; ne mesure pas l'adaptation JS (ex. qualité vidéo dynamique).",
    },
    "1.13": {
        "critere_court": "Les principaux parcours utilisateurs sont-ils optimisés pour être fluides et efficaces ?",
        "categorie": "automatisable",
        "champ_donnee": "cwv.json: accessibility_score_pct (API PageSpeed Insights, catégorie accessibility, mêmes appels que les CWV)",
        "regle": (
            "Score d'accessibilité >= 90 sur TOUTES les pages/stratégies -> "
            "'✅ Point fort confirmé'. Score < 60 sur au moins une -> "
            "'💡 Potentiel d'amélioration identifié'. Zone 60-90 sans aucune page "
            "< 60 -> '🤔 À évaluer' (ambigu, ne pas trancher)."
        ),
        "confidence_max": "high",
        "note": "Proxy accessibilité (pas directement 'fluidité de parcours') — le référentiel n'a pas de critère a11y dédié dans les 54, celui-ci est le plus proche sémantiquement. À corroborer humainement.",
    },
    "1.4": {
        "critere_court": "La conception comprend-elle des composants personnalisés plutôt que des composants natifs ?",
        "categorie": "partiel",
        "champ_donnee": "html-css-criteria.json: pages[].native_buttons vs pages[].custom_role_buttons",
        "regle": "Un ratio custom/natif élevé est un indice de composants réinventés plutôt que natifs - ne couvre que les boutons (proxy partiel, pas tous les composants UI personnalisés).",
        "confidence_max": "low",
        "note": "Détection HTML statique uniquement (post-hydratation React/Vue le DOM réel diffère potentiellement) — indice, jamais une preuve.",
    },
    "1.11": {
        "critere_court": "Sobriété par défaut : préférences système respectées (mouvement réduit, thème) ?",
        "categorie": "partiel",
        "champ_donnee": "html-css-criteria.json: css.has_prefers_reduced_or_scheme",
        "regle": "Présence de @media (prefers-reduced-motion) ou (prefers-color-scheme) dans le CSS chargé est un indice de sobriété par défaut - l'absence n'est pas une preuve d'absence de sobriété (peut être géré autrement, ex. JS).",
        "confidence_max": "low",
        "note": "Détection syntaxique simple (présence de la règle), pas de vérification que le comportement réel change en conséquence.",
    },
    "6.1": {
        "critere_court": "Existe-t-il un dispositif d'observabilité efficace pour le produit ?",
        "categorie": "partiel",
        "champ_donnee": "security-headers-analysis.json: worst_page.grade (score sécurité local, proxy de maturité prod)",
        "regle": "Un score sécurité élevé (grade A/B) est un indice indirect de maturité opérationnelle générale, jamais une preuve d'observabilité (métriques/logs/traces) - donnée totalement invisible côté client.",
        "confidence_max": "low",
        "note": "Proxy très indirect (rigueur sécurité != observabilité) ; affiché en annexe seulement, jamais coché.",
    },
    "6.3": {
        "critere_court": "Existe-t-il un processus CI/CD efficace ?",
        "categorie": "partiel",
        "champ_donnee": "har-analysis.json: http_codes/dominant_http_version (part HTTP/2) ; wellknown-scan.json: sitemap.days_since_lastmod",
        "regle": "HTTP/2 généralisé et/ou sitemap récent (<30j) sont des indices indirects de maturité de déploiement - ne mesurent ni la fréquence de déploiement réelle ni l'existence d'un pipeline CI/CD (le contenu peut être mis à jour manuellement).",
        "confidence_max": "low",
        "note": "Deux proxys faibles et indirects, jamais combinés en une réponse automatique.",
    },
    "6.6": {
        "critere_court": "Existe-t-il des indicateurs permettant de suivre la qualité des logiciels ?",
        "categorie": "partiel",
        "champ_donnee": "cwv.json: best_practices_score_pct ; security-headers-analysis.json: worst_page.grade ; wellknown-scan.json: security_txt.present",
        "regle": "Un score Best Practices élevé et/ou un security.txt bien formé sont des indices de pratiques de qualité outillées - ne prouvent jamais l'existence d'indicateurs de qualité suivis en interne (SonarQube, etc., invisibles côté client).",
        "confidence_max": "low",
        "note": "Trois proxys faibles combinés en annexe informative seulement, jamais un critère cochable automatiquement.",
    },
    "5.5": {
        "critere_court": "Les parcours critiques (les plus fréquents) sont-ils optimisés en priorité ?",
        "categorie": "partiel",
        "champ_donnee": "audit/coverage-analysis.json (JS/CSS inutilisé par page) ; cwv.json (par page)",
        "regle": "Suppose que les pages effectivement auditées sont les parcours les plus fréquents du site - hypothèse non vérifiée par les données disponibles (pas de classement de fréquentation par page).",
        "confidence_max": "low",
        "note": "Le \"critique\"/\"fréquent\" n'est jamais mesuré : seul le contenu des pages auditées l'est.",
    },
}
