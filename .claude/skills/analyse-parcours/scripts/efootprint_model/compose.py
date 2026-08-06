#!/usr/bin/env python3
"""
Fusion et validation de spécifications. ZÉRO import e-footprint.

TROIS RESPONSABILITÉS, ET RIEN D'AUTRE
--------------------------------------
1. `compose()`   : fusionner plusieurs fragments de spécification en un site.
2. `validate_spec()` : vérifier la cohérence des renvois entre clés.
3. `collect_sources()` : rassembler toutes les provenances pour le rapport.

La construction du modèle e-footprint n'est PAS ici. Ce fichier reste du Python
pur, donc exécutable et testable sans la librairie installée.

POURQUOI LA FUSION EST UN MODULE À PART
---------------------------------------
Un vrai site est rarement un archétype pur : un site vitrine avec une boutique
et un agent conversationnel, c'est trois archétypes combinés. Chaque archétype
est une transformation qui produit un fragment ; `compose()` les réunit. Le
point délicat est la collision de clés : deux fragments qui nomment tous deux
leur serveur "web" doivent produire une ERREUR, jamais un écrasement silencieux.
Un écrasement fait disparaître un serveur du modèle sans rien signaler, et le
total baisse pour une raison introuvable.
"""

from dataclasses import replace

from .spec import (
    AudienceSpec,
    JobSpec,
    JourneySpec,
    ServerSpec,
    SiteSpec,
    SpecError,
    StepSpec,
    ThirdPartyHost,
    Traced,
)

# ---------------------------------------------------------------------------
# Fusion
# ---------------------------------------------------------------------------

# Les collections fusionnées, avec le nom lisible utilisé dans les messages
# d'erreur. L'ordre n'a pas d'importance fonctionnelle.
_MERGED = (
    ("servers", "serveur"),
    ("jobs", "traitement"),
    ("steps", "étape"),
    ("journeys", "parcours"),
)


def compose(*fragments, name=None, audience=None, journeys=None,
            third_party_hosts=None, notes=()):
    """Fusionne des fragments de spécification en un seul `SiteSpec`.

    fragments : des SiteSpec, typiquement produits par des archétypes.
    name      : nom du site résultant. Par défaut celui du premier fragment.
    audience  : audience du site. Si aucun fragment n'en porte et qu'aucune n'est
                fournie, le résultat n'en a pas ; c'est au constructeur du modèle
                de dire s'il peut s'en passer, pas à la fusion.
    journeys  : remplace les parcours des fragments. Un archétype décrit des
                étapes ; l'enchaînement réel est une décision de l'audit, pas de
                l'archétype.
    third_party_hosts : hôtes tiers observés, comptés en réseau seulement.

    COLLISIONS : deux fragments qui déclarent la même clé lèvent SpecError, avec
    UNE exception. Deux ServerSpec de même clé dont l'`evidence` désigne la même
    infrastructure sont MUTUALISÉS : c'est le cas normal quand deux archétypes
    s'appliquent au même serveur web. Sans cette règle, il faudrait dupliquer le
    serveur et son empreinte de fabrication serait comptée deux fois.

    Deux ServerSpec de même clé dont l'evidence DIFFÈRE restent une erreur : ce
    sont deux machines qui se disputent un nom.
    """
    fragments = [f for f in fragments if f is not None]
    for fragment in fragments:
        if not isinstance(fragment, SiteSpec):
            raise SpecError(
                "compose() attend des SiteSpec, reçu "
                f"{type(fragment).__name__}. Un archétype doit retourner une "
                "spécification complète, pas un fragment d'objet."
            )

    if not fragments and name is None:
        raise SpecError("compose() sans fragment ni nom : rien à composer. "
                        "Fournir au moins `name` pour construire un site vide.")

    resolved_name = name or fragments[0].name

    merged = {attr: [] for attr, _ in _MERGED}
    seen = {attr: {} for attr, _ in _MERGED}

    for fragment in fragments:
        for attr, label in _MERGED:
            for item in getattr(fragment, attr):
                previous = seen[attr].get(item.key)
                if previous is None:
                    seen[attr][item.key] = item
                    merged[attr].append(item)
                    continue
                if attr == "servers" and _same_infrastructure(previous, item):
                    fused = _fuse_servers(previous, item)
                    seen[attr][item.key] = fused
                    merged[attr][merged[attr].index(previous)] = fused
                    continue
                raise SpecError(
                    f"collision de clé sur le {label} \"{item.key}\" entre deux "
                    f"fragments de \"{resolved_name}\". Renommer l'un des deux "
                    "avec un préfixe distinct. La fusion ne choisit jamais à "
                    "votre place : écraser en silence ferait disparaître un "
                    f"{label} du modèle."
                )

    # L'audience explicite l'emporte. Sinon on prend celle des fragments, à
    # condition qu'ils n'en portent pas deux différentes : le trafic d'un site
    # est unique, deux audiences signalent une erreur de composition.
    resolved_audience = audience
    if resolved_audience is None:
        candidates = [f.audience for f in fragments if f.audience is not None]
        distinct = {a.key: a for a in candidates}
        if len(distinct) > 1:
            raise SpecError(
                f"\"{resolved_name}\" : {len(distinct)} audiences différentes "
                f"dans les fragments ({', '.join(sorted(distinct))}). Un site a "
                "un seul trafic. Passer l'audience retenue à compose(audience=...)."
            )
        resolved_audience = candidates[0] if candidates else None

    resolved_journeys = tuple(journeys) if journeys is not None \
        else tuple(merged["journeys"])

    resolved_third_party = tuple(third_party_hosts) if third_party_hosts is not None \
        else _merge_third_party(fragments)

    archetypes = []
    for fragment in fragments:
        for archetype in fragment.archetypes:
            if archetype not in archetypes:
                archetypes.append(archetype)

    all_notes = list(notes)
    for fragment in fragments:
        for note in fragment.notes:
            if note not in all_notes:
                all_notes.append(note)

    spec = SiteSpec(
        name=resolved_name,
        servers=tuple(merged["servers"]),
        jobs=tuple(merged["jobs"]),
        steps=tuple(merged["steps"]),
        journeys=resolved_journeys,
        audience=resolved_audience,
        third_party_hosts=resolved_third_party,
        archetypes=tuple(archetypes),
        notes=tuple(all_notes),
    )
    validate_spec(spec)
    return spec


