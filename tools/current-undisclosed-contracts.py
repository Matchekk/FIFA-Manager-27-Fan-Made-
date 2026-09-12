"""Export the explicit policy queue for permanent moves with undisclosed ends."""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from fm27.common import read_csv, write_csv, write_json
from fm27.matching import IdentityIndex


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blockers", type=Path,
                        default=ROOT / "reports/current/integration/essential-state-blockers.csv")
    parser.add_argument("--rosters", type=Path, nargs="+", default=[
        ROOT / "data/current/workers/south-west/rosters.csv",
        ROOT / "data/current/workers/eng-ger/tm-squads.csv"])
    parser.add_argument("--profiles", type=Path, nargs="+", default=[
        ROOT / "data/current/workers/south-west/profiles.csv",
        ROOT / "data/current/evidence/review-profiles.csv"])
    parser.add_argument("--events", type=Path,
                        default=ROOT / "data/current/evidence/transfer-events.csv")
    parser.add_argument("--players", type=Path,
                        default=ROOT / "data/intermediate/transfer-increment-20260909-07/players.csv")
    parser.add_argument("--prior-plan", type=Path,
                        default=ROOT / "data/generated/transfer-increment-plan-20260909-07.csv")
    parser.add_argument("--primary-facts", type=Path,
                        default=ROOT / "data/current/evidence/primary-transfers/confirmed-facts.json")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "reports/current/UNDISCLOSED_CONTRACTS.csv")
    args = parser.parse_args()
    snapshot = "2026-09-12"

    roster = {row["player_tm_id"]: row for path in args.rosters for row in read_csv(path)}
    profiles = {row["player_tm_id"]: row for path in args.profiles for row in read_csv(path)}
    events = {}
    for row in read_csv(args.events):
        if row.get("snapshot_date") == snapshot and row.get("source_status") == "CONFIRMED":
            events.setdefault((row.get("player_tm_id", ""), row.get("new_club_tm_id", "")), []).append(row)
    primary = {row["player_tm_id"]: row for row in json.loads(
        args.primary_facts.read_text(encoding="utf-8")) if row.get("confidence") == "CONFIRMED"}
    index = IdentityIndex(read_csv(args.players))
    prior = {row["fm_id"]: row for row in read_csv(args.prior_plan)}

    output = []
    for blocker in read_csv(args.blockers):
        if blocker.get("queue") != "CONTRACT_CHRONOLOGY":
            continue
        tm_id = blocker["player_tm_id"]
        current, profile = roster.get(tm_id, {}), profiles.get(tm_id, {})
        if (not current or not profile or profile.get("club_tm_id") != current.get("club_tm_id")
                or profile.get("dob") != current.get("dob") or not (current.get("joined") or profile.get("joined"))
                or current.get("contract_until") or profile.get("contract_until")):
            continue
        method, candidates = index.match({"player": blocker["player"], "dob": blocker["dob"],
                                          "fifa_id": blocker["fifa_id"]})
        if len(candidates) != 1:
            continue
        rich = candidates[0]
        applied = prior.get(rich["fm_id"], {})
        native_end = applied.get("contract_until", rich.get("contract_until", ""))
        if not native_end or native_end >= snapshot:
            continue
        permanent = {row.get("event_id", ""): row for row in events.get(
            (tm_id, current["club_tm_id"]), []) if row.get("transfer_type") == "PERMANENT"}
        if len(permanent) != 1:
            continue
        event = next(iter(permanent.values()))
        fact = primary.get(tm_id, {})
        output.append({
            "league": blocker["league"], "player": blocker["player"], "player_tm_id": tm_id,
            "fm_id": blocker["fm_id"], "fifa_id": blocker["fifa_id"], "dob": blocker["dob"],
            "old_native_club_id": blocker["native_club_id"],
            "new_native_club_id": blocker["target_club_id"], "current_club": blocker["club"],
            "current_club_tm_id": blocker["club_tm_id"],
            "known_join": current.get("joined") or profile.get("joined"),
            "public_contract_end": "", "old_native_contract_end": native_end,
            "event_id": event.get("event_id", ""), "event_date": event.get("explicit_event_date", ""),
            "event_old_club_tm_id": event.get("old_club_tm_id", ""),
            "event_new_club_tm_id": event.get("new_club_tm_id", ""),
            "roster_profile_agree": "YES", "identity_method": method,
            "source_confidence": "PRIMARY_PERMANENT_END_UNDISCLOSED" if fact else
                                 "SECONDARY_ROSTER_PROFILE_PERMANENT_EVENT_END_UNDISCLOSED",
            "primary_source": fact.get("source", ""), "primary_source_sha256": fact.get("source_sha256", ""),
            "roster_source": current.get("source", ""), "roster_source_sha256": current.get("source_sha256", ""),
            "profile_source": profile.get("source", ""), "profile_source_sha256": profile.get("source_sha256", ""),
            "event_source": event.get("source", ""), "event_source_sha256": event.get("source_sha256", ""),
            "snapshot_date": snapshot, "status": "POLICY_EXCEPTION_REQUIRED",
            "policy_reason": "Current permanent membership and join are confirmed, but no evidenced future contract end exists and the Native08 end is expired",
        })
    output.sort(key=lambda row: (row["league"], row["current_club"], row["player"], row["dob"]))
    fields = list(output[0]) if output else []
    if args.output.exists():
        args.output.unlink()
    if output:
        write_csv(args.output, fields, output)
    report = {
        "status": "USER_POLICY_DECISION_REQUIRED" if output else "NO_POLICY_QUEUE",
        "rows": len(output), "snapshot_date": snapshot,
        "primary_confirmed_rows": sum(row["source_confidence"].startswith("PRIMARY") for row in output),
        "provisional_end_dates_generated": 0,
        "limitation": "No contract end is inferred. These rows remain blocked until an evidenced end or explicit bounded exception policy is approved.",
    }
    write_json(args.output.with_suffix(".json"), report)
    print(json.dumps(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
