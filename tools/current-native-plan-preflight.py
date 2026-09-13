"""Offline mirror of native squad-plan guards using a same-read semantic export.

This does not write a database.  It reports every deterministically testable
row failure at once so an expensive native read is not used as a one-error
preflight loop.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import difflib
import json
import hashlib
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from fm27.common import read_csv, sha256, write_csv, write_json


def args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--plan", type=Path, required=True)
    p.add_argument("--before", type=Path, required=True,
                   help="Same-read native_player_semantics.csv")
    p.add_argument("--clubs", type=Path,
                   default=ROOT / "data/intermediate/transfer-increment-20260909-07/clubs.csv")
    p.add_argument("--creation-plan", type=Path)
    p.add_argument("--creation-identity-audit", type=Path,
                   help="Whole-plan DOB/name/nationality and loan-semantics gate")
    p.add_argument("--native-rich", type=Path,
                   default=ROOT / "data/intermediate/transfer-increment-20260909-07/players.csv")
    p.add_argument("--output", type=Path,
                   default=ROOT / "reports/current/integration/native-plan-preflight.csv")
    return p.parse_args()


def iso(value: str) -> dt.date:
    return dt.date.fromisoformat(value)


def native_date(value: str) -> dt.date | None:
    return dt.datetime.strptime(value, "%d.%m.%Y").date() if value else None


def name_key(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value).split())


def plausible_native_alias(display: str, native_name: str) -> bool:
    created = name_key(display).split()
    existing = name_key(native_name).split()
    if not created or not existing:
        return False
    joined_created, joined_existing = "".join(created), "".join(existing)
    surname = difflib.SequenceMatcher(None, created[-1], existing[-1]).ratio()
    full = difflib.SequenceMatcher(None, joined_created, joined_existing).ratio()
    return (created[-1] == existing[-1] or surname >= .78 or full >= .72
            or created[-1] in joined_existing or existing[-1] in joined_created)


def cached_source_ok(url: str, digest: str) -> bool:
    if not url.startswith("https://") or not re.fullmatch(r"[0-9a-f]{64}", digest):
        return False
    path = ROOT / "data/raw/transfermarkt" / f"{digest}.html"
    if not path.is_file():
        return False
    return hashlib.sha256(path.read_bytes()).hexdigest() == digest


def main() -> int:
    a = args()
    plan = read_csv(a.plan)
    before_rows = read_csv(a.before)
    before = {r["fm_id"]: r for r in before_rows}
    clubs = {r["club_id"] for r in read_csv(a.clubs)}
    empty_hash = Counter(r.get("future_conditions_sha256", "") for r in before_rows).most_common(1)[0][0]
    issues: list[dict] = []

    def add(row: dict, predicate: str, detail: str, severity: str = "ERROR") -> None:
        actual = before.get(row.get("fm_id", ""), {})
        issues.append({
            "fm_id": row.get("fm_id", ""), "player": actual.get("name", ""),
            "action": row.get("action", ""), "predicate": predicate,
            "severity": severity, "detail": detail,
        })

    seen: set[str] = set()
    snapshots: set[str] = set()
    for row in plan:
        ident = row.get("fm_id", "")
        actual = before.get(ident)
        if ident in seen:
            add(row, "unique_player", "duplicate fm_id")
        seen.add(ident)
        if not actual:
            add(row, "native_player", "fm_id absent from same-read export")
            continue
        if (row.get("fifa_id") != actual.get("fifa_id")
                or native_date(actual.get("dob", "")) != iso(row["dob"])
                or row.get("old_club_id") != actual.get("club_id")):
            add(row, "identity_and_old_club", "fifa, DOB, or old club differs from native")
        action = row.get("action", "SQUAD")
        free_agent, retire, shirt_only = (action == "FREE_AGENT", action == "RETIRE",
                                          action == "SHIRT_ONLY")
        preserve_protected = action == "PRESERVE_PROTECTED_SQUAD"
        move_preserve = action == "MOVE_PRESERVE_METADATA"
        replace_expired = action == "REPLACE_EXPIRED_LOAN"
        replace_active = action == "REPLACE_ACTIVE_LOAN"
        resolve_active = action == "RESOLVE_ACTIVE_LOAN"
        purchase = action == "PURCHASE_AND_LOAN"
        resolve = action in {"RESOLVE_EXPIRED_LOAN", "REPLACE_EXPIRED_LOAN",
                             "REPLACE_ACTIVE_LOAN", "RESOLVE_ACTIVE_LOAN",
                             "PURCHASE_AND_LOAN"}
        if action not in {"SQUAD", "FREE_AGENT", "RETIRE", "SHIRT_ONLY",
                          "RESOLVE_EXPIRED_LOAN", "REPLACE_EXPIRED_LOAN",
                          "REPLACE_ACTIVE_LOAN", "RESOLVE_ACTIVE_LOAN",
                          "PURCHASE_AND_LOAN", "PRESERVE_PROTECTED_SQUAD",
                          "MOVE_PRESERVE_METADATA"}:
            add(row, "action", "unsupported action")
        target = row.get("new_club_id", "")
        clubless = free_agent or retire
        if (clubless and (target != "0" or actual.get("club_id") == "0")) or (
                not clubless and target not in clubs):
            add(row, "destination", "invalid native destination for action")
        try:
            joined, until, snapshot = iso(row["joined"]), iso(row["contract_until"]), iso(row["snapshot_date"])
            snapshots.add(row["snapshot_date"])
            if ((not move_preserve and (joined > snapshot
                    or (not clubless and not shirt_only and until < snapshot)
                    or joined < iso(row["dob"]) or (not clubless and until < joined)))
                    or snapshot < dt.date(2026, 9, 8)):
                add(row, "contract_chronology", "invalid joined/end/snapshot ordering")
        except (ValueError, KeyError):
            add(row, "contract_chronology", "malformed required date")
            continue
        try:
            number = int(row.get("shirt_number", ""))
            if number < 0 or number > 99 or row.get("team_type") not in {"FIRST", "RESERVE"}:
                add(row, "team_and_number", "invalid team type or shirt number")
        except ValueError:
            add(row, "team_and_number", "shirt number is not an integer")
            number = -1
        if shirt_only:
            actual_number = (actual.get("shirt_number_reserve") if actual.get("in_reserve") == "1"
                             else actual.get("shirt_number_first"))
            if (target != actual.get("club_id") or native_date(actual.get("joined", "")) != joined
                    or native_date(actual.get("contract_until", "")) != until
                    or (row.get("team_type") == "RESERVE") != (actual.get("in_reserve") == "1")
                    or row.get("loan_owner_club_id") != "0" or row.get("loan_end")
                    or row.get("shirt_number") == actual_number):
                add(row, "shirt_only", "row changes more than native shirt or is a no-op")
        if move_preserve:
            actual_number = (actual.get("shirt_number_reserve") if actual.get("in_reserve") == "1"
                             else actual.get("shirt_number_first"))
            if (target == actual.get("club_id") or native_date(actual.get("joined", "")) != joined
                    or native_date(actual.get("contract_until", "")) != until
                    or (row.get("team_type") == "RESERVE") != (actual.get("in_reserve") == "1")
                    or row.get("loan_owner_club_id") != "0" or row.get("loan_end")
                    or row.get("shirt_number") != actual_number
                    or actual.get("loan_enabled") == "1" or actual.get("contract_loaned") == "1"):
                add(row, "move_preserve", "row changes native metadata, is a no-op, or has an active loan")
        if clubless and (until != joined - dt.timedelta(days=1) or number != 0
                         or row.get("team_type") != "FIRST"
                         or row.get("loan_owner_club_id") != "0" or row.get("loan_end")):
            add(row, "clubless", "invalid free-agent/retirement contract reset")
        native_loan = actual.get("loan_enabled") == "1"
        native_retire = actual.get("retirement_enabled") == "1"
        native_future = actual.get("future_conditions_sha256", empty_hash) != empty_hash
        if preserve_protected:
            condition = [row.get("protected_condition_type", "")] + [
                row.get(f"protected_condition_param{i}", "") for i in range(5)]
            if (condition[0] not in {"1", "2", "7"} or
                    any(not value.isdigit() for value in condition) or
                    actual.get("protected_conditions_sha256", empty_hash) == empty_hash or
                    native_loan or native_retire or native_future):
                add(row, "protected_condition_precondition",
                    "unsupported/missing protected condition or conflicting native condition")
        elif any(row.get(field, "") for field in ["protected_condition_type"] + [
                f"protected_condition_param{i}" for i in range(5)]):
            add(row, "protected_condition_fields", "protected fields on unrelated action")
        if not shirt_only and not preserve_protected and not move_preserve and (native_retire or (native_loan and not resolve) or native_future):
            add(row, "existing_conditions", "unhandled retirement, loan, or future condition")
        if resolve:
            if not native_loan:
                add(row, "typed_loan", "typed action has no enabled native loan")
            previous_matches = (
                row.get("previous_loan_owner_club_id") == actual.get("loan_owner_club_id")
                and native_date(actual.get("loan_start", "")) == iso(row["previous_loan_start"])
                and native_date(actual.get("loan_end", "")) == iso(row["previous_loan_end"])
                and row.get("previous_loan_buy_option") == actual.get("loan_buy_option"))
            if not previous_matches:
                add(row, "typed_loan_precondition", "previous owner/start/end/option differs from native")
            previous_end = iso(row["previous_loan_end"])
            if ((replace_active or resolve_active) and previous_end < snapshot) or (
                    not (replace_active or resolve_active) and previous_end >= snapshot):
                add(row, "typed_loan_phase", "active/expired action disagrees with prior loan end")
            evidenced_early_switch = (row.get("loan_owner_club_id") ==
                row.get("previous_loan_owner_club_id") and actual.get("club_id") != target
                and joined >= iso(row["previous_loan_start"]))
            if replace_expired and (row.get("loan_owner_club_id") == "0" or (
                    joined < previous_end and not (
                        (actual.get("club_id") == target and joined == iso(row["previous_loan_start"]))
                        or evidenced_early_switch))):
                add(row, "successor_loan", "expired successor overlaps or lacks owner")
            if replace_active and (row.get("loan_owner_club_id") == "0"
                                   or joined < iso(row["previous_loan_start"]) or joined > snapshot):
                add(row, "successor_loan", "active successor chronology invalid")
            if resolve_active and (row.get("loan_owner_club_id") != "0" or row.get("loan_end")):
                add(row, "active_resolution", "resolution also attempts successor loan")
        elif any((row.get("previous_loan_owner_club_id") != "0",
                  row.get("previous_loan_start"), row.get("previous_loan_end"),
                  row.get("previous_loan_buy_option") != "0")):
            add(row, "previous_loan_fields", "previous-loan fields on unrelated action")
        owner = row.get("loan_owner_club_id", "0")
        if owner != "0":
            if owner not in clubs or owner == target:
                add(row, "loan_owner", "owner missing or identical to borrower")
            try:
                loan_end = iso(row["loan_end"])
                if loan_end < snapshot or loan_end < joined or until < loan_end:
                    add(row, "loan_chronology", "loan/owner dates conflict")
            except ValueError:
                add(row, "loan_chronology", "missing or malformed loan end")
            if not (replace_expired or replace_active or purchase) and actual.get("club_id") not in {owner, target}:
                add(row, "loan_baseline", "native club is neither owner nor borrower")
        elif row.get("loan_end"):
            add(row, "loan_end", "loan end present without owner")
        seller = row.get("acquisition_seller_club_id", "0")
        event = row.get("acquisition_event_key", "")
        acquisition_date = row.get("acquisition_date", "")
        acquisition_source = row.get("acquisition_source", "")
        acquisition_hash = row.get("acquisition_source_sha256", "")
        if purchase:
            if (owner == "0" or not event or not acquisition_source.startswith("https://")
                    or len(acquisition_hash) != 64 or seller not in clubs or seller == owner
                    or seller != actual.get("club_id")):
                add(row, "purchase_and_loan", "seller, owner, event, or evidence invalid")
        elif (seller != "0" or acquisition_source or acquisition_hash
              or (event and not event.isdigit())):
            add(row, "acquisition_evidence", "unsupported acquisition evidence")
        if acquisition_date:
            try:
                event_date = iso(acquisition_date)
                if event_date < iso(row["dob"]) or event_date > joined:
                    add(row, "acquisition_date", "event date outside DOB/joined interval")
            except ValueError:
                add(row, "acquisition_date", "malformed acquisition date")
        # The export cannot distinguish an allowed injury/league ban from a
        # disallowed ban-until condition. Preserve this as an explicit warning.
        if (not shirt_only and not preserve_protected and not move_preserve and actual.get("protected_conditions_sha256", empty_hash) != empty_hash
                and not native_loan and not native_retire and not native_future):
            add(row, "protected_condition_detail",
                "non-future protected condition requires native guard confirmation", "WARNING")

    creation = read_csv(a.creation_plan) if a.creation_plan else []
    if creation:
        rich = read_csv(a.native_rich)
        audit_rows = read_csv(a.creation_identity_audit) if a.creation_identity_audit else []
        audit_decisions: dict[str, set[str]] = {}
        for audit_row in audit_rows:
            audit_decisions.setdefault(audit_row.get("player_tm_id", ""), set()).add(
                audit_row.get("decision", ""))
        existing_tm = {r.get("transfermarkt_id", "") for r in rich
                       if r.get("transfermarkt_id", "") not in {"", "0"}}
        existing_fifa = {r.get("fifa_id", "") for r in before_rows
                         if r.get("fifa_id", "") not in {"", "0"}}
        existing_name_dob = {(name_key(r.get("name", "")), native_date(r.get("dob", "")))
                             for r in before_rows}
        create_ids: set[str] = set()
        create_tm: set[str] = set()
        create_names: set[tuple[str, dt.date]] = set()
        positions = {"GK", "LB", "CB", "RB", "DM", "LM", "CM", "RM",
                     "AM", "LW", "RW", "CF", "ST"}
        for row in creation:
            ident, tm_id = row.get("fm_id", ""), row.get("player_tm_id", "")
            display = row.get("pseudonym") or " ".join(
                v for v in (row.get("first_name", ""), row.get("last_name", "")) if v)
            pseudo = {"fm_id": ident, "action": "CREATE"}
            if audit_decisions.get(tm_id) != {"CREATE_CLEAR"}:
                add(pseudo, "create_identity_audit",
                    "creation lacks a unique CREATE_CLEAR whole-corpus identity/loan audit decision")
            if (not ident.isdigit() or ident == "0" or ident in before or ident in create_ids):
                add(pseudo, "create_fm_id", "missing, existing, or repeated creation fm_id")
            create_ids.add(ident)
            if (not tm_id.isdigit() or tm_id == "0" or tm_id in existing_tm or tm_id in create_tm):
                add(pseudo, "create_tm_id", "missing, existing, or repeated Transfermarkt id")
            create_tm.add(tm_id)
            if row.get("fifa_id") != "0" or row.get("fifa_id") in existing_fifa:
                add(pseudo, "create_fifa_id", "creation FIFA id must be zero")
            try:
                dob, joined, until, snapshot = (iso(row["dob"]), iso(row["joined"]),
                                                iso(row["contract_until"]), iso(row["snapshot_date"]))
                if joined < dob or joined > snapshot or until < snapshot:
                    add(pseudo, "create_chronology", "DOB/joined/end/snapshot ordering invalid")
            except (ValueError, KeyError):
                add(pseudo, "create_chronology", "malformed required date")
                continue
            candidate = (name_key(display), dob)
            if not candidate[0] or candidate in existing_name_dob or candidate in create_names:
                add(pseudo, "create_name_dob", "empty or duplicate normalized name and DOB")
            create_names.add(candidate)
            nations = {row.get("nationality1", "")}
            if row.get("nationality2") not in {"", "0"}:
                nations.add(row["nationality2"])
            plausible = [native for native in rich
                         if native.get("dob") == row.get("dob")
                         and native.get("nationality") in nations
                         and plausible_native_alias(display,
                             native.get("common_name") or native.get("name", ""))]
            if plausible:
                add(pseudo, "create_native_alias_candidate",
                    "plausible Native08 DOB/name/nationality identities: " +
                    "|".join(native.get("fm_id", "") for native in plausible[:10]))
            try:
                nation1, nation2, shirt, seed = (int(row["nationality1"]), int(row["nationality2"]),
                                                 int(row["shirt_number"]), int(row["rating_seed"]))
                if not 1 <= nation1 <= 207 or not 0 <= nation2 <= 207:
                    add(pseudo, "create_nationality", "unsupported native country id")
                if not 0 <= shirt <= 99 or not 35 <= seed <= 60:
                    add(pseudo, "create_defaults", "shirt or conservative rating seed out of bounds")
            except (ValueError, KeyError):
                add(pseudo, "create_defaults", "non-numeric bounded default")
            if (row.get("club_id") not in clubs or row.get("team_type") not in {"FIRST", "RESERVE"}
                    or row.get("position") not in positions):
                add(pseudo, "create_native_fields", "club, team, or position unsupported")
            if (len(row.get("first_name", "")) > 15 or not row.get("last_name", "")
                    or len(row.get("last_name", "")) > 19 or len(row.get("pseudonym", "")) > 29):
                add(pseudo, "create_name_fields", "native name field missing or too long")
            if (row.get("status") != "CONFIRMED" or row.get("snapshot_date") != "2026-09-12"
                    or not cached_source_ok(row.get("source", ""), row.get("source_sha256", ""))):
                add(pseudo, "create_source", "unconfirmed/stale creation or uncached source")
    if len(snapshots) > 1:
        issues.append({"fm_id": "", "player": "", "action": "", "predicate": "snapshot",
                       "severity": "ERROR", "detail": "mixed snapshot dates"})

    a.output.parent.mkdir(parents=True, exist_ok=True)
    fields = ["fm_id", "player", "action", "predicate", "severity", "detail"]
    write_csv(a.output, fields, issues)
    errors = [r for r in issues if r["severity"] == "ERROR"]
    report = {
        "status": "PASS" if not errors else "FAIL", "plan": str(a.plan.resolve()),
        "plan_sha256": sha256(a.plan), "before": str(a.before.resolve()),
        "before_sha256": sha256(a.before), "plan_rows": len(plan),
        "native_rows": len(before), "creation_rows": len(creation), "errors": len(errors),
        "warnings": sum(r["severity"] == "WARNING" for r in issues),
        "error_counts": dict(sorted(Counter(r["predicate"] for r in errors).items())),
        "empty_conditions_sha256": empty_hash,
    }
    write_json(a.output.with_suffix(".json"), report)
    print(json.dumps(report, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
