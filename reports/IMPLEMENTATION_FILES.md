# Implementation file changes

## Master-goal continuation

`reviewed_rosters.py` validates individually reviewed permanent transfers that
supersede an exact older primary roster observation. It binds the full native
identity, snapshot, original DFB rows, current roster/profile hashes and three
official source roles. Both reconciliation tools consume the same review;
loans and releases do not inherit a permanent-transfer exception. Nine new
regression tests cover stale sources, changed people/destinations/dates, loans,
duplicate reviews, missing facts and independent-source requirements: Python289PASS.
Thomas is the first reviewed case. Full-row multiset comparison confirms that
all6265other current observations and4421prior plans remain unchanged. The first
wrapper's TM-ID-only comparison failed on repeated observations; its failure is
retained alongside a separate successful multiset assessment.

`missing_player_review.py` adds conservative cross-club full-name and nearby or
same-club birthday conflict leads. These only prevent accidental duplicate
creation; they never authorize identity, transfer or birthday changes. Eleven
regression tests brought the prior Python total to280. Current source overrides
contain28reviewed player identities,3historical events and148external club aliases.
Fulham U21 is explicitly mapped to its existing English native parent/reserve,
supported by its official Amissah biography and exact cached loan-owner profile.

`transfer_rating_validation.py` accepts the two real source date representations
and validates planned reserve/youth flags separately from retained rating fields.
The cumulative CLI binds baseline IDs and complete serialized player states to
the source archive. Native05 passes all11pipeline steps and11cumulative checks;
the prior native04 date-comparison failure remains separately frozen.

`player_identities.py` now accepts explicitly reviewed EA common names only with
exact cached HTML/CSV agreement. Four regression tests cover valid corroboration,
missing review, forged common names and identity conflicts; Python245PASS.
`validate-cumulative-transfer.py` binds an incremental transfer to frozen source
ratings and proves complete rating/world/script preservation. Increment01 adds the
existing Alysson transfer and passes all11pipeline steps;2844evidence files frozen.
Current overrides contain17reviewed identities,3historical events and138club aliases.
`reconcile-departures.py` and `validate-production-candidate.py` expose
`--no-project-status` for isolated reports that must preserve cumulative status.
These CLI additions postdate the frozen candidate proof; no native source changed.

`review-rating-field-retention.py` evaluates conservative partial profiles for756
sole-extreme-review cases, retaining1096disputed attributes. The native evaluator
recomputes all220428variants and confirms all181116unaffected variants exactly.
`integrate-retained-rating-profiles.py` binds source/model/native evidence, retains
the3009prior plan rows and materializes3765source-bound native proposals.
The resulting ratings02 candidate passes full native validation for82863changes.
`validate-rating-retention.py` additionally proves the actual prior3009native rows
and1096retainedfields are unchanged. Actual AFTER/diff reports are regenerated;
completed02 evidence freezes155files. No core/native/model source changed.

`rating_batch.h` reads hashed individualPLAYERblocks with the native reader and
checks baseline position/style/experience/37attributes/level parity.52alternatives
perplayer allow native calibration without repeated world loads.123native tests pass.
`rating_calibration.py` adds monotonic positional-scale fitting and deterministic
identity holdout; nine tests bring Python to241. The reviewed GK mapping revision
retains incompatible generic fields and applies explicit upstream GK formulas.
Calibratedplan02 passes distribution/holdout gates for3009players, holding1230.
`stage-native-ratings.py` wrote the external candidate. `validate-native-ratings.py`
passes all21 native scope, world and roundtrip checks for3009players/65310attributes.
`report-validated-ratings.py` reproduces the original BEFORE distribution, proves
the complete pre-rating native level universe matches it, and creates the actual
AFTER distribution (56 groups) and3009-row detailed player diff on fixed cohorts.
The new completion archive freezes151 evidence files; the earlier173-file
source/model archive remains separate. Editor and game gates remain open.

