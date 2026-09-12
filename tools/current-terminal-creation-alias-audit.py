"""Resolve terminal creation holds only when cached evidence proves one Native08 alias."""
from __future__ import annotations
import argparse, csv, hashlib, json, re, runpy, sys, unicodedata
from difflib import SequenceMatcher
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from fm27.common import read_csv,sha256,write_csv,write_json

def norm(s): return ''.join(c for c in unicodedata.normalize('NFKD',s).casefold() if c.isalnum())
def plausible(a,b):
 at=[norm(x) for x in re.split(r"[\s\-']+",a) if norm(x)];bt=[norm(x) for x in re.split(r"[\s\-']+",b) if norm(x)]
 if not at or not bt:return False,0
 score=SequenceMatcher(None,''.join(at),''.join(bt)).ratio()
 return (at[-1]==bt[-1] or any(x and x in bt for x in at) or score>=.70),score
def source_ok(url,digest):
 p=ROOT/'data/raw/transfermarkt'/(digest+'.html')
 return url.startswith('https://') and re.fullmatch('[0-9a-f]{64}',digest or '') and p.is_file() and sha256(p)==digest

def profile_nations(text):
 module=runpy.run_path(str(ROOT/'tools/current-native10-create.py')); names=module['NATIONS'];overrides=module['NATION_ID_OVERRIDES']
 enum=(ROOT/'upstream/fifam/fmapi/FifamNation.h').read_text(encoding='utf-8-sig')
 enum_ids={name:num for num,name in re.findall(r'ENUM_MEMBER\(\s*(\d+),\s*(\w+),',enum)}
 labels=text.split();result=set();i=0
 while i<len(labels):
  label=labels[i]
  if i+1<len(labels) and ' '.join(labels[i:i+2]) in names:label=' '.join(labels[i:i+2]);i+=1
  mapped=names.get(label);value=overrides.get(label,enum_ids.get(mapped,''));
  if value!='':result.add(str(value))
  i+=1
 return result

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--queue',type=Path,required=True);p.add_argument('--native-rich',type=Path,required=True)
 p.add_argument('--profiles',nargs='+',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--bridges',type=Path,required=True);a=p.parse_args()
 native={r['fm_id']:r for r in read_csv(a.native_rich)};profiles={}
 for path in a.profiles:
  for r in read_csv(path):profiles[r.get('player_tm_id','')]=r
 audited=[];bridges=[]
 for q in read_csv(a.queue):
  if q.get('queue')!='PLAYER_CREATION':continue
  refs=re.findall(r'candidate (\d+)',q.get('required_evidence_or_decision',''),re.I); prof=profiles.get(q['player_tm_id'],{})
  candidates=[]
  for ident in refs:
   n=native.get(ident,{})
   names=[q.get('player',''),prof.get('full_name',''),prof.get('player','')]
   matches=[plausible(name,n.get('common_name') or n.get('name','')) for name in names if name]
   ok_name=any(v[0] for v in matches);score=max((v[1] for v in matches),default=0)
   exact=(n and n.get('dob')==q.get('dob') and n.get('club_id')==q.get('target_club_id')
          and n.get('nationality') in profile_nations(prof.get('nationality_text',''))
          and prof.get('dob')==q.get('dob') and source_ok(prof.get('source',''),prof.get('source_sha256',''))
          and source_ok(q.get('source',''),q.get('source_sha256','')) and ok_name)
   candidates.append((n,score,exact))
  valid=[v for v in candidates if v[2]]
  decision='BRIDGE_EXISTING_NATIVE08' if len(valid)==1 else 'HOLD_IDENTITY_REVIEW'
  chosen=valid[0] if len(valid)==1 else ({},0,False)
  n,score,_=chosen
  audited.append({'player_tm_id':q['player_tm_id'],'player':q['player'],'dob':q['dob'],'profile_full_name':prof.get('full_name',''),
   'profile_nationality':prof.get('nationality_text',''),'candidate_fm_id':n.get('fm_id',''),'candidate_fifa_id':n.get('fifa_id',''),
   'candidate_name':n.get('name',''),'candidate_common_name':n.get('common_name',''),'candidate_nationality_id':n.get('nationality',''),
   'candidate_club_id':n.get('club_id',''),'target_club_id':q.get('target_club_id',''),'name_similarity':f'{score:.4f}',
   'decision':decision,'reason':'Unique same-DOB/current-club alias with cached roster and profile evidence' if len(valid)==1 else 'No unique fully bound Native08 alias',
   'profile_source':prof.get('source',''),'profile_source_sha256':prof.get('source_sha256',''),'roster_source':q.get('source',''),'roster_source_sha256':q.get('source_sha256',''),'snapshot_date':q.get('snapshot_date','')})
  if len(valid)==1:
   bridges.append({'player_tm_id':q['player_tm_id'],'fm_id':n['fm_id'],'fifa_id':n['fifa_id'],'dob':q['dob'],'status':'CONFIRMED','identity_method':'CACHED_PROFILE_NATIVE08_ALIAS','source':prof['source'],'source_sha256':prof['source_sha256'],'snapshot_date':q['snapshot_date']})
 fields=list(audited[0]);write_csv(a.output,fields,audited);write_csv(a.bridges,list(bridges[0]) if bridges else ['player_tm_id','fm_id'],bridges)
 rep={'status':'CANDIDATE_NOT_FROZEN','queue_rows':len(audited),'bridged_rows':len(bridges),'held_rows':len(audited)-len(bridges),'audit_sha256':sha256(a.output),'bridges_sha256':sha256(a.bridges),'production_ready':False}
 write_json(a.output.with_suffix('.json'),rep);print(json.dumps(rep));return 0
if __name__=='__main__':raise SystemExit(main())
