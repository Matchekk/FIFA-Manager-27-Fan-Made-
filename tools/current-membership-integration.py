"""Generate a deterministic, conservation-checked Native10 membership plan.

Current membership evidence may cover only the requested leagues.  The tool
derives native slots from the accepted Native08 inspection and refuses to
freeze when a relegated/outgoing team lacks explicit destination evidence, or
when a league size changed and no separately validated format plan exists.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from fm27.common import read_csv, sha256, write_csv, write_json

LEAGUES = {"ENG1", "ITA1", "ESP1", "GER1", "FRA1", "POR1", "NED1",
           "BEL1", "TUR1", "CZE1", "GER2", "GER3"}
FIELDS = ["competition_id", "slot", "old_club_id", "old_team_type",
          "new_club_id", "new_team_type", "status", "source",
          "source_sha256", "snapshot_date"]
HEX64 = re.compile(r"[0-9a-f]{64}")


def evidence_ok(url: str, digest: str) -> bool:
    if not url.startswith("https://") or not HEX64.fullmatch(digest):
        return False
    candidates = [ROOT / "data/raw/transfermarkt" / (digest + ".html")]
    candidates.extend((ROOT / "data/current/evidence").rglob(digest + ".*"))
    return any(p.is_file() and sha256(p) == digest for p in candidates)


def team(row: dict) -> tuple[str, str]:
    return row["club_id"], row["team_type"].upper()


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--membership", type=Path, required=True)
    p.add_argument("--coverage", type=Path, required=True)
    p.add_argument("--movement-evidence", type=Path)
    p.add_argument("--dependency-review", type=Path,
                   default=ROOT / "reports/local/LEAGUE_DEPENDENCY_REVIEW_01.json")
    p.add_argument("--competition-members", type=Path,
                   default=ROOT / "data/generated/native-competition-inspection-20260908-01/competition_members.csv")
    p.add_argument("--output-dir", type=Path, default=ROOT / "data/current/integration/membership")
    p.add_argument("--report-dir", type=Path, default=ROOT / "reports/current/integration/membership")
    p.add_argument("--freeze", action="store_true")
    a = p.parse_args()
    a.output_dir.mkdir(parents=True, exist_ok=True)
    a.report_dir.mkdir(parents=True, exist_ok=True)

    rows = read_csv(a.membership)
    coverage_input = json.loads(a.coverage.read_text(encoding="utf-8"))
    expected = coverage_input.get("expected_clubs_by_league", {})
    checkpoint_hashes = coverage_input.get("source_hashes", {})
    failures = coverage_input.get("source_failures", coverage_input.get("gaps", []))
    native_diff = coverage_input.get("native_membership_diff", {})
    required = {"league", "season", "snapshot_date", "club_name", "external_club_id",
                "native_club_id", "team_type", "status", "source_url", "source_sha256"}
    if not rows or not required <= set(rows[0]):
        raise ValueError("Unexpected membership source schema")
    snapshots = {r["snapshot_date"] for r in rows}
    if len(snapshots) != 1 or next(iter(snapshots)) < "2026-09-12":
        raise ValueError("Membership must use one fresh snapshot")
    snapshot = next(iter(snapshots))

    dependencies = {r["league"]: r for r in json.loads(
        a.dependency_review.read_text(encoding="utf-8"))["leagues"]}
    native_rows = read_csv(a.competition_members)
    native_slots = {(r["competition_id"], r["slot"]): r for r in native_rows}
    desired = defaultdict(list)
    reviews = []
    for row in rows:
        valid = (row["league"] in LEAGUES and row["season"] == "2026/27"
                 and row["status"] == "CONFIRMED" and row["native_club_id"].isdigit()
                 and row["team_type"] in {"FIRST", "RESERVE"}
                 and (evidence_ok(row["source_url"], row["source_sha256"])
                      or checkpoint_hashes.get(row["league"]) == row["source_sha256"]))
        if not valid:
            reviews.append({"league": row.get("league", ""), "club": row.get("club_name", ""),
                            "queue": "MEMBERSHIP_IDENTITY_OR_SOURCE", "blocking": "YES",
                            "reason": "Unconfirmed, unmapped, stale, or unbound membership row"})
            continue
        desired[row["league"]].append({**row, "club_id": row["native_club_id"]})

    coverage = []
    for league in sorted(LEAGUES):
        actual = len(desired[league])
        count = expected.get(league)
        status = "PASS" if isinstance(count, int) and count == actual and actual > 0 else "GAP"
        coverage.append({"league": league, "expected_clubs": count if count is not None else "",
                         "confirmed_clubs": actual, "status": status})
    coverage_pass = not failures and all(r["status"] == "PASS" for r in coverage)

    proposals = []
    format_changes = []
    for league in sorted(LEAGUES):
        dep = dependencies[league]
        comp = dep["competition"]["competition_id"]
        current = [r for r in native_rows if r["competition_id"] == comp]
        wanted = {(r["club_id"], r["team_type"]): r for r in desired[league]}
        # The membership checkpoint compares against the accepted Native08
        # serialized scripts.  Older generic inspection is used only to obtain
        # guarded slots for leagues that the checkpoint says still differ.
        if native_diff.get(league, {}).get("status") == "MATCH":
            continue
        if len(current) != len(wanted):
            format_changes.append({"league": league, "competition_id": comp,
                                   "native_teams": len(current), "desired_teams": len(wanted),
                                   "status": "SEPARATE_FORMAT_PLAN_REQUIRED"})
            continue
        current_keys = {team(r) for r in current}
        outgoing = sorted((r for r in current if team(r) not in wanted), key=lambda r: int(r["slot"]))
        incoming = sorted((wanted[k] for k in wanted if k not in current_keys),
                          key=lambda r: (int(r["club_id"]), r["team_type"]))
        if len(outgoing) != len(incoming):
            reviews.append({"league": league, "club": "", "queue": "MEMBERSHIP_CARDINALITY",
                            "blocking": "YES", "reason": "Incoming/outgoing membership is unbalanced"})
            continue
        for old, new in zip(outgoing, incoming):
            proposals.append({"competition_id": comp, "slot": old["slot"],
                "old_club_id": old["club_id"], "old_team_type": old["team_type"].upper(),
                "new_club_id": new["club_id"], "new_team_type": new["team_type"],
                "status": "CONFIRMED", "source": new["source_url"],
                "source_sha256": new["source_sha256"], "snapshot_date": snapshot,
                "league": league})

    # Close global membership conservation with explicit destinations for teams
    # that leave the requested league set.
    movement = {}
    if a.movement_evidence:
        for row in read_csv(a.movement_evidence):
            movement[(row["club_id"], row.get("team_type", "FIRST"))] = row
    before = Counter(team(r) for r in native_rows if ((int(r["competition_id"]) >> 16) & 255) == 1)
    after = before.copy()
    changed_slots = {(r["competition_id"], r["slot"]) for r in proposals}
    for row in proposals:
        after[(row["old_club_id"], row["old_team_type"])] -= 1
        after[(row["new_club_id"], row["new_team_type"])] += 1
    deficits = list((before - after).elements())
    surpluses = list((after - before).elements())
    for outgoing in sorted(deficits):
        evidence = movement.get(outgoing)
        if not evidence or evidence.get("status") != "CONFIRMED" or not evidence_ok(
                evidence.get("source_url", ""), evidence.get("source_sha256", "")):
            reviews.append({"league": "", "club": outgoing[0], "queue": "MOVEMENT_DESTINATION",
                            "blocking": "YES", "reason": "Outgoing team lacks confirmed destination evidence"})
            continue
        destination = evidence.get("destination_competition_id", "")
        candidates = [r for r in native_rows if team(r) in surpluses
                      and r["competition_id"] == destination
                      and (r["competition_id"], r["slot"]) not in changed_slots]
        if len(candidates) != 1:
            reviews.append({"league": "", "club": outgoing[0], "queue": "MOVEMENT_DESTINATION",
                            "blocking": "YES", "reason": "Destination does not identify one displaced native slot"})
            continue
        old = candidates[0]
        proposals.append({"competition_id": destination, "slot": old["slot"],
            "old_club_id": old["club_id"], "old_team_type": old["team_type"].upper(),
            "new_club_id": outgoing[0], "new_team_type": outgoing[1], "status": "CONFIRMED",
            "source": evidence["source_url"], "source_sha256": evidence["source_sha256"],
            "snapshot_date": snapshot, "league": evidence.get("league", "")})
        changed_slots.add((destination, old["slot"]))
        after[team(old)] -= 1
        after[outgoing] += 1
        surpluses.remove(team(old))

    conservation = before == after
    proposals.sort(key=lambda r: (int(r["competition_id"]), int(r["slot"])))
    write_csv(a.output_dir / "candidate-membership-plan.csv", FIELDS, proposals)
    write_csv(a.report_dir / "coverage-matrix.csv", list(coverage[0]), coverage)
    write_json(a.report_dir / "review-queue.json", reviews)
    ready = coverage_pass and conservation and not reviews and not format_changes and bool(proposals)
    report = {"status": "READY_TO_FREEZE" if ready else "INCOMPLETE_REVIEW_REQUIRED",
              "snapshot_date": snapshot, "coverage_pass": coverage_pass,
              "source_failures": failures, "format_changes": format_changes,
              "candidate_rows": len(proposals), "changed_competitions": len({r["competition_id"] for r in proposals}),
              "global_team_conservation": conservation, "review_rows": len(reviews),
              "freeze_ready": ready, "frozen": False,
              "membership_sha256": sha256(a.membership), "coverage_sha256": sha256(a.coverage),
              "candidate_sha256": sha256(a.output_dir / "candidate-membership-plan.csv"),
              "limitations": "Membership slots only. Size/format changes require the separate validated native format plan; calendars and gameplay are separate gates."}
    if a.freeze:
        if not ready:
            write_json(a.report_dir / "integration.json", report)
            raise ValueError("Incomplete membership evidence; refusing to freeze")
        frozen = a.output_dir / "native10-membership-plan.csv"
        if frozen.exists():
            raise ValueError("Frozen membership plan already exists")
        write_csv(frozen, FIELDS, proposals)
        report.update(status="FROZEN_NATIVE10_MEMBERSHIP_PLAN_NOT_WRITTEN", frozen=True,
                      frozen_plan_sha256=sha256(frozen))
        write_json(frozen.with_suffix(".manifest.json"), report)
    write_json(a.report_dir / "integration.json", report)
    print(json.dumps({k: report[k] for k in ("status", "candidate_rows", "review_rows",
                                             "coverage_pass", "global_team_conservation", "freeze_ready")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
