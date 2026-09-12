"""Validate a Native10 native write/reread against its exact guarded plans."""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import sys
from collections import Counter, defaultdict
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


def group(rows: list[dict], key) -> dict:
    result = defaultdict(list)
    for row in rows:
        result[key(row)].append(row)
    return dict(result)


def semantic_fingerprint(row: dict) -> tuple[tuple[str, str], ...]:
    """Stable exported semantics, excluding read/write serialization ids."""
    return tuple((field, value) for field, value in row.items()
                 if field not in {"fm_id", "serialized_sha256"})


def multiset(rows: list[dict], fields: list[str] | None = None) -> Counter:
    if fields is None:
        return Counter(semantic_fingerprint(row) for row in rows)
    return Counter(tuple(row.get(field, "") for field in fields) for row in rows)


def remove_fingerprint(pool: list[dict], fingerprint: tuple[tuple[str, str], ...]) -> bool:
    """Remove one exact row deterministically while retaining duplicate counts."""
    matches = [index for index, row in enumerate(pool) if semantic_fingerprint(row) == fingerprint]
    if not matches:
        return False
    # FM ids are assigned during read and are not semantic identity.  Sorting is
    # only a deterministic tie-break for otherwise identical exported rows.
    index = min(matches, key=lambda value: (int(pool[value]["fm_id"]), value))
    pool.pop(index)
    return True


