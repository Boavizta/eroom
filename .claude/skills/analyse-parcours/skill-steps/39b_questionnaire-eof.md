# Étape 39b — Questionnaire EOF (génération et relecture)

> Source : skill-steps/39b_questionnaire-eof.md. Retour : SKILL.md étape 40.

## Vue d'ensemble

Sur les 54 critères détaillés du référentiel EOF-V.1.1, l'Étape 39 (`run_eof.py`)
n'en tranche qu'une petite partie automatiquement. Le **résidu** (critères sans
réponse, ou répondus "🤔 À évaluer" / "⌛️ Évaluation en cours") peut être posé
sous forme de questions à cocher par le service audité. Deux scripts déjà
écrits et testés font ce travail :

- `generate_questionnaire.py` : lit `eof-audit-results.json` (Étape 39) et
  `questionnaire-blocs.json`, produit un fichier Markdown unique
  `questionnaire-eof.md` contenant les seules questions encore utiles, triées
  par rendement décroissant (les blocs qui débloquent le plus de critères
  passent en premier).
- `parse_questionnaire.py` : lit `questionnaire-eof.md` une fois REMPLI par le
  service audité, écrit `lots/relecture-questionnaire.json` (contrat de sortie
  de lot standard, provenance `"precise"`).

Cette étape correspond à la vague `4-questionnaire` de
`processus/manifeste-lots.json` (lots `generation-questionnaire` et
`relecture-questionnaire`), mais ne documente que les deux scripts existants,
pas la reconstruction du pipeline multi-lots complet (cf. "Ce qui reste
explicitement HORS de cette étape").

-----

## AVERTISSEMENT OBLIGATOIRE

Jamais de questionnaire vierge dans `audits/`. `generate_questionnaire.py`
refuse par défaut d'écrire dans un chemin
contenant `audits` (sortie 2, message d'erreur explicite). Raison : un
questionnaire généré est vierge, toutes ses cases restent à cocher ; s'il
atterrit dans `audits/<domaine>/`, il peut être renvoyé au client comme s'il
était à jour alors qu'il ne contient aucune réponse.

- **Génération de travail (systématique)** : sortir vers `/tmp`, jamais vers
  `audits/`.
- **`--dans-le-dossier-audit`** : réservé au moment où le questionnaire va
  effectivement être transmis au client dans la foulée. Ne pas l'utiliser
  "pour voir" ou par habitude.

-----

## Déclenchement

Étape **manuelle**, pas automatique comme l'Étape 39 : c'est une décision de
mission (le questionnaire part-il maintenant vers le service audité ?), pas
un calcul qui doit se refaire à chaque analyse. Se place après l'Étape 39
(il faut qu'`eof-audit-results.json` existe), avant ou en parallèle de
l'Étape 40 (le rapport).

-----

## Génération

```bash
python3 .claude/skills/analyse-parcours/scripts/generate_questionnaire.py <dossier-audit> --output-dir /tmp/questionnaire-<domaine>
```

- `<dossier-audit>` = le dossier contenant `eof-audit-results.json` (celui de
  l'Étape 39, ex. `audits/<domaine>/`).
- Sortie : `/tmp/questionnaire-<domaine>/questionnaire-eof.md`, un seul
  fichier, pas un découpage produit/technique (voir note manifeste plus bas).
- Si le résidu est vide (Étape 39 a déjà tout couvert), le script n'écrit
  rien et affiche `Aucun bloc à afficher (résidu vide)` : ce n'est pas une
  erreur.
- Relire le fichier généré avant tout envoi : rien ne garantit automatiquement
  qu'il est adapté au contexte de la mission.

Pour l'envoi effectif au service audité, régénérer directement dans le
dossier d'audit :

```bash
python3 .claude/skills/analyse-parcours/scripts/generate_questionnaire.py <dossier-audit> --dans-le-dossier-audit
```

Les contrôles de non-régression : `generate_questionnaire.py --autotest`
(15 cas).

-----

## Relecture (une fois le questionnaire revenu rempli)

```bash
python3 .claude/skills/analyse-parcours/scripts/parse_questionnaire.py <dossier-audit>
```

- Prérequis humain : `<dossier-audit>/questionnaire-eof.md` doit être la
  version **remplie** par le service audité (pas la version vierge produite
  sous `/tmp`).
- Écrit `<dossier-audit>/lots/relecture-questionnaire.json`.
- Une case laissée vide reste vide : aucune réponse par défaut, aucun pire
  cas. Un bloc sans exactement une case cochée ne verse rien.

Les contrôles de non-régression : `parse_questionnaire.py --autotest`
(7 cas).

-----

## AVERTISSEMENT

Ne jamais relancer `run_eof.py` seul après une relecture de questionnaire.
`run_eof.py` (Étape 39) réécrit `eof-audit-results.json` uniquement depuis les
données automatiques : il ne relit **jamais** `lots/relecture-questionnaire.json`.
Le relancer seul après une relecture de questionnaire efface donc en silence
les réponses déjà versées.

La fusion des lots (dont `relecture-questionnaire.json`) dans
`eof-audit-results.json` est le rôle de `processus/fusionner_lots.py` :

```bash
python3 processus/fusionner_lots.py <dossier-audit>
```

Puis régénérer le rapport (Étape 40) pour refléter les nouvelles réponses.

-----

## Ce qui reste explicitement HORS de cette étape

- Câbler les lots LLM de jugement (`jugement-diagnostic-rapide`,
  `jugement-dimension-1` à `jugement-dimension-6`, `porte-go-no-go`) : tous
  `"etat": "a_ecrire"` dans `processus/manifeste-lots.json`, ce ne sont pas
  (encore) des étapes scriptées de ce skill.
- Automatiser la fusion (`fusionner_lots.py`) ou la régénération du rapport
  après relecture : rappelées ci-dessus comme suite logique, pas déclenchées
  automatiquement par `parse_questionnaire.py`.
- Concevoir un nouveau processus : les deux scripts documentés ici existent
  déjà et sont testés (`--autotest`), cette étape ne fait que dire quand et
  comment les lancer.

-----

## Décisions clés (référence)

- Un seul fichier `questionnaire-eof.md`, jamais un découpage
  produit/technique : décision explicite (l'ancien découpage en deux fichiers
  envoyait 3 destinataires sur 4 dans les deux fichiers à la fois). Note :
  `processus/manifeste-lots.json` (lots `generation-questionnaire` et
  `relecture-questionnaire`) mentionne encore `questionnaire-produit-usage.md`
  et `questionnaire-technique.md` : décalage connu avec le code actuel, non
  corrigé par cette étape (cf. rapport de chantier).
- Le questionnaire est **généré**, jamais rédigé à la main : la couverture
  automatique diffère d'un service à l'autre, un questionnaire figé serait
  faux au service suivant.
- Une case vide reste vide : aucune réponse par défaut, aucun pire cas.
