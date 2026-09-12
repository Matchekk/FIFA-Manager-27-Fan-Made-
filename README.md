# FM27 Community Overhaul — development toolkit

**Status: twelve-league source capture and guarded native staging candidate; not a finished game patch.**

Current delivery: `docs/ABGABE_1500.md` and `reports/DELIVERY_1500.json`.
Scope: current squads in 12 leagues, then realistic ratings, non-3D simulation,
menu responsiveness and stability. No 3D or XXL portrait work.

The existing game installation is kept separate from this Git repository.
No game executable, configuration, database or save is changed by the data
tools. Reports are review proposals, not an imported 2026/27 database.

## Implemented

- Recursive installation inventory, executable/plugin SHA-256, bounded PE and
  LAA inspection, Windows/CPU/RAM/GPU/storage diagnostics.
- Strict read-only 2013.12 identity projection, with separate serialized club
  references and unique IDs; free-agent ID handling follows upstream semantics.
- Native x86 probe using the compiled FIFAM reader and original player-level
  functions. Exact source commits are pinned in `config/upstream-lock.json`.
- FIFA-ID-first matching, name/date fallback, duplicate/conflict and loan guards;
  deterministic transfer proposal CSVs; no fee required for a proposal.
- Cached official FPL 2026/27 roster adapter, provenance/hash verification,
  season guard and review-only installed-vs-real squad comparison.
- Identity validator, process memory/CPU/IO recorder, manual scenario timing
  and repeated-run median comparison with incomplete-run rejection.
- Source-only toolkit ZIP with hash-checked installation and uninstall that
  preserves changed and unrelated files. It does not install a game patch.

## Run from the project directory

Requires Python 3.12+ and PowerShell 7 for Windows diagnostic scripts.
All destinations must be outside the game installation.

```powershell
python tools/fm27.py audit --game-root 'C:\path\to\game' --output reports/local
python tools/fm27.py export-identities --database 'C:\path\to\game\database' --output data/intermediate/installed
python tools/validate-data.py --export data/intermediate/installed --output reports/local --snapshot 2026-09-08
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-data.txt
.venv/Scripts/python -m unittest discover -s tests -v
```

`validate-data` returns nonzero when it finds ERROR/FATAL findings. Its checks
cover the identity projection, not native loan/competition/save semantics.

Network access is explicit and optional:

```powershell
python tools/fm27.py fetch-fpl --output data/raw/fpl
python tools/compare-squads.py --export data/intermediate/installed --source data/raw/fpl/SNAPSHOT.json --output reports/local/premier-league
.venv/Scripts/python tools/fetch-dfb.py
python tools/compare-dfb.py
python tools/combine-reports.py
```

The DFB comparison currently expects the installed projection at
`data/intermediate/installed-teams`; export to that path first. It resolves
German owner clubs through the reviewed alias file and keeps reserve teams
separate. The combined reports expose missing leagues and source failures.

Use the exact snapshot filename returned by fetch-fpl. FPL/Opta IDs are not
FIFA IDs. Fantasy eligibility, availability and membership are not sufficient
proof of loan ownership or all registered senior/youth players.

For independently verified transfer evidence, use the CSV schema in
`src/fm27/reconcile.py::INPUT_FIELDS` and:

```powershell
python tools/fm27.py reconcile --export data/intermediate/installed --evidence data/raw/confirmed-transfers.csv --output reports/local/transfers --snapshot 2026-09-08
```

This generates proposals only. `PROPOSE_NATIVE_CHANGE` is not an instruction
that has been applied to the game. Ambiguous cases never silently create players.
Missing roster evidence never implies a departure. Refresh the snapshot date
only from a newly retrieved and validated source.

## Extended source and staging pipeline

The detailed FC27 website adapter captures IDs and attributes without enabling a
guessed native FC27 database schema. Public transfer and roster adapters cover
only the twelve configured leagues. No portraits are downloaded.

```powershell
.venv/Scripts/python tools/fetch-ea.py
.venv/Scripts/python tools/fetch-transfers.py
.venv/Scripts/python tools/fetch-squads.py
.venv/Scripts/python tools/reconcile-current.py
```

Reviewed club aliases are in `config/tm-club-aliases.json`. The staging plan
requires confirmed identity, dated current contract and transfer evidence for
club changes. Loans, future conditions, contradictory primary-source evidence
and ambiguous identities are excluded. It does not remove every departed player
or create missing people. Competition participants are not changed.

`--stage-plan <csv>` on the native bridge applies that frozen plan only to a NEW
external candidate directory. Validate the exported result with
`tools/validate-candidate.py`; never treat the staging flag as production approval.

## Native build (developer checkout)

Clone the five repositories into `upstream/<name>` at the commits in the lock.
Install Visual Studio 2022 Build Tools with v143 C++ x86 and Windows SDK.
Run `pwsh -File tools/build-native.ps1`. Use `-Resume` only for an inspected
existing shadow tree. Optional `-OptimizeOffline` builds a separate optimized
offline-tool shadow and executable; it does not change or speed up Manager.exe. Libraries are compiled locally; third-party assets and
linked upstream binaries are not included in the distributable toolkit.

```powershell
build/fm27-db-probe.exe 'C:\path\to\game\database' 'C:\external\new-native-output'
python tools/compare-native.py --projection data/intermediate/installed/players.csv --native data/intermediate/native-installed/native_players.csv --output reports/local/NATIVE_READ_PARITY.json
```

Do not point native output into the game installation. Optional
`--stage-roundtrip` writes an unchanged native database into a NEW external
output directory only. It is not a production transfer importer. Export that
staged database and use `tools/compare-roundtrip.py` to compare projected
semantics; this does not validate every database field or save compatibility.
Headless errors fail fast instead of dismissing
upstream error dialogs and continuing.

## Install/uninstall the toolkit ZIP

Extract the ZIP to a temporary directory. Run PowerShell 7:

```powershell
pwsh -File tools/Install-Toolkit.ps1 -Destination 'C:\FM27Tools'
pwsh -File tools/Uninstall-Toolkit.ps1 -Installation 'C:\FM27Tools'
```

The installer requires a new directory and writes an uninstall manifest before
copying files, so an interrupted installation can still be cleaned up. It
does not alter antivirus, execution-policy, activation or DRM settings.

## Evidence and next gates

Read `docs/AUDIT.md`, `docs/UPSTREAM_ARCHITECTURE.md`,
`docs/SAVE_COMPATIBILITY.md`, `docs/BENCHMARK_PROTOCOL.md` and `HANDOFF.md`.
Generated player/source data stays ignored and local. Public raw data, licensed
upstream assets and private diagnostics are not bundled into the toolkit.

Still required for an actual overhaul release: complete authoritative squad
evidence for all covered clubs; native ownership/contract/competition mutation
and full round-trip validation; calibrated ratings;
repeatable baseline and optimized timings; new-career and long-run save tests;
only then a reversible installer for validated game modifications.
