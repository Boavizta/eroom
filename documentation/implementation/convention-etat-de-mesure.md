-----
-----
# Convention d'état de mesure
-----
-----

Comment nos extracteurs disent si leur sonde a réussi, et pourquoi cela ne change rien
au livrable que le client lit.

-----

## 1. Le problème que cette convention règle

Nos extracteurs confondent deux choses très différentes :

- **le service audité n'a pas la chose** : pas de `robots.txt`, pas de déclaration
  d'accessibilité. C'est un fait sur le service, et c'est un résultat d'audit ;
- **notre sonde a échoué** : timeout réseau, quota d'API dépassé, capture incomplète,
  fichier illisible. C'est un fait sur notre outil, et ce n'est pas un résultat d'audit.

Aujourd'hui les deux produisent la même valeur de repli. Un timeout sur `robots.txt` rend
`present: False`, exactement comme un vrai 404. Une capture sans corps HTML rend un nombre
de balises égal à zéro, ce qui fabrique un EcoIndex flatteur.

**Conséquence mesurée sur octo.com au 8 septembre 2026.** Sur les 11 captures du HAR, 6 ont
un DOM à zéro. Le rapport déduplique par URL et privilégie la capture dont le DOM a été
mesuré, ce qui masque le défaut la plupart du temps. Mais quand une URL n'a QUE des captures
sans corps HTML, le zéro passe au lecteur :

| Ligne du rapport | DOM affiché | EcoIndex | Poids | Requêtes |
|---|---|---|---|---|
| P4 `/recrutement/offers/consultant-mlops-engineer...` | 292 | B 79/100 | 557 Ko | 28 |
| P5 `/recrutement/offers/consultant-ai-engineer-senior...` | 0 | **A 91/100** | 557 Ko | 28 |

Deux offres d'emploi de même poids et de même nombre de requêtes. La seconde décroche la
meilleure note du rapport parce que ses balises n'ont jamais été comptées. **Le lecteur n'a
aucun moyen de le savoir**, et la déduplication ne peut pas le rattraper faute de seconde
capture pour cette URL.

### 1.1 La cause de ce cas précis, et la leçon qu'elle porte

Vérifié dans le HAR le 8 septembre 2026 : **le corps HTML de cette page était présent**,
33 168 caractères. Son entrée porte `response.content.encoding == "base64"`, champ que
`har_metrics.py` ne regardait pas. Il comptait donc les balises dans du base64, et en
trouvait zéro, forcément. Décodé, le document a 311 balises.

Sur les 20 entrées HTML des trois HAR archivés du dépôt, **2 sont en base64**, une par
capture d'octo.com. Le cas n'est ni théorique ni rare.

⚠️ **La leçon, et elle vaut pour tout le chantier** : la page n'était pas non mesurable, elle
était mal mesurée. Signaler un échec ne dispense jamais de vérifier d'abord si la donnée est
là. Le garde-fou qui aurait attrapé ce bug est arithmétique et tient en une phrase : **un
document HTML lu avec succès qui donne zéro balise est un `echec_analyse`, jamais un `ok`.**
Un zéro impossible doit être traité comme un échec de sonde, pas comme une mesure.

### 1.2 Résultat après correction

`har_metrics.py` honore désormais `content.encoding`. Vérifié en rejouant la déduplication du
rapport sur le HAR d'octo.com :

| Ligne | Avant | Après |
|---|---|---|
| P5 `/recrutement/offers/consultant-ai-engineer-senior...` | DOM 0, **A 91/100** | DOM 311, **B 78/100** |

Les 5 autres lignes gardent exactement leurs valeurs, et l'autotest de référence de l'EcoIndex
reste à 53 sur 100. **Les 6 lignes du rapport ont maintenant un DOM réellement mesuré** : la
règle d'affichage de la section 4.1 ne se déclenche plus sur cet audit. Elle reste nécessaire
pour les captures futures, où un corps de réponse peut manquer pour de bon.

Sur les 11 captures du HAR, 5 restent non mesurables et sont désormais dites comme telles :
3 `echec_lecture` (corps de réponse absent de la capture) et 2 `echec_analyse` (aucune entrée
HTML pour cette page). Aucune ne survit à la déduplication, donc aucune n'atteint le lecteur.

-----

## 2. Le principe

**Un échec d'extracteur n'est pas un état du service audité, c'est un état de notre
outil.** Il n'a donc rien à faire dans le livrable client. Il sort par une alerte interne.

Deux destinations séparées, et c'est tout.

-----

## 3. Destination interne : le bloc `mesure`

Chaque résultat d'extracteur porte un bloc `mesure` :

```json
"mesure": {
  "statut": "ok",
  "cible": "https://example.com/robots.txt",
  "detail": null
}
```

| Champ | Contenu |
|---|---|
| `statut` | une des cinq valeurs ci-dessous, jamais autre chose |
| `cible` | ce qui était cherché : URL, chemin de fichier, nom de champ |
| `detail` | une phrase courte expliquant l'échec, ou `null` si `statut` vaut `ok` |

