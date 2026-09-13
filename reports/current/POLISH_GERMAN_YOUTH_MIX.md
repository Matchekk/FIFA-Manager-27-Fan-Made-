# Polish-German youth mix parameter profile

Status: **APPLIED - RESTART REQUIRED**

Profile: `polish-german-youth-mix-v1`

Runtime: `runtime/loan-test-20260912-08`

## Effect

The profile changes only the Germany-to-Poland row in
`Youth Players Countries.txt`:

- Polish first-nationality weight at German clubs: 1.04 -> 6.0.
- Polish second-nationality weight at German clubs: 1.0 -> 12.0.
- All other country pairs remain byte-identical.

This makes Polish youth players and German-Polish youth players noticeably more
common at German clubs while retaining the normal German youth pool. It applies to
future youth generation after the next normal game restart.

## Technical scope

The FIFA Manager 13 parameter table receives the generating club country, but it
does not expose the human manager's nationality. The guarded parameter solution is
therefore Germany-wide rather than dynamically tied to one manager or VfB Stuttgart.
It implements the current Polish-manager-in-Germany career case without an unsafe,
version-specific executable hook. Other manager/club country combinations can use
separate exact country-pair profiles later.

## Validation

- Profile SHA-256:
  `0b16966263fcd64f732dfde3b6024e7d083f8932bdf2c116004e945da6292320`
- Guarded application: PASS, 1/1 exact patch in 1 file.
- Exact reread/idempotence: PASS, 0 files changed.
- Python regression suite: PASS, 305/305.
- Runtime parameter reread: PASS.
- Backup hash verification: PASS.
- Protected original installation: unchanged.
- Executable, database and save files changed: none.
- Running isolated game process: responsive and left open.

Local evidence and reversible backup:

- `reports/local/POLISH_GERMAN_YOUTH_MIX_V1_APPLY_20260913_01.json`
- `reports/local/POLISH_GERMAN_YOUTH_MIX_V1_IDEMPOTENCE_20260913_01.json`
- `reports/local/polish-german-youth-mix-v1-backup-20260913-01`
