---
name: release
description: >
  Evolves, consistently, the version number of the Agent EROOM project
  and the 3 files that must stay in sync: `.claude/skills/analyse-parcours/SKILL.md`
  (the `version:` field, source of truth, displayed in the footer of generated reports),
  `CHANGELOG.md` (history) and `README.md` (the "Current version: X" line at the top
  of the file). Activates on "/release", "bump the version", "new version",
  "cut a release", or any request to evolve the project version number.
version: 1.0.0
---

# Skill: release (Agent EROOM)

## Overview

The Agent EROOM project has a single version number, whose source of truth
is the `version:` field of the frontmatter of `.claude/skills/analyse-parcours/SKILL.md`
(read dynamically by `generate_report_html.py` for the H1 and the footer of
generated reports). Two other files must reflect the same value:

1. `CHANGELOG.md` (repo root): one entry per version, the most recent on top.
2. `README.md` (repo root): the line `**Current version: X.Y.Z**` right after
   the one-line project description, before the "Why this project exists" section.

**Never modify only one of these 3 files without the other two.** That is
exactly the problem this skill solves: without it, it is easy to bump
`SKILL.md` while forgetting `CHANGELOG.md` or `README.md`, and the 3 sources drift.

## Steps

### 1. Read the current state

- Current version: the `version:` field of `.claude/skills/analyse-parcours/SKILL.md`.
- Last bump commit: `git log --oneline -- .claude/skills/analyse-parcours/SKILL.md`
  then `git show <hash>` on the most recent one to find its date and message.
- Check that `CHANGELOG.md` and `README.md` are indeed aligned on this current
  version (before starting). If one of the two is already out of sync, signal it
  explicitly to the user before continuing — it is a sign that a previous
  evolution was done without going through this skill.

### 2. Inventory what changed since the last bump

```bash
git log --oneline <last-bump-hash>..HEAD
```

Group the commits by theme (not one bullet per commit: that would be unreadable
for a session with many small fixes). Draw inspiration from the grouping already
done in the existing `CHANGELOG.md` entries for the tone and level of detail
expected.

### 3. Ask the user for the release type

Ask the question with `AskUserQuestion` (never decide a version number alone,
it is a product decision):
- **Patch** (X.Y.Z+1): fixes, stabilization, no new capability.
- **Minor** (X.Y+1.0): new feature, probes or criteria added, backward compatible.
- **Major** (X+1.0.0): breaking change (migrated reference, changed output format,
  incompatible with previous audits).

Also ask for a short theme (1 to 3 words) for the changelog entry header,
like "Stabilization" for 1.2.1 — reuse the same keyword if the user explicitly
asks for it again, otherwise propose a theme consistent with the content
inventoried at step 2 and have it validated.

### 4. Draft the CHANGELOG.md entry and have it validated before writing

Entry format (see existing entries):

```markdown
## [X.Y.Z] - YYYY-MM-DD — Theme

Optional intro sentence if the context justifies it (ex: "no major new
feature: ...").

- Thematic bullet 1
- Thematic bullet 2
```

Show the draft entry to the user before touching any file.

### 5. Write the 3 files in one go

In this order, without stopping between the three (so as never to leave an
inconsistent state visible in git status):

1. `.claude/skills/analyse-parcours/SKILL.md`: `version: X.Y.Z`
2. `CHANGELOG.md`: new entry on top (right after the header, before the
   first existing entry)
3. `README.md`: `**Current version: X.Y.Z**`

### 6. Check consistency afterwards

```bash
grep -n "version:" .claude/skills/analyse-parcours/SKILL.md
grep -n "^## \[" CHANGELOG.md | head -1
grep -n "Current version" README.md
```

Confirm to the user that the 3 values do display the same number.

### 7. Commit

Only commit if the user explicitly asks for it (general project rule, not lifted
by this skill). A release commit typically groups the 3 files in a single commit,
message of the type `chore(release): bump to X.Y.Z (theme)`.

## What this skill does not do

- No automatic git tag (the repo does not use tags to date).
- No publication/deployment: only the consistency of the 3 version files and the history.
- Never decides alone the version number or the content of the changelog entry:
  always validated with the user before writing.
