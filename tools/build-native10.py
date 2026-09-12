"""Snapshot guarded current-data plans and build one isolated native candidate.

Draft builds are explicitly incomplete.  A production freeze requires the
integration gate to be ready; this tool never deploys or changes the game.
"""
from __future__ import annotations
import argparse, datetime, hashlib, json, shutil, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'data/generated/release-candidate/native08-integrated-20260912-01'

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def inventory(path): return {str(p.relative_to(path)).replace('\\','/'):sha(p) for p in sorted(path.rglob('*')) if p.is_file()}
def save(path,value): path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--name',required=True)
 p.add_argument('--binary',type=Path,default=ROOT/'build/fm27-db-probe-native10.exe')
 p.add_argument('--squad-plan',type=Path,default=ROOT/'data/current/integration/candidate-squad-plan.csv')
 p.add_argument('--membership-plan',type=Path)
 p.add_argument('--belgium-plan',type=Path)
 p.add_argument('--draft',action='store_true')
 p.add_argument('--snapshot-only',action='store_true')
 a=p.parse_args()
 if not a.name.startswith('native10-') or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-' for c in a.name):
  raise ValueError('Name must be a lowercase native10- leaf name')
 gate_path=ROOT/'reports/current/integration/integration.json'
 gate=json.loads(gate_path.read_text(encoding='utf-8-sig'))
 if not a.draft and not gate.get('freeze_ready'):
  raise ValueError('Production freeze refused: football data coverage gate is incomplete')
 out=ROOT/'data/generated/release-candidate'/a.name
 if out.exists(): raise ValueError('Exclusive new candidate directory required')
 for path in [a.binary,a.squad_plan,a.membership_plan,a.belgium_plan]:
  if path is not None and not path.is_file(): raise ValueError('Missing input: '+str(path))
 out.mkdir(parents=True); inputs=out/'inputs';inputs.mkdir()
 plans={}
 for key,path in [('squad',a.squad_plan),('membership',a.membership_plan),('belgium',a.belgium_plan)]:
  if path is None:continue
  target=inputs/(key+'.csv');shutil.copy2(path,target)
  plans[key]=dict(path=str(target),source=str(path.resolve()),sha256=sha(target))
 shutil.copy2(gate_path,inputs/'integration.json')
 binary=inputs/'native-probe.exe';shutil.copy2(a.binary,binary)
 build_record=Path(str(a.binary)+'.build.json')
 if build_record.is_file():shutil.copy2(build_record,inputs/'native-probe.build.json')
 base_hashes=inventory(BASE/'database');save(inputs/'base-inventory.json',base_hashes)
 manifest=dict(schema=1,name=a.name,created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
  status='DRAFT_INPUT_SNAPSHOT' if a.draft else 'FROZEN_INPUT_SNAPSHOT',production_frozen=not a.draft,
  base=str(BASE),base_inventory_sha256=sha(inputs/'base-inventory.json'),plans=plans,
  binary_sha256=sha(binary),integration_sha256=sha(inputs/'integration.json'),
  runtime_smoke='NOT_RUN',original_install_modified=False,write='NOT_RUN',reread='NOT_RUN',semantic_diff='NOT_RUN')
 save(out/'BUILD.json',manifest)
 if a.snapshot_only:print(json.dumps(dict(output=str(out),status=manifest['status'])));return
 def run(args,log):
  with log.open('w',encoding='utf-8') as stream:
   result=subprocess.run([str(x) for x in args],cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT)
  if result.returncode:raise RuntimeError('Native operation failed; see '+str(log))
 try:
  run([binary,BASE/'database',out/'before'],out/'before.log')
  run([binary,BASE/'database',out/'write','--stage-current-build',plans['squad']['path'],
       plans.get('membership',{}).get('path','-'),plans.get('belgium',{}).get('path','-')],out/'write.log')
  manifest['write']='PASS';save(out/'BUILD.json',manifest)
  run([binary,out/'write/database',out/'reread'],out/'reread.log')
  manifest['reread']='PASS'
  if inventory(BASE/'database')!=base_hashes:raise RuntimeError('Accepted base changed during build')
  manifest['base_preserved']=True
  diff=[sys.executable,ROOT/'tools/native10-semantic-diff.py','--before',out/'before','--after',out/'reread',
        '--squad-plan',plans['squad']['path'],'--output',out/'semantic-diff.json']
  if 'membership' in plans:diff.extend(['--membership-plan',plans['membership']['path']])
  run(diff,out/'semantic-diff.log')
  manifest['semantic_diff']='PASS'
  manifest['status']='DRAFT_VALIDATED_DATA_INCOMPLETE' if a.draft else 'NATIVE_VALIDATED_RUNTIME_SMOKE_PENDING'
  if (BASE/'overlay').is_dir():shutil.copytree(BASE/'overlay',out/'overlay')
 except Exception as exc:
  manifest['status']='FAILED';manifest['error']=str(exc);save(out/'BUILD.json',manifest);raise
 save(out/'BUILD.json',manifest)
 print(json.dumps(dict(output=str(out),status=manifest['status'],write=manifest['write'],reread=manifest['reread'],semantic_diff=manifest['semantic_diff'])))
if __name__=='__main__':main()
