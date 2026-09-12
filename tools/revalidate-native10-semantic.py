#!/usr/bin/env python3
"""Revalidate existing Native10 before/reread exports with a versioned validator.

This never edits BUILD.json, frozen inputs, or a native database.  It snapshots
the replacement validator and binds its report to complete before/after export
inventories so an original failed validation remains intact as evidence.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inventory(path: Path) -> dict[str, str]:
    return {
        item.relative_to(path).as_posix(): sha256(item)
        for item in sorted(path.rglob("*")) if item.is_file()
    }


def save(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--label", default="semantic-v3")
    parser.add_argument("--validator", type=Path, default=ROOT / "tools/native10-semantic-diff.py")
    parser.add_argument("--rewrite-auditor", type=Path,
                        default=ROOT / "tools/audit-native10-player-rewrites.py")
    args = parser.parse_args()
    candidate = args.candidate.resolve()
    if not args.label or any(char not in "abcdefghijklmnopqrstuvwxyz0123456789-" for char in args.label):
        raise ValueError("label must be a lowercase safe leaf")
    build_path = candidate / "BUILD.json"
    before = candidate / "write/before"
    after = candidate / "reread"
    inputs = candidate / "inputs"
    for required in (build_path, before / "native_player_semantics.csv",
                     after / "native_player_semantics.csv", inputs / "squad.csv",
                     inputs / "native10-semantic-diff.py", args.validator, args.rewrite_auditor):
        if not required.is_file():
            raise ValueError(f"missing revalidation input: {required}")

    original_build_bytes = build_path.read_bytes()
    original_build = json.loads(original_build_bytes.decode("utf-8-sig"))
    if original_build.get("write") != "PASS" or original_build.get("reread") != "PASS":
        raise ValueError("candidate does not contain a completed write and reread")

    output = candidate / "revalidation" / args.label
    if output.exists():
        raise ValueError("exclusive new revalidation directory required")
    output.mkdir(parents=True)
    validator = output / "native10-semantic-diff.py"
    shutil.copy2(args.validator, validator)
    auditor = output / "audit-native10-player-rewrites.py"
    shutil.copy2(args.rewrite_auditor, auditor)
    source_dir = output / "source"
    source_dir.mkdir()
    database_source = ROOT / "upstream/fifam/fmapi/FifamDatabase.cpp"
    player_source = ROOT / "upstream/fifam/fmapi/FifamPlayer.cpp"
    shutil.copy2(database_source, source_dir / database_source.name)
    shutil.copy2(player_source, source_dir / player_source.name)
    before_inventory_path = output / "before-inventory.json"
    after_inventory_path = output / "after-inventory.json"
    save(before_inventory_path, inventory(before))
    save(after_inventory_path, inventory(after))

    allowlist = output / "serialization-normalization.csv"
    audit_report = output / "serialization-normalization.json"
    base_database = Path(original_build["base"]) / "database"
    audit_command = [sys.executable, str(auditor),
        "--before-semantics", str(before / "native_player_semantics.csv"),
        "--after-semantics", str(after / "native_player_semantics.csv"),
        "--before-database", str(base_database), "--after-database", str(candidate / "write/database"),
        "--squad-plan", str(inputs / "squad.csv"), "--database-source", str(source_dir / database_source.name),
        "--player-source", str(source_dir / player_source.name), "--output", str(allowlist),
        "--report", str(audit_report)]
    audit_run = subprocess.run(audit_command, cwd=ROOT, text=True,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (output / "serialization-normalization.log").write_text(audit_run.stdout, encoding="utf-8")

    command = [sys.executable, str(validator), "--before", str(before), "--after", str(after),
               "--squad-plan", str(inputs / "squad.csv"),
               "--serialization-allowlist", str(allowlist),
               "--output", str(output / "semantic-diff.json")]
    negative_command = [sys.executable, str(validator), "--before", str(before), "--after", str(after),
                        "--squad-plan", str(inputs / "squad.csv"),
                        "--output", str(output / "negative-missing-allowlist.json")]
    plan_hashes = {"squad": sha256(inputs / "squad.csv")}
    for name, option in (("membership", "--membership-plan"), ("belgium", "--belgium-plan"),
                         ("creation", "--creation-plan"), ("germany", "--germany-plan")):
        path = inputs / f"{name}.csv"
        if path.is_file():
            command.extend([option, str(path)])
            negative_command.extend([option, str(path)])
            plan_hashes[name] = sha256(path)

    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(inputs / "python")
    run = (subprocess.run(command, cwd=ROOT, env=environment, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
           if audit_run.returncode == 0 else subprocess.CompletedProcess(command, 1, "audit failed; comparator not run\n"))
    (output / "semantic-diff.log").write_text(run.stdout, encoding="utf-8")
    report_path = output / "semantic-diff.json"
    report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.is_file() else None
    negative_run = (subprocess.run(negative_command, cwd=ROOT, env=environment, text=True,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                    if audit_run.returncode == 0 else
                    subprocess.CompletedProcess(negative_command, 1, "audit failed; negative control not run\n"))
    (output / "negative-missing-allowlist.log").write_text(negative_run.stdout, encoding="utf-8")
    negative_path = output / "negative-missing-allowlist.json"
    negative_report = json.loads(negative_path.read_text(encoding="utf-8")) if negative_path.is_file() else None
    negative_failed = ([key for key, value in negative_report.get("checks", {}).items()
                        if value.get("status") != "PASS"] if negative_report else [])
    negative_passed = (negative_run.returncode == 1 and
                       negative_failed == ["serialization_normalization_allowlist"])
    negative_control = {
        "status": "PASS" if negative_passed else "FAIL",
        "negative_case": "OPAQUE_REWRITES_WITHOUT_ALLOWLIST",
        "expected_returncode": 1, "actual_returncode": negative_run.returncode,
        "failed_checks": negative_failed,
        "validator_sha256": sha256(validator),
        "negative_report_sha256": sha256(negative_path) if negative_path.is_file() else None,
    }
    save(output / "STRICT_NEGATIVE_CONTROLS.json", negative_control)
    passed = (audit_run.returncode == 0 and run.returncode == 0 and report and negative_passed and
              report.get("status") == "PASS_NATIVE10_EXACT_SEMANTIC_DELTA")
    manifest = {
        "schema": 1,
        "status": "PASS" if passed else "FAIL",
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "candidate": str(candidate),
        "original_build_sha256": hashlib.sha256(original_build_bytes).hexdigest(),
        "original_build_status": original_build.get("status"),
        "original_failed_phase": original_build.get("failed_phase"),
        "original_validator_sha256": sha256(inputs / "native10-semantic-diff.py"),
        "replacement_validator_sha256": sha256(validator),
        "rewrite_auditor_sha256": sha256(auditor),
        "serialization_allowlist_sha256": sha256(allowlist) if allowlist.is_file() else None,
        "serialization_audit_sha256": sha256(audit_report) if audit_report.is_file() else None,
        "serializer_source_hashes": {
            database_source.name: sha256(source_dir / database_source.name),
            player_source.name: sha256(source_dir / player_source.name),
        },
        "validator_common_sha256": sha256(inputs / "python/fm27/common.py"),
        "before_inventory_sha256": sha256(before_inventory_path),
        "after_inventory_sha256": sha256(after_inventory_path),
        "plan_hashes": plan_hashes,
        "audit_returncode": audit_run.returncode, "returncode": run.returncode,
        "strict_negative_control": negative_control,
        "strict_negative_control_sha256": sha256(output / "STRICT_NEGATIVE_CONTROLS.json"),
        "semantic_report_sha256": sha256(report_path) if report_path.is_file() else None,
        "original_artifacts_modified": False,
        "native_process_run": False,
    }
    save(output / "REVALIDATION.json", manifest)
    print(json.dumps({"output": str(output), "status": manifest["status"],
                      "validator_sha256": manifest["replacement_validator_sha256"],
                      "semantic_report_sha256": manifest["semantic_report_sha256"]}))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
