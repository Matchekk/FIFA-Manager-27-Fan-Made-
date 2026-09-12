"""Compare complete canonical serialized player records after native reread."""
import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fm27.common import sha256, write_json

p = argparse.ArgumentParser()
p.add_argument("--expected", type=Path, required=True)
p.add_argument("--actual", type=Path, required=True)
p.add_argument("--output", type=Path, required=True)
a = p.parse_args()
def records(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return Counter((r["fifa_id"], r["dob"], r["name"], r["club_id"], r["serialized_sha256"])
                       for r in csv.DictReader(stream))
expected, actual = records(a.expected), records(a.actual)
passed = bool(expected) and expected == actual
report = {"status": "PASS" if passed else "FAIL", "expected_players": expected.total(), "actual_players": actual.total(),
          "unexpected_missing": (expected - actual).total(), "unexpected_added": (actual - expected).total(),
          "examples_expected": list((expected - actual).items())[:10], "examples_actual": list((actual - expected).items())[:10],
          "expected_sha256": sha256(a.expected), "actual_sha256": sha256(a.actual),
          "scope": "All canonical 2013.12 serialized player fields, normalized club references, native reread; includes full contracts, histories, biases, attributes, nationality and starting conditions",
          "limitations": "Canonical serialization can normalize internal values. Does not validate staff, competition structures, engine behavior or saves; not a full production gate.",
          "production_ready": False}
write_json(a.output, report)
print(json.dumps(report))
sys.exit(not passed)
