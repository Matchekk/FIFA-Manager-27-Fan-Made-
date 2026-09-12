"""Validate the exact allowed byte delta and recheck history fields independently."""
from pathlib import Path
import json,hashlib,importlib.util
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/generated/release-candidate/native08-integrated-20260912-01'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    manifest=json.loads((OUT/'INTEGRATION.json').read_text(encoding='utf-8'))
    history=Path(manifest['history_base']);changes=manifest['changes']
    assert len({r['fm_id'] for r in changes})==len(changes)
    checked=0
    for source in (history/'database').rglob('*'):
        if not source.is_file():continue
        rel=source.relative_to(history/'database');target=OUT/'database'/rel
        original=source.read_bytes();actual=target.read_bytes()
        if source.name.startswith('CountryData'):
            cid=int(source.stem.removeprefix('CountryData'))
            for row in [r for r in changes if r['country_id']==cid]:
                from datetime import date
                offset=row['byte_offset']
                assert actual[offset:offset+7]==b'2461223'
                expected=str(date.fromisoformat(row['source_start']).toordinal()+1721425).encode()
                assert original[offset:offset+7]==expected
                actual=actual[:offset]+expected+actual[offset+7:]
        assert actual==original,f'Unapproved delta: {rel}'
        checked+=1
    for source in (history/'overlay').rglob('*'):
        if source.is_file():assert sha(source)==sha(OUT/'overlay'/source.relative_to(history/'overlay'))
    spec=importlib.util.spec_from_file_location('history_validation',ROOT/'tools/validate-history-2026-package.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.OUT=OUT;module.main()
    result=dict(status='PASS_EXACT_DELTA_AND_HISTORY',database_files=checked,
                changed_loan_dates=len(changes),all_other_database_bytes_unchanged=True,
                history_overlays_unchanged=True,native_reread='PENDING')
    (OUT/'VALIDATION.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))
if __name__=='__main__':main()
