-----
-----
# Batterie de contrôles
-----
-----

À rejouer avant tout commit. Chaque contrôle sort en 0 s'il est content, en 1 sinon.

⚠️ **Jusqu'ici cette liste n'existait que dans un handoff de session, sous `tmp/`, qui est
gitignoré.** Elle vivait donc en dehors de git, et se perdait à chaque nettoyage. C'est ce
fichier qui en tient lieu désormais.

-----

## Sans aucun appel réseau

```bash
python3 processus/valider_coherence_cles.py
python3 processus/valider_manifeste.py
python3 .claude/skills/analyse-parcours/scripts/check_valeurs_rapport.py --autotest
python3 processus/valider_sante_sondes.py audits/<domaine>
```

| Contrôle | Ce qu'il garantit | Sortie attendue |
|---|---|---|
| `valider_coherence_cles.py` | les 9 clés canoniques sont écrites par les deux producteurs et lues par les deux consommateurs, sans nom mort ni clé inventée | `[SUCCÈS]` |
| `valider_manifeste.py` | le manifeste de lots est cohérent | `[SUCCÈS]`, 17 lots, 6 vagues |
| `check_valeurs_rapport.py --autotest` | les accidents connus du rapport sont détectés et les usages légitimes ignorés | 28 cas passés |
| `valider_sante_sondes.py` | **aucune sonde n'a échoué en silence** dans le dossier d'audit visé | `[SUCCÈS]`, ou la liste des échecs |

-----

## La règle des `--autotest`, à ne pas oublier

⛔ **Cette batterie ne suffit pas.** Elle contrôle le dépôt, pas les scripts que vous venez de
modifier.

**Quand un changement touche un script qui porte un `--autotest`, rejouez cet `--autotest`.
Et rejouez celui de TOUS les scripts touchés, pas seulement celui auquel vous pensez.**

Cette erreur a été payée deux fois dans la même session, la seconde fois sans que personne la
voie. Un refactoring a renommé une fonction sans toucher ses 16 sites d'appel dans l'autotest,
qui est tombé de 15 cas sur 15 à **0 sur 15** ; les 5 contrôles de cette batterie sortaient
tous en 0 pendant ce temps, parce qu'aucun ne regarde ce que fait un script. Un filet de
sécurité crevé est plus dangereux qu'un filet absent : il rassure.

Les **huit** scripts qui portent un `--autotest`. ⚠️ Ils ne sont **plus tous** dans le même
dossier depuis la session 26 : `fusionner_lots.py` vit sous `processus/`. À lancer depuis la
racine du dépôt :

```bash
S=.claude/skills/analyse-parcours/scripts
python3 $S/check_valeurs_rapport.py       --autotest
python3 $S/generate_questionnaire.py      --autotest
python3 $S/parse_questionnaire.py         --autotest
python3 $S/valider_blocs_questionnaire.py --autotest
python3 $S/parse_html_criteria.py         --autotest
python3 $S/parse_pages_publiques.py       --autotest
python3 $S/run_eof.py                     --autotest
python3 processus/fusionner_lots.py       --autotest
```

`parse_html_criteria.py` et `parse_pages_publiques.py` sont faciles à oublier, parce qu'on ne
pense pas à un extracteur comme à un script testé. `parse_html_criteria.py` sort sur le réseau
dans son usage normal ; son `--autotest`, lui, travaille sur des fixtures et n'écrit rien.

Les deux derniers sont les **producteurs** du fichier de résultats, et leur `--autotest` est né
en session 26 : l'arithmétique du critère écarté avait été livrée sans aucun test. Ils gardent
notamment le cas qui prouve qu'une dimension entièrement écartée ne sort **jamais** 0 % de
potentiel d'optimisation, ce qui la ferait passer pour la mieux notée du rapport.

⚠️ Pour accueillir `--autotest`, leur argument positionnel est devenu optionnel (`nargs="?"`),
avec un `parser.error` qui refuse l'appel sans argument. **Ne retirez pas ce garde-fou** : sans
lui, un appel sans argument partirait avec un chemin `None`.

Pour trouver la liste à jour plutôt que de faire confiance à celle-ci. Le `--` est
indispensable, sinon `grep` prend `--autotest` pour une de ses propres options, et les
guillemets le sont aussi, sinon zsh essaie de développer `*.py` :

```bash
grep -rl -- "--autotest" .claude/skills processus "--include=*.py"
```

-----

## Avec un appel réseau, à lancer à part

```bash
.claude/skills/eof/scripts/verifier_source_sheet.sh
```

Contrôle que le référentiel EOF publié par EROOM n'a pas changé sous nos pieds. Attendu :
9 onglets identiques. **C'est le seul contrôle de la batterie qui sort sur le réseau**, vers
Google Sheets : ne le mettez pas dans une boucle.

-----

## Notes sur `valider_sante_sondes.py`

C'est le contrôle le plus récent, posé avec la convention décrite dans
`documentation/implementation/convention-etat-de-mesure.md`.

- Il prend un dossier d'audit en argument, par exemple `audits/octo.com`. Sans argument, il
  sort en 2 avec son usage.
- Il cherche récursivement, à n'importe quelle profondeur et à travers les listes, tout bloc
  `mesure` portant un `statut`.
- **Il ne sort en 1 que sur `echec_reseau`, `echec_lecture` ou `echec_analyse`.** Un
  `rien_trouve` est un résultat d'audit légitime, jamais un problème.
- Un JSON illisible dans le dossier fait sortir en 1 : c'est en soi un problème de santé.
- Un `statut` hors des cinq valeurs autorisées, ou un bloc `mesure` sans `cible`, sont
  signalés mais ne font pas échouer : ils dénoncent un extracteur mal posé, pas un audit
  malade.
- `--liste-fichiers` dit quels JSON ont été trouvés et combien de blocs `mesure` chacun porte.
  Utile quand le script ne voit rien.

⚠️ **Sur un dossier d'audit antérieur à la convention, il annonce n'avoir trouvé aucun bloc
`mesure` et sort en 0.** C'est voulu, mais lisez le message : ce n'est pas un feu vert, c'est
l'aveu qu'il n'a rien eu à contrôler. Les blocs n'apparaissent qu'après avoir rejoué les
extracteurs.
