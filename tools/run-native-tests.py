"""Run native fixture tests only with a binary tied to the current source tree."""
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
p.add_argument("--output", type=Path, required=True)
a = p.parse_args()
root = Path(__file__).resolve().parents[1]
build = json.loads(a.binary.with_suffix(a.binary.suffix + ".build.json").read_text(encoding="utf-8-sig"))
if build.get("status") != "PASS" or build["binary_sha256"] != sha256(a.binary):
    raise ValueError("Native binary build evidence mismatch")
if not build.get("source_sha256"):
    raise ValueError("Missing native build source hashes")
for name, digest in build["source_sha256"].items():
    path = (root / name).resolve()
    if not path.is_relative_to(root) or sha256(path) != digest:
        raise ValueError("Native binary was built from different source: " + name)
result = subprocess.run([str(a.binary.resolve()), "--self-test", str(a.output.resolve())], cwd=root)
if result.returncode:
    report = {"status":"FAIL", "tests":None, "exit_code":result.returncode, "binary":str(a.binary.resolve()),
              "binary_sha256":sha256(a.binary), "source_sha256":build["source_sha256"],
              "run_at":dt.datetime.now(dt.timezone.utc).isoformat()}
    if a.output.exists():
        write_json(a.output / "NATIVE_TESTS.json", report)
    write_json(root / "reports/local/NATIVE_TESTS.json", report)
    print(json.dumps({k:v for k,v in report.items() if k!="source_sha256"}))
    sys.exit(result.returncode)
report = json.loads((a.output / "NATIVE_TESTS.json").read_text(encoding="utf-8"))
report.update(binary=str(a.binary.resolve()), binary_sha256=sha256(a.binary),
              source_sha256=build["source_sha256"], run_at=dt.datetime.now(dt.timezone.utc).isoformat())
write_json(root / "reports/local/NATIVE_TESTS.json", report)
print(json.dumps({k: v for k, v in report.items() if k != "source_sha256"}))
