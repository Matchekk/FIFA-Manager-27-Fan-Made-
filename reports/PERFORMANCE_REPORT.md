# Performance status

No performance improvement is claimed. The running game was successfully attached.
No comparable baseline/optimized scenario measurements exist.
LAA is already enabled; changing it cannot supply additional headroom here.

Implemented: process CPU/wall time, working/peak set, private and virtual bytes,
read/write bytes and operations; manual scenario boundaries; repeated-run
median comparison rejecting observations, incomplete runs and mixed workloads.
Sampler smoke-tested against a synthetic native process, separate from game
measurements. No simulation features, graphics or assets have been disabled.

Actual observation: 30.1827s wall, 1.8594s CPU, 114 samples; observed maximum
working set 324,870,144 bytes, private 649,363,456, virtual 1,064,558,592.
Uncontrolled workload, no scenario timing and no improvement inference.

Next requirement: known selected DB and a
repeatable test-career workload. Then measure 1/7/30 days, window deadline,
season boundary, load/save and player/staff/transfer lists before choosing a fix.
