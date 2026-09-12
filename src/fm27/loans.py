"""Typed native loan plans from explicit owner, borrower and dated return evidence."""
import datetime as dt
import json
from collections import Counter, defaultdict

from .matching import IdentityIndex, normalize_club_name
from .transfer_timeline import match_profile
from .purchase_loans import ACQUISITION_DEFAULTS, acquisition_evidence
from .loan_contracts import preserved_owner_contract


def project_added_loan_condition(existing, start, end, owner_reference):
    conditions = json.loads(existing)
    if any(c[0] not in (1, 2) for c in conditions):
        raise ValueError("Loan plan would overwrite a protected condition")
    days = lambda value: dt.date.fromisoformat(value).toordinal() + 1721425
    # FifamPlayerStartingConditions::Write emits loans before injury/league ban.
    return json.dumps([[4, days(start), days(end), int(owner_reference), 0, 0]] + conditions)


def plan_loans(players, clubs, profiles, events, aliases, snapshot):
    index = IdentityIndex(players)
    by_id = {c["club_id"]: c for c in clubs}
    by_reference = defaultdict(list)
    for c in clubs:
        if c.get("reference_id"):
            by_reference[int(c["reference_id"])].append(c["club_id"])
    names = defaultdict(list)
    for c in clubs:
        names[normalize_club_name(c["club"])].append(c)
    def club(tm_id, name):
        resolved = aliases.get(tm_id, {}).get("club_id", "")
        if not resolved and len(names[normalize_club_name(name)]) == 1:
            resolved = names[normalize_club_name(name)][0]["club_id"]
        return resolved if resolved in by_id else ""
    by_person = defaultdict(list)
    for e in events:
        by_person[e["player_tm_id"]].append(e)
    counts = Counter(p["player_tm_id"] for p in profiles)
    reports, plans = [], []
    for profile in profiles:
        if not profile.get("loan_owner_tm_id"):
            continue
        if profile["snapshot_date"] != snapshot:
            raise ValueError("Mixed loan profile snapshots")
        row = {"player_tm_id": profile["player_tm_id"], "player": profile["player"], "fm_id": "", "fifa_id": "",
               "owner_club_id": "", "borrower_club_id": "", "loan_start": profile["joined"],
               "loan_end": profile["contract_until"], "owner_contract_until": profile["owner_contract_until"],
               "status": "MANUAL_REVIEW", "reason": "", "source": profile["source"],
               "source_sha256": profile["source_sha256"], "snapshot_date": snapshot,
               "acquisition_evidence": "", "loan_event_keys": "",
               "owner_contract_source_value": profile["owner_contract_until"],
               "owner_contract_basis": "CURRENT_PROFILE" if profile["owner_contract_until"] else "UNRESOLVED",
               "native_owner_contract_value": ""}
        reports.append(row)
        if profile.get("source_status") != "CONFIRMED":
            row["reason"] = "Unconfirmed current loan profile"
            continue
        method, p = match_profile(profile, index)
        if not p or counts[profile["player_tm_id"]] != 1:
            row.update(status="IDENTITY_CONFLICT", reason=method if not p else "Repeated profile")
            continue
        row.update(fm_id=p["fm_id"], fifa_id=p["fifa_id"])
        owner = club(profile["loan_owner_tm_id"], profile["loan_owner"])
        borrower = club(profile["club_tm_id"], profile["club"])
        row.update(owner_club_id=owner, borrower_club_id=borrower)
        if not owner:
            row.update(status="MISSING_OWNER", reason="Owner club unresolved")
            continue
        if not borrower:
            row["reason"] = "Borrower club unresolved"
            continue
        start, end, until = profile["joined"], profile["contract_until"], profile["owner_contract_until"]
        row["native_owner_contract_value"] = p.get("contract_until", "")
        if not end:
            row.update(status="MISSING_RETURN", reason="Loan end absent")
            continue
        if not until:
            until = preserved_owner_contract(p, owner, by_reference, start, end, snapshot)
            if until:
                row.update(owner_contract_until=until, owner_contract_basis="PRESERVED_NATIVE_SAME_OWNER")
        try:
            for value in (start, end, until):
                dt.date.fromisoformat(value)
            if not p["dob"] <= start <= snapshot <= end <= until or owner == borrower:
                raise ValueError("Invalid owner/borrower or date ordering")
        except ValueError:
            row.update(status="DATE_CONFLICT", reason="Require DOB <= start <= snapshot <= return <= owner contract")
            continue
        matching = [e for e in by_person[profile["player_tm_id"]] if e["transfer_type"] == "LOAN"
                    and (e["old_club_tm_id"] == profile["loan_owner_tm_id"] or (
                        aliases.get(e["old_club_tm_id"], {}).get("club_id") == owner
                        and aliases.get(profile["loan_owner_tm_id"], {}).get("club_id") == owner))
                    and e["new_club_tm_id"] == profile["club_tm_id"]
                    and e["timeline_status"] == "CURRENT_OR_UNDATED"
                    and (not e["explicit_event_date"] or e["explicit_event_date"] == start)]
        if not matching or any(e["timeline_status"] == "CONFLICT" for e in by_person[profile["player_tm_id"]]):
            row["reason"] = "Current profile lacks unconflicted matching loan event"
            continue
        row["loan_event_keys"] = json.dumps(sorted(e["event_key"] for e in matching))
        if not p["fm_id"]:
            row["reason"] = "Native baseline identity/ownership needs review"
            continue
        conditions = json.loads(p["starting_conditions"])
        previous = {"action":"SQUAD", "previous_loan_owner_club_id":"0", "previous_loan_start":"",
                    "previous_loan_end":"", "previous_loan_buy_option":"0", **ACQUISITION_DEFAULTS}
        if p["contract_loan_flag"] == "True" or any(c[0] not in (1, 2, 4) for c in conditions):
            row["reason"] = "Existing starting condition protected"
            continue
        old_loans = [c for c in conditions if c[0] == 4]
        seller = p["club_id"]
        old_end = ""
        if old_loans:
            if len(old_loans) != 1:
                row["reason"] = "Repeated existing loan condition protected"
                continue
            old = old_loans[0]
            old_start = dt.date.fromordinal(old[1] - 1721425).isoformat()
            old_end = dt.date.fromordinal(old[2] - 1721425).isoformat()
            owners = by_reference.get(old[3], [])
            seller = owners[0] if len(owners) == 1 else ""
            if (not seller or old[4] < -1 or old[5] != 0
                    or not p["club_id"] or p["club_id"] == "0"
                    or not p["dob"] <= old_start <= old_end < snapshot):
                row["reason"] = "Existing loan owner/flags/expiry do not permit replacement"
                continue
            if start < old_end and not (seller == owner and p["club_id"] == borrower and start == old_start):
                row["reason"] = "New loan overlaps previous borrower chronology"
                continue
            previous.update(action="REPLACE_EXPIRED_LOAN", previous_loan_owner_club_id=seller,
                            previous_loan_start=old_start, previous_loan_end=old_end, previous_loan_buy_option=str(old[4]))
        acquisition_needed = seller != owner if old_loans else p["club_id"] not in {owner, borrower}
        if acquisition_needed:
            purchase, reason = acquisition_evidence(profile, by_person[profile["player_tm_id"]], seller,
                                                    owner, club, snapshot, old_end)
            if not purchase:
                row["reason"] = reason
                continue
            previous.update(action="PURCHASE_AND_LOAN", acquisition_seller_club_id=seller,
                            acquisition_event_key=purchase["event_key"], acquisition_date=purchase["explicit_event_date"],
                            acquisition_source=purchase["source"], acquisition_source_sha256=purchase["source_sha256"])
            row["acquisition_evidence"] = json.dumps(purchase, ensure_ascii=False)
        else:
            reason = "Expired loan replaced by evidenced same-owner successor" if old_loans else "Profile owner/borrower/return and source event agree; staging only"
        if row["owner_contract_basis"] == "PRESERVED_NATIVE_SAME_OWNER":
            reason += "; existing same-owner contract end retained unchanged (source end absent)"
        row.update(status="VALID", reason=reason)
        plans.append({"fm_id": p["fm_id"], "fifa_id": p["fifa_id"], "dob": p["dob"], "old_club_id": p["club_id"],
                      "new_club_id": borrower, "joined": start, "contract_until": until, "shirt_number": profile.get("shirt_number") or p["shirt_number"],
                      "team_type": aliases.get(profile["club_tm_id"], {}).get("team_type", "FIRST"), "status": "CONFIRMED", "source": profile["source"],
                      "source_sha256": profile["source_sha256"], "snapshot_date": snapshot,
                      "loan_owner_club_id": owner, "loan_end": end, **previous})
    counts = Counter(r["fm_id"] for r in reports if r["fm_id"])
    for row in reports:
        if row["fm_id"] and counts[row["fm_id"]] > 1:
            row.update(status="IDENTITY_CONFLICT", reason="Multiple profiles matched one native person")
    plans = [p for p in plans if counts[p["fm_id"]] == 1]
    return reports, plans


def plan_current_loans(players, clubs, profiles, events, aliases, snapshot, current_rows):
    """Current roster's FIFA/identity/primary-source holds remain authoritative."""
    eligible = defaultdict(list)
    for row in current_rows:
        if row["source_date"] != snapshot:
            raise ValueError("Mixed current-loan reconciliation snapshot")
        if row["status"] == "REVIEW_REQUIRED" and row["classification"] == "LOAN_IN" and row["fm_id"]:
            eligible[row["player_tm_id"]].append(row)
    reports, plans = plan_loans(players, clubs, [p for p in profiles if p["player_tm_id"] in eligible],
                                events, aliases, snapshot)
    allowed = set()
    for report in reports:
        if report["status"] != "VALID":
            continue
        observed = eligible[report["player_tm_id"]]
        if any(row["fm_id"] != report["fm_id"] or row["new_club_id"] != report["borrower_club_id"] for row in observed):
            report.update(status="IDENTITY_CONFLICT", reason="Current roster identity/borrower disagrees with loan profile")
        else:
            allowed.add(report["fm_id"])
    return reports, [p for p in plans if p["fm_id"] in allowed]
