"""Resolve observed country/position labels against native enums; no player writes."""
import csv,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
NATIONS={'Elfenbeinküste':'Cote_d_Ivoire','Ghana':'Ghana','Usbekistan':'Uzbekistan','Senegal':'Senegal','Belgien':'Belgium','Tschechien':'Czech_Republic','Japan':'Japan','Serbien':'Serbia','Nigeria':'Nigeria','Ukraine':'Ukraine','Gambia':'Gambia','Ägypten':'Egypt','Spanien':'Spain','Frankreich':'France','Brasilien':'Brazil','Griechenland':'Greece','England':'England','Niederlande':'Netherlands','Italien':'Italy','Deutschland':'Germany','Haiti':'Haiti','Portugal':'Portugal','Mexiko':'Mexico','Marokko':'Morocco','Südkorea':'Korea_Republic','Türkei':'Turkey','Guinea':'Guinea'}
POSITIONS={'Torwart':'GK','Mittelfeld - Zentrales Mittelfeld':'CM','Sturm - Mittelstürmer':'ST','Sturm - Rechtsaußen':'RW','Mittelfeld - Offensives Mittelfeld':'AM','Abwehr - Innenverteidiger':'CB','Mittelfeld - Defensives Mittelfeld':'DM','Abwehr - Rechter Verteidiger':'RB','Sturm - Hängende Spitze':'CF','Sturm - Linksaußen':'LW'}
def main():
 enum=(ROOT/'upstream/fifam/fmapi/FifamNation.h').read_text(encoding='utf-8-sig')
 nations={name:int(num) for num,name in re.findall(r'ENUM_MEMBER\(\s*(\d+),\s*(\w+),',enum)}
 inputs=ROOT/'data/current/workers/south-west/create-ready.csv'
 rows=[]
 for r in csv.DictReader(inputs.open(encoding='utf-8-sig')):
  labels=r['nationality'].split();unknown=[x for x in labels if x not in NATIONS or NATIONS[x] not in nations]
  ids=[nations[NATIONS[x]] for x in labels if x not in unknown]
  rows.append(dict(player_tm_id=r['player_tm_id'],source_nationalities=r['nationality'],native_nationality_ids=json.dumps(ids),native_position=POSITIONS.get(r['position'],''),status='REVIEW_REQUIRED' if unknown or r['position'] not in POSITIONS else 'CONFIRMED',notes='Unsupported source nation: '+','.join(unknown) if unknown else 'Source order retained; native enum values, not serialized position codes.'))
 out=ROOT/'data/current/workers/south-west/create-native-fields.csv'
 with out.open('w',encoding='utf-8',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 print(json.dumps(dict(rows=len(rows),confirmed=sum(r['status']=='CONFIRMED' for r in rows),held=[r for r in rows if r['status']!='CONFIRMED'])))
if __name__=='__main__':main()
