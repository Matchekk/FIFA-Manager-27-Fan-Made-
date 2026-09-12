"""Capture current detailed squads for covered clubs, without fetching portraits."""
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from fm27.common import write_csv,write_json
from fm27.matching import normalize
from fm27.public_cache import DfbCache
from fm27.transfermarkt import parse_squad

root=Path(__file__).resolve().parents[1]
metadata=json.loads((root/"reports/local/TRANSFER_FETCH.json").read_text(encoding="utf-8"))
cache=DfbCache(root/"data/raw/transfermarkt",host="www.transfermarkt.de")
snapshot=dt.datetime.now(dt.timezone.utc).date().isoformat()
rows,sources,failures,coverage=[],[],[],{}
order=["GER1","GER2","GER3","ENG1","ITA1","ESP1","FRA1","POR1","NED1","BEL1","TUR1","CZE1"]
def checkpoint():
    if rows:write_csv(root/"data/intermediate/tm-squads.csv",list(rows[0]),rows)
    write_json(root/"reports/local/TM_SQUADS_FETCH.json",{"DATABASE_SNAPSHOT_DATE":snapshot,"coverage":coverage,
        "sources":sources,"failures":failures,"records":len(rows),"production_writes":0})
for league in order:
    clubs=metadata["coverage"].get(league,{}).get("clubs",{})
    coverage[league]={"expected":len(clubs),"fetched":0}
    for club_id,name in clubs.items():
        slug=normalize(name).replace(" ","-")
        url=f"https://www.transfermarkt.de/{slug}/kader/verein/{club_id}/saison_id/2026/plus/1"
        try:
            html,source=cache.fetch(url,reuse_today=True)
            batch=parse_squad(html,league,club_id)
            for row in batch:row.update(source=url,source_sha256=source["sha256"],snapshot_date=snapshot)
            rows.extend(batch);sources.append(source);coverage[league]["fetched"]+=1
            print(json.dumps({"league":league,"club_id":club_id,"players":len(batch),"progress":coverage[league]}),flush=True)
        except Exception as exc:
            failures.append({"league":league,"club_id":club_id,"source":url,"error":str(exc)})
            print(json.dumps(failures[-1]),flush=True)
        checkpoint()
checkpoint()
sys.exit(bool(failures))
