#!/usr/bin/env python3
"""Conservative public-data importer. Never publishes partial or implausible snapshots."""
import argparse
import datetime as dt
import io
import json
import pathlib
import re
import sys
import urllib.request
from bs4 import BeautifulSoup

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "v2" / "data"
SOURCES = {
    "countries": "https://coeffarchive.com/",
    "clubs": "https://eurocoeff.com/en/rankings/clubs/",
}
ALIASES = {
    "Türkiye": "Turkey", "Turkiye": "Turkey", "Türki̇ye": "Turkey",
    "Czechia": "Czech Republic", "Republic of Ireland": "Republic of Ireland",
    "Ireland": "Republic of Ireland", "Bosnia and Herzegovina": "Bosnia & Herzegovina",
    "Bosnia & Herzegovina": "Bosnia & Herzegovina", "North Macedonia": "North Macedonia",
    "Faroe Islands": "Faroe Islands", "Russia": "Russia",
}
def clean(value):
    return re.sub(r"\s+", " ", value).strip()
def number(value):
    text = clean(value).replace(",", "")
    m = re.search(r"(?<!\d)(\d{1,3}(?:\.\d{1,3})?)(?!\d)", text)
    if not m:
        raise ValueError("Missing numeric coefficient: " + repr(value))
    return float(m.group(1))
def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "CoefficientHub/2.0 (public rankings; contact via GitHub)", "Accept": "text/html"})
    with urllib.request.urlopen(req, timeout=25) as response:
        return response.read().decode("utf-8", errors="replace")
def rows(html):
    soup = BeautifulSoup(html, "html.parser")
    for table in soup.find_all("table"):
        for tr in table.find_all("tr"):
            cells = tr.find_all(["td", "th"], recursive=False)
            if cells:
                yield [clean(cell.get_text(" ", strip=True)) for cell in cells]
def extract_countries(html):
    """Parse the public CoeffArchive table, including rank movement arrows."""
    found = {}
    for row in rows(html):
        if len(row) < 8:
            continue
        # Rank may include a movement indicator: "10 ▲2", "12 ▼2".
        match = re.match(r"^(\\d{1,2})(?!\\d)", row[0])
        if not match:
            continue
        rank = int(match.group(1))
        if not 1 <= rank <= 55:
            continue
        name = ALIASES.get(row[1], row[1])
        try:
            total = number(row[2])
            seasons = [number(v) for v in row[3:8]]
        except (ValueError, IndexError):
            continue
        if not name or len(seasons) != 5 or abs(sum(seasons) - total) > 0.012:
            continue
        if name in found:
            raise ValueError(f"Duplicate association: {name}")
        found[name] = {"rank": rank, "name": name, "score": round(total, 3), "seasons": seasons}
    ranks = sorted(x["rank"] for x in found.values())
    if len(found) != 55 or ranks != list(range(1, 56)):
        missing = sorted(set(range(1, 56)) - set(ranks))
        raise ValueError(f"Expected 55 unique, sequential associations; got {len(found)}; missing ranks {missing}; existing snapshot preserved")
    return sorted(found.values(), key=lambda x: x["rank"])
def extract_clubs(html):
    found = {}
    for row in rows(html):
        if len(row) < 3:
            continue
        try:
            rank = int(row[0].strip().rstrip("."))
            name = row[1]
            score = number(row[-1])
        except (ValueError, IndexError):
            continue
        if not 1 <= rank <= 1000 or not name or len(name) > 100 or not 0 < score < 250:
            continue
        found[name] = {"rank": rank, "name": name, "score": round(score, 3)}
    if len(found) < 100:
        raise ValueError(f"Expected at least 100 clubs, got {len(found)}")
    return sorted(found.values(), key=lambda x: (x["rank"], x["name"]))
def publish(kind, data, source, dry_run):
    payload = {"source": source, "retrieved_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
               "verified_by_uefa": False, "status": "third_party_snapshot", "count": len(data), "rows": data}
    target = OUT / (kind + ".json")
    serialized = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if dry_run:
        print(f"DRY RUN {kind}: {len(data)} rows; no file written")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(serialized, encoding="utf-8")
    print(f"Wrote {target}: {len(data)} rows")
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--kind", choices=["countries", "clubs", "all"], default="all")
    args = parser.parse_args()
    failed = []
    for kind in (["countries", "clubs"] if args.kind == "all" else [args.kind]):
        try:
            html = get(SOURCES[kind])
            data = extract_countries(html) if kind == "countries" else extract_clubs(html)
            publish(kind, data, SOURCES[kind], args.dry_run)
        except Exception as e:
            failed.append(kind)
            print(f"ERROR {kind}: {e}; existing snapshot preserved", file=sys.stderr)
    return 1 if failed else 0
if __name__ == "__main__":
    sys.exit(main())
