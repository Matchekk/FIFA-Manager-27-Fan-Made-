"""Bind completed player validations to a candidate; leave unproved release gates closed."""
import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fm27.common import read_csv, write_json, sha256
from fm27.world_validation import bind_world_inspection

p = argparse.ArgumentParser()
p.add_argument("--candidate", type=Path, required=True)
p.add_argument("--reread", type=Path, required=True)
p.add_argument("--plan", type=Path, required=True)
p.add_argument("--projected-report", type=Path, required=True)
p.add_argument("--semantic-report", type=Path, required=True)
p.add_argument("--diff-report", type=Path, required=True)
p.add_argument("--extended-report", type=Path)
p.add_argument("--world-mutation-report", type=Path)
p.add_argument("--world-baseline", type=Path)
p.add_argument("--support-report", type=Path)
p.add_argument("--world-inspection", type=Path)
p.add_argument("--world-reread", type=Path)
p.add_argument("--output", type=Path, required=True)
p.add_argument("--no-project-status", action="store_true",
               help="Validate this candidate without replacing the separately validated cumulative project status")
a = p.parse_args()
if not (a.candidate / "STAGING_ONLY.txt").exists() or not (a.candidate / "DATABASE_METADATA.txt").exists():
    raise ValueError("Native staging completion metadata missing")
projected = json.loads(a.projected_report.read_text(encoding="utf-8"))
semantic = json.loads(a.semantic_report.read_text(encoding="utf-8"))
diff = json.loads(a.diff_report.read_text(encoding="utf-8"))
plan = read_csv(a.plan)
digest = sha256(a.plan)
expected_hash = sha256(a.candidate / "native_player_semantics.csv")
actual_hash = sha256(a.reread / "native_player_semantics.csv")
if projected["plan_sha256"] != digest or diff["plan_sha256"] != digest or semantic["expected_sha256"] != expected_hash or diff["expected_sha256"] != expected_hash or semantic["actual_sha256"] != actual_hash:
    raise ValueError("Validation evidence belongs to different inputs")
passed = projected["status"] == "PROJECTED_STAGE_MATCHES_PLAN" and semantic["status"] == diff["status"] == "PASS"
player_passed = passed
extended_passed = None
extended_counts = {}
if any((a.extended_report, a.world_mutation_report, a.world_baseline)):
    if not all((a.extended_report, a.world_mutation_report, a.world_baseline)):
        raise ValueError("Extended validation requires reread report, mutation-scope report and original world baseline")
    extended = json.loads(a.extended_report.read_text(encoding="utf-8"))
    world = json.loads(a.world_mutation_report.read_text(encoding="utf-8"))
    if extended["comparison"] != "NATIVE_REREAD" or world["comparison"] != "UNCHANGED_WORLD_MUTATION_SCOPE":
        raise ValueError("Wrong extended comparison mode")
    if sha256(a.world_baseline/"native_player_semantics.csv") != diff["before_sha256"]:
        raise ValueError("World baseline differs from player mutation baseline")
    for key, filename in (("staffs","native_staff_semantics.csv"),("competitions","native_competition_semantics.csv"),("relation_rows","native_player_relations.csv")):
        if (extended["checks"][key]["expected_sha256"] != sha256(a.candidate/filename) or
            extended["checks"][key]["actual_sha256"] != sha256(a.reread/filename) or
            world["checks"][key]["expected_sha256"] != sha256(a.world_baseline/filename) or
            world["checks"][key]["actual_sha256"] != sha256(a.candidate/filename)):
            raise ValueError("Extended validation evidence belongs to different inputs")
        extended_counts[key] = extended["checks"][key]["actual"]
    for report, expected_dir, actual_dir in ((extended,a.candidate,a.reread),(world,a.world_baseline,a.candidate)):
        if (report["expected_metadata_sha256"] != sha256(expected_dir/"NATIVE_EXTENDED_SEMANTICS.json") or
            report["actual_metadata_sha256"] != sha256(actual_dir/"NATIVE_EXTENDED_SEMANTICS.json")):
            raise ValueError("Extended metadata hash mismatch")
    extended_passed = extended["status"] == world["status"] == "PASS"
    passed = passed and extended_passed
support_passed = None
support_files = {}
if (a.candidate/"native_support_files.csv").exists():
    if not a.support_report:
        raise ValueError("Candidate with preserved support files requires --support-report")
    support = json.loads(a.support_report.read_text(encoding="utf-8"))
    if support["candidate"] != str(a.candidate.resolve()) or support["manifest_sha256"] != sha256(a.candidate/"native_support_files.csv"):
        raise ValueError("Support validation belongs to different inputs")
    for name, hashes in support["files"].items():
        source = (a.candidate/name).resolve()
        if not source.is_relative_to(a.candidate.resolve()) or sha256(source) != hashes["candidate_sha256"]:
            raise ValueError("Support validation is stale: " + name)
        support_files[name] = hashes["candidate_sha256"]
    support_passed = support["status"] == "PASS"
    passed = passed and support_passed
files = {str(path.relative_to(a.candidate)): sha256(path) for path in sorted((a.candidate / "database").rglob("*")) if path.is_file()}
files.update(support_files)
expanded_world = None
if a.world_inspection or a.world_reread:
    if not (a.world_inspection and a.world_reread and extended_passed):
        raise ValueError("Expanded world proof requires both exports and passed prior extended checks")
    expanded_world = bind_world_inspection(a.world_inspection, a.world_reread, plan_hash=digest,
        before_hash=diff["before_sha256"], expected_hash=expected_hash, actual_hash=actual_hash)
    passed = passed and expanded_world["status"] == "PASS"
