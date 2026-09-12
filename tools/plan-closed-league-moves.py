"""Freeze only source-bound moves whose origins and destinations are both in scope.

This is an explicit partial membership phase, not a complete league-format plan.
Untouched slots stay in place; stable slots have no invented current-season claim.
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'src'))
from fm27.common import read_csv, sha256, write_csv, write_json

p = argparse.ArgumentParser()
p.add_argument('--leagues', nargs='+', required=True)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
manifest_path = a.output.with_suffix('.manifest.json')
if a.output.exists() or manifest_path.exists():
    raise ValueError('Frozen plan outputs must be new')
dependency_path = root / 'reports/local/LEAGUE_DEPENDENCY_REVIEW_01.json'
inspection_path = root / 'reports/local/NATIVE_COMPETITION_INSPECTION_01.json'
review_path = root / 'reports/local/LEAGUE_STRUCTURE_REVIEW.json'
dependency = json.loads(dependency_path.read_text(encoding='utf-8'))
inspection = json.loads(inspection_path.read_text(encoding='utf-8'))
if (dependency['native_inspection_evidence_sha256'] != sha256(inspection_path)
        or dependency['membership_review_sha256'] != sha256(review_path)
        or dependency['native_changes'] != 0 or not inspection['source_unchanged']):
    raise ValueError('League review binding changed')
inputs = {str(p.relative_to(root)): sha256(p) for p in (dependency_path, inspection_path, review_path, Path(__file__))}
for name, digest in inspection['output_files_sha256'].items():
    path = Path(inspection['output']) / name
    if sha256(path) != digest:
        raise ValueError('Native inspection changed')
    inputs[str(path.relative_to(root))] = digest
selected = {r['league']: r for r in dependency['leagues'] if r['league'] in a.leagues}
if set(selected) != set(a.leagues) or len(a.leagues) != len(selected):
    raise ValueError('Missing or duplicate requested league')
native = read_csv(Path(inspection['output']) / 'competition_members.csv')
def key(row):
    return row['club_id'], row['team_type'].upper()
desired = {}
current = {}
for league, review in selected.items():
    if review['format_change_required']:
        raise ValueError('Format changes need a separate plan: ' + league)
    for row in review['desired_members']:
        if key(row) in desired:
            raise ValueError('Ambiguous desired membership')
        desired[key(row)] = (league, row)
    for row in review['current_members']:
        if key(row) in current:
            raise ValueError('Ambiguous current membership')
        current[key(row)] = (league, row)
moves = {team: (origin[0], desired[team][0]) for team, origin in current.items()
         if team in desired and origin[0] != desired[team][0]}
rows, deltas, remaining = [], [], {}
for league, review in selected.items():
    outgoing = sorted((current[team][1] for team, move in moves.items() if move[0] == league), key=lambda r: int(r['slot']))
    incoming = sorted((desired[team][1] for team, move in moves.items() if move[1] == league), key=lambda r: (int(r['club_id']), r['team_type']))
    if len(outgoing) != len(incoming):
        raise ValueError('Selected closed moves would change league size: ' + league)
    result = {key(r) for r in review['current_members']}
    for old, new in zip(outgoing, incoming):
        digest = new['source_sha256']
        raw = root / 'data/raw/transfermarkt' / (digest + '.html')
        if sha256(raw) != digest or not new['source'].startswith('https://www.transfermarkt.de/'):
            raise ValueError('Target source evidence is missing or changed')
        inputs[str(raw.relative_to(root))] = digest
        rows.append(dict(competition_id=review['competition']['competition_id'], slot=old['slot'],
            old_club_id=old['club_id'], old_team_type=old['team_type'].upper(),
            new_club_id=new['club_id'], new_team_type=new['team_type'], status='CONFIRMED',
            source=new['source'], source_sha256=digest, snapshot_date=dependency['snapshot_date']))
        result.remove(key(old)); result.add(key(new))
        deltas.append(dict(league=league, slot=old['slot'], old_club_id=old['club_id'], new_club_id=new['club_id'], new_club=new['club']))
    wanted = {key(r) for r in review['desired_members']}
    remaining[league] = dict(membership_matches_review=result == wanted,
        still_missing=sorted(wanted-result), still_outgoing=sorted(result-wanted))
before = Counter(key(r) for r in native if (int(r['competition_id']) >> 16) & 255 == 1)
after = before.copy()
for row in rows:
    old = row['old_club_id'], row['old_team_type']
    new = row['new_club_id'], row['new_team_type']
    if before[old] != 1 or before[new] != 1:
        raise ValueError('A moved team has ambiguous global membership')
    after[old] -= 1; after[new] += 1
if not rows or before != after:
    raise ValueError('No moves or failed global team conservation')
write_csv(a.output, list(rows[0]), rows)
write_json(manifest_path, dict(status='FROZEN_PARTIAL_LEAGUE_MEMBERSHIP_NOT_RELEASE',
    snapshot_date=dependency['snapshot_date'], plan_sha256=sha256(a.output),
    source_database=inspection['database'], source_database_sha256=inspection['input_files_sha256'],
    evidence_sha256=inputs, changed_slots=len(rows), leagues=a.leagues, moves=deltas,
    remaining_membership=remaining, release_ready=False,
    limitations='Only balanced moves within the selected leagues. Slots are preserved where possible; replacement order is deterministic, not a table position. Regional moves, calendar dates, qualification, league formats and game season transitions remain open.'))
print(json.dumps(dict(changed_slots=len(rows), remaining_membership=remaining, plan_sha256=sha256(a.output))))
