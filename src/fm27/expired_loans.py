"""Resolve evidenced completed loans with exact native old-condition preconditions."""
import datetime as dt
import json
from collections import defaultdict, Counter

from .matching import IdentityIndex, normalize_club_name
from .transfer_timeline import match_profile


def project_removed_expired_loan(existing, plan, owner_reference):
    conditions = json.loads(existing)
    days = lambda value: dt.date.fromisoformat(value).toordinal() + 1721425
    expected = [4, days(plan["previous_loan_start"]), days(plan["previous_loan_end"]),
                int(owner_reference), int(plan["previous_loan_buy_option"]), 0]
    if ([c for c in conditions if c[0] == 4] != [expected]
            or any(c[0] not in (1, 2, 4) for c in conditions)
            or not plan["previous_loan_start"] <= plan["previous_loan_end"] < plan["snapshot_date"]):
        raise ValueError("Expired-loan projection precondition mismatch")
    return json.dumps([c for c in conditions if c[0] != 4])


def plan_expired_loans(players, clubs, current, profiles, events, aliases, snapshot):
    index = IdentityIndex(players)
    by_id = {p["fm_id"]:p for p in players if p["fm_id"]}
    references = {int(c["reference_id"]):c for c in clubs}
    names = defaultdict(list)
    for club in clubs:
        names[normalize_club_name(club["club"])].append(club)
    def club_id(tm_id, name):
        alias = aliases.get(tm_id)
        if alias:
            return alias["club_id"]
        matches = names[normalize_club_name(name)]
        return matches[0]["club_id"] if len(matches) == 1 else ""
    by_profile = defaultdict(list)
    for p in profiles:
        by_profile[p["player_tm_id"]].append(p)
    history = defaultdict(list)
    for event in events:
        history[event["player_tm_id"]].append(event)
    rows, plans = [], []
    for observed in current:
        if observed["status"] != "REVIEW_REQUIRED" or observed["reason"] != "Installed future conditions need typed native review":
            continue
        p = by_id.get(observed["fm_id"])
        if not p:
            continue
        row = {"player_tm_id":observed["player_tm_id"], "fm_id":p["fm_id"], "player":p["name"],
               "old_club_id":p["club_id"], "new_club_id":observed["new_club_id"],
               "status":"REVIEW_REQUIRED", "reason":"UNSUPPORTED_EXISTING_CONDITION",
               "previous_conditions":p["starting_conditions"], "source":"", "source_sha256":"", "snapshot_date":snapshot}
        rows.append(row)
        conditions = json.loads(p["starting_conditions"])
        loans = [c for c in conditions if c[0] == 4]
        if len(loans) != 1 or any(c[0] not in (1, 2, 4) for c in conditions) or p["contract_loan_flag"] == "True":
            continue
        old = loans[0]
        if old[3] not in references or old[5] != 0 or old[4] < -1:
            row["reason"] = "UNSUPPORTED_OLD_LOAN_REFERENCE_OR_FLAGS"
            continue
        owner = references[old[3]]["club_id"]
        start = dt.date.fromordinal(old[1] - 1721425).isoformat()
        end = dt.date.fromordinal(old[2] - 1721425).isoformat()
        if not p["dob"] <= start <= end < snapshot:
            row["reason"] = "OLD_LOAN_NOT_EXPIRED"
            continue
        candidates = by_profile[observed["player_tm_id"]]
        if len(candidates) != 1:
            row["reason"] = "MISSING_OR_DUPLICATE_CURRENT_PROFILE"
            continue
        profile = candidates[0]
        row.update(source=profile["source"], source_sha256=profile["source_sha256"])
        if profile["snapshot_date"] != snapshot or observed["source_date"] != snapshot:
            raise ValueError("Mixed expired-loan evidence snapshot")
        method, actual = match_profile(profile, index)
        if (profile.get("source_status") != "CONFIRMED" or not actual or actual["fm_id"] != p["fm_id"]
                or profile["club_tm_id"] != observed["club_tm_id"] or profile["dob"] != observed["dob"]):
            row["reason"] = "CURRENT_PROFILE_IDENTITY_OR_CLUB_CONFLICT"
            continue
        if profile.get("loan_owner_tm_id") or "ausgeliehen" in profile.get("profile_notes", "").casefold():
            row["reason"] = "CURRENT_PROFILE_STILL_ON_LOAN"
            continue
        joined, until = profile["joined"], profile["contract_until"]
        if (not joined or not until or not p["dob"] <= joined <= snapshot <= until
                or joined != observed["joined"] or until != observed["contract_until"]):
            row["reason"] = "CURRENT_CONTRACT_EVIDENCE_CONFLICT"
            continue
        dt.date.fromisoformat(joined); dt.date.fromisoformat(until)
        person_events = history[observed["player_tm_id"]]
        if any(e["timeline_status"] in {"CONFLICT", "REVIEW_REQUIRED"} for e in person_events):
            row["reason"] = "CONFLICTING_TRANSFER_EVENTS"
            continue
        target = observed["new_club_id"]
        returns = [e for e in person_events if e["transfer_type"] == "LOAN_RETURN" and target == owner
                   and e["new_club_tm_id"] == profile["club_tm_id"] and e["timeline_status"] == "CURRENT_OR_UNDATED"
                   and club_id(e["old_club_tm_id"], e["old_club"]) == p["club_id"]
                   and (not e["explicit_event_date"] or e["explicit_event_date"] in {end, (dt.date.fromisoformat(end)+dt.timedelta(days=1)).isoformat()})]
        permanent = [e for e in person_events if e["transfer_type"] == "PERMANENT"
                     and e["new_club_tm_id"] == profile["club_tm_id"] and e["timeline_status"] == "CURRENT_OR_UNDATED"
                     and club_id(e["old_club_tm_id"], e["old_club"]) in {owner, p["club_id"]}
                     and (target == p["club_id"] or joined >= end)
                     and (not e["explicit_event_date"] or end <= e["explicit_event_date"] <= snapshot)]
        if not returns and not permanent:
            row["reason"] = "NO_CONFIRMED_RETURN_OR_PERMANENT_SUCCESSOR"
            continue
        row.update(status="CONFIRMED", reason="EXPIRED_LOAN_RETURN" if returns else "EXPIRED_LOAN_PERMANENT_SUCCESSOR")
        plans.append({"fm_id":p["fm_id"], "fifa_id":p["fifa_id"], "dob":p["dob"], "old_club_id":p["club_id"],
                      "new_club_id":target, "joined":joined, "contract_until":until,
                      "shirt_number":observed["shirt_number"] if observed["shirt_number"].isdigit() and int(observed["shirt_number"])<=99 else p["shirt_number"],
                      "team_type":observed["team_type"], "status":"CONFIRMED", "source":profile["source"],
                      "source_sha256":profile["source_sha256"], "snapshot_date":snapshot,
                      "loan_owner_club_id":"0", "loan_end":"", "action":"RESOLVE_EXPIRED_LOAN",
                      "previous_loan_owner_club_id":owner, "previous_loan_start":start, "previous_loan_end":end,
                      "previous_loan_buy_option":str(old[4])})
    counts = Counter(p["fm_id"] for p in plans)
    # Multiple current team observations must be reconciled first, never applied twice.
    for row in rows:
        if counts[row["fm_id"]] > 1:
            row.update(status="REVIEW_REQUIRED", reason="REPEATED_CURRENT_TEAM_OBSERVATION")
    return rows, [p for p in plans if counts[p["fm_id"]] == 1]
