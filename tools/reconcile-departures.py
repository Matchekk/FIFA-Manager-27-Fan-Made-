"""Rebuild bidirectional coverage and guarded outside-scope departure proposals."""
import datetime as dt
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fm27.common import read_csv, write_csv, write_json, sha256
from fm27.transfer_timeline import canonical_events, departure_plan
from fm27.transfermarkt import parse_profile
from fm27.loans import plan_loans, plan_current_loans
from fm27.free_agents import plan_free_agents
from fm27.expired_loans import plan_expired_loans
from fm27.primary_loans import load_primary_loans
from fm27.player_identities import load_player_identities
from fm27.historical_transfers import load_historical_transfers
from fm27.reviewed_rosters import load_primary_roster_reviews, reviewed_departure_target

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--baseline", type=Path, default=root / "data/intermediate/baseline-final")
parser.add_argument("--no-project-status", action="store_true",
                    help="Write reconciliation reports without replacing the separately validated cumulative project status")
args = parser.parse_args()
args.baseline = args.baseline.resolve()
print("Verifying native baseline identity binding", flush=True)
if (args.baseline / "NATIVE_ID_BINDING.json").exists():
    binding = json.loads((args.baseline / "NATIVE_ID_BINDING.json").read_text(encoding="utf-8"))
    if (sha256(args.baseline / "players.csv") != binding["bound_players_sha256"] or
        sha256(Path(binding["native"])) != binding["native_sha256"] or
        sha256(Path(binding["baseline_players"])) != binding["baseline_players_sha256"]):
        raise ValueError("Native baseline identity binding evidence changed")
events = read_csv(root / "data/intermediate/transfer-events.csv")
roster = read_csv(root / "data/intermediate/tm-squads.csv")
current = read_csv(root / "reports/local/current/TRANSFER_DIFF.csv")
meta = json.loads((root / "reports/local/TM_SQUADS_FETCH.json").read_text(encoding="utf-8"))
snapshot = meta["DATABASE_SNAPSHOT_DATE"]
profiles_path = root / "data/intermediate/departure-profiles.csv"
profiles = read_csv(profiles_path) if profiles_path.exists() else []
source_digests = sorted({r["source_sha256"] for r in events + roster + profiles})
print(f"Verifying {len(source_digests)} cached source hashes", flush=True)
for source_index, digest in enumerate(source_digests, 1):
    if sha256(root / "data/raw/transfermarkt" / (digest + ".html")) != digest:
        raise ValueError("Source hash mismatch")
    if source_index % 500 == 0 or source_index == len(source_digests):
        print(f"Source hashes verified: {source_index}/{len(source_digests)}", flush=True)
# Reparse immutable cached HTML with the current schema, never silently refresh it.
parsed_profiles = []
for profile_index, r in enumerate(profiles, 1):
    parsed_profiles.append({**r, **parse_profile((root / "data/raw/transfermarkt" / (r["source_sha256"] + ".html")).read_text(encoding="utf-8-sig"), r["player_tm_id"])})
    if profile_index % 500 == 0 or profile_index == len(profiles):
        print(f"Profiles reparsed: {profile_index}/{len(profiles)}", flush=True)
profiles = parsed_profiles
primary_events, primary_evidence = load_primary_loans(root, snapshot, profiles)
events += primary_events
if any(r["snapshot_date"] != snapshot for r in roster + profiles) or any(r["source_date"] != snapshot for r in current):
    raise ValueError("Mixed snapshot dates")
aliases = json.loads((root / "config/tm-club-aliases.json").read_text(encoding="utf-8"))
external = root / "data/overrides/external_clubs.csv"
if external.exists():
    for row in read_csv(external):
        if not all(row.get(k) for k in ("reason", "source", "date", "author", "club_id", "club_tm_id")):
            raise ValueError("Club override lacks provenance")
        if row["club_tm_id"] in aliases:
            raise ValueError("Club override shadows existing alias")
        aliases[row["club_tm_id"]] = row
players = read_csv(args.baseline / "players.csv")
profiles, identity_evidence = load_player_identities(root, snapshot, profiles, players, args.baseline / "players.csv", aliases)
historical_events, historical_evidence = load_historical_transfers(root, snapshot, profiles, players, aliases, events,
    baseline_path=args.baseline/"players.csv")
