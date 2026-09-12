"""Explicit, dated releases to the native clubless pool; never delete a person."""
import datetime as dt
import json
from collections import Counter, defaultdict

from .matching import IdentityIndex
from .transfer_timeline import match_profile


def plan_free_agents(players, profiles, events, aliases, snapshot, current_roster):
    today = dt.date.fromisoformat(snapshot)
    index = IdentityIndex(players)
    roster_ids = {p["player_tm_id"] for p in current_roster}
    grouped = defaultdict(list)
    for event in events:
        grouped[event["player_tm_id"]].append(event)
    counts = Counter(p["player_tm_id"] for p in profiles)
    rows, plans = [], []
    for profile in profiles:
        if profile["club_tm_id"] != "515" or profile["player_tm_id"] in roster_ids:
            continue
        ident = profile["player_tm_id"]
        history = grouped[ident]
        if not any(o["direction"] == "Abgang" for e in history for o in json.loads(e["observations"])):
            continue
        row = {"player_tm_id": ident, "player": profile["player"], "dob": profile["dob"], "fm_id": "",
               "old_club_id": "", "new_club_id": "0", "effective_date": profile["joined"],
               "status": "REVIEW_REQUIRED", "reason": "UNCONFIRMED_PROFILE",
               "source": profile["source"], "source_sha256": profile["source_sha256"], "snapshot_date": snapshot}
        rows.append(row)
        if profile["snapshot_date"] != snapshot:
            raise ValueError("Mixed free-agent profile snapshots")
        if profile.get("source_status") != "CONFIRMED":
            continue
        if counts[ident] != 1:
            row.update(status="CONFLICT", reason="DUPLICATE_PROFILE")
            continue
        method, player = match_profile(profile, index)
        if not player:
            row["reason"] = method
            continue
        row.update(fm_id=player["fm_id"], old_club_id=player["club_id"])
        if player["club_id"] == "0":
            row.update(status="ALREADY_FREE_AGENT", reason="NO_MUTATION_REQUIRED")
            continue
        if not player["fm_id"]:
            row["reason"] = "NATIVE_ID_REQUIRED"
            continue
        if any(e["timeline_status"] in {"CONFLICT", "REVIEW_REQUIRED", "FUTURE"} for e in history):
            row["reason"] = "CONFLICTING_OR_FUTURE_EVENT"
            continue
        if profile.get("loan_owner_tm_id") or profile.get("contract_until"):
            row["reason"] = "PROFILE_HAS_ACTIVE_CONTRACT_OR_LOAN"
            continue
        joined = profile["joined"]
        if not joined or not player["dob"] < joined <= snapshot:
            row["reason"] = "MISSING_OR_INVALID_RELEASE_DATE"
            continue
        effective = dt.date.fromisoformat(joined)
        if effective > today:
            raise ValueError("Future release")
        matching = [e for e in history if e["new_club_tm_id"] == "515" and e["transfer_type"] == "FREE_AGENT"
                    and e["timeline_status"] == "CURRENT_OR_UNDATED"
                    and (not e["explicit_event_date"] or e["explicit_event_date"] == joined)]
        if not matching:
            row["reason"] = "NO_MATCHING_RELEASE_EVENT"
            continue
        origins = {aliases.get(e["old_club_tm_id"], {}).get("club_id", "") for e in matching}
        if player["club_id"] not in origins:
            row["reason"] = "INSTALLED_ORIGIN_CONFLICT"
            continue
        if any(c[0] in (3, 4, 5, 6, 7, 8, 9, 10) for c in json.loads(player["starting_conditions"])) or player["contract_loan_flag"] == "True":
            row["reason"] = "STARTING_CONDITION_CONFLICT"
            continue
        row.update(status="CONFIRMED", reason="CURRENT_PROFILE_AND_RELEASE_EVENT_AGREE")
        plans.append({"fm_id": player["fm_id"], "fifa_id": player["fifa_id"], "dob": player["dob"],
                      "old_club_id": player["club_id"], "new_club_id": "0", "joined": joined,
                      "contract_until": (effective - dt.timedelta(days=1)).isoformat(), "shirt_number": "0",
                      "team_type": "FIRST", "status": "CONFIRMED", "source": profile["source"],
                      "source_sha256": profile["source_sha256"], "snapshot_date": snapshot,
                      "loan_owner_club_id": "0", "loan_end": "", "action": "FREE_AGENT"})
    native_ids = Counter(row["fm_id"] for row in rows if row["fm_id"])
    collisions = {ident for ident, count in native_ids.items() if count > 1}
    for row in rows:
        if row["fm_id"] in collisions:
            row.update(status="CONFLICT", reason="IDENTITY_COLLISION")
    return rows, [p for p in plans if p["fm_id"] not in collisions]
