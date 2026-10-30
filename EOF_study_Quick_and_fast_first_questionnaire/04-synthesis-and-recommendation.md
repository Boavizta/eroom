# Synthesis: can we ask fewer questions to cover dimension 0 and dimension 6?

## The question asked

On the 26 EOF criteria of the "0 - Quick diagnostic" dimension (16 criteria) and the "6 - Ease of change" dimension (10 criteria), can we ask fewer questions to a human while covering the maximum number of criteria, without changing the EOF-V.1.1 reference nor degrading the precision of the answers?

## Starting numbers

- Current questionnaire: **25 questions for 26 criteria, ratio 1.04 criterion/question** (file 01).
- Real automation today: **1 criterion out of 26** (`0.16`), confirmed both on the reference alone and on octo.com's real data (files 02 and 03).
- 9 criteria have a "partial" hint (datum displayed in the appendix) but none dispenses with the human question, by construction of the reference.
- 15 criteria are internal facts about the team (skills, backlog, engineering practices, governance): no external datum can answer them, whatever the tooling. A 16th criterion (`0.15`) is not structurally out of reach but is not searched by the current tooling (cf. file 02).

## What was already tried on this scope, and did not work

On 2026-09-07, a QCM format with independent checkboxes was tested on a real run targeting 21 criteria of this same scope in 7 questions. Real result: **9 criteria settled out of 21 targeted**, worse than one direct question per criterion (which can cover up to 21/21 if the respondent answers everything). The screenshot provided upstream of this study corresponds to this trial. The decision taken at the time was to reject this format for this scope: it reduces the number of questions displayed, but it reduces the real coverage even more, which goes against the goal sought here (maximize answered criteria).

This study does not relaunch that trial. It did however look for, without finding it, another semantic duplicate comparable to `0.3`/`6.10` (the only existing merge) among the 26 criteria: no other pair covers exactly the same underlying fact without risking mixing two different answers in a single box.

## The only safe gain identified: a question asked for nothing

Criterion `0.16` is already solved automatically (`env-data.json`, provenance `collected`, exact duplicate of `3.3`), but the current questionnaire still asks a manual question for this criterion. It is the only case, out of the 26, where a question can be removed without losing the slightest coverage:

- Before: 25 questions / 26 criteria = 1.04
- After: 24 questions / 26 criteria = 1.083

Modest gain (one question less, about +4% ratio) but real, without degradation, and without touching the reference. Point of vigilance before acting: check with the team whether this manual question on `0.16` was kept voluntarily as a human confirmation point against the automation, rather than by oversight.

## Two different situations behind "no automatic answer"

The criteria without an automatic answer today are not all in the same situation, and the distinction matters to know where to look for a gain:

**The 9 "partial" criteria** (`0.4, 0.7, 0.10, 0.11, 0.12` in dimension 0; `6.1, 6.3, 6.6, 6.8` in dimension 6) already have a real datum measured by the tools, but this datum is never reliable enough to settle the criterion on its own: it is a correlation or an indirect hint, not proof. Examples: a good HTTP security grade (`6.1`) does not prove that an observability setup (logs, metrics, traces) is in place, it only makes it more likely. A Lighthouse duplicated-code score (`6.8`) only sees the JavaScript executed in the browser, not the real source code. The project rule is explicit: a "partial" datum never ticks a box on its own, it is at best displayed as a reminder in the question to help the human answer faster and with more confidence. On these 9 criteria, the datum already exists "on disk" (files `env-data.json`, `cwv.json`, `security-headers-analysis.json`, HAR) but is only wired as a reminder for 4 of them (`0.4`, `6.1`, `6.3`, `6.6`, `6.8` - see detail file 02); for `0.7`, `0.11` and `0.12`, the datum exists but is not even displayed yet.

**Criterion `0.15`** (data deletion/archiving policy) is different: no datum is collected today, neither box ticked nor hint displayed. But unlike the 15 "structural" criteria (which require an internal fact about the team, invisible from outside whatever the tool, e.g. "do you do code reviews?"), a data policy is sometimes published on a public page of the site (legal notices, "data protection" page...), so it is in principle observable from outside. The reason nothing is found today is that the tool `parse_public_pages.py` only looks for environmental patterns, not data retention/deletion patterns. It is a tool configuration gap, not a fundamental impossibility: unlike the 15 structural criteria, which no future development will make automatable, `0.15` can progress towards "partial" (or even be settled) with a targeted, low-risk code change.

## Jobs to explore to optimize the automation of answers

These jobs do not change the number of questions asked (this floor is already reached, cf. previous section): they increase the share of criteria where the human answers with a reminder of the data already collected "on disk", rather than blindly.

⚠️ **Update of 2026-09-10: jobs 1, 2 and 3 below are DONE** (numbered 37, 38,
39 in `tmp/handoff.md`, commits `671b45d`/`3f45a3f`). Contrary to the hope expressed in point 1,
`0.15` only progressed to the reminder (like the others), not to a settled answer:
no retention declaration was found on `audits/octo.com` (expected behavior, positively
tested on a synthetic case). Only job 4 (`0.10`) remains open, deliberately left
aside: not verifiable on octo.com, which has neither `robots.txt` nor `sitemap.xml` at all.