def _same_infrastructure(server_a, server_b):
    """Deux ServerSpec décrivent-ils la même machine ?

    Exige que les DEUX portent une preuve, et que les preuves concordent. Sans
    preuve, on ne conclut pas : mutualiser sur la seule égalité des clés
    fusionnerait deux serveurs distincts qu'un archétype aurait nommés
    identiquement par défaut.
    """
    if server_a.evidence is None or server_b.evidence is None:
        return False
    return server_a.evidence.identity == server_b.evidence.identity


def _fuse_servers(base, other):
    """Complète `base` avec les champs que seul `other` renseigne.

    Ne remplace JAMAIS une valeur déjà présente : le premier fragment garde la
    main. Un champ renseigné différemment par les deux est signalé, parce que
    c'est un désaccord de modélisation sur la même machine, pas un détail à
    arbitrer en silence.
    """
    updates = {}
    for field_name in ("server_type", "country", "carbon_intensity", "provider",
                       "instance_type", "storage_gb", "base_ram", "base_compute",
                       "power", "carbon_footprint_fabrication", "pue"):
        mine = getattr(base, field_name)
        theirs = getattr(other, field_name)
        if theirs is None:
            continue
        if mine is None:
            updates[field_name] = theirs
            continue
        if mine.value != theirs.value:
            raise SpecError(
                f"le serveur \"{base.key}\" reçoit deux valeurs de "
                f"\"{field_name}\" : {mine.value!r} et {theirs.value!r}. Les "
                "deux fragments désignent la même infrastructure mais ne sont "
                "pas d'accord. Trancher explicitement avant la composition."
            )

    notes = list(base.notes) + [n for n in other.notes if n not in base.notes]
    updates["notes"] = tuple(notes)
    return replace(base, **updates)


def _merge_third_party(fragments):
    """Réunit les hôtes tiers des fragments, un seul enregistrement par hôte.

    Le premier vu gagne : les comptages viennent du même HAR, les réunir par
    addition les compterait deux fois.
    """
    merged = {}
    for fragment in fragments:
        for host in fragment.third_party_hosts:
            merged.setdefault(host.host, host)
    return tuple(merged.values())


