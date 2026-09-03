# Analyse — Minimiser le nombre de questions humaines pour maximiser les réponses EOF

> Fichier intermédiaire (pas consommé par du code, pas encore décisionnel).
> Objectif : avant de concevoir un futur "mode entretien" pour `eof-audit`
> (poser des questions à un humain quand les données d'audit ne suffisent
> pas), identifier les liens entre les 70 questions du référentiel
> (54 critères détaillés + 16 questions de 🏦 0-Diagnostic rapide) pour
> qu'une même information serve à répondre à plusieurs critères, et que les
> critères restants soient regroupés en un minimum de questions composées
> plutôt que posés un par un.
>
> Méthode : lecture intégrale du texte des 70 questions (`eof-referentiel.json`),
> recherche de 3 types de liens, jamais d'inférence automatique fabriquée à
> partir d'un lien "faible" (cf. section "Liens écartés" en fin de document).

-----

## 1. Ce qui est déjà résolu sans aucune question humaine (5/70)

Inchangé depuis `eof_criteria_mapping.py`, + 1 nouveauté trouvée par cette analyse :

| id | Critère | Donnée | Confidence |
|---|---|---|---|
| 1.12 | Trackers | `tech_stack.categories['Analytics']` | medium |
| 2.1 | Technologies gourmandes | `ai_external_apis` / `tech_stack` | medium |
| 3.3 | Mix électrique région (détaillé) | `servers[].carbon_intensity_g_kwh` | high |
| 5.4 | Indicateurs de performance | `cwv.json` (seuils CWV officiels) | high |
| **0.16** *(nouveau)* | Mix électrique pays (Diagnostic rapide) | **même champ que 3.3** | high |

**0.16 est un doublon quasi exact de 3.3**, avec un avantage : ses 5 crans
sont des **seuils numériques explicites** (`> 750`, `< 500`, `< 300`,
`< 200`, `< 100` gCO2e/kWh), qui se lisent directement sur
`servers[].carbon_intensity_g_kwh` — plus précis encore que le seuil
binaire utilisé pour 3.3. Sur octo.com (381 gCO2e/kWh, Allemagne) :
tranche **"2 - < 500 gCO2e/kWh"**.

