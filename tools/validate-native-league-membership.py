"""Prove exact script-slot changes and full native roundtrip for a league candidate."""
import argparse
import datetime as dt
import json
import re
import sys
from collections import Counter
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'src'))
from fm27.common import read_csv, sha256, write_json
from fm27.competitions import parse_leagues, fixture_errors
from fm27.world_validation import compare_world, compare_global

p = argparse.ArgumentParser()
for name in ('plan', 'candidate', 'reread', 'before', 'clubs', 'output'):
    p.add_argument('--' + name, type=Path, required=True)
a = p.parse_args()
if a.output.exists():
    raise ValueError('Do not overwrite league validation')
manifest = json.loads(a.plan.with_suffix('.manifest.json').read_text(encoding='utf-8'))
stage = json.loads((a.candidate / 'NATIVE_BUILD_INPUTS.json').read_text(encoding='utf-8'))
if (stage['status'] != 'NATIVE_LEAGUE_STAGE_WRITTEN_NOT_VALIDATED' or not stage['source_and_inputs_unchanged']
        or manifest != stage['plan'] or sha256(a.plan) != manifest['plan_sha256']
        or str(a.candidate.resolve()) != stage['candidate']):
    raise ValueError('Candidate is not bound to this frozen league plan')
source = Path(manifest['source_database'])
for name, digest in manifest['source_database_sha256'].items():
    if sha256(source / name) != digest:
        raise ValueError('Source database changed since plan review')
rows = read_csv(a.plan)
touched = {r['competition_id'] for r in rows}
checks = {}
bound_files = {}
def records(folder, filename, fields):
    path = folder / filename
    bound_files[str(path.resolve())] = sha256(path)
    return Counter(tuple(r[f] for f in fields) for r in read_csv(path))
def equal(name, left, right):
    passed = bool(left) and left == right
    checks[name] = dict(status='PASS' if passed else 'FAIL', expected=sum(left.values()), actual=sum(right.values()),
        missing=sum((left-right).values()), added=sum((right-left).values()))
for name, filename, fields in (
    ('players', 'native_player_semantics.csv', ('fifa_id','dob','name','club_id','serialized_sha256')),
    ('staffs', 'native_staff_semantics.csv', ('dob','name','club_id','serialized_sha256')),
    ('relations', 'native_player_relations.csv', ('relation','from_key','to_key'))):
    before = records(a.before, filename, fields)
    expected = records(a.candidate, filename, fields)
    actual = records(a.reread, filename, fields)
    equal(name + '_unchanged', before, expected)
    equal(name + '_roundtrip', expected, actual)
before_comps = records(a.before, 'native_competition_semantics.csv', ('competition_id','serialized_sha256'))
expected_comps = records(a.candidate, 'native_competition_semantics.csv', ('competition_id','serialized_sha256'))
actual_comps = records(a.reread, 'native_competition_semantics.csv', ('competition_id','serialized_sha256'))
equal('competitions_roundtrip', expected_comps, actual_comps)
equal('untouched_competitions', Counter({k:v for k,v in before_comps.items() if k[0] not in touched}),
    Counter({k:v for k,v in expected_comps.items() if k[0] not in touched}))
changed_ids = {k[0] for k in (before_comps-expected_comps)} | {k[0] for k in (expected_comps-before_comps)}
checks['exact_changed_competitions'] = dict(status='PASS' if changed_ids == touched else 'FAIL',
    expected=sorted(touched), actual=sorted(changed_ids))
for name, function in (('world', compare_world), ('global', compare_global)):
    checks[name + '_unchanged'] = function(a.before, a.candidate)
    checks[name + '_roundtrip'] = function(a.candidate, a.reread)

# Check the ENTIRE native script text, permitting only the ten reviewed TEAMS
# substitutions. No masked competition fields, pool instructions or calendar
# bytes are silently accepted. Native club-reference IDs are separately bound.
clubs = read_csv(a.clubs)
uid_to_ref = {r['club_id']: int(r['reference_id']) for r in clubs}
ref_to_uid = {v:k for k,v in uid_to_ref.items()}
if len(uid_to_ref) != len(clubs) or len(ref_to_uid) != len(clubs):
    raise ValueError('Club references are not unique')
bound_files[str(a.clubs.resolve())] = sha256(a.clubs)
def team_ref(uid, kind):
    if kind not in ('FIRST','RESERVE'):
        raise ValueError('Unexpected team type')
    return uid_to_ref[uid] | (0x1000000 if kind == 'RESERVE' else 0)
changes = {(r['competition_id'], int(r['slot'])): r for r in rows}
if len(changes) != len(rows):
    raise ValueError('Duplicate planned slots')
seen = set()
script_errors = []
actual_members = {}
source_scripts = {p.relative_to(source / 'script') for p in (source / 'script').rglob('*') if p.is_file()}
target_scripts = {p.relative_to(a.candidate / 'database/script') for p in (a.candidate / 'database/script').rglob('*') if p.is_file()}
if source_scripts != target_scripts:
    raise ValueError('Native script file coverage changed')
