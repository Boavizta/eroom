-----
-----
# The pitfalls of the EOF reference framework, recorded verbatim
-----
-----

**This file contains no opinion about EOF.** It lists the places where the reference framework,
as EROOM publishes it, says something other than what we think we read. Each pitfall is backed
by the exact text of the source, so it can be found again without rediscovering it.

**Why this file exists**: the same accident has happened at least six times in this project.
Someone reads a criterion's label, deduces what to ask, and gets it wrong, because
the label and the evaluation method do not ask the same question. Each time, the result is
a wrong answer in the deliverable, which is worse than an empty box.

**THE GOLDEN RULE, it explains half of this document**: it is the `method` key that defines what
the criterion measures. Neither the label (`criterion`), nor the pedagogical text (`explanation`).
Those two are for talking to the reader, the `method` is for deciding.

-----

## Where is the source, and how to re-verify this file

Everything below is extracted from:

```
.claude/skills/eof/docs/EOF-V.1.1 (EROOM Optimization Framework) - Template - English/eof-reference.json
```

It is the only file the code reads. The copy of EROOM's Google Sheet's 9 tabs is in
`docs/source-sheet/`, and `verify_source_sheet.sh` says whether EROOM has evolved its source since.

The option labels are copied **character for character**, emojis included, because
`validate_questionnaire_blocks.py` rejects any label that does not exist in the reference framework. Never
touch them up to make them prettier.

To re-verify a point in this file, the generic command:

```bash
python3 - <<'PY'
import json
R=".claude/skills/eof/docs/EOF-V.1.1 (EROOM Optimization Framework) - Template - English/eof-reference.json"
d=json.load(open(R))
cr={c["id"]:c for c in d["criteria"]}
dr={q["id"]:q for q in d["quick_diagnostic"]}
c=cr["5.3"]                       # replace with the wanted id
print(c["criterion"]); print(c["explanation"]); print(c["method"])
print(c["evaluation_coefficient_options"])
print(dr["0.13"]["screens"])        # for a quick-diagnostic question
PY
```

-----
-----
# Part 1. Structural pitfalls
-----
-----

## 1.1 There are two answer vocabularies, and even three ways to answer

The reference framework does not ask its questions in a single way. Counting on it is the first pitfall.

**The 44 criteria of dimensions 1 to 5** have exactly these 5 options, with their coefficient:

| Exact label | Coefficient |
|---|---|
| `✅ Confirmed strength` | 0 |
| `💡 Improvement potential identified` | 1 |
| `🚫 Not applicable` | 0 |
| `🤔 To be assessed` | 0 |
| `⌛️ Assessment in progress` | 0,5 |

The ids concerned: 1.1 to 1.16, 2.1 to 2.5, 3.1, 3.2, 3.3, 3.5 to 3.9, 4.1 to 4.6, 5.1 to 5.9.

**The 10 criteria of dimension 6** have a completely different vocabulary, and **only
three options**:

| Exact label | Coefficient |
|---|---|
| `🟢 Easy to change` | 0 |
| `🟡 Moderate effort` | 0,5 |
| `🔴 Hard to change` | 1 |

The ids concerned: 6.1 to 6.10. There is **neither `🚫 Not applicable`, nor `🤔 To be assessed`, nor
`⌛️ Assessment in progress`** on dimension 6. Code that assumes the 5 options exist
everywhere crashes or fabricates an answer unknown to the reference framework.

**The 16 quick-diagnostic questions** (ids `0.1` to `0.16`) have no options at all: they
have `screens`, a written scale, **different for each question**, and **with no
coefficient**. They therefore weigh nothing in the optimization potential. The lot output
contract requires it anyway: an answer given on a `0.x` question must go out **without** a
`coefficient` key, while a detailed criterion requires one.

## 1.2 Criterion 3.4 does not exist

Dimension 3 goes from `3.1` to `3.9` but counts only **8 criteria**: `3.4` is absent from the
source. It is not a data loss on our side, it is a numbering gap at EROOM's.
All the other dimensions are complete.

Practical consequence: never generate a list of ids by looping over a range. Always
iterate over what the source contains.

## 1.3 The quick diagnostic's 1-to-5 scale has no constant direction

**This is the most dangerous pitfall for the respondent, and it is invisible.** The 16 questions
all use a numbered 1-to-5 scale, but **the meaning of the number changes from one question to
the next**. Three families coexist.

