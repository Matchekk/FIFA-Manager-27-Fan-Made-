"""Bind desired 2026/27 league membership to immutable sources and inspect fixtures."""
import argparse
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fm27.common import read_csv, write_csv, write_json, sha256
from fm27.competitions import parse_leagues, fixture_errors
from fm27.team_scope import decode_reference

p = argparse.ArgumentParser()
p.add_argument("--database", type=Path, required=True)
a = p.parse_args()
root = Path(__file__).resolve().parents[1]
scope = json.loads((root / "config/scope.json").read_text(encoding="utf-8"))
aliases = json.loads((root / "config/tm-club-aliases.json").read_text(encoding="utf-8"))
metadata = json.loads((root / "reports/local/TM_SQUADS_FETCH.json").read_text(encoding="utf-8"))
snapshot = metadata["DATABASE_SNAPSHOT_DATE"]
roster = read_csv(root / "data/intermediate/tm-squads.csv")
clubs = {c["club_id"]:c for c in read_csv(root / "data/intermediate/baseline-final/clubs.csv")}
references = {int(c["reference_id"]):c for c in clubs.values()}
sources = {}
for row in roster:
    if row["snapshot_date"] != snapshot:
        raise ValueError("Mixed league roster source dates")
    sources[row["source_sha256"]] = row["source"]
for digest in sources:
    if sha256(root / "data/raw/transfermarkt" / (digest + ".html")) != digest:
        raise ValueError("Roster source hash mismatch")
league_scripts = {}
script_hashes = {}
for country in {r["country_id"] for r in scope["competitions"]}:
    path = a.database / "script" / f"CountryScript{country}.sav"
    script_hashes[str(path.resolve())] = sha256(path)
    league_scripts[country] = parse_leagues(path.read_text(encoding="utf-8-sig"))
def describe(ref):
    base, team = decode_reference(ref)
    if base not in references:
        raise ValueError("Unresolved concrete league team reference")
    club = references[base]
    return {"club_id":club["club_id"], "club":club["club"], "team_type":team, "reference":ref}
rows, details = [], []
desired_global = set()
for config in scope["competitions"]:
    league = config["key"]
    selected = [r for r in league_scripts[config["country_id"]] if r["competition_type"] == "LEAGUE" and r["division"] == config["division"]]
    if len(selected) != 1:
        raise ValueError("Missing/ambiguous scoped native league")
    native = selected[0]
    observed = {}
    for r in roster:
        if r["league"] != league:
            continue
        alias = aliases[r["club_tm_id"]]
        club = clubs[alias["club_id"]]
        if int(club["country_id"]) != config["country_id"]:
            raise ValueError("League alias country mismatch")
        team = alias["team_type"]
        if team not in {"FIRST", "RESERVE"}:
            raise ValueError("Unsupported target league team type")
        ref = int(club["reference_id"]) | (0x1000000 if team == "RESERVE" else 0)
        observed[r["club_tm_id"]] = {**describe(ref), "source":r["source"], "source_sha256":r["source_sha256"]}
    desired = {r["reference"] for r in observed.values()}
    if len(desired) != len(observed) or len(observed) != metadata["coverage"][league]["expected"] or desired & desired_global:
        raise ValueError("Missing, duplicated or cross-league target membership")
    desired_global |= desired
    installed = set(native["team_references"])
    added, removed = desired - installed, installed - desired
    errors = fixture_errors(native)
    rows.append({"league":league, "snapshot_date":snapshot, "installed_teams":native["team_count"], "desired_teams":len(desired),
                 "added_teams":len(added), "removed_teams":len(removed), "installed_rounds":native["rounds"],
                 "installed_matchdays":len(native["matchdays"]), "installed_fixture_errors":json.dumps(errors),
                 "format_change_required":native["team_count"] != len(desired),
                 "status":"REVIEW_REQUIRED" if added or removed or errors else "MEMBERSHIP_ONLY_MATCHES",
                 "gate_D":"NOT_PASSED"})
    details.append({"league":league, "installed":{k:v for k,v in native.items() if k != "raw_block"},
                    "native_block_sha256":hashlib.sha256(native["raw_block"].encode()).hexdigest(),
                    "desired_members":list(observed.values()), "incoming":[describe(r) for r in sorted(added)],
                    "outgoing":[describe(r) for r in sorted(removed)],
                    "dependent_competitions":[{"competition_type":r["competition_type"], "division":r["division"],
                        "affected_references":sorted((added | removed) & set(r["team_references"]))}
                        for r in league_scripts[config["country_id"]] if r is not native and (added | removed) & set(r["team_references"])]})
write_csv(root / "reports/LEAGUE_STRUCTURE_VALIDATION.csv", list(rows[0]), rows)
write_json(root / "reports/local/LEAGUE_STRUCTURE_REVIEW.json", {"snapshot_date":snapshot, "status":"READ_ONLY_REVIEW_NOT_NATIVE_MUTATION",
    "script_sha256":script_hashes, "source_hashes":sources, "leagues":details, "release_ready":False,
    "limitations":"Membership evidence alone cannot safely change pools, promotions, relegations, playoff format, fixtures or season transitions."})
print(json.dumps(rows))
