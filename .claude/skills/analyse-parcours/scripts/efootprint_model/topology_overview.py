#!/usr/bin/env python3
"""
Overview of the detected topology, to present to the user BEFORE any CO2e
calculation (Step 25 of the efootprint skill).

ZERO e-footprint import here (like the rest of efootprint_model/): this
module only does cross-reading between an already-built `SiteSpec` and the
result of `detect_tech.detect_from_har()` (heuristic HAR detection, outside
e-footprint). It builds nor modifies no e-footprint object.

WHY A SEPARATE MODULE, RATHER THAN ENRICHING from_har.py:
from_har.py builds the SiteSpec that drives the CO2e calculation (contract
numerically checked by check_efootprint_contract.py) and carries the history
of already-fixed pitfalls (attribution by real bytes, not by page name).
This module drives NO number: it produces a DERIVED PRESENTATION (suspicion
annotations, text summary), never consumed by build.py. Separating the two
guarantees that this presentation step can never, even through a future
mistake, deflect a published CO2e total.

VOCABULARY: "suspected", never "detected" in the firm sense — except for an
AI/BaaS provider recognized by EXACT domain name (near-certain signal), where
the text may say "identified". An absence of signal NEVER proves the absence
of the technology: a self-hosted database behind the application server
emits no visible network signal on the client side, it is structurally
invisible from the captured traffic alone.
"""

from dataclasses import replace

# Categories from detect_tech.py routed to a ThirdPartyHost note. A mapping
# table, not a re-discovery of rules: this module ONLY routes a result already
# produced by detect_tech.py, never its own detection. The KEYS must stay
# byte-identical to the category strings emitted by detect_tech.py.
_SUSPICION_LABELS = {
    "Generative AI (third-party)": "third-party generative AI (identified by domain)",
    "Media streaming": "media streaming (suspected)",
    "Backend-as-a-Service / DB (third-party)": "third-party DB/BaaS (identified by domain)",
}

_SUSPICION_CATEGORIES = tuple(_SUSPICION_LABELS)


def _spec_hosts(spec):
    """The spec's third-party hosts, for the evidence->host routing below."""
    return tuple(h.host for h in spec.third_party_hosts)


def annotate_third_party_hosts(spec, tech_result):
    """Returns a COPY of `spec` whose `ThirdPartyHost`s carry a `note` of
    suspicion when `tech_result` (detect_tech.detect_from_har()) attached
    this host to one of the followed categories.

    Never modifies `spec` in place (consistent with the rest of the library: a
    transformation returns a new one rather than modifying the one it is
    given). If `tech_result` is None (HAR absent, unreadable, or the
    detect_tech module unavailable), returns `spec` unchanged.

    KNOWN LIMIT: the host<-evidence routing is BEST-EFFORT. `evidence` is a
    text truncated to 60 characters built by detect_tech.py for human
    display, not for a guaranteed 100% programmatic re-matching (a truncated
    host or a request without a recognizable host in the evidence will not be
    routed). Accepted for this lot: an honest partial routing is better than
    an enlarged output contract on detect_tech.detect() for a marginal gain.
    """
    if not tech_result:
        return spec

    hosts = _spec_hosts(spec)
    host_to_labels = {}
    for tech in tech_result.get("technologies", []):
        label = _SUSPICION_LABELS.get(tech["category"])
        if not label:
            continue
        evidence = tech.get("evidence") or ""
        for host in hosts:
            if host in evidence:
                host_to_labels.setdefault(host, []).append(label)

    if not host_to_labels:
        return spec

    new_hosts = tuple(
        replace(h, note=", ".join(dict.fromkeys(host_to_labels[h.host])))
        if h.host in host_to_labels else h
        for h in spec.third_party_hosts
    )
    return replace(spec, third_party_hosts=new_hosts)


def overview_text(spec, tech_result):
    """Text summary of the detected topology, for Step 25 (before
    calculation).

    Combines: the number of 1st-party servers (spec.servers, already
    reliable — cf. from_har.py::detect_infrastructures()), the detected
    technologies grouped by followed category (DB/BaaS, streaming, AI), and
    the honest reminder that a self-hosted DB stays invisible from the HAR.
    """
    lines = []
    lines.append(f"Detected 1st-party servers: {len(spec.servers)}")
    for server in spec.servers:
        lines.append(f"  - {server.label}")

    if tech_result:
        categories = tech_result.get("categories") or {}
        for cat in _SUSPICION_CATEGORIES:
            names = categories.get(cat) or []
            if names:
                lines.append(f"{cat} suspected: {', '.join(names)}")

    lines.append(
        "Note: a database or a self-hosted service BEHIND the application "
        "server emits no visible signal from the captured network traffic. "
        "This section can therefore NEVER conclude to its absence — only "
        "report the third-party services directly exposed to the browser."
    )
    return "\n".join(lines)
