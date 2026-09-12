# FM27 Community Overhaul — Project State

Updated 2026-09-12. Active production sprint: complete the 2026/27 football database.

## Accepted foundation

Native08 accepted base: `data/generated/release-candidate/native08-integrated-20260912-01/database`.
Integrated history/ratings, native reader/writer, Editor export, new career, save/load
and first season transition work. User confirmed corrected loans in a NEW career: PASS.
794 active loans, 744 corrected begins, 50 intentional unchanged begins. Do not redo
Native07/08 or investigate the general loan root cause.

## Scope

ENG1, ITA1, ESP1, GER1, FRA1, POR1, NED1, BEL1, TUR1, CZE1, GER2, GER3.
Membership and first-team coverage → frozen plan → Native10 write/reread/exact diff
→ ONE representative new-career smoke. No advanced ratings, long simulation,
engine optimization or installer work. Original game installation remains protected.

## Current evidence

- Canonical official membership: `data/current/league-membership-2026-27.csv`,
  12 competitions / 222 clubs. Integration sidecar retains team types/source hashes.
- Current squads: 6,272 observations, all 222 clubs. Inputs:
  `data/current/workers/eng-ger/tm-squads.csv` and `workers/south-west/rosters.csv`.
- Current scoped transfers: `data/current/evidence/transfer-events.csv`, 7,255 rows.
- Targeted exception profiles: `data/current/evidence/review-profiles.csv`,
  499/499 fetched, immutable source hashes retained.
- South-west worker: 34 existing identities resolved, 61 adult create-ready proposals
  after duplicate checks. Additional 106 identity reviews / 21 known identities retained
  in `data/current/workers/south-west/create-ready-review.csv`. Sol must intake.
- Primary deltas: Capelle/Bamba retirements, Magri to Al-Gharafa, two official Serie A
  shirt corrections. Lahmadi destination remains a specific review.

## Implementation and holds

Canonical reconciliation: `tools/current-integration.py`. Latest counts/gates:
`reports/current/integration/integration.json`. Never equate source capture or an
unchanged source row with proof of applied native state. Coverage is not yet complete.

Belgium requires18/15 top-two format and lower membership chain. Typed implementation
`src/native/belgium_format_plan.h` with tests. Source membership manifest:
`data/current/belgium-membership-format-2026-27.manifest.json`; two lower dependency
gaps remain at this checkpoint. No review rows may be applied.

GER3 needs membership and regional dependencies. Fresh accepted-base inspection:
`data/generated/native10-base-competition-inspection-20260912-01` (generation in progress).
Native unique club IDs differ from serialized CountryScript references. Earlier worker
old-ID values were corrected; verify against fresh preconditions.
Official Nordost18/Bayern19 evidence: `data/current/german-regional-dependencies.csv`.
Bayern needs a native format change; no binary patch.

`tools/build-native10.py` snapshots plans/executable/base hashes and orchestrates
read → combined native plan application/write → reread → semantic diff.
Production freeze is refused while coverage is incomplete; draft builds are labeled.
No Native10 release has passed and no new smoke has run.

## Next actions

1. Sol integrates targeted profiles, proven creation records and preserving loan actions.
2. Close Belgium/German structural dependencies using official current evidence.
3. Build/test native changes; freeze canonical plan only when coverage passes.
4. Generate Native10, exact diff and candidate membership validation.
5. One representative smoke after data completion; final report with actual gates/counts.

Historical state: `reports/current/PROJECT_STATE_PRE_DATA_SPRINT.md`. Its pending loan
tests are superseded, not active work. First sprint evidence checkpoint: commit39192c5.