**Family A, 9 questions: level 1 is the unfavorable situation, level 5 the favorable one.**
`0.2`, `0.3`, `0.7`, `0.10`, `0.11`, `0.12`, `0.14`, `0.15`, `0.16`.

Example, `0.7`: level 1 = `1 - Very complex / I don't know`, level 5 = `5 - Very simple`.

**Family B, 3 questions: it is the reverse, level 1 is the favorable situation.**
`0.5`, `0.6`, `0.13`.

Example, `0.6`: level 1 = `1 - The team has a solid command of the functional and technical design of the
project and can work with full confidence.`, level 5 = `5 - No one knows the project.`

Example, `0.5`: level 1 = `1 - The source code is fully available (open source or fully
accessible to the organization).`, level 5 = `5 - No, the source code is not available / I don't
know.`

**Family C, 4 questions: the scale measures not a merit but a size.** Neither good nor bad.
`0.1`, `0.4`, `0.8`, `0.9`.

Example, `0.8`: level 1 = `1 - One of the organization's largest infrastructures`, level 5 =
`5 - Very small (e.g. a few VMs or containers)`.

**Consequences, both count**:

1. A respondent who understood that 5 is the good score will be wrong on `0.5`, `0.6` and `0.13`. Our
   questionnaire displays the full label of each level, which protects, **provided we never
   display only the number and never reorder the levels**.
2. **The quick diagnostic's levels cannot be added or averaged.** An overall score of
   the door would be meaningless. This is consistent with what the code does today: the
   quick diagnostic has no score, we store the level's label and nothing else.

## 1.4 Question 0.13 has only 3 levels, numbered 1, 3 and 5

All the other questions have 5 levels numbered 1 to 5. `0.13` has **three**, and they carry the
numbers **1, 3 and 5**, as if two levels had been removed without renumbering.

Verbatim of the three levels:

```
1 - In the backlog and a recurring topic
3 - Some improvements are possible
5 - No performance issue identified
```

Consequence for the code: **never deduce a level's rank from its printed number.** The
parser finds the answer by the index of the checked box (`<!-- opt:N -->`, 0-based) and re-reads
the original level in the reference framework. That is the only safe method.

## 1.5 Eight levels stick an admission of ignorance onto an extreme level

**It is the worst default on an unknown, and it is in the source.** Eight levels mix
a precise situation and the mention "I don't know". An honest respondent who does not know
is therefore given an extreme level.

Verbatim of the eight, with the level number as printed:

| Question | Level concerned | Verbatim |
|---|---|---|
| `0.5` | level **5** | `5 - No, the source code is not available / I don't know.` |
| `0.7` | level 1 | `1 - Very complex / I don't know` |
| `0.9` | level 1 | `1 - The product has one of the largest data storage volumes in the IS / I don't know.` |
| `0.10` | level 1 | `1 - Very complex / I don't know` |
| `0.11` | level 1 | `1 - The UX/UI is very poor, users complain and/or there are pending items to fix it / I don't know` |
| `0.12` | level 1 | `1 - Incompatible or unknown` |
| `0.14` | level 1 | `1 - Not optimized enough / don't know` |
| `0.15` | level 1 | `1 - No policy / don't know` |

Note that `0.5` is the only one where the admission is attached to level **5** and not to level 1: it is a
direct consequence of its inverted direction, described in 1.3.

**What our code does with it, and why it is safe**: the generator removes the mention from the **displayed**
label, so that the respondent is not scored "very complex" because they said they didn't
know. The lot written, however, always carries the original level, mention included, because the parser
finds the answer by the box index and never by text comparison. **Never make the parser
depend on the displayed text**, otherwise this cleanup stops being a reading comfort and
becomes a falsification.

The respondent who does not know also has a separate "I don't know" box,
added by our generator on all blocks, which records no answer and adds nothing to the radar.

-----
-----
# Part 2. The label does not say what the method asks
-----
-----

This is the family of pitfalls that cost the project the most. It comes in four forms.

## 2.1 About twenty criteria are worded backwards, and `✅ Confirmed strength` answers the method, not the label

A good half of the criteria asks a question whose **good** answer is "no". Examples of
labels: `Are there many trackers on the product?`, `Is application support poor on the oldest targeted devices?`, `Is there duplicated code in the application?`, `Are the deployment components (VM, server, containers)
oversized?`, `Are the performance indicators poor?`.

