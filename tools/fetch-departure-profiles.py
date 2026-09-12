"""Fetch only people appearing in scoped departures; resumable, hash-bound batches."""
import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fm27.common import read_csv, write_csv, write_json, sha256
from fm27.public_cache import DfbCache
from fm27.transfermarkt import parse_profile

parser = argparse.ArgumentParser()
parser.add_argument("--limit", type=int, default=100)
parser.add_argument("--include-missing-roster", action="store_true",
                    help="Also fetch profiles of unresolved current scoped-roster identities")
parser.add_argument("--include-current-review", action="store_true",
                    help="Also fetch profiles for current scoped-roster loan, contract and other review holds")
a = parser.parse_args()
if a.limit < 1:
    parser.error("limit must be positive")
root = Path(__file__).resolve().parents[1]
events = read_csv(root / "data/intermediate/transfer-events.csv")
rosters = read_csv(root / "data/intermediate/tm-squads.csv")
dates = {r["snapshot_date"] for r in events + rosters}
today = dt.datetime.now(dt.timezone.utc).date().isoformat()
if dates != {today}:
    raise ValueError("Refresh explicitly: current profiles cannot be mixed with a historical snapshot")
current = {r["player_tm_id"] for r in rosters}
queue = {}
for row in events:
    if row["direction"] == "Abgang" and row["player_tm_id"] not in current:
        queue.setdefault(row["player_tm_id"], row)
departure_ids = set(queue)
if a.include_missing_roster:
    missing = {r["player_tm_id"] for r in read_csv(root / "reports/local/current/UNMATCHED_PLAYERS.csv")}
    for row in rosters:
        if row["player_tm_id"] in missing:
            queue.setdefault(row["player_tm_id"], row)
missing_ids = set(queue) - departure_ids
if a.include_current_review:
    review = {r["player_tm_id"] for r in read_csv(root / "reports/local/current/TRANSFER_DIFF.csv") if r["status"] != "CONFIRMED"}
    for row in rosters:
        if row["player_tm_id"] in review:
            queue.setdefault(row["player_tm_id"], row)
path = root / "data/intermediate/departure-profiles.csv"
rows = read_csv(path) if path.exists() else []
if any(r["snapshot_date"] != today for r in rows):
    raise ValueError("Existing profile file has a different snapshot")
for row in rows:
    if sha256(root / "data/raw/transfermarkt" / (row["source_sha256"] + ".html")) != row["source_sha256"]:
        raise ValueError("Profile hash mismatch")
seen = {r["player_tm_id"] for r in rows}
cache = DfbCache(root / "data/raw/transfermarkt", host="www.transfermarkt.de")
failures = []
attempts = 0
for ident, event in queue.items():
    if ident in seen:
        continue
    if attempts >= a.limit:
        break
    attempts += 1
    try:
        html, source = cache.fetch(event["profile_url"], reuse_today=True)
        row = parse_profile(html, ident)
        row.update(source=event["profile_url"], source_sha256=source["sha256"],
                   retrieved_at=source["retrieved_at"], snapshot_date=today,
                   imported_at=dt.datetime.now(dt.timezone.utc).isoformat())
        rows.append(row)
        seen.add(ident)
        write_csv(path, list(row), rows)
    except Exception as exc:
        failures.append({"player_tm_id": ident, "source": event["profile_url"], "error": str(exc)})
    report = {"snapshot_date": today, "scoped_departure_people": len(departure_ids),
              "requested_people": len(queue), "requested_missing_roster_people": len(missing_ids),
              "requested_current_review_people": len(queue.keys() - departure_ids - missing_ids),
              "profiles_captured": len(seen & queue.keys()), "remaining": len(queue.keys() - seen),
              "attempted_this_run": attempts, "failures_this_run": failures, "production_writes": 0}
    write_json(root / "reports/local/DEPARTURE_PROFILE_FETCH.json", report)
    if attempts % 10 == 0:
        print(json.dumps(report), flush=True)
print(json.dumps({"profiles_captured": len(rows), "attempts": attempts, "failures": failures}), flush=True)
