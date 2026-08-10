#!/usr/bin/env python3
"""
Spécifications déclaratives d'un service web, pour modélisation e-footprint.

ZÉRO import e-footprint dans ce fichier. C'est une contrainte, pas un hasard :
ces structures doivent être testables sans la librairie installée et sans
réseau. La construction du modèle e-footprint est le travail d'un autre module.

LE PRINCIPE CENTRAL : LA SOURCE VOYAGE AVEC LA VALEUR
-----------------------------------------------------
Toute grandeur qui entre dans le calcul est un `Traced` : la valeur, son unité
et sa provenance sont le MÊME objet. Il est donc impossible d'écrire un chiffre
sans dire d'où il vient, parce qu'il n'existe pas de champ où poser un nombre
nu.

Sur les champs CRITIQUES (temps utilisateur, poids transféré, type d'instance),
une valeur sans provenance fait ÉCHOUER la construction. Le raisonnement : un
chiffre non tracé qui atterrit dans un rapport ressemble à une mesure. Mieux
vaut une erreur bruyante à la construction qu'une fausse mesure publiée.

LE VOCABULAIRE DE CONFIANCE N'EST PAS LIBRE
-------------------------------------------
`CONFIDENCE_LEVELS` reproduit EXACTEMENT les sept niveaux reconnus par
`_confidence_badge()` dans `generate_report_html.py`. Un niveau inventé ici
serait affiché tel quel, en chaîne brute, à la place du badge. D'où la
validation à la construction.

GÉNÉRICITÉ
----------
Aucune valeur par défaut chiffrée tirée d'un site réel n'a sa place dans ce
fichier. Une spécification qui ne reçoit rien ne doit rien pouvoir inventer :
c'est ce qui garantit qu'un chiffre publié vient des données du site analysé.
Contrôlé mécaniquement par `check_genericite.py`.
"""

from dataclasses import dataclass, field
from numbers import Real
from typing import Any, Mapping, Optional, Tuple

# ---------------------------------------------------------------------------
# Vocabulaire
# ---------------------------------------------------------------------------

# Les sept niveaux de `_confidence_badge()`, dans l'ordre décroissant de
# fiabilité. Ne pas en ajouter sans ajouter le badge correspondant au rapport.
#   high               : collecté (API, HAR, mesure directe)
#   medium             : estimé (inféré à partir d'une donnée collectée)
#   low                : supposé (hypothèse assumée, argumentée)
#   default            : niveau historique conservé pour les JSON déjà produits
#   default_efootprint : valeur par défaut de la LIBRAIRIE e-footprint
#   default_script     : valeur fixée par NOS scripts — distinction volontaire,
#                        pour ne pas faire passer nos choix pour ceux de l'outil
#   unjustified        : précisé à la main, sans justification vérifiable
CONFIDENCE_LEVELS = (
    "high",
    "medium",
    "low",
    "default",
    "default_efootprint",
    "default_script",
    "unjustified",
)

# Deux natures de valeur, qui deviendront deux classes e-footprint distinctes
# (SourceValue pour une grandeur physique, SourceObject pour un libellé
# catégoriel comme un nom de fournisseur ou un type d'instance). La distinction
# est faite ICI, dans le Python pur, pour que le constructeur n'ait pas à
# deviner à partir du type Python.
KINDS = ("value", "object")


class SpecError(ValueError):
    """Spécification invalide : incohérence structurelle ou provenance manquante.

    Volontairement une exception, jamais un avertissement. Une spécification
    incohérente qui continue produit un chiffre, et un chiffre est cru.
    """


