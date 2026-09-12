# Validation â€” 2026-09-08

| Check | Result |
|---|---|
| Synthetic Python unit suite | 42 passed |
| PowerShell parser, all toolkit scripts | Passed |
| Upstream generic/fmapi/fifaapi Win32 builds | Passed; upstream warnings recorded |
| Own x86 native probe and optional staging writer /W4 /WX | Passed |
| Native read of installed database | Completed, 266,764 players |
| Persisted player-ID projection parity | 255,297 checked, zero mismatches in FIFA ID/club/DOB |
| All-player identity multiset parity | Equal, including free agents |
| Process counter sampler | Passed against synthetic x86 fixture, eight samples |
| ZIP clean install/uninstall | Passed, installed files removed |
| ZIP uninstall after user edits | Modified and unrelated files preserved |
| Original relevant game-file hashes | 943 verified unchanged |
| Git diff whitespace check | Passed |
| Actual game baseline | Running; 114 observation samples, controlled baseline pending |
| Native database writer round-trip | External native rewrite completed; projected player semantics equal; full DB/game validation pending |
| Current 12-league production data | Incomplete; review reports only |
| Long-career / season transition / save tests | Not run |
| Performance improvements | None claimed |

Live installation data was read only for explicit audit/integration verification.
Automated unit tests use synthetic records and temporary output paths; no
real saves, game binaries or licensed assets are test fixtures or ZIP contents.
The synthetic Manager.exe fixture is our own tiny C++ process, unrelated to
the installed game. Its counter result is not a game performance result.

Twelve-league sources: 222/222 detailed squad pages, 6266 roster records, 7178 transfer-event rows; 5980 official FC27 website entries. Inspect CANDIDATE_VALIDATION.json for the actual staged-write gate. No production or performance success is inferred from source coverage.

Final native candidate: PROJECTED_STAGE_MATCHES_PLAN, 266764 players before/after, 3820 planned updates including 948 club moves, zero unexpected rows. Attributes, talent and other projected fields match the exact expected plan. Source game hashes: 943 unchanged. This is not in-game/save/season validation.
