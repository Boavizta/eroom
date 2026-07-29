-----
Guide de reconstitution de l'API interne SimilarWeb
-----

Ce guide explique comment REFAIRE la découverte de l'appel à l'API interne de
l'extension SimilarWeb, si l'extension change un jour (nouvel endpoint, nouvel
en-tête, nouvelle version qui déclenche un 403). La méthode décrite ici est celle
qui a été réellement rejouée et vérifiée le 29/07/2026, pas une procédure
théorique.

Le module concerné est `.claude/skills/analyse-parcours/scripts/similarweb_api.py`.


-----
1. Quand utiliser ce guide
-----

L'appel courant fonctionne sans compte ni cookie : il suffit d'un vrai User-Agent
de navigateur, de l'en-tête `X-Extension-Version`, et de NE PAS envoyer d'en-tête
`Origin` (CloudFront le rejette avec un 403).

Symptômes qui justifient une reconstitution :

- 403 persistant alors que l'absence d'`Origin` et un User-Agent navigateur sont
  déjà en place (donc pas le 403 "classique" documenté dans similarweb_api.py).
- L'appel répond 200 mais les champs attendus sont absents : `TopCountryShares`
  (mix pays) ou `EstimatedMonthlyVisits` (trafic).

Dans ces cas, l'extension a probablement changé d'endpoint, d'en-têtes ou de
version. La revalidation simple de la version (voir similarweb_api.md) ne suffit
plus : il faut ré-inspecter l'extension.


-----
2. Faits connus (point de départ)
-----

Valeurs relevées et vérifiées le 29/07/2026 :

- ID de l'extension (Chrome Web Store) : `hoklmmgfnpapgjgcpechhaamimifchmp`
- Version installée : `6.12.21` (manifest V3)
- Endpoint : `https://data.similarweb.com/api/v1/data`
- En-têtes envoyés par l'extension : `Content-Type: application/json`,
  `X-Extension-Version: <version>`, `redirect: follow`. PAS d'en-tête `Origin`.
- Fichier porteur de l'endpoint : `background/background.js` (l'endpoint apparait
  aussi dans options/popup/panel/content, mais l'appel réel part du background).

Ces valeurs vivent dans les constantes de `similarweb_api.py` :
`DATA_API`, `EXTENSION_VERSION`, `BROWSER_USER_AGENT`, et le dict d'en-têtes de
`fetch_domain_data()`.


-----
3. Méthode A - Récupérer et inspecter l'extension
-----

But : retrouver l'endpoint, les en-têtes et la version dans le code de
l'extension. Trois voies pour obtenir les fichiers, de la plus simple à la plus
lourde. La voie 1 est celle qui a marché cette session.

Voie 1 (recommandée, sans tiers, sans réseau) : lire l'extension déjà installée
-----

Chrome décompresse les extensions installées sur le disque. Localiser le dossier :

    ls -d ~/Library/Application\ Support/Google/Chrome/*/Extensions/hoklmmgfnpapgjgcpechhaamimifchmp/*/

Le profil peut être `Default`, `Profile 1`, `Profile 5`, etc. ; le sous-dossier
final est la version (ex. `6.12.21_0`). Cette session, le chemin réel était :

    ~/Library/Application Support/Google/Chrome/Profile 5/Extensions/hoklmmgfnpapgjgcpechhaamimifchmp/6.12.21_0/

Si l'extension n'est pas installée : l'installer depuis le Chrome Web Store (page
`https://chrome.google.com/webstore/detail/hoklmmgfnpapgjgcpechhaamimifchmp`),
l'activer une fois sur un site, puis relire le dossier ci-dessus.

Voie 2 (sans installer) : télécharger le `.crx`
-----

Télécharger le paquet via le service de mise à jour Google :

    https://clients2.google.com/service/update2/crx?response=redirect&prodversion=120&acceptformat=crx2,crx3&x=id%3Dhoklmmgfnpapgjgcpechhaamimifchmp%26uc