# ---------------------------------------------------------------------------
# Traced : l'unité de traçabilité de toute la bibliothèque
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Traced:
    """Une valeur et sa provenance, indissociables.

    value       : le nombre (kind="value") ou le libellé (kind="object")
    unit        : unité e-footprint sous forme de texte ("kB", "ms", "GB_stored",
                  "cpu_core", "g/kWh", "dimensionless"). Obligatoire pour une
                  grandeur, interdite pour un libellé. Reste du texte : la
                  conversion en unité e-footprint appartient au constructeur,
                  pas à la spécification.
    source_name : d'où vient la valeur, en clair ("CrUX", "mesure HAR",
                  "défaut du script"). Ce n'est pas forcément une publication :
                  nommer un défaut du script EST une provenance.
    source_url  : lien vérifiable si la source en a un.
    confidence  : un des CONFIDENCE_LEVELS.
    comment     : ce que le lecteur du rapport doit savoir en plus, notamment
                  les LIMITES de la valeur (période de la mesure, biais connu).
    kind        : "value" ou "object".
    """

    value: Any
    unit: Optional[str] = None
    source_name: Optional[str] = None
    source_url: Optional[str] = None
    confidence: str = "default"
    comment: Optional[str] = None
    kind: str = "value"

    def __post_init__(self):
        if self.confidence not in CONFIDENCE_LEVELS:
            raise SpecError(
                f"niveau de confiance inconnu : {self.confidence!r}. "
                f"Attendu un de {', '.join(CONFIDENCE_LEVELS)}. "
                "Un niveau hors liste s'afficherait en chaîne brute dans le "
                "rapport, à la place du badge."
            )
        if self.kind not in KINDS:
            raise SpecError(
                f"nature de valeur inconnue : {self.kind!r}. "
                f"Attendu un de {', '.join(KINDS)}."
            )

        if self.kind == "value":
            if isinstance(self.value, bool) or not isinstance(self.value, Real):
                raise SpecError(
                    f"une grandeur (kind=\"value\") doit être un nombre, "
                    f"reçu {type(self.value).__name__} : {self.value!r}. "
                    "Pour un libellé, utiliser kind=\"object\"."
                )
            if not self.unit:
                raise SpecError(
                    f"unité manquante pour la grandeur {self.value!r}. "
                    "Une grandeur sans unité est inexploitable et se convertit "
                    "silencieusement de travers. Utiliser \"dimensionless\" "
                    "pour un ratio."
                )
        else:
            if not isinstance(self.value, str) or not self.value:
                raise SpecError(
                    "un libellé (kind=\"object\") doit être une chaîne non vide, "
                    f"reçu {self.value!r}."
                )
            if self.unit:
                raise SpecError(
                    f"unité {self.unit!r} sur un libellé {self.value!r} : "
                    "un libellé n'a pas d'unité."
                )

    @property
    def has_source(self):
        """La provenance est-elle renseignée ? (nom obligatoire, lien facultatif)"""
        return bool(self.source_name and self.source_name.strip())

    def as_dict(self):
        """Forme sérialisable, pour le bloc `sources` du JSON de résultats."""
        return {
            "value": self.value,
            "unit": self.unit,
            "source_name": self.source_name,
            "source_url": self.source_url,
            "confidence": self.confidence,
            "comment": self.comment,
            "kind": self.kind,
        }


# --- Fabriques : le niveau de confiance vient du MODE d'obtention -----------
# Passer par ces fabriques évite la faute la plus courante : annoncer "high"
# sur une valeur inférée. Le nom de la fabrique dit ce qui s'est passé.

def measured(value, unit, source_name, source_url=None, comment=None):
    """Valeur COLLECTÉE : mesure directe (HAR, API, en-tête de réponse)."""
    return Traced(value, unit, source_name, source_url, "high", comment)


def estimated(value, unit, source_name, source_url=None, comment=None):
    """Valeur INFÉRÉE à partir d'une donnée collectée (calcul, pondération)."""
    return Traced(value, unit, source_name, source_url, "medium", comment)


def assumed(value, unit, source_name, source_url=None, comment=None):
    """Valeur SUPPOSÉE : hypothèse assumée, dont le comment doit dire pourquoi."""
    return Traced(value, unit, source_name, source_url, "low", comment)


def library_default(value, unit, comment=None, source_url=None):
    """Valeur par défaut de la LIBRAIRIE e-footprint. Provenance : la librairie."""
    return Traced(value, unit, "défaut e-footprint", source_url,
                  "default_efootprint", comment)


def script_default(value, unit, comment=None):
    """Valeur par défaut de NOS scripts. À ne jamais confondre avec la précédente :
    la confondre revient à faire endosser nos choix par l'outil."""
    return Traced(value, unit, "défaut du script d'audit", None,
                  "default_script", comment)


