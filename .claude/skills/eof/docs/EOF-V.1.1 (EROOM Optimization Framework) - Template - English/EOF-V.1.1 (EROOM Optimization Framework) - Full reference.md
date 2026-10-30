# EOF-V.1.1 (EROOM Optimization Framework) — Full reference

> Generated from the source Google Sheet: https://docs.google.com/spreadsheets/d/1zJkT_5Ck9WKyxHZ7Uf5f03PmsaLh_SUB7LzKToPlcZ0/edit
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

### 🎯 Objective of the EROOM optimization framework

This diagnostic assesses the maturity of a digital service in order to identify its main optimization levers: algorithm, code, architecture, operations, data, hosting, etc.

Each question covers a factor influencing performance, efficiency, or maintainability.

The diagnostic is not a performance grade: it helps determine action priorities. There are no "good" or "bad" grades, only improvement opportunities.

### 📊 Rating scale

For each criterion, give a score from 1 to 5 based on the current level of mastery.

1 = not mastered / unknown

5 = mastered and measured

Each question contributes equally to the overall score, which is then converted into a percentage of optimization potential (0% to 100%).

This percentage reflects the remaining room for improvement for the service.

A low individual score highlights an improvement opportunity, while a high score indicates that good practices are already in place.

### 🧮 Interpreting the scores

The total score is expressed as a percentage of the optimization potential.

• High percentage → strong improvement potential (technical, organizational, or environmental).

• Low percentage → service already mature or efficient.

The diagnostic does not assign a performance grade.

It is designed to prioritize actions and identify the areas where improvement efforts will have the most impact.

There are no "good" or "bad" results, only opportunities to act.

### 💡 Who is it for?

The EROOM quick diagnostic is designed to be lightweight and accessible, but it requires a basic understanding of the technical context.

This can be done by:

• someone familiar with the technical environment, able to assess the maturity of current practices;

• a technical-product pair, to cross-check viewpoints and ensure alignment between technical and functional priorities;

• a technical-product pair, to cross-check viewpoints and ensure alignment between technical and functional priorities;

### 💡 How to use

One diagnostic corresponds to a single digital service.

An organization can therefore run several quick diagnostics to map its entire information system and identify the areas where action should be taken as a priority.

Step 1 - Duplicate the file

This tool is provided as a Google Sheets spreadsheet.

Start by duplicating the file for your personal use, so you can enter your answers without modifying the original template.

Step 2 - Define the scope

The diagnostic is performed for a digital service, a platform, or the entire information system.

Each assessed service must have its own dedicated sheet.

Step 4 - Answer the questions - 0 - Quick diagnostic

Give each question a score from 1 to 5, based on the available information.

1 = not mastered / unknown

5 = mastered, measured, optimised

If in doubt, select 1 ("I don't know") or choose a cautious score, and note the point to clarify later.

You can ignore any criterion by setting its weight to "Not applicable".

If the quick diagnostic score is very low, there is no need to continue with the detailed steps. The optimization potential is either already low or too hard to reach, so it is more effective to focus on other services.

Step 5 - Answer the questions - 1 - Product to - 5 - Algo&Code

✅ Confirmed strength = already handled, no improvement potential possible.

💡 Improvement potential identified = not fully exploited, significant room for improvement remains.

You can ignore any criterion by setting its weight to "Not applicable".

Step 6 - Answer the questions - 6 - Ease of change

🟢 Easy to change = can be updated with minimal obstacles.

🟡 Moderate effort = making the change would be a feasible challenge.

🔴 Hard to change = implementing the change would be difficult.

You can ignore any criterion by setting its weight to "Not applicable".

Step 7 - Collaborate across the different roles

Carry out the diagnostic with technical, product, and corporate social responsibility (CSR) representatives, in order to reach a shared understanding — not to grade the teams.

The goal is to reach a shared understanding, not to assign a performance grade.

Low score → mature, already efficient service.

High score → strong optimization potential (technical, organizational, or environmental).

Step 7 - Use the results

Compare the results across the different services.

Those with the best scores become the priority candidates for a more in-depth analysis within the EROOM program.

Licence CC-BY-SA

« Cette licence permet aux réutilisateurs de distribuer, remixer, adapter et développer le contenu sur tout support ou format, à condition que le créateur soit mentionné.

La licence autorise l'utilisation commerciale. Si vous remixez, adaptez ou développez le contenu, vous devez accorder une licence au contenu modifié selon des conditions identiques. »


