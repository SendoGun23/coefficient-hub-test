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
    "UECL": "https://www.uefa.com/uefaconferenceleague/news/02a8-2174cb200f25-b94693ddff4e-1000--2026-27-conference-league-league-phase-fixtures/",
}
MONTHS = {"september":9,"october":10,"november":11,"december":12,"january":1,
          "february":2,"march":3,"april":4,"may":5,"june":6,"july":7,"august":8}
DATE = re.compile(r"^(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s+(\d{1,2})\s+([A-Za-z]+)\s+(20\d{2})$",re.I)
SCORE = re.compile(r"^(.+?)\s+(\d+)\s*[-–]\s*(\d+)\s+(.+?)$")
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
        # Articles can repeat fixtures in a later by-team section; stop there.
        if line.casefold() in {"league phase fixtures by team", "fixtures by team"} and matches:
            break
        m=DATE.fullmatch(line)
        if m:
            day,month,year=m.groups()
            month_num=MONTHS.get(month.lower())
            try:
                current=dt.date(int(year),month_num,int(day)).isoformat() if month_num else None
            except ValueError:
                current=None
            continue
        if not current: continue
        if line.casefold().startswith(("matchday ", "group ", "league phase", "round of ", "fixtures by ")): continue
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
        if not row["home"].strip() or not row["away"].strip() or norm(row["home"])==norm(row["away"]):
            raise ValueError(f"{competition}: invalid teams")
        if row["status"]=="finished" and (row["hg"]>30 or row["ag"]>30):
            raise ValueError(f"{competition}: implausible score")
        key=(row["date"],norm(row["home"]),norm(row["away"]))
        if key in keys: raise ValueError(f"{competition}: duplicate source match {key}")
        keys.add(key)
    return matches
def audit(existing,source):
    indexed={}
    for row in existing:
        key=(row["date"],norm(row["home"]),norm(row["away"]))
        if key in indexed:
            raise ValueError(f"duplicate archive fixture: {key}")
        indexed[key]=row
    verified=[]; conflicts=[]; missing=[]; result_updates=[]; archive_only=[]; matched=set(); source_keys=set()
    for row in source:
        key=(row["date"],norm(row["home"]),norm(row["away"]))
        if key in source_keys:
            raise ValueError(f"duplicate source fixture: {key}")
        source_keys.add(key)
        prior=indexed.get(key)
        if prior is not None: matched.add(key)
        if prior is None:
            missing.append(row)
        elif prior["status"]==row["status"] and (prior["status"]!="finished" or (prior["hg"],prior["ag"])==(row["hg"],row["ag"])):
            verified.append(key)
        elif prior["status"]=="scheduled" and row["status"]=="finished":
            result_updates.append({"existing":prior,"source":row})
        else:
            conflicts.append({"existing":prior,"source":row})
    archive_only=[x for key,x in indexed.items() if key not in matched]
    return {"verified":len(verified),"pending_results":result_updates,"conflicts":conflicts,
            "not_in_archive":missing,"not_in_source":archive_only,"source_count":len(source),
            "archive_count":len(existing)}
def fetch(url):
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 (compatible; CoefficientHubAudit/1.0)","Accept":"text/html"})
    with urllib.request.urlopen(req,timeout=25) as response:
        return response.read().decode("utf-8","replace")
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",default="uefa-fixture-audit.json")
    parser.add_argument("--offline-html-dir",type=pathlib.Path,help="Use saved UCL.html, UEL.html, UECL.html instead of network (reproducible diagnostics)")
    args=parser.parse_args()
    archive=json.loads((ROOT/"v2/data/fixtures.json").read_text(encoding="utf-8"))
    result={"generated_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
            "mode":"read_only_audit","sources":SOURCES,"competitions":{}}
    failed=False
    for comp,url in SOURCES.items():
        try:
            html=(args.offline_html_dir / (comp+".html")).read_text(encoding="utf-8") if args.offline_html_dir else fetch(url)
            extracted=extract(html,comp)
            existing=[x for x in archive["rows"] if x["season"]=="2026/27" and x["competition"]==comp]
            comparison=audit(existing,extracted)
            # A parseable but unrelated article is not evidence of correct UEFA fixtures.
            overlap=comparison["verified"]+len(comparison["pending_results"])+len(comparison["conflicts"])
            if overlap==0:
                raise ValueError(f"{comp}: no fixture identity overlap with archive; source or parser must be reviewed")
            result["competitions"][comp]=comparison
            result["competitions"][comp]["source_url"]=url
            result["competitions"][comp]["verification_status"]="parsed_unverified"
            print(f"{comp}: {result['competitions'][comp]['verified']} confirmed; "
                  f"{len(result['competitions'][comp]['pending_results'])} result updates for review; "
                  f"{len(result['competitions'][comp]['conflicts'])} conflicts; "
                  f"{len(result['competitions'][comp]['not_in_archive'])} missing")
        except Exception as exc:
            failed=True
            result["competitions"][comp]={"error":str(exc),"source_url":url,"verification_status":"failed"}
            print(f"{comp}: source unavailable or format changed: {exc}",file=sys.stderr)
    output=pathlib.Path(args.output)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return 1 if failed else 0
if __name__=="__main__": sys.exit(main())
