"""Package existing review decisions without researching or inventing football facts."""
import csv
import hashlib
import io
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def digest(data):
    return hashlib.sha256(data).hexdigest()

def read(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))

def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode('utf-8')

def main():
    queue_path = ROOT / 'reports/current/integration/review-queue.csv'
    delta_path = ROOT / 'data/current/integration-staged/native10-post-draft05-condition-delta.csv'
    proof_path = ROOT / 'reports/current/integration/native-protected-condition-proof.json'
    queue, delta = read(queue_path), read(delta_path)
    proof = json.loads(proof_path.read_text(encoding='utf-8-sig'))
    assert digest(delta_path.read_bytes()) == proof['delta_sha256']
    actions = {row['fm_id']: row for row in delta}
    assert len(actions) == len(delta) == proof['staged_delta_rows']
    records, resolved, consumed = [], [], set()
    for source in queue:
        row_id = 'FM27-' + digest(encoded(source))[:24]
        decision, state, basis = '', {}, ''
        if source['blocking'] == 'NO':
            decision, basis = 'NONBLOCKING', 'Existing canonical review already marks this row nonblocking.'
        elif source['queue'] == 'TYPED_CONDITION' and source['fm_id'] in actions:
            state = actions[source['fm_id']]
            assert (source['fifa_id'], source['dob']) == (state['fifa_id'], state['dob'])
            assert source['native_club_id'] == state['old_club_id']
            assert source['target_club_id'] == state['new_club_id']
            decision, basis = 'APPLY', 'Existing staged exact protected-condition delta; no football reinterpretation.'
            consumed.add(source['fm_id'])
        row = dict(row_id=row_id, decision=decision,
                   resolution_status='RESOLVED' if decision else 'AWAITING_EXTERNAL_RESOLUTION',
                   resolution_basis=basis, resolved_state_json=json.dumps(state, ensure_ascii=False, sort_keys=True, separators=(',', ':')) if state else '',
                   **source)
        records.append(row)
        if decision:
            resolved.append(dict(row_id=row_id, decision=decision, resolved_state=state, basis=basis))
    assert consumed == set(actions)
    assert len({r['row_id'] for r in records}) == len(records)
    output = io.StringIO(newline='')
    writer = csv.DictWriter(output, fieldnames=list(records[0]), lineterminator='\n')
    writer.writeheader()
    writer.writerows(records)
    csv_bytes = output.getvalue().encode('utf-8')
    counts = dict(Counter(r['decision'] or 'AWAITING_EXTERNAL_RESOLUTION' for r in records))
    manifest = dict(schema_version=1, status='PARTIALLY_RESOLVED_NOT_A_PRODUCTION_FREEZE',
        queue_file='FM27_RESOLVED_REVIEW_QUEUE.csv', queue_sha256=digest(csv_bytes), rows=len(records),
        decision_counts=counts, allowed_decisions=['APPLY', 'KEEP_EXISTING', 'CREATE', 'NONBLOCKING', 'ESCALATE_TECHNICAL'],
        empty_decision='Awaiting external resolution; never interpret as KEEP_EXISTING or NONBLOCKING.',
        native_reference_base='Native08; fm_id fields must be bridged when applying to another native read.',
        state_schema='APPLY resolved_state uses the existing guarded native squad-plan schema; CREATE must supply the existing native creation-plan schema.',
        football_research_performed=False, applied_to_candidate=False, production_freeze_ready=False,
        sources=[dict(path=str(p.relative_to(ROOT)).replace('\\','/'), sha256=digest(p.read_bytes())) for p in (queue_path, delta_path, proof_path)],
        resolved_rows=resolved)
    outputs = {ROOT/'data/current/FM27_RESOLVED_REVIEW_QUEUE.csv': csv_bytes,
               ROOT/'data/current/FM27_RESOLVED_REVIEW_QUEUE.manifest.json': encoded(manifest)}
    # Never silently replace externally edited decisions on a later run.
    for path, data in outputs.items():
        if path.exists() and path.read_bytes() != data:
            raise ValueError('Preserve edited artifact; refusing overwrite: ' + str(path))
    for path, data in outputs.items():
        path.write_bytes(data)
    print(json.dumps(dict(rows=len(records), decisions=counts, outputs=[str(p) for p in outputs])))

if __name__ == '__main__':
    main()
