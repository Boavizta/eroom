-----
Préremplissage assisté du questionnaire EOF - octo.com
-----

Date : 2026-09-10

## Objectif

Le questionnaire généré (`questionnaire-eof.md`, 59 questions) comporte, pour certaines
questions, un encart **"Ce que nous avons mesuré :"** : un rappel d'une donnée déjà collectée
automatiquement par le pipeline (HAR, CSP, Core Web Vitals, déclarations publiques...), affiché
pour aider la personne qui répond, sans jamais cocher de case à sa place.

À la demande explicite de l'utilisatrice, ce rappel a été transformé en **proposition de case
précochée**, à confirmer ou corriger, uniquement là où un tel rappel existe. Aucune réponse n'a
été inventée ou simulée pour les questions sans donnée mesurée.

## Chiffres

- **59 questions au total** dans le questionnaire.
- **20 questions portaient un rappel mesuré** : ce sont uniquement celles-là qui ont reçu une
  case précochée.
- **39 questions sont restées entièrement vides** (aucune donnée collectée ne les concerne),
  exactement comme dans le questionnaire vierge d'origine.

## Méthode et honnêteté du préremplissage

Sur les 20 questions assistées, la case proposée n'est pas toujours la plus flatteuse : le choix
suit ce que la mesure permet réellement de dire, pas un optimisme par défaut. Trois cas de figure :

1. **9 propositions franches** (positives ou négatives), quand la mesure était suffisamment claire
   pour orienter vers une option précise. Exemples : `6.3` (CI/CD) → 🟢 Facile à modifier, preuve
   d'un déploiement atomique et automatisé (24 ressources publiées en 13 s, horodatage cohérent) ;
   `1.11` (valeurs par défaut sobres) → 💡 Potentiel d'amélioration identifié, aucune règle
   d'accessibilité `@media` détectée.
2. **6 propositions "🤔 À évaluer"**, quand la mesure existe mais ne permet pas de trancher.
   Exemple : `2.3` (communication entre composants), où le rappel dit lui-même "nous ne pouvons
   pas évaluer de l'extérieur l'efficacité de leur couplage".
3. **3 propositions "Je ne sais pas"**, quand même l'assistance ne donne pas de quoi répondre.
   Exemple : le dimensionnement/élasticité (`3.6`/`3.7`), où la mesure confirme seulement que la
   plate-forme d'hébergement *peut* ajuster ses ressources, jamais si c'est activé.

## Marquage, pour ne jamais confondre une proposition avec une vraie réponse

Chaque case précochée porte une mention visible entre parenthèses, par exemple
*(proposition depuis la mesure, à confirmer)*, directement dans le texte de l'option. Ce marquage
reste dans le texte lu par un humain ; il n'affecte pas la syntaxe `- [x] ... <!-- opt:N -->` que
lit `parse_questionnaire.py`, qui continuera à traiter ces cases comme n'importe quelle réponse
cochée si elles sont conservées telles quelles.

## Fichiers concernés

- `questionnaire-eof.md` : le questionnaire **vierge** d'origine, non modifié.
- `questionnaire-eof-assistance.md` : la version avec les 20 cases précochées décrites ci-dessus,
  destinée à être relue et corrigée avant tout usage réel.

## Rappel important

Ce préremplissage n'est **pas** une réponse automatique au sens du référentiel EOF : les critères
concernés restent classés "partiel", jamais "automatisable". Toute case précochée doit être
confirmée ou corrigée par une personne avant d'être considérée comme une réponse valide.
