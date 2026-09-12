"""Freeze detailed-source substitutions for native calibration experiments, never a release plan."""
import argparse
import datetime as dt
import json
import sys
from collections import Counter,defaultdict
from pathlib import Path

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'src'))
from fm27.common import read_csv,sha256,write_csv,write_json
from fm27.ea import page_props,league_page
from fm27.matching import normalize
p=argparse.ArgumentParser()
p.add_argument('--inspection',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args()
manifest_path=a.output.with_suffix('.manifest.json')
if a.output.exists() or manifest_path.exists():
    raise ValueError('New preview plan required')
inspection=json.loads(a.inspection.read_text(encoding='utf-8'))
if inspection['status']!='NATIVE_RATING_BASELINE_INSPECTION_PASS' or not inspection['source_unchanged']:
    raise ValueError('Validated rating inspection required')
native_path=Path(inspection['output'])
if sha256(native_path)!=inspection['output_sha256']:
    raise ValueError('Rating baseline changed')
mapping_path=root/'reports/local/RATING_MAPPING_SOURCE_REVIEW_01.json'
mapping=json.loads(mapping_path.read_text(encoding='utf-8'))
for name,digest in mapping['input_sha256'].items():
    if sha256(root/name)!=digest:
        raise ValueError('Mapping evidence changed: '+name)
fields=mapping['serialized_fm13_attributes']
if len(fields)!=37:
    raise ValueError('Expected37persisted FM13 attributes')
ea_path=root/'data/intermediate/ea-fc27.csv'
ea=read_csv(ea_path)
native=read_csv(native_path)
by_fifa=defaultdict(list)
for person in native:
    if int(person['fifa_id'])>0:
        by_fifa[person['fifa_id']].append(person)
old_path=root/'data/intermediate/native-bound-baseline/players.csv'
old={r['fm_id']:r for r in read_csv(old_path)}
league_path=root/'reports/local/LEAGUE_DEPENDENCY_REVIEW_01.json'
league_review=json.loads(league_path.read_text(encoding='utf-8'))
# Bind the real2026/27 target clubs to the existing frozen membership evidence.
combined_manifest_path=root/'data/generated/league-membership-plan-20260908-03.manifest.json'
combined_manifest=json.loads(combined_manifest_path.read_text(encoding='utf-8'))
if sha256(league_path)!=combined_manifest['evidence_sha256'][str(league_path.relative_to(root))]:
    raise ValueError('Desired league identities changed')
membership={}
for league in league_review['leagues']:
    for club in league['desired_members']:
        key=(club['club_id'],club['team_type'])
        if key in membership:
            raise ValueError('Ambiguous scoped native team')
        membership[key]=league['league']
source_hashes={}
source_rows={}
counts=Counter(); rows=[]; cohort=[]
ea_counts=Counter(r['fifa_id'] for r in ea)
gk_attributes={'Diving','Handling','Positioning','Reflexes','Kicking'}
gk_overrides={'Jumping','LongPassing','Passing','ShotPower'}
for entry in ea:
    candidates=by_fifa[entry['fifa_id']]
    if ea_counts[entry['fifa_id']]!=1 or len(candidates)!=1:
        counts['IDENTITY_MISSING_OR_AMBIGUOUS']+=1;continue
    person=candidates[0]
    dob=dt.datetime.strptime(person['dob'],'%d.%m.%Y').date().isoformat()
    if dob!=entry['dob']:
        counts['DOB_CONFLICT']+=1;continue
    names={normalize(person['name'])}
    prior=old.get(person['fm_id'])
    if prior and prior['fifa_id']==person['fifa_id'] and prior['dob']==dob:
        names.update(normalize(prior[k]) for k in ('name','common_name') if prior[k])
    if not names & {normalize(entry[k]) for k in ('player','common_name') if entry[k]}:
        counts['NAME_REVIEW_REQUIRED']+=1;continue
    team_type='RESERVE' if person['in_reserve']=='1' else 'FIRST'
    league=membership.get((person['club_id'],team_type))
    if not league or person['in_youth']=='1':
        counts['OUTSIDE_TARGET_SQUAD']+=1;continue
    if (person['main_position']=='GK')!=(entry['position']=='GK') or person['main_position']=='None':
        counts['POSITION_REVIEW_REQUIRED']+=1;continue
    if entry['rating_evidence_status']!='CONFIRMED':
        counts['UNCONFIRMED_RATING_SOURCE']+=1;continue
    key=(entry['source_sha256'],entry['league'])
    if key not in source_rows:
        path=root/'data/raw/ea'/(entry['source_sha256']+'.html')
        if sha256(path)!=entry['source_sha256']:
            raise ValueError('EA raw source hash mismatch')
        parsed,_,_=league_page(page_props(path.read_text(encoding='utf-8-sig')),entry['league'])
        source_rows[key]={str(r['fifa_id']):r for r in parsed}
        source_hashes[str(path.relative_to(root))]=sha256(path)
    original=source_rows[key].get(entry['fifa_id'])
    if (not original or original['dob']!=dob or original['attributes']!=entry['attributes']
            or original['player']!=entry['player'] or original['position']!=entry['position']):
        raise ValueError('Detailed rating source row differs from raw page')
    attributes=json.loads(entry['attributes'])
    proposed={field:person[field] for field in fields}
    changed=[]
    for field,ea_key in mapping['deterministic_direct_source_candidates'].items():
        # Avoid transferring meaningless outfield GK values or replacing the
        # upstream GK-specific derived fields with its outfield direct mapping.
        if person['main_position']=='GK' and field in gk_overrides:
            continue
        if person['main_position']!='GK' and field in gk_attributes:
            continue
        value=attributes[ea_key]
        if type(value) is not int or not 0<=value<=99:
            raise ValueError('Invalid detailed source attribute')
        proposed[field]=str(value)
        if value!=int(person[field]): changed.append(field)
    if not changed:
        counts['ALREADY_EQUAL']+=1;continue
    row=dict(fm_id=person['fm_id'],fifa_id=person['fifa_id'],dob=dob,club_id=person['club_id'],
        baseline_sha256=person['serialized_sha256'],expected_level13='',**proposed,
        status='CONFIRMED',source=entry['source'],source_sha256=entry['source_sha256'],snapshot_date=entry['snapshot_date'])
    rows.append(row)
    cohort.append(dict(fm_id=person['fm_id'],fifa_id=person['fifa_id'],name=person['name'],dob=dob,
        target_league=league,native_position=person['main_position'],source_position=entry['position'],
        baseline_level13=int(person['level13']),changed_attributes=changed,source_phase=entry['source_phase']))
    counts['NATIVE_PREVIEW_PROPOSAL']+=1
if not rows or sum(counts.values())!=len(ea):
    raise ValueError('Preview source coverage does not reconcile')
write_csv(a.output,list(rows[0]),rows)
inputs=(a.inspection,native_path,mapping_path,ea_path,old_path,league_path,combined_manifest_path,Path(__file__),root/'src/fm27/ea.py')
write_json(manifest_path,dict(status='UNCALIBRATED_NATIVE_PREVIEW_ONLY_NOT_STAGEABLE',
    plan_sha256=sha256(a.output),candidate=inspection['candidate'],inspection_sha256=sha256(a.inspection),
    rows=len(rows),counts=dict(counts),source_phase=sorted({r['source_phase'] for r in cohort}),
    cohort=cohort,evidence_sha256={**source_hashes,**{str(p.resolve().relative_to(root)):sha256(p) for p in inputs}},
    method='Detailed upstream direct mappings, retaining five unmapped fields, outfield GK fields and four GK overrides. '
        'No blending or overall-to-level conversion. Empty expected_level13 requires preview mode; native calibration is pending.',
    release_ready=False,ratings_written_to_database=False))
print(json.dumps(dict(rows=len(rows),counts=dict(counts),plan_sha256=sha256(a.output))))