Les cinq valeurs de `statut`, et elles seules :

| Valeur | Sens | La valeur produite vaut-elle quelque chose ? |
|---|---|---|
| `ok` | mesuré | oui |
| `rien_trouve` | la sonde a bien cherché, la chose est réellement absente | oui, c'est un résultat d'audit |
| `echec_reseau` | requête impossible : timeout, DNS, connexion refusée, quota d'API | **non** |
| `echec_lecture` | la ressource est là mais illisible : fichier absent, encodage cassé, JSON invalide | **non** |
| `echec_analyse` | la ressource est lue mais inexploitable : champ attendu absent, réponse 200 sans données | **non** |

**La distinction qui compte est `rien_trouve` contre `echec_*`.** `rien_trouve` est un
résultat d'audit et se traite comme tel. Les trois `echec_*` disent que nous ne savons pas.

-----

## 4. Destination client : rien de neuf

Un critère dont la mesure a échoué est traité **exactement comme non répondu** :

```json
"reponse": null,
"provenance": null
```

Il part dans le questionnaire comme les autres critères non répondus. Le lecteur voit
"aucune réponse", libellé qui existe déjà. **Il n'y a pas de septième libellé d'absence à
inventer.**

### 4.1 Le seul endroit du rapport qui change : le tableau EcoIndex

Ce tableau n'est pas un critère EOF, la règle ci-dessus ne le couvrait pas. **Arbitré par
l'utilisatrice le 8 septembre 2026** : sur une page dont le DOM n'a pas pu être compté, les
cellules EcoIndex et DOM affichent **"non mesuré"**, et la ligne reste dans le tableau.

```
Page                     | EcoIndex   | Requetes | Poids   | DOM
-------------------------|------------|----------|---------|-----------
P4 /...consultant-mlops  | B 79/100   |       28 |  557 Ko |        292
P5 /...consultant-ai     | non mesure |       28 |  557 Ko | non mesure
```

Le raisonnement : c'est l'équivalent, dans ce tableau, du "aucune réponse" imposé aux
critères EOF. **Nous ne publions pas un chiffre que nous n'avons pas.**

⛔ **La ligne n'est pas retirée**, et le poids comme le nombre de requêtes restent affichés :
ceux-là ont bien été mesurés, et faire disparaître la page recréerait précisément l'absence
silencieuse que cette convention corrige.

-----

## 5. Ce que cette convention ne touche pas, et c'est voulu

⛔ **L'axe de provenance ne gagne aucune valeur.** La provenance répond à "d'où vient cette
valeur". Un échec de mesure répond à "ma sonde a-t-elle réussi". Ce sont deux axes
indépendants : les mélanger corromprait un vocabulaire canonique protégé par validateurs, et
placer une valeur neuve au mauvais rang de précédence écraserait en silence une réponse déjà
établie.

Restent donc intacts, sans une ligne de changement :

| Fichier | Ce qui ne change pas |
|---|---|
| `processus/valider_sortie_lot.py` | `PROVENANCE_VALUES` |
| `processus/schema-sortie-lot.json` | l'énumération de provenance |
| `processus/manifeste-lots.json` | `precedence_provenance` |
| `.claude/skills/eof/scripts/generate_radar_svg.py` | `PROVENANCES_ETABLI`, `LIBELLES_PROVENANCE` |
| `processus/fusionner_lots.py` | `compute_metrics` |
| `.claude/skills/eof/scripts/generate_questionnaire.py` | `compute_residu` |

⛔ **L'arithmétique ne change pas d'une ligne.** Puisqu'un échec de mesure produit
`reponse: null`, tous les comptages existants continuent de fonctionner sans retouche :
`criteres_repondus`, `completude_pct`, `potentiel_optimisation_pct`,
`repondus_par_provenance`. Les 8 clés canoniques sont intactes et
`processus/valider_coherence_cles.py` reste vert sans exemption.

⛔ **Ne pas utiliser `sans_objet`.** Il retire le critère du dénominateur. Une mesure ratée
doit **rester** au dénominateur : nous ne savons pas, donc le potentiel reste à évaluer.
`sans_objet` garde son sens propre, "le critère ne s'applique pas".

-----

## 6. Où est l'alerte

Dans `processus/valider_sante_sondes.py`, et nulle part ailleurs.

Il relit un dossier d'audit, ramasse tous les `mesure.statut` qu'il y trouve, et **sort en 1
si un seul `echec_*` est présent**. Il ne fait aucun appel réseau.

```bash
python3 processus/valider_sante_sondes.py audits/<domaine>
```

-----

## 7. Comment le vérifier

**Par test négatif, extracteur par extracteur.** Forcer l'échec, puis contrôler deux
choses : que `statut` ne vaut pas `ok`, et que `valider_sante_sondes.py` sort en 1.

⛔ **Ne jamais conclure sur la foi d'un succès.** Un extracteur qui marche ne prouve rien
sur ce qu'il fait quand il rate : c'est précisément le défaut que cette convention corrige.