events += historical_events
canonical = canonical_events(events, snapshot)
rows, plans = departure_plan(players, read_csv(root / "data/intermediate/baseline-final/clubs.csv"),
                            canonical, profiles, aliases, snapshot, roster)
current_tm_ids = {r["player_tm_id"] for r in roster}
loan_reports, loan_plans = plan_loans(players, read_csv(root / "data/intermediate/baseline-final/clubs.csv"),
                                    [p for p in profiles if p["player_tm_id"] not in current_tm_ids], canonical, aliases, snapshot)
current_loan_reports, current_loan_plans = plan_current_loans(players, read_csv(root / "data/intermediate/baseline-final/clubs.csv"),
                                                            profiles, canonical, aliases, snapshot, current)
loan_reports += current_loan_reports
loan_plans += current_loan_plans
free_reports, free_plans = plan_free_agents(players, profiles, canonical, aliases, snapshot, roster)
# A conflicting primary roster remains a hold, including for outside-scope departures.
official = {}
official_observations = read_csv(root / "reports/local/germany/TRANSFER_DIFF.csv")
primary_reviews, primary_review_evidence = load_primary_roster_reviews(root, snapshot, players,
    args.baseline / "players.csv", roster, profiles, official_observations,
    read_csv(args.baseline / "clubs.csv"))
for r in official_observations:
    if r.get("fm_id") and r.get("source_status") == "CONFIRMED" and r["classification"] != "AMBIGUOUS":
        official.setdefault(r["fm_id"], set()).add(r["new_club"])
held = set()
club_names = {c["club_id"]: c["club"] for c in read_csv(root / "data/intermediate/baseline-final/clubs.csv")}
for r in rows:
    if (r["database_action"] == "STAGE_CURRENT_SQUAD" and official.get(r["fm_id"])
            and club_names.get(r["new_club_id"]) not in official[r["fm_id"]]
            and not reviewed_departure_target(r, current, primary_reviews)):
        r.update(status="CONFLICT", database_action="REVIEW_REQUIRED", reason="PRIMARY_ROSTER_CONTRADICTS_DEPARTURE")
        held.add(r["fm_id"])
plans = [p for p in plans if p["fm_id"] not in held]
for r in loan_reports:
    if r["status"] == "VALID" and (r["fm_id"] in primary_reviews or
            (official.get(r["fm_id"]) and club_names.get(r["borrower_club_id"]) not in official[r["fm_id"]])):
        r.update(status="MANUAL_REVIEW", reason="Primary roster contradicts borrower")
        held.add(r["fm_id"])
loan_plans = [p for p in loan_plans if p["fm_id"] not in held]
for r in free_reports:
    if r["status"] == "CONFIRMED" and official.get(r["fm_id"]):
        r.update(status="CONFLICT", reason="PRIMARY_ROSTER_CONTRADICTS_RELEASE")
        held.add(r["fm_id"])
free_plans = [p for p in free_plans if p["fm_id"] not in held]
# Integrate typed outcomes into the bidirectional person report, retaining their
# separate detailed plan/validation reports. A reviewed alias is never enough.
typed_outcomes = {r["player_tm_id"]: ("STAGE_LOAN", r["borrower_club_id"], r["reason"])
                  for r in loan_reports if r["status"] == "VALID"}
typed_outcomes.update({r["player_tm_id"]: ("STAGE_FREE_AGENT", "0", r["reason"])
                       for r in free_reports if r["status"] == "CONFIRMED"})
for r in rows:
    if r["player_tm_id"] in typed_outcomes and r["status"] != "CONFLICT":
        action, target, reason = typed_outcomes[r["player_tm_id"]]
        r.update(status="CONFIRMED", database_action=action, new_club_id=target, reason=reason)
current_loan_valid = {r["player_tm_id"]: r for r in loan_reports if r["status"] == "VALID"}
expired_reports, expired_plans = plan_expired_loans(players, read_csv(args.baseline / "clubs.csv"),
    current, profiles, canonical, aliases, snapshot)
expired_valid = {r["fm_id"]: r for r in expired_reports if r["status"] == "CONFIRMED"}
for r in current:
    if r["player_tm_id"] in current_loan_valid and r["status"] != "CONFLICT":
        r.update(status="CONFIRMED", database_action="STAGE_LOAN", reason="Current roster identity and typed native loan evidence agree")
    elif r["fm_id"] in expired_valid and r["status"] == "REVIEW_REQUIRED":
        r.update(status="CONFIRMED", database_action="STAGE_EXPIRED_LOAN_RESOLUTION", reason=expired_valid[r["fm_id"]]["reason"])