def unjustified(value, unit, comment=None):
    """Valeur précisée à la main sans justification vérifiable : choix ACTIF,
    donc à afficher comme tel, mais non vérifié."""
    return Traced(value, unit, "précisé à la main, sans justification", None,
                  "unjustified", comment)


# Variantes "libellé" des trois fabriques utiles pour un champ catégoriel
# (fournisseur, type d'instance, pays, type de serveur).

def measured_label(value, source_name, source_url=None, comment=None):
    """Libellé COLLECTÉ (ex. fournisseur déduit d'un en-tête de réponse)."""
    return Traced(value, None, source_name, source_url, "high", comment, "object")


def estimated_label(value, source_name, source_url=None, comment=None):
    """Libellé INFÉRÉ (ex. pays déduit d'une adresse IP)."""
    return Traced(value, None, source_name, source_url, "medium", comment, "object")


def assumed_label(value, source_name, source_url=None, comment=None):
    """Libellé SUPPOSÉ, dont le comment doit dire sur quoi repose l'hypothèse."""
    return Traced(value, None, source_name, source_url, "low", comment, "object")


def script_default_label(value, comment=None):
    """Libellé par défaut de NOS scripts (ex. type d'instance faute de mieux)."""
    return Traced(value, None, "défaut du script d'audit", None,
                  "default_script", comment, "object")


# ---------------------------------------------------------------------------
# Garde-fou des champs critiques
# ---------------------------------------------------------------------------

def require_traced(value, owner, field_name, *, kind=None, critical=False):
    """Vérifie qu'un champ est bien un `Traced` exploitable.

    `critical=True` exige en plus une PROVENANCE. Les champs critiques sont ceux
    qui pilotent directement un chiffre publié : temps utilisateur, poids
    transféré, type d'instance. Sur ceux-là, une valeur sans provenance est
    refusée à la construction.

    Retourne la valeur (ou None si le champ est absent et non critique).
    """
    if value is None:
        if critical:
            raise SpecError(
                f"{owner} : le champ critique \"{field_name}\" est absent. "
                "Il pilote un chiffre publié, il ne peut pas être deviné."
            )
        return None
    if not isinstance(value, Traced):
        raise SpecError(
            f"{owner} : \"{field_name}\" doit être un Traced, reçu "
            f"{type(value).__name__} ({value!r}). Une valeur nue n'est pas "
            "acceptée : la provenance et la valeur sont le même objet."
        )
    if kind and value.kind != kind:
        raise SpecError(
            f"{owner} : \"{field_name}\" attend kind=\"{kind}\", "
            f"reçu kind=\"{value.kind}\"."
        )
    if critical and not value.has_source:
        raise SpecError(
            f"{owner} : \"{field_name}\" vaut {value.value!r} sans provenance. "
            "C'est un champ critique : renseigner source_name. Nommer un défaut "
            "du script est une provenance acceptable ; ne rien nommer non."
        )
    return value


def _require_key(value, owner, field_name):
    """Une clé doit être une chaîne non vide : elle sert d'identité dans les
    index et dans les messages d'erreur."""
    if not isinstance(value, str) or not value.strip():
        raise SpecError(f"{owner} : \"{field_name}\" doit être une clé texte "
                        f"non vide, reçu {value!r}.")
    return value


