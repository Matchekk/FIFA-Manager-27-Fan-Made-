"""Record actual native player changes and refuse any identity outside the frozen plan."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fm27.common import read_csv, write_csv, write_json, sha256

p = argparse.ArgumentParser()
p.add_argument("--before", type=Path, required=True)
p.add_argument("--expected", type=Path, required=True)
p.add_argument("--plan", type=Path, required=True)
p.add_argument("--output", type=Path, required=True)
a = p.parse_args()
before = read_csv(a.before)
expected = read_csv(a.expected)
plan = read_csv(a.plan)
def index(rows):
    result = {r["fm_id"]: r for r in rows}
    if len(result) != len(rows):
        raise ValueError("Repeated native identity")
    return result
old, new, planned = index(before), index(expected), index(plan)
if old.keys() != new.keys():
    raise ValueError("Unexpected creation/deletion before native write")
changes, violations = [], []
for ident, row in old.items():
    other = new[ident]
    if row == other:
        continue
    c = planned.get(ident)
    if not c or any(row[k] != other[k] for k in ("fifa_id", "dob", "name")) or row["club_id"] != c["old_club_id"] or other["club_id"] != c["new_club_id"]:
        violations.append(ident)
    changes.append({"fm_id": ident, "fifa_id": row["fifa_id"], "name": row["name"], "dob": row["dob"],
                    "old_club_id": row["club_id"], "new_club_id": other["club_id"],
                    "old_serialized_sha256": row["serialized_sha256"], "new_serialized_sha256": other["serialized_sha256"],
                    "planned": bool(c), "loan_owner_club_id": (c or {}).get("loan_owner_club_id", "0"),
                    "source": (c or {}).get("source", ""), "source_sha256": (c or {}).get("source_sha256", ""),
                    "snapshot_date": (c or {}).get("snapshot_date", "")})
fields = ["fm_id", "fifa_id", "name", "dob", "old_club_id", "new_club_id", "old_serialized_sha256", "new_serialized_sha256",
          "planned", "loan_owner_club_id", "source", "source_sha256", "snapshot_date"]
write_csv(a.output, fields, changes)
report = {"status": "PASS" if not violations else "FAIL", "actual_changed_players": len(changes),
          "planned_players": len(plan), "actual_club_changes": sum(r["old_club_id"] != r["new_club_id"] for r in changes),
          "unexpected_identity_changes": violations, "before_sha256": sha256(a.before), "expected_sha256": sha256(a.expected),
          "plan_sha256": sha256(a.plan), "production_ready": False,
          "limitations": "Player mutation scope only. Requires projected field comparison and native semantic reread; staff, competitions and engine gates are separate."}
write_json(a.output.with_suffix(".json"), report)
print(json.dumps(report))
sys.exit(bool(violations))
