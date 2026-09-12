# FM27 Community Overhaul â€” Project State

Updated: 2026-09-12 UTC

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

Native07 payload was directly observed in the career. Day7/Day30 and the first
2027 transition/save-reload were operator-confirmed; the separate Day1 gate was
explicitly waived. Loan-return discrepancies led to a separate two-player date
experiment; this does not yet supersede the Native08 gate or complete cleanup.

The 2025/26 title/cup/movement-marker history package is offline complete at
`data/generated/history-20260912-03/`: ten country files, 20 competition-history
records, 103 intended fields and 37 obsolete-marker removals validated. Native
reread and all 266,764 player/rating records match Native07. It is not installed
or Editor-exported as a standalone package and excludes full match-result archives and later Czech
administrative membership changes. See `reports/local/HISTORY_2025_26_REPORT.md`.
The combined candidate `native08-integrated-20260912-01` now includes this history
and 744 current-loan start-date projections to 01.07.2026 (50 of 794 unchanged).
Independent byte-delta validation and native reread PASS; all 266,764 player/rating
values are preserved. Moore/Amissah return behavior was operator-confirmed in the
two-player experiment; the full combined candidate is not yet game-tested.
At the user's explicit request, it is reversibly integrated into the closed
`runtime/loan-test-20260912-08`, with its previous database/Master backed up.
Runtime07 and original executable/Master identities remain unchanged; all 16
pre-existing saves match preflight after restoring four test-modified files.
Next: Editor export of the combined candidate, followed by bounded in-game history
and loan checks and final Native08 cleanup. See `reports/local/NATIVE08_INTEGRATION_REPORT.md`.

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
