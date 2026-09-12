"""Describe unchanged native FM13 levels before rating work; never change attributes."""
import argparse
import datetime as dt
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from fm27.common import read_csv, sha256, write_csv, write_json
from fm27.native_identity import bind_native_free_agent_ids

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--players', type=Path, default=root / 'data/intermediate/native-bound-baseline/players.csv')
parser.add_argument('--native-levels', type=Path, default=root / 'data/generated/native-baseline-semantic-20260908-01/native_players.csv')
parser.add_argument('--snapshot', default='2026-09-08')
parser.add_argument('--output', type=Path, default=root / 'reports/RATING_DISTRIBUTION_BEFORE.csv')
parser.add_argument('--evidence', type=Path, default=root / 'reports/local/RATING_BASELINE_01.json')
args = parser.parse_args()
snapshot = dt.date.fromisoformat(args.snapshot)
if args.output.exists() or args.evidence.exists():
    raise ValueError('Refuse to overwrite an existing rating baseline')
players = read_csv(args.players)
native = read_csv(args.native_levels)
by_id = {p['fm_id']: p for p in players}
native_by_id = {p['fm_id']: p for p in native}
if len(by_id) != len(players) or len(native_by_id) != len(native) or set(by_id) != set(native_by_id):
    raise ValueError('Native level and identity universes differ or contain duplicate IDs')
if bind_native_free_agent_ids([dict(p) for p in players], native):
    raise ValueError('Rating report requires an already bound native identity baseline')
scope = json.loads((root / 'config/scope.json').read_text(encoding='utf-8'))
leagues = {r['key'] for r in scope['competitions']}
groups = defaultdict(list)
observations = []
invalid_age = []
for record in native:
    person = by_id[record['fm_id']]
    level = int(record['level13'])
    best = int(record['level13_best_style'])
    if not 0 <= level <= 99 or not 0 <= best <= 99:
        raise ValueError('Unexpected native level range')
    birthday = dt.date.fromisoformat(person['dob'])
    age = snapshot.year - birthday.year - ((snapshot.month, snapshot.day) < (birthday.month, birthday.day))
    if not 0 <= age <= 100:
        age_group = 'UNKNOWN_OR_OUT_OF_RANGE'
        invalid_age.append(person['fm_id'])
    else:
        age_group = 'U18' if age < 18 else '18-21' if age < 22 else '22-25' if age < 26 else '26-29' if age < 30 else '30-34' if age < 35 else '35+'
    item = {'fm_id': person['fm_id'], 'fifa_id': person['fifa_id'], 'name': person['name'],
        'dob': person['dob'], 'age': age, 'age_group': age_group, 'club_id': person['club_id'],
        'club': person['club'], 'league': person['team_league'], 'squad': person['squad'],
        'position': record['main_position'], 'level13': level, 'level13_best_style': best,
        'style': record['style'], 'best_style': record['best_style']}
    observations.append(item)
    groups[('WORLD', 'ALL')].append(item)
    groups[('WORLD_POSITION', item['position'])].append(item)
    groups[('WORLD_AGE', age_group)].append(item)
    if person['team_league'] in leagues:
        groups[('SCOPED_LEAGUE_INSTALLED', person['team_league'])].append(item)
        groups[('SCOPED_POSITION_INSTALLED', item['position'])].append(item)
        groups[('SCOPED_AGE_INSTALLED', age_group)].append(item)
        groups[('SCOPED_INSTALLED', 'ALL')].append(item)
if {key for category, key in groups if category == 'SCOPED_LEAGUE_INSTALLED'} != leagues:
    raise ValueError('Baseline lacks one or more requested league groups')
ranked = sorted(observations, key=lambda r: (-r['level13'], int(r['fm_id'])))
for size in (10, 50, 100, 500):
    groups[('WORLD_TOP', str(size))] = ranked[:size]
def quantile(values, fraction):
    # Linear interpolation between ordered observations (same as common type7).
    offset = (len(values) - 1) * fraction
    lower = int(offset)
    upper = min(lower + 1, len(values) - 1)
    return round(values[lower] + (values[upper] - values[lower]) * (offset - lower), 4)
rows = []
for (category, group), members in sorted(groups.items()):
    levels = sorted(r['level13'] for r in members)
    rows.append({'category': category, 'group': group, 'snapshot_date': args.snapshot,
        'players': len(levels), 'minimum': levels[0], 'p10': quantile(levels, .1),
        'median': statistics.median(levels), 'mean': round(statistics.mean(levels), 4),
        'p90': quantile(levels, .9), 'p99': quantile(levels, .99), 'maximum': levels[-1],
        'level_80_plus': sum(v >= 80 for v in levels), 'level_85_plus': sum(v >= 85 for v in levels),
        'level_90_plus': sum(v >= 90 for v in levels),
        'alternative_best_style_changes_level': sum(r['level13'] != r['level13_best_style'] for r in members)})
write_csv(args.output, list(rows[0]), rows)
write_json(args.evidence, {'status': 'READ_ONLY_BASELINE_NOT_CALIBRATED', 'snapshot_date': args.snapshot,
    'players': len(players), 'native_level_authority': 'FifamPlayerLevel::GetPlayerLevel13(existing main position, existing playing style)',
    'membership': 'Original installed team_league, including explicitly assigned reserve competition members; not the intended2026/27 membership.',
    'level_style': 'Existing style is used for distribution; best style is recorded only as a diagnostic and is not applied.',
    'scope_league_counts': {group: len(value) for (category, group), value in groups.items() if category == 'SCOPED_LEAGUE_INSTALLED'},
    'world_level_histogram': dict(sorted(Counter(r['level13'] for r in observations).items())),
    'invalid_or_out_of_range_age_ids': invalid_age,
    'top500': ranked[:500], 'rating_changes': 0, 'talent_changes': 0, 'release_ready': False,
    'input_sha256': {str(p.resolve()): sha256(p) for p in (args.players, args.native_levels, root / 'config/scope.json', Path(__file__))},
    'distribution_sha256': sha256(args.output),
    'limitations': 'No FC overall-to-FM level equality or new rating mapping. Recompute after planned rating mutations using the same cohort or report membership changes separately.'})
print(json.dumps({'players': len(players), 'groups': len(rows), 'scoped_leagues': len(leagues),
    'report': str(args.output), 'evidence_sha256': sha256(args.evidence), 'rating_changes': 0}))
