# FM27 Community Overhaul — Project State

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

## Runtime and Data Work in Progress

Runtime07 is copied and bound to an isolated working directory. Static routing proves
that the copied Editor would export `Master.dat` inside that runtime. The launch stopped
before Editor input because the administrator consent surface was not targetable; an
operator must close the original apps, start `runtime/START_NATIVE07_EDITOR_SAFE.cmd`,
and approve the single constrained UAC prompt. Before export, the exact Runtime07 Editor
process, native07-specific data, and absent runtime `Master.dat` must be checked together;
the ASI route remains conditional. No original installation file was changed. See
`reports/local/RUNTIME_SMOKE_NATIVE07_BLOCKED_20260912_01.json` and
`reports/local/RUNTIME_EDITOR_ASI_ROUTE_20260912_02.json`.

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

- Operator-approved isolated Editor export and verification that Runtime07 receives the
  exported database.
- New-career start, save/reload, and season-transition observations against the isolated
  runtime.
- Remaining football-data work, beginning with the bounded Belgium package.
- Remaining prior-season origin-club rows from review05, excluding aliases already applied;
  the 12 September correction-only origin review is not an integration input.
- Review and integration of the 149 EA rating candidates while retaining all 86 holds.
- Performance measurement and a reversible installer/uninstaller after gameplay gates pass.

## Next Concrete Work

1. In a fresh primary thread, have an operator approve the constrained Runtime07 Editor
   UAC prompt from `runtime/START_NATIVE07_EDITOR_SAFE.cmd`; verify the exact process,
   native07 data, and missing runtime `Master.dat` before export. Then export only to the
   isolated runtime, start a new 2026/27 career, and run save/reload checks. Original
   Manager and Editor windows are not valid Runtime07 targets.
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
