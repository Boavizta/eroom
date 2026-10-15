---
name: calibrer-complexite-dispatch-analyse-parcours
description: >
  Maintient la grille de niveaux (modèle économique/standard/avancé, effort
  faible/moyen/élevé) utilisée par l'orchestrateur du skill analyse-parcours
  pour résoudre, à chaque dispatch, le champ COMPLEXITE (A/B/C/D) de chaque
  bloc :::dispatch en modèle/effort concrets — sans jamais nommer de modèle
  dans le skill lui-même. À invoquer ponctuellement pour affiner cette grille
  (seuils, justifications, nouveaux cas rencontrés), jamais pour choisir un
  nom de modèle.
triggers:
  - "affine la grille de complexité du dispatch analyse-parcours"
  - "revois les paliers de complexité des blocs dispatch"
  - "/calibrer-complexite-dispatch-analyse-parcours"
version: 1.0.0
---

# Skill : Grille de complexité des sous-agents — Dispatch analyse-parcours

## Pourquoi ce skill existe

Le skill `analyse-parcours` dispatche 7 blocs `:::dispatch` par analyse (Wave 1 :
`analyse-har`, `analyse-coverage`, `collecte-cwv`, `collecte-env-data`,
`extracteur-security-headers` ; Wave 2 : `extracteur-html-css`,
`extracteur-wellknown` — voir
`analyse-parcours/skill-steps/25_dispatch-orchestration.md`). Chaque bloc
porte un champ `COMPLEXITE:` (A/B/C/D) — un palier abstrait, sans aucun nom
de modèle.

**L'agent orchestrateur résout lui-même ce palier en modèle/effort concrets,
au moment du dispatch, avec sa propre connaissance de l'environnement
d'exécution courant** (quels modèles sont disponibles dans ce harnais, lequel
est le plus économique, lequel est le plus capable). Ce skill ne fournit donc
jamais de table « palier → nom de modèle » : une telle table se périmerait à
chaque sortie de modèle et casserait l'agnosticisme recherché (le skill
`analyse-parcours` doit rester utilisable sous n'importe quel harnais/
fournisseur LLM, pas seulement Claude Code).

Ce que ce skill fournit, c'est **la grille de niveaux et sa justification
concrète** : pour chaque palier, quel niveau abstrait de modèle et d'effort
est nécessaire, et surtout *pourquoi* — pour que l'orchestrateur ait une base
de jugement solide plutôt que de deviner (et donc, par prudence, de
systématiquement choisir le modèle le plus capable en effort élevé —
exactement le gaspillage que cette logique vise à éviter).

Contrairement à l'audit RGAA (où chaque bloc porte un jugement d'expert sur
un critère d'accessibilité), les 7 blocs d'`analyse-parcours` sont tous des
**wrappers de script Python déterministe** : la variable qui change d'un
bloc à l'autre n'est pas la profondeur de jugement métier à porter, mais la
quantité de sources à croiser et la présence (ou non) d'une logique de
bascule ou de vigilance à interpréter autour du script.

## Ce qui ne doit JAMAIS figurer ici ni dans `25_dispatch-orchestration.md`

- Un nom de modèle (sonnet, haiku, opus, gpt-*, gemini-*, etc.) lié au
  dispatch des 7 blocs ci-dessus. *(Note : l'étape 45 — `collecte-env-data` /
  e-footprint — référence par ailleurs des noms de modèles IA tiers, ex.
  `claude-sonnet-4-5`, via `collect_env_data.py --set-ai-model`, pour estimer
  l'empreinte carbone d'un usage IA générative détecté sur le site audité.
  C'est un sujet homonyme sans rapport avec le dispatch de sous-agents — hors
  périmètre de ce skill, ne pas y toucher.)*
- Une valeur d'effort spécifique à un fournisseur (ex. les enums d'un harnais
  donné). On ne parle qu'en niveaux abstraits : économique/standard/avancé
  pour le modèle, faible/moyen/élevé pour l'effort.

## Ce qui ne doit JAMAIS être recalculé ici

Les signaux suivants, déjà documentés dans le texte de chaque bloc
`:::dispatch` de `25_dispatch-orchestration.md`, sont des faits stables du
pipeline `analyse-parcours`. Ne pas les réinterpréter à chaque dispatch — ils
ne dépendent d'aucun modèle :

- **Nombre de sources externes croisées par le script** pour produire un
  seul JSON consolidé (ex. `collecte-env-data` = 4 : HAR + CrUX + ipinfo +
  SimilarWeb).
- **Présence d'une bascule vers un outil/méthode alternatif**, documentée
  explicitement dans le texte du bloc (ex. `collecte-cwv` : PageSpeed →
  Lighthouse si quota dépassé). **À ne pas confondre** avec une simple
  dégradation de périmètre ou de confiance des champs (ex.
  `extracteur-security-headers` qui analyse toutes les pages du HAR au lieu
  d'une liste filtrée si `env-data.json` est absent ; `collecte-env-data` qui
  marque des champs `confidence: default` en cas d'échec réseau/clé API
  manquante) : ces dégradations changent le *périmètre* ou la *précision* du
  résultat, pas la *méthode* de calcul — elles ne comptent pas comme signal
  de palier.
- **Présence d'une vigilance de validation au-delà du simple wrapping**,
  documentée dans le texte du bloc ou dans le format de sortie JSON (ex.
  `no_js_no_css` dans `coverage-analysis.json`, `uncached_requests`/
  `duplicate_urls`/ressources bloquantes dans `har-analysis.json`, ou — cas
  particulier — la gestion d'un re-fetch réseau live potentiellement en
  échec pour `extracteur-html-css`, qui ne se contente pas de parser un
  fichier déjà sur disque).
