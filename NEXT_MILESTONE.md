# Next Milestone: Runtime07 Editor and Career Smoke

Start this milestone in a fresh primary thread. Its only goal is to test the already
validated native07 candidate in the prepared isolated runtime through Editor export, a
new 2026/27 career start, and save/reload. Do not add data, run performance benchmarks,
or begin native08 here.

## Acceptance

- An operator approves the single constrained Runtime07 launcher UAC prompt.
- Automation binds only the copied Runtime07 Editor process/window by executable path.
  The user's already open original Manager and original Editor windows are excluded.
- The copied Editor exports `Master.dat` under
  `runtime/game-test-20260912-07/database/`; the original installation remains unchanged.
- The isolated Manager starts a new 2026/27 career from that export and reaches a stable
  playable screen.
- A save is created in the isolated test context, then loaded successfully with the same
  career identity and date/state observations.
- Candidate, export, process paths, hashes, screenshots/observations, and any exception
  are written to a compact report. On PASS, update `PROJECT_STATE.md`, commit the small
  checkpoint, and end the thread.

## Exact Start and Proofs

- User-facing start file: `C:\\FM27CommunityOverhaul\\runtime\\START_NATIVE07_EDITOR_SAFE.cmd`
  (SHA-256 `e093faa3f4755802493e8b152e24bb3e293a47e578c5c8f5f1528e647193c0f0`).
- The user closes the original Manager and Editor, starts that command file, and approves
  UAC. Do not export until the fresh Runtime07 Editor process path, native07-specific data,
  and absent runtime `database/Master.dat` have all been observed together.
- Bound launcher used by the command file:
  `C:\\FM27CommunityOverhaul\\runtime\\launch-isolated-editor.exe`
- Runtime root: `C:\\FM27CommunityOverhaul\\runtime\\game-test-20260912-07`
- Native07 candidate: `data/generated/release-candidate/transfer-increment-20260909-07/`
- Preflight: `reports/local/RUNTIME_SMOKE_NATIVE07_PREFLIGHT_20260912_01.json`
- Current UAC blocker: `reports/local/RUNTIME_SMOKE_NATIVE07_BLOCKED_20260912_01.json`
- Editor path-routing proof: `reports/local/RUNTIME_EDITOR_ROUTING_20260912_01.json`
- Conditional ASI-route proof: `reports/local/RUNTIME_EDITOR_ASI_ROUTE_20260912_02.json`
- Candidate cumulative proof: `reports/local/NATIVE_CUMULATIVE_VALIDATION_07.json`
- Evidence archive verification: `reports/local/NATIVE_INCREMENT_ARCHIVE_VERIFICATION_07.json`
- Database status: `reports/PROJECT_STATUS.json`

## Later Milestones

- Jahnilo review/proposals: `data/generated/identity-review-20260912-jahnilo-01/`
- EA rating review, 149 candidates and 86 holds:
  `data/generated/ea-refresh-20260912-01/NEW_IDENTITIES_REVIEW.json`
- Latest current-origin reconciliation:
  `data/generated/prior-season-transfer-review-20260909-05/reconciliation/`
- Latest departure reconciliation: `data/generated/departure-review-20260909-05/`
- Reviewed origin history: `data/overrides/historical_transfers.json`
- Correction-only origin review, do not integrate or count as progress:
  `data/generated/prior-season-origin-review-20260912-01/`. The real later origin backlog
  is review05's held set after subtracting aliases already applied.
- Belgium, season transition, performance, and installer work remain separate milestones.

Knowledge pointers: `docs/FM13_MODDING_KNOWLEDGE.md`,
`docs/FIFAM_WIKI_COVERAGE.md`, and `reports/usage-forensics/FINAL_REPORT.md`.
