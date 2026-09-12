# Latest handoff — deadline 08.09.2026 15:00 Europe/Berlin

The time-bounded delivery was completed before 15:00. Consult the goal tool
and docs/ABGABE_1500.md for the final delivery; do not confuse source coverage
with a complete game overhaul.

New: public FC27 website parser (5980 records, detailed stats/FIFA IDs),
Transfermarkt event parser (7178 rows across all 12 leagues), and detailed
current squad parser (6266 records, 222/222 teams, no source failures).
Native FC27 file schema remains unsupported; this is the official website payload.
All raw sources are local, hashed, timestamped and excluded from distribution.

Reviewed club aliases map all 222 observed teams to installed owner/team IDs.
Current reconciliation uses FIFA ID via DOB/name corroboration, then exact
DOB/name; DFB contradictions and existing complex native conditions are held.
The frozen .agent_tmp/frozen-squad-plan-20260908.csv has 3820 rows, 948 club
changes, with current contracts/shirt/squad metadata. No ratings applied.

Native bridge now supports --stage-plan and validates all row preconditions
before any in-memory mutation. It removes old club membership/captain pointers,
adds target membership, preserves attributes/talent and injury/league-ban data.
It refuses loan/retirement/future conditions. All writes are external/new only.
Candidate run: .agent_tmp/candidate-stage.log, output
 data/generated/candidate-20260908-1500. Original native executable used.
Source projection with reserve_shirt_number: data/intermediate/baseline-final.
Candidate validation PASSED at 14:57:44 local: all 266764 projected players match the 3820-row plan, 948 club changes, zero unexpected missing/added rows. Validate final candidate with tools/validate-candidate.py and inspect
reports/local/CANDIDATE_VALIDATION.json. A partially written directory is NOT success.

An optional -OptimizeOffline native build uses a separate build/upstream-optimized
shadow. It changes only compiler optimization for offline tooling, not the game.
The optional optimized offline build completed at delivery; it has not been runtime-benchmarked and was not used by the candidate. The standard native build passed.

42 unit tests pass after source/serializer additions. Recheck latest logs and
actual candidate validation. Full engine/save tests, complete departures/loans/
missing players, 2026/27 competition promotion/relegation, calibrated ratings
and measurable non-3D improvements remain unfinished. Game capture still fails
with E_NOINTERFACE. No production installation is authorized by a projection pass.

---

# FM27 handoff — 2026-09-08

Project: C:\FM27CommunityOverhaul, independent Git repository on
`codex/fm27-foundation`. No commit/push made. Aelunor was inspected initially
because it was the supplied CWD; it was not modified.

## User authority and priorities

User authorized locating the installation, creating this separate project,
and installing all necessary development dependencies. Visual Studio 2022
Build Tools with v143 C++/Windows SDK installed successfully using winget.

Scope override: transfers/squads in 12 specified leagues first; detailed
current ability second; non-3D simulation/menu/save stability third. No 3D or
XXL work. Covered league list is config/scope.json. Do not broaden transfer
research to the whole world, but retain relationships with outside clubs.

## Actual results

- Game: C:\Fifa Manager 13\FUSSBALL MANAGER 13. Registry FM13; EXE resources FM26.
  Readme v1.0, season.ini 2025; live window identifies 2026 1.1.0. LAA already on.
- Read-only audit: 47,109 files, no read errors. All 943 inventoried hashed
  executables/plugins/configs/database files verified unchanged after the work.
- Five public upstream repos cloned and pinned in config/upstream-lock.json.
- Local native generic/fmapi/fifaapi libraries and x86 db probe compiled.
  Shadow copy under build/upstream uses fail-fast Error.h for unattended offline
  reads. Own bridge /W4 /WX; upstream warnings retained in build logs.
- Native read: 266,764 players, 13,270 clubs. Text projection includes 207
  national-team blocks as well. 255,297 persisted-ID comparisons match on
  FIFA ID, club and DOB. All-player identity multisets match including free
  agents. Free agents have no persisted person IDs in Without.sav.
