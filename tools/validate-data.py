import argparse
import datetime as dt
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fm27.common import read_csv, write_csv, write_json
from fm27.validate import validate

parser = argparse.ArgumentParser(description="Validate identity projection; not a full native database gate")
parser.add_argument("--export", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("--snapshot", required=True)
args = parser.parse_args()
issues = validate(read_csv(args.export / "players.csv"), read_csv(args.export / "clubs.csv"),
                  dt.date.fromisoformat(args.snapshot))
write_csv(args.output / "IDENTITY_VALIDATION.csv", ["severity", "code", "identity", "message"], issues)
report = {"severity_counts": dict(Counter(r["severity"] for r in issues)),
          "code_counts": dict(Counter(r["code"] for r in issues)),
          "scope": "identity projection only; loans, competition graphs, graphics and native round-trip NOT validated",
          "release_eligible": False}
write_json(args.output / "IDENTITY_VALIDATION.json", report)
print(json.dumps(report))
sys.exit(1 if any(r["severity"] in {"ERROR", "FATAL"} for r in issues) else 0)
