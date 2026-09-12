from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "reports/current/integration/review-queue.csv"
EVENTS = ROOT / "data/current/evidence/transfer-events.csv"
PROFILE_FILES = [
    ROOT / "data/current/evidence/review-profiles.csv",
    ROOT / "data/current/workers/south-west/profiles.csv",
    ROOT / "data/current/workers/eng-ger/profiles.csv",
]
RAW_CACHE = ROOT / "data/raw/transfermarkt"
WORKER_CACHE = ROOT / "data/current/workers/eng-ger/source-cache"
OUT = ROOT / "data/current/workers/typed-condition-evidence.csv"
SUMMARY = ROOT / "data/current/workers/typed-condition-evidence.json"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def valid_hash(value: str) -> bool:
    return bool(re.fullmatch(r"[0-9a-f]{64}", value or ""))


def cached_hash_path(value: str) -> Path | None:
    if not valid_hash(value):
        return None
    for root in (RAW_CACHE, WORKER_CACHE):
        for suffix in (".html", ".json", ""):
            path = root / f"{value}{suffix}"
            if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == value:
                return path
    return None


queue_all = read_csv(QUEUE)
queue = [r for r in queue_all if r.get("queue") == "TYPED_CONDITION"]
events = read_csv(EVENTS)
profiles: dict[str, dict[str, str]] = {}
for path in PROFILE_FILES:
    for row in read_csv(path):
        profiles.setdefault(row.get("player_tm_id", ""), row)
events_by_player: dict[str, list[dict[str, str]]] = {}
for row in events:
    events_by_player.setdefault(row.get("player_tm_id", ""), []).append(row)

headers = [
    "queue",
    "league",
    "club",
    "club_tm_id",
    "player",
    "player_tm_id",
    "dob",
    "fm_id",
    "fifa_id",
    "native_club_id",
    "target_club_id",
    "identity_method",
    "profile_present",
    "current_employer_explicit",
    "profile_current_employer_tm_id",
    "profile_current_employer",
    "profile_joined",
    "profile_contract_until",
    "loan_owner_tm_id",
    "loan_owner",
    "owner_contract_until",
    "profile_source_url",
    "profile_source_sha256",
    "profile_source_status",
    "event_count",
    "event_ids",
    "event_types",
    "event_dates",
    "event_old_clubs",
    "event_new_clubs",
    "event_source_urls",
    "event_source_sha256s",
    "event_source_statuses",
    "event_evidence_status",
    "source_fields_status",
    "missing_fields",
    "escalation",
    "queue_source_url",
    "queue_source_sha256",
    "source_hash_validation",
    "snapshot_date",
]

