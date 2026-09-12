#!/usr/bin/env python3
"""Build an additions-only squad delta against an immutable native draft input.

Rows already present in the base draft are never emitted because their old-club
preconditions describe the pre-draft database.  Replaying them after the draft
would either fail safely or risk obscuring an integration error.  Common-row
changes are classified in the manifest for review instead.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or "fm_id" not in reader.fieldnames:
            raise ValueError(f"{path}: missing fm_id column")
        rows = list(reader)
        return list(reader.fieldnames), rows


def index_rows(path: Path, rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    indexed: dict[str, dict[str, str]] = {}
    for row_number, row in enumerate(rows, start=2):
        fm_id = row.get("fm_id", "").strip()
        if not fm_id:
            raise ValueError(f"{path}:{row_number}: blank fm_id")
        if fm_id in indexed:
            raise ValueError(f"{path}:{row_number}: duplicate fm_id {fm_id}")
        indexed[fm_id] = row
    return indexed


def numeric_key(value: str) -> tuple[int, str]:
    try:
        return int(value), value
    except ValueError:
        return 2**63 - 1, value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-plan", required=True, type=Path)
    parser.add_argument("--current-plan", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    args = parser.parse_args()

    base_fields, base_rows = read_csv(args.base_plan)
    current_fields, current_rows = read_csv(args.current_plan)
    if base_fields != current_fields:
        raise ValueError("base and current plan schemas differ")

    base = index_rows(args.base_plan, base_rows)
    current = index_rows(args.current_plan, current_rows)
    additions = sorted(set(current) - set(base), key=numeric_key)
    removals = sorted(set(base) - set(current), key=numeric_key)

    changed: list[dict[str, object]] = []
    for fm_id in sorted(set(base) & set(current), key=numeric_key):
        fields = [field for field in current_fields if base[fm_id].get(field, "") != current[fm_id].get(field, "")]
        if fields:
            changed.append({"fm_id": fm_id, "changed_fields": fields})

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=current_fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(current[fm_id] for fm_id in additions)

    passive_fields = {"acquisition_event_key", "acquisition_source", "acquisition_source_sha256"}
    native_common_changes = [
        item for item in changed if not set(item["changed_fields"]).issubset(passive_fields)
    ]
    manifest = {
        "status": "PASS" if not removals and not native_common_changes else "REVIEW",
        "policy": "ADDITIONS_ONLY_NO_REPLAY",
        "base_plan": str(args.base_plan),
        "base_plan_sha256": sha256(args.base_plan),
        "base_rows": len(base_rows),
        "current_plan": str(args.current_plan),
        "current_plan_sha256": sha256(args.current_plan),
        "current_rows": len(current_rows),
        "output": str(args.output),
        "output_sha256": sha256(args.output),
        "addition_count": len(additions),
        "addition_fm_ids": additions,
        "removal_count": len(removals),
        "removal_fm_ids": removals,
        "common_changed_count": len(changed),
        "common_changes": changed,
        "common_native_change_count": len(native_common_changes),
        "common_native_changes": native_common_changes,
        "note": (
            "Common rows are not emitted because their guards bind the pre-draft state. "
            "Changes limited to passive acquisition evidence have no native database effect."
        ),
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: manifest[key] for key in ("status", "addition_count", "removal_count", "common_changed_count", "common_native_change_count", "output_sha256")}, indent=2))
    return 0 if manifest["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
