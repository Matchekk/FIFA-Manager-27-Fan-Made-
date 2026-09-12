"""Publish actual data-sprint gates; an incomplete draft never becomes a release."""
import argparse
import csv
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def rows(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', type=Path, required=True)
    args = parser.parse_args()
    build = json.loads((args.candidate / 'BUILD.json').read_text(encoding='utf-8-sig'))
    gate_path = args.candidate / 'RELEASE_GATES.json'
    gates = json.loads(gate_path.read_text(encoding='utf-8-sig')) if gate_path.exists() else {}
    integration = json.loads((ROOT / 'reports/current/integration/integration.json').read_text(encoding='utf-8-sig'))
    coverage = json.loads((ROOT / 'reports/current/club-coverage-summary.json').read_text(encoding='utf-8-sig'))
    plan = rows(args.candidate / 'inputs/squad.csv')
    created = rows(args.candidate / 'inputs/creation.csv') if (args.candidate / 'inputs/creation.csv').exists() else []
    membership = rows(ROOT / 'data/current/league-membership-2026-27.csv')
    actions = Counter(r.get('action') or 'SQUAD' for r in plan)
    moves = [r for r in plan if r['old_club_id'] != r['new_club_id']]
    loans = [r for r in plan if r.get('loan_owner_club_id', '0') not in ('', '0')]
    totals = coverage['overall']
    reviews = integration['review_queue_counts']
    terminal = json.loads((ROOT / 'reports/current/integration/terminal-data-queue.json').read_text(encoding='utf-8-sig'))
    identity_states = terminal['terminal_state_counts']
    identity_holds = sum(identity_states.get(k, 0) for k in ('HOLD_NATIVE08_IDENTITY_CANDIDATE', 'HOLD_IDENTITY_REVIEW'))
    identity_search = identity_states.get('IDENTITY_SEARCH_REQUIRED', 0)
    native_membership_path = args.candidate / 'membership-validation.json'
    native_membership = json.loads(native_membership_path.read_text()) if native_membership_path.exists() else {}
    write = build['write']
    if build['status'] == 'FAILED' and write == 'NOT_RUN':
        write = 'FAIL (aborted before a completed write)'
    text = f'''# FM27 2026/27 data completion — current gate report

**INCOMPLETE — production sprint continues.** This file reports the latest selected
draft, not a successful release or a frozen production plan.

## League coverage

Authoritative source coverage: {len(set(r['league_code'] for r in membership))} / 12 leagues, {len(membership)} clubs.
Selected candidate native membership: {native_membership.get('leagues_pass', 0)} / 12 verified; status {native_membership.get('status', 'NOT_RUN')}.
Source coverage alone does not establish native application.

## Club coverage

{totals.get('COMPLETE', 0)} / {coverage['clubs']} COMPLETE; {totals.get('GOOD_ENOUGH', 0)} GOOD_ENOUGH;
{totals.get('PARTIAL', 0)} PARTIAL; {totals.get('BLOCKED', 0)} BLOCKED.
Per-club gaps: `CLUB_COVERAGE_MATRIX.csv`. These are evidence/plan coverage statuses.

## Transfers

Selected immutable draft contains {len(plan)} squad actions, {len(moves)} club changes,
{len(loans)} loan-state rows and {actions.get('RESOLVE_EXPIRED_LOAN', 0)} expired-loan resolutions.
These counts describe input actions, not successfully applied transfers. Arrivals and
departures by covered club are recorded in the coverage matrix; they count new plan
deltas only, not cumulative Native08 work. A loan resolution is not automatically
counted as a football loan return.

## Players

Latest reconciliation: {integration['resolved_observations']} matched roster observations
out of {integration['roster_observations']} (observations, not unique player identities).
Selected draft proposes {len(created)} creations; native creation success is unverified
until write/reread/semantic comparison pass. Identity candidate/review holds:
{identity_holds}; additional identity searches required: {identity_search}.
Blocking player-creation review rows: {terminal['queue_counts'].get('PLAYER_CREATION', 0)};
nonblocking creation review rows: {reviews.get('PLAYER_CREATION', 0) - terminal['queue_counts'].get('PLAYER_CREATION', 0)}.
Separately retained provisional rating records: {reviews.get('PROVISIONAL_CREATION_RATING', 0)}.
Exact unresolved records remain in
`integration/review-queue.csv`; provisional ratings are deferred, not silently discarded.

## Candidate

Candidate: `{build['name']}`. Status: {build['status']}.

Identity release gate: {gates.get('identity_gate', 'NOT_SEPARATELY_VERIFIED')}.
{gates.get('identity_reason', '')}

- Write: {write}
- Reread: {build['reread']}
- Semantic diff: {build['semantic_diff']}
- Production freeze: {'YES' if build['production_frozen'] else 'NO'}

## Runtime smoke

PARTIAL — {build['runtime_smoke']}. No completed-data smoke is claimed.
The user's accepted Native08 new-career loan result remains PASS and is not reopened.

## Remaining blockers

- Current coverage has {coverage['review_queue']['sprint_blocking_rows']} sprint-blocking review rows;
  exact reasons and club assignments are in the review queue and coverage matrix.
- The selected draft has not passed all native release gates.
- Undisclosed-contract exceptions may be applied only after an explicit user decision;
  `UNDISCLOSED_CONTRACTS.csv` preserves the individually documented cases.
- A single completed-data new-career smoke remains required after the data gates pass.

Sources: selected candidate `BUILD.json` and immutable input CSVs; current
`integration/integration.json`, `club-coverage-summary.json`, canonical membership.
The current reconciliation can advance beyond the selected immutable draft.
'''
    output = ROOT / 'reports/current/DATA_COMPLETION_FINAL.md'
    output.write_text(text, encoding='utf-8')
    print(json.dumps({'report': str(output), 'status': 'INCOMPLETE', 'candidate': build['name']}))

if __name__ == '__main__':
    main()
