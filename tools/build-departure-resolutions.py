from __future__ import annotations

import csv
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
]
RAW_CACHE = ROOT / "data/raw/transfermarkt"
WORKER_CACHE = ROOT / "data/current/workers/eng-ger/source-cache"
OUT = ROOT / "data/current/workers/departure-resolutions.csv"
SUMMARY = ROOT / "data/current/workers/departure-resolutions.json"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def valid_hash(value: str) -> bool:
    return bool(re.fullmatch(r"[0-9a-f]{64}", value or ""))


def cached_hash_path(value: str) -> Path | None:
    """Return a cached source whose bytes hash exactly to value, if present."""
    if not valid_hash(value):
        return None
    for root in (RAW_CACHE, WORKER_CACHE):
        for suffix in (".html", ".json", ""):
            path = root / f"{value}{suffix}"
            if path.exists() and __import__("hashlib").sha256(path.read_bytes()).hexdigest() == value:
                return path
    return None


queue = [r for r in read_csv(QUEUE) if r.get("queue") == "SOURCE_ABSENCE"]
events = read_csv(EVENTS)
profiles: dict[str, dict[str, str]] = {}
for path in PROFILE_FILES:
    for row in read_csv(path):
        profiles.setdefault(row.get("player_tm_id", ""), row)

headers = [
    "queue",
    "league",
    "old_club",
    "old_club_tm_id",
    "player",
    "player_tm_id",
    "dob",
    "fm_id",
    "fifa_id",
    "native_club_id",
    "status",
    "new_club",
    "new_club_tm_id",
    "transaction_type",
    "effective_date",
    "loan_end",
    "current_contract_until",
    "owner_club_tm_id",
    "owner_contract_until",
    "event_id",
    "event_date",
    "identity_method",
    "evidence_class",
    "source_url",
    "source_sha256",
    "source_status",
    "confidence",
    "attempts",
    "targeted_profile_attempt",
    "source_hash_validation",
    "review_reason",
    "notes",
    "snapshot_date",
]

out_rows: list[dict[str, str]] = []
for q in queue:
    pid = q["player_tm_id"]
    # A departure must be an explicit Abgang from the queued club. A roster
    # absence is never used to infer one.
    candidates = [
        e
        for e in events
        if e.get("player_tm_id") == pid
        and e.get("direction") == "Abgang"
        and e.get("old_club_tm_id") == q.get("club_tm_id")
    ]
    # Use the latest event in the source order; a later row can supersede an
    # earlier loan return or intermediate entry.
    event = candidates[-1] if candidates else None
    profile = profiles.get(pid)
    source_urls: list[str] = []
    source_hashes: list[str] = []
    if event:
        source_urls.append(event.get("source", ""))
        source_hashes.append(event.get("source_sha256", ""))
    if profile and profile.get("source"):
        source_urls.append(profile["source"])
        source_hashes.append(profile.get("source_sha256", ""))

    event_cache = cached_hash_path(event.get("source_sha256", "")) if event else None
    profile_cache = cached_hash_path(profile.get("source_sha256", "")) if profile and profile.get("source_sha256") else None

    row = {h: "" for h in headers}
    row.update(
        {
            "queue": q.get("queue", ""),
            "league": q.get("league", ""),
            "old_club": (event or {}).get("old_club") or q.get("club", ""),
            "old_club_tm_id": (event or {}).get("old_club_tm_id") or q.get("club_tm_id", ""),
            "player": q.get("player", ""),
            "player_tm_id": pid,
            "dob": q.get("dob", ""),
            "fm_id": q.get("fm_id", ""),
            "fifa_id": q.get("fifa_id", ""),
            "native_club_id": q.get("native_club_id", ""),
            "identity_method": q.get("identity_method", ""),
            "source_url": " | ".join(u for u in source_urls if u),
            "source_sha256": " | ".join(h for h in source_hashes if h),
            "source_status": "CONFIRMED" if event else "REVIEW_REQUIRED",
            "attempts": "2",
            "targeted_profile_attempt": "",
            "source_hash_validation": ";".join(
                x
                for x in (
                    "EVENT_CACHED_BYTES_MATCH" if event_cache else ("EVENT_CACHE_UNAVAILABLE" if event else ""),
                    "PROFILE_CACHED_BYTES_MATCH" if profile_cache else ("PROFILE_CACHE_UNAVAILABLE" if profile else ""),
                )
                if x
            ),
            "snapshot_date": q.get("snapshot_date", "2026-09-12"),
        }
    )

    if event:
        row.update(
            {
                "new_club": event.get("new_club", ""),
                "new_club_tm_id": event.get("new_club_tm_id", ""),
                "transaction_type": event.get("transfer_type", ""),
                "event_id": event.get("event_id", ""),
                "event_date": event.get("explicit_event_date", ""),
            }
        )
        if profile:
            if profile.get("club_tm_id") == event.get("new_club_tm_id") and profile.get("club"):
                # Prefer the current profile's canonical display name when a
                # transfer capture duplicated a synthetic label (for example
                # VereinslosVereinslos).
                row["new_club"] = profile["club"]
            row["effective_date"] = profile.get("joined", "")
            row["current_contract_until"] = profile.get("contract_until", "")
            row["owner_club_tm_id"] = profile.get("loan_owner_tm_id", "")
            row["owner_contract_until"] = profile.get("owner_contract_until", "")
            if event.get("transfer_type") == "LOAN" and profile.get("club_tm_id") == event.get("new_club_tm_id"):
                # This is the current destination contract boundary, not a
                # fabricated transfer end date; the notes state its basis.
                row["loan_end"] = profile.get("contract_until", "")
            agrees = profile.get("club_tm_id") == event.get("new_club_tm_id")
            if agrees:
                row["evidence_class"] = "EXPLICIT_TRANSFER_EVENT+CURRENT_PROFILE"
                row["confidence"] = "0.99"
                row["notes"] = "Current profile agrees with explicit departure; loan_end uses destination profile contract_until when present."
            else:
                row["evidence_class"] = "EXPLICIT_TRANSFER_EVENT+PROFILE_MISMATCH"
                row["confidence"] = "0.90"
                row["notes"] = "Explicit departure is retained; current profile destination differs and requires review."
        else:
            row["evidence_class"] = "EXPLICIT_TRANSFER_EVENT"
            row["confidence"] = "0.95"
            row["notes"] = "Explicit departure event is authoritative; no matching current profile was present in the reviewed cache."

            # The four event-only rows received one targeted direct profile
            # request after the cache review. Transfermarkt returned 403 for
            # each, so no current destination/date/owner fields are inferred.
            if pid in {"353775", "374954", "1235583", "460245"}:
                row["targeted_profile_attempt"] = "DIRECT_PROFILE_URL:403_FORBIDDEN"
                row["notes"] = "Explicit departure event is authoritative; targeted current profile request returned 403, so destination date/owner fields remain blank."

        # Transfermarkt's synthetic suspension destination is not a club and
        # must not be serialized as a confirmed departure.
        if event.get("new_club_tm_id") == "2077" or "Sperre" in event.get("new_club", ""):
            row["status"] = "REVIEW_REQUIRED"
            row["source_status"] = "REVIEW_REQUIRED"
            row["confidence"] = "0.45"
            row["evidence_class"] = "INVALID_DESTINATION_RECORD"
            row["review_reason"] = "Transfer event points to synthetic suspension record (Sperre), not an identifiable destination club; absence alone cannot establish departure."
            row["notes"] = "Two attempts: explicit transfer event and current profile cache reviewed; hold for authoritative release/club evidence."
        else:
            row["status"] = "CONFIRMED"
    else:
        row.update(
            {
                "status": "REVIEW_REQUIRED",
                "source_status": "REVIEW_REQUIRED",
                "evidence_class": "CURRENT_PROFILE_RESERVE_ONLY" if profile else "ABSENCE_ONLY_NO_EXPLICIT_EVENT",
                "confidence": "0.50" if profile else "0.20",
                "review_reason": "No explicit departure/retirement/loan event from the queued club; current first-team absence is insufficient."
                if not profile
                else "Current profile shows a reserve/internal club entry but no departure event from the queued first-team club; absence is insufficient.",
                "notes": "Two attempts: transfer-event cache and current profile cache reviewed; hold for explicit authoritative departure evidence.",
            }
        )
        if profile:
            row.update(
                {
                    "new_club": profile.get("club", ""),
                    "new_club_tm_id": profile.get("club_tm_id", ""),
                    "effective_date": profile.get("joined", ""),
                    "current_contract_until": profile.get("contract_until", ""),
                    "owner_club_tm_id": profile.get("loan_owner_tm_id", ""),
                    "owner_contract_until": profile.get("owner_contract_until", ""),
                }
            )

    out_rows.append(row)

