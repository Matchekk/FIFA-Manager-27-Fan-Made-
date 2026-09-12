"""Build a deterministic Native10 review package from current squad captures.

The tool is deliberately conservative.  It emits a native staging row only when
the current observation resolves to one Native08 person, the destination is a
known native club, chronology is complete, and any club change has a matching
confirmed transfer event.  Everything else is retained in an explicit queue.
It never writes a game database.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import gc
import hashlib
import json
import re
import sys
import unicodedata
from functools import lru_cache
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from fm27.common import read_csv, sha256, write_csv, write_json
from fm27.matching import IdentityIndex

LEAGUE_SIZES = {
    "ENG1": 20, "ITA1": 20, "ESP1": 20, "GER1": 18,
    "FRA1": 18, "POR1": 18, "NED1": 18, "BEL1": 18,
    "TUR1": 18, "CZE1": 16, "GER2": 18, "GER3": 20,
}
PLAN_FIELDS = [
    "fm_id", "fifa_id", "dob", "old_club_id", "new_club_id", "joined",
    "contract_until", "shirt_number", "team_type", "status", "source",
    "source_sha256", "snapshot_date", "loan_owner_club_id", "loan_end",
    "action", "previous_loan_owner_club_id", "previous_loan_start",
    "previous_loan_end", "previous_loan_buy_option", "acquisition_seller_club_id",
    "acquisition_event_key", "acquisition_date", "acquisition_source",
    "acquisition_source_sha256",
]
REVIEW_FIELDS = [
    "queue", "blocking", "reason", "league", "club", "club_tm_id", "player",
    "player_tm_id", "dob", "fm_id", "fifa_id", "native_club_id",
    "target_club_id", "identity_method", "source", "source_sha256",
    "snapshot_date",
]
HEX64 = re.compile(r"[0-9a-f]{64}")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--rosters", nargs="+", type=Path, required=True)
    p.add_argument("--events", nargs="*", type=Path, default=[])
    p.add_argument("--players", type=Path,
                   default=ROOT / "data/intermediate/transfer-increment-20260909-07/players.csv")
    p.add_argument("--native-reread", type=Path,
                   default=ROOT / "data/generated/native08-integrated-20260912-01-reread")
    p.add_argument("--club-map", type=Path, default=ROOT / "config/tm-club-aliases.json")
    p.add_argument("--identity-bridge", type=Path,
                   default=ROOT / "reports/local/current/TRANSFER_DIFF.csv")
    p.add_argument("--identity-bridge-extra", nargs="*", type=Path, default=[])
    p.add_argument("--profiles", nargs="*", type=Path, default=[])
    p.add_argument("--profile-club-aliases", nargs="*", type=Path, default=[],
                   help="Reviewed reserve/U23-to-parent employer affiliations")
    p.add_argument("--prior-rosters", nargs="*", type=Path,
                   default=[ROOT / "data/intermediate/tm-squads.csv"],
                   help="Accepted source snapshots used to distinguish inherited state from new deltas")
    p.add_argument("--prior-plan", type=Path,
                   default=ROOT / "data/generated/transfer-increment-plan-20260909-07.csv")
    p.add_argument("--explicit-deltas", nargs="*", type=Path, default=[])
    p.add_argument("--exceptions", nargs="*", type=Path, default=[])
    p.add_argument("--create-ready", nargs="*", type=Path, default=[],
                   help="Globally searched missing-player proposals requiring a native creation action")
    p.add_argument("--creation-plan", type=Path,
                   help="Guarded native creation candidate for zero-duplicate missing people")
    p.add_argument("--timeline-resolutions", nargs="*", type=Path, default=[],
                   help="Reviewed current transfer/loan rows with direct native identities")
    p.add_argument("--departure-resolutions", nargs="*", type=Path, default=[],
                   help="Reviewed departures from freshly captured squads")
    p.add_argument("--duplicate-affiliation-resolutions", nargs="*", type=Path, default=[],
                   help="Reviewed first/reserve duplicate listings for one native parent club")
    p.add_argument("--native-loan-preconditions", type=Path,
                   default=ROOT / "data/current/integration/native08-loan-preconditions.csv",
                   help="Exact serialized Native08 loan guards from the native semantic exporter")
    p.add_argument("--membership", type=Path,
                   help="Authoritative current membership CSV used for expected club counts")
    p.add_argument("--membership-validation", type=Path,
                   help="Membership sidecar containing source and accepted-native coverage by league")
    p.add_argument("--output-dir", type=Path, default=ROOT / "data/current/integration")
    p.add_argument("--report-dir", type=Path, default=ROOT / "reports/current/integration")
    p.add_argument("--minimum-squad", type=int, default=15)
    p.add_argument("--freeze", action="store_true",
                   help="Write immutable native plan only when every coverage/review gate passes")
    return p


def load_many(paths: list[Path]) -> list[dict]:
    rows: list[dict] = []
    for path in sorted({p.resolve() for p in paths}, key=str):
        rows.extend({**row, "_input": str(path)} for row in read_csv(path))
    return rows


@lru_cache(maxsize=None)
def source_evidence_ok(url: str, digest: str) -> bool:
    if not url.startswith("https://") or not HEX64.fullmatch(digest):
        return False
    raw = ROOT / "data/raw/transfermarkt" / (digest + ".html")
    return raw.is_file() and sha256(raw) == digest


def source_ok(row: dict) -> bool:
    return source_evidence_ok(row.get("source", ""), row.get("source_sha256", ""))


def source_list_ok(urls: str, digests: str) -> bool:
    """Validate a worker artifact that binds several cached source documents."""
    url_items = [v.strip() for v in re.split(r"\s*[|;]\s*", urls) if v.strip()]
    digest_items = [v.strip() for v in re.split(r"\s*[|;]\s*", digests) if v.strip()]
    return (bool(url_items) and len(url_items) == len(digest_items)
            and all(source_evidence_ok(url, digest)
                    for url, digest in zip(url_items, digest_items)))


def source_pairs(urls: str, digests: str) -> list[tuple[str, str]]:
    url_items = [v.strip() for v in re.split(r"\s*[|;]\s*", urls) if v.strip()]
    digest_items = [v.strip() for v in re.split(r"\s*[|;]\s*", digests) if v.strip()]
    return list(zip(url_items, digest_items)) if len(url_items) == len(digest_items) else []


def iso(value: str) -> str:
    return dt.date.fromisoformat(value).isoformat() if value else ""


def club_name_key(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    words = re.sub(r"[^a-z0-9]+", " ", value).split()
    while words and words[0] in {"fc", "sc", "sv", "sg", "sk", "kv", "kvc"}:
        words.pop(0)
    while words and words[-1] in {"fc", "sc", "sv", "sg", "sk"}:
        words.pop()
    return " ".join(words)


def fm_serial_date(value: int | str) -> str:
    return dt.date.fromordinal(int(value) - 1721425).isoformat()


def make_review(row: dict, queue: str, reason: str, *, person: dict | None = None,
                target: str = "", method: str = "") -> dict:
    person = person or {}
    return {
        "queue": queue, "blocking": "YES" if queue in {
            "SOURCE_EVIDENCE", "SOURCE_SCOPE", "CLUB_IDENTITY", "DUPLICATE_OBSERVATION",
            "DUPLICATE_AFFILIATION", "IDENTITY_CONFLICT", "IDENTITY_COLLISION",
            "CONTRACT_CHRONOLOGY", "TYPED_CONDITION", "TRANSFER_TIMELINE",
            "PRIMARY_EXCEPTION", "PROFILE_CONFLICT",
            "TIMELINE_RESOLUTION",
        } else "NO", "reason": reason, "league": row.get("league", ""),
        "club": row.get("club", ""), "club_tm_id": row.get("club_tm_id", ""),
        "player": row.get("player", ""), "player_tm_id": row.get("player_tm_id", ""),
        "dob": row.get("dob", ""), "fm_id": person.get("fm_id", ""),
        "fifa_id": person.get("fifa_id", ""), "native_club_id": person.get("club_id", ""),
        "target_club_id": target, "identity_method": method,
        "source": row.get("source", ""), "source_sha256": row.get("source_sha256", ""),
        "snapshot_date": row.get("snapshot_date", ""),
    }


def main() -> int:
    a = parser().parse_args()
    for output in (a.output_dir, a.report_dir):
        if a.freeze and output.exists():
            raise ValueError("Freeze requires new output directories")
        output.mkdir(parents=True, exist_ok=True)
    roster_rows = load_many(a.rosters)
    create_ready_rows = load_many(a.create_ready)
    create_ready_tm_ids = {r.get("player_tm_id", "") for r in create_ready_rows
                           if r.get("eligibility") == "ADULT_SCOPED_SQUAD_ZERO_DUPLICATE"
                           and r.get("confidence") == "HIGH"}
    creation_plan_rows = read_csv(a.creation_plan) if a.creation_plan and a.creation_plan.is_file() else []
    creation_by_tm = {r.get("player_tm_id", ""): r for r in creation_plan_rows
                      if r.get("status") == "CONFIRMED"}
    prior_roster_rows = load_many([p for p in a.prior_rosters if p.is_file()])
    event_rows = load_many(a.events)
    if not roster_rows:
        raise ValueError("No roster observations")
    snapshots = {r.get("snapshot_date", "") for r in roster_rows}
    if len(snapshots) != 1 or "" in snapshots:
        raise ValueError("Roster inputs must have one explicit snapshot date")
    snapshot = iso(next(iter(snapshots)))
    if snapshot < "2026-09-12":
        raise ValueError("Native10 requires a fresh 2026-09-12 or later snapshot")
    expected_sizes = dict(LEAGUE_SIZES)
    membership_authoritative = False
    membership_rows: list[dict] = []
    membership_validation: dict = {}
    if a.membership:
        membership_rows = read_csv(a.membership)
        confirmed = defaultdict(set)
        for row in membership_rows:
            if row.get("status") == "CONFIRMED" and row.get("native_club_id"):
                confirmed[row.get("league", "")].add(row["native_club_id"])
        if set(confirmed) == set(LEAGUE_SIZES):
            expected_sizes = {league: len(clubs) for league, clubs in confirmed.items()}
            membership_authoritative = all(expected_sizes.values())
    if a.membership_validation and a.membership_validation.is_file():
        membership_validation = json.loads(a.membership_validation.read_text(encoding="utf-8"))
        source_statuses = membership_validation.get("status_by_league", {})
        expected_from_sidecar = membership_validation.get("expected_clubs_by_league", {})
        membership_authoritative = (membership_authoritative
            and not membership_validation.get("source_failures")
            and not membership_validation.get("gaps")
            and set(source_statuses) == set(LEAGUE_SIZES)
            and all(source_statuses[k] == "CONFIRMED" for k in LEAGUE_SIZES)
            and all(expected_from_sidecar.get(k) == expected_sizes.get(k) for k in LEAGUE_SIZES))

    extracted_players = read_csv(a.players)
    native_rows = read_csv(a.native_reread / "native_players.csv")
    native = {r["fm_id"]: r for r in native_rows}
    # Transfers between CountryData files can reallocate the native fm_id.  Join
    # the rich extraction by identity, then take fm_id and club from the reread.
    extracted_index = IdentityIndex(extracted_players)
    prior_plan = {r["fm_id"]: r for r in read_csv(a.prior_plan)} if a.prior_plan.is_file() else {}
    active_loan_ids = set()
    active_loan_records: dict[str, dict] = {}
    integration_path = (a.native_reread.parent / "release-candidate" /
                        "native08-integrated-20260912-01/INTEGRATION.json")
    if integration_path.is_file():
        integration = json.loads(integration_path.read_text(encoding="utf-8"))
        active_loan_records = {r["fm_id"]: r for r in
                               integration.get("changes", []) + integration.get("preserved", [])}
        active_loan_ids = set(active_loan_records)
    native_loan_preconditions = ({r["fm_id"]: r for r in read_csv(a.native_loan_preconditions)}
                                 if a.native_loan_preconditions.is_file() else {})
    full_players = []
    rich_unresolved = []
    for row in native_rows:
        native_dob = dt.datetime.strptime(row["dob"], "%d.%m.%Y").date().isoformat()
        method, candidates = extracted_index.match({
            "player": row["name"], "dob": native_dob, "fifa_id": row["fifa_id"]})
        if method == "MISSING_FROM_FM" and row["fifa_id"] not in {"", "0"}:
            method, candidates = extracted_index.match({
                "player": row["name"], "dob": native_dob, "fifa_id": ""})
        rich = candidates[0] if len(candidates) == 1 else {}
        if not rich:
            rich_unresolved.append(row["fm_id"])
        applied = prior_plan.get(rich.get("fm_id", ""), {})
        team_type = applied.get("team_type", rich.get("squad", ""))
        condition = rich.get("starting_conditions", "UNKNOWN")
        loan_flag = rich.get("contract_loan_flag", "UNKNOWN")
        if applied:
            if applied.get("loan_owner_club_id", "0") != "0":
                condition, loan_flag = "NATIVE_ACTIVE_LOAN", "False"
            elif applied.get("action", "SQUAD") in {"SQUAD", "RESOLVE_EXPIRED_LOAN"}:
                condition, loan_flag = "[]", "False"
        if row["fm_id"] in active_loan_ids:
            condition, loan_flag = "NATIVE_ACTIVE_LOAN", "False"
        if row["fm_id"] in native_loan_preconditions:
            condition, loan_flag = "NATIVE_ACTIVE_LOAN", "False"
        full_players.append({**rich, **row, "dob": native_dob,
                             "_prior_plan_applied": "YES" if applied else "NO",
                             "_native_condition_raw": rich.get("starting_conditions", "UNKNOWN"),
                             "contract_joined": applied.get("joined", rich.get("contract_joined", "")),
                             "contract_until": applied.get("contract_until", rich.get("contract_until", "")),
                             "shirt_number": applied.get("shirt_number", rich.get("shirt_number", ""))
                                if team_type != "RESERVE" else rich.get("shirt_number", ""),
                             "reserve_shirt_number": applied.get("shirt_number", rich.get("reserve_shirt_number", ""))
                                if team_type == "RESERVE" else rich.get("reserve_shirt_number", ""),
                             "squad": team_type, "starting_conditions": condition,
                             "contract_loan_flag": loan_flag})
    full = {r["fm_id"]: r for r in full_players}
    if len(full) != len(native):
        raise ValueError("Native08 contains duplicate player IDs")
    del extracted_index, extracted_players, native_rows
    gc.collect()

    aliases = json.loads(a.club_map.read_text(encoding="utf-8"))
    native_club_rows = read_csv(
        ROOT / "data/intermediate/transfer-increment-20260909-07/clubs.csv")
    native_clubs_by_name: dict[str, list[dict]] = defaultdict(list)
    for club in native_club_rows:
        native_clubs_by_name[club_name_key(club.get("club", ""))].append(club)

    def resolve_club(external_id: str, name: str) -> dict:
        reviewed = aliases.get(external_id)
        if reviewed:
            return reviewed
        exact = native_clubs_by_name.get(club_name_key(name), [])
        if len(exact) == 1:
            return {"club_id": exact[0]["club_id"], "team_type": "FIRST",
                    "tm_name": name, "fm_name": exact[0]["club"],
                    "method": "EXACT_NORMALIZED_GLOBAL_CLUB_NAME"}
        return {}

    duplicate_affiliations = {}
    for row in load_many(a.duplicate_affiliation_resolutions):
        current_tm, parent_tm = (row.get("current_employer_tm_id", ""),
                                 row.get("parent_club_tm_id", ""))
        current_info, parent_info = aliases.get(current_tm, {}), aliases.get(parent_tm, {})
        valid = (row.get("decision") == "RESOLVE_VALID_PARENT_RESERVE_COEXISTENCE"
                 and row.get("snapshot_date") == snapshot
                 and row.get("current_team_type") in {"FIRST", "RESERVE"}
                 and current_tm and parent_tm and current_tm != parent_tm
                 and current_info and parent_info
                 and str(current_info.get("club_id", "")) == row.get("native_club_id", "")
                 and str(parent_info.get("club_id", "")) == row.get("native_club_id", "")
                 and current_info.get("team_type") == row.get("current_team_type")
                 and source_list_ok(row.get("source_urls", ""), row.get("source_sha256s", "")))
        tm_id = row.get("player_tm_id", "")
        if valid and tm_id and tm_id not in duplicate_affiliations:
            duplicate_affiliations[tm_id] = row
    index = IdentityIndex(full_players)
    # Moving players between native country files can reallocate fm_id.  Rebind
    # accepted Native08 loan records by exact name and DOB before generating a
    # typed successor action.
    for record in list(active_loan_records.values()):
        method, candidates = index.match({"player": record.get("name", ""),
                                          "dob": record.get("dob", ""), "fifa_id": ""})
        if method == "DOB_NAME" and len(candidates) == 1:
            active_loan_records[candidates[0]["fm_id"]] = record
    active_loan_ids = set(active_loan_records)
    native_club_ids = {c["club_id"] for c in read_csv(
        ROOT / "data/intermediate/transfer-increment-20260909-07/clubs.csv")}
    profiles = {}
    for row in load_many(a.profiles):
        if row.get("snapshot_date") == snapshot and row.get("source_status") == "CONFIRMED" and source_ok(row):
            key = row.get("player_tm_id", "")
            if key and row.get("retrieved_at", row.get("imported_at", "")) >= profiles.get(
                    key, {}).get("retrieved_at", profiles.get(key, {}).get("imported_at", "")):
                profiles[key] = row
    profile_club_aliases = {}
    for row in load_many(a.profile_club_aliases):
        if (row.get("status") == "CONFIRMED" and row.get("snapshot_date") == snapshot
                and row.get("team_type") in {"FIRST", "RESERVE"} and source_ok(row)):
            profile_club_aliases[row.get("player_tm_id", "")] = row
    prior_rosters = {}
    for row in prior_roster_rows:
        key = (row.get("player_tm_id", ""), row.get("club_tm_id", ""))
        if all(key) and row.get("source_status") == "CONFIRMED":
            prior_rosters[key] = row
    bridge: dict[str, set[str]] = defaultdict(set)
    identity_review_rows: dict[str, dict] = {}
    prior_bridge_rows: list[dict] = []
    if a.identity_bridge.is_file():
        for row in read_csv(a.identity_bridge):
            prior_bridge_rows.append(row)
            ident = row.get("fm_id", "")
            if (ident in native and row.get("player_tm_id") and row.get("status") == "CONFIRMED"
                    and row.get("dob") == full[ident]["dob"]):
                bridge[row["player_tm_id"]].add(ident)
    for row in load_many(a.identity_bridge_extra):
        ident = row.get("fm_id", row.get("native_fm_id", row.get("prior_native_fm_id", "")))
        tm_id = row.get("player_tm_id", row.get("external_player_id", ""))
        status = row.get("status", "")
        supplied_fifa = row.get("fifa_id", row.get("native_fifa_id",
                                                   row.get("prior_native_fifa_id", "")))
        supplied_dob = row.get("dob", row.get("prior_native_dob", ""))
        if row.get("creation_action") == "DO_NOT_CREATE_USE_NATIVE_BRIDGE":
            profile_evidence_ok = (source_evidence_ok(row.get("profile_source_url", ""),
                                                      row.get("profile_source_sha256", ""))
                if row.get("profile_present") == "YES" else
                row.get("prior_identity_status") == "CONFIRMED" and
                row.get("prior_identity_method", "").startswith("EXISTING_OVERRIDE_"))
            evidence_ok = (row.get("snapshot_date") == snapshot
                and profile_evidence_ok
                and source_evidence_ok(row.get("current_significance_source_url", ""),
                                       row.get("current_significance_source_sha256", ""))
                and row.get("prior_native_club_id") == row.get("target_club_id"))
            candidate_method, candidates = index.match({
                "player": row.get("prior_native_name", ""),
                "dob": row.get("prior_native_dob", ""), "fifa_id": ""})
            if candidate_method == "DOB_NAME" and len(candidates) == 1:
                candidate = candidates[0]
                if candidate.get("club_id") == row.get("target_club_id"):
                    ident, supplied_fifa = candidate["fm_id"], candidate["fifa_id"]
            status = "CONFIRMED" if evidence_ok else "REVIEW_REQUIRED"
        if (ident in native and tm_id and status == "CONFIRMED"
                and supplied_dob == full[ident]["dob"]
                and (not supplied_fifa or supplied_fifa == full[ident]["fifa_id"])):
            bridge[tm_id].add(ident)
        elif tm_id and status == "REVIEW_REQUIRED":
            identity_review_rows[tm_id] = row
        elif tm_id and row.get("creation_action") == "HOLD_REVIEW_AFTER_PRIOR_ATTEMPTS":
            identity_review_rows[tm_id] = row

    events: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in event_rows:
        if (row.get("snapshot_date") != snapshot or row.get("source_status") != "CONFIRMED"
                or not source_ok(row)):
            continue
        events[(row.get("player_tm_id", ""), row.get("new_club_tm_id", ""))].append(row)

    # Deduplicate identical source observations and expose real disagreements.
    observations: dict[tuple[str, str], list[dict]] = defaultdict(list)
    reviews: list[dict] = []
    for row in roster_rows:
        key = (row.get("player_tm_id", ""), row.get("club_tm_id", ""))
        observations[key].append(row)
    unique: list[dict] = []
    for key, group in sorted(observations.items()):
        canonical = {tuple((k, r.get(k, "")) for k in (
            "league", "club", "player", "dob", "joined", "contract_until",
            "shirt_number", "source_sha256", "snapshot_date")) for r in group}
        if len(canonical) != 1:
            for row in group:
                reviews.append(make_review(row, "DUPLICATE_OBSERVATION", "Conflicting rows for one player and club"))
        else:
            unique.append(group[0])

    # A person listed by multiple clubs cannot produce a safe destination.
    player_clubs: dict[str, set[str]] = defaultdict(set)
    for row in unique:
        player_clubs[row.get("player_tm_id", "")].add(row.get("club_tm_id", ""))

    resolved: list[dict] = []
    plans: list[dict] = []
    seen_fm: dict[str, set[str]] = defaultdict(set)
    observed_native_by_club: dict[str, set[str]] = defaultdict(set)
    club_observed_counts = Counter(r.get("club_tm_id", "") for r in unique)
    coverage_clubs: dict[str, set[str]] = defaultdict(set)
    for row in unique:
        league = row.get("league", "")
        coverage_clubs[league].add(row.get("club_tm_id", ""))
        if league not in LEAGUE_SIZES:
            reviews.append(make_review(row, "SOURCE_SCOPE", "Unexpected league code"))
            continue
        if row.get("snapshot_date") != snapshot or row.get("source_status") != "CONFIRMED" or not source_ok(row):
            reviews.append(make_review(row, "SOURCE_EVIDENCE", "Roster row is stale, unconfirmed, or missing bound raw evidence"))
            continue
        target_info = aliases.get(row.get("club_tm_id", ""))
        if not target_info:
            reviews.append(make_review(row, "CLUB_IDENTITY", "External club has no reviewed native mapping"))
            continue
        target = str(target_info["club_id"])
        if target not in native_club_ids:
            reviews.append(make_review(row, "CLUB_IDENTITY", "Mapped native club does not exist", target=target))
            continue
        tm_id = row.get("player_tm_id", "")
        profile = profiles.get(tm_id, {})
        profile_conflicting_club = bool(profile and profile.get("club_tm_id")
                                        and profile.get("club_tm_id") != row.get("club_tm_id"))
        affiliation = profile_club_aliases.get(tm_id, {})
        affiliation_valid = bool(profile_conflicting_club and affiliation
            and affiliation.get("roster_club_tm_id") == row.get("club_tm_id")
            and affiliation.get("profile_club_tm_id") == profile.get("club_tm_id")
            and affiliation.get("native_club_id") == target
            and affiliation.get("source") == profile.get("source")
            and affiliation.get("source_sha256") == profile.get("source_sha256"))
        duplicate_resolution = duplicate_affiliations.get(tm_id, {})
        if len(player_clubs[tm_id]) != 1 and not (
                duplicate_resolution
                and player_clubs[tm_id] == {
                    duplicate_resolution.get("current_employer_tm_id", ""),
                    duplicate_resolution.get("parent_club_tm_id", "")}
                and row.get("club_tm_id") == duplicate_resolution.get("current_employer_tm_id", "")):
            if (duplicate_resolution
                    and row.get("club_tm_id") == duplicate_resolution.get("parent_club_tm_id", "")):
                resolved.append({**make_review(row, "", "", target=target,
                                               method="REVIEWED_PARENT_RESERVE_AFFILIATION"),
                                 "classification": "PARENT_RESERVE_SECONDARY_COVERED"})
                continue
            reviews.append(make_review(row, "DUPLICATE_AFFILIATION", "Player appears in multiple current clubs", target=target))
            continue
        bridged = bridge.get(tm_id, set())
        if len(bridged) == 1:
            person = full[next(iter(bridged))]
            method = "VERIFIED_PRIOR_TM_BRIDGE"
            if person["dob"] != row.get("dob"):
                reviews.append(make_review(row, "IDENTITY_CONFLICT", "Prior identity bridge DOB differs", person=person, target=target, method=method))
                continue
        elif len(bridged) > 1:
            reviews.append(make_review(row, "IDENTITY_AMBIGUOUS", "Prior identity bridge maps to multiple native people", target=target))
            continue
        else:
            method, candidates = index.match({"player": row.get("player", ""), "dob": row.get("dob", ""), "fifa_id": ""})
            if method == "MISSING_FROM_FM" and profile:
                profile_matches = []
                for name in {profile.get("player", ""), profile.get("full_name", "")} - {""}:
                    candidate_method, found = index.match({
                        "player": name, "dob": row.get("dob", ""), "fifa_id": ""})
                    if candidate_method == "DOB_NAME" and len(found) == 1:
                        profile_matches.extend(found)
                unique_matches = {p["fm_id"]: p for p in profile_matches}
                if len(unique_matches) == 1:
                    method, candidates = "PROFILE_EXACT_DOB_NAME", list(unique_matches.values())
            if method not in {"DOB_NAME"} or len(candidates) != 1:
                if method == "PROFILE_EXACT_DOB_NAME" and len(candidates) == 1:
                    pass
                else:
                    queue = "PLAYER_CREATION" if method == "MISSING_FROM_FM" else "IDENTITY_AMBIGUOUS"
                    if queue == "PLAYER_CREATION" and tm_id in creation_by_tm:
                        create = creation_by_tm[tm_id]
                        if (profile_conflicting_club and not affiliation_valid):
                            reviews.append(make_review(row, "PROFILE_CONFLICT",
                                f"Current player profile club {profile.get('club_tm_id')} conflicts with roster club {row.get('club_tm_id')}",
                                target=target, method=method))
                            continue
                        expected_team = affiliation.get("team_type") if affiliation_valid else "FIRST"
                        if (create.get("dob") == row.get("dob") and create.get("club_id") == target
                                and create.get("team_type") == expected_team):
                            resolved.append({**make_review(row, "", "", target=target,
                                                          method="ZERO_DUPLICATE_CREATE_PLAN"),
                                             "classification": "NATIVE_CREATE_CANDIDATE"})
                            reviews.append(make_review(row, "PROVISIONAL_CREATION_RATING",
                                "Native creation is identity/source complete; neutral rating seed remains provisional",
                                target=target, method="ZERO_DUPLICATE_CREATE_PLAN"))
                            continue
                    triage = identity_review_rows.get(tm_id, {})
                    reason = "No unique Native08 identity by exact DOB and normalized full name"
                    review_method = method
                    if (queue == "PLAYER_CREATION"
                            and triage.get("creation_action") == "HOLD_REVIEW_AFTER_PRIOR_ATTEMPTS"):
                        reason = ("Two-attempt creation triage remains blocked: " +
                                  triage.get("missing_prerequisites", "UNRESOLVED_IDENTITY_OR_PROFILE"))
                        review_method = "TWO_ATTEMPT_CREATION_TRIAGE"
                    reviews.append(make_review(row, queue, reason, target=target, method=review_method))
                    continue
            person = candidates[0]
        seen_fm[person["fm_id"]].add(tm_id)
        observed_native_by_club[target].add(person["fm_id"])
        if len(seen_fm[person["fm_id"]]) > 1:
            reviews.append(make_review(row, "IDENTITY_COLLISION", "Multiple external people resolve to one native person", person=person, target=target, method=method))
            continue

        if profile_conflicting_club and not affiliation_valid:
            reviews.append(make_review(row, "PROFILE_CONFLICT",
                f"Current player profile club {profile.get('club_tm_id')} conflicts with roster club {row.get('club_tm_id')}",
                person=person, target=target, method=method))
            resolved.append({**make_review(row, "", "", person=person, target=target, method=method),
                             "classification": "PROFILE_CONFLICT"})
            continue
        joined, until = row.get("joined", ""), row.get("contract_until", "")
        matching_events = events.get((tm_id, row.get("club_tm_id", "")), [])
        profile_conflict = False
        for field in ("joined", "contract_until"):
            observed, supplied = row.get(field, ""), profile.get(field, "")
            if observed and supplied and observed != supplied:
                profile_conflict = True
            elif not observed and supplied:
                if field == "joined": joined = supplied
                else: until = supplied
        raw_shirt = row.get("shirt_number", "")
        shirt = "" if raw_shirt.strip() in {"", "-", "—", "–"} else raw_shirt.strip()
        team_type = (affiliation.get("team_type") if affiliation_valid else
                     str(target_info.get("team_type", "FIRST")).upper())
        contract_end_preserved = False
        if (joined and not until and person.get("contract_until", "") >= snapshot
                and person.get("contract_until", "") >= joined
                and len({e.get("event_id", "") for e in matching_events
                         if e.get("transfer_type") == "PERMANENT"}) == 1):
            until = person["contract_until"]
            contract_end_preserved = True
        try:
            valid_contract = bool(joined and until) and (iso(person["dob"]) <= iso(joined) <= snapshot <= iso(until))
            valid_shirt = not shirt or (shirt.isdigit() and 0 <= int(shirt) <= 99)
        except ValueError:
            valid_contract = False
            valid_shirt = False
        native_number = person["reserve_shirt_number"] if team_type == "RESERVE" else person["shirt_number"]
        club_changed = person["club_id"] != target
        metadata_changed = (valid_contract and (person["contract_joined"] != joined
                            or person["contract_until"] != until))
        shirt_changed = bool(shirt) and native_number != shirt
        source_semantic_fields = ("dob", "joined", "contract_until")
        prior = prior_rosters.get((tm_id, row.get("club_tm_id", "")))
        prior_raw_shirt = prior.get("shirt_number", "") if prior else ""
        prior_shirt = "" if prior_raw_shirt.strip() in {"", "-", "—", "–"} else prior_raw_shirt.strip()
        source_changed = (prior is None or shirt != prior_shirt or any(
            row.get(field, "") != prior.get(field, "") for field in source_semantic_fields))
        inherited_native = bool(prior and not source_changed and not club_changed
                                and person.get("_prior_plan_applied") == "YES")
        changed = (club_changed or (not inherited_native and (metadata_changed or shirt_changed
                   or (person["squad"] == "RESERVE") != (team_type == "RESERVE"))))
        classification = ("INHERITED_NATIVE08_COVERED" if inherited_native else
                          "NATIVE_DELTA" if changed else "CURRENT_COVERED")
        result = {**make_review(row, "", "", person=person, target=target, method=method),
                  "classification": classification}
        resolved.append(result)
        if not changed:
            continue
        if profile_conflict or not valid_shirt or not valid_contract:
            reviews.append(make_review(row, "CONTRACT_CHRONOLOGY", "Joined/end/shirt fields are incomplete or invalid", person=person, target=target, method=method))
            continue
        try:
            conditions = json.loads(person.get("_native_condition_raw", person["starting_conditions"]))
        except json.JSONDecodeError:
            conditions = ["INVALID"]
        if conditions != [] or person.get("contract_loan_flag") != "False":
            if not club_changed:
                # A matching current borrower/club observation is coverage.  Do
                # not rewrite or re-prove an inherited typed Native08 condition.
                continue
            active = active_loan_records.get(person["fm_id"], {})
            actual_loan = native_loan_preconditions.get(person["fm_id"], {})
            condition_type = (4 if actual_loan or active else conditions[0][0]
                              if conditions and isinstance(conditions[0], list) and conditions[0] else None)
            if condition_type == 4 and actual_loan:
                previous = {
                    "previous_loan_owner_club_id": actual_loan["loan_owner_club_id"],
                    "previous_loan_start": dt.datetime.strptime(
                        actual_loan["loan_start"], "%d.%m.%Y").date().isoformat(),
                    "previous_loan_end": dt.datetime.strptime(
                        actual_loan["loan_end"], "%d.%m.%Y").date().isoformat(),
                    "previous_loan_buy_option": actual_loan["loan_buy_option"],
                }
                active = {"native_semantic_precondition": True}
            elif condition_type == 4 and active:
                previous = {
                    "previous_loan_owner_club_id": str(active.get("owner", "")),
                    "previous_loan_start": active.get("effective_start", ""),
                    "previous_loan_end": active.get("end", ""),
                    "previous_loan_buy_option": "0",
                }
            elif condition_type == 4 and conditions and isinstance(conditions[0], list) and len(conditions[0]) >= 5:
                native_loan = conditions[0]
                previous = {
                    "previous_loan_owner_club_id": str(native_loan[3]),
                    "previous_loan_start": fm_serial_date(native_loan[1]),
                    "previous_loan_end": fm_serial_date(native_loan[2]),
                    "previous_loan_buy_option": str(native_loan[4]),
                }
                active = {"native_condition": True}
            if condition_type == 4 and active:
                profile_owner = profile.get("loan_owner_tm_id", "")
                owner_info = resolve_club(profile_owner, profile.get("loan_owner", "")) if profile_owner else None
                permanent = [e for e in matching_events if e.get("transfer_type") == "PERMANENT"]
                loan_returns = [e for e in matching_events if e.get("transfer_type") == "LOAN_RETURN"
                                and e.get("explicit_event_date")
                                and e.get("explicit_event_date") <= snapshot]
                terminal_events = permanent + loan_returns
                event_ids = {e.get("event_id", "") for e in terminal_events}
                plan_source = profile if profile else row
                plan_joined = profile.get("joined", joined) if profile else joined
                plan_loan_end = profile.get("contract_until", "") if profile else ""
                owner_until = profile.get("owner_contract_until", "") if profile else ""
                plan_until = owner_until or person.get("contract_until", "")
                if plan_loan_end and (not plan_until or plan_until < plan_loan_end):
                    plan_until = plan_loan_end
                typed_base = {
                    "fm_id": person["fm_id"], "fifa_id": person["fifa_id"], "dob": person["dob"],
                    "old_club_id": person["club_id"], "new_club_id": target, "joined": plan_joined,
                    "contract_until": plan_until, "shirt_number": shirt or native_number,
                    "team_type": team_type, "status": "CONFIRMED", "source": plan_source.get("source", ""),
                    "source_sha256": plan_source.get("source_sha256", ""), "snapshot_date": snapshot,
                    "acquisition_seller_club_id": "0", "acquisition_event_key": "",
                    "acquisition_date": "", "acquisition_source": "", "acquisition_source_sha256": "",
                    **previous,
                }
                valid_previous = (previous["previous_loan_owner_club_id"] in native_club_ids
                                  and bool(previous["previous_loan_start"] and previous["previous_loan_end"])
                                  and previous["previous_loan_start"] <= previous["previous_loan_end"])
                is_expired = previous["previous_loan_end"] < snapshot
                new_owner_id = str(owner_info.get("club_id", "")) if owner_info else ""
                early_borrower_switch = (is_expired and new_owner_id ==
                    previous["previous_loan_owner_club_id"] and target != person["club_id"]
                    and plan_joined >= previous["previous_loan_start"]
                    and plan_joined < previous["previous_loan_end"])
                successor_chronology = (not is_expired or
                    plan_joined >= previous["previous_loan_end"] or early_borrower_switch)
                if (owner_info and new_owner_id in native_club_ids
                        and str(owner_info.get("club_id")) != target and plan_joined and plan_loan_end
                        and plan_joined <= snapshot <= plan_loan_end <= plan_until and valid_previous
                        and successor_chronology):
                    plans.append({**typed_base,
                        "loan_owner_club_id": new_owner_id, "loan_end": plan_loan_end,
                        "action": "REPLACE_EXPIRED_LOAN" if is_expired else "REPLACE_ACTIVE_LOAN"})
                    if early_borrower_switch:
                        reviews.append(make_review(row, "EARLY_BORROWER_SWITCH",
                            "Current profile proves the same owner switched borrowers before the stale native loan end",
                            person=person, target=target, method=method))
                    continue
                if (not profile_owner and len(event_ids) == 1 and valid_contract and valid_previous):
                    event = terminal_events[0]
                    plans.append({**typed_base, "joined": joined, "contract_until": until,
                        "loan_owner_club_id": "0", "loan_end": "",
                        "action": "RESOLVE_EXPIRED_LOAN" if is_expired else "RESOLVE_ACTIVE_LOAN",
                        "acquisition_event_key": event.get("event_id", ""),
                        "acquisition_date": (event.get("explicit_event_date", "")
                            if event.get("explicit_event_date", "") <= joined else "")})
                    continue
                if (is_expired and profile and not profile_owner and valid_contract and valid_previous
                        and target == previous["previous_loan_owner_club_id"]):
                    plans.append({**typed_base, "joined": joined, "contract_until": until,
                        "loan_owner_club_id": "0", "loan_end": "", "action": "RESOLVE_EXPIRED_LOAN"})
                    continue
            reason = ("Existing native loan condition requires verified current owner and return chronology"
                      if condition_type == 4 or person.get("contract_loan_flag") == "True" else
                      "Existing future, retirement, ban, or other condition requires a preserving typed plan")
            reviews.append(make_review(row, "TYPED_CONDITION", reason,
                                       person=person, target=target, method=method))
            continue
        if club_changed:
            permanent = [e for e in matching_events if e.get("transfer_type") == "PERMANENT"]
            if len({e.get("event_id", "") for e in permanent}) != 1:
                reason = "No unique confirmed permanent event for changed native club"
                if any(e.get("transfer_type") == "LOAN" for e in matching_events):
                    reason = "Current loan requires owner and return-date evidence"
                reviews.append(make_review(row, "TRANSFER_TIMELINE", reason, person=person, target=target, method=method))
                continue
            event = permanent[0]
        else:
            event = None
        effective_joined = joined if valid_contract else person["contract_joined"]
        effective_until = until if valid_contract else person["contract_until"]
        effective_shirt = shirt if shirt else native_number
        plans.append({
            "fm_id": person["fm_id"], "fifa_id": person["fifa_id"], "dob": person["dob"],
            "old_club_id": person["club_id"], "new_club_id": target, "joined": effective_joined,
            "contract_until": effective_until, "shirt_number": effective_shirt, "team_type": team_type,
            "status": "CONFIRMED", "source": row["source"], "source_sha256": row["source_sha256"],
            "snapshot_date": snapshot, "loan_owner_club_id": "0", "loan_end": "",
            "action": "SQUAD", "previous_loan_owner_club_id": "0", "previous_loan_start": "",
            "previous_loan_end": "", "previous_loan_buy_option": "0",
            "acquisition_seller_club_id": "0", "acquisition_event_key": "",
            "acquisition_date": event.get("explicit_event_date", "") if event else "",
            "acquisition_source": "", "acquisition_source_sha256": "",
        })
        if contract_end_preserved:
            reviews.append(make_review(row, "CONTRACT_END_PRESERVED",
                "Confirmed permanent move; public end unavailable, so still-valid native contract end is preserved",
                person=person, target=target, method=method))

    # A roster omission is not departure authority.  Surface only people who
    # were confirmed in the prior roster source and disappeared from a freshly
    # captured club; do not enumerate all native reserve/youth members.
    current_pairs = {(r.get("player_tm_id", ""), r.get("club_tm_id", "")) for r in unique}
    roster_by_tm = {r.get("player_tm_id", ""): r for r in unique}
    observed_tm_clubs = {r.get("club_tm_id", "") for r in unique}
    prior_seen = set()
    for row in prior_bridge_rows:
        pair = row.get("player_tm_id", ""), row.get("club_tm_id", "")
        if (row.get("status") != "CONFIRMED" or not all(pair) or pair in prior_seen
                or pair[1] not in observed_tm_clubs or pair in current_pairs):
            continue
        prior_seen.add(pair)
        person = full.get(row.get("fm_id", ""), {})
        if not person or person.get("dob") != row.get("dob") or (
                row.get("player") and club_name_key(person.get("name", "")) !=
                club_name_key(row.get("player", ""))):
            method, candidates = index.match({"player": row.get("player", ""),
                                              "dob": row.get("dob", ""), "fifa_id": ""})
            person = candidates[0] if method == "DOB_NAME" and len(candidates) == 1 else {}
        reviews.append(make_review({**row, "snapshot_date": snapshot}, "SOURCE_ABSENCE",
            "Confirmed prior roster member is absent now; destination/release evidence required",
            person=person, target=person.get("club_id", ""), method="VERIFIED_PRIOR_TM_BRIDGE"))

    # Any FM collision invalidates all rows for that person, even the first row encountered.
    collided = {ident for ident, tm_ids in seen_fm.items() if len(tm_ids) > 1}
    if collided:
        plans = [r for r in plans if r["fm_id"] not in collided]

    timeline_applied = set()
    timeline_attempted = set()
    for row in load_many(a.timeline_resolutions):
        if row.get("status") != "CONFIRMED":
            continue
        ident, tm_id = row.get("fm_id", ""), row.get("player_tm_id", "")
        timeline_attempted.add(tm_id)
        person, roster = full.get(ident), roster_by_tm.get(tm_id, {})
        source, digest = row.get("event_source", ""), row.get("event_source_sha256", "")
        target, transfer_type = row.get("target_club_id", ""), row.get("transfer_type", "")
        try:
            native_conditions = json.loads(person.get("starting_conditions", "[]")) if person else ["INVALID"]
        except json.JSONDecodeError:
            native_conditions = ["INVALID"]
        loan_owner = row.get("transaction_owner_native_club_id", "") if transfer_type == "LOAN" else "0"
        # Worker source fields retain profile semantics: contract_until is the
        # loan spell end; loan_end contains the owning-club contract end.
        spell_end = row.get("contract_until", "") if transfer_type == "LOAN" else ""
        owner_until = row.get("loan_end", "") if transfer_type == "LOAN" else row.get("contract_until", "")
        valid = (person is not None and roster and row.get("dob") == person.get("dob")
                 and row.get("fifa_id") == person.get("fifa_id")
                 and row.get("native_club_id") == person.get("club_id")
                 and target in native_club_ids and source_evidence_ok(source, digest)
                 and row.get("joined") and owner_until and row["joined"] <= snapshot <= owner_until
                 and native_conditions == [] and person.get("contract_loan_flag") == "False"
                 and (transfer_type == "FREE_TRANSFER" or transfer_type == "LOAN"))
        if transfer_type == "LOAN":
            valid = valid and loan_owner in native_club_ids and loan_owner != target and bool(
                spell_end) and snapshot <= spell_end <= owner_until and person.get("club_id") in {
                    loan_owner, target}
        if not valid:
            reviews.append(make_review(roster or {"player": row.get("player", ""), "dob": row.get("dob", "")},
                "TIMELINE_RESOLUTION", "Confirmed timeline row failed exact native, source, or loan chronology guards",
                person=person, target=target, method="REVIEWED_TIMELINE"))
            continue
        raw_shirt = roster.get("shirt_number", "")
        shirt = raw_shirt if raw_shirt.isdigit() else (person.get("reserve_shirt_number", "")
            if person.get("squad") == "RESERVE" else person.get("shirt_number", ""))
        plans = [p for p in plans if p["fm_id"] != ident]
        plans.append({
            "fm_id": ident, "fifa_id": person["fifa_id"], "dob": person["dob"],
            "old_club_id": person["club_id"], "new_club_id": target, "joined": row["joined"],
            "contract_until": owner_until, "shirt_number": shirt or "0", "team_type": "FIRST",
            "status": "CONFIRMED", "source": source, "source_sha256": digest,
            "snapshot_date": snapshot, "loan_owner_club_id": loan_owner, "loan_end": spell_end,
            "action": "SQUAD", "previous_loan_owner_club_id": "0", "previous_loan_start": "",
            "previous_loan_end": "", "previous_loan_buy_option": "0",
            "acquisition_seller_club_id": "0", "acquisition_event_key": row.get("transfer_event_id", ""),
            "acquisition_date": row.get("event_date", ""), "acquisition_source": "",
            "acquisition_source_sha256": "",
        })
        timeline_applied.add(tm_id)
    if timeline_attempted:
        reviews = [r for r in reviews if not (r["queue"] == "TRANSFER_TIMELINE"
                                               and r["player_tm_id"] in timeline_attempted)]

    # Apply explicit departures only when both the transfer event and the
    # current player profile are cached and the destination/loan owner resolve
    # uniquely to native clubs.  Event-only rows remain review evidence.
    departure_applied = set()
    for row in load_many(a.departure_resolutions):
        tm_id = row.get("player_tm_id", "")
        identity_method, candidates = index.match({"player": row.get("player", ""),
                                                    "dob": row.get("dob", ""), "fifa_id": ""})
        person = candidates[0] if identity_method == "DOB_NAME" and len(candidates) == 1 else None
        ident = person.get("fm_id", "") if person else ""
        pairs = source_pairs(row.get("source_url", ""), row.get("source_sha256", ""))
        target_info = resolve_club(row.get("new_club_tm_id", ""), row.get("new_club", ""))
        target = str(target_info.get("club_id", ""))
        transfer_type = row.get("transaction_type", "")
        complete_source = (row.get("status") == "CONFIRMED"
            and row.get("source_status") == "CONFIRMED"
            and row.get("evidence_class") == "EXPLICIT_TRANSFER_EVENT+CURRENT_PROFILE"
            and float(row.get("confidence", "0") or 0) >= .99
            and source_list_ok(row.get("source_url", ""), row.get("source_sha256", ""))
            and len(pairs) >= 2)
        old_info = resolve_club(row.get("old_club_tm_id", ""), row.get("old_club", ""))
        identity_ok = (person is not None and row.get("dob") == person.get("dob")
            and str(old_info.get("club_id", "")) == person.get("club_id"))
        effective, spell_end = row.get("effective_date", ""), row.get("loan_end", "")
        owner_until = row.get("owner_contract_until", "")
        current_until = row.get("current_contract_until", "")
        owner_info = resolve_club(row.get("owner_club_tm_id", ""), row.get("owner", ""))
        owner = str(owner_info.get("club_id", "")) if transfer_type == "LOAN" else "0"
        try:
            chronology_ok = bool(effective and effective <= snapshot)
            if transfer_type == "LOAN":
                chronology_ok = (chronology_ok and bool(spell_end and owner_until)
                    and snapshot <= spell_end <= owner_until)
            elif transfer_type == "PERMANENT":
                chronology_ok = chronology_ok and bool(current_until) and snapshot <= current_until
            else:
                chronology_ok = False
        except TypeError:
            chronology_ok = False
        if not (complete_source and identity_ok and target in native_club_ids
                and target != person.get("club_id") and chronology_ok
                and (transfer_type != "LOAN" or
                     (owner in native_club_ids and owner != target))):
            continue
        actual_loan = native_loan_preconditions.get(ident, {})
        try:
            native_conditions = json.loads(person.get("_native_condition_raw", "[]"))
        except json.JSONDecodeError:
            native_conditions = ["INVALID"]
        action = "SQUAD"
        previous = {"previous_loan_owner_club_id": "0", "previous_loan_start": "",
                    "previous_loan_end": "", "previous_loan_buy_option": "0"}
        if actual_loan:
            previous = {
                "previous_loan_owner_club_id": actual_loan["loan_owner_club_id"],
                "previous_loan_start": dt.datetime.strptime(
                    actual_loan["loan_start"], "%d.%m.%Y").date().isoformat(),
                "previous_loan_end": dt.datetime.strptime(
                    actual_loan["loan_end"], "%d.%m.%Y").date().isoformat(),
                "previous_loan_buy_option": actual_loan["loan_buy_option"],
            }
            expired = previous["previous_loan_end"] < snapshot
            if transfer_type == "LOAN":
                action = "REPLACE_EXPIRED_LOAN" if expired else "REPLACE_ACTIVE_LOAN"
            else:
                action = "RESOLVE_EXPIRED_LOAN" if expired else "RESOLVE_ACTIVE_LOAN"
        elif native_conditions != [] or person.get("contract_loan_flag") != "False":
            continue
        profile_source, profile_digest = pairs[-1]
        event_source, event_digest = pairs[0]
        shirt = (person.get("reserve_shirt_number", "") if person.get("squad") == "RESERVE"
                 else person.get("shirt_number", "")) or "0"
        plans = [p for p in plans if p["fm_id"] != ident]
        plans.append({
            "fm_id": ident, "fifa_id": person["fifa_id"], "dob": person["dob"],
            "old_club_id": person["club_id"], "new_club_id": target, "joined": effective,
            "contract_until": owner_until if transfer_type == "LOAN" else current_until,
            "shirt_number": shirt, "team_type": str(target_info.get("team_type", "FIRST")),
            "status": "CONFIRMED", "source": profile_source, "source_sha256": profile_digest,
            "snapshot_date": snapshot, "loan_owner_club_id": owner,
            "loan_end": spell_end if transfer_type == "LOAN" else "", "action": action,
            **previous, "acquisition_seller_club_id": "0",
            "acquisition_event_key": row.get("event_id", ""),
            "acquisition_date": "", "acquisition_source": "",
            "acquisition_source_sha256": "",
        })
        departure_applied.add(tm_id)
    if departure_applied:
        reviews = [r for r in reviews if not (r["queue"] == "SOURCE_ABSENCE"
                                               and r["player_tm_id"] in departure_applied)]

    # Apply exact, independently reviewed exceptions after broad reconciliation.
    # These rows may use official sources outside the Transfermarkt cache.
    evidence_hashes = {}
    evidence_root = ROOT / "data/current/evidence"
    for path in sorted(evidence_root.rglob("*")) if evidence_root.exists() else []:
        if path.is_file():
            evidence_hashes[sha256(path)] = path
    explicit_rows = load_many(a.explicit_deltas)
    for row in explicit_rows:
        ident = row.get("fm_id", "")
        person = full.get(ident)
        digest = row.get("source_sha256", "")
        valid = (person is not None and row.get("confidence") == "CONFIRMED"
                 and row.get("transaction_type") == "SHIRT_NUMBER"
                 and row.get("dob") == person.get("dob") and row.get("fifa_id") == person.get("fifa_id")
                 and row.get("club_id") == person.get("club_id") and digest in evidence_hashes
                 and row.get("source", "").startswith("https://")
                 and row.get("new_shirt_number", "").isdigit()
                 and 0 <= int(row.get("new_shirt_number", "-1")) <= 99
                 and person.get("contract_joined") and person.get("contract_until"))
        if not valid:
            reviews.append(make_review({
                "league": row.get("league", ""), "player": row.get("player", ""),
                "dob": row.get("dob", ""), "source": row.get("source", ""),
                "source_sha256": digest, "snapshot_date": snapshot,
            }, "PRIMARY_EXCEPTION", "Explicit delta failed Native08 identity, evidence, or contract preconditions",
                person=person, target=row.get("club_id", ""), method="EXPLICIT_NATIVE_ID"))
            continue
        plans = [p for p in plans if p["fm_id"] != ident]
        plans.append({
            "fm_id": ident, "fifa_id": person["fifa_id"], "dob": person["dob"],
            "old_club_id": person["club_id"], "new_club_id": person["club_id"],
            "joined": person["contract_joined"], "contract_until": person["contract_until"],
            "shirt_number": row["new_shirt_number"],
            "team_type": "RESERVE" if person.get("squad") == "RESERVE" else "FIRST",
            "status": "CONFIRMED", "source": row["source"], "source_sha256": digest,
            "snapshot_date": snapshot, "loan_owner_club_id": "0", "loan_end": "",
            "action": "SHIRT_ONLY", "previous_loan_owner_club_id": "0", "previous_loan_start": "",
            "previous_loan_end": "", "previous_loan_buy_option": "0",
            "acquisition_seller_club_id": "0", "acquisition_event_key": "",
            "acquisition_date": "", "acquisition_source": "", "acquisition_source_sha256": "",
        })

    manifest_sources = {}
    primary_manifest = evidence_root / "primary/manifest.json"
    if primary_manifest.is_file():
        for item in json.loads(primary_manifest.read_text(encoding="utf-8")):
            manifest_sources[item["url"]] = item["sha256"]
    for path in a.exceptions:
        package = json.loads(path.read_text(encoding="utf-8"))
        for row in package.get("rows", []):
            ident, source = row.get("fm_id", ""), row.get("source", "")
            person, digest = full.get(ident), manifest_sources.get(source, "")
            exact = (person is not None and row.get("dob") == person.get("dob")
                     and row.get("fifa_id") == person.get("fifa_id")
                     and row.get("old_club_id") == person.get("club_id")
                     and row.get("confidence") == "CONFIRMED" and digest in evidence_hashes)
            if row.get("transaction_type") == "RETIREMENT" and exact:
                plans = [p for p in plans if p["fm_id"] != ident]
                plans.append({
                    "fm_id": ident, "fifa_id": person["fifa_id"], "dob": person["dob"],
                    "old_club_id": person["club_id"], "new_club_id": "0",
                    "joined": "2026-07-01", "contract_until": "2026-06-30",
                    "shirt_number": "0", "team_type": "FIRST", "status": "CONFIRMED",
                    "source": source, "source_sha256": digest, "snapshot_date": snapshot,
                    "loan_owner_club_id": "0", "loan_end": "", "action": "RETIRE",
                    "previous_loan_owner_club_id": "0", "previous_loan_start": "",
                    "previous_loan_end": "", "previous_loan_buy_option": "0",
                    "acquisition_seller_club_id": "0", "acquisition_event_key": "",
                    "acquisition_date": "", "acquisition_source": "", "acquisition_source_sha256": "",
                })
            elif row.get("transaction_type") == "FREE_TRANSFER" and exact and row.get("new_club_id") in native_club_ids:
                matching_profiles = [p for p in profiles.values() if p.get("dob") == row.get("dob")
                                     and p.get("player") == row.get("player")
                                     and p.get("joined") and p.get("contract_until")
                                     and p.get("shirt_number", "").isdigit()]
                if len(matching_profiles) == 1:
                    profile = matching_profiles[0]
                    plans = [p for p in plans if p["fm_id"] != ident]
                    plans.append({
                        "fm_id": ident, "fifa_id": person["fifa_id"], "dob": person["dob"],
                        "old_club_id": person["club_id"], "new_club_id": row["new_club_id"],
                        "joined": profile["joined"], "contract_until": profile["contract_until"],
                        "shirt_number": profile["shirt_number"], "team_type": "FIRST",
                        "status": "CONFIRMED", "source": profile["source"],
                        "source_sha256": profile["source_sha256"], "snapshot_date": snapshot,
                        "loan_owner_club_id": "0", "loan_end": "", "action": "SQUAD",
                        "previous_loan_owner_club_id": "0", "previous_loan_start": "",
                        "previous_loan_end": "", "previous_loan_buy_option": "0",
                        "acquisition_seller_club_id": "0", "acquisition_event_key": "",
                        "acquisition_date": profile["joined"], "acquisition_source": "",
                        "acquisition_source_sha256": "",
                    })
                    continue
                reviews.append(make_review({
                    "club": row.get("old_club", ""), "player": row.get("player", ""),
                    "dob": row.get("dob", ""), "source": source, "source_sha256": digest,
                    "snapshot_date": snapshot,
                }, "PRIMARY_EXCEPTION", "Confirmed free transfer lacks one complete current profile",
                    person=person, target=row.get("new_club_id", ""), method="EXPLICIT_NATIVE_ID"))
            else:
                reviews.append(make_review({
                    "league": row.get("league", ""), "club": row.get("old_club", ""),
                    "player": row.get("player", ""), "dob": row.get("dob", ""),
                    "source": source, "source_sha256": digest, "snapshot_date": snapshot,
                }, "PRIMARY_EXCEPTION", row.get("notes", "Confirmed exception still needs a supported complete native action"),
                    person=person, target=row.get("new_club_id", ""), method="EXPLICIT_NATIVE_ID"))

    coverage = []
    for league, expected in expected_sizes.items():
        clubs = coverage_clubs.get(league, set()) - {""}
        thin = sorted(k for k in clubs if club_observed_counts[k] < a.minimum_squad)
        coverage.append({
            "league": league, "expected_clubs": expected, "observed_clubs": len(clubs),
            "clubs_with_minimum_squad": len(clubs) - len(thin),
            "missing_clubs": max(0, expected - len(clubs)), "thin_club_ids": ";".join(thin),
            "expected_source": "MEMBERSHIP" if membership_authoritative else "FALLBACK_NOT_FREEZE",
            "status": "PASS" if membership_authoritative and len(clubs) == expected and not thin else "GAP",
        })

    # One row per authoritative current club.  Source coverage answers whether
    # the club and squad were captured; native coverage answers whether the
    # accepted Native08 competition state already contains that membership.
    native_diffs = membership_validation.get("native_membership_diff", {})
    club_coverage = []
    resolved_by_club = Counter(r["club_tm_id"] for r in resolved)
    reviews_by_club = Counter(r["club_tm_id"] for r in reviews if r.get("club_tm_id"))
    for member in sorted(membership_rows, key=lambda r: (r.get("league", ""), r.get("club_name", ""))):
        league = member.get("league", "")
        external_id = member.get("external_club_id", "")
        count = club_observed_counts.get(external_id, 0)
        source_confirmed = member.get("status") == "CONFIRMED"
        source_coverage = "PASS" if source_confirmed and count >= a.minimum_squad else "GAP"
        diff = native_diffs.get(league, {})
        added_names = {club_name_key(str(r.get("club_name", ""))) for r in diff.get("added", [])}
        if diff.get("status") == "MATCH":
            native_status = "APPLIED_NATIVE08"
        elif club_name_key(member.get("club_name", "")) in added_names:
            native_status = "PENDING_NATIVE_MEMBERSHIP"
        else:
            native_status = "APPLIED_NATIVE08"
        club_coverage.append({
            "league": league, "club_name": member.get("club_name", ""),
            "external_club_id": external_id, "native_club_id": member.get("native_club_id", ""),
            "membership_source_status": member.get("status", ""),
            "roster_observations": count, "resolved_observations": resolved_by_club.get(external_id, 0),
            "review_rows": reviews_by_club.get(external_id, 0),
            "source_coverage": source_coverage, "native_membership_coverage": native_status,
            "native_league_status": diff.get("status", "UNKNOWN"),
        })
    for review in reviews:
        if review["queue"] == "PLAYER_CREATION":
            age = int((dt.date.fromisoformat(snapshot) - dt.date.fromisoformat(review["dob"])).days / 365.2425)
            if review["player_tm_id"] in create_ready_tm_ids or age >= 20:
                review["blocking"] = "YES"
    queue_counts = Counter(r["queue"] for r in reviews)
    coverage_pass = all(r["status"] == "PASS" for r in coverage)
    blocking_reviews = [r for r in reviews if r["blocking"] == "YES"]
    review_pass = not blocking_reviews
    duplicate_plan_ids = [k for k, n in Counter(r["fm_id"] for r in plans).items() if n > 1]
    plan_safe = not duplicate_plan_ids
    freeze_ready = coverage_pass and review_pass and plan_safe and bool(plans)

    plans.sort(key=lambda r: int(r["fm_id"]))
    reviews.sort(key=lambda r: (r["queue"], r["league"], r["club"], r["player"], r["dob"]))
    resolved.sort(key=lambda r: (r["league"], r["club"], r["player"], r["dob"]))
    write_csv(a.output_dir / "candidate-squad-plan.csv", PLAN_FIELDS, plans)
    write_csv(a.output_dir / "resolved-observations.csv",
              REVIEW_FIELDS + ["classification"], resolved)
    write_csv(a.report_dir / "review-queue.csv", REVIEW_FIELDS, reviews)
    write_csv(a.report_dir / "coverage-matrix.csv", list(coverage[0]), coverage)
    if club_coverage:
        write_csv(a.report_dir / "CLUB_COVERAGE_MATRIX.csv", list(club_coverage[0]), club_coverage)

    essential = [r for r in reviews if r["blocking"] == "YES" and r.get("fm_id")
                 and r.get("target_club_id") and r.get("native_club_id") != r.get("target_club_id")]
    essential.sort(key=lambda r: ({"TYPED_CONDITION": 0, "PROFILE_CONFLICT": 1,
                                  "TRANSFER_TIMELINE": 2}.get(r["queue"], 9),
                                  r["league"], r["player"]))
    write_csv(a.report_dir / "essential-state-blockers.csv", REVIEW_FIELDS, essential)

    roster_by_pair = {(r.get("player_tm_id", ""), r.get("club_tm_id", "")): r for r in unique}
    creation_review = []
    for review in (r for r in reviews if r["queue"] == "PLAYER_CREATION"):
        row = roster_by_pair.get((review["player_tm_id"], review["club_tm_id"]), {})
        profile = profiles.get(review["player_tm_id"], {})
        identity_review = identity_review_rows.get(review["player_tm_id"], {})
        age = int((dt.date.fromisoformat(snapshot) - dt.date.fromisoformat(review["dob"])).days / 365.2425)
        candidate = identity_review.get("candidate_fm_id", "")
        searched = (identity_review.get("identity_method") == "REVIEW_REQUIRED_AFTER_TWO_ATTEMPTS"
                    and "native08_bridge" in identity_review.get("attempts", ""))
        profile_complete = bool(profile.get("nationality_text") and row.get("position")
                                and (profile.get("joined") or row.get("joined"))
                                and (profile.get("contract_until") or row.get("contract_until")))
        if review["player_tm_id"] in create_ready_tm_ids:
            disposition = "CREATE_READY_NATIVE_ACTION_REQUIRED"
            reason = "Global zero-duplicate proof and source fields are complete; native creation action remains required"
        elif identity_review.get("creation_action") == "HOLD_REVIEW_AFTER_PRIOR_ATTEMPTS":
            disposition = "EXPLICIT_PREREQUISITE_BLOCKER"
            reason = ("Two prior identity/profile attempts completed; unresolved prerequisite: " +
                      identity_review.get("missing_prerequisites", "UNRESOLVED_IDENTITY_OR_PROFILE"))
        elif age < 20:
            disposition = "ACADEMY_EDGE_CASE_GOOD_ENOUGH"
            reason = "Under-20 source roster entry; retain as explicit coverage edge case unless promoted to creation scope"
        elif candidate:
            disposition = "IDENTITY_CANDIDATE_REVIEW"
            reason = f"Native candidate {candidate} must be resolved before player creation"
        elif searched and profile_complete:
            disposition = "CREATE_EVIDENCE_RATING_REQUIRED"
            reason = "Global Native08 identity search found no safe match; identity/contract evidence complete, but no reviewed native rating row exists"
        elif searched:
            disposition = "CREATE_PROFILE_FIELDS_REQUIRED"
            reason = "Global Native08 identity search found no safe match; nationality or contract evidence remains incomplete"
        else:
            disposition = "IDENTITY_SEARCH_REQUIRED"
            reason = "Native08 nonmatch has not passed the two-step global identity review"
        creation_review.append({
            "league": review["league"], "club": review["club"],
            "club_tm_id": review["club_tm_id"], "target_club_id": review["target_club_id"],
            "player": review["player"], "player_tm_id": review["player_tm_id"],
            "dob": review["dob"], "age": age, "position": row.get("position", ""),
            "shirt_number": row.get("shirt_number", ""),
            "joined": profile.get("joined", row.get("joined", "")),
            "contract_until": profile.get("contract_until", row.get("contract_until", "")),
            "nationality": profile.get("nationality_text", ""),
            "identity_search": "VERIFIED_NONMATCH" if searched and not candidate else
                               "POSSIBLE_NATIVE_CANDIDATE" if candidate else "UNVERIFIED_NONMATCH",
            "profile_complete": "YES" if profile_complete else "NO",
            "disposition": disposition, "native_create_ready": "NO", "reason": reason,
            "source": review["source"], "source_sha256": review["source_sha256"],
            "snapshot_date": snapshot,
        })
    creation_review.sort(key=lambda r: (r["disposition"], r["league"], r["club"], r["player"]))
    if creation_review:
        write_csv(a.report_dir / "player-creation-review.csv", list(creation_review[0]), creation_review)

    input_hashes = {str(p.resolve()): sha256(p) for p in sorted(set(a.rosters + a.prior_rosters + a.events + a.timeline_resolutions + a.departure_resolutions + a.duplicate_affiliation_resolutions + a.explicit_deltas + a.exceptions + a.create_ready + a.profiles + a.profile_club_aliases + a.identity_bridge_extra + [
        a.players, a.native_reread / "native_players.csv", a.club_map, a.prior_plan,
    ] + ([a.native_loan_preconditions] if a.native_loan_preconditions else []) +
        ([a.creation_plan] if a.creation_plan else []) + ([a.membership] if a.membership else []) +
        ([a.membership_validation] if a.membership_validation else [])), key=str) if p.is_file()}
    if a.identity_bridge.is_file():
        input_hashes[str(a.identity_bridge.resolve())] = sha256(a.identity_bridge)
    report = {
        "status": "READY_TO_FREEZE" if freeze_ready else "INCOMPLETE_REVIEW_REQUIRED",
        "snapshot_date": snapshot, "native_base": str(a.native_reread.resolve()),
        "native_players": len(native), "rich_native_joins_unresolved": len(rich_unresolved),
        "rich_native_join_examples": rich_unresolved[:25],
        "roster_observations": len(roster_rows),
        "unique_observations": len(unique), "resolved_observations": len(resolved),
        "candidate_plan_rows": len(plans), "candidate_club_changes": sum(
            r["old_club_id"] != r["new_club_id"] for r in plans),
        "coverage_pass": coverage_pass, "membership_authoritative": membership_authoritative,
        "review_pass": review_pass, "blocking_review_rows": len(blocking_reviews),
        "review_queue_rows": len(reviews), "review_queue_counts": dict(sorted(queue_counts.items())),
        "source_membership_clubs": len(membership_rows),
        "source_membership_coverage_pass": bool(club_coverage) and all(
            r["source_coverage"] == "PASS" for r in club_coverage),
        "native_membership_pending_clubs": sum(
            r["native_membership_coverage"] != "APPLIED_NATIVE08" for r in club_coverage),
        "essential_state_blockers": len(essential), "top_essential_state_blockers": essential[:10],
        "player_creation_dispositions": dict(sorted(Counter(
            r["disposition"] for r in creation_review).items())),
        "native_create_ready_rows": sum(r["native_create_ready"] == "YES" for r in creation_review),
        "planned_player_creations": len(creation_plan_rows),
        "planned_creation_tm_ids": sorted(creation_by_tm, key=int),
        "timeline_resolutions_applied": len(timeline_applied),
        "departure_resolutions_applied": len(departure_applied),
        "duplicate_affiliations_resolved": len(duplicate_affiliations),
        "coverage": coverage, "duplicate_plan_ids": duplicate_plan_ids,
        "freeze_ready": freeze_ready, "frozen": False, "input_sha256": input_hashes,
        "candidate_plan_sha256": sha256(a.output_dir / "candidate-squad-plan.csv"),
        "ratings_policy": "Existing-player ratings are not generated or changed by the squad plan; separate created-player seeds remain provisional.",
        "history_policy": "Existing player histories are retained; guarded new-player candidates contain no invented history entries.",
        "conditions_policy": "Rows with any existing starting condition or loan flag are held for typed review.",
        "limitations": "Roster capture proves current inclusion, not every departure, loan owner, or acquisition chronology. No native database was written.",
    }
    if a.freeze:
        if not freeze_ready:
            write_json(a.report_dir / "integration.json", report)
            raise ValueError("Coverage or review queues are incomplete; refusing to freeze")
        frozen = a.output_dir / "native10-squad-plan.csv"
        if frozen.exists():
            raise ValueError("Frozen plan already exists")
        write_csv(frozen, PLAN_FIELDS, plans)
        report.update(frozen=True, frozen_plan=str(frozen), frozen_plan_sha256=sha256(frozen),
                      status="FROZEN_NATIVE10_SQUAD_PLAN_NOT_WRITTEN")
        write_json(frozen.with_suffix(".manifest.json"), report)
    write_json(a.report_dir / "integration.json", report)
    print(json.dumps({k: report[k] for k in (
        "status", "snapshot_date", "roster_observations", "resolved_observations",
        "candidate_plan_rows", "review_queue_rows", "coverage_pass", "freeze_ready")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
