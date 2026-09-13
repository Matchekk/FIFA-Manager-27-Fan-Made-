"""Build an immutable ENG1/GER1/GER2/GER3 current-squad intake from public roster pages.

This worker owns data/current/workers/eng-ger only. It never changes production plans.
"""
import csv
import datetime as dt
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fm27.common import read_csv, write_csv, write_json, sha256
from fm27.matching import normalize
from fm27.public_cache import DfbCache
from fm27.transfermarkt import parse_squad

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/current/workers/eng-ger"
LEAGUES = ("ENG1", "GER1", "GER2", "GER3")


def main():
    metadata = json.loads((ROOT / "reports/local/TRANSFER_FETCH.json").read_text(encoding="utf-8"))
    aliases = json.loads((ROOT / "config/tm-club-aliases.json").read_text(encoding="utf-8"))
    diff = read_csv(ROOT / "reports/local/current/TRANSFER_DIFF.csv")
    events = read_csv(ROOT / "data/intermediate/transfer-events.csv")
    loan_plan_path = ROOT / "data/intermediate/loan-plan.csv"
    loan_plan = read_csv(loan_plan_path) if loan_plan_path.exists() else []
    loan_by_fm = {(r.get("fm_id", ""), r.get("new_club_id", "")): r for r in loan_plan}
    incoming_events = defaultdict(list)
    for e in events:
        if e.get("direction") == "Zugang":
            incoming_events[(e.get("player_tm_id", ""), e.get("new_club_tm_id", ""))].append(e)
    # This is the richer, pre-native08 identity baseline requested by integration. The
    # current candidate's FM ids are from an earlier bound export, so remap by numeric
    # FIFA identity first and then DOB+normalized name before emitting its FM id.
    baseline_rows = read_csv(ROOT / "data/intermediate/transfer-increment-20260909-07/players.csv")
    baseline = {r["fm_id"]: r for r in baseline_rows if r.get("fm_id")}
    baseline_fifa = {r["fifa_id"]: r for r in baseline_rows if r.get("fifa_id") and r["fifa_id"] != "0"}
    baseline_tm = {r["transfermarkt_id"]: r for r in baseline_rows if r.get("transfermarkt_id") and r["transfermarkt_id"] != "0"}
    baseline_dobname = {(r["dob"], normalize(r["name"])): r for r in baseline_rows if r.get("dob") and r.get("name")}
    # Use a private cache so the worker's evidence cannot be mistaken for production input.
    cache = DfbCache(OUT / "source-cache", host="www.transfermarkt.de")
    snapshot = dt.datetime.now(dt.timezone.utc).date().isoformat()
    observed, failures, coverage = [], [], {}
    for league in LEAGUES:
        clubs = metadata["coverage"][league]["clubs"]
        coverage[league] = {"expected_clubs": len(clubs), "observed_clubs": 0, "players": 0}
        for club_id, name in clubs.items():
            slug = normalize(name).replace(" ", "-")
            url = f"https://www.transfermarkt.de/{slug}/kader/verein/{club_id}/saison_id/2026/plus/1"
            try:
                html, source = cache.fetch(url, reuse_today=True)
                batch = parse_squad(html, league, club_id)
                target = aliases.get(club_id, {})
                for row in batch:
                    row.update(source=url, source_sha256=source["sha256"], snapshot_date=snapshot,
                               season="2026/27", club_name=target.get("fm_name", name),
                               native_club_id=target.get("club_id", ""),
                               external_club_id=club_id,
                               loan_owner_external_club_id="", loan_end="")
                observed.extend(batch)
                coverage[league]["observed_clubs"] += 1
                coverage[league]["players"] += len(batch)
            except Exception as exc:
                failures.append({"league": league, "external_club_id": club_id, "club_name": name,
                                 "source_url": url, "error": str(exc)})
    # Attach existing numeric identity where the current candidate resolves it. Any unresolved
    # or conflicting row remains review-required; no identity is invented.
    by_key = {(r["league"], r["club_tm_id"], r["player_tm_id"]): r for r in diff}
    rows = []
    delta_rows = []
    review_details = []
    loan_preservation = []
    review_by_club = Counter()
    confirmed_by_club = Counter()
    for r in observed:
        d = by_key.get((r["league"], r["club_tm_id"], r["player_tm_id"]), {})
        fm_id = d.get("fm_id", "")
        native = baseline.get(fm_id, {})
        if d.get("fifa_id") and d.get("fifa_id") != "0":
            native = baseline_fifa.get(d["fifa_id"], native)
        if not native and d.get("dob"):
            native = baseline_dobname.get((d["dob"], normalize(d.get("player", ""))), {})
        fm_id = native.get("fm_id", "")
        native_fifa = native.get("fifa_id", "")
        status = "CONFIRMED" if d.get("status") == "CONFIRMED" and fm_id else "REVIEW_REQUIRED"
        evs = incoming_events.get((r["player_tm_id"], r["club_tm_id"]), [])
        loan = d.get("transfer_type") == "LOAN" or d.get("classification") == "LOAN_IN"
        loan_owner = evs[0].get("old_club_tm_id", "") if loan and evs else ""
        loan_end = r["contract_until"] if loan else ""
        old_native_club = d.get("old_club_id", "")
        new_native_club = r["native_club_id"]
        if status == "CONFIRMED":
            confirmed_by_club[(r["league"], r["club_name"])] += 1
        else:
            review_by_club[(r["league"], r["club_name"])] += 1
        if loan:
            lp = loan_by_fm.get((d.get("fm_id", ""), r["native_club_id"]), {})
            loan_preservation.append({"league": r["league"], "club_name": r["club_name"],
                                      "external_club_id": r["external_club_id"], "player_name": r["player"],
                                      "external_player_id": r["player_tm_id"], "fm_id": fm_id,
                                      "fifa_id": native_fifa or d.get("fifa_id", ""),
                                      "native_club_id": r["native_club_id"],
                                      "loan_owner_external_club_id": loan_owner,
                                      "loan_owner_native_club_id": lp.get("loan_owner_club_id", d.get("old_club_id", "")),
                                      "source_joined": r["joined"],
                                      "projected_begin": "2026-07-01",
                                      "loan_end": lp.get("loan_end", loan_end),
                                      "preservation_status": "PRESERVE_NATIVE08_PROJECTED_BEGIN",
                                      "source_url": r["source"], "source_sha256": r["source_sha256"]})
        # Keep unresolved identity blank, while preserving source-side external IDs and dates.
        out_row = {
            "league": r["league"], "season": "2026/27", "snapshot_date": snapshot,
            "club_name": r["club_name"], "external_club_id": r["external_club_id"],
            "player_name": r["player"], "external_player_id": r["player_tm_id"],
            "dob": r["dob"], "shirt_number": r["shirt_number"],
            "team_type": "RESERVE" if aliases.get(r["club_tm_id"], {}).get("team_type") == "RESERVE" else "FIRST",
            "joined": r["joined"], "contract_until": r["contract_until"],
            "loan_owner_external_club_id": loan_owner, "loan_end": loan_end,
            "status": status, "source_url": r["source"], "source_sha256": r["source_sha256"],
            "fm_id": fm_id, "fifa_id": native_fifa or d.get("fifa_id", ""),
            "native_club_id": r["native_club_id"],
        }
        rows.append(out_row)
        if status != "CONFIRMED":
            review_details.append({"league": r["league"], "club_name": r["club_name"],
                                   "external_club_id": r["external_club_id"], "player_name": r["player"],
                                   "external_player_id": r["player_tm_id"], "dob": r["dob"],
                                   "status": "REVIEW_REQUIRED", "review_reason": d.get("reason", "Identity or chronology review"),
                                   "classification": d.get("classification", "MISSING_FROM_FM"),
                                   "transfer_type": d.get("transfer_type", "UNVERIFIED"),
                                   "old_club_id": old_native_club, "new_club_id": new_native_club,
                                   "fm_id": fm_id, "fifa_id": native_fifa or d.get("fifa_id", ""),
                                   "source_url": r["source"], "source_sha256": r["source_sha256"]})
        if status == "CONFIRMED" and old_native_club and new_native_club and old_native_club != new_native_club:
            delta_rows.append({**out_row, "old_club_id": old_native_club, "new_club_id": new_native_club,
                               "transfer_type": d.get("transfer_type", "UNVERIFIED"),
                               "database_action": "STAGE_CURRENT_SQUAD"})
    fields = ["league", "season", "snapshot_date", "club_name", "external_club_id",
              "player_name", "external_player_id", "dob", "shirt_number", "team_type",
              "joined", "contract_until", "loan_owner_external_club_id", "loan_end", "status",
              "source_url", "source_sha256", "fm_id", "fifa_id", "native_club_id"]
    OUT.mkdir(parents=True, exist_ok=True)
    write_csv(OUT / "squad_observations.csv", fields, rows)
    confirmed = [r for r in rows if r["status"] == "CONFIRMED"]
    review = [r for r in rows if r["status"] != "CONFIRMED"]
    write_csv(OUT / "confirmed_squad_deltas.csv", fields, confirmed)
    delta_fields = fields + ["old_club_id", "new_club_id", "transfer_type", "database_action"]
    write_csv(OUT / "confirmed_transfer_deltas.csv", delta_fields, delta_rows)
    write_csv(OUT / "review_queue.csv", fields, review)
    review_detail_fields = ["league", "club_name", "external_club_id", "player_name", "external_player_id", "dob",
                            "status", "review_reason", "classification", "transfer_type", "old_club_id", "new_club_id",
                            "fm_id", "fifa_id", "source_url", "source_sha256"]
    write_csv(OUT / "review_queue_detail.csv", review_detail_fields, review_details)
    loan_fields = ["league", "club_name", "external_club_id", "player_name", "external_player_id", "fm_id", "fifa_id",
                   "native_club_id", "loan_owner_external_club_id", "loan_owner_native_club_id", "source_joined",
                   "projected_begin", "loan_end", "preservation_status", "source_url", "source_sha256"]
    write_csv(OUT / "loan_preservation.csv", loan_fields, loan_preservation)
    source_meta = []
    for m in sorted((OUT / "source-cache").glob("*.json")):
        try:
            x = json.loads(m.read_text(encoding="utf-8"))
            if x.get("url"):
                source_meta.append({"url": x["url"], "retrieved_at": x.get("retrieved_at", ""), "sha256": x.get("sha256", "")})
        except Exception:
            pass
    # Keep one source record per URL; this is the freshness/evidence manifest consumed by integration.
    source_meta = list({x["url"]: x for x in source_meta}.values())
    write_json(OUT / "source_manifest.json", {"snapshot_date": snapshot, "source_count": len(source_meta), "sources": source_meta,
                                               "evidence_root": str((ROOT / "data/raw/transfermarkt").resolve())})
    # Adapter for the existing reconcile-current.py input contract.
    tm_fields = ["league", "club", "club_tm_id", "player", "player_tm_id", "dob", "position",
                 "shirt_number", "joined", "contract_until", "change_notes", "profile_url",
                 "source_status", "database_action", "source", "source_sha256", "snapshot_date"]
    tm_rows = []
    for r in observed:
        d = by_key.get((r["league"], r["club_tm_id"], r["player_tm_id"]), {})
        tm_rows.append({"league": r["league"], "club": r["club_name"], "club_tm_id": r["external_club_id"],
                        "player": r["player"], "player_tm_id": r["player_tm_id"], "dob": r["dob"],
                        "position": r["position"], "shirt_number": r["shirt_number"], "joined": r["joined"],
                        "contract_until": r["contract_until"], "change_notes": r["change_notes"],
                        "profile_url": r["profile_url"], "source_status": r["source_status"],
                        "database_action": "STAGE_CURRENT_SQUAD" if d.get("status") == "CONFIRMED" else "REVIEW_REQUIRED",
                        "source": r["source"], "source_sha256": r["source_sha256"], "snapshot_date": snapshot})
    write_csv(OUT / "tm-squads.csv", tm_fields, tm_rows)
    write_json(OUT / "coverage.json", {
        "schema": "native10-squad-intake-v1", "season": "2026/27", "snapshot_date": snapshot,
        "expected_clubs_by_league": {l: coverage[l]["expected_clubs"] for l in LEAGUES},
        "observed_clubs_by_league": {l: coverage[l]["observed_clubs"] for l in LEAGUES},
        "records_by_league": {l: coverage[l]["players"] for l in LEAGUES},
        "active_loan_observations": len(loan_preservation),
        "native08_base": "data/generated/native08-integrated-20260912-01-reread",
        "native08_loan_policy": "Preserve corrected active-loan owner/end/rating/future-condition data; projected begin 2026-07-01 is carried separately in loan_preservation.csv.",
        "confirmed_by_league": {l: sum(1 for r in confirmed if r["league"] == l) for l in LEAGUES},
        "review_required_by_league": {l: sum(1 for r in review if r["league"] == l) for l in LEAGUES},
        "confirmed_transfer_deltas_by_league": {l: sum(1 for r in delta_rows if r["league"] == l) for l in LEAGUES},
        "confirmed_by_club": {f"{l}:{c}": n for (l, c), n in sorted(confirmed_by_club.items())},
        "review_required_by_club": {f"{l}:{c}": n for (l, c), n in sorted(review_by_club.items())},
        "review_queue_by_club": {f"{l}:{c}": [
            {k: r[k] for k in ("external_player_id", "player_name", "dob", "status", "review_reason", "classification", "transfer_type", "fm_id", "fifa_id")}
            for r in review_details if r["league"] == l and r["club_name"] == c
        ] for l, c in sorted(review_by_club)},
        "source_failures": failures,
        "known_gaps": ["Transfermarkt pages are roster evidence; status review remains required for identity, loan and contract conflicts.",
                       "Source snapshot is generated on this run; compare against prior candidate before integration.",
                       "No departures are inferred from absence."],
        "source_policy": "Transfermarkt 2026/27 club roster pages, fetched with immutable SHA-256 evidence.",
        "production_writes": 0,
    })
    print(json.dumps({"snapshot_date": snapshot, "rows": len(rows), "confirmed": sum(r["status"] == "CONFIRMED" for r in rows),
                      "review_required": sum(r["status"] != "CONFIRMED" for r in rows), "coverage": coverage,
                      "failures": failures}, ensure_ascii=False))


if __name__ == "__main__":
    main()
