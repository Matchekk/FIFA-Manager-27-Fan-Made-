"""Resolve current transfer timelines without inferring departures from absence."""
from __future__ import annotations

import csv
import datetime as dt
import json
from collections import Counter, defaultdict
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/current/workers"
SNAPSHOT = "2026-09-12"
EVENT_PATH = ROOT / "data/current/evidence/transfer-events.csv"
QUEUE_PATH = ROOT / "reports/current/integration/review-queue.csv"
PROFILE_PATH = ROOT / "data/current/evidence/review-profiles.csv"
ALIASES_PATH = ROOT / "config/tm-club-aliases.json"
sys.path.insert(0, str(ROOT / "src"))
from fm27.transfer_timeline import canonical_events  # noqa: E402


def read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def main() -> None:
    queues = [r for r in read(QUEUE_PATH) if r.get("queue") == "TRANSFER_TIMELINE"]
    by_pid: dict[str, dict[str, str]] = {}
    for row in queues:
        by_pid.setdefault(row["player_tm_id"], row)
    queues = list(by_pid.values())
    raw_events = read(EVENT_PATH)
    events = canonical_events(raw_events, SNAPSHOT)
    by_player: defaultdict[str, list[dict[str, str]]] = defaultdict(list)
    for event in events:
        by_player[event["player_tm_id"]].append(event)
    profiles = {r["player_tm_id"]: r for r in read(PROFILE_PATH)}
    aliases = json.loads(ALIASES_PATH.read_text(encoding="utf-8"))

    fields = [
        "league", "club", "club_tm_id", "player_tm_id", "player", "dob", "fm_id", "fifa_id",
        "native_club_id", "target_club_id", "current_club_tm_id", "current_club_name",
        "current_profile_source", "current_profile_sha256", "transfer_event_id", "event_date",
        "transfer_type", "old_club_tm_id", "old_club_name", "old_native_club_id", "new_club_tm_id",
        "new_club_name", "new_native_club_id", "transaction_owner_external_club_id",
        "transaction_owner_native_club_id", "loan_end", "joined", "contract_until", "status",
        "timeline_basis", "attempts", "escalation", "event_source", "event_source_sha256",
        "roster_source", "roster_source_sha256", "history_event_ids", "provenance",
    ]
    result = []
    status_counts: Counter[str] = Counter()
    reason_counts: Counter[str] = Counter()
    for queue in sorted(queues, key=lambda r: (r["league"], r["club_tm_id"], r["player_tm_id"])):
        pid = queue["player_tm_id"]
        profile = profiles.get(pid, {})
        history = by_player.get(pid, [])
        # Event IDs are deduped by canonical_events; retain all event sequence
        # members for reviewability.  No numeric event ID is treated as a date.
        history_ids = ";".join(e["event_id"] for e in history if e.get("event_id"))
        destination_events = [
            e for e in history
            if aliases.get(e.get("new_club_tm_id", ""), {}).get("club_id") == queue.get("target_club_id", "")
        ]
        # Prefer an explicit effective date, then an event matching the current
        # profile's joined date. Undated ties remain review-required.
        selected = None
        if destination_events:
            dated = [e for e in destination_events if e.get("explicit_event_date") and e["explicit_event_date"] <= SNAPSHOT]
            if dated:
                selected = sorted(dated, key=lambda e: e["explicit_event_date"])[-1]
            elif len(destination_events) == 1:
                selected = destination_events[0]

        status = "REVIEW_REQUIRED"
        reason = "NO_CURRENT_DESTINATION_EVENT"
        basis = "NO_CURRENT_DESTINATION_EVENT_NO_DEPARTURE_INFERRED"
        owner_native = ""
        event = selected or {}
        if selected:
            reason = "CURRENT_DESTINATION_EVENT_FOUND"
            basis = "UNDATED_EVENT_PROFILE_CURRENT_CLUB"
            if len(destination_events) > 1 and not any(e.get("explicit_event_date") for e in destination_events):
                reason = "AMBIGUOUS_UNDATED_DESTINATION_SEQUENCE"
                basis = "TWO_ATTEMPTS_EXHAUSTED_UNDATED_SEQUENCE"
            elif not profile:
                reason = "CURRENT_PROFILE_REQUIRED"
                basis = "EVENT_FOUND_PROFILE_MISSING"
            elif profile.get("club_tm_id") != event.get("new_club_tm_id"):
                reason = "PROFILE_CLUB_EVENT_CONFLICT"
                basis = "EVENT_PROFILE_CLUB_CONFLICT"
            elif event.get("transfer_type") in {"PERMANENT", "FREE_TRANSFER", "FREE_AGENT"}:
                status = "CONFIRMED"
                reason = "CURRENT_DESTINATION_EVENT_AND_PROFILE_AGREE"
                basis = "CURRENT_UNDATED_PERMANENT_OR_FREE_EVENT"
            elif event.get("transfer_type") == "LOAN":
                owner_native = aliases.get(event.get("old_club_tm_id", ""), {}).get("club_id", "")
                if profile.get("loan_owner_tm_id") != event.get("old_club_tm_id") or not owner_native or not profile.get("owner_contract_until"):
                    reason = "LOAN_OWNER_OR_RETURN_DATE_UNRESOLVED"
                    basis = "TWO_ATTEMPTS_EXHAUSTED_LOAN_OWNER_END"
                else:
                    status = "CONFIRMED"
                    reason = "CURRENT_LOAN_EVENT_OWNER_AND_RETURN_DATE_AGREE"
                    basis = "CURRENT_UNDATED_LOAN_EVENT_PROFILE_OWNER_END"
            else:
                reason = "UNSUPPORTED_TRANSFER_TYPE"
                basis = "TWO_ATTEMPTS_EXHAUSTED_UNSUPPORTED_EVENT"
        attempts = "transfer-event-capture;current-profile-crosscheck"
        escalation = "" if status == "CONFIRMED" else "Sol"
        status_counts[status] += 1
        reason_counts[reason] += 1
        profile_url = profile.get("source", "")
        profile_hash = profile.get("source_sha256", "")
        roster_url = queue.get("source", "")
        roster_hash = queue.get("source_sha256", "")
        record = {field: "" for field in fields}
        record.update(
            league=queue.get("league", ""), club=queue.get("club", ""), club_tm_id=queue.get("club_tm_id", ""),
            player_tm_id=pid, player=queue.get("player", ""), dob=queue.get("dob", ""), fm_id=queue.get("fm_id", ""),
            fifa_id=queue.get("fifa_id", ""), native_club_id=queue.get("native_club_id", ""), target_club_id=queue.get("target_club_id", ""),
            current_club_tm_id=profile.get("club_tm_id", ""), current_club_name=profile.get("club", ""),
            current_profile_source=profile_url, current_profile_sha256=profile_hash,
            transfer_event_id=event.get("event_id", ""), event_date=event.get("explicit_event_date", ""),
            transfer_type=event.get("transfer_type", ""), old_club_tm_id=event.get("old_club_tm_id", ""), old_club_name=event.get("old_club", ""),
            old_native_club_id=aliases.get(event.get("old_club_tm_id", ""), {}).get("club_id", ""),
            new_club_tm_id=event.get("new_club_tm_id", ""), new_club_name=event.get("new_club", ""),
            new_native_club_id=aliases.get(event.get("new_club_tm_id", ""), {}).get("club_id", ""),
            transaction_owner_external_club_id=event.get("old_club_tm_id", ""), transaction_owner_native_club_id=owner_native,
            loan_end=profile.get("owner_contract_until", "") if event.get("transfer_type") == "LOAN" else "",
            joined=profile.get("joined", ""), contract_until=profile.get("contract_until", ""), status=status,
            timeline_basis=basis, attempts=attempts, escalation=escalation,
            event_source=event.get("source", ""), event_source_sha256=event.get("source_sha256", ""),
            roster_source=roster_url, roster_source_sha256=roster_hash, history_event_ids=history_ids,
            provenance=(f"Queue {roster_url} sha256={roster_hash}; transfer event {event.get('event_id', '') or 'none'} "
                        f"from {event.get('source', '')} sha256={event.get('source_sha256', '')}; profile {profile_url} "
                        f"sha256={profile_hash}; effective date used only when explicit, otherwise current profile/joined and "
                        f"event endpoints; {reason}; no departure inferred from roster absence."),
        )
        result.append(record)

    output_path = OUT / "timeline-resolutions.csv"
    with output_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields); writer.writeheader(); writer.writerows(result)
    meta = {
        "schema": 1, "snapshot_date": SNAPSHOT, "rows": len(result), "status_counts": dict(status_counts),
        "reason_counts": dict(reason_counts), "native_ids_are_columns": True,
        "event_source": str(EVENT_PATH.relative_to(ROOT)).replace("\\", "/"),
        "event_source_rows": len(raw_events), "canonical_event_rows": len(events),
        "profile_source": str(PROFILE_PATH.relative_to(ROOT)).replace("\\", "/"),
        "sequence_rule": "Explicit effective dates <= snapshot win; otherwise a unique current-destination undated event is bound to the current profile; multiple undated destinations remain REVIEW_REQUIRED.",
        "loan_rule": "Confirmed loans require event owner == current profile loan_owner, mapped owner native club, and current owner return/contract end; missing return-date evidence remains REVIEW_REQUIRED.",
        "absence_rule": "No current event is recorded as REVIEW_REQUIRED; roster absence never implies departure.",
        "canonical_mutation": False, "escalation": "Sol",
    }
    (OUT / "timeline-resolutions.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False))


if __name__ == "__main__": main()
