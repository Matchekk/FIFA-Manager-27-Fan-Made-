# FIFA Manager 13 Modding Knowledge Base for Codex

**Research snapshot:** 2026-09-10
**Primary target:** FIFA Manager 13 / current FM-Zocker + FIFAM-Mods Season Patch ecosystem
**Primary wiki:** `https://fifam.miraheze.org/wiki`
**Purpose:** Give Codex a technically grounded map of what can be modded, which mechanism belongs to which task, which historical methods are obsolete, and where the strongest source-of-truth code lives.

---

## 0. Critical research limitation / honesty note

The live Miraheze wiki could **not be exhaustively enumerated or fetched directly** from this research environment on 2026-09-10. Direct requests to the wiki root, individual pages, `Special:AllPages`, and the MediaWiki API were blocked/failing for the automated client. Therefore it would be false to claim that every current live wiki page was directly read.

To recover as much of the wiki as possible, this knowledge base triangulates four source classes:

1. **Indexed/mirrored copies of actual wiki pages** (especially Scribd mirrors for `GUI_Elements` and `EVT`).
2. **Developer posts by Dmitri/DK22 and the FIFAM community** that link specific wiki pages and often reproduce their contents or explain their purpose.
3. **Current public FIFAM-Mods GitHub repositories**, especially `FIFAM-Mods/fifam`, `scripts`, `TheSeason`, `HufConverter`, `FFN-Studio`, `AnimationConverter`, and `otools`.
4. **Current Season Patch documentation/changelogs**, used to distinguish what remains current from what was only valid for Season 2019/2020.

Miraheze public wikis are reported to be dumped monthly to Archive.org, but a complete retrievable dump for this specific wiki was not located in the available search path during this run. If a full XML dump becomes available later, Codex should parse it and compare its page inventory against the coverage ledger in this document.

### Confidence tags used here

- **CURRENT / HIGH** — supported by current FIFAM-Mods source or modern patch behavior.
- **FM13-RELEVANT / HIGH** — directly applicable to FIFA Manager 13 and strongly evidenced.
- **HISTORICAL** — documented behavior/tool from older Season/UCP eras; do not assume it still applies.
- **LOW PRIORITY FOR FM27** — valid modding information but not important for the user's non-3D FM27 overhaul.
- **UNSAFE TO ASSUME** — evidence exists, but compatibility with the user's exact FM26/FM27 executable/build is not established.

---

# 1. Reconstructed wiki coverage ledger

The following wiki pages were directly confirmed through indexed mirrors, developer posts, repository README links, or historical Season/UCP documentation.

| Wiki page | Topic | Recovery status | FM13 relevance | Guidance |
|---|---|---:|---:|---|
| `Scripting_Instructions` | Original FM07–FM14 script commands | Strong recovery + current source equivalent | Very high | Use with native script definitions; current `scripts-fm13-14.txt` is stronger authority |
| `ASI_Loader_(FIFA_Manager)` | Loading `.asi` DLL plugins | Strong historical recovery | High | Architecture valid; exact legacy loader/build assumptions must be revalidated |
| `CustomTranslation.asi` | Runtime text replacement | Strong historical recovery | Medium/high | Useful concept; validate current patch integration before use |
| `TheSeason.asi` | Start season/date and related patches | Strong recovery + current source | High | Current source exists; never reuse hardcoded addresses across unknown builds |
| `ScriptStudio` | UCP script authoring/import tool | Strong recovery | Very high | Core competition editing workflow |
| `Universal_Converter_Project_Scripting_Syntax` | High-level UCP competition scripting | Strong recovery/examples | Very high | Preferred way to represent competitions when supported |
| `Universal_Converter_Project_Database_Editing` | `.dbe` edit mechanism | Strong historical recovery | Historical only | **Do not use for FM23+ / FM26/FM27**; developer explicitly says DBE files no longer work there |
| `UCP_Patch_Features` | Season/UCP feature overview | Strong historical recovery | Contextual | Use to understand patch capabilities, not as current API spec |
| `Graphics_Location` | Asset folders / graphics paths | Partial/strong examples | Medium | Verify exact precedence/paths in current build |
| `Updating_kits_for_Universal_Converter_Patch` | Kit integration | Strong recovery | Low for current project | Custom kits can be loose files in known paths; 3D-related |
| `3D_Pitch_Customization` | Per-club pitch/env parameters | Strong summary | Low | User does not use 3D |
| `Domestic_Cups_Tutorial` | Creating cup competitions via ScriptStudio | Near-full recovery | Very high | Excellent concrete script workflow |
| `Creating_your_own_mobile_phone_theme` | UI phone theme | Title confirmed, content only partially indexed | Low/medium | UI customization example; current patch supports theme switching |
| `Notable_changes_in_FIFA_Manager_2025` | Modern engine/patch changes | Strong mirror on ModDB | High contextual | Demonstrates what runtime/UI/competition fixes are feasible |
| `FIFA_Manager_2021_Leagues` | Historical playable league list | Confirmed | Historical | Reference only |
| `Pre-Season_2020_Leagues` | Historical playoff/league systems | Confirmed | Historical | Reference only |
| 2019 Season database-leagues page | Historical league list | Exact title unresolved in indexed result | Historical | Do not invent exact page title |
| `O` | EA old-gen `.o` model format | Strong developer-thread recovery | Low | Relevant mainly to 3D models/shaders; current OTools exists |
| `EBO` | Animation/model container data | Strong summary | Low | Old-gen animation research |
| `BNK_(Animation)` | Animation sequence bank | Strong summary | Low | Old-gen animation research |
| `EVT` | Audio event database | Full/near-full mirror | Low | Binary format documented; 010 template exists |
| `FFN` | EA Sports font format | Confirmed via current tool README | Low/experimental for FM13 | Tool tested on TCM2005; FM13 support must be proven separately |
| `FFN_Studio` | FFN creation/extraction tool | Confirmed via current README | Low/experimental | OTF/TTF -> FFN; extraction -> FSH/PNG |
| `Translations.huf` | Localization database | Strong current recovery | Medium/high | Current HufConverter makes this practical |
| `GUI_Elements` | XML UI controls | Full/near-full mirror | High for UI work | Documents 40 GUI RTTI/control classes and XML structure |

### Important conclusion about “all pages”