(ajuster `prodversion` si besoin). Ou passer par un service type CRX Extractor.
Un `.crx` est un ZIP préfixé d'un petit en-tête binaire ; `unzip` suffit :

    unzip fichier.crx -d tmp/similarweb-ext/

(ignorer l'avertissement d'octets parasites en tête d'archive).

Puis, dans le dossier obtenu (voie 1 ou 2)
-----

Relever la version :

    grep '"version"' manifest.json

Retrouver l'endpoint (chaines uniques) :

    grep -rhoE "data\.similarweb\.com[a-zA-Z0-9/._?=&-]*" . | sort -u

Attendu : `data.similarweb.com/api/v1/data` (le mix pays et le trafic viennent de
ce endpoint). On voit aussi `data.similarweb.com/api/v1/identity`,
`rank.similarweb.com/api/v1/global` et un `config.json` sur S3, non utilisés ici.

Identifier le(s) fichier(s) porteur(s) :

    grep -rlniE "data\.similarweb\.com|api/v1/data" .

Attendu : `background/background.js` (+ options/popup/panel/content).

Retrouver les en-têtes autour du fetch :

    grep -oE ".{60}X-Extension-Version.{120}" background/background.js

Cette session, l'extrait obtenu était :

    ...{headers:{"Content-Type":"application/json","X-Extension-Version":n},redirect:"follow"}...

Ce qui confirme : Content-Type json, X-Extension-Version, redirect follow, et
surtout AUCUN en-tête Origin.


-----
4. Méthode B - Capture HAR (vérification croisée)
-----

À utiliser si le JS est trop minifié pour être lisible, ou pour confirmer ce que
l'extension envoie réellement sur le réseau.

1. Extension installée et active. Ouvrir DevTools (onglet Network / Réseau).
2. Visiter un site, puis cliquer l'icône SimilarWeb dans la barre du navigateur.
3. Repérer l'appel vers `data.similarweb.com` dans la liste des requêtes.
4. Exporter en HAR (clic droit sur la requête ou export global) et lire l'entrée :
   - URL exacte (doit finir par `/api/v1/data?domain=...`).
   - Request Headers : `X-Extension-Version`, `User-Agent` (vrai navigateur),
     présence ou absence d'`Origin`.
   - Response JSON : champs `TopCountryShares`, `EstimatedMonthlyVisits`,
     `Engagments`.


-----
5. Reporter dans le code et revérifier
-----

Si une valeur a changé, mettre à jour dans `similarweb_api.py` :
`DATA_API`, `EXTENSION_VERSION`, `BROWSER_USER_AGENT`, et le dict d'en-têtes de
`fetch_domain_data()`.

Vérification directe (n'écrit aucun fichier), celle utilisée cette session :

    cd .claude/skills/analyse-parcours/scripts
    python3 -c "import similarweb_api as s; d,e=s.fetch_domain_data('octo.com'); print(e or ('OK', 'EstimatedMonthlyVisits' in d, len(d.get('TopCountryShares') or [])))"

Résultat attendu : `('OK', True, 5)` (200, trafic présent, 5 pays dans le mix).

Alternative sur un dossier existant :

    python3 similarweb_api.py <dossier_avec_env-data> --print-only


-----
6. Note d'honnêteté et dernière vérification
-----

Ce guide documente la méthode réellement rejouée et vérifiée, pas la recette exacte
de juillet 2026 (elle n'avait pas été tracée). Un futur mainteneur doit donc
regarder la date ci-dessous pour juger de la fraicheur.

- Dernière re-découverte vérifiée : 29/07/2026.
- Version d'extension relevée : 6.12.21.
- Appel de contrôle : `octo.com` -> 200 OK, `EstimatedMonthlyVisits` présent,
  `TopCountryShares` = 5 pays.

Rappel CGU : SimilarWeb est une estimation tierce, source non officielle, dont
l'usage automatisé est à la limite des conditions d'utilisation. Les analytics du
site (GA4, Matomo, logs serveur) restent prioritaires quand ils sont disponibles.
