"""Cross-check fresh profiles against captured rosters; contradictions remain holds."""
import csv,json
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'data/current/workers/south-west'
def read(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def main():
    profiles={r['player_tm_id']:r for r in read(OUT/'profiles.csv')}
    roster=read(OUT/'rosters.csv'); rows=[]
    for r in roster:
        p=profiles.get(r['player_tm_id'])
        if not p:continue
        issues=[]
        if p['dob']!=r['dob']:issues.append('DOB_CONFLICT')
        if p['club_tm_id']!=r['club_tm_id']:issues.append('CLUB_CONFLICT')
        if p.get('contract_until') and r.get('contract_until') and p['contract_until']!=r['contract_until']:issues.append('CONTRACT_CONFLICT')
        if p.get('joined') and r.get('joined') and p['joined']!=r['joined']:issues.append('JOIN_DATE_CONFLICT')
        if p['snapshot_date']!=r['snapshot_date']:issues.append('MIXED_SNAPSHOT')
        rows.append(dict(league=r['league'],club=r['club'],player=r['player'],player_tm_id=r['player_tm_id'],
            status='REVIEW_REQUIRED' if issues else 'HIGH_CONFIDENCE',issues=';'.join(issues),
            roster_club_tm_id=r['club_tm_id'],profile_club_tm_id=p['club_tm_id'],full_name=p['full_name'],
            dob=p['dob'],nationality=p['nationality_text'],loan_owner_tm_id=p['loan_owner_tm_id'],
            owner_contract_until=p['owner_contract_until'],profile_source=p['source'],profile_sha256=p['source_sha256'],
            roster_source=r['source'],roster_sha256=r['source_sha256'],snapshot_date=r['snapshot_date']))
    if rows:
        with (OUT/'profile-crosscheck.csv').open('w',encoding='utf-8',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    counts=dict(profiles=len(profiles),roster_crosschecks=len(rows),statuses=dict(Counter(r['status'] for r in rows)),
        issues=dict(Counter(i for r in rows for i in r['issues'].split(';') if i)))
    (OUT/'profile-crosscheck.json').write_text(json.dumps(counts,indent=2),encoding='utf-8');print(json.dumps(counts))
if __name__=='__main__':main()
