#!/usr/bin/env python3
"""
Rapport de dimensionnement (Lot 6) : compare, serveur par serveur, la demande
RÉELLE (raw_nb_of_instances, fractionnaire) au nombre d'instances effectivement
FACTURÉES (nb_of_instances, arrondi selon le mode de dimensionnement).

CE QUE CE RAPPORT MESURE, ET CE QU'IL NE MESURE PAS
----------------------------------------------------
Le ratio facturé/réel PEUT ressembler à un indicateur de surdimensionnement du
client, mais ce n'est PAS ce qu'il mesure ici : le trafic annuel est réparti en
timeseries UNIFORME sur 24 h (build.py:_hourly_volume), jamais sur le vrai
profil horaire du site. Un trafic uniforme lisse les pics qu'un trafic réel
concentrerait sur quelques heures, ce qui MINIMISE artificiellement l'écart
mesuré. NE JAMAIS présenter ce chiffre comme une mesure du surdimensionnement
réel d'un client (cf. handoff du 06/08/2026, plan H, Lot 6).

Pour l'instant ce n'est qu'un diagnostic INTERNE (écrit dans le JSON, pas
encore rendu dans le rapport HTML) : la décision d'affichage revient au Lot 9,
qui devra porter l'avertissement ci-dessus s'il choisit de le montrer.

PAS D'IMPORT EFOOTPRINT ICI
----------------------------
Ce module ne lit que des attributs déjà calculés par `build_system()`
(build.py) : `raw_nb_of_instances`/`nb_of_instances`, déjà des tableaux numpy
via `.magnitude`. Comme `ranges.py`, il n'a donc pas besoin d'être exempté du
contrôle `check_no_efootprint_import()`.
"""


def server_sizing(key, server, server_spec):
    """Dimensionnement d'un seul serveur construit.

    `server_spec` peut être None (défensif) si la clé n'est plus alignée avec
    `built.spec.servers` ; le rapport retombe alors sur la clé technique comme
    étiquette plutôt que d'échouer.
    """
    raw = server.raw_nb_of_instances.magnitude
    billed = server.nb_of_instances.magnitude

    real_instance_hours = float(raw.sum())
    billed_instance_hours = float(billed.sum())
    oversizing_ratio = (billed_instance_hours / real_instance_hours
                         if real_instance_hours > 0 else None)

    return {
        "key": key,
        "label": server_spec.label if server_spec else key,
        "server_type": server.server_type.value,
        "real_instance_hours": round(real_instance_hours, 4),
        "billed_instance_hours": round(billed_instance_hours, 4),
        "oversizing_ratio": round(oversizing_ratio, 4) if oversizing_ratio is not None else None,
        "peak_real_instances": round(float(raw.max()), 4),
        "peak_billed_instances": round(float(billed.max()), 4),
    }


def servers_sizing(built):
    """Dimensionnement de tous les serveurs d'un `BuiltModel` (build.py)."""
    server_specs = {s.key: s for s in built.spec.servers}
    return [
        server_sizing(key, server, server_specs.get(key))
        for key, server in built.servers_by_key.items()
    ]
