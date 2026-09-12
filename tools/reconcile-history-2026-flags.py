"""Prepare scoped stale-marker removals. Does not mutate any database."""
from pathlib import Path
import csv, hashlib, json, re
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/generated/history-20260912-01'
BASE=ROOT/'data/generated/release-candidate/transfer-increment-20260909-07/database/data'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    draft_path=OUT/'HISTORY_DRAFT.json'
    draft=json.loads(draft_path.read_text(encoding='utf-8'))
    with (ROOT/'data/intermediate/transfer-increment-20260909-07/clubs.csv').open(encoding='utf-8-sig',newline='') as f:
        clubs={int(c['club_id']):c for c in csv.DictReader(f)}
    scope={c['key'] for c in draft['scope']}
    desired={(r['club_id'],r['target_field']):r for r in draft['rows']}
    cup_sources={r['country_id']:r['source'] for r in draft['rows'] if r['kind']=='cup_winner'}
    clears=[];holds=[];inspected=0
    for cid in sorted(cup_sources):
        path=BASE/f'CountryData{cid}.sav'
        lines=path.read_text(encoding='utf-8-sig').splitlines()
        digest=sha(path)
        starts=[i for i,s in enumerate(lines) if re.fullmatch(r'%INDEX%CLUB\d+',s)]
        for ix,start in enumerate(starts):
            end=starts[ix+1] if ix+1<len(starts) else len(lines)
            assert lines[start+1]=='%INDEX%VERSION' and lines[start+3]=='%INDEXEND%VERSION'
            uid=int(lines[start+4])
            hist=lines.index('%INDEX%HIST',start,end)
            assert len(lines[hist-1].split(','))==5
            flags=int(lines[hist-2]);inspected+=1
            club=clubs.get(uid)
            if not club:continue
            for field,mask in [('mFirstTeamLastSeasonInfo.mCup',80),('mFirstTeamLastSeasonInfo.mLeague',5)]:
                if not flags & mask or (uid,field) in desired:continue
                row=dict(country_id=cid,club_id=uid,club=club['club'],target_field=field,
                         source_file=str(path),source_sha256=digest,source_line=hist-1,
                         before_flags=flags,clear_mask=mask,after_flags=flags & ~mask,
                         proposed_value='None',rule='Clear obsolete first-team last-season marker only; preserve reserve/other bits')
                if mask==5 and club['league'] not in scope:
                    row['reason']='Outside covered league set; do not erase unreviewed lower-division history'
                    holds.append(row)
                else:
                    row['evidence']=cup_sources[cid] if mask==80 else 'Complete movement proposal for covered leagues in bound HISTORY_DRAFT.json; review source coverage before installation'
                    clears.append(row)
    result=dict(status='OFFLINE_RECONCILIATION_PREVIEW_NOT_INSTALLED',draft_sha256=sha(draft_path),
                inspected_clubs=inspected,clear_proposals=clears,out_of_scope_preserved=holds,
                limits=['No database writes. Proposed removals require the same source review as positive markers.',
                        '1860 remains labeled GER3 in candidate club mapping; historical marker does not fix membership.',
                        'Czech administrative events remain held and cannot be reclassified as sporting results.'])
    (OUT/'FLAG_RECONCILIATION.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(inspected_clubs=inspected,proposed_clears=len(clears),out_of_scope_preserved=len(holds))))
if __name__=='__main__':main()
