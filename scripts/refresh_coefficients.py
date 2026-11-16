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
    "countries": "https://www.uefa.com/nationalassociations/uefarankings/country/",
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
    """Parse official UEFA five-season rows; reject anything short of all 55."""
    found = {}
    for row in rows(html):
        if len(row) < 7:
            continue
        # UEFA renders columns in different orders across its desktop/mobile views.
        rank = None
        rank_idx = None
        for i in range(min(3, len(row))):
            m = re.fullmatch(r"(?:Pos\\s*)?(\\d{1,2})\\.?", row[i], re.I)
            if m and 1 <= int(m.group(1)) <= 55:
                rank = int(m.group(1))
                rank_idx = i
                break
        if rank is None:
            continue
        # Association name is the first non-numeric, non-header cell after rank.
        name = None
        name_idx = None
        for i in range(rank_idx + 1, min(len(row), rank_idx + 5)):
            candidate = clean(row[i])
            if re.fullmatch(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ .&'’()\\-]{2,65}", candidate):
                name = ALIASES.get(candidate, candidate)
                name_idx = i
                break
        if name is None:
            continue
        values = []
        for cell in row[name_idx + 1:]:
            candidate = clean(cell).replace(",", "")
            if re.fullmatch(r"\\d{1,3}(?:\\.\\d{1,3})?", candidate):
                values.append(float(candidate))
        if len(values) < 6:
            continue
        # Find five consecutive season coefficients whose sum equals a total
        # elsewhere in the row. Reject ambiguity and unexpected layouts.
        matches = []
        for start in range(len(values) - 4):
            seasons = values[start:start + 5]
            for total in values[:start] + values[start + 5:]:
                if 0 < total < 150 and abs(sum(seasons) - total) <= 0.012:
                    matches.append((round(total, 3), seasons))
        if len(matches) != 1:
            continue
        total, seasons = matches[0]
        if name in found and found[name]["rank"] != rank:
            raise ValueError(f"Conflicting ranks for {name}")
        found[name] = {"rank": rank, "name": name, "score": total, "seasons": seasons}
    ranks = sorted(x["rank"] for x in found.values())
    if len(found) != 55 or ranks != list(range(1, 56)):
        raise ValueError(f"Official UEFA table parser found {len(found)}/55 associations. Missing ranks: {sorted(set(range(1,56))-set(ranks))}; existing snapshot preserved")
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
