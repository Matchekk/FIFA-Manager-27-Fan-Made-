# FM27 2026/27 data completion — current gate report

**INCOMPLETE — production sprint continues.** This file reports the latest selected
draft, not a successful release or a frozen production plan.

## League coverage

Authoritative source coverage: 12 / 12 leagues, 222 clubs.
Selected candidate native membership: 12 / 12 verified; status PASS.
Source coverage alone does not establish native application.

## Club coverage

0 / 222 COMPLETE; 52 GOOD_ENOUGH;
170 PARTIAL; 0 BLOCKED.
Per-club gaps: `CLUB_COVERAGE_MATRIX.csv`. These are evidence/plan coverage statuses.

## Transfers

Selected immutable draft contains 250 squad actions, 150 club changes,
20 loan-state rows and 111 expired-loan resolutions.
These counts describe input actions, not successfully applied transfers. Arrivals and
departures by covered club are recorded in the coverage matrix; they count new plan
deltas only, not cumulative Native08 work. A loan resolution is not automatically
counted as a football loan return.
Verified field changes: 93 contract ends,
148 first-team shirt numbers,
25 competition records,
2 planned history records.

## Players

Latest reconciliation: 6142 matched roster observations
out of 6272 (observations, not unique player identities).
Selected draft: 54 creations, native validation PASS.
Identity candidate/review holds:
48; additional identity searches required: 21.
Blocking player-creation review rows: 72;
nonblocking creation review rows: 58.
Separately retained provisional rating records: 54.
Exact unresolved records remain in
`integration/review-queue.csv`; provisional ratings are deferred, not silently discarded.

## Candidate

Candidate: `native10-data-draft-20260913-05`. Status: DRAFT_VALIDATED_DATA_INCOMPLETE.

Identity release gate: PASS_SCOPED_CREATION_AUDIT_AND_NATIVE_COMPARE.
Only identity-audited CREATE_CLEAR rows applied; held aliases and loan creations excluded. Zero new opaque serialization rewrites.

- Write: PASS
- Reread: PASS
- Semantic diff: PASS
- Production freeze: NO

## Runtime smoke

PARTIAL — NOT_RUN. No completed-data smoke is claimed.
The user's accepted Native08 new-career loan result remains PASS and is not reopened.

## Remaining blockers

- Current coverage has 488 sprint-blocking review rows;
  exact reasons and club assignments are in the review queue and coverage matrix.
- Selected draft native gates: PASS; complete squad coverage and runtime gates remain open.
- Undisclosed-contract exceptions may be applied only after an explicit user decision;
  `UNDISCLOSED_CONTRACTS.csv` preserves the individually documented cases.
- A single completed-data new-career smoke remains required after the data gates pass.

Sources: selected candidate `BUILD.json` and immutable input CSVs; current
`integration/integration.json`, `club-coverage-summary.json`, canonical membership.
The current reconciliation can advance beyond the selected immutable draft.
