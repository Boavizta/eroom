# Étape 37 — CWV via Lighthouse

**Quand :** après l'étape 35, avant l'étape 40.

---

## Flux automatique

### Cas 1 : cwv.json absent

1. Lancer le script sans URLs : il extrait lui-même toutes les URLs uniques depuis le HAR.

```bash
bash .claude/skills/analyse-parcours/scripts/run_lighthouse.sh <dossier-audit>
```

Le script déduplique les URLs (`log.pages[].title`) avant de lancer Lighthouse, donc chaque page n'est analysée qu'une seule fois même si elle apparaît plusieurs fois dans le parcours.

3. Afficher la progression :
```
[Étape 37] Lighthouse CWV — analyse de N page(s) via npx...
  -> page_1 : https://...
  -> page_2 : https://...
[Étape 37] cwv.json généré.
```

4. Continuer vers l'étape 40.

### Cas 2 : cwv.json déjà présent

Afficher :
```
[Étape 37] cwv.json déjà présent — Lighthouse skippé.
```
Passer directement à l'étape 40.

### Cas 3 : l'utilisateur demande "relance Lighthouse"

Supprimer `cwv.json` du dossier d'audit, puis reprendre depuis le Cas 1.

---

## Si Lighthouse échoue

Afficher un warning et continuer sans CWV :
```
[Étape 37] Lighthouse indisponible (npx absent ou pages inaccessibles).
Le rapport continuera sans CWV. Pour relancer : "relance Lighthouse".
```

Causes possibles :
- `npx` absent (Node.js non installé)
- Pages derrière authentification (Chrome headless sans session)
- Réseau bloqué

---

## Limites

- Mesures "lab" (simulation réseau), pas données terrain réelles
- Pages derrière login non supportées
- Résultats peuvent différer du terrain selon la connexion

Pour des données terrain réelles, fournir un `cwv.json` manuel (voir docs/capturer-har-et-coverage.md).
