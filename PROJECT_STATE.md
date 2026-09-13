# FM27 Community Overhaul — Project State

Updated 2026-09-13; football evidence snapshot 2026-09-12. Active production sprint:
complete the 2026/27 football database.

## Publication target

The only project publication remote is
`https://github.com/Matchekk/FIFA-Manager-27-Fan-Made-`. Do not publish FM27
commits or artifacts to Aelunor. Commit and upload only useful source, plans,
validated data, reports, installer material and release artifacts; omit temporary
working files, caches, failed scratch candidates and local game-installation files.

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
External pass1 is imported and hash-validated: 624 stable row IDs with 6 APPLY,
97 KEEP_EXISTING, 137 NONBLOCKING and 384 ESCALATE_TECHNICAL decisions. The
deterministic importer is `tools/import-external-football-resolutions.py`; no
football web research was performed. It produced a guarded plan for 542 existing
players and 57 identity-audited creations. Fifty-seven supplied identities were
bridged to existing native players without duplicates.

Current candidate: `data/generated/release-candidate/native10-data-external-pass1-20260913-02`.
Native write PASS, independent reread PASS, corrected exact semantic diff PASS,
membership 12/12 PASS. Exact result: 542 planned existing-player states, 57
creations, 442 club assignments, zero rating changes, zero future-condition
changes and zero unplanned serialization rewrites. The original comparator
failure is retained and hash-bound in `SEMANTIC_REVALIDATION.json`; it incorrectly
required pure club-list moves to rewrite the player block. Python tests 305 PASS;
native tests 127 PASS.
The hash-bound checkpoint summary is
`reports/current/NATIVE10_EXTERNAL_PASS1_VALIDATION.json`.
The Native10 external-pass1 editor database was reversibly deployed to the
isolated `runtime/loan-test-20260912-08`, compiled to a new runtime-only
`Master.dat`, and launched from that exact runtime. The user confirmed that the
game works. Runtime activation: PASS. This does not replace the representative
completed-data new-career smoke, which remains deferred until production freeze.
Evidence: `reports/current/NATIVE10_EXTERNAL_PASS1_RUNTIME_ACTIVATION.json`.

Runtime quality-of-life profile `relaxed-career-v1` is applied to the isolated
Native10 runtime: 54 guarded patch groups in 10 parameter files cover morale,
trust, transfers, sponsors, scouting, board pressure, fatigue, training,
injuries, staff, youth development, youth camps and cooperations. The earlier
communication fix is included in the combined deterministic profile. The
running game was left open to protect unsaved progress; the tuning loads on the
next launch. Original installation unchanged. Profile, tool and validation:
`data/parameter-tuning/relaxed-career-v1.json`,
`tools/apply-relaxed-career-tuning.py`, and
`reports/current/RELAXED_CAREER_TUNING.md`.

Coverage: 222 clubs; 179 GOOD_ENOUGH, 43 PARTIAL, 0 BLOCKED. The current matrix is
`data/current/CLUB_COVERAGE_MATRIX.csv`. Production freeze remains closed because
55 exact technical conflicts remain: 30 owner contracts end before supplied loan
ends, 13 resolved loan timelines end after supplied owner contracts, 5 ambiguous
local native identities and 7 creation records without a safe native bridge or
complete creation fields. Do not guess these values. The exact queue is
`reports/current/integration-resolved-pass1/TECHNICAL_BLOCKERS.csv`.

## Accepted foundation

Native08 accepted base: `data/generated/release-candidate/native08-integrated-20260912-01/database`.
Integrated history/ratings, native reader/writer, Editor export, new career, save/load
and first season transition work. User confirmed corrected loans in a NEW career: PASS.
794 active loans, 744 corrected begins, 50 intentional unchanged begins. Do not redo
Native07/08 or investigate the general loan root cause.

## Relaxed development profile

`dynamic-development-v1` is applied to the isolated runtime after
`relaxed-career-v1`. It uses global `DC.txt` and `Training.txt` behavior for AI and
human clubs, moves the outfield target-age window to 24–28 (goalkeepers 26–30),
raises performance-led match/training development, lowers general decline, and
allows more positive national-competition re-evaluations. Guarded application and
idempotent reread passed for all 18 patch groups; 305/305 automated tests passed.
A read-only inspection of the decrypted runtime code confirmed the separate
star-talent evaluator already uses an exclusive age-25 gate, so talent changes are
eligible through age 24 for club rosters; no executable patch is required.
Original installation, executables and save files remain unchanged. The live game
was not interrupted, so the new parameters load at the next normal restart. Exact
profile and evidence: `data/parameter-tuning/dynamic-development-v1.json` and
`reports/current/DYNAMIC_PLAYER_DEVELOPMENT_TUNING.md`.

## Relaxed QoL v2 profile

