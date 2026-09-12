# Upstream architecture

Locally inspected on 2026-09-08. Exact Git commits: `config/upstream-lock.json`.
Local clones live under ignored `upstream/`; their assets are not packaged.

## Repositories

- [fifam](https://github.com/FIFAM-Mods/fifam): native C++ `fmapi`, `fifaapi`,
  generic helpers, converter applications and an interactive test/tool harness.
- [TheSeason](https://github.com/FIFAM-Mods/TheSeason): x86 ASI source and bundled
  plugin/injector helpers. The inspected source declares TheSeason.v2.3.1,
  defaults to a 2025 start, checks UCP presence, and contains build-specific
  date patches. This is not authority to reuse its addresses on an unknown EXE.
- [scripts](https://github.com/FIFAM-Mods/scripts): continental/national UCP
  competition source, including WC_WCMode2026.ucpsc. Reuse script tooling before
  considering executable patches for competition changes.
- [FIFA-Manager-Patch](https://github.com/FIFAM-Mods/FIFA-Manager-Patch): this
  inspected checkout contains README and GitHub metadata, not the UCP Main
  source. A public issue repository is not evidence that a DLL's internals are
  source-editable.
- [UniversalConverterProjectInstaller](https://github.com/FIFAM-Mods/UniversalConverterProjectInstaller):
  C#/WPF installer source/assets. Not UniversalConverterProject.Main.asi source.

## Database and identity

`fmapi/FifamDatabase.cpp::Read` reads `Countries.sav`, `data/CountryDataN.sav`,
`script/CountryScriptN.sav`, `Without.sav`, supporting city/region data and
external scripts. `Write` is the canonical native serialization path.
The file version is a packed year/revision; decimal 538116114 is `2013.12`.
This format version is distinct from game product branding and season year.
`Master.dat` is not decoded by our Python identity projection.

`FifamClub::ReadClubMembers` reads a persisted person ID before club PLAYER
blocks. In `Without.sav`, `FifamDatabase::Read` allocates IDs using
`GetNextFreePersonID()`. Therefore free agents must not be assigned guessed
persisted FM IDs by a text extractor.

`FifamClub` has both a unique club ID and FIFA team ID. Serialized competition
references use country/ordinal IDs; they must be resolved, not equated with
`mUniqueID`. The projection retains `reference_id` separately from `club_id`.

`FifamPlayer::Read` has explicit branches for format versions. In 2013.12,
the post-contract tail contains comment, birth city, creator, `mFifaID`,
Football Manager ID and Transfermarkt ID. A `FIFAID:` comment is not the
authoritative numeric `mFifaID`. An FPL, Opta or SI ID is never an EA/FIFA ID.

Starting conditions represent loans, future transfers, retirement and other
dated behaviour. Ownership must be reconciled through those native semantics;
moving a PLAYER text block alone is not a correct transfer implementation.
Contract flags include loan status and other obligations.

## Positions, abilities, levels and converter

`FifamPlayerPosition.h` translates serialized 2012.05+ positions (14 values)
to internal enum values (18). Do not use raw persisted position as an internal
enum. `mPositionBias` records differing suitability for each position.

`FifamPlayerAttributes::Read` defines 37 serialized modern detailed attributes.
The user's illustrative legacy attributes Technique, Touch and Anticipation
are not independent entries in this 37-field stream. No arbitrary group
mapping has been applied.

`FifamPlayerLevel::GetPlayerLevel13(player, position, style, experience)` is the
native level authority; `GetBestStyleForPlayer` considers playing styles.
Our native probe calls these existing functions. FC OVR is not assigned to FM
level. Current ability, bias, style, experience and talent remain distinct.

`fm-fifam-converter/FifaConverter.cpp` attaches EA player IDs, converts detailed
attributes and resolves loans through FIFA team associations. `PlayerConverter`
also handles source-specific identity/profile conversion. Reuse these mappings
after input schema validation rather than recreating them from card stats.
`fifaapi/FifaDatabase.cpp` currently sets last supported version to **26**.
FC27 native schema support is not enabled by this project.

## Build and boundaries

Visual Studio 2022 v143, Win32, Windows SDK are used by upstream vcxproj files.
The generic/fmapi/fifaapi Release projects explicitly disable compiler
optimization: this describes offline tools, not the performance of Manager.exe.
Our project builds a local shadow copy, replacing modal error reporting with
fail-fast logging only in the offline tool. The original clone is untouched.
Our own bridge uses /W4 /WX; upstream headers are external headers, and upstream
library warnings remain visible in build logs.

The game engine, most installed UCP Main internals and Master.dat behaviour
are not made source-editable by these repositories. No runtime address is
approved. The audit records hashes and PE properties but deliberately grants
no binary patch support based on filenames, resource versions or entry points.

Native libraries/binaries linked from upstream are local build artifacts.
Public availability alone is not a redistribution licence; confirm licensing
before publishing a linked binary or any upstream assets.