# ---------------------------------------------------------------------------
# Preuve : ce que les données du site disent d'une infrastructure
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Evidence:
    """Ce que le HAR permet d'affirmer sur une infrastructure, et rien de plus.

    Sert deux usages : justifier dans le rapport pourquoi tel serveur a été
    modélisé, et permettre à `compose()` de reconnaître que deux fragments
    parlent de la même machine.

    `cache_header_seen` est distingué de `cache_hit_ratio` à None parce que les
    deux situations ne se ressemblent pas : aucun en-tête de cache observé est
    une INFORMATION sur l'hébergement, alors qu'un ratio incalculable est une
    absence de mesure. Confondre les deux fait croire à une détection réussie
    là où il n'y a rien.
    """

    hosts: Tuple[str, ...] = ()
    ips: Tuple[str, ...] = ()
    request_count: Optional[int] = None
    transferred_bytes: Optional[int] = None
    cache_hit_ratio: Optional[float] = None
    cache_header_seen: bool = False
    note: Optional[str] = None

    def __post_init__(self):
        object.__setattr__(self, "hosts", tuple(self.hosts))
        object.__setattr__(self, "ips", tuple(self.ips))

    @property
    def identity(self):
        """Signature d'infrastructure, pour comparer deux Evidence.

        Volontairement les HÔTES ET les IP ensemble, en ensembles complets. Une
        IP partagée ne suffit PAS à conclure à une infrastructure commune : un
        cas réel de validation présente deux sous-domaines distincts derrière
        une même adresse. Exiger l'égalité des deux ensembles évite de fusionner
        deux serveurs sur un indice trop faible.
        """
        return (frozenset(self.hosts), frozenset(self.ips))

    def as_dict(self):
        return {
            "hosts": list(self.hosts),
            "ips": list(self.ips),
            "request_count": self.request_count,
            "transferred_bytes": self.transferred_bytes,
            "cache_hit_ratio": self.cache_hit_ratio,
            "cache_header_seen": self.cache_header_seen,
            "note": self.note,
        }


@dataclass(frozen=True)
class ThirdPartyHost:
    """Un hôte tiers observé dans le HAR, compté en RÉSEAU SEULEMENT.

    Décision de modélisation : les octets des tiers sont comptés (ils traversent
    le réseau et l'appareil du visiteur), mais leurs SERVEURS ne le sont pas.
    Aucune source publique ne donne de g CO2e par requête pour un CDN ou un
    service de police de caractères ; un chiffre y serait inventé.

    Cette structure existe pour que le rapport puisse le DIRE avec des nombres
    propres au site analysé. La formulation compte : ce n'est pas "les tiers ont
    été oubliés", c'est "leur trafic est compté, pas leurs machines". Et
    l'ampleur de cet angle mort varie fortement d'un site à l'autre, donc elle
    ne peut pas être annoncée en pourcentage universel.
    """

    host: str
    request_count: Optional[int] = None
    transferred_bytes: Optional[int] = None
    share_of_requests: Optional[float] = None
    share_of_bytes: Optional[float] = None
    note: Optional[str] = None

    def __post_init__(self):
        _require_key(self.host, "ThirdPartyHost", "host")

    def as_dict(self):
        return {
            "host": self.host,
            "request_count": self.request_count,
            "transferred_bytes": self.transferred_bytes,
            "share_of_requests": self.share_of_requests,
            "share_of_bytes": self.share_of_bytes,
            "note": self.note,
        }


@dataclass(frozen=True)
class ExternalApiSpec:
    """Un appel à un modèle d'IA générative tiers (OpenAI, Anthropic...), à la
    différence d'un `ThirdPartyHost` : ici une source publique DONNE une
    empreinte par appel (bibliothèque EcoLogits, déjà installée avec
    e-footprint), donc la compter en réseau seulement sous-estimerait le calcul
    lui-même. Distinct d'un `ThirdPartyHost` (CDN, police de caractères) pour
    qui aucune source publique de ce genre n'existe (cf. sa docstring).

    `provider`/`model_name` doivent être reconnus par le catalogue EcoLogits
    (ex. "anthropic" / "claude-sonnet-4-5") : c'est `build.py` qui vérifie,
    cette dataclasse reste zéro import e-footprint.
    `output_tokens` pilote le calcul : plus de mots générés, plus d'énergie et
    de calcul consommés. `request_count_per_step` est le nombre d'appels que
    déclenche l'étape qui le porte (ex. plusieurs tours de conversation).
    """

    provider: str
    model_name: str
    output_tokens: Traced
    request_count_per_step: float = 1.0

    def __post_init__(self):
        owner = "ExternalApiSpec"
        _require_key(self.provider, owner, "provider")
        _require_key(self.model_name, owner, "model_name")
        require_traced(self.output_tokens, owner, "output_tokens", kind="value",
                       critical=True)
        if isinstance(self.request_count_per_step, bool) \
                or not isinstance(self.request_count_per_step, Real) \
                or self.request_count_per_step <= 0:
            raise SpecError(f"{owner} : \"request_count_per_step\" doit être un "
                            f"nombre strictement positif, reçu "
                            f"{self.request_count_per_step!r}.")
        object.__setattr__(self, "request_count_per_step", float(self.request_count_per_step))


