# 3D match-engine tactics: code evidence

Status: **PASS — EVIDENCE BOUNDARY PROVEN**

## Result

The active FIFA Manager 13 build does **not** contain a universal tactical score or
a code table that ranks one formation and instruction set above every other one.
Therefore no specific “best tactic” can honestly be proved from static code alone.
This is a direct result of the engine structure, not a lack of tactical guessing.

The available parser source proves the exact tactical prefix written to the match
engine:

```text
teamid, offsidetrap, withoutball, formationid, attack, teammentality,
attacktactic1, attacktactic2, defensetactic1, defensetactic2
```

`GfxCore.dll` contains the corresponding tactics and formation code markers and
directly references 25 of the 27 selected option-scoring keys below. The two marked
values exist in the active archive but have no literal binary reference, so they are
retained as config evidence rather than direct code evidence. The engine weighs each
possible action from the current situation. Examples from `tcmai.ini` are:

| Decision input | Active value/range |
|---|---:|
| Base action value | 100,000 |
| Maximum action value | 1,000,000 (config only) |
| Forward-progress factor | 2 / 6 / 12 |
| Safety factor | 60 / 70 / 80 |
| Pass-forward value | 50 / 100 / 150 |
| Safe receiver value | 275 |
| Through-pass forward value | 40 |
| Lob-pass safety value | 75,000 |
| Goal-angle bonus | 70 (config only) |
| Close / far shooting distance | 10 / 23.8 yards |
| Shooting-from-distance bias | 77.5 |
| Dribble direction / safety value | 10,000 / 165 |
| Dribble speed penalty | 0.3 |

These factors depend on the players, opponents, ball position, available receiver,
angle and distance. They create tradeoffs rather than a total order. For example,
more forward play can increase territorial value while reducing the safety of the
available action. Changing the opponent positions changes which action wins the
comparison. Formation, mentality and the two attacking and defensive tactics
therefore cannot be ranked independently of the match state.

## Formation and benchmark evidence

The active `Formations.xml` declares 68 formations and serializes 81 unique formation
nodes, including normal IDs 1–74 and seven short-handed formations 101–107. It stores
team instructions and individual player instructions, but contains no performance
weight or win-probability field.

The engine includes a historical FIFAMARK batch path, but active `sku.ini` explicitly
says its settings need to be fixed for the new AI. `FIFAMARK_MODE`, loop count and
script are all commented out. It is not a valid automated proof harness in this
build.

## What the code does prove

- Long-distance shooting is explicitly treated differently from close shooting.
- Forward progress, action safety and receiver safety are separate scoring inputs.
- Through balls, lob passes and ordinary passes have different bonuses.
- Dribbling has both a large direction term and a movement-speed penalty.
- Offside is enabled, so forward positioning has a real counterconstraint.
- The match engine receives several distinct tactical fields; it does not receive a
  precomputed “tactic quality” number.

Those facts can reject invented claims such as “formation X has the highest internal
score.” They do not prove that one complete tactic wins the most matches.

## Required proof of a best tactic

A defensible best-tactic claim requires a controlled 3D match harness: fixed teams,
attributes, fitness, morale, injuries and venue; many random seeds per variant; one
declared outcome metric; holdout opponents; and confidence intervals. The bundled
benchmark cannot currently supply that evidence. Building or instrumenting such a
harness is a separate match-engine experiment.

No game, database, parameter or save file was changed by this audit.

Machine-readable evidence:
`reports/current/3d-match-engine-tactics-code-evidence.json`.

Reproduction tool:
`tools/inspect-3d-match-engine-tactics.py`.
