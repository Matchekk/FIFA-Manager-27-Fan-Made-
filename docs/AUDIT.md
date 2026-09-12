# Installation audit — 2026-09-08

## Detected installation

- Game root: `C:\Fifa Manager 13\FUSSBALL MANAGER 13`.
- Windows uninstall registration: FUSSBALL MANAGER 13, version 1.0.0.0.
- Executable resource product: FIFA Manager 26, file version 26,0,0,0.
- Base-install evidence points to FM13; the EXE branding is overwritten by the
  season patch. No claim of a supported binary build is inferred from either.
- Local ReadMe - FIFA Manager 2026.txt says Version 1.0. UCP plugins have no
  usable FileVersion resources. Update 1 presence/absence is **unresolved**;
  compare official release manifests before declaring an exact patch version.
- `plugins/season.ini`: `SEASON_START_YEAR 2025`.
- `database` and `database_update` both exist with differing content hashes.
  Neither has been overwritten. The currently selected in-game DB is unknown.
- Inventoried 47,109 files; 0 read errors.
  File manifest is `reports/local/installation-files.csv`. Graphics were
  enumerated by path/size, not decoded, compressed, removed or optimized.

## Binary evidence

Manager.exe: `8ebe1291fbcc1291bfee182995a165194156a0b4b8e0d6c80994cadb087a857c` (SHA-256), 53,083,648 bytes.
PE x86, image base 0x400000, entry-point RVA
0x32a1200, LAA **already enabled**.
No LAA patch is necessary and no byte has been changed.

UniversalConverterProject.Main.asi: `b1bb51ebb708bef328ce0be93a377e3dcf1343aef7efd4e2b9e78219a4a89327`.
Also installed: UniversalConverterProject.Editor.asi, TheSeason.asi,
internationalgoals.asi, nationalteams.asi. All are individually hashed in
installation.json. Root includes loader/render DLLs; they remain untouched.
No hash has been added to a binary-write allowlist. No runtime patch was made.

## Hardware

Windows 10 Home 64-bit, build 19045; AMD Ryzen 5 7530U, 6 cores / 12 threads;
approximately 15.3 GiB OS-visible RAM; AMD Radeon integrated graphics;
Samsung 512GB NVMe SSD. Driver-reported AdapterRAM is 512MiB but does **not**
represent all memory available to an integrated GPU. Raw CIM evidence is local.

## Readability and source build

Installed text database format: **2013.12**, Countries Version 3.
Python projection: 266,764 players, 13,477 club/national-team blocks, 218 clubs
in the installed twelve covered leagues and 16,880 linked players including
reserves/youth. These are installed membership counts, not claimed current
2026/27 league memberships. Source SHA-256 is checked before/after each read.

Visual Studio Build Tools 2022 17.14.39 / MSVC 14.44 / Windows SDK were installed
with user authorization through winget. Upstream generic, fmapi and fifaapi
and our x86 read-only probe compiled successfully. Upstream diagnostics in the
local build shadow are changed to fail-fast logging, not suppressed errors.

The native reader completed with **266,764 players and 13,270 clubs**. The
207-block difference is the separate national-team blocks. Comparison of
255,297 persisted player IDs found **zero mismatches** in FIFA ID, club ID and
DOB after date-format normalization. Full-player identity multisets, including
free agents, match. See `reports/local/NATIVE_READ_PARITY.json`.
This is a read/identity proof, not a writer round-trip or save compatibility test.

## Initial source reconciliation

Official FPL 2026/27 source snapshot retrieved 2026-09-08, hash
`96d6a6eb63de69fd2e12fc6c01197b69658dd8ecfc16da78f32e6ac806dfc936`:
https://fantasy.premierleague.com/api/bootstrap-static/

654 source entries: 325 same-club matches, 173 possible arrivals, 99 ambiguous
or unavailable entries, 46 unmatched and 11 requiring identity review.
117 installed first-team entries have no matched source record; absence is
not interpreted as a departure. FPL is not a full registration or loan database.
DFB roster evidence now covers 55 German teams across GER1/GER2/GER3; Bielefeld returns HTTP 500 on both season and club pages. Eight other competitions still need authoritative roster snapshots.
All transfer output is REVIEW ONLY. No updated production database exists.

Identity validator: 23 duplicate FIFA-ID values and 14,851 contract-order
candidates globally. No duplicate internal persisted person IDs reported.
These are baseline data findings requiring semantic review, not proven crash
causes. Reports are local and no bulk date repair has been applied.

## Running game and baseline

User confirmed normal startup through the resolution selector. Attached to
Manager.exe PID 9412 at the exact installation path; window title is
Fussball Manager 2026 1.1.0. Earlier short-lived process observations do not
establish a game failure. The launcher now follows the startup flow and can
attach to an existing game without restarting it.

A 30.18-second uncontrolled observation produced 114 samples: CPU 1.859s,
peak observed working set 324,870,144 bytes, private bytes 649,363,456,
virtual bytes 1,064,558,592; process reads 1,556,480 and writes 0 bytes.
These are observations, not scenario latency or performance improvements.
Native capture fails on this host with SetIsBorderRequired E_NOINTERFACE;
text accessibility exposes only the root pane. No coordinates were guessed.
No career was created, no save loaded and no season simulated by this work.

## Current change boundary

Own code, tests and reports live only in C:\FM27CommunityOverhaul. No game
database/configuration/executable modifications, ASI installation, save edits,
DRM changes or asset redistribution. Aelunor is untouched.
The distributable is a source diagnostic toolkit, not a completed overhaul.

External operations: five public GitHub clones, public EA/FM-Zocker/league web
research, one FPL snapshot request, Microsoft build-tool installation. No model
API costs, paid football feeds, save uploads or telemetry uploads were used.
No antivirus or execution-policy settings were changed.
