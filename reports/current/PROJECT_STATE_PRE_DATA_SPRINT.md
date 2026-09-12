# FM27 Community Overhaul â€” Project State

Updated: 2026-09-12 UTC

## Active sprint: 2026/27 football data completion (supersedes next actions below)

The user confirmed the integrated corrected current-loan behavior in a NEW career:
representative integrated current-loan runtime test PASS. Native08's 794 active loans,
744 corrected starts and 50 intentionally unchanged starts are accepted foundation.
Do not repeat Native07/08 or general loan diagnosis. Historical observations below are
retained as evidence history; their pending loan-verification instructions are superseded.

Current production scope: ENG1, ITA1, ESP1, GER1, FRA1, POR1, NED1, BEL1, TUR1,
CZE1, GER2, GER3. Complete authoritative 2026/27 membership, club-level squad and
transfer coverage, explicit exceptions, then freeze and build deterministic Native10
from `data/generated/release-candidate/native08-integrated-20260912-01`.
Preserve ratings, history, ownership, loan ends, contracts and future conditions except
source-supported explicit deltas. No rating calibration or extended simulation this sprint.

Work products: `data/current/`, `reports/current/`. Membership and bounded squad workers
produce staging evidence; Sol owns canonical integration. Never treat inherited applied
counts as current coverage. Freeze requires acceptable coverage; candidate release
requires native reread, exact semantic diff and one representative new-career smoke.

## Release Goal

Deliver a playable FM27 season update for FIFA Manager 13. Native/database proof is
necessary, but release readiness also requires an isolated Editor export, a new career,
save/reload, season transition, performance evidence, and a reversible installer.

The earlier `40%` figure is a planning estimate only. It is not measured completion and
must not be presented as a release-readiness score.

## Verified Milestone

`native07` is the latest immutable candidate. It preserves all prior native06 rows and
adds the reviewed prior-season transfer increment: 3,048 cumulative club changes,
794 loans, 296 expired-loan resolutions, 255 successor loans, 181 free agents, and
25 loan purchases. All 3,765 inherited rating profiles and 82,863 attributes were
preserved. The bound suites report 298 Python tests and 123 native tests PASS.

The native07 pipeline completed native write, independent inspection, reread, eleven
pipeline steps, and eleven cumulative preservation checks. Its evidence archive was
independently reread and verified. The authoritative summary is
[`reports/PROJECT_STATUS.json`](reports/PROJECT_STATUS.json); the cumulative proof is
`reports/local/NATIVE_CUMULATIVE_VALIDATION_07.json` and the local archive manifest is
`data/generated/transfer-increment-20260909-07-evidence-v2/EVIDENCE.json`.

## Native08 Runtime and History Update

Native08 is closed with overall PARTIAL, not an unrestricted release PASS.
Native07-specific Cabral payload: PASS. Day7/Day30: PASS by operator evidence;
separate Day1: PARTIAL, explicitly waived. First 2027 calendar crossing and
post-transition save/reload succeeded; structural transition gate remains PARTIAL
because the original candidate exposed Moore/Amissah loan discrepancies.
Darvich returned directly; the corrected two-player experiment returned both
Moore/Amissah per operator. No multi-year validation is claimed.

History and loan correction are integrated and Editor-exported in the separate
`runtime/loan-test-20260912-08`. Combined candidate: `native08-integrated-20260912-01`.
Ten-country history package; 744 current-loan start projections, 50 unchanged.
Exact-delta/native validation PASS; 266,764 player/rating values preserved.
Combined-export new-career/history/return verification remains NOT_TESTED.
Original/Runtime07 Manager.exe and Master.dat remain hash-identical. All 16
original saves and 12 baseline configs are restored/verified; test evidence kept.
Manager/Editor closed. Cabral planned/displayed contract-date discrepancy remains open.

Next bounded milestone, fresh task: verify the combined export in a new career,
including history views, active loans, representative corrected return and
post-transition save/reload. Do not restart a global audit or broad rating work.
See `reports/local/NATIVE08_FINAL_REPORT.md` and `reports/local/NATIVE08_GATE.json`.

## Runtime and Data Work in Progress

