# Dynamic player development profile

Status: **APPLIED — RESTART REQUIRED**

Profile: `dynamic-development-v1`

Runtime: `runtime/loan-test-20260912-08`

## Intended behavior

The profile makes season and match performance matter more for player growth in
all clubs. It is applied after `relaxed-career-v1` and uses the global development
files rather than editing player records or save games. The game labels the
resulting level changes collectively as its pre-season, New Year and post-season
"Ups and Downs" evaluations.

- Outfield target-age window: 23–27 → 24–28.
- Goalkeeper target-age window: 25–29 → 26–30.
- General skill-decrease probability multiplier: 0.60 → 0.45.
- Strong performances receive more match-development credit.
- Poor performances still matter, with a smaller automatic downward effect.
- Overall performance-development multiplier: 0.60 → 0.78.
- Youth weekly skill/position development: 4/5 → 5/6.
- Youth position talent bonus: 1.00 → 1.15.
- Human-team development reduction: 0.75 → 1.00, matching the global rate used
  by computer-controlled clubs.
- Development-curve and match-training gains are raised moderately across the
  full curve, including late developers.

The configurable national-competition re-evaluation allows more positive cases,
requires only three appearances, protects players under 24 from its negative
branch, raises the positive value and lowers the negative value.

## Technical boundary

The game exposes global development curves and the national-competition
re-evaluation through parameter files. It does not expose a separate parameter
that changes the number of pre-season, New Year and post-season screens. The
profile therefore increases how many meaningful changes are produced within the
existing evaluation cadence.

The 24-year late-bloomer behavior is implemented through the global target-age
development window. A read-only inspection of the decrypted runtime code for the
exact protected executable also confirmed that the separate star-talent evaluator
already accepts ages below 25. Both its outer eligibility branch and its internal
evaluation function compare the calculated player age with 25 and skip at age 25
or above. Talent stars can therefore already change through age 24; no age-limit
binary patch is required. The evaluator operates on a club roster and is not tied
to the human-team UI. The UI presents the user's re-evaluation, while the global
development inputs apply to computer-controlled clubs as well.

No executable bytes were changed. The check was read-only and version-bound to
the recorded `Manager.exe` SHA-256 below.

## Validation

- Guarded profile application: PASS, 18/18 patch groups across 3 files.
- Exact runtime reread/idempotence: PASS, all 18 groups already applied.
- Exact before/after diff: PASS, only the intended parameter lines changed.
- Profile SHA-256:
  `8fcbf399cf49c4290c8a453f8efb6fe4fbc9f6659df7ecf0e9038403c86413cc`
- Runtime hashes after application:
  - `DC.txt`: `f49c97d3df06b12d10eabc7d83a5df4c459ef32868610d1cf29a69e54224fcb4`
  - `Training.txt`: `ada9b4ddb12bf6b1ab57543cd6a90b0ede37b8bfc9e3f8ad1077ea472693bc4e`
  - `National Cup Ups And Downs.txt`:
    `ca45841a33f17f9ecc820748298c55e044d03163e8c6dcac8809f66b0e10d3be`
- Automated project tests: PASS, 305/305.
- Protected original installation: unchanged.
- Inspected `Manager.exe` SHA-256:
  `8ebe1291fbcc1291bfee182995a165194156a0b4b8e0d6c80994cadb087a857c`
- Runtime star-talent age gate: PASS, eligible through age 24.
- Executables and save files modified: none.

The running game was left open to protect the active session. The parameter files
are loaded on startup, so this profile becomes active after the next normal game
restart.
