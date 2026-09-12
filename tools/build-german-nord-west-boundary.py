"""Build the two-entry German Regionalliga -> Oberliga boundary chain.

Evidence-only output for the GER3 closure: one selected promotion into each
Regionalliga vacancy and one existing Native08 club promoted into the resulting
Oberliga vacancy.  No production membership plan or database is changed.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "current"
CSV_PATH = OUT / "german-nord-west-dependencies.csv"
JSON_PATH = OUT / "german-nord-west-dependencies.json"
INSPECTION = ROOT / "data" / "generated" / "native10-base-competition-inspection-20260912-01"
STRUCTURE = INSPECTION / "competition_structure.csv"
MEMBERS = INSPECTION / "competition_members.csv"
RICH = ROOT / "data" / "generated" / "combined-20260908-01-evidence" / "data" / "intermediate" / "native-bound-baseline" / "clubs.csv"

SOURCES = {
    "north_promotion": {
        "url": "https://www.nordfv.de/news/aufstieg-perfekt",
        "sha256": "1bd11d9d79c6bcf0453a3cccd46adec56e48f25d335618cd907cad9df8136cef",
        "claim": "NFV confirms Atlas Delmenhorst, Eimsbütteler TV and SV Todesfelde for the 2026/27 Regionalliga Nord; Atlas had already secured direct promotion as Oberliga Niedersachsen champion.",
    },
    "north_boundary": {
        "url": "https://www.vorwaertsnordhorn.de/news/mannschaftsfoto-oberliga-2026-2027/",
        "sha256": "22497b74ea8ee3ddfe88cebc17999ad660f78edfb7e0c9f1267d041a7d35e429",
        "claim": "SV Vorwärts Nordhorn states its first team enters the 2026/27 Oberliga Niedersachsen after winning the Landesliga.",
    },
    "west_promotion": {
        "url": "https://www.sportschau.de/regional/wdr/wdr-regionalliga-west-das-sind-die-vier-aufsteiger-100.html",
        "sha256": "9208add2b7706ee9888e4200d3fb70bfc2f034997de95dcd3c497fb2d6ae06c3",
        "claim": "Sportschau/WDR confirms Westfalia Rhynern, SG Wattenscheid 09, SV Bergisch Gladbach 09 and VfB 03 Hilden as the four 2026/27 Regionalliga West promotions; Rhynern is the Oberliga Westfalen champion.",
    },
    "west_boundary": {
        "url": "https://www.fupa.net/news/flvw-gibt-ueberkreisliche-staffeleinteilung-202627-bekannt-3199174",
        "sha256": "848cbc7915a3fcd573767d1e8e91f8b13beef2eb811a25acc675b0b72760ae10",
        "claim": "The FLVW 2026/27 overregional staff allocation lists SC Westf. Kinderhaus as an Oberliga Westfalen promotion from Westfalenliga Staffel 1.",
    },
}

CHAINS = [
    {
        "boundary": "NORD",
        "regional_competition": "Regionalliga Nord",
        "regional_competition_native_id": "352387075",
        "regional_promoted_club": "SV Atlas Delmenhorst",
        "regional_promoted_club_native_id": "1384964",
        "regional_promoted_origin": "Oberliga Niedersachsen",
        "regional_vacated_club": "SV Meppen",
        "regional_vacated_club_native_id": "1376347",
        "oberliga_competition": "Oberliga Niedersachsen",
        "oberliga_competition_native_id": "352387083",
        "boundary_promoted_club": "SV Vorwärts Nordhorn",
        "boundary_promoted_club_native_id": "1389307",
        "boundary_promoted_origin": "Landesliga Weser-Ems",
        "source_keys": ["north_promotion", "north_boundary"],
        "proof": "Atlas fills the selected Meppen Regionalliga Nord vacancy; Vorwärts Nordhorn is the existing Native08 club promoted from Landesliga Weser-Ems into the resulting Oberliga Niedersachsen boundary.",
    },
    {
        "boundary": "WEST",
        "regional_competition": "Regionalliga West",
        "regional_competition_native_id": "352387077",
        "regional_promoted_club": "SV Westfalia Rhynern",
        "regional_promoted_club_native_id": "1380503",
        "regional_promoted_origin": "Oberliga Westfalen",
        "regional_vacated_club": "SC Fortuna Köln",
        "regional_vacated_club_native_id": "1376444",
        "oberliga_competition": "Oberliga Westfalen",
        "oberliga_competition_native_id": "352387086",
        "boundary_promoted_club": "SC Westfalia Kinderhaus",
        "boundary_promoted_club_native_id": "1376965",
        "boundary_promoted_origin": "Westfalenliga Staffel 1",
        "source_keys": ["west_promotion", "west_boundary"],
        "proof": "Rhynern fills the selected Fortuna Köln Regionalliga West vacancy; Westfalia Kinderhaus is the existing Native08 club promoted from Westfalenliga Staffel 1 into the resulting Oberliga Westfalen boundary.",
    },
]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    with RICH.open(encoding="utf-8-sig", newline="") as fh:
        rich = {r["club_id"]: r for r in csv.DictReader(fh)}
    with MEMBERS.open(encoding="utf-8-sig", newline="") as fh:
        members = list(csv.DictReader(fh))
    members_by_comp = {}
    for row in members:
        members_by_comp.setdefault(row["competition_id"], set()).add(row["club_id"])

    for chain in CHAINS:
        for key in ("regional_promoted_club_native_id", "regional_vacated_club_native_id", "boundary_promoted_club_native_id"):
            if chain[key] not in rich:
                raise RuntimeError(f"missing Native08 identity: {chain[key]}")
        if chain["regional_vacated_club_native_id"] not in members_by_comp.get(chain["regional_competition_native_id"], set()):
            raise RuntimeError(f"vacated regional club not in Native10 baseline: {chain['regional_vacated_club']}")
        if chain["regional_promoted_club_native_id"] not in members_by_comp.get(chain["oberliga_competition_native_id"], set()):
            raise RuntimeError(f"selected regional promotion origin not in Native10 lower baseline: {chain['regional_promoted_club']}")
        if chain["boundary_promoted_club_native_id"] in members_by_comp.get(chain["oberliga_competition_native_id"], set()):
            raise RuntimeError(f"boundary club already assigned to target Oberliga baseline: {chain['boundary_promoted_club']}")
        if rich[chain["boundary_promoted_club_native_id"]].get("league", ""):
            raise RuntimeError(f"boundary club is already modeled in a league: {chain['boundary_promoted_club']}")

    local_sources = {
        str(p.relative_to(ROOT)): digest(p)
        for p in (STRUCTURE, MEMBERS, RICH)
    }
    fields = [
        "snapshot_date", "season", "boundary", "regional_competition", "regional_competition_native_id",
        "regional_promoted_club", "regional_promoted_club_native_id", "regional_promoted_club_reference_id",
        "regional_promoted_origin", "regional_vacated_club", "regional_vacated_club_native_id",
        "oberliga_competition", "oberliga_competition_native_id", "boundary_promoted_club",
        "boundary_promoted_club_native_id", "boundary_promoted_club_reference_id", "boundary_promoted_origin",
        "status", "source_url", "source_sha256", "native_source_path", "native_source_sha256", "source_proof",
    ]
    OUT.mkdir(parents=True, exist_ok=True)
    with CSV_PATH.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for chain in CHAINS:
            regional = rich[chain["regional_promoted_club_native_id"]]
            boundary = rich[chain["boundary_promoted_club_native_id"]]
            sources = [SOURCES[k] for k in chain["source_keys"]]
            writer.writerow({
                "snapshot_date": "2026-09-12",
                "season": "2026/27",
                "boundary": chain["boundary"],
                "regional_competition": chain["regional_competition"],
                "regional_competition_native_id": chain["regional_competition_native_id"],
                "regional_promoted_club": chain["regional_promoted_club"],
                "regional_promoted_club_native_id": chain["regional_promoted_club_native_id"],
                "regional_promoted_club_reference_id": regional["reference_id"],
                "regional_promoted_origin": chain["regional_promoted_origin"],
                "regional_vacated_club": chain["regional_vacated_club"],
                "regional_vacated_club_native_id": chain["regional_vacated_club_native_id"],
                "oberliga_competition": chain["oberliga_competition"],
                "oberliga_competition_native_id": chain["oberliga_competition_native_id"],
                "boundary_promoted_club": chain["boundary_promoted_club"],
                "boundary_promoted_club_native_id": chain["boundary_promoted_club_native_id"],
                "boundary_promoted_club_reference_id": boundary["reference_id"],
                "boundary_promoted_origin": chain["boundary_promoted_origin"],
                "status": "CONFIRMED",
                "source_url": ";".join(s["url"] for s in sources),
                "source_sha256": ";".join(s["sha256"] for s in sources),
                "native_source_path": str(RICH.relative_to(ROOT)),
                "native_source_sha256": local_sources[str(RICH.relative_to(ROOT))],
                "source_proof": chain["proof"],
            })

    sidecar = {
        "artifact": "german-nord-west-dependencies",
        "snapshot_date": "2026-09-12",
        "season": "2026/27",
        "status": "CONFIRMED",
        "canonical_mutation": False,
        "rows": 2,
        "policy": "Exactly one selected official regional promotion and one existing Native08 lower-division promotion per GER3 boundary; no arbitrary cross-region club selection.",
        "chains": CHAINS,
        "sources": {"web": SOURCES, "local_native": local_sources},
        "native_identity_fields": {
            chain["boundary"]: {
                "regional_promoted": rich[chain["regional_promoted_club_native_id"]],
                "boundary_promoted": rich[chain["boundary_promoted_club_native_id"]],
            }
            for chain in CHAINS
        },
    }
    JSON_PATH.write_text(json.dumps(sidecar, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