On a criterion like that, checking `✅ Confirmed strength` **does not mean "yes"**. It
means "the validation criterion expressed in the `method` is satisfied", so here "there are not
many trackers".

**Consequence, never to forget when writing a question**: an option's label is
interpreted only relative to the `method`, never relative to the criterion's label. That is why
the `direct`-type blocks of our questionnaire do not write their options by hand:
they are read from the reference framework, which makes divergence impossible.

## 2.2 Two criteria are outright written as a negative statement

They are not even questions.

**`2.2`**, Decisive, potential 2,0:

```
criterion: There is no compatibility strategy.
```

**`3.2`**, potential 1,5:

```
criterion: There is no environmental impact monitoring system.
method  : Confirmed strength if satisfactory monitoring is in place; otherwise, there is an
          improvement potential.
```

On `3.2`, the label asserts the absence of monitoring and the `✅ Confirmed strength` option means
**that monitoring is in place**. The label and the option literally contradict each other. Only the
`method` allows deciding, and it is explicit here, which makes it an easy case despite
appearances.

## 2.3 The method of 2.2 contains a passage that belongs to another criterion

It is the most serious defect of the reference framework in this list, and it concerns a **Decisive
at 2.0**, i.e. 2.5% of the total potential by itself.

```
criterion: There is no compatibility strategy.
method : Improvement potential exists if the project does not use elasticity tools
          and the load is not constant.
 The service is not compatible with all targeted devices, or the list of targeted devices is not known.
```

The first sentence talks about **elasticity and load**, which is the subject of `2.4` and `3.7`,
and has nothing to do with a compatibility strategy. The second sentence, however, matches the
label well.

**Reading retained**: only the second sentence is `2.2`'s method. The first is
presumably a copy-paste leftover in EROOM's source. ⚠️ This is an **interpretation**,
not a fact: it is written here to be debated, not to be believed. If `2.2` must be
decided one day, rely on the compatibility and the knowledge of the list of targeted
devices, and say so in the `source` field.

## 2.4 The label and the method sometimes ask two different questions

Five cases recorded, all verified verbatim. In each, a question written from the label
**would record the wrong fact**.

**`1.12`**, potential 1,5:

```
criterion: Are there many trackers on the product?
method : Tracking is strictly limited to what is necessary, the number of trackers/tools is
          kept to a minimum, and each tracking request is justified.
```

The label suggests a count. The method asks for a **justification**. A single
unjustified tracker fails, twenty justified trackers pass. No probe can establish the
justification: that is what makes this criterion non-automatable, whatever the quality of the
network capture.

**`1.3`**, potential 1,5:

```
criterion: Are updates of new features mandatory on all devices, regardless of operating
           system or browser?
method : Tests show that the update does not degrade performance on older or modest
           devices, and that the product offers optional or lightweight modes
           when necessary.
```

The label talks about the mandatory nature of an update, the method about performance
degradation and lightweight modes. They are not the same facts.

**`5.4`**, potential 1,0:

```
criterion: Are the performance indicators poor?
method : An improvement is identified if the performance indicators do not match the
           project's ambition (e.g. more than 2 seconds to display a web page).
```

There is **no absolute threshold**. The "2 seconds" is an example, not a rule. The
discriminating fact is the gap to the project's ambition, which only the product team knows. That
is why this criterion carries a "to be validated with the product manager" note in our
questionnaire.

**`5.6`**, potential 1,5:

```
criterion: Is the technical stack (Java, JS, Python, PHP, etc.) out of date?
method : An improvement is identified if the project's technical base is not up to date, at least
           up to the latest LTS version.
```

The label is broken French and ambiguous. The method sets the precise threshold: **the latest
LTS version**, which is not the latest stable version. That is what distinguishes `5.6` from `5.8`, which concerns
**dependencies** and asks for the latest stable version. A Java 21 LTS base with a four-year-old
framework satisfies `5.6` and fails `5.8`: the two criteria are indeed distinct, they must
not be answered by a single forced box.

**`5.1`**, potential 1,0:

```
criterion: Are there statistical analysis tools in place to highlight potential efficiency
           improvements?
```

