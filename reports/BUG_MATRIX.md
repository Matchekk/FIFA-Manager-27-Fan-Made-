# Bug matrix — 2026-09-08

## Additional staging gaps found by complete source-file inventory

`reports/local/NATIVE_FILE_COVERAGE_07.json` inventories 1068 database/external/history
files. Candidate07 omits six UCP/editor auxiliary files: `AssessmentAFC.sav`,
`AssessmentCAF.sav`, `CountryNames.txt`, `picture.tga`, `PriorityClubs.txt`,
`TownDataUniques.txt`. Native preservation and its verifier now include all six;
the fixture checks exact binary contents. A new candidate is required to validate
the repair. The historical 638-file support PASS covered only its declared subset.

The inventory also exposes `Master.dat` as an unfulfilled game-export step.
The installed EdManager binary contains `Database.CompleteWorld.WriteDatabase`
and `database\\Master.dat`; Manager contains a Master.dat path. This is static
evidence of the export/runtime boundary, not proof that the candidate was exported.
Do not copy the original compiled database and claim updated squads are playable.
`database/data/CountryData21.zip` contains one `CountryData21.sav` archive member;
its intended backup/runtime role remains to be resolved separately.

## Proven offline database-tool defects fixed in candidate 05

| Defect | Cause and repair | Evidence |
|---|---|---|
| 819 international competitions absent after reread | Upstream writes `script_converted`, while its reader loads `script`. Staging now preserves the original external scripts, including mod-specific sections, alongside historical data and omitted name tables. | All 2380 competition serializations agree; 638 support files are byte-identical. `reports/local/NATIVE_EXTENDED_ROUNDTRIP_05.json`, `reports/local/NATIVE_SUPPORT_05.json`. |
| Four directed relationships lost, eight added by the old writer | The upstream brother writer groups neighbours as a clique and skips some edges by pointer ordering. Exact pair rows now preserve the original symmetric graph, with full validation before writing. | All 11226 directed edges agree after native reread. A non-clique fixture passes; asymmetric or ambiguous graphs fail before replacement. |

These repairs affect the isolated offline staging tool. They do not prove game
runtime stability, saves or season transitions. Candidate 04 retains its FAIL
evidence; candidate 05 contains the corrected and validated write.

## Runtime and historical candidates

No runtime fix is claimed. The following are candidates, not proven causes.
3D/XXL issues are excluded by the user's scope override.

| Candidate | Reproduction/evidence | Version/root cause/fix/regression/save status |
|---|---|---|
| Direct game launch ends immediately | Start Manager.exe with its installation as CWD; observed twice, controlled retry exit 0 within 1.5s; no matching recent Application Error event | Observed EXE hash in AUDIT; cause unknown; awaiting normal launch route; no patch |
| Duplicate FIFA IDs | Run identity validator; 23 duplicate FIFA-ID values in installed data | Data finding confirmed; identity matching blocks these; not a demonstrated game crash; no save mutation |
| Contract end before joined date | Run identity validator; 14,851 candidates globally, including historic/default dates | Projection field order follows upstream; requires native semantic review, no bulk date repair |
| Italian/Spanish language IDs | Switch language and exercise text/date paths in a controlled new career | Upstream fix status and affected versions not yet verified; no duplicate patch |
| First team vs reserve result display | Arrange such a fixture and compare engine result/table/UI | Not reproduced; root cause unknown; no patch |
| UI resolution/scaling/hitboxes | Exercise menus/search/dialogs at user's display settings | Not tested in running game; no 3D work |
| Competition edge cases | Fixed DB and seed, redraw/qualification/promotion transitions | Needs native round-trip and game simulation; not reproduced |
| June 30 / July 1 2028 career crash | Controlled 2027-2030+ career with dated saves and process traces | Community hypothesis; not reproduced; no speculative date patch |
| Fitness/training inconsistency | Log training load, roster, match use and fitness for fixed scenarios | Community hypothesis; no parameter rebalance |
| National-team fitness | Compare before/during/after international duty | Not reproduced; no parameter patch |
| Youth/amateur lineup selection | Fixed available roster/tactics, compare selected lineup repeatedly | Not reproduced; no RNG/selection patch |
| Repeated desire to leave | Log morale/contracts/playing time and event sequence | Not reproduced; no morale rebalance |
| Save corruption / long-career slowdown | New test career, repeated load/save, 1/3/5/10 seasons | Not run; existing saves untouched |

Each future fix needs a specific reproducer, version/hash, root cause,
regression and save-compatibility statement before activation. Warnings in
the identity projection are not automatically simulation defects.
