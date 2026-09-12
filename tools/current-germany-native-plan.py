"""Close only the German membership dependencies needed for the GER3 update."""
import csv,hashlib,json
from collections import Counter,defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'data/generated/native10-base-competition-inspection-20260912-01'
def read(p):
 with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 original=read(BASE/'competition_members.csv');groups=defaultdict(list)
 for r in original:groups[int(r['competition_id'])].append((r['club_id'],r['team_type'].upper()))
 desired={k:list(v) for k,v in groups.items()};changes=[]
 def swap(cid,old,new):
  key=(str(old),'FIRST');target=(str(new),'FIRST');assert desired[cid].count(key)==1
  slot=desired[cid].index(key);desired[cid][slot]=target
  changes.append(dict(competition_id=cid,slot=slot+1,old_club_id=old,new_club_id=new,team_type='FIRST'))
 for old,new in [(1376297,1376306),(1376291,1376540),(1376277,1376347),(1376467,1376444)]:swap(352387074,old,new)
 swap(352387078,1376306,1376297)  # Ulm / Grossaspach
 swap(352387079,1376540,1376291)  # Wurzburg /1860
 desired[352387079].append(('1376467','FIRST'))
 changes.append(dict(competition_id=352387079,slot=19,old_club_id=0,new_club_id=1376467,team_type='FIRST'))
 boundary=read(ROOT/'data/current/german-nord-west-dependencies.csv')
 assert len(boundary)==2 and all(r['status']=='CONFIRMED' for r in boundary)
 for row in boundary:
  swap(int(row['regional_competition_native_id']),int(row['regional_vacated_club_native_id']),int(row['regional_promoted_club_native_id']))
  swap(int(row['oberliga_competition_native_id']),int(row['regional_promoted_club_native_id']),int(row['boundary_promoted_club_native_id']))
 swap(352387076,1376375,1376277) # Aue -> Nordost; Meuselwitz -> its current Oberliga
 swap(352387085,1376368,1376375) # Grimma officially relegated below the modeled tier
 permissions={('1376368','FIRST'),('1389307','FIRST'),('1376965','FIRST')}
 domestic=lambda d: Counter(t for cid,teams in d.items() if cid>>24==21 and (cid>>16)&255==1 for t in teams)
 before,after=domestic(groups),domestic(desired)
 assert all(n==1 for n in after.values())
 assert before[('1376368','FIRST')]==1 and after[('1376368','FIRST')]==0
 for uid in ['1389307','1376965']:assert before[(uid,'FIRST')]==0 and after[(uid,'FIRST')]==1
 assert {k:v for k,v in before.items() if k not in permissions}=={k:v for k,v in after.items() if k not in permissions}
 authoritative=read(ROOT/'data/current/league-membership-2026-27.integration.csv')
 assert set(desired[352387074])=={(r['native_club_id'],r['team_type'].upper()) for r in authoritative if r['league']=='GER3'}
 touched=sorted({c['competition_id'] for c in changes});rows=[]
 for cid in touched:
  assert len(desired[cid])==len(groups[cid])+(cid==352387079)
  for uid,team in desired[cid]:rows.append(dict(competition_id=cid,club_id=uid,team_type=team))
 rows.extend(dict(competition_id=0,club_id=uid,team_type=team) for uid,team in sorted(permissions))
 path=ROOT/'data/current/germany-native-plan.csv'
 with path.open('w',encoding='utf-8',newline='') as f:
  w=csv.DictWriter(f,fieldnames=['competition_id','club_id','team_type']);w.writeheader();w.writerows(rows)
 inputs=[BASE/'competition_members.csv',ROOT/'data/current/league-membership-2026-27.integration.csv',ROOT/'data/current/ger3-membership-plan.manifest.json',ROOT/'data/current/german-nord-west-dependencies.csv',ROOT/'data/current/german-nord-west-dependencies.json',ROOT/'data/current/evidence/german-dependencies/manifest.json']
 manifest=dict(status='PASS_SCOPED_MEMBERSHIP_PLAN',plan_sha256=sha(path),changes=changes,boundary=sorted(permissions),counts={str(cid):len(desired[cid]) for cid in touched},
  input_sha256={str(p.relative_to(ROOT)):sha(p) for p in inputs},
  source_evidence=json.loads((ROOT/'data/current/evidence/german-dependencies/manifest.json').read_text()),
  policy='Only required GER3 closure: unrelated lower memberships retained exactly, not asserted current. Grimma exits below the fifth modeled tier; Nordhorn/Kinderhaus enter from below it. All other club memberships conserved.',
  format=dict(league='Bayern',teams=19,rounds=38,regional_pool=91,calendar='existing German19-team native donor',future_policy='Balanced stable19-team modeled format; any official2027/28 transient size adaptation remains an explicit later script review, not a claimed historical fact.'))
 (path.with_suffix('.manifest.json')).write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(dict(rows=len(rows),changed_slots=len(changes),leagues=len(touched),status=manifest['status'])))
if __name__=='__main__':main()
