#!/usr/bin/env python3
"""
Filet de sécurité du refactoring e-footprint : contrôle des GARDE-FOUS de la
bibliothèque de spécification.

POURQUOI CE SCRIPT EXISTE
-------------------------
`efootprint_model/` repose entièrement sur des refus : une valeur sans
provenance est refusée, une clé qui renvoie dans le vide est refusée, une
collision de clés est refusée. Ces refus sont la seule chose qui empêche un
chiffre non tracé d'atterrir dans un rapport.

Or un garde-fou cassé ne se remarque pas. Il ne produit aucune erreur : il
laisse simplement passer. Un contrôle qui ne vérifie que le chemin normal
resterait vert même si tous les refus avaient disparu.

Ce script vérifie donc les DEUX sens :
  - une spécification correcte se construit (chemin normal) ;
  - chaque faute prévue est bien REFUSÉE (chemin d'échec).

Le second est le seul qui prouve quelque chose.

CE QU'IL NE FAIT PAS
--------------------
Il ne vérifie aucun chiffre de CO2e : la bibliothèque testée ici n'en calcule
aucun, elle décrit. La non-régression numérique est le travail de
`check_efootprint_contract.py`.

Il ne prouve pas la généricité : c'est `check_genericite.py`, et surtout
l'exécution sur un second site réel.

Usage :
    python3 check_efootprint_spec.py
    python3 check_efootprint_spec.py --verbose

Code de sortie : 0 si tous les garde-fous répondent, 1 sinon.
"""

import argparse
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from efootprint_model import (  # noqa: E402  (après ajustement de sys.path)
    RESERVE_CODES,
    AudienceSpec,
    Evidence,
    ExternalApiSpec,
    JobSpec,
    JourneySpec,
    ServerSpec,
    SiteSpec,
    SpecError,
    StepSpec,
    ThirdPartyHost,
    Traced,
    arbitrations_for,
    assumed,
    calculation_reserves,
    collect_sources,
    compose,
    estimated,
    measured,
    orphan_steps,
    primary_server,
    require_calculable,
    script_default,
    unused_jobs,
    validate_spec,
)
from efootprint_model.compose import (  # noqa: E402
    confidence_summary,
    reserves_without_arbitration,
    servers_note,
    untraced_fields,
)
from efootprint_model.spec import (  # noqa: E402
    estimated_label,
    measured_label,
    script_default_label,
)
from efootprint_model.temps_utilisateur import (  # noqa: E402
    is_within_nielsen_domain,
    nielsen_raw_seconds,
    recalibration_factor,
    step_user_time,
)

# ---------------------------------------------------------------------------
# Journal des contrôles
# ---------------------------------------------------------------------------


class Journal:
    """Accumule les résultats. Aucun contrôle n'interrompt les suivants : un
    rapport complet vaut mieux qu'un premier échec isolé."""

    def __init__(self, verbose=False):
        self.verbose = verbose
        self.passed = 0
        self.failures = []

    def ok(self, label):
        self.passed += 1
        if self.verbose:
            print(f"  [ok]     {label}")

    def fail(self, label, detail):
        self.failures.append((label, detail))
        print(f"  [ÉCHEC]  {label}")
        print(f"           {detail}")

    def expect_ok(self, label, thunk):
        """Le chemin normal : la construction doit RÉUSSIR."""
        try:
            result = thunk()
        except Exception as exc:  # noqa: BLE001 - on rapporte, on ne masque pas
            self.fail(label, f"a levé {type(exc).__name__} : {exc}")
            return None
        self.ok(label)
        return result

    def expect_refused(self, label, thunk, expect_in_message=None):
        """Le chemin d'échec : la construction doit être REFUSÉE par SpecError.

        `expect_in_message` vérifie que le message ORIENTE vers la cause. Un
        refus au bon endroit avec un message incompréhensible fait perdre le
        bénéfice du garde-fou : la personne qui le rencontre ne sait pas quoi
        corriger.
        """
        try:
            thunk()
        except SpecError as exc:
            message = str(exc)
            if expect_in_message and expect_in_message not in message:
                self.fail(label,
                          f"refusé (correct) mais le message ne mentionne pas "
                          f"{expect_in_message!r} : {message}")
                return
            self.ok(label)
            return
        except Exception as exc:  # noqa: BLE001
            self.fail(label,
                      f"refusé par {type(exc).__name__} au lieu de SpecError : "
                      f"{exc}. Les refus de la bibliothèque doivent être "
                      "reconnaissables par leur type.")
            return
        self.fail(label, "ACCEPTÉ alors que ce cas doit être refusé. "
                         "Le garde-fou ne protège plus rien.")

    def expect_equal(self, label, actual, expected):
        if actual == expected:
            self.ok(label)
        else:
            self.fail(label, f"attendu {expected!r}, obtenu {actual!r}")

    def expect_true(self, label, condition, detail=""):
        if condition:
            self.ok(label)
        else:
            self.fail(label, detail or "condition fausse")


# ---------------------------------------------------------------------------
# Jeu de données de contrôle
# ---------------------------------------------------------------------------
# Valeurs FICTIVES et volontairement rondes, sans rapport avec un site réel. Ce
# script n'est pas un cas d'audit : y recopier des mesures ferait de lui la
# porte d'entrée exacte que `check_genericite.py` cherche à fermer.

