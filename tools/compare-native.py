"""Compare an independent projection with the canonical native reader."""
import argparse
import datetime as dt
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fm27.common import read_csv, write_json

parser = argparse.ArgumentParser()
parser.add_argument("--projection", type=Path, required=True)
parser.add_argument("--native", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
projected = read_csv(args.projection)
native = read_csv(args.native)
for person in native:
    person["dob"] = dt.datetime.strptime(person["dob"], "%d.%m.%Y").date().isoformat()
by_id = {p["fm_id"]: p for p in native}
if len(by_id) != len(native):
    raise ValueError("Native reader emitted duplicate IDs")
fields = ["fifa_id", "club_id", "dob"]
mismatches = []
for p in projected:
    if not p["fm_id"]:
        continue
    counterpart = by_id.get(p["fm_id"])
    if counterpart is None or any(p[f] != counterpart[f] for f in fields):
        mismatches.append(p["fm_id"])
projected_identity = Counter(tuple(p[f] for f in fields) for p in projected)
native_identity = Counter(tuple(p[f] for f in fields) for p in native)
report = {"projected_players": len(projected), "native_players": len(native),
          "persisted_id_comparisons": sum(bool(p["fm_id"]) for p in projected),
          "persisted_id_mismatches": mismatches,
          "all_player_identity_multisets_equal": projected_identity == native_identity,
          "fields_compared": fields,
          "limitations": "Free agents compare as an identity multiset; no persisted FM IDs. Attributes/contracts/native write semantics not covered."}
write_json(args.output, report)
print(json.dumps(report))
sys.exit(bool(mismatches) or projected_identity != native_identity)
