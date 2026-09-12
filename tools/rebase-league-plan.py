"""Carry a proven membership plan onto a validated transfer database with identical league baselines."""
import argparse
import json
import sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'src'))
from fm27.common import sha256,write_json
p=argparse.ArgumentParser()
p.add_argument('--plan',type=Path,required=True)
p.add_argument('--transfer-validation',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args()
target_manifest=a.output.with_suffix('.manifest.json')
if a.output.exists() or target_manifest.exists():
    raise ValueError('New rebased plan required')
old_manifest_path=a.plan.with_suffix('.manifest.json')
old=json.loads(old_manifest_path.read_text(encoding='utf-8'))
proof=json.loads(a.transfer_validation.read_text(encoding='utf-8'))
if old['status']!='FROZEN_PARTIAL_LEAGUE_MEMBERSHIP_NOT_RELEASE' or sha256(a.plan)!=old['plan_sha256']:
    raise ValueError('Original league plan not frozen')
if (proof['status']!='INCOMPLETE' or proof['snapshot_date']!=old['snapshot_date']
        or any(proof[k]!='PASS' for k in ('player_validation','extended_native_validation','native_support_validation'))
        or proof['expanded_world_validation']['status']!='PASS' or proof['gates']['I_AUTOMATED_TESTS']!='PASS'):
    raise ValueError('Transfer database lacks completed native validation')
candidate=Path(proof['candidate'])
database=candidate/'database'
for name,digest in proof['candidate_database_files'].items():
    if sha256(candidate/name)!=digest:
        raise ValueError('Validated transfer candidate changed: '+name)
previous=Path(old['source_database'])
for name,digest in old['source_database_sha256'].items():
    if sha256(previous/name)!=digest:
        raise ValueError('Previous league baseline changed')
def scripts(folder):
    return {str(p.relative_to(folder/'script')):sha256(p) for p in sorted((folder/'script').rglob('*')) if p.is_file()}
old_scripts,new_scripts=scripts(previous),scripts(database)
if not old_scripts or old_scripts!=new_scripts:
    raise ValueError('Competition scripts changed; a fresh membership review is required')
old_sem=previous.parent/'native_competition_semantics.csv'
new_sem=candidate/'native_competition_semantics.csv'
if sha256(old_sem)!=sha256(new_sem):
    raise ValueError('Native competition semantics changed')
evidence=dict(old['evidence_sha256'])
for name,digest in evidence.items():
    if sha256(root/name)!=digest:
        raise ValueError('League evidence changed: '+name)
for path in (a.plan,old_manifest_path,a.transfer_validation,old_sem,new_sem,Path(__file__)):
    resolved=path.resolve()
    if not resolved.is_relative_to(root):
        raise ValueError('Rebase evidence must stay inside project')
    evidence[str(resolved.relative_to(root))]=sha256(resolved)
inventory={str(p.relative_to(database)):sha256(p) for p in sorted(database.rglob('*')) if p.is_file()}
validated={}
for name,digest in proof['candidate_database_files'].items():
    normalized=name.replace('\\','/')
    if normalized in validated and validated[normalized]!=digest:
        raise ValueError('Conflicting validation paths')
    validated[normalized]=digest
if any(validated.get('database/'+name.replace('\\','/'))!=digest for name,digest in inventory.items()):
    raise ValueError('New source has unvalidated database files')
a.output.write_bytes(a.plan.read_bytes())
write_json(target_manifest,{**old,'source_database':str(database),'source_database_sha256':inventory,
    'evidence_sha256':evidence,'rebase':dict(status='IDENTICAL_NATIVE_COMPETITION_BASELINE',
        original_manifest_sha256=sha256(old_manifest_path),transfer_validation_sha256=sha256(a.transfer_validation),
        transfer_plan_sha256=proof['plan_sha256'],identical_script_files=len(old_scripts),
        native_competition_semantics_sha256=sha256(new_sem)),
    'limitations':old['limitations']+' Rebased onto a separately validated transfer database; the combined write/reread must still be validated.'})
print(json.dumps(dict(plan_sha256=sha256(a.output),source_database=str(database),identical_scripts=len(old_scripts))))
