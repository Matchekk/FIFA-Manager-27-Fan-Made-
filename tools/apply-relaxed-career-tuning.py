"""Apply a guarded, reversible relaxed-career parameter profile.

Only isolated runtimes below this repository's runtime directory are accepted.
Every replacement is exact, all changed files are backed up and hash-verified,
and the protected FIFA Manager installation is checked before and after writing.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLATION = Path(r"C:\Fifa Manager 13\FUSSBALL MANAGER 13")
DEFAULT_PROFILE = ROOT / "data" / "parameter-tuning" / "relaxed-career-v1.json"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024**2), b""):
            digest.update(chunk)
    return digest.hexdigest()


def save(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def newline_for(text: str) -> str:
    return "\r\n" if "\r\n" in text else "\n"


def protected_hashes(relative_files: list[Path]) -> dict[str, str]:
    paths = {
        "Manager.exe": INSTALLATION / "Manager.exe",
        "database/Master.dat": INSTALLATION / "database" / "Master.dat",
    }
    for relative in relative_files:
        paths[relative.as_posix()] = INSTALLATION / relative
    return {name: sha(path) for name, path in paths.items()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", required=True, type=Path)
    parser.add_argument("--backup", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    args = parser.parse_args()

    runtime = args.runtime.resolve()
    backup = args.backup.resolve()
    report_path = args.report.resolve()
    profile_path = args.profile.resolve()
    expected_runtime_root = (ROOT / "runtime").resolve()
    expected_report_root = (ROOT / "reports" / "local").resolve()
    if not runtime.is_relative_to(expected_runtime_root):
        raise ValueError("runtime must stay inside the project runtime directory")
    if not (runtime / "Manager.exe").is_file():
        raise ValueError("isolated runtime Manager.exe is missing")
    if not backup.is_relative_to(expected_report_root) or not report_path.is_relative_to(expected_report_root):
        raise ValueError("backup and report must stay inside reports/local")
    if backup.exists() or report_path.exists():
        raise ValueError("exclusive new backup and report paths are required")

    profile = json.loads(profile_path.read_text(encoding="utf-8-sig"))
    relative_files = [Path(value) for value in profile["files"]]
    original_before = protected_hashes(relative_files)
    staged: dict[Path, bytes] = {}
    file_reports: list[dict] = []

    for relative, patches in zip(relative_files, profile["files"].values(), strict=True):
        target = runtime / relative
        if not target.is_file():
            raise FileNotFoundError(target)
        raw = target.read_bytes()
        text = raw.decode("cp1252")
        newline = newline_for(text)
        patch_reports: list[dict] = []
        for patch in patches:
            before = patch["before"].replace("\n", newline)
            after = patch["after"].replace("\n", newline)
            before_count = text.count(before)
            after_count = text.count(after)
            if before_count == 1:
                text = text.replace(before, after, 1)
                patch_reports.append({"id": patch["id"], "status": "APPLIED"})
            elif before_count == 0 and after_count == 1:
                patch_reports.append({"id": patch["id"], "status": "ALREADY_APPLIED"})
            else:
                raise ValueError(
                    f"{relative.as_posix()}:{patch['id']} expected one source or one applied target; "
                    f"found source={before_count}, target={after_count}"
                )
        patched = text.encode("cp1252")
        if relative.name == "Difficulty Levels.txt":
            begins = sum(1 for line in text.splitlines() if line.startswith("BEGIN("))
            ends = sum(1 for line in text.splitlines() if line.strip() == "END")
            if begins != ends:
                raise RuntimeError(f"unbalanced Difficulty Levels blocks: BEGIN={begins}, END={ends}")
        staged[relative] = patched
        file_reports.append(
            {
                "file": relative.as_posix(),
                "before_sha256": sha(target),
                "changed": patched != raw,
                "patches": patch_reports,
            }
        )

    changed = [relative for relative, data in staged.items() if data != (runtime / relative).read_bytes()]
    written: list[Path] = []
    if changed:
        backup.mkdir(parents=True)
        for relative in changed:
            source = runtime / relative
            destination = backup / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            if sha(source) != sha(destination):
                raise RuntimeError(f"backup hash mismatch: {relative.as_posix()}")

        try:
            for relative in changed:
                target = runtime / relative
                temporary = target.with_name(target.name + ".relaxed-new")
                if temporary.exists():
                    raise RuntimeError(f"unexpected temporary file: {temporary}")
                temporary.write_bytes(staged[relative])
                os.replace(temporary, target)
                if target.read_bytes() != staged[relative]:
                    raise RuntimeError(f"runtime verification failed: {relative.as_posix()}")
                written.append(relative)
        except Exception:
            for relative in written:
                shutil.copy2(backup / relative, runtime / relative)
            raise

    original_after = protected_hashes(relative_files)
    if original_before != original_after:
        for relative in written:
            shutil.copy2(backup / relative, runtime / relative)
        raise RuntimeError("protected original installation changed; runtime changes rolled back")

    for row in file_reports:
        relative = Path(row["file"])
        row["after_sha256"] = sha(runtime / relative)
    if changed:
        backup_manifest = {
            "profile": profile["profile"],
            "runtime": str(runtime),
            "files": [
                {"file": relative.as_posix(), "sha256": sha(backup / relative)} for relative in changed
            ],
        }
        save(backup / "BACKUP.json", backup_manifest)
    report = {
        "status": "PASS" if changed else "PASS_ALREADY_APPLIED",
        "profile": profile["profile"],
        "profile_sha256": sha(profile_path),
        "runtime": str(runtime),
        "applied_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "restart_required": bool(profile.get("restart_required", True)),
        "changed_files": len(changed),
        "backup": str(backup) if changed else None,
        "files": file_reports,
        "original_install_modified": False,
        "original_install_hashes": original_after,
    }
    save(report_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
