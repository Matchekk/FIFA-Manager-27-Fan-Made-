"""Describe source snapshot changes; roster absence never authorizes departure."""
import csv, json
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/current/workers/south-west'
def read(path):
    with path.open(encoding='utf-8-sig', newline='') as f: return list(csv.DictReader(f))
def main():
    old=read(ROOT/'data/intermediate/tm-squads.csv'); new=read(OUT/'rosters.csv')
    leagues={r['league'] for r in new}
    key=lambda r:(r['club_tm_id'],r['player_tm_id'])
    before={key(r):r for r in old if r['league'] in leagues}; after={key(r):r for r in new}
    fields=['player','dob','position','shirt_number','joined','contract_until','change_notes']
    changes=[]
    for k in sorted(before.keys()|after.keys()):
        a,b=before.get(k,{}),after.get(k,{})
        altered=[f for f in fields if a.get(f)!=b.get(f)]
        if not altered: continue
        r=b or a
        changes.append(dict(league=r['league'],club=r['club'],club_tm_id=k[0],player=r['player'],player_tm_id=k[1],
            classification='NEW_SOURCE_ROW' if not a else 'ABSENT_FROM_NEW_SOURCE' if not b else 'SOURCE_FIELDS_CHANGED',
            fields=json.dumps(altered),before=json.dumps({f:a.get(f,'') for f in altered},ensure_ascii=False),
            after=json.dumps({f:b.get(f,'') for f in altered},ensure_ascii=False),source=r['source'],
            previous_source_sha256=a.get('source_sha256',''),current_source_sha256=b.get('source_sha256',''),
            confidence='REVIEW_REQUIRED',note='Source comparison only; absence is not departure evidence.'))
    with (OUT/'source-snapshot-delta.csv').open('w',encoding='utf-8',newline='') as f:
        header=list(changes[0]) if changes else ['league','club','club_tm_id','player','player_tm_id','classification']
        w=csv.DictWriter(f,fieldnames=header);w.writeheader();w.writerows(changes)
    result=dict(old_rows=len(before),current_rows=len(after),changed_rows=len(changes),
        categories=dict(Counter(r['classification'] for r in changes)),by_league=dict(Counter(r['league'] for r in changes)))
    (OUT/'source-snapshot-delta.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
if __name__=='__main__':main()
