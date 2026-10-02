#!/usr/bin/env python3
"""List terms in the content that are not yet in glossary.json, so the glossary stays complete.

  python3 glossary_gaps.py            # candidates not in the glossary (exit 1 if any)
  python3 glossary_gaps.py --stale    # also list glossary terms that no longer appear in the content

It scans every prose field of every peptide and blend file. Candidates are:
  - abbreviations (IGF-1, HbA1c, GHRH) and units after numbers (mg, mL, IU)
  - words missing from the system dictionary (/usr/share/dict/words)
  - words with medical endings (-emia, -itis, -osis, -pathy, -oma, -kinase and similar)
Peptide and blend names, aliases and ids are skipped automatically. Names that are not glossary terms
(trial names, sites, companies) go in glossary_ignore.json. Ordinary words used as technical terms
(placebo, half-life) cannot be detected automatically; add them to glossary.json by hand.
"""
import collections
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
SKIP_KEYS = {"url", "id", "citation_id", "identifier", "source_type", "label", "validity", "retrieved",
             "last_reviewed", "evidence_type", "source_kind", "components", "category", "regulatory_status",
             "basis", "title"}
ABBR = re.compile(r"\b(?:[A-Z][A-Za-z]*[A-Z0-9][A-Za-z0-9]*|[A-Z]{2,})(?:-[A-Za-z0-9]+)?\b")
UNIT = re.compile(r"\b\d+(?:\.\d+)?\s?(mg/kg|mcg/kg|mcg|mg|mL|IU|kg|g|µg|nmol/L|mmol/L|pg/mL|ng/mL|mIU/mL|cm|mm|μg)\b")
WORD = re.compile(r"\b[a-z][a-z]+(?:-[a-z]+)*\b")
MEDICAL_END = re.compile(r"(emia|aemia|itis|osis|pathy|oma|genic|tropic|kinase|ectomy|plasia|uria|algia|penia|philia)$")


def texts(o, key=""):
    if isinstance(o, str):
        if key not in SKIP_KEYS:
            yield o
    elif isinstance(o, list):
        for x in o:
            yield from texts(x, key)
    elif isinstance(o, dict):
        for k, v in o.items():
            yield from texts(v, k)


def stem_forms(w):
    yield w
    for suf in ("s", "es", "ed", "ing", "ly", "al", "er", "est", "ies", "ied"):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            b = w[: -len(suf)]
            yield b
            yield b + "e"
            yield b + "y"
            if len(b) > 3 and b[-1] == b[-2]:
                yield b[:-1]


def main():
    stale = "--stale" in sys.argv
    files = sorted(glob.glob(os.path.join(ROOT, "peptides", "*.json")) + glob.glob(os.path.join(ROOT, "blends", "*.json")))
    corpus, own_names = {}, set()
    for f in files:
        d = json.load(open(f))
        corpus[os.path.relpath(f, ROOT)] = "\n".join(texts(d))
        for s in [d["id"], d["name"]] + d.get("aliases", []):
            own_names.update(re.split(r"[\s/()+,]+", s))
            own_names.add(s)
    gp = os.path.join(ROOT, "glossary.json")
    entries = json.load(open(gp))["entries"] if os.path.exists(gp) else []
    cs, ci = set(), set()
    for e in entries:
        (cs if e.get("abbreviation") else ci).add(e["term"] if e.get("abbreviation") else e["term"].lower())
        ci.update(a.lower() for a in e.get("aliases", []))
        cs.update(e.get("abbreviation_aliases", []))
    ip = os.path.join(ROOT, "glossary_ignore.json")
    ignore = set(json.load(open(ip))["ignore"]) if os.path.exists(ip) else set()
    ignore_l = {i.lower() for i in ignore}
    dictionary = set()
    if os.path.exists("/usr/share/dict/words"):
        dictionary = {w.strip().lower() for w in open("/usr/share/dict/words")}
        dictionary.update(w.strip().lower() for w in open("/usr/share/dict/web2a")
                          ) if os.path.exists("/usr/share/dict/web2a") else None
        dictionary.update(("women", "men", "children", "people", "mice", "online", "website", "telehealth", "has", "using", "began",
                           "became", "held", "paid", "withdrew", "earlier", "blog", "app", "podcast", "marketplace", "ads",
                           "promo", "box", "med", "hoc", "com", "gov", "org", "wiki"))
    else:
        print("note: /usr/share/dict/words not found, skipping the dictionary check", file=sys.stderr)

    found = collections.defaultdict(lambda: [0, set(), ""])

    def add(kind, term, name):
        r = found[(kind, term)]
        r[0] += 1
        r[1].add(name)

    for name, text in corpus.items():
        for m in ABBR.findall(text):
            if m in cs or m.lower() in ci or m in ignore or m in own_names:
                continue
            add("abbreviation", m, name)
        for u in UNIT.findall(text):
            if u not in cs and u.lower() not in ci and u not in ignore:
                add("unit", u, name)
        for w in WORD.findall(text):
            if w in ci or w in cs or w in ignore_l or w in own_names or w.capitalize() in own_names:
                continue
            parts = [p for p in w.split("-") if len(p) >= 3]
            if MEDICAL_END.search(w):
                add("word", w, name)
            elif dictionary and any(not any(s in dictionary for s in stem_forms(p)) for p in parts):
                add("word", w, name)

    for kind in ("abbreviation", "unit", "word"):
        rows = sorted(((k[1], v) for k, v in found.items() if k[0] == kind), key=lambda x: -x[1][0])
        if rows:
            print(f"\n## {kind}s not in the glossary ({len(rows)})")
            for term, (n, fs, _) in rows:
                print(f"{term}\t{n} uses in {len(fs)} files\te.g. {sorted(fs)[0]}")
    if stale:
        alltext = "\n".join(corpus.values())
        lower = alltext.lower()
        gone = [e["term"] for e in entries if (e["term"] not in alltext if e.get("abbreviation") else e["term"].lower() not in lower)
                and not any(a.lower() in lower for a in e.get("aliases", []))
                and not any(a in alltext for a in e.get("abbreviation_aliases", []))]
        print(f"\n## glossary terms no longer in the content ({len(gone)})")
        for t in gone:
            print(t)
    print(f"\n{len(found)} candidate terms" if found else "\nGlossary covers all candidate terms.")
    sys.exit(1 if found else 0)


if __name__ == "__main__":
    main()
