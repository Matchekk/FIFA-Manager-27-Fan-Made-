"""Build the bounded 2026/27 German Regionalliga Nord/West membership dependency artifact.

This is an evidence-only dataset.  It records the authoritative promotion set and
the Native08 IDs needed to close the net vacancies in the fresh Native10 inspection;
it does not edit a membership plan or database.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "current"
CSV_PATH = OUT_DIR / "german-nord-west-dependencies.csv"
JSON_PATH = OUT_DIR / "german-nord-west-dependencies.json"

INSPECTION_DIR = ROOT / "data" / "generated" / "native10-base-competition-inspection-20260912-01"
STRUCTURE_PATH = INSPECTION_DIR / "competition_structure.csv"
MEMBERS_PATH = INSPECTION_DIR / "competition_members.csv"
RICH_CLUBS_PATH = ROOT / "data" / "generated" / "combined-20260908-01-evidence" / "data" / "intermediate" / "native-bound-baseline" / "clubs.csv"

WEB_SOURCES = {
    "nordfv": {
        "url": "https://www.nordfv.de/news/aufstieg-perfekt",
        "sha256": "1bd11d9d79c6bcf0453a3cccd46adec56e48f25d335618cd907cad9df8136cef",
        "published": "2026-06-10",
    },
    "sportschau": {
        "url": "https://www.sportschau.de/regional/wdr/wdr-regionalliga-west-das-sind-die-vier-aufsteiger-100.html",
        "sha256": "9208add2b7706ee9888e4200d3fb70bfc2f034997de95dcd3c497fb2d6ae06c3",
        "published": "2026-06-13",
    },
}

ROWS = [
    {
        "region": "NORD",
        "competition": "Regionalliga Nord",
        "competition_native_id": "352387075",
        "club_name": "SV Atlas Delmenhorst",
        "native_club_id": "1384964",
        "origin_competition": "Oberliga Niedersachsen",
        "origin_detail": "2025/26 Niedersachsenmeister; direct promotion",
        "source_key": "nordfv",
    },
    {
        "region": "NORD",
        "competition": "Regionalliga Nord",
        "competition_native_id": "352387075",
        "club_name": "Eimsbütteler TV",
        "native_club_id": "1380408",
        "origin_competition": "Oberliga Hamburg",
        "origin_detail": "2025/26 runner-up; won the Nord promotion round",
        "source_key": "nordfv",
    },
    {
        "region": "NORD",
        "competition": "Regionalliga Nord",
        "competition_native_id": "352387075",
        "club_name": "SV Todesfelde",
        "native_club_id": "1380495",
        "origin_competition": "Oberliga Schleswig-Holstein (Flens-Oberliga)",
        "origin_detail": "2025/26 champion; won the Nord promotion round",
        "source_key": "nordfv",
    },
    {
        "region": "WEST",
        "competition": "Regionalliga West",
        "competition_native_id": "352387077",
        "club_name": "SV Westfalia Rhynern",
        "native_club_id": "1380503",
        "origin_competition": "Oberliga Westfalen",
        "origin_detail": "2025/26 champion; promotion",
        "source_key": "sportschau",
    },
    {
        "region": "WEST",
        "competition": "Regionalliga West",
        "competition_native_id": "352387077",
        "club_name": "SG Wattenscheid 09",
        "native_club_id": "1376423",
        "origin_competition": "Oberliga Westfalen",
        "origin_detail": "2025/26 runner-up; promotion",
        "source_key": "sportschau",
    },
    {
        "region": "WEST",
        "competition": "Regionalliga West",
        "competition_native_id": "352387077",
        "club_name": "SV Bergisch Gladbach 09",
        "native_club_id": "1376447",
        "origin_competition": "Mittelrheinliga",
        "origin_detail": "2025/26 champion; promotion",
        "source_key": "sportschau",
    },
    {
        "region": "WEST",
        "competition": "Regionalliga West",
        "competition_native_id": "352387077",
        "club_name": "VfB 03 Hilden",
        "native_club_id": "1378842",
        "origin_competition": "Oberliga Niederrhein",
        "origin_detail": "2025/26 champion; promotion",
        "source_key": "sportschau",
    },
]

OUTGOING = {
    "NORD": [
        ("SV Meppen", "1376347", "promoted to 3. Liga"),
        ("Altonaer FC 1893", "1376340", "no longer in the 2026/27 RL Nord field"),
        ("TuS Blau-Weiß Lohne", "1388585", "no longer in the 2026/27 RL Nord field"),
    ],
    "WEST": [
        ("SC Fortuna Köln", "1376444", "promoted to 3. Liga"),
        ("Fortuna Düsseldorf 1895", "1376429", "forced relegation to Oberliga after parent-club relegation"),
        ("Wuppertaler SV", "1376424", "relegated to Oberliga"),
        ("SSVg Velbert 02", "1376382", "relegated to Oberliga"),
    ],
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_rich_clubs() -> dict[str, dict[str, str]]:
    with RICH_CLUBS_PATH.open(encoding="utf-8-sig", newline="") as fh:
        return {row["club_id"]: row for row in csv.DictReader(fh)}


def load_membership() -> dict[str, list[dict[str, str]]]:
    result: dict[str, list[dict[str, str]]] = {"352387075": [], "352387077": []}
    with MEMBERS_PATH.open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            if row["competition_id"] in result:
                result[row["competition_id"]].append(row)
    return result


def main() -> None:
    rich = load_rich_clubs()
    members = load_membership()
    local_hashes = {
        str(STRUCTURE_PATH.relative_to(ROOT)): sha256(STRUCTURE_PATH),
        str(MEMBERS_PATH.relative_to(ROOT)): sha256(MEMBERS_PATH),
        str(RICH_CLUBS_PATH.relative_to(ROOT)): sha256(RICH_CLUBS_PATH),
    }

    # The inspection is the pre-change Native10 membership baseline.  Every named
    # outgoing club must be present, and every promoted club must be a distinct
    # rich-club identity absent from its target baseline.
    for region, outgoing in OUTGOING.items():
        comp_id = "352387075" if region == "NORD" else "352387077"
        ids = {row["club_id"] for row in members[comp_id]}
        missing = [club_id for _, club_id, _ in outgoing if club_id not in ids]
        if missing:
            raise RuntimeError(f"outgoing baseline IDs missing for {region}: {missing}")
    for row in ROWS:
        if row["native_club_id"] not in rich:
            raise RuntimeError(f"promoted club missing from rich Native08 clubs: {row['club_name']}")
        if row["native_club_id"] in {m["club_id"] for m in members[row["competition_native_id"]]}:
            raise RuntimeError(f"promoted club already in target baseline: {row['club_name']}")

    vacancy_context = {}
    for region, outgoing in OUTGOING.items():
        vacancy_context[region] = {
            "net_vacancies": len(outgoing),
            "outgoing": [
                {"club_name": name, "native_club_id": club_id, "reason": reason}
                for name, club_id, reason in outgoing
            ],
            "pairing_policy": "Promotion set closes the net vacancies; no one-to-one sporting pairing asserted.",
        }

    fields = [
        "snapshot_date", "season", "region", "competition", "competition_native_id",
        "movement", "club_name", "native_club_id", "native_reference_id", "native_fifa_id",
        "origin_competition", "origin_detail", "vacancy_context", "status", "source_url",
        "source_sha256", "native_source_path", "native_source_sha256", "notes",
    ]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with CSV_PATH.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in ROWS:
            club = rich[row["native_club_id"]]
            source = WEB_SOURCES[row["source_key"]]
            writer.writerow({
                "snapshot_date": "2026-09-12",
                "season": "2026/27",
                "region": row["region"],
                "competition": row["competition"],
                "competition_native_id": row["competition_native_id"],
                "movement": "PROMOTION_IN",
                "club_name": row["club_name"],
                "native_club_id": row["native_club_id"],
                "native_reference_id": club["reference_id"],
                "native_fifa_id": club["fifa_id"],
                "origin_competition": row["origin_competition"],
                "origin_detail": row["origin_detail"],
                "vacancy_context": json.dumps(vacancy_context[row["region"]], ensure_ascii=False, separators=(",", ":")),
                "status": "CONFIRMED",
                "source_url": source["url"],
                "source_sha256": source["sha256"],
                "native_source_path": str(RICH_CLUBS_PATH.relative_to(ROOT)),
                "native_source_sha256": local_hashes[str(RICH_CLUBS_PATH.relative_to(ROOT))],
                "notes": "Evidence-only dependency; do not apply directly to production membership plan.",
            })

    sidecar = {
        "artifact": "german-nord-west-dependencies",
        "snapshot_date": "2026-09-12",
        "season": "2026/27",
        "status": "CONFIRMED",
        "canonical_mutation": False,
        "rows": len(ROWS),
        "promoted_by_region": {"NORD": 3, "WEST": 4},
        "vacancy_closures": vacancy_context,
        "sources": {
            "web": WEB_SOURCES,
            "local_native": local_hashes,
        },
        "method": [
            "Authoritative 2026/27 promotion outcomes were cross-checked against the fresh Native10 competition inspection.",
            "Native IDs, reference IDs and FIFA IDs come from the rich Native08 club corpus; no new IDs were invented.",
            "Net vacancy sets are reported without arbitrary one-to-one pairing between outgoing and incoming clubs.",
        ],
    }
    JSON_PATH.write_text(json.dumps(sidecar, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
