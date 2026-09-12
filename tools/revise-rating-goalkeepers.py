"""Apply explicit native-converter goalkeeper mappings after the direct-preview scale review."""
import argparse
import json
import sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'src'))
from fm27.common import read_csv,sha256,write_csv,write_json
p=argparse.ArgumentParser()
p.add_argument('--plan',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
p.add_argument('--report',type=Path,required=True)
a=p.parse_args()
if a.output.exists() or a.output.with_suffix('.manifest.json').exists() or a.report.exists():
    raise ValueError('New goalkeeper revision required')
manifest=json.loads(a.plan.with_suffix('.manifest.json').read_text(encoding='utf-8'))
if sha256(a.plan)!=manifest['plan_sha256']: raise ValueError('Original preview changed')
for name,digest in manifest['evidence_sha256'].items():
    if sha256(root/name)!=digest: raise ValueError('Original source evidence changed')
rows=read_csv(a.plan); cohort={r['fm_id']:r for r in manifest['cohort']}
baseline_path=root/'data/generated/native-rating-baseline-20260908-01/native_ratings.csv'
baseline={r['fm_id']:r for r in read_csv(baseline_path) if r['fm_id'] in cohort}
ea_path=root/'data/intermediate/ea-fc27.csv'
ea={r['fifa_id']:r for r in read_csv(ea_path)}
fields=list(rows[0])[6:-4]
revised=[]
for row in rows:
    ident=row['fm_id']; original=baseline[ident]
    if original['main_position']!='GK': continue
    entry=ea[row['fifa_id']]
    if entry['position']!='GK' or entry['source_sha256']!=row['source_sha256']:
        raise ValueError('Goalkeeper source role or provenance differs')
    source=json.loads(entry['attributes'])
    for field in fields: row[field]=original[field]
    for field,source_field in dict(Diving='gkDiving',Handling='gkHandling',Positioning='gkPositioning',Reflexes='gkReflexes',Kicking='gkKicking').items():
        row[field]=str(source[source_field])
    # Exact role-specific upstream formulas; remove only the symmetric random
    # jitter from passing/shot power. EAoverall contributes to this existing
    # distribution attribute mapping and is never assigned as an FM level.
    row['Jumping']=str(max(source['gkDiving'],source['jumping']))
    row['LongPassing']=str((int(entry['ea_overall'])+source['gkKicking']+1)//2)
    row['Passing']=row['LongPassing']
    row['ShotPower']=str(source['gkKicking'])
    cohort[ident]['changed_attributes']=[f for f in fields if row[f]!=original[f]]
    if not cohort[ident]['changed_attributes']: raise ValueError('Goalkeeper revision produced no-op; review coverage')
    revised.append(ident)
write_csv(a.output,list(rows[0]),rows)
evidence={**manifest['evidence_sha256'],**{str(path.resolve().relative_to(root)):sha256(path)
    for path in (a.plan,a.plan.with_suffix('.manifest.json'),baseline_path,ea_path,Path(__file__))}}
write_json(a.report,dict(status='REVIEWED_GOALKEEPER_SOURCE_MAPPING_REVISION',original_plan_sha256=sha256(a.plan),
    revised_plan_sha256=sha256(a.output),revised_player_ids=revised,unchanged_outfield_players=len(rows)-len(revised),
    allowed_gk_attributes=['Diving','Handling','Positioning','Reflexes','Kicking','Jumping','LongPassing','Passing','ShotPower'],
    evidence_sha256=evidence,ratings_written_to_database=False,release_ready=False,
    reasoning='The direct experiment showed incompatible scales in generic EA goalkeeper outfield/physical fields. '
        'Retain those detailed native fields. Update the five directly comparable GK skills and four explicit '
        'GK-specific native-converter mappings. Keep OneOnOne,Consistency,TacticAwareness because their proxies '
        'do not independently establish those football qualities. Native scale calibration still required.'))
evidence[str(a.report.resolve().relative_to(root))]=sha256(a.report)
write_json(a.output.with_suffix('.manifest.json'),{**manifest,'plan_sha256':sha256(a.output),
    'cohort':list(cohort.values()),'evidence_sha256':evidence,'goalkeeper_revision_sha256':sha256(a.report),
    'method':manifest['method']+' Revised GK role mapping is bound to the explicit goalkeeper review report.'})
print(json.dumps(dict(rows=len(rows),revised_goalkeepers=len(revised),plan_sha256=sha256(a.output))))
