"""Inventory every source database/support file; do not equate object tests with a game export."""
import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fm27.common import sha256, write_json

p = argparse.ArgumentParser()
p.add_argument("--database", type=Path, required=True)
p.add_argument("--candidate", type=Path, required=True)
p.add_argument("--output", type=Path, required=True)
a = p.parse_args()
database, candidate = a.database.resolve(), a.candidate.resolve()
known = {"Countries.sav": "COUNTRY_HEADERS", "Without.sav": "PLAYERS",
         "Rules.sav": "GLOBAL_RULES", "Assessment.sav": "ASSESSMENT", "AppearanceDefs.sav": "APPEARANCE",
         "Cities.txt": "CITIES", "Regions.txt": "REGIONS", "PlayerRelations.sav": "PLAYER_RELATIONS"}
rows = []
for source_root, prefix in ((database, Path("database")), (database.parent / "script", Path("script")),
                            (database.parent / "fmdata/historic", Path("fmdata/historic"))):
    if not source_root.is_dir():
        continue
    for source in sorted(source_root.rglob("*")):
        if source.is_symlink():
            raise ValueError("Source file inventory cannot follow symlinks")
        if not source.is_file():
            continue
        relative = prefix / source.relative_to(source_root)
        target = candidate / relative
        source_hash = sha256(source)
        target_hash = sha256(target) if target.is_file() else None
        coverage = None
        name = relative.as_posix()
        if name == "database/Master.dat":
            status = "GAME_DATABASE_COMPILATION_REQUIRED"
            coverage = "The native FIFAM writer does not generate Master.dat; copying the old binary database is not proof of updated squads."
        elif target_hash == source_hash:
            status = "BYTE_EXACT"
        elif prefix == Path("database") and relative.relative_to(prefix).as_posix() in known and target_hash:
            status = "NATIVE_SEMANTIC_PROOF_REQUIRED"
            coverage = known[relative.relative_to(prefix).as_posix()]
        else:
            match = re.fullmatch(r"database/(data/CountryData|script/CountryScript)(\d+)\.sav", name)
            if match and 1 <= int(match[2]) <= 207 and target_hash:
                status = "NATIVE_SEMANTIC_PROOF_REQUIRED"
                coverage = "COUNTRY_OBJECTS_AND_MEMBERS" if match[1].startswith("data/") else "COMPETITIONS_AND_FIXTURES"
            else:
                status = "UNPRESERVED_SOURCE_FILE"
        rows.append({"relative_path": name, "status": status, "coverage": coverage,
                     "source_sha256": source_hash, "candidate_sha256": target_hash})
counts = Counter(r["status"] for r in rows)
report = {"status": "INCOMPLETE", "source_database": str(database), "candidate": str(candidate),
          "source_files": len(rows), "counts": dict(counts), "files": rows,
          "uncovered": [r for r in rows if r["status"] in {"UNPRESERVED_SOURCE_FILE", "GAME_DATABASE_COMPILATION_REQUIRED"}],
          "limitations": "Inventory only: native semantic classes require separately bound roundtrip evidence. "
                         "Master.dat must be exported for the changed candidate and checked in the game. Generated-only files also need review.",
          "release_ready": False}
write_json(a.output, report)
print(json.dumps({k: v for k, v in report.items() if k != "files"}))
