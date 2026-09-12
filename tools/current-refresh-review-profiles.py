"""Fetch only actual current integration holds, with immutable source snapshots."""
import csv,datetime,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from fm27.public_cache import DfbCache
from fm27.transfermarkt import parse_profile
OUT=ROOT/'data/current/evidence'
def read(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def main():
    review=read(ROOT/'reports/current/integration/review-queue.csv')
    wanted={r['player_tm_id'] for r in review if r.get('blocking')=='YES' and r.get('player_tm_id')}
    sources={r['player_tm_id']:r for p in [OUT/'transfer-events.csv',ROOT/'data/current/workers/eng-ger/tm-squads.csv',ROOT/'data/current/workers/south-west/rosters.csv'] for r in read(p)}
    cache=DfbCache(ROOT/'data/raw/transfermarkt',host='www.transfermarkt.de')
    rows=[];failures=[];stamp=datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    def save():
        if rows:
            with (OUT/'review-profiles.csv').open('w',encoding='utf-8',newline='') as f:
                w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
        (OUT/'review-profile-capture.json').write_text(json.dumps(dict(snapshot_date=stamp,requested=len(wanted),captured=len(rows),failures=failures),indent=2),encoding='utf-8')
    for pid in sorted(wanted,key=int):
        source=sources.get(pid,{})
        url=source.get('profile_url','')
        if not url:
            failures.append(dict(player_tm_id=pid,error='No observed scoped profile URL'));continue
        try:
            html,e=cache.fetch(url,reuse_today=True);p=parse_profile(html,pid)
            p.update(source=url,source_sha256=e['sha256'],retrieved_at=e['retrieved_at'],snapshot_date=stamp,imported_at=datetime.datetime.now(datetime.timezone.utc).isoformat());rows.append(p)
        except Exception as exc:failures.append(dict(player_tm_id=pid,source=url,error=str(exc)))
        save()
        if (len(rows)+len(failures))%50==0:print(json.dumps(dict(captured=len(rows),failures=len(failures),requested=len(wanted))),flush=True)
    save();print(json.dumps(dict(captured=len(rows),failures=len(failures),requested=len(wanted))),flush=True)
if __name__=='__main__':main()
