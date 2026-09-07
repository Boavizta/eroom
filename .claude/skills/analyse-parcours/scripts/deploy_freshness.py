#!/usr/bin/env python3
"""Indices de fraîcheur et d'atomicité de déploiement, depuis le `.har`.

Pourquoi ce module : l'indice utilisé jusqu'ici pour le critère EOF 6.3
("Existe-t-il un processus CI/CD efficace ?") reposait sur
`sitemap.days_since_lastmod`. Vérifié sur octo.com le 2026-09-03 : le site
n'a **pas** de `sitemap.xml` (0 balise `<loc>`), donc l'indice ne produisait
rien du tout. Les en-têtes `Last-Modified` des ressources 1st-party, déjà
présents dans le `.har`, donnent un signal plus riche et disponible bien plus
souvent.

Trois signaux extraits, aucun appel réseau :

1. **Fraîcheur** : âge de la ressource 1st-party la plus récente, mesuré par
   rapport à la date de capture du HAR (et non par rapport à maintenant : un
   HAR de juillet analysé en septembre donnerait sinon un âge faussement
   élevé).
2. **Atomicité** : dispersion des `Last-Modified` entre ressources 1st-party,
   mesurée **uniquement sur les ressources de code** (HTML, CSS, JS). Une
   dispersion de quelques secondes signale une publication en un seul bloc
   (reconstruction complète puis mise en ligne atomique), motif typique d'une
   chaîne automatisée. Une dispersion de plusieurs mois signale des fichiers
   déposés au coup par coup.

   Les images, polices et médias sont **exclus** de ce calcul. Vérifié sur
   octo.com : mesurée sur toutes les ressources, la dispersion atteint
   644 jours, parce que les images conservent leur date de téléversement
   d'origine (2024) alors que le code est régénéré à chaque build. Mélanger
   les deux ne mesure pas l'atomicité du déploiement mais l'ancienneté du
   contenu, ce qui répond à une autre question.
3. **Horodatage de build déclaré** : paramètres d'anti-cache du type
   `?v=2026-6-10-1-1`. Quand la valeur est datée, on la compare au
   `Last-Modified` de la même ressource ; une concordance indique que le
   paramètre est généré par la chaîne de build elle-même.

Ce que ces signaux ne prouvent PAS, et pourquoi ce critère reste un indice
jamais coché automatiquement :

- Une dispersion serrée est aussi le résultat d'un `rsync` ou d'un dépôt
  manuel de l'arborescence complète. Atomicité n'est pas automatisation.
- Un déploiement récent ne dit rien de la **fréquence** des déploiements. Il
  faudrait deux audits espacés pour parler de cadence.
- Une heure de publication nocturne est suggestive d'une tâche planifiée,
  pas une preuve : rien n'interdit de publier à la main à 1 h du matin.

Vérification du décodage du paramètre daté (octo.com, deux observations
indépendantes) : le HAR du 10/07/2026 porte `?v=2026-6-10-1-1` avec un
`Last-Modified` au 10/07/2026 01:01:26, et un `curl` du 03/09/2026 renvoie
`?v=2026-8-3-1-1` avec un `Last-Modified` au 03/09/2026 01:01:31. Le mois est
donc indexé à 0 (comportement de `Date.getMonth()` en JavaScript), et le
format est année-mois-jour-heure-minute. Les deux observations concordent
exactement avec le `Last-Modified`, ce qui rend l'interprétation fiable pour
ce site. Le décodage reste tenté de façon tolérante : en cas d'échec, aucune
valeur n'est inventée.

Usage comme module :
    from deploy_freshness import analyse_har_freshness
    info = analyse_har_freshness(har_path, first_party_hosts)

Usage en ligne de commande (inspection) :
    python3 deploy_freshness.py <source_dir>
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlparse, parse_qs

RAW_DATA_DIR = "donnees-brutes-potentiellement-sensibles"

# Paramètres de requête couramment utilisés comme anti-cache de build.
_VERSION_PARAMS = ("v", "ver", "version", "rev", "build", "t", "_")

# Un horodatage de build de la forme AAAA-M-J[-H-M], mois éventuellement
# indexé à 0. Bornes larges volontairement : la validation se fait par
# concordance avec Last-Modified, pas par la forme seule.
_DATED_VERSION_RE = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})(?:-(\d{1,2})-(\d{1,2}))?$")

# Ressources régénérées à chaque build (donc porteuses de la date de
# déploiement) par opposition aux médias téléversés une fois pour toutes.
_CODE_MIME_HINTS = ("html", "javascript", "ecmascript", "css", "json", "xml")
_CODE_EXTENSIONS = (".html", ".htm", ".js", ".mjs", ".css", ".json", ".xml", ".txt", ".map")


def _is_code_resource(url, mime_type):
    """True si la ressource est du code régénéré au build, pas un média téléversé."""
    if mime_type:
        lowered = mime_type.lower()
        # Le test média passe AVANT les indices de code : `image/svg+xml`
        # contient "xml" alors que c'est un média téléversé, pas du code de build.
        if lowered.startswith(("image/", "font/", "video/", "audio/")):
            return False
        if any(hint in lowered for hint in _CODE_MIME_HINTS):
            return True
    path = urlparse(url).path.lower()
    if path.endswith(_CODE_EXTENSIONS):
        return True
    if "." not in path.rsplit("/", 1)[-1]:
        return True  # URL sans extension : page rendue côté serveur ou statique
    return False


def find_har(source_dir):
    hars = list(source_dir.glob("*.har")) or list((source_dir / RAW_DATA_DIR).glob("*.har"))
    return hars[0] if hars else None


def _parse_http_date(value):
    try:
        dt = parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        return None
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _har_capture_date(har):
    """Date de capture du HAR, depuis la première page. None si indisponible."""
    pages = har.get("log", {}).get("pages") or []
    for page in pages:
        started = page.get("startedDateTime")
        if started:
            try:
                return datetime.fromisoformat(started.replace("Z", "+00:00"))
            except ValueError:
                continue
    return None


def _first_party_hosts_from_env(source_dir):
    """Hôtes 1st-party, déduits des pages listées dans env-data.json."""
    env_path = source_dir / "env-data.json"
    if not env_path.exists():
        return set()
    env = json.loads(env_path.read_text(encoding="utf-8"))
    hosts = set()
    for page in env.get("pages") or []:
        url = page.get("url")
        if url:
            host = urlparse(url).netloc.lower()
            if host:
                hosts.add(host)
    return hosts


def _decode_dated_version(raw):
    """'2026-6-10-1-1' -> (datetime mois indexé à 0, datetime mois indexé à 1).

    Renvoie les deux lectures possibles, sans choisir : c'est la concordance
    avec Last-Modified qui tranchera. (None, None) si la forme ne colle pas.
    """
    match = _DATED_VERSION_RE.match(raw.strip())
    if not match:
        return None, None
    year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
    hour = int(match.group(4)) if match.group(4) else 0
    minute = int(match.group(5)) if match.group(5) else 0
    candidates = []
    for month_value in (month + 1, month):  # mois indexé à 0, puis indexé à 1
        if not 1 <= month_value <= 12 or not 1 <= day <= 31 or hour > 23 or minute > 59:
            candidates.append(None)
            continue
        try:
            candidates.append(datetime(year, month_value, day, hour, minute, tzinfo=timezone.utc))
        except ValueError:
            candidates.append(None)
    return candidates[0], candidates[1]


def _extract_version_stamp(url, last_modified):
    """Cherche un paramètre de version daté et vérifie s'il colle au Last-Modified.

    Retourne None si aucun paramètre daté, sinon un dict décrivant la
    concordance. Tolérance de 5 minutes : le paramètre est généralement figé
    au début du build, les fichiers écrits quelques secondes plus tard.
    """
    query = parse_qs(urlparse(url).query)
    for param in _VERSION_PARAMS:
        for raw in query.get(param, []):
            base0, base1 = _decode_dated_version(raw)
            if base0 is None and base1 is None:
                continue
            entry = {
                "parametre": f"{param}={raw}",
                "lecture_mois_indexe_0": base0.isoformat() if base0 else None,
                "lecture_mois_indexe_1": base1.isoformat() if base1 else None,
                "concorde_avec_last_modified": None,
                "ecart_secondes": None,
            }
            if last_modified is not None:
                best = None
                for label, candidate in (("mois indexé à 0", base0), ("mois indexé à 1", base1)):
                    if candidate is None:
                        continue
                    delta = abs((candidate - last_modified).total_seconds())
                    if best is None or delta < best[1]:
                        best = (label, delta)
                if best is not None:
                    entry["ecart_secondes"] = round(best[1])
                    entry["concorde_avec_last_modified"] = best[0] if best[1] <= 300 else None
            return entry
    return None


def analyse_har_freshness(har_path, first_party_hosts=None):
    """Indices de fraîcheur/atomicité de déploiement. None si rien d'exploitable."""
    with open(har_path, encoding="utf-8") as f:
        har = json.load(f)

    capture_date = _har_capture_date(har)
    entries = har.get("log", {}).get("entries") or []

    observed = []
    for entry in entries:
        url = entry.get("request", {}).get("url") or ""
        host = urlparse(url).netloc.lower()
        if not host:
            continue
        if first_party_hosts and host not in first_party_hosts:
            continue
        response = entry.get("response", {})
        headers = {h["name"].lower(): h["value"] for h in response.get("headers") or []}
        last_modified = _parse_http_date(headers.get("last-modified"))
        if last_modified is None:
            continue
        mime_type = (response.get("content") or {}).get("mimeType")
        observed.append({
            "url": url, "last_modified": last_modified,
            "est_code": _is_code_resource(url, mime_type),
        })

    if not observed:
        return None

    observed.sort(key=lambda o: o["last_modified"])
    code_only = [o for o in observed if o["est_code"]]
    # L'atomicité se mesure sur le code seul ; à défaut de code identifié, on
    # ne calcule pas de dispersion plutôt que d'en calculer une trompeuse.
    if code_only:
        spread_seconds = (code_only[-1]["last_modified"] - code_only[0]["last_modified"]).total_seconds()
        newest = code_only[-1]
    else:
        spread_seconds = None
        newest = observed[-1]
    oldest = observed[0]

    version_stamp = None
    for item in observed:
        stamp = _extract_version_stamp(item["url"], item["last_modified"])
        if stamp is not None:
            version_stamp = {**stamp, "url": item["url"]}
            break

    reference = capture_date or datetime.now(timezone.utc)
    age_days = (reference - newest["last_modified"]).total_seconds() / 86400

    return {
        "ressources_1st_party_avec_last_modified": len(observed),
        "ressources_de_code": len(code_only),
        "plus_recente": {
            "url": newest["url"],
            "last_modified": newest["last_modified"].isoformat(),
        },
        "plus_ancienne": {
            "url": oldest["url"],
            "last_modified": oldest["last_modified"].isoformat(),
        },
        "dispersion_code_secondes": round(spread_seconds) if spread_seconds is not None else None,
        "age_jours_vs_capture": round(age_days, 2),
        "reference_age": "date de capture du HAR" if capture_date else "maintenant (date de capture du HAR introuvable)",
        "heure_publication_utc": newest["last_modified"].strftime("%H:%M"),
        "horodatage_build_declare": version_stamp,
        "note": (
            "Indices de fraîcheur et d'atomicité, jamais une preuve de CI/CD : "
            "une dispersion serrée peut résulter d'un dépôt manuel de "
            "l'arborescence complète, et un déploiement récent ne dit rien de "
            "la fréquence des déploiements."
        ),
    }


