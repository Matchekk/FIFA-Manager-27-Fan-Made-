"""Read-only inventory. No graphics decoding, launch, or save inspection."""
import datetime as dt
import json
import os
import shutil
import subprocess
from collections import Counter
from pathlib import Path

from . import pe
from .common import external_output, sha256, write_csv, write_json

SKIP = {".git", "__pycache__", "saves", "savegames"}
RELEVANT = {".exe", ".dll", ".asi", ".ini", ".par", ".ucpsc"}


def windows_metadata(root: Path) -> dict:
    script = Path(__file__).resolve().parents[2] / "tools" / "hardware.ps1"
    result = subprocess.run(
        [shutil.which("pwsh") or "powershell.exe", "-NoProfile", "-File", str(script), "-GameRoot", str(root)],
        capture_output=True, text=True, encoding="utf-8", timeout=60, check=True,
    )
    return json.loads(result.stdout.lstrip("\ufeff"))


def run(root: Path, output: Path) -> dict:
    root = root.resolve(strict=True)
    output = external_output(output, root)
    if not (root / "Manager.exe").is_file():
        raise ValueError("Manager.exe missing from supplied installation")
    manifest, components, categories, errors = [], [], Counter(), []
    for current, directories, files in os.walk(root, followlinks=False):
        directories[:] = sorted(d for d in directories if d.lower() not in SKIP
                                and not (Path(current) / d).is_junction()
                                and not (Path(current) / d).is_symlink())
        for name in sorted(files):
            path = Path(current) / name
            if path.is_symlink() or path.is_junction():
                continue
            if name.lower().startswith(".env"):
                continue
            relative = path.relative_to(root).as_posix()
            try:
                stat = path.stat()
                row = {"path": relative, "size": stat.st_size, "sha256": ""}
                categories[path.suffix.lower()] += 1
                is_db = relative.startswith(("database/", "database_update/"))
                if path.suffix.lower() in RELEVANT or is_db:
                    row["sha256"] = sha256(path)
                manifest.append(row)
                if path.suffix.lower() in RELEVANT:
                    component = dict(row)
                    if path.suffix.lower() in {".exe", ".dll", ".asi"}:
                        try:
                            component["pe"] = pe.inspect(path)
                        except ValueError as exc:
                            component["pe_error"] = str(exc)
                    components.append(component)
            except OSError as exc:
                errors.append({"path": relative, "error": str(exc)})
    report = {"captured_at": dt.datetime.now(dt.timezone.utc).isoformat(),
              "game_root": str(root), "file_count": len(manifest),
              "file_types": dict(categories), "components": components, "errors": errors,
              "limitations": ["Readme version is not proof of Update 1 presence/absence",
                              "File/resource versions do not establish binary patch compatibility",
                              "No save data inspected; no graphics decoded or optimized"]}
    season = root / "plugins" / "season.ini"
    if season.exists():
        report["season_ini"] = season.read_text(encoding="utf-8-sig").strip()
    try:
        report["system"] = windows_metadata(root)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        report["system_error"] = str(exc)
    write_csv(output / "installation-files.csv", ["path", "size", "sha256"], manifest)
    write_json(output / "installation.json", report)
    return report