`relaxed-qol-v2` is applied on top of the two earlier comfort/development
profiles in the isolated Native10 runtime. It adds youth-player retention,
friendlier player and manager negotiations, fewer match injuries and faster
recovery, gentler finances, cheaper and faster facilities, stronger sponsor/fan
stability, more effective staff, lower routine discipline pressure and rarer
private-life relationship declines. The deterministic application changed 16
parameter files: 65 exact patch groups and 1,443 guarded construction cost/time
values. Final reread was idempotent (0 changes), facility block structure passed,
and 305/305 Python tests passed. Match goal/attack/card probabilities, executable,
database and saves were not changed. The protected original installation remains
unchanged. The running game was left open; this profile loads after the next normal
restart. Exact profile, tool and report:
`data/parameter-tuning/relaxed-qol-v2.json`,
`tools/apply-relaxed-qol-tuning.py`, and
`reports/current/RELAXED_QOL_V2_TUNING.md`.

## Overpowered staff profile

`overpowered-staff-v1` is applied on top of all relaxed profiles in the isolated
Native10 runtime. Nineteen guarded patches across `Staff Tasks.txt`, `Training.txt`,
`Staff Generation.txt` and `Staff.txt` make existing staff task/training effects
very strong, reduce staff motivation/stress pressure, accelerate staff skill growth
and create much stronger future staff. Guarded application and exact idempotence
passed, 305/305 Python tests passed, and the protected original installation is
unchanged. The running game remains open, so the new values load at the next normal
restart. Exact profile and report: `data/parameter-tuning/overpowered-staff-v1.json`
and `reports/current/OVERPOWERED_STAFF_TUNING.md`.

## Polish-German youth mix profile

`polish-german-youth-mix-v1` is applied after the relaxed and overpowered-staff
profiles in the isolated Native10 runtime. The one guarded country-pair patch raises
the Germany-to-Poland youth-generation values from 1.04 to 6.0 for first nationality
and from 1.0 to 12.0 for second nationality. This makes future Polish and
German-Polish youth players more common at German clubs while preserving the normal
German pool and every other country pair. The parameter table is scoped by club
country and has no manager-nationality input, so this safe implementation applies to
all German clubs rather than dynamically following the human manager. Application,
idempotence and 305/305 Python tests passed; the protected original installation is
unchanged. The running game remains open and the values load after the next normal
restart. Exact profile and report:
`data/parameter-tuning/polish-german-youth-mix-v1.json` and
`reports/current/POLISH_GERMAN_YOUTH_MIX.md`.

## 3D match-engine attribute evidence

A read-only inspection now separates actual 3D match influence from the displayed
position-strength matrix. `GfxCore.dll` directly references the raw match attributes
and the active sprint, dribbling, heading, shooting, passing, tackling and marking
tuning stored in `config.big`. There is no single global 3D attribute-weight table:
attributes enter movement, action and duel formulas. Direct evidence includes sprint
speed endpoints 6.0 to 11.0 engine units; aerial-duel weights of 55% jumping, 25%
strength, 15% height and 5% front position; and nonlinear action-quality curves for
eight technical/defensive actions. Acceleration is consumed by the engine but its
curve remains hard-coded. A complete FM-Arena-style ordered ranking needs controlled
repeated matches with one attribute varied at a time. No engine, database, parameter
or save file was changed. Evidence and deterministic extractor:
`reports/current/3D_MATCH_ENGINE_ATTRIBUTE_INFLUENCE.md`,
`reports/current/3d-match-engine-attribute-influence.json`, and
`tools/inspect-3d-match-engine-attributes.py`.

## 3D match-engine tactics code evidence

A second read-only audit traced the actual team-tactic payload and the active 3D
action-selection constants. `Fifa07Team::ParseTeamWrite` proves that the runtime
receives offside trap, without-ball behavior, formation, attack, mentality and two
attacking plus two defensive tactic fields. `GfxCore.dll` directly references 25
selected context-dependent keys for forward progress, action/receiver safety,
passing type, shooting distance and dribble direction. Two additional selected
values, including goal angle, remain config-only evidence. There is no
global formation or tactical-quality score, so a universal best tactic cannot be
proved from static code. The bundled FIFAMARK repeat-match path is explicitly marked
as needing repair for the new AI and is commented out. A best-tactic claim therefore
requires a new controlled repeated-match harness. No gameplay file changed. Exact
evidence and deterministic extractor:
`reports/current/3D_MATCH_ENGINE_TACTICS_CODE_EVIDENCE.md`,
`reports/current/3d-match-engine-tactics-code-evidence.json`, and
`tools/inspect-3d-match-engine-tactics.py`.

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

## Offer-to-all-clubs QoL

The `13TransfersOfferToClub` dialog now has a native-styled
`Spieler allen Vereinen anbieten` button. A guarded x86 ASI hook snapshots every
club ID in the currently visible list and reuses the game's existing validation and
offer routines for each unique club before one native refresh. The direct German
label avoids an unregistered runtime translation key. Result feedback uses the
game's own localized modal-dialog path, so fullscreen focus stays inside the game.
`Manager.exe` and
`screens.big` are not edited. The hook is bound to the supported executable hash and
runtime signature and fails closed on other builds. Build, installer, normal/dark UI
overrides and implementation evidence are in the repository; the isolated runtime
loaded the plugin and logged `PATCH_APPLIED`. Manual in-dialog click smoke remains.
