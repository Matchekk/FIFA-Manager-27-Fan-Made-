"""Merge disjoint guarded plans and freeze their provenance for one native build."""
import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fm27.common import read_csv, write_csv, write_json, sha256
from fm27.purchase_loans import ACQUISITION_DEFAULTS

p = argparse.ArgumentParser()
p.add_argument("--plans", nargs="+", type=Path, required=True)
p.add_argument("--output", type=Path, required=True)
a = p.parse_args()
if a.output.exists():
    raise ValueError("Frozen output must not already exist")
rows, seen, snapshots = [], set(), set()
for path in a.plans:
    for row in read_csv(path):
        if row["fm_id"] in seen:
            raise ValueError("Overlapping plans require a reviewed identity/chronology resolution")
        if row["status"] != "CONFIRMED":
            raise ValueError("Unconfirmed plan row")
        seen.add(row["fm_id"])
        snapshots.add(row["snapshot_date"])
        rows.append({**row, "loan_owner_club_id": row.get("loan_owner_club_id", "0"), "loan_end": row.get("loan_end", ""),
                     "action": row.get("action", "SQUAD"),
                     "previous_loan_owner_club_id": row.get("previous_loan_owner_club_id", "0"),
                     "previous_loan_start": row.get("previous_loan_start", ""),
                     "previous_loan_end": row.get("previous_loan_end", ""),
                     "previous_loan_buy_option": row.get("previous_loan_buy_option", "0"),
                     **{k: row.get(k, v) for k, v in ACQUISITION_DEFAULTS.items()}})
if len(snapshots) != 1 or not rows:
    raise ValueError("Empty or mixed-snapshot plan")
write_csv(a.output, list(rows[0]), sorted(rows, key=lambda r: int(r["fm_id"])))
write_json(a.output.with_suffix(".manifest.json"), {
    "snapshot_date": next(iter(snapshots)), "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    "plan_sha256": sha256(a.output), "input_hashes": {str(path): sha256(path) for path in a.plans},
    "rows": len(rows), "club_changes": sum(r["old_club_id"] != r["new_club_id"] for r in rows),
    "loans": sum(r["loan_owner_club_id"] != "0" for r in rows),
    "free_agents": sum(r["action"] == "FREE_AGENT" for r in rows),
    "expired_loans": sum(r["action"] == "RESOLVE_EXPIRED_LOAN" for r in rows),
    "successor_loans": sum(r["action"] == "REPLACE_EXPIRED_LOAN" for r in rows),
    "purchase_loans": sum(r["action"] == "PURCHASE_AND_LOAN" for r in rows), "status": "FROZEN_STAGING_NOT_RELEASE"})
print(json.dumps({"rows": len(rows), "sha256": sha256(a.output)}))