SRC = "jeu de contrôle"


def sample_server(key="web", **overrides):
    fields = dict(
        key=key,
        label="Serveur applicatif",
        server_type=script_default_label("autoscaling",
                                        "mode de dimensionnement par défaut"),
        country=estimated_label("FRANCE", SRC, comment="déduit d'une adresse IP"),
        carbon_intensity=measured(50.0, "g/kWh", SRC),
        provider=measured_label("fournisseur-a", SRC),
        instance_type=script_default_label("instance-standard",
                                          "faute d'information sur l'hébergement"),
        storage_gb=script_default(20.0, "GB_stored", "ordre de grandeur assumé"),
        evidence=Evidence(hosts=("hote-principal",), ips=("10.0.0.1",),
                          request_count=200, transferred_bytes=900_000,
                          cache_hit_ratio=0.5, cache_header_seen=True),
    )
    fields.update(overrides)
    return ServerSpec(**fields)


def sample_job(key="page", server_key="web", **overrides):
    fields = dict(
        key=key,
        server_key=server_key,
        label="Chargement d'une page",
        data_transferred=measured(500.0, "kB", SRC),
        request_duration=measured(400.0, "ms", SRC),
        compute_needed=script_default(0.05, "cpu_core",
                                      "CPU serveur indéductible d'une capture réseau"),
        ram_needed=script_default(50.0, "MB_ram"),
        data_stored=script_default(0.0, "kB_stored"),
    )
    fields.update(overrides)
    return JobSpec(**fields)


def sample_step(key="accueil", jobs=None, **overrides):
    fields = dict(
        key=key,
        label="Consulter l'accueil",
        intention="s'informer",
        user_time=estimated(30.0, "s", SRC,
                            comment="modèle de temps de lecture, pas une mesure"),
        jobs=jobs if jobs is not None else {"page": 1},
        words=measured(200.0, "dimensionless", SRC),
    )
    fields.update(overrides)
    return StepSpec(**fields)


def sample_audience(**overrides):
    fields = dict(
        key="visiteurs",
        label="Visiteurs annuels",
        visits_per_year=estimated(10_000.0, "dimensionless", SRC),
        phone_fraction=measured(0.5, "dimensionless", SRC),
        desktop_fraction=measured(0.5, "dimensionless", SRC),
        wifi_fraction=assumed(0.5, "dimensionless", SRC,
                              comment="répartition supposée, non mesurée"),
        mobile_fraction=assumed(0.5, "dimensionless", SRC,
                                comment="répartition supposée, non mesurée"),
        journey_key="visite",
    )
    fields.update(overrides)
    return AudienceSpec(**fields)


def sample_site(**overrides):
    fields = dict(
        name="site-de-controle",
        servers=(sample_server(),),
        jobs=(sample_job(),),
        steps=(sample_step(),),
        journeys=(JourneySpec("visite", "Visite simple", ("accueil",)),),
        audience=sample_audience(),
    )
    fields.update(overrides)
    return SiteSpec(**fields)


# ---------------------------------------------------------------------------
# Contrôles : Traced
# ---------------------------------------------------------------------------

def check_traced(journal):
    print("Traced — la provenance voyage avec la valeur")

    journal.expect_ok("une grandeur avec unité et source se construit",
                      lambda: measured(1.5, "kB", SRC))
    journal.expect_ok("un libellé sans unité se construit",
                      lambda: measured_label("fournisseur-a", SRC))

    journal.expect_refused(
        "un niveau de confiance inventé est refusé",
        lambda: Traced(1.0, "kB", SRC, confidence="tres-sur"),
        "niveau de confiance inconnu")
    journal.expect_refused(
        "une grandeur sans unité est refusée",
        lambda: Traced(1.0, None, SRC),
        "unité manquante")
    journal.expect_refused(
        "un texte présenté comme grandeur est refusé",
        lambda: Traced("beaucoup", "kB", SRC),
        "doit être un nombre")
    journal.expect_refused(
        "un libellé avec unité est refusé",
        lambda: Traced("fournisseur-a", "kB", SRC, kind="object"),
        "n'a pas d'unité")
    journal.expect_refused(
        "une nature de valeur inconnue est refusée",
        lambda: Traced(1.0, "kB", SRC, kind="quantite"),
        "nature de valeur inconnue")

    # Un booléen est un entier en Python : sans contrôle explicite, True
    # passerait pour la valeur 1 et se convertirait en « 1 kB ».
    journal.expect_refused(
        "un booléen n'est pas accepté comme grandeur",
        lambda: Traced(True, "kB", SRC),
        "doit être un nombre")

    # Le vocabulaire de confiance doit rester celui du rapport, sinon le badge
    # affiche la chaîne brute au lieu du libellé coloré.
    from efootprint_model import CONFIDENCE_LEVELS
    journal.expect_equal(
        "les 7 niveaux de confiance du rapport sont exactement ceux de la lib",
        CONFIDENCE_LEVELS,
        ("high", "medium", "low", "default", "default_efootprint",
         "default_script", "unjustified"))

    journal.expect_true("has_source distingue une source vide d'une source réelle",
                        not Traced(1.0, "kB", "   ").has_source
                        and measured(1.0, "kB", SRC).has_source)

    # Les fabriques doivent poser le bon niveau : c'est tout leur intérêt.
    journal.expect_equal("measured() pose \"high\"",
                         measured(1.0, "kB", SRC).confidence, "high")
    journal.expect_equal("estimated() pose \"medium\"",
                         estimated(1.0, "kB", SRC).confidence, "medium")
    journal.expect_equal("assumed() pose \"low\"",
                         assumed(1.0, "kB", SRC).confidence, "low")
    journal.expect_equal("script_default() pose \"default_script\"",
                         script_default(1.0, "kB").confidence, "default_script")
    journal.expect_true(
        "script_default() nomme le script comme source, pas e-footprint",
        "script" in (script_default(1.0, "kB").source_name or ""),
        "un défaut du script annoncé comme défaut de la librairie ferait "
        "endosser nos choix par l'outil")
    print()


