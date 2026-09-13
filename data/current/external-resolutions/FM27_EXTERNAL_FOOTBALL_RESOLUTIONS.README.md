# FM27 external football-resolution handoff

This pass is designed to remove **football web research** from Codex.

## Result

All **624** rows now have an explicit decision.

Final decisions:

- APPLY: 6
- KEEP_EXISTING: 97
- NONBLOCKING: 137
- ESCALATE_TECHNICAL: 384
- empty / awaiting external football resolution: **0**

The original handoff had 482 empty external-resolution rows. This file resolves the football side of all of them.

## Meaning of ESCALATE_TECHNICAL

It no longer means “research the football fact”.

It means:

> the football state is resolved; Codex must only synthesize/apply the correct native FIFAM plan or local identity bridge.

Use `FM27_EXTERNAL_FOOTBALL_RESOLUTIONS.csv` for the exact `technical_action`, loan owner/end, football fact, evidence URL and compact implementation instruction.

## 1.0 rules applied

- If native club already equals target and only joined/contract/shirt metadata is incomplete: `KEEP_EXISTING`. Never invent metadata.
- If the target 2026/27 roster differs from native and chronology fields are incomplete: move to target while preserving unresolved native metadata.
- Current loans: use the researched owner/destination/end and the already-proven active-loan start projection `2026-07-01`.
- Season-long 2026/27 loans default to `2027-06-30` only where the external research established a season-long/current-season loan.
- Vladimir Neuman is a specific six-month exception ending `2026-12-31`.
- Missing native identity: local identity bridge first; CREATE only if absent. Never invent EA/FIFA IDs.
- Stale native loan/future conditions for permanent/current target players must be cleared without destroying valid target/contract/profile state.
- Undisclosed contract/shirt/join chronology must not block FM27 1.0 when current football state is already correct.

## Special resolutions

- Noah Lahmadi: free transfer to **Aviron Bayonnais**, 24.07.2026. Map to that native club if it exists; otherwise free-agent fallback.
- Rica Rocha: current Vitória SC assignment is nonblocking; first-team/preseason evidence coexists with B-team profile usage.
- Rodrigo Guth: treat as **one-season loan from CA Talleres to Fortuna Sittard**; Fortuna's current official announcement is used despite conflicting secondary wording elsewhere.
- Current-loan generalized return logic remains the previously validated Native08 approach.

## Files

- `FM27_RESOLVED_REVIEW_QUEUE.external-pass1.csv` — original schema, all decisions now populated
- `FM27_EXTERNAL_FOOTBALL_RESOLUTIONS.csv` — technical action + football fact + evidence companion
- `FM27_EXTERNAL_FOOTBALL_RESOLUTIONS.manifest.json` — hashes/counts
- `FM27_CODEX_IMPLEMENTATION_ONLY.md` — implementation-only Codex handoff

## Important

Do **not** feed the whole research history to Codex.

Give Codex the resolved queue + companion + the short implementation-only prompt. Codex should not browse football sources.
