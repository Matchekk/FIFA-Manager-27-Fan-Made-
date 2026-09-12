"""Publish readable, identity-bound provenance for an immutable data-build input."""
import argparse,csv,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def read(p):
 with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--candidate',type=Path,required=True);a=p.parse_args()
 build=json.loads((a.candidate/'BUILD.json').read_text(encoding='utf-8'))
 players={r['fm_id']:r for r in read(ROOT/'data/generated/native08-integrated-20260912-01-reread/native_players.csv')}
 clubs={r['club_id']:r['club'] for r in read(ROOT/'data/intermediate/transfer-increment-20260909-07/clubs.csv')}
 result=[]
 for r in read(a.candidate/'inputs/squad.csv'):
  person=players[r['fm_id']];action=r.get('action','SQUAD')
  kind=action if action!='SQUAD' else 'LOAN' if r.get('loan_owner_club_id','0')!='0' else 'PERMANENT_MOVE' if r['old_club_id']!=r['new_club_id'] else 'SQUAD_METADATA'
  result.append(dict(player=person['name'],identity=json.dumps(dict(native_id=r['fm_id'],fifa_id=r['fifa_id'],dob=r['dob']),separators=(',',':')),old_club=clubs.get(r['old_club_id'],r['old_club_id']),new_club=clubs.get(r['new_club_id'],'FREE_AGENT' if r['new_club_id']=='0' else r['new_club_id']),transaction_type=kind,effective_state='CURRENT_2026_27_INPUT',source=r['source'],source_date=r['snapshot_date'],confidence=r['status'],source_sha256=r['source_sha256'],application_status=build['status']))
 creation=a.candidate/'inputs/creation.csv'
 if creation.is_file():
  for r in read(creation):
   result.append(dict(player=r['pseudonym'] or (r['first_name']+' '+r['last_name']).strip(),identity=json.dumps(dict(native_id=r['fm_id'],fifa_id=r['fifa_id'],dob=r['dob'],player_tm_id=r['player_tm_id']),separators=(',',':')),old_club='NOT_IN_NATIVE_DATABASE',new_club=clubs[r['club_id']],transaction_type='PLAYER_CREATED',effective_state='CURRENT_2026_27_INPUT_PROVISIONAL_RATING',source=r['source'],source_date=r['snapshot_date'],confidence=r['status'],source_sha256=r['source_sha256'],application_status=build['status']))
 out=a.candidate/'DELTA_PROVENANCE.csv'
 with out.open('w',encoding='utf-8',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(result[0]));w.writeheader();w.writerows(result)
 print(json.dumps(dict(rows=len(result),output=str(out),source_date_definition='source snapshot date; publication date not inferred')))
if __name__=='__main__':main()
