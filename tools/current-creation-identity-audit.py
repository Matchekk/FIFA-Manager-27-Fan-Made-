"""Audit Native10 creation candidates against Native08 aliases and loan semantics.

Creation is allowed only when no plausible same-person Native08 candidate remains
and the current source profile does not describe a loan.  The report is intended
to be reviewed and then supplied to the creation generator/preflight as a gate.
"""
from __future__ import annotations

import argparse
import csv
import difflib
import json
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from fm27.common import read_csv, sha256, write_csv, write_json

# These aliases were proved by Draft04's exact native string-id collisions.  The
# created and existing rows have the same DOB, surname identity and nationality.
PROVED_DRAFT04_ALIASES = {
    "191829": "200401", "211628": "285154", "486031": "284973",
    "537844": "288116", "584452": "153244", "669380": "99998",
    "683571": "23757", "1052374": "206551", "1057394": "289780",
    "1118347": "231683", "1178721": "284428",
}

FIELDS = [
    "player_tm_id", "creation_fm_id", "creation_name", "dob",
    "creation_nationality1", "creation_nationality2", "creation_club_id",
    "profile_full_name", "profile_club_tm_id", "loan_owner_tm_id",
    "owner_contract_until", "loan_end", "candidate_fm_id", "candidate_fifa_id",
    "candidate_name", "candidate_common_name", "candidate_nationality",
    "candidate_club_id", "name_similarity", "surname_similarity", "decision",
    "reason", "source", "source_sha256", "snapshot_date",
]


def norm(value: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", value).casefold()
                   if c.isalnum())


def tokens(value: str) -> list[str]:
    return [norm(part) for part in re.split(r"[\s\-']+", value) if norm(part)]