with OUT.open("w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=headers)
    w.writeheader()
    w.writerows(out_rows)

failures = []
cache_validation = {"matched": 0, "unavailable": 0, "mismatch": 0, "hashes": {}}
for row in out_rows:
    for h in (row.get("source_sha256", "").split(" | ")):
        if h and not valid_hash(h):
            failures.append({"player_tm_id": row["player_tm_id"], "hash": h})
        elif h:
            path = cached_hash_path(h)
            cache_validation["hashes"][h] = {
                "status": "CACHED_BYTES_MATCH" if path else "CACHE_UNAVAILABLE",
                "path": str(path.relative_to(ROOT)) if path else "",
            }
            cache_validation["matched" if path else "unavailable"] += 1
summary = {
    "snapshot_date": "2026-09-12",
    "scope": "SOURCE_ABSENCE queue only",
    "queue_rows": len(out_rows),
    "status_counts": dict(Counter(r["status"] for r in out_rows)),
    "evidence_class_counts": dict(Counter(r["evidence_class"] for r in out_rows)),
    "confirmed_player_tm_ids": [r["player_tm_id"] for r in out_rows if r["status"] == "CONFIRMED"],
    "review_player_tm_ids": [r["player_tm_id"] for r in out_rows if r["status"] == "REVIEW_REQUIRED"],
    "review_queue": [
        {
            "player_tm_id": r["player_tm_id"],
            "player": r["player"],
            "reason": r["review_reason"],
            "attempts": int(r["attempts"]),
        }
        for r in out_rows
        if r["status"] == "REVIEW_REQUIRED"
    ],
    "source_failures": failures,
    "source_hash_validation": cache_validation,
    "targeted_profile_attempts": [
        {
            "player_tm_id": r["player_tm_id"],
            "player": r["player"],
            "result": r["targeted_profile_attempt"],
        }
        for r in out_rows
        if r["targeted_profile_attempt"]
    ],
    "source_files": [str(EVENTS.relative_to(ROOT)), *(str(p.relative_to(ROOT)) for p in PROFILE_FILES)],
    "production_mutation": False,
}
with SUMMARY.open("w", encoding="utf-8") as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)
    f.write("\n")
print(json.dumps({k: summary[k] for k in ("queue_rows", "status_counts", "evidence_class_counts", "review_player_tm_ids", "source_failures")}, ensure_ascii=False))
