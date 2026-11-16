#!/usr/bin/env python3
"""Read-only UEFA fixture audit. Never modifies published fixtures or coefficients.

This intentionally requires exact match of date, clubs and score. Ambiguous rows
are reported for human review, not silently imported.
"""
import argparse
import datetime as dt
import json
import pathlib
import re
import sys
import unicodedata
import urllib.request
from bs4 import BeautifulSoup

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCES = {
    "UCL": "https://www.uefa.com/uefachampionsleague/news/02a8-2174c9e9019d-f909a77bd77a-1000--2026-27-uefa-champions-league-all-the-league-phase-fix/",
    "UEL": "https://www.uefa.com/uefaeuropaleague/news/02a8-2174cafa5bb6-82bbc20c9b92-1000--2026-27-europa-league-all-the-league-phase-fixtures-and-results/",
}
MONTHS = {"september":9,"october":10,"november":11,"december":12,"january":1,
          "february":2,"march":3,"april":4,"may":5,"june":6,"july":7,"august":8}
DATE = re.compile(r"^(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s+(\d{1,2})\s+([A-Za-z]+)\s+(20\d{2})$",re.I)
SCORE = re.compile(r"^(.+?)\s+(\d{1,2})\s*[-–]\s*(\d{1,2})\s+(.+?)$")
SCHEDULED = re.compile(r"^(.+?)\s+vs\s+(.+?)(?:\s*\(\d{1,2}:\d{2}\))?$",re.I)
ALIASES = {"atletico de madrid":"atletico de madrid","atletico madrid":"atletico de madrid",
           "bayern munchen":"bayern munchen","bayern munich":"bayern munchen",
           "paris saint germain":"paris saint germain","psg":"paris saint germain",
           "man city":"manchester city","man utd":"manchester united",
           "borussia dortmund":"borussia dortmund","b dortmund":"borussia dortmund",
           "gnk dinamo":"gnk dinamo","dinamo zagreb":"gnk dinamo",
           "sporting cp":"sporting cp","sporting clube de portugal":"sporting cp",
           "nec nijmegen":"nec nijmegen","nec":"nec nijmegen",
           "union sg":"union sg","union saint gilloise":"union sg"}
def norm(s):
    s = unicodedata.normalize("NFKD",s.casefold())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9]+"," ",s).strip()
    return ALIASES.get(s,s)
def extract(html, competition):
    soup=BeautifulSoup(html,"html.parser")
    for tag in soup(["script","style","nav","footer","header"]): tag.decompose()
    main=soup.find("article") or soup.find("main") or soup
    lines=[re.sub(r"\s+"," ",x).strip() for x in main.get_text("\n").splitlines()]
    current=None; matches=[]
    for line in lines:
        m=DATE.fullmatch(line)
        if m:
            day,month,year=m.groups()
            month_num=MONTHS.get(month.lower())
            current=dt.date(int(year),month_num,int(day)).isoformat() if month_num else None
            continue
        if not current: continue
        m=SCORE.fullmatch(line)
        if m:
            home,hg,ag,away=m.groups()
            matches.append(dict(competition=competition,date=current,home=home,away=away,hg=int(hg),ag=int(ag),status="finished"))
            continue
        m=SCHEDULED.fullmatch(line)
        if m:
            home,away=m.groups()
            matches.append(dict(competition=competition,date=current,home=home,away=away,hg=None,ag=None,status="scheduled"))
    # Avoid accepting a blocked/changed page as a successful source.
    if len(matches)<30: raise ValueError(f"{competition}: too few parseable matches ({len(matches)})")
    keys=set()
    for row in matches:
        key=(row["date"],norm(row["home"]),norm(row["away"]))
        if key in keys: raise ValueError(f"{competition}: duplicate source match {key}")
        keys.add(key)
    return matches
def audit(existing,source):
    indexed={(x["date"],norm(x["home"]),norm(x["away"])):x for x in existing}
    verified=[]; conflicts=[]; missing=[]
    for row in source:
        key=(row["date"],norm(row["home"]),norm(row["away"]))
        prior=indexed.get(key)
        if prior is None:
            missing.append(row)
        elif prior["status"]==row["status"] and (prior["status"]!="finished" or (prior["hg"],prior["ag"])==(row["hg"],row["ag"])):
            verified.append(key)
        else:
            conflicts.append({"existing":prior,"source":row})
    return {"verified":len(verified),"conflicts":conflicts,"not_in_archive":missing,"source_count":len(source)}
def fetch(url):
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 (compatible; CoefficientHubAudit/1.0)","Accept":"text/html"})
    with urllib.request.urlopen(req,timeout=25) as response:
        return response.read().decode("utf-8","replace")
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",default="uefa-fixture-audit.json")
    args=parser.parse_args()
    archive=json.loads((ROOT/"v2/data/fixtures.json").read_text(encoding="utf-8"))
    result={"generated_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
            "mode":"read_only_audit","sources":SOURCES,"competitions":{}}
    failed=False
    for comp,url in SOURCES.items():
        try:
            extracted=extract(fetch(url),comp)
            existing=[x for x in archive["rows"] if x["season"]=="2026/27" and x["competition"]==comp]
            result["competitions"][comp]=audit(existing,extracted)
            print(f"{comp}: {result['competitions'][comp]['verified']} confirmed; "
                  f"{len(result['competitions'][comp]['conflicts'])} conflicts; "
                  f"{len(result['competitions'][comp]['not_in_archive'])} missing")
        except Exception as exc:
            failed=True
            result["competitions"][comp]={"error":str(exc)}
            print(f"{comp}: source unavailable or format changed: {exc}",file=sys.stderr)
    pathlib.Path(args.output).write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return 1 if failed else 0
if __name__=="__main__": sys.exit(main())