# ---------------------------------------------------------------------------
# Contrôles : champs critiques
# ---------------------------------------------------------------------------

def check_critical_fields(journal):
    print("Champs critiques — échec bruyant plutôt que chiffre non tracé")

    journal.expect_refused(
        "un poids transféré absent est refusé",
        lambda: sample_job(data_transferred=None),
        "data_transferred")
    journal.expect_refused(
        "un poids transféré sans provenance est refusé",
        lambda: sample_job(data_transferred=Traced(500.0, "kB")),
        "sans provenance")
    journal.expect_refused(
        "un temps utilisateur absent est refusé",
        lambda: sample_step(user_time=None),
        "user_time")
    journal.expect_refused(
        "un temps utilisateur sans provenance est refusé",
        lambda: sample_step(user_time=Traced(30.0, "s")),
        "sans provenance")
    journal.expect_refused(
        "un type d'instance sans provenance est refusé",
        lambda: sample_server(instance_type=Traced("instance-x", kind="object")),
        "sans provenance")

    # Un champ NON critique se passe de provenance : la bibliothèque doit rester
    # utilisable là où la donnée manque légitimement, sans forcer à inventer.
    journal.expect_ok(
        "un champ non critique sans provenance reste accepté",
        lambda: sample_server(storage_gb=Traced(20.0, "GB_stored")))

    # Un serveur sans type d'instance est valide : c'est le cas d'un serveur
    # générique, hors cloud public. Le constructeur du modèle exigera l'un ou
    # l'autre jeu de champs, la spécification n'a pas à trancher.
    journal.expect_ok("un serveur sans type d'instance reste accepté",
                      lambda: sample_server(instance_type=None))

    journal.expect_refused(
        "une valeur nue à la place d'un Traced est refusée",
        lambda: sample_job(request_duration=400.0),
        "doit être un Traced")
    journal.expect_refused(
        "un libellé à la place d'une grandeur est refusé",
        lambda: sample_job(data_transferred=measured_label("lourd", SRC)),
        "kind")
    print()


# ---------------------------------------------------------------------------
# Contrôles : structures
# ---------------------------------------------------------------------------

def check_structures(journal):
    print("Structures — refus des états incohérents")

    journal.expect_ok("un site complet se construit", sample_site)

    journal.expect_refused("une clé vide est refusée",
                           lambda: sample_job(key="  "), "clé texte non vide")

    journal.expect_refused(
        "un poids de traitement nul est refusé",
        lambda: sample_step(jobs={"page": 0}),
        "doit être retiré")
    journal.expect_refused(
        "un poids de traitement négatif est refusé",
        lambda: sample_step(jobs={"page": -1}),
        "vaut -1")
    journal.expect_ok("un poids fractionnaire est accepté",
                      lambda: sample_step(jobs={"page": 0.5}))
    journal.expect_refused(
        "un times_per_journey nul est refusé",
        lambda: sample_step(times_per_journey=0),
        "strictement positif")

    journal.expect_refused(
        "une étape répétée dans la liste d'un parcours est refusée",
        lambda: JourneySpec("visite", "Visite", ("accueil", "accueil")),
        "times_per_journey")

    journal.expect_refused(
        "une répartition d'appareils qui ne somme pas à 1 est refusée",
        lambda: sample_audience(phone_fraction=measured(0.5, "dimensionless", SRC),
                                desktop_fraction=measured(0.3, "dimensionless", SRC)),
        "somment à")
    journal.expect_refused(
        "une demi-répartition est refusée plutôt que complétée en silence",
        lambda: sample_audience(desktop_fraction=None),
        "n'est pas déduit")
    journal.expect_ok(
        "une audience sans répartition d'appareils du tout est acceptée",
        lambda: sample_audience(phone_fraction=None, desktop_fraction=None))
    journal.expect_ok(
        "une audience sans volume de visites est acceptée (petits sites, intranets)",
        lambda: sample_audience(visits_per_year=None))

    journal.expect_refused(
        "un élément du mauvais type dans une collection est refusé",
        lambda: sample_site(jobs=(sample_step(),)),
        "attend des JobSpec")

    journal.expect_refused("un hôte tiers sans nom est refusé",
                           lambda: ThirdPartyHost(""), "host")

    # Deux situations distinctes qu'il serait tentant de confondre : aucun
    # en-tête de cache observé est une information sur l'hébergement ; un ratio
    # incalculable est une absence de mesure.
    silent = Evidence(hosts=("a",), cache_header_seen=False)
    journal.expect_true(
        "absence d'en-tête de cache et ratio inconnu restent distinguables",
        silent.cache_hit_ratio is None and silent.cache_header_seen is False)
    print()


