-----
e-footprint methodology (Boavizta): what the calculation measures, what it relies on, its limits
-----

This document answers a simple but not so simple question: when the EROOM report
displays "X kg CO2e/year", what exactly does this figure represent, and how far can
we trust it? Everything below was verified in the locally installed source code
(`e-footprint` v22.3.1, Boavizta's Python package), not deduced or assumed.

It deals ONLY with what the e-footprint library itself does. What the Agent EROOM
project ADDS on top (Nielsen reading time recalibrated, uncertainty ranges, topology
detection...) is documented elsewhere (see `skill-steps/45_efootprint.md` and the
project's persistent memory); this document only mentions them when they touch a point
discussed here.


-----
Summary in 7 points (details and references in the sections that follow)
-----

- **Not an ISO 14040/14044 LCA.** Only 2 phases modeled (manufacturing + use);
  transport and end of life excluded, judged negligible by the authors themselves.
- **Single-criterion.** CO2e only. Water, abiotic resources, acidification and
  co. are announced as a future evolution, not yet delivered.
- **Generative AI: calculated if added by hand, never automatically.** A third-party
  AI (OpenAI, Anthropic...) detected in the network traffic is FLAGGED but not
  included in the total CO2e without manual intervention; a self-hosted model
  (GPU) is, for its part, invisible from the HAR and can only be added by hand.
- **Main sources: ADEME (Base Carbone V19) for hardware manufacturing, Boavizta API
  for cloud instances, Our World in Data (2023-2024) for electricity carbon intensity
  by country**, plus several dated one-off studies (ARCEP 2022, State of Mobile 2022,
  arXiv papers). Neither ecoinvent, nor GreenIT LCA, nor ReCiPe/PEF.
- **Key hard-coded assumptions: lifespans 3 to 6 years depending on the hardware,
  datacenter PUE 1.2, generic electricity carbon intensity 400 g CO2/kWh.**
- **Advantages**: calculation traceable formula by formula, fine granularity per
  component, open code (free license), actively maintained by Boavizta.
- **Limits assumed by the authors**: deliberately restricted scope, sometimes dated
  assumptions, two default values (PUE, generic intensity) with no source cited in
  the code.


-----
1. Is it a Life Cycle Assessment (LCA)?
-----

**No, not in the ISO 14040/14044 sense.** The code never uses the terms "LCA" to
qualify itself. A full LCA normally covers five phases: raw material extraction,
manufacturing, distribution/transport, use, end of life. e-footprint models only
**two** of them:

- **Manufacturing** (`Manufacturing`): carbon footprint of building the hardware,
  amortized over its lifespan.
- **Use** (`Usage`): carbon footprint of the electricity consumption during use.

(Reference: `efootprint/core/lifecycle_phases.py`, class `LifeCyclePhases`.)

Hardware transport and end of life (recycling, waste) are **explicitly excluded**,
judged negligible by the authors themselves. Quote from the package's official README:

> "the lifecycle phases of device transportation and end of life are currently
> considered negligible."

Network hardware manufacturing is also not modeled (only its use consumption is):
"Network fabrication is not modeled" (`efootprint/core/hardware/network.py`).

**What this means concretely when reading an EROOM report**: the CO2e figure does not
cover the full life cycle of the hardware. It notably ignores transport (the server
arriving from the manufacturer by boat/plane) and end of life (dismantling, recycling,
e-waste). On IT hardware, these two items are generally documented as minor compared to
manufacturing and use, which partly justifies the authors' choice, but it is not
exhaustive coverage.


-----
2. Is it a multi-criteria analysis (beyond carbon)?
-----

**No, not in this version. The calculation is single-criterion: CO2e (greenhouse
  gases) only.**

No model output concerns abiotic resource depletion (ADP), acidification,
eutrophication, ecotoxicity or water consumption. All output units of the code are
carbon; all attributes are called `carbon_footprint_*`, never `water_footprint` or
`adp_footprint`.

The package README confirms this and announces a future evolution, not yet delivered:

> "Other environmental impacts (water, rare earth metals, etc.) will be added soon
> through an integration with the Boavizta API."

One point to note, for precision: for calls to generative AI APIs (OpenAI, Anthropic,
etc.), e-footprint relies on a third-party library (**EcoLogits**) which itself
calculates *internally* three additional indicators (abiotic resource depletion,
primary energy, water consumption). But e-footprint's code deliberately filters these
three values before exposing them: they are cached "for a future Boavizta integration"
but remain, to this day, outside the displayed carbon scope
(`efootprint/builders/external_apis/ecologits/`).

**What this means concretely**: an EROOM report says nothing about the water consumed,
the rare metals extracted, or the soil acidification linked to hardware manufacturing.
A multi-criteria analysis (16-category PEF type, or ReCiPe) would require another tool,
or waiting for the announced Boavizta integration.


-----
3. Artificial intelligence components: how the calculation treats them (or not)
-----

A site can call generative AI in two different ways, and e-footprint does not treat
them at all the same way.

**3.1. Call to a third-party generative AI (external API, e.g. a chatbot querying
GPT/Claude/Gemini/Mistral)**

e-footprint has a dedicated class, `ExternalApiSpec`/`EcoLogitsGenAIExternalAPI`
(`efootprint/builders/external_apis/ecologits/`), which relies on a third-party
library, **EcoLogits** ("genai-impact" project). The catalog covers 6 providers:
**Anthropic, OpenAI, Google Generative AI, Mistral AI, Cohere, Hugging Face**. For a
given model, EcoLogits provides the number of parameters, the throughput, the
datacenter location and the carbon intensity of the local electricity grid, to
calculate a footprint per call (a function of the number of output tokens generated).

**It is a calculation, not a network estimate.** The reason documented in the code
(`spec.py`, class `ExternalApiSpec`): unlike a CDN or a font that delivers a ready-made
file, a call to a generative model triggers a real computation (the model produces the
text word by word) — counting it only in transferred bytes would largely underestimate
its real footprint.

**Since 28/08/2026, this component CAN be added automatically to the calculation —
but only if the user knows the exact model.** Step 25 of the efootprint skill
(overview before calculation) *detects* that a call to a third-party generative AI
happened — by exact domain name recognition in the HAR (`detect_tech.py`, categories
"OpenAI (API)", "Anthropic (API Claude)", "Google Generative AI (Gemini)", "Mistral
AI (API)", "Cohere (API)", "Azure OpenAI", "Hugging Face Inference API"). Step 30 then
asks two questions (exact model, then typical length of a response); the number of
calls per year is itself derived automatically from the number of requests to this host
observed in the captured HAR, cross-checked with the site's already known annual traffic
(SimilarWeb or manual input) — never an additional question.

The two remaining questions do not get the same treatment in case of an "I don't know"
answer (MCQ decision of 28/08/2026):
- **Unknown model**: the host stays out of the calculation, FLAGGED in the report but not
  quantified. No default offered: EcoLogits models differ too much from each other
  (provider, size) for a default value to be honest.
- **Unknown response length** (model alone known): the call is counted anyway, with a
  documented default assumption ("average response", ~150 words,
  `_DEFAULT_OUTPUT_TOKENS` in `from_har.py`) — visible as such in the assumptions
  appendix, never a silent default.

Calculation mechanics (`efootprint_model/from_har.py::_ai_job_specs_for_step()`):
a dedicated `JobSpec` carries the `ExternalApiSpec`, attached to the **same 1st-party
server already modeled** for the page where the call was seen — never an additional
fictional server (a previous archetype, `archetypes/ia_streaming.py`, would have created
one and doubled the server manufacturing if plugged as-is on a real site; not used by
this mechanism). The network weight of the call stays counted once, in the page job;
this dedicated `JobSpec` carries `data_transferred=0` and exists only to trigger the
EcoLogits calculation.

Concrete example of what this represents, once the two questions are answered:

```python
ExternalApiSpec(provider="anthropic", model_name="claude-sonnet-4-5", output_tokens=195,
                request_count_per_step=3.0)  # request_count_per_step derived from the HAR
```

Persistence: the user's answers are written into `env-data.json::ai_external_apis` (one
entry per host, never expired except on an explicit `--refresh` of `collect_env_data.py`)
— unlike annual traffic/instance type, which are asked again at each skill run.

**Limit that remains true**: only the **text** case is covered (chatbots/assistants).
Third-party generative **video** AI (Sora, Veo, Kling...) is neither detected nor
calculated — track 2 of the comparative review, not planned to date.

**3.2. Self-hosted AI server (the site runs its own model on its own machines, e.g. a
dedicated GPU)**

There, e-footprint has a different class, `GPUServer`
(`efootprint/core/hardware/gpu_server.py`), which models a GPU-equipped server:
dedicated power (400 W per GPU, source arXiv paper "Estimating the Carbon Footprint
of BLOOM"), manufacturing (150 kg CO2e per GPU), lifespan 6 years, PUE 1.2 (same
default assumptions as a classic server, cf. section 5).

**This path is, again, never activated automatically.** A GPUServer cannot be detected
from a simple captured network traffic (HAR): by nature, inference runs server-side,
invisible from the browser. A self-hosted model behind a site's application API emits
no distinctive network signal — just like any self-hosted database (cf. the systematic
warning of Step 25: "a database or a self-hosted service behind the application server
emits no visible signal from the captured network traffic"). A `GPUServer` can therefore
only be added by hand, based on information transmitted by the team operating the site
(never deduced from the HAR).

**What this means concretely when reading an EROOM report**: if the report mentions no
generative AI, this can mean either that there is none, or that it is invisible from the
captured network traffic (self-hosted server). If the report FLAGS an identified
third-party generative AI, the displayed total CO2e does not include it as long as it has
not been manually added to the model: distinguishing "detected in the topology" from
"counted in the calculation" is essential to avoid underestimating the site's real
footprint.


-----
4. What data does the calculation rely on?
-----

The source registry is centralized in the code (`efootprint/constants/sources.py`,
class `Sources`). Summary of what actually feeds a calculation:

| Modeled data | Source | Observed vintage |
|---|---|---|
| Carbon manufacturing of generic hardware (server, smartphone, laptop, screen, box) | Base Carbone® ADEME, version "V19" | Not stated explicitly in the source name; code comments dated 2018-2023 |
| Manufacturing + characteristics of cloud instances (AWS, GCP, Azure, OVH, Scaleway) | Boavizta API (`api.boavizta.org/v1/cloud/instance`), with an embedded snapshot | Snapshot frozen in the package, not re-dated on each call |
| Electricity carbon intensity, by country | Our World in Data | 2023 or 2024 depending on the country (varies line by line in the provided file) |
| SSD/HDD manufacturing | arXiv paper "Dirty secret of SSDs: embodied carbon" | One-off study, no official reference vintage |
| Mobile network (energy per GB) | ARCEP Observatory | Q3 2022 |
| Daily smartphone/laptop usage time | data.ai, "State of Mobile" | 2022 |
| Wifi/mobile energy (kWh/GB) | Traficom study (Finland) | Not stated |
| Server GPU manufacturing and power | arXiv paper "Estimating the Carbon Footprint of BLOOM" | One-off study |
| Footprint of calls to a third-party generative AI | EcoLogits library | Depends on updates of this dependency |

**What is NOT used** (verified by searching the code, absence confirmed):
ecoinvent, GreenIT Life Cycle Analysis, ReCiPe, PEF. These are recognized LCA
databases/methods, but they appear nowhere in e-footprint.

**What this means concretely**: the data are not all of the same freshness nor the same
nature. Some are official databases regularly updated (ADEME, Boavizta), others are
one-off studies frozen in time (ARCEP 2022, State of Mobile 2022, the BLOOM paper). A
report generated in 2026 therefore relies, for part of its assumptions, on measurements
that are several years old.


-----
5. What are the structuring assumptions of the calculation?
-----

These are values hard-coded in the library, applied by default to any calculation unless
the user explicitly overrides them.

**Hardware lifespan** (period over which manufacturing is amortized):

| Equipment | Default lifespan |
|---|---|
| Smartphone | 3 years |
| Laptop / Internet box / Screen | 6 years |
| Server (generic or GPU) | 6 years |
| SSD storage | 6 years |
| HDD storage | 4 years |

**Other default assumptions:**
- PUE (datacenter energy overhead, cooling etc.) : **1.2** (hard-coded value, no
  source cited in the code).
- Generic electricity carbon intensity (if no country is specified) :
  **400 g CO2/kWh**.
- Daily usage rate: smartphone 3.6 h/day, laptop/screen 7 h/day, box 24 h/day
  (source State of Mobile 2022).
- Device power: smartphone 1 W, laptop 50 W, box 10 W, screen 30 W, server
  300 W (50 W idle).
- Default server utilization ("fill rate"): 0.9 (90 %).
- Data replication factor: 3 copies, default retention period 5 years.

**What this means concretely**: each calculation rests on about ten default assumptions
that are NOT measured on the audited site, but come from sector averages. The EROOM
report documents them one by one, with a confidence badge, precisely to make this
assumption part visible (see the "Methodology & assumptions" appendix of each report).


-----
6. Advantages
-----

- **Calculation traceability.** Each calculated value stays linked to the formula and
  the inputs that produced it (internal `ExplainableObject` mechanism). The tool can
  generate a calculation graph that shows, value by value, where it comes from.
- **Fine granularity.** The model distinguishes servers, storage, network, user devices,
  each with its own parameters (instead of one aggregated global figure).
- **Open and verifiable.** Free license (AGPL v3), code and assumptions readable,
  unlike a proprietary black-box calculator.
- **Active and documented.** Maintained by Boavizta (an association recognized in the
  responsible digital ecosystem), with a graphical interface and online documentation.
- **Extensible.** Allows adding specific cloud instances via the Boavizta API,
  generative AI calls via EcoLogits, and recently "edge devices" (consoles,
  connected objects) with hierarchical groupings.


-----
7. Limits (theirs, assumed in their own documentation)
-----

- **Restricted life-cycle scope.** Neither transport nor end of life modeled (judged
  negligible, the authors' assumption, not demonstrated in the code itself).
- **Single-criterion.** No indicator beyond carbon to date; multi-criteria (water,
  abiotic resources...) is announced but not delivered.
- **Frozen and sometimes dated assumptions.** Some source studies are several years old
  (ARCEP 2022, State of Mobile 2022) and are not automatically updated by a version
  upgrade.
- **PUE and generic carbon intensity with no cited source.** These two default values
  (1.2 and 400 g/kWh) are not attached to a reference in the code: use them as an order
  of magnitude, not a measurement.
- **The network has no manufacturing footprint.** Only its use consumption is counted;
  telecom infrastructures (cables, antennas, routers) are absent from the manufacturing
  calculation.


-----
8. What the Agent EROOM project adds (reminder, detailed elsewhere)
-----

These points are NOT native to e-footprint: they are specific to the integration done
in this project, to compensate for or document some of the limits above.

- **User reading time (Nielsen 2008 recalibrated)**: e-footprint expects a usage time
  per journey step as input, it does not calculate it itself. The project derives it
  from the real content of the captured pages (word count), recalibrated on a SimilarWeb
  engagement measurement. See `efootprint_model/user_time.py` and the "Reading time per
  step" appendix of each report.
- **Non-cumulative uncertainty ranges** (infrastructure vs use): added by the project
  to visualize the sensitivity of the result to two distinct assumptions, without ever
  adding them together (see persistent memory "non-cumulative ranges").
- **Value/source/confidence traceability per line** in the HTML appendix: a project
  convention, not e-footprint's itself (which traces the formula but does not display a
  confidence badge in its own output).
