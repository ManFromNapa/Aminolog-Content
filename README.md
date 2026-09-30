# Aminolog Content

Educational content for the Aminolog iOS app, served through GitHub Pages.
For research and educational purposes only. Not medical advice.

- `peptides/<id>.json` — one file per peptide, validated by `schema/peptide.schema.json`
- `manifest.json` — `content_version` bumps whenever content changes; the app downloads files only when this is newer
- `validate.py` — run before every commit (`pip install jsonschema`)

## Update workflow
1. Edit or add JSON. Every claim needs a citation whose identifier (PMID, NCT number, or FDA label URL) was checked against the primary source.
2. Run `python3 validate.py`.
3. Bump `content_version` and `updated` in `manifest.json`.
4. Review the diff, then commit and push.

Rules: no preprints; vendor-sourced claims have `url: null` and no link; doses for unapproved compounds are worded as what was studied, never as instructions.
