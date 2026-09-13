# 3D match-engine attribute influence

Status: **DIRECT ENGINE EVIDENCE PASS**

Scope: FIFA Manager 13 3D match engine (`GfxCore.dll`) only. Displayed player
strength, position weighting and text-mode event selection are deliberately excluded.

## Main finding

The 3D engine does not use one global attribute-weight table. Attributes enter
different movement, action and duel formulas, so an exact universal ranking cannot
be read from one matrix. A cross-attribute ranking comparable to an FM Arena test
requires controlled repeated matches with one attribute changed at a time.

Pace nevertheless has unusually broad direct influence. The active engine tuning
maps poor-to-excellent sprint speed from 6.0 to 11.0 engine units. This is an 83.3%
endpoint increase before repeated positional consequences such as reaching passes,
creating separation and recovering defensively. `GfxCore.dll` also contains the raw
`ACCELERATION` field and acceleration-specific match code, but its response curve is
hard-coded and is not exposed as a single editable scalar.

## Exact direct values

The active attribute tiers are 20 (average), 50 (good) and 80 (excellent). The
action-quality values used at poor / average / good / excellent tiers are:

| Match action | Poor | Average | Good | Excellent |
|---|---:|---:|---:|---:|
| Direct shot | 30 | 55 | 88 | 99 |
| Long shot | 49 | 69 | 85 | 99 |
| Passing | 45 | 69 | 86 | 99 |
| Long passing | 55 | 79 | 90 | 99 |
| Dribbling | 45 | 69 | 87 | 99 |
| Crossing | 45 | 68 | 84 | 99 |
| Tackling | 45 | 63 | 79 | 99 |
| Marking | 45 | 63 | 79 | 99 |

These are action-specific response curves, not shares of a global overall score.
The engine binary directly references every key in this table.

For aerial challenges, the shares are explicit and sum to 1.0:

| Input | Weight |
|---|---:|
| Jumping | 55% |
| Strength | 25% |
| Player height | 15% |
| Being in front | 5% |

The dribbling run-speed endpoints are both configured at 95%. This means technique
does not change the percentage of base running speed while dribbling in this build;
dribbling still changes the separate dribble action-quality curve. Pace therefore
continues to determine much of the actual movement speed with and without the ball.

Tackling and dribbling interact through separate tiered miss-chance and opponent
modifiers. Consistency may reduce effective skills globally by up to 30%, with a
configured impact factor of 90. CPU attribute effects are enabled.

## Evidence boundary

`config.big` contains the active `tcmai.ini`, `ai.ini` and `career.ini` tuning.
`GfxCore.dll` contains the 3D match-engine routines, raw attribute names and direct
references to the sprint, dribble-speed, heading and action-quality keys extracted
here. The original files were only read and hashed.

The current evidence supports these conclusions:

- Pace is definitely a high-impact 3D attribute because it directly changes movement
  speed across nearly every phase of play.
- Acceleration is definitely consumed by the 3D engine, but its exact curve still
  requires disassembly or a controlled isolated-match experiment.
- Jumping dominates the configured aerial-duel calculation; strength is second.
- Shooting, passing, dribbling, crossing, tackling and marking have strong but
  event-specific nonlinear curves.
- A precise ordered list for all attributes cannot be claimed from configuration
  values alone. Event frequency must be measured as well as per-event effect.

No match-engine parameter was changed during this inspection.

Machine-readable evidence:
`reports/current/3d-match-engine-attribute-influence.json`.

Reproduction tool:
`tools/inspect-3d-match-engine-attributes.py`.