The framework says **statistical**, not "static". It is tempting to read "static code
analysis" into it, which would be another subject. ⚠️ Nothing in the source allows deciding: do not
"correct" this word, and write the question so as to cover what the method says, namely
tools in place that have highlighted efficiency gains.

## 2.5 Four criteria are validated by the absence of a discovery, which rewards inaction

A family of pitfalls on its own, and it produces a false exemplary service if taken at face value.

```
5.1 method : An improvement is identified if the statistical analysis tools in place have
             revealed potential efficiency gains.
5.2 method : An improvement is identified if a load or stress testing campaign
             has revealed efficiency problems.
5.3 method : The criterion is met if the tasks identified by the team (issues, tickets,
             etc.) include points that improve performance/efficiency.
5.9 method : An improvement is identified if the team has detected
             compatibility issues.
```

Read literally, `5.1`, `5.2` and `5.9` are satisfied when **nothing was revealed**. Yet a
team that has **no** tool, **no** campaign and **no** compatibility test has effectively
revealed nothing: it would pass as exemplary when it never looked at anything.

**What the project decided, and which is not reopened**: the absence of the practice is treated
as a `💡 Improvement potential identified`, which is the criterion's manifest intent. The
options of our questions are written that way.

`5.3` is the symmetrical and instructive case: it is validated when the team **has**
identified performance topics. See part 4, overlap `0.13` and `5.3`.

-----
-----
# Part 3. Counting pitfalls
-----
-----

## 3.1 Three options weigh 0, and they do not say the same thing at all

On the 44 criteria of dimensions 1 to 5, **three options have coefficient 0**:

```
✅ Confirmed strength   coefficient 0   there is nothing to optimize, and we checked it
🚫 Not applicable        coefficient 0   the topic does not concern this service
🤔 To be assessed             coefficient 0   nobody knows anything
```

Once written in the results file, **they are indistinguishable in all
percentages**: each counts as an answer and places a point at 0% on its radar axis.

**`🤔 To be assessed` is therefore an admission of ignorance that imitates an exemplary service.** It is the only
mechanism of the project that actively fabricated a falsehood, and not a mere hole. It is
now locked: a composed question block can no longer map to `🤔 To be assessed`, and an
autotest proves it.

**`⌛️ Assessment in progress` (coefficient 0.5) remains allowed in a composed question, and this
distinction is deliberate.** "To be assessed" means "I have no idea", hence the 0. "Assessment
in progress" means "we are looking, and we expect to find potential", hence the 0.5. The second does
not fabricate a strength, and the respondent affirms it expressly. ⚠️ Do not "harmonize" by adding
`⌛️ Assessment in progress` to the lock: an autotest case exists to prevent that.

**`🚫 Not applicable` is an open and distinct topic.** It also weighs 0, so it also places a
point at 0%, **but it asserts something true**: there is nothing to optimize since the
topic does not apply. The right question is that of the denameinator: if three criteria out of six
are really out of scope, the real potential carries on the other three. The lot output contract
has a `sans_objet` field planned for that, **never used to date**.

## 3.2 Dimension 6 offers no escape hatch

As said in 1.1, dimension 6 has only three options and **none** allows saying "I don't
know" nor "out of scope". A respondent who does not know whether an observability setup exists has nothing
true to check.

That is what makes the "I don't know" box of our generator indispensable on these ten criteria:
it records a context and no answer, so it does not move the radar.

## 3.3 The potential is flat, no criterion dominates

Measured on the source: the 54 criteria weigh between **1.0 and 2.0**, for a total of **80.0**.
Distribution per dimension: dimension 1, 16 criteria for 23.5; dimension 2, 5 for 8.0;
dimension 3, 8 for 12.0; dimension 4, 6 for 8.0; dimension 5, 9 for 13.0; dimension 6, 10
for 15.5.

**Consequence to know before proposing to shorten the questionnaire by order
of importance**: it takes 14 questions out of 37 to cover half of the detailed potential, against
18.5 when picking at random. The gain is too small to justify an importance sort. There is
no long tail to cut.

The **8 Decisive** are worth 2.0 each, i.e. 16.0 out of 80.0, a fifth of the potential:
`1.1`, `1.2`, `2.2`, `5.8`, `5.9`, `6.1`, `6.4`, `6.6`.

-----
-----
# Part 4. Overlaps between the quick diagnostic and the detailed criteria
-----
-----

