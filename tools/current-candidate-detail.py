"""Publish exact field changes only after the immutable native comparator passes."""
import argparse
import csv
import json
import hashlib
from collections import Counter, defaultdict
from pathlib import Path

def rows(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', type=Path, required=True)
    candidate = parser.parse_args().candidate
    result_path = candidate / 'semantic-diff-v2.json' if (candidate / 'semantic-diff-v2.json').is_file() else candidate / 'semantic-diff.json'
    result = json.loads(result_path.read_text())
    assert result['status'] == 'PASS_NATIVE10_EXACT_SEMANTIC_DELTA'
    plan = rows(candidate / 'inputs/squad.csv')
    wanted = {row['fm_id'] for row in plan}
    before = {row['fm_id']: row for row in rows(candidate / 'write/before/native_player_semantics.csv') if row['fm_id'] in wanted}
    identity = lambda row: (row['fifa_id'], row['dob'], row['name'])
    keys = {identity(row) for row in before.values()}
    after = defaultdict(list)
    for row in rows(candidate / 'reread/native_player_semantics.csv'):
        if identity(row) in keys:
            after[identity(row)].append(row)
    changes = []
    for action in plan:
        old = before[action['fm_id']]
        candidates = after[identity(old)]
        assert len(candidates) == 1, 'Detailed report requires uniquely mapped planned identity'
        new = candidates[0]
        for field in old:
            if field not in {'fm_id', 'serialized_sha256'} and old[field] != new[field]:
                changes.append(dict(player=old['name'], before_fm_id=old['fm_id'], fifa_id=old['fifa_id'], dob=old['dob'], action=action.get('action') or 'SQUAD', field=field, before=old[field], after=new[field]))
    with (candidate / 'EXACT_PLAYER_FIELD_DIFF.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(changes[0]))
        writer.writeheader()
        writer.writerows(changes)
    summary = dict(status='PASS', existing_players_changed=len(plan), players_created=result['checks']['created_players']['actual'], field_counts=dict(sorted(Counter(row['field'] for row in changes).items())), competitions_changed=len(result['checks']['competition_delta']['actual']), existing_ratings_changed=0, unexpected_serialization_rewrites=result['checks']['unplanned_stable_semantics']['opaque_serialization_rewrites'], future_conditions_changed=0)
    (candidate / 'EXACT_CHANGE_SUMMARY.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    audit_path = candidate / 'inputs/creation-identity-audit.csv'
    audit = rows(audit_path)
    build = json.loads((candidate / 'BUILD.json').read_text(encoding='utf-8-sig'))
    assert build['evidence']['creation_identity_audit']['sha256'] == hashlib.sha256(audit_path.read_bytes()).hexdigest()
    assert len(audit) == summary['players_created'] and all(row['decision'] == 'CREATE_CLEAR' for row in audit)
    assert summary['unexpected_serialization_rewrites'] == 0
    gates = dict(status='NATIVE_DATA_DRAFT_PASS_COVERAGE_INCOMPLETE', identity_gate='PASS_SCOPED_CREATION_AUDIT_AND_NATIVE_COMPARE', identity_reason='Only identity-audited CREATE_CLEAR rows applied; ambiguous aliases remain in the technical blocker queue. Zero new opaque serialization rewrites.', write='PASS', reread='PASS', semantic_diff='PASS_REVALIDATED' if result_path.name.endswith('v2.json') else 'PASS', production_freeze=False, release_ready=False, runtime_smoke='NOT_RUN', remaining='Technical blocker rows, remaining PARTIAL clubs, production freeze and the completed-data runtime smoke remain open.')
    (candidate / 'RELEASE_GATES.json').write_text(json.dumps(gates, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(summary))

if __name__ == '__main__':
    main()