out_rows: list[dict[str, str]] = []
for q in queue:
    pid = q.get("player_tm_id", "")
    p = profiles.get(pid, {})
    pe = events_by_player.get(pid, [])
    # Keep event evidence in source order. This preserves all return and loan
    # records without treating an event as a current owner assertion.
    def join(key: str) -> str:
        return " | ".join(dict.fromkeys(e.get(key, "") for e in pe if e.get(key, "")))

    missing = []
    required = {
        "current_employer": p.get("club_tm_id") and p.get("club"),
        "joined": p.get("joined"),
        "profile_contract_until": p.get("contract_until"),
        "loan_owner_tm_id": p.get("loan_owner_tm_id"),
        "owner_contract_until": p.get("owner_contract_until"),
        "profile_source_url": p.get("source"),
        "profile_source_sha256": p.get("source_sha256"),
    }
    for field, value in required.items():
        if not value:
            missing.append(field)

    source_hashes = [q.get("source_sha256", "")]
    if p.get("source_sha256"):
        source_hashes.append(p["source_sha256"])
    source_hashes.extend(e.get("source_sha256", "") for e in pe)
    validations = []
    for h in dict.fromkeys(h for h in source_hashes if h):
        if not valid_hash(h):
            validations.append(f"{h}:INVALID_FORMAT")
        elif cached_hash_path(h):
            validations.append(f"{h}:CACHED_BYTES_MATCH")
        else:
            validations.append(f"{h}:CACHE_UNAVAILABLE")

    row = {h: "" for h in headers}
    row.update(
        {
            "queue": q.get("queue", ""),
            "league": q.get("league", ""),
            "club": q.get("club", ""),
            "club_tm_id": q.get("club_tm_id", ""),
            "player": q.get("player", ""),
            "player_tm_id": pid,
            "dob": q.get("dob", ""),
            "fm_id": q.get("fm_id", ""),
            "fifa_id": q.get("fifa_id", ""),
            "native_club_id": q.get("native_club_id", ""),
            "target_club_id": q.get("target_club_id", ""),
            "identity_method": q.get("identity_method", ""),
            "profile_present": "YES" if p else "NO",
            "current_employer_explicit": "YES" if p.get("club_tm_id") and p.get("club") else "NO",
            "profile_current_employer_tm_id": p.get("club_tm_id", ""),
            "profile_current_employer": p.get("club", ""),
            "profile_joined": p.get("joined", ""),
            "profile_contract_until": p.get("contract_until", ""),
            "loan_owner_tm_id": p.get("loan_owner_tm_id", ""),
            "loan_owner": p.get("loan_owner", ""),
            "owner_contract_until": p.get("owner_contract_until", ""),
            "profile_source_url": p.get("source", ""),
            "profile_source_sha256": p.get("source_sha256", ""),
            "profile_source_status": p.get("source_status", "REVIEW_REQUIRED") if p else "REVIEW_REQUIRED",
            "event_count": str(len(pe)),
            "event_ids": join("event_id"),
            "event_types": join("transfer_type"),
            "event_dates": join("explicit_event_date"),
            "event_old_clubs": join("old_club"),
            "event_new_clubs": join("new_club"),
            "event_source_urls": join("source"),
            "event_source_sha256s": join("source_sha256"),
            "event_source_statuses": join("source_status"),
            "event_evidence_status": "AVAILABLE" if pe else "NO_MATCHING_TRANSFER_EVENT",
            "source_fields_status": "SUFFICIENT_OWNER_AND_CHRONOLOGY" if not missing else "MISSING_FIELDS",
            "missing_fields": " | ".join(missing),
            "escalation": "" if not missing else "Sol",
            "queue_source_url": q.get("source", ""),
            "queue_source_sha256": q.get("source_sha256", ""),
            "source_hash_validation": " | ".join(validations),
            "snapshot_date": q.get("snapshot_date", "2026-09-12"),
        }
    )
    out_rows.append(row)

with OUT.open("w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=headers)
    writer.writeheader()
    writer.writerows(out_rows)

hash_status = Counter()
hashes: dict[str, dict[str, str]] = {}
for row in out_rows:
    for token in row["source_hash_validation"].split(" | "):
        if not token:
            continue
        h, status = token.split(":", 1)
        hash_status[status] += 1
        hashes[h] = {"status": status}

summary = {
    "snapshot_date": "2026-09-12",
    "scope": "TYPED_CONDITION queue only",
    "queue_rows": len(out_rows),
    "excluded_transfer_timeline_rows": sum(r.get("queue") == "TRANSFER_TIMELINE" for r in queue_all),
    "profile_match_count": sum(r["profile_present"] == "YES" for r in out_rows),
    "source_fields_status_counts": dict(Counter(r["source_fields_status"] for r in out_rows)),
    "event_evidence_status_counts": dict(Counter(r["event_evidence_status"] for r in out_rows)),
    "missing_field_counts": dict(Counter(field for r in out_rows for field in r["missing_fields"].split(" | ") if field)),
    "escalation_count": sum(bool(r["escalation"]) for r in out_rows),
    "source_hash_validation": {
        "status_counts": dict(hash_status),
        "unique_hash_count": len(hashes),
        "hashes": hashes,
    },
    "source_files": [str(EVENTS.relative_to(ROOT)), *(str(p.relative_to(ROOT)) for p in PROFILE_FILES)],
    "production_mutation": False,
}
with SUMMARY.open("w", encoding="utf-8") as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)
    f.write("\n")
print(json.dumps({k: summary[k] for k in ("queue_rows", "excluded_transfer_timeline_rows", "profile_match_count", "source_fields_status_counts", "event_evidence_status_counts", "missing_field_counts", "escalation_count", "source_hash_validation")}, ensure_ascii=False))
