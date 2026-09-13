"""Capture narrowly scoped official confirmation for unresolved current moves."""
import csv,datetime,hashlib,json,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/current/evidence/primary-transfers'
FACTS=[
 dict(player='Boubakar Dembaga',player_tm_id='1173870',transaction_type='PERMANENT',effective_date='2026-07-15',old_club='AS Monaco',new_club='Royal Charleroi SC',contract_until='',shirt_number='23',source='https://www.sporting-charleroi.be/news/boubakar-dembaga-rejoint-le-sporting-de-charleroi/',notes='Official buyer confirms permanent transfer; duration undisclosed; shirt23 corroborated official player page.'),
 dict(player='Ryotaro Araki',player_tm_id='',transaction_type='PERMANENT',effective_date='2026-07-20',old_club='Kashima Antlers',new_club='Sint-Truidense VV',contract_until='',shirt_number='71',source='https://stvv.com/nl/nieuws/artikel/stvv-neemt-ryotaro-araki-over-van-kashima-antlers',notes='Official buyer confirms multi-year permanent contract and shirt71; exact end date not supplied.'),
]
def main():
 OUT.mkdir(parents=True,exist_ok=True)
 profiles=list(csv.DictReader((ROOT/'data/current/evidence/review-profiles.csv').open(encoding='utf-8-sig')))
 for row in FACTS:
  if not row['player_tm_id']:
   candidates=[x for x in profiles if x['player']==row['player']];assert len(candidates)==1
   row['player_tm_id']=candidates[0]['player_tm_id']
  with urllib.request.urlopen(urllib.request.Request(row['source'],headers={'User-Agent':'FM27Research/0.1'}),timeout=30) as response:body=response.read(4000000)
  digest=hashlib.sha256(body).hexdigest();(OUT/(digest+'.html')).write_bytes(body)
  row.update(source_sha256=digest,source_date=row['effective_date'],snapshot_date='2026-09-12',confidence='CONFIRMED',retrieved_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
 (OUT/'confirmed-facts.json').write_text(json.dumps(FACTS,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(dict(confirmed=len(FACTS),players=[r['player'] for r in FACTS])))
if __name__=='__main__':main()
