"""Project exact loan guards from a native semantic baseline into a small sidecar."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--semantics", type=Path, required=True)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "data/current/integration/native08-loan-preconditions.csv")
    args = parser.parse_args()
    if not args.semantics.is_file():
        raise ValueError("Missing native semantic baseline")
    digest = hashlib.sha256(args.semantics.read_bytes()).hexdigest()
    fields = ["fm_id", "fifa_id", "dob", "club_id", "loan_owner_club_id", "loan_start",
              "loan_end", "loan_buy_option", "protected_conditions_sha256", "future_conditions_sha256"]
    rows = []
    with args.semantics.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            if row.get("loan_enabled") == "1":
                rows.append({field: row.get(field, "") for field in fields})
    rows.sort(key=lambda row: int(row["fm_id"]))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader(); writer.writerows(rows)
    metadata = {"status": "EXACT_NATIVE08_LOAN_PRECONDITIONS", "rows": len(rows),
                "semantic_source": str(args.semantics.resolve()), "semantic_source_sha256": digest,
                "output_sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
                "scope": "Read-only projection of serialized native loan owner/start/end/buy guards."}
    args.output.with_suffix(".json").write_text(json.dumps(metadata, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(metadata))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