# ---------------------------------------------------------------------------
# Contrôles : appel IA générative (ExternalApiSpec, Lot 7)
# ---------------------------------------------------------------------------

def check_external_api(journal):
    print("IA générative — ExternalApiSpec refuse ce qu'EcoLogits ne peut pas chiffrer")

    journal.expect_ok(
        "un ExternalApiSpec complet se construit",
        lambda: ExternalApiSpec(provider="anthropic", model_name="claude-sonnet-4-5",
                                output_tokens=measured(300.0, "dimensionless", SRC)))

    journal.expect_refused(
        "un provider vide est refusé",
        lambda: ExternalApiSpec(provider="", model_name="claude-sonnet-4-5",
                                output_tokens=measured(300.0, "dimensionless", SRC)),
        "provider")
    journal.expect_refused(
        "un model_name vide est refusé",
        lambda: ExternalApiSpec(provider="anthropic", model_name="",
                                output_tokens=measured(300.0, "dimensionless", SRC)),
        "model_name")
    journal.expect_refused(
        "output_tokens absent est refusé : champ critique, pilote le calcul EcoLogits",
        lambda: ExternalApiSpec(provider="anthropic", model_name="claude-sonnet-4-5",
                                output_tokens=None),
        "output_tokens")
    journal.expect_refused(
        "output_tokens sans provenance est refusé",
        lambda: ExternalApiSpec(provider="anthropic", model_name="claude-sonnet-4-5",
                                output_tokens=Traced(300.0, "dimensionless")),
        "provenance")
    journal.expect_refused(
        "request_count_per_step nul est refusé",
        lambda: ExternalApiSpec(provider="anthropic", model_name="claude-sonnet-4-5",
                                output_tokens=measured(300.0, "dimensionless", SRC),
                                request_count_per_step=0),
        "strictement positif")
    journal.expect_refused(
        "request_count_per_step négatif est refusé",
        lambda: ExternalApiSpec(provider="anthropic", model_name="claude-sonnet-4-5",
                                output_tokens=measured(300.0, "dimensionless", SRC),
                                request_count_per_step=-1),
        "strictement positif")

    journal.expect_ok(
        "un JobSpec avec external_api complet se construit",
        lambda: sample_job(
            external_api=ExternalApiSpec(
                provider="anthropic", model_name="claude-sonnet-4-5",
                output_tokens=measured(300.0, "dimensionless", SRC))))
    journal.expect_refused(
        "un external_api du mauvais type est refusé (pas un simple nom)",
        lambda: sample_job(external_api="anthropic"),
        "ExternalApiSpec")
    print()


# ---------------------------------------------------------------------------
# Contrôles : validation croisée des clés
# ---------------------------------------------------------------------------

def check_validation(journal):
    print("Validation croisée — aucune clé ne renvoie dans le vide")

    journal.expect_ok("un site cohérent passe la validation",
                      lambda: validate_spec(sample_site()))

    journal.expect_refused(
        "un traitement attribué à un serveur inexistant est refusé",
        lambda: validate_spec(sample_site(jobs=(sample_job(server_key="fantome"),))),
        "qui n'existe pas")
    journal.expect_refused(
        "une étape déclenchant un traitement inexistant est refusée",
        lambda: validate_spec(sample_site(steps=(sample_step(jobs={"fantome": 1}),))),
        "qui n'existe pas")
    journal.expect_refused(
        "un parcours passant par une étape inexistante est refusé",
        lambda: validate_spec(sample_site(
            journeys=(JourneySpec("visite", "Visite", ("fantome",)),))),
        "qui n'existe pas")
    journal.expect_refused(
        "une audience renvoyant à un parcours inexistant est refusée",
        lambda: validate_spec(sample_site(
            audience=sample_audience(journey_key="fantome"))),
        "qui n'existe pas")

    # Une étape hors parcours n'est PAS refusée ici : décrire un site par
    # morceaux est légitime. Le refus a lieu à l'entrée du calcul, contrôlé plus
    # bas par check_reserves().
    journal.expect_ok(
        "une étape hors parcours ne bloque pas la description",
        lambda: validate_spec(sample_site(
            steps=(sample_step(), sample_step(key="orpheline")))))

    # Un traitement que personne ne déclenche ne fausse aucun total : on le
    # signale sans bloquer. Bloquer empêcherait de décrire un service dont
    # toutes les étapes ne sont pas encore modélisées.
    with_spare = sample_site(jobs=(sample_job(), sample_job(key="inutilise")))
    journal.expect_ok("un traitement non déclenché ne bloque pas",
                      lambda: validate_spec(with_spare))
    journal.expect_equal("un traitement non déclenché est signalé",
                         unused_jobs(with_spare), ("inutilise",))

    journal.expect_refused("une clé de serveur en double est refusée",
                           lambda: validate_spec(sample_site(
                               servers=(sample_server(), sample_server()))),
                           "déclaré deux fois")
    print()


