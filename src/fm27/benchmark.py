"""Compare repeated completed scenarios; refuse idle/failed/insufficient samples."""
import statistics

METRICS = ("wall_seconds", "cpu_seconds", "io_read_bytes", "io_write_bytes",
           "max_working_set", "max_private_bytes", "max_virtual_bytes")


def aggregate(runs: list[dict]) -> dict:
    if len(runs) < 3 or any(r.get("status") != "MANUAL_BOUNDARIES" for r in runs):
        raise ValueError("At least three successfully bounded scenario runs are required")
    for field in ("scenario", "workload_id", "executable_sha256", "graphics_profile"):
        if len({r.get(field) for r in runs}) != 1 or not runs[0].get(field):
            raise ValueError(f"Inconsistent/missing {field}")
    if runs[0]["workload_id"] == "unspecified" or runs[0]["scenario"] == "observation":
        raise ValueError("A defined, reproducible non-observation workload is required")
    return {"scenario": runs[0]["scenario"], "workload_id": runs[0]["workload_id"],
            "n": len(runs), "median": {key: statistics.median(r["summary"][key] for r in runs)
                                        for key in METRICS},
            "wall_range": [min(r["summary"]["wall_seconds"] for r in runs),
                           max(r["summary"]["wall_seconds"] for r in runs)]}


def compare(baseline: list[dict], optimized: list[dict]) -> dict:
    before, after = aggregate(baseline), aggregate(optimized)
    for field in ("scenario", "workload_id"):
        if before[field] != after[field]:
            raise ValueError("Baseline and optimized workloads must match")
    return {"baseline": before, "optimized": after,
            "percent_reduction": {key: (100 * (before["median"][key] - after["median"][key])
                                         / before["median"][key]) if before["median"][key] else None
                                  for key in METRICS},
            "caveat": "Manual-boundary latency; inspect ranges and reaction overhead before claiming improvement"}
