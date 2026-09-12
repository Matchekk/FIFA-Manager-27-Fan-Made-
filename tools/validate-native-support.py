"""Verify native staging support files against the actual source tree and manifest."""
import argparse
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fm27.common import read_csv, sha256, write_json

p = argparse.ArgumentParser()
p.add_argument("--database", type=Path, required=True)
p.add_argument("--candidate", type=Path, required=True)
p.add_argument("--output", type=Path, required=True)
a = p.parse_args()
database, candidate = a.database.resolve(), a.candidate.resolve()
sources = {}
for folder in ("script", "fmdata/historic"):
    directory = database.parent / folder
    if directory.exists():
        for path in directory.rglob("*"):
            if path.is_file():
                sources[path.relative_to(database.parent).as_posix()] = path
for name in ("MaleNames.txt", "FemaleNames.txt", "Surnames.txt", "AssessmentAFC.sav", "AssessmentCAF.sav",
             "CountryNames.txt", "picture.tga", "PriorityClubs.txt", "TownDataUniques.txt"):
    if (database / name).exists():
        sources["database/" + name] = database / name
manifest_path = candidate / "native_support_files.csv"
manifest = read_csv(manifest_path)
recorded = {r["relative_path"]: r["sha256"] for r in manifest}
errors = []
if len(recorded) != len(manifest) or set(recorded) != set(sources):
    errors.append("Support manifest does not exactly cover source files")
hashes = {}
for relative, source in sources.items():
    target = candidate / relative
    expected = sha256(source)
    actual = sha256(target) if target.is_file() else None
    hashes[relative] = {"source_sha256": expected, "candidate_sha256": actual}
    if actual != expected or recorded.get(relative) != expected:
        errors.append("Missing or changed support file: " + relative)
report = {"status": "FAIL" if errors else "PASS", "source_database": str(database),
          "candidate": str(candidate), "checked_at": dt.datetime.now(dt.timezone.utc).isoformat(),
          "manifest_sha256": sha256(manifest_path), "files": hashes, "errors": errors,
          "scope": "Byte-exact external scripts, historical data, name tables and six UCP/editor auxiliary files; native semantics and compiled game database require separate checks.",
          "release_ready": False}
write_json(a.output, report)
print({"status": report["status"], "files": len(hashes), "errors": errors})
sys.exit(bool(errors))