# ---------------------------------------------------------------------------
# Contrôles : réserves de calcul
# ---------------------------------------------------------------------------

def check_reserves(journal):
    print("Réserves — libre de décrire, refusé de publier un chiffre faux")

    site = sample_site()
    journal.expect_equal("un site complet n'a aucune réserve",
                         calculation_reserves(site), ())
    journal.expect_ok("un site complet passe la porte du calcul",
                      lambda: require_calculable(site))

    orphan = sample_site(steps=(sample_step(), sample_step(key="orpheline")))
    journal.expect_equal("une étape hors parcours est détectée",
                         orphan_steps(orphan), ("orpheline",))
    journal.expect_equal(
        "une étape hors parcours devient une réserve de calcul",
        [code for code, _ in calculation_reserves(orphan)],
        ["steps_hors_parcours"])
    journal.expect_refused(
        "le calcul est refusé tant que la réserve n'est pas assumée",
        lambda: require_calculable(orphan),
        "steps_hors_parcours")

    # Le point central du dispositif : on peut passer outre, mais seulement
    # explicitement, et la réserve assumée est RENDUE pour être écrite au rapport.
    accepted = journal.expect_ok(
        "la réserve peut être assumée explicitement",
        lambda: require_calculable(orphan,
                                   accepted_reserves=("steps_hors_parcours",)))
    journal.expect_true(
        "une réserve assumée est rendue à l'appelant, pas avalée",
        accepted is not None and len(accepted) == 1
        and accepted[0][0] == "steps_hors_parcours",
        "sans cela l'arbitrage disparaîtrait et le chiffre paraîtrait sans réserve")

    journal.expect_refused(
        "accepter une réserve qui ne s'applique pas est refusé",
        lambda: require_calculable(site,
                                   accepted_reserves=("steps_hors_parcours",)),
        "ne s'appliquent pas")
    journal.expect_refused(
        "un code de réserve inventé est refusé",
        lambda: require_calculable(orphan, accepted_reserves=("peu_importe",)),
        "ne s'appliquent pas")

    # Les autres réserves : chacune rendrait le total vide ou nul.
    journal.expect_equal(
        "un site sans parcours du tout est une réserve",
        [code for code, _ in calculation_reserves(
            sample_site(journeys=(), audience=sample_audience(journey_key=None)))],
        ["aucun_parcours"])
    journal.expect_true(
        "un site sans audience est une réserve",
        "aucune_audience" in [code for code, _ in
                              calculation_reserves(sample_site(audience=None))])
    journal.expect_refused(
        "une spécification vide ne peut pas produire de chiffre",
        lambda: require_calculable(SiteSpec(name="vide")),
        "réserve(s)")

    # Un traitement non déclenché ne fausse aucun total : il ne doit PAS bloquer
    # le calcul. Confondre les deux rendrait le refus incompréhensible.
    journal.expect_equal(
        "un traitement non déclenché n'est pas une réserve de calcul",
        calculation_reserves(sample_site(
            jobs=(sample_job(), sample_job(key="inutilise")))),
        ())

    # Le refus doit toujours laisser une porte : sinon la personne est coincée.
    journal.expect_equal(
        "chaque réserve propose au moins une issue",
        reserves_without_arbitration(), ())
    journal.expect_true(
        "les issues proposées commencent par corriger, et finissent par assumer",
        arbitrations_for("steps_hors_parcours")[0].startswith("rattacher")
        and "assum" in arbitrations_for("steps_hors_parcours")[-1],
        "l'ordre d'affichage suggère une préférence : corriger avant d'assumer")
    journal.expect_equal("un code inconnu ne propose aucune issue, sans erreur",
                         arbitrations_for("inexistant"), ())
    journal.expect_equal(
        "les codes de réserve énumérés sont ceux réellement émis",
        sorted(RESERVE_CODES),
        sorted({"steps_hors_parcours", "aucun_parcours", "aucune_etape",
                "aucune_audience"}))
    print()


# ---------------------------------------------------------------------------
# Contrôles : fusion
# ---------------------------------------------------------------------------

