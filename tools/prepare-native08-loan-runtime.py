"""Physical, verified Runtime07 diagnostic copy. No links and no stale Master.dat."""
from pathlib import Path
import hashlib, json, os, shutil, datetime

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'runtime/game-test-20260912-07'
DEST=ROOT/'runtime/loan-test-20260912-08'
EXPERIMENT=ROOT/'data/generated/native08-loan-date-experiment-02/EXPERIMENT.json'
REPORT=ROOT/'reports/local/native08-20260912-evidence/loan-runtime-copy.json'

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(4*1024**2), b''):h.update(chunk)
    return h.hexdigest()

def main():
    assert not DEST.exists() and not REPORT.exists(), 'Exclusive destination required'
    experiment=json.loads(EXPERIMENT.read_text(encoding='utf-8'))
    overlays={Path(x['source']).relative_to(SOURCE):x for x in experiment['observations']}
    entries=[]
    for folder,dirs,files in os.walk(SOURCE,followlinks=False):
        for name in dirs+files:
            p=Path(folder)/name
            assert not p.is_symlink() and not (hasattr(p,'is_junction') and p.is_junction()),p
        for name in files:
            p=Path(folder)/name
            rel=p.relative_to(SOURCE)
            if rel.as_posix().lower() in ('database/master.dat','fm27_runtime_copy.json'):continue
            entries.append((p,rel,p.stat().st_size))
    total=sum(x[2] for x in entries)
    assert shutil.disk_usage(ROOT).free>total+2*1024**3
    DEST.mkdir()
    manifest=[]
    for index,(source,rel,size) in enumerate(entries,1):
        actual=Path(overlays[rel]['variant']) if rel in overlays else source
        if rel in overlays:
            assert sha(source)==overlays[rel]['source_sha256']
            assert sha(actual)==overlays[rel]['variant_sha256']
        target=DEST/rel
        target.parent.mkdir(parents=True,exist_ok=True)
        before=actual.stat()
        shutil.copyfile(actual,target)
        digest=sha(actual)
        assert sha(target)==digest and actual.stat().st_mtime_ns==before.st_mtime_ns
        manifest.append(dict(path=rel.as_posix(),sha256=digest,variant=rel in overlays))
        if index%1000==0: print(json.dumps(dict(copied=index,total=len(entries))),flush=True)
    assert not (DEST/'database/Master.dat').exists()
    result=dict(status='VERIFIED_PHYSICAL_COPY_EDITOR_EXPORT_REQUIRED',source=str(SOURCE),destination=str(DEST),
        timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),files=len(entries),bytes=total,
        experiment=str(EXPERIMENT),changed_fields=2,compiled_database='NOT_EXPORTED',file_hashes=manifest)
    REPORT.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='file_hashes'}),flush=True)

if __name__=='__main__':main()
