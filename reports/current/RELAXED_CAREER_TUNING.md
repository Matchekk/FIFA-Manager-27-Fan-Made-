# Relaxed Career parameter profile

Status: **APPLIED — RESTART REQUIRED**

Profile: `relaxed-career-v1`

Runtime: `runtime/loan-test-20260912-08`

## Goal

The profile reduces routine micromanagement and harsh negative spirals while
keeping football results, squad decisions and normal career progression relevant.
It consists of 54 guarded patch groups across 10 supported parameter files. The
same values are used on Easy, Medium and Hard where a difficulty block exists.

## Player management

- Morale below 100 receives a +10 modifier.
- Trust below 10 receives a +1 modifier.
- Declining aggressive transfer approaches causes no morale penalty.
- Unfulfilled contract-demand impact is reduced to 25 percent.
- Training schedules no longer apply their small automatic morale penalties.
- A psychologist can reduce unused-player morale loss by up to 50 percent.

## Transfers, sponsors and scouting

- Aggressive-offer frequency multiplier: 0.35.
- Initial sponsor-offer multiplier: 1.25.
- Sponsor-offer frequency multiplier: 1.5.
- Initial expectation multiplier: 0.9.
- Scouting mission duration multiplier: 0.35.
- Scout report capacity multiplier: 2.0.
- Swap scouting checks two clubs per week with a 65 percent hit probability.

## Board pressure

Negative board effects from league position, ordinary losses, heavy losses,
derbies, relegation places, cup exits and a missed Champions Cup final were
reduced to roughly 25–38 percent of their original values. Positive effects from
wins, large wins, derbies and exceeding objectives remain unchanged.

## Fitness, training and injuries

- Fitness achievable without match minutes: 75 → 85.
- Weekly gym gain: 0.08 → 0.12.
- Match and heavy-training fatigue reduced by about 25–35 percent.
- Rest weeks recover slightly more fatigue.
- First-match-after-injury risk multiplier: 7 → 3.
- General training-injury multiplier: 7.0 → 4.0.
- Human-team training multipliers: 0.50 → 0.75.
- Medical staff can reduce injury duration by up to 35 percent and training
  injury probability by up to 40 percent.
- Training-camp form-bonus loss probability: 50 → 30.

## Youth development

- The initial youth-talent distributions shift moderately toward three-, four-
  and five-star prospects.
- New youth-player chance: 1/19 → 1/14 per week.
- Youth-player quitting chance: 1/240 → 1/480 per week.
- Youth injury chance: 1/75 → 1/120 per week.
- Youth good-year bonus probability: 43 → 55.
- Global youth-talent multiplier: 0.65 → 0.72.
- International youth-camp arrival chance: 1/73 → 1/55 per day.
- Youth-coach skill gain, retention and tactical-development effects increased.
- Youth facilities contribute more strongly to cooperation evaluations.

## Staff and administration

- Masseur energy gain maximum: 20 → 35 percent.
- Construction-manager building-cost reduction maximum: 20 → 30 percent.
- Lawyer compensation reduction maximum: 20 → 35 percent.
- Spokesperson media-status chance maximum: 20 → 30 percent.
- Fan-representative active-fan gain maximum: 15 → 25 percent.

## Deployment and validation

- Final profile SHA-256:
  `014e824b05d5496a488c4436b9164b97172b7afaf47d0fa802ab347cea941b64`
- Applied mutation reports:
  `reports/local/relaxed-career-20260913-01.json` and
  `reports/local/relaxed-career-20260913-03.json`
- Hash-verified backups:
  `reports/local/relaxed-career-20260913-01-backup` and
  `reports/local/relaxed-career-20260913-03-backup`
- The earlier communication-only backup remains at
  `reports/local/player-communication-20260913-02-backup`.
- Exact final-profile reread: PASS.
- Fresh stock-parameter single-pass application: PASS (10/10 files).
- All changed-file backups hash-verified: PASS.
- Parameter block balance: PASS.
- Protected original installation unchanged: PASS.
- Executables modified: none.
- Save files modified: none.

The running game was left open to protect unsaved progress. Parameter files load
at startup. Existing low morale, trust and fitness values may need subsequent
daily or weekly game updates to recover after the next launch.
