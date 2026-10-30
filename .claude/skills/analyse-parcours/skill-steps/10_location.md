# Step 10 — File location

> Source: skill-steps/10_location.md. Return: SKILL.md step 20.

## SOURCE_DIR / AUDIT_DIR convention

- `SOURCE_DIR`: folder containing the files provided by the user (HAR, Coverage, optional cwv.json)
- `AUDIT_DIR`: `SOURCE_DIR/audit/` — created automatically if absent, contains only the files produced by the analysis

Input files (`.har`, `Coverage-*.json`, `cwv.json`) are looked for in `SOURCE_DIR`.
Output files (`har-analysis.json`, `coverage-analysis.json`, HTML report, `analyse-cout-agent/`) are written to `AUDIT_DIR`.

## Optional raw-capture subfolder

An authenticated journey HAR can contain credentials, session tokens or personal data. Raw captures can therefore be stored in a dedicated subfolder, covered by `.gitignore`:

```
SOURCE_DIR/raw-data-potentially-sensitive/
```

Search rule applied by all scripts: **flat in `SOURCE_DIR` first, subfolder as fallback**. Both layouts work; an audit whose files stayed flat keeps working. The constant is declared at the top of each relevant script (`RAW_DATA_DIR`), in `collect_env_data.py`, `collect_cwv_pagespeed.py`, `detect_tech.py`, `similarweb_api.py` and `generate_report_html.py`.

These files are never committed, never modified, never anonymized.

## Where audit cases live

Repo convention: `audits/<site>/`, one folder per analyzed case. `SOURCE_DIR` is this folder, `AUDIT_DIR` is `audits/<site>/audit/`.

## Case 1 — Folder passed as argument

```
/analyse-parcours ./my-folder/
```

1. `SOURCE_DIR` = path passed as argument
2. `AUDIT_DIR` = `SOURCE_DIR/audit/` (create with `mkdir -p` if absent)
3. List the contents of `SOURCE_DIR`
4. Identify the `.har` file(s) in `SOURCE_DIR`
5. Identify the coverage files: `Coverage-*.json` or `*coverage*.json` or `*Coverage*.json` in `SOURCE_DIR`
6. Look for business context: `README.md`, `CONTEXT.md`, `*.txt` in `SOURCE_DIR`

If several `.har` files are found: ask which one to use.

## Case 2 — Files passed directly

```
/analyse-parcours ./capture.har ./cov-page1.json ./cov-page2.json
```

- `SOURCE_DIR` = parent folder of the `.har` file
- `AUDIT_DIR` = `SOURCE_DIR/audit/` (create with `mkdir -p` if absent)
- Use the files as-is. Check that they exist before continuing.

## Case 3 — No argument

Ask the user:
> "Which folder or HAR/Coverage files to analyze? (path to the folder, or a .har file + Coverage-*.json files)"

## Summary to produce

Before moving to step 20, display:

```
Files identified:
- Source   : <SOURCE_DIR>
- Audit    : <AUDIT_DIR>
- HAR      : <file-name.har> ([N] KB)
- Coverage : [N] file(s) — page 1: <name>, page 2: <name>, ...
- Context  : <README.md or "none">
```
