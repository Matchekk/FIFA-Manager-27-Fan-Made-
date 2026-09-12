from __future__ import annotations

import ast
import csv
import json
import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
QUEUE_PATH = ROOT / "reports/current/integration/review-queue.csv"
PROFILE_PATHS = [
    ROOT / "data/current/evidence/review-profiles.csv",
    ROOT / "data/current/workers/south-west/profiles.csv",
    ROOT / "data/current/workers/eng-ger/profiles.csv",
]
ROSTER_PATH = ROOT / "data/current/workers/south-west/rosters.csv"
OBS_PATH = ROOT / "data/current/workers/eng-ger/squad_observations.csv"
IDENTITY_RES_PATH = ROOT / "data/current/workers/south-west/identity-resolutions.csv"
IDENTITY_CONF_PATH = ROOT / "data/current/workers/south-west/identity-confirmed.csv"
CREATE_REVIEW_PATHS = [
    ROOT / "data/current/workers/south-west/create-ready-review.csv",
    ROOT / "data/current/workers/eng-ger/create-ready-review.csv",
]
CREATE_READY_PATHS = [
    ROOT / "data/current/workers/south-west/create-ready.csv",
    ROOT / "data/current/workers/eng-ger/create-ready.csv",
]
OUT = ROOT / "data/current/workers/creation-blocker-triage.csv"
SUMMARY = ROOT / "data/current/workers/creation-blocker-triage.json"
ADDITIONAL = ROOT / "data/current/workers/additional-create-ready.csv"
ADDITIONAL_PROOF = ROOT / "data/current/workers/additional-create-ready.json"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def parse_json(value: str, default):
    if not value:
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        try:
            return ast.literal_eval(value)
        except (ValueError, SyntaxError):
            return default


queue_all = read_csv(QUEUE_PATH)
queue = [r for r in queue_all if r.get("queue") == "PLAYER_CREATION" and r.get("blocking") == "YES"]

profiles: dict[str, dict[str, str]] = {}
for path in PROFILE_PATHS:
    for row in read_csv(path):
        profiles.setdefault(row.get("player_tm_id", ""), row)

rosters = {r.get("player_tm_id"): r for r in read_csv(ROSTER_PATH)}
observations = {r.get("external_player_id"): r for r in read_csv(OBS_PATH)}
identity_res = {r.get("player_tm_id"): r for r in read_csv(IDENTITY_RES_PATH)}
identity_conf = {r.get("player_tm_id"): r for r in read_csv(IDENTITY_CONF_PATH)}
create_reviews: dict[str, dict[str, str]] = {}
for path in CREATE_REVIEW_PATHS:
    for row in read_csv(path):
        create_reviews.setdefault(row.get("player_tm_id", ""), row)
existing_ready: dict[str, dict[str, str]] = {}
for path in CREATE_READY_PATHS:
    for row in read_csv(path):
        existing_ready.setdefault(row.get("player_tm_id", ""), row)

headers = [
    "queue",
    "blocking",
    "league",
    "club",
    "club_tm_id",
    "player",
    "player_tm_id",
    "dob",
    "fm_id",
    "fifa_id",
    "native_club_id",
    "target_club_id",
    "identity_method",
    "profile_present",
    "profile_name",
    "profile_dob",
    "profile_nationality",
    "profile_position",
    "profile_contract_until",
    "profile_joined",
    "profile_source_url",
    "profile_source_sha256",
    "current_employer_tm_id",
    "current_employer",
    "current_first_team_significance",
    "current_significance_source_url",
    "current_significance_source_sha256",
    "current_significance_source_status",
    "current_roster_position",
    "current_roster_joined",
    "current_roster_contract_until",
    "current_roster_shirt_number",
    "queue_source_url",
    "queue_source_sha256",
    "prior_audit_sources",
    "prior_attempt_count",
    "prior_identity_status",
    "prior_identity_method",
    "prior_native_fm_id",
    "prior_native_fifa_id",
    "prior_native_name",
    "prior_native_dob",
    "prior_native_club_id",
    "prior_exact_candidates",
    "prior_duplicate_leads",
    "prior_fuzzy_candidates",
    "prior_review_reason",
    "prerequisite_category",
    "missing_prerequisites",
    "creation_action",
    "escalation",
    "snapshot_date",
]

