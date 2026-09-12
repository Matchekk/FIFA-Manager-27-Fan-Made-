"""As-of transfer reconciliation: a season table is history, not a current roster."""
import datetime as dt
import json
from collections import defaultdict

from .matching import IdentityIndex, normalize_club_name
from .transfermarkt import endpoint_kind
from .player_identities import reviewed_profile_match
from .contracts import retain_existing_end


def canonical_events(rows, snapshot):
    dt.date.fromisoformat(snapshot)
    groups = defaultdict(list)
    for row in rows:
        if row["snapshot_date"] != snapshot:
            raise ValueError("Mixed event snapshots")
        row = dict(row)
        other = "old" if row["direction"] == "Zugang" else "new"
        row["transfer_type"] = endpoint_kind(row["transfer_type"], row[other + "_club_tm_id"],
                                               row[other + "_club"], row["direction"])
        if row.get("explicit_event_date"):
            dt.date.fromisoformat(row["explicit_event_date"])
        # Never use a numeric event ID as an effective date or chronology.
        key = row["event_id"] or "missing:" + json.dumps([row["player_tm_id"], row["old_club_tm_id"],
              row["new_club_tm_id"], row["transfer_type"], row["explicit_event_date"]])
        groups[key].append(row)
    result = []
    for key, observations in groups.items():
        row = dict(observations[0])
        signatures = {(r["player_tm_id"], r["old_club_tm_id"], r["new_club_tm_id"],
                       # Free transfer/agent direction is one endpoint relationship.
                       "CLUBLESS" if r["transfer_type"] in {"FREE_AGENT", "FREE_TRANSFER"} else r["transfer_type"],
                       r["explicit_event_date"]) for r in observations}
        row["observation_count"] = len(observations)
        row["observations"] = json.dumps([{k: r[k] for k in ("league", "club_tm_id", "direction", "source", "source_sha256")}
                                          for r in observations], ensure_ascii=False)
        row["event_key"] = key
        row["timeline_status"] = ("CONFLICT" if len(signatures) != 1 else "REVIEW_REQUIRED"
                                  if any(r["source_status"] != "CONFIRMED" for r in observations) else
                                  "FUTURE" if row["explicit_event_date"] > snapshot else "CURRENT_OR_UNDATED")
        result.append(row)
    return result


def incoming_kind(events, club_id, snapshot, joined=""):
    current = [e for e in events if e["new_club_tm_id"] == club_id
               and (not e["explicit_event_date"] or e["explicit_event_date"] <= snapshot)
               and not (joined and e["explicit_event_date"] and e["explicit_event_date"] < joined)]
    if any(e.get("source_status") != "CONFIRMED" or e.get("timeline_status") == "CONFLICT" for e in current):
        return "REVIEW_REQUIRED"
    kinds = {e["transfer_type"] for e in current}
    # Historical loan returns must not silently override a later loan or purchase.
    return next(iter(kinds)) if len(kinds) == 1 else "REVIEW_REQUIRED" if kinds else "UNVERIFIED"


def match_profile(profile, index):
    matches = [index.match({"player": name, "dob": profile["dob"]})
               for name in {profile["player"], profile.get("full_name", "")} if name]
    resolved = {id(p): p for method, players in matches for p in players if method == "DOB_NAME"}
    if any(m in {"CONFLICT", "AMBIGUOUS"} for m, _ in matches) or len(resolved) > 1:
        return "CONFLICT", {}
    method, people = reviewed_profile_match(index, profile, profile,
        ("DOB_NAME", list(resolved.values())) if resolved else ("MISSING_FROM_FM", []))
    return method, people[0] if people else {}


