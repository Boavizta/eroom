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
| `valider_coherence_cles.py` | les 8 clés canoniques sont écrites par les deux producteurs et lues par les deux consommateurs, sans nom mort ni clé inventée | `[SUCCÈS]` |
| `valider_manifeste.py` | le manifeste de lots est cohérent | `[SUCCÈS]`, 17 lots, 6 vagues |
| `check_valeurs_rapport.py --autotest` | les accidents connus du rapport sont détectés et les usages légitimes ignorés | 28 cas passés |
| `valider_sante_sondes.py` | **aucune sonde n'a échoué en silence** dans le dossier d'audit visé | `[SUCCÈS]`, ou la liste des échecs |

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
