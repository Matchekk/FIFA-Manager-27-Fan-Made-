"""Apply the guarded FM27 relaxed QoL parameter profile.

The tool supports exact text replacements and two narrowly scoped numeric
transformations for construction price/time tables. It only writes to an
isolated project runtime, creates byte-for-byte backups, verifies rereads and
confirms that the protected FIFA Manager installation stays unchanged.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLATION = Path(r"C:\Fifa Manager 13\FUSSBALL MANAGER 13")
DEFAULT_PROFILE = ROOT / "data" / "parameter-tuning" / "relaxed-qol-v2.json"


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


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


def scaled(value: int, factor: float, minimum: int) -> int:
    if value == 0:
        return 0
    return max(minimum, int(value * factor + 0.5))


def apply_structured(text: str, specification: dict) -> tuple[str, list[dict]]:
    marker = specification["marker"]
    if marker in text:
        expected_result = specification.get("result_sha256")
        actual_result = sha_bytes(text.encode("cp1252"))
        if expected_result and actual_result != expected_result:
            raise ValueError(
                f"structured target contains the profile marker but has hash {actual_result}; "
                f"expected {expected_result}"
            )
        return text, [
            {"id": transform["id"], "status": "ALREADY_APPLIED"}
            for transform in specification["transforms"]
        ]

    reports: list[dict] = []
    for transform in specification["transforms"]:
        factor = float(transform["factor"])
        minimum = int(transform.get("minimum", 1))
        expected = int(transform["expected_matches"])
        kind = transform["kind"]
        changed = 0

        if kind == "assignment_integer_scale":
            field = re.escape(transform["field"])
            pattern = re.compile(rf"^(\s*{field}\s*=\s*)(\d+)(\s*)$", re.MULTILINE)
        elif kind == "bare_integer_scale":
            pattern = re.compile(r"^(\s*)(\d+)(\s*)$", re.MULTILINE)
        else:
            raise ValueError(f"unsupported structured transform kind: {kind}")

        def replace(match: re.Match[str]) -> str:
            nonlocal changed
            value = int(match.group(2))
            if value == 0:
                return match.group(0)
            changed += 1
            return f"{match.group(1)}{scaled(value, factor, minimum)}{match.group(3)}"

        text = pattern.sub(replace, text)
        if changed != expected:
            raise ValueError(
                f"{transform['id']} expected {expected} positive values, found {changed}"
            )
        reports.append({"id": transform["id"], "status": "APPLIED", "values_changed": changed})

    newline = newline_for(text)
    text = marker + newline + text
    return text, reports


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
    runtime_root = (ROOT / "runtime").resolve()
    report_root = (ROOT / "reports" / "local").resolve()
    if not runtime.is_relative_to(runtime_root):
        raise ValueError("runtime must stay inside the project runtime directory")
    if not (runtime / "Manager.exe").is_file():
        raise ValueError("isolated runtime Manager.exe is missing")
    if not backup.is_relative_to(report_root) or not report_path.is_relative_to(report_root):
        raise ValueError("backup and report must stay inside reports/local")
    if backup.exists() or report_path.exists():
        raise ValueError("exclusive new backup and report paths are required")

    profile = json.loads(profile_path.read_text(encoding="utf-8-sig"))
    exact_files: dict[str, list[dict]] = profile.get("files", {})
    structured_files: dict[str, dict] = profile.get("structured_files", {})
    all_names = list(exact_files) + list(structured_files)
    if len(all_names) != len(set(all_names)):
        raise ValueError("a file cannot use exact and structured transforms in the same profile")
    relative_files = [Path(value) for value in all_names]
    original_before = protected_hashes(relative_files)
    staged: dict[Path, bytes] = {}
    file_reports: list[dict] = []

    for name, patches in exact_files.items():
        relative = Path(name)
        target = runtime / relative
        raw = target.read_bytes()
        text = raw.decode("cp1252")
        newline = newline_for(text)
        patch_reports: list[dict] = []
        for patch in patches:
            before = patch["before"].replace("\n", newline)
            after = patch["after"].replace("\n", newline)
            before_count = text.count(before)
            after_count = text.count(after)
            # Check the applied form first because a numeric target such as
            # 0.96 can contain its source value (0.9) as a prefix.
            if after_count == 1:
                patch_reports.append({"id": patch["id"], "status": "ALREADY_APPLIED"})
            elif before_count == 1:
                text = text.replace(before, after, 1)
                patch_reports.append({"id": patch["id"], "status": "APPLIED"})
            else:
                raise ValueError(
                    f"{name}:{patch['id']} expected one source or one target; "
                    f"found source={before_count}, target={after_count}"
                )
        staged[relative] = text.encode("cp1252")
        file_reports.append(
            {
                "file": relative.as_posix(),
                "mode": "exact",
                "before_sha256": sha_bytes(raw),
                "patches": patch_reports,
            }
        )

    for name, specification in structured_files.items():
        relative = Path(name)
        target = runtime / relative
        raw = target.read_bytes()
        text = raw.decode("cp1252")
        marker_present = specification["marker"] in text
        if not marker_present and sha_bytes(raw) != specification["source_sha256"]:
            raise ValueError(
                f"{name} source hash mismatch: expected {specification['source_sha256']}, "
                f"found {sha_bytes(raw)}"
            )
        text, transform_reports = apply_structured(text, specification)
        staged[relative] = text.encode("cp1252")
        file_reports.append(
            {
                "file": relative.as_posix(),
                "mode": "structured",
                "before_sha256": sha_bytes(raw),
                "patches": transform_reports,
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
                temporary = target.with_name(target.name + ".qol-new")
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
        row["changed"] = relative in changed
    if changed:
        save(
            backup / "BACKUP.json",
            {
                "profile": profile["profile"],
                "runtime": str(runtime),
                "files": [
                    {"file": relative.as_posix(), "sha256": sha(backup / relative)}
                    for relative in changed
                ],
            },
        )

    report = {
        "status": "PASS" if changed else "PASS_ALREADY_APPLIED",
        "profile": profile["profile"],
        "profile_sha256": sha(profile_path),
        "runtime": str(runtime),
        "applied_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "restart_required": bool(profile.get("restart_required", True)),
        "changed_files": len(changed),
        "exact_patch_count": sum(len(value) for value in exact_files.values()),
        "structured_value_count": sum(
            patch.get("values_changed", 0)
            for row in file_reports
            for patch in row["patches"]
        ),
        "backup": str(backup) if changed else None,
        "files": file_reports,
        "original_install_modified": False,
        "original_install_hashes": original_after,
    }
    save(report_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
