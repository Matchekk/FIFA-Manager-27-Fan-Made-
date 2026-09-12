"""Fit a positional native scale on training identities and select bounded native-evaluated profiles."""
import argparse
import datetime as dt
import json
import statistics
import sys
from collections import Counter,defaultdict
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'src'))
from fm27.common import read_csv,sha256,write_csv,write_json
from fm27.rating_calibration import family,holdout,fit_native_scale,calibrated_level,attributes_for_variant
p=argparse.ArgumentParser()
for name in ('alternatives-report','preview-report','plan','output'):
    p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args()
target_manifest=a.output.with_suffix('.manifest.json')
if a.output.exists() or target_manifest.exists(): raise ValueError('New calibrated plan required')
alt=json.loads(a.alternatives_report.read_text(encoding='utf-8'))
preview=json.loads(a.preview_report.read_text(encoding='utf-8'))
manifest=json.loads(a.plan.with_suffix('.manifest.json').read_text(encoding='utf-8'))
if (alt['status']!='NATIVE_CALIBRATION_ALTERNATIVES_PASS'
        or alt['preview_report_sha256']!=sha256(a.preview_report)
        or alt['plan_sha256']!=sha256(a.plan) or manifest['plan_sha256']!=sha256(a.plan)):
    raise ValueError('Bound full-world and batch-native evidence required')
alt_path=Path(alt['alternatives_path'])
if sha256(alt_path)!=alt['alternatives_sha256']: raise ValueError('Native alternatives changed')
for name,digest in preview['files_sha256'].items():
    if sha256(Path(name))!=digest: raise ValueError('Native preview changed')
for name,digest in manifest['evidence_sha256'].items():
    if sha256(root/name)!=digest: raise ValueError('Rating source evidence changed')
source_plan={r['fm_id']:r for r in read_csv(a.plan)}
cohort={r['fm_id']:r for r in manifest['cohort']}
before_path=Path(preview['preview'])/'before-ratings/native_ratings.csv'
before={r['fm_id']:r for r in read_csv(before_path)}
diff_path=Path(preview['preview'])/'RATING_PREVIEW_DIFF.csv'
diff={r['fm_id']:r for r in read_csv(diff_path)}
alternatives=defaultdict(list)
direct={}
for row in read_csv(alt_path):
    if row['variant']=='DIRECT': direct[row['fm_id']]=int(row['level13'])
    elif row['source_percent']=='75': alternatives[row['fm_id']].append(row)
training=defaultdict(list); training_ids=defaultdict(list)
for ident,entry in cohort.items():
    birthday=dt.date.fromisoformat(entry['dob']); snapshot=dt.date(2026,9,8)
    age=snapshot.year-birthday.year-((snapshot.month,snapshot.day)<(birthday.month,birthday.day))
    role=family(entry['native_position'])
    # Mature, position-consistent identities calibrate the scale. Large source
    # disagreements are not silently treated as stable calibration anchors.
    if (not holdout(entry['fifa_id']) and age>=22 and role==family(entry['source_position'])
            and abs(direct[ident]-int(before[ident]['level13']))<=8):
        training[role].append((direct[ident],int(before[ident]['level13'])))
        training_ids[role].append(entry['fifa_id'])
models={role:fit_native_scale(pairs) for role,pairs in training.items()}
required={family(r['native_position']) for r in cohort.values()}
if set(models)!=required: raise ValueError('Uncovered positional calibration family')
fields=list(next(iter(source_plan.values())))[6:-4]
chosen_rows=[]; diagnostics=[]; holds=[]
selected_levels={}
for ident,entry in cohort.items():
    old=before[ident]; original=source_plan[ident]
    role=family(entry['native_position'])
    target=calibrated_level(models[role],direct[ident])
    best=min(alternatives[ident],key=lambda r:(abs(int(r['level13'])-target),abs(int(r['offset'])),int(r['source_squared_distance'])))
    level=int(best['level13']); previous=int(old['level13'])
    old_attributes={f:int(old[f]) for f in fields}; source_attributes={f:int(original[f]) for f in fields}
    attributes=attributes_for_variant(old_attributes,source_attributes,75,int(best['offset']))
    deltas=[abs(attributes[f]-old_attributes[f]) for f in fields]
    if (max(deltas)!=int(best['max_attribute_delta'])
            or sum(d>0 for d in deltas)!=int(best['changed_attributes'])
            or sum((attributes[f]-source_attributes[f])**2 for f in fields)!=int(best['source_squared_distance'])):
        raise ValueError('Materialized attributes disagree with native grid')
    reasons=[]
    if role!=family(entry['source_position']): reasons.append('POSITION_FAMILY_REVIEW')
    if max(abs(source_attributes[f]-old_attributes[f]) for f in fields)>35: reasons.append('EXTREME_SOURCE_PROFILE_REVIEW')
    if abs(level-previous)>6: reasons.append('LARGE_LEVEL_CHANGE_REVIEW')
    if abs(level-target)>1: reasons.append('TARGET_NOT_REACHABLE_WITH_PROFILE_LIMITS')
    if not any(deltas): reasons.append('NO_ATTRIBUTE_CHANGE')
    item=dict(fm_id=ident,fifa_id=entry['fifa_id'],name=entry['name'],league=entry['target_league'],
        family=role,position=entry['native_position'],source_position=entry['source_position'],
        holdout=holdout(entry['fifa_id']),level_before=previous,level_direct=direct[ident],
        target_level=round(target,3),selected_level=level,level_delta=level-previous,
        source_percent=75,offset=int(best['offset']),max_attribute_delta=max(deltas),reasons=reasons)
    diagnostics.append(item)
    if reasons: holds.append(item);continue
    chosen_rows.append({**original,'expected_level13':str(level),**{f:str(v) for f,v in attributes.items()}})
    selected_levels[ident]=level
