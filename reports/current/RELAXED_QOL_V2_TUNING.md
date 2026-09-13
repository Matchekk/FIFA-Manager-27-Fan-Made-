# Relaxed QoL v2 parameter profile

Status: **APPLIED - RESTART REQUIRED**

Profile: `relaxed-qol-v2`

Runtime: `runtime/loan-test-20260912-08`

## Goal and scope

This profile extends `relaxed-career-v1` and `dynamic-development-v1` with the
remaining low-maintenance career settings. It contains 65 guarded patch groups
in 14 ordinary parameter files plus deterministic construction-table scaling in
2 files. No executable, database or save-game bytes are changed.

## Youth retention

- Youth-roster size before transfer pressure: 30 -> 40.
- Minimum talent for youth-transfer interest: 3 -> 4.
- Required talent and team-level improvements were raised.
- Maximum youth-transfer probability: 35 -> 18.
- National poaching basis: 20 -> 10.
- Transfer checks occur after 40 plus up to 20 days instead of 25 plus 10.
- General transfer-check probability: 90 -> 55.
- Youth players take 10 plus up to 7 days to decide instead of 5 plus 3.
- League/national/continental/intercontinental reach probabilities were reduced
  from 60/80/90/100 to 45/65/80/95.

## Player contracts and transfers

- Contract-extension point gate: 10/10 -> 6/6.
- Initial incoming transfer-offer range: 35-46 -> 40-51.
- Easy-mode fair-salary multiplier: 0.95 -> 0.85.
- Automatic player salary increase: 3 -> 2.
- Basic-salary counteroffer range: 10-21 -> 5-11.
- Goal-bonus counteroffer probability: 60 -> 35, with smaller increases.
- Transfer-offer point gate: 11 -> 8; salary and transfer budget tolerance rose.
- General extension bonus: 75 -> 100.
- Foreign-language and long-injury extension penalties were reduced.
- Transfer evaluation difficulty bonus: 50/0/-25 -> 60/25/0.
- Human-club transfer-interest multiplier: 1.10 -> 1.20.

## Injuries and recovery

- Match injury chances and gradual match-injury chances are 30 percent lower.
- Escalation from a pre-injury state: 60000 -> 35000.
- Physical fitness returns faster throughout the healing period.
- Injury-retirement evaluation starts at age 34 instead of 28.
- Injury lengths considered for retirement/severity: 100/60 -> 180/120 days.
- Medical staff can reduce injury duration by up to 50 percent and training
  injury probability by up to 55 percent.
- Masseur energy benefit: up to 45 percent.

Goal, attack and card probabilities were not changed. Calendar simulation gets
easier through morale, fatigue, injury and recovery behavior without adding a
hidden match-result advantage.

## Finances and facilities

- Facility maintenance: 25 -> 15 percent of construction costs.
- Investments stop at 96 percent budget use instead of 90 percent.
- Allowed budget overrun: 5 -> 12.
- Debt warnings move from 50/80/95 to 70/90/98 percent.
- Negative-cash budget penalty: 0.10 -> 0.05.
- Facility budget share: 1 -> 4 percent; maximum building share: 20 -> 30.
- All 697 positive club-facility costs are scaled to 75 percent.
- All 684 positive club-facility construction times are scaled to 70 percent.
- All 62 positive stadium-construction prices are scaled to 70 percent.
- Construction-manager maximum saving: 30 -> 40 percent.

## Sponsors and fans

- Safe sponsor base reduction: 7 -> 3.
- Risky sponsor base reduction: 40 -> 25.
- Sponsor-negotiation skill multiplier: 3 -> 4.
- Main sponsor term: 2-3 -> 3-4 years.
- Win fan multiplier: 1.02 -> 1.03; loss multiplier: 0.98 -> 0.995.
- Missed-objective and relegation-zone fan losses were reduced.
- Lower-division active-fan multipliers were raised moderately.
- Spokesperson and fan-representative maximum benefits rose to 40 and 35 percent.

## Manager career, staff and private life

- First manager offer is within 5 percent of the demand instead of 10 percent.
- Starting manager-negotiation points: 15 -> 25.
- Negotiation point costs and random point loss were reduced.
- Season-objective change chance: 30 -> 15 percent.
- More clubs can show interest in the human manager.
- Relationship decline chance: 1/20 -> 1/60, with at least 12 weeks between
  declines and only 3 weeks required between improvements.
- Youth-coach retention, training and tactical benefits rose again.
- Psychologist unused-player morale protection: up to 70 percent.
- Lawyer compensation saving: up to 50 percent.
- Internal discipline points for routine manager/training incidents were reduced;
  serious physical misconduct remains unchanged.

## Validation

- Final profile SHA-256:
  `9f5aaa39f29e3ed4194e47d6ccc82bd22f81d9a047accef4edaf9ae20c7a7f3c`
- Aggregate application: PASS, 16 changed parameter files.
- Exact patch groups: 65/65 applied.
- Structured construction values: 1,443/1,443 changed.
- Final reread/idempotence: PASS, 0 files changed.
- Club-facility structure: 768 BEGIN / 768 END blocks; 734 level, cost and
  construction-time records retained.
- Python regression suite: PASS, 305/305.
- Backup hashes: PASS.
- Protected original installation: unchanged.
- Running isolated game process: responsive and left open.

Local evidence and reversible backups:

- `reports/local/RELAXED_QOL_V2_APPLY_20260913_01.json`
- `reports/local/RELAXED_QOL_V2_APPLY_20260913_02.json`
- `reports/local/RELAXED_QOL_V2_IDEMPOTENCE_20260913_04.json`
- `reports/local/relaxed-qol-v2-backup-20260913-01`
- `reports/local/relaxed-qol-v2-backup-20260913-02`

The parameter files load when the game starts. The active game was not closed so
that unsaved user progress remains safe; the new profile becomes effective after
the next normal restart.
