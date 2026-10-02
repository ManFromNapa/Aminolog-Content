# Aminolog Content

Educational content for the Aminolog iOS app, served through GitHub Pages.
For research and educational purposes only. Not medical advice.

- `peptides/<id>.json` — one file per peptide, validated by `schema/peptide.schema.json`
- `manifest.json` — `content_version` bumps whenever content changes; the app downloads files only when this is newer
- `blends/<id>.json`: mixtures of peptides, validated by `schema/blend.schema.json`
- `validate.py`: schema and cross-reference check. Run before every commit (`pip install jsonschema`)
- `check_sources.py`: verifies every PMID, trial number, label date and link against the live sources. Run before publishing and in the monthly review
- `audit_report.py`: prints a readable Markdown report of everything (status, doses, every citation as a link, every claim) for auditing

## Update workflow
1. Edit or add JSON. Every claim needs a citation whose identifier (PMID, NCT number, or FDA label URL) was checked against the primary source.
2. Run `python3 validate.py`.
3. Bump `content_version` and `updated` in `manifest.json`.
4. Review the diff, then commit and push.

Rules: no preprints; vendor-sourced claims have `url: null` and no link; doses for unapproved compounds are worded as what was studied, never as instructions.

## How to take, what it does, side effect groups
Every peptide and blend file has three sections built from sourced items:
- `how_to_take`: six lines, in this order: `dose`, `timing`, `fasting`, `frequency`, `cycle_length`, `storage_and_handling`
- `what_it_does`: two lines, `mechanism` and `best_documented_effect`
- `side_effect_groups`: an array of `{title, summary, items}` with at least one item each

Each line is `{summary, items}`. `summary` is empty exactly when `items` is empty; the app shows "No data found" for an empty line. Never fill a line without a source.

An item is one of:
- Research: `text`, `label: "research"`, `validity`, optional `conflicts_with_label`, and `citation_id` matching an `id` in the file's `research` array
- Internet: `text`, `label: "internet"`, `validity`, optional `conflicts_with_label`, `source_type`, `url` and `retrieved` (YYYY-MM-DD). Anyone selling the product, including telehealth sellers and clinics, is `vendor` with `url: null`.

`conflicts_with_label: true` marks an item that contradicts an FDA label or regulator document for that compound (cycling a once-daily drug, refrigerating a room-temperature product, doses above the label).

On blends these lines hold only information about the combination itself. Details about one component stay on that component's page.

The older fields (`dosing`, `administration_guidance`, `side_effects`) stay populated and unchanged until the app version that reads the new sections is the minimum in use.

### Validity scale
Every item has one, and every internet item is `very_low`.

| Level | Meaning |
|---|---|
| `strong` | FDA label, or consistent human trials for that use. Phase 3 trials count, even for unapproved drugs. |
| `moderate` | Human trials that are small, or in a different population, dose or route. Phase 2 trials and reviews. |
| `low` | Only animal or lab studies, or physiology reasoning applied to the compound. Uncontrolled human pilots and case series also count as low. Data on a related compound is low. |
| `very_low` | Clinic, vendor or community convention with no supporting study. |
