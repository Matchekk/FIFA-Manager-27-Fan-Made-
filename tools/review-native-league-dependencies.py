"""Join verified native competition graphs to the source-bound2026/27 membership review."""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from fm27.common import read_csv, sha256, write_json
root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--evidence', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
if args.output.exists():
    raise ValueError('Do not overwrite a prior dependency review')
evidence = json.loads(args.evidence.read_text(encoding='utf-8'))
if evidence['status'] != 'READ_ONLY_NATIVE_INSPECTION' or not evidence['source_unchanged']:
    raise ValueError('Native inspection is not verified')
inspection = Path(evidence['output'])
for name, digest in evidence['output_files_sha256'].items():
    if sha256(inspection / name) != digest:
        raise ValueError('Native inspection bytes changed')
competitions = read_csv(inspection / 'competition_structure.csv')
by_id = {p['competition_id']: p for p in competitions}
members = read_csv(inspection / 'competition_members.csv')
edges = read_csv(inspection / 'competition_edges.csv')
instructions = read_csv(inspection / 'competition_instructions.csv')
if (len(by_id) != len(competitions) or len(competitions) != evidence['competitions']
        or len(members) != evidence['league_members'] or len(edges) != evidence['edges']
        or len(instructions) != evidence['instructions']):
    raise ValueError('Native graph export cardinalities differ')
for edge in edges:
    if edge['competition_id'] not in by_id or (edge['target_competition_id'] in by_id) != (edge['target_exists'] == '1'):
        raise ValueError('Native edge existence flag is inconsistent')
missing = [e for e in edges if e['target_exists'] == '0']
if len(missing) != evidence['unresolved_edge_targets']:
    raise ValueError('Unresolved native target count differs')
instruction_by_key = {(r['competition_id'], r['index']): r for r in instructions}
if len(instruction_by_key) != len(instructions):
    raise ValueError('Duplicate native instruction positions')
membership_by_comp = defaultdict(list)
assignments = defaultdict(list)
for member in members:
    if member['competition_id'] not in by_id:
        raise ValueError('League member references an absent competition')
    membership_by_comp[member['competition_id']].append(member)
    # Normal league assignments, not seeded knockout/playoff memberships.
    if (int(member['competition_id']) >> 16) & 255 == 1:
        assignments[(member['club_id'], member['team_type'])].append(member['competition_id'])
scope_path = root / 'config/scope.json'
scope = json.loads(scope_path.read_text(encoding='utf-8'))['competitions']
review_path = root / 'reports/local/LEAGUE_STRUCTURE_REVIEW.json'
membership_review = json.loads(review_path.read_text(encoding='utf-8'))
reviews = {r['league']: r for r in membership_review['leagues']}
if set(reviews) != {r['key'] for r in scope}:
    raise ValueError('League review does not cover exactly the requested scope')
clubs = read_csv(root / 'data/intermediate/native-bound-baseline/clubs.csv')
references = {int(c['reference_id']): c['club_id'] for c in clubs}
if len(references) != len(clubs):
    raise ValueError('Ambiguous native club reference')
desired_global = {}
for config in scope:
    for member in reviews[config['key']]['desired_members']:
        key = (member['club_id'], {'FIRST': 'First', 'RESERVE': 'Reserve'}[member['team_type']])
        if key in desired_global:
            raise ValueError('Duplicate desired league membership')
        desired_global[key] = config['key']
results = []
for config in scope:
    ident = str((config['country_id'] << 24) | (1 << 16) | config['division'])
    comp = by_id[ident]
    native = membership_by_comp[ident]
    actual = {(p['club_id'], p['team_type']) for p in native}
    reviewed = reviews[config['key']]
    installed = {(references[int(ref) & 0xffffff], 'Reserve' if int(ref) & 0x1000000 else 'First')
        for ref in reviewed['installed']['team_references']}
    if actual != installed or len(actual) != len(native) or int(comp['num_teams']) != len(native):
        raise ValueError('Native membership differs from original league review: ' + config['key'])
    desired = {(p['club_id'], {'FIRST': 'First', 'RESERVE': 'Reserve'}[p['team_type']]) for p in reviewed['desired_members']}
    direct_edges = [e for e in edges if e['competition_id'] == ident or e['target_competition_id'] == ident]
    relevant_instructions = [instruction_by_key[(e['competition_id'], e['index'])] for e in direct_edges if e['relation'] == 'INSTRUCTION']
    results.append({'league': config['key'], 'competition': comp,
        'current_members': native, 'desired_members': reviewed['desired_members'],
        'incoming': [{'club_id': c, 'team_type': t, 'existing_normal_league_assignments': assignments[(c,t)]} for c,t in sorted(desired-actual)],
        'outgoing': [{'club_id': c, 'team_type': t, 'desired_scoped_league': desired_global.get((c,t)),
                      'outside_scope_destination_requires_evidence': (c,t) not in desired_global} for c,t in sorted(actual-desired)],
        'direct_edges': direct_edges, 'referencing_instructions': relevant_instructions,
        'format_change_required': len(actual) != len(desired), 'native_mutations': 0})
write_json(args.output, {'status': 'NATIVE_DEPENDENCIES_REVIEWED_NOT_MUTATED',
    'snapshot_date': membership_review['snapshot_date'], 'leagues': results,
    'global_competitions': len(competitions), 'global_edges': len(edges), 'global_unresolved_edges': missing,
    'native_inspection_evidence_sha256': sha256(args.evidence),
    'membership_review_sha256': sha256(review_path), 'scope_sha256': sha256(scope_path),
    'code_sha256': sha256(Path(__file__)), 'native_changes': 0, 'release_ready': False,
    'limitations': 'Actual competition graph and current versus desired members. Promotion ranges, calendars, outside-scope demotions and continental qualification still require a complete native mutation plan and game validation.'})
print(json.dumps({'leagues': len(results), 'competitions': len(competitions), 'edges': len(edges),
    'unresolved_edges': len(missing), 'format_changes': [r['league'] for r in results if r['format_change_required']],
    'report': str(args.output)}))
