"""Materialize exact current Native08 bridges found in the ENG/GER queue."""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/current/workers/eng-ger"


def read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def main() -> None:
    source = read(OUT / "create-ready-review.csv")
    bridges = []
    for row in source:
        candidates = json.loads(row["exact_candidates"])
        if len(candidates) != 1:
            continue
        native = candidates[0]
        bridges.append({
            "league": row["league"], "club_name": row["club_name"], "club_tm_id": row["club_tm_id"],
            "player_tm_id": row["player_tm_id"], "source_player_name": row["player"], "dob": row["dob"],
            "native_fm_id": native["fm_id"], "native_fifa_id": native["fifa_id"], "native_name": native["name"],
            "native_dob": native["dob"], "native_club_id": native["club_id"], "target_club_id": row["club_id"],
            "status": "CONFIRMED", "identity_method": "EXACT_PROFILE_DOB_NAME",
            "profile_source": row["profile_source"], "profile_sha256": row["profile_sha256"],
            "source_url": row["source_url"], "source_sha256": row["source_sha256"],
            "provenance": "Unique exact DOB + normalized profile/full-name bridge from current Native08; all other exact/fuzzy candidates were retained in review CSV.",
        })
    fields = list(bridges[0]) if bridges else ["league", "club_name", "club_tm_id", "player_tm_id", "source_player_name", "dob", "native_fm_id", "native_fifa_id", "native_name", "native_dob", "native_club_id", "target_club_id", "status", "identity_method", "profile_source", "profile_sha256", "source_url", "source_sha256", "provenance"]
    with (OUT / "confirmed-bridges.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields); writer.writeheader(); writer.writerows(bridges)
    (OUT / "confirmed-bridges.json").write_text(json.dumps({"schema": 1, "snapshot_date": "2026-09-12", "rows": len(bridges), "canonical_mutation": False, "identity_method": "EXACT_PROFILE_DOB_NAME"}, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"confirmed_bridges": len(bridges), "path": str(OUT / 'confirmed-bridges.csv')}))


if __name__ == "__main__": main()
