"""Build an isolated candidate with frozen plan, executable and native-test provenance."""
import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fm27.common import sha256, write_json

p = argparse.ArgumentParser()
p.add_argument("--binary", type=Path, required=True)
p.add_argument("--database", type=Path, required=True)
p.add_argument("--plan", type=Path, required=True)
p.add_argument("--candidate", type=Path, required=True)
p.add_argument("--report", type=Path, required=True)
p.add_argument("--inspect-only", action="store_true", help="Export before/after plan semantics in memory without writing a database")
a = p.parse_args()
root = Path(__file__).resolve().parents[1]
binary, plan, candidate = a.binary.resolve(), a.plan.resolve(), a.candidate.resolve()
database = a.database.resolve()
if candidate.exists() or a.report.exists():
    raise ValueError("Candidate and provenance report must be new")
build = json.loads(binary.with_suffix(binary.suffix + ".build.json").read_text(encoding="utf-8-sig"))
tests_path = root / "reports/local/NATIVE_TESTS.json"
tests = json.loads(tests_path.read_text(encoding="utf-8"))
digest = sha256(binary)
if build["status"] != "PASS" or build["binary_sha256"] != digest or tests["status"] != "PASS" or tests["binary_sha256"] != digest:
    raise ValueError("Executable lacks matching successful build and native tests")
if not build["source_sha256"] or build["source_sha256"] != tests["source_sha256"]:
    raise ValueError("Build/test source evidence differs")
for name, expected in build["source_sha256"].items():
    source = (root / name).resolve()
    if not source.is_relative_to(root) or sha256(source) != expected:
        raise ValueError("Stale build evidence: " + name)
manifest_path = plan.with_suffix(".manifest.json")
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
plan_hash = sha256(plan)
if manifest["plan_sha256"] != plan_hash or manifest["status"] != "FROZEN_STAGING_NOT_RELEASE":
    raise ValueError("Plan is not a verified frozen staging input")
report = {"status": "RUNNING", "mode": "INSPECT_PLAN" if a.inspect_only else "STAGE_PLAN", "started_at": dt.datetime.now(dt.timezone.utc).isoformat(),
          "binary": str(binary), "binary_sha256": digest, "source_database": str(database),
          "candidate": str(candidate), "plan": str(plan), "plan_sha256": plan_hash,
          "frozen_plan_manifest": manifest, "build": build, "native_tests": tests,
          "native_test_report_sha256": sha256(tests_path), "release_ready": False}
write_json(a.report, report)
result = subprocess.run([str(binary), str(database), str(candidate), "--inspect-plan" if a.inspect_only else "--stage-plan", str(plan)], cwd=root)
intact = sha256(binary) == digest and sha256(plan) == plan_hash
marker = candidate / ("NATIVE_WORLD_SEMANTICS.json" if a.inspect_only else "STAGING_ONLY.txt")
completed = result.returncode == 0 and intact and marker.is_file()
if a.inspect_only:
    completed = completed and (candidate / "before-plan" / "NATIVE_WORLD_SEMANTICS.json").is_file() and not (candidate / "database").exists()
success_status = "READ_ONLY_PLAN_INSPECTION_COMPLETED" if a.inspect_only else "STAGING_WRITE_COMPLETED_NOT_VALIDATED"
report.update(status=success_status if completed else "FAIL",
              exit_code=result.returncode, immutable_inputs_unchanged=intact,
              finished_at=dt.datetime.now(dt.timezone.utc).isoformat())
write_json(a.report, report)
if candidate.exists():
    write_json(candidate / "NATIVE_BUILD_INPUTS.json", report)
print(json.dumps({k: report[k] for k in ("status", "candidate", "plan_sha256", "binary_sha256", "release_ready")}))
sys.exit(0 if completed else result.returncode or 1)
