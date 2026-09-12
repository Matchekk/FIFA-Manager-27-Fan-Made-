"""Generate a guarded Native10 player-creation plan from zero-duplicate reviews."""
from __future__ import annotations
import argparse, csv, hashlib, json, re, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from fm27.common import read_csv, write_csv, write_json, sha256

NATIONS={'Elfenbeinküste':'Cote_d_Ivoire','Ghana':'Ghana','Usbekistan':'Uzbekistan','Senegal':'Senegal',
'Belgien':'Belgium','Tschechien':'Czech_Republic','Japan':'Japan','Serbien':'Serbia','Nigeria':'Nigeria',
'Ukraine':'Ukraine','Gambia':'Gambia','Ägypten':'Egypt','Spanien':'Spain','Frankreich':'France','Brasilien':'Brazil',
'Griechenland':'Greece','England':'England','Niederlande':'Netherlands','Italien':'Italy','Deutschland':'Germany',
'Haiti':'Haiti','Portugal':'Portugal','Mexiko':'Mexico','Marokko':'Morocco','Südkorea':'Korea_Republic',
'Türkei':'Turkey','Guinea':'Guinea','Australien':'Australia','DR Kongo':'DR_Congo','Mali':'Mali'}
NATIONS.update({'Suriname':'Surinam','Kroatien':'Croatia','Kosovo':'Kosovo','Argentinien':'Argentina',
'Kolumbien':'Colombia','Kongo':'Congo','Sambia':'Zambia','Aserbaidschan':'Azerbaijan'})
NATION_ID_OVERRIDES={'Kosovo':207}  # Actual Native08 country207 is Kosovo (verified by native read).
POSITIONS={'Torwart':'GK','Mittelfeld - Zentrales Mittelfeld':'CM','Sturm - Mittelstürmer':'ST',
'Sturm - Rechtsaußen':'RW','Mittelfeld - Offensives Mittelfeld':'AM','Abwehr - Innenverteidiger':'CB',
'Mittelfeld - Defensives Mittelfeld':'DM','Abwehr - Rechter Verteidiger':'RB','Sturm - Hängende Spitze':'CF',
'Sturm - Linksaußen':'LW'}
POSITIONS.update({'Innenverteidiger':'CB','Offensives Mittelfeld':'AM','Zentrales Mittelfeld':'CM',
'Linker Verteidiger':'LB','Linksaußen':'LW','Linkes Mittelfeld':'LM','Mittelstürmer':'ST',
'Defensives Mittelfeld':'DM','Rechter Verteidiger':'RB'})
FIELDS=['fm_id','player_tm_id','fifa_id','first_name','last_name','pseudonym','dob','nationality1','nationality2',
'club_id','joined','contract_until','shirt_number','team_type','position','rating_seed','status','source','source_sha256','snapshot_date']

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--create-ready',nargs='+',type=Path,required=True)
 p.add_argument('--creation-review',nargs='*',type=Path,default=[],help='Verified adult nonmatches with complete profile fields')
 p.add_argument('--rosters',nargs='+',type=Path,required=True);p.add_argument('--native-reread',type=Path,default=ROOT/'data/generated/native08-integrated-20260912-01-reread')
 p.add_argument('--profiles',nargs='*',type=Path,default=[]);p.add_argument('--profile-club-aliases',nargs='*',type=Path,default=[])
 p.add_argument('--output',type=Path,default=ROOT/'data/current/integration/candidate-player-creation-plan.csv')
 p.add_argument('--report',type=Path,default=ROOT/'reports/current/integration/player-creation.json');a=p.parse_args()
 enum=(ROOT/'upstream/fifam/fmapi/FifamNation.h').read_text(encoding='utf-8-sig')
 nation_ids={name:int(num) for num,name in re.findall(r'ENUM_MEMBER\(\s*(\d+),\s*(\w+),',enum)}
 roster={r['player_tm_id']:r for path in a.rosters for r in read_csv(path)}
 profiles={r['player_tm_id']:r for path in a.profiles for r in read_csv(path)}
 affiliation={r['player_tm_id']:r for path in a.profile_club_aliases for r in read_csv(path)}
 native=read_csv(a.native_reread/'native_players.csv');used={int(r['fm_id']) for r in native};next_id=max(used)+1
 ready=[r for path in a.create_ready for r in read_csv(path)]
 for path in a.creation_review:
  for review in read_csv(path):
   if (review.get('disposition')!='CREATE_EVIDENCE_RATING_REQUIRED'
       or review.get('identity_search')!='VERIFIED_NONMATCH' or review.get('profile_complete')!='YES'):
    continue
   ready.append({'player_tm_id':review['player_tm_id'],'player':review['player'],'dob':review['dob'],
    'fifa_id':'0','confidence':'HIGH','eligibility':'ADULT_SCOPED_SQUAD_ZERO_DUPLICATE',
    'nationality':review['nationality'],'position':review['position'],'club_id':review['target_club_id'],
    'contract_joined':review['joined'],'contract_until':review['contract_until'],
    'shirt_number':review['shirt_number'],'source_urls':json.dumps([review['source']]),
    'source_hashes':json.dumps([review['source_sha256']])})
 ready=list({r['player_tm_id']:r for r in ready}.values());plans=[];held=[]
 for r in sorted(ready,key=lambda x:int(x['player_tm_id'])):
  source=roster.get(r['player_tm_id'],{}); labels=r['nationality'].split(); ids=[];i=0
  while i<len(labels):
   label=labels[i]
   if i+1<len(labels) and ' '.join(labels[i:i+2]) in NATIONS: label=' '.join(labels[i:i+2]);i+=1
   mapped=NATIONS.get(label); ids.append(NATION_ID_OVERRIDES.get(label,nation_ids.get(mapped,0)));i+=1
  name=source.get('player',r['player']).strip(); parts=name.split(' ',1); first=parts[0] if len(parts)>1 else '';last=parts[1] if len(parts)>1 else parts[0]
  urls=json.loads(r['source_urls']);hashes=json.loads(r['source_hashes']); raw=ROOT/'data/raw/transfermarkt'/(hashes[0]+'.html')
  profile=profiles.get(r['player_tm_id'],{}); alias=affiliation.get(r['player_tm_id'],{})
  profile_conflict=bool(profile.get('club_tm_id') and profile.get('club_tm_id')!=source.get('club_tm_id'))
  alias_valid=(profile_conflict and alias.get('status')=='CONFIRMED' and alias.get('snapshot_date')=='2026-09-12'
    and alias.get('roster_club_tm_id')==source.get('club_tm_id') and alias.get('profile_club_tm_id')==profile.get('club_tm_id')
    and alias.get('native_club_id')==r.get('club_id') and alias.get('team_type') in {'FIRST','RESERVE'}
    and alias.get('source')==profile.get('source') and alias.get('source_sha256')==profile.get('source_sha256')
    and (ROOT/'data/raw/transfermarkt'/(alias.get('source_sha256','')+'.html')).is_file())
  valid=(r['fifa_id']=='0' and r['confidence']=='HIGH' and r['eligibility']=='ADULT_SCOPED_SQUAD_ZERO_DUPLICATE'
    and len(ids) in {1,2} and all(ids) and r['position'] in POSITIONS and len(first)<=15 and 0<len(last)<=19
    and urls and urls[0].startswith('https://') and raw.is_file() and sha256(raw)==hashes[0]
    and r['club_id'].isdigit() and r['contract_joined'] and r['contract_until'] and (not profile_conflict or alias_valid))
  if not valid:
   held.append({'player_tm_id':r['player_tm_id'],'player':r['player'],'reason':'Native nation/position/name/evidence or employer-affiliation preconditions incomplete'})
   continue
  while next_id in used:next_id+=1
  plans.append(dict(fm_id=next_id,player_tm_id=r['player_tm_id'],fifa_id=0,first_name=first,last_name=last,pseudonym='',dob=r['dob'],
   nationality1=ids[0],nationality2=ids[1] if len(ids)>1 else 0,club_id=r['club_id'],joined=r['contract_joined'],contract_until=r['contract_until'],
   shirt_number=r['shirt_number'] if r['shirt_number'].isdigit() else 0,team_type=alias['team_type'] if alias_valid else 'FIRST',position=POSITIONS[r['position']],rating_seed=45,
   status='CONFIRMED',source=urls[0],source_sha256=hashes[0],snapshot_date='2026-09-12'));used.add(next_id);next_id+=1
 a.output.parent.mkdir(parents=True,exist_ok=True);a.report.parent.mkdir(parents=True,exist_ok=True);write_csv(a.output,FIELDS,plans)
 report={'status':'CANDIDATE_NOT_FROZEN','source_rows':len(ready),'candidate_rows':len(plans),'held_rows':len(held),'held':held,
  'candidate_sha256':sha256(a.output),'fifa_policy':'All created players retain fifa_id=0.',
  'rating_policy':'Deterministic neutral attribute seed 45, talent 3, tactical education 3, zero experience; requires later evidence-based rating review.',
  'history_policy':'New players have no invented historical entries.','production_ready':False}
 write_json(a.report,report);print(json.dumps(report))
if __name__=='__main__':main()