# ---------------------------------------------------------------------------
# Serveur
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ServerSpec:
    """Une infrastructure 1st-party distincte.

    Un serveur par infrastructure réellement distincte, jamais d'agrégation de
    complaisance. Deux raisons : agréger prête au serveur principal une charge
    qu'il ne porte pas, et surtout agréger rend le poste INVISIBLE, donc non
    isolable comme levier de réduction. Un service d'analytique qui pèse peu en
    octets mais concentre beaucoup de requêtes disparaîtrait dans un job de page
    unique.

    `provider` et `instance_type` ne valent que pour un serveur de cloud public
    modélisé par la voie Boavizta. Un serveur générique utilise à la place
    `power`, `carbon_footprint_fabrication` et `pue`. Les deux jeux sont
    facultatifs ici : c'est le constructeur du modèle qui exigera l'un ou
    l'autre, parce que lui seul sait quelle classe e-footprint il instancie.
    """

    key: str
    label: str
    role: str = "web"
    server_type: Optional[Traced] = None          # autoscaling / serverless / on_premise
    country: Optional[Traced] = None
    carbon_intensity: Optional[Traced] = None
    provider: Optional[Traced] = None
    instance_type: Optional[Traced] = None
    storage_gb: Optional[Traced] = None
    base_ram: Optional[Traced] = None
    base_compute: Optional[Traced] = None
    power: Optional[Traced] = None
    carbon_footprint_fabrication: Optional[Traced] = None
    pue: Optional[Traced] = None
    evidence: Optional[Evidence] = None
    notes: Tuple[str, ...] = ()

    def __post_init__(self):
        _require_key(self.key, "ServerSpec", "key")
        _require_key(self.label, f"ServerSpec[{self.key}]", "label")
        owner = f"ServerSpec[{self.key}]"
        object.__setattr__(self, "notes", tuple(self.notes))

        for name in ("server_type", "country", "provider"):
            require_traced(getattr(self, name), owner, name, kind="object")
        # Le type d'instance est CRITIQUE : il détermine à lui seul la puissance
        # et l'empreinte de fabrication attribuées. Un t3.medium posé sans
        # justification devient, dans le rapport, une caractéristique du site.
        require_traced(self.instance_type, owner, "instance_type", kind="object",
                       critical=self.instance_type is not None)
        for name in ("carbon_intensity", "storage_gb", "base_ram", "base_compute",
                     "power", "carbon_footprint_fabrication", "pue"):
            require_traced(getattr(self, name), owner, name, kind="value")

        if self.evidence is not None and not isinstance(self.evidence, Evidence):
            raise SpecError(f"{owner} : \"evidence\" doit être un Evidence, "
                            f"reçu {type(self.evidence).__name__}.")


# ---------------------------------------------------------------------------
# Traitement (job)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class JobSpec:
    """Un échange réseau attribué à un serveur.

    `data_transferred` est le poids TRANSFÉRÉ (compressé, tel qu'il circule),
    pas le poids décompressé : c'est le trafic réel qui pilote l'énergie réseau.
    Le poids décompressé reste un repère utile pour le rapport, mais il n'entre
    pas dans le calcul.

    `external_api` porte un `ExternalApiSpec` si ce traitement appelle un
    modèle d'IA générative tiers (OpenAI, Anthropic...) dont l'empreinte est
    calculée via EcoLogits (cf. sa docstring), EN PLUS du `data_transferred`
    habituel : le trafic réseau du prompt/réponse et le calcul du modèle chez
    le fournisseur sont deux grandeurs distinctes, elles se cumulent.
    """

    key: str
    server_key: str
    label: str
    data_transferred: Optional[Traced] = None
    request_duration: Optional[Traced] = None
    compute_needed: Optional[Traced] = None
    ram_needed: Optional[Traced] = None
    data_stored: Optional[Traced] = None
    external_api: Optional[ExternalApiSpec] = None
    notes: Tuple[str, ...] = ()

    def __post_init__(self):
        _require_key(self.key, "JobSpec", "key")
        owner = f"JobSpec[{self.key}]"
        _require_key(self.server_key, owner, "server_key")
        _require_key(self.label, owner, "label")
        object.__setattr__(self, "notes", tuple(self.notes))

        # Le poids transféré est CRITIQUE : c'est l'entrée principale du calcul.
        require_traced(self.data_transferred, owner, "data_transferred",
                       kind="value", critical=True)
        for name in ("request_duration", "compute_needed", "ram_needed", "data_stored"):
            require_traced(getattr(self, name), owner, name, kind="value")

        if self.external_api is not None and not isinstance(self.external_api, ExternalApiSpec):
            raise SpecError(f"{owner} : \"external_api\" doit être un "
                            f"ExternalApiSpec, reçu {type(self.external_api).__name__}.")


