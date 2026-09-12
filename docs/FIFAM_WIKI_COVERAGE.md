# FIFA Manager Modding Wiki — Coverage Ledger

**Date:** 2026-09-10

## Why this ledger exists

The live `fifam.miraheze.org` wiki could not be enumerated directly from the automated research environment. Therefore this file separates **confirmed pages** from any claim of exhaustive coverage.

A page is listed only when its existence was confirmed through a mirror, developer post, GitHub README, or indexed reference.

| Page | Evidence strength | Content recovered | Notes |
|---|---|---|---|
| Scripting_Instructions | High | Strong + current GitHub equivalent | FM07–14 instruction list; exact FM13/14 table preserved in `fifam/doc/formats/scripts-fm13-14.txt` |
| ASI_Loader_(FIFA_Manager) | High | Strong historical | DLL/ASI plugin architecture, Visual Studio/C++, reverse engineering |
| CustomTranslation.asi | High | Strong historical | Runtime text additions/changes |
| TheSeason.asi | High | Strong + current source | Start-season/date plugin; modern source supersedes old wiki where conflicting |
| ScriptStudio | High | Strong | `.ucpsc`, syntax highlighting, Editor import |
| Universal_Converter_Project_Scripting_Syntax | High | Strong examples | Main high-level competition-scripting reference |
| Universal_Converter_Project_Database_Editing | High | Strong historical | `.dbe`; explicitly obsolete for FM23+ |
| UCP_Patch_Features | High | Strong historical | Season/UCP feature overview |
| Graphics_Location | High | Partial | Trophy paths and asset references confirmed |
| Updating_kits_for_Universal_Converter_Patch | High | Strong | Loose paths and kit adaptation references |
| 3D_Pitch_Customization | High | Summary | Per-club pitch pattern/color/brightness/net/environment |
| Domestic_Cups_Tutorial | High | Near-full | ScriptStudio cup syntax/import/prizes/IDs |
| Creating_your_own_mobile_phone_theme | High | Title/summary | Added July 2025; full article not recovered |
| Notable_changes_in_FIFA_Manager_2025 | High | Strong mirror | Modern patch capabilities |
| FIFA_Manager_2021_Leagues | High | Historical summary | League list |
| Pre-Season_2020_Leagues | High | Historical summary | Playoff/league systems list |
| Season 2019 database leagues page | Medium | Title text only | Indexed result shows “FIFA Manager 13 Season 2019 Database Leagues”; exact URL/page slug not fully recovered |
| O | High | Strong developer recovery | `.o` meshes/skeleton/shaders/morph |
| EBO | High | Strong summary | Animation data |
| BNK_(Animation) | High | Strong summary | Animation sequence bank |
| EVT | High | Near-full mirrored page | Audio-event binary DB, 010 template |
| FFN | High | Tool README link | Font format; FM13 compatibility not established by FFN Studio README |
| FFN_Studio | High | Current README | OTF/TTF create; FSH/PNG extraction |
| Translations.huf | High | Strong current tool info | HUF localization DB |
| GUI_Elements | High | Near-full mirrored page | 40 UI control classes and XML examples |

## Unresolved completeness gap

Until a full MediaWiki XML dump or `Special:AllPages` response is obtained, **there may be additional pages not represented above**. Any future researcher/Codex task that obtains a dump should:

1. enumerate namespace 0 pages;
2. diff against this ledger;
3. ingest missing pages;
4. update `FM13_MODDING_KNOWLEDGE_FOR_CODEX.md`;
5. preserve historical/current applicability tags.