write_csv(root / "reports/CURRENT_SQUAD_TYPED_DIFF.csv", list(current[0]), current)
plan_fields = ["fm_id", "fifa_id", "dob", "old_club_id", "new_club_id", "joined", "contract_until",
               "shirt_number", "team_type", "status", "source", "source_sha256", "snapshot_date"]
write_csv(root / "data/intermediate/departure-plan.csv", plan_fields, plans)
write_csv(root / "data/intermediate/loan-plan.csv", plan_fields + ["loan_owner_club_id", "loan_end", "action",
    "previous_loan_owner_club_id", "previous_loan_start", "previous_loan_end", "previous_loan_buy_option",
    "acquisition_seller_club_id", "acquisition_event_key", "acquisition_date", "acquisition_source", "acquisition_source_sha256"], loan_plans)
write_csv(root / "data/intermediate/free-agent-plan.csv", plan_fields + ["loan_owner_club_id", "loan_end", "action"], free_plans)
write_csv(root / "data/intermediate/expired-loan-plan.csv", plan_fields + ["loan_owner_club_id", "loan_end", "action",
    "previous_loan_owner_club_id", "previous_loan_start", "previous_loan_end", "previous_loan_buy_option"], expired_plans)
if expired_reports:
    write_csv(root / "reports/EXPIRED_LOAN_RECONCILIATION.csv", list(expired_reports[0]), expired_reports)
write_json(root / "reports/local/EXPIRED_LOAN_RECONCILIATION.json", {
    "snapshot_date": snapshot, "plans": len(expired_plans), "cases": len(expired_reports),
    "statuses": dict(Counter(r["status"] for r in expired_reports)),
    "reasons": dict(Counter(r["reason"] for r in expired_reports)),
    "status": "SOURCE_PLAN_REQUIRES_NATIVE_CANDIDATE_VALIDATION",
    "plan_sha256": sha256(root / "data/intermediate/expired-loan-plan.csv"),
    "current_report_sha256": sha256(root / "reports/local/current/TRANSFER_DIFF.csv"),
    "baseline_sha256": sha256(args.baseline / "players.csv"), "release_ready": False})
if free_reports:
    write_csv(root / "reports/FREE_AGENT_RECONCILIATION.csv", list(free_reports[0]), free_reports)
if loan_reports:
    write_csv(root / "reports/LOAN_VALIDATION.csv", list(loan_reports[0]), loan_reports)
conflicts = [r for r in rows if r["reason"] == "STARTING_CONDITION_CONFLICT"]
write_csv(root / "reports/STARTING_CONDITION_CONFLICTS.csv", list(rows[0]), conflicts)
write_csv(root / "reports/DEPARTURE_RECONCILIATION.csv", list(rows[0]), rows)
write_csv(root / "reports/TRANSFER_EVENTS_CANONICAL.csv", list(dict.fromkeys(k for event in canonical for k in event)), canonical)
target_teams = {(aliases[r["club_tm_id"]]["club_id"], aliases[r["club_tm_id"]].get("team_type", "FIRST")): r["league"]
                for r in roster}
observed_native = {r["fm_id"] for r in current + rows if r["fm_id"]}
unaccounted = [{"fm_id": p["fm_id"], "fifa_id": p["fifa_id"], "player": p["name"], "dob": p["dob"],
                "club_id": p["club_id"], "club": p["club"], "team_type": p["squad"],
                "league": target_teams[(p["club_id"], p["squad"])], "snapshot_date": snapshot,
                "status": "REVIEW_REQUIRED", "database_action": "NO_AUTOMATIC_REMOVAL",
                "reason": "Installed senior member lacks matched current roster or reconciled departure identity; absence is not a confirmed departure"}
               for p in players if (p["club_id"], p["squad"]) in target_teams and p["fm_id"] not in observed_native]
write_csv(root / "reports/UNACCOUNTED_SQUAD_MEMBERS.csv", ["fm_id", "fifa_id", "player", "dob", "club_id", "club", "team_type",
    "league", "snapshot_date", "status", "database_action", "reason"], unaccounted)