# ---------------------------------------------------------------------------
# Étape de parcours
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class StepSpec:
    """Une étape du parcours utilisateur, avec les traitements qu'elle déclenche.

    `jobs` associe une clé de traitement à un POIDS : le nombre de fois que ce
    traitement s'exécute pendant l'étape. Un poids, pas un booléen, parce qu'une
    étape peut relancer plusieurs fois le même appel.

    `intention` est le regroupement métier utilisé pour la PRÉSENTATION
    (s'informer, contacter, candidater...). Le calcul reste au niveau de
    l'étape ; l'intention n'est qu'une agrégation des résultats, ce qui garantit
    que les totaux se conservent.

    `words` et `images` servent à estimer le temps de lecture. Sur une page
    rendue côté client, le comptage tombe à zéro ; ce repli doit rester VISIBLE
    dans la confiance du Traced, jamais silencieux.
    """

    key: str
    label: str
    intention: Optional[str] = None
    user_time: Optional[Traced] = None
    jobs: Mapping[str, float] = field(default_factory=dict)
    times_per_journey: float = 1.0
    words: Optional[Traced] = None
    images: Optional[Traced] = None
    url: Optional[str] = None
    notes: Tuple[str, ...] = ()

    def __post_init__(self):
        _require_key(self.key, "StepSpec", "key")
        owner = f"StepSpec[{self.key}]"
        _require_key(self.label, owner, "label")
        object.__setattr__(self, "notes", tuple(self.notes))

        # Le temps utilisateur est CRITIQUE : il pilote l'empreinte de
        # l'appareil du visiteur, qui pèse lourd dans le total. Une durée posée
        # sans provenance est le genre de chiffre qu'on croit mesuré.
        require_traced(self.user_time, owner, "user_time", kind="value", critical=True)
        for name in ("words", "images"):
            require_traced(getattr(self, name), owner, name, kind="value")

        if not isinstance(self.jobs, Mapping):
            raise SpecError(f"{owner} : \"jobs\" doit associer une clé de "
                            f"traitement à un nombre d'exécutions, reçu "
                            f"{type(self.jobs).__name__}.")
        cleaned = {}
        for job_key, weight in self.jobs.items():
            _require_key(job_key, owner, "jobs (clé)")
            if isinstance(weight, bool) or not isinstance(weight, Real):
                raise SpecError(f"{owner} : le poids du traitement "
                                f"\"{job_key}\" doit être un nombre, reçu "
                                f"{weight!r}.")
            if weight <= 0:
                raise SpecError(f"{owner} : le poids du traitement "
                                f"\"{job_key}\" vaut {weight}. Un traitement "
                                "qui ne s'exécute pas doit être retiré de "
                                "l'étape, pas mis à zéro : à zéro il reste "
                                "listé dans le modèle et laisse croire qu'il "
                                "est compté.")
            cleaned[job_key] = float(weight)
        object.__setattr__(self, "jobs", cleaned)

        if isinstance(self.times_per_journey, bool) \
                or not isinstance(self.times_per_journey, Real) \
                or self.times_per_journey <= 0:
            raise SpecError(f"{owner} : \"times_per_journey\" doit être un "
                            f"nombre strictement positif, reçu "
                            f"{self.times_per_journey!r}.")
        object.__setattr__(self, "times_per_journey", float(self.times_per_journey))