⚠️ **Ceci contredit la décision du 2026-09-03** ("Diagnostic rapide : aperçu
sans remplissage automatique"). Cette décision reste valable pour les 15
autres questions de 🏦 0 (aucune n'a de donnée). Mais pour 0.16 spécifiquement,
la donnée existe, est déjà utilisée pour 3.3, et le lien est un doublon
exact (pas une inférence) : **à valider explicitement avec l'utilisatrice
avant d'implémenter**, ce n'est pas fait dans cette analyse.

-----

## 2. Doublons exacts / quasi-exacts (même fait, formulation différente)

Une seule réponse humaine suffit pour les deux critères de chaque paire.
Aucune des deux n'a de donnée d'audit — le gain est uniquement sur le
**nombre de questions posées à l'humain**, pas sur l'automatisation.

| Paire | Textes | Nature du lien |
|---|---|---|
| **0.3 ⟺ 6.10** | "Les composants principaux sont-ils soumis à des contraintes de haute disponibilité ?" | **Texte identique mot pour mot.** Échelles différentes (0.3 : 5 crans SLA ; 6.10 : 🟢/🟡/🔴) — nécessite une table de correspondance simple (SLA 24/7 99,99% → 🔴 ; pas de SLA → 🟢) mais un seul fait à établir. |
| **0.15 ⟺ 4.1** | "Politique de suppression/archivage" vs "Mécanismes de suppression/archivage mis en place" | Même fait (politique de rétention des données), granularité quasi identique. |
| **0.11 ⟺ 1.13** | "Parcours utilisateurs fluides, intuitifs, sans friction UX/UI" vs "Principaux parcours utilisateurs optimisés fluides et efficaces" | Même fait (qualité UX des parcours), formulation quasi identique. |
| **0.12 ⟺ 1.8** | "Compatible matériel ancien + expérience fluide" vs "Support médiocre sur appareils anciens" | Même fait, **polarité inversée** (0.12 positif, 1.8 négatif) — propager avec négation. |
| **0.13 ⟺ 5.3** | "Backlog contient des pb de perf" vs "Équipe a identifié des améliorations perf et les a ajoutées au backlog" | Même fait (existence d'un backlog performance), formulation quasi identique. |

**5 paires → 10 critères couverts par 5 réponses humaines au lieu de 10.**

-----

## 3. Clusters thématiques (regroupables en une question composée)

Contrairement à la section 2, ces critères ne sont **pas le même fait** :
répondre à l'un ne répond pas automatiquement aux autres. Mais ils portent
sur le **même sujet** et peuvent être posés en **une seule interaction**
("décrivez votre gestion de X"), dont la réponse riche de l'humain permet
ensuite de renseigner chaque critère séparément — sans fabriquer de lien
logique qui n'existe pas, juste en évitant de répéter la question 6 ou 7
fois sous des angles légèrement différents.

### Cluster A — Infrastructure / FinOps (7 critères, 1 question)
`3.1` (facture réductible), `3.2` (suivi impact env.), `3.5` (mutualisation),
`3.6` (surdimensionnement), `3.7` (élasticité/auto-scaling), `3.8`
(environnements toujours actifs), `3.9` (env. de test = taille prod)

*Question suggérée* : "Décrivez la gestion de votre infrastructure : les
composants sont-ils mutualisés/dimensionnés au juste besoin, disposez-vous
d'élasticité (auto-scaling), les environnements non productifs sont-ils
coupés quand inutilisés, leur taille est-elle réduite par rapport à la
prod, et suivez-vous les coûts/l'impact environnemental de cette
infrastructure ?"

### Cluster B — Stockage et données (5 critères, 1 question)
`4.2` (bonnes pratiques BDD), `4.3` (techno adaptée), `4.4` (BDD test =
taille prod), `4.5` (doublons), `4.6` (données froides)

*(4.1 exclu : déjà apparié avec 0.15 en section 2)*

### Cluster C — Dette technique & suivi performance (6 critères, 1 question)
`5.1` (outils d'analyse statique), `5.2` (tests de charge révélateurs),
`5.6` (pile technique à jour), `5.7` (composants réglables), `5.8`
(dépendances à jour), `5.9` (pb de compatibilité identifiés)

*(5.3 exclu : déjà apparié avec 0.13 ; 5.4 déjà automatique ; 5.5 déjà
"partiel" avec indice coverage/CWV)*

### Cluster D — Maturité d'ingénierie / Facilité de changement (11 critères, 1 question)
`6.1` (observabilité), `6.2` (revues de code/pair prog), `6.3` (CI/CD),
`6.4` (tests non-régression), `6.5` (découplage métier/technique), `6.6`
(indicateurs qualité), `6.7` (documentation), `6.8` (code dupliqué), `6.9`
(autonomie équipe outillage), **+ `0.5`** (code source accessible à
l'équipe) **+ `0.6`** (compétences dispo) — ces deux questions du
Diagnostic rapide portent sur le même thème "capacité de l'équipe à agir"
que 6.9/6.2/6.7, naturellement posées dans la même interaction.

*(6.10 exclu : déjà apparié avec 0.3 en section 2)*

C'est le plus gros cluster (11 critères en une seule question) : c'est
attendu, "Facilité de changement" est structurellement la dimension la
plus organisationnelle du référentiel — c'est aussi la dimension à 0/10
répondue automatiquement, ce qui est cohérent.

### Cluster E — Architecture (3-4 critères, 1 question)
`2.2` (stratégie de compatibilité), `2.3` (séparation/communication
composants), `2.4` (lissage pics de charge), **+ `0.7`** (complexité
architecture, en cadrage/intro de la question)

*(2.1 exclu : déjà automatique ; 2.5 déjà "partiel" avec indice HAR)*

### Cluster F — Nécessité et sobriété du produit (3 critères, 1 question)
`1.1` (moyen simple existant), `1.7` (fonctionnalités utiles/utilisées),
`0.2` (fonctionnalités redondantes)

*Question suggérée* : "Le produit numérique a-t-il une alternative plus
simple pour cette action, ses fonctionnalités sont-elles toutes utilisées,
et existe-t-il des doublons avec d'autres produits/systèmes ?"

### Cluster G — Conception UX et compatibilité (7 critères, 1 question)
`1.2` (utilisateurs cibles connus), `1.3` (MAJ obligatoires tous
appareils), `1.4` (composants custom vs natifs), `1.5` (autoplay
animations/vidéos), `1.6` (adapter ressources à la config matérielle),
`1.10` (dark patterns), `1.11` (valeurs par défaut modifiables)

*(1.13 exclu : déjà apparié avec 0.11 ; 1.8 exclu : déjà apparié avec 0.12)*

**7 clusters → 42 critères couverts par 7 questions composées au lieu de 42.**

-----

## 4. Questions de Diagnostic rapide restées isolées (6)

Aucun lien fort trouvé (ni doublon, ni cluster naturel) — restent des
questions à poser telles quelles, une par une :

`0.1` (criticité du service), `0.4` (dépendances techniques), `0.8`
(taille infra), `0.9` (volume de données), `0.10` (complexité
fonctionnelle), `0.14` (fonctionnalités optimisées)

-----

## 5. Ce qui reste "partiel" (indice affiché, confirmation humaine légère)

Inchangé de `eof_criteria_mapping.py`, avec un regroupement : `1.15` et
`1.16` utilisent déjà **le même champ** (`traffic.visits_per_year`) — à
poser comme **une seule** question de confirmation, pas deux.

`1.9`, `1.14`, `{1.15+1.16}`, `2.5`, `5.5` → **5 questions de confirmation**
(au lieu de 6 critères).

-----

## 6. Bilan quantifié

| | Nombre |
|---|---|
| Critères totaux (54 détaillés + 16 Diagnostic rapide) | 70 |
| **Résolus sans aucune interaction humaine** (§1) | **5** |
| Résolus par doublon (1 réponse = 2 critères, §2) | 10 critères → 5 questions |
| Résolus par cluster thématique (§3) | 42 critères → 7 questions |
| Isolés, 1 question chacun (§4) | 6 critères → 6 questions |
| Partiels, confirmation légère (§5) | 6 critères → 5 questions |
| **Total questions humaines nécessaires** | **23** (au lieu de 65 restants un par un) |

**Résultat : 70 critères couverts par 5 réponses automatiques + 23
interactions humaines**, au lieu de 65 questions séparées si on interrogeait
chaque critère individuellement — un facteur ~2,8 de réduction du nombre
d'interactions, sans qu'aucune réponse ne soit jamais fabriquée à la place
de l'humain.

-----

## 7. Liens écartés (pour mémoire — évalués, jugés trop faibles pour être utilisés)

- **0.14 (fonctionnalités optimisées) vs 5.4 (indicateurs de performance,
  déjà automatique via CWV)** : CWV ne mesure que la performance de
  chargement frontend, pas l'efficacité algorithmique/backend que 0.14
  interroge plus largement. Propager la réponse de 5.4 vers 0.14 serait une
  extrapolation non vérifiée. **Écarté.**
- **Écart mobile/desktop dans `cwv.json` comme signal de compatibilité
  matériel ancien (1.8/0.12/5.9)** : vérifié sur octo.com — le mobile est
  systématiquement plus lent que le desktop (attendu, réseau + CPU), mais
  CrUX mobile agrège TOUS les mobiles Chrome, pas spécifiquement le
  matériel ancien de la cible. **Écarté** (aurait fabriqué un signal).
- **`device_mix`/`network_mix` d'`env-data.json`** : donnent une
  répartition mobile/desktop/réseau, mais rien sur l'ancienneté du
  matériel. Vérifié, aucun signal utilisable trouvé.
- **`tech_stack.technologies` pour 5.6/5.8 (stack/dépendances à jour)** :
  vérifié, aucune information de version dans les données détectées
  (seulement nom/catégorie/évidence HTTP) — pas automatisable depuis ce
  pipeline.
- **`README.md`/`CONTEXT.md` métier (cherché à l'Étape 10
  d'`analyse-parcours`)** : aurait pu répondre à plusieurs questions
  organisationnelles s'il existait. Absent pour octo.com. À garder en tête
  pour un futur site audité qui en fournirait un.

-----

## 8. Suite possible (non décidée, non implémentée)

1. Valider avec l'utilisatrice l'automatisation de **0.16** (§1) —
   contredit une décision précédente, à trancher explicitement.
2. Si un futur "mode entretien" est construit pour `eof-audit`, cette
   analyse donne directement sa structure : 5 questions de confirmation
   (§5) + 5 questions de doublon (§2) + 7 questions composées (§3) + 6
   questions isolées (§4) = 23 interactions, dans cet ordre de priorité
   (les clusters couvrant le plus de critères en premier).
3. Rejouer cette analyse si le référentiel change (43→54→? critères déjà
   observé) : les liens texte peuvent bouger, ne pas supposer qu'ils sont
   stables dans le temps.
