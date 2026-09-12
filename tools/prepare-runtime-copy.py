"""Create a real external copy of installed assets with a staged editor database.

Never links files, modifies the installation, or carries old database/Master.dat.
This is a local test fixture, not a redistributable release or a game-test claim.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fm27.common import sha256, write_json

p = argparse.ArgumentParser()
p.add_argument("--installation", type=Path, required=True)
p.add_argument("--candidate", type=Path, required=True)
p.add_argument("--destination", type=Path, required=True)
p.add_argument("--report", type=Path, required=True)
a = p.parse_args()
root = Path(__file__).resolve().parents[1]
installation, candidate, destination = a.installation.resolve(), a.candidate.resolve(), a.destination.resolve()
if not destination.is_relative_to(root / "runtime") or destination.exists() or a.report.exists():
    raise ValueError("Runtime copy and report must be new; runtime copy must stay in this project's runtime directory")
if not (installation / "EdManager.exe").is_file() or not (installation / "Manager.exe").is_file():
    raise ValueError("Named source is not the inspected FIFA Manager installation")
if not (candidate / "STAGING_ONLY.txt").is_file() or not (candidate / "NATIVE_BUILD_INPUTS.json").is_file():
    raise ValueError("Candidate native staging proof missing")
build = json.loads((candidate / "NATIVE_BUILD_INPUTS.json").read_text(encoding="utf-8"))
if build.get("status") != "STAGING_WRITE_COMPLETED_NOT_VALIDATED" or not build.get("immutable_inputs_unchanged"):
    raise ValueError("Candidate native write did not complete with immutable inputs")
if (candidate / "database/Master.dat").exists():
    raise ValueError("Only an editor candidate without a stale compiled Master.dat is accepted")
entries = []

def inventory(base, prefix, exclude_database=False):
    for folder, subdirs, files in os.walk(base, followlinks=False):
        current = Path(folder)
        if current == base and exclude_database:
            subdirs[:] = [name for name in subdirs if name.casefold() not in {"database", "database_update"}]
        for name in subdirs + files:
            path = current / name
            if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
                raise ValueError("Runtime source cannot contain links/junctions: " + str(path))
        for name in files:
            source = current / name
            relative = prefix / source.relative_to(base)
            entries.append((source, relative, source.stat().st_size))

inventory(installation, Path(), True)
inventory(candidate / "database", Path("database"))
total = sum(size for _, _, size in entries)
if shutil.disk_usage(root).free < total + 2 * 1024**3:
    raise ValueError("Insufficient space for a physical runtime copy plus working headroom")
report = {"status": "COPYING", "installation": str(installation), "candidate": str(candidate),
          "destination": str(destination), "started_at": dt.datetime.now(dt.timezone.utc).isoformat(),
          "planned_files": len(entries), "planned_bytes": total,
          "candidate_native_inputs_sha256": sha256(candidate / "NATIVE_BUILD_INPUTS.json"),
          "compiled_game_database": "NOT_EXPORTED", "release_ready": False, "files": {}}
report["excluded_original_database_trees"] = ["database", "database_update"]
write_json(a.report, report)
destination.mkdir(parents=True)
copied = 0
try:
    for index, (source, relative, size) in enumerate(entries, 1):
        target = destination / relative
        if not target.resolve().is_relative_to(destination):
            raise ValueError("Runtime target escaped destination")
        target.parent.mkdir(parents=True, exist_ok=True)
        stat = source.stat()
        digest = hashlib.sha256()
        with source.open("rb") as reader, target.open("xb") as writer:
            while chunk := reader.read(4 * 1024**2):
                digest.update(chunk)
                writer.write(chunk)
        after = source.stat()
        if (stat.st_size, stat.st_mtime_ns) != (after.st_size, after.st_mtime_ns) or sha256(target) != digest.hexdigest():
            raise ValueError("Runtime file changed during copy or failed verification: " + str(relative))
        report["files"][relative.as_posix()] = {"bytes": size, "sha256": digest.hexdigest(),
                                               "source": "candidate" if relative.parts[0] == "database" else "installation"}
        copied += size
        if index % 1000 == 0:
            print(json.dumps({"copied_files": index, "total_files": len(entries), "copied_bytes": copied}), flush=True)
    if (destination / "database/Master.dat").exists():
        raise ValueError("Unexpected old compiled game database in runtime copy")
    report.update(status="PHYSICAL_RUNTIME_COPY_VERIFIED_EDITOR_EXPORT_REQUIRED", copied_files=len(entries), copied_bytes=copied,
                  finished_at=dt.datetime.now(dt.timezone.utc).isoformat())
except Exception as error:
    report.update(status="FAIL", error=str(error))
    write_json(a.report, report)
    raise
write_json(a.report, report)
write_json(destination / "FM27_RUNTIME_COPY.json", {k: v for k, v in report.items() if k != "files"})
print(json.dumps({k: v for k, v in report.items() if k != "files"}))