Runtime07 Editor export was observed on 12 September 2026. Its exact isolated process
path and Native07-only Jovane Cabral record (GrÃªmio, shirt 77, contract 2027) were
verified before export while runtime Master.dat was absent. Operator screenshots show
the 125-country initialization notice and final "Datenbank gespeichert!" confirmation.
The exported `runtime/game-test-20260912-07/database/Master.dat` has 71,966,494 bytes,
SHA-256 `2c507e3d6e725cd36d0920f881dc4fbcfc954b8c4e413069621bd8002d931333`.
The original installation Master.dat hash is unchanged. Evidence and remaining smoke
steps: `reports/local/RUNTIME_SMOKE_NATIVE07_20260912_04.json`.
The new career and reload were observed with Marek Wrona at 1. FC KÃ¶ln on 01.07.2026,
7 unread messages and 57.0 million cash before and after reload. The uniquely named
Native07-Smoke-20260912.ea exists (110,980,876 bytes; SHA-256
32117f2b8a30c3f97080658943004fdca46a49e877ae7058db23e1790fc21de8).
This bounded Editor/export/career/save-reload milestone is PASS; the full release is not.
Computer-use screenshot capture failed, so the Editor UI observations use operator
screenshots combined with independently observed process paths and filesystem checks.

The country-selection UI faults were resolved in the observed test context. Existing
32px archive flags were recovered as loose assets in Runtime07; after a windowed
restart the operator confirmed flags, also visible in the club-selection screenshot.
The pre-existing FM26 touchpad scroll fault was resolved by the game's own
"Ich benutze ein Touchpad" option (explicit operator confirmation). No input hook was
added. Loose-flag versus restart causality was not tested separately. The shared
WINDOWED preference was restored, along with the automatically overwritten
quickstart.ea. All 15 pre-existing saves match their pretest backups; the new Native07
save and enabled touchpad option remain. The completed smoke ran in windowed mode;
fullscreen after restoration was not retested. Native07 was identified in the Editor
and selected for career creation; no separate in-game Cabral record was inspected.

The separate 12 September EA capture identified 149 exact existing-native identities for
rating review. Another 86 records remain holds because native identity is unresolved or
only a Transfermarkt profile match exists. EA affiliation is observation, not transfer
authority. See `data/generated/ea-refresh-20260912-01/NEW_IDENTITIES_REVIEW.json`.

Jahnilo Wiegel-Triebel has a guarded identity/alias/history and expired-loan draft under
`data/generated/identity-review-20260912-jahnilo-01/`. It still requires live override
integration and current/departure reconciliation before it can enter the next native plan.

`data/generated/prior-season-origin-review-20260912-01/` is correction-only and must not
be counted as new mapping progress: it rechecked 51 aliases already applied, produced zero
new aliases, and its 31 package-limit holds are not data conflicts. Later origin work must
start from the still-held rows in review05 after subtracting aliases already present.

## Open Release Gates

- Season-transition observation against the isolated runtime (later milestone).
- Remaining football-data work, beginning with the bounded Belgium package.
- Remaining prior-season origin-club rows from review05, excluding aliases already applied;
  the 12 September correction-only origin review is not an integration input.
- Review and integration of the 149 EA rating candidates while retaining all 86 holds.
- Performance measurement and a reversible installer/uninstaller after gameplay gates pass.

## Next Concrete Work

1. Native07 runtime milestone is complete. End this task after committing its selected
   evidence and fixes; use a fresh task for the next data or release gate.
2. Integrate and reconcile the Jahnilo draft, then prepare its native08 plan row without
   launching a one-player native build.
3. Build the 149-player EA rating-review package and keep the 86 unresolved cases held.
4. Complete and validate the next bounded Belgium data package.
5. Bundle accepted transfer/rating rows into native08, then handle season transition,
   performance, and the reversible installer in later bounded milestones.

## Knowledge and Evidence

- [`docs/FM13_MODDING_KNOWLEDGE.md`](docs/FM13_MODDING_KNOWLEDGE.md) is the practical
  database, scripting, Editor, runtime, asset, save, season, and installer knowledge base.
- [`docs/FIFAM_WIKI_COVERAGE.md`](docs/FIFAM_WIKI_COVERAGE.md) records recovered wiki
  coverage and confidence limits.
- [`reports/usage-forensics/FINAL_REPORT.md`](reports/usage-forensics/FINAL_REPORT.md)
  preserves the usage-forensics evidence: 1,880 responses, about 262.8 million input
  tokens, about 140,000 median input tokens, and 16 observed compactions.

Keep this file compact and report-bound. Never write to the original FIFA Manager 13
installation during preparation or automated validation.
