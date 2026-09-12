#!/usr/bin/env python3
"""Audit unplanned stable-player hash rewrites against exact raw native blocks."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def identity(row: dict[str, str]) -> tuple[str, str, str]:
    return row["fifa_id"], row["dob"], row["name"]


def stable(row: dict[str, str]) -> tuple[tuple[str, str], ...]:
    return tuple((field, value) for field, value in row.items()
                 if field not in {"fm_id", "serialized_sha256"})


def raw_blocks(database: Path, ids: set[str]) -> dict[str, tuple[str, bytes]]:
    found: dict[str, tuple[str, bytes]] = {}
    if not ids:
        return found
    choices = sorted(ids, key=lambda value: (-len(value), value))
    pattern = re.compile(rb"(?m)^(" + b"|".join(re.escape(value.encode()) for value in choices) +
                         rb")\r?\n%INDEX%PLAYER\r?\n(.*?)%INDEXEND%PLAYER", re.S)
    files = list(sorted((database / "data").glob("CountryData*.sav")))
    files.extend(path for path in (database / "Without.sav", database / "data/Without.sav") if path.is_file())
    for path in files:
        for match in pattern.finditer(path.read_bytes()):
            fm_id = match.group(1).decode("ascii")
            if fm_id in found:
                raise ValueError(f"raw player {fm_id} occurs in multiple files")
            found[fm_id] = (path.relative_to(database).as_posix(), match.group(2))
        if len(found) == len(ids):
            break
    missing = ids - set(found)
    if missing:
        raise ValueError(f"raw player blocks missing: {sorted(missing)}")
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before-semantics", type=Path, required=True)
    parser.add_argument("--after-semantics", type=Path, required=True)
    parser.add_argument("--before-database", type=Path, required=True)
    parser.add_argument("--after-database", type=Path, required=True)
    parser.add_argument("--squad-plan", type=Path, required=True)
    parser.add_argument("--database-source", type=Path,
                        default=Path(__file__).resolve().parents[1] / "upstream/fifam/fmapi/FifamDatabase.cpp")
    parser.add_argument("--player-source", type=Path,
                        default=Path(__file__).resolve().parents[1] / "upstream/fifam/fmapi/FifamPlayer.cpp")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.report.exists():
        raise ValueError("audit outputs must be new")

    before_rows = read_csv(args.before_semantics)
    after_rows = read_csv(args.after_semantics)
    before_groups: dict[tuple[str, str, str], list[dict[str, str]]] = {}
    after_groups: dict[tuple[str, str, str], list[dict[str, str]]] = {}
    for row in before_rows:
        before_groups.setdefault(identity(row), []).append(row)
    for row in after_rows:
        after_groups.setdefault(identity(row), []).append(row)
    planned_ids = {row["fm_id"] for row in read_csv(args.squad_plan)}

    candidates: list[tuple[dict[str, str], dict[str, str]]] = []
    for key, rows in before_groups.items():
        if len(rows) != 1 or len(after_groups.get(key, [])) != 1:
            continue
        before = rows[0]
        after = after_groups[key][0]
        if (before["fm_id"] not in planned_ids and stable(before) == stable(after)
                and before["serialized_sha256"] != after["serialized_sha256"]):
            candidates.append((before, after))

    before_blocks = raw_blocks(args.before_database, {row[0]["fm_id"] for row in candidates})
    after_blocks = raw_blocks(args.after_database, {row[1]["fm_id"] for row in candidates})
    audited = []
    errors = []
    for before, after in candidates:
        before_file, before_block = before_blocks[before["fm_id"]]
        after_file, after_block = after_blocks[after["fm_id"]]
        before_lines = before_block.decode("cp1252").splitlines()
        after_lines = after_block.decode("cp1252").splitlines()
        changed_lines = [index for index in range(max(len(before_lines), len(after_lines)))
                         if (before_lines[index] if index < len(before_lines) else None) !=
                            (after_lines[index] if index < len(after_lines) else None)]
        valid = len(changed_lines) == 1 and changed_lines[0] == 15
        old_fields = before_lines[15].split(",") if len(before_lines) > 15 else []
        new_fields = after_lines[15].split(",") if len(after_lines) > 15 else []
        changed_fields = [index for index in range(max(len(old_fields), len(new_fields)))
                          if (old_fields[index] if index < len(old_fields) else None) !=
                             (new_fields[index] if index < len(new_fields) else None)]
        valid = valid and len(old_fields) == 6 and len(new_fields) == 6 and changed_fields == [1]
        valid = valid and old_fields[1] == "0" and new_fields[1].isdigit() and int(new_fields[1]) > 0
        item = {
            "before_fm_id": before["fm_id"], "after_fm_id": after["fm_id"],
            "fifa_id": before["fifa_id"], "dob": before["dob"], "name": before["name"],
            "before_file": before_file, "after_file": after_file,
            "raw_block_line": "15", "raw_field_index": "1", "raw_field_name": "mEmpicsId",
            "old_value": old_fields[1] if len(old_fields) > 1 else "",
            "new_value": new_fields[1] if len(new_fields) > 1 else "",
            "before_block_sha256": sha256_bytes(before_block), "after_block_sha256": sha256_bytes(after_block),
            "before_serialized_sha256": before["serialized_sha256"],
            "after_serialized_sha256": after["serialized_sha256"],
            "classification": "WRITEABLE_STRING_ID_COLLISION_EMPICS_DISAMBIGUATOR",
            "status": "VERIFIED" if valid else "REJECTED",
        }
        audited.append(item)
        if not valid:
            errors.append({"identity": identity(before), "changed_lines": changed_lines,
                           "changed_fields": changed_fields})

    fields = list(audited[0]) if audited else [
        "before_fm_id", "after_fm_id", "fifa_id", "dob", "name", "before_file", "after_file",
        "raw_block_line", "raw_field_index", "raw_field_name", "old_value", "new_value",
        "before_block_sha256", "after_block_sha256", "before_serialized_sha256",
        "after_serialized_sha256", "classification", "status"]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(audited)

    source_database = args.database_source
    source_player = args.player_source
    if not source_database.is_file() or not source_player.is_file():
        raise ValueError("serializer source evidence is missing")
    report = {
        "status": "PASS_NARROW_DERIVED_METADATA_NORMALIZATION" if audited and not errors else "FAIL",
        "rows": len(audited), "errors": errors,
        "output_sha256": sha256(args.output),
        "before_semantics_sha256": sha256(args.before_semantics),
        "after_semantics_sha256": sha256(args.after_semantics),
        "squad_plan_sha256": sha256(args.squad_plan),
        "serializer_evidence": {
            "field": "FifamPlayer::mEmpicsId",
            "write_location": "FifamPlayer.cpp:672 (mSpecialFace,mEmpicsId,height,weight,shirt numbers)",
            "derivation_location": "FifamDatabase.cpp:688-701 (duplicate string-id disambiguation)",
            "derivation": "When a duplicate player string id has mEmpicsId=0, writer setup assigns mFootballManagerID when positive, otherwise a generated high Empics id.",
            "FifamPlayer.cpp_sha256": sha256(source_player),
            "FifamDatabase.cpp_sha256": sha256(source_database),
        },
        "policy": "Only the exact verified rows and before/after hashes in the CSV may pass comparator normalization. Any other opaque serialization rewrite fails.",
    }
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "rows": len(audited), "errors": len(errors)}))
    return 0 if report["status"].startswith("PASS") else 1


if __name__ == "__main__":
    raise SystemExit(main())
