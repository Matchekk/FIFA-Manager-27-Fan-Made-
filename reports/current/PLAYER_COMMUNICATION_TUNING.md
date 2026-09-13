# Player communication tuning

Status: **APPLIED — RESTART REQUIRED**

Profile: `relaxed-player-communication-v1`

Runtime: `runtime/loan-test-20260912-08`

## Purpose

Calendar simulation can skip regular player talks. The game's player-talk
difficulty description explicitly ties those talks to player morale and trust.
The corresponding supported parameter block is `MORALE_AND_TRUST` in
`fmdata/ParameterFiles/Difficulty Levels.txt`.

The profile raises morale and trust when they fall below a healthy level. It is
applied to Easy, Medium and Hard so the result does not depend on the career's
selected player-talk difficulty.

| Setting | Original Easy | Original Medium | Original Hard | Tuned value |
|---|---:|---:|---:|---:|
| `PLAYER_MORALE_MODIFIER_THRESHOLD` | -50 | 0 | 50 | -100 |
| `PLAYER_MORALE_MODIFIER` | 3 | 0 | -3 | 10 |
| `PLAYER_TRUST_MODIFIER_THRESHOLD` | 6 | 0 | 8 | -10 |
| `PLAYER_TRUST_MODIFIER` | 1 | 0 | -1 | 1 |

Per the parameter file's own threshold semantics, a negative threshold means
"apply while the current value is lower than the threshold's magnitude". The
tuned profile therefore assists morale below 100 and trust below 10.

## Deployment and safety

- Runtime parameter before SHA-256:
  `d30ff3f4c96be562fab7a196c1fffdc0132b03da1ac6ccb18d6903e1c706652a`
- Runtime parameter after SHA-256:
  `5cbaf8158c33b88f7b1f63a0d7a5c6dea06495d17e765ec59d9393d70112b6bc`
- Hash-verified local backup:
  `reports/local/player-communication-20260913-02-backup`
- Local deployment report:
  `reports/local/player-communication-20260913-02.json`
- Original installation modified: **no**

The running Manager process was deliberately left open to protect unsaved career
progress. FIFA Manager reads these parameters at startup, so the profile becomes
active on the next game launch.

## Validation

- Profile JSON parsed: PASS
- Patch tool compiled: PASS
- Parameter block has balanced `BEGIN`/`END` markers: PASS (12/12)
- All 12 requested values reread exactly: PASS
- Joined value/`END` markers: none
- Backup hash verification: PASS
- Protected original hashes unchanged: PASS

This is a supported parameter adjustment. No executable or save file was patched.
A hard-coded notification may still appear in some exceptional situations, but
low morale and trust from skipped routine conversations should recover instead of
remaining a lasting performance penalty.