matrix = []
for league, coverage in meta["coverage"].items():
    league_rows = [r for r in current if r["league"] == league]
    departures = [r for r in rows if league in json.loads(r["leagues"])]
    league_events = [e for e in canonical if any(o["league"] == league for o in json.loads(e["observations"]))]
    matrix.append({"league": league, "snapshot_date": snapshot, "target_clubs": coverage["expected"],
                   "captured_clubs": coverage["fetched"], "squad_entries": len(league_rows),
                   "squad_entries_confirmed": sum(r["status"] == "CONFIRMED" for r in league_rows),
                   "squad_entries_review": sum(r["status"] != "CONFIRMED" for r in league_rows),
                   "missing_players": sum(r["confidence"] == "MISSING_FROM_FM" for r in league_rows),
                   "unique_events": len(league_events), "future_events": sum(e["timeline_status"] == "FUTURE" for e in league_events),
                   "event_conflicts": sum(e["timeline_status"] == "CONFLICT" for e in league_events),
                   "outside_roster_departure_people": len(departures),
                   "departure_people_confirmed": sum(r["status"] == "CONFIRMED" for r in departures),
                   "departure_people_review": sum(r["status"] != "CONFIRMED" for r in departures),
                   "unaccounted_installed_members": sum(r["league"] == league for r in unaccounted),
                   "transfer_gate": "NOT_PASSED"})
write_csv(root / "reports/TRANSFER_COVERAGE_MATRIX.csv", list(matrix[0]), matrix)
summary = {"snapshot_date": snapshot, "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
           "raw_event_rows": len(events), "canonical_events": len(canonical),
           "primary_loan_announcements": len(primary_events),
           "event_statuses": dict(Counter(e["timeline_status"] for e in canonical)),
           "event_types": dict(Counter(e["transfer_type"] for e in canonical)),
           "outside_roster_departure_people": len(rows), "departure_plan_rows": len(plans),
           "unaccounted_installed_members": len(unaccounted),
           "departure_club_changes": sum(p["old_club_id"] != p["new_club_id"] for p in plans),
           "loan_plan_rows": len(loan_plans), "loan_statuses": dict(Counter(r["status"] for r in loan_reports)),
           "expired_loan_plan_rows": len(expired_plans),
           "successor_loan_plan_rows": sum(p["action"] == "REPLACE_EXPIRED_LOAN" for p in loan_plans),
           "purchase_loan_plan_rows": sum(p["action"] == "PURCHASE_AND_LOAN" for p in loan_plans),
           "free_agent_plan_rows": len(free_plans), "free_agent_statuses": dict(Counter(r["status"] for r in free_reports)),
           "departure_review_reasons": dict(Counter(r["reason"] for r in rows if r["status"] != "CONFIRMED")),
           "input_sha256": {str(p.relative_to(root)): sha256(p) for p in [root / "data/intermediate/transfer-events.csv",
                               root / "data/intermediate/tm-squads.csv", args.baseline / "players.csv"]},
           "release_ready": False}
write_json(root / "reports/local/DEPARTURE_RECONCILIATION.json", summary)
write_json(root / "reports/local/DEPARTURE_INPUTS.json", {
    "snapshot_date": snapshot, "generated_at": summary["generated_at"],
    "profile_rows_consumed": len(profiles),
    "primary_loan_announcements": primary_evidence,
    "reviewed_historical_transfers": historical_evidence,
    "reviewed_player_identities": identity_evidence,
    "reviewed_primary_rosters": primary_review_evidence,
    "profiles": [{k: r[k] for k in ("player_tm_id", "source", "source_sha256", "retrieved_at", "snapshot_date")}
                 for r in profiles],
    "club_alias_sha256": sha256(root / "config/tm-club-aliases.json"),
    "external_club_overrides_sha256": sha256(external) if external.exists() else None,
    "departure_plan_sha256": sha256(root / "data/intermediate/departure-plan.csv"),
    "loan_plan_sha256": sha256(root / "data/intermediate/loan-plan.csv"),
    "free_agent_plan_sha256": sha256(root / "data/intermediate/free-agent-plan.csv"),
    "expired_loan_plan_sha256": sha256(root / "data/intermediate/expired-loan-plan.csv"),
    "code_sha256": {str(p.relative_to(root)): sha256(p) for p in [root / "src/fm27/transfer_timeline.py",
        root / "src/fm27/historical_transfers.py", root / "src/fm27/reviewed_rosters.py",
        root / "src/fm27/loans.py", root / "src/fm27/loan_contracts.py", root / "src/fm27/purchase_loans.py", root / "src/fm27/primary_loans.py", root / "src/fm27/free_agents.py", root / "src/fm27/expired_loans.py",
        root / "src/fm27/matching.py", root / "src/fm27/contracts.py", root / "src/fm27/player_identities.py", root / "src/fm27/ea.py", root / "src/fm27/transfermarkt.py", Path(__file__)]}})
