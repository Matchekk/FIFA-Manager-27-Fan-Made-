"""Publish the final evidence blockers for unresolved typed player conditions."""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from fm27.common import read_csv, sha256, write_csv, write_json


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--review", type=Path,
                   default=ROOT / "reports/current/integration/review-queue.csv")
    p.add_argument("--evidence", type=Path,
                   default=ROOT / "data/current/workers/typed-condition-evidence.csv")
    p.add_argument("--before", type=Path, required=True)
    p.add_argument("--output", type=Path,
                   default=ROOT / "reports/current/TYPED_CONDITION_REVIEW.csv")
    a = p.parse_args()
    unresolved = {r["player_tm_id"]: r for r in read_csv(a.review)
                  if r.get("queue") == "TYPED_CONDITION"}
    evidence = {r["player_tm_id"]: r for r in read_csv(a.evidence)}
    native = {r["fm_id"]: r for r in read_csv(a.before)}
    empty_hash = Counter(r.get("future_conditions_sha256", "")
                         for r in native.values()).most_common(1)[0][0]
    rows = []
    for tm_id, review in sorted(unresolved.items(), key=lambda item: int(item[0])):
        observed, actual = evidence.get(tm_id, {}), native.get(review.get("fm_id", ""), {})
        if actual.get("loan_enabled") == "1":
            if observed.get("loan_owner_tm_id") and not observed.get("owner_contract_until"):
                category = "OWNER_CONTRACT_END_UNPROVEN"
            elif not observed.get("loan_owner_tm_id"):
                category = "CURRENT_OWNER_OR_TERMINAL_EVENT_UNPROVEN"
            else:
                category = "OWNER_NATIVE_MAPPING_UNPROVEN"
        elif actual.get("future_conditions_sha256", empty_hash) != empty_hash:
            category = "FUTURE_NATIVE_CONDITION_MUST_BE_PRESERVED"
        elif actual.get("protected_conditions_sha256", empty_hash) != empty_hash:
            category = "NATIVE_CONDITION_TYPE_NOT_EXPORTED"
        else:
            category = "SOURCE_AND_NATIVE_CONDITION_DISAGREE"
        rows.append({
            "league": review.get("league", ""), "club": review.get("club", ""),
            "player": review.get("player", ""), "player_tm_id": tm_id,
            "fm_id": review.get("fm_id", ""), "native_club_id": review.get("native_club_id", ""),
            "target_club_id": review.get("target_club_id", ""),
            "native_loan_enabled": actual.get("loan_enabled", ""),
            "native_loan_owner_club_id": actual.get("loan_owner_club_id", ""),
            "native_loan_start": actual.get("loan_start", ""),
            "native_loan_end": actual.get("loan_end", ""),
            "protected_conditions_sha256": actual.get("protected_conditions_sha256", ""),
            "future_conditions_sha256": actual.get("future_conditions_sha256", ""),
            "profile_joined": observed.get("profile_joined", ""),
            "profile_contract_until": observed.get("profile_contract_until", ""),
            "profile_loan_owner_tm_id": observed.get("loan_owner_tm_id", ""),
            "profile_owner_contract_until": observed.get("owner_contract_until", ""),
            "event_types": observed.get("event_types", ""),
            "event_dates": observed.get("event_dates", ""),
            "blocker_category": category, "disposition": "HOLD_NO_SAFE_NATIVE_MUTATION",
            "source": observed.get("profile_source_url", review.get("source", "")),
            "source_sha256": observed.get("profile_source_sha256", review.get("source_sha256", "")),
            "snapshot_date": review.get("snapshot_date", ""),
        })
    fields = list(rows[0]) if rows else ["player_tm_id", "blocker_category", "disposition"]
    a.output.parent.mkdir(parents=True, exist_ok=True)
    write_csv(a.output, fields, rows)
    report = {
        "status": "EXPLICIT_EVIDENCE_BLOCKERS" if rows else "PASS",
        "rows": len(rows), "counts": dict(sorted(Counter(r["blocker_category"] for r in rows).items())),
        "review_sha256": sha256(a.review), "evidence_sha256": sha256(a.evidence),
        "native_before_sha256": sha256(a.before), "output_sha256": sha256(a.output),
        "policy": "No current owner, contract end, destination mapping, or protected condition type is invented.",
    }
    write_json(a.output.with_suffix(".json"), report)
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
