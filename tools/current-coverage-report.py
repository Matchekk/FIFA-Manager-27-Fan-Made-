"""Publish an honest per-club evidence coverage matrix.

The report describes current integration evidence and proposed actions. A
    candidate player plan row marked CONFIRMED is still a proposal; provisional
    creation ratings remain provenance and are deferred from this sprint's gate.
"""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RATING_QUEUE = "PROVISIONAL_CREATION_RATING"


def read(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def source_info(path):
    data = path.read_bytes()
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = max(sum(1 for _ in handle) - 1, 0)
    return {"path": str(path.relative_to(ROOT)), "rows": rows,
            "sha256": hashlib.sha256(data).hexdigest()}


def player_key(row):
    return row.get("player_tm_id") or row.get("fm_id") or row.get("fifa_id") or ""


def unique_rows(rows):
    seen = set()
    result = []
    for row in rows:
        key = player_key(row)
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(row)
    return result


def status_for(queues, names):
    return "PARTIAL" if any(queues.get(name, 0) for name in names) else "GOOD_ENOUGH"


def main():
    membership_path = ROOT / "data/current/league-membership-2026-27.integration.csv"
    observation_paths = [ROOT / "data/current/workers/eng-ger/tm-squads.csv",
                         ROOT / "data/current/workers/south-west/rosters.csv"]
    review_path = ROOT / "reports/current/integration/review-queue.csv"
    resolved_path = ROOT / "data/current/integration/resolved-observations.csv"
    squad_plan_path = ROOT / "data/current/integration/candidate-squad-plan.csv"
    creation_plan_path = ROOT / "data/current/integration/candidate-player-creation-plan.csv"

    memberships = read(membership_path)
    observations = [row for path in observation_paths for row in read(path)]
    reviews = read(review_path)
    resolved = read(resolved_path)
    squad_plan = read(squad_plan_path)
    creation_plan = read(creation_plan_path)

    # Rating seeds are intentionally conservative and deferred. Other review
    # queues remain release blockers when they attach to a candidate.
    blocking_reviews = [row for row in reviews
                        if row.get("blocking") == "YES" and row.get("queue") != RATING_QUEUE]
    raw_blocking_reviews = [row for row in reviews if row.get("blocking") == "YES"]
    rating_reviews = [row for row in reviews if row.get("queue") == RATING_QUEUE]
    review_by_player = {}
    for row in blocking_reviews:
        review_by_player.setdefault(player_key(row), []).append(row)

    creation_ids = [player_key(row) for row in creation_plan]
    duplicate_creation_ids = sorted(key for key, count in Counter(creation_ids).items() if key and count > 1)
    # A blank first_name is valid for a mononym (for example Costinha).  Keep
    # the identity requirement explicit: a last name or pseudonym must still
    # be present, while the remaining native fields are required.
    required_creation_fields = ("dob", "club_id", "joined", "contract_until",
                                "shirt_number", "position", "rating_seed")

    rows = []
    for club in memberships:
        league = club["league"]
        external = club["external_club_id"]
        native_id = club["native_club_id"]
        roster = unique_rows(row for row in observations
                             if row["league"] == league and row["club_tm_id"] == external)
        people = unique_rows(row for row in resolved
                             if row["league"] == league and row["club_tm_id"] == external)
        holds = [row for row in reviews if row["league"] == league and row["club_tm_id"] == external
                 and row.get("blocking") == "YES" and row.get("queue") != RATING_QUEUE]
        rating_holds = [row for row in rating_reviews if row["league"] == league and row["club_tm_id"] == external]
        material = unique_rows(holds)
        queues = Counter(row["queue"] for row in holds)
        bad_people = {player_key(row) for row in material}
        confirmed = {player_key(row) for row in people
                     if player_key(row) not in bad_people and row.get("classification") != "PROFILE_CONFLICT"}

        candidate_creations = unique_rows(row for row in creation_plan if row["club_id"] == native_id)
        unresolved_creations = []
        ready_creations = []
        rating_only_creations = []
        for candidate in candidate_creations:
            key = player_key(candidate)
            has_name = any(candidate.get(field, "").strip() for field in ("last_name", "pseudonym"))
            has_required_gap = (not has_name or
                                any(not candidate.get(field, "").strip() for field in required_creation_fields))
            candidate_holds = review_by_player.get(key, [])
            has_rating_hold = any(player_key(hold) == key for hold in rating_holds)
            if candidate.get("status") != "CONFIRMED" or has_required_gap or candidate_holds:
                unresolved_creations.append(candidate)
            elif has_rating_hold:
                rating_only_creations.append(candidate)
            else:
                ready_creations.append(candidate)
        confirmed_plan = [row for row in squad_plan if row.get("status") == "CONFIRMED"]
        additions = unique_rows(row for row in confirmed_plan
                                if row["new_club_id"] == native_id and row["old_club_id"] != native_id)
        departures = unique_rows(row for row in confirmed_plan
                                 if row["old_club_id"] == native_id and row["new_club_id"] != native_id)
        loans_in = unique_rows(row for row in additions if row.get("loan_owner_club_id", "0") not in ("", "0"))
        loans_out = unique_rows(row for row in confirmed_plan if row.get("loan_owner_club_id", "0") == native_id)
        loan_keys = {player_key(row) for row in loans_in + loans_out}
        ambiguous = {player_key(row) for row in holds
                     if row["queue"] in ("IDENTITY_AMBIGUOUS", "DUPLICATE_AFFILIATION", "PROFILE_CONFLICT")}
        missing = {player_key(row) for row in holds if row["queue"] == "PLAYER_CREATION"}
        creation_status = ("PROPOSED_UNRESOLVED" if unresolved_creations else
                           "PROPOSED_RATING_DEFERRED" if rating_only_creations else
                           "PROPOSED_READY" if ready_creations else "NONE")

        evidence_complete = (len(roster) >= 18 and not material and not unresolved_creations
                             and not ambiguous and len(confirmed) >= 18)
        overall = "GOOD_ENOUGH" if evidence_complete else "BLOCKED" if len(roster) < 11 else "PARTIAL"
        rows.append({
            "league": league,
            "club": club["club_name"],
            "club_id": native_id,
            "roster_source_status": "COMPLETE" if len(roster) >= 18 else "PARTIAL",
            "arrivals_status": status_for(queues, ("TRANSFER_TIMELINE", "CONTRACT_CHRONOLOGY", "PROFILE_CONFLICT")),
            "departures_status": status_for(queues, ("PRIMARY_EXCEPTION", "SOURCE_ABSENCE", "PROFILE_CONFLICT")),
            "loans_in_status": status_for(queues, ("TYPED_CONDITION", "TRANSFER_TIMELINE")),
            "loans_out_status": status_for(queues, ("TYPED_CONDITION", "TRANSFER_TIMELINE")),
            "missing_players_status": "PARTIAL" if missing else "GOOD_ENOUGH",
            "contracts_status": status_for(queues, ("CONTRACT_CHRONOLOGY",)),
            "shirt_numbers_status": "PARTIAL" if any(not row.get("shirt_number", "").strip() or row.get("shirt_number", "").strip() in ("-", "—", "–") for row in roster) else "GOOD_ENOUGH",
            "creation_status": creation_status,
            "confirmed_players": len(confirmed),
            "proposed_creations": len(candidate_creations),
            "unresolved_creations": len(unresolved_creations),
            "rating_deferred_creations": len(rating_only_creations),
            "sprint_eligible_creations": len(rating_only_creations) + len(ready_creations),
            "ready_creations": len(ready_creations),
            "confirmed_arrivals": len(additions),
            "confirmed_departures": len(departures),
            "confirmed_loans_in": len(loans_in),
            "confirmed_loans_out": len(loans_out),
            "confirmed_loans": len(loan_keys),
            "blocking_holds": len(material),
            "ambiguous_records": len(ambiguous),
            "unmatched_records": len(missing),
            "overall_status": overall,
        })

    out = ROOT / "reports/current/CLUB_COVERAGE_MATRIX.csv"
    with out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        "status": "REVIEW_REQUIRED" if any(row["overall_status"] != "GOOD_ENOUGH" for row in rows) else "GOOD_ENOUGH",
        "snapshot_date": "2026-09-12",
        "clubs": len(rows),
        "overall": dict(Counter(row["overall_status"] for row in rows)),
        "creation_summary": {
            "proposed": len(unique_rows(creation_plan)),
            "unresolved": sum(row["unresolved_creations"] for row in rows),
            "rating_deferred": sum(row["rating_deferred_creations"] for row in rows),
            "sprint_eligible_except_rating": sum(row["sprint_eligible_creations"] for row in rows),
            "ready": sum(row["ready_creations"] for row in rows),
            "duplicate_player_ids": duplicate_creation_ids,
        },
        "review_queue": {
            "rows": len(reviews),
            "raw_blocking_rows": len(raw_blocking_reviews),
            "sprint_blocking_rows": len(blocking_reviews),
            "rating_deferred_rows": len(rating_reviews),
            "sprint_blocking_counts": dict(Counter(row["queue"] for row in blocking_reviews)),
        },
        "loan_counting": "confirmed_loans is the unique union of confirmed incoming and outgoing loan player IDs per club; a player is never counted twice.",
        "interpretation": "Evidence and proposed-action coverage, not proof of native application. Proposed player creations remain unresolved when required native fields or non-rating review holds are outstanding. PROVISIONAL_CREATION_RATING is retained as provenance but deferred from this sprint gate. GOOD_ENOUGH requires a full roster, no sprint-blocking review holds, no unresolved creation candidates, and at least 18 resolved players.",
        "sources": {
            "membership": source_info(membership_path),
            "observations": [source_info(path) for path in observation_paths],
            "review_queue": source_info(review_path),
            "resolved_observations": source_info(resolved_path),
            "candidate_squad_plan": source_info(squad_plan_path),
            "candidate_player_creation_plan": source_info(creation_plan_path),
        },
    }
    (out.parent / "club-coverage-summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