The reference framework sometimes asks **the same fact twice**, once in the quick diagnostic and once
in a detailed criterion. The questionnaire therefore asked the same question twice to the same client.

This part lists all the overlaps examined, with the verdict and its reason, so that the
analysis is not redone and above all so that those that were refused are not reopened.

## 4.1 `0.3` and `6.10`: the label is identical word for word. KEPT

```
0.3  criterion: Are the main components subject to high-availability constraints?
6.10 criterion: Are the main components subject to high-availability constraints?
```

There is nothing to interpret, it is the same sentence. Only the way to answer differs.

The 5 levels of `0.3`:

```
1 - 7 days a week, 24 hours a day - 99.99% - International coverage
2 - 7 days a week, 24 hours a day - 99%
3 - Some SLAs.
4 - 5 days a week, 8 hours a day - No SLA - No Disaster Recovery Plan (DRP)
5 - No SLA/SLO
```

The method of `6.10`: `The criterion is met if the system's availability constraints
still allow the team to modify or optimize the components without major difficulty.`

The direction goes the same way over the whole scale: the stricter the required availability, the
harder it is to modify. The correspondence is monotone and requires no judgment.

**And this overlap is technically feasible, which is not the case for the others**: the three
options of dimension 6 have neither "not applicable" nor "to be assessed", so there is no option to
fit that would have no equivalent among the levels. See 4.6 for the obstacle that blocks the
criteria of dimensions 1 to 5.

## 4.2 `0.12`, `1.8` and `5.9`: same subject, but the overlap gains nothing. DISCARDED

```
0.12 criterion: Is the product compatible with the oldest hardware in the target fleet, and
                does it offer a smooth experience on it?
1.8  criterion: Is application support poor on the oldest targeted devices?
1.8  method : The application works correctly on the oldest devices in the target group,
                without imposing unnecessary upgrades or causing performance issues
                that accelerate obsolescence.
5.9  criterion: Have compatibility issues been identified for the targeted devices?
5.9  method : An improvement is identified if the team has detected
                compatibility issues.
```

On the substance, `0.12` and `1.8` measure the same fact well, and `5.9` measures a third distinct one:
whether the team has **detected** them, not whether the issues exist.

**Reason for the refusal, and it is technical, not substantive**: `1.8` and `5.9` are already covered together
by a single question of our questionnaire, one of whose options is
`Our service does not target any old device: the user fleet is recent and under control`, which
sets `🚫 Not applicable` on both. Yet **none of `0.12`'s 5 levels can express an "out of
scope"**, and the validator requires that all the options of a composed question fill in
exactly the same set of criteria. Bringing `0.12` into this question would therefore force
removing the "out of scope" option, which is a legitimate answer.

And the count does not even move: today two questions cover three criteria, afterwards it
would still be two questions. **Zero gain, real loss.**

## 4.3 `0.13` and `5.3`: the reference framework counts backwards between its two parts. DISCARDED

**It is the most revealing case in the document.** Both concern the same subject.

```
0.13 criterion: Does the product backlog contain performance problems and improvements?
0.13 levels   : 1 - In the backlog and a recurring topic
                3 - Some improvements are possible
                5 - No performance issue identified

5.3  criterion: Has the team identified areas for improvement in terms of performance /
                efficiency and added them to the backlog?
5.3  method : The criterion is met if the tasks identified by the team (issues, tickets,
                etc.) include points that improve performance / efficiency.
```

In the quick diagnostic, **5 is presented as the good score**. So `No performance issue
identified` is the most flattering level.

For `5.3`, it is exactly the reverse: a team that identified nothing has looked at nothing, it
takes `💡 Improvement potential identified`, coefficient 1, the **maximum** potential. And
the team that has performance tickets in its backlog takes `✅ Confirmed strength`,
coefficient 0.

**The most flattering level of the door gives the worst score of the criterion, and vice versa.**

**Reason for the refusal**: the overlap is feasible, but the correspondence would have to be written
against the intuitive direction, and **no automatic check can detect an inversion**. The
validator checks that the answer's label exists in the reference framework, it knows nothing about
direction. A careless re-read would put the correspondence "the right way round" and fabricate a
wrong answer, without anything lighting up. The gain was one question out of sixty-three.

## 4.4 `0.14` and `5.5`: two different facts. REFUSED

