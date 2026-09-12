"""Reversibly integrate into the closed diagnostic runtime, never the installation."""
from pathlib import Path
import json,hashlib,shutil,subprocess,datetime
ROOT=Path(__file__).resolve().parents[1]
CANDIDATE=ROOT/'data/generated/release-candidate/native08-integrated-20260912-01'
RUNTIME=ROOT/'runtime/loan-test-20260912-08'
BACKUP=ROOT/'reports/local/native08-20260912-evidence/before-combined-integration'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    assert json.loads((CANDIDATE/'VALIDATION.json').read_text())['status']=='PASS_NATIVE_REREAD_HISTORY_AND_ALLOWED_LOAN_DELTA'
    state=subprocess.run(['powershell','-NoProfile','-Command',"if (Get-Process -Name Manager,EdManager -ErrorAction SilentlyContinue) {exit 8}"],capture_output=True)
    assert state.returncode==0,'Close Manager and Editor first'
    assert RUNTIME.resolve()==ROOT/'runtime/loan-test-20260912-08'
    assert not BACKUP.exists(),'Exclusive backup required'
    BACKUP.mkdir(parents=True)
    mappings=[]
    for folder,prefix in [(CANDIDATE/'database',Path('database')),(CANDIDATE/'overlay',Path())]:
        for source in folder.rglob('*'):
            if source.is_file():mappings.append((source,prefix/source.relative_to(folder)))
    # Snapshot every target before changing any target; old Master remains recoverable.
    backups=[]
    for rel in [r for _,r in mappings]+[Path('database/Master.dat')]:
        target=RUNTIME/rel
        if target.exists():
            backup=BACKUP/rel;backup.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(target,backup)
            digest=sha(target);assert sha(backup)==digest
            backups.append(dict(path=rel.as_posix(),sha256=digest,backup=str(backup)))
        else:backups.append(dict(path=rel.as_posix(),absent=True))
    (BACKUP/'BACKUP.json').write_text(json.dumps(backups,indent=2)+'\n')
    changed=[]
    for source,rel in mappings:
        target=RUNTIME/rel;digest=sha(source)
        if target.exists() and sha(target)==digest:continue
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source,target);assert sha(target)==digest
        changed.append(dict(path=rel.as_posix(),sha256=digest))
    master=RUNTIME/'database/Master.dat'
    if master.exists():
        bound=next(x for x in backups if x['path']=='database/Master.dat')
        assert sha(master)==bound['sha256'] and sha(Path(bound['backup']))==bound['sha256']
        master.unlink() # Exact diagnostic file only; verified backup exists.
    report=dict(status='INTEGRATED_EDITOR_EXPORT_REQUIRED',runtime=str(RUNTIME),candidate=str(CANDIDATE),
                backup=str(BACKUP),changed=changed,compiled_master='ABSENT_PENDING_EXPORT',
                original_install_modified=False,runtime07_modified=False,save_files_modified=False,
                timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat())
    (ROOT/'reports/local/NATIVE08_INTEGRATION.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='changed'}))
if __name__=='__main__':main()
