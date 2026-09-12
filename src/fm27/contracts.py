"""Fill missing roster dates only from an agreeing current profile."""
import datetime as dt
import json


def current_contract(roster, profile, snapshot):
    result = {k: roster.get(k, "") for k in ("joined", "contract_until")}
    result.update(status="UNCHANGED", used_profile=False)
    if not profile:
        return result
    if (profile.get("source_status") != "CONFIRMED" or profile.get("snapshot_date") != snapshot
            or profile.get("club_tm_id") != roster["club_tm_id"] or profile.get("dob") != roster["dob"]):
        result["status"] = "CONFLICT"
        return result
    if profile.get("loan_owner_tm_id"):
        result["status"] = "LOAN"
        return result
    for key in ("joined", "contract_until"):
        value = profile.get(key, "")
        if value:
            dt.date.fromisoformat(value)
            if result[key] and result[key] != value:
                result["status"] = "CONFLICT"
                return result
            if not result[key]:
                result[key] = value
                result["used_profile"] = True
    if result["used_profile"]:
        if not result["joined"] or not result["contract_until"] or not roster["dob"] <= result["joined"] <= snapshot <= result["contract_until"]:
            result["status"] = "INCOMPLETE"
        else:
            result["status"] = "PROFILE_COMPLETED"
    return result


def retain_existing_end(contract, player, profile, snapshot):
    """Keep an existing plausible end when current sources omit it (master §18).

    This is deliberately not a claim that the old end is a newly sourced contract.
    Callers still require resolved identity/club, current affiliation, an effective
    start and the matching transfer event. Loan ownership has its separate planner.
    """
    if (contract.get("contract_until") or profile.get("contract_until")
            or contract.get("status") in {"CONFLICT", "LOAN"}
            or profile.get("source_status") != "CONFIRMED" or profile.get("snapshot_date") != snapshot
            or profile.get("dob") != player.get("dob") or profile.get("loan_owner_tm_id")
            or "ausgeliehen" in profile.get("profile_notes", "").casefold()
            or player.get("contract_loan_flag") != "False"):
        return contract
    try:
        conditions = json.loads(player["starting_conditions"])
        if (not isinstance(conditions, list) or any(not isinstance(c, list) or len(c) != 6
                or c[0] not in {1, 2} for c in conditions)):
            return contract
        dob, old_joined, joined, today, until = [dt.date.fromisoformat(v) for v in (
            player["dob"], player["contract_joined"], contract["joined"], snapshot, player["contract_until"])]
    except (KeyError, TypeError, ValueError):
        return contract
    if not dob <= old_joined <= joined <= today <= until:
        return contract
    return {**contract, "contract_until": player["contract_until"],
            "status": "NATIVE_END_PRESERVED", "native_until_preserved": True}