`rating_plan.h` and20native tests add a guarded FM13 rating inspection, preview and
stage path.119native tests pass. It binds full player serialization, updates only
the37persisted attributes atomically and validates native expected levels before
staging. `inspect-native-ratings.py` verified266764combinedcandidateplayers.
`plan-rating-preview.py` reparsedEAevidence and bound4239target-squad proposals.
`preview-native-ratings.py` runs the in-memory experiment and checks protected
fields, exact attributes, untouched players and level distributions. Calibration
and actual rating database staging remain pending.

`rebase-league-plan.py` binds the existing52slot plan to transfer15 after proving
identical207competition scripts and canonical competition baseline. Combined01
passes the full native reread and exact-script validator. The new
`validate-native-combined.py` binds preserved transfer15 player semantics, candidate
file hashes, source evidence and644support files into one combined proof.
The standalone transfer report stays separate; PROJECT_STATUS identifies the
combined candidate explicitly. Full formats, ratings and game gates remain open.

`league_sources.py` strictly parses the requested competition/season and unique
club IDs, rejecting cross-linked identities. Eight new cases bring Python to232PASS.
Nine second-tier source tables were captured;22relegated-club identities were
explicitly reviewed without changing global transfer aliases. The new
`extend-league-moves-with-relegations.py` freezes52rows covering19competitions.
League candidate02 passes complete native reread, unchanged-world and exact-script
validation, matching ten requested primary memberships. Evidence archive has139files.
Belgium membership/rule review02 includes its additional amateur-boundary changes.
Source15 passes all12native steps with the unchanged99test binary:5490changedplayers,
2854clubchanges,787loans and644support files. The central transfer report now points
to15. Historical league02 derives from14; combined01 now includes transfer15.

`league_membership_plan.h` and19native cases implement atomic full/sparse domestic
membership plans, global team conservation, native calendar and pairing guards.
Native99PASS. `plan-closed-league-moves.py` freezes only balanced moves whose two
endpoints have reviewed in-scope memberships; unchanged slots inherit the baseline.
`stage-native-leagues.py` binds every input database file, raw source, build and test.
`validate-native-league-membership.py` checks full native semantics and entire script
texts, allowing only approved TEAMS substitutions. Candidate league-membership01
has ten changes across GER1/2/3 and644support PASS; full reread and script comparison
PASS. GER1/GER2 memberships exactly match their reviewed targets; GER3 retains four
pending incoming and four pending outgoing regional teams. No other script fields,
player records, staff, relations, club/country records or global entities changed.
This candidate derives from transfer14, not the unstaged transfer15 plan.

Source15 adds `historical_transfers.py`, explicit season/event selection in
`transfermarkt.py`, and integration in current/departure reconciliation.8newPython
tests verify source/profile/native bindings and rejection of conflicting arrivals;
224Python PASS. All6137source14rows unchanged, two reviewed winter arrivals added.

`competition_inspection.h`, the new `--inspect-competitions` native mode and7native
fixtures expose competition members, calendar slots, match pairings, instruction
ranges and all predecessor/successor/instruction/pool-constraint references.
Native80PASS. `inspect-native-competitions.py` verifies source preservation and
binds evidence; `review-native-league-dependencies.py` joins actual native graphs
to all12 source-bound target memberships. This is preparation for native league
mutations, not a passed league/game gate.

Current source14: `player_identities.py` verifies reviewed name variants and
hash-bound official EA evidence for people whose native FIFA ID is zero. The ID
stays zero; globally assigned or contradictory source IDs are rejected.
`contracts.py::retain_existing_end` implements Master section18 by retaining an
exact plausible native end only when the source omits it. `reconcile-current.py`
and `transfer_timeline.py` keep event, identity, date, loan and conflict checks.
Seven identity tests and seven contract/integration tests bring Python to216 PASS;
native73 PASS is unchanged. Source14 audit preserves every source13 row and adds
188SQUAD rows; native14 passed all12 stages with5488changedplayers and2852clubchanges.
Game/export/league/rating gates remain open. `tools/report-rating-baseline.py` now
creates the required native before-distribution; the separate baseline audit against
candidate14 verifies unchanged native levels/styles through canonical reread identities.

