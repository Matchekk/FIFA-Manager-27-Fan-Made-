"""Read only: compare two loan records and select a tiny start-date control set."""
from pathlib import Path
import re, json, csv
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'data/generated/release-candidate/transfer-increment-20260909-07/database/data'
RUN=ROOT/'runtime/game-test-20260912-07/database/data'
OUT=ROOT/'reports/local/native08-20260912-evidence/loan-control-inspection.json'
def block(data, identity):
    pos=data.index(identity)
    return data[pos:data.index(b'%INDEXEND%PLAYER',pos)]
traces=[]
for cid,identity in [(21,b'Mikey|Moore'),(38,b'Samuel|Amissah')]:
    a=(BASE/f'CountryData{cid}.sav').read_bytes()
    b=(RUN/f'CountryData{cid}.sav').read_bytes()
    differences=[i+1 for i,(x,y) in enumerate(zip(a.splitlines(),b.splitlines())) if x!=y]
    traces.append(dict(player=identity.decode(), player_block_identical=block(a,identity)==block(b,identity),
                       country_bytes_identical=a==b, differing_line_count=len(differences), differing_lines= differences[:10]))
with (ROOT/'data/intermediate/transfer-increment-20260909-07/clubs.csv').open(encoding='utf-8-sig',newline='') as f:
    clubs=list(csv.DictReader(f))
refs={c['reference_id']:c['club'] for c in clubs}
uids={c['club_id']:c['club'] for c in clubs}
with (ROOT/'data/generated/native-reread-increment-20260909-07/native_players.csv').open(encoding='utf-8-sig',newline='') as f:
    players={p['fm_id']:p for p in csv.DictReader(f)}
controls=[]
for cid in [21,14,38,45,27,18]:
    data=(BASE/f'CountryData{cid}.sav').read_text(encoding='utf-8-sig')
    for match in re.finditer(r'(?m)^(\d+)\n%INDEX%PLAYER\n(.*?)%INDEXEND%PLAYER',data,re.S):
        conditions=re.findall(r'(?m)^4,2461223,2461587,(\d+),(-?\d+),0$',match[2])
        if not conditions: continue
        p=players.get(match[1])
        if p:
            runtime_text=(RUN/f'CountryData{cid}.sav').read_text(encoding='utf-8-sig')
            runtime_block=re.search(r'(?m)^'+re.escape(match[1])+r'\n%INDEX%PLAYER\n(.*?)%INDEXEND%PLAYER',runtime_text,re.S)
            controls.append(dict(name=p['name'],fm_id=p['fm_id'],dob=p['dob'],borrower=uids.get(p['club_id'],p['club_id']),owner=refs.get(conditions[0][0],conditions[0][0]),buy_option=conditions[0][1],start='2026-07-01',end='2027-06-30',country=cid,runtime_player_identical=bool(runtime_block and runtime_block[1]==match[2])))
        if len(controls)>=5:break
    if len(controls)>=5:break
result=dict(target_traces=traces,control_candidates=controls,limit='Native text evidence only; no exported Master or career ownership parsing')
OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,ensure_ascii=False))
