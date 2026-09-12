"""Capture current profiles for concrete changed/missing south-west roster records."""
import csv, datetime, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from fm27.public_cache import DfbCache
from fm27.transfermarkt import parse_profile
OUT=ROOT/'data/current/workers/south-west'
def read(path):
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def main():
    fresh=read(OUT/'rosters.csv');leagues={r['league'] for r in fresh}
    old=read(ROOT/'data/intermediate/tm-squads.csv')
    events=read(ROOT/'data/current/evidence/transfer-events.csv')
    source={r['player_tm_id']:r for r in events+old+fresh if r['league'] in leagues}
    changes=read(OUT/'source-snapshot-delta.csv')
    wanted={r['player_tm_id'] for r in changes}
    wanted.update(r['player_tm_id'] for r in read(ROOT/'reports/local/current/UNMATCHED_PLAYERS.csv') if r['league'] in leagues)
    wanted.update({'807689','1069459'})
    profiles=[]; failures=[]; today=datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    cache=DfbCache(ROOT/'data/raw/transfermarkt',host='www.transfermarkt.de')
    def save():
        if profiles:
            with (OUT/'profiles.csv').open('w',encoding='utf-8',newline='') as f:
                w=csv.DictWriter(f,fieldnames=list(profiles[0]));w.writeheader();w.writerows(profiles)
        (OUT/'profile-capture.json').write_text(json.dumps(dict(snapshot_date=today,requested=len(wanted),captured=len(profiles),failures=failures),indent=2),encoding='utf-8')
    for pid in sorted(wanted,key=int):
        r=source.get(pid)
        if not r:
            failures.append(dict(player_tm_id=pid,error='No scoped source profile URL'));continue
        try:
            html,e=cache.fetch(r['profile_url'],reuse_today=True);p=parse_profile(html,pid)
            p.update(source=r['profile_url'],source_sha256=e['sha256'],retrieved_at=e['retrieved_at'],snapshot_date=today,imported_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
            profiles.append(p)
        except Exception as exc:failures.append(dict(player_tm_id=pid,source=r['profile_url'],error=str(exc)))
        save()
        if (len(profiles)+len(failures))%40==0:print(json.dumps(dict(captured=len(profiles),failures=len(failures),requested=len(wanted))),flush=True)
    save();print(json.dumps(dict(captured=len(profiles),failures=len(failures),requested=len(wanted))),flush=True)
if __name__=='__main__':main()