- Installed coverage: 220 teams (218 owner clubs, two reserve teams) / 16,880 players including youth
  and reserves. Must reconcile actual 2026/27 promoted/relegated membership.
- FPL official 2026/27 snapshot with 654 entries cached on 2026-09-08. Review
  comparison: 325 same-club, 173 possible arrivals, 99 ambiguous/unavailable,
  46 missing, 11 identity-review entries; 117 unverified absences. No automatic
  transfer changes from FPL. German DFB roster comparison additionally covers 55/56 teams (18/17/20), 1,430 source records; eight other competitions remain unrefreshed.
- Identity validator: 23 duplicate FIFA-ID values, 14,851 contract-order
  candidates globally. No bulk fix applied; not proven crash causes.
- 39 synthetic unit tests pass, PowerShell syntax checks pass, native counter
  fixture recorded 8 samples successfully. Actual 30s process observation exists; controlled scenario timings not available.
- Toolkit ZIP packaged and installed/uninstalled in temporary project folders.
  Clean uninstall removed all installed files. Modified README and an unrelated
  test file were preserved in the separate preservation smoke test.

## Current operational state

User confirms normal startup through resolution selection. Attached to exact
Manager.exe PID 9412, window title Fussball Manager 2026 1.1.0. No startup
question remains. Launcher now supports attach and follows the selector flow.
30s process observation completed (114 samples); no controlled latency claim.
Native screenshot API fails SetIsBorderRequired E_NOINTERFACE on this Win10
host. One prescribed retry failed; text tree only has a root pane. No UI clicks.

Canonical native --stage-roundtrip wrote to external
`data/generated/roundtrip-20260908-01/database`. All 266,764 projected player
semantics match after accounting for native person-ID renumbering. This does
not certify all relations, competitions, histories, staff or game/save behavior.
Run tools/compare-roundtrip.py for the repeatable projection gate.

DFB official 2026/27 roster ETL is in tools/fetch-dfb.py. Isolated .venv and
requirements-data.txt provide BeautifulSoup. Source snapshots have SHA-256 and
retrieval times. Cached same-day retries avoid repeat downloads; parser refuses
old seasons, flags conflicting duplicate IDs and preserves players with no profile ID.
Inspect reports/local/DFB_FETCH.json for actual coverage and fetch failures.

## Important local artifacts

- docs/AUDIT.md and docs/UPSTREAM_ARCHITECTURE.md
- reports/local/installation.json, installation-files.csv, UNCHANGED.json
- reports/local/NATIVE_READ_PARITY.json and IDENTITY_VALIDATION.csv
- data/intermediate/installed/{players,clubs,covered_squads}.csv
- data/intermediate/native-installed/native_players.csv (native levels/styles)
- data/raw/fpl/fpl-20260908T074104Z-96d6a6eb63de.json (+ provenance)
- reports/local/premier-league/TRANSFER_DIFF.csv and companion reports
- benchmarks/baseline.json: running game, controlled baseline pending
- build/fm27-db-probe.exe: local linked native artifact, not distributed
- dist/FM27CommunityToolkit-0.1.0.zip: source diagnostic toolkit, NOT game patch
- .agent_tmp/: full build, test, read-probe, launch and packaging logs

## Still required — no finished overhaul claim

Establish fixed-workload game baselines and
controlled new careers. Obtain authoritative squads/transfers for every covered
club, including loans, returns and departed players; reconcile real league
membership. Current proposals are passive and cannot write a game database.
Implement mutation through the canonical native FIFAM writer only after
ownership/date/loan semantics and native round-trip are verified.

Then calibrate ratings through existing FIFAM conversion/level functions,
test non-3D careers across June/July and 1/3/5/10 years, reproduce bugs and
profile real bottlenecks. No runtime patch, ASI plugin, crash handler, game
config preset, performance optimization or production
database installation exists yet. No optimization benefit is claimed.

EA ratings are public, but inspected fifaapi supports through 26. Do not just
set 27. POST_TRANSFER requires detected source refresh, not calendar date alone.
Keep upstream assets/data and linked binaries out of distribution until licence
terms are verified; public GitHub visibility is not a redistribution grant.