# ---------------------------------------------------------------------------
# Validation des renvois entre clés
# ---------------------------------------------------------------------------

def validate_spec(spec):
    """Vérifie qu'aucune clé ne renvoie dans le vide et qu'aucune n'est doublée.

    Ces contrôles ne peuvent pas vivre dans les dataclasses : une `StepSpec` ne
    connaît que des clés de traitement, elle n'a aucun moyen de savoir si le
    traitement existe. Seul le site entier le sait.

    Lève SpecError au premier problème. Retourne le site inchangé, pour pouvoir
    écrire `spec = validate_spec(spec)`.
    """
    if not isinstance(spec, SiteSpec):
        raise SpecError(f"validate_spec() attend un SiteSpec, reçu "
                        f"{type(spec).__name__}.")

    owner = f"SiteSpec[{spec.name}]"

    for attr, label in _MERGED:
        _check_unique_keys(getattr(spec, attr), owner, label)
    _check_unique_hosts(spec.third_party_hosts, owner)

    server_keys = set(spec.server_keys)
    job_keys = set(spec.job_keys)
    step_keys = set(spec.step_keys)
    journey_keys = set(spec.journey_keys)

    for job in spec.jobs:
        if job.server_key not in server_keys:
            raise SpecError(
                f"{owner} : le traitement \"{job.key}\" est attribué au serveur "
                f"\"{job.server_key}\", qui n'existe pas. "
                f"Serveurs déclarés : {_listing(server_keys)}."
            )

    for step in spec.steps:
        for job_key in step.jobs:
            if job_key not in job_keys:
                raise SpecError(
                    f"{owner} : l'étape \"{step.key}\" déclenche le traitement "
                    f"\"{job_key}\", qui n'existe pas. "
                    f"Traitements déclarés : {_listing(job_keys)}."
                )

    for journey in spec.journeys:
        for step_key in journey.steps:
            if step_key not in step_keys:
                raise SpecError(
                    f"{owner} : le parcours \"{journey.key}\" passe par l'étape "
                    f"\"{step_key}\", qui n'existe pas. "
                    f"Étapes déclarées : {_listing(step_keys)}."
                )

    if spec.audience is not None and spec.audience.journey_key is not None:
        if spec.audience.journey_key not in journey_keys:
            raise SpecError(
                f"{owner} : l'audience \"{spec.audience.key}\" renvoie au "
                f"parcours \"{spec.audience.journey_key}\", qui n'existe pas. "
                f"Parcours déclarés : {_listing(journey_keys)}."
            )

    # Les étapes hors parcours ne sont PAS traitées ici : voir orphan_steps() et
    # require_calculable() juste en dessous, ainsi que la note qui les précède.
    return spec


# ---------------------------------------------------------------------------
# Réserves : ce qui n'empêche pas de décrire, mais empêche de publier
# ---------------------------------------------------------------------------
# Une étape rattachée à aucun parcours n'est visitée par personne : son empreinte
# n'entre dans aucun total. Le modèle se construit quand même et le chiffre est
# simplement plus bas, sans rien indiquer.
#
# Le refus a donc bien lieu, mais PAS au même moment que les autres : décrire un
# site par morceaux (les pages d'abord, les parcours ensuite) est un usage
# légitime, et bloquer dès la description l'interdirait. Le risque, lui, n'existe
# qu'à partir du moment où un chiffre est calculé, donc publiable.
#
# D'où la séparation :
#   validate_spec()      -> ne dit rien, la description reste libre
#   orphan_steps()       -> liste les réserves, pour les afficher
#   require_calculable() -> refuse, à l'entrée du calcul
#
# Décision de l'utilisatrice, à respecter en aval : au moment du calcul, la
# personne qui lance l'audit doit pouvoir ARBITRER en direct (rattacher l'étape,
# la retirer, ou passer outre en connaissance de cause) plutôt que subir un
# refus sec. Deux contraintes sur cette interaction :
#   - sans réponse possible (exécution automatique, sans clavier), le défaut est
#     le REFUS. Un choix par défaut favorable publierait un total incomplet.
#   - l'arbitrage retenu doit être TRACÉ dans le rapport (bloc model.decisions),
#     sinon c'est un correctif silencieux, exactement ce qu'on veut éviter.