This ledger is a **reconstructed confirmed set, not a certified complete live `Special:AllPages` dump**. The inability to enumerate the live wiki is itself a tracked research gap. Codex must not state that the above list is guaranteed to contain every current page until a full MediaWiki XML/API page list is obtained.

---

# 2. The most important mental model: FM13 modding is not one thing

Codex should first classify a requested change into the correct layer. Mixing layers is one of the easiest ways to make fragile or unnecessary patches.

## Layer A — Native database / Editor data

Use for:

- clubs
- players
- staff
- contracts
- loans / starting conditions
- nationalities
- player attributes
- positions
- histories
- league membership where represented in DB
- club metadata
- countries/cities/regions

**Preferred modern mechanism:** the native FIFAM `fmapi` read/write model and the Editor/UCP-supported database pipeline.

Do **not** use old `.dbe` hacks for modern FM23+/FM26 builds.

## Layer B — Competition scripts / UCP ScriptStudio

Use for:

- league/cup competition structures
- qualification
- competition participant selection
- pools/rounds
- cups
- league cups
- super cups
- continental/national competition logic
- matchday/calendar structure when script-expressible

**Preferred mechanism:** `.ucpsc` source + ScriptStudio / UCP script tooling.

Use scripting before binary-patching the executable for competition behavior.

## Layer C — Parameter/config files

Use for behavior already exposed as tunable configuration, e.g. historically/currently:

- player-level / player-style weighting-related data
- formations / routes (`UCPFormations.xml` historically/currently used in UCP ecosystem)
- economic/payment parameters
- media-market-related parameters
- certain limits and feature toggles in `ucp.ini` or modern equivalents

Never invent parameter names. Discover current files in the actual installation and trace readers where source exists.

## Layer D — Translation/UI resource layer

Use for:

- localized strings
- renamed playing styles
- screen text
- GUI XML layouts and controls
- phone themes
- icons/badges/trophies and loose UI graphics

Mechanisms include `Translations.huf`, historical `CustomTranslation.asi`, XML GUI resources, and current asset-folder override behavior.

## Layer E — Runtime patch / ASI plugin

Use only for behavior that lives in the closed-source game/editor executable and cannot be solved safely in database/scripts/config.

Examples from the historical/current ecosystem:

- changing start season/date
- fixing game-code bugs
- national-team selection behavior
- national-team stat tracking
- multithreading race fixes
- UI/windowing improvements
- editor behavior fixes
- limits hardcoded in engine code

**This is reverse engineering.** It is not normal configuration editing.

## Layer F — Asset / legacy EA file formats

Includes:

- `.big` / BIG4 / `.viv` archives
- FSH textures
- `.o` models
- EBO/BNK animations
- EVT audio-event DBs
- FFN fonts
- HUF translations

Some are central to FM13, some are old-gen cross-game formats. Applicability must be proven per FM13 subsystem.

---

# 3. Current strongest source-of-truth repository map

The current FIFAM-Mods organization contains a group of repositories that together are more useful to Codex than treating the old wiki as the only authority.

## `FIFAM-Mods/fifam`

This is the most important technical repository for database work.

Observed structure includes:

- `fmapi/` — FIFA Manager database/API types and serialization
- `fifaapi/` — EA FIFA/FC database structures
- `fm-fifam-converter/` — conversion between source football data and FIFA Manager database concepts
- `foom_db/`
- `generic/`
- `shared/`
- `tools/`
- `test/`
- legacy/current format documentation under `doc/`

For Codex: **if a DB structure is modeled here, prefer this code over a guessed text-file parser.**

## `FIFAM-Mods/scripts`

Current competition script source repository. Confirmed files include continental, World Cup and national/continental tournament `.ucpsc` sources such as:

- `AfricaCup.ucpsc`
- `AsiaCup.ucpsc`
- `ContinentalAfrica.ucpsc`
- `ContinentalAsia.ucpsc`
- `ContinentalEurope.ucpsc`
- `ContinentalNorthAmerica.ucpsc`
- `ContinentalOceania.ucpsc`
- `ContinentalSouthAmerica.ucpsc`
- `CopaAmerica.ucpsc`
- `EC.ucpsc`
- `NamCup.ucpsc`
- `OFCCup.ucpsc`
- `U20WC.ucpsc`
- `WC_WCMode2022.ucpsc`
- `WC_WCMode2026.ucpsc`
- `WorldCup...` source(s)

For Codex: these are real examples of modern UCP syntax and should be mined for patterns before inventing competition scripts.

## `FIFAM-Mods/TheSeason`

Current C++ ASI plugin source. It demonstrates:

- x86 in-process plugin architecture
- game-version detection
- config-file loading
- UCP plugin presence detection
- build-specific runtime patching
- date/start-season modification
- guarded feature configuration

For Codex: useful architecture example, **not permission to copy addresses into an unknown executable**.

## `FIFAM-Mods/HufConverter`

Current tool for Bright Future/FIFA Manager `.HUF` locale files. Developer documentation states support for conversions including XLSX, CSV, TSV, TXT, TR, hash/name matching, older formats, line breaks, CLI and GUI.

Use it rather than reverse-engineering `Translations.huf` again.

## `FIFAM-Mods/FFN-Studio`

Creates/extracts EA Sports Font Files:

- OTF/TTF -> FFN
- FFN texture -> FSH
- FFN texture -> PNG

Important warning: the README says font import was successfully tested in **Total Club Manager 2005**, while other platform support was implemented but not tested. Do not assume FM13 is verified merely because the repository belongs to FIFAM-Mods.

## `FIFAM-Mods/AnimationConverter`

Tool for converting `.viv` animation files across old EA generations. Useful for old-gen animation work; very low priority for the user's non-3D project.

## `FIFAM-Mods/otools` and `OTools_GUI`

Tools for `.O` model and FSH texture import/export. Modern repository exists and old developer research documents mesh/skeleton/shader/morph internals.

## `FIFAM-Mods/FIFA-Manager-Patch`

Public issue/project repository for current patch bugs/improvements. Do **not** infer that `UniversalConverterProject.Main.asi` source is present merely from issue descriptions.

## `FIFAM-Mods/UniversalConverterProjectInstaller`

Installer source, not the source of every UCP runtime module.

---

# 4. Native FIFA Manager database architecture

For the user's FM27 project, this is the highest-value section.

## 4.1 Canonical database reader/writer

Current `fmapi/FifamDatabase.cpp` models native FIFA Manager serialization. The inspected project architecture confirms that database reading covers files such as:

- `Countries.sav`
- `data/CountryDataN.sav`
- `script/CountryScriptN.sav`
- `Without.sav`
- supporting city/region and external script data

`FifamDatabase::Write` is the canonical native write path in the public library.

The user's installed DB format was identified as `2013.12` (format/version concept distinct from “FM26” branding or season year).

### Rule for Codex

**Never replace this with a homemade line-oriented parser when modifying production data.** A projection/parser may be useful for analysis, but production serialization should use native semantics.

## 4.2 Identity fields

Important identifiers are not interchangeable:

- persisted internal person IDs
- FIFA/EA player ID (`mFifaID`)
- club unique ID
- FIFA team ID
- competition reference IDs
- Football Manager / Transfermarkt IDs in newer database tails
- external IDs such as FPL/Opta/SI IDs

An external API ID is not automatically an EA/FIFA ID.

For modern data reconciliation, `mFifaID` is the strongest identity key when present.

## 4.3 Person-ID serialization trap

Native read/write can renumber internal person IDs. Free agents and club players are not necessarily handled identically by simplistic text extraction.

Therefore a round-trip validator must compare **semantic identity/content**, not assume numeric internal person IDs are stable.

Suggested stable comparison key:

- EA/FIFA ID when available
- normalized name
- DOB
- nationality
- club association
- plus attribute/contract data for content parity

## 4.4 Loans and future transfers are semantic objects

One of the most important findings for FM27:

**Moving a PLAYER block from one club to another is not a complete transfer implementation.**

Starting conditions and contract fields represent concepts such as:

- loans
- future transfers
- return dates
- retirement / dated behaviors
- other contract obligations

Codex must inspect and preserve these native semantics.

## 4.5 Competition IDs

Serialized competition references are not necessarily equal to a club or competition object's human-friendly/unique ID. Resolve through the proper native structures.

This matters for scripts, graphics IDs and tournament membership.

---

# 5. FIFA Manager 13 player data and level calculation

The public `fmapi` models the FM13 player in detail.

Important player concepts include:

- main position
- position bias (suitability by position)
- playing style
- detailed attributes
- general experience
- tactical education
- feet
- captain flag
- current market value
- contract
- starting conditions
- histories
- EA/FIFA ID in newer Season formats

## 5.1 Detailed FM13 attributes

Modern FM13 level calculation uses a detailed attribute vector rather than a single OVR. The relevant fields include categories such as:

- Ball Control
- Dribbling
- Finishing
- Shot Power
- Long Shots
- Volleys
- Crossing
- Passing
- Long Passing
- Heading
- Standing Tackle
- Sliding Tackle
- Man Marking
- Acceleration
- Pace
- Agility
- Jumping
- Strength
- Stamina
- Balance
- Offensive Positioning
- Defensive Positioning
- Vision
- Aggression
- Reactions
- Composure
- Consistency
- Tactical Awareness
- Free Kicks
- Corners
- Penalties
- GK Diving
- Handling
- Positioning
- One-on-One
- Reflexes
- Kicking

## 5.2 Level is position + style dependent

`FifamPlayerLevel::GetPlayerLevel13(player, position, style, experience)` uses a weight table indexed by playing style and position family. Thus there is no single simple “average attributes = level” rule.

Conceptually:

1. Select the 37 relevant attributes.
2. Multiply each by the weight for the chosen style/position.
3. Divide weighted sum by total weight -> base/int level.
4. Apply position suitability (`mPositionBias`).
5. Optionally apply the general-experience modifier.
6. Clamp to 1..99.

This means one player can have different effective levels at ST, CF, AM, etc., and changing style can alter the weighting.

## 5.3 Playing styles

The public enum contains styles including:

- AttackingFB
- DefenceFB
- Libero
- SimplePasser
- BallWinner
- HardMan
- Holding
- BallWinnerMidfield
- BoxToBox
- Busy
- PlayMaker
- Dribbler
- Winger
- TargetMan
- PenaltyBox
- RunsChannels
- PullsWideLeft
- PullsWideRight
- DribblerAttack
- HoldsUp
- BusyAttacker
- TowerStrength
- DistanceShooter

The library can find best styles for a player by evaluating the level function.

## 5.4 Position bias

Default FM13 position suitability is explicitly modeled. Main position generally begins at 100 and related positions receive lower values. A player is not equally good everywhere.

### FM27 implication

Do not import FC27 OVR as FM level. Import/adjust **attributes**, positions and style, then let FM's own level function calculate the resulting strength.

---

# 6. FIFA/EA -> FIFA Manager conversion knowledge

The current `fm-fifam-converter` is invaluable because it documents how FIFAM-Mods already maps FIFA/FC data into FIFA Manager semantics.

Observed mappings include direct or derived use of:

- acceleration -> FM Acceleration
- sprint speed -> FM Pace
- ball control -> FM BallControl
- dribbling -> FM Dribbling
- finishing -> FM Finishing
- shot power -> FM ShotPower
- long shots -> FM LongShots
- short passing -> FM Passing
- long passing -> FM LongPassing
- crossing -> FM Crossing
- vision -> FM Vision
- standing/sliding tackle -> FM tackle fields
- interceptions -> defensive positioning/tactical derivation
- reactions -> FM Reactions
- composure -> FM Composure and derived mental values
- GK fields -> FM goalkeeper attributes

The converter also derives FM-only concepts when the source game lacks a direct field.

### Rule for Codex

When updating FC27 support, extend/reuse the existing converter after validating the FC27 schema. Do not create arbitrary mappings from six card stats if full detailed data is available.

The public `fifaapi` code observed in the project currently treats **version 26** as the latest supported FIFA/FC schema. “Set 27 and hope” is not a valid upgrade. Schema fields/tables must be compared first.

---

# 7. Scripting: original FM13/14 low-level command set

The wiki page `Scripting_Instructions` was described by its author as a list of all scripting instructions in FIFA Manager 07–14 with descriptions. A current copy of the FM13/14 command table exists in `FIFAM-Mods/fifam/doc/formats/scripts-fm13-14.txt`.

Confirmed FM13/14 instruction IDs 0–38:

| ID | Command | Purpose / note |
|---:|---|---|
| 0 | `END_OF_ENTRY` | Finish script execution |
| 1 | `XXXBUILD_COUNTERXXX` | Unused |
| 2 | `RESERVE_ASSESSMENT_TEAMS` | Reserve slots based on assessment position |
| 3 | `GET_CHAMP` | Add champion of competition |
| 4 | `GET_EUROPEAN_ASSESSMENT_TEAMS` | Add table teams by UEFA/assessment country position |
| 5 | `FILL_ASSESSMENT_RESERVES` | Fill reserved assessment slots |
| 6 | `GET_CHAMP_OR_RUNNER_UP` | Champion or runner-up source |
| 7 | `GET_TAB_X_TO_Y` | Add table positions from competition |
| 8 | `GET_TAB_SURE_X_TO_Y_Z` | Table selection variant |
| 9 | `GET_TAB_LEVEL_X_TO_Y` | Add teams by league level |
| 10 | `GET_TAB_SPARE` | Add spare teams, respecting relegation handling |
| 11 | `GET_TAB_LEVEL_START_X_TO_Y` | League-level selection variant |
| 12 | `GET_EUROPEAN_ASSESSMENT_CUPWINNER` | Add national cup winner/runner-up by assessment country |
| 13 | `GET_WINNER` | Add winners of a round |
| 14 | `GET_LOSER` | Add losers of a round |
| 15 | `GET_POOL` | Add teams from a pool |
| 16 | `GET_NAT_UEFA5_WITH_HOST` | National-team selection variant |
| 17 | `GET_NAT_UEFA5_WITHOUT_HOST` | National-team selection without host |
| 18 | `GET_NAT_SOUTH_AMERICA` | South American NT selection |
| 19 | `GET_NAT_AMERICA` | American NT selection |
| 20 | `GET_NAT_AFRICA` | African NT selection |
| 21 | `GET_NAT_ASIA` | Asian NT selection |
| 22 | `GET_NAT_OCEANIA` | Oceanian NT selection |
| 23 | `GET_HOST` | Add host team(s), historically max 2 |
| 24 | `GET_INTERNATIONAL_TAB_LEVEL_X_TO_Y` | International table-level selection |
| 25 | `GET_INTERNATIONAL_SPARE` | Marked unused by game |
| 26 | `GET_RUNNER_UP` | Add runner-up |
| 27 | `GET_RELEGATED_TEAMS` | Marked unused by game |
| 28 | `GET_INTERNATIONAL_TEAMS` | International teams selection |
| 29 | `GET_CC_FA_WINNER` | Set competition team to champion of source competition |
| 30 | `GET_CC_SPARE` | Fill free competition slots with country spare teams |
| 31 | `GET_CHAMP_COUNTRY_TEAM` | Add top team from champion's country |
| 32 | `GET_RANDOM_NATIONAL_TEAM` | Random NT selection by continent/count |
| 33 | `CHANGE_TEAM_TYPES` | Change all teams between regular/reserve type |
| 34 | `GET_FAIRNESS_TEAM` | Add fairness teams |
| 35 | `COPY_LEAGUE_DATA` | Copy league data including teams |
| 36 | `GET_NATIONAL_TEAM` | Add NT by country ID |
| 37 | `GET_NATIONAL_TEAM_WITHOUT_HOST` | Add NT unless it is host |
| 38 | `SHUFFLE_TEAMS` | Randomly shuffle teams |

These names are useful for reverse-engineering compiled competition scripts and understanding old `CountryScript*.sav` behavior even if UCP source is written in a higher-level syntax.

---

# 8. ScriptStudio and high-level UCP scripting

`ScriptStudio` is the central authoring/import workflow for custom competition scripts in the Season/UCP ecosystem.

Historical developer documentation states:

- ScriptStudio ran on Windows 7+.
- Its package included Notepad++ syntax highlighting under an `extras/npp`-style location.
- Scripts are saved as `.ucpsc`.
- In the FIFA Manager Editor, use **Assistant > ScriptStudio**.
- Import offers **Replace** and **Merge** semantics.
  - **Replace**: replace the complete competition system represented by the import.
  - **Merge**: add/replace selected competitions while leaving the rest intact.

For adding one new cup, the tutorial explicitly recommends **Merge**.

## 8.1 Domestic cups example semantics

The recovered tutorial uses a pattern conceptually like:

```text
comp Spain {
    league_cup index 0 "..." teams 128
    format [1EP+128,1EP,1EP,1EP,1EP,1EP,1EP]
    matchdays [1-7] {
        getTabLevelXToY([3-4], 1, 24)
    }
}
```

Do not cargo-cult this exact competition. The key semantics are:

### `comp Spain { ... }`

Defines the country/global region context for competitions inside the block.

### Competition tags

Domestic competition types documented by the tutorial include:

- `cup` — main national cup
- `league_cup` — league cup
- `super_cup` — super cup

### `index`

Competition index prevents collision with existing competitions.

Historical tutorial notes:

- `league_cup`: indices 0–3 available
- `cup`: one competition (index 0)
- `super_cup`: one competition (index 0)

Revalidate limits against current ScriptStudio/UCP if changing modern builds.

### `teams`

Historical domestic cup maximum in the tutorial: **128** teams.

### `format`

An array representing rounds.

Examples:

- `1EP` — single match with extra time/penalties
- `2EP` — two-match tie with extra-time/penalty semantics
- `+128` — inject 128 teams in that round

Teams may enter progressively in different rounds.

Historical tutorial maximum: **8 rounds** for a domestic cup.

### `matchdays`

An array of calendar-day IDs. The first calendar day uses ID 1. Ranges such as `[1-7]` expand to consecutive IDs.

After import, calendars can be adjusted through Editor league-system/calendar UI when permitted by the competition type.

### Participant functions

`getTabLevelXToY([3-4], 1, 24)` means, in the recovered tutorial, collect clubs from league levels 3 and 4, starting at table position 1, with 24 used as the maximum league-size position bound, until the cup is filled.

### Prize money

The tutorial demonstrates `bonus` as an array of per-round `[regular, TV]` prize pairs.

### Competition ID and graphics

ScriptStudio's **Competition List** exposes a hexadecimal competition ID. That ID is used by custom competition graphics such as badges/logos/trophies.

### Critical FM27 rule

When modern competition formats need changes, Codex should inspect current `FIFAM-Mods/scripts` examples before inventing syntax. The repo already demonstrates modern World Cup and continental formats.

---

# 9. Competition editing and Editor constraints

Historical Season 2020 work revealed several engine/editor constraints:

- The original editor historically had trouble allowing more than ~6 levels in a country; the patched editor was modified to permit **16 levels**.
- A **32-league limit** was reported as still remaining in that era.
- Some calendars for leagues with complex relegation/split logic were intentionally made non-editable in Editor to avoid corrupting structures; manual/script editing was used instead.

These are **historical constraints**, not guaranteed current limits. Codex must detect current behavior before relying on them.

The public `fifam` repository also contains an `FM13 Editor CDialog virtual table.txt` reference listing MFC `CWnd`/`CDialog` virtual methods. This is evidence of historical Editor reverse-engineering and may help identify UI class structure, but it contains no safe universal patch addresses.

---

# 10. Historical `.dbe` database editing — do not use for modern FM27

The page `Universal_Converter_Project_Database_Editing` documented a special `.dbe` mechanism in early UCP/Season builds when the normal database could not be edited through the usual Editor path.

A later direct statement by Dmitri says:

- `.dbe` files **do not work in FM23**.
- They were meant for Season 2019/2020, when normal DB editing was not possible.

Therefore for FM26/FM27:

**Treat this page as historical documentation only.**

Do not build a new FM27 data pipeline around `.dbe` files.

Use current Editor/native `fmapi` serialization instead.

---

# 11. ASI Loader and runtime plugin architecture

The historical `ASI_Loader_(FIFA_Manager)` material is important because it explains the core runtime-patch concept still visible in current plugins.

## 11.1 What an ASI plugin is in this ecosystem

An ASI plugin is essentially a Windows dynamic library (`.dll`) renamed/compiled as `.asi`, loaded into the game/editor process by an ASI loading mechanism.

Historical workflow:

1. Build a Windows DLL, usually C/C++ in Visual Studio.
2. Use `.asi` extension.
3. Place in a game `plugins` folder.
4. Loader attaches/loads it into the selected game/editor process.

The purpose is to modify behavior dynamically without permanently editing every executable byte on disk.

## 11.2 Reverse engineering requirement

The developers explicitly described plugin development as primarily **reverse engineering and locating executable code regions**.

IDA was historically recommended for disassembly/research.

### Modern safety rule

For the user's FM26/FM27 build:

- executable hash must be known
- exact build must be identified
- signatures/patterns should be preferred over unguarded addresses where feasible
- original bytes must be verified before writing
- feature must fail closed if signature doesn't match
- never copy a hardcoded address from FM13 vanilla or an older Season Patch into a different Manager.exe build

## 11.3 Current source exemplar: TheSeason

The public modern `TheSeason` source demonstrates exactly this family of behavior: version detection, configuration, UCP presence checks and build-specific patches.

It is a template for **architecture**, not a universal address map.

---

# 12. Known ASI/plugin examples and what they teach us

Historical plugin pages/posts confirm that runtime patching has successfully changed nontrivial engine behavior.

## `TheSeason.asi`

Purpose:

- change start season/date
- work in game/editor
- historically/currently include additional minor limits/patches

The modern source has evolved beyond the old wiki description.

## `CustomTranslation.asi`

Historical purpose:

- add/change game text dynamically

It supported FM13-era game/editor builds. For current patch work, prefer current localization tooling when possible and use runtime string patches only if needed.

## `nationalteams.asi`

Historical purpose:

- allow selection of any national team at career start

Shows career-setup logic can be runtime-patched.

## `internationalgoals.asi`

Historical purpose:

- make national-team goals and assists count correctly in player statistics

Shows stat-tracking bugs can be corrected in engine code.

### FM27 implication

Runtime patches are feasible, but only after the data/script/config options have been exhausted.

---

# 13. What recent Season Patch development proves is patchable

The modern patch history is valuable because it demonstrates actual successful modifications to FM13/14 beyond the old wiki.

Examples from FIFA Manager 2025-era public notes include:

- borderless/draggable window behavior
- UEFA/AFC League Phase formats
- AFC/CAF association rankings
- revised FIFA World Ranking calculation/display
- new FIFA Club World Cup format
- reworked Former Opponents screen
- reworked season-transition screen
- Results tab support for newer competition types
- redesigned mobile phone + runtime theme switching
- dark-mode badges
- fix for staff disappearing/losing level after several years
- fix allowing AI first teams to use youth players correctly
- prestige-loss fix on relegation from lowest loaded league
- race-condition fix in team-email logic (`CDBEAMail` / multithreading)
- touchpad scrolling option
- subfolders under `data\assets`
- background-music behavior in windowed mode
- host-country support for intercontinental competitions
- English “Accidents Of Game” support

This is strong evidence that the modern UCP/Season ecosystem touches:

- UI
- game logic
- multithreading bugs
- competition engine behavior
- AI squad behavior
- long-career data bugs
- asset lookup
- input/window handling

For FM27 performance/stability research, study current patch changes before reinventing already-fixed behavior.

---

# 14. Parameter/config modding

The historical UCP ecosystem exposes several behaviors through external parameter/config files rather than executable patches.

Known examples/concepts from developer discussions include:

## `UCPFormations.xml`

Used for formation definitions/routes. Historical discussions mention formation count limits and position/style customization.

For Codex:

- locate actual installed file/version
- parse schema from existing examples
- determine whether current FM26 still consumes it in same way
- do not assume historical count limits without testing

## Player Level / Player Style parameter files

Developer discussions reference parameter files affecting player level/style concepts. They should be inspected when analyzing role balance or simulation effects.

Do not edit blindly because the public `GetPlayerLevel13()` code already gives the exact native level algorithm. Parameter files may influence other selection/behavioral layers rather than replace the hardcoded level calculation.

## Loan-limit setting

Historical UCP FAQ exposed a setting in `ucp.ini` under `[MAIN]`, such as `EXTEND_LOANS_LIMIT=1`, to alter loan-limit behavior.

Treat the exact key as historical until verified in the installed FM26 build.

## Modern economic/ranking parameters

Later patches added/reworked parameter files for areas such as media-market rankings and tournament payments. This proves that economic behavior may sometimes be data-driven.

### General rule

Before runtime patching an economy/simulation constant, search:

1. installed config files
2. parameter files
3. XML
4. `.sav` / script data
5. current patch options
6. then executable logic

---

# 15. Localization and text modding

## 15.1 `Translations.huf`

Modern HufConverter makes HUF translation editing practical.

Capabilities described by the author include:

- import/export XLSX
- CSV
- TSV
- TXT
- TR
- hash-to-key-name matching
- older HUF formats
- correct line-break handling
- GUI and CLI

