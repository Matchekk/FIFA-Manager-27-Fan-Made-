# FM27 — IMPLEMENTATION-ONLY DATA QUEUE PASS

This is a bounded engineering task.

## ABSOLUTE RULE

DO NOT PERFORM FOOTBALL WEB RESEARCH.

The football research/review pass has been completed outside Codex.

Use these two files as the external football-state handoff:

- `FM27_RESOLVED_REVIEW_QUEUE.external-pass1.csv`
- `FM27_EXTERNAL_FOOTBALL_RESOLUTIONS.csv`

The companion file contains the exact `technical_action`, resolved football fact, loan owner/end where applicable, evidence URL, confidence and compact engineering instruction.

All 624 rows now have a decision. There are ZERO rows awaiting external football resolution.

## Decision semantics

### APPLY
Existing exact guarded delta. Apply through the existing importer/pipeline.

### KEEP_EXISTING
No football-state change. Remove it from sprint-blocking coverage. Do not invent joined/contract/shirt data.

### NONBLOCKING
No release-blocking football correction required. Preserve valid native state.

### ESCALATE_TECHNICAL
IMPORTANT: this does NOT mean “research it”.

It means the FOOTBALL FACT IS ALREADY RESOLVED and only LOCAL TECHNICAL WORK remains.

Read `technical_action` from the companion and implement it using existing native FIFAM structures.

Expected technical actions include:

- `MOVE_TO_TARGET_PRESERVE_METADATA`
- `SET_CURRENT_LOAN`
- `SET_CURRENT_LOAN_PRESERVE_TYPED_CONDITION`
- `CLEAR_STALE_LOAN_KEEP_TARGET`
- `CREATE_OR_BRIDGE_IDENTITY`
- `APPLY_CONFIRMED_TIMELINE_WITH_GUARD_REPAIR`
- `MOVE_TO_EXTERNAL_IF_CLUB_EXISTS_ELSE_FREE_AGENT`

## Player creation / identity

For `CREATE_OR_BRIDGE_IDENTITY`:

1. search the LOCAL native identity index,
2. bridge to an existing identity if safe,
3. otherwise use the existing guarded creation pipeline,
4. NEVER invent an EA/FIFA ID.

No public football research.

## Loans

Use the supplied owner/destination/end from the companion.

Use the previously validated current-loan runtime start projection:

`2026-07-01`

Do not reopen the Native08 loan root-cause investigation.

## Unknown chronology/contract/shirt fields

Preserve existing native values unless the resolved handoff supplies a concrete value.

Do not invent metadata to make a row look complete.

## Required execution

1. Validate the two handoff file hashes/row IDs.
2. Import decisions.
3. Implement generic handlers for the listed `technical_action` values rather than hand-patching individual rows.
4. Apply deterministic deltas.
5. Recompute the review queue and club coverage.
6. Report only LOCAL TECHNICAL conflicts.
7. Resolve those conflicts through code/native data inspection — NOT web research.
8. Once the technical queue is clear enough, freeze the football-data plan.
9. Native write.
10. Native reread.
11. Semantic diff/regression validation.
12. Build the completed-data candidate.
13. Run the single completed-data new-career smoke required by the existing project plan.
14. Update `PROJECT_STATE.md`.
15. END THE THREAD.

## Usage rule

Do not reread broad project documentation.

Use PROJECT_STATE plus only the active importer/native-plan files.

Do not dump the 624-row CSV into model context. Parse it locally and work from aggregates/exceptions.

The objective is:

# PROGRAM, INTEGRATE, VALIDATE.

Not research.