def orphan_steps(spec):
    """Étapes déclarées qu'aucun parcours ne traverse.

    Vide si le site ne déclare encore aucun parcours : à ce stade rien n'est
    orphelin, la description est simplement en cours. Distinguer les deux
    importe, sinon un site en travaux afficherait toutes ses étapes en réserve.
    """
    if not spec.journeys:
        return ()
    used = {key for journey in spec.journeys for key in journey.steps}
    return tuple(sorted(set(spec.step_keys) - used))


def unused_jobs(spec):
    """Traitements déclarés mais déclenchés par aucune étape.

    Ne fausse aucun total, contrairement à une étape orpheline : c'est seulement
    du poids mort dans le modèle. À signaler, jamais à refuser.
    """
    triggered = {job_key for step in spec.steps for job_key in step.jobs}
    return tuple(sorted(set(spec.job_keys) - triggered))


# Tous les codes de réserve existants, énumérés une fois. Source de vérité pour
# le contrôle "toute réserve propose une issue" : le déduire d'une spécification
# d'exemple ne marcherait pas, aucune spécification ne déclenchant les quatre à
# la fois (une spécification vide n'a pas d'étape, donc pas d'étape orpheline).
RESERVE_CODES = (
    "steps_hors_parcours",
    "aucun_parcours",
    "aucune_etape",
    "aucune_audience",
)


def calculation_reserves(spec):
    """Réserves qui rendent un chiffre publié faux, en (code, message).

    Ce que la fonction NE renvoie pas est aussi important : un traitement non
    déclenché n'y figure pas, parce qu'il ne change aucun total.

    Retourner des codes plutôt que du texte seul permet à l'appelant de proposer
    l'arbitrage adapté à chaque réserve, au lieu d'un message unique.
    """
    reserves = []

    orphans = orphan_steps(spec)
    if orphans:
        reserves.append((
            "steps_hors_parcours",
            f"{len(orphans)} étape(s) ne figurent dans aucun parcours : "
            f"{_listing(orphans)}. Elles ne seront visitées par personne, donc "
            "leur empreinte n'entrera pas dans le total. Le chiffre publié "
            "serait plus bas que la réalité décrite."
        ))

    if not spec.journeys:
        reserves.append((
            "aucun_parcours",
            "aucun parcours n'est déclaré. Sans parcours, aucune étape n'est "
            "visitée et le total serait vide de tout usage."
        ))

    if not spec.steps:
        reserves.append((
            "aucune_etape",
            "aucune étape n'est déclarée. Le modèle n'aurait aucun usage à "
            "calculer."
        ))

    if spec.audience is None:
        reserves.append((
            "aucune_audience",
            "aucune audience n'est déclarée. Sans volume de trafic, il n'y a "
            "rien à multiplier : le total serait nul."
        ))

    return tuple(reserves)


def require_calculable(spec, *, accepted_reserves=()):
    """Porte d'entrée du calcul : refuse une spécification qui produirait un
    chiffre faux, sauf réserves EXPLICITEMENT acceptées.

    accepted_reserves : codes de réserve que la personne qui lance l'audit a
    choisi d'assumer. L'acceptation est un acte volontaire, jamais un défaut :
    appeler cette fonction sans rien passer refuse toute réserve.

    Retourne les réserves acceptées, en (code, message), pour que l'appelant les
    inscrive dans le rapport. Les rendre plutôt que les taire est le point
    important : une réserve assumée doit rester lisible dans le livrable, sinon
    l'arbitrage disparaît et le chiffre paraît sans réserve.
    """
    validate_spec(spec)

    reserves = calculation_reserves(spec)
    accepted_codes = set(accepted_reserves)

    unknown = accepted_codes - {code for code, _ in reserves}
    if unknown:
        # Accepter une réserve qui ne s'applique pas est presque toujours un
        # code recopié de travers. Le signaler évite qu'une acceptation traîne
        # dans une commande et couvre plus tard une réserve réelle.
        raise SpecError(
            f"réserve(s) acceptée(s) qui ne s'appliquent pas à "
            f"\"{spec.name}\" : {_listing(unknown)}. "
            f"Réserves en cours : {_listing(code for code, _ in reserves)}."
        )

    blocking = [(code, message) for code, message in reserves
                if code not in accepted_codes]
    if blocking:
        details = "\n".join(f"  - [{code}] {message}" for code, message in blocking)
        raise SpecError(
            f"SiteSpec[{spec.name}] : {len(blocking)} réserve(s) empêchent un "
            f"calcul publiable :\n{details}\n"
            "Corriger la spécification, ou assumer la réserve en passant son "
            "code à accepted_reserves — auquel cas elle sera écrite dans le "
            "rapport, pas passée sous silence."
        )

    return tuple((code, message) for code, message in reserves
                 if code in accepted_codes)