def summarise(info):
    """Phrase courte pour l'annexe du rapport. None si info est None."""
    if not info:
        return None
    # Ce texte est lu par le service audité, dans le questionnaire et dans le rapport :
    # il est rédigé pour lui, sans notre vocabulaire d'outillage.
    parts = [
        f"ressource de votre site la plus récente : {info['age_jours_vs_capture']:.1f} jour(s) "
        f"avant la capture (publiée à {info['heure_publication_utc']} UTC)"
    ]
    spread = info["dispersion_code_secondes"]
    if spread is None:
        parts.append("aucune ressource de code identifiée : atomicité non mesurable")
    elif spread <= 300:
        parts.append(
            f"les {info['ressources_de_code']} ressources de code (HTML/CSS/JS) sont "
            f"publiées en {spread} s (mise en ligne en un seul bloc)"
        )
    else:
        parts.append(
            f"dispersion des publications de code : {spread / 86400:.1f} jour(s) "
            "(mises en ligne échelonnées)"
        )
    stamp = info.get("horodatage_build_declare")
    if stamp and stamp.get("concorde_avec_last_modified"):
        parts.append(
            f"les adresses de vos fichiers portent une date ({stamp['parametre']}) qui "
            f"concorde à {stamp['ecart_secondes']} s près avec la date de dernière "
            "modification déclarée par votre serveur, donc produite par votre chaîne "
            "de fabrication"
        )
    elif stamp:
        parts.append(
            f"les adresses de vos fichiers portent une date ({stamp['parametre']}) qui ne "
            "concorde pas avec la date de dernière modification déclarée par votre serveur"
        )
    return " ; ".join(parts)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source_dir")
    args = parser.parse_args()
    source_dir = Path(args.source_dir).resolve()

    har_path = find_har(source_dir)
    if not har_path:
        print(f"Erreur : aucun .har dans {source_dir} (ni dans {RAW_DATA_DIR}/).")
        sys.exit(1)

    hosts = _first_party_hosts_from_env(source_dir)
    info = analyse_har_freshness(har_path, hosts or None)
    if info is None:
        print("Aucune ressource 1st-party avec en-tête Last-Modified : indice indisponible.")
        sys.exit(0)

    print(f"HAR : {har_path.name}")
    print(f"Hôtes 1st-party retenus : {sorted(hosts) or '(tous, env-data.json absent)'}")
    print(json.dumps(info, ensure_ascii=False, indent=2))
    print(f"\nRésumé : {summarise(info)}")


if __name__ == "__main__":
    main()
