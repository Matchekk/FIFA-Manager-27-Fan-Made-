"""Extract existing native player blocks for fast FM13 calibration without loading the world repeatedly."""
import argparse
import datetime as dt
import json
import sys
from pathlib import Path

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'src'))
from fm27.common import read_csv,sha256,write_csv,write_json
from fm27.database import check_versions,player_record,ATTRIBUTES
p=argparse.ArgumentParser()
p.add_argument('--inspection',type=Path,required=True)
p.add_argument('--plan',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args()
if a.output.exists(): raise ValueError('New block extraction directory required')
inspection=json.loads(a.inspection.read_text(encoding='utf-8'))
manifest=json.loads(a.plan.with_suffix('.manifest.json').read_text(encoding='utf-8'))
if (inspection['status']!='NATIVE_RATING_BASELINE_INSPECTION_PASS'
        or manifest['inspection_sha256']!=sha256(a.inspection) or sha256(a.plan)!=manifest['plan_sha256']):
    raise ValueError('Bound inspection and source plan required')
native_path=Path(inspection['output'])
if sha256(native_path)!=inspection['output_sha256']: raise ValueError('Rating inspection changed')
plan={r['fm_id']:r for r in read_csv(a.plan)}
native={r['fm_id']:r for r in read_csv(native_path) if r['fm_id'] in plan}
database=Path(inspection['candidate'])/'database'
inventory={str(path.relative_to(database)):sha256(path) for path in database.rglob('*') if path.is_file()}
if inventory!=inspection['source_database_sha256']: raise ValueError('Source database changed')
rows=[]; found=set()
a.output.mkdir(parents=True)
for path in sorted((database/'data').glob('CountryData*.sav')):
    lines=path.read_text(encoding='utf-8-sig').splitlines()
    check_versions(lines)
    index=0
    while index<len(lines):
        if lines[index]!='%INDEX%PLAYER': index+=1;continue
        end=lines.index('%INDEXEND%PLAYER',index+1)
        ident=str(int(lines[index-1]))
        if ident in plan:
            if ident in found: raise ValueError('Duplicate native player block')
            found.add(ident)
            expected=native[ident]
            parsed=player_record(lines[index+1:end],ident,{},path,index+1)
            if (str(parsed['fifa_id'])!=expected['fifa_id']
                    or parsed['dob']!=dt.datetime.strptime(expected['dob'],'%d.%m.%Y').date().isoformat()
                    or any(int(expected[field])!=json.loads(parsed['attributes'])[field] for field in ATTRIBUTES)):
                raise ValueError('Player block identity or attributes differ')
            block=a.output/(ident+'.sav')
            block.write_text('\n'.join(lines[index:end+1])+'\n',encoding='utf-8-sig',newline='\n')
            rows.append(dict(fm_id=ident,fifa_id=expected['fifa_id'],dob=parsed['dob'],club_id=expected['club_id'],
                baseline_sha256=expected['serialized_sha256'],block_sha256=sha256(block),
                main_position=expected['main_position'],style=expected['style'],experience=expected['experience'],
                level13=expected['level13'],**{field:expected[field] for field in ATTRIBUTES}))
        index=end+1
if found!=set(plan): raise ValueError('Incomplete player block coverage')
write_csv(a.output/'players.csv',list(rows[0]),sorted(rows,key=lambda r:int(r['fm_id'])))
write_json(a.output/'BLOCKS.json',dict(status='NATIVE_PLAYER_BLOCKS_EXTRACTED_FOR_LEVEL_EVALUATION',
    players=len(rows),index_sha256=sha256(a.output/'players.csv'),source_database_sha256=inventory,
    inspection_sha256=sha256(a.inspection),plan_sha256=sha256(a.plan),tool_sha256=sha256(Path(__file__)),
    limitations='Existing player blocks only. Independent native reader must prove position/style/experience/attribute/level parity before evaluating alternatives.',
    release_ready=False))
print(json.dumps(dict(players=len(rows),index_sha256=sha256(a.output/'players.csv'))))
