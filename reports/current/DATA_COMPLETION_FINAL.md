# FM27 2026/27 data completion — current gate report

**INCOMPLETE — production sprint continues.** This file reports the latest selected
draft, not a successful release or a frozen production plan.

## League coverage

Authoritative source coverage: 12 / 12 leagues, 222 clubs.
Selected candidate native membership: 0 / 12 verified; status NOT_RUN.
Source coverage alone does not establish native application.

## Club coverage

0 / 222 COMPLETE; 23 GOOD_ENOUGH;
199 PARTIAL; 0 BLOCKED.
Per-club gaps: `CLUB_COVERAGE_MATRIX.csv`. These are evidence/plan coverage statuses.

## Transfers

Selected immutable draft contains 123 squad actions, 66 club changes,
18 loan-state rows and 30 expired-loan resolutions.
These counts describe input actions, not successfully applied transfers. Arrivals and
departures by covered club are recorded in the coverage matrix; they count new plan
deltas only, not cumulative Native08 work. A loan resolution is not automatically
counted as a football loan return.

## Players

Latest reconciliation: 6100 matched roster observations
out of 6272 (observations, not unique player identities).
Selected draft proposes 71 creations; native creation success is unverified
until write/reread/semantic comparison pass. Identity ambiguity queue:
1; player-creation review queue:
161. Exact unresolved records remain in
`integration/review-queue.csv`; provisional ratings are deferred, not silently discarded.

## Candidate

Candidate: `native10-data-draft-20260912-02`. Status: FAILED.

- Write: FAIL (aborted before a completed write)
- Reread: NOT_RUN
- Semantic diff: NOT_RUN
- Production freeze: NO

## Runtime smoke

PARTIAL — NOT_RUN. No completed-data smoke is claimed.
The user's accepted Native08 new-career loan result remains PASS and is not reopened.

## Remaining blockers

- Current coverage has 640 sprint-blocking review rows;
  exact reasons and club assignments are in the review queue and coverage matrix.
- The selected draft has not passed all native release gates.
- Undisclosed-contract exceptions may be applied only after an explicit user decision;
  `UNDISCLOSED_CONTRACTS.csv` preserves the individually documented cases.
- A single completed-data new-career smoke remains required after the data gates pass.

Sources: selected candidate `BUILD.json` and immutable input CSVs; current
`integration/integration.json`, `club-coverage-summary.json`, canonical membership.
The current reconciliation can advance beyond the selected immutable draft.
