"""Translate the external football-state handoff into guarded native deltas.

This tool never browses or reinterprets football facts. It validates the supplied
handoff, performs local native identity/reference checks, and reports concrete
technical conflicts instead of inventing missing chronology or IDs.
"""
from __future__ import annotations

import csv
import datetime as dt
import difflib
import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HANDOFF = ROOT / "data/current/external-resolutions"
OUT = ROOT / "data/current/integration-resolved-pass1"
REPORT = ROOT / "reports/current/integration-resolved-pass1"
SNAPSHOT = dt.date(2026, 9, 12)
EMPTY_CONDITION = "9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa"
PLAN_FIELDS = [
    "fm_id", "fifa_id", "dob", "old_club_id", "new_club_id", "joined",
    "contract_until", "shirt_number", "team_type", "status", "source",
    "source_sha256", "snapshot_date", "loan_owner_club_id", "loan_end",
    "action", "previous_loan_owner_club_id", "previous_loan_start",
    "previous_loan_end", "previous_loan_buy_option", "acquisition_seller_club_id",
    "acquisition_event_key", "acquisition_date", "acquisition_source",
    "acquisition_source_sha256", "protected_condition_type",
    "protected_condition_param0", "protected_condition_param1",
    "protected_condition_param2", "protected_condition_param3",
    "protected_condition_param4",
]
CREATE_FIELDS = [
    "fm_id", "player_tm_id", "fifa_id", "first_name", "last_name", "pseudonym",
    "dob", "nationality1", "nationality2", "club_id", "joined", "contract_until",
    "shirt_number", "team_type", "position", "rating_seed", "status", "source",
    "source_sha256", "snapshot_date",
]