# ---------------------------------------------------------------------------
# Parcours
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class JourneySpec:
    """Un enchaînement d'étapes. L'ordre est conservé : il porte du sens pour la
    lecture du rapport, même si le calcul ne dépend pas de l'ordre."""

    key: str
    label: str
    steps: Tuple[str, ...] = ()
    notes: Tuple[str, ...] = ()

    def __post_init__(self):
        _require_key(self.key, "JourneySpec", "key")
        owner = f"JourneySpec[{self.key}]"
        _require_key(self.label, owner, "label")
        object.__setattr__(self, "steps", tuple(self.steps))
        object.__setattr__(self, "notes", tuple(self.notes))
        for step_key in self.steps:
            _require_key(step_key, owner, "steps (élément)")
        if len(set(self.steps)) != len(self.steps):
            # Répéter une étape est légitime, mais s'exprime par
            # times_per_journey. Deux entrées identiques dans la liste rendent
            # le comptage ambigu à la lecture du modèle.
            raise SpecError(f"{owner} : une étape apparaît deux fois dans "
                            "\"steps\". Pour une étape répétée, utiliser "
                            "times_per_journey sur le StepSpec.")


# ---------------------------------------------------------------------------
# Audience
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AudienceSpec:
    """Le volume et la composition du trafic.

    Les fractions d'appareils et de réseaux sont séparées parce qu'elles
    donneront deux motifs d'usage distincts. La librairie e-footprint ne pondère
    PAS l'usage entre plusieurs appareils d'une même liste : y mettre téléphone
    et ordinateur ensemble facture la totalité du trafic sur CHACUN. Deux motifs
    aux volumes proportionnels sont le seul montage correct.

    `visits_per_year` n'est pas un champ critique au sens du garde-fou, et c'est
    délibéré : les données d'audience manquent pour les petits sites et les
    intranets. Le modèle doit rester utilisable sans elles, avec un défaut
    affiché comme tel.
    """

    key: str
    label: str
    visits_per_year: Optional[Traced] = None
    phone_fraction: Optional[Traced] = None
    desktop_fraction: Optional[Traced] = None
    wifi_fraction: Optional[Traced] = None
    mobile_fraction: Optional[Traced] = None
    country: Optional[Traced] = None
    country_mix: Tuple[Tuple[str, float], ...] = ()
    journey_key: Optional[str] = None
    notes: Tuple[str, ...] = ()

    # Les fractions doivent sommer à 1. Tolérance étroite : elle absorbe un
    # arrondi de sérialisation, pas une répartition bancale.
    FRACTION_TOLERANCE = 1e-6

    def __post_init__(self):
        _require_key(self.key, "AudienceSpec", "key")
        owner = f"AudienceSpec[{self.key}]"
        _require_key(self.label, owner, "label")
        object.__setattr__(self, "notes", tuple(self.notes))
        object.__setattr__(self, "country_mix",
                           tuple((str(name), float(share))
                                 for name, share in self.country_mix))

        require_traced(self.visits_per_year, owner, "visits_per_year", kind="value")
        require_traced(self.country, owner, "country", kind="object")
        for name in ("phone_fraction", "desktop_fraction",
                     "wifi_fraction", "mobile_fraction"):
            require_traced(getattr(self, name), owner, name, kind="value")

        self._check_pair(owner, "phone_fraction", self.phone_fraction,
                         "desktop_fraction", self.desktop_fraction)
        self._check_pair(owner, "wifi_fraction", self.wifi_fraction,
                         "mobile_fraction", self.mobile_fraction)

        if self.journey_key is not None:
            _require_key(self.journey_key, owner, "journey_key")

    def _check_pair(self, owner, name_a, traced_a, name_b, traced_b):
        """Refuse une répartition qui ne somme pas à 1, et refuse aussi une
        moitié de répartition.

        Pas de renormalisation automatique : compléter en silence la fraction
        manquante fabrique une donnée d'audience que personne n'a mesurée.
        """
        if (traced_a is None) != (traced_b is None):
            missing = name_b if traced_a is not None else name_a
            raise SpecError(
                f"{owner} : \"{missing}\" manque alors que l'autre part de la "
                "répartition est fournie. Le complément n'est pas déduit "
                "automatiquement : ce serait inventer une donnée d'audience."
            )
        if traced_a is None:
            return
        total = traced_a.value + traced_b.value
        if abs(total - 1.0) > self.FRACTION_TOLERANCE:
            raise SpecError(
                f"{owner} : \"{name_a}\" ({traced_a.value}) et \"{name_b}\" "
                f"({traced_b.value}) somment à {total}, pas à 1. Une "
                "répartition incomplète sous-compte le trafic ; une "
                "répartition excédentaire le surcompte."
            )