def check_compose(journal):
    print("Fusion — jamais d'écrasement silencieux")

    front = SiteSpec(
        name="site-de-controle",
        servers=(sample_server(),),
        jobs=(sample_job(),),
        steps=(sample_step(),),
        archetypes=("vitrine",),
    )
    # Second fragment : MÊME serveur (même preuve), traitement et étape distincts.
    chat = SiteSpec(
        name="site-de-controle",
        servers=(sample_server(provider=None,
                              base_ram=script_default(1.0, "GB_ram")),),
        jobs=(sample_job(key="conversation"),),
        steps=(sample_step(key="dialoguer", jobs={"conversation": 3},
                           intention="obtenir de l'aide"),),
        archetypes=("agent-conversationnel",),
    )

    fused = journal.expect_ok(
        "deux archétypes se composent",
        lambda: compose(front, chat,
                        journeys=(JourneySpec("visite", "Visite",
                                              ("accueil", "dialoguer")),),
                        audience=sample_audience()))
    if fused is not None:
        journal.expect_equal("le serveur commun est mutualisé, pas dupliqué",
                             len(fused.servers), 1)
        journal.expect_equal("les traitements des deux fragments sont conservés",
                             sorted(fused.job_keys), ["conversation", "page"])
        journal.expect_equal("les archétypes appliqués sont tracés",
                             fused.archetypes,
                             ("vitrine", "agent-conversationnel"))
        journal.expect_true(
            "la fusion complète les champs absents du premier fragment",
            fused.servers[0].base_ram is not None
            and fused.servers[0].provider is not None,
            "base_ram venait du second fragment, provider du premier")

    # Deux serveurs de même clé sur des infrastructures DIFFÉRENTES : ce sont
    # deux machines qui se disputent un nom, pas une machine décrite deux fois.
    other_infra = SiteSpec(
        name="site-de-controle",
        servers=(sample_server(evidence=Evidence(hosts=("autre-hote",),
                                                 ips=("10.0.0.2",))),),
    )
    journal.expect_refused(
        "deux serveurs de même clé sur des infrastructures distinctes sont refusés",
        lambda: compose(front, other_infra),
        "collision de clé")

    # Sans preuve, on ne mutualise pas : deux archétypes peuvent avoir nommé
    # leur serveur pareil par défaut sans parler de la même machine.
    no_evidence = SiteSpec(name="x", servers=(sample_server(evidence=None),))
    journal.expect_refused(
        "sans preuve d'infrastructure, deux serveurs de même clé sont refusés",
        lambda: compose(no_evidence,
                        SiteSpec(name="x", servers=(sample_server(evidence=None),))),
        "collision de clé")

    journal.expect_refused(
        "un désaccord sur un champ du même serveur est refusé",
        lambda: compose(
            front,
            SiteSpec(name="x", servers=(sample_server(
                provider=measured_label("fournisseur-b", SRC)),))),
        "deux valeurs")

    journal.expect_refused(
        "une collision de traitement est refusée",
        lambda: compose(front, SiteSpec(name="x", jobs=(sample_job(),))),
        "collision de clé")

    journal.expect_refused(
        "deux audiences différentes dans les fragments sont refusées",
        lambda: compose(
            SiteSpec(name="x", audience=sample_audience(journey_key=None)),
            SiteSpec(name="x", audience=sample_audience(key="autres",
                                                        journey_key=None))),
        "un seul trafic")

    journal.expect_refused("compose() sans rien du tout est refusé",
                           lambda: compose(), "rien à composer")
    journal.expect_refused(
        "un objet qui n'est pas un SiteSpec est refusé",
        lambda: compose({"name": "x"}),
        "attend des SiteSpec")

    # Immuabilité : appliquer une fusion ne doit pas modifier les fragments,
    # sinon composer deux fois dans le même processus donnerait deux résultats.
    journal.expect_equal("la fusion ne modifie pas les fragments",
                         (len(front.servers), len(front.jobs)), (1, 1))

    tiers = compose(
        SiteSpec(name="x", third_party_hosts=(ThirdPartyHost("tiers-a", 5, 1000),)),
        SiteSpec(name="x", third_party_hosts=(ThirdPartyHost("tiers-a", 5, 1000),
                                              ThirdPartyHost("tiers-b", 2, 500))))
    journal.expect_equal(
        "un hôte tiers vu dans deux fragments n'est pas compté deux fois",
        sorted(h.host for h in tiers.third_party_hosts), ["tiers-a", "tiers-b"])
    print()


# ---------------------------------------------------------------------------
# Contrôles : provenances et serveur principal
# ---------------------------------------------------------------------------