for relative in sorted(source_scripts):
    old_path = source / 'script' / relative
    new_path = a.candidate / 'database/script' / relative
    bound_files[str(new_path.resolve())] = sha256(new_path)
    changed_script_names = {f'CountryScript{int(ident) >> 24}.sav' for ident in touched}
    if relative.as_posix() not in changed_script_names:
        if sha256(old_path) != sha256(new_path):
            script_errors.append(str(relative) + ': changed unplanned script')
        continue
    old_text = old_path.read_text(encoding='utf-8-sig').replace('\r\n','\n')
    new_text = new_path.read_text(encoding='utf-8-sig').replace('\r\n','\n')
    expected_text = old_text
    for league in parse_leagues(old_text):
        if league['competition_type'] != 'LEAGUE':
            continue
        ident = str((league['country_id'] << 24) | (1 << 16) | league['division'])
        if ident not in touched:
            continue
        refs = list(league['team_references'])
        for slot in range(1,len(refs)+1):
            change = changes.get((ident,slot))
            if change is None:
                continue
            if refs[slot-1] != team_ref(change['old_club_id'],change['old_team_type']):
                raise ValueError('Source script slot disagrees with native plan')
            refs[slot-1] = team_ref(change['new_club_id'],change['new_team_type'])
            seen.add((ident,slot))
        block, count = re.subn(r'(?<=%INDEX%TEAMS\n)[^\n]*(?=\n%INDEXEND%TEAMS)',
            ','.join(format(ref,'x') for ref in refs), league['raw_block'])
        if count != 1 or expected_text.count(league['raw_block']) != 1:
            raise ValueError('Ambiguous competition block')
        expected_text = expected_text.replace(league['raw_block'],block,1)
    if expected_text != new_text:
        script_errors.append(str(relative) + ': differs beyond approved team slots')
    for league in parse_leagues(new_text):
        if league['competition_type'] != 'LEAGUE':
            continue
        ident = str((league['country_id'] << 24) | (1 << 16) | league['division'])
        if ident in touched:
            errors = fixture_errors(league)
            if errors:
                script_errors.append(str(relative) + ': ' + str(errors))
            actual_members[ident] = {(ref_to_uid[ref & 0xffffff], 'RESERVE' if ref & 0x1000000 else 'FIRST')
                for ref in league['team_references']}
checks['exact_script_changes'] = dict(status='PASS' if not script_errors and seen == set(changes) else 'FAIL',
    script_files=len(source_scripts), changed_slots=len(seen), errors=script_errors)
review_path = root / 'reports/local/LEAGUE_DEPENDENCY_REVIEW_01.json'
if sha256(review_path) != manifest['evidence_sha256'][str(review_path.relative_to(root))]:
    raise ValueError('Reviewed targets changed')
review = json.loads(review_path.read_text(encoding='utf-8'))
membership = {}
for league in review['leagues']:
    if league['league'] not in manifest['leagues']:
        continue
    ident = league['competition']['competition_id']
    desired = {(r['club_id'],r['team_type']) for r in league['desired_members']}
    actual = actual_members[ident]
    membership[league['league']] = dict(matches_review=actual == desired, teams=len(actual),
        missing=sorted(desired-actual), outgoing=sorted(actual-desired))
    promised = manifest['remaining_membership'][league['league']]
    if (membership[league['league']]['matches_review'] != promised['membership_matches_review']
            or [list(x) for x in sorted(desired-actual)] != promised['still_missing']
            or [list(x) for x in sorted(actual-desired)] != promised['still_outgoing']):
        raise ValueError('Result differs from explicit partial membership scope')
passed = all(c['status'] == 'PASS' for c in checks.values())
write_json(a.output, dict(status='NATIVE_PARTIAL_LEAGUE_MEMBERSHIP_PASS_GAME_GATES_OPEN' if passed else 'FAIL',
    candidate=str(a.candidate.resolve()), reread=str(a.reread.resolve()),
    plan_sha256=sha256(a.plan), stage_provenance_sha256=sha256(a.candidate / 'NATIVE_BUILD_INPUTS.json'),
    validated_at=dt.datetime.now(dt.timezone.utc).isoformat(), checks=checks,
    actual_membership=membership, bound_files_sha256=bound_files,
    candidate_database_files_sha256={str(p.relative_to(a.candidate / 'database')): sha256(p)
        for p in sorted((a.candidate / 'database').rglob('*')) if p.is_file()},
    release_ready=False, limitations='Exact native membership changes and serialization only. Third-tier regional changes remain open; existing calendar dates, qualification and format rules are preserved, not verified for 2026/27. No editor compilation, game career, save/load or season-transition claim.'))
print(json.dumps(dict(status='PASS' if passed else 'FAIL', failed_checks=[k for k,v in checks.items() if v['status'] != 'PASS'], membership=membership)))
sys.exit(0 if passed else 1)
