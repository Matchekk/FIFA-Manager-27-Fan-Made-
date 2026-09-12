"""Produce reviewable transfer proposals. This module cannot write game files."""
import datetime as dt
import json
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

from .common import read_csv, sha256, write_csv, write_json
from .matching import IdentityIndex

FIELDS = ["league", "club", "player", "fifa_id", "fm_id", "old_club", "new_club",
          "transfer_type", "contract_until", "shirt_number", "source", "source_date",
          "confidence", "database_action", "classification", "status", "reason",
          "loan_parent_club_id", "loan_end"]
INPUT_FIELDS = ["league", "player", "fifa_id", "dob", "nationality", "from_club_id",
                "to_club_id", "transfer_type", "status", "source", "source_date",
                "observed_at", "confidence", "contract_until", "shirt_number",
                "loan_parent_club_id", "loan_end"]
KINDS = {"PERMANENT", "LOAN", "LOAN_RETURN", "FREE_TRANSFER", "RELEASED", "RETIRED"}
STATUSES = {"CONFIRMED", "CONFLICT", "REVIEW_REQUIRED", "RUMOR"}


def validate_evidence(row: dict, snapshot: dt.date, clubs: dict) -> list[str]:
    errors = []
    if row.get("status") not in STATUSES:
        errors.append("Invalid evidence status")
    if row.get("status") != "CONFIRMED":
        errors.append("Evidence is not CONFIRMED")
    if row.get("transfer_type") not in KINDS:
        errors.append("Unsupported transfer type")
    url = urlparse(row.get("source", ""))
    if url.scheme != "https" or not url.hostname:
        errors.append("HTTPS source citation required")
    for field in ("source_date", "observed_at"):
        try:
            if dt.date.fromisoformat(row.get(field, "")) > snapshot:
                errors.append(f"{field} is after database snapshot")
        except ValueError:
            errors.append(f"Invalid {field}")
    for field in ("contract_until", "loan_end"):
        if row.get(field):
            try:
                end = dt.date.fromisoformat(row[field])
                if end < snapshot:
                    errors.append(f"{field} predates snapshot")
            except ValueError:
                errors.append(f"Invalid {field}")
    try:
        if not 0 <= float(row.get("confidence", "")) <= 1:
            errors.append("Confidence outside [0,1]")
    except ValueError:
        errors.append("Invalid confidence")
    target = row.get("to_club_id", "")
    if target != "0" and target not in clubs:
        errors.append("Unknown destination club")
    if row.get("from_club_id", "") not in clubs and row.get("from_club_id") != "0":
        errors.append("Unknown origin club")
    if row.get("transfer_type") in {"RELEASED", "RETIRED"} and target != "0":
        errors.append("Released/retired player requires destination 0")
    if row.get("transfer_type") not in {"RELEASED", "RETIRED"} and target == "0":
        errors.append("Transfer requires a destination club")
    if row.get("transfer_type") == "LOAN":
        if row.get("loan_parent_club_id") not in clubs or not row.get("loan_end"):
            errors.append("Loan requires valid parent club and end date")
        if row.get("loan_parent_club_id") != row.get("from_club_id"):
            errors.append("Loan parent must match origin; chained loans need native review")
    if row.get("shirt_number"):
        try:
            if not 1 <= int(row["shirt_number"]) <= 99:
                errors.append("Shirt number outside supported range")
        except ValueError:
            errors.append("Invalid shirt number")
    return errors