def read(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write(path: Path, fields: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def iso(value: str) -> str:
    if not value:
        return ""
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return dt.date.fromisoformat(value).isoformat()
    return dt.datetime.strptime(value, "%d.%m.%Y").date().isoformat()


def normalized(value: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", value or "").casefold() if c.isalnum())


def similarity(left: str, right: str) -> float:
    left, right = normalized(left), normalized(right)
    return difflib.SequenceMatcher(None, left, right).ratio() if left and right else 0.0


def same_or_contained(left: str, right: str) -> bool:
    left, right = normalized(left), normalized(right)
    return bool(left and right and (left == right or (min(len(left), len(right)) >= 4 and (left in right or right in left))))


def base_plan(person: dict, queue: dict, target: str) -> dict:
    reserve = person["in_reserve"] == "1"
    return {
        "fm_id": person["fm_id"], "fifa_id": person["fifa_id"], "dob": iso(person["dob"]),
        "old_club_id": person["club_id"], "new_club_id": target,
        "joined": iso(person["joined"]), "contract_until": iso(person["contract_until"]),
        "shirt_number": person["shirt_number_reserve" if reserve else "shirt_number_first"],
        "team_type": "RESERVE" if reserve else "FIRST", "status": "CONFIRMED",
        "source": queue["source"], "source_sha256": queue["source_sha256"],
        "snapshot_date": queue["snapshot_date"], "loan_owner_club_id": "0", "loan_end": "",
        "action": "MOVE_PRESERVE_METADATA", "previous_loan_owner_club_id": "0",
        "previous_loan_start": "", "previous_loan_end": "", "previous_loan_buy_option": "0",
        "acquisition_seller_club_id": "0", "acquisition_event_key": "",
        "acquisition_date": "", "acquisition_source": "", "acquisition_source_sha256": "",
        "protected_condition_type": "", "protected_condition_param0": "",
        "protected_condition_param1": "", "protected_condition_param2": "",
        "protected_condition_param3": "", "protected_condition_param4": "",
    }


def previous_loan(row: dict, person: dict, *, successor: bool) -> None:
    row.update({
        "action": "REPLACE_EXPIRED_LOAN" if successor else "RESOLVE_EXPIRED_LOAN",
        "previous_loan_owner_club_id": person["loan_owner_club_id"],
        "previous_loan_start": iso(person["loan_start"]),
        "previous_loan_end": iso(person["loan_end"]),
        "previous_loan_buy_option": person["loan_buy_option"],
    })


def blocker(queue: dict, companion: dict, code: str, detail: str) -> dict:
    return {
        "row_id": queue["row_id"], "player": queue["player"], "dob": queue["dob"],
        "league": queue["league"], "club": queue["club"], "fm_id": queue["fm_id"],
        "player_tm_id": queue["player_tm_id"], "technical_action": companion["technical_action"],
        "conflict_code": code, "technical_conflict": detail,
    }


def main() -> None:
    manifest_path = HANDOFF / "FM27_EXTERNAL_FOOTBALL_RESOLUTIONS.manifest.json"
    queue_path = HANDOFF / "FM27_RESOLVED_REVIEW_QUEUE.external-pass1.csv"
    companion_path = HANDOFF / "FM27_EXTERNAL_FOOTBALL_RESOLUTIONS.csv"
    source_path = HANDOFF / "FM27_RESOLVED_REVIEW_QUEUE.source.csv"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    assert sha(source_path) == manifest["source_queue_sha256"]
    assert sha(queue_path) == manifest["resolved_queue_sha256"]
    assert sha(companion_path) == manifest["companion_sha256"]
    queue_rows, companion_rows, source_rows = read(queue_path), read(companion_path), read(source_path)
    assert len(queue_rows) == len(companion_rows) == len(source_rows) == manifest["rows"]
    queue = {r["row_id"]: r for r in queue_rows}
    companion = {r["row_id"]: r for r in companion_rows}
    source = {r["row_id"]: r for r in source_rows}
    assert len(queue) == len(companion) == len(source) == manifest["rows"]
    assert set(queue) == set(companion) == set(source)
    assert Counter(r["decision"] for r in queue_rows) == Counter(manifest["final_decision_counts"])
    original_fields = [f for f in source_rows[0] if f not in {"decision", "resolution_status", "resolution_basis"}]
    for row_id, row in queue.items():
        assert row["decision"] in {"APPLY", "KEEP_EXISTING", "CREATE", "NONBLOCKING", "ESCALATE_TECHNICAL"}
        assert all(row.get(k, "") == source[row_id].get(k, "") for k in original_fields)
        assert companion[row_id]["external_decision"] == row["decision"]

    baseline_path = ROOT / "data/generated/release-candidate/native10-data-draft-20260913-05/write/before/native_player_semantics.csv"
    rich_path = ROOT / "data/intermediate/transfer-increment-20260909-07/players.csv"
    clubs_path = ROOT / "data/intermediate/transfer-increment-20260909-07/clubs.csv"
    baseline = {r["fm_id"]: r for r in read(baseline_path)}
    rich = {r["fm_id"]: r for r in read(rich_path)}
    clubs = read(clubs_path)
    club_ids = {r["club_id"] for r in clubs}
    bayonne = [r for r in clubs if normalized(r["club"]) in {"bayonne", "avironbayonnais", "avironbayonnaisfootballclub"}]
    by_dob: dict[str, list[dict]] = defaultdict(list)
    for player in rich.values():
        by_dob[player["dob"]].append(player)
    override_path = HANDOFF / "LOCAL_TECHNICAL_IDENTITY_BRIDGES.csv"
    override_rows = read(override_path)
    overrides = {r["row_id"]: r for r in override_rows}
    assert len(overrides) == len(override_rows)
    assert len({r["native_fm_id"] for r in override_rows}) == len(override_rows)
    for row_id, override in overrides.items():
        assert row_id in queue and companion[row_id]["technical_action"] == "CREATE_OR_BRIDGE_IDENTITY"
        assert queue[row_id]["player_tm_id"] == override["player_tm_id"]
        native = rich[override["native_fm_id"]]
        assert native["fifa_id"] == override["expected_native_fifa_id"]
        assert native["dob"] == override["expected_native_dob"]
        assert native["name"] == override["expected_native_name"]
        assert native["club_id"] == override["expected_native_club_id"]
        assert (ROOT / override["evidence_path"]).is_file()
    current_squad = read(ROOT / "data/current/integration/candidate-squad-plan.csv")
    current_creation = read(ROOT / "data/current/integration/candidate-player-creation-plan.csv")
    used_plan_ids = {r["fm_id"] for r in current_squad}
    used_creation_tm = {r["player_tm_id"] for r in current_creation}
    used_creation_ids = {r["fm_id"] for r in current_creation}

    audit = {r["player_tm_id"]: r for r in read(ROOT / "reports/current/integration/creation-identity-audit.csv")}
    draft04_create = {r["player_tm_id"]: r for r in read(ROOT / "data/generated/release-candidate/native10-data-draft-20260913-04/inputs/creation.csv")}
    ready: dict[str, dict] = {}
    for path in ROOT.glob("data/current/workers/**/create-ready.csv"):
        for row in read(path):
            ready.setdefault(row["player_tm_id"], row)
    native_fields: dict[str, dict] = {}
    for path in ROOT.glob("data/current/workers/**/create-native-fields.csv"):
        for row in read(path):
            native_fields.setdefault(row["player_tm_id"], row)
    proof = {r["fm_id"]: r for r in read(ROOT / "reports/current/integration/native-protected-condition-proof.csv")}

    delta: list[dict] = []
    creates: list[dict] = []
    bridges: list[dict] = []
    blockers: list[dict] = []
    implementation: list[dict] = []
    next_creation_id = max([int(v) for v in used_creation_ids] + [1000024914]) + 1

    def stage(row: dict, q: dict, c: dict, status: str = "STAGED_TECHNICAL") -> None:
        if row["fm_id"] in used_plan_ids:
            blockers.append(blocker(q, c, "DUPLICATE_NATIVE_PLAN_ID", f"Native fm_id {row['fm_id']} already has a canonical squad action."))
            implementation.append({"row_id": q["row_id"], "decision": q["decision"], "technical_action": c["technical_action"], "implementation_status": "TECHNICAL_BLOCKER", "native_fm_id": row["fm_id"], "detail": "Duplicate canonical plan identity"})
            return
        used_plan_ids.add(row["fm_id"])
        delta.append(row)
        implementation.append({"row_id": q["row_id"], "decision": q["decision"], "technical_action": c["technical_action"], "implementation_status": status, "native_fm_id": row["fm_id"], "detail": row["action"]})

    for row_id in sorted(queue):
        q, c = queue[row_id], companion[row_id]
        decision, action = q["decision"], c["technical_action"]
        if decision in {"KEEP_EXISTING", "NONBLOCKING"}:
            implementation.append({"row_id": row_id, "decision": decision, "technical_action": action, "implementation_status": "RESOLVED_NO_CHANGE", "native_fm_id": q["fm_id"], "detail": q["resolution_status"]})
            continue
        if decision == "APPLY":
            state = json.loads(q["resolved_state_json"])
            stage({field: state.get(field, "") for field in PLAN_FIELDS}, q, c, "STAGED_APPLY")
            continue
        if decision != "ESCALATE_TECHNICAL":
            blockers.append(blocker(q, c, "UNSUPPORTED_DECISION", f"Decision {decision} has no supplied generic handler."))
            continue
        if action != "CREATE_OR_BRIDGE_IDENTITY" and (not q["fm_id"] or q["fm_id"] not in baseline):
            blockers.append(blocker(q, c, "NATIVE_IDENTITY_MISSING", f"Native fm_id {q['fm_id'] or '<blank>'} is absent from the bound Native08 baseline."))
            continue

        if action in {"MOVE_TO_TARGET_PRESERVE_METADATA", "CLEAR_STALE_LOAN_KEEP_TARGET"}:
            person = baseline[q["fm_id"]]
            target = c["target_club_id"]
            if target not in club_ids:
                blockers.append(blocker(q, c, "IMPOSSIBLE_CLUB_REFERENCE", f"Target club_id {target} does not exist locally.")); continue
            plan = base_plan(person, q, target)
            if person["loan_enabled"] == "1":
                if iso(person["loan_end"]) >= q["snapshot_date"]:
                    blockers.append(blocker(q, c, "ACTIVE_LOAN_CONFLICT", "Resolved permanent target conflicts with an active native loan condition.")); continue
                previous_loan(plan, person, successor=False)
            stage(plan, q, c)
            continue

        if action == "MOVE_TO_EXTERNAL_IF_CLUB_EXISTS_ELSE_FREE_AGENT":
            person = baseline[q["fm_id"]]
            if len(bayonne) != 1:
                blockers.append(blocker(q, c, "EXTERNAL_CLUB_MAPPING_AMBIGUOUS", f"Expected one local Bayonne club, found {len(bayonne)}.")); continue
            stage(base_plan(person, q, bayonne[0]["club_id"]), q, c)
            continue

        if action in {"SET_CURRENT_LOAN", "SET_CURRENT_LOAN_PRESERVE_TYPED_CONDITION"}:
            person = baseline[q["fm_id"]]
            target, owner, start, end = c["target_club_id"], c["owner_club_id"], c["loan_start"], c["loan_end"]
            if target not in club_ids or owner not in club_ids or target == owner:
                blockers.append(blocker(q, c, "IMPOSSIBLE_LOAN_CLUB_REFERENCE", f"Loan owner/target invalid: {owner} -> {target}.")); continue
            if not start or not end or dt.date.fromisoformat(start) > SNAPSHOT or dt.date.fromisoformat(end) < SNAPSHOT:
                blockers.append(blocker(q, c, "INVALID_RESOLVED_LOAN_DATES", f"Loan interval {start or '<blank>'}..{end or '<blank>'} does not contain snapshot.")); continue
            if iso(person["contract_until"]) < end:
                blockers.append(blocker(q, c, "OWNER_CONTRACT_BEFORE_LOAN_END", f"Native owner contract ends {iso(person['contract_until'])}, before resolved loan end {end}; no replacement contract date supplied.")); continue
            plan = base_plan(person, q, target)
            plan.update({"joined": start, "loan_owner_club_id": owner, "loan_end": end, "action": "SQUAD"})
            if person["loan_enabled"] == "1":
                if iso(person["loan_end"]) >= q["snapshot_date"]:
                    blockers.append(blocker(q, c, "ACTIVE_LOAN_REPLACEMENT_CONFLICT", "Existing native loan is still active at snapshot and no replacement priority is supplied.")); continue
                previous_loan(plan, person, successor=True)
            elif person["protected_conditions_sha256"] != EMPTY_CONDITION:
                exact = proof.get(person["fm_id"])
                if not exact or exact["native_protected_conditions_sha256"] != person["protected_conditions_sha256"]:
                    blockers.append(blocker(q, c, "PROTECTED_CONDITION_PRECONDITION_MISSING", "Non-loan protected condition lacks an exact raw native precondition.")); continue
                plan.update({"action": "PRESERVE_PROTECTED_SQUAD", "protected_condition_type": exact["condition_type"],
                             **{f"protected_condition_param{i}": exact[f"param{i}"] for i in range(5)}})
            stage(plan, q, c)
            continue

        if action == "APPLY_CONFIRMED_TIMELINE_WITH_GUARD_REPAIR":
            timeline = {r["fm_id"]: r for r in read(ROOT / "data/current/workers/timeline-resolutions.csv")}.get(q["fm_id"])
            if not timeline:
                blockers.append(blocker(q, c, "TIMELINE_RECORD_MISSING", "No local confirmed timeline row exists for this native identity.")); continue
            if timeline["transfer_type"] == "LOAN" and timeline["loan_end"] > timeline["contract_until"]:
                blockers.append(blocker(q, c, "LOAN_END_AFTER_OWNER_CONTRACT", f"Local confirmed timeline says loan end {timeline['loan_end']} after owner contract {timeline['contract_until']}; exact loan end cannot be synthesized safely.")); continue
            blockers.append(blocker(q, c, "TIMELINE_HANDLER_UNSUPPORTED", "Local timeline shape is not supported by an exact guarded handler.")); continue

        if action == "CREATE_OR_BRIDGE_IDENTITY":
            tm_id = q["player_tm_id"]
            if not tm_id:
                blockers.append(blocker(q, c, "SOURCE_IDENTITY_KEY_MISSING", "CREATE_OR_BRIDGE row has no player_tm_id.")); continue
            candidate = None
            override = overrides.get(row_id)
            if override:
                candidate = rich[override["native_fm_id"]]
            known = audit.get(tm_id, {})
            if not candidate and known.get("candidate_fm_id") and known.get("decision") == "HOLD_NATIVE08_IDENTITY_CANDIDATE":
                p = rich.get(known["candidate_fm_id"])
                if p:
                    score = max(similarity(q["player"], p["name"]), similarity(q["player"], p["common_name"]))
                    strong = same_or_contained(q["player"], p["name"]) or same_or_contained(q["player"], p["common_name"]) or score >= .80
                    if strong:
                        candidate = p
            if not candidate:
                scored = []
                for p in by_dob.get(q["dob"], []):
                    score = max(similarity(q["player"], p["name"]), similarity(q["player"], p["common_name"]))
                    contained = same_or_contained(q["player"], p["name"]) or same_or_contained(q["player"], p["common_name"])
                    if score >= .88 or (p["club_id"] == c["target_club_id"] and (score >= .80 or contained)):
                        scored.append((score, p))
                scored.sort(key=lambda item: (-item[0], int(item[1]["fm_id"])))
                if len(scored) == 1 or (scored and (len(scored) == 1 or scored[0][0] - scored[1][0] >= .08)):
                    candidate = scored[0][1]
            if candidate:
                if candidate["fm_id"] in {r["native_fm_id"] for r in bridges}:
                    blockers.append(blocker(q, c, "DUPLICATE_IDENTITY_BRIDGE", f"Native fm_id {candidate['fm_id']} would bind multiple source identities.")); continue
                bridges.append({"row_id": row_id, "player_tm_id": tm_id, "source_player": q["player"], "dob": q["dob"], "native_fm_id": candidate["fm_id"], "native_fifa_id": candidate["fifa_id"], "native_name": candidate["name"], "native_club_id": candidate["club_id"], "target_club_id": c["target_club_id"], "method": override["method"] if override else "LOCAL_UNIQUE_DOB_NAME_ALIAS"})
                person = baseline[candidate["fm_id"]]
                if person["club_id"] == c["target_club_id"]:
                    implementation.append({"row_id": row_id, "decision": q["decision"], "technical_action": action, "implementation_status": "RESOLVED_IDENTITY_BRIDGE_NO_STATE_CHANGE", "native_fm_id": candidate["fm_id"], "detail": candidate["name"]})
                elif person["loan_enabled"] == "0":
                    stage(base_plan(person, q, c["target_club_id"]), q, c, "STAGED_IDENTITY_BRIDGE")
                elif iso(person["loan_end"]) < q["snapshot_date"]:
                    plan = base_plan(person, q, c["target_club_id"]); previous_loan(plan, person, successor=False)
                    stage(plan, q, c, "STAGED_IDENTITY_BRIDGE")
                else:
                    blockers.append(blocker(q, c, "IDENTITY_BRIDGE_ACTIVE_LOAN_CONFLICT", f"Safe local identity {candidate['fm_id']} has an active loan requiring a supplied current-state decision."))
                continue
            creation = None
            possible = known.get("candidate_fm_id", "")
            if not possible and known.get("decision") == "HOLD_CURRENT_LOAN_SEMANTICS" and tm_id in draft04_create:
                creation = dict(draft04_create[tm_id])
            elif not possible and tm_id in ready and tm_id in native_fields and native_fields[tm_id].get("status") == "CONFIRMED":
                source_ready, fields = ready[tm_id], native_fields[tm_id]
                nations = json.loads(fields["native_nationality_ids"])
                parts = source_ready["player"].split()
                first, last, pseudonym = ("", parts[0], "") if len(parts) == 1 else (parts[0], " ".join(parts[1:]), "")
                if len(first) > 15 or len(last) > 19:
                    first, last = (parts[0][:15] if len(parts) > 1 else ""), parts[-1][:19]
                    pseudonym = source_ready["player"] if len(source_ready["player"]) <= 29 else ""
                urls, hashes = json.loads(source_ready["source_urls"]), json.loads(source_ready["source_hashes"])
                creation = {"fm_id": str(next_creation_id), "player_tm_id": tm_id, "fifa_id": "0", "first_name": first,
                            "last_name": last, "pseudonym": pseudonym, "dob": source_ready["dob"],
                            "nationality1": str(nations[0]), "nationality2": str(nations[1] if len(nations) > 1 else 0),
                            "club_id": c["target_club_id"], "joined": source_ready["contract_joined"],
                            "contract_until": source_ready["contract_until"], "shirt_number": source_ready["shirt_number"],
                            "team_type": "FIRST", "position": fields["native_position"], "rating_seed": "45",
                            "status": "CONFIRMED", "source": urls[0], "source_sha256": hashes[0], "snapshot_date": q["snapshot_date"]}
                next_creation_id += 1
            if creation:
                if creation["player_tm_id"] in used_creation_tm or creation["fm_id"] in used_creation_ids:
                    blockers.append(blocker(q, c, "DUPLICATE_CREATION_IDENTITY", "Creation TM/native ID collides with the canonical creation plan.")); continue
                used_creation_tm.add(creation["player_tm_id"]); used_creation_ids.add(creation["fm_id"])
                creates.append({field: creation.get(field, "") for field in CREATE_FIELDS})
                implementation.append({"row_id": row_id, "decision": q["decision"], "technical_action": action, "implementation_status": "STAGED_CREATE", "native_fm_id": creation["fm_id"], "detail": creation["last_name"]})
            else:
                code = "AMBIGUOUS_LOCAL_NATIVE_IDENTITY" if possible else "CREATION_NATIVE_FIELDS_INCOMPLETE"
                detail = f"Local candidate fm_id {possible} is not strong enough for a duplicate-safe bridge." if possible else "No safe local identity and no complete supplied native creation fields."
                blockers.append(blocker(q, c, code, detail))
                implementation.append({"row_id": row_id, "decision": q["decision"], "technical_action": action, "implementation_status": "TECHNICAL_BLOCKER", "native_fm_id": possible, "detail": detail})
            continue

        blockers.append(blocker(q, c, "UNSUPPORTED_TECHNICAL_ACTION", f"No handler for {action!r}."))

    # Every handoff row must have one visible implementation disposition.
    status_ids = {r["row_id"] for r in implementation}
    blocker_ids = {r["row_id"] for r in blockers}
    for row_id in sorted(set(queue) - status_ids):
        q, c = queue[row_id], companion[row_id]
        implementation.append({"row_id": row_id, "decision": q["decision"], "technical_action": c["technical_action"], "implementation_status": "TECHNICAL_BLOCKER", "native_fm_id": q["fm_id"], "detail": next((b["technical_conflict"] for b in blockers if b["row_id"] == row_id), "Unclassified technical conflict")})
    assert len(implementation) == len(queue) and len({r["row_id"] for r in implementation}) == len(queue)

    delta.sort(key=lambda r: int(r["fm_id"]))
    creates.sort(key=lambda r: int(r["fm_id"]))
    bridges.sort(key=lambda r: int(r["player_tm_id"]))
    blockers.sort(key=lambda r: (r["conflict_code"], r["league"], r["player"]))
    implementation.sort(key=lambda r: r["row_id"])
    full_squad = sorted([{field: r.get(field, "") for field in PLAN_FIELDS} for r in current_squad] + delta, key=lambda r: int(r["fm_id"]))
    full_creation = sorted(current_creation + creates, key=lambda r: int(r["fm_id"]))
    assert len({r["fm_id"] for r in full_squad}) == len(full_squad)
    assert len({r["fm_id"] for r in full_creation}) == len(full_creation)
    assert len({r["player_tm_id"] for r in full_creation}) == len(full_creation)
    create_tm = {r["player_tm_id"] for r in creates}
    audit_fields = list(next(iter(audit.values())))
    creation_audit = []
    for creation in full_creation:
        prior = audit[creation["player_tm_id"]]
        row = dict(prior)
        if creation["player_tm_id"] in create_tm:
            assert prior["decision"] == "HOLD_CURRENT_LOAN_SEMANTICS"
            row["decision"] = "CREATE_CLEAR"
            row["reason"] = ("External pass1 confirms current target membership; local whole-corpus "
                             "identity scan found no safe native bridge.")
        else:
            assert prior["decision"] == "CREATE_CLEAR"
        display = creation["pseudonym"] or " ".join(
            value for value in (creation["first_name"], creation["last_name"]) if value)
        row.update({"creation_fm_id": creation["fm_id"], "creation_name": display,
                    "dob": creation["dob"], "creation_nationality1": creation["nationality1"],
                    "creation_nationality2": creation["nationality2"],
                    "creation_club_id": creation["club_id"], "source": creation["source"],
                    "source_sha256": creation["source_sha256"],
                    "snapshot_date": creation["snapshot_date"]})
        creation_audit.append(row)

    write(OUT / "resolved-squad-delta.csv", PLAN_FIELDS, delta)
    write(OUT / "resolved-player-creation-delta.csv", CREATE_FIELDS, creates)
    write(OUT / "candidate-squad-plan.csv", PLAN_FIELDS, full_squad)
    write(OUT / "candidate-player-creation-plan.csv", CREATE_FIELDS, full_creation)
    write(REPORT / "creation-identity-audit.csv", audit_fields, creation_audit)
    write(OUT / "identity-bridges.csv", ["row_id", "player_tm_id", "source_player", "dob", "native_fm_id", "native_fifa_id", "native_name", "native_club_id", "target_club_id", "method"], bridges)
    blocker_fields = ["row_id", "player", "dob", "league", "club", "fm_id", "player_tm_id", "technical_action", "conflict_code", "technical_conflict"]
    write(REPORT / "TECHNICAL_BLOCKERS.csv", blocker_fields, blockers)
    remaining_fields = list(queue_rows[0]) + ["technical_action", "technical_conflict_code", "technical_conflict"]
    remaining = []
    for blocked in blockers:
        row = dict(queue[blocked["row_id"]])
        row["blocking"] = "YES"
        row.update({"technical_action": blocked["technical_action"],
                    "technical_conflict_code": blocked["conflict_code"],
                    "technical_conflict": blocked["technical_conflict"]})
        remaining.append(row)
    write(REPORT / "remaining-review-queue.csv", remaining_fields, remaining)
    write(REPORT / "implementation-status.csv", ["row_id", "decision", "technical_action", "implementation_status", "native_fm_id", "detail"], implementation)
    summary = {
        "status": "TECHNICAL_BLOCKERS_REMAIN" if blockers else "READY_TO_FREEZE",
        "handoff_rows": len(queue), "decision_counts": dict(sorted(Counter(r["decision"] for r in queue_rows).items())),
        "implementation_counts": dict(sorted(Counter(r["implementation_status"] for r in implementation).items())),
        "technical_action_counts": dict(sorted(Counter(r["technical_action"] or "NO_TECHNICAL_ACTION" for r in companion_rows).items())),
        "resolved_squad_delta_rows": len(delta), "resolved_creation_delta_rows": len(creates),
        "identity_bridges": len(bridges), "technical_blockers": len(blockers),
        "technical_blocker_counts": dict(sorted(Counter(r["conflict_code"] for r in blockers).items())),
        "full_squad_plan_rows": len(full_squad), "full_creation_plan_rows": len(full_creation),
        "freeze_ready": not blockers, "football_web_research_performed": False,
        "input_hashes": {str(p.relative_to(ROOT)).replace("\\", "/"): sha(p) for p in (manifest_path, source_path, queue_path, companion_path, override_path, baseline_path)},
        "output_hashes": {str(p.relative_to(ROOT)).replace("\\", "/"): sha(p) for p in (OUT / "resolved-squad-delta.csv", OUT / "resolved-player-creation-delta.csv", OUT / "candidate-squad-plan.csv", OUT / "candidate-player-creation-plan.csv", OUT / "identity-bridges.csv", REPORT / "creation-identity-audit.csv", REPORT / "TECHNICAL_BLOCKERS.csv", REPORT / "remaining-review-queue.csv", REPORT / "implementation-status.csv")},
    }
    (REPORT / "integration.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
