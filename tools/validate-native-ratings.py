"""Validate exact rating mutations, protected fields and the entire native world roundtrip."""
import argparse
import datetime as dt
import json
import sys
from collections import Counter
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'src'))
from fm27.common import read_csv,sha256,write_json
from fm27.world_validation import compare_world,compare_global
p=argparse.ArgumentParser()
for name in ('plan','candidate','reread','output'):
    p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args()
if a.output.exists(): raise ValueError('New rating validation report required')
manifest=json.loads(a.plan.with_suffix('.manifest.json').read_text(encoding='utf-8'))
stage=json.loads((a.candidate/'NATIVE_BUILD_INPUTS.json').read_text(encoding='utf-8'))
if (stage['status']!='NATIVE_RATING_STAGE_WRITTEN_NOT_VALIDATED' or not stage['source_unchanged']
        or stage['plan']!=manifest or sha256(a.plan)!=manifest['plan_sha256']
        or Path(stage['candidate']).resolve()!=a.candidate.resolve()):
    raise ValueError('Native rating stage does not bind this plan')
source=Path(stage['source_candidate'])
before_folder=a.candidate/'before-ratings'
bound={}
def rows(path):
    bound[str(path.resolve())]=sha256(path)
    return read_csv(path)
def read_json(path):
    bound[str(path.resolve())]=sha256(path)
    return json.loads(path.read_text(encoding='utf-8'))
before_rows=rows(before_folder/'native_ratings.csv')
after_rows=rows(a.candidate/'native_ratings.csv')
reread_rows=rows(a.reread/'native_ratings.csv')
before={r['fm_id']:r for r in before_rows}
after={r['fm_id']:r for r in after_rows}
planned=rows(a.plan); plan={r['fm_id']:r for r in planned}
if (len(before)!=len(before_rows) or len(after)!=len(after_rows) or len(plan)!=len(planned)
        or set(before)!=set(after) or not set(plan)<=set(before)):
    raise ValueError('Rating player IDs or coverage differ')
fields=list(planned[0])[6:-4]
if len(fields)!=37: raise ValueError('Rating attribute schema differs')
checks={};errors=[];changed=0
for ident,old in before.items():
    new=after[ident]
    if any(old[k]!=new[k] for k in ('fifa_id','dob','club_id','name','protected_sha256')):
        errors.append('Protected fields: '+ident)
    if ident not in plan:
        if old!=new: errors.append('Unplanned rating: '+ident)
    else:
        row=plan[ident]
        if old['serialized_sha256']!=row['baseline_sha256']: errors.append('Baseline hash: '+ident)
        if any(new[f]!=row[f] for f in fields): errors.append('Planned attributes: '+ident)
        if new['level13']!=row['expected_level13']: errors.append('Native expected level: '+ident)
        if old['serialized_sha256']==new['serialized_sha256']: errors.append('No-op planned rating: '+ident)
        changed+=sum(old[f]!=new[f] for f in fields)
checks['exact_rating_mutation_scope']=dict(status='FAIL' if errors else 'PASS',planned_players=len(plan),
    changed_attributes=changed,protected_players=len(before),errors=errors[:30])
def equal(name,left,right):
    checks[name]=dict(status='PASS' if left and left==right else 'FAIL',expected=sum(left.values()),actual=sum(right.values()),
        missing=sum((left-right).values()),added=sum((right-left).values()))
def records(folder,filename,columns):
    return Counter(tuple(r[f] for f in columns) for r in rows(folder/filename))
rating_columns=[k for k in after_rows[0] if k!='fm_id']
equal('all_rating_fields_and_levels_roundtrip',Counter(tuple(r[k] for k in rating_columns) for r in after_rows),
    Counter(tuple(r[k] for k in rating_columns) for r in reread_rows))
player_fields=('fifa_id','dob','name','club_id','serialized_sha256')
equal('source_player_baseline',records(source,'native_player_semantics.csv',player_fields),
    records(before_folder,'native_player_semantics.csv',player_fields))
equal('player_semantics_roundtrip',records(a.candidate,'native_player_semantics.csv',player_fields),
    records(a.reread,'native_player_semantics.csv',player_fields))
for name,filename,columns in (
    ('staff','native_staff_semantics.csv',('dob','name','club_id','serialized_sha256')),
    ('competitions','native_competition_semantics.csv',('competition_id','serialized_sha256'))):
    baseline=records(before_folder,filename,columns)
    written=records(a.candidate,filename,columns)
    equal(name+'_source_baseline',records(source,filename,columns),baseline)
    equal(name+'_unchanged',baseline,written)
    equal(name+'_roundtrip',written,records(a.reread,filename,columns))