def plan(players: list[dict], clubs_list: list[dict], evidence: list[dict],
         snapshot: dt.date, scope_keys: set[str]) -> list[dict]:
    clubs = {str(c["club_id"]): c for c in clubs_list}
    if len(clubs) != len(clubs_list):
        raise ValueError("Duplicate club IDs; cannot reconcile safely")
    index = IdentityIndex(players)
    matches = [index.match(row) for row in evidence]
    # All competing evidence for a person requires review, regardless of status/order.
    identities = [(f"fm:{c[0]['fm_id']}" if c[0].get("fm_id") else
                   f"source:{c[0].get('source_file')}:{c[0].get('source_line')}")
                  if len(c) == 1 else "" for _, c in matches]
    counts = Counter(identity for identity in identities if identity)
    result = []
    for row, (method, candidates), identity in zip(evidence, matches, identities):
        p = candidates[0] if len(candidates) == 1 else {}
        errors = validate_evidence(row, snapshot, clubs)
        source = str(p.get("club_id", row.get("from_club_id", "")))
        target = row.get("to_club_id", "")
        old, new = clubs.get(source, {}), clubs.get(target, {})
        scope = row.get("league", "")
        if scope not in scope_keys or not (old.get("league") or new.get("league")):
            errors.append("No verified covered-club relationship; review real league membership")
        if method not in {"FIFA_ID", "DOB_NAME"}:
            errors.append(f"Identity: {method}")
        if counts[identity] > 1:
            errors.append("Duplicate/conflicting evidence for the same identity")
        if p and source != row.get("from_club_id") and source != target:
            errors.append("Origin disagrees with installed ownership")
        kind = row.get("transfer_type", "")
        classification = {"RELEASED": "FREE_AGENT", "RETIRED": "RETIRED",
                          "LOAN_RETURN": "LOAN_RETURN", "LOAN": "LOAN_IN"}.get(kind, "TRANSFER_IN")
        if old.get("league") and not new.get("league"):
            classification = "LOAN_OUT" if kind == "LOAN" else classification if kind in {"RELEASED", "RETIRED"} else "TRANSFER_OUT"
        if p and source == target:
            classification = "UNCHANGED"
        if method in {"AMBIGUOUS", "MISSING_FROM_FM"}:
            classification = method
        if counts[identity] > 1:
            classification = "DUPLICATE"
        if p and json.loads(p.get("starting_conditions") or "[]"):
            # Native semantics must reconcile loan/future-transfer/retirement conditions.
            errors.append("Existing starting conditions require native semantic review")
        metadata_changed = p and any(row.get(key) and str(row[key]) != str(p.get(key, ""))
                                    for key in ("contract_until", "shirt_number"))
        if classification == "UNCHANGED" and kind in {"LOAN", "LOAN_RETURN"}:
            errors.append("Unchanged club does not prove loan ownership/status is unchanged")
        action = ("REVIEW_REQUIRED" if errors else "NO_CHANGE"
                  if classification == "UNCHANGED" and not metadata_changed else "PROPOSE_NATIVE_CHANGE")
        result.append({**row, "club": new.get("club", old.get("club", "")),
                       "fm_id": p.get("fm_id", ""), "fifa_id": p.get("fifa_id", row.get("fifa_id", "")),
                       "old_club": old.get("club", "FREE_AGENT" if source == "0" else source),
                       "new_club": new.get("club", "FREE_AGENT" if target == "0" else target),
                       "classification": classification, "database_action": action,
                       "reason": "; ".join(errors) or f"Identity confirmed by {method}; no game files written"})
    return result


def run(export_dir: Path, evidence_file: Path, output: Path, snapshot: str, scope: Path) -> dict:
    date = dt.date.fromisoformat(snapshot)
    config = json.loads(scope.read_text(encoding="utf-8"))
    if date < dt.date.fromisoformat(config["minimum_snapshot_date"]) or date > dt.date.today():
        raise ValueError("Snapshot must be within the requested date range, not in the future")
    players, clubs = read_csv(export_dir / "players.csv"), read_csv(export_dir / "clubs.csv")
    rows = plan(players, clubs, read_csv(evidence_file), date,
                {c["key"] for c in config["competitions"]})
    write_csv(output / "TRANSFER_DIFF.csv", FIELDS, rows)
    for filename, kinds in [("UNMATCHED_PLAYERS.csv", {"MISSING_FROM_FM"}),
                            ("AMBIGUOUS_MATCHES.csv", {"AMBIGUOUS", "DUPLICATE"})]:
        write_csv(output / filename, FIELDS, (r for r in rows if r["classification"] in kinds))
    write_csv(output / "DATA_WARNINGS.csv", FIELDS, (r for r in rows if r["database_action"] == "REVIEW_REQUIRED"))
    manifest = {"DATABASE_SNAPSHOT_DATE": snapshot, "status": "RECONCILIATION_ONLY_NOT_RELEASE_READY",
                "evidence_sha256": sha256(evidence_file), "player_export_sha256": sha256(export_dir / "players.csv"),
                "club_export_sha256": sha256(export_dir / "clubs.csv"), "records": len(rows),
                "actions": dict(Counter(r["database_action"] for r in rows)),
                "coverage": "Evidence records only; absence from evidence never means departure",
                "production_database_written": False}
    write_json(output / "reconciliation.json", manifest)
    return manifest
