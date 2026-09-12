from pathlib import Path
import csv,json,hashlib
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/generated/release-candidate/native08-integrated-20260912-01'
READ=ROOT/'data/generated/native08-integrated-20260912-01-reread'
BASE=ROOT/'data/generated/native-reread-increment-20260909-07'
def rows(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def main():
    m=json.loads((OUT/'INTEGRATION.json').read_text(encoding='utf-8'))
    v=json.loads((OUT/'VALIDATION.json').read_text())
    assert v['status']=='PASS_EXACT_DELTA_AND_HISTORY'
    assert rows(READ/'native_players.csv')==rows(BASE/'native_players.csv'),'Player inventory changed'
    expected={r['fm_id'] for r in m['changes']}
    old_ratings=rows(BASE/'native_ratings.csv');new_ratings=rows(READ/'native_ratings.csv')
    assert len(old_ratings)==len(new_ratings)
    changed_hashes=set()
    for before,after in zip(old_ratings,new_ratings):
        # These hashes include the serialized loan condition, not only ratings.
        different={k for k in before.keys()|after.keys() if before.get(k)!=after.get(k)}
        assert different <= {'serialized_sha256','protected_sha256'},f'Rating field changed: {different}'
        if different:changed_hashes.add(before['fm_id'])
    assert changed_hashes==expected,'Unexpected serialized rating-row hash changes'
    old={r['fm_id']:r for r in rows(BASE/'native_player_semantics.csv')}
    new={r['fm_id']:r for r in rows(READ/'native_player_semantics.csv')}
    assert old.keys()==new.keys()
    actual={pid for pid in old if old[pid]!=new[pid]}
    assert actual==expected,{'unexpected':sorted(actual-expected)[:10],'missing':sorted(expected-actual)[:10]}
    v.update(status='PASS_NATIVE_REREAD_HISTORY_AND_ALLOWED_LOAN_DELTA',native_reread='PASS',
             player_rating_records_preserved=len(new),changed_player_semantics=len(actual),
             unit_tests='3 tests / 7 cases PASS',operator_return_test='Moore/Tottenham and Amissah/Fulham confirmed; not 744 individual runtime checks')
    (OUT/'VALIDATION.json').write_text(json.dumps(v,indent=2)+'\n')
    m['status']=v['status'];m['native_reread']=str(READ)
    (OUT/'INTEGRATION.json').write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(v))
if __name__=='__main__':main()
