#!/usr/bin/env python3
"""Annotate the current blocking queue with its concrete remaining prerequisite."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--undisclosed-contracts", type=Path, required=True)
    parser.add_argument("--typed-review", type=Path, required=True)
    parser.add_argument("--creation-review", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args()

    review = [row for row in read_rows(args.review) if row.get("blocking", "").upper() == "YES"]
    policy_contracts = {row["fm_id"] for row in read_rows(args.undisclosed_contracts)}
    typed = {row["fm_id"]: row for row in read_rows(args.typed_review)}
    creations = {row["player_tm_id"]: row for row in read_rows(args.creation_review)}

    annotated: list[dict[str, str]] = []
    for row in review:
        queue = row["queue"]
        fm_id = row.get("fm_id", "")
        player_tm_id = row.get("player_tm_id", "")
        if queue == "CONTRACT_CHRONOLOGY" and fm_id in policy_contracts:
            state = "POLICY_DECISION_PENDING"
            prerequisite = "Authorized provisional contract end or newly sourced exact end"
        elif queue == "CONTRACT_CHRONOLOGY":
            state = "SOURCE_CHRONOLOGY_UNRESOLVED"
            prerequisite = "Reliable current transfer type and noncontradictory contract chronology"
        elif queue == "TRANSFER_TIMELINE":
            state = "TARGETED_SOURCE_ATTEMPTS_EXHAUSTED"
            prerequisite = "Explicit transaction or current loan owner/end evidence"
        elif queue == "TIMELINE_RESOLUTION":
            state = "OWNERSHIP_CHAIN_UNPROVEN"
            prerequisite = "Explicit acquisition and onward-loan ownership chain"
        elif queue == "TYPED_CONDITION":
            detail = typed.get(fm_id, {})
            category = detail.get("blocker_category", "TYPED_CONDITION_EVIDENCE_MISSING")
            state = category
            prerequisite = {
                "CURRENT_OWNER_OR_TERMINAL_EVENT_UNPROVEN": "Current owner or explicit terminal loan event",
                "NATIVE_CONDITION_TYPE_NOT_EXPORTED": "Exact native protected-condition subtype export",
                "OWNER_CONTRACT_END_UNPROVEN": "Reliable owner contract end",
                "OWNER_NATIVE_MAPPING_UNPROVEN": "Unique native owner-club mapping",
            }.get(category, "Typed preserving evidence")
        elif queue == "PLAYER_CREATION":
            detail = creations.get(player_tm_id, {})
            state = detail.get("disposition", "PLAYER_CREATION_PREREQUISITE_MISSING")
            prerequisite = detail.get("reason", row.get("reason", "Creation prerequisite"))
        elif queue == "PRIMARY_EXCEPTION":
            state = "DESTINATION_UNPROVEN_AFTER_TARGETED_SEARCH"
            prerequisite = "Current destination or explicit retirement/release fact"
        elif queue == "PROFILE_CONFLICT":
            state = "EMPLOYER_AFFILIATION_UNPROVEN"
            prerequisite = "Explicit reserve-to-parent affiliation evidence"
        else:
            state = "SOURCE_EVIDENCE_UNRESOLVED"
            prerequisite = row.get("reason", "Source evidence")

        annotated.append(
            {
                **row,
                "terminal_state": state,
                "required_evidence_or_decision": prerequisite,
                "research_policy": "NO_REPEAT_WITHOUT_NEW_SOURCE_OR_POLICY",
            }
        )

    fields = list(review[0]) + ["terminal_state", "required_evidence_or_decision", "research_policy"] if review else []
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(annotated)

    queue_counts = Counter(row["queue"] for row in annotated)
    state_counts = Counter(row["terminal_state"] for row in annotated)
    summary = {
        "status": "BLOCKED_ON_EXPLICIT_EVIDENCE_OR_POLICY",
        "rows": len(annotated),
        "queue_counts": dict(sorted(queue_counts.items())),
        "terminal_state_counts": dict(sorted(state_counts.items())),
        "policy_pending_contracts": len(policy_contracts),
        "review_source_sha256": sha256(args.review),
        "undisclosed_contracts_sha256": sha256(args.undisclosed_contracts),
        "typed_review_sha256": sha256(args.typed_review),
        "creation_review_sha256": sha256(args.creation_review),
        "output_sha256": sha256(args.output),
        "research_policy": "Do not repeat exhausted searches without a new source lead or user policy decision.",
    }
    args.summary.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
