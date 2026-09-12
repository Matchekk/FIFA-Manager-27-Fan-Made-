"""Freeze source-grounded releases; preserve conflicting primary roster holds."""
import datetime as dt
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fm27.common import read_csv, write_csv, write_json, sha256
from fm27.free_agents import plan_free_agents
from fm27.transfermarkt import parse_profile
from fm27.transfer_timeline import canonical_events

root = Path(__file__).resolve().parents[1]
meta = json.loads((root / "reports/local/TM_SQUADS_FETCH.json").read_text(encoding="utf-8"))
snapshot = meta["DATABASE_SNAPSHOT_DATE"]
events = read_csv(root / "data/intermediate/transfer-events.csv")
profiles = [r for r in read_csv(root / "data/intermediate/departure-profiles.csv") if r["club_tm_id"] == "515"]
for digest in {r["source_sha256"] for r in events + profiles}:
    if sha256(root / "data/raw/transfermarkt" / (digest + ".html")) != digest:
        raise ValueError("Source hash mismatch")
profiles = [{**r, **parse_profile((root / "data/raw/transfermarkt" / (r["source_sha256"] + ".html")).read_text(encoding="utf-8-sig"), r["player_tm_id"])} for r in profiles]
aliases = json.loads((root / "config/tm-club-aliases.json").read_text(encoding="utf-8"))
rows, plans = plan_free_agents(read_csv(root / "data/intermediate/baseline-final/players.csv"), profiles,
    canonical_events(events, snapshot), aliases, snapshot, read_csv(root / "data/intermediate/tm-squads.csv"))
official = {r["fm_id"] for r in read_csv(root / "reports/local/germany/TRANSFER_DIFF.csv")
            if r["fm_id"] and r["source_status"] == "CONFIRMED" and r["classification"] != "AMBIGUOUS"}
held = set()
for row in rows:
    if row["status"] == "CONFIRMED" and row["fm_id"] in official:
        row.update(status="CONFLICT", reason="PRIMARY_ROSTER_CONTRADICTS_RELEASE")
        held.add(row["fm_id"])
plans = [p for p in plans if p["fm_id"] not in held]
fields = ["fm_id", "fifa_id", "dob", "old_club_id", "new_club_id", "joined", "contract_until", "shirt_number",
          "team_type", "status", "source", "source_sha256", "snapshot_date", "loan_owner_club_id", "loan_end", "action"]
output = root / "data/intermediate/free-agent-plan.csv"
write_csv(output, fields, plans)
write_csv(root / "reports/FREE_AGENT_RECONCILIATION.csv", list(rows[0]), rows)
write_json(root / "reports/local/FREE_AGENT_RECONCILIATION.json", {
    "snapshot_date": snapshot, "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    "profiles": len(profiles), "plan_rows": len(plans), "statuses": dict(Counter(r["status"] for r in rows)),
    "review_reasons": dict(Counter(r["reason"] for r in rows if r["status"] != "CONFIRMED")),
    "plan_sha256": sha256(output), "profile_sources": [{k: r[k] for k in ("player_tm_id", "source", "source_sha256")} for r in profiles],
    "input_sha256": {str(path.relative_to(root)): sha256(path) for path in [
        root / "config/tm-club-aliases.json", root / "data/intermediate/transfer-events.csv",
        root / "data/intermediate/baseline-final/players.csv", root / "data/intermediate/tm-squads.csv",
        root / "reports/local/germany/TRANSFER_DIFF.csv", root / "src/fm27/free_agents.py"]},
    "status": "SOURCE_PLAN_REQUIRES_NATIVE_VALIDATION", "release_ready": False})
print(json.dumps({"plan_rows": len(plans), "statuses": dict(Counter(r["status"] for r in rows))}))
