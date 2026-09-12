"""Independently reread intended fields from the completed history package."""
from pathlib import Path
import importlib.util,json
from collections import defaultdict
ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'data/generated/history-20260912-01'
OUT=ROOT/'data/generated/history-20260912-03'
def main():
    spec=importlib.util.spec_from_file_location('inspect_history',ROOT/'tools/inspect-history-2026-draft.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.verify_upstream_layout(ROOT)
    inspected=json.loads((WORK/'CURRENT_NATIVE_HISTORY.json').read_text(encoding='utf-8'))
    clears=json.loads((WORK/'FLAG_RECONCILIATION.json').read_text(encoding='utf-8'))['clear_proposals']
    wanted=defaultdict(set)
    ready=[r for r in inspected['comparisons'] if r['comparison_status']=='READY_FOR_SEPARATE_MUTATION_REVIEW']
    for row in ready+clears:wanted[row['country_id']].add(row['club_id'])
    actual={}
    for cid,uids in wanted.items():
        found,_=module.parse_country_file(OUT/f'database/data/CountryData{cid}.sav',cid,uids)
        for uid,matches in found.items():
            assert len(matches)==1
            actual[uid]=matches[0]
    for row in ready:
        club=actual[row['club_id']];field=row['target_field']
        if field.startswith('mHistory.'):
            assert club['history'][field]==row['proposed_result'],row
        else:
            key='cup' if field.endswith('.mCup') else 'league'
            assert club['mFirstTeamLastSeasonInfo'][key]==row['proposed_value'],row
    for row in clears:
        assert actual[row['club_id']]['lastSeasonFlags'] & row['clear_mask']==0,row
    result=dict(status='PASS_INDEPENDENT_FIELD_REREAD',positive_fields_checked=len(ready),
                stale_marker_removals_checked=len(clears),unique_clubs=len(actual),
                held_rows_not_applied=sum(r['comparison_status']=='DRAFT_HELD' for r in inspected['comparisons']))
    (OUT/'FIELD_VALIDATION.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))
if __name__=='__main__':main()
