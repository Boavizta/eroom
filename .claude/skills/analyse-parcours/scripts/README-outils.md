# Outils CLI - analyse-parcours

## Lighthouse CLI

Utilisé pour calculer les Core Web Vitals (LCP, INP, CLS) à l'étape 37 du skill.

### Install initiale (une seule fois)

    npm install --prefix .claude/skills/analyse-parcours/scripts/

Installe Lighthouse localement dans `scripts/node_modules/`.
La version installée est tracée dans `package-lock.json`.

### Vérifier la version installée

    scripts/node_modules/.bin/lighthouse --version

### Vérifier si une mise à jour est disponible

    npm outdated --prefix .claude/skills/analyse-parcours/scripts/

Exemple de sortie :

    Package     Current  Wanted  Latest
    lighthouse  12.3.0   12.3.0  12.5.1

### Mettre à jour Lighthouse

    npm update lighthouse --prefix .claude/skills/analyse-parcours/scripts/

Ou demander à Claude : "vérifie si Lighthouse est à jour" / "mets à jour Lighthouse".

### Fonctionnement dans le skill

`run_lighthouse.sh` utilise en priorité le binaire local (`node_modules/.bin/lighthouse`).
Si l'install locale est absente, il bascule sur `npx` (version non fixée) et propose
de lancer `npm install` pour fixer la version.

La version utilisée est affichée dans les logs :

    [Étape 37] Lighthouse 12.3.0 (install locale)
