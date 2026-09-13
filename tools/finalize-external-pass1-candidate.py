#!/usr/bin/env python3
"""Bind the external-pass1 candidate's release gates and validation evidence."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def csv_rows(path: Path) -> int:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def csv_unique(path: Path, column: str) -> int:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return len({row[column] for row in csv.DictReader(handle)})


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--coverage", required=True, type=Path)
    parser.add_argument("--coverage-copy", required=True, type=Path)
    parser.add_argument("--coverage-summary", required=True, type=Path)
    parser.add_argument("--integration", required=True, type=Path)
    parser.add_argument("--technical-blockers", required=True, type=Path)
    parser.add_argument("--python-tests", required=True, type=Path)
    parser.add_argument("--native-tests", required=True, type=Path)
    parser.add_argument("--validation-output", type=Path)
    args = parser.parse_args()

    candidate = args.candidate.resolve()
    build_path = candidate / "BUILD.json"
    semantic_path = candidate / "semantic-diff-v2.json"
    membership_path = candidate / "membership-validation.json"
    exact_summary_path = candidate / "EXACT_CHANGE_SUMMARY.json"
    exact_diff_path = candidate / "EXACT_PLAYER_FIELD_DIFF.csv"
    provenance_path = candidate / "DELTA_PROVENANCE.csv"

    build = read_json(build_path)
    semantic = read_json(semantic_path)
    membership = read_json(membership_path)
    exact = read_json(exact_summary_path)
    coverage = read_json(args.coverage_summary)
    integration = read_json(args.integration)
    python_tests = read_json(args.python_tests)
    native_tests = read_json(args.native_tests)

    require(build["write"] == "PASS", "candidate write is not PASS")
    require(build["reread"] == "PASS", "candidate reread is not PASS")
    require(build["semantic_diff"] == "PASS_REVALIDATED", "semantic revalidation is not PASS")
    require(build["membership"] == "PASS", "candidate membership is not PASS")
    require(build["runtime_smoke"] == "NOT_RUN", "unexpected runtime smoke state")
    require(build["production_frozen"] is False, "external pass1 must remain unfrozen")
    require(semantic["status"] == "PASS_NATIVE10_EXACT_SEMANTIC_DELTA", "semantic diff failed")
    require(semantic["checks"]["exact_changed_players"]["actual"] == 542, "unexpected changed-player count")
    require(semantic["checks"]["created_players"]["actual"] == 57, "unexpected created-player count")
    require(semantic["checks"]["unplanned_stable_semantics"]["opaque_serialization_rewrites"] == 0,
            "unexpected opaque serialization rewrites")
    require(membership["status"] == "PASS" and membership["leagues_pass"] == membership["leagues_total"] == 12,
            "league membership validation failed")
    require(exact["status"] == "PASS" and exact["existing_players_changed"] == 542 and exact["players_created"] == 57,
            "exact change summary disagrees with the candidate")
    require(coverage["clubs"] == 222, "coverage matrix must contain 222 clubs")
    require(coverage["overall"] == {"GOOD_ENOUGH": 179, "PARTIAL": 43}, "unexpected coverage totals")
    require(integration["technical_blockers"] == 55 and integration["freeze_ready"] is False,
            "unexpected technical blocker or freeze state")
    require(integration["football_web_research_performed"] is False, "football web research flag must be false")
    require(python_tests["status"] == "PASS" and python_tests["tests"] == 305,
            "Python regression report is not the expected PASS")
    require(native_tests["status"] == "PASS" and native_tests["tests"] == 127,
            "native regression report is not the expected PASS")
    require(csv_rows(args.coverage) == 222, "coverage CSV row count is not 222")
    require(sha256(args.coverage) == sha256(args.coverage_copy), "coverage CSV copies differ")
    require(csv_rows(args.technical_blockers) == 55, "technical blocker CSV row count is not 55")
    require(csv_rows(exact_diff_path) == 2131, "exact player field-diff row count is not 2131")
    require(csv_unique(exact_diff_path, "before_fm_id") == 542,
            "exact player field diff does not cover 542 unique existing players")
    require(csv_rows(provenance_path) == 599, "delta provenance row count is not 599")

    gates = {
        "status": "NATIVE_DATA_DRAFT_PASS_COVERAGE_INCOMPLETE",
        "identity_gate": "PASS_SCOPED_CREATION_AUDIT_AND_NATIVE_COMPARE",
        "identity_reason": (
            "Only identity-audited CREATE_CLEAR rows applied; ambiguous aliases remain in the technical "
            "blocker queue. Zero new opaque serialization rewrites."
        ),
        "write": "PASS",
        "reread": "PASS",
        "semantic_diff": "PASS_REVALIDATED",
        "membership": {"status": "PASS", "leagues": 12, "clubs": 222},
        "coverage": {"COMPLETE": 0, "GOOD_ENOUGH": 179, "PARTIAL": 43, "BLOCKED": 0},
        "technical_blockers": 55,
        "regression_tests": {
            "python": {"status": "PASS", "tests": 305},
            "native": {"status": "PASS", "tests": 127},
        },
        "production_freeze": False,
        "release_ready": False,
        "runtime_smoke": "NOT_RUN",
        "remaining": (
            "55 technical blocker rows, 43 PARTIAL clubs, production freeze and the completed-data "
            "runtime smoke remain open."
        ),
    }
    gates_path = candidate / "RELEASE_GATES.json"
    write_json(gates_path, gates)

    evidence = {
        "BUILD.json": build_path,
        "semantic-diff-v2.json": semantic_path,
        "membership-validation.json": membership_path,
        "EXACT_CHANGE_SUMMARY.json": exact_summary_path,
        "EXACT_PLAYER_FIELD_DIFF.csv": exact_diff_path,
        "DELTA_PROVENANCE.csv": provenance_path,
        "RELEASE_GATES.json": gates_path,
        "CLUB_COVERAGE_MATRIX.csv": args.coverage,
        "club-coverage-summary.json": args.coverage_summary,
        "integration.json": args.integration,
        "TECHNICAL_BLOCKERS.csv": args.technical_blockers,
        "AUTOMATED_TESTS.json": args.python_tests,
        "NATIVE_TESTS.json": args.native_tests,
    }
    validation = {
        "schema": 1,
        "status": "PASS_WITH_TECHNICAL_BLOCKERS",
        "candidate": candidate.name,
        "football_web_research_performed": False,
        "league_membership": {"status": "PASS", "leagues": 12, "clubs": 222},
        "coverage": {"COMPLETE": 0, "GOOD_ENOUGH": 179, "PARTIAL": 43, "BLOCKED": 0},
        "native_candidate": {
            "write": "PASS",
            "reread": "PASS",
            "semantic_diff": "PASS_REVALIDATED",
            "existing_players_changed": 542,
            "players_created": 57,
            "unexpected_serialization_rewrites": 0,
        },
        "technical_blockers": {
            "total": 55,
            "counts": integration["technical_blocker_counts"],
        },
        "regression_tests": gates["regression_tests"],
        "production_freeze": False,
        "runtime_smoke": "NOT_RUN",
        "evidence_sha256": {name: sha256(path.resolve()) for name, path in sorted(evidence.items())},
    }
    write_json(candidate / "VALIDATION_SUMMARY.json", validation)
    if args.validation_output:
        args.validation_output.parent.mkdir(parents=True, exist_ok=True)
        write_json(args.validation_output, validation)
    print(json.dumps(validation, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
