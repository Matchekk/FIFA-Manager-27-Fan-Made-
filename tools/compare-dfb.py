"""Official DFB roster evidence vs FM identities; no production writes."""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fm27.common import read_csv, sha256, write_csv, write_json
from fm27.matching import IdentityIndex, normalize
from fm27.squad_compare import FIELDS

root = Path(__file__).resolve().parents[1]
export = root / "data/intermediate/installed-teams"
out = root / "reports/local/germany"
roster = read_csv(root / "data/intermediate/dfb-rosters.csv")
metadata = json.loads((root / "reports/local/DFB_FETCH.json").read_text(encoding="utf-8"))
sources = {(s["url"], s["sha256"]) for s in metadata["sources"]}
for digest in {r["source_sha256"] for r in roster}:
    if sha256(root / "data/raw/dfb" / (digest + ".html")) != digest:
        raise ValueError("DFB evidence cache hash mismatch")
if any((r["source"], r["source_sha256"]) not in sources or r["snapshot_date"] != metadata["DATABASE_SNAPSHOT_DATE"] for r in roster):
    raise ValueError("Unprovenanced roster row")
players, clubs = read_csv(export / "players.csv"), read_csv(export / "clubs.csv")
index = IdentityIndex(players)
by_id = {c["club_id"]: c for c in clubs}
by_name = defaultdict(list)
for c in clubs:
    if c["country_id"] == "21":
        by_name[normalize(c["club"])].append(c)
aliases = json.loads((root / "config/dfb-club-aliases.json").read_text(encoding="utf-8"))
mapping, team_types = {}, {}
for name in sorted({r["club"] for r in roster}):
    found = [by_id[aliases[name]]] if name in aliases else by_name[normalize(name)]
    if len(found) != 1 or found[0]["country_id"] != "21":
        raise ValueError(f"Club needs unique verified alias: {name}")
    mapping[name] = found[0]
    team_types[name] = "RESERVE" if name.endswith(" II") else "FIRST"
rows, observed = [], set()
for evidence in roster:
    method, candidates = index.match(evidence)
    p = candidates[0] if method in {"FIFA_ID", "DOB_NAME"} else {}
    target = mapping[evidence["club"]]
    active = evidence["membership_at_snapshot"] == "True"
    conflict = evidence["source_status"] != "CONFIRMED"
    same_club = bool(p) and p["club_id"] == target["club_id"]
    same_team = same_club and p["squad"] == team_types[evidence["club"]]
    classification = "UNCHANGED" if same_team else "AMBIGUOUS" if same_club else "TRANSFER_IN" if p else method
    if conflict or not active:
        classification = "AMBIGUOUS"
    if p and active and not conflict:
        observed.add((p["source_file"], p["source_line"]))
    rows.append({"league": evidence["league"], "club": evidence["club"], "player": evidence["player"],
                 "fifa_id": p.get("fifa_id", ""), "fm_id": p.get("fm_id", ""),
                 "old_club": p.get("club", ""), "new_club": target["club"],
                 "transfer_type": "UNVERIFIED", "contract_until": "", "shirt_number": evidence["shirt_number"],
                 "source": evidence["source"], "source_date": evidence["snapshot_date"],
                 "confidence": method, "database_action": "NO_CLUB_CHANGE" if same_team and active and not conflict else "REVIEW_REQUIRED",
                 "classification": classification, "dob": evidence["dob"], "status": "CONFLICT" if conflict else "REVIEW_REQUIRED",
                 "reason": "Conflicting source rows" if conflict else "Dated membership is not current" if not active else
                           "Squad evidence only: verify ownership, loans, dates, team status and installed conditions",
                 "team_type": team_types[evidence["club"]], "source_person_id": evidence["source_person_id"],
                 "source_sha256": evidence["source_sha256"], "source_status": evidence["source_status"]})
fields = FIELDS + ["team_type", "source_person_id", "source_sha256", "source_status"]
write_csv(out / "TRANSFER_DIFF.csv", fields, rows)
write_csv(out / "UNMATCHED_PLAYERS.csv", fields, (r for r in rows if not r["fm_id"]))
write_csv(out / "AMBIGUOUS_MATCHES.csv", fields, (r for r in rows if r["classification"] in {"AMBIGUOUS", "CONFLICT"}))
covered = {(c["club_id"], team_types[n]) for n, c in mapping.items()}
absent = [{"club": p["club"], "player": p["name"], "fm_id": p["fm_id"], "fifa_id": p["fifa_id"],
           "classification": "AMBIGUOUS", "database_action": "REVIEW_REQUIRED", "reason": "No matched DFB observation; absence is not departure proof"}
          for p in players if (p["club_id"], p["squad"]) in covered and (p["source_file"], p["source_line"]) not in observed]
write_csv(out / "UNVERIFIED_ABSENCES.csv", FIELDS, absent)
installed_teams = {(t["club_id"], t["team_type"]): t["league"] for t in read_csv(export / "covered_teams.csv")}
club_rows = [{"club": name, "club_id": mapping[name]["club_id"], "team_type": team_types[name],
              "installed_league": installed_teams.get((mapping[name]["club_id"],team_types[name]), "OUTSIDE_COVERED_LEAGUES"),
              "observed_league": league, "source": next(r["source"] for r in roster if r["club"] == name)}
             for league, name in sorted({(r["league"],r["club"]) for r in roster})]
write_csv(out / "CLUB_DIFF.csv", list(club_rows[0]), club_rows)
report = {"DATABASE_SNAPSHOT_DATE": metadata["DATABASE_SNAPSHOT_DATE"], "coverage": metadata["coverage"],
          "source_failures": metadata["failures"], "records": len(rows), "classifications": dict(Counter(r["classification"] for r in rows)),
          "unverified_absences": len(absent), "production_writes": 0, "status": "REVIEW_ONLY_NOT_UPDATED_DATABASE"}
write_json(out / "SQUAD_COMPARISON.json", report)
print(json.dumps(report))