1. ✅ **DONE.** ~~Extend `parse_public_pages.py`~~ so that it also looks for data retention/deletion/archiving patterns (ex. "data protection", "retention period", "right to erasure"), in addition to the current environmental patterns.
2. ✅ **DONE.** ~~Wire the measured-fact reminder for `0.7`~~: the datum already exists (CSP listing backend hosts of PaaS type, CDNs detected in `tech_stack`), it only remains to display it in the question, on the same principle as what already exists for `0.4`.
3. ✅ **DONE.** ~~Wire the measured-fact reminder for `0.11` and `0.12`~~: the Core Web Vitals scores (accessibility, best practices, LCP/INP/CLS, CrUX category) are already collected in `cwv.json` and could be recalled in the questions on UX/UI smoothness and old-hardware compatibility, with the explicit caveat that these are technical hints, not a direct measure of the user's feeling.
4. **Check whether the sitemap can be found another way for `0.10`**: the mechanism already exists (`diag_context_0_10`) but remains inert on sites without a declared `sitemap.xml` (the octo.com case). Not a priority: even when it works, it is a weak proxy of functional complexity (a single page can carry a complex SPA).
5. **Do not try to automate the 15 structural criteria** (`0.1, 0.2, 0.3, 0.5, 0.6, 0.8, 0.9, 0.13, 0.14` and `6.2, 6.4, 6.5, 6.7, 6.9, 6.10`): they are internal facts about the team, no datum collectable from outside the service can answer them, whatever the tool developed (cf. memory [[reference_eof_maturite_pas_surface]]).

## Lead examined on 2026-09-10 and rejected as is: pre-ticking a suggested box

Initial request: on the "partial" criteria, instead of a simple prose reminder under the
question, directly pre-tick the box that the reminder suggests, the person only having to
confirm or correct. Sought objective: speed up filling in (59 questions, that is a lot).

**Why this is not just a "slightly more timid" automation**: a criterion is classified
"partial" precisely because no reliable threshold was found to turn the hint into a
precise box. If such a threshold existed, the criterion would already be "automatable" and
the box would already be ticked on its own (like `0.16`). Pre-ticking a box would therefore
amount to inventing this threshold that we just refused to invent, with the same risk as
an automation, not a lesser risk.

**Two concrete risks identified**:
1. **Default bias**: an already-ticked box is statistically confirmed more often than it
   is corrected, even when it is wrong — documented cognitive bias, not a supposition.
2. **Confirmation indistinguishable from oversight**: `parse_questionnaire.py` only reads
   whether a box is ticked or not. It cannot distinguish "the person thought and confirmed
   our suggestion" from "the person sent the file back without really rereading it". That
   is exactly the kind of silent failure this project has put a lot of energy into
   eliminating elsewhere (cf. memory [[feedback_echec_silencieux_vs_absence]]): a false
   human confirmation, indistinguishable from a real one, would fabricate a wrong figure
   with an appearance of legitimacy (a box ticked by a human) higher than that of a simple
   "I don't know".

**What already exists and covers part of the need, without this risk**: the prose reminder
*does* say what the measurement suggests (ex. for `0.7`: "3 components detected... which
suggests several separate bricks"). The person does not have to search for the information,
only to read it and choose. The reading-speed gain is already acquired; what would be missing
is only the physical act of ticking, not the reflection.

**Decision**: idea not implemented, not definitively rejected. If it is taken up again, it
needs a design guardrail before any code: for example display the suggestion visually
apart from the checkboxes (never in an already-ticked box), so that ticking remains an active
and verifiable act, never a default state one could just let slip by.

## Honest conclusion

On this precise scope, **the number of questions asked is already close to the structural floor of the reference**, for three cumulative reasons:

1. Almost all the criteria not covered by automation (15 out of 25) concern internal facts about the team, by construction invisible from outside the service.
2. The only merge possible without loss of precision (`0.3` + `6.10`, the only clean structural overlap of the reference between quick diagnostic and dimension 6) is already in place.
3. The format that promised to reduce the number of questions (QCM with independent checkboxes) was tested on almost this same scope and degraded the real coverage rather than improving it.

The remaining lever is therefore not reducing the number of questions (already close to its floor, apart from the 1-question gain above), but improving the quality of the answer to each question asked, so that a hesitant respondent does not leave a criterion at "I don't know" when they could have answered.

## Recommendations for the follow-up (not implemented in this study)

This study modified no production file, in accordance with the requested scope. The 5 jobs listed above ("Jobs to explore to optimize the automation of answers") would require touching `run_eof.py`, `eof_criteria_mapping.py` and `parse_public_pages.py`, hence a dedicated decision and session. In addition:

1. ✅ **ALREADY ACQUIRED, not a job.** ~~Remove the redundant question on `0.16`~~: verified on
   2026-09-10 by really rerunning `generate_questionnaire.py` on `audits/octo.com`, `0.16`
   no longer appears in the produced questionnaire. A general mechanism already in place (not
   specific to `0.16`) automatically removes any question whose criterion already has a
   settled answer. The "25 questions" announced above was therefore already stale when written.
2. **Do not reopen the QCM grouping** on this scope: already tested, already rejected, the real result (9/21 in 7 questions) is documented above and in the project memory.
