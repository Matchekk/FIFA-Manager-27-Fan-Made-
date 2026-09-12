# FM27 Project State

Updated: 2026-09-12 UTC

## Current Goal

Continue FM27 Community Overhaul in bounded, milestone-sized deliverables.

## Completed Milestones

The existing project checkpoint is native06. The repository documents 2,880 club
changes, 794 loans, 296 expired returns, 289 Python tests, and 123 native tests.
These are project-reported checkpoint figures; release, game/editor, career/save,
season, and performance gates remain open.

## Architecture

Data pipeline and native/runtime tooling are under src/, tools/, data/, build/, and reports/.

## Important Paths

src/; tools/; data/; tests/; reports/; docs/; build/; dist/

## Active Blockers

No blocker inferred from usage logs; validate repository state before implementation.

## Next Tasks

Choose one deliverable, define its acceptance test, implement, gate, commit, and update this file.

## Test Commands

Use the narrowest existing project validator/test command first; full suites only at milestone gates.

## Known Traps

Do not modify the FIFA installation. Do not expose giant logs. Avoid full repository rereads.
Preserve native identity and serialization constraints.

## Key Decisions

Prefer compact state plus linked reports. Usage-forensics evidence is under
reports/usage-forensics/FINAL_REPORT.md.

Keep this file under 5,000 words. Link to detailed reports instead of copying them.