This should be the preferred tool for bulk localization edits.

## 15.2 Historical `CustomTranslation.asi`

This runtime plugin could add/change game text and was used for FM13-era builds. It is useful where HUF alone cannot reach runtime-generated/otherwise inaccessible strings, but current compatibility must be verified.

## 15.3 Language selector

The modern patch ecosystem also ships/maintains a language-selector mechanism. Avoid hardcoding a single localization assumption in tools.

---

# 16. GUI XML and screen modding (`GUI_Elements`)

A mirrored copy of the wiki page documents **40 GUI control/RTTI classes** used in FIFA Manager screen XML:

1. AnimatedButton
2. AnimTrackController
3. AnmRotate
4. AnmTransRotScale
5. BaseButton
6. Button
7. CheckBox
8. ClipRect
9. ComboBox
10. ComboCompound
11. EditBox
12. EditBoxMultiline
13. FmListBox
14. Image
15. ListBoxCompound
16. MemoryBasedImage
17. NullNode
18. ProgressBar
19. Radio
20. ScrollCtrl
21. SimpleImage
22. SlideBar
23. SlideCtrl
24. Slider
25. SndCtrl
26. Spin
27. SpinBar
28. StqcAnimator
29. Table
30. TextBox
31. TextButton
32. Tile3Image
33. Tile5Image
34. Tile9Image
35. TrackedAnimator
36. ValueCtrl
37. VisibleCtrl
38. VpSwitch
39. XgBase
40. Zone

Typical XML concepts shown by the page include:

- `<Obj Rtti="..." Uid="...">`
- `<Attribs ... />`
- `<Appearance Rect="x,y,w,h" />`
- active/inactive/disabled/highlight texture states
- `<Texture Rect="..." Resrc="..." Color="..." ScaleMethod="..." />`
- `<ColText ... />`

The example resources use FM13 custom-control paths.

### What Codex should infer

FIFA Manager UI is at least partly data/XML-driven. For UI changes:

- first locate the screen resource/XML
- inspect existing `Rtti` object hierarchy and IDs
- modify layout/resource references rather than patching executable rendering logic if possible
- preserve UIDs expected by game code

### Caution

The mirrored page was last edited in 2019. Current Season patches may add custom controls or change resource paths. Treat it as structural documentation, then verify against installed assets.

---

# 17. Mobile phone themes

A 2025 wiki tutorial titled `Creating_your_own_mobile_phone_theme` is confirmed. Full live article text was not recovered in this research run.

Modern FIFA Manager 2025 patch notes confirm:

- the phone UI was redesigned
- phone themes can be switched in-game

For Codex, the safe conclusion is:

- phone themes are asset/UI-driven and supported by the modern patch
- inspect current installed theme files and UI XML before editing
- do not invent paths or schema from the title alone

This is low priority for the current FM27 performance/data project.

---

# 18. Graphics locations and override behavior

The `Graphics_Location` page exists and is repeatedly linked by the developer as the mapping reference for asset folders.

Recovered concrete examples:

## Trophy images

Custom trophy images use size-specific folders such as:

- `trophies\32x32\`
- `trophies\64x64\`
- `trophies\128x128\`
- `trophies\256x256\`
- `trophies\534x423\`

Original trophy resources can be inspected in `art_05.big` according to a developer answer.

## User graphics

Historical/current patch FAQs support user-supplied graphics in the Documents-side FM graphics hierarchy. Windowed-mode drag-and-drop was added for some portraits/logos in modern patches.

## Asset precedence insight

Recovered 3D loading-screen documentation gives an important general pattern:

- Documents/user override location can take priority over game-folder custom assets.
- If one level is missing, the game may fall back to another resource (e.g. club stadium image).
- Some defaults are packed inside `.big` archives and therefore do not appear as loose files.

Do not generalize this precedence to every asset type without testing, but it is a strong clue for the resource loader.

---

# 19. Kits (`Updating_kits_for_Universal_Converter_Patch`)

Developer posts confirm:

- large batches of FIFA kits were converted into the Season patch
- custom kits may be placed as loose files under paths such as `data/kits`
- another supported user path historically/currently cited is `Documents/FM/Graphics/3DMatch/Kits`
- official/patch kits may also be packed in art archives
- UCP evolved to use external kit parameter data (historically moved to CSV for parameters such as collar/name/front-number behavior)
- modern FM26 patch documentation links the wiki's “kit fonts” section for custom jersey-name fonts

This is **LOW PRIORITY FOR THE USER** because they do not use 3D, but it demonstrates UCP's data-driven asset pipeline.

---

# 20. BIG/VIV archives and loose files

FIFA Manager uses EA-style archive containers.

Evidence across wiki/developer material:

- `.big` archives contain art/resources (e.g. `art_05.big`).
- `.VIV` can be BIG4-format containers for animation bundles.
- historical tools existed for viewing/editing BIG resources, including fonts/XML/INI previews.
- loose files in certain directories can override packed resources.

### Codex rule

Never unpack/repack giant archives just to change one resource if a documented loose-file override exists.

For performance work, archive enumeration/resource lookup can be profiled, but do not assume extracting archives speeds the game without measurement.

---

# 21. `.O` model format and OTools

The wiki page `O` documents EA's old-gen `.o` model format. Developer research covers:

- meshes
- skeleton/skinning
- shaders
- morph data
- EAGL microcode / shader representation
- model conversion/export/import

Historical progress reports said meshes/skeleton were largely understood, shaders were later researched much further, and animation data inside `.O` remained the least-understood portion at one point.

Modern OTools supports `.O`/FSH workflows and later fixes included:

- Direct3D-device creation for FSH texture processing
- collision-geometry node naming
- FIFA stadium light position export/import
- DXT3 preference option

### Stability insight

Developer research discussed a resource-memory reuse issue where replacing packed model resources with larger uncompressed data could cause a crash if memory was reserved according to original `.fat` uncompressed size. A workaround involved keeping/alignment-sizing resources appropriately.

This is useful general evidence that **resource size assumptions can be hardcoded/metadata-driven**.

### FM27 priority

LOW. User does not use 3D. Only revisit if a non-3D crash loads these assets unexpectedly.

---

# 22. EBO / BNK animation formats

Confirmed wiki pages:

- `EBO`
- `BNK_(Animation)`

Developer summary:

- these store animation data for actors (player/referee), ball and camera
- animation packages are stored in `.VIV` BIG4 archives
- package typically contains BNK, optional EBO, optional text SET files
- EBO appeared around FIFA 2005; BNK around FIFA 2004
- the specific developer research scope was old PC FIFA 2005–FIFA 10

Do **not** assume every format detail maps directly to FM13 without testing.

LOW PRIORITY for current project.

---

# 23. EVT audio-event format

A mirrored copy of `EVT` is available and documents the binary structure in detail.

Core points:

- EVT acts as an audio-event database in FIFA/FIFA Manager.
- A common example is language-specific `pbp_X.evt` commentary/event data.
- File begins with a **24-byte header** containing version, offsets and counts.
- Variable-length sections represent event descriptions, match parameters, events, rules, sentences/phrases, functions and strings.
- Event definitions contain concepts such as ID, duration/expiry, priority, rules, contexts, probability/frequency, flags and parameters.
- The page includes a 010 Editor binary template.

The wiki mirror lists the page under **File Formats** and shows a 2024 edit date, so it is one of the more recently maintained technical pages.

LOW PRIORITY for the user's non-3D/no-commentary goal, but it proves binary format reverse engineering in this ecosystem can be highly detailed.

---

# 24. FFN fonts and FFN Studio

`FFN` and `FFN_Studio` are confirmed wiki pages linked from the current GitHub README.

FFN Studio capabilities:

- build FFN from OTF/TTF
- extract FFN texture into FSH
- extract FFN texture into PNG

Important applicability warning:

The current README says successful import testing was on **TCM 2005 PC**, and other platforms were implemented but not tested. Do not tell Codex “FFN editing is confirmed for FM13” unless it tests an FM13 file successfully.

---

# 25. FSH textures

FSH appears throughout the tools ecosystem as an EA texture container/format. OTools supports FSH texture workflows, and FFN Studio can extract font textures to FSH.

For Codex:

- identify which FM13 subsystem owns a given FSH before editing
- preserve compression/layout requirements
- use existing tools instead of writing a new parser unless necessary

---

# 26. Historical image format/tool hints

Older FIFAM forum material mentions a tool to convert `.tpi` images to PNG, run from the game directory with files in a `tpi` directory. This is not a confirmed reconstructed wiki page and may be old/obsolete.

Treat as historical tooling evidence only.

---

# 27. 3D pitch customization

The recovered `3D_Pitch_Customization` summary states that Season 2020 introduced per-club configuration for:

- pitch pattern texture
- pitch color
- brightness
- goal-net color
- stadium environment type

LOW PRIORITY for current project.

---

# 28. 3D loading-screen customization (related tutorial evidence)

Although this specific tutorial was recovered from the developer forum and was not confirmed as a named wiki page, it provides useful asset-loading facts:

- club-specific 3D loading screen based on unique club ID
- historical target: 1920x1200 BMP
- historical loose folder: `stadiums/tunnel`
- user Documents loading-screen path can have higher priority
- fallback can use club stadium image
- some patch defaults remain packed in `.big`

LOW PRIORITY, but useful for understanding resource override order.

---

# 29. Season/UCP feature history as a reverse-engineering map

Historical UCP Patch Features and Season changelogs reveal a large set of capabilities that were implemented over time. This is useful to Codex because it shows **what kinds of limits/bugs were actually found in data vs script vs runtime code**.

Examples across historical releases:

- increased loan limit option
- improved player-experience distribution
- winger-scoring parameter changes
- additional registration day in Spain
- improved regional-league distribution
- national-team staff updates
- formation rework
- custom table colors
- fixes around June 30 transition/crashes
- reserve/spare-club loading
- geographic coordinate corrections
- editor stability fixes
- historical result fixes
- competition naming/ticket-screen fixes
- UEFA/World Cup qualification changes
- league/nation assessment/ranking changes
- long-term staff bugs
- AI youth-player squad-use fixes
- promotion/relegation prestige fixes
- multithreaded email race-condition fix

### Why this matters

When investigating a bug, Codex should search current patch history/source first. A “vanilla FM13 bug” may already have an existing UCP fix, and duplicating it can cause conflicts.

---

# 30. Save/new-career implications

Many database/competition changes require a **new career**.

Historical changelogs explicitly mark changes such as:

- country names/data
- UEFA assessment/ranking data
- club identities
- World Cup qualification formats

as requiring a new career.

For the current FM27 project:

- transfers
- ratings
- league membership
- competition structure

should be classified as `NEW_CAREER_REQUIRED` unless independently proven otherwise.

Runtime/UI fixes can be save-compatible if they don't change serialized state, but must be tested.

---

# 31. Modding decision tree for Codex

When given a requested change, Codex should follow this order:

## Step 1 — Is it pure player/club/person data?

Use `fmapi` native DB structures and writer.

## Step 2 — Is it tournament structure/qualification/calendar/participants?

Use current UCP `.ucpsc` / ScriptStudio / `FIFAM-Mods/scripts` examples.

## Step 3 — Is it an exposed parameter/config/formation value?

Use parameter/XML/config files.

## Step 4 — Is it localized text or UI asset/layout?

Use HUF / GUI XML / loose assets / supported theme mechanisms.

## Step 5 — Is it closed-source behavior with no supported data path?

Only then consider x86 ASI runtime patching.

## Step 6 — Runtime patch safety gate

Require exact binary identification, signature/bytes, regression test, toggle and rollback.

## Step 7 — Is it 3D/media format only?

For the user's project, deprioritize unless it affects non-3D stability/performance.

---

# 32. What NOT to do in the FM27 overhaul

Based on the recovered wiki + current upstream evidence:

1. **Do not use `.dbe` as the modern production DB mechanism.**
2. **Do not copy legacy ASI addresses into FM26/FM27 Manager.exe.**
3. **Do not equate FPL/Opta/SI IDs with `mFifaID`.**
4. **Do not move PLAYER text blocks to implement loans.**
5. **Do not replace competition scripts with binary hacks if `.ucpsc` can express the behavior.**
6. **Do not interpret FC27 OVR as FIFA Manager player level.**
7. **Do not optimize 3D/XXL assets for this user unless profiling proves non-3D impact.**
8. **Do not assume historical editor limits remain unchanged.**
9. **Do not rebuild tools that current FIFAM-Mods repositories already provide.**
10. **Do not call a change safe/save-compatible without a new-career/save/season-transition test where relevant.**

---

# 33. High-value research targets the wiki does not fully answer

For the current FM27 Overhaul, these require source/reverse-engineering work beyond recovered wiki prose:

## 33.1 Manager.exe non-3D performance internals

Need profiling/instrumentation to locate:

- simulation loops
- calendar processing
- player/club lookup hot paths
- AI transfer calculations
- save/load bottlenecks
- UI list/filter bottlenecks
- allocator/memory pressure

The wiki proves runtime patching is possible, but does not provide a universal performance map.

## 33.2 Current UCP Main internals

Public issue trackers and installers do not imply the entire `UniversalConverterProject.Main.asi` source is public. Treat it as a binary component unless source is actually located.

## 33.3 `Master.dat`

Do not claim it is fully decoded by the current FM27 tooling unless source proves it. The user's architecture audit specifically notes it is not decoded by the Python identity projection.

## 33.4 FC27 schema

Current public `fifaapi` supports through 26 in the inspected source. Native FC27 support must be schema-researched rather than guessed.

## 33.5 Complete live wiki inventory

Still open because Miraheze direct enumeration was inaccessible from this environment. A future XML dump should be parsed to close this gap.

---

# 34. Recommended Codex project integration

Copy this document into:

`C:\FM27CommunityOverhaul\docs\FM13_MODDING_KNOWLEDGE.md`

Then add a short pointer in `PROJECT_STATE.md`:

> For FIFA Manager/UCP/ScriptStudio/ASI/database/file-format decisions, consult `docs/FM13_MODDING_KNOWLEDGE.md`. Use current `FIFAM-Mods` source as higher authority than historical wiki instructions when they conflict.

Codex should **not reread the entire document every small turn**. Instead search it by topic when needed to keep context usage low.

Suggested tags to search:

- `database`
- `loans`
- `starting conditions`
- `mFifaID`
- `ScriptStudio`
- `ucpsc`
- `competition`
- `ASI`
- `runtime patch`
- `HUF`
- `GUI XML`
- `parameter`
- `formations`
- `Graphics_Location`
- `BIG`
- `O`
- `EVT`

---

# 35. Priority map specifically for the user's FM27 Community Overhaul

## P0 — use immediately

- native `fmapi` DB read/write
- identities / `mFifaID`
- contracts / Starting Conditions / loans
- player attribute/level model
- FIFA/FC converter mappings
- ScriptStudio / `.ucpsc`
- current `FIFAM-Mods/scripts`
- new-career semantics
- version-safe ASI principles

## P1 — likely useful

- parameter/config discovery
- formations / player-style parameters
- HUF/localization
- GUI XML if UI/performance/QoL work is done
- current patch bug/feature history

## P2 — use only if needed

- asset folder/precedence knowledge
- BIG/resource inspection
- regular graphics location

## P3 — intentionally low priority

- kits
- stadiums
- pitch
- `.O`
- EBO/BNK
- EVT commentary
- FFN fonts
- 3D loading screens

The user explicitly does not use 3D and does not use XXL portraits.

---

# 36. Source index

## Primary/recovered wiki mirrors and author references

- FIFA Manager Modding Wiki announcement / Scripting Instructions reference:
  `https://forum.fifam.ru/index.php?showtopic=13565`