```
0.14 criterion: Are the main features optimized and efficient?
5.5  criterion: Are the most critical use cases (most frequent user journeys)
                optimized?
5.5  method : An improvement is identified if no study has been conducted to improve the
                performance / efficiency of the most used code paths.
```

`0.14` asks whether the features **are** optimized. `5.5`'s method asks whether **a
study has been conducted**. Of `0.14`'s 5 levels, only one talks about study ("regularly reviewed for
optimization"). The other four do not inform `5.5`.

## 4.5 `0.11` and `1.13`: classic label-vs-method error. REFUSED

```
0.11 criterion: "Are user journeys smooth, intuitive, and free of UX/UI friction that could
                be improved?"
1.13 criterion: Are the main user journeys optimized to be smooth and
                efficient?
1.13 method : The main workflows require a minimal number of steps / screens,
                without redundant navigation, which improves efficiency and reduces the number of
                server or client requests.
```

The two labels look very similar, and that is exactly the trap. `0.11`'s
levels talk about felt friction, user complaints and user tests. `1.13`'s method talks about the **number of steps and screens**. A pleasant interface can very well have
eight redundant screens.

## 4.6 `0.15` and `4.1`: solid overlap on the substance, zero gain. DISCARDED

```
0.15 criterion: Is there a policy on data deletion and archiving?
0.15 levels   : 1 - No policy / don't know
                2 - Informal or ad-hoc deletion and archiving practices
                3 - A policy exists but is not applied consistently
                4 - A clear, partially automated policy is in place
                5 - A strict, enforced, regularly audited data deletion and archiving policy

4.1  criterion: Are deletion and archiving mechanisms in place?
4.1  method : The criterion is met if automatic deletion and archiving mechanisms
                exist and are actually applied.
```

The correspondence is good and monotone: levels 4 and 5 describe an automated and
applied policy, which is exactly `4.1`'s method.

**Reason for the discard**: `4.1` is already covered with `4.6` by a single question. Undoing it to
attach it to `0.15` would put `4.6` back as a separate question, so the question count would not
change. The only benefit would be filling in `4.1` (potential 1.5) **before** the decision to go into
detail. To be reconsidered if sequencing becomes the subject, not before.

## 4.7 The other approaches examined and discarded outright

| Approach | Why it does not hold |
|---|---|
| `0.6` skills available, and `6.9` team autonamey | having the skills is not having the right to deploy a tool |
| `0.7` architecture complexity, and `6.5` business / technical decoupling | `6.5`'s method asks whether the technique can be changed without touching the functional side, which a simple architecture does not guarantee |
| `0.2` redundant features, and `6.8` duplicated code | duplicated features in the information system are not duplicated code in an application |
| `0.16` country of the electricity mix, and `3.3` region of the electricity mix | real duplicate, **already handled**: both are read from the same collected data and `0.16` belongs to the automatic-judgment lot |

-----
-----
# Part 5. What the reference framework implies for automation
-----
-----

This is not a wording pitfall, but it is the conclusion that drives the most decisions, and
it is regularly forgotten.

**On the 16 criteria of dimensions 4 and 6, none of the methods can be satisfied by an
external observation.** Established by reading the 16 verbatim. The methods say, word for word,
"if the team has identified", "if a strategy is applied", "if the project has a complete set
of tests", "if observability tools are in place". These are internal states and team
practices. No HTTP request, no header, no DNS record, no public file
establishes them.

These two dimensions weigh 23.5 out of 80, i.e. 29.4% of the total potential.

**EOF asks about a team's maturity, not a website's technical surface.** The ceiling of
automation is therefore a property of the reference framework, not a defect of our tooling. The
only levers that move the numbers are asking for an artifact (the code repository, then
infrastructure as code or the cloud bill) or asking a question. Any additional public probe
on these dimensions can only produce a partial clue, hence a `context`, hence
never a point on the radar.

-----
-----
# Should we report it to EROOM?
-----
-----

**Open question, not decided.** Several points in this document are defects of the source
and not subtleties: the `3.4` gap, the eight levels that assign an extreme level to whoever says they
don't know, the method of `2.2` that contains a foreign passage, the contradiction between the
label of `3.2` and its option, the three levels of `0.13` numbered 1, 3, 5.

Reporting them would serve all users of the reference framework. To be decided with the user.