report = {"status": "INCOMPLETE" if passed else "FAIL", "player_validation": "PASS" if player_passed else "FAIL",
          "extended_native_validation": "NOT_RUN" if extended_passed is None else "PASS" if extended_passed else "FAIL",
          "extended_native_counts": extended_counts,
          "expanded_world_validation": expanded_world,
          "native_support_validation": "NOT_RUN" if support_passed is None else "PASS" if support_passed else "FAIL",
          "validated_at": dt.datetime.now(dt.timezone.utc).isoformat(), "candidate": str(a.candidate.resolve()),
          "snapshot_date": plan[0]["snapshot_date"], "plan_sha256": digest, "planned_rows": len(plan),
          "actual_changed_players": diff["actual_changed_players"], "club_changes": diff["actual_club_changes"],
          "native_reread_players": semantic["actual_players"],
          "loans_native_reread_validated": sum(r.get("loan_owner_club_id", "0") != "0" for r in plan) if passed else 0,
          "free_agents_native_reread_validated": sum(r.get("action") == "FREE_AGENT" for r in plan) if passed else 0,
          "expired_loans_native_reread_validated": sum(r.get("action") == "RESOLVE_EXPIRED_LOAN" for r in plan) if passed else 0,
          "successor_loans_native_reread_validated": sum(r.get("action") == "REPLACE_EXPIRED_LOAN" for r in plan) if passed else 0,
          "purchase_loans_native_reread_validated": sum(r.get("action") == "PURCHASE_AND_LOAN" for r in plan) if passed else 0,
          "gates": {"A_TRANSFERS": "INCOMPLETE", "B_IDENTITIES": "NO_UNEXPECTED_PLAYER_IDENTITY_CHANGE" if diff["status"] == "PASS" else "FAIL",
                    "C_SERIALIZATION": "PLAYER_PASS_STAFF_COMPETITIONS_RELATIONS_NOT_FULLY_VALIDATED" if passed else "FAIL",
                    "D_LEAGUES": "NOT_VALIDATED", "E_RATINGS": "NOT_UPDATED", "F_CAREER": "NOT_RUN",
                    "G_SAVE_LOAD": "NOT_RUN", "H_SEASON_TRANSITION": "NOT_RUN"},
          "candidate_database_files": files, "release_ready": False,
          "limitations": "A successful native player roundtrip does not validate the entire world database or prove engine playability. No production package or installation is authorized by this report."}
if extended_passed:
    report["gates"]["C_SERIALIZATION"] = "PLAYER_STAFF_COMPETITIONS_RELATIONS_PASS_CLUB_COUNTRY_RULES_STADIUM_NOT_FULLY_VALIDATED"
if expanded_world is not None:
    report["gates"]["C_SERIALIZATION"] = ("PLAYER_STAFF_COMPETITIONS_RELATIONS_CLUBS_COUNTRIES_PASS_GLOBAL_ENTITIES_NOT_FULLY_VALIDATED"
        if expanded_world["status"] == "PASS" else "FAIL_EXPANDED_WORLD")
    if expanded_world["status"] == "PASS" and expanded_world.get("global_entities") is not None:
        report["gates"]["C_SERIALIZATION"] = "NATIVE_OBJECTS_PASS_SOURCE_FILE_COVERAGE_AUDIT_PENDING"
root = Path(__file__).resolve().parents[1]
def current_tests(filename):
    path = root / "reports/local" / filename
    if not path.exists():
        return False, {}
    data = json.loads(path.read_text(encoding="utf-8"))
    valid = data.get("status") == "PASS" and bool(data.get("source_sha256"))
    for name, digest in data.get("source_sha256", {}).items():
        source = (root / name).resolve()
        if not source.is_relative_to(root) or not source.is_file() or sha256(source) != digest:
            valid = False
    return valid, data
python_valid, python_tests = current_tests("AUTOMATED_TESTS.json")
native_valid, native_tests = current_tests("NATIVE_TESTS.json")
report["gates"]["I_AUTOMATED_TESTS"] = "PASS" if python_valid and native_valid else "MISSING_OR_STALE_EVIDENCE"
report["test_counts"] = {"python": python_tests.get("tests"), "native": native_tests.get("tests")}
write_json(a.output, report)
if a.no_project_status:
    print(json.dumps({k: v for k, v in report.items() if k != "candidate_database_files"}))
    sys.exit(not passed)
status_path = root / "reports/PROJECT_STATUS.json"
status = json.loads(status_path.read_text(encoding="utf-8"))
status.update(latest_validated_candidate=str(a.candidate.resolve()),
              database_roundtrip=("FAIL" if not passed else "NATIVE_OBJECTS_PASS_GAME_EXPORT_PENDING"
                                  if expanded_world and expanded_world["status"] == "PASS" and expanded_world.get("global_entities")
                                  else "PLAYER_PASS_WORLD_NOT_VALIDATED"),
              loans_validated=report["loans_native_reread_validated"],
              free_agents_native_validated=report["free_agents_native_reread_validated"],
              expired_loans_native_validated=report["expired_loans_native_reread_validated"],
              successor_loans_native_validated=report["successor_loans_native_reread_validated"],
              purchase_loans_native_validated=report["purchase_loans_native_reread_validated"],
              extended_native_validation=report["extended_native_validation"],
              expanded_world_validation=expanded_world["status"] if expanded_world is not None else "NOT_RUN",
              database_roundtrip_note="Bound to latest_validated_candidate and frozen plan " + digest,
              release_ready=False)
status["automated_tests"] = {k: python_tests.get(k) for k in ("status", "tests", "run_at")}
write_json(status_path, status)
print(json.dumps({k: v for k, v in report.items() if k != "candidate_database_files"}))
sys.exit(not passed)
