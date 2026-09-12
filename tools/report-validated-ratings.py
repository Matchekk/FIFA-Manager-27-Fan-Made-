"""Report actual validated rating changes using the original fixed comparison cohort."""
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
p=argparse.ArgumentParser()
for name in ('validation','support','plan','after','diff','evidence'):
    p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args()
if any(path.exists() for path in (a.after,a.diff,a.evidence)):
    raise ValueError('Do not overwrite validated rating reports')
validation=json.loads(a.validation.read_text(encoding='utf-8'))
support=json.loads(a.support.read_text(encoding='utf-8'))
if validation['status']!='NATIVE_RATINGS_PASS_GAME_GATES_OPEN' or support['status']!='PASS':
    raise ValueError('Completed native rating and support validation required')
candidate=Path(validation['candidate'])
if Path(support['candidate']).resolve()!=candidate.resolve() or sha256(a.plan)!=validation['plan_sha256']:
    raise ValueError('Rating report candidate or plan differs')
for name,digest in validation['bound_files_sha256'].items():
    if sha256(Path(name))!=digest: raise ValueError('Native rating validation input changed')
for name,digest in validation['candidate_database_files_sha256'].items():
    if sha256(candidate/'database'/name)!=digest: raise ValueError('Validated rating database changed')
for name,values in support['files'].items():
    if sha256(candidate/name)!=values['candidate_sha256']: raise ValueError('Validated support file changed')
baseline_path=root/'reports/local/RATING_BASELINE_01.json'
baseline=json.loads(baseline_path.read_text(encoding='utf-8'))
for name,digest in baseline['input_sha256'].items():
    if sha256(Path(name))!=digest: raise ValueError('Original fixed rating cohort changed')
before_distribution=root/'reports/RATING_DISTRIBUTION_BEFORE.csv'
if sha256(before_distribution)!=baseline['distribution_sha256']: raise ValueError('Original rating distribution changed')
original_path=root/'data/generated/native-baseline-semantic-20260908-01/native_players.csv'
people_path=root/'data/intermediate/native-bound-baseline/players.csv'
original=read_csv(original_path)
people={r['fm_id']:r for r in read_csv(people_path)}
before_native=read_csv(candidate/'before-ratings/native_ratings.csv')
after_native=read_csv(Path(validation['reread'])/'native_ratings.csv')
comparison=('fifa_id','dob','name','main_position','style','level13','best_style','level13_best_style')
if Counter(tuple(r[f] for f in comparison) for r in original)!=Counter(tuple(r[f] for f in comparison) for r in before_native):
    raise ValueError('Pre-rating native level universe differs from original fixed baseline')
plan=read_csv(a.plan)
before_by_id={r['fm_id']:r for r in before_native}
old_by_fifa=defaultdict(list);new_by_fifa=defaultdict(list)
for r in original:
    if int(r['fifa_id'])>0: old_by_fifa[r['fifa_id']].append(r)
for r in after_native:
    if int(r['fifa_id'])>0: new_by_fifa[r['fifa_id']].append(r)
manifest=json.loads(a.plan.with_suffix('.manifest.json').read_text(encoding='utf-8'))
diagnostics={r['fm_id']:r for r in manifest['diagnostics']}
fields=list(plan[0])[6:-4]
replacements={};diff=[]
for row in plan:
    old=before_by_id[row['fm_id']]
    historical=old_by_fifa[row['fifa_id']];actual=new_by_fifa[row['fifa_id']]
    if len(historical)!=1 or len(actual)!=1: raise ValueError('Rating diff FIFA identity ambiguous')
    historical,actual=historical[0],actual[0]
    if any(historical[k]!=old[k] or actual[k]!=old[k] for k in ('fifa_id','dob','name')):
        raise ValueError('Rating diff identity differs across native generations')
    replacements[historical['fm_id']]=actual
    changed=[f for f in fields if old[f]!=actual[f]]
    info=diagnostics[row['fm_id']]
    diff.append(dict(fm_id=row['fm_id'],original_baseline_fm_id=historical['fm_id'],fifa_id=row['fifa_id'],
        name=actual['name'],dob=row['dob'],club_id=actual['club_id'],target_league=info['league'],
        native_position=actual['main_position'],source_position=info['source_position'],
        style_before=old['style'],style_after=actual['style'],experience_before=old['experience'],experience_after=actual['experience'],
        talent_before=old['talent'],talent_after=actual['talent'],level_before=old['level13'],level_after=actual['level13'],
        level_delta=int(actual['level13'])-int(old['level13']),best_style_before=old['best_style'],best_style_after=actual['best_style'],
        attributes_before=json.dumps({f:int(old[f]) for f in fields},sort_keys=True),
        attributes_after=json.dumps({f:int(actual[f]) for f in fields},sort_keys=True),changed_attributes='|'.join(changed),
        source=row['source'],source_sha256=row['source_sha256'],snapshot_date=row['snapshot_date']))
