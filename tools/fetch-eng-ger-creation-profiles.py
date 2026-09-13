"""Capture current profiles for the bounded ENG/GER creation queue."""
from __future__ import annotations

import csv
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/current/workers/eng-ger"
sys.path.insert(0, str(ROOT / "src"))
from fm27.public_cache import DfbCache  # noqa: E402
from fm27.transfermarkt import parse_profile  # noqa: E402


def read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def main() -> None:
    leagues = {"ENG1", "GER1", "GER2", "GER3"}
    queue = [r for r in read(ROOT / "reports/current/integration/review-queue.csv") if r["league"] in leagues and r["queue"] == "PLAYER_CREATION"]
    source = {r["player_tm_id"]: r for r in read(OUT / "tm-squads.csv")}
    profiles, failures = [], []
    cache = DfbCache(ROOT / "data/raw/transfermarkt", host="www.transfermarkt.de")
    for row in sorted(queue, key=lambda r: int(r["player_tm_id"])):
        pid = row["player_tm_id"]
        roster = source.get(pid)
        url = (roster or {}).get("profile_url", "")
        if not url:
            failures.append({"player_tm_id": pid, "error": "No observed scoped profile URL"})
            continue
        try:
            html, evidence = cache.fetch(url, reuse_today=True)
            profile = parse_profile(html, pid)
            profile.update(source=url, source_sha256=evidence["sha256"], retrieved_at=evidence["retrieved_at"], snapshot_date="2026-09-12", imported_at=dt.datetime.now(dt.timezone.utc).isoformat())
            profiles.append(profile)
        except Exception as exc:
            failures.append({"player_tm_id": pid, "source": url, "error": str(exc)})
    if profiles:
        fields = list(profiles[0])
        with (OUT / "profiles.csv").open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fields); writer.writeheader(); writer.writerows(profiles)
    meta = {"snapshot_date": "2026-09-12", "requested": len(queue), "captured": len(profiles), "failures": failures, "canonical_mutation": False}
    (OUT / "profile-capture.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False))


if __name__ == "__main__":
    main()