- La **dépendance dure vs souple** entre blocs (`depends_on`/wave de
  séquencement vs dégradation documentée en cas d'ordre non garanti) : c'est
  un signal de séquencement du DISPATCH, pas un signal de palier de
  complexité en lui-même.

Si l'un de ces faits change (ex. un script est réécrit pour ajouter une
vraie bascule de méthode qu'il n'avait pas), c'est une évolution du skill
`analyse-parcours` lui-même, pas de ce skill — mettre à jour le texte du
bloc concerné directement dans `25_dispatch-orchestration.md` à cette
occasion, puis vérifier que le `COMPLEXITE` du bloc est toujours cohérent
avec la formule ci-dessous.

## Formule : signaux → palier

- **Palier de départ : A** (wrapper de script simple, aucune des conditions
  ci-dessous).
- Puis, en gardant le palier le plus élevé déclenché :
  - **≥ 3 sources externes à croiser** → au moins **C**.
  - **Bascule vers une méthode alternative** documentée explicitement
    (fallback d'outil, pas une simple dégradation de périmètre/confiance) →
    **+1 palier**.
  - **Vigilance de validation au-delà du simple wrapping** (anomalie
    détectée et signalée, ou gestion d'un échec de re-fetch réseau live sur
    des données déjà auditées) → **+1 palier**.
  - Plafond : **D**.

**Palier D** n'est atteint par aucun des 7 blocs actuels : il est réservé à
un futur bloc qui cumulerait au moins deux de ces signaux à la fois (ex. ≥3
sources externes à croiser *et* une bascule de méthode explicite). Ne jamais
monter un bloc à D « par prudence » sans qu'au moins deux signaux de la
formule soient effectivement cumulés — un simple appel API, par exemple,
n'est pas en soi un motif de palier D.

Le volume traité (nombre de pages, taille du `.har`) n'entre **pas** dans ce
calcul : il augmente le coût en tokens quel que soit le modèle, mais pas la
difficulté d'orchestration du script — ce n'est pas un signal de complexité,
c'est un signal de volume.

## Grille de niveaux (ce que l'orchestrateur consulte à chaque dispatch)

| Palier | Niveau de modèle | Niveau d'effort | Justification concrète |
|---|---|---|---|
| **A** | Économique (le plus rapide/léger disponible) | Faible | Wrapper de script Python strictement mécanique : un seul appel subprocess, lecture du JSON déjà structuré produit par le script, aucune bascule de méthode ni anomalie à interpréter — relayer un résultat déterministe. (`extracteur-wellknown`, `extracteur-security-headers`) |
| **B** | Standard | Faible | Wrapper de script avec un seul point d'attention supplémentaire : soit une bascule de méthode explicite documentée (ex. `collecte-cwv` : PageSpeed → Lighthouse), soit une vigilance de validation simple au-delà du wrapping (lire une clé d'anomalie dans le JSON produit — `no_js_no_css`, ressources bloquantes/doublons/sans-cache — et la signaler en langage naturel), soit gérer l'échec d'un re-fetch réseau live sur des pages déjà auditées (`extracteur-html-css`). Un seul signal à la fois, pas un croisement de sources. (`analyse-har`, `analyse-coverage`, `collecte-cwv`, `extracteur-html-css`) |
| **C** | Standard | Moyen | Script qui croise au moins 3 sources externes (API/fichiers) pour produire un seul JSON consolidé (ex. `collecte-env-data` : HAR + CrUX + ipinfo + SimilarWeb) : plus de surface à vérifier (cohérence entre sources, absence d'une source) qu'un wrapper simple, mais sans bascule de méthode ni anomalie supplémentaire à arbitrer en plus du croisement. (`collecte-env-data`) |
| **D** | Avancé (le plus capable disponible) | Élevé | Réservé à un futur bloc qui cumulerait au moins deux signaux de la formule à la fois (ex. ≥3 sources externes à croiser *et* une bascule de méthode explicite, ou une vigilance de validation complexe en plus du croisement de sources) : une erreur de jugement y impacterait plusieurs enrichissements à la fois. Aucun des 7 blocs actuels n'atteint ce palier. |

**Usage par l'orchestrateur** : lire `COMPLEXITE` du bloc à dispatcher,
retrouver la ligne correspondante, puis choisir — parmi les modèles/réglages
d'effort réellement disponibles dans l'environnement d'exécution courant —
ceux qui correspondent le mieux au niveau indiqué. Si l'environnement ne
propose que deux niveaux de modèle (pas trois), fusionner B et C sur le
niveau « standard » plutôt que de forcer un niveau « avancé » non justifié.

## Procédure d'affinage (invocation ponctuelle)

Ce skill ne s'invoque pas pour choisir un modèle, mais pour revoir la grille
elle-même :

1. Lire `analyse-parcours/skill-steps/25_dispatch-orchestration.md`,
   vérifier pour chaque bloc `:::dispatch` que `COMPLEXITE` est bien
   cohérent avec la formule ci-dessus appliquée aux signaux documentés dans
   son texte (nombre de sources externes, bascule de méthode explicite,
   vigilance de validation au-delà du wrapping). Corriger `COMPLEXITE` si un
   écart est trouvé (et uniquement ce champ).
2. Si l'expérience d'analyses réelles montre qu'un palier est mal calibré
   (ex. un bloc classé B a en pratique besoin du niveau C), ajuster la
   formule ou la grille ci-dessus — avec l'exemple concret qui justifie le
   changement.
3. Montrer le diff à l'utilisateur avant d'écrire quoi que ce soit : ce
   fichier et `25_dispatch-orchestration.md` pilotent toutes les analyses de
   parcours futures.

Dernière revue : 2026-10-15.
