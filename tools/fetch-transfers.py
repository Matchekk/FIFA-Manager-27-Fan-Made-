import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fm27.common import write_csv, write_json
from fm27.public_cache import DfbCache
from fm27.transfermarkt import LEAGUES, parse_page

root = Path(__file__).resolve().parents[1]
cache = DfbCache(root / "data/raw/transfermarkt", host="www.transfermarkt.de")
rows, sources, failures, coverage = [], [], [], {}
snapshot = dt.datetime.now(dt.timezone.utc).date().isoformat()
for league, (slug, code) in LEAGUES.items():
    url = f"https://www.transfermarkt.de/{slug}/transfers/wettbewerb/{code}/saison_id/2026"
    try:
        html, source = cache.fetch(url, reuse_today=True)
        batch, clubs = parse_page(html, league)
        for row in batch:
            row.update(source=url,source_sha256=source["sha256"],snapshot_date=snapshot)
        rows.extend(batch)
        sources.append(source)
        coverage[league] = {"clubs":clubs,"records":len(batch)}
        print(json.dumps({"league":league,"clubs":len(clubs),"records":len(batch)}),flush=True)
    except Exception as exc:
        failures.append({"league":league,"source":url,"error":str(exc)})
        print(json.dumps(failures[-1]),flush=True)
if rows:
    write_csv(root / "data/intermediate/transfer-events.csv",list(rows[0]),rows)
write_json(root / "reports/local/TRANSFER_FETCH.json",{"DATABASE_SNAPSHOT_DATE":snapshot,"coverage":coverage,
    "sources":sources,"failures":failures,"records":len(rows),"production_writes":0,
    "limitations":"Season event history includes intermediate moves and future loan returns. Requires identity and as-of-date reconciliation before mutation."})
sys.exit(bool(failures))