def check_sources_and_primary(journal):
    print("Provenances et serveur principal")

    site = sample_site()
    sources = collect_sources(site)
    journal.expect_true("chaque provenance porte son chemin et son champ",
                        all("path" in s and "field" in s for s in sources),
                        "sans le chemin, on ne sait pas quel paramètre vient "
                        "de quelle source")
    journal.expect_true("les provenances couvrent serveur, traitement, étape "
                        "et audience",
                        {s["path"].split(":")[0] for s in sources}
                        >= {"server", "job", "step", "audience"})

    counts = confidence_summary(site)
    journal.expect_true("le résumé de confiance compte les valeurs par niveau",
                        sum(counts.values()) == len(sources) and "high" in counts)

    journal.expect_equal(
        "une valeur non tracée sur un champ non critique est signalée",
        len(untraced_fields(sample_site(
            servers=(sample_server(storage_gb=Traced(20.0, "GB_stored")),)))),
        1)
    journal.expect_equal("un site entièrement tracé ne signale rien",
                         untraced_fields(site), ())

    # Serveur principal : celui qui porte le plus d'octets.
    heavy = sample_server(key="lourd", evidence=Evidence(
        hosts=("h1",), ips=("10.0.0.1",), request_count=10,
        transferred_bytes=900_000))
    light = sample_server(key="leger", evidence=Evidence(
        hosts=("h2",), ips=("10.0.0.2",), request_count=500,
        transferred_bytes=2_000))
    multi = sample_site(servers=(light, heavy),
                        jobs=(sample_job(server_key="leger"),))
    journal.expect_equal(
        "le serveur principal est celui qui porte le plus d'octets",
        primary_server(multi).key, "lourd")
    journal.expect_true(
        "beaucoup de requêtes ne suffisent pas à désigner le serveur principal",
        primary_server(multi).key != "leger",
        "un service d'analytique concentre les requêtes sans porter le trafic")

    # À égalité d'octets, le choix doit être STABLE. Arbitraire est acceptable,
    # changeant d'une exécution à l'autre ne l'est pas.
    tie_a = sample_server(key="bbb", evidence=Evidence(hosts=("h1",),
                                                       transferred_bytes=100))
    tie_b = sample_server(key="aaa", evidence=Evidence(hosts=("h2",),
                                                       transferred_bytes=100))
    journal.expect_equal(
        "à égalité d'octets, le départage est stable et reproductible",
        (primary_server(sample_site(servers=(tie_a, tie_b),
                                    jobs=(sample_job(server_key="bbb"),))).key,
         primary_server(sample_site(servers=(tie_b, tie_a),
                                    jobs=(sample_job(server_key="bbb"),))).key),
        ("aaa", "aaa"))

    journal.expect_true("un serveur sans preuve ne fait pas échouer le départage",
                        primary_server(sample_site()).key == "web")
    journal.expect_equal("un site sans serveur retourne None, sans erreur",
                         primary_server(SiteSpec(name="x")), None)

    journal.expect_equal("un site à un seul serveur n'a pas de note à ajouter",
                         servers_note(site), None)
    note = servers_note(multi)
    journal.expect_true(
        "la note multi-serveurs nomme le principal et les autres",
        note is not None and "lourd" in note and "leger" in note,
        "sans elle, les clés au singulier laissent croire à une seule machine")
    print()


# ---------------------------------------------------------------------------
# Contrôle : la bibliothèque reste indépendante d'e-footprint
# ---------------------------------------------------------------------------

def check_nielsen_temps_utilisateur(journal):
    print("Temps utilisateur — Nielsen recalé, jamais silencieux hors domaine")

    # Domaine de validité publié par Nielsen (30-1250 mots) : correctement
    # reconnu aux deux bornes et à l'intérieur.
    journal.expect_true(
        "150 mots est dans le domaine Nielsen (30-1250)",
        is_within_nielsen_domain(150.0))
    journal.expect_true(
        "30 mots (borne basse incluse) est dans le domaine Nielsen",
        is_within_nielsen_domain(30.0))
    journal.expect_true(
        "1250 mots (borne haute incluse) est dans le domaine Nielsen",
        is_within_nielsen_domain(1250.0))
    journal.expect_true(
        "10 mots est HORS du domaine Nielsen",
        not is_within_nielsen_domain(10.0))
    journal.expect_true(
        "2000 mots est HORS du domaine Nielsen",
        not is_within_nielsen_domain(2000.0))

    # La formule elle-même : 25 s de socle + 4,4 s par 100 mots.
    journal.expect_equal(
        "Nielsen brut à 0 mot vaut le socle seul (25 s)",
        nielsen_raw_seconds(0.0), 25.0)
    journal.expect_equal(
        "Nielsen brut à 100 mots vaut 25 + 4,4 s",
        nielsen_raw_seconds(100.0), 29.4)

    # Recalage : moyenne SimilarWeb / moyenne des Nielsen bruts du parcours.
    # Deux pages à 100 et 200 mots -> Nielsen bruts 29.4 et 33.8, moyenne 31.6.
    raws = [nielsen_raw_seconds(100.0), nielsen_raw_seconds(200.0)]
    factor = recalibration_factor(15.8, raws)
    journal.expect_true(
        "le facteur de recalage est la mesure divisée par la moyenne des Nielsen bruts",
        factor is not None and abs(factor - 0.5) < 1e-9,
        f"attendu 0.5, obtenu {factor!r}")

    journal.expect_true(
        "recalage impossible sans mesure SimilarWeb (avg_time_on_page_s=None)",
        recalibration_factor(None, raws) is None)
    journal.expect_true(
        "recalage impossible sans aucune page à Nielsen connu",
        recalibration_factor(15.8, []) is None)
    journal.expect_true(
        "recalage impossible si toutes les pages du parcours sont à None (repli Lot 3)",
        recalibration_factor(15.8, [None, None]) is None)

    # step_user_time() : les quatre combinaisons dégradent la confiance
    # (jamais silencieusement) exactement quand attendu.
    in_domain_recalibrated = step_user_time(150.0, factor)
    journal.expect_true(
        "page dans le domaine + recalage disponible -> confiance medium",
        in_domain_recalibrated is not None and in_domain_recalibrated.confidence == "medium",
        f"confiance obtenue : {in_domain_recalibrated.confidence if in_domain_recalibrated else None!r}")
    journal.expect_true(
        "medium : aucun motif de dégradation dans le commentaire",
        "hors du domaine" not in in_domain_recalibrated.comment
        and "SANS recalage" not in in_domain_recalibrated.comment)

    out_of_domain = step_user_time(10.0, factor)
    journal.expect_true(
        "page hors domaine (10 mots) -> confiance dégradée (low)",
        out_of_domain is not None and out_of_domain.confidence == "low")
    journal.expect_true(
        "le motif de sortie de domaine est ÉCRIT dans le commentaire, jamais silencieux",
        "domaine de validité Nielsen" in out_of_domain.comment)

    no_recalage = step_user_time(150.0, None)
    journal.expect_true(
        "aucune mesure SimilarWeb -> confiance dégradée (low), Nielsen BRUT appliqué",
        no_recalage is not None and no_recalage.confidence == "low"
        and abs(no_recalage.value - nielsen_raw_seconds(150.0)) < 1e-9)
    journal.expect_true(
        "le motif d'absence de recalage est ÉCRIT dans le commentaire, jamais silencieux",
        "aucune mesure SimilarWeb" in no_recalage.comment)

    both_degraded = step_user_time(10.0, None)
    journal.expect_true(
        "hors domaine ET sans recalage -> les DEUX motifs sont écrits, pas un seul",
        both_degraded is not None
        and "domaine de validité Nielsen" in both_degraded.comment
        and "aucune mesure SimilarWeb" in both_degraded.comment)

    journal.expect_true(
        "aucun comptage de mots (repli Lot 3) -> pas de Traced deviné, None explicite",
        step_user_time(None, factor) is None)

    journal.expect_true(
        "le Traced produit est bien tracé (source_name renseigné) : "
        "un temps Nielsen ne doit jamais ressembler à une mesure sans provenance",
        in_domain_recalibrated.has_source)
    print()


