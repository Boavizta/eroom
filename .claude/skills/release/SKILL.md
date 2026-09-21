---
name: release
description: >
  Fait évoluer de manière cohérente le numéro de version du projet Agent EROOM
  et les 3 fichiers qui doivent rester synchronisés : `.claude/skills/analyse-parcours/SKILL.md`
  (champ `version:`, source de vérité, affichée dans le footer des rapports générés),
  `CHANGELOG.md` (historique) et `README.md` (ligne "Version actuelle : X" en tête
  de fichier). S'active sur "/release", "bump la version", "nouvelle version",
  "sors une release", ou toute demande de faire évoluer le numéro de version du projet.
version: 1.0.0
---

# Skill : release (Agent EROOM)

## Vue d'ensemble

Le projet Agent EROOM a un seul numéro de version, dont la source de vérité
est le champ `version:` du frontmatter de `.claude/skills/analyse-parcours/SKILL.md`
(lu dynamiquement par `generate_report_html.py` pour le H1 et le footer des
rapports générés). Deux autres fichiers doivent refléter la même valeur :

1. `CHANGELOG.md` (racine du dépôt) : une entrée par version, la plus récente en tête.
2. `README.md` (racine du dépôt) : la ligne `**Version actuelle : X.Y.Z**` juste après
   la description en une ligne du projet, avant la section "Pourquoi ce projet existe".

**Ne jamais modifier un seul de ces 3 fichiers sans les deux autres.** C'est
exactement le problème que ce skill résout : sans lui, il est facile de bumper
`SKILL.md` en oubliant `CHANGELOG.md` ou `README.md`, et les 3 sources dérivent.

## Étapes

### 1. Lire l'état actuel

- Version actuelle : champ `version:` de `.claude/skills/analyse-parcours/SKILL.md`.
- Dernier commit de bump : `git log --oneline -- .claude/skills/analyse-parcours/SKILL.md`
  puis `git show <hash>` sur le plus récent pour retrouver sa date et son message.
- Vérifier que `CHANGELOG.md` et le `README.md` sont bien alignés sur cette version
  actuelle (avant de commencer). Si l'un des deux est déjà décalé, le signaler
  explicitement à l'utilisateur avant de continuer — c'est un signal qu'une
  évolution précédente a été faite sans passer par ce skill.

### 2. Recenser ce qui a changé depuis le dernier bump

```bash
git log --oneline <hash-du-dernier-bump>..HEAD
```

Regrouper les commits par thème (pas un bullet par commit : ce serait illisible
pour une session avec beaucoup de petits fixes). S'inspirer du regroupement déjà
fait dans les entrées existantes de `CHANGELOG.md` pour le ton et le niveau de
détail attendu.

### 3. Demander le type de release à l'utilisateur

Poser la question avec `AskUserQuestion` (jamais trancher seul un numéro de
version, c'est une décision produit) :
- **Patch** (X.Y.Z+1) : correctifs, stabilisation, pas de nouvelle capacité.
- **Minor** (X.Y+1.0) : nouvelle fonctionnalité, sondes ou critères ajoutés,
  rétrocompatible.
- **Major** (X+1.0.0) : rupture (référentiel migré, format de sortie changé,
  incompatible avec les audits précédents).

Demander aussi un thème court (1 à 3 mots) pour l'entête de l'entrée changelog,
comme "Stabilisation" pour la 1.2.1 — reprendre ce même mot-clé si l'utilisateur
le redemande explicitement, sinon proposer un thème cohérent avec le contenu
recensé à l'étape 2 et le faire valider.

### 4. Rédiger l'entrée CHANGELOG.md et la faire valider avant d'écrire

Format d'une entrée (voir les entrées existantes) :

```markdown
## [X.Y.Z] - AAAA-MM-JJ — Thème

Phrase d'intro optionnelle si le contexte le justifie (ex : "pas de nouvelle
fonctionnalité majeure : ...").

- Bullet thématique 1
- Bullet thématique 2
```

Afficher le brouillon de l'entrée à l'utilisateur avant de toucher aux fichiers.

### 5. Écrire les 3 fichiers en une seule fois

Dans cet ordre, sans s'arrêter entre les trois (pour ne jamais laisser un état
incohérent visible en git status) :

1. `.claude/skills/analyse-parcours/SKILL.md` : `version: X.Y.Z`
2. `CHANGELOG.md` : nouvelle entrée en tête (juste après le chapeau, avant la
   première entrée existante)
3. `README.md` : `**Version actuelle : X.Y.Z**`

### 6. Vérifier la cohérence après coup

```bash
grep -n "version:" .claude/skills/analyse-parcours/SKILL.md
grep -n "^## \[" CHANGELOG.md | head -1
grep -n "Version actuelle" README.md
```

Confirmer à l'utilisateur que les 3 valeurs affichent bien le même numéro.

### 7. Commit

Ne committer que si l'utilisateur le demande explicitement (règle générale du
projet, non levée par ce skill). Un commit de release regroupe typiquement les
3 fichiers en un seul commit, message du type
`chore(release): passe en X.Y.Z (thème)`.

## Ce que ce skill ne fait pas

- Pas de tag git automatique (le dépôt n'utilise pas de tags à ce jour).
- Pas de publication/déploiement : uniquement la cohérence des 3 fichiers de
  version et l'historique.
- Ne décide jamais seul du numéro de version ou du contenu de l'entrée
  changelog : toujours validé avec l'utilisateur avant écriture.