def map_planned_group(before_rows: list[dict], after_rows: list[dict], plan_row: dict) -> tuple[dict | None, list[dict]]:
    """Map one FM-id-bound planned row after consuming unchanged siblings."""
    pool = list(after_rows)
    errors = []
    unplanned = [row for row in before_rows if row["fm_id"] != plan_row["fm_id"]]
    for row in sorted(unplanned, key=lambda value: int(value["fm_id"])):
        if not remove_fingerprint(pool, semantic_fingerprint(row)):
            errors.append({"fm_id": row["fm_id"],
                           "error": "unchanged duplicate semantics missing after reread"})
    if len(pool) != 1:
        errors.append({"before_fm_id": plan_row["fm_id"], "remaining_after_rows": len(pool),
                       "error": "planned row does not map unambiguously after unchanged siblings"})
        return None, errors
    return pool[0], errors


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
    p.add_argument("--serialization-allowlist", type=Path,
                   help="Exact raw-audited derived-metadata rewrites")
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    if a.output.exists():
        raise ValueError("Semantic report must be new")

    plan = read_csv(a.squad_plan)
    creation = read_csv(a.creation_plan) if a.creation_plan else []
    before_player_rows = read_csv(a.before / "native_player_semantics.csv")
    after_player_rows = read_csv(a.after / "native_player_semantics.csv")
    before_groups = group(before_player_rows, identity)
    after_groups = group(after_player_rows, identity)
    before_by_fm = {r["fm_id"]: r for r in before_player_rows}
    if len(before_by_fm) != len(before_player_rows):
        raise ValueError("Duplicate before fm_id")
    planned = {}
    for row in plan:
        if row["status"] != "CONFIRMED" or row["fm_id"] not in before_by_fm:
            raise ValueError("Plan is unconfirmed or not bound to before semantics")
        key = identity(before_by_fm[row["fm_id"]])
        if key in planned:
            raise ValueError("Multiple planned rows share a semantic identity: " + repr(key))
        planned[key] = (row, before_by_fm[row["fm_id"]])

    created = {}
    for row in creation:
        dob = dt.datetime.strptime(row["dob"], "%Y-%m-%d").strftime("%d.%m.%Y")
        name = row["pseudonym"] or " ".join(x for x in (row["first_name"], row["last_name"]) if x)
        key = row["fifa_id"], dob, name
        if row["status"] != "CONFIRMED" or key in created or key in before_groups:
            raise ValueError("Creation plan is unconfirmed, duplicate, or already exists")
        created[key] = row

    # Identity is deliberately a multiset: Native08 contains legitimate people
    # with the same FIFA id, birthday and display name.  Bind every changed row
    # to its explicit pre-write FM id, consume unchanged siblings by their full
    # exported semantics, and require exactly one changed after-row to remain.
    before_identity_counts = Counter(identity(row) for row in before_player_rows)
    expected_identity_counts = before_identity_counts.copy()
    expected_identity_counts.update(created.keys())
    actual_identity_counts = Counter(identity(row) for row in after_player_rows)
    inventory_errors = []
    for key in sorted(set(expected_identity_counts) | set(actual_identity_counts)):
        if expected_identity_counts[key] != actual_identity_counts[key]:
            inventory_errors.append({"identity": key, "expected": expected_identity_counts[key],
                                     "actual": actual_identity_counts[key]})

    planned_pairs = {}
    unchanged_errors = []
    mapping_errors = []
    unplanned_serialization_rewrites = []
    for key, before_rows in before_groups.items():
        after_rows = list(after_groups.get(key, []))
        if key in planned:
            plan_row, baseline = planned[key]
            actual, errors = map_planned_group(before_rows, after_rows, plan_row)
            for error in errors:
                error["identity"] = key
                (unchanged_errors if error.get("fm_id") else mapping_errors).append(error)
            if actual is not None:
                planned_pairs[key] = (plan_row, baseline, actual)
        elif key not in created:
            if multiset(before_rows) != multiset(after_rows):
                unchanged_errors.append({"identity": key, "before_count": len(before_rows),
                                         "after_count": len(after_rows),
                                         "error": "unplanned stable semantic multiset changed"})
            else:
                before_sorted = sorted(before_rows, key=lambda row: (semantic_fingerprint(row), int(row["fm_id"])))
                after_sorted = sorted(after_rows, key=lambda row: (semantic_fingerprint(row), int(row["fm_id"])))
                for baseline, actual in zip(before_sorted, after_sorted):
                    if baseline["serialized_sha256"] != actual["serialized_sha256"]:
                        unplanned_serialization_rewrites.append({
                            "identity": key,
                            "before_fm_id": baseline["fm_id"], "after_fm_id": actual["fm_id"],
                            "before_serialized_sha256": baseline["serialized_sha256"],
                            "after_serialized_sha256": actual["serialized_sha256"],
                        })

    checks = {}
    checks["player_identity_inventory"] = {
        "status": "PASS" if not inventory_errors else "FAIL",
        "before": len(before_player_rows), "created": len(created), "after": len(after_player_rows),
        "multiplicity_errors": inventory_errors[:25],
    }
    checks["existing_player_mapping"] = {
        "status": "PASS" if not mapping_errors and not unchanged_errors else "FAIL",
        "planned": len(planned), "mapped": len(planned_pairs),
        "preexisting_duplicate_identity_groups": sum(len(rows) > 1 for rows in before_groups.values()),
        "mapping_errors": mapping_errors[:25], "unchanged_errors": unchanged_errors[:25],
        "method": "explicit before FM id; unchanged full-row multiset; unique residual changed row",
    }
    checks["unplanned_stable_semantics"] = {
        "status": "PASS" if not unchanged_errors else "FAIL",
        "opaque_serialization_rewrites": len(unplanned_serialization_rewrites),
        "rewrites": unplanned_serialization_rewrites[:25],
        "method": "all exported state/history/condition fields compared as multisets; read/write ids excluded",
    }
    rewrite_key_fields = ("before_fm_id", "after_fm_id", "fifa_id", "dob", "name",
                          "before_serialized_sha256", "after_serialized_sha256")
    actual_rewrite_keys = {
        (item["before_fm_id"], item["after_fm_id"], *item["identity"],
         item["before_serialized_sha256"], item["after_serialized_sha256"])
        for item in unplanned_serialization_rewrites
    }
    allowlist_rows = read_csv(a.serialization_allowlist) if a.serialization_allowlist else []
    malformed_allowlist = [row for row in allowlist_rows if
        row.get("status") != "VERIFIED" or
        row.get("classification") != "WRITEABLE_STRING_ID_COLLISION_EMPICS_DISAMBIGUATOR" or
        row.get("raw_field_name") != "mEmpicsId" or row.get("old_value") != "0" or
        not row.get("new_value", "").isdigit() or int(row.get("new_value", "0")) <= 0]
    allowed_rewrite_keys = {
        tuple(row.get(field, "") for field in rewrite_key_fields) for row in allowlist_rows
    }
    rewrite_allowlist_pass = (not malformed_allowlist and
                              actual_rewrite_keys == allowed_rewrite_keys)
    checks["serialization_normalization_allowlist"] = {
        "status": "PASS" if rewrite_allowlist_pass else "FAIL",
        "actual": len(actual_rewrite_keys), "allowed": len(allowed_rewrite_keys),
        "missing_allowlist_rows": [list(key) for key in sorted(actual_rewrite_keys - allowed_rewrite_keys)[:25]],
        "unused_allowlist_rows": [list(key) for key in sorted(allowed_rewrite_keys - actual_rewrite_keys)[:25]],
        "malformed_allowlist_rows": malformed_allowlist[:25],
        "policy": "Every opaque serialization hash rewrite must be exact-bound to a verified raw mEmpicsId normalization row.",
    }
    actual_player_changes = {key for key, (_, baseline, actual) in planned_pairs.items()
                             if baseline["serialized_sha256"] != actual["serialized_sha256"]}
    checks["exact_changed_players"] = {
        "status": "PASS" if actual_player_changes == set(planned) else "FAIL",
        "expected": len(planned), "actual": len(actual_player_changes),
        "missing": [list(k) for k in sorted(set(planned) - actual_player_changes)[:25]],
        "unexpected": [list(k) for k in sorted(actual_player_changes - set(planned))[:25]],
    }
    def native_date(value: str) -> str:
        return dt.datetime.strptime(value, "%Y-%m-%d").strftime("%d.%m.%Y")

    detail_errors = []
    for key, (row, baseline, actual) in planned_pairs.items():
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
        candidates=after_groups.get(key,[])
        actual=candidates[0] if len(candidates)==1 else {}
        expected={"club_id":row["club_id"],
                  "joined":native_date(row["joined"]),"contract_until":native_date(row["contract_until"]),
                  "shirt_number_reserve" if row["team_type"]=="RESERVE" else "shirt_number_first":row["shirt_number"],
                  "in_reserve":"1" if row["team_type"]=="RESERVE" else "0",
                  "nation1":row["nationality1"],"nation2":row["nationality2"],
                  "loan_enabled":"0","retirement_enabled":"0"}
        differences={field:{"expected":value,"actual":actual.get(field)}
                     for field,value in expected.items() if actual.get(field)!=value}
        if differences:
            creation_errors.append({"identity":key,"planned_temporary_fm_id":row["fm_id"],
                                    "reread_fm_id":actual.get("fm_id"),"expected_club":row["club_id"],
                                    "actual_club":actual.get("club_id"),"fields":differences})
    checks["created_players"]={"status":"PASS" if not creation_errors else "FAIL",
                               "expected":len(created),"actual":sum(
                                   max(0,actual_identity_counts[key]-before_identity_counts[key])
                                   for key in actual_identity_counts),
                               "errors":creation_errors[:25]}

    if not all("history_sha256" in row and "conditions_sha256" in row
               for row in before_player_rows + after_player_rows):
        raise ValueError("Native exporter lacks component history/condition hashes")
    history_expected = {key for key, (row, _) in planned.items()
                        if row.get("action", "SQUAD") in {"FREE_AGENT", "RETIRE"}}
    condition_expected = {key for key, (row, _) in planned.items()
                          if row.get("action", "SQUAD") in {
                              "RETIRE", "RESOLVE_EXPIRED_LOAN", "REPLACE_EXPIRED_LOAN",
                              "RESOLVE_ACTIVE_LOAN", "REPLACE_ACTIVE_LOAN", "PURCHASE_AND_LOAN"}
                          or row.get("loan_owner_club_id", "0") != "0"}
    actual_history = {key for key, (_, baseline, actual) in planned_pairs.items()
                      if baseline["history_sha256"] != actual["history_sha256"]}
    actual_conditions = {key for key, (_, baseline, actual) in planned_pairs.items()
                         if baseline["conditions_sha256"] != actual["conditions_sha256"]}
    checks["history_delta"] = {"status": "PASS" if actual_history == history_expected else "FAIL",
                                "expected": len(history_expected), "actual": len(actual_history)}
    checks["starting_condition_delta"] = {
        "status": "PASS" if actual_conditions == condition_expected else "FAIL",
        "expected": len(condition_expected), "actual": len(actual_conditions),
        "preserved_unplanned_and_future_conditions": actual_conditions == condition_expected,
    }
    actual_protected_conditions = {key for key, (_, baseline, actual) in planned_pairs.items()
        if baseline["protected_conditions_sha256"] != actual["protected_conditions_sha256"]}
    actual_future_conditions = {key for key, (_, baseline, actual) in planned_pairs.items()
        if baseline["future_conditions_sha256"] != actual["future_conditions_sha256"]}
    checks["protected_conditions_preserved"] = {
        "status": "PASS" if not actual_protected_conditions else "FAIL",
        "changed": [list(k) for k in sorted(actual_protected_conditions)[:25]],
    }
    checks["future_conditions_preserved"] = {
        "status": "PASS" if not actual_future_conditions else "FAIL",
        "changed": [list(k) for k in sorted(actual_future_conditions)[:25]],
    }

    before_rating_rows = read_csv(a.before / "native_ratings.csv")
    after_rating_rows = read_csv(a.after / "native_ratings.csv")
    before_rating_groups = group(before_rating_rows, identity)
    after_rating_groups = group(after_rating_rows, identity)
    rating_fields = [f for f in before_rating_rows[0]
                     if f not in {"fm_id", "club_id", "serialized_sha256", "protected_sha256",
                                  "in_reserve", "in_youth"}]
    rating_errors = []
    for key, before_rows in before_rating_groups.items():
        after_rows = after_rating_groups.get(key, [])
        if multiset(before_rows, rating_fields) != multiset(after_rows, rating_fields):
            rating_errors.append({"identity": key, "before_count": len(before_rows),
                                  "after_count": len(after_rows),
                                  "error": "rating-value multiset changed"})
            if len(rating_errors) >= 25:
                break
    checks["ratings_preserved"] = {"status": "PASS" if not rating_errors else "FAIL",
                                    "players": len(before_rating_rows), "errors": rating_errors,
                                    "preexisting_duplicate_identity_groups": sum(
                                        len(rows) > 1 for rows in before_rating_groups.values())}
    creation_rating_errors=[]
    for key,row in created.items():
        candidates=after_rating_groups.get(key,[])
        actual=candidates[0] if len(candidates)==1 else {}
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

    before_staff = read_csv(a.before / "native_staff_semantics.csv")
    after_staff = read_csv(a.after / "native_staff_semantics.csv")
    staff_fields = [field for field in before_staff[0] if field != "fm_id"]
    staff_preserved = multiset(before_staff, staff_fields) == multiset(after_staff, staff_fields)
    checks["staff_semantics_preserved"] = {
        "status": "PASS" if staff_preserved else "FAIL",
        "before": len(before_staff), "after": len(after_staff),
        "method": "full exported staff-row multiset excluding read-assigned fm_id",
    }

    before_countries = unique(read_csv(a.before / "native_world_countries.csv"), lambda row: row["country_id"])
    after_countries = unique(read_csv(a.after / "native_world_countries.csv"), lambda row: row["country_id"])
    actual_country_changes = ((set(before_countries) ^ set(after_countries)) |
        {key for key in set(before_countries) & set(after_countries)
         if before_countries[key]["serialized_sha256"] != after_countries[key]["serialized_sha256"]})
    allowed_country_changes = set()
    if a.belgium_plan:
        allowed_country_changes.add("7")
    if a.germany_plan:
        allowed_country_changes.add("21")
    unexpected_country_changes = actual_country_changes - allowed_country_changes
    checks["world_country_semantics"] = {
        "status": "PASS" if not unexpected_country_changes else "FAIL",
        "actual": sorted(actual_country_changes), "allowed_by_structural_plans": sorted(allowed_country_changes),
        "unexpected": sorted(unexpected_country_changes),
    }
    global_preserved = sha256(a.before / "native_global_semantics.csv") == sha256(
        a.after / "native_global_semantics.csv")
    checks["unrelated_global_semantics"] = {
        "status": "PASS" if global_preserved else "FAIL",
        "exact_file": "native_global_semantics.csv",
    }

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
        "serialization_allowlist": str(a.serialization_allowlist.resolve()) if a.serialization_allowlist else None,
        "serialization_allowlist_sha256": sha256(a.serialization_allowlist) if a.serialization_allowlist else None,
        "checks": checks, "release_ready": False,
        "limitations": "Native semantic write/reread only. Exact raw-audited mEmpicsId collision normalization is reported separately; editor export and gameplay remain separate gates.",
    }
    write_json(a.output, report)
    print(json.dumps({"status": report["status"],
                      "failed": [k for k, v in checks.items() if v["status"] != "PASS"]}))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
