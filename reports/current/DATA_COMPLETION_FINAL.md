# FM27 2026/27 data completion — external pass1 checkpoint

Status: **VALIDATED NATIVE DATA DRAFT; PRODUCTION FREEZE BLOCKED**.

This checkpoint imports the supplied external football resolutions without web
research or independent reinterpretation. The remaining gaps are technical
conflicts only.

## League coverage

**12 / 12 leagues complete**, covering 222 competition rows. The independently
reread candidate passes exact membership validation for all target leagues.

## Club coverage

- 0 / 222 COMPLETE
- 179 GOOD_ENOUGH
- 43 PARTIAL
- 0 BLOCKED

The authoritative per-club artifact is `data/current/CLUB_COVERAGE_MATRIX.csv`.
The 43 PARTIAL clubs are tied to the retained technical queue; 137 NONBLOCKING
rows do not count against release coverage.

## Transfers

- Confirmed arrivals into covered clubs: 442
- Confirmed departures from covered clubs: 190
- Permanent club changes: 394
- Current-loan rows in the integrated plan: 48
- Guarded expired-loan resolutions / loan returns: 152
- Total existing-player actions: 542

## Players

- Existing native player actions matched and applied: 542
- External identities bridged to native identities: 57
- Players created: 57
- Unmatched creation records: 7
- Ambiguous native identity records: 5
- Duplicate creation IDs: 0

All creations use FIFA ID 0 unless an existing native identity was bridged; no
EA/FIFA ID was invented. Creation ratings use the existing conservative seed.

## Candidate

Candidate: `native10-data-external-pass1-20260913-02`.

- Native write: **PASS**
- Independent native reread: **PASS**
- Exact semantic diff: **PASS (revalidated)**
- Competition membership: **PASS, 12 / 12**
- Existing player end states: **542 / 542**
- Created players: **57 / 57**
- Unplanned serialization rewrites: **0**
- Existing rating changes: **0**
- Future-condition changes: **0**
- Python regression tests: **305 PASS**
- Native regression tests: **127 PASS**
- Production freeze: **NO**

The original semantic comparator counted only rewritten player blocks. Pure
`MOVE_PRESERVE_METADATA` changes are serialized through club membership lists,
so 207 valid club changes kept byte-identical player blocks. The corrected
validator compares full exported player semantics including `club_id`. Both the
original failure and corrected result are hash-bound in
`SEMANTIC_REVALIDATION.json`.

## Runtime smoke

**PARTIAL — NOT RUN for this incomplete pass1 draft.** The accepted Native08
new-career loan smoke remains PASS and was not repeated. A completed-data smoke
is deferred until the technical queue is resolved and the plan can be frozen.

## Remaining blockers

There are **55 technical blockers**:

- 30 `OWNER_CONTRACT_BEFORE_LOAN_END`: the supplied loan end exceeds the native
  owner contract and no replacement contract end was supplied.
- 13 `LOAN_END_AFTER_OWNER_CONTRACT`: the supplied resolved timeline ends after
  the supplied owner contract.
- 5 `AMBIGUOUS_LOCAL_NATIVE_IDENTITY`: a local candidate exists but cannot be
  bound without duplicate risk.
- 7 `CREATION_NATIVE_FIELDS_INCOMPLETE`: no safe native bridge and insufficient
  supplied fields for guarded creation.

Exact rows: `reports/current/integration-resolved-pass1/TECHNICAL_BLOCKERS.csv`.
No contract, identity, loan date or FIFA ID was guessed to close these rows.

## Primary artifacts

- `data/current/FM27_RESOLVED_REVIEW_QUEUE.csv`
- `data/current/CLUB_COVERAGE_MATRIX.csv`
- `data/current/integration-resolved-pass1/resolved-squad-delta.csv`
- `data/current/integration-resolved-pass1/resolved-player-creation-delta.csv`
- `data/current/integration-resolved-pass1/candidate-squad-plan.csv`
- `data/current/integration-resolved-pass1/candidate-player-creation-plan.csv`
- `reports/current/integration-resolved-pass1/creation-identity-audit.csv`
- `reports/current/integration-resolved-pass1/native-plan-preflight.json`
- `reports/current/integration-resolved-pass1/TECHNICAL_BLOCKERS.csv`
- `reports/current/NATIVE10_EXTERNAL_PASS1_VALIDATION.json`
- `data/generated/release-candidate/native10-data-external-pass1-20260913-02/EXACT_CHANGE_SUMMARY.json`
- `data/generated/release-candidate/native10-data-external-pass1-20260913-02/EXACT_PLAYER_FIELD_DIFF.csv`
- `data/generated/release-candidate/native10-data-external-pass1-20260913-02/DELTA_PROVENANCE.csv`