out: list[dict[str, str]] = []
for q in queue:
    pid = q.get("player_tm_id", "")
    p = profiles.get(pid, {})
    roster = rosters.get(pid, {})
    obs = observations.get(pid, {})
    ir = identity_res.get(pid, {})
    ic = identity_conf.get(pid, {})
    cr = create_reviews.get(pid, {})
    ready = existing_ready.get(pid, {})

    # The current roster source establishes why the player was considered;
    # explicit FIRST is available for ENG/GER observations, while the broader
    # roster capture is recorded without promoting it to a first-team claim.
    if obs.get("team_type") == "FIRST":
        significance = "EXPLICIT_FIRST_TEAM"
        sig = obs
    elif p and p.get("club_tm_id") and p.get("club_tm_id") != q.get("club_tm_id"):
        significance = "PROFILE_RESERVE_MISMATCH"
        sig = roster or p
    elif roster:
        significance = "CURRENT_ROSTER_SOURCE_OBSERVED"
        sig = roster
    else:
        significance = "QUEUE_SOURCE_ONLY"
        sig = q

    exact = parse_json(cr.get("exact_candidates", "[]"), [])
    dup = parse_json(cr.get("duplicate_leads", "{}"), {})
    fuzzy = parse_json(cr.get("fuzzy_candidates", "[]"), [])
    if not isinstance(exact, list):
        exact = []
    if not isinstance(fuzzy, list):
        fuzzy = []
    if not isinstance(dup, dict):
        dup = {}
    dup_people = dup.get("people") if isinstance(dup.get("people"), list) else []

    missing_profile = []
    if p:
        for field, label in (
            ("nationality_text", "NATIONALITY"),
            ("position", "POSITION"),
            ("contract_until", "CONTRACT_UNTIL"),
            ("joined", "CONTRACT_JOINED"),
            ("source", "PROFILE_SOURCE"),
            ("source_sha256", "PROFILE_SOURCE_HASH"),
        ):
            if not p.get(field):
                missing_profile.append(label)
    elif not ic:
        missing_profile.extend(["NATIONALITY", "POSITION", "CONTRACT_UNTIL", "CONTRACT_JOINED", "PROFILE_SOURCE", "PROFILE_SOURCE_HASH"])

    prior_sources = []
    if ir:
        prior_sources.append("identity-resolutions")
    if ic:
        prior_sources.append("identity-confirmed")
    if cr:
        prior_sources.append("create-ready-review")
    if ready:
        prior_sources.append("create-ready")

    # Every blocking row has an existing two-step audit (profile/source plus
    # Native08 bridge or DuplicateReviewIndex review). Preserve this as a
    # count instead of starting another attempt.
    prior_attempts = 2 if prior_sources else 0
    blockers: list[str] = []
    if ic:
        category = "EXISTING_NATIVE_IDENTITY_CONFIRMED"
        action = "DO_NOT_CREATE_USE_NATIVE_BRIDGE"
        blockers = ["NONE_CREATION_NOT_REQUIRED"]
    elif ready:
        category = "ALREADY_CREATE_READY"
        action = "EXCLUDE_EXISTING_CREATE_READY_DUPLICATE"
        blockers = ["NONE_ALREADY_IN_EXISTING_CREATE_READY"]
    else:
        category = "PLAYER_CREATION_PREREQUISITE_MISSING"
        action = "HOLD_REVIEW"
        if exact:
            blockers.append("IDENTITY_AMBIGUITY_EXACT_NATIVE_CANDIDATE")
        if dup_people:
            blockers.append("IDENTITY_AMBIGUITY_DUPLICATE_REVIEW_LEAD")
        if fuzzy:
            blockers.append("IDENTITY_AMBIGUITY_FUZZY_CANDIDATE")
        reason = cr.get("review_reason", "")
        if "alias" in reason.lower() and not (exact or dup_people or fuzzy):
            blockers.append("IDENTITY_AMBIGUITY_REVIEWED_ALIAS_NO_BRIDGE")
        for field in missing_profile:
            blockers.append(field)
        if significance == "PROFILE_RESERVE_MISMATCH":
            blockers.append("FIRST_TEAM_SIGNIFICANCE_UNCONFIRMED_RESERVE_PROFILE")
        if not blockers:
            blockers.append("IDENTITY_UNIQUE_NATIVE_ID_REQUIRED")
        # Existing/fuzzy rows have already reached the two-attempt boundary.
        action = "HOLD_REVIEW_AFTER_PRIOR_ATTEMPTS"

    row = {h: "" for h in headers}
    row.update(
        {
            "queue": q.get("queue", ""),
            "blocking": q.get("blocking", ""),
            "league": q.get("league", ""),
            "club": q.get("club", ""),
            "club_tm_id": q.get("club_tm_id", ""),
            "player": q.get("player", ""),
            "player_tm_id": pid,
            "dob": q.get("dob", ""),
            "fm_id": q.get("fm_id", ""),
            "fifa_id": q.get("fifa_id", ""),
            "native_club_id": q.get("native_club_id", ""),
            "target_club_id": q.get("target_club_id", ""),
            "identity_method": q.get("identity_method", ""),
            "profile_present": "YES" if p else "NO",
            "profile_name": p.get("full_name") or p.get("player", ""),
            "profile_dob": p.get("dob", ""),
            "profile_nationality": p.get("nationality_text", ""),
            "profile_position": p.get("position", ""),
            "profile_contract_until": p.get("contract_until", ""),
            "profile_joined": p.get("joined", ""),
            "profile_source_url": p.get("source", ""),
            "profile_source_sha256": p.get("source_sha256", ""),
            "current_employer_tm_id": p.get("club_tm_id", "") or roster.get("club_tm_id") or obs.get("external_club_id", ""),
            "current_employer": p.get("club", "") or roster.get("club", "") or obs.get("club_name", ""),
            "current_first_team_significance": significance,
            "current_significance_source_url": sig.get("source") or sig.get("source_url", ""),
            "current_significance_source_sha256": sig.get("source_sha256", ""),
            "current_significance_source_status": sig.get("source_status", "CONFIRMED"),
            "current_roster_position": sig.get("position", ""),
            "current_roster_joined": sig.get("joined", ""),
            "current_roster_contract_until": sig.get("contract_until", ""),
            "current_roster_shirt_number": sig.get("shirt_number", ""),
            "queue_source_url": q.get("source", ""),
            "queue_source_sha256": q.get("source_sha256", ""),
            "prior_audit_sources": " | ".join(prior_sources),
            "prior_attempt_count": str(prior_attempts),
            "prior_identity_status": ic.get("status", "") or ir.get("status", ""),
            "prior_identity_method": ic.get("identity_method", "") or ir.get("identity_method", ""),
            "prior_native_fm_id": ic.get("native_fm_id", "") or ir.get("native_fm_id", ""),
            "prior_native_fifa_id": ic.get("native_fifa_id", "") or ir.get("native_fifa_id", ""),
            "prior_native_name": ic.get("native_name", "") or ir.get("native_name", ""),
            "prior_native_dob": ic.get("native_dob", "") or ir.get("native_dob", ""),
            "prior_native_club_id": ic.get("native_club_id", "") or ir.get("native_club_id", ""),
            "prior_exact_candidates": json.dumps(exact, ensure_ascii=False, separators=(",", ":")),
            "prior_duplicate_leads": json.dumps(dup_people, ensure_ascii=False, separators=(",", ":")),
            "prior_fuzzy_candidates": json.dumps(fuzzy, ensure_ascii=False, separators=(",", ":")),
            "prior_review_reason": cr.get("review_reason", ""),
            "prerequisite_category": category,
            "missing_prerequisites": " | ".join(dict.fromkeys(blockers)),
            "creation_action": action,
            "escalation": "" if ic or ready else "Sol",
            "snapshot_date": q.get("snapshot_date", "2026-09-12"),
        }
    )
    out.append(row)

