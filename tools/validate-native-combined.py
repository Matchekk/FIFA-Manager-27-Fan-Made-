"""Bind a combined league candidate to its preserved, validated transfer semantics."""
import argparse
import datetime as dt
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'src'))
from fm27.common import sha256, write_json

p = argparse.ArgumentParser()
for name in ('transfer-report', 'player-report', 'league-report', 'support-report', 'plan', 'output'):
    p.add_argument('--' + name, type=Path, required=True)
a = p.parse_args()
if a.output.exists():
    raise ValueError('A new combined report is required')
bound = {}


def read(path):
    path = path.resolve()
    bound[str(path)] = sha256(path)
    return json.loads(path.read_text(encoding='utf-8'))


def verify(path, digest):
    path = path.resolve()
    if sha256(path) != digest:
        raise ValueError('Validation input changed: ' + str(path))
    bound[str(path)] = digest


transfer = read(a.transfer_report)
players = read(a.player_report)
league = read(a.league_report)
support = read(a.support_report)
manifest = read(a.plan.with_suffix('.manifest.json'))
source = Path(transfer['candidate'])
candidate = Path(league['candidate'])
stage = read(candidate / 'NATIVE_BUILD_INPUTS.json')
if (transfer['player_validation'] != 'PASS' or transfer['extended_native_validation'] != 'PASS'
        or transfer['native_support_validation'] != 'PASS'
        or transfer['expanded_world_validation']['status'] != 'PASS'
        or transfer['gates']['I_AUTOMATED_TESTS'] != 'PASS' or players['status'] != 'PASS'
        or league['status'] != 'NATIVE_PARTIAL_LEAGUE_MEMBERSHIP_PASS_GAME_GATES_OPEN'
        or support['status'] != 'PASS' or not league['checks']
        or any(v['status'] != 'PASS' for v in league['checks'].values())):
    raise ValueError('Completed transfer, league and support validations required')
if (Path(manifest['source_database']).resolve() != (source / 'database').resolve()
        or Path(support['source_database']).resolve() != (source / 'database').resolve()
        or Path(support['candidate']).resolve() != candidate.resolve()
        or stage['plan'] != manifest or not stage['source_and_inputs_unchanged']
        or manifest['rebase']['transfer_validation_sha256'] != sha256(a.transfer_report)
        or manifest['rebase']['transfer_plan_sha256'] != transfer['plan_sha256']):
    raise ValueError('Combined candidate does not derive from this transfer validation')
verify(a.plan, league['plan_sha256'])
verify(candidate / 'NATIVE_BUILD_INPUTS.json', league['stage_provenance_sha256'])
verify(source / 'native_player_semantics.csv', players['expected_sha256'])
if (players['expected_players'] != transfer['native_reread_players']
        or league['checks']['players_unchanged']['expected'] != transfer['native_reread_players']):
    raise ValueError('Player coverage differs')
for name, digest in transfer['candidate_database_files'].items():
    verify(source / name, digest)
for name, digest in league['candidate_database_files_sha256'].items():
    verify(candidate / 'database' / name, digest)
for name, digest in league['bound_files_sha256'].items():
    verify(Path(name), digest)
for name, digest in manifest['evidence_sha256'].items():
    verify(root / name, digest)
for name, values in support['files'].items():
    verify(source / name, values['source_sha256'])
    verify(candidate / name, values['candidate_sha256'])
verify(candidate / 'native_support_files.csv', support['manifest_sha256'])
for name, digest in stage['build']['source_sha256'].items():
    verify(root / name, digest)
verify(Path(stage['native_tests']['binary']), stage['binary_sha256'])
verify(Path(__file__), sha256(Path(__file__)))
matched = [k for k, v in league['actual_membership'].items() if v['matches_review']]
report = dict(
    status='NATIVE_COMBINED_PASS_GAME_GATES_OPEN',
    validated_at=dt.datetime.now(dt.timezone.utc).isoformat(),
    candidate=str(candidate.resolve()), source_transfer_candidate=str(source.resolve()),
    snapshot_date=transfer['snapshot_date'], transfer_plan_sha256=transfer['plan_sha256'],
    league_plan_sha256=league['plan_sha256'],
    actual_changed_players=transfer['actual_changed_players'], club_changes=transfer['club_changes'],
    planned_transfer_rows=transfer['planned_rows'], native_reread_players=transfer['native_reread_players'],
    league_changed_slots=league['checks']['exact_script_changes']['changed_slots'],
    exact_reviewed_memberships=matched, actual_membership=league['actual_membership'],
    checks=league['checks'], support_files=len(support['files']),
    native_test_count=stage['native_tests']['tests'], bound_files_sha256=bound,
    release_ready=False,
    limitations='Transfer validation is inherited through unchanged full canonical player serialization. '
        'Exactly reviewed league slots and native reread pass together. This does not close transfer '
        'coverage, league format/calendar, ratings, file coverage, editor export, game or release gates.')
write_json(a.output, report)
print(json.dumps({k: report[k] for k in ('status', 'actual_changed_players', 'club_changes',
    'league_changed_slots', 'exact_reviewed_memberships', 'support_files')}))
