"""Recover exact protected starting conditions for the nine current typed holds."""
from __future__ import annotations
import argparse,csv,hashlib,json,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from fm27.common import read_csv,sha256,write_csv,write_json

BASE_FIELDS=['fm_id','fifa_id','dob','old_club_id','new_club_id','joined','contract_until','shirt_number','team_type','status','source','source_sha256','snapshot_date','loan_owner_club_id','loan_end','action','previous_loan_owner_club_id','previous_loan_start','previous_loan_end','previous_loan_buy_option','acquisition_seller_club_id','acquisition_event_key','acquisition_date','acquisition_source','acquisition_source_sha256']
COND_FIELDS=['protected_condition_type']+[f'protected_condition_param{i}' for i in range(5)]

def blocks(database):
 files=sorted((database/'data').glob('CountryData*.sav'))+[database/'Without.sav']
 for path in files:
  if not path.is_file():continue
  data=path.read_bytes()
  for match in re.finditer(rb'%INDEX%PLAYER\r?\n(.*?)%INDEXEND%PLAYER',data,re.S):
   yield path.relative_to(database).as_posix(),match.group(1)

def condition(block):
 lines=block.decode('cp1252').splitlines();hist=lines.index('%INDEX%HIST')
 for index in range(hist-1,15,-1):
  if not lines[index].isdigit():continue
  count=int(lines[index]);values=lines[index+1:hist]
  if len(values)==count and all(len(v.split(','))==6 for v in values):
   return lines,values
 raise ValueError('starting-condition section not found')

