#!/usr/bin/env python3
"""Validate content: JSON Schema, cross-references, and manifest consistency."""
import json, re, sys, pathlib
from jsonschema import Draft202012Validator

root = pathlib.Path(__file__).parent
schema = json.loads((root / "schema/peptide.schema.json").read_text())
v = Draft202012Validator(schema)
errors = []

def check_sections(label, d, ids):
    lines = [(f"{sec}.{k}", v) for sec in ("how_to_take", "what_it_does") for k, v in d.get(sec, {}).items()]
    lines += [(f"side_effect_groups[{n}]", g) for n, g in enumerate(d.get("side_effect_groups", []))]
    for where, line in lines:
        if bool(line["items"]) != bool(line["summary"].strip()):
            errors.append(f"{label}: {where} summary must be empty exactly when it has no items")
        for n, item in enumerate(line["items"]):
            if item.get("label") == "research" and item["citation_id"] not in ids:
                errors.append(f"{label}: {where}[{n}] cites unknown {item['citation_id']}")
            if item.get("label") == "internet" and (item["source_type"] == "vendor") != (item["url"] is None):
                errors.append(f"{label}: {where}[{n}] vendor/url mismatch")

only = set(sys.argv[1:])
all_files = sorted((root / "peptides").glob("*.json"))
files = [f for f in all_files if not only or f.stem in only]
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
        if k in ("fda", "regulator") and not i.startswith("https://"): errors.append(f"{f.name}: FDA id must be URL")
    for c in d.get("internet_claims", []):
        if (c["source_type"] == "vendor") != (c["url"] is None):
            errors.append(f"{f.name}: vendor/url mismatch")
    for n, e in enumerate(d.get("dosing", {}).get("internet_entries", [])):
        if (e["source_type"] == "vendor") != (e["url"] is None):
            errors.append(f"{f.name}: dosing.internet_entries[{n}] vendor/url mismatch")
    check_sections(f.name, d, ids)
    for field in ("administration_guidance", "side_effects"):
        for n, item in enumerate(d.get(field, [])):
            if item.get("label") == "research":
                if item["citation_id"] not in ids: errors.append(f"{f.name}: {field}[{n}] cites unknown {item['citation_id']}")
            elif item.get("label") == "internet":
                if (item["source_type"] == "vendor") != (item["url"] is None):
                    errors.append(f"{f.name}: {field}[{n}] vendor/url mismatch")
# Blends
bschema = json.loads((root / "schema/blend.schema.json").read_text())
bv = Draft202012Validator(bschema)
peptide_ids = {f.stem for f in all_files}
blend_files = sorted((root / "blends").glob("*.json")) if (root / "blends").exists() else []
for f in blend_files:
    b = json.loads(f.read_text())
    for e in bv.iter_errors(b): errors.append(f"blends/{f.name}: {e.message}")
    if b.get("id") != f.stem: errors.append(f"blends/{f.name}: id != filename")
    if b.get("id") in peptide_ids: errors.append(f"blends/{f.name}: id clashes with a peptide")
    for c in b.get("components", []):
        if c not in peptide_ids: errors.append(f"blends/{f.name}: unknown component {c}")
    if len(b.get("components", [])) + len(b.get("other_components", [])) < 2:
        errors.append(f"blends/{f.name}: a blend needs at least two components")
    ids = {r["id"] for r in b.get("research", [])}
    for r in b.get("research", []):
        k, i = r["source_kind"], r["identifier"]
        if k == "pubmed" and not re.fullmatch(r"\d+", i): errors.append(f"blends/{f.name}: bad PMID {i}")
        if k == "clinicaltrials" and not re.fullmatch(r"NCT\d{8}", i): errors.append(f"blends/{f.name}: bad NCT {i}")
        if k in ("fda", "regulator") and not i.startswith("https://"): errors.append(f"blends/{f.name}: FDA id must be URL")
    for c in b.get("internet_claims", []):
        if (c["source_type"] == "vendor") != (c["url"] is None): errors.append(f"blends/{f.name}: vendor/url mismatch")
    check_sections(f"blends/{f.name}", b, ids)
    for field in ("administration_guidance", "side_effects"):
        for n, item in enumerate(b.get(field, [])):
            if item.get("label") == "research" and item["citation_id"] not in ids:
                errors.append(f"blends/{f.name}: {field}[{n}] cites unknown {item['citation_id']}")
            if item.get("label") == "internet" and (item["source_type"] == "vendor") != (item["url"] is None):
                errors.append(f"blends/{f.name}: {field}[{n}] vendor/url mismatch")
# Glossary
gp = root / "glossary.json"
if gp.exists() and not only:
    g = json.loads(gp.read_text())
    gv = Draft202012Validator(json.loads((root / "schema/glossary.schema.json").read_text()))
    for e in gv.iter_errors(g): errors.append(f"glossary.json: {e.message}")
    seen = {}
    for entry in g.get("entries", []):
        t = entry["term"]
        if "\u2014" in entry["definition"] or "\u2013" in entry["definition"]: errors.append(f"glossary.json: {t}: dash in definition")
        cat = entry["category"]
        if cat == "units" and "source" in entry: errors.append(f"glossary.json: {t}: units take no source")
        # every match string and its case rule: (text, case_sensitive)
        forms = [(t, bool(entry.get("abbreviation")))]
        forms += [(a, False) for a in entry.get("aliases", [])]
        forms += [(a, True) for a in entry.get("abbreviation_aliases", [])]
        for text, cs in forms:
            key = text if cs else text.lower()
            for (k2, cs2), owner in seen.items():
                if (cs and cs2 and text == k2) or (not cs and not cs2 and key == k2) or (cs != cs2 and text.lower() == k2.lower()):
                    if owner != t: errors.append(f"glossary.json: '{text}' ({t}) collides with '{k2}' ({owner})")
            seen[(key, cs)] = t
mp = root / "manifest.json"
if mp.exists() and not only:
    m = json.loads(mp.read_text())
    if sorted(m["peptides"]) != sorted(f.stem for f in all_files): errors.append("manifest does not match peptides/")
    if sorted(m.get("blends", [])) != sorted(f.stem for f in blend_files): errors.append("manifest does not match blends/")
print("\n".join(errors) or f"OK: {len(files)} files")
sys.exit(1 if errors else 0)
