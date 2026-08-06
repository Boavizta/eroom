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

-----

## PageSpeed Insights + CrUX (données terrain)

Alternative à Lighthouse pour obtenir des données **terrain réelles** (CrUX P75).
Nécessite `GOOGLE_API_KEY` dans `.env` à la racine du projet.

### Vérifier la clé API

    .venv/bin/python3 .claude/skills/analyse-parcours/scripts/collect_cwv_pagespeed.py <dossier-audit> --check

### Collecter les CWV terrain

    .venv/bin/python3 .claude/skills/analyse-parcours/scripts/collect_cwv_pagespeed.py <dossier-audit>

Par défaut : collecte **mobile ET desktop** (`--strategy both`), conservés côte à côte.

Options :
- `--strategy mobile` | `desktop` | `both` : restreindre à un appareil (défaut : `both`)
- `--urls https://... https://...` : URLs explicites (sinon extraites du .har)

### Obtenir la clé API

Voir `documentation/setup/setup_api_keys.md`.
APIs à activer sur Google Cloud : PageSpeed Insights API + Chrome UX Report API.
Quota gratuit : 25 000 req/jour (PageSpeed), pas de limite journalière (CrUX).

-----

## Filet de sécurité du refactoring e-footprint

Trois vérificateurs, à lancer après chaque modification touchant au calcul CO2e.
Ils répondent à des questions différentes et ne se remplacent pas :

| Script | Question à laquelle il répond |
|---|---|
| `check_efootprint_contract.py` | la sortie JSON a-t-elle perdu une clé ? |
| `check_genericite.py` | le code est-il collé à un site précis ? |
| `check_efootprint_spec.py` | les refus de la bibliothèque refusent-ils encore ? |

### `check_efootprint_contract.py` — la sortie n'a rien perdu

Le rapport HTML lit `efootprint-results.json` clé par clé avec `.get()`. Une clé
manquante n'y provoque **aucune erreur** : elle produit un trou silencieux. Ce
script compare une baseline figée à la sortie fraîche.

    # Une seule fois, AVANT de modifier le code
    .venv/bin/python3 .claude/skills/analyse-parcours/scripts/check_efootprint_contract.py \
        audits/<site> --freeze

    # Après chaque modification
    .venv/bin/python3 .claude/skills/analyse-parcours/scripts/check_efootprint_contract.py \
        audits/<site> --total 174.076

Signale les chemins perdus et les changements de type (erreurs), les chemins
ajoutés (information). Code de sortie 1 en cas de problème.

Les baselines vont dans `tmp/baselines/`, hors git.

**Sa limite, à connaître** : il vérifie que les clés existent et gardent leur
type, pas que les valeurs sont justes. Un total passant de 174 à 300 kg avec
toutes les clés en place ne serait pas vu. D'où `--total`, à utiliser en
complément et non à la place.

### `check_genericite.py` — le code n'est pas collé au cas de test

Échoue si le code exécutable contient un nom de domaine, une IP, un chemin de cas
d'audit, ou **une valeur mesurée sur un site précis** (la faute la plus sournoise :
un nombre nu ressemble à une constante physique).

    .venv/bin/python3 .claude/skills/analyse-parcours/scripts/check_genericite.py
    .venv/bin/python3 .claude/skills/analyse-parcours/scripts/check_genericite.py --list-values
    .venv/bin/python3 .claude/skills/analyse-parcours/scripts/check_genericite.py --audit-exemptions

Cible par défaut : `efootprint_model/`. Tant qu'elle n'existe pas, le script sort
en 0 avec un message : ce n'est pas une panne.

Docstrings et commentaires sont exclus de l'analyse, un exemple documenté étant
légitime. Une occurrence légitime dans le code s'exempte avec sa raison :

    RAW_DATA_DIR = "..."        # genericite: ok - declaration de la constante

    TRACKER_DOMAINS = {         # genericite: ok-debut - table explicite de tiers
        "google-analytics.com",
    }                           # genericite: ok-fin

Une exemption sans raison écrite est refusée.

**Sa limite, à connaître** : il attrape le copier-coller, pas le biais de
conception. Une fonction qui suppose un site à deux serveurs, ou du HTML servi
complet, passe sans broncher. Seule l'exécution sur un second site réel prouve la
généricité. Les entiers courts (82, 317) sont signalés comme "à vérifier" plutôt
qu'affirmés : ils peuvent légitimement désigner autre chose.

**Un fichier non analysable est une violation, pas un fichier conforme.** Trou
découvert au lot 1 et corrigé : une classe dont le corps est uniquement une
docstring devenait un corps vide après nettoyage, ce qui cassait l'analyse
syntaxique et désactivait *tout* le contrôle des valeurs mesurées du fichier,
sans aucun message. Le script sortait en vert sans avoir rien examiné. Un filet
qui s'annule tout seul est pire qu'un filet absent : on se croit protégé.

### `check_efootprint_spec.py` — les garde-fous refusent encore

La bibliothèque `efootprint_model/` ne repose que sur des refus : une valeur sans
provenance est refusée, une clé qui renvoie dans le vide est refusée, une
collision de clés est refusée. Un garde-fou cassé ne produit aucune erreur, il
laisse simplement passer. Ce script vérifie donc les deux sens : une
spécification correcte passe, **et chaque faute prévue est bien refusée**. Seul
le second sens prouve quelque chose.

    .venv/bin/python3 .claude/skills/analyse-parcours/scripts/check_efootprint_spec.py
    .venv/bin/python3 .claude/skills/analyse-parcours/scripts/check_efootprint_spec.py -v

92 contrôles. Il vérifie aussi que le message d'erreur mentionne la cause : un
refus au bon endroit avec un message incompréhensible fait perdre le bénéfice du
garde-fou.

**Sa limite, à connaître** : il ne vérifie aucun chiffre de CO2e, la bibliothèque
contrôlée n'en calculant aucun. La non-régression numérique reste celle de
`check_efootprint_contract.py`.

### Toute nouvelle valeur publiée doit rejoindre la liste

Quand un chiffre mesuré sur un cas d'audit part dans un rapport, l'ajouter à
`FORBIDDEN_VALUES` avec son origine. Sinon le filet se périme sans prévenir.

De même, tout nouveau garde-fou ajouté à `efootprint_model/` doit recevoir son
contrôle de refus dans `check_efootprint_spec.py`. Un refus non testé finit par
disparaître à l'occasion d'un remaniement, en silence.
