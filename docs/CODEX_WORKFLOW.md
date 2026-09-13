# FM27 Codex workflow

Purpose: maximize completed implementation per unit of Codex allowance and prevent long
sessions from becoming read/think/check loops.

## Milestone loop

1. Read PROJECT_STATE.md, the relevant report link, git status --short, and git diff --stat.
2. Define exactly one deliverable with an acceptance check.
3. Read only the files needed for that deliverable. Prefer symbols, ranges, and local summaries.
4. Implement one coherent batch rather than a sequence of tiny edits.
5. Run the narrowest targeted test or validator.
6. Fix failures from summarized output; do not paste entire logs into context.
7. Run the milestone gate test/build once.
8. Inspect git diff --stat and git diff --check.
9. Commit the milestone.
10. Update PROJECT_STATE.md with the result, test command, blockers, and next task.

Flow:

STATE -> ONE DELIVERABLE -> RELEVANT READS -> COHERENT WRITE -> TARGETED TEST -> FIX -> GATE -> COMMIT -> STATE

## Context budget rules

- Treat repeated 140k–150k actual input-token requests as a warning signal.
- Keep output from scans, CSVs, builds, tests, and diffs summarized locally.
- Never reread a large file without stating why the previous read is insufficient.
- After compaction, reload state and the active file set; do not reconstruct the whole repository.
- Start a new thread at a milestone boundary if the task has no writes for 30 minutes while activity continues.
- Use Medium for focused, low-uncertainty edits; use High for a difficult batch with a clear acceptance gate.
- Use xHigh only for a genuinely hard, bounded investigation or design decision, then switch to implementation.

## Parallelism

Spawn a child only for a disjoint, named deliverable. Require a compact result containing:
changed files, evidence, tests, blockers, and next action. Do not parallelize repository
orientation or duplicate validation.

## Evidence discipline

- rg --files and git diff --stat first.
- Full-file reads only when a targeted read cannot answer the question.
- Build output: return errors and a short count/summary.
- Test output: return failing tests and a pass/fail summary.
- Large data: aggregate with scripts and return rows relevant to the deliverable.
- Record durable decisions in PROJECT_STATE.md, not in repeated chat summaries.
