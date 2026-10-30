# EOF-V.1.1 (EROOM Optimization Framework) — Full reference

> Generated from the source Google Sheet: https://docs.google.com/spreadsheets/d/1_fymJEyXxKjqy3jFlyO8MHhfmLZduUsLyloMeU2kSRM/edit
>
> **Blank template** — no answer is pre-filled. The Excel file provided as a complement was only used for two things that the Sheet's data API does not provide: the 2 logos of the "Read me" section and 3 hyperlink URLs (see where relevant).

## Contents

- [Read me](#read-me)
- [0 — Quick diagnostic](#0--quick-diagnostic)
- [🛠 6 — Ease of change](#6--ease-of-change)
- [🛖 1 — Product](#1--product)
- [🗺️ 2 — Architecture](#2--architecture)
- [🏢 3 — Infrastructure](#3--infrastructure)
- [💾 4 — Storage and data](#4--storage-and-data)
- [👨‍💻 5 — Algorithms & code](#5--algorithms--code)
- [Synthesis](#🕸️-7--synthesis)

## 📖 Read me

![Logo Boavizta](logo1.png) ![Licence CC BY-SA](logo2.png)

> ⚠️ The Boavizta logo (`logo1.png`) is white on a transparent background: it does not show on a white-background Markdown render (GitHub, VS Code, most viewers). Only visible on a dark background, or when opening the file directly. Not fixed here (graphic retouching out of scope) — flagged so it is not mistaken for a missing image.

### 🎯 Purpose of the EROOM Optimization Framework

This diagnosis evaluates the maturity of a digital service to identify its key optimisation levers - algorithm, code, architecture, operations, data, hosting, etc.

Each question focuses on a factor influencing performance, efficiency, or maintainability.

The diagnosis is not a performance grade - it helps prioritize where to act first. There are no “good” or “bad” scores, only opportunities for improvement.

### 📊 Scoring Scale

For each criterion, assign a score from 1 to 5 based on the current level of mastery.

1 = not mastered / unknown

5 = mastered and measured

Each question contributes equally to the overall score, which is then converted into a percentage of optimization potential (0%–100%).

This percentage reflects how much room for improvement remains for the service.

### 🧮 Score Interpretation

The total score is expressed as a percentage of optimization potential.

• High percentage → strong potential for improvement (technical, organizational, or environmental).

• Low percentage → already mature or efficient service.

The diagnosis does not assign a performance grade.

It is designed to prioritise actions and identify where improvement efforts will have the most impact.

There are no “good” or “bad” results - only opportunities to act.

### 💡 For who?

The EROOM quick diagnosis is designed to be lightweight and accessible, but it requires a minimum understanding of the technical context.

It can be carried out by:

• someone familiar with the technical environment, able to assess the maturity of current practices;

• a tech–product duo, to cross perspectives and ensure alignment between technical and functional priorities;

• an external consultant, as part of an audit or Green IT assessment.

### 💡 How to Use

A diagnosis corresponds to a single digital service.

An organisation can therefore perform several quick diagnoses to build a complete map of its information system and identify where to act first.

Step 1 - Duplicate the file

The tool is provided as a Google Sheets spreadsheet.

Start by duplicating the file for your own use so you can enter your answers without modifying the original template.

Step 2 - Identify the scope

The diagnosis is performed for a digital service, a platform, or the entire IS.

Each evaluated service should have its own dedicated sheet.

Step 4 - Answer the questions - 0 - Quick Diagnosis

Assign a score from 1 to 5 for each question, based on the available information.

1 = not mastered / unknown

5 = mastered, measured, optimised

When uncertain, select 1 (“I don’t know”) or choose a conservative score, and note the point to clarify later.

You can ignore any criteria by setting its Weight to “Not Applicable”.

If the Quick Diagnosis score is very low, there is no need to continue with the detailed steps. The optimisation potential is either already low or too difficult to reach, so it is more efficient to focus on other services.

Step 5 - Answer the questions - 1 - Product to  - 5 - Algo&Code

✅ Strength confirmed = already addressed, no potential of improvement left.

💡 Improvement potential identified = not fully addressed, significant room for improvement remains.

You can ignore any criteria by setting its Weight to “Not Applicable”.

Step 6 - Answer the questions - 6 - Ease of change

🟢 Easy to change = can be updated with minimal obstacles.

🟡 Moderate effort = bring change would be an achievable challenge.

🔴 Hard to change = implementing change would be difficult.

You can ignore any criteria by setting its Weight to “Not Applicable”.

Step 7 - Collaborate across roles

Complete the diagnosis with technical, product, and sustainability (RSE) representatives to build a shared understanding, not to grade the teams.

The goal is to create a shared understanding, not to assign a performance grade.

Low score → mature, already efficient service.

High score → strong potential for optimisation (technical, organisational, or environmental).

Step 7 - Use the results

Compare the results across services.

Those with the highest scores become the priority candidates for deeper analysis within the EROOM framework.

License CC-BY-SA

This license enables reusers to distribute, remix, adapt, and build upon the material in any medium or format, so long as attribution is given to the creator. 
The license allows for commercial use. If you remix, adapt, or build upon the material, you must license the modified material under identical terms.

CC BY-SA includes the following elements: 
BY = credit must be given to the creator - SA = Adaptations must be shared under the same terms.


-----

## 🏦 0 — Quick diagnostic

*Identify the best optimization opportunities. A higher score reflects greater optimization potential.*

### 0.1 — Would it have a high impact if the digital service were to disapear ?

**Evaluation**
- [ ] 1 - No or negligible impact
- [ ] 2 - Limited impact on a small group of users or processes
- [ ] 3 - Moderate impact but workarounds exist
- [ ] 4 - Significant impact on core activities
- [ ] 5 - Critical impact (operations blocked, major business or SI risk)

**Impact level**
- [ ] Moderate
- [ ] Significant
- [x] Decisive

### 0.2 — Are there redondant features or duplicate applications among the system ?

**Evaluation**
- [ ] 1 - Something very similar already exists elsewhere (same feature or same code).
- [ ] 2 - Part of it already exists elsewhere.
- [ ] 3 - Small similarities exist, but nothing major.
- [ ] 4 - Almost no similarity with other products or code.
- [ ] 5 - Completely unique; nothing similar exists.

**Impact level**
- [ ] Moderate
- [ ] Significant
- [x] Decisive

### 0.3 — Do main components got high availability constraints?

**Evaluation**
- [ ] 1 - 7/7 24/24 - 99.99% - International coverage
- [ ] 2 - 7/7 24/24 - 99%
- [ ] 3 - Some [SLA](https://fr.wikipedia.org/wiki/Service-level_agreement).
- [ ] 4 - 5/7 8/24 - No SLA - No DRP
- [ ] 5 - No SLA/SLO

**Impact level**
- [ ] Moderate
- [ ] Significant
- [x] Decisive

### 0.4 — Dependencies: How many technical links to other systems are in place?

**Evaluation**
- [ ] 1 - The product is not connected to any other systems
- [ ] 2 - The product is connected to a few of the other systems
- [ ] 3 - The product is connected to some other systems and the connection is important (business value and/or technical coupling)
- [ ] 4 - The product is connected to many of the other systems
- [ ] 5 - The product is connected to most of the other systems in the IS (eg : authentication and authorization)

**Impact level**
- [ ] Moderate
- [ ] Significant
- [x] Decisive

### 0.5 — Is the source code of the project fully or partially available to the team?

**Evaluation**
- [ ] 1 - The source code is fully available (open source or fully accessible to the organization)
- [ ] 2 - The source code is mainly available (code accessible internally, but not to the public).
- [ ] 3 - The source code is partially available (some components or modules are accessible).
- [ ] 4 - Access is restricted to a very small group or the supplier only.
- [ ] 5 - No, the source code is not available / I don't know.

**Impact level**
- [ ] Moderate
- [ ] Significant
- [x] Decisive

### 0.6 — Are skills available to update the service?

**Evaluation**
- [ ] 1 - The team is well versed in the functional and technical design of the projet and can work confidently
- [ ] 2 - The team knows most of the project and can work on it with caution
- [ ] 3 - The knowledge about the project is poor
- [ ] 4 - Some people know a bit about the project
- [ ] 5 - No one knows the project

**Impact level**
- [ ] Moderate
- [ ] Significant
- [x] Decisive

### 0.7 — Is it possible to simplify the architecture?

**Evaluation**
- [ ] 1 - Very Complex / I don't know
- [ ] 2 - Complex
- [ ] 3 - Medium
- [ ] 4 - Simple
- [ ] 5 - Very simple

**Impact level**
- [ ] Moderate
- [ ] Significant
- [x] Decisive

### 0.8 — Is the infrastructure (number and size of the compenents like VM and containers) very large ?

**Evaluation**
- [ ] 1 - One of the largest infrastructures in the organisation
- [ ] 2 - Larger than most services
- [ ] 3- Comparable to the organisational average
- [ ] 4- Smaller than most services
- [ ] 5- Very small (e.g. a few VMs or containers)

**Impact level**
- [ ] Moderate
- [ ] Significant
- [x] Decisive

### 0.9 — Is an important volume of data stored?

**Evaluation**
- [ ] 1 - The product has among the largest data storage volumes in the IS / I don't know
- [ ] 2 - The product stores a large volume of data in the IS compared to most systems
- [ ] 3 - The product stores an average amount of data compared to the rest of the IS
- [ ] 4 - The product stores a limited amount of data
- [ ] 5 - The product stores very little data

**Impact level**
- [ ] Moderate
- [ ] Significant
- [x] Decisive

### 0.10 — Is there a high functional complexity?

**Evaluation**
- [ ] 1 - Very Complex / I don't know
- [ ] 2 - Complex
- [ ] 3 - Medium
- [ ] 4 - Simple
- [ ] 5 - light

**Impact level**
- [ ] Moderate
- [ ] Significant
- [x] Decisive

### 0.11 — Are user journeys smooth, intuitive, and free of UX/UI friction that could be improved?

**Evaluation**
- [ ] 1 - The UX/UI is very poor, users complain and/or there are items in the backlog to change it / I don't know
- [ ] 2 - The UX/UI shows recurring friction points or usability issues
- [ ] 3 - The UX/UI is functional but a few aspects could be improved
- [ ] 4 - The UX/UI is clear and pleasant to use, only minor improvements identified
- [ ] 5 - The UX/UI is well polished, user-tested, and provides a smooth, consistent experience

**Impact level**
- [ ] Moderate
- [ ] Significant
- [x] Decisive

### 0.12 — Is the product compatible with the oldest hardware of the target fleet and provides a seamless experience on them?

**Evaluation**
- [ ] 1 - Incompatible or unknown
- [ ] 2 - Compatible but with significant degradation (irritating or frustrating for the user)
- [ ] 3 - Compatible and usable but not comfortable (noticeable slowness)
- [ ] 4 - Compatible and mostly smooth (minor slowdowns)
- [ ] 5 - Compatible and seamless (comfortable and responsive even on older hardware)

**Impact level**
- [ ] Moderate
- [ ] Significant
- [x] Decisive

### 0.13 — Does the product backlog contain performance issues and improvements?

**Evaluation**
- [ ] 1 - In the backlog & recurring discussion
- [ ] 3 - A few improvements are possible
- [ ] 5 - No performance problem identified

**Impact level**
- [ ] Moderate
- [ ] Significant
- [x] Decisive

### 0.14 — Are the main features optimised and efficient?

**Evaluation**
- [ ] 1 - Not optimized enough / don’t know
- [ ] 2 - Some main features are inefficient or redundant
- [ ] 3 - The main features are functional but show room for optimisation
- [ ] 4 - Most main features are well implemented and perform efficiently
- [ ] 5 - All main features are fully efficient, streamlined, and regularly reviewed for optimisation

**Impact level**
- [ ] Moderate
- [ ] Significant
- [x] Decisive

### 0.15 — Is there a policy for data deletion and archiving?

**Evaluation**
- [ ] 1 - No policy / don’t know
- [ ] 2 - Informal or ad-hoc deletion and archiving practices
- [ ] 3 - A policy exists but is not consistently applied
- [ ] 4 - A clear policy is in place and partially automated
- [ ] 5 - A strict, applied, and regularly audited policy for data deletion and archiving

**Impact level**
- [ ] Moderate
- [ ] Significant
- [x] Decisive

### 0.16 — Is the service hosted in a country with an impactful electricity mix? (location based)

**Evaluation**
- [ ] 1 - > 750 gCO2e / kWh
- [ ] 2- < 500 gCO2e / kWh
- [ ] 3- < 300 gCO2e / kWh
- [ ] 4- < 200 gCO2e / kWh
- [ ] 5- < 100 gCO2e / kWh

**Impact level**
- [ ] Moderate
- [ ] Significant
- [x] Decisive


-----

## 🛠 6 — Ease of change

*Spot the best optimisation opportunities.*

### 6.1 — Is there an efficient observability system in place for the product ?

**Additional explanation**: Without a minimum of knowledge about the runtime behaviour of the product, it's difficult to identify optimisations. No monitoring implies low optimisatin potential.

**Evaluation**
- [ ] 🟢 Easy to change
- [ ] 🟡 Moderate effort
- [ ] 🔴 Hard to change

**Impact level**
- [ ] Moderate
- [ ] Significant
- [x] Decisive

### 6.2 — Is there code reviews and/or pair programming in place ?

**Additional explanation**: Code reviews and pair programmaing enforce minimum shared knowledge about the code base and minimum quality.

**Evaluation**
- [ ] 🟢 Easy to change
- [ ] 🟡 Moderate effort
- [ ] 🔴 Hard to change

**Impact level**
- [ ] Moderate
- [x] Significant
- [ ] Decisive

### 6.3 — Is there an effective [CI/CD](https://fr.wikipedia.org/wiki/CI/CD) in place ?

**Additional explanation**: The presence of a CI/CD is a good indicator of how easy it will be to work on the application with confidence.

**Evaluation**
- [ ] 🟢 Easy to change
- [ ] 🟡 Moderate effort
- [ ] 🔴 Hard to change

**Impact level**
- [ ] Moderate
- [x] Significant
- [ ] Decisive

### 6.4 — Is there non regression tests in place (unit tests, integration tests, end to end tests) ?

**Additional explanation**: The presence of non regression tests allow the programmers to change the software while beeing confident in the absence of problems indeuced by their work.

**Evaluation**
- [ ] 🟢 Easy to change
- [ ] 🟡 Moderate effort
- [ ] 🔴 Hard to change

**Impact level**
- [ ] Moderate
- [ ] Significant
- [x] Decisive

### 6.5 — Is there a strong decloupling between business domain & technical integration ?

**Additional explanation**: Decoupling practives like dependency injection or Hexagonal/Clean/Onion Architecture allow more effective and ambitious technical changes.
it's 'D' (Dependency Inversion) from 5 Solid principles

**Evaluation**
- [ ] 🟢 Easy to change
- [ ] 🟡 Moderate effort
- [ ] 🔴 Hard to change

**Impact level**
- [ ] Moderate
- [x] Significant
- [ ] Decisive

### 6.6 — Is there metrics to follow the software quality ?

**Additional explanation**: Like code coverage, cyclomatic complexity, number of issues, number of delivery problems, number of rollbacks, change lead time, deployment frequency, change fail percentage, failed deployment recovery time

**Evaluation**
- [ ] 🟢 Easy to change
- [ ] 🟡 Moderate effort
- [ ] 🔴 Hard to change

**Impact level**
- [ ] Moderate
- [ ] Significant
- [x] Decisive

### 6.7 — Is there an extensive documentation ?

**Additional explanation**: The presence of a relevant documentation allow more ambitious changes.

**Evaluation**
- [ ] 🟢 Easy to change
- [ ] 🟡 Moderate effort
- [ ] 🔴 Hard to change

**Impact level**
- [ ] Moderate
- [x] Significant
- [ ] Decisive

### 6.8 — Is there duplicated code in the application ?

**Additional explanation**: Duplicated code can be removed to simplify the products maintenance.

**Evaluation**
- [ ] 🟢 Easy to change
- [ ] 🟡 Moderate effort
- [ ] 🔴 Hard to change

**Impact level**
- [x] Moderate
- [ ] Significant
- [ ] Decisive

### 6.9 — Does the team have sufficient autonomy to deploy the tools it needs to observe, measure or optimise the system?

**Additional explanation**: Ease of change increases when teams can rely on the tools they need to monitor performance, measure impact, or analyse behaviour.
This autonomy may come from the ability to install custom tools, or from relying on comprehensive built-in tooling provided by the platform.
What matters is not where the infrastructure is hosted, but whether the team can instrument it effectively to support optimisation.

**Evaluation**
- [ ] 🟢 Easy to change
- [ ] 🟡 Moderate effort
- [ ] 🔴 Hard to change

**Impact level**
- [x] Moderate
- [ ] Significant
- [ ] Decisive

### 6.10 — Do main components got high availability constraints?

**Additional explanation**: High availability requirements can reduce the team’s ability to modify, migrate or optimise components.
Services that must maintain strict uptime leave fewer opportunities for maintenance windows, architectural changes or resource optimisation.
Understanding these constraints helps assess how easily the system can evolve toward lower environmental impact.

**Evaluation**
- [ ] 🟢 Easy to change
- [ ] 🟡 Moderate effort
- [ ] 🔴 Hard to change

**Impact level**
- [ ] Moderate
- [x] Significant
- [ ] Decisive


-----

## 🛖 1 — Product

*Spot the best optimisation opportunities.*

### 1.1 — Is there a low tech way exist to achieve this action ?

**Additional explanation**: If there's already a way to do it, does a digital way add value to the user ?

**Evaluation**
- [ ] ✅ Confirmed strength
- [ ] 💡 Improvement potential identified
- [ ] 🚫 Not applicable
- [ ] 🤔 To be assessed
- [ ] ⌛️ Assessment in progress

**Impact level**
- [ ] Moderate
- [ ] Significant
- [x] Decisive

### 1.2 — Are the target users, with there business needs, typical devices and ergonomy expectations, well known ?

**Additional explanation**: The product may not be well designed if the target users are not well known, or better, involved in the projet. For instance, the user journeys might be cumbersome or the compatibility strategy might be inadequate.

**Evaluation**
- [ ] ✅ Confirmed strength
- [ ] 💡 Improvement potential identified
- [ ] 🚫 Not applicable
- [ ] 🤔 To be assessed
- [ ] ⌛️ Assessment in progress

**Impact level**
- [ ] Moderate
- [ ] Significant
- [x] Decisive

### 1.3 — Are the new features updates mandatory for all devices, with no relation to their operating system or browser ?

**Additional explanation**: New features makes the application heavier. On older devices, users may prefer to keep the product simpler, with better performances and less resources used.

**Evaluation**
- [ ] ✅ Confirmed strength
- [ ] 💡 Improvement potential identified
- [ ] 🚫 Not applicable
- [ ] 🤔 To be assessed
- [ ] ⌛️ Assessment in progress

**Impact level**
- [ ] Moderate
- [x] Significant
- [ ] Decisive

### 1.4 — Does the design include custom made components instead of native ones ?

**Additional explanation**: System components (buttons, menu, forms, ...) are almost always more efficient than custom made ones. Not to mention accessible and compatible.

**Evaluation**
- [ ] ✅ Confirmed strength
- [ ] 💡 Improvement potential identified
- [ ] 🚫 Not applicable
- [ ] 🤔 To be assessed
- [ ] ⌛️ Assessment in progress

**Impact level**
- [x] Moderate
- [ ] Significant
- [ ] Decisive

### 1.5 — Is there animations, videos, sounds, maps (…) that are played automatically ?

**Additional explanation**: Playing this type of content without any user action is annoying and uses resources like bandwidth and gpu.

**Evaluation**
- [ ] ✅ Confirmed strength
- [ ] 💡 Improvement potential identified
- [ ] 🚫 Not applicable
- [ ] 🤔 To be assessed
- [ ] ⌛️ Assessment in progress

**Impact level**
- [x] Moderate
- [ ] Significant
- [ ] Decisive

### 1.6 — Is it possible to adapt the resources used by the application to the user's hardware configuration ?

**Additional explanation**: Not everyone has a device capable of running computationally intensive content (like multimedia content, etc.).
What happens if a user tries to run computationally intensive content on an inappropriate device? In this case, ideally, the service should not be blocking and should perform basic functions.

**Evaluation**
- [ ] ✅ Confirmed strength
- [ ] 💡 Improvement potential identified
- [ ] 🚫 Not applicable
- [ ] 🤔 To be assessed
- [ ] ⌛️ Assessment in progress

**Impact level**
- [x] Moderate
- [ ] Significant
- [ ] Decisive

### 1.7 — Are all features useful, usable and used ?

**Additional explanation**: Simplifying the product by removing unused features will result in less resources used.

**Evaluation**
- [ ] ✅ Confirmed strength
- [ ] 💡 Improvement potential identified
- [ ] 🚫 Not applicable
- [ ] 🤔 To be assessed
- [ ] ⌛️ Assessment in progress

**Impact level**
- [ ] Moderate
- [x] Significant
- [ ] Decisive

### 1.8 — Is the application support poor on the oldest devices targeted ?

**Additional explanation**: Most of the impacts of digital services are on the client devices side. Not pushing these devices to obsolescence by breaking compatibility is very important.

**Evaluation**
- [ ] ✅ Confirmed strength
- [ ] 💡 Improvement potential identified
- [ ] 🚫 Not applicable
- [ ] 🤔 To be assessed
- [ ] ⌛️ Assessment in progress

**Impact level**
- [ ] Moderate
- [x] Significant
- [ ] Decisive

### 1.9 — Is a high bandwidth network required to use the application ?

**Additional explanation**: Requiring high bandwidth means that there's a lot resource use. It indicates that some optimisations are possible to reduce the number and/or the size of requets.

**Evaluation**
- [ ] ✅ Confirmed strength
- [ ] 💡 Improvement potential identified
- [ ] 🚫 Not applicable
- [ ] 🤔 To be assessed
- [ ] ⌛️ Assessment in progress

**Impact level**
- [ ] Moderate
- [x] Significant
- [ ] Decisive

### 1.10 — Does the product uses UX dark patterns that increase resource use ?

**Additional explanation**: UX dark patterns includes infinite scroll, prechecked subscriptions, making unsuscribtion difficult, etc.

**Evaluation**
- [ ] ✅ Confirmed strength
- [ ] 💡 Improvement potential identified
- [ ] 🚫 Not applicable
- [ ] 🤔 To be assessed
- [ ] ⌛️ Assessment in progress

**Impact level**
- [ ] Moderate
- [x] Significant
- [ ] Decisive

### 1.11 — Is it possible to change default values (number of elements displayed, quality, refresh frequency, ...) to reduce resource use ?

**Additional explanation**: Users usually don't change the default values. Setting more sober default may result in less resources used.

**Evaluation**
- [ ] ✅ Confirmed strength
- [ ] 💡 Improvement potential identified
- [ ] 🚫 Not applicable
- [ ] 🤔 To be assessed
- [ ] ⌛️ Assessment in progress

**Impact level**
- [ ] Moderate
- [x] Significant
- [ ] Decisive

### 1.12 — Is there a lot of tracking on the product ?

**Additional explanation**: Analytics and marketing tracking tools are often responsible of more than a third of the requests on websites. Limiting the number of tools and partner would result in less resources use and improve privacy.

**Evaluation**
- [ ] ✅ Confirmed strength
- [ ] 💡 Improvement potential identified
- [ ] 🚫 Not applicable
- [ ] 🤔 To be assessed
- [ ] ⌛️ Assessment in progress

**Impact level**
- [ ] Moderate
- [x] Significant
- [ ] Decisive

### 1.13 — Are the main user jouneys optimised to be smooth and efficient ?

**Additional explanation**: Having efficient user journeys with few screens reduces resources use and improves user satisfaction and productivity.

**Evaluation**
- [ ] ✅ Confirmed strength
- [ ] 💡 Improvement potential identified
- [ ] 🚫 Not applicable
- [ ] 🤔 To be assessed
- [ ] ⌛️ Assessment in progress

**Impact level**
- [ ] Moderate
- [x] Significant
- [ ] Decisive

### 1.14 — Are the main screens light and well designed ?

**Additional explanation**: The most used screens must be light in terms of displayed information and media to reduce resources use.

**Evaluation**
- [ ] ✅ Confirmed strength
- [ ] 💡 Improvement potential identified
- [ ] 🚫 Not applicable
- [ ] 🤔 To be assessed
- [ ] ⌛️ Assessment in progress

**Impact level**
- [ ] Moderate
- [x] Significant
- [ ] Decisive

### 1.15 — Is the service frequently used?

**Additional explanation**: A service that is rarely used but continuously running may represent unnecessary environmental impact.
Conversely, a service used frequently justifies its resource consumption.
Understanding usage frequency helps evaluate whether the service should remain as-is, be simplified, be partially decommissioned, or switch to on-demand execution.

**Evaluation**
- [ ] ✅ Confirmed strength
- [ ] 💡 Improvement potential identified
- [ ] 🚫 Not applicable
- [ ] 🤔 To be assessed
- [ ] ⌛️ Assessment in progress

**Impact level**
- [ ] Moderate
- [x] Significant
- [ ] Decisive

### 1.16 — Volume (number of users)

**Additional explanation**: Knowing the number of active users helps contextualise the environmental impact and determine whether the service’s scale matches its actual audience.
A large infrastructure serving a small population may indicate overprovisioning, while high usage may fully justify the allocated resources.

**Evaluation**
- [ ] ✅ Confirmed strength
- [ ] 💡 Improvement potential identified
- [ ] 🚫 Not applicable
- [ ] 🤔 To be assessed
- [ ] ⌛️ Assessment in progress

**Impact level**
- [ ] Moderate
- [x] Significant
- [ ] Decisive


-----

## 🗺️ 2 — Architecture

*Spot the best optimisation opportunities.*

### 2.1 — Does the product uses greedy technologies ?

**Additional explanation**: If the products uses heavy technologes like generative IA or blockchain, it may be possible to replace it or use more efficient implementations

**Evaluation**
- [ ] ✅ Confirmed strength
- [ ] 💡 Improvement potential identified
- [ ] 🚫 Not applicable
- [ ] 🤔 To be assessed
- [ ] ⌛️ Assessment in progress

**Impact level**
- [ ] Moderate
- [x] Significant
- [ ] Decisive

### 2.2 — There is no compatibility strategy

**Additional explanation**: The service should be compatible with all devices it's users may have to avoid pushing theses devices to obsolescence.

**Evaluation**
- [ ] ✅ Confirmed strength
- [ ] 💡 Improvement potential identified
- [ ] 🚫 Not applicable
- [ ] 🤔 To be assessed
- [ ] ⌛️ Assessment in progress

**Impact level**
- [ ] Moderate
- [ ] Significant
- [x] Decisive

### 2.3 — Is it possible to optimise the components separation and communication ?

**Additional explanation**: The architecture choices may allow an efficient scaling strategy that reduces ressources use, but also lead to some overhead if the components separation et coupling is not well optimised.

**Evaluation**
- [ ] ✅ Confirmed strength
- [ ] 💡 Improvement potential identified
- [ ] 🚫 Not applicable
- [ ] 🤔 To be assessed
- [ ] ⌛️ Assessment in progress

**Impact level**
- [ ] Moderate
- [x] Significant
- [ ] Decisive

### 2.4 — Can the peak load be smoothed over a time scale ?

**Additional explanation**: Moving tasks in time using batching or message brokers allow to smooth the load and have a lighter infrastructure, since the peak load is lower.

**Evaluation**
- [ ] ✅ Confirmed strength
- [ ] 💡 Improvement potential identified
- [ ] 🚫 Not applicable
- [ ] 🤔 To be assessed
- [ ] ⌛️ Assessment in progress

**Impact level**
- [ ] Moderate
- [x] Significant
- [ ] Decisive

### 2.5 — Is there heavy computations or requests which results can be cached ?

**Additional explanation**: If within the system some heavy computations and requests returns the same results several times, it may be possible to cache them. This will save resources and improve performance.

**Evaluation**
- [ ] ✅ Confirmed strength
- [ ] 💡 Improvement potential identified
- [ ] 🚫 Not applicable
- [ ] 🤔 To be assessed
- [ ] ⌛️ Assessment in progress

**Impact level**
- [ ] Moderate
- [x] Significant
- [ ] Decisive


-----

## 🏢 3 — Infrastructure

*Spot the best optimisation opportunities.*

### 3.1 — Can the invoice be reduced ?

**Additional explanation**: Deploying a FinOps/GreenOps strategy will allow the product to use less resources.
Almost all FinOps practices (localise underused components, use spot instances, adjust components sizes, use managed services, …) allow the reduction of resources use and consequently of environnemental impacts. A strategy aiming a reduction of environnemental impacts is called GreenOps.

**Evaluation**
- [ ] ✅ Confirmed strength
- [ ] 💡 Improvement potential identified
- [ ] 🚫 Not applicable
- [ ] 🤔 To be assessed
- [ ] ⌛️ Assessment in progress

**Impact level**
- [ ] Moderate
- [x] Significant
- [ ] Decisive

### 3.2 — There is no environnement impact tracking in place.

**Additional explanation**: Monitoring Carbon Emission and the Carbon Intensity? Do you know the PUE,WUE of your datacenter? Are you considering moving to greener locations?

**Evaluation**
- [ ] ✅ Confirmed strength
- [ ] 💡 Improvement potential identified
- [ ] 🚫 Not applicable
- [ ] 🤔 To be assessed
- [ ] ⌛️ Assessment in progress

**Impact level**
- [ ] Moderate
- [x] Significant
- [ ] Decisive

### 3.3 — Is the service hosted in a region where the electricity mix has a high impact ?

**Additional explanation**: The local electrity mix mix very important : choosing the right region has a drastic effect on the impacts of the usage of the service.

**Evaluation**
- [ ] ✅ Confirmed strength
- [ ] 💡 Improvement potential identified
- [ ] 🚫 Not applicable
- [ ] 🤔 To be assessed
- [ ] ⌛️ Assessment in progress

**Impact level**
- [ ] Moderate
- [x] Significant
- [ ] Decisive

### 3.4 — Can the infrastructure be mutualized ?

**Additional explanation**: Using mutualized hosting (though VM, containers, managed services, *aaS) allow the reduction of resource use since it's shared with other products.

**Evaluation**
- [ ] ✅ Confirmed strength
- [ ] 💡 Improvement potential identified
- [ ] 🚫 Not applicable
- [ ] 🤔 To be assessed
- [ ] ⌛️ Assessment in progress

**Impact level**
- [ ] Moderate
- [x] Significant
- [ ] Decisive

### 3.5 — Are the deployment components (VM, server, containers) oversized ?

**Additional explanation**: Use observability tools/methodologies to check the VM/servers load (CPU/RAM). It should be at least 70%.

**Evaluation**
- [ ] ✅ Confirmed strength
- [ ] 💡 Improvement potential identified
- [ ] 🚫 Not applicable
- [ ] 🤔 To be assessed
- [ ] ⌛️ Assessment in progress

**Impact level**
- [ ] Moderate
- [x] Significant
- [ ] Decisive

### 3.6 — Can elasticity/scalability tools and strategies be deployed to reduce the infrastructure size ?

**Additional explanation**: With tools like cron jobs, orchestrators, containers, or functions as a service, it is possible to adjust the number of components deployed. 
So if the load is low, the number of components is low.

**Evaluation**
- [ ] ✅ Confirmed strength
- [ ] 💡 Improvement potential identified
- [ ] 🚫 Not applicable
- [ ] 🤔 To be assessed
- [ ] ⌛️ Assessment in progress

**Impact level**
- [ ] Moderate
- [x] Significant
- [ ] Decisive

### 3.7 — Are all the environnements always on ?

**Additional explanation**: Environnements that are not used (for instance non produciton ones at night or weekends) can be swicthed off.

**Evaluation**
- [ ] ✅ Confirmed strength
- [ ] 💡 Improvement potential identified
- [ ] 🚫 Not applicable
- [ ] 🤔 To be assessed
- [ ] ⌛️ Assessment in progress

**Impact level**
- [ ] Moderate
- [x] Significant
- [ ] Decisive

### 3.8 — Are the test environnements as big as the production ones ?

**Additional explanation**: It's usually not necessary to have as many components (VM, containers) in tests environnements, except for load testing.

**Evaluation**
- [ ] ✅ Confirmed strength
- [ ] 💡 Improvement potential identified
- [ ] 🚫 Not applicable
- [ ] 🤔 To be assessed
- [ ] ⌛️ Assessment in progress

**Impact level**
- [ ] Moderate
- [x] Significant
- [ ] Decisive


-----

## 💾 4 — Storage and data

*Spot the best optimisation opportunities.*

### 4.1 — Are deletion and archiving mechanisms implemented?

**Additional explanation**: Without automated deletion or archiving, data accumulates unnecessarily and increases storage usage. Retention rules and archiving policies limit data growth and reduce environmental impact.

**Evaluation**
- [ ] ✅ Confirmed strength
- [ ] 💡 Improvement potential identified
- [ ] 🚫 Not applicable
- [ ] 🤔 To be assessed
- [ ] ⌛️ Assessment in progress

**Impact level**
- [ ] Moderate
- [x] Significant
- [ ] Decisive

### 4.2 — Are the best practices for database in place ?

**Additional explanation**: An unoptimised database requires more CPU, memory or I/O to deliver the same level of service, which increases energy consumption. Proper indexing, good data modelling and regular maintenance help reduce unnecessary resource usage.

**Evaluation**
- [ ] ✅ Confirmed strength
- [ ] 💡 Improvement potential identified
- [ ] 🚫 Not applicable
- [ ] 🤔 To be assessed
- [ ] ⌛️ Assessment in progress

**Impact level**
- [ ] Moderate
- [x] Significant
- [ ] Decisive

### 4.3 — Does the product use the right database/storage technologies for the right usages ?

**Additional explanation**: If the product storage needs are large, it may be beneficial to specialize the storage technologies : 
- PG/MYSQL/Oracle/SQLServer or object relation
- MongoDB for document oriented.
- Columnar db for analytics.
- Specialized database (vector, times series).

**Evaluation**
- [ ] ✅ Confirmed strength
- [ ] 💡 Improvement potential identified
- [ ] 🚫 Not applicable
- [ ] 🤔 To be assessed
- [ ] ⌛️ Assessment in progress

**Impact level**
- [ ] Moderate
- [x] Significant
- [ ] Decisive

### 4.4 — Are the tests databases as big as the production ones ?

**Additional explanation**: Usually it's not necessary to have as much data in tests environnements than in production.

**Evaluation**
- [ ] ✅ Confirmed strength
- [ ] 💡 Improvement potential identified
- [ ] 🚫 Not applicable
- [ ] 🤔 To be assessed
- [ ] ⌛️ Assessment in progress

**Impact level**
- [ ] Moderate
- [x] Significant
- [ ] Decisive

### 4.5 — Is there data duplications ?

**Additional explanation**: If data is duplicated and this is not part of product strategy as High Availability, this usually indicates an optimisation opportunity, except when the duplication results from intentional performance-driven denormalisation.

**Evaluation**
- [ ] ✅ Confirmed strength
- [ ] 💡 Improvement potential identified
- [ ] 🚫 Not applicable
- [ ] 🤔 To be assessed
- [ ] ⌛️ Assessment in progress

**Impact level**
- [x] Moderate
- [ ] Significant
- [ ] Decisive

### 4.6 — Is there data that is very seldom used in the service, and that could be moved to cold storage?

**Additional explanation**: Data that is rarely accessed can be moved to a more energy-efficient but slower storage tier (“cold storage”).
For example, transactions older than three months in a banking service can be removed from the main database and archived.
The user can still retrieve them, but through a slower process, which is acceptable given their infrequent use.
For example: SSD got a 2x to 3x higher embodied carbon impact.

**Evaluation**
- [ ] ✅ Confirmed strength
- [ ] 💡 Improvement potential identified
- [ ] 🚫 Not applicable
- [ ] 🤔 To be assessed
- [ ] ⌛️ Assessment in progress

**Impact level**
- [x] Moderate
- [ ] Significant
- [ ] Decisive


-----

## 👨‍💻 5 — Algorithms & code

*Spot the best optimisation opportunities.*

### 5.1 — Is there statical analysis tools in place, revealing potential efficiency improvements  ?

**Additional explanation**: Static analysis helps identify performance and efficiency issues.
Static analysis also helps improve quality, making product modification easier.

**Evaluation**
- [ ] ✅ Confirmed strength
- [ ] 💡 Improvement potential identified
- [ ] 🚫 Not applicable
- [ ] 🤔 To be assessed
- [ ] ⌛️ Assessment in progress

**Impact level**
- [x] Moderate
- [ ] Significant
- [ ] Decisive

### 5.2 — Has a campaign of load or stress tests revealed efficiency problems ?

**Additional explanation**: If a load or stress test campaign has revealed efficiency problems, it may be possible to improve the product.

**Evaluation**
- [ ] ✅ Confirmed strength
- [ ] 💡 Improvement potential identified
- [ ] 🚫 Not applicable
- [ ] 🤔 To be assessed
- [ ] ⌛️ Assessment in progress

**Impact level**
- [ ] Moderate
- [x] Significant
- [ ] Decisive

### 5.3 — Have any areas for improvement in terms of performance/efficiency been identified by the team and put in the backlog?

**Additional explanation**: Improvement is identified if the team has indentified efficicency improvements.

**Evaluation**
- [ ] ✅ Confirmed strength
- [ ] 💡 Improvement potential identified
- [ ] 🚫 Not applicable
- [ ] 🤔 To be assessed
- [ ] ⌛️ Assessment in progress

**Impact level**
- [ ] Moderate
- [x] Significant
- [ ] Decisive

### 5.4 — Are the performance metrics poor ?

**Additional explanation**: Poor performance implies an optimisation potential. Performance metrics include latency, requests per seconds, [Core Web Vitals](https://developers.google.com/search/docs/appearance/core-web-vitals?hl=fr), etc.

**Evaluation**
- [ ] ✅ Confirmed strength
- [ ] 💡 Improvement potential identified
- [ ] 🚫 Not applicable
- [ ] 🤔 To be assessed
- [ ] ⌛️ Assessment in progress

**Impact level**
- [x] Moderate
- [ ] Significant
- [ ] Decisive

### 5.5 — Are the most critical use cases (most used user journeys) optimized ?

**Additional explanation**: The most used user journeys are critical to the overall resources used by the application. Applying optimisations on these code path will likely result in good results.

**Evaluation**
- [ ] ✅ Confirmed strength
- [ ] 💡 Improvement potential identified
- [ ] 🚫 Not applicable
- [ ] 🤔 To be assessed
- [ ] ⌛️ Assessment in progress

**Impact level**
- [ ] Moderate
- [x] Significant
- [ ] Decisive

### 5.6 — Is the technical stack (Java, JS, python, php, ...) not up to date ?

**Additional explanation**: Updating the tools (like the Java Virtual Machine) allow almost free performance and efficiency improvements.

**Evaluation**
- [ ] ✅ Confirmed strength
- [ ] 💡 Improvement potential identified
- [ ] 🚫 Not applicable
- [ ] 🤔 To be assessed
- [ ] ⌛️ Assessment in progress

**Impact level**
- [ ] Moderate
- [x] Significant
- [ ] Decisive

### 5.7 — Can the components be tuned to improve efficiency ?

**Additional explanation**: Tuning components (like the  Java Virtual Machine) allow performance an efficiency improvements

**Evaluation**
- [ ] ✅ Confirmed strength
- [ ] 💡 Improvement potential identified
- [ ] 🚫 Not applicable
- [ ] 🤔 To be assessed
- [ ] ⌛️ Assessment in progress

**Impact level**
- [x] Moderate
- [ ] Significant
- [ ] Decisive

### 5.8 — Are the dependencies of the project up to date ?

**Additional explanation**: Updating the project dependencies (like the the Spring Framwork in java) may allow performance and efficiency improvements.

**Evaluation**
- [ ] ✅ Confirmed strength
- [ ] 💡 Improvement potential identified
- [ ] 🚫 Not applicable
- [ ] 🤔 To be assessed
- [ ] ⌛️ Assessment in progress

**Impact level**
- [ ] Moderate
- [ ] Significant
- [x] Decisive

### 5.9 — Is there compatibility problems identified for targeted devices ?

**Additional explanation**: The service should be compatible with all devices it's users may have to avoid pushing theses devices to obsolescence.

**Evaluation**
- [ ] ✅ Confirmed strength
- [ ] 💡 Improvement potential identified
- [ ] 🚫 Not applicable
- [ ] 🤔 To be assessed
- [ ] ⌛️ Assessment in progress

**Impact level**
- [ ] Moderate
- [ ] Significant
- [x] Decisive


-----

## 🕸️ 7 — Synthesis

This framework counts **54 detailed criteria** in total, spread over the 6 dimensions below (excluding the Quick diagnostic, which covers them in condensed form but is not part of this synthesis).

| Category | Number of criteria | Link |
|---|---|---|
| 🛖 Product | 16 | [See the section](#product) |
| 🗺️ Architecture | 5 | [See the section](#architecture) |
| 🏢 Infrastructure | 8 | [See the section](#infrastructure) |
| 💾 Storage & Data | 6 | [See the section](#storage--data) |
| 👨‍💻 Algo & Code | 9 | [See the section](#algo--code) |
| 🛠 Ease of change | 10 | [See the section](#ease-of-change) |

**Note on the source Sheet's total.** The Google Sheets formula that counts the total number of criteria references tabs that no longer exist (`#REF!` + old tab names) — its displayed value is frozen and wrong. The total above (54) is recomputed directly from the current data, one by one.

**Radar.** The source Sheet displays a 6-axis radar which, on inspection, only draws 5 of them: the *Ease of change* category is missing from the chart (bug observed, not a deliberate exclusion). As long as this template is blank, no real radar makes sense here; a rendering example (fictitious optimization potentials, 6 axes) is available via `.claude/skills/eof/scripts/generate_radar_svg.py`.

### How to read this framework

- **Dimensions 1 to 5 (Product, Architecture, Infrastructure, Storage, Algo & Code)**: each criterion is answered by a single choice among 5 (`✅ Confirmed strength`, `💡 Improvement potential identified`, `🚫 Not applicable`, `🤔 To be assessed`, `⌛️ Assessment in progress`), by checking the corresponding box. Coefficient observed on the source Sheet: `✅`/`🚫`/`🤔`/empty = 0, `💡` = 1, `⌛️` = 0.5 (this last value was observed only once in the whole workbook at generation time, to be confirmed if it occurs elsewhere, it is not yet a certain rule).
- **Dimension 6 (Ease of change)**: a **different** dropdown from the 5 other dimensions (confirmed by the source Sheet's "Read me" tab): `🟢 Easy to change`, `🟡 Moderate effort`, `🔴 Hard to change`. No real answer existed on this tab at generation time, so the numeric mapping (0 / 0.5 / 1 used here) is an assumption by analogy with the other dimensions, **not verified** on real data.
- **Optimization potential of a dimension** = `Σ (coefficient of the answer × potential maximum of the criterion)` ÷ `Σ (potential maximum of ALL the criteria of the dimension, answered or not)`. **An unanswered criterion counts 0 in the numerator but its maximum stays in the denameinator**, so it never penalizes the optimization potential, and a blank dimension shows 0% optimization potential, not "unknown". This is a methodological bias of the source Sheet, not a correction made here.
- **"Not applicable" potential maximum**: the "Read me" tab says a criterion can be excluded entirely by setting its potential maximum to "Not applicable" (not just answering "Not applicable" to the evaluation, which still counts the maximum in the denameinator). No real example of this setting was observed in the fetched data; the mechanism is documented here as described by the Sheet, not verified on a concrete case.
- **Tab 0 (Quick diagnostic)**: different logic, a 1-to-5 scale per criterion (`(5 − answer) ÷ 4 × potential maximum`), does not contribute to this synthesis table.
- **Potential maximum**: each criterion carries its own potential maximum (visible in the source Sheet, corresponding column), different from one criterion to another, it is never 1 everywhere.
