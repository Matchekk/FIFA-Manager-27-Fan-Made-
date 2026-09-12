"""Validate the exported identity contract. Not a native database release gate."""
import datetime as dt
import json
from collections import Counter


def validate(players: list[dict], clubs: list[dict], snapshot: dt.date) -> list[dict]:
    warnings = []

    def add(severity: str, code: str, identity: str, message: str) -> None:
        warnings.append({"severity": severity, "code": code, "identity": identity, "message": message})

    for kind, rows, key in (("CLUB", clubs, "club_id"), ("PERSON", players, "fm_id"),
                            ("FIFA", players, "fifa_id")):
        counts = Counter(str(r.get(key, "")) for r in rows if str(r.get(key, "")) not in ("", "0"))
        for identity, count in counts.items():
            if count > 1:
                add("FATAL" if kind != "FIFA" else "ERROR", f"DUPLICATE_{kind}_ID", identity, str(count))
    club_ids = {str(c["club_id"]) for c in clubs}
    valid_clubs = club_ids | {"0"}
    squads = Counter()
    for p in players:
        identity = str(p.get("fm_id") or p.get("fifa_id") or f"{p.get('source_file')}:{p.get('source_line')}")
        if str(p["club_id"]) not in valid_clubs:
            add("FATAL", "MISSING_CLUB", identity, str(p["club_id"]))
        try:
            birthday = dt.date.fromisoformat(p["dob"])
            age = (snapshot - birthday).days / 365.2425
            if age < 10 or age > 65:
                add("WARNING", "UNUSUAL_AGE", identity, f"{age:.1f}")
        except ValueError:
            add("ERROR", "INVALID_DOB", identity, p["dob"])
        if p.get("position") == "NONE":
            add("ERROR", "MISSING_POSITION", identity, "No main position")
        values = json.loads(p.get("attributes") or "{}")
        if any(type(value) is not int or not 0 <= value <= 99 for value in values.values()):
            add("ERROR", "ATTRIBUTE_RANGE", identity, "Expected integer attributes in [0,99]")
        joined, until = p.get("contract_joined"), p.get("contract_until")
        try:
            start = dt.date.fromisoformat(joined) if joined not in (None, "", "0000-00-00") else None
            end = dt.date.fromisoformat(until) if until not in (None, "", "0000-00-00") else None
            # Native converter encodes clubless players with an expired interval
            # (e.g. joined 1 July, until 30 June). This is not an active contract.
            native_clubless_interval = (str(p["club_id"]) == "0" and p.get("contract_loan_flag") not in (True, "True")
                                        and start and end and end + dt.timedelta(days=1) == start)
            if start and end and end < start and not native_clubless_interval:
                add("ERROR", "CONTRACT_ORDER", identity, "End before start")
        except ValueError:
            add("ERROR", "CONTRACT_DATE", identity, "Malformed contract date")
        if p.get("squad") == "FIRST":
            squads[str(p["club_id"])] += 1
    for club in clubs:
        if club.get("league"):
            size = squads[str(club["club_id"])]
            if size == 0 or size > 60:
                add("ERROR" if size == 0 else "WARNING", "SQUAD_SIZE", str(club["club_id"]), str(size))
    return warnings
