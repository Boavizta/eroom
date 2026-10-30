# Inventory of the 26 criteria: dimension 0 (quick diagnostic) and dimension 6 (ease of change)

Study scope: the 16 criteria `0.1` to `0.16` (dimension "0 - Quick diagnostic") and the 10 criteria `6.1` to `6.10` (dimension "6 - Ease of change") of the EOF-V.1.1 reference.

Sources consulted (read-only, no modification):
- `.claude/skills/eof/docs/EOF-V.1.1 (EROOM Optimization Framework) - Template - English/eof-reference.json`
- `.claude/skills/analyse-parcours/scripts/questionnaire-blocs.json`
- `.claude/skills/analyse-parcours/scripts/eof_criteria_mapping.py`

## Dimension 0 - Quick diagnostic (0.1 to 0.16)

Specific to this dimension: the 0.x criteria have neither `method`, nor `max_potential`, nor a coefficient. Each has only a label, a 5-rung answer scale (sometimes 3), and an `impact_level` always equal to "Decisive".

| Criterion | Label | Current block(s) | Type | Grouped with | Automated today |
|---|---|---|---|---|---|
| 0.1 | Would the disappearance of the digital service have a significant impact? | gate-diag-0.1 | direct | none | No |
| 0.2 | Are there redundant features or duplicate applications in the system? | gate-diag-0.2 | direct | none | No |
| 0.3 | Are the main components subject to high-availability constraints? | gate-composite-high-availability-0.3 | composite | 6.10 | No |
| 0.4 | Dependencies: how many technical links to other systems are in place? | gate-diag-0.4 | direct | none | No (contextual hint wired, cf. file 02) |
| 0.5 | Is the project source code fully or partially accessible to the team? | gate-diag-0.5 | direct | none | No |
| 0.6 | Are the skills needed to update the service available? | gate-diag-0.6 | direct | none | No |
| 0.7 | Is the architecture complexity high? | gate-diag-0.7 | direct | none | No |
| 0.8 | Is the infrastructure (number and size of components) very large? | gate-diag-0.8 | direct | none | No |
| 0.9 | Is a large volume of data stored? | gate-diag-0.9 | direct | none | No |
| 0.10 | Is the functional complexity high? | gate-diag-0.10 | direct | none | No (contextual hint wired but inert on octo.com, cf. file 02) |
| 0.11 | Are the user journeys smooth, intuitive and friction-free in UX/UI? | gate-diag-0.11 | direct | none | No |
| 0.12 | Is the product compatible with the oldest hardware in the target fleet? | gate-diag-0.12 | direct | none | No |
| 0.13 | Does the product backlog contain performance issues and improvements? | gate-diag-0.13 | direct | none | No |
| 0.14 | Are the main features optimized and effective? | gate-diag-0.14 | direct | none | No |
| 0.15 | Is there a policy regarding the deletion and archiving of data? | gate-diag-0.15 | direct | none | No |
| 0.16 | Is the service hosted in a country whose electricity mix has a significant impact? | gate-diag-0.16 | direct | none | **Yes** - `eof_criteria_mapping.py`, category `automatable`, field `env-data.json: servers[].carbon_intensity_g_kwh` (exact duplicate of `3.3`). A manual question block still remains in the current questionnaire. |

## Dimension 6 - Ease of change (6.1 to 6.10)

Each 6.x criterion has a `method`, an `impact_level`, a `max_potential`, and the same 3-rung scale (🟢 easy / 🟡 moderate effort / 🔴 hard, coefficients 0 / 0.5 / 1).

| Criterion | Label | Max potential | Current block(s) | Type | Grouped with | Mapping category |
|---|---|---|---|---|---|---|
| 6.1 | Is there an effective observability setup for the product? | 2.0 | gate-dim6-6.1 | direct | none | `partial` (hint never ticked on its own) |
| 6.2 | Are there code reviews and/or pair programming? | 1.5 | gate-dim6-6.2 | direct | none | absent from the mapping |
| 6.3 | Is there an effective CI/CD process? | 1.5 | gate-dim6-6.3 | direct | none | `partial` |
| 6.4 | Are there non-regression tests? | 2.0 | gate-dim6-6.4 | direct | none | absent from the mapping |
| 6.5 | Is there a strong decoupling between the business domain and the technical integration? | 1.5 | gate-dim6-6.5 | direct | none | absent from the mapping |
| 6.6 | Are there software quality indicators? | 2.0 | gate-dim6-6.6 | direct | none | `partial` |
| 6.7 | Is there complete documentation? | 1.5 | gate-dim6-6.7 | direct | none | absent from the mapping |
| 6.8 | Is there duplicated code in the application? | 1.0 | gate-dim6-6.8 | direct | none | `partial` |
| 6.9 | Does the team have the autonamey to deploy the tools it needs? | 1.0 | gate-dim6-6.9 | direct | none | absent from the mapping |
| 6.10 | Are the main components subject to high-availability constraints? | 1.5 | gate-composite-high-availability-0.3 | composite | 0.3 | absent from the mapping (answer deduced from the same block as 0.3) |

## Coverage gaps

Exhaustive check (grep on all `0.x`/`6.x` occurrences in `questionnaire-blocs.json`): **all 26 criteria are covered by at least one block of the current questionnaire.** No gap. A single grouping in this scope: `0.3` + `6.10`, in the block `gate-composite-high-availability-0.3` (a single set of answers that fills both criteria at once, because it is the same underlying fact: availability constraints). All the other blocks are `direct`, one per criterion.

**Total: 25 questions asked for 26 criteria covered. Current ratio: 1.04 criterion/question.**