Official loan evidence: src/fm27/primary_loans.py and tests/test_primary_loans.py
validate reviewed club announcements, cached source bytes and exact current-profile
bindings. loans.py supports explicitly mapped parent/reserve legal owners while
retaining exact borrower IDs. public_cache.py adds two reviewed official hosts.
reconcile-departures.py binds supplemental evidence and preserves announcement
dates separately. Python179 PASS; native source unchanged/native73 PASS. Plan10
adds23 proposals to unchanged plan09 and is undergoing native validation.

Final purchase-and-loan source guards reject earlier owner sales without later
dated reacquisition and inconsistent later loan starts. Python173/native73 PASS.
Plan09 freezes22 new chains on top of unchanged5815 prior rows; native validation
is orchestrated by .agent_tmp/validate-purchase-candidate-09.py with per-step logs
and reports/local/NATIVE_VALIDATION_RUN_09.json. Six additional reviewed reserve
aliases (review05) are a later source change and require the next reconciliation.

Purchase-and-loan extension: src/fm27/purchase_loans.py supplies acquisition
evidence checks; loans.py resolves prior native ownership and emits a distinct
PURCHASE_AND_LOAN action with five acquisition provenance fields. stage_plan.h
validates seller/owner/borrower, old-loan expiry and evidence before mutation.
Projection, plan merge, source reconciliation and aggregate counts understand the
new action. tests/test_purchase_loans.py and tests/native_purchase_tests.h cover
source conflicts, chronology, buy-option non-inference and atomic rejection.
Python170/native73 pass; real new-candidate validation remains pending.

Latest verified candidate07 includes exact expired/successor-loan resolution, pairwise
relationship writing and preservation of external scripts/history/name tables.
Relevant additions: `src/native/staging_support.h`, `tests/native_expired_tests.h`,
`src/fm27/expired_loans.py`, `tools/stage-native-candidate.py`,
`tools/validate-native-support.py`, `tests/test_latin_identity.py`.
Player, staff, competition and relationship roundtrips PASS. Original installation
unchanged; league/rating/world/game gates still prevent a release claim.

Further current additions: `tests/native_successor_tests.h`, guarded full-profile
name recovery in `src/fm27/matching.py`, 52 reviewed external club aliases,
`src/native/world_semantics.h`, `tests/native_world_tests.h`,
`src/fm27/world_validation.py`, `tests/test_world_validation.py`,
`tools/compare-native-world.py` and the read-only `--inspect-plan` native mode
(`stage-native-candidate.py --inspect-only` binds its frozen-plan/build/test evidence).
World and global inspection now PASS against actual candidate07, bound to its
verified player bytes and frozen plan. `global_semantics.h`, `native_global_tests.h`
and evidence binding in `world_validation.py` extend coverage. The source-file
inventory `tools/audit-native-file-coverage.py` identifies auxiliary/compiled-data
gaps; support writer/validator now preserve six additional original files. Candidate08
is being built. Full source-file/game export coverage remains an open gate.

The following additions extend the existing project after its original delivery:

- Transfer timeline/profile parsing, exact global identity recovery, dated outside
  departures, typed native loans and explicit free-agent releases.
- Native full serialized player hashes, projected candidate checks, mutation-scope
  diffs and evidence-bound production status (release gates remain incomplete).
- Atomic profile checkpoints, scoped review-profile fetching, profile contract
  corroboration and native baseline ID binding for originally clubless people.
- Read-only league membership/calendar/fixture review with reserve references.
- Native fixtures and a runner tied to build/binary/source hashes; expanded Python
  tests. Reviewed outside-club overrides retain their source and country context.

See `HANDOFF.md` and `docs/FORTSCHRITT.md` for exact current candidates and counts.
The table below describes the historical initial addition set only.

All entries are new files in the independent FM27 repository. Counts are approximate; no Aelunor files changed.

