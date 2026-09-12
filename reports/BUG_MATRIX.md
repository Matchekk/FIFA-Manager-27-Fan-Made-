# Bug matrix — 2026-09-08

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
