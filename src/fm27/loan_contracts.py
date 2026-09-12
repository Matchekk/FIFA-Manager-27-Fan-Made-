"""Retain plausible existing same-owner contracts when source detail is absent."""
import datetime as dt
import json


def preserved_owner_contract(player, owner, by_reference, start, end, snapshot):
    """Return the existing value unchanged, or empty when ownership/dates are unproved.

    This is preservation of an installed value, not evidence of a new contract.
    It cannot carry a seller's contract into a purchase-and-loan transaction.
    """
    until = player.get("contract_until", "")
    joined = player.get("contract_joined", "")
    try:
        for value in (player["dob"], joined, start, end, snapshot, until):
            dt.date.fromisoformat(value)
        if not player["dob"] <= joined <= start <= snapshot <= end <= until:
            return ""
        if player.get("contract_loan_flag") != "False" or not player.get("fm_id"):
            return ""
        conditions = json.loads(player["starting_conditions"])
        if any(len(c) != 6 or c[0] not in (1, 2, 4) for c in conditions):
            return ""
        loans = [c for c in conditions if c[0] == 4]
        if not loans:
            return until if player.get("club_id") == owner else ""
        if len(loans) != 1 or player.get("club_id") in (None, "", "0", owner):
            return ""
        old = loans[0]
        old_start = dt.date.fromordinal(old[1] - 1721425).isoformat()
        old_end = dt.date.fromordinal(old[2] - 1721425).isoformat()
        if (by_reference.get(old[3], []) != [owner] or old[4] < -1 or old[5] != 0
                or not player["dob"] <= old_start <= old_end < snapshot):
            return ""
        return until
    except (KeyError, ValueError, TypeError, OverflowError):
        return ""
