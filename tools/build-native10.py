"""Snapshot guarded current-data plans and build one isolated native candidate.

Draft builds are explicitly incomplete.  A production freeze requires the
integration gate to be ready; this tool never deploys or changes the game.
"""
from __future__ import annotations
import argparse, datetime, hashlib, json, os, shutil, subprocess, sys
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
 p.add_argument('--creation-plan',type=Path)
 p.add_argument('--germany-plan',type=Path)
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
 for path in [a.binary,a.squad_plan,a.membership_plan,a.belgium_plan,a.creation_plan,a.germany_plan]:
  if path is not None and not path.is_file(): raise ValueError('Missing input: '+str(path))
 out.mkdir(parents=True); inputs=out/'inputs';inputs.mkdir()
 plans={}
 for key,path in [('squad',a.squad_plan),('membership',a.membership_plan),('belgium',a.belgium_plan),('creation',a.creation_plan),('germany',a.germany_plan)]:
  if path is None:continue
  target=inputs/(key+'.csv');shutil.copy2(path,target)
  plans[key]=dict(path=str(target),source=str(path.resolve()),sha256=sha(target))
  evidence=path.with_suffix('.manifest.json')
  if evidence.is_file():
   shutil.copy2(evidence,inputs/(key+'.manifest.json'));plans[key]['manifest_sha256']=sha(evidence)
 shutil.copy2(gate_path,inputs/'integration.json')
 # Exact native guard provenance accompanies the embedded per-player guards.
 for name in ['native08-loan-preconditions.csv','native08-loan-preconditions.json']:
  evidence=ROOT/'data/current/integration'/name
  if evidence.is_file():shutil.copy2(evidence,inputs/name)
 binary=inputs/'native-probe.exe';shutil.copy2(a.binary,binary)
 validators={}
 for name in ['native10-semantic-diff.py','current-membership-audit.py']:
  target=inputs/name;shutil.copy2(ROOT/'tools'/name,target)
  validators[name]=dict(path=str(target),sha256=sha(target))
 shutil.copy2(ROOT/'data/current/league-membership-2026-27.integration.csv',inputs/'expected-membership.csv')
 package=inputs/'python/fm27';package.mkdir(parents=True)
 (package/'__init__.py').write_text('',encoding='utf-8')
 shutil.copy2(ROOT/'src/fm27/common.py',package/'common.py')
 build_record=Path(str(a.binary)+'.build.json')
 if build_record.is_file():shutil.copy2(build_record,inputs/'native-probe.build.json')
 base_hashes=inventory(BASE/'database');save(inputs/'base-inventory.json',base_hashes)
 manifest=dict(schema=1,name=a.name,created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
  status='DRAFT_INPUT_SNAPSHOT' if a.draft else 'FROZEN_INPUT_SNAPSHOT',production_frozen=not a.draft,
  base=str(BASE),base_inventory_sha256=sha(inputs/'base-inventory.json'),plans=plans,
  binary_sha256=sha(binary),validators=validators,
  validator_common_sha256=sha(package/'common.py'),expected_membership_sha256=sha(inputs/'expected-membership.csv'),
  integration_sha256=sha(inputs/'integration.json'),
  runtime_smoke='NOT_RUN',original_install_modified=False,write='NOT_RUN',reread='NOT_RUN',semantic_diff='NOT_RUN')
 save(out/'BUILD.json',manifest)
 if a.snapshot_only:print(json.dumps(dict(output=str(out),status=manifest['status'])));return
 def run(args,log):
  with log.open('w',encoding='utf-8') as stream:
   environment=os.environ.copy();environment['PYTHONPATH']=str(inputs/'python')
   result=subprocess.run([str(x) for x in args],cwd=ROOT,env=environment,stdout=stream,stderr=subprocess.STDOUT)
  if result.returncode:raise RuntimeError('Native operation failed; see '+str(log))
 phase='write'
 try:
  stage=[binary,BASE/'database',out/'write','--stage-current-build',plans['squad']['path'],
       plans.get('membership',{}).get('path','-'),plans.get('belgium',{}).get('path','-')]
  if 'creation' in plans or 'germany' in plans:stage.append(plans.get('creation',{}).get('path','-'))
  if 'germany' in plans:stage.append(plans['germany']['path'])
  # The native process exports its untouched object to write/before, applies
  # the frozen plans, then writes. The result is reread in a separate process.
  run(stage,out/'write.log')
  manifest['write']='PASS';save(out/'BUILD.json',manifest)
  phase='reread'
  run([binary,out/'write/database',out/'reread'],out/'reread.log')
  manifest['reread']='PASS'
  if inventory(BASE/'database')!=base_hashes:raise RuntimeError('Accepted base changed during build')
  manifest['base_preserved']=True
  phase='semantic_diff'
  diff=[sys.executable,inputs/'native10-semantic-diff.py','--before',out/'write/before','--after',out/'reread',
        '--squad-plan',plans['squad']['path'],'--output',out/'semantic-diff.json']
  if 'membership' in plans:diff.extend(['--membership-plan',plans['membership']['path']])
  if 'belgium' in plans:diff.extend(['--belgium-plan',plans['belgium']['path']])
  if 'creation' in plans:diff.extend(['--creation-plan',plans['creation']['path']])
  if 'germany' in plans:diff.extend(['--germany-plan',plans['germany']['path']])
  run(diff,out/'semantic-diff.log')
  manifest['semantic_diff']='PASS'
  phase='membership'
  run([sys.executable,inputs/'current-membership-audit.py','--inspection',out/'reread',
       '--source',inputs/'expected-membership.csv','--output',out/'membership-validation.json'],out/'membership-validation.log')
  membership_result=json.loads((out/'membership-validation.json').read_text(encoding='utf-8'))
  manifest['membership']=membership_result['status']
  if (not a.draft or ('belgium' in plans and 'germany' in plans)) and membership_result['status']!='PASS':
   raise RuntimeError('Integrated target membership validation failed')
  manifest['status']='DRAFT_VALIDATED_DATA_INCOMPLETE' if a.draft else 'NATIVE_VALIDATED_RUNTIME_SMOKE_PENDING'
  if (BASE/'overlay').is_dir():shutil.copytree(BASE/'overlay',out/'overlay')
 except Exception as exc:
  manifest['status']='FAILED';manifest[phase]='FAIL';manifest['failed_phase']=phase
  manifest['error']=str(exc);save(out/'BUILD.json',manifest);raise
 save(out/'BUILD.json',manifest)
 print(json.dumps(dict(output=str(out),status=manifest['status'],write=manifest['write'],reread=manifest['reread'],semantic_diff=manifest['semantic_diff'])))
if __name__=='__main__':main()
