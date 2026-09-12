# Non-3D benchmark protocol

Do not compare the offline reader's time to game startup or claim it speeds up
the game. Installed source data may differ from the game's selected database.

For each scenario use the same game/patch hashes, selected database, leagues,
start save, simulation options, game date, RNG/reload procedure where possible,
power plan, AC/battery state, graphics profile and background applications.
Record these in a stable WorkloadId plus a companion workload description.
Record cold/warm filesystem-cache state separately. Finish builds/downloads
before timing. Run at least 3, preferably 5, trials per scenario; report median
and spread. Do not disable simulation systems to improve the numbers.

Scenarios: startup -> main menu; new career; load/save; 1/7/30 days; transfer
deadline; June 30 -> July 1; player search/open/query; transfer/staff lists.
Observe 2027, 2028, 2029, 2030+ and careers lasting 1/3/5/10 years.

`tools/Launch-Benchmark.ps1` attaches to an existing exact-path game process or
launches normally and follows the resolution-selector startup flow. Process
creation time is explicitly not menu readiness. No ownership checks are changed.
`tools/Measure-Run.ps1` attaches only to Manager.exe under the requested root:

```powershell
pwsh -File tools/Measure-Run.ps1 -ProcessId 1234 -GameRoot 'C:\path\to\game' -Output benchmarks/runs/week-01.json -Scenario week -WorkloadId 'week-fixed-save-v1' -UntilEnter -Seconds 300
```

Press Enter before the action and after completion. Manual timings include
reaction, window-switching and 250ms sampling error. Fixed-duration samples
without UntilEnter are OBSERVATION_ONLY and are rejected by the comparison
module. Failed and timed-out runs are likewise rejected. Memory/watchdog
observations are useful even when no latency claim can be made.

Counters: CPU seconds, wall time, working/peak set, private bytes, virtual
bytes, process read/write bytes and operations. Process IO is not equivalent
to physical disk traffic. The 3GB virtual-memory warning does not prove an
allocation will fail. Driver-reported AdapterRAM is not total available VRAM
on integrated graphics. No 3D/FPS measurements are part of this protocol.

Native window discovery works, but screenshot capture fails on this Windows 10
host (`SetIsBorderRequired`, E_NOINTERFACE) and accessibility exposes only the
root pane. Main-menu readiness and in-game scenario boundaries cannot currently
be observed safely by automation. Use operator boundaries or a verified
instrumentation point. Never fill missing measurements with estimates.