def check_no_efootprint_import(journal):
    print("Indépendance — la spécification n'importe pas e-footprint")

    # build.py est l'EXCEPTION documentée : c'est le seul module dont la
    # raison d'être est d'instancier e-footprint (cf. son en-tête). L'exempter
    # ici par son nom, pas en l'ignorant en silence : si un second fichier
    # se met un jour à importer e-footprint, ce contrôle doit encore le voir.
    EXEMPT_FILES = {"build.py"}

    library = SCRIPTS_DIR / "efootprint_model"
    offenders = []
    build_py_imports_efootprint = False
    for path in sorted(library.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        imports_here = []
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(),
                                      start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if stripped.startswith(("import efootprint", "from efootprint")):
                imports_here.append(lineno)
        if not imports_here:
            continue
        if path.name in EXEMPT_FILES:
            build_py_imports_efootprint = True
            continue
        offenders.extend(f"{path.name}:{lineno}" for lineno in imports_here)

    journal.expect_true(
        "aucun module de la spécification (hors build.py) n'importe e-footprint",
        not offenders,
        f"importé dans {', '.join(offenders)}. La spécification doit rester "
        "testable sans la librairie installée ; cette propriété se perd au "
        "premier import et ne se remarque pas tant qu'elle est installée.")

    journal.expect_true(
        "build.py importe bien e-footprint (l'exemption n'est pas devenue "
        "obsolète en silence)",
        build_py_imports_efootprint,
        "si ce contrôle échoue, soit build.py a été vidé de son rôle, soit "
        "l'exemption ne cible plus le bon fichier : dans les deux cas, "
        "l'exemption doit être revue, pas laissée traîner sans objet.")

    # Le contrôle ci-dessus est textuel. Celui-ci est réel : on vérifie que
    # l'import du PAQUET (donc de __init__.py, spec.py, compose.py) n'a
    # effectivement PAS chargé e-footprint. build.py n'est pas importé par
    # __init__.py (cf. son garde-fou propre) donc reste hors de ce test.
    journal.expect_true(
        "importer la spécification ne charge pas e-footprint en mémoire",
        not any(name == "efootprint" or name.startswith("efootprint.")
                for name in sys.modules),
        "un import indirect suffit à rendre la bibliothèque dépendante")
    print()


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Contrôle des garde-fous de efootprint_model/ : une "
                    "spécification correcte passe, chaque faute prévue est "
                    "refusée.")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Affiche aussi les contrôles réussis.")
    args = parser.parse_args()

    journal = Journal(verbose=args.verbose)

    print("-" * 68)
    print("  GARDE-FOUS — efootprint_model/")
    print("-" * 68)
    print()

    check_traced(journal)
    check_critical_fields(journal)
    check_structures(journal)
    check_external_api(journal)
    check_validation(journal)
    check_reserves(journal)
    check_compose(journal)
    check_sources_and_primary(journal)
    check_nielsen_temps_utilisateur(journal)
    check_no_efootprint_import(journal)

    total = journal.passed + len(journal.failures)
    print("-" * 68)
    if journal.failures:
        print(f"[ÉCHEC] {len(journal.failures)} contrôle(s) sur {total} :")
        for label, detail in journal.failures:
            print(f"  - {label}")
            print(f"    {detail}")
        print()
        print("Un contrôle en échec sur un REFUS attendu est le cas grave : le")
        print("garde-fou laisse passer, donc une valeur non tracée peut atteindre")
        print("le rapport sans que rien ne le signale.")
        return 1

    print(f"[SUCCÈS] {total} contrôles. Les garde-fous répondent.")
    print()
    print("Rappel de portée : ce contrôle vérifie des REFUS, pas des chiffres.")
    print("La non-régression numérique est celle de check_efootprint_contract.py,")
    print("et la généricité ne sera prouvée que par un second site réel.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
