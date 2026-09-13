"""Bounded second profile attempt for south-west identity holds.

Uses only profile URLs already observed in the scoped south-west roster
capture.  It updates worker artifacts and the public source cache; it never
changes native, override, or production integration data.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/current/workers/south-west"
sys.path.insert(0, str(ROOT / "src"))
from fm27.public_cache import DfbCache  # noqa: E402
from fm27.transfermarkt import parse_profile  # noqa: E402


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def main() -> None:
    resolutions = read_csv(OUT / "identity-resolutions.csv")
    wanted = {
        row["player_tm_id"]
        for row in resolutions
        if row["status"] == "REVIEW_REQUIRED" and "ABSENT" in row["attempts"]
    }
    rosters = {row["player_tm_id"]: row for row in read_csv(OUT / "rosters.csv")}
    missing_url = sorted(pid for pid in wanted if not rosters.get(pid, {}).get("profile_url"))
    if missing_url:
        raise ValueError(f"Observed profile URL missing for {missing_url}")

    profiles = read_csv(OUT / "profiles.csv")
    existing = {row["player_tm_id"] for row in profiles}
    captures: list[dict[str, str]] = []
    failures: list[dict[str, str]] = []
    cache = DfbCache(ROOT / "data/raw/transfermarkt", host="www.transfermarkt.de")
    for pid in sorted(wanted, key=int):
        if pid in existing:
            continue
        source = rosters[pid]
        try:
            html, evidence = cache.fetch(source["profile_url"], reuse_today=True)
            profile = parse_profile(html, pid)
            profile.update(
                source=source["profile_url"], source_sha256=evidence["sha256"],
                retrieved_at=evidence["retrieved_at"], snapshot_date="2026-09-12",
                imported_at=dt.datetime.now(dt.timezone.utc).isoformat(),
            )
            captures.append(profile)
        except Exception as exc:  # retain explicit second-attempt failure
            failures.append({"player_tm_id": pid, "source": source["profile_url"], "error": str(exc)})
        done = len(captures) + len(failures)
        if done % 20 == 0:
            print(json.dumps({"attempted": done, "captured": len(captures), "failures": len(failures)}), flush=True)

    if captures:
        all_profiles = profiles + captures
        # Keep one current row per Transfermarkt identity, retaining the
        # original order for stable diffs and appending second-attempt rows.
        by_id: dict[str, dict[str, str]] = {}
        for row in all_profiles:
            by_id[row["player_tm_id"]] = row
        all_profiles = list(by_id.values())
        fields = list(all_profiles[0])
        with (OUT / "profiles.csv").open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fields)
            writer.writeheader()
            writer.writerows(all_profiles)

    meta = {
        "snapshot_date": "2026-09-12", "requested": len(wanted),
        "attempted": len(captures) + len(failures), "captured": len(captures),
        "failures": failures, "source": "south-west/rosters.csv observed profile_url",
        "cache_reuse_today": True, "canonical_mutation": False,
    }
    (OUT / "profile-second-attempt.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
