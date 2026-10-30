#!/usr/bin/env python3
"""Non-regression check dedicated to track 1 (third-party generative AI text,
cf. documentation/implementation/efootprint-methodology.md section 3.1).

Unlike check_efootprint_contract.py (compares a real audit against its
baseline), this script replays a minimal SYNTHETIC HAR fixture: no real audit
available today has a detected generative-AI host, so there is nothing to
compare against an existing baseline. Unlike check_efootprint_spec.py
(pure Python guards, zero e-footprint imports), this one imports the
library (like build.py) to verify a real EcoLogits computation.

What this script proves, by construction of the model (not by reading code):
  1. a detected AI host whose model the user did not provide
     ("resolved": False) CHANGES NOTHING in the total (status quo, never an
     invented value);
  2. the generative-AI job, attached to the REAL 1st-party server, NEVER
     inflates its Servers line (no double counting, no fictitious server — the
     risk identified in the ia_streaming.py archetype during scoping);
  3. once the model and output_tokens are known, the ExternalAPIs line
     appears and the total really increases.
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
                                "text": "<html><body><p>hello world</p></body></html>"},
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
        raise AssertionError(f"unexpected warnings on the fixture: {warnings}")
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
        # Known model, UNKNOWN response length (multiple-choice decision of 2026-08-28):
        # must NOT exclude the host, must fall back to the documented default
        # value (_DEFAULT_OUTPUT_TOKENS in from_har.py).
        fab_default_len, ener_default_len, total_default_len = _run(har_path, {
            "api.anthropic.com": {"rule_name": "Anthropic (API Claude)",
                                   "provider": "anthropic", "resolved": True,
                                   "model_name": "claude-sonnet-4-5",
                                   "output_tokens": None},
        })

    checks = [
        (total_off == total_unresolved,
         "a detected but UNRESOLVED host (unknown model) must not change "
         "the total (status quo)"),
        (fab_off.get("Servers", 0) == fab_on.get("Servers", 0),
         "the AI job must NEVER inflate the Servers line of the real server "
         "(double counting / fictitious server)"),
        (fab_on.get("ExternalAPIs", 0) > 0 or ener_on.get("ExternalAPIs", 0) > 0,
         "the EcoLogits computation must produce a non-zero ExternalAPIs "
         "footprint once the model and output_tokens are known"),
        (total_on > total_off,
         "the total must increase once the AI call is counted"),
        (total_default_len > total_off,
         "known model but unknown response length: must NOT exclude "
         "the host, must fall back to the documented default value"),
        (fab_default_len.get("ExternalAPIs", 0) > 0 or ener_default_len.get("ExternalAPIs", 0) > 0,
         "the default response-length value must produce a non-zero "
         "ExternalAPIs computation, not a silently skipped one"),
    ]

    failed = [msg for ok, msg in checks if not ok]
    if failed:
        print("[FAIL]")
        for msg in failed:
            print(f"  - {msg}")
        sys.exit(1)

    print(f"[SUCCESS] {len(checks)} checks, track 1 (third-party generative AI text).")
    print(f"  status quo (unresolved): total={total_off:.4f} kg")
    print(f"  resolved (known model) : total={total_on:.4f} kg "
          f"(+{total_on - total_off:.4f} kg, of which ExternalAPIs "
          f"fab={fab_on.get('ExternalAPIs', 0):.4f} + "
          f"energy={ener_on.get('ExternalAPIs', 0):.4f})")


if __name__ == "__main__":
    main()
