-----
Arborescence des skills du projet (registre + recalcul)
-----

Ce fichier joue, pour l'arborescence des skills, le même rôle que
`diagrammes-analyse-parcours/SKILL.md` pour les diagrammes : c'est un REGISTRE.
Il décrit ce qui est mesuré, la source de vérité, et surtout la COMMANDE de recalcul.
L'arborescence ci-dessous est un instantané ; elle se recalcule à tout moment (section
"Recalcul"), il ne faut donc jamais l'ajuster à la main sans relancer la commande.

Unités : tailles en kilo-octets (Ko) pour tous les fichiers. Le nombre de lignes n'est
indiqué que pour les fichiers Markdown (`.md`), où il reflète l'effort de lecture ; il
n'est PAS indiqué pour les autres types (`.py`, `.sh`, `.json`, `.gitignore`), où seule
la taille en Ko est pertinente.


-----
1. Registre
-----

| Ce qui est mesuré | Emplacement | Source de vérité | Recalculer si... |
|-------------------|-------------|------------------|------------------|
| Skills du projet | `<projet>/.claude/skills/` | les fichiers eux-mêmes | ajout d'un skill/step/script, ou édition notable |

`<projet>` = `~/Documents/missions/MyAIEnv/Agent EROOM`.

Périmètre : ce registre couvre **uniquement les skills du projet**. Les skills globaux
(`~/.claude/skills/`) sont hors périmètre : ils sont partagés entre tous les projets et
ne font pas partie de ce dépôt.

Exclusions : `__pycache__/` (cache Python régénéré) et `.DS_Store` (métadonnées macOS).


-----
2. Recalcul (commande unique, pure Bash)
-----

Lister chaque fichier de skill du projet avec sa taille en Ko et son nombre de lignes,
avec un total. À relancer puis reporter le résultat dans l'arborescence de la section 3.

```bash
ROOT="$HOME/Documents/missions/MyAIEnv/Agent EROOM/.claude/skills"
find "$ROOT" -type f -not -path '*__pycache__*' -not -name '.DS_Store' -print0 \
| sort -z | while IFS= read -r -d '' f; do
    b=$(wc -c <"$f"); l=$(wc -l <"$f")
    awk -v b="$b" -v l="$l" -v f="$f" 'BEGIN{printf "%8.1f Ko  %6d l  %s\n", b/1024, l, f}'
  done
# total projet
find "$ROOT" -type f -not -path '*__pycache__*' -not -name '.DS_Store' -print0 \
| xargs -0 wc -c | tail -1 \
| awk '{printf "  -> total projet : %.1f Ko\n", $1/1024}'
```

Notes de lecture du résultat :
- La colonne "lignes" n'est à conserver, dans l'arborescence, que pour les fichiers `.md`.
- Pour un fichier non-Markdown (`.py`, `.sh`, `.json`, `.gitignore`), ne garder que les Ko.
- Un fichier sous ~0,05 Ko (ex. `.gitignore`) s'affiche "0,0 Ko" : le noter en Ko quand même,
  ce n'est pas une erreur.


-----
3. Arborescence de référence (instantané)
-----

Dernier recalcul : 2026-07-30.

Convention : `.md` → `Ko · N l` (lignes) ; autres types → `Ko` seul.

```
SKILLS DU PROJET  (Agent EROOM/.claude/skills/)
│
├── analyse-parcours/
│   ├── SKILL.md ......................... 6,7 Ko · 218 l
│   ├── skill-steps/                       [tous des .md]
│   │   ├── 10_localisation.md .......... 2,0 Ko ·  54 l
│   │   ├── 20_analyse-har.md ........... 0,8 Ko ·  20 l
│   │   ├── 25_dispatch-orchestration.md  5,3 Ko · 160 l
│   │   ├── 30_analyse-coverage.md ...... 2,3 Ko ·  91 l
│   │   ├── 35_calcul_ecoindex.md ....... 2,2 Ko ·  56 l
│   │   ├── 37_lighthouse.md ............ 3,9 Ko · 113 l
│   │   ├── 40_rapport.md ............... 1,8 Ko ·  54 l
│   │   └── 45_efootprint.md ........... 22,1 Ko · 473 l
│   ├── docs/
│   │   └── capturer-har-et-coverage.md . 8,6 Ko · 231 l
│   └── scripts/                           [code + config : Ko seul]
│       ├── generate_report_html.py ... 136,5 Ko  ⚠️ le + gros (~37 % du total)
│       ├── collect_env_data.py ........ 61,4 Ko
│       ├── run_efootprint.py .......... 27,9 Ko
│       ├── detect_tech.py ............. 18,7 Ko
│       ├── similarweb_api.py .......... 13,1 Ko
│       ├── collect_cwv_pagespeed.py ... 12,5 Ko
│       ├── har_metrics.py ............. 6,3 Ko
│       ├── run_lighthouse.sh .......... 4,6 Ko
│       ├── README-outils.md ........... 2,2 Ko ·  68 l   (.md)
│       ├── package.json ............... 0,2 Ko
│       └── .gitignore ................. 0,0 Ko
│                     └─ sous-total analyse-parcours : 339,3 Ko
│
└── diagrammes-analyse-parcours/SKILL.md . 25,6 Ko · 737 l

TOTAL projet : 364,9 Ko  (hors __pycache__ et .DS_Store)
```


-----
4. Lecture : comment les skills s'articulent
-----

Deux skills de projet.

- `analyse-parcours` : le skill principal. Il a un dossier `skill-steps/` (étapes 10 à 45)
  et un dossier `scripts/` (les outils Python/Bash). C'est lui qui produit le rapport HTML.
  L'étape 45 (`skill-steps/45_efootprint.md`) porte le calcul CO2e (ex-skill `efootprint`,
  fusionné le 2026-07-30 : il n'avait pas de script propre et dépendait entièrement des
  scripts et données d'analyse-parcours, il n'avait pas sa place comme skill séparé).
- `diagrammes-analyse-parcours` : skill outil qui génère les diagrammes PlantUML d'analyse-parcours.

À l'étape 40, `generate_report_html.py` AFFICHE une section CO2e si un
`efootprint-synthese-python.json` existe déjà ; il ne la DÉCLENCHE pas (l'étape 45 reste
optionnelle, invoquée via `/efootprint`).
Voir aussi `documentation/implementation/` pour le détail des scripts.
