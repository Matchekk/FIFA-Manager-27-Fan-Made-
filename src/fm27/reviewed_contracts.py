"""Explicit, evidence-bound end-date corrections for otherwise confirmed plans.

The source planner and its cached profile remain unchanged. The staging manifest
must bind the review and every returned evidence file alongside the corrected row.
This does not resolve player identities, affiliations, loans or effective starts.
"""
import datetime as dt
import re
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from .common import sha256


def exact_date_literal(value):
    """Parse an explicitly reviewed full date, independently of OS locale."""
    if not isinstance(value, str):
        return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        try:
            return dt.date.fromisoformat(value).isoformat()
        except ValueError:
            return None
    months = ("january", "february", "march", "april", "may", "june", "july",
              "august", "september", "october", "november", "december")
    match = re.fullmatch(r"(\d{1,2}) ([A-Za-z]+) (\d{4})", value)
    if not match or match[2].casefold() not in months:
        return None
    try:
        return dt.date(int(match[3]), months.index(match[2].casefold()) + 1, int(match[1])).isoformat()
    except ValueError:
        return None


def apply_reviewed_contract_end(row, review, root):
    if (review.get("status") != "REVIEWED_PERMANENT_CONTRACT_END"
            or review.get("expected_plan_row") != row):
        raise ValueError("Reviewed contract input differs from the exact confirmed row")
    if (row.get("status") != "CONFIRMED" or row.get("team_type") != "FIRST"
            or row.get("action", "SQUAD") != "SQUAD"
            or row.get("loan_owner_club_id", "0") != "0" or row.get("loan_end", "")
            or row.get("previous_loan_owner_club_id", "0") != "0"
            or row.get("previous_loan_start", "") or row.get("previous_loan_end", "")
            or not row.get("fm_id") or not row.get("new_club_id")
            or not row.get("source_sha256") or not review.get("reason")):
        raise ValueError("Only an individually confirmed permanent contract is eligible")
    until = review.get("contract_until", "")
    try:
        dob, joined, snapshot, end = [dt.date.fromisoformat(v) for v in
            (row["dob"], row["joined"], row["snapshot_date"], until)]
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Invalid reviewed contract dates") from exc
    if (review.get("snapshot_date") != row["snapshot_date"]
            or not dob < joined <= snapshot <= end or until == row.get("contract_until")):
        raise ValueError("Reviewed contract chronology or snapshot differs")
    evidence = review.get("evidence", [])
    if not evidence or not any(e.get("role") == "OFFICIAL_CLUB" for e in evidence):
        raise ValueError("An individually reviewed official source is required")
    bound = {}
    exact_date_evidence = False
    for item in evidence:
        if (item.get("status") != "REQUIRED_FACTS_PRESENT"
                or urlsplit(item.get("url", "")).scheme != "https"
                or not urlsplit(item.get("url", "")).hostname
                or not item.get("required")
                or not all(isinstance(f, str) and f.strip() for f in item["required"])):
            raise ValueError("Incomplete reviewed contract evidence")
        path = (root / item["file"]).resolve()
        if not path.is_relative_to(root.resolve()) or sha256(path) != item["sha256"]:
            raise ValueError("Reviewed contract source changed")
        body = BeautifulSoup(path.read_bytes(), "html.parser").get_text(" ", strip=True)
        if any(f.casefold() not in body.casefold() for f in item["required"]):
            raise ValueError("Reviewed contract source facts are absent")
        # An explicit exact date must be part of the reviewed facts, not inferred
        # solely from a season, option year or a generic 'summer' announcement.
        literal = item.get("contract_end_literal", until)
        if literal in item["required"] and exact_date_literal(literal) == until:
            exact_date_evidence = True
        bound[path.relative_to(root.resolve()).as_posix()] = item["sha256"]
    if not exact_date_evidence:
        raise ValueError("Exact contract end needs explicit supporting evidence")
    return {**row, "contract_until": until}, bound
