#!/usr/bin/env python3
"""Check every citation and link in the content against the live primary sources.

Run before publishing content and as part of the monthly review.

  python3 check_sources.py            # check everything
  python3 check_sources.py semaglutide bpc-157   # only these files

Hard failures (exit 1): a PMID or NCT number that does not exist, a retracted PubMed paper,
a stated year that is more than 1 year from the record, an FDA label URL that does not resolve,
a DailyMed label whose published year differs from the stated year, or a broken FDA page.
Warnings: claim links that did not return 200 (some sites block scripts; re-check by hand).
"""
import concurrent.futures as cf
import glob
import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
UA = "Mozilla/5.0 (Macintosh) AminologContentCheck"


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "AminologContentCheck"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.load(r)


def curl_status(url):
    out = subprocess.run(
        ["curl", "-sL", "-o", "/dev/null", "-w", "%{http_code}", "-A", UA, "--max-time", "30", url],
        capture_output=True, text=True)
    return out.stdout.strip()


def load_files(only):
    files = sorted(glob.glob(os.path.join(ROOT, "peptides", "*.json")))
    if only:
        files = [f for f in files if os.path.basename(f)[:-5] in only]
    out = [(os.path.basename(f)[:-5], json.load(open(f))) for f in files]
    for f in sorted(glob.glob(os.path.join(ROOT, "blends", "*.json"))):
        name = os.path.basename(f)[:-5]
        if not only or name in only:
            out.append(("blend:" + name, json.load(open(f))))
    return out


def main():
    only = set(sys.argv[1:])
    items = load_files(only)
    errors, warnings = [], []

    pmids = {}      # pmid -> [(file, year)]
    ncts = {}
    labels = {}     # url -> [(file, year)]
    fda_pages = {}  # url -> [file]
    claims = []     # (file, url)
    for name, d in items:
        for r in d["research"]:
            k, i = r["source_kind"], r["identifier"]
            if k == "pubmed":
                pmids.setdefault(i, []).append((name, r["year"]))
            elif k == "clinicaltrials":
                ncts.setdefault(i, []).append((name, r["year"]))
            elif k == "fda":
                if "dailymed.nlm.nih.gov" in i:
                    labels.setdefault(i, []).append((name, r["year"]))
                else:
                    fda_pages.setdefault(i, []).append(name)
            elif k == "regulator":
                fda_pages.setdefault(i, []).append(name)
        for c in d["internet_claims"]:
            if c["url"]:
                claims.append((name, c["url"]))
        for e in d.get("dosing", {}).get("internet_entries", []):
            if e.get("url"):
                claims.append((name, e["url"]))
        for field in ("administration_guidance", "side_effects"):
            for item in d.get(field, []):
                if item.get("label") == "internet" and item.get("url"):
                    claims.append((name, item["url"]))

    # PubMed in batches
    ids = list(pmids)
    for n in range(0, len(ids), 150):
        batch = ids[n:n + 150]
        try:
            res = get_json("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id="
                           + ",".join(batch) + "&retmode=json")["result"]
        except Exception as e:  # noqa: BLE001
            errors.append(f"PubMed lookup failed: {e}")
            continue
        for p in batch:
            e = res.get(p)
            if not e or "error" in e:
                errors.append(f"PMID {p} does not exist ({pmids[p][0][0]})")
                continue
            year = int(re.match(r"\d{4}", e.get("pubdate", "0000")).group(0) or 0) if e.get("pubdate") else 0
            types = [t.lower() for t in e.get("pubtype", [])]
            if "retracted publication" in types:
                errors.append(f"PMID {p} is RETRACTED ({pmids[p][0][0]})")
            if "preprint" in types:
                errors.append(f"PMID {p} is a preprint ({pmids[p][0][0]})")
            for fname, y in pmids[p]:
                if year and abs(year - y) > 1:
                    errors.append(f"PMID {p}: stated year {y}, PubMed says {year} ({fname})")

    # ClinicalTrials.gov
    def check_nct(n):
        try:
            d = get_json(f"https://clinicaltrials.gov/api/v2/studies/{n}?fields=BriefTitle,OverallStatus")
            return n, d["protocolSection"]["identificationModule"]["briefTitle"], d["protocolSection"]["statusModule"].get("overallStatus"), None
        except Exception as e:  # noqa: BLE001
            return n, None, None, str(e)

    with cf.ThreadPoolExecutor(8) as ex:
        nct_status = {}
        for n, title, status, err in ex.map(check_nct, list(ncts)):
            if err:
                errors.append(f"{n} not found on ClinicalTrials.gov ({ncts[n][0][0]}): {err}")
            else:
                nct_status[n] = status

    # DailyMed labels
    def check_label(url):
        m = re.search(r"setid=([0-9a-f-]{36})", url)
        if not m:
            return url, None, "no setid in URL"
        try:
            d = get_json("https://dailymed.nlm.nih.gov/dailymed/services/v2/spls.json?setid=" + m.group(1))["data"]
            if not d:
                return url, None, "label not found"
            return url, d[0]["published_date"], None
        except Exception as e:  # noqa: BLE001
            return url, None, str(e)

    with cf.ThreadPoolExecutor(8) as ex:
        for url, pub, err in ex.map(check_label, list(labels)):
            if err:
                errors.append(f"label {url}: {err} ({labels[url][0][0]})")
                continue
            year = int(pub[-4:])
            for fname, y in labels[url]:
                if year != y:
                    errors.append(f"label year: stated {y}, DailyMed published {pub} ({fname})")

    # FDA pages and claim links
    with cf.ThreadPoolExecutor(12) as ex:
        for url, st in zip(fda_pages, ex.map(curl_status, list(fda_pages))):
            if st != "200":
                errors.append(f"FDA page {url} returned {st} ({fda_pages[url][0]})")
        for (fname, url), st in zip(claims, ex.map(curl_status, [u for _, u in claims])):
            if st != "200":
                warnings.append(f"claim link {url} returned {st} ({fname})")

    print(f"Checked {len(items)} files: {len(pmids)} PMIDs, {len(ncts)} trials, "
          f"{len(labels)} labels, {len(fda_pages)} FDA pages, {len(claims)} claim links.")
    for w in warnings:
        print("WARN ", w)
    for e in errors:
        print("ERROR", e)
    if errors:
        print(f"\n{len(errors)} error(s).")
        sys.exit(1)
    print("OK: no hard failures." + (f" {len(warnings)} warning(s)." if warnings else ""))


if __name__ == "__main__":
    main()