all_plans = read_csv(root / "data/intermediate/current-squad-plan.csv") + plans + loan_plans + free_plans + expired_plans
plan_people = {p["fm_id"]: p for p in all_plans}
test_file = root / "reports/local/AUTOMATED_TESTS.json"
test_status = json.loads(test_file.read_text(encoding="utf-8")) if test_file.exists() else {}
previous_candidate = json.loads((root / "reports/local/CANDIDATE_VALIDATION.json").read_text(encoding="utf-8"))
project_status = {
    "snapshot_date": snapshot, "generated_at": summary["generated_at"], "target_leagues": len(matrix),
    "target_clubs": sum(r["target_clubs"] for r in matrix),
    "transfer_coverage_percent": None, "transfer_coverage_note": "Capture is not validated transfer coverage; all club gates remain open",
    "captured_clubs": sum(r["captured_clubs"] for r in matrix),
    "unaccounted_installed_members": len(unaccounted),
    "confirmed_transfers": sum(r["old_club_id"] != r["new_club_id"] for r in plan_people.values()),
    "overlapping_plan_rows": len(all_plans) - len(plan_people),
    "confirmed_transfers_note": "Source-backed staging proposals, not installed or game-tested transfers",
    "loans_validated": 0, "loan_evidence_validated": len(loan_plans),
    "expired_loans_evidence_validated": len(expired_plans),
    "successor_loans_evidence_validated": sum(p["action"] == "REPLACE_EXPIRED_LOAN" for p in loan_plans),
    "purchase_loans_evidence_validated": sum(p["action"] == "PURCHASE_AND_LOAN" for p in loan_plans),
    "free_agents_evidence_validated": len(free_plans), "free_agents_native_validated": 0,
    "missing_players": len({r["player_tm_id"] for r in current if r["confidence"] == "MISSING_FROM_FM"}),
    "ratings_updated": 0, "database_roundtrip": previous_candidate.get("status", "NOT_RUN"),
    "database_roundtrip_note": "Historical frozen candidate projection only; current proposal plans have separate validation",
    "automated_tests": {k: test_status.get(k) for k in ("status", "tests", "run_at")},
    "career_start_test": "NOT_RUN", "save_load_test": "NOT_RUN", "season_transition_test": "NOT_RUN", "release_ready": False}
validated_file = root / "reports/local/PRODUCTION_DB_VALIDATION.json"
if validated_file.exists():
    validated = json.loads(validated_file.read_text(encoding="utf-8"))
    if validated.get("player_validation") == "PASS":
        project_status.update(latest_validated_candidate=validated["candidate"],
                              database_roundtrip=("FAIL" if validated["status"]=="FAIL" else
                                  "NATIVE_OBJECTS_PASS_GAME_EXPORT_PENDING"
                                  if (validated.get("expanded_world_validation") or {}).get("status") == "PASS"
                                  and (validated.get("expanded_world_validation") or {}).get("global_entities")
                                  else "PLAYER_PASS_WORLD_NOT_VALIDATED"),
                              loans_validated=validated["loans_native_reread_validated"],
                              free_agents_native_validated=validated.get("free_agents_native_reread_validated", 0),
                              expired_loans_native_validated=validated.get("expired_loans_native_reread_validated", 0),
                              successor_loans_native_validated=validated.get("successor_loans_native_reread_validated", 0),
                              purchase_loans_native_validated=validated.get("purchase_loans_native_reread_validated", 0),
                              extended_native_validation=validated.get("extended_native_validation", "NOT_RUN"),
                              database_roundtrip_note="Frozen validated candidate only: " + validated["plan_sha256"])
if not args.no_project_status:
    write_json(root / "reports/PROJECT_STATUS.json", project_status)
print(json.dumps(summary))
