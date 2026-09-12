"""Combine validated history with provenance-bound current-loan start projection."""
from pathlib import Path
from datetime import date,datetime
from collections import defaultdict
import csv,json,hashlib,re,shutil,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from fm27.runtime_loan_dates import effective_current_loan_start
HISTORY=ROOT/'data/generated/history-20260912-03'
OUT=ROOT/'data/generated/release-candidate/native08-integrated-20260912-01'
NATIVE=ROOT/'data/generated/native-reread-increment-20260909-07'
BASE=ROOT/'data/generated/native-baseline-semantic-20260908-01'
START=date(2026,7,1)
def rows(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def iso(s):return datetime.strptime(s,'%d.%m.%Y').date().isoformat()
def main():
    assert not OUT.exists(),'Exclusive candidate required'
    assert json.loads((HISTORY/'PACKAGE.json').read_text())['status'].startswith('PASS_')
    players={p['fm_id']:p for p in rows(NATIVE/'native_players.csv')}
    old_players={p['fm_id']:p for p in rows(BASE/'native_players.csv')}
    names=defaultdict(list);fifa=defaultdict(list)
    for p in players.values():
        names[p['name'],iso(p['dob'])].append(p)
        if p['fifa_id']!='0':fifa[p['fifa_id'],iso(p['dob'])].append(p)
    p15=ROOT/'data/generated/transfer-loan-plan-20260908-15.csv'
    p07=ROOT/'data/generated/transfer-increment-plan-20260909-07.csv'
    adopted={}
    for r in rows(p15):
        if r['loan_owner_club_id']=='0':continue
        old=old_players[r['fm_id']]
        assert iso(old['dob'])==r['dob']
        matches=names[old['name'],r['dob']]
        if len(matches)!=1 and r['fifa_id']!='0':matches=fifa[r['fifa_id'],r['dob']]
        assert len(matches)==1,('Ambiguous loan identity',old['name'],r['dob'])
        adopted[matches[0]['fm_id']]=(r,p15)
    for r in rows(p07):
        p=players[r['fm_id']];assert iso(p['dob'])==r['dob']
        if r['loan_owner_club_id']!='0':adopted[p['fm_id']]=(r,p07)
        else:adopted.pop(p['fm_id'],None)
    assert len(adopted)==794,('Adopted loan count differs from Native07',len(adopted))
    clubs={c['club_id']:c for c in rows(ROOT/'data/intermediate/transfer-increment-20260909-07/clubs.csv')}
    grouped=defaultdict(list)
    for pid,(r,plan) in adopted.items():
        p=players[pid];assert p['club_id']==r['new_club_id'],('Borrower mismatch',p['name'])
        grouped[int(clubs[p['club_id']]['country_id'])].append((p,r,plan))
    changes=[];preserved=[];buffers={}
    for cid,entries in grouped.items():
        path=HISTORY/f'database/data/CountryData{cid}.sav';raw=path.read_bytes()
        edits=[]
        for p,r,plan in entries:
            match=re.search(rb'(?m)^'+p['fm_id'].encode()+rb'\r?\n%INDEX%PLAYER\r?\n(.*?)%INDEXEND%PLAYER',raw,re.S)
            assert match,('Missing player block',p['name'])
            block=match[1];header=block.split(b'%INDEX%HIST',1)[0]
            condition=list(re.finditer(rb'(?m)^4,(\d{7}),(\d{7}),(\d+),(-?\d+),0\r?$',header))
            assert len(condition)==1,('Missing/ambiguous current loan',p['name'])
            c=condition[0];start=date.fromordinal(int(c[1])-1721425);end=date.fromordinal(int(c[2])-1721425)
            assert start.isoformat()==r['joined'] and end.isoformat()==r['loan_end'],('Loan dates differ from frozen plan',p['name'])
            assert c[3].decode()==clubs[r['loan_owner_club_id']]['reference_id'],('Loan owner mismatch',p['name'])
            snapshot=date.fromisoformat(r['snapshot_date'])
            effective=effective_current_loan_start(start,end,START,snapshot)
            evidence=dict(fm_id=p['fm_id'],name=p['name'],dob=r['dob'],borrower=r['new_club_id'],
                          owner=r['loan_owner_club_id'],source_start=str(start),effective_start=str(effective),
                          end=str(end),frozen_plan=str(plan),frozen_plan_sha256=sha(plan),source_url=r['source'],
                          source_sha256=r['source_sha256'],country_id=cid)
            if effective==start:preserved.append(evidence);continue
            offset=match.start(1)+c.start(1);replacement=str(effective.toordinal()+1721425).encode()
            assert len(replacement)==len(c[1])
            edits.append((offset,c[1],replacement));evidence['byte_offset']=offset;changes.append(evidence)
        output=raw
        for offset,before,after in sorted(edits,reverse=True):
            assert output[offset:offset+len(before)]==before
            output=output[:offset]+after+output[offset+len(before):]
        if edits:buffers[path.name]=(raw,output)
    assert {'288892','23675'} <= {r['fm_id'] for r in changes},'Experiment players not corrected'
    OUT.mkdir(parents=True)
    shutil.copytree(HISTORY/'database',OUT/'database')
    shutil.copytree(HISTORY/'overlay',OUT/'overlay')
    files=[]
    for name,(before,after) in buffers.items():
        target=OUT/'database/data'/name;assert target.read_bytes()==before;target.write_bytes(after)
        assert len(before)==len(after)
        files.append(dict(file=name,before_sha256=hashlib.sha256(before).hexdigest(),after_sha256=sha(target)))
    assert not (OUT/'database/Master.dat').exists()
    result=dict(status='BUILT_INDEPENDENT_VALIDATION_PENDING',candidate=str(OUT),history_base=str(HISTORY),
                policy='Project adopted current loans only: min(source start, career start) when source start <= snapshot. Future-condition types untouched.',
                career_start=str(START),adopted_loans=len(adopted),changed_loans=len(changes),preserved_loans=len(preserved),
                changes=changes,preserved=preserved,country_files=files,
                frozen_sources_modified=False,original_install_modified=False,history_integrated=True,
                diagnostic_evidence='Native08 same-player Moore/Amissah experiment; both destinations operator-confirmed',
                generalization_limit='The rule is tested at date boundaries and with two career records, not individually for every affected loan.')
    (OUT/'INTEGRATION.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ['status','adopted_loans','changed_loans','preserved_loans','history_integrated']}))
if __name__=='__main__':main()
