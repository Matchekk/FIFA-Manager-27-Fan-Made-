"""Check every projected player against exactly the frozen staged mutation plan."""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from fm27.common import read_csv,write_json,sha256
parser=argparse.ArgumentParser()
parser.add_argument("--before",type=Path,required=True)
parser.add_argument("--after",type=Path,required=True)
parser.add_argument("--plan",type=Path,required=True)
parser.add_argument("--output",type=Path,required=True)
a=parser.parse_args()
before=read_csv(a.before/"players.csv");after=read_csv(a.after/"players.csv");plan=read_csv(a.plan)
changes={r["fm_id"]:r for r in plan}
if len(changes)!=len(plan):raise ValueError("Duplicate plan person")
clubs={c["club_id"]:c for c in read_csv(a.before/"clubs.csv")}
teams={(c["club_id"],c["team_type"]):c["league"] for c in read_csv(a.before/"covered_teams.csv")}
applied=set()
for p in before:
    c=changes.get(p["fm_id"])
    if not c:continue
    applied.add(p["fm_id"])
    if p["club_id"]!=c["old_club_id"] or p["fifa_id"]!=c["fifa_id"] or p["dob"]!=c["dob"]:
        raise ValueError("Plan does not match baseline identity")
    club=clubs[c["new_club_id"]]
    if p["club_id"]!=c["new_club_id"]:p["captain"]="False"
    p.update(club_id=club["club_id"],club=club["club"],country_id=club["country_id"],league=club["league"],
             team_league=teams.get((club["club_id"],c["team_type"]),""),squad=c["team_type"],
             contract_joined=c["joined"],contract_until=c["contract_until"])
    p["reserve_shirt_number" if c["team_type"]=="RESERVE" else "shirt_number"]=c["shirt_number"]
if applied!=changes.keys():raise ValueError("Not every planned person existed")
fields=[f for f in before[0] if f not in {"fm_id","source_file","source_line"}]
if before[0].keys()!=after[0].keys():raise ValueError("Different projection schema")
expected=Counter(tuple(p[f] for f in fields) for p in before)
actual=Counter(tuple(p[f] for f in fields) for p in after)
report={"status":"PROJECTED_STAGE_MATCHES_PLAN" if expected==actual else "FAILED",
        "DATABASE_SNAPSHOT_DATE":plan[0]["snapshot_date"],"plan_sha256":sha256(a.plan),"planned_rows":len(plan),
        "planned_club_changes":sum(r["old_club_id"]!=r["new_club_id"] for r in plan),
        "players_before":len(before),"players_after":len(after),"unexpected_missing":sum((expected-actual).values()),
        "unexpected_added":sum((actual-expected).values()),"fields_compared":fields,
        "examples_expected":[dict(zip(fields,r)) for r in list(expected-actual)[:3]],
        "examples_actual":[dict(zip(fields,r)) for r in list(actual-expected)[:3]],
        "production_ready":False,"limitations":"No game/save/competition-season validation. Missing players, loans and uncovered departures remain unresolved; do not install as a complete overhaul."}
write_json(a.output,report)
print(json.dumps({k:v for k,v in report.items() if not k.startswith('examples')}))
sys.exit(report["status"]=="FAILED")