- DK22/Dmitri historical developer posts (ASI loader, CustomTranslation, TheSeason, converter):
  `https://forum.fifam.ru/index.php?act=thanks&mid=46569&st=50&type=history`
- Season 2020 thread / Domestic Cups tutorial mirror / 3D Pitch summary:
  `https://forum.fifam.ru/index.php?showtopic=13585`
- Domestic Cups recovered content in historical forum page:
  `https://forum.fifam.ru/index.php?p=262341&showtopic=13585&st=60`
- GUI Elements mirror:
  `https://de.scribd.com/document/509506141/GUI-Elements-FIFA-Manager-Modding-Wiki`
- EVT mirror:
  `https://www.scribd.com/document/1011998324/EVT-FIFA-Manager-Modding-Wiki`
- Old-gen `.O` research / wiki link:
  `https://soccergaming.com/forums/threads/old-gen-ea-model-file-format-research-o.6467176/`
- EBO/BNK research / wiki links:
  `https://soccergaming.com/forums/threads/animation-files-research-ebo-bnk.6470245/`
- HUF converter / Translations.huf wiki link:
  `https://soccergaming.com/forums/threads/huf-excel-converter.6474876/`
- FIFA Manager 2025 thread / wiki tutorials:
  `https://soccergaming.com/forums/threads/fifa-manager-2025-released.6473719/`
- Notable changes in FIFA Manager 2025 mirror:
  `https://www.moddb.com/features/notable-changes-in-fifa-manager-2025`
- FIFA Manager 2023 thread / DBE obsolete note / kit paths:
  `https://soccergaming.com/threads/fifa-manager-2023-released.6471430/`

## Current upstream GitHub

- `https://github.com/FIFAM-Mods/fifam`
- `https://github.com/FIFAM-Mods/scripts`
- `https://github.com/FIFAM-Mods/TheSeason`
- `https://github.com/FIFAM-Mods/FIFA-Manager-Patch`
- `https://github.com/FIFAM-Mods/UniversalConverterProjectInstaller`
- `https://github.com/FIFAM-Mods/HufConverter`
- `https://github.com/FIFAM-Mods/FFN-Studio`
- `https://github.com/FIFAM-Mods/AnimationConverter`
- `https://github.com/FIFAM-Mods/otools`
- `https://github.com/FIFAM-Mods/OTools_GUI`

## Archival availability note

- Miraheze archival overview: `https://wiki.archiveteam.org/index.php/Miraheze`

---

# 37. Final Codex directive

When working on FIFA Manager 13/FM26/FM27, use this evidence order:

1. **The user's actual installed files and hashes**
2. **Current FIFAM-Mods source code**
3. **Current Season Patch behavior/issues/changelogs**
4. **Recovered FIFA Manager Modding Wiki documentation**
5. **Historical forum posts/examples**
6. **Inference/reverse engineering**

If levels disagree, do not silently merge them. Document the conflict and test the actual installed build.

The central architectural rule is:

> **Database changes belong in native database semantics; competition changes belong in UCP scripts when possible; text/UI belongs in data/resources; engine behavior belongs in version-guarded runtime patches only when necessary.**

That rule should guide all future FM27 implementation decisions.