# Arbitrages proposables pour chaque réserve, dans l'ordre où les présenter.
# Ces libellés vivent ici, à côté de la définition des réserves, pour qu'ajouter
# une réserve sans proposer d'issue soit visible tout de suite : une réserve
# bloquante sans arbitrage ne laisse à la personne qu'un refus sans porte.
#
# La ligne de commande y puisera pour poser la question en direct (lot 5). Le
# dernier choix de chaque liste est l'acceptation, jamais le premier : l'ordre
# d'affichage suggère une préférence, et corriger vaut mieux qu'assumer.
RESERVE_ARBITRATIONS = {
    "steps_hors_parcours": (
        "rattacher ces étapes à un parcours (le total les comptera)",
        "les retirer de la spécification (elles ne décrivent pas ce site)",
        "calculer sans elles, en l'assumant (le total sera plus bas, et le "
        "rapport le dira)",
    ),
    "aucun_parcours": (
        "déclarer le parcours suivi par les visiteurs",
        "renoncer au calcul pour l'instant",
    ),
    "aucune_etape": (
        "décrire au moins une page visitée",
        "renoncer au calcul pour l'instant",
    ),
    "aucune_audience": (
        "renseigner le trafic annuel, même approximatif et signalé comme tel",
        "renoncer au calcul pour l'instant",
    ),
}


def arbitrations_for(code):
    """Issues proposables pour une réserve, ou () si la réserve n'en propose pas.

    Retourne un tuple vide plutôt que de lever : une réserve sans arbitrage
    reste bloquante et c'est le comportement sûr. Mais elle doit être repérable,
    d'où `reserves_without_arbitration()`.
    """
    return RESERVE_ARBITRATIONS.get(code, ())


def reserves_without_arbitration():
    """Codes de réserve qu'aucun arbitrage ne couvre.

    Sert de contrôle : une réserve ajoutée sans issue proposée place la personne
    devant un refus sans solution. Vérifié par check_efootprint_spec.py.
    """
    return tuple(sorted(set(RESERVE_CODES) - set(RESERVE_ARBITRATIONS)))


def _check_unique_keys(items, owner, label):
    seen = set()
    for item in items:
        if item.key in seen:
            raise SpecError(f"{owner} : le {label} \"{item.key}\" est déclaré "
                            "deux fois.")
        seen.add(item.key)


def _check_unique_hosts(hosts, owner):
    seen = set()
    for host in hosts:
        if host.host in seen:
            raise SpecError(f"{owner} : l'hôte tiers \"{host.host}\" est "
                            "déclaré deux fois.")
        seen.add(host.host)


def _listing(keys):
    """Liste triée et lisible, ou une mention explicite quand il n'y a rien.

    "aucun" plutôt qu'une liste vide : sur une erreur de clé, savoir que RIEN
    n'est déclaré oriente vers une cause différente qu'une faute de frappe.
    """
    keys = sorted(keys)
    return ", ".join(f"\"{k}\"" for k in keys) if keys else "aucun"


# ---------------------------------------------------------------------------
# Collecte des provenances
# ---------------------------------------------------------------------------

# Où chercher des Traced, et sous quel chemin les annoncer. Le chemin sert à
# retrouver la valeur dans le modèle depuis le rapport : "server:web.storage_gb"
# se lit sans documentation.
_TRACED_SCOPES = (
    ("servers", "server"),
    ("jobs", "job"),
    ("steps", "step"),
)


def iter_traced(spec):
    """Parcourt tous les `Traced` du site, en (chemin, champ, traced).

    Parcourt la SPÉCIFICATION, pas le modèle construit : donc utilisable sans
    e-footprint et sans avoir lancé le moindre calcul. C'est ce qui permet de
    contrôler la traçabilité AVANT de produire un chiffre.
    """
    for attr, prefix in _TRACED_SCOPES:
        for item in getattr(spec, attr):
            for field_name, value in vars(item).items():
                if isinstance(value, Traced):
                    yield f"{prefix}:{item.key}", field_name, value

    if spec.audience is not None:
        for field_name, value in vars(spec.audience).items():
            if isinstance(value, Traced):
                yield f"audience:{spec.audience.key}", field_name, value