after_fixed=[]
for record in original:
    row=dict(record)
    if row['fm_id'] in replacements:
        actual=replacements[row['fm_id']]
        for key in ('level13','best_style','level13_best_style'): row[key]=actual[key]
    after_fixed.append(row)
snapshot=dt.date.fromisoformat(plan[0]['snapshot_date'])
leagues={r['key'] for r in json.loads((root/'config/scope.json').read_text(encoding='utf-8'))['competitions']}
def distribution(records):
    groups=defaultdict(list);items=[]
    for row in records:
        person=people[row['fm_id']];birthday=dt.date.fromisoformat(person['dob'])
        age=snapshot.year-birthday.year-((snapshot.month,snapshot.day)<(birthday.month,birthday.day))
        age_group=('UNKNOWN_OR_OUT_OF_RANGE' if not 0<=age<=100 else 'U18' if age<18 else '18-21' if age<22
                   else '22-25' if age<26 else '26-29' if age<30 else '30-34' if age<35 else '35+')
        item=(int(row['level13']),int(row['level13_best_style']),int(row['fm_id']))
        items.append(item)
        for key in (('WORLD','ALL'),('WORLD_POSITION',row['main_position']),('WORLD_AGE',age_group)): groups[key].append(item)
        if person['team_league'] in leagues:
            for key in (('SCOPED_LEAGUE_INSTALLED',person['team_league']),('SCOPED_POSITION_INSTALLED',row['main_position']),
                        ('SCOPED_AGE_INSTALLED',age_group),('SCOPED_INSTALLED','ALL')): groups[key].append(item)
    ranked=sorted(items,key=lambda r:(-r[0],r[2]))
    for size in (10,50,100,500): groups[('WORLD_TOP',str(size))]=ranked[:size]
    def q(values,fraction):
        offset=(len(values)-1)*fraction;lower=int(offset);upper=min(lower+1,len(values)-1)
        return round(values[lower]+(values[upper]-values[lower])*(offset-lower),4)
    output=[]
    for (category,group),members in sorted(groups.items()):
        levels=sorted(r[0] for r in members)
        output.append(dict(category=category,group=group,snapshot_date=snapshot.isoformat(),players=len(levels),
            minimum=levels[0],p10=q(levels,.1),median=statistics.median(levels),mean=round(statistics.mean(levels),4),
            p90=q(levels,.9),p99=q(levels,.99),maximum=levels[-1],level_80_plus=sum(x>=80 for x in levels),
            level_85_plus=sum(x>=85 for x in levels),level_90_plus=sum(x>=90 for x in levels),
            alternative_best_style_changes_level=sum(r[0]!=r[1] for r in members)))
    return output
before_rows=distribution(original);after_rows=distribution(after_fixed)
if [{k:str(v) for k,v in r.items()} for r in before_rows]!=read_csv(before_distribution):
    raise ValueError('Fixed-cohort reporting does not reproduce original BEFORE artifact exactly')
if len(diff)!=validation['changed_players'] or sum(len(r['changed_attributes'].split('|')) for r in diff)!=validation['changed_attributes']:
    raise ValueError('Validated rating diff count differs')
write_csv(a.after,list(after_rows[0]),after_rows)
write_csv(a.diff,list(diff[0]),diff)
write_json(a.evidence,dict(status='VALIDATED_NATIVE_RATING_BEFORE_AFTER_REPORTED',
    candidate=str(candidate),changed_players=len(diff),changed_attributes=validation['changed_attributes'],
    groups=len(after_rows),fixed_cohort_players=len(original),before_reproduced_exactly=True,
    before_sha256=sha256(before_distribution),after_sha256=sha256(a.after),diff_sha256=sha256(a.diff),
    validation_sha256=sha256(a.validation),support_sha256=sha256(a.support),plan_sha256=sha256(a.plan),
    source_sha256={str(path.resolve()):sha256(path) for path in (baseline_path,original_path,people_path,Path(__file__))},
    release_ready=False,limitations='Original installed league cohorts are fixed to isolate rating effects. Current target leagues are identified separately in PLAYER_RATING_DIFF. Review holds, editor export and game gates remain open.'))
print(json.dumps(dict(status='PASS',changed_players=len(diff),groups=len(after_rows),before_reproduced_exactly=True)))
