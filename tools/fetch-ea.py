"""Fetch only the 12 target EA leagues, with paging/identity/season validation."""
import datetime as dt
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fm27.common import write_csv, write_json
from fm27.ea import LEAGUES, page_props, league_page
from fm27.matching import normalize
from fm27.public_cache import DfbCache

root = Path(__file__).resolve().parents[1]
cache = DfbCache(root / "data/raw/ea", host="www.ea.com")
base = "https://www.ea.com/games/ea-sports-fc/ratings"
html, source = cache.fetch(base, reuse_today=True)
main = page_props(html)
groups = {str(t["id"]): t for t in main["ratingsFilters"]["teamGroups"]}
rows, sources, failures, coverage = [], [source], [], {}
snapshot = dt.datetime.now(dt.timezone.utc).date().isoformat()
for league, identity in LEAGUES.items():
    try:
        slug = normalize(groups[identity]["label"]).replace(" ", "-")
        if league == "FRA1":
            slug = "ligue-1-mc-donald-s"
        url = base + f"/leagues-ratings/{slug}/{identity}"
        league_rows, league_sources, seen = [], [], set()
        pages, page, total = 1, 1, None
        while page <= pages:
            address = url + f"?page={page}"
            html, source = cache.fetch(address, reuse_today=True)
            batch, count, group = league_page(page_props(html), league)
            if total is None:
                total, pages = count, math.ceil(count / 100)
            if count != total or not batch or len(batch) != min(100, total-(page-1)*100) or pages > 15:
                raise ValueError("Pagination total/size changed or invalid")
            for row in batch:
                if row["fifa_id"] in seen:
                    raise ValueError("EA repeated a page/player; abort incomplete league")
                seen.add(row["fifa_id"])
                row.update(source=address, source_sha256=source["sha256"], snapshot_date=snapshot)
            league_rows.extend(batch)
            league_sources.append(source)
            print(json.dumps({"league": league, "page": page, "pages": pages, "records": len(league_rows)}), flush=True)
            page += 1
        rows.extend(league_rows)
        sources.extend(league_sources)
        coverage[league] = {"teams": len(group["teams"]), "players": len(league_rows),
                            "real_league_complete": False if league == "CZE1" else None}
    except Exception as exc:
        failures.append({"league": league, "error": str(exc)})
        print(json.dumps(failures[-1]), flush=True)
if rows:
    write_csv(root / "data/intermediate/ea-fc27.csv", list(rows[0]), rows)
write_json(root / "reports/local/EA_FETCH.json", {"DATABASE_SNAPSHOT_DATE": snapshot,
    "coverage": coverage, "records": len(rows), "sources": sources, "failures": failures,
    "phase": "PRE_ANNOUNCED_SEPTEMBER_10_UPDATE", "production_writes": 0,
    "limitations": "EA launch cards, not transfer/loan registrations. Czech league has only three licensed teams. Affiliation may lag real transfers. No portrait assets fetched."})
sys.exit(bool(failures))