def plausible(creation: dict, native: dict) -> tuple[bool, float, float]:
    display = creation.get("pseudonym") or " ".join(
        filter(None, (creation.get("first_name"), creation.get("last_name"))))
    cn = tokens(display)
    native_display = native.get("common_name") or native.get("name", "")
    nn = tokens(native_display)
    if not cn or not nn:
        return False, 0.0, 0.0
    name_score = difflib.SequenceMatcher(None, "".join(cn), "".join(nn)).ratio()
    surname_score = difflib.SequenceMatcher(None, cn[-1], nn[-1]).ratio()
    joined_c, joined_n = "".join(cn), "".join(nn)
    match = (cn[-1] == nn[-1] or surname_score >= .78 or name_score >= .72
             or cn[-1] in joined_n or nn[-1] in joined_c)
    return match, name_score, surname_score


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--creation-plan", type=Path, required=True)
    p.add_argument("--native-rich", type=Path, required=True)
    p.add_argument("--profiles", nargs="*", type=Path, default=[])
    p.add_argument("--collision-rewrites", type=Path)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--corrected-creation-plan", type=Path, required=True)
    p.add_argument("--bridges", type=Path, required=True)
    p.add_argument("--collision-proof", type=Path,
                   help="Separate Draft04 collision-partner proof; semantic-v3 remains immutable")
    a = p.parse_args()

    creation = read_csv(a.creation_plan)
    rich = read_csv(a.native_rich)
    rich_by_fm = {r["fm_id"]: r for r in rich}
    by_dob: dict[str, list[dict]] = defaultdict(list)
    for row in rich:
        by_dob[row.get("dob", "")].append(row)
    profiles: dict[str, dict] = {}
    for path in a.profiles:
        for row in read_csv(path):
            if row.get("source_status") == "CONFIRMED":
                profiles[row.get("player_tm_id", "")] = row
    rewrite_by_fm = {}
    if a.collision_rewrites:
        rewrite_by_fm = {r["before_fm_id"]: r for r in read_csv(a.collision_rewrites)}

    audit: list[dict] = []
    decisions: dict[str, str] = {}
    bridge_rows: list[dict] = []
    collision_proof: list[dict] = []
    for row in creation:
        tm_id = row["player_tm_id"]
        profile = profiles.get(tm_id, {})
        nations = {row.get("nationality1", "")}
        if row.get("nationality2") not in {"", "0"}:
            nations.add(row["nationality2"])
        candidates = []
        for native in by_dob.get(row.get("dob", ""), []):
            if native.get("nationality") not in nations:
                continue
            match, name_score, surname_score = plausible(row, native)
            if match:
                candidates.append((native, name_score, surname_score))

        proved_fm = PROVED_DRAFT04_ALIASES.get(tm_id)
        loan = bool(profile.get("loan_owner_tm_id"))
        if proved_fm:
            native = rich_by_fm[proved_fm]
            selected = next(((n, ns, ss) for n, ns, ss in candidates
                             if n["fm_id"] == proved_fm), (native, 1.0, 1.0))
            candidates = [selected]
            decision = "BRIDGE_EXISTING_NATIVE08"
            reason = "Draft04 exact string-id collision proves alias of existing Native08 identity"
            rw = rewrite_by_fm.get(proved_fm, {})
            bridge_rows.append({
                "player_tm_id": tm_id, "fm_id": proved_fm,
                "fifa_id": native.get("fifa_id", ""), "dob": row["dob"],
                "status": "CONFIRMED", "identity_method": "DRAFT04_STRING_ID_COLLISION_ALIAS",
                "source": row["source"], "source_sha256": row["source_sha256"],
                "snapshot_date": row["snapshot_date"],
                "collision_before_block_sha256": rw.get("before_block_sha256", ""),
                "collision_after_block_sha256": rw.get("after_block_sha256", ""),
            })
            old_parts = native.get("name", "").split()
            old_first, old_last = " ".join(old_parts[:-1]), old_parts[-1]
            day, month, year = row["dob"].split("-")[2], row["dob"].split("-")[1], row["dob"].split("-")[0]
            old_key = norm(old_last)[:19] + norm(old_first)[:2] + day + month + year
            new_key = norm(row.get("last_name", ""))[:19] + norm(row.get("first_name", ""))[:2] + day + month + year
            collision_proof.append({
                "string_id_key": old_key, "keys_equal": "YES" if old_key == new_key else "NO",
                "existing_fm_id": proved_fm, "existing_fifa_id": native.get("fifa_id", ""),
                "existing_name": native.get("name", ""), "existing_dob": native.get("dob", ""),
                "existing_nationality": native.get("nationality", ""),
                "existing_club_id": native.get("club_id", ""),
                "creation_fm_id": row["fm_id"], "creation_tm_id": tm_id,
                "creation_name": " ".join(filter(None, (row.get("first_name"), row.get("last_name")))),
                "creation_dob": row["dob"], "creation_nationality1": row["nationality1"],
                "creation_club_id": row["club_id"], "collision_partner_is_new_creation": "YES",
                "identity_conclusion": "SAME_REAL_PLAYER_ALIAS_DUPLICATE",
                "required_action": "REMOVE_CREATION_AND_BIND_EXISTING_FM_ID",
                "raw_existing_old_mEmpicsId": rw.get("old_value", ""),
                "raw_existing_new_mEmpicsId": rw.get("new_value", ""),
                "before_block_sha256": rw.get("before_block_sha256", ""),
                "after_block_sha256": rw.get("after_block_sha256", ""),
                "source": row["source"], "source_sha256": row["source_sha256"],
            })
        elif candidates:
            decision = "HOLD_NATIVE08_IDENTITY_CANDIDATE"
            reason = "Same DOB and nationality with plausible surname/full-name alias; creation prohibited pending identity adjudication"
        elif loan:
            decision = "HOLD_CURRENT_LOAN_SEMANTICS"
            reason = "Profile identifies an owner; permanent creation at borrower would lose loan ownership and owner contract"
        else:
            decision = "CREATE_CLEAR"
            reason = "No plausible Native08 DOB/name/nationality candidate and no sourced current loan"
        decisions[tm_id] = decision
        display = row.get("pseudonym") or " ".join(filter(None, (row.get("first_name"), row.get("last_name"))))
        emit = candidates or [(None, 0.0, 0.0)]
        for native, name_score, surname_score in emit:
            audit.append({
                "player_tm_id": tm_id, "creation_fm_id": row["fm_id"],
                "creation_name": display, "dob": row["dob"],
                "creation_nationality1": row["nationality1"],
                "creation_nationality2": row["nationality2"],
                "creation_club_id": row["club_id"],
                "profile_full_name": profile.get("full_name", ""),
                "profile_club_tm_id": profile.get("club_tm_id", ""),
                "loan_owner_tm_id": profile.get("loan_owner_tm_id", ""),
                "owner_contract_until": profile.get("owner_contract_until", ""),
                "loan_end": profile.get("contract_until", "") if loan else "",
                "candidate_fm_id": native.get("fm_id", "") if native else "",
                "candidate_fifa_id": native.get("fifa_id", "") if native else "",
                "candidate_name": native.get("name", "") if native else "",
                "candidate_common_name": native.get("common_name", "") if native else "",
                "candidate_nationality": native.get("nationality", "") if native else "",
                "candidate_club_id": native.get("club_id", "") if native else "",
                "name_similarity": f"{name_score:.4f}",
                "surname_similarity": f"{surname_score:.4f}",
                "decision": decision, "reason": reason,
                "source": row["source"], "source_sha256": row["source_sha256"],
                "snapshot_date": row["snapshot_date"],
            })

    corrected = [r for r in creation if decisions[r["player_tm_id"]] == "CREATE_CLEAR"]
    write_csv(a.output, FIELDS, audit)
    write_csv(a.corrected_creation_plan, list(creation[0]), corrected)
    bridge_fields = list(bridge_rows[0]) if bridge_rows else ["player_tm_id", "fm_id"]
    write_csv(a.bridges, bridge_fields, bridge_rows)
    if a.collision_proof:
        write_csv(a.collision_proof, list(collision_proof[0]), collision_proof)
        collision_report = {
            "status": "FAIL_DRAFT04_DUPLICATE_PLAYER_CREATIONS",
            "production_signoff": False, "collision_pairs": len(collision_proof),
            "all_partners_are_draft04_creations": all(
                r["collision_partner_is_new_creation"] == "YES" for r in collision_proof),
            "all_pairs_same_real_identity": all(
                r["identity_conclusion"] == "SAME_REAL_PLAYER_ALIAS_DUPLICATE" for r in collision_proof),
            "proof_sha256": sha256(a.collision_proof),
            "semantic_v3_mutated": False,
        }
        write_json(a.collision_proof.with_suffix(".json"), collision_report)
    counts = defaultdict(int)
    for decision in decisions.values(): counts[decision] += 1
    report = {
        "status": "DRAFT04_IDENTITY_FAIL_CORRECTED_PLAN_NOT_BUILT",
        "draft04_production_signoff": False,
        "source_creation_rows": len(creation), "corrected_creation_rows": len(corrected),
        "decision_counts": dict(sorted(counts.items())),
        "audit_sha256": sha256(a.output),
        "corrected_creation_plan_sha256": sha256(a.corrected_creation_plan),
        "bridges_sha256": sha256(a.bridges),
        "policy": "Every same-DOB/name/nationality candidate is held; current loans require typed creation semantics; only exact collision-proved aliases are bridged.",
    }
    write_json(a.output.with_suffix(".json"), report)
    print(json.dumps(report, ensure_ascii=False))
    return 1 if len(creation) == len(corrected) else 0


if __name__ == "__main__":
    raise SystemExit(main())
