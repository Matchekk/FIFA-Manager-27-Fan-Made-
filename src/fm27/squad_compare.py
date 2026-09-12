"""Official fantasy roster vs installed squads, with explicit evidence gaps."""
import json
from collections import Counter, defaultdict
from pathlib import Path

from .common import read_csv, sha256, write_csv, write_json
from .matching import IdentityIndex, normalize
from .sources import parse_fpl

FIELDS = ["league", "club", "player", "fifa_id", "fm_id", "old_club", "new_club",
          "transfer_type", "contract_until", "shirt_number", "source", "source_date",
          "confidence", "database_action", "classification", "dob", "status", "reason"]


def compare(export: Path, snapshot: Path, aliases_path: Path, output: Path) -> dict:
    metadata = json.loads(snapshot.with_suffix(".provenance.json").read_text(encoding="utf-8"))
    if sha256(snapshot) != metadata["sha256"]:
        raise ValueError("Source snapshot hash mismatch")
    roster = parse_fpl(json.loads(snapshot.read_text(encoding="utf-8")), 2026)
    aliases = json.loads(aliases_path.read_text(encoding="utf-8"))
    clubs = read_csv(export / "clubs.csv")
    players = read_csv(export / "players.csv")
    index = IdentityIndex(players)
    by_name = defaultdict(list)
    by_id = {c["club_id"]: c for c in clubs}
    for club in clubs:
        if club["country_id"] == "14":
            by_name[normalize(club["club"])].append(club)
    mapping = {}
    for name in {r["club"] for r in roster}:
        found = by_name[normalize(aliases.get(name, ""))]
        if len(found) != 1:
            raise ValueError(f"Club alias must resolve uniquely: {name}")
        mapping[name] = found[0]
    rows, observed = [], set()
    for evidence in roster:
        method, candidates = index.match(evidence)
        if method == "MISSING_FROM_FM" and evidence["common_name"]:
            method, candidates = index.match({**evidence, "player": evidence["common_name"]})
        p = candidates[0] if len(candidates) == 1 else {}
        if p:
            observed.add((p["source_file"], p["source_line"]))
        club = mapping[evidence["club"]]
        unchanged = p and p["club_id"] == club["club_id"]
        excluded = evidence["removed"] or evidence["fpl_status"] == "u"
        classification = "UNCHANGED" if unchanged else "TRANSFER_IN" if p else method
        if excluded:
            classification = "AMBIGUOUS"
        # Current affiliation alone cannot establish permanence vs loan, or
        # clear installed future conditions. No transfer is auto-committed.
        reason = ("Removed/unavailable fantasy record; registration must be checked" if excluded else
                  "Identity matched; verify permanent/loan/return status and installed conditions" if p else
                  f"Identity unresolved: {method}")
        rows.append({"league": "ENG1", "club": club["club"], "player": evidence["player"],
                     "fifa_id": p.get("fifa_id", ""), "fm_id": p.get("fm_id", ""),
                     "old_club": by_id.get(p.get("club_id"), {}).get("club", "FREE_AGENT" if p else ""),
                     "new_club": club["club"], "transfer_type": "UNVERIFIED", "contract_until": "",
                     "shirt_number": evidence["shirt_number"], "source": metadata["url"],
                     "source_date": metadata["retrieved_at"][:10], "confidence": "",
                     "database_action": "NO_CLUB_CHANGE" if unchanged and not excluded else "REVIEW_REQUIRED",
                     "classification": classification, "dob": evidence["dob"], "status": "REVIEW_REQUIRED",
                     "reason": reason})
    covered_ids = {c["club_id"] for c in mapping.values()}
    absent = []
    for p in players:
        if p["club_id"] in covered_ids and p["squad"] == "FIRST" and (p["source_file"], p["source_line"]) not in observed:
            absent.append({"club": p["club"], "player": p["name"], "fifa_id": p["fifa_id"],
                           "fm_id": p["fm_id"], "classification": "AMBIGUOUS", "database_action": "REVIEW_REQUIRED",
                           "reason": "Not matched in fantasy roster; absence is not evidence of departure"})
    write_csv(output / "TRANSFER_DIFF.csv", FIELDS, rows)
    write_csv(output / "UNMATCHED_PLAYERS.csv", FIELDS, (r for r in rows if not r["fifa_id"] and not r["fm_id"]))
    write_csv(output / "AMBIGUOUS_MATCHES.csv", FIELDS, (r for r in rows if r["classification"] == "AMBIGUOUS"))
    write_csv(output / "UNVERIFIED_ABSENCES.csv", FIELDS, absent)
    club_diff = [{"club_id": c["club_id"], "club": c["club"], "installed_league": c["league"],
                  "observed_league": "ENG1", "status": "MEMBERSHIP_REVIEW_REQUIRED" if c["league"] != "ENG1" else "UNCHANGED"}
                 for c in sorted(mapping.values(), key=lambda c: c["club"])]
    write_csv(output / "CLUB_DIFF.csv", list(club_diff[0]), club_diff)
    result = {"DATABASE_SNAPSHOT_DATE": metadata["retrieved_at"][:10], "season": "2026/27",
              "scope": "ENG1 official fantasy roster only; 11 other competitions not refreshed",
              "records": len(rows), "classifications": dict(Counter(r["classification"] for r in rows)),
              "unverified_absences": len(absent), "source_sha256": metadata["sha256"],
              "status": "REVIEW_ONLY_NOT_AN_UPDATED_GAME_DATABASE", "production_writes": 0}
    write_json(output / "SQUAD_COMPARISON.json", result)
    return result