def collect_sources(spec):
    """Rassemble les provenances pour le bloc `sources` du JSON de résultats.

    Une entrée par (chemin, champ), dans l'ordre de parcours. Pas de
    déduplication par source : le rapport doit pouvoir dire quel PARAMÈTRE vient
    de quelle source, et regrouper par source perdrait précisément ce lien.
    """
    entries = []
    for path, field_name, traced in iter_traced(spec):
        entry = {"path": path, "field": field_name}
        entry.update(traced.as_dict())
        entries.append(entry)
    return entries


def untraced_fields(spec):
    """Champs portant une valeur sans provenance, en (chemin, champ, valeur).

    Le garde-fou des dataclasses couvre les champs CRITIQUES. Cette fonction
    couvre le reste : elle ne bloque pas, elle rend visible. Sans elle, on ne
    saurait pas combien de valeurs non tracées un modèle contient, et le rapport
    afficherait des badges "défaut" sans qu'on sache lesquels sont évitables.
    """
    return tuple(
        (path, field_name, traced.value)
        for path, field_name, traced in iter_traced(spec)
        if not traced.has_source
    )


def confidence_summary(spec):
    """Compte les Traced par niveau de confiance.

    Donne en une ligne la solidité globale d'un modèle. Utile comme repère de
    non-régression : un refactoring qui fait glisser des valeurs de "high" vers
    "default" a perdu de la traçabilité en route, ce qu'aucun total en kilos ne
    révélerait.
    """
    counts = {}
    for _, _, traced in iter_traced(spec):
        counts[traced.confidence] = counts.get(traced.confidence, 0) + 1
    return counts


# ---------------------------------------------------------------------------
# Serveur principal
# ---------------------------------------------------------------------------

def primary_server(spec):
    """Le serveur qui alimente les clés scalaires historiques du JSON.

    Le fichier de résultats porte depuis l'origine des clés au singulier
    (provider, instance_type, storage_gb). Quand le modèle contient plusieurs
    serveurs, il faut décider LEQUEL elles décrivent, sans quoi le rapport
    afficherait un serveur arbitraire, changeant d'une exécution à l'autre.

    Critère : le plus d'octets transférés, mesuré dans le HAR. C'est le serveur
    qui porte le trafic, donc celui qu'on décrirait spontanément comme "le"
    serveur du site.

    Départage explicite quand les octets sont inconnus ou à égalité : le nombre
    de requêtes, puis l'ordre alphabétique de la clé. L'ordre alphabétique n'a
    aucun sens physique, mais il est STABLE, et c'est tout ce qu'on lui demande :
    à égalité, mieux vaut un choix arbitraire reproductible qu'un choix
    dépendant de l'ordre de lecture du HAR.

    Retourne None si le site n'a aucun serveur.
    """
    if not spec.servers:
        return None

    def sort_key(server):
        evidence = server.evidence
        transferred = (evidence.transferred_bytes or 0) if evidence else 0
        requests = (evidence.request_count or 0) if evidence else 0
        return (-transferred, -requests, server.key)

    return sorted(spec.servers, key=sort_key)[0]


def servers_note(spec):
    """Phrase à écrire dans le JSON quand le modèle contient plusieurs serveurs.

    Sans elle, un lecteur voit `provider` et `instance_type` au singulier et en
    conclut que le site tient sur une machine. La note dit ce que ces clés
    décrivent réellement et ce qu'elles laissent de côté.
    """
    if len(spec.servers) <= 1:
        return None
    main = primary_server(spec)
    others = [s.key for s in spec.servers if s.key != main.key]
    return (
        f"Le modèle contient {len(spec.servers)} serveurs. Les clés au "
        f"singulier ci-dessus décrivent le serveur principal "
        f"(\"{main.key}\", celui qui porte le plus d'octets). Les autres "
        f"({_listing(others)}) sont modélisés à part et figurent dans le bloc "
        "\"model\", avec leur propre empreinte."
    )
