"""Deploy the validated Native10 external-pass1 editor DB to the isolated runtime.

The original installation is read only. Every replaced runtime file and the old
compiled Master.dat are hash-verified in an exclusive backup before mutation.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLATION = Path(r"C:\Fifa Manager 13\FUSSBALL MANAGER 13")


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024**2), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def process_guard() -> None:
    command = "if (Get-Process -Name Manager,EdManager -ErrorAction SilentlyContinue) { exit 8 }"
    result = subprocess.run(["powershell", "-NoProfile", "-Command", command], check=False)
    if result.returncode:
        raise RuntimeError("Close Manager and Editor before deploying the runtime database")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--runtime", required=True, type=Path)
    parser.add_argument("--backup", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()

    candidate = args.candidate.resolve()
    runtime = args.runtime.resolve()
    backup = args.backup.resolve()
    report_path = args.report.resolve()
    expected_runtime_root = (ROOT / "runtime").resolve()
    expected_report_root = (ROOT / "reports" / "local").resolve()
    if not runtime.is_relative_to(expected_runtime_root):
        raise ValueError("runtime must stay inside the project runtime directory")
    if not backup.is_relative_to(expected_report_root) or not report_path.is_relative_to(expected_report_root):
        raise ValueError("backup and report must stay inside reports/local")
    if backup.exists() or report_path.exists():
        raise ValueError("exclusive new backup and report paths are required")
    if not (runtime / "Manager.exe").is_file() or not (runtime / "EdManager.exe").is_file():
        raise ValueError("isolated runtime executables are missing")
    database = candidate / "write" / "database"
    if not database.is_dir() or (database / "Master.dat").exists():
        raise ValueError("candidate editor database is missing or carries a stale Master.dat")

    build = load(candidate / "BUILD.json")
    validation = load(candidate / "VALIDATION_SUMMARY.json")
    if not (build.get("write") == "PASS" and build.get("reread") == "PASS"
            and build.get("semantic_diff") == "PASS_REVALIDATED" and build.get("membership") == "PASS"):
        raise ValueError("candidate native validation gates are not PASS")
    if validation.get("status") != "PASS_WITH_TECHNICAL_BLOCKERS":
        raise ValueError("unexpected candidate validation status")
    process_guard()

    original_before = {
        "Manager.exe": sha(INSTALLATION / "Manager.exe"),
        "database/Master.dat": sha(INSTALLATION / "database" / "Master.dat"),
    }
    mappings: list[tuple[Path, Path]] = []
    for source in sorted(database.rglob("*")):
        if source.is_file():
            mappings.append((source, Path("database") / source.relative_to(database)))
    native08_overlay = ROOT / "data" / "generated" / "release-candidate" / "native08-integrated-20260912-01" / "overlay"
    for source in sorted(native08_overlay.rglob("*")):
        if source.is_file():
            mappings.append((source, source.relative_to(native08_overlay)))

    backup.mkdir(parents=True)
    changed: list[dict] = []
    backups: list[dict] = []
    seen: set[Path] = set()

    def back_up(relative: Path) -> None:
        if relative in seen:
            return
        seen.add(relative)
        target = runtime / relative
        if target.exists():
            destination = backup / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, destination)
            digest = sha(target)
            if sha(destination) != digest:
                raise RuntimeError("backup hash mismatch: " + str(relative))
            backups.append({"path": relative.as_posix(), "sha256": digest})
        else:
            backups.append({"path": relative.as_posix(), "absent": True})

    for source, relative in mappings:
        target = runtime / relative
        source_hash = sha(source)
        if target.exists() and sha(target) == source_hash:
            continue
        back_up(relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + ".native10-new")
        if temporary.exists():
            raise RuntimeError("unexpected temporary deployment file: " + str(temporary))
        shutil.copy2(source, temporary)
        if sha(temporary) != source_hash:
            raise RuntimeError("temporary copy hash mismatch: " + str(relative))
        os.replace(temporary, target)
        if sha(target) != source_hash:
            raise RuntimeError("deployed file hash mismatch: " + str(relative))
        changed.append({"path": relative.as_posix(), "sha256": source_hash})

    master_relative = Path("database") / "Master.dat"
    master = runtime / master_relative
    back_up(master_relative)
    if master.exists():
        master.unlink()
    if master.exists():
        raise RuntimeError("old runtime Master.dat was not removed")

    original_after = {
        "Manager.exe": sha(INSTALLATION / "Manager.exe"),
        "database/Master.dat": sha(INSTALLATION / "database" / "Master.dat"),
    }
    if original_before != original_after:
        raise RuntimeError("original installation changed during isolated deployment")

    save(backup / "BACKUP.json", {"runtime": str(runtime), "files": backups})
    report = {
        "status": "NATIVE10_DEPLOYED_EDITOR_EXPORT_REQUIRED",
        "candidate": str(candidate),
        "runtime": str(runtime),
        "backup": str(backup),
        "deployed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "changed_files": len(changed),
        "candidate_database_files": sum(1 for p in database.rglob("*") if p.is_file()),
        "native08_overlay_files": sum(1 for p in native08_overlay.rglob("*") if p.is_file()),
        "old_master_backed_up": any(row["path"] == master_relative.as_posix() and "sha256" in row for row in backups),
        "compiled_master": "ABSENT_PENDING_EDITOR_EXPORT",
        "original_install_modified": False,
        "candidate_build_sha256": sha(candidate / "BUILD.json"),
        "candidate_validation_sha256": sha(candidate / "VALIDATION_SUMMARY.json"),
        "original_install_hashes": original_after,
        "changed": changed,
    }
    save(report_path, report)
    print(json.dumps({key: value for key, value in report.items() if key != "changed"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
