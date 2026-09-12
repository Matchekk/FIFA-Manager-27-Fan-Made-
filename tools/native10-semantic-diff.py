"""Validate a Native10 native write/reread against its exact guarded plans."""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from fm27.common import read_csv, sha256, write_json


def identity(row: dict) -> tuple[str, str, str]:
    return row["fifa_id"], row["dob"], row["name"]


def unique(rows: list[dict], key) -> dict:
    result = {}
    for row in rows:
        ident = key(row)
        if ident in result:
            raise ValueError("Ambiguous semantic identity: " + repr(ident))
        result[ident] = row
    return result


def changed(before: dict, after: dict, field: str) -> set:
    if before.keys() != after.keys():
        raise ValueError("Before/after inventories differ")
    return {key for key in before if before[key].get(field) != after[key].get(field)}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--before", type=Path, required=True,
                   help="Fresh native inspection of the accepted Native08 base")
    p.add_argument("--after", type=Path, required=True,
                   help="Independent reread of the Native10 candidate")
    p.add_argument("--squad-plan", type=Path, required=True)
    p.add_argument("--membership-plan", type=Path)
    p.add_argument("--belgium-plan", type=Path)
    p.add_argument("--germany-plan", type=Path)
    p.add_argument("--creation-plan", type=Path)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    if a.output.exists():
        raise ValueError("Semantic report must be new")

    plan = read_csv(a.squad_plan)
    creation = read_csv(a.creation_plan) if a.creation_plan else []
    before_players = unique(read_csv(a.before / "native_player_semantics.csv"), identity)
    after_players = unique(read_csv(a.after / "native_player_semantics.csv"), identity)
    before_by_fm = {r["fm_id"]: identity(r) for r in before_players.values()}
    if len(before_by_fm) != len(before_players):
        raise ValueError("Duplicate before fm_id")
    planned = {}
    for row in plan:
        if row["status"] != "CONFIRMED" or row["fm_id"] not in before_by_fm:
            raise ValueError("Plan is unconfirmed or not bound to before semantics")
        key = before_by_fm[row["fm_id"]]
        if key in planned:
            raise ValueError("Duplicate planned person")
        planned[key] = row

    created = {}
    for row in creation:
        dob = dt.datetime.strptime(row["dob"], "%Y-%m-%d").strftime("%d.%m.%Y")
        name = row["pseudonym"] or " ".join(x for x in (row["first_name"], row["last_name"]) if x)
        key = row["fifa_id"], dob, name
        if row["status"] != "CONFIRMED" or key in created or key in before_players:
            raise ValueError("Creation plan is unconfirmed, duplicate, or already exists")
        created[key] = row
    if set(after_players) - set(before_players) != set(created) or set(before_players) - set(after_players):
        raise ValueError("Before/after player inventory differs outside the creation plan")
    after_existing = {k:v for k,v in after_players.items() if k in before_players}
    checks = {}
    actual_player_changes = changed(before_players, after_existing, "serialized_sha256")
    checks["exact_changed_players"] = {
        "status": "PASS" if actual_player_changes == set(planned) else "FAIL",
        "expected": len(planned), "actual": len(actual_player_changes),
        "missing": [list(k) for k in sorted(set(planned) - actual_player_changes)[:25]],
        "unexpected": [list(k) for k in sorted(actual_player_changes - set(planned))[:25]],
    }
    def native_date(value: str) -> str:
        return dt.datetime.strptime(value, "%Y-%m-%d").strftime("%d.%m.%Y")

    detail_errors = []
    for key, row in planned.items():
        actual = after_players[key]
        baseline = before_players[key]
        reserve = row["team_type"] == "RESERVE"
        expected = {
            "club_id": row["new_club_id"], "joined": native_date(row["joined"]),
            "contract_until": native_date(row["contract_until"]),
            "in_reserve": "1" if reserve else "0",
            "shirt_number_reserve" if reserve else "shirt_number_first": row["shirt_number"],
            "nation1": baseline["nation1"], "nation2": baseline["nation2"],
            "main_position_id": baseline["main_position_id"],
        }
        if row.get("action") in {"FREE_AGENT", "RETIRE"}:
            expected.update({"shirt_number_first": "0", "shirt_number_reserve": "0"})
        else:
            other_shirt = "shirt_number_first" if reserve else "shirt_number_reserve"
            expected[other_shirt] = baseline[other_shirt]
        owner = row.get("loan_owner_club_id", "0")
        expected.update({
            "retirement_enabled": "1" if row.get("action") == "RETIRE" else "0",
            "loan_enabled": "1" if owner != "0" else "0",
            "loan_owner_club_id": owner,
            "loan_start": native_date(row["joined"]) if owner != "0" else "",
            "loan_end": native_date(row["loan_end"]) if owner != "0" else "",
            "loan_buy_option": "0",
        })
        differences = {field: {"expected": value, "actual": actual.get(field)}
                       for field, value in expected.items() if actual.get(field) != value}
        if differences:
            detail_errors.append({"identity": key, "fields": differences})
    checks["planned_player_results"] = {"status": "PASS" if not detail_errors else "FAIL",
                                         "players": len(planned), "errors": detail_errors[:25]}
    creation_errors=[]
    for key,row in created.items():
        actual=after_players.get(key,{})
        expected={"fm_id":row["fm_id"],"club_id":row["club_id"],
                  "joined":native_date(row["joined"]),"contract_until":native_date(row["contract_until"]),
                  "shirt_number_reserve" if row["team_type"]=="RESERVE" else "shirt_number_first":row["shirt_number"],
                  "in_reserve":"1" if row["team_type"]=="RESERVE" else "0",
                  "nation1":row["nationality1"],"nation2":row["nationality2"],
                  "loan_enabled":"0","retirement_enabled":"0"}
        differences={field:{"expected":value,"actual":actual.get(field)}
                     for field,value in expected.items() if actual.get(field)!=value}
        if differences:
            creation_errors.append({"identity":key,"expected_fm_id":row["fm_id"],
                                    "actual_fm_id":actual.get("fm_id"),"expected_club":row["club_id"],
                                    "actual_club":actual.get("club_id"),"fields":differences})
    checks["created_players"]={"status":"PASS" if not creation_errors else "FAIL",
                               "expected":len(created),"actual":len(set(after_players)-set(before_players)),
                               "errors":creation_errors[:25]}

    if not all("history_sha256" in row and "conditions_sha256" in row
               for row in list(before_players.values()) + list(after_players.values())):
        raise ValueError("Native exporter lacks component history/condition hashes")
    history_expected = {key for key, row in planned.items()
                        if row.get("action", "SQUAD") in {"FREE_AGENT", "RETIRE"}}
    condition_expected = {key for key, row in planned.items()
                          if row.get("action", "SQUAD") in {
                              "RETIRE", "RESOLVE_EXPIRED_LOAN", "REPLACE_EXPIRED_LOAN",
                              "RESOLVE_ACTIVE_LOAN", "REPLACE_ACTIVE_LOAN", "PURCHASE_AND_LOAN"}
                          or row.get("loan_owner_club_id", "0") != "0"}
    actual_history = changed(before_players, after_existing, "history_sha256")
    actual_conditions = changed(before_players, after_existing, "conditions_sha256")
    checks["history_delta"] = {"status": "PASS" if actual_history == history_expected else "FAIL",
                                "expected": len(history_expected), "actual": len(actual_history)}
    checks["starting_condition_delta"] = {
        "status": "PASS" if actual_conditions == condition_expected else "FAIL",
        "expected": len(condition_expected), "actual": len(actual_conditions),
        "preserved_unplanned_and_future_conditions": actual_conditions == condition_expected,
    }
    actual_protected_conditions = changed(before_players, after_existing, "protected_conditions_sha256")
    actual_future_conditions = changed(before_players, after_existing, "future_conditions_sha256")
    checks["protected_conditions_preserved"] = {
        "status": "PASS" if not actual_protected_conditions else "FAIL",
        "changed": [list(k) for k in sorted(actual_protected_conditions)[:25]],
    }
    checks["future_conditions_preserved"] = {
        "status": "PASS" if not actual_future_conditions else "FAIL",
        "changed": [list(k) for k in sorted(actual_future_conditions)[:25]],
    }

    before_ratings = unique(read_csv(a.before / "native_ratings.csv"), identity)
    after_ratings = unique(read_csv(a.after / "native_ratings.csv"), identity)
    rating_fields = [f for f in next(iter(before_ratings.values()))
                     if f not in {"fm_id", "club_id", "serialized_sha256", "protected_sha256",
                                  "in_reserve", "in_youth"}]
    rating_errors = []
    after_existing_ratings={k:v for k,v in after_ratings.items() if k in before_ratings}
    if before_ratings.keys() != after_existing_ratings.keys():
        rating_errors.append("inventory")
    else:
        for key in before_ratings:
            differences = [f for f in rating_fields if before_ratings[key][f] != after_existing_ratings[key][f]]
            if differences:
                rating_errors.append({"identity": key, "fields": differences})
                if len(rating_errors) >= 25:
                    break
    checks["ratings_preserved"] = {"status": "PASS" if not rating_errors else "FAIL",
                                    "players": len(before_ratings), "errors": rating_errors}
    creation_rating_errors=[]
    for key,row in created.items():
        actual=after_ratings.get(key,{})
        seed=row["rating_seed"]
        if actual.get("main_position") != row["position"]:
            creation_rating_errors.append({"identity":key,"fields":{
                "main_position":{"expected":row["position"],"actual":actual.get("main_position")}}})
            continue
        differences=[f for f in rating_fields if f in actual and f not in {
            "fifa_id","dob","name","main_position","style","experience","level13","best_style","level13_best_style",
            "talent"} and actual[f]!=seed]
        if differences: creation_rating_errors.append({"identity":key,"fields":differences})
    checks["created_player_rating_seed"]={"status":"PASS" if not creation_rating_errors else "FAIL",
        "players":len(created),"seed_policy":"explicit bounded provisional seed","errors":creation_rating_errors[:25]}

    membership = read_csv(a.membership_plan) if a.membership_plan else []
    expected_competitions = {r["competition_id"] for r in membership}
    before_members = read_csv(a.before / "competition_members.csv")
    before_members_by_comp = {}
    for row in before_members:
        before_members_by_comp.setdefault(row["competition_id"], []).append(
            (int(row["slot"]), row["club_id"], row["team_type"]))
    def canonical_team(value: str) -> str:
        return "RESERVE" if value.strip().upper().startswith("RESERVE") else "FIRST"

    before_members_by_comp = {comp: [(club, canonical_team(team)) for _, club, team in sorted(rows)]
                              for comp, rows in before_members_by_comp.items()}

    def add_planned_membership_changes(rows: list[dict]) -> None:
        proposed = {}
        for row in rows:
            if row.get("competition_id") != "0":
                proposed.setdefault(row["competition_id"], []).append(
                    (row["club_id"], canonical_team(row["team_type"])))
        for comp, members in proposed.items():
            if before_members_by_comp.get(comp, []) != members:
                expected_competitions.add(comp)

    if a.belgium_plan:
        belgium_rows=read_csv(a.belgium_plan)
        allowed={"0","117506048","117506049","117506050","117506051","117506052","117506053","117506054"}
        if not belgium_rows or any(r.get("competition_id","") not in allowed for r in belgium_rows):
            raise ValueError("Belgium plan contains an unsupported membership/boundary competition")
        # competition_id=0 rows authorize a source-proven boundary assignment;
        # they are not real competitions and therefore never enter this set.
        expected_competitions.update({"117506048","117506049","117964800","117964801",
                                      "117964802","119013376","119013377","119013378"})
        add_planned_membership_changes(belgium_rows)
    if a.germany_plan:
        germany_rows=read_csv(a.germany_plan)
        if not germany_rows or any(not r.get("competition_id", "").isdigit() for r in germany_rows):
            raise ValueError("German plan contains a malformed membership/boundary competition")
        add_planned_membership_changes(germany_rows)
        expected_competitions.update({"352387079","352845829","353894403","353894404"})
    before_comps = unique(read_csv(a.before / "native_competition_semantics.csv"), lambda r: r["competition_id"])
    after_comps = unique(read_csv(a.after / "native_competition_semantics.csv"), lambda r: r["competition_id"])
    actual_competitions = ((set(before_comps)^set(after_comps)) |
        {k for k in set(before_comps)&set(after_comps)
         if before_comps[k].get("serialized_sha256")!=after_comps[k].get("serialized_sha256")})
    checks["competition_delta"] = {
        "status": "PASS" if actual_competitions == expected_competitions else "FAIL",
        "expected": sorted(expected_competitions), "actual": sorted(actual_competitions),
    }

    exact_files = ["native_staff_semantics.csv", "native_global_semantics.csv",
                   "native_world_countries.csv"]
    exact_errors = []
    for name in exact_files:
        if sha256(a.before / name) != sha256(a.after / name):
            exact_errors.append(name)
    checks["unrelated_world_semantics"] = {"status": "PASS" if not exact_errors else "FAIL",
                                            "exact_files": exact_files, "changed": exact_errors}

    passed = all(c["status"] == "PASS" for c in checks.values())
    report = {
        "status": "PASS_NATIVE10_EXACT_SEMANTIC_DELTA" if passed else "FAIL",
        "before": str(a.before.resolve()), "after": str(a.after.resolve()),
        "squad_plan": str(a.squad_plan.resolve()), "squad_plan_sha256": sha256(a.squad_plan),
        "membership_plan": str(a.membership_plan.resolve()) if a.membership_plan else None,
        "membership_plan_sha256": sha256(a.membership_plan) if a.membership_plan else None,
        "belgium_plan": str(a.belgium_plan.resolve()) if a.belgium_plan else None,
        "belgium_plan_sha256": sha256(a.belgium_plan) if a.belgium_plan else None,
        "creation_plan": str(a.creation_plan.resolve()) if a.creation_plan else None,
        "creation_plan_sha256": sha256(a.creation_plan) if a.creation_plan else None,
        "germany_plan": str(a.germany_plan.resolve()) if a.germany_plan else None,
        "germany_plan_sha256": sha256(a.germany_plan) if a.germany_plan else None,
        "checks": checks, "release_ready": False,
        "limitations": "Native semantic write/reread only. Club serialization and person-link keys legitimately follow planned player membership; editor export and gameplay remain separate gates.",
    }
    write_json(a.output, report)
    print(json.dumps({"status": report["status"],
                      "failed": [k for k, v in checks.items() if v["status"] != "PASS"]}))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
