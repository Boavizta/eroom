#!/usr/bin/env python3
"""Contrôle de non-régression dédié à la piste 1 (IA générative tierce texte,
cf. documentation/implementation/methodologie_efootprint.md section 3.1).

Contrairement à check_efootprint_contract.py (compare un audit réel à sa
baseline), ce script rejoue une fixture HAR SYNTHÉTIQUE minimale : aucun audit
réel disponible aujourd'hui n'a de host IA générative détecté, donc rien à
comparer à une baseline existante. Contrairement à check_efootprint_spec.py
(garde-fous purs Python, zéro import e-footprint), celui-ci importe la
librairie (comme build.py) pour vérifier un vrai calcul EcoLogits.

Ce que ce script prouve, par construction du modèle (pas par lecture de code) :
  1. un host IA détecté mais dont l'utilisatrice n'a pas donné le modèle
     ("resolved": False) NE CHANGE RIEN au total (statu quo, jamais de valeur
     inventée) ;
  2. le job IA générative, attaché au serveur 1st-party RÉEL, N'INFLATE JAMAIS
     son poste Servers (pas de double comptage, pas de serveur fictif — le
     risque identifié dans l'archétype ia_streaming.py lors du cadrage) ;
  3. une fois le modèle et output_tokens connus, le poste ExternalAPIs
     apparaît et le total augmente réellement.
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from efootprint_model.from_har import spec_from_env_data
from efootprint_model.build import build_system, energy_kg, fabrication_kg, total_kg

_FIXTURE_HAR = {
    "log": {
        "pages": [{"id": "page_1", "title": "https://example.com/"}],
        "entries": [
            {
                "pageref": "page_1",
                "request": {"url": "https://example.com/index.html"},
                "response": {
                    "_transferSize": 200000,
                    "headers": [],
                    "content": {"size": 200000, "mimeType": "text/html",
                                "text": "<html><body><p>bonjour le monde</p></body></html>"},
                },
                "serverIPAddress": "1.2.3.4",
            },
            {
                "pageref": "page_1",
                "request": {"url": "https://api.anthropic.com/v1/messages"},
                "response": {
                    "_transferSize": 5000,
                    "headers": [],
                    "content": {"size": 5000, "mimeType": "application/json"},
                },
                "serverIPAddress": "5.6.7.8",
            },
        ],
    },
}

_BASE_ENV_DATA = {
    "servers": [{"host": "example.com", "detected_provider": None,
                 "efootprint_country": "FRANCE", "country_code": "FR", "ip": "1.2.3.4"}],
    "server": {"efootprint_country": "FRANCE"},
    "device_mix": {"phone_fraction": 0.6, "desktop_fraction": 0.4},
    "network_mix": {"wifi_fraction": 0.4, "mobile_fraction": 0.6},
    "traffic": {"visits_per_year": 100000},
}


def _run(har_path, ai_external_apis):
    env_data = dict(_BASE_ENV_DATA)
    if ai_external_apis is not None:
        env_data["ai_external_apis"] = ai_external_apis
    spec, warnings = spec_from_env_data(env_data, har_path, "example.com")
    if warnings:
        raise AssertionError(f"warnings inattendus sur la fixture : {warnings}")
    built = build_system(spec)
    return fabrication_kg(built), energy_kg(built), total_kg(built)


def main():
    with tempfile.TemporaryDirectory() as tmp:
        har_path = Path(tmp) / "fixture.har"
        har_path.write_text(json.dumps(_FIXTURE_HAR), encoding="utf-8")

        fab_off, _, total_off = _run(har_path, None)
        fab_unresolved, _, total_unresolved = _run(har_path, {
            "api.anthropic.com": {"rule_name": "Anthropic (API Claude)",
                                   "provider": "anthropic", "resolved": False,
                                   "model_name": None, "output_tokens": None},
        })
        fab_on, ener_on, total_on = _run(har_path, {
            "api.anthropic.com": {"rule_name": "Anthropic (API Claude)",
                                   "provider": "anthropic", "resolved": True,
                                   "model_name": "claude-sonnet-4-5",
                                   "output_tokens": 300},
        })
        # Modèle connu, longueur de réponse INCONNUE (décision QCM du 28/08/2026) :
        # ne doit PAS exclure le host, doit utiliser la valeur par défaut
        # documentée (_DEFAULT_OUTPUT_TOKENS dans from_har.py).
        fab_default_len, ener_default_len, total_default_len = _run(har_path, {
            "api.anthropic.com": {"rule_name": "Anthropic (API Claude)",
                                   "provider": "anthropic", "resolved": True,
                                   "model_name": "claude-sonnet-4-5",
                                   "output_tokens": None},
        })

    checks = [
        (total_off == total_unresolved,
         "un host détecté mais NON résolu (modèle inconnu) ne doit rien changer "
         "au total (statu quo)"),
        (fab_off.get("Servers", 0) == fab_on.get("Servers", 0),
         "le job IA ne doit JAMAIS inflater le poste Servers du serveur réel "
         "(double comptage / serveur fictif)"),
        (fab_on.get("ExternalAPIs", 0) > 0 or ener_on.get("ExternalAPIs", 0) > 0,
         "le calcul EcoLogits doit produire une empreinte ExternalAPIs non nulle "
         "une fois le modèle et output_tokens connus"),
        (total_on > total_off,
         "le total doit augmenter une fois l'appel IA compté"),
        (total_default_len > total_off,
         "modèle connu mais longueur de réponse inconnue : ne doit PAS exclure "
         "le host, doit retomber sur la valeur par défaut documentée"),
        (fab_default_len.get("ExternalAPIs", 0) > 0 or ener_default_len.get("ExternalAPIs", 0) > 0,
         "la valeur par défaut de longueur de réponse doit produire un calcul "
         "ExternalAPIs non nul, pas un calcul silencieusement ignoré"),
    ]

    failed = [msg for ok, msg in checks if not ok]
    if failed:
        print("[ÉCHEC]")
        for msg in failed:
            print(f"  - {msg}")
        sys.exit(1)

    print(f"[SUCCÈS] {len(checks)} contrôles piste 1 (IA générative tierce texte).")
    print(f"  statu quo (non résolu) : total={total_off:.4f} kg")
    print(f"  résolu (modèle connu)  : total={total_on:.4f} kg "
          f"(+{total_on - total_off:.4f} kg dont ExternalAPIs "
          f"fab={fab_on.get('ExternalAPIs', 0):.4f} + "
          f"énergie={ener_on.get('ExternalAPIs', 0):.4f})")


if __name__ == "__main__":
    main()
