"""Verify/reuse original save backups; snapshot new test saves and current config."""
from pathlib import Path
import json, hashlib, shutil
ROOT=Path(__file__).resolve().parents[1]
E=ROOT/'reports/local/native08-20260912-evidence'
OUT=E/'loan-experiment-preflight'
SAVES=Path(r'C:\Users\Matej Uni\Documents\FM\Data\SaveGames')
CONFIG=Path(r'C:\Users\Matej Uni\Documents\FM\Config')
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for c in iter(lambda:f.read(4*1024**2),b''):h.update(c)
    return h.hexdigest()
def main():
    OUT.mkdir(exist_ok=False)
    baseline=json.loads((E/'preflight.json').read_text(encoding='utf-8-sig'))
    originals={r['relative_path']:r for r in baseline['saves']}
    rows=[]
    for category,folder in [('saves',SAVES),('config',CONFIG)]:
        for source in sorted(folder.rglob('*')):
            if not source.is_file():continue
            rel=source.relative_to(folder)
            digest=sha(source)
            old=originals.get(str(rel)) if category=='saves' else None
            if old:
                assert digest==old['sha256'],f'Existing save changed: {rel}'
                backup=Path(old['backup'])
            else:
                backup=OUT/category/rel
                backup.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(source,backup)
            assert sha(backup)==digest and sha(source)==digest
            rows.append(dict(category=category,relative_path=str(rel),sha256=digest,backup=str(backup)))
    result=dict(status='PASS_VERIFIED_BACKUPS',rows=rows,
                namespace=['L08-Day1.ea','L08-Pre.ea','L08-Post.ea'],
                autosave='Must remain off; verify in newly created career before simulation')
    assert all(not (SAVES/n).exists() for n in result['namespace'])
    (OUT/'PREFLIGHT.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=result['status'],files=len(rows))))
if __name__=='__main__':main()
