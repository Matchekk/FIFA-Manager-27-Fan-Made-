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
- Identity work integrated: 71 guarded player-creation rows with FIFA ID 0,
  duplicate-search evidence and explicitly provisional conservative attributes.
  One Martinique/France nationality exception remains held.
- Primary deltas: Capelle/Bamba retirements, Magri to Al-Gharafa, two official Serie A
  shirt corrections. Lahmadi destination remains a specific review.

## Implementation and holds

Canonical reconciliation: `tools/current-integration.py`. Latest counts/gates:
`reports/current/integration/integration.json`. Never equate source capture or an
unchanged source row with proof of applied native state. Coverage is not yet complete.

Belgium18/15 format and minimal lower dependency chain are implemented and tested.
Apply only `data/current/belgium-native-plan.csv` (113 rows), with its manifest.
The broader research table contains unrelated review rows and is not production input.

GER3 and minimal regional dependencies are implemented and tested in
`src/native/germany_format_plan.h`; input `data/current/germany-native-plan.csv`
(165 rows). This replaces the generic GER3 membership plan; never apply both.
Bayern19 uses a stable modeled format; exact 2027/28 transient adaptation is not claimed.
Fresh accepted-base inspection is complete at
`data/generated/native10-base-competition-inspection-20260912-01`.
Native08 target membership audit:10/12 pass; Belgium/GER3 require the new native plans.
Native unique club IDs differ from serialized CountryScript references.

`tools/build-native10.py` snapshots plans/executable/base hashes and orchestrates
read → combined native plan application/write → reread → semantic diff.
Production freeze is refused while coverage is incomplete; draft builds are labeled.
No Native10 release has passed and no new smoke has run. Draft01 failed safely on
expired metadata contract dates. Draft02 failed before writing on acquisition fields
attached to an unrelated action; Sol owns the focused correction and input preflight.
Preserve both immutable failed build records. Next candidate must use a new name.

Latest reconciliation:123 squad actions,66 club changes,71 creations;711 blocking
review rows and390 essential wrong-state holds. These are incomplete draft inputs.
`reports/current/UNDISCLOSED_CONTRACTS.csv` lists85 permanent moves with agreeing
roster/profile and known join but unknown end and expired native end. No substitute
dates have been generated. A bounded provisional-end policy question is pending;
do not apply any exception without the user's answer.

## Next actions

1. Sol fixes draft02 action-field preflight, then continues typed-condition holds.
2. Worker resolves22 explicit source-absence exceptions; another audits club coverage.
3. Build/test native changes; freeze canonical plan only when coverage passes.
4. Generate Native10, exact diff and candidate membership validation.
5. One representative smoke after data completion; final report with actual gates/counts.

Historical state: `reports/current/PROJECT_STATE_PRE_DATA_SPRINT.md`. Its pending loan
tests are superseded, not active work. First sprint evidence checkpoint: commit39192c5.