def departure_plan(players, clubs, events, profiles, aliases, snapshot, current_roster):
    index = IdentityIndex(players)
    by_profile = defaultdict(list)
    for row in profiles:
        if row["snapshot_date"] != snapshot:
            raise ValueError("Mixed profile snapshots")
        by_profile[row["player_tm_id"]].append(row)
    by_club = {r["club_id"]: r for r in clubs}
    names = defaultdict(list)
    for club in clubs:
        names[normalize_club_name(club["club"])].append(club)
    current_ids = {r["player_tm_id"] for r in current_roster}
    grouped = defaultdict(list)
    for event in events:
        if any(o["direction"] == "Abgang" for o in json.loads(event["observations"])):
            grouped[event["player_tm_id"]].append(event)
    rows, plans = [], []
    for ident, history in grouped.items():
        if ident in current_ids:
            continue  # covered by current-squad reconciliation, counted separately
        row = {"player_tm_id": ident, "player": history[0]["player"], "fm_id": "", "fifa_id": "", "dob": "",
               "old_club_id": "", "new_club_id": "", "new_club": "", "status": "REVIEW_REQUIRED",
               "database_action": "REVIEW_REQUIRED", "reason": "MISSING_CURRENT_PROFILE", "source": "",
               "source_sha256": "", "snapshot_date": snapshot, "event_keys": json.dumps([e["event_key"] for e in history]),
               "source_contract_until": "", "contract_evidence": "UNRESOLVED",
               "leagues": json.dumps(sorted({o["league"] for e in history for o in json.loads(e["observations"])
                                              if o["direction"] == "Abgang"}))}
        rows.append(row)
        profiles_for_person = by_profile[ident]
        if not profiles_for_person:
            continue
        if len(profiles_for_person) != 1:
            row.update(status="CONFLICT", reason="DUPLICATE_CURRENT_PROFILE")
            continue
        profile = profiles_for_person[0]
        row.update(source=profile["source"], source_sha256=profile["source_sha256"], dob=profile["dob"], new_club=profile["club"])
        method, p = match_profile(profile, index)
        if not p:
            row.update(reason=method, status="CONFLICT" if method == "CONFLICT" else "REVIEW_REQUIRED")
            continue
        row.update(fm_id=p["fm_id"], fifa_id=p["fifa_id"], old_club_id=p["club_id"])
        target = aliases.get(profile["club_tm_id"], {}).get("club_id", "")
        if not target and len(names[normalize_club_name(profile["club"])]) == 1:
            target = names[normalize_club_name(profile["club"])][0]["club_id"]
        if profile["club_tm_id"] == "515":
            row["reason"] = "FREE_AGENT_REQUIRES_TYPED_NATIVE_PLAN"
            continue
        if profile["club_tm_id"] == "123" or profile["club"] == "Karriereende":
            row["reason"] = "RETIRED_REQUIRES_TYPED_NATIVE_PLAN"
            continue
        if not target or target not in by_club:
            row["reason"] = "DESTINATION_CLUB_UNRESOLVED"
            continue
        row["new_club_id"] = target
        if not p["fm_id"]:
            row["reason"] = "FREE_AGENT_NATIVE_ID_REQUIRED"
            continue
        if any(e["timeline_status"] == "CONFLICT" for e in history):
            row.update(status="CONFLICT", reason="EVENT_OBSERVATIONS_CONFLICT")
            continue
        matching = [e for e in history if e["new_club_tm_id"] == profile["club_tm_id"]
                    and e["timeline_status"] == "CURRENT_OR_UNDATED"
                    and (not e["explicit_event_date"] or e["explicit_event_date"] == profile["joined"])]
        if not matching:
            row["reason"] = "NO_CURRENT_DESTINATION_EVENT"
            continue
        kinds = {e["transfer_type"] for e in matching}
        if not kinds <= {"PERMANENT", "FREE_TRANSFER"}:
            row["reason"] = "LOAN_OR_RETURN_REQUIRES_TYPED_NATIVE_PLAN"
            continue
        origin_ids = {aliases.get(e["old_club_tm_id"], {}).get("club_id", "") for e in matching}
        if p["club_id"] not in origin_ids | {target}:
            row["reason"] = "INSTALLED_ORIGIN_CONFLICT"
            continue
        if profile.get("loan_owner_tm_id") or "ausgeliehen" in profile.get("profile_notes", "").casefold():
            row["reason"] = "PROFILE_LOAN_REQUIRES_TYPED_NATIVE_PLAN"
            continue
        if any(c[0] in (3, 4, 5, 6, 7, 8, 9, 10) for c in json.loads(p["starting_conditions"])) or p["contract_loan_flag"] == "True":
            row["reason"] = "STARTING_CONDITION_CONFLICT"
            continue
        joined, until = profile["joined"], profile["contract_until"]
        contract = retain_existing_end({"joined": joined, "contract_until": until, "status": "CURRENT_PROFILE"},
                                       p, profile, snapshot)
        row.update(source_contract_until=until, contract_evidence=contract["status"])
        until = contract["contract_until"]
        if not joined or not until or not p["dob"] <= joined <= snapshot <= until:
            row["reason"] = "MISSING_OR_INVALID_CURRENT_CONTRACT"
            continue
        dt.date.fromisoformat(joined)
        dt.date.fromisoformat(until)
        row.update(status="CONFIRMED", database_action="STAGE_CURRENT_SQUAD", reason="PROFILE_AND_DEPARTURE_AGREE")
        if contract.get("native_until_preserved"):
            row["reason"] = "PROFILE_AND_DEPARTURE_AGREE_NATIVE_CONTRACT_END_PRESERVED"
        plans.append({"fm_id": p["fm_id"], "fifa_id": p["fifa_id"], "dob": p["dob"],
                      "old_club_id": p["club_id"], "new_club_id": target, "joined": joined, "contract_until": until,
                      "shirt_number": profile.get("shirt_number") or p["shirt_number"], "team_type": aliases.get(profile["club_tm_id"], {}).get("team_type", "FIRST"), "status": "CONFIRMED",
                      "source": profile["source"], "source_sha256": profile["source_sha256"], "snapshot_date": snapshot})
    # Different source people may not collapse into a single FM identity.
    fm_people = defaultdict(set)
    for row in rows:
        if row["fm_id"]:
            fm_people[row["fm_id"]].add(row["player_tm_id"])
    collisions = {k for k, v in fm_people.items() if len(v) > 1}
    for row in rows:
        if row["fm_id"] in collisions:
            row.update(status="CONFLICT", database_action="REVIEW_REQUIRED", reason="IDENTITY_COLLISION")
    return rows, [p for p in plans if p["fm_id"] not in collisions]
