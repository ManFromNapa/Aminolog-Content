#!/usr/bin/env python3
"""Validate content: JSON Schema, cross-references, and manifest consistency."""
import json, re, sys, pathlib
from jsonschema import Draft202012Validator

root = pathlib.Path(__file__).parent
schema = json.loads((root / "schema/peptide.schema.json").read_text())
v = Draft202012Validator(schema)
errors = []
files = sorted((root / "peptides").glob("*.json"))
for f in files:
    d = json.loads(f.read_text())
    for e in v.iter_errors(d):
        errors.append(f"{f.name}: {e.message}")
    if d.get("id") != f.stem: errors.append(f"{f.name}: id != filename")
    ids = {r["id"] for r in d.get("research", [])}
    for e in d.get("dosing", {}).get("entries", []):
        if e["citation_id"] not in ids: errors.append(f"{f.name}: unknown citation {e['citation_id']}")
    for r in d.get("research", []):
        k, i = r["source_kind"], r["identifier"]
        if k == "pubmed" and not re.fullmatch(r"\d+", i): errors.append(f"{f.name}: bad PMID {i}")
        if k == "clinicaltrials" and not re.fullmatch(r"NCT\d{8}", i): errors.append(f"{f.name}: bad NCT {i}")
        if k == "fda" and not i.startswith("https://"): errors.append(f"{f.name}: FDA id must be URL")
    for c in d.get("internet_claims", []):
        if (c["source_type"] == "vendor") != (c["url"] is None):
            errors.append(f"{f.name}: vendor/url mismatch")
mp = root / "manifest.json"
if mp.exists():
    m = json.loads(mp.read_text())
    if sorted(m["peptides"]) != sorted(f.stem for f in files): errors.append("manifest does not match peptides/")
print("\n".join(errors) or f"OK: {len(files)} files")
sys.exit(1 if errors else 0)