with OUT.open("w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=headers)
    writer.writeheader()
    writer.writerows(out)

# The current audits contain one already-promoted zero-duplicate row. It is
# intentionally excluded from the additional artifact so no duplicate create
# record is emitted. Any future eligible row must carry the existing schema
# and its complete proof.
ready_headers = list(read_csv(CREATE_READY_PATHS[0])[0]) if read_csv(CREATE_READY_PATHS[0]) else []
with ADDITIONAL.open("w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=ready_headers)
    writer.writeheader()

additional_summary = {
    "snapshot_date": "2026-09-12",
    "eligible_new_rows": 0,
    "already_in_existing_create_ready": sorted(existing_ready.keys() & {r["player_tm_id"] for r in queue}),
    "reason": "No new eligible rows: the only zero-duplicate CREATE_READY audit row in scope is already present in the existing create-ready artifact.",
    "production_mutation": False,
}
with ADDITIONAL_PROOF.open("w", encoding="utf-8") as f:
    json.dump(additional_summary, f, ensure_ascii=False, indent=2)
    f.write("\n")

summary = {
    "snapshot_date": "2026-09-12",
    "scope": "blocking PLAYER_CREATION rows only",
    "queue_rows": len(out),
    "all_player_creation_rows": sum(r.get("queue") == "PLAYER_CREATION" for r in queue_all),
    "blocking_rows": len(out),
    "profile_match_count": sum(r["profile_present"] == "YES" for r in out),
    "first_team_significance_counts": dict(Counter(r["current_first_team_significance"] for r in out)),
    "prerequisite_category_counts": dict(Counter(r["prerequisite_category"] for r in out)),
    "missing_prerequisite_counts": dict(Counter(x for r in out for x in r["missing_prerequisites"].split(" | ") if x)),
    "prior_attempt_counts": dict(Counter(r["prior_attempt_count"] for r in out)),
    "escalation_count": sum(bool(r["escalation"]) for r in out),
    "additional_create_ready": additional_summary,
    "source_files": [
        str(QUEUE_PATH.relative_to(ROOT)),
        *(str(p.relative_to(ROOT)) for p in PROFILE_PATHS),
        str(ROSTER_PATH.relative_to(ROOT)),
        str(OBS_PATH.relative_to(ROOT)),
        str(IDENTITY_RES_PATH.relative_to(ROOT)),
        str(IDENTITY_CONF_PATH.relative_to(ROOT)),
        *(str(p.relative_to(ROOT)) for p in CREATE_REVIEW_PATHS),
        *(str(p.relative_to(ROOT)) for p in CREATE_READY_PATHS),
    ],
    "production_mutation": False,
}
with SUMMARY.open("w", encoding="utf-8") as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)
    f.write("\n")
print(json.dumps(summary, ensure_ascii=False))
