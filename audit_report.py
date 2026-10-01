#!/usr/bin/env python3
"""Print a Markdown audit report of the content: one section per peptide with its status, doses,
every citation as a clickable link, and every internet claim. Use it for the monthly review.

  python3 audit_report.py > report.md
  python3 audit_report.py semaglutide bpc-157 > report.md
"""
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))

EVIDENCE = {"human_trial": "Human trial", "animal_study": "Animal study", "in_vitro": "In vitro",
            "fda_label": "FDA label", "regulatory_document": "Regulatory document",
            "case_report": "Case report", "systematic_review": "Systematic review",
            "regulator_notice": "Regulator notice"}


def link(r):
    k, i = r["source_kind"], r["identifier"]
    if k == "pubmed":
        return f"[PMID {i}](https://pubmed.ncbi.nlm.nih.gov/{i}/)"
    if k == "clinicaltrials":
        return f"[{i}](https://clinicaltrials.gov/study/{i})"
    return f"[{'Regulator' if k == 'regulator' else 'FDA'} source]({i})"


def main():
    only = set(sys.argv[1:])
    files = sorted(glob.glob(os.path.join(ROOT, "peptides", "*.json")))
    data = [json.load(open(f)) for f in files]
    data = [d for d in data if not only or d["id"] in only]
    manifest = json.load(open(os.path.join(ROOT, "manifest.json")))

    print(f"# Aminolog content audit\n\nContent version {manifest['content_version']} "
          f"({manifest['updated']}). {len(data)} peptides.\n")
    print("| Peptide | Status | Category | Doses | Research | Guidance | Side effects | Claims |\n|---|---|---|---|---|---|---|---|")
    for d in data:
        print(f"| [{d['name']}](#{d['id']}) | {d['regulatory_status']} | {d['category']} | {len(d['dosing']['entries'])} "
              f"({d['dosing']['basis']}) | {len(d['research'])} | {len(d['administration_guidance'])} | "
              f"{len(d['side_effects'])} | {len(d['internet_claims'])} |")
    for d in data:
        print(f"\n---\n\n## {d['name']} <a id=\"{d['id']}\"></a>\n")
        if d["aliases"]:
            print(f"Also known as: {', '.join(d['aliases'])}\n")
        print(f"**Status:** {d['regulatory_status']}  \n**Category:** {d['category']}  \n**Last reviewed:** {d['last_reviewed']}\n")
        print(f"**Used for:** {d['used_for']}\n")
        by_id = {r["id"]: r for r in d["research"]}
        print(f"### Doses ({d['dosing']['basis']})\n")
        if not d["dosing"]["entries"]:
            print("_None included._\n")
        for e in d["dosing"]["entries"]:
            r = by_id.get(e["citation_id"])
            cite = f"{EVIDENCE[r['evidence_type']]}, {link(r)}" if r else "MISSING CITATION"
            print(f"- {e['text']}  \n  *{e['population']}* ({cite})")
        print("\n### Research\n")
        for r in d["research"]:
            print(f"- **{EVIDENCE[r['evidence_type']]}**, {link(r)}, {r['year']}  \n"
                  f"  {r['summary']}  \n  *Finding:* {r['finding']}")
        for title, field in (("Administration guidance", "administration_guidance"), ("Side effects", "side_effects")):
            print(f"\n### {title}\n")
            if not d[field]:
                print("_None recorded._")
            for item in d[field]:
                if item["label"] == "research":
                    r = by_id.get(item["citation_id"])
                    cite = f"{EVIDENCE[r['evidence_type']]}, {link(r)}" if r else "MISSING CITATION"
                    print(f"- **Research** ({cite}): {item['text']}")
                else:
                    src = f"[source]({item['url']})" if item["url"] else "no link (vendor)"
                    print(f"- **Internet** ({item['source_type']}, {src}, retrieved {item['retrieved']}): {item['text']}")
        print("\n### What the internet is saying\n")
        if not d["internet_claims"]:
            print("_None recorded._")
        for c in d["internet_claims"]:
            src = f"[source]({c['url']})" if c["url"] else "no link (vendor)"
            print(f"- **{c['source_type']}**, {src}, retrieved {c['retrieved']}  \n  {c['claim']}")


if __name__ == "__main__":
    main()
