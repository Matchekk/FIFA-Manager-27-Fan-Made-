"""Bind a corrected semantic validator to an existing write/reread candidate.

This never rewrites database data or frozen candidate inputs. It accepts only a
candidate whose original failure was the superseded exact-change predicate and
records both the failed report and the corrected revalidation hashes.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from fm27.common import sha256, write_json


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--validator", type=Path,
                        default=ROOT / "tools/native10-semantic-diff.py")
    args = parser.parse_args()
    candidate = args.candidate.resolve()
    build_path = candidate / "BUILD.json"
    build = json.loads(build_path.read_text(encoding="utf-8-sig"))
    original = json.loads((candidate / "semantic-diff.json").read_text(encoding="utf-8-sig"))
    corrected = json.loads((candidate / "semantic-diff-v2.json").read_text(encoding="utf-8-sig"))
    membership = json.loads((candidate / "membership-validation.json").read_text(encoding="utf-8-sig"))

    if (build.get("status") != "FAILED" or build.get("failed_phase") != "semantic_diff"
            or build.get("write") != "PASS" or build.get("reread") != "PASS"):
        raise ValueError("Candidate is not an eligible completed write/reread semantic-only failure")
    failed = [name for name, check in original["checks"].items() if check["status"] != "PASS"]
    if original.get("status") != "FAIL" or failed != ["exact_changed_players"]:
        raise ValueError("Original failure is broader than the superseded exact-change predicate")
    if corrected.get("status") != "PASS_NATIVE10_EXACT_SEMANTIC_DELTA":
        raise ValueError("Corrected semantic validation did not pass")
    if membership.get("status") != "PASS" or membership.get("leagues_pass") != 12:
        raise ValueError("Membership validation did not pass all 12 leagues")
    for name, item in build["plans"].items():
        path = Path(item["path"])
        if not path.is_file() or sha256(path) != item["sha256"]:
            raise ValueError(f"Frozen {name} input hash changed")

    revalidation = {
        "status": "PASS",
        "reason": ("MOVE_PRESERVE_METADATA changes club-list membership while the player block may remain "
                   "byte-identical; corrected validator compares full exported player semantics including club_id."),
        "validated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "validator": str(args.validator.resolve()),
        "validator_sha256": sha256(args.validator),
        "original_semantic_diff_sha256": sha256(candidate / "semantic-diff.json"),
        "corrected_semantic_diff_sha256": sha256(candidate / "semantic-diff-v2.json"),
        "membership_validation_sha256": sha256(candidate / "membership-validation.json"),
        "exact_changed_players": corrected["checks"]["exact_changed_players"]["actual"],
        "serialized_player_blocks_changed": corrected["checks"]["exact_changed_players"]["serialized_player_blocks_changed"],
        "club_membership_only_or_byte_stable_moves": corrected["checks"]["exact_changed_players"]["club_membership_only_or_byte_stable_moves"],
        "created_players": corrected["checks"]["created_players"]["actual"],
        "opaque_serialization_rewrites": corrected["checks"]["unplanned_stable_semantics"]["opaque_serialization_rewrites"],
    }
    write_json(candidate / "SEMANTIC_REVALIDATION.json", revalidation)
    build["original_failure"] = {"phase": build.pop("failed_phase"), "error": build.pop("error"),
                                 "semantic_diff_sha256": revalidation["original_semantic_diff_sha256"]}
    build["semantic_diff"] = "PASS_REVALIDATED"
    build["semantic_diff_revalidation"] = revalidation
    build["membership"] = "PASS"
    build["status"] = "DRAFT_VALIDATED_DATA_INCOMPLETE"
    write_json(build_path, build)
    print(json.dumps({"status": build["status"], "semantic_diff": build["semantic_diff"],
                      "membership": build["membership"]}))


if __name__ == "__main__":
    main()
