"""Source-backed ownership changes before a current loan; no guessed purchase dates."""
import datetime as dt
import re


ACQUISITION_DEFAULTS = {
    "acquisition_seller_club_id": "0", "acquisition_event_key": "",
    "acquisition_date": "", "acquisition_source": "", "acquisition_source_sha256": "",
}


def acquisition_evidence(profile, history, seller, owner, resolve_club, snapshot, old_end=""):
    """Return exactly one proved seller→owner acquisition, or a review reason.

    Undated events establish the ownership path using the dated current profile,
    not an ordering of event IDs. A conflicting or unresolved competing ownership
    event cannot be discarded. Earlier explicitly dated history may remain.
    """
    if not seller or seller == "0" or seller == owner:
        return None, "Acquisition needs a distinct resolved native seller"
    if any(e.get("snapshot_date") != snapshot for e in history):
        return None, "Mixed acquisition event snapshots"
    if any(e.get("timeline_status") in {"CONFLICT", "REVIEW_REQUIRED"} for e in history):
        return None, "Unconfirmed or conflicting acquisition timeline"
    start = profile["joined"]
    matches = []
    for e in history:
        if e.get("transfer_type") != "PERMANENT" or e.get("new_club_tm_id") != profile["loan_owner_tm_id"]:
            continue
        if e.get("timeline_status") != "CURRENT_OR_UNDATED":
            continue
        date = e.get("explicit_event_date", "")
        if date:
            try:
                dt.date.fromisoformat(date)
            except ValueError:
                return None, "Invalid acquisition date"
            if not profile["dob"] <= date <= start or (old_end and date < old_end):
                return None, "Acquisition date conflicts with existing loan or current loan start"
        if resolve_club(e["old_club_tm_id"], e["old_club"]) != seller:
            return None, "Competing acquisition seller requires review"
        if (e.get("source_status") != "CONFIRMED" or not e.get("event_key")
                or not e.get("source", "").startswith("https://")
                or not re.fullmatch("[0-9a-f]{64}", e.get("source_sha256", ""))):
            return None, "Acquisition source provenance missing"
        matches.append(e)
    if len(matches) != 1:
        return None, "Require one unambiguous permanent acquisition from native seller"
    purchase = matches[0]
    purchase_date = purchase.get("explicit_event_date", "")
    for e in history:
        if e.get("timeline_status") != "CURRENT_OR_UNDATED" or e is purchase:
            continue
        date = e.get("explicit_event_date", "")
        if e.get("old_club_tm_id") == profile["loan_owner_tm_id"]:
            if e.get("transfer_type") == "LOAN" and e.get("new_club_tm_id") == profile["club_tm_id"]:
                if date and date > start:
                    return None, "Later loan event conflicts with current profile start"
                continue
            # A dated return to the evidenced seller can precede an undated
            # acquisition. An unrelated exit needs an explicitly later purchase;
            # merely preceding the current loan does not prove reacquisition.
            prior_return = (e.get("transfer_type") == "LOAN_RETURN" and date and date < start
                            and resolve_club(e["new_club_tm_id"], e["new_club"]) == seller
                            and (not purchase_date or date <= purchase_date)
                            and (not old_end or date == old_end))
            if not prior_return and not (date and purchase_date and date < purchase_date):
                return None, "Competing owner exit lacks a later proved acquisition"
    return purchase, "Permanent seller-to-owner event and current owner-to-borrower loan agree"