| File | Added | Removed |
|---|---:|---:|
| .gitignore | +12 | -0 |
| HANDOFF.md | +87 | -0 |
| README.md | +107 | -0 |
| benchmarks/COMPARISON.md | +4 | -0 |
| benchmarks/baseline.json | +77 | -0 |
| benchmarks/baseline.md | +6 | -0 |
| config/fpl-club-aliases.json | +22 | -0 |
| config/scope.json | +18 | -0 |
| config/upstream-lock.json | +22 | -0 |
| docs/AUDIT.md | +100 | -0 |
| docs/BENCHMARK_PROTOCOL.md | +40 | -0 |
| docs/SAVE_COMPATIBILITY.md | +15 | -0 |
| docs/SCOPE.md | +22 | -0 |
| docs/UPSTREAM_ARCHITECTURE.md | +92 | -0 |
| reports/BUG_MATRIX.md | +24 | -0 |
| reports/IMPLEMENTATION_FILES.md | +48 | -0 |
| reports/PERFORMANCE_REPORT.md | +15 | -0 |
| reports/RATING_CALIBRATION.md | +18 | -0 |
| reports/VALIDATION_SUMMARY.md | +27 | -0 |
| src/fm27/__init__.py | +2 | -0 |
| src/fm27/audit.py | +76 | -0 |
| src/fm27/benchmark.py | +32 | -0 |
| src/fm27/common.py | +36 | -0 |
| src/fm27/database.py | +178 | -0 |
| src/fm27/matching.py | +52 | -0 |
| src/fm27/pe.py | +44 | -0 |
| src/fm27/reconcile.py | +153 | -0 |
| src/fm27/sources.py | +80 | -0 |
| src/fm27/squad_compare.py | +84 | -0 |
| src/fm27/validate.py | +53 | -0 |
| src/native/db_probe.cpp | +71 | -0 |
| tests/process_probe.cpp | +11 | -0 |
| tests/test_core.py | +228 | -0 |
| tools/Install-Toolkit.ps1 | +32 | -0 |
| tools/Launch-Benchmark.ps1 | +19 | -0 |
| tools/Measure-Run.ps1 | +105 | -0 |
| tools/Uninstall-Toolkit.ps1 | +32 | -0 |
| tools/build-native.ps1 | +53 | -0 |
| tools/compare-native.py | +42 | -0 |
| tools/compare-squads.py | +15 | -0 |
| tools/fm27.py | +46 | -0 |
| tools/hardware.ps1 | +23 | -0 |
| tools/package-toolkit.py | +25 | -0 |
| tools/validate-data.py | +26 | -0 |
| tools/verify-unchanged.py | +31 | -0 |
# 08.09.2026 — preserve plausible native owner contracts (candidate11 native PASS)

`src/fm27/loan_contracts.py` implements master-request section18: preserve a
plausible existing FM value when uncertain contract detail is absent. It returns
the native contract end unchanged only for an exact same legal owner, covering the
whole new loan with valid native joined/date chronology. An expired loan owner is
resolved through its unique serialized reference; borrower/seller contracts are
not carried to another owner. Protected, duplicate, active or malformed conditions
remain held. `loans.py` applies this only when the current source end is empty,
reports source and native values separately, and retains all event/identity guards.
`tests/test_loan_contracts.py` adds11 helper/integration cases; Python190 PASS.
Native code is unchanged. Candidate10 remains historical179-Python/73-native PASS;
Candidate11 now passes its own complete implemented native validation for784loans,
including57preserved native contract ends. No game readiness claim.


## Reviewed existing-player identities — 08.09.2026

`src/fm27/player_identities.py` binds individually reviewed spelling variants to the
immutable baseline and exact current profile bytes, native ID/FIFA/name/DOB/nation/
club and reviewed destination. It rejects competing native/source identities and
FIFA conflicts. No general fuzzy matcher or new-person creation is enabled.
`matching.py`, `transfer_timeline.py`, current/departure reconciliation and the
missing-player review consume these guarded identities. Current and missing-player
profiles are reparsed from their verified cached HTML. Twelve new regression tests
bring the Python suite to202 passing tests; native73 remains unchanged.

Candidate12 freezes the initial two identities (Seol and Konoplia) plus review08
club aliases. Its5940-row source plan preserves all5935candidate11 rows exactly.
The later ten-identity review02 and EstorilU23 club alias are separate source work
for candidate13. Arizala is excluded pending conflicting official contract dates.
