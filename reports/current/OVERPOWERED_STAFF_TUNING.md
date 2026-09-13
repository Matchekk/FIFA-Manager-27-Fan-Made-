# Overpowered staff parameter profile

Status: **APPLIED - RESTART REQUIRED**

Profile: `overpowered-staff-v1`

Runtime: `runtime/loan-test-20260912-08`

## Effects

The profile is applied after the relaxed career, dynamic development and relaxed
QoL profiles. Existing staff receive much stronger task effects after the next
game restart. Newly generated staff also start at a much higher quality level.

- Youth coaches can provide up to 100 percent additional skill development,
  prevent up to 100 percent of youth quitting and provide maximum tactical help.
- Medical staff can reduce injury duration by up to 85 percent and training
  injury risk by up to 90 percent.
- Masseurs can provide up to 90 percent energy gain.
- Psychologists can prevent up to 100 percent of unused-player morale loss.
- Construction managers can reduce building costs by up to 75 percent.
- Lawyers can remove up to 100 percent of staff-dismissal compensation.
- Spokesperson media-status chance rises to 80 percent.
- Fan-representative active-fan gain rises to 75 percent.
- General training staff become beneficial from a much lower skill threshold;
  their training multiplier rises from 1.01 to 1.10.
- Staff fitness-bonus probability rises from 0.33 to 0.80.
- Team and individual tactics effects rise from 0.30 to 0.80.
- Staff protection against negative player characteristics starts at skill 30
  instead of 70; motivation effect rises from 0.10 to 0.50.
- Daily staff motivation loss falls from 3.0 to 0.25 and motivation recovery
  rises from 0.07 to 0.50.
- Staff skill growth rises from 0.004 to 0.05 per day.

## Generated staff

- Rookie average rating: 10 -> 70.
- Rookie average talent: 5 -> 8 of 9.
- Average characteristics: 50 -> 85.
- Lower deviation produces more consistently strong staff.
- Non-job skill allocation is reduced so generated staff focus on useful skills.
- Prestige quality bonus: 10 -> 25.

These generation values affect future staff creation and are most visible over
time or in a new career. Task and training effects also apply to existing staff.

## Validation

- Profile SHA-256:
  `de95906338c2e893ca580bea63acac2f145289fcd52f1ac26c826151c9ba3265`
- Guarded application: PASS, 19/19 patches across 4 files.
- Exact reread/idempotence: PASS, 0 files changed.
- Python regression suite: PASS, 305/305.
- Backup hashes: PASS.
- Protected original installation: unchanged.
- Executable, database and save files changed: none.
- Running isolated game process: responsive and left open.

Local evidence and reversible backup:

- `reports/local/OVERPOWERED_STAFF_V1_APPLY_20260913_01.json`
- `reports/local/OVERPOWERED_STAFF_V1_IDEMPOTENCE_20260913_01.json`
- `reports/local/overpowered-staff-v1-backup-20260913-01`

The profile becomes active after the next normal game restart.
