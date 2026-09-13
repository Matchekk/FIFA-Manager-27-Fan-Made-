"""Materialize the first south-west confirmed identity batch for Sol intake."""
from __future__ import annotations

import csv
import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/current/workers/south-west"
IDS = {
    "922792", "124182", "1184725", "430310", "559979", "263918", "467632", "659089",
    "1297674", "1143375", "354361", "646747", "1371198", "997646", "763948", "1086915",
    "1047861", "746358", "1241219", "1218658", "1026524", "938156", "1093061", "666539",
    "902869", "1076666", "1197994", "1296109", "720286", "1181959", "1189059", "1442800",
    "1237420", "1152080",
}


def read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def date_value(value: str) -> str:
    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return dt.datetime.strptime((value or "").strip(), fmt).date().isoformat()
        except ValueError:
            pass
    return ""


def main() -> None:
    profiles = {r["player_tm_id"]: r for r in read(OUT / "profiles.csv")}
    rosters = {r["player_tm_id"]: r for r in read(OUT / "rosters.csv")}
    native = read(ROOT / "data/generated/native08-integrated-20260912-01-reread/native_players.csv")
    overrides = {r["player_tm_id"]: r for r in json.loads((ROOT / "data/overrides/player_identities.json").read_text(encoding="utf-8"))["rows"]}
    by_fifa_dob = {(r["fifa_id"], date_value(r["dob"])): r for r in native if r.get("fifa_id") not in {"", "0"}}
    by_name_dob = {(r["name"].casefold(), date_value(r["dob"])): r for r in native}
    by_dob_club = {(date_value(r["dob"]), r["club_id"]): r for r in native}
    methods = {
        "922792": "EXISTING_OVERRIDE_NAME_DOB", "124182": "EXISTING_OVERRIDE_FIFA_DOB", "1184725": "CONTROLLED_NAME_VARIANT",
        "430310": "EXISTING_OVERRIDE_FIFA_DOB", "559979": "EXISTING_OVERRIDE_FIFA_DOB", "263918": "EXISTING_OVERRIDE_FIFA_DOB",
        "467632": "CONTROLLED_NAME_VARIANT", "659089": "EXISTING_OVERRIDE_FIFA_DOB", "1297674": "CONTROLLED_NAME_VARIANT",
        "1143375": "EXISTING_OVERRIDE_FIFA_DOB", "354361": "EXISTING_OVERRIDE_FIFA_DOB", "646747": "EXISTING_OVERRIDE_FIFA_DOB",
        "1371198": "EXISTING_OVERRIDE_NAME_DOB", "997646": "EXISTING_OVERRIDE_FIFA_DOB", "763948": "EXISTING_OVERRIDE_NAME_DOB",
        "1086915": "CONTROLLED_NAME_VARIANT", "1047861": "CONTROLLED_NAME_VARIANT", "746358": "CONTROLLED_NAME_VARIANT",
        "1241219": "CONTROLLED_NAME_VARIANT", "1218658": "EXISTING_OVERRIDE_NAME_DOB", "1026524": "EXISTING_OVERRIDE_NAME_DOB",
        "938156": "EXISTING_OVERRIDE_NAME_DOB", "1093061": "CONTROLLED_NAME_VARIANT", "666539": "EXISTING_OVERRIDE_FIFA_DOB",
        "902869": "CONTROLLED_NAME_VARIANT", "1076666": "CONTROLLED_NAME_VARIANT", "1197994": "EXACT_PROFILE_DOB_NAME",
        "1296109": "CONTROLLED_NAME_VARIANT", "720286": "EXISTING_OVERRIDE_NAME_DOB", "1181959": "CONTROLLED_NAME_VARIANT",
        "1189059": "CONTROLLED_NAME_VARIANT", "1442800": "CONTROLLED_NAME_VARIANT", "1237420": "CONTROLLED_NAME_VARIANT",
        "1152080": "CONTROLLED_NAME_VARIANT",
    }
    controlled_native = {
        "1184725": "Jef Godelaine", "467632": "Cristian Cásseres", "1297674": "Mezian Soares",
        "1086915": "Raffie Benzzine", "1047861": "Martim Watts", "746358": "Daniel Júnior",
        "1241219": "Khaly", "902869": "Ricardo Rocha", "1093061": "Santiago Verdi",
        "1076666": "Ahmet Bircan", "1296109": "Ömer Kara", "1181959": "İbrahim Alkış",
        "1189059": "Berk Çukurcu", "1442800": "Prince Martor", "1237420": "Efe Üstün",
        "1152080": "Erol Çolak", "1197994": "Hasan Ege Akdoğan",
    }
    rows = []
    for pid in sorted(IDS, key=int):
        roster, override = rosters[pid], overrides.get(pid)
        p = profiles.get(pid) or {
            "source": (override or {}).get("profile_source", roster.get("profile_url", "")),
            "source_sha256": (override or {}).get("profile_sha256", ""),
            "dob": (override or {}).get("dob", roster.get("dob", "")),
        }
        dob = date_value((override or {}).get("dob") or p.get("dob"))
        candidate = None
        if override and override.get("native_fifa_id") not in {"", "0"}:
            candidate = by_fifa_dob.get((override["native_fifa_id"], dob))
        if not candidate and override:
            candidate = by_name_dob.get(((override.get("native_name") or "").casefold(), dob))
        if not candidate:
            # Controlled variants are bound to the reviewed native club and
            # DOB; names are already recorded in the first worker artifact.
            target = (override or {}).get("target_club_id", "")
            if target:
                candidate = by_dob_club.get((dob, target))
            else:
                candidate = by_dob_club.get((dob, roster.get("club_tm_id") or ""))
        if not candidate and pid in controlled_native:
            candidate = by_name_dob.get((controlled_native[pid].casefold(), dob))
        if not candidate:
            raise ValueError(f"Could not rebuild confirmed identity {pid}")
        target = (override or {}).get("target_club_id") or candidate["club_id"]
        rows.append({
            "league": roster["league"], "club": roster["club"], "player_tm_id": pid,
            "source_player_name": roster["player"], "dob": dob,
            "native_fm_id": candidate["fm_id"], "native_fifa_id": candidate["fifa_id"],
            "native_name": candidate["name"], "native_dob": date_value(candidate["dob"]),
            "native_club_id": candidate["club_id"], "target_club_id": target,
            "status": "CONFIRMED", "identity_method": methods[pid],
            "source_url": p["source"], "source_sha256": p["source_sha256"],
            "queue_source": roster["source"], "queue_source_sha256": roster["source_sha256"],
            "provenance": f"Fresh profile {p['source']} sha256={p['source_sha256']}; Native08 reread current FIFA+DOB/name bridge via {methods[pid]}; no FM-only bridge.",
        })
    fields = list(rows[0])
    with (OUT / "identity-confirmed.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    (OUT / "identity-confirmed.json").write_text(json.dumps({"schema": 1, "snapshot_date": "2026-09-12", "confirmed_rows": len(rows), "canonical_mutation": False, "source": "first south-west identity-resolution batch"}, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"confirmed_rows": len(rows), "path": str(OUT / 'identity-confirmed.csv')}))


if __name__ == "__main__":
    main()
