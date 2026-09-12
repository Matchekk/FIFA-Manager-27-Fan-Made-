import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fm27.common import write_csv, write_json
from fm27.dfb import parse_page
from fm27.public_cache import DfbCache

root = Path(__file__).resolve().parents[1]
cache = DfbCache(root / "data/raw/dfb")
seeds = {
    "GER1": "https://datencenter.dfb.de/competitions/bundesliga/seasons/2026-2027/teams/borussia-dortmund",
    "GER2": "https://datencenter.dfb.de/competitions/2-bundesliga/seasons/2026-2027/teams/hannover-96",
    "GER3": "https://datencenter.dfb.de/teams/fortuna-duesseldorf",
}
all_records, all_sources, failures, coverage = [], [], [], {}
for league, seed in seeds.items():
    try:
        html, provenance = cache.fetch(seed, reuse_today=True)
        records, peers = parse_page(html, league, dt.date.today())
        all_sources.append(provenance)
        expected = 20 if league == "GER3" else 18
        if len(peers) != expected:
            raise ValueError(f"Expected {expected} same-season teams, found {len(peers)}")
        for index, url in enumerate(peers):
            try:
                page, provenance = cache.fetch(url, reuse_today=True)
                records, _ = parse_page(page, league, dt.date.today())
            except Exception as exc:
                failures.append({"league": league, "source": url, "error": str(exc)})
                print(json.dumps(failures[-1]), flush=True)
                continue
            for record in records:
                record.update(source=url, source_sha256=provenance["sha256"])
            all_records.extend(records)
            all_sources.append(provenance)
            print(json.dumps({"league": league, "team": index + 1, "of": expected, "players": len(records)}), flush=True)
        coverage[league] = len({r["club"] for r in all_records if r["league"] == league})
    except Exception as exc:
        failures.append({"league": league, "error": str(exc)})
        print(json.dumps(failures[-1]), flush=True)
if all_records:
    write_csv(root / "data/intermediate/dfb-rosters.csv", list(all_records[0]), all_records)
write_json(root / "reports/local/DFB_FETCH.json", {"DATABASE_SNAPSHOT_DATE": dt.date.today().isoformat(),
           "coverage": coverage, "records": len(all_records), "failures": failures, "sources": all_sources,
           "status": "ROSTER_EVIDENCE_ONLY_NOT_TRANSFER_TYPES_OR_CONTRACTS"})
sys.exit(bool(failures))
