"""Capture the narrow regional dependencies of the confirmed GER3 movements."""
import csv, datetime, hashlib, json, urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/current/evidence/german-dependencies'
SOURCES={
 'nordost-movements': 'https://www.nofv-online.de/index.php/aktuelles-leser/loks-aus-fuehrt-zum-abstiegsdomino.html',
 'nordost-members': 'https://www.nofv-online.de/index.php/regionalliga-nordost.html',
 'bayern-format': 'https://www.bfv.de/mspw/regionalliga-bayern/2026-27/regionalliga-bayern-der-1.-spieltag',
 'bayern-schedule': 'https://www.bfv.de/news/regionalliga-bayern/2026/07/rahmenspielplan-regionalliga-bayern-2026-27',
}
def main():
 OUT.mkdir(parents=True,exist_ok=True)
 evidence=[]
 for label,url in SOURCES.items():
  try:
   req=urllib.request.Request(url,headers={'User-Agent':'FM27Research/0.1'})
   with urllib.request.urlopen(req,timeout=35) as response: body=response.read(5000000)
   digest=hashlib.sha256(body).hexdigest(); (OUT/(digest+'.html')).write_bytes(body)
   evidence.append(dict(label=label,url=url,sha256=digest,retrieved_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),status='CAPTURED'))
  except Exception as exc: evidence.append(dict(label=label,url=url,status='FAILED',error=str(exc)))
 (OUT/'manifest.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
 # Explicit identity map reviewed against the native club index.  Native club
 # IDs, never CountryScript serialized references, are written here.
 clubs={r['club_id']:r for r in csv.DictReader((ROOT/'data/intermediate/transfer-increment-20260909-07/clubs.csv').open(encoding='utf-8-sig'))}
 memberships={
  '352387076': [('1376277','FIRST'),('1376269','RESERVE'),('1376358','FIRST'),('1378815','FIRST'),('1380433','FIRST'),('1376361','FIRST'),('1376417','FIRST'),('1376281','FIRST'),('1376554','FIRST'),('1376366','FIRST'),('1376427','FIRST'),('1376497','FIRST'),('1380447','FIRST'),('1376607','FIRST'),('1376373','RESERVE'),('1376351','FIRST'),('1388978','FIRST'),('1376494','FIRST')],
  '352387079': [('1376572','FIRST'),('1376312','FIRST'),('1376571','FIRST'),('1376292','FIRST'),('1384541','FIRST'),('1376291','FIRST'),('1378752','FIRST'),('1376467','FIRST'),('1378782','FIRST'),('1376431','RESERVE'),('1376290','FIRST'),('1378770','FIRST'),('1384981','FIRST'),('1376258','RESERVE'),('1376264','RESERVE'),('1376441','FIRST'),('1376288','RESERVE'),('1384579','FIRST'),('1376465','FIRST')],
 }
 rows=[]
 for competition,teams in memberships.items():
  label='nordost-members' if competition=='352387076' else 'bayern-format'
  source=next(e for e in evidence if e['label']==label)
  if source['status']!='CAPTURED': continue
  for pid,team in teams:
   assert clubs[pid]['country_id']=='21'
   rows.append(dict(competition_id=competition,club_id=pid,team_type=team,club=clubs[pid]['club'],source=source['url'],source_sha256=source['sha256'],status='CONFIRMED',snapshot_date='2026-09-12'))
 with (ROOT/'data/current/german-regional-dependencies.csv').open('w',encoding='utf-8',newline='') as f:
  writer=csv.DictWriter(f,fieldnames=list(rows[0])); writer.writeheader();writer.writerows(rows)
 print(json.dumps(evidence))
if __name__=='__main__':main()
