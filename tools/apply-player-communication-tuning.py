"""Apply the relaxed player-communication profile to an isolated FM27 runtime.

The tool only edits the supported MORALE_AND_TRUST parameter block. It refuses
to operate on the original installation, creates a hash-verified backup, writes
atomically, and proves that the protected installation stayed unchanged.
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
DEFAULT_PROFILE = ROOT / "data" / "parameter-tuning" / "relaxed-player-communication.json"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024**2), b""):
            digest.update(chunk)
    return digest.hexdigest()


def save(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def protected_hashes() -> dict[str, str]:
    paths = {
        "Manager.exe": INSTALLATION / "Manager.exe",
        "database/Master.dat": INSTALLATION / "database" / "Master.dat",
        "fmdata/ParameterFiles/Difficulty Levels.txt": (
            INSTALLATION / "fmdata" / "ParameterFiles" / "Difficulty Levels.txt"
        ),
    }
    return {name: sha(path) for name, path in paths.items()}


def patch_section(text: str, section: str, values: dict[str, int]) -> tuple[str, dict[str, dict[str, int]]]:
    section_pattern = re.compile(
        rf"(BEGIN\(\s*{re.escape(section)}\s*\)(?P<body>.*?)^\s*END\s*$)",
        re.MULTILINE | re.DOTALL,
    )
    match = section_pattern.search(text)
    if not match:
        raise ValueError(f"MORALE_AND_TRUST section {section} was not found")

    full = match.group(1)
    body = match.group("body")
    changes: dict[str, dict[str, int]] = {}
    for key, desired in values.items():
        value_pattern = re.compile(
            rf"^(?P<prefix>[ \t]*{re.escape(key)}[ \t]*=[ \t]*)(?P<value>-?\d+)[ \t]*(?P<cr>\r?)$",
            re.MULTILINE,
        )
        hits = list(value_pattern.finditer(body))
        if len(hits) != 1:
            raise ValueError(f"expected one {section}.{key}, found {len(hits)}")
        old = int(hits[0].group("value"))
        body = value_pattern.sub(
            lambda item: item.group("prefix") + str(desired) + item.group("cr"), body, count=1
        )
        changes[key] = {"before": old, "after": desired}

    patched_full = full.replace(match.group("body"), body, 1)
    return text[: match.start(1)] + patched_full + text[match.end(1) :], changes


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
    if runtime == INSTALLATION.resolve() or INSTALLATION.resolve().is_relative_to(runtime):
        raise ValueError("the original installation is protected")
    if not backup.is_relative_to(expected_report_root) or not report_path.is_relative_to(expected_report_root):
        raise ValueError("backup and report must stay inside reports/local")
    if backup.exists() or report_path.exists():
        raise ValueError("exclusive new backup and report paths are required")
    if not (runtime / "Manager.exe").is_file():
        raise ValueError("isolated runtime Manager.exe is missing")

    profile = json.loads(profile_path.read_text(encoding="utf-8-sig"))
    relative = Path(profile["target_file"])
    target = runtime / relative
    if not target.is_file():
        raise FileNotFoundError(target)

    original_before = protected_hashes()
    before_hash = sha(target)
    raw = target.read_bytes()
    text = raw.decode("cp1252")
    marker = "BEGIN( MORALE_AND_TRUST )"
    next_marker = "BEGIN( SCOUTING )"
    start = text.find(marker)
    end = text.find(next_marker, start + len(marker))
    if start < 0 or end < 0:
        raise ValueError("unable to isolate the MORALE_AND_TRUST parameter block")

    prefix, block, suffix = text[:start], text[start:end], text[end:]
    all_changes: dict[str, dict[str, dict[str, int]]] = {}
    for section in ("EASY", "MEDIUM", "HARD"):
        block, all_changes[section] = patch_section(block, section, profile["morale_and_trust"][section])
    patched_text = prefix + block + suffix
    if re.search(r"\dEND", patched_text):
        raise RuntimeError("generated parameter text joined a value and END marker")
    for section in ("EASY", "MEDIUM", "HARD"):
        section_match = re.search(
            rf"BEGIN\(\s*{section}\s*\)(?P<body>.*?)^\s*END\s*$",
            block,
            re.MULTILINE | re.DOTALL,
        )
        if not section_match:
            raise RuntimeError(f"generated section {section} is invalid")
        for key, desired in profile["morale_and_trust"][section].items():
            value_match = re.search(
                rf"^[ \t]*{re.escape(key)}[ \t]*=[ \t]*(?P<value>-?\d+)[ \t]*\r?$",
                section_match.group("body"),
                re.MULTILINE,
            )
            if not value_match or int(value_match.group("value")) != desired:
                raise RuntimeError(f"generated value {section}.{key} is invalid")
    patched = patched_text.encode("cp1252")
    if patched == raw:
        raise ValueError("profile is already applied; no backup or mutation was made")

    backup_target = backup / relative
    backup_target.parent.mkdir(parents=True)
    shutil.copy2(target, backup_target)
    if sha(backup_target) != before_hash:
        raise RuntimeError("backup hash mismatch")

    temporary = target.with_name(target.name + ".communication-new")
    if temporary.exists():
        raise RuntimeError(f"unexpected temporary file: {temporary}")
    temporary.write_bytes(patched)
    os.replace(temporary, target)
    after_hash = sha(target)
    if target.read_bytes() != patched:
        raise RuntimeError("runtime parameter verification failed")

    original_after = protected_hashes()
    if original_before != original_after:
        raise RuntimeError("protected original installation changed")

    backup_manifest = {
        "runtime": str(runtime),
        "profile": profile["profile"],
        "file": relative.as_posix(),
        "sha256": before_hash,
    }
    save(backup / "BACKUP.json", backup_manifest)
    report = {
        "status": "PASS",
        "profile": profile["profile"],
        "runtime": str(runtime),
        "target_file": relative.as_posix(),
        "applied_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "restart_required": bool(profile.get("restart_required", True)),
        "runtime_manager_was_allowed_to_remain_open": True,
        "before_sha256": before_hash,
        "after_sha256": after_hash,
        "backup": str(backup),
        "changes": all_changes,
        "original_install_modified": False,
        "original_install_hashes": original_after,
    }
    save(report_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