-----

## 🏦 0 — Quick diagnostic

*Identify the best optimization opportunities. A higher score reflects greater optimization potential.*

### 0.1 — Would the disappearance of the digital service have a significant impact?

**Evaluation**
- [ ] 1 - No or negligible impact
- [ ] 2 - Limited impact on a small group of users or processes
- [ ] 3 - Moderate impact, but workarounds exist
- [ ] 4 - Significant impact on core activities
- [ ] 5 - Critical impact (operations blocked, major risk to the company or IT infrastructure)

**Impact level**
- [ ] Moderate
- [ ] Significant
- [x] Decisive

### 0.2 — Are there redundant features or duplicate applications in the system?

**Evaluation**
- [ ] 1 - Something very similar already exists elsewhere (same feature or same code).
- [ ] 2 - Something already exists elsewhere.
- [ ] 3 - There are minor similarities, but nothing major.
- [ ] 4 - Almost no similarity with other products or codebases.
- [ ] 5 - Totally unique; nothing similar exists.

**Impact level**
- [ ] Moderate
- [ ] Significant
- [x] Decisive

### 0.3 — Are the main components subject to high-availability constraints?

**Evaluation**
- [ ] 1 - 7 days a week, 24 hours a day - 99.99% - International coverage
- [ ] 2 - 7 days a week, 24 hours a day - 99%
- [ ] 3 - Some [SLA](https://fr.wikipedia.org/wiki/Service-level_agreement)s.
- [ ] 4 - 5 days a week, 8 hours a day - No SLA - No Disaster Recovery Plan (DRP)
- [ ] 5 - No SLA/SLO

**Impact level**
- [ ] Moderate
- [ ] Significant
- [x] Decisive

### 0.4 — Dependencies: how many technical links to other systems are in place?

**Evaluation**
- [ ] 1 - The product is not connected to any other system
- [ ] 2 - The product is connected to a few other systems
- [ ] 3 - The product is connected to some other systems and the connection matters (business value and/or technical coupling)
- [ ] 4 - The product is connected to many other systems
- [ ] 5 - The product is connected to most other IS systems (e.g. authentication and authorization)

**Impact level**
- [ ] Moderate
- [ ] Significant
- [x] Decisive

### 0.5 — Is the project's source code fully or partially accessible to the team?

**Evaluation**
- [ ] 1 - The source code is fully available (open source or fully accessible to the organization).
- [ ] 2 - The source code is mostly available (accessible internally, but not publicly).
- [ ] 3 - The source code is partially available (some components or modules are accessible).
- [ ] 4 - Access is limited to a very small group or to the vendor only.
- [ ] 5 - No, the source code is not available / I don't know.

**Impact level**
- [ ] Moderate
- [ ] Significant
- [x] Decisive

### 0.6 — Are the skills needed to update the service available?

**Evaluation**
- [ ] 1 - The team has a solid command of the functional and technical design of the project and can work with full confidence.
- [ ] 2 - The team knows most of the project and can work on it with caution.
- [ ] 3 - Knowledge of the project is insufficient.
- [ ] 4 - Some people have partial knowledge of the project.
- [ ] 5 - No one knows the project.

**Impact level**
- [ ] Moderate
- [ ] Significant
- [x] Decisive

### 0.7 — Is the architecture highly complex?

**Evaluation**
- [ ] 1 - Very complex / I don't know
- [ ] 2 - Complex
- [ ] 3 - Medium
- [ ] 4 - Simple
- [ ] 5 - Very simple

**Impact level**
- [ ] Moderate
- [ ] Significant
- [x] Decisive

### 0.8 — Is the infrastructure (number and size of components such as virtual machines and containers) very large?

**Evaluation**
- [ ] 1 - One of the organization's largest infrastructures
- [ ] 2 - Larger than most services
- [ ] 3 - Comparable to the organization's average
- [ ] 4 - Smaller than most services
- [ ] 5 - Very small (e.g. a few VMs or containers)

**Impact level**
- [ ] Moderate
- [ ] Significant
- [x] Decisive

### 0.9 — Is a large volume of data stored?

**Evaluation**
- [ ] 1 - The product has one of the largest data storage volumes in the IS / I don't know.
- [ ] 2 - The product stores a large amount of data in the IS compared to most systems.
- [ ] 3 - The product stores an average amount of data compared to the rest of the IS.
- [ ] 4 - The product stores a limited amount of data.
- [ ] 5 - The product stores very little data.

**Impact level**
- [ ] Moderate
- [ ] Significant
- [x] Decisive

### 0.10 — Is the functional complexity high?

**Evaluation**
- [ ] 1 - Very complex / I don't know
- [ ] 2 - Complex
- [ ] 3 - Medium
- [ ] 4 - Simple
- [ ] 5 - Easy

**Impact level**
- [ ] Moderate
- [ ] Significant
- [x] Decisive

### 0.11 — "Are user journeys smooth, intuitive, and free of UX/UI friction that could be improved?"

**Evaluation**
- [ ] 1 - The UX/UI is very poor, users complain and/or there are pending items to fix it / I don't know
- [ ] 2 - The UX/UI has recurring friction points or usability issues
- [ ] 3 - The UX/UI is functional, but some aspects could be improved
- [ ] 4 - The UX/UI is clear and pleasant to use; only minor improvements were identified
- [ ] 5 - The UX/UI is well designed, user-tested, and offers a smooth, consistent experience

**Impact level**
- [ ] Moderate
- [ ] Significant
- [x] Decisive

### 0.12 — Is the product compatible with the oldest hardware in the target fleet, and does it offer a smooth experience on it?

**Evaluation**
- [ ] 1 - Incompatible or unknown
- [ ] 2 - Compatible but with significant degradation (irritating or frustrating for the user)
- [ ] 3 - Compatible and usable but not comfortable (noticeable slowdown)
- [ ] 4 - Compatible and generally smooth (minor slowdowns)
- [ ] 5 - Compatible and smooth (comfortable and responsive even on old hardware)

**Impact level**
- [ ] Moderate
- [ ] Significant
- [x] Decisive

### 0.13 — Does the product backlog contain performance problems and improvements?

**Evaluation**
- [ ] 1 - In the backlog and a recurring topic
- [ ] 3 - Some improvements are possible
- [ ] 5 - No performance issue identified

**Impact level**
- [ ] Moderate
- [ ] Significant
- [x] Decisive

### 0.14 — Are the main features optimized and efficient?

**Evaluation**
- [ ] 1 - Not optimized enough / don't know
- [ ] 2 - Some core features are ineffective or redundant
- [ ] 3 - Core features work but could be optimized
- [ ] 4 - Most core features are well implemented and work efficiently
- [ ] 5 - All core features are fully effective, streamlined, and regularly reviewed for optimization

**Impact level**
- [ ] Moderate
- [ ] Significant
- [x] Decisive

### 0.15 — Is there a policy on data deletion and archiving?

**Evaluation**
- [ ] 1 - No policy / don't know
- [ ] 2 - Informal or ad-hoc deletion and archiving practices
- [ ] 3 - A policy exists but is not applied consistently
- [ ] 4 - A clear, partially automated policy is in place
- [ ] 5 - A strict, enforced, regularly audited data deletion and archiving policy

**Impact level**
- [ ] Moderate
- [ ] Significant
- [x] Decisive

### 0.16 — Is the service hosted in a country whose electricity mix has a significant impact? (depending on location)

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

*Identify the best optimization opportunities.*

### 6.1 — Is there an effective observability setup for the product?

**Additional explanation**: Without a minimum of knowledge about the product's runtime behavior, it is difficult to identify possible optimizations. Lack of monitoring implies low optimization potential.

**Evaluation**
- [ ] 🟢 Easy to change
- [ ] 🟡 Moderate effort
- [ ] 🔴 Hard to change

**Impact level**
- [ ] Moderate
- [ ] Significant
- [x] Decisive

### 6.2 — Are there code reviews and/or pair programming?

**Additional explanation**: Code reviews and pair programming guarantee a minimum level of shared knowledge about the codebase and a minimum quality.

**Evaluation**
- [ ] 🟢 Easy to change
- [ ] 🟡 Moderate effort
- [ ] 🔴 Hard to change

**Impact level**
- [ ] Moderate
- [x] Significant
- [ ] Decisive

### 6.3 — Is there an effective [CI/CD](https://fr.wikipedia.org/wiki/CI/CD) process?

**Additional explanation**: Having a CI/CD is a good indicator of how easily the team will be able to work on the application with confidence.

**Evaluation**
- [ ] 🟢 Easy to change
- [ ] 🟡 Moderate effort
- [ ] 🔴 Hard to change

**Impact level**
- [ ] Moderate
- [x] Significant
- [ ] Decisive

### 6.4 — Are there non-regression tests (unit tests, integration tests, end-to-end tests)?

**Additional explanation**: Having non-regression tests lets developers change the software while being assured that their work causes no problems.

**Evaluation**
- [ ] 🟢 Easy to change
- [ ] 🟡 Moderate effort
- [ ] 🔴 Hard to change

**Impact level**
- [ ] Moderate
- [ ] Significant
- [x] Decisive

### 6.5 — Is there strong decoupling between the business domain and the technical integration?

**Additional explanation**: Decoupling practices such as dependency injection or hexagonal/clean/onion architecture enable more effective and ambitious technical changes.
This is the "D" (dependency inversion) of the 5 fundamental SOLID principles.

**Evaluation**
- [ ] 🟢 Easy to change
- [ ] 🟡 Moderate effort
- [ ] 🔴 Hard to change

**Impact level**
- [ ] Moderate
- [x] Significant
- [ ] Decisive

### 6.6 — Are there indicators for tracking software quality?

**Additional explanation**: Such as code coverage, cyclomatic complexity, number of issues, number of deployment issues, number of rollbacks, lead time for changes, deployment frequency, change failure rate, recovery time after a failed deployment.

**Evaluation**
- [ ] 🟢 Easy to change
- [ ] 🟡 Moderate effort
- [ ] 🔴 Hard to change

**Impact level**
- [ ] Moderate
- [ ] Significant
- [x] Decisive

### 6.7 — Is there comprehensive documentation?

**Additional explanation**: Relevant documentation makes more ambitious changes possible.

**Evaluation**
- [ ] 🟢 Easy to change
- [ ] 🟡 Moderate effort
- [ ] 🔴 Hard to change

**Impact level**
- [ ] Moderate
- [x] Significant
- [ ] Decisive

### 6.8 — Is there duplicated code in the application?

**Additional explanation**: Duplicated code can be removed to simplify product maintenance.

**Evaluation**
- [ ] 🟢 Easy to change
- [ ] 🟡 Moderate effort
- [ ] 🔴 Hard to change

**Impact level**
- [x] Moderate
- [ ] Significant
- [ ] Decisive

### 6.9 — Does the team have enough autonamey to deploy the tools it needs to observe, measure, or optimize the system?

**Additional explanation**: Ease of change increases when teams can rely on the tools they need to monitor performance, measure impact, or analyze behavior.
This autonamey can come from being able to install custom tools, or from relying on comprehensive built-in tools provided by the platform.
What matters is not where the infrastructure is hosted, but the team's ability to use it effectively to support optimization.

**Evaluation**
- [ ] 🟢 Easy to change
- [ ] 🟡 Moderate effort
- [ ] 🔴 Hard to change

**Impact level**
- [x] Moderate
- [ ] Significant
- [ ] Decisive

### 6.10 — Are the main components subject to high-availability constraints?

**Additional explanation**: High-availability requirements can reduce the team's ability to modify, migrate, or optimize components.
Services that must maintain strict availability leave fewer opportunities for maintenance windows, architectural changes, or resource optimization.
Understanding these constraints helps assess how easily the system can evolve toward a lower environmental impact.

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

*Identify the best optimization opportunities.*

### 1.1 — Is there a simple way to perform this action?

**Additional explanation**: If there is already a way to do it, does the digital approach bring added value to the user?

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

### 1.2 — Are the target users — with their business needs, typical devices, and ergonameics expectations — well known?

**Additional explanation**: The product risks being poorly designed if the target users are not well known, or better still, involved in the project. For example, user journeys could be cumbersome or the compatibility strategy inadequate.

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

### 1.3 — Are updates of new features mandatory on all devices, regardless of operating system or browser?

**Additional explanation**: New features weigh down the application. On older devices, users may prefer to keep a simpler, more performant, less resource-hungry product.

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

### 1.4 — Does the design include custom components rather than native ones?

**Additional explanation**: System components (buttons, menus, forms, etc.) are almost always more efficient than custom-built ones — not to mention their accessibility and compatibility.

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

### 1.5 — Are there animations, videos, sounds, maps (...) that play automatically?

**Additional explanation**: Playing this kind of content without any user action is disruptive and uses resources such as bandwidth and the graphics processor.

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

### 1.6 — Can the resources used by the application be adapted to the user's hardware configuration?

**Additional explanation**: Not everyone has a device capable of running resource-intensive content (such as multimedia, etc.).
What happens when a user tries to run resource-intensive content on an unsuitable device? Ideally, the service should not block access and should run the basic functions.

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

### 1.7 — Are all features useful, usable, and used?

**Additional explanation**: Simplifying the product by removing unused features will reduce resource consumption.

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

### 1.8 — Is application support poor on the oldest targeted devices?

**Additional explanation**: Most of the impact of digital services is felt on client devices. It is very important not to push these devices into obsolescence by breaking their compatibility.

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

### 1.9 — Does using the application require a high-speed network?

**Additional explanation**: High bandwidth implies significant resource use. This indicates that optimizations are possible to reduce the number and/or size of requests.

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

### 1.10 — Does the product use manipulative designs (UX dark patterns) that increase resource use?

**Additional explanation**: Bad user-experience practices include infinite scrolling, pre-checked subscriptions, difficulty unsubscribing, etc.

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

### 1.11 — Can the default values (number of items displayed, quality, refresh rate, etc.) be changed to reduce resource use?

**Additional explanation**: Users generally do not change default values. Setting more frugal defaults can reduce resource consumption.

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

### 1.12 — Are there many trackers on the product?

**Additional explanation**: Marketing analytics and tracking tools are often responsible for more than a third of requests on websites. Limiting the number of tools and partners would reduce resource use and improve privacy.

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

### 1.13 — Are the main user journeys optimized to be smooth and efficient?

**Additional explanation**: Efficient user journeys with few screens reduce resource use and improve user satisfaction and productivity.

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

### 1.14 — Are the main screens clear and well designed?

**Additional explanation**: The most-used screens must be light in terms of displayed information and media, in order to reduce resource use.

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

### 1.15 — Is this service used frequently?

**Additional explanation**: A rarely used service that runs continuously can have an unnecessary environmental impact.
Conversely, a frequently used service justifies its resource consumption.
Understanding usage frequency helps assess whether the service should stay as is, be simplified, be partially decommissioned, or move to on-demand execution.

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

**Additional explanation**: Knowing the number of active users helps put the environmental impact into context and determine whether the scale of the service matches its actual audience.
A large infrastructure serving a small population may indicate over-provisioning, while high usage can fully justify the allocated resources.

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

*Identify the best optimization opportunities.*

### 2.1 — Does the product use resource-hungry technologies?

**Additional explanation**: If the product uses heavyweight technologies such as generative AI or blockchain, it may be possible to replace them or use more efficient implementations.

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

### 2.2 — There is no compatibility strategy.

**Additional explanation**: The service must be compatible with all the devices users have, to avoid making those devices obsolete.

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

### 2.3 — Can the separation and communication between components be optimized?

**Additional explanation**: Architectural choices can enable an efficient scaling strategy that reduces resource use, but can also add overhead if component separation and coupling are not well optimized.

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

### 2.4 — Can the load peak be smoothed over a period of time?

**Additional explanation**: Shifting tasks over time using batch processing or message brokers smooths the load and lightens the infrastructure, because the peak load is lower.

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

### 2.5 — Are there heavy calculations or queries whose results could be cached?

**Additional explanation**: If, within the system, some heavy calculations or queries return the same results several times, they may be cacheable. This saves resources and improves performance.

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

*Identify the best optimization opportunities.*

### 3.1 — Can the bill be reduced?

**Additional explanation**: Deploying a FinOps/GreenOps strategy will let the product use fewer resources.
Almost all FinOps practices (locating underused components, using spot instances, right-sizing components, using managed services, etc.) reduce resource use and therefore environmental impact. A strategy aimed at reducing environmental impact is called GreenOps.

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

### 3.2 — There is no environmental impact monitoring system.

**Additional explanation**: Monitoring carbon emissions and carbon intensity? Do you know the PUE and WUE of your data center? Are you considering moving to greener sites?

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

### 3.3 — Is the service hosted in a region where the electricity mix has a significant impact?

**Additional explanation**: The local electricity mix matters a great deal: choosing the right region has a considerable effect on the impacts of using the service.

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

### 3.5 — Can the infrastructure be shared?

**Additional explanation**: Using shared hosting (via VMs, containers, managed services, *aaS) reduces resource use, because resources are shared with other products.

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

### 3.6 — Are the deployment components (VM, server, containers) oversized?

**Additional explanation**: Use observability tools/methodologies to check the load of virtual machines/servers (CPU/RAM). It must be at least 70%.

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

### 3.7 — Can elasticity/auto-scaling tools and strategies be deployed to reduce the size of the infrastructure?

**Additional explanation**: With tools such as cron jobs, orchestrators, containers, or functions as a service, the number of deployed components can be adjusted.
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

### 3.8 — Are all environments always switched on?

**Additional explanation**: Environments that are not used (e.g. those not in production at night or on weekends) can be switched off.

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

### 3.9 — Are test environments as big as production environments?

**Additional explanation**: It is generally not necessary to have as many components (VMs, containers) in test environments, except for load testing.

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

*Identify the best optimization opportunities.*

### 4.1 — Are deletion and archiving mechanisms in place?

**Additional explanation**: Without automated deletion or archiving, data accumulates unnecessarily and takes up more storage space. Retention rules and archiving policies limit data growth and reduce environmental impact.

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

### 4.2 — Are database best practices in place?

**Additional explanation**: An unoptimized database needs more CPU, memory, or I/O resources to deliver the same level of service, which increases energy consumption. Proper indexing, good data modeling, and regular maintenance help reduce unnecessary resource use.

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

### 4.3 — Does the product use database/storage technologies suited to the intended uses?

**Additional explanation**: If the product's storage needs are large, it may be worth specializing storage technologies:
- PG/MYSQL/Oracle/SQLServer or object-relational
- MongoDB for document-oriented use.
- Column-oriented database for analytics.
- Specialized database (vector, time series).

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

### 4.4 — Are test databases as large as production databases?

**Additional explanation**: In general, there is no need to have as much data in test environments as in production.

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

### 4.5 — Is there duplicated data?

**Additional explanation**: If data is duplicated and this is not part of the product's high-availability strategy, it generally indicates an optimization opportunity — unless the duplication results from intentional denormalization for performance reasons.

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

### 4.6 — Is there data that is very rarely used in the service and could be moved to cold storage?

**Additional explanation**: Rarely accessed data can be moved to a more energy-efficient but slower storage tier ("cold storage").
For example, transactions more than three months old in a banking service can be removed from the main database and archived.
The user can still retrieve them, but through a slower process, which is acceptable given their infrequent use.
For example: SSDs have a carbon impact 2 to 3 times higher than mechanical hard drives (HDDs) of equivalent capacity

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

*Identify the best optimization opportunities.*

### 5.1 — Are there statistical analysis tools in place to highlight potential efficiency improvements?

**Additional explanation**: Static analysis helps identify performance and efficiency issues.
It also helps improve quality and makes products easier to change.

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

### 5.2 — Has a load or stress testing campaign revealed efficiency problems?

**Additional explanation**: If a load or stress testing campaign has revealed efficiency problems, it may be possible to improve the product.

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

### 5.3 — Has the team identified areas for improvement in terms of performance/efficiency and added them to the backlog?

**Additional explanation**: An improvement is identified if the team has identified efficiency gains.

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

### 5.4 — Are the performance indicators poor?

**Additional explanation**: Poor performance implies optimization potential. Performance indicators include latency, requests per second, [Core Web Vitals](https://developers.google.com/search/docs/appearance/core-web-vitals?hl=fr) metrics, etc.

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

### 5.5 — Are the most critical use cases (most frequent user journeys) optimized?

**Additional explanation**: The most frequent user journeys account for all the resources used by the application. Applying optimizations to these code paths should yield good results.

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

### 5.6 — Is the technical stack (Java, JS, Python, PHP, etc.) out of date?

**Additional explanation**: Updating tools (such as the Java virtual machine) improves performance and efficiency at lower cost.

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

### 5.7 — Can the components be tuned to improve efficiency?

**Additional explanation**: Optimization components (such as the Java virtual machine) improve performance and efficiency.

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

### 5.8 — Are the project's dependencies up to date?

**Additional explanation**: Updating the project's dependencies (e.g. the Spring Framework in Java) can improve performance and efficiency.

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

### 5.9 — Have compatibility issues been identified for the targeted devices?

**Additional explanation**: The service must be compatible with all the devices users have, to avoid making those devices obsolete.

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