def date_from_days(D):
 D=int(D);j=D-1721119;y=(j*4-1)//146097;j=j*4-146097*y-1;x=j//4;j=(x*4+3)//1461;y=100*y+j;x=x*4+3-1461*j;x=(x+4)//4;m=(5*x-3)//153;x=5*x-3-153*m;d=(x+5)//5
 if m<10:m+=3
 else:m-=9;y+=1
 return f'{y:04}-{m:02}-{d:02}'

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--database',type=Path,required=True);p.add_argument('--typed-review',type=Path,required=True);p.add_argument('--before-semantics',type=Path,required=True);p.add_argument('--profiles',nargs='+',type=Path,required=True);p.add_argument('--rosters',nargs='+',type=Path,required=True);p.add_argument('--club-map',type=Path,required=True);p.add_argument('--proof',type=Path,required=True);p.add_argument('--delta',type=Path,required=True);a=p.parse_args()
 holds=[r for r in read_csv(a.typed_review) if r.get('blocker_category')=='NATIVE_CONDITION_TYPE_NOT_EXPORTED']
 before={r['fm_id']:r for r in read_csv(a.before_semantics)};wanted={(before[r['fm_id']]['fifa_id'],r['fm_id']):r for r in holds};profiles={};rosters={}
 for path in a.profiles:
  for r in read_csv(path):profiles[r.get('player_tm_id','')]=r
 for path in a.rosters:
  for r in read_csv(path):rosters[r.get('player_tm_id','')]=r
 clubs=json.loads(a.club_map.read_text(encoding='utf-8'));found={}
 for file,raw in blocks(a.database):
  try:lines,conditions=condition(raw)
  except (ValueError,UnicodeDecodeError):continue
  for key,row in wanted.items():
   fifa_match=(f'FIFAID:{key[0]}' in lines or (len(lines)>15 and lines[15].split(',')[0]==key[0]))
   if fifa_match and lines[4]==profiles.get(row['player_tm_id'],{}).get('dob',''):
    found[row['fm_id']]=(file,raw,conditions)
 proof=[];delta=[]
 for row in holds:
  if row['fm_id'] not in found:raise ValueError('raw condition record missing '+row['fm_id'])
  file,raw,conditions=found[row['fm_id']]
  parsed=[c.split(',') for c in conditions];supported=len(parsed)==1 and parsed[0][0] in {'1','2','7'}
  params=parsed[0][1:] if len(parsed)==1 else ['','','','',''];typ=parsed[0][0] if len(parsed)==1 else ''
  profile=profiles.get(row['player_tm_id'],{});roster=rosters.get(row['player_tm_id'],{});native=before[row['fm_id']]
  owner_tm=profile.get('loan_owner_tm_id','');owner=str(clubs.get(owner_tm,{}).get('club_id','')) if owner_tm else '0'
  loan_end=profile.get('contract_until','') if owner_tm else ''
  source_path=ROOT/'data/raw/transfermarkt'/(profile.get('source_sha256','')+'.html')
  source_ok=(profile.get('source_status')=='CONFIRMED' and profile.get('source_sha256') and
   source_path.is_file() and sha256(source_path)==profile['source_sha256'])
  baseline_ok=(not owner_tm or owner==row['native_club_id'])
  chronology=bool(profile.get('joined') and profile.get('contract_until'))
  safe=supported and source_ok and baseline_ok and chronology and (not owner_tm or owner not in {'','0'} and profile.get('owner_contract_until'))
  hold_reason=('' if safe else 'OWNER_NATIVE_MAPPING_UNPROVEN' if owner_tm and owner in {'','0'} else
   'OWNER_CONTRACT_END_UNPROVEN' if owner_tm and not profile.get('owner_contract_until') else
   'OWNERSHIP_CHAIN_UNPROVEN' if owner_tm and owner!=row['native_club_id'] else 'UNSUPPORTED_OR_INCOMPLETE_SOURCE')
  proof.append({'fm_id':row['fm_id'],'fifa_id':native['fifa_id'],'player':row['player'],'player_tm_id':row['player_tm_id'],'dob':profile.get('dob',''),'raw_file':file,'raw_block_sha256':hashlib.sha256(raw).hexdigest(),'condition_count':str(len(parsed)),'condition_type':typ,'condition_name':{'1':'INJURY','2':'LEAGUE_BAN','7':'BAN_UNTIL'}.get(typ,'UNSUPPORTED'),'param0':params[0],'param1':params[1],'param2':params[2],'param3':params[3],'param4':params[4],'start_date':date_from_days(params[0]) if typ=='1' else '','end_or_until_date':date_from_days(params[1]) if typ in {'1','7'} else '','native_protected_conditions_sha256':row['protected_conditions_sha256'],'source_owner_tm_id':owner_tm,'mapped_owner_club_id':owner,'source_owner_contract_until':profile.get('owner_contract_until',''),'resolution_status':'STAGED_SEPARATE_DELTA' if safe else 'HOLD_OTHER_TYPED_PREREQUISITE','hold_reason':hold_reason})
  if safe:
   shirt=roster.get('shirt_number','');shirt=shirt if shirt.isdigit() else (native['shirt_number_reserve'] if native['in_reserve']=='1' else native['shirt_number_first'])
   d={k:'' for k in BASE_FIELDS+COND_FIELDS};d.update({'fm_id':row['fm_id'],'fifa_id':native['fifa_id'],'dob':profile['dob'],'old_club_id':row['native_club_id'],'new_club_id':row['target_club_id'],'joined':profile['joined'],'contract_until':profile.get('owner_contract_until') if owner_tm else profile['contract_until'],'shirt_number':shirt,'team_type':'FIRST','status':'CONFIRMED','source':profile['source'],'source_sha256':profile['source_sha256'],'snapshot_date':'2026-09-12','loan_owner_club_id':owner,'loan_end':loan_end,'action':'PRESERVE_PROTECTED_SQUAD','previous_loan_owner_club_id':'0','previous_loan_buy_option':'0','acquisition_seller_club_id':'0','protected_condition_type':typ});d.update({f'protected_condition_param{i}':v for i,v in enumerate(params)});delta.append(d)
 write_csv(a.proof,list(proof[0]),proof);write_csv(a.delta,BASE_FIELDS+COND_FIELDS,delta)
 report={'status':'STAGED_NOT_CANONICAL','records':len(proof),'exact_supported_conditions':sum(r['condition_name']!='UNSUPPORTED' for r in proof),'staged_delta_rows':len(delta),'held_rows':len(proof)-len(delta),'condition_counts':{n:sum(r['condition_name']==n for r in proof) for n in ['INJURY','LEAGUE_BAN','BAN_UNTIL']},'proof_sha256':sha256(a.proof),'delta_sha256':sha256(a.delta),'canonical_plan_mutated':False}
 write_json(a.proof.with_suffix('.json'),report);print(json.dumps(report));return 0
if __name__=='__main__':raise SystemExit(main())
