# FM27 Community Overhaul — Project State

Updated 2026-09-13; football evidence snapshot 2026-09-12. Active production sprint:
complete the 2026/27 football database.

## Active implementation-only directive

No football web research. Football facts and resolved identities are supplied
externally in `FM27_RESOLVED_REVIEW_QUEUE.csv` and associated resolved manifests.
These supersede older source-research tasks and policy holds where explicitly resolved.
Import decisions exactly: APPLY implements the supplied state; KEEP_EXISTING makes
no football-data change; CREATE uses supplied player/identity data; NONBLOCKING
removes the row from release-blocking coverage; ESCALATE_TECHNICAL investigates
only the implementation conflict. Reopen resolved rows only for concrete native
identity/reference/condition/serialization/invariant conflicts, reporting the exact
failure. Do not reopen confirmed identities or reinterpret football facts.
After import: deterministic deltas, coverage rebuild, frozen plan, native write and
reread, semantic diff, regression tests, candidate, technical-blocker report.
Input discovery: the named resolved queue/manifests are not yet present in the
project, supplied workspace roots, or top-level Downloads/Desktop/Documents.
Await the supplied artifact location; do not substitute older unresolved queues.

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
- Identity work integrated: 54 cleared player-creation rows with FIFA ID 0,
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
Preserve all immutable failed build records. Draft03 failed before writing on13
SQUAD loan rows with unproven intermediate ownership. Its completed before exports
now support an offline all-row preflight, including creation inputs.
Path: `data/generated/release-candidate/native10-data-draft-20260912-03`.

Draft04 WRITE/REREAD PASS and native membership12/12 PASS, but **IDENTITY GATE FAIL**:
11 of94 creations duplicate existing players through name variants (including
Arokodare, Koulierakis, Trubin). They caused the11 new native string-ID collisions.
Do not use semantic-v3 field-comparison PASS as release signoff. Explicit veto:
candidate `RELEASE_GATES.json`. Corrected identity audit committed as4f0d19a:
11 confirmed existing-player bridges,26 plausible alias holds,3 loan-creation holds.
Draft04 contains240 squad actions and94 creations; its earlier offline preflight
did not sufficiently detect alias duplicates. The strengthened preflight now passes
the corrected250 squad actions and54 creations with0 errors and0 warnings.
Native self-tests passed but did not catch this source-identity defect. Candidate path:
`data/generated/release-candidate/native10-data-draft-20260913-04`.
Executable snapshot SHA94f77cbe0f06c26ca16e042e90721abba287d2fd1c5a6976015100fe94b8da60.
The13
ownership-chain rows are held; five sourced same-owner early borrower switches use
a narrow guard (prior loan expired by snapshot, unchanged owner, different borrower,
joined after prior start, explicit current profile dates).
Use latest `integration/integration.json` for current counts; no production freeze.
Post-Draft04 delta: `data/current/integration/native10-post-draft04-additions.csv`,
six safe additions (five metadata corrections and Hamidou Kante loan return).
Current full plan250 +54 creations passes offline preflight. Thirty common-row
provenance changes are deliberately not replayed as native changes. Commitaa5e5db.
Current blockers488: contract220 (85 user-policy pending), transfer timeline155,
creation72, typed26, ownership chain13, primary1, affiliation1.
Exact prerequisites: `reports/current/integration/terminal-data-queue.csv` and JSON.
Source attempts are exhausted; do not restart Luna searches or broad loan analysis.
Last matrix checkpoint52 GOOD_ENOUGH /170 PARTIAL. All59 profile employer conflicts were resolved
with explicit parent/reserve aliases and passed onward through independent guards.
Provisional creation ratings are retained but are not blockers for this data sprint.
Twenty explicit departure resolutions and116 typed-condition evidence rows are
available in worker artifacts; integration continues. All referenced cached bytes
were hash-verified. Ten duplicate rows resolved as five parent/reserve identities.
Creation triage100:20 prior existing identities,1 already create-ready,79 specific
prerequisite holds after two source attempts. No further Luna search loops on these.
`reports/current/UNDISCLOSED_CONTRACTS.csv` lists85 permanent moves with agreeing
roster/profile and known join but unknown end and expired native end. No substitute
dates have been generated. A bounded provisional-end policy question is pending;
do not apply any exception without the user's answer.

## Next actions

1. Draft05 completed from corrected immutable250/54 inputs:
   `data/generated/release-candidate/native10-data-draft-20260913-05`.
   WRITE/REREAD/EXACT SEMANTIC DIFF PASS; membership12/12 PASS. Total266818
   players; zero new opaque serialization rewrites. All250 planned changes and54
   creations match. Existing ratings and future conditions preserved. Exact report:
   candidate `EXACT_PLAYER_FIELD_DIFF.csv`, `EXACT_CHANGE_SUMMARY.json`,
   `DELTA_PROVENANCE.csv` and `RELEASE_GATES.json`. Session96967 completed.
   Draft04 cannot be released. Preserve all failed evidence. Post-build delta remains
   separate: `data/current/integration-staged/native10-post-draft05-condition-delta.csv`
   has6 guarded actions preserving exact raw injury/ban parameters. Proof recovered
   all9 missing condition types;3 ownership cases remain held. Commitb5b5557.
   Protected-condition binary exists for a future delta build; Draft05 keeps its
   immutable preflight2 binary and does not contain these6 actions.
2. Preserve the six-row post-Draft04 delta for the next explicitly recorded data
   build. Await the pending85-contract policy decision; do not invent dates.
3. Build/test native changes; freeze canonical plan only when coverage passes.
4. Draft05 is a validated incomplete data checkpoint, not a production release.
   Resolve documented source/policy holds before another integrated data build.
5. One representative smoke after data completion; final report with actual gates/counts.

Historical state: `reports/current/PROJECT_STATE_PRE_DATA_SPRINT.md`. Its pending loan
tests are superseded, not active work. First sprint evidence checkpoint: commit39192c5.
