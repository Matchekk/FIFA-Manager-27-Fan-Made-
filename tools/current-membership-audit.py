"""Compare authoritative target membership to an independent native inspection."""
import argparse,csv,json
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
LEAGUES={'ENG1':(14,0,20),'ITA1':(27,0,20),'ESP1':(45,0,20),'GER1':(21,0,18),'FRA1':(18,0,18),'POR1':(38,0,18),'NED1':(34,0,18),'BEL1':(7,0,18),'TUR1':(48,0,18),'CZE1':(12,0,16),'GER2':(21,1,18),'GER3':(21,2,20)}
def read(p):
 with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--inspection',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
 p.add_argument('--source',type=Path,default=ROOT/'data/current/league-membership-2026-27.integration.csv')
 a=p.parse_args(); source=read(a.source)
 native=read(a.inspection/'competition_members.csv')
 # Cup/group-stage seed lists can legitimately repeat league members. Only
 # domestic normal League IDs participate in impossible-assignment checks.
 all_native=Counter((r['club_id'],r['team_type'].upper()) for r in native
                    if ((int(r['competition_id'])>>16)&255)==1 and 1<=int(r['competition_id'])>>24<=207)
 results=[]
 for league,(country,index,count) in LEAGUES.items():
  cid=str((country<<24)+(1<<16)+index)
  expected=[(r['native_club_id'],r['team_type'].upper()) for r in source if r['league']==league]
  actual=[(r['club_id'],r['team_type'].upper()) for r in native if r['competition_id']==cid]
  missing=sorted(set(expected)-set(actual));unexpected=sorted(set(actual)-set(expected))
  duplicates=[list(t) for t in set(actual) if all_native[t]!=1]
  source_ok=len(expected)==count and len(set(expected))==count
  passed=source_ok and len(actual)==count and len(set(actual))==count and not missing and not unexpected and not duplicates
  results.append(dict(league=league,competition_id=cid,expected_clubs=count,source_clubs=len(expected),native_clubs=len(actual),source_unique=source_ok,missing_promoted_or_required=missing,unexpected_relegated_or_other=unexpected,duplicate_domestic_assignments=duplicates,status='PASS' if passed else 'FAIL'))
 report=dict(inspection=str(a.inspection),status='PASS' if all(r['status']=='PASS' for r in results) else 'INCOMPLETE',leagues_pass=sum(r['status']=='PASS' for r in results),leagues_total=12,results=results)
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({k:v for k,v in report.items() if k!='results'}))
if __name__=='__main__':main()