if not chosen_rows: raise ValueError('No calibrated rating proposals survived review')
holdout_checks={}
for role in sorted(models):
    items=[r for r in diagnostics if r['family']==role and r['holdout'] and not r['reasons']]
    shifts=[r['level_delta'] for r in items]
    passed=len(items)>=20 and abs(statistics.mean(shifts))<=2 and abs(statistics.median(shifts))<=1.5
    holdout_checks[role]=dict(status='PASS' if passed else 'REVIEW_REQUIRED',players=len(items),
        mean_shift=round(statistics.mean(shifts),3) if shifts else None,median_shift=statistics.median(shifts) if shifts else None,
        note='Checks scale drift on held-out identities, not correctness of individual football performance ratings.')
league_checks={}
for league in sorted({r['target_league'] for r in cohort.values()}):
    ids=[ident for ident,r in cohort.items() if r['target_league']==league]
    old=[int(before[i]['level13']) for i in ids]
    new=[selected_levels.get(i,int(before[i]['level13'])) for i in ids]
    shift=statistics.mean(new)-statistics.mean(old)
    league_checks[league]=dict(status='PASS' if abs(shift)<=2 else 'REVIEW_REQUIRED',players=len(ids),
        mean_before=round(statistics.mean(old),3),mean_after=round(statistics.mean(new),3),mean_shift=round(shift,3),
        maximum_before=max(old),maximum_after=max(new))
world_before=sorted((int(r['level13']) for r in before.values()),reverse=True)
world_after=sorted((selected_levels.get(i,int(r['level13'])) for i,r in before.items()),reverse=True)
world={str(size):dict(mean_before=statistics.mean(world_before[:size]),mean_after=statistics.mean(world_after[:size]),
    maximum_before=world_before[0],maximum_after=world_after[0]) for size in (10,50,100,500)}
old85=sum(x>=85 for x in world_before);new85=sum(x>=85 for x in world_after)
old90=sum(x>=90 for x in world_before);new90=sum(x>=90 for x in world_after)
inflation=dict(status='PASS' if new85<=max(old85+25,int(old85*1.25)) and new90<=old90+10
    and world_after[0]<=world_before[0]+1 else 'REVIEW_REQUIRED',at85_before=old85,at85_after=new85,
    at90_before=old90,at90_after=new90,world_top=world)
passed=all(r['status']=='PASS' for r in (*holdout_checks.values(),*league_checks.values(),inflation))
write_csv(a.output,list(chosen_rows[0]),chosen_rows)
inputs=(a.alternatives_report,a.preview_report,a.plan,a.plan.with_suffix('.manifest.json'),alt_path,
    before_path,diff_path,Path(__file__),root/'src/fm27/rating_calibration.py',root/'reports/local/AUTOMATED_TESTS.json')
write_json(target_manifest,dict(status='CALIBRATED_NATIVE_PLAN_GATES_PASS_NOT_WRITTEN' if passed else 'CALIBRATION_REVIEW_REQUIRED',
    plan_sha256=sha256(a.output),source_plan_sha256=sha256(a.plan),candidate=manifest['candidate'],
    rows=len(chosen_rows),held_players=len(holds),holds=holds,diagnostics=diagnostics,models=models,
    training_fifa_ids=training_ids,holdout_checks=holdout_checks,league_checks=league_checks,inflation_check=inflation,
    evidence_sha256={**manifest['evidence_sha256'],**{str(path.resolve().relative_to(root)):sha256(path) for path in inputs}},
    method='Position-family monotonic native-level quantile calibration on mature, position-consistent training identities. '
        'Deterministic20percent identity holdout.75percent detailed source weight,25percent retained profile; '
        'each changed attribute bounded to20points and natively evaluated offsets -8..8. '
        'Unmapped attributes and every protected player field unchanged. Large or position-conflicting cases held for review.',
    release_ready=False,ratings_written_to_database=False))
print(json.dumps(dict(status='PASS' if passed else 'REVIEW_REQUIRED',rows=len(chosen_rows),held=len(holds),
    hold_reasons=dict(Counter(reason for r in holds for reason in r['reasons'])),holdout=holdout_checks,inflation=inflation)))
