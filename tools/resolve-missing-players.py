"""Global duplicate-prevention review before any new native person is created."""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fm27.common import read_csv, write_csv, write_json, sha256
from fm27.matching import IdentityIndex, recover_profile_identity
from fm27.player_identities import load_player_identities, verified_profile
from fm27.missing_player_review import DuplicateReviewIndex

root = Path(__file__).resolve().parents[1]
baseline = root / "data/intermediate/native-bound-baseline"
binding = json.loads((baseline / "NATIVE_ID_BINDING.json").read_text(encoding="utf-8"))
if (sha256(baseline / "players.csv") != binding["bound_players_sha256"] or
        sha256(Path(binding["native"])) != binding["native_sha256"] or
        sha256(Path(binding["baseline_players"])) != binding["baseline_players_sha256"]):
    raise ValueError("Native baseline identity binding changed")
players = read_csv(baseline / "players.csv")
rosters = read_csv(root / "data/intermediate/tm-squads.csv")
ea = read_csv(root / "data/intermediate/ea-fc27.csv")
unmatched = read_csv(root / "reports/local/current/UNMATCHED_PLAYERS.csv")
index = IdentityIndex(players)
duplicate_review = DuplicateReviewIndex(players)
ea_index = IdentityIndex([{**p, "name": p["player"]} for p in ea])
source_index = {p["player_tm_id"]: p for p in rosters}
profile_file = root / "data/intermediate/departure-profiles.csv"
profile_rows = read_csv(profile_file) if profile_file.exists() else []
if len({p["player_tm_id"] for p in profile_rows}) != len(profile_rows):
    raise ValueError("Duplicate missing-player profile identities")
snapshot = json.loads((root / "reports/local/TM_SQUADS_FETCH.json").read_text(encoding="utf-8"))["DATABASE_SNAPSHOT_DATE"]
needed = {r["player_tm_id"] for r in unmatched}
# The loader additionally verifies every reviewed profile, even if now matched.
review_path = root / "data/overrides/player_identities.json"
if review_path.exists():
    needed.update(r["player_tm_id"] for r in json.loads(review_path.read_text(encoding="utf-8"))["rows"])