# ---------------------------------------------------------------------------
# Le site : le contrat de la bibliothèque
# ---------------------------------------------------------------------------

# Version du contrat de spécification. À incrémenter dès qu'un champ change de
# SENS (un ajout de champ facultatif n'est pas un changement de sens).
SCHEMA_VERSION = "1.0"


@dataclass(frozen=True)
class SiteSpec:
    """La description complète d'un service, prête à être construite.

    C'est le SEUL contrat de la bibliothèque : elle ne connaît ni le format HAR
    ni le fichier de données d'environnement. Un adaptateur les traduit en
    SiteSpec, ce qui permettra plus tard de modéliser un service à partir d'un
    schéma d'architecture ou d'un entretien technique, sans capture réseau.

    Les collections sont des tuples : une spécification est immuable, et une
    transformation (un archétype) en retourne une nouvelle plutôt que de
    modifier celle qu'on lui passe. Sans quoi appliquer deux archétypes au même
    site produirait un résultat dépendant de l'ordre des appels.
    """

    name: str
    servers: Tuple[ServerSpec, ...] = ()
    jobs: Tuple[JobSpec, ...] = ()
    steps: Tuple[StepSpec, ...] = ()
    journeys: Tuple[JourneySpec, ...] = ()
    audience: Optional[AudienceSpec] = None
    third_party_hosts: Tuple[ThirdPartyHost, ...] = ()
    archetypes: Tuple[str, ...] = ()
    notes: Tuple[str, ...] = ()
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self):
        _require_key(self.name, "SiteSpec", "name")
        for attr, expected in (("servers", ServerSpec), ("jobs", JobSpec),
                               ("steps", StepSpec), ("journeys", JourneySpec),
                               ("third_party_hosts", ThirdPartyHost)):
            items = tuple(getattr(self, attr))
            for item in items:
                if not isinstance(item, expected):
                    raise SpecError(
                        f"SiteSpec[{self.name}] : \"{attr}\" attend des "
                        f"{expected.__name__}, reçu "
                        f"{type(item).__name__}.")
            object.__setattr__(self, attr, items)
        object.__setattr__(self, "archetypes", tuple(self.archetypes))
        object.__setattr__(self, "notes", tuple(self.notes))

        if self.audience is not None and not isinstance(self.audience, AudienceSpec):
            raise SpecError(f"SiteSpec[{self.name}] : \"audience\" doit être un "
                            f"AudienceSpec, reçu {type(self.audience).__name__}.")

    # --- Index par clé : indispensable en aval -----------------------------
    # Sans ces index, les résultats d'attribution reviennent indexés par objet
    # e-footprint et on ne sait plus à quelle intention métier les rattacher.

    def server_by_key(self, key):
        return _index(self.servers)[key]

    def job_by_key(self, key):
        return _index(self.jobs)[key]

    def step_by_key(self, key):
        return _index(self.steps)[key]

    def journey_by_key(self, key):
        return _index(self.journeys)[key]

    @property
    def server_keys(self):
        return tuple(server.key for server in self.servers)

    @property
    def job_keys(self):
        return tuple(job.key for job in self.jobs)

    @property
    def step_keys(self):
        return tuple(step.key for step in self.steps)

    @property
    def journey_keys(self):
        return tuple(journey.key for journey in self.journeys)


def _index(items):
    """Index clé -> élément. Les doublons sont impossibles à ce stade :
    `compose()` et `validate_spec()` les refusent en amont."""
    return {item.key: item for item in items}
