# Resolved review handoff

`FM27_RESOLVED_REVIEW_QUEUE.csv` preserves all624 original review rows and adds
stable `row_id`, `decision`, `resolution_status`, `resolution_basis` and
`resolved_state_json` fields. The associated manifest records hashes and the
currently resolved decisions. No football research was performed to create it.

-6 APPLY rows reference the existing exact protected-condition delta.
-136 NONBLOCKING rows preserve the canonical queue's existing nonblocking status.
-482 rows await external resolution; their decision is intentionally empty.

External resolution must retain `row_id`, specify one of APPLY, KEEP_EXISTING,
CREATE, NONBLOCKING or ESCALATE_TECHNICAL, and record its basis. APPLY requires the
exact native squad-plan fields in `resolved_state_json`; CREATE requires the native
creation-plan fields. Never invent EA/FIFA IDs. The importer must verify concrete
identity/reference/condition invariants and report technical conflicts exactly.

The manifest and its hashes must accompany the final resolved revision. Its current
status is PARTIALLY_RESOLVED_NOT_A_PRODUCTION_FREEZE. Empty decisions remain pending;
they are neither KEEP_EXISTING nor NONBLOCKING. Native IDs refer to Native08 and
require the existing identity bridge for a different candidate/read.

Generation: `.venv\Scripts\python.exe tools/prepare-resolved-review-queue.py`.
The generator is deterministic and refuses to overwrite externally edited files.
These decisions have not yet been applied to Draft05 or a new native candidate.