profile_rows = [verified_profile(root, p, snapshot) if p["player_tm_id"] in needed else p for p in profile_rows]
aliases = json.loads((root / "config/tm-club-aliases.json").read_text(encoding="utf-8"))
profile_rows, identity_evidence = load_player_identities(root, snapshot, profile_rows, players, baseline / "players.csv", aliases)
profiles = {p["player_tm_id"]: p for p in profile_rows}
rows = []
seen = set()
for r in unmatched:
    if r["player_tm_id"] in seen:
        continue
    seen.add(r["player_tm_id"])
    source = source_index[r["player_tm_id"]]
    method, candidates = index.match({"player": r["player"], "dob": r["dob"], "fifa_id": r["fifa_id"]})
    fallback, alternative = index.match({"player": r["player"], "dob": r["dob"]})
    ea_method, ea_candidates = ea_index.match(source)
    names = {r["player"]}
    profile = profiles.get(r["player_tm_id"], {})
    profile_conflict = False
    profile_club_conflict = False
    if profile:
        if profile["snapshot_date"] != source["snapshot_date"] or sha256(root / "data/raw/transfermarkt" / (profile["source_sha256"] + ".html")) != profile["source_sha256"]:
            raise ValueError("Profile snapshot/hash mismatch")
        profile_conflict = profile["dob"] != r["dob"]
        profile_club_conflict = profile["club_tm_id"] != source["club_tm_id"]
        if not profile_conflict:
            names.update([profile["player"], profile["full_name"]])
    if ea_method == "DOB_NAME":
        names.update([ea_candidates[0]["player"], ea_candidates[0]["common_name"]])
    global_matches = {id(p): p for p in candidates + alternative}
    reviewed_method, reviewed = recover_profile_identity(index,
        {**source, "fifa_id": r["fifa_id"]}, profile, snapshot, source["club_tm_id"], r["new_club_id"])
    global_matches.update({id(p): p for p in reviewed})
    for name in names - {""}:
        _, found = index.match({"player": name, "dob": r["dob"]})
        global_matches.update({id(p): p for p in found})
    # Cross-club full-name components and nearby/same-club DOB discrepancies
    # only block unreviewed creation. They never authorize a transfer or DOB edit.
    leads, lead_reasons = duplicate_review.candidates(source, profile, snapshot, r["new_club_id"])
    global_matches.update({id(p): p for p in leads})
    matches = list(global_matches.values())
    status = "EXISTING_PERSON_REVIEW" if matches else "PROFILE_EVIDENCE_REQUIRED"
    if matches and r["fifa_id"] not in {"", "0"} and any(p["fifa_id"] not in {"0", "", r["fifa_id"]} for p in matches):
        status = "FIFA_ID_CONFLICT"
    if len(matches) > 1:
        status = "IDENTITY_CONFLICT"
    elif matches and matches[0]['dob'] != r['dob'] and status != 'FIFA_ID_CONFLICT':
        status = 'BIRTH_DATE_CONFLICT'
    if reviewed_method in {"CONFLICT", "AMBIGUOUS"} and status != "FIFA_ID_CONFLICT":
        status = "IDENTITY_CONFLICT"
    if profile_conflict:
        status = "SOURCE_DOB_CONFLICT"
    elif profile_club_conflict:
        status = "SOURCE_CLUB_CONFLICT"
    missing_evidence = []
    if not matches:
        usable_profile = bool(profile) and not profile_conflict and not profile_club_conflict and profile.get("source_status") == "CONFIRMED"
        for field in ("nationality_text", "position", "foot", "height", "joined", "contract_until"):
            if not usable_profile or not profile.get(field):
                missing_evidence.append(field)
        # Cached TM profiles and EA league rows do not establish a weight or a
        # calibrated native FM attribute profile. These are still required.
        missing_evidence.extend(["verified_weight", "native_attribute_calibration", "final_duplicate_review"])
        if usable_profile and profile.get("loan_owner_tm_id"):
            missing_evidence.append("new_player_loan_owner_and_return_semantics")
    rows.append({"player_tm_id": r["player_tm_id"], "player": r["player"], "dob": r["dob"], "fifa_id": r["fifa_id"],
                 "target_club_id": r["new_club_id"], "status": status, "database_action": "REVIEW_REQUIRED",
                 "global_fifa_check": method, "global_dob_name_check": fallback,
                 "candidate_review_basis": json.dumps(lead_reasons, ensure_ascii=False),
                 "candidates": json.dumps([{k: p[k] for k in ("fm_id", "fifa_id", "name", "dob", "club_id", "squad", "source_file", "source_line")}
                                            for p in matches], ensure_ascii=False),
                 "searched": "ALL_NATIVE_PROJECTION_PLAYERS_INCLUDING_FREE_AGENTS_YOUTH_RESERVES_EA_AND_VERIFIED_PROFILE_NAMES",
                 "creation_missing_evidence": "; ".join(missing_evidence),
                 "verified_profile_fields": json.dumps({k: profile.get(k, "") for k in ("full_name", "nationality_text", "position", "foot", "height", "joined", "contract_until")}, ensure_ascii=False) if profile and not profile_conflict and not profile_club_conflict else "{}",
                 "source": source["source"], "source_sha256": source["source_sha256"], "snapshot_date": source["snapshot_date"],
                 "profile_source": profile.get("source", ""), "profile_sha256": profile.get("source_sha256", "")})
write_csv(root / "reports/PLAYER_CREATION_REVIEW.csv", list(rows[0]), rows)
created = root / "reports/CREATED_PLAYERS.csv"
if not created.exists():
    write_csv(created, ["player_tm_id", "fifa_id", "name", "dob", "club_id", "native_id", "source", "snapshot_date", "status"], [])
write_json(root / "reports/local/PLAYER_CREATION_REVIEW.json", {
    "reviewed_people": len(rows), "statuses": dict(Counter(r["status"] for r in rows)),
    "global_players_searched": len(players), "created_players": len(read_csv(created)),
    "snapshot_date": rows[0]["snapshot_date"],
    "unmatched_input_sha256": sha256(root / "reports/local/current/UNMATCHED_PLAYERS.csv"),
    "baseline_sha256": sha256(baseline / "players.csv"),
    "reviewed_player_identities": identity_evidence,
    "limitations": "No person is created from an unmatched roster alone. Alternate spellings beyond current EA names and full biographical evidence remain review work."})
print(json.dumps({"reviewed_people": len(rows), "statuses": dict(Counter(r["status"] for r in rows))}))
