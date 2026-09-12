"""Run an in-memory native rating experiment with exact attribute/protected-field validation."""
import argparse
import datetime as dt
import json
import statistics
import subprocess
import sys
from collections import Counter,defaultdict
from pathlib import Path

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'src'))
from fm27.common import read_csv,sha256,write_csv,write_json
p=argparse.ArgumentParser()
for name in ('binary','plan','output','report'):
    p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args()
if a.output.exists() or a.report.exists():
    raise ValueError('New native preview outputs required')
manifest=json.loads(a.plan.with_suffix('.manifest.json').read_text(encoding='utf-8'))
if manifest['status']!='UNCALIBRATED_NATIVE_PREVIEW_ONLY_NOT_STAGEABLE' or sha256(a.plan)!=manifest['plan_sha256']:
    raise ValueError('Frozen preview plan required')
for name,digest in manifest['evidence_sha256'].items():
    if sha256(root/name)!=digest: raise ValueError('Preview evidence changed: '+name)
build=json.loads(a.binary.with_suffix('.exe.build.json').read_text(encoding='utf-8-sig'))
tests=json.loads((root/'reports/local/NATIVE_TESTS.json').read_text(encoding='utf-8'))
if (build['status']!='PASS' or tests['status']!='PASS' or tests['tests']<119
        or sha256(a.binary)!=tests['binary_sha256'] or tests['source_sha256']!=build['source_sha256']):
    raise ValueError('Tested native rating build required')
for name,digest in build['source_sha256'].items():
    if sha256(root/name)!=digest: raise ValueError('Native build source changed')
candidate=Path(manifest['candidate'])
inspection_path=next(root/name for name,digest in manifest['evidence_sha256'].items()
    if digest==manifest['inspection_sha256'])
inspection=json.loads(inspection_path.read_text(encoding='utf-8'))
database=candidate/'database'
def inventory():
    return {str(path.relative_to(database)):sha256(path) for path in sorted(database.rglob('*')) if path.is_file()}
if inventory()!=inspection['source_database_sha256']:
    raise ValueError('Rating preview source database changed')
result=subprocess.run([str(a.binary.resolve()),str(database),str(a.output.resolve()),'--preview-ratings',str(a.plan.resolve())],cwd=root)
if result.returncode: raise RuntimeError('Native rating preview failed')
if (a.output/'database').exists() or inventory()!=inspection['source_database_sha256']:
    raise ValueError('Read-only preview wrote a database or source changed')
before_path=a.output/'before-ratings/native_ratings.csv'
after_path=a.output/'native_ratings.csv'
before={r['fm_id']:r for r in read_csv(before_path)}
after={r['fm_id']:r for r in read_csv(after_path)}
plan={r['fm_id']:r for r in read_csv(a.plan)}
if set(before)!=set(after) or len(before)!=inspection['players'] or len(plan)!=manifest['rows']:
    raise ValueError('Preview identity coverage differs')
attribute_fields=list(next(iter(plan.values())))[6:-4]
if len(attribute_fields)!=37: raise ValueError('Unexpected plan attribute scope')
for ident,old in before.items():
    new=after[ident]
    if any(old[k]!=new[k] for k in ('fifa_id','dob','club_id','name','protected_sha256')):
        raise ValueError('Protected native fields changed: '+ident)
    if ident not in plan:
        if old!=new: raise ValueError('Unplanned rating change: '+ident)
    else:
        if old['serialized_sha256']!=plan[ident]['baseline_sha256']:
            raise ValueError('Native preview baseline differs')
        if any(new[field]!=plan[ident][field] for field in attribute_fields):
            raise ValueError('Native preview attributes differ')
cohort={r['fm_id']:r for r in manifest['cohort']}
groups=defaultdict(list)
diff=[]
for ident,entry in cohort.items():
    old,new=before[ident],after[ident]
    level_old,level_new=int(old['level13']),int(new['level13'])
    age=(dt.date(2026,9,8)-dt.date.fromisoformat(entry['dob'])).days/365.2425
    age_group='U18' if age<18 else '18-21' if age<22 else '22-25' if age<26 else '26-29' if age<30 else '30-34' if age<35 else '35+'
    row=dict(fm_id=ident,fifa_id=entry['fifa_id'],name=entry['name'],league=entry['target_league'],
        position=entry['native_position'],source_position=entry['source_position'],age_group=age_group,
        level_before=level_old,level_preview=level_new,level_delta=level_new-level_old,
        max_attribute_delta=max(abs(int(old[f])-int(new[f])) for f in attribute_fields),
        best_style_before=old['best_style'],best_style_preview=new['best_style'],
        style_preserved=old['style']==new['style'])
    diff.append(row)
    for key in (('COHORT','ALL'),('LEAGUE',row['league']),('POSITION',row['position']),('AGE',age_group)):
        groups[key].append((level_old,level_new))
summary=[]
for (category,group),values in sorted(groups.items()):
    old,new=zip(*values)
    summary.append(dict(category=category,group=group,players=len(values),
        mean_before=round(statistics.mean(old),3),mean_preview=round(statistics.mean(new),3),
        median_delta=statistics.median(b-a for a,b in values),maximum_before=max(old),maximum_preview=max(new),
        at85_before=sum(x>=85 for x in old),at85_preview=sum(x>=85 for x in new),
        at90_before=sum(x>=90 for x in old),at90_preview=sum(x>=90 for x in new)))
top={}
for size in (10,50,100,500):
    old=sorted((int(r['level13']) for r in before.values()),reverse=True)[:size]
    new=sorted((int(r['level13']) for r in after.values()),reverse=True)[:size]
    top[str(size)]=dict(mean_before=statistics.mean(old),mean_preview=statistics.mean(new),
        minimum_before=min(old),minimum_preview=min(new),maximum_before=max(old),maximum_preview=max(new))
diff_path=a.output/'RATING_PREVIEW_DIFF.csv'
distribution_path=a.output/'RATING_PREVIEW_DISTRIBUTION.csv'
write_csv(diff_path,list(diff[0]),diff)
write_csv(distribution_path,list(summary[0]),summary)
write_json(a.report,dict(status='NATIVE_PREVIEW_VALIDATED_CALIBRATION_REQUIRED',
    candidate=str(candidate),preview=str(a.output.resolve()),plan_sha256=sha256(a.plan),players=len(after),
    proposed_players=len(plan),source_unchanged=True,protected_fields_unchanged=True,
    exact_proposed_attributes=True,world_top=top,cohort_summary=summary,
    large_level_changes=sum(abs(r['level_delta'])>5 for r in diff),
    largest_changes=sorted(diff,key=lambda r:abs(r['level_delta']),reverse=True)[:30],
    binary_sha256=sha256(a.binary),native_tests=tests,
    files_sha256={str(path.resolve()):sha256(path) for path in
        (a.plan,a.plan.with_suffix('.manifest.json'),before_path,after_path,diff_path,distribution_path,Path(__file__))},
    release_ready=False,ratings_written_to_database=False,
    limitations='Direct detailed attribute substitution is an experiment. Native levels and distribution must be calibrated and reviewed before database staging.'))
print(json.dumps(dict(status='NATIVE_PREVIEW_VALIDATED_CALIBRATION_REQUIRED',players=len(plan),
    large_level_changes=sum(abs(r['level_delta'])>5 for r in diff),cohort=summary[0])))