# Rating changes alter canonical person hashes used as link keys. Translate
# exactly through the verified same-person before/after mapping, never drop links.
key_map={}
old_keys=set()
for ident,old in before.items():
    old_key=old['serialized_sha256']+'@'+old['club_id']
    new_key=after[ident]['serialized_sha256']+'@'+after[ident]['club_id']
    if new_key in key_map or old_key in old_keys: raise ValueError('Ambiguous canonical player link identity')
    key_map[new_key]=old_key;old_keys.add(old_key)
def relationships(folder,translate=False):
    result=Counter()
    for row in rows(folder/'native_player_relations.csv'):
        left,right=row['from_key'],row['to_key']
        if translate: left,right=key_map[left],key_map[right]
        result[(row['relation'],left,right)]+=1
    return result
equal('relationships_source_baseline',relationships(source),relationships(before_folder))
equal('relationships_unchanged',relationships(before_folder),relationships(a.candidate,True))
equal('relationships_roundtrip',relationships(a.candidate),relationships(a.reread))
for folder in (before_folder,a.candidate,a.reread):
    metadata=read_json(folder/'NATIVE_EXTENDED_SEMANTICS.json')
    if metadata.get('relation_errors')!=0 or metadata.get('player_key_collisions')!=0:
        raise ValueError('Invalid native player relationships')
def world_links(folder,translate=False):
    result=Counter()
    for row in rows(folder/'native_world_person_links.csv'):
        key=row['person_key']
        if translate and key.startswith('PLAYER:'): key='PLAYER:'+key_map[key[7:]]
        result[(row['kind'],row['owner_id'],row['slot'],key)]+=1
    return result
equal('world_person_links_unchanged',world_links(before_folder),world_links(a.candidate,True))
checks['world_source_baseline']=compare_world(source,before_folder)
checks['world_metadata_unchanged']=compare_world(before_folder,a.candidate,metadata_only=True)
checks['world_roundtrip']=compare_world(a.candidate,a.reread)
checks['global_source_baseline']=compare_global(source,before_folder)
checks['global_unchanged']=compare_global(before_folder,a.candidate)
checks['global_roundtrip']=compare_global(a.candidate,a.reread)
scripts=lambda folder:{str(path.relative_to(folder/'database/script')):sha256(path)
    for path in sorted((folder/'database/script').rglob('*')) if path.is_file()}
checks['all_competition_scripts_unchanged']=dict(status='PASS' if scripts(source)==scripts(a.candidate) and scripts(source) else 'FAIL',
    script_files=len(scripts(source)))
# Bind all semantic evidence consumed inside the world/global comparison helpers.
for folder in (source,before_folder,a.candidate,a.reread):
    for pattern in ('native_*.csv','NATIVE_*SEMANTICS.json'):
        for path in folder.glob(pattern): bound[str(path.resolve())]=sha256(path)
for path in (a.plan,a.plan.with_suffix('.manifest.json'),a.candidate/'NATIVE_BUILD_INPUTS.json',Path(__file__)):
    bound[str(path.resolve())]=sha256(path)
passed=all(value['status']=='PASS' for value in checks.values())
write_json(a.output,dict(status='NATIVE_RATINGS_PASS_GAME_GATES_OPEN' if passed else 'FAIL',
    validated_at=dt.datetime.now(dt.timezone.utc).isoformat(),candidate=str(a.candidate.resolve()),
    source_candidate=str(source),reread=str(a.reread.resolve()),plan_sha256=sha256(a.plan),
    changed_players=len(plan),changed_attributes=changed,checks=checks,bound_files_sha256=bound,
    candidate_database_files_sha256={str(path.relative_to(a.candidate/'database')):sha256(path)
        for path in sorted((a.candidate/'database').rglob('*')) if path.is_file()},
    release_ready=False,limitations='Native rating mutation scope and world roundtrip only. Support-file audit, rating review holds, full league formats, editor export and game/release gates remain separate.'))
print(json.dumps(dict(status='PASS' if passed else 'FAIL',changed_players=len(plan),changed_attributes=changed,
    failed_checks=[name for name,value in checks.items() if value['status']!='PASS'])))
sys.exit(not passed)
