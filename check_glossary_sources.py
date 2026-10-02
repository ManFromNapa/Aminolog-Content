#!/usr/bin/env python3
"""Check every glossary source link against its reference site. Run before publishing glossary changes.

  python3 check_glossary_sources.py

NCI Dictionary of Cancer Terms pages return 200 for any address, so those links are checked through the
NCI glossary API instead. MedlinePlus links must return 200 and a page title that is not an error page.
Also lists medical-category terms that have no source, for information.
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
UA = {"User-Agent": "Mozilla/5.0 AminologContentCheck"}


def get(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:
        return 0, str(e)


def main():
    entries = json.load(open(os.path.join(ROOT, "glossary.json")))["entries"]
    bad, nosrc = [], []
    for e in entries:
        s = e.get("source")
        if not s:
            if e["category"] in ("hormones_receptors", "body_conditions"):
                nosrc.append(e["term"])
            continue
        url = s["url"]
        if s["name"] == "NCI Dictionary of Cancer Terms":
            m = re.fullmatch(r"https://www\.cancer\.gov/publications/dictionaries/cancer-terms/def/([a-z0-9-]+)", url)
            if not m:
                bad.append(f"{e['term']}: unexpected NCI link {url}")
                continue
            code, body = get(f"https://webapis.cancer.gov/glossary/v1/Terms/Cancer.gov/Patient/en/{m.group(1)}")
            if code != 200 or '"termName"' not in body:
                bad.append(f"{e['term']}: not in the NCI dictionary ({url})")
        else:
            code, body = get(url)
            t = re.search(r"<title>([^<]*)", body)
            if code != 200 or not t or "not found" in t.group(1).lower():
                bad.append(f"{e['term']}: MedlinePlus link failed ({code}) {url}")
    if nosrc:
        print(f"info: {len(nosrc)} medical terms without a source: {', '.join(nosrc)}")
    print("\n".join(bad) or f"OK: {sum(1 for e in entries if e.get('source'))} source links checked")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
