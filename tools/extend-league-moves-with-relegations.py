"""Extend a frozen membership plan with reviewed first/second-tier exchanges."""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'src'))
from fm27.common import read_csv,sha256,write_csv,write_json
from fm27.league_sources import parse_league_members

p=argparse.ArgumentParser()
p.add_argument('--base-plan',type=Path,required=True)
p.add_argument('--review',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args()
manifest_path=a.output.with_suffix('.manifest.json')
if a.output.exists() or manifest_path.exists():
    raise ValueError('Outputs must be new')
base_manifest_path=a.base_plan.with_suffix('.manifest.json')
base=json.loads(base_manifest_path.read_text(encoding='utf-8'))
if base['status']!='FROZEN_PARTIAL_LEAGUE_MEMBERSHIP_NOT_RELEASE' or sha256(a.base_plan)!=base['plan_sha256']:
    raise ValueError('Base league plan is not frozen')
review=json.loads(a.review.read_text(encoding='utf-8'))
if review['status']!='REVIEWED_LEAGUE_ONLY_IDENTITIES' or review['snapshot_date']!=base['snapshot_date']:
    raise ValueError('Relegation identity review is unconfirmed or stale')
inputs={**base['evidence_sha256'],**review['inputs_sha256']}
for name,digest in inputs.items():
    if sha256(root/name)!=digest:
        raise ValueError('Review input changed: '+name)
for path in (a.base_plan,base_manifest_path,a.review,Path(__file__)):
    inputs[str(path.resolve().relative_to(root))]=sha256(path)
dependency_path=root/'reports/local/LEAGUE_DEPENDENCY_REVIEW_01.json'
dependencies={r['league']:r for r in json.loads(dependency_path.read_text(encoding='utf-8'))['leagues']}
inspection=json.loads((root/'reports/local/NATIVE_COMPETITION_INSPECTION_01.json').read_text(encoding='utf-8'))
native=read_csv(Path(inspection['output'])/'competition_members.csv')
structure={r['competition_id']:r for r in read_csv(Path(inspection['output'])/'competition_structure.csv')}
capture=json.loads((root/'reports/local/SECOND_TIER_MEMBERSHIP_CAPTURE_01.json').read_text(encoding='utf-8'))
sources={r['parent_league']:r for r in capture['leagues']}
rows=read_csv(a.base_plan)
selected=list(base['leagues'])
deferred={}
def key(row):
    return row['club_id'],row['team_type'].upper()
for league in sources:
    dep=dependencies[league]
    if dep['format_change_required']:
        deferred[league]='First and second-tier format changes require separate calendar/instruction plan'
        continue
    if league in selected:
        raise ValueError('Cannot append a league already in the base plan')
    source=sources[league]
    raw=root/'data/raw/transfermarkt'/source['source']['file']
    if sha256(raw)!=source['source']['sha256']:
        raise ValueError('Second-tier raw source changed')
    reparsed=parse_league_members(raw.read_text(encoding='utf-8-sig'),source['competition_code'])
    if reparsed!=source['members']:
        raise ValueError('Second-tier source reparse differs')
    inputs[str(raw.relative_to(root))]=sha256(raw)
    demotions=[r for r in review['rows'] if r['league']==league]
    if {r['club_id'] for r in demotions}!={r['club_id'] for r in dep['outgoing']}:
        raise ValueError('Not all departures have reviewed destinations')
    lower_ids={r['destination_competition_id'] for r in demotions}
    if len(lower_ids)!=1:
        raise ValueError('Departures do not share one reviewed second tier')
    lower=next(iter(lower_ids))
    if int(structure[lower]['num_teams'])!=source['teams']:
        raise ValueError('Second-tier format change required: '+league)
    promotions=[]
    for incoming in dep['incoming']:
        if incoming['existing_normal_league_assignments']!=[lower]:
            raise ValueError('Promotion origin disagrees with reviewed second tier')
        members=[r for r in dep['desired_members'] if key(r)==key(incoming)]
        if len(members)!=1:
            raise ValueError('Missing reviewed promoted member')
        promotions.append(members[0])
    if len(promotions)!=len(demotions):
        raise ValueError('Unbalanced first/second-tier moves')
    new_top_keys={key(r) for r in promotions}
    old_top_keys={key(r) for r in demotions}
    top_slots=sorted([r for r in dep['current_members'] if key(r) in old_top_keys],key=lambda r:int(r['slot']))
    lower_slots=sorted([r for r in native if r['competition_id']==lower and key(r) in new_top_keys],key=lambda r:int(r['slot']))
    if len(top_slots)!=len(demotions) or len(lower_slots)!=len(promotions):
        raise ValueError('Native slots do not match reviewed identities')
    for slots,replacements in ((top_slots,promotions),(lower_slots,demotions)):
        for old,new in zip(slots,sorted(replacements,key=lambda r:(int(r['club_id']),r['team_type']))):
            raw=root/'data/raw/transfermarkt'/(new['source_sha256']+'.html')
            if sha256(raw)!=new['source_sha256']:
                raise ValueError('Target membership source changed')
            inputs[str(raw.relative_to(root))]=sha256(raw)
            rows.append(dict(competition_id=old['competition_id'],slot=old['slot'],old_club_id=old['club_id'],
                old_team_type=old['team_type'].upper(),new_club_id=new['club_id'],new_team_type=new['team_type'],
                status='CONFIRMED',source=new['source'],source_sha256=new['source_sha256'],snapshot_date=base['snapshot_date']))
    selected.append(league)
changes={(r['competition_id'],r['slot']):r for r in rows}
if len(changes)!=len(rows):
    raise ValueError('Overlapping base/new league slots')
before=Counter(key(r) for r in native if (int(r['competition_id'])>>16)&255==1)
after=before.copy()
final={}
for old in native:
    next_row=changes.get((old['competition_id'],old['slot']))
    if next_row:
        if (next_row['old_club_id'],next_row['old_team_type'])!=key(old):
            raise ValueError('Combined plan baseline differs')
        next_key=next_row['new_club_id'],next_row['new_team_type']
        if before[key(old)]!=1 or before[next_key]!=1:
            raise ValueError('Ambiguous global league membership')
        after[key(old)]-=1;after[next_key]+=1
    else:
        next_key=key(old)
    final.setdefault(old['competition_id'],set()).add(next_key)
if before!=after:
    raise ValueError('Combined plan fails global team conservation')
remaining={}
for league in selected:
    dep=dependencies[league]
    wanted={key(r) for r in dep['desired_members']}
    actual=final[dep['competition']['competition_id']]
    remaining[league]=dict(membership_matches_review=actual==wanted,still_missing=sorted(wanted-actual),still_outgoing=sorted(actual-wanted))
write_csv(a.output,list(rows[0]),rows)
write_json(manifest_path,dict(status='FROZEN_PARTIAL_LEAGUE_MEMBERSHIP_NOT_RELEASE',snapshot_date=base['snapshot_date'],
    plan_sha256=sha256(a.output),source_database=base['source_database'],source_database_sha256=base['source_database_sha256'],
    evidence_sha256=inputs,changed_slots=len(rows),leagues=selected,remaining_membership=remaining,
    deferred_format_changes=deferred,base_plan_sha256=sha256(a.base_plan),new_rows=len(rows)-len(read_csv(a.base_plan)),
    release_ready=False,limitations='Reviewed first/second-tier exchanges plus unchanged German base moves. Secondary leagues receive the necessary moves only; their other third-tier exchanges are outside this phase. GER3 regional boundary and Belgium format remain open. Preserved native calendars and qualification rules are not a2026/27 game-validation claim.'))
print(json.dumps(dict(rows=len(rows),leagues_touched=len({r['competition_id'] for r in rows}),
    matched_primary_memberships=[k for k,v in remaining.items() if v['membership_matches_review']],deferred=deferred,plan_sha256=sha256(a.output))))
