"""Close the bounded milestone; preserve test artifacts before restoring baseline."""
from pathlib import Path
import json, hashlib, shutil, subprocess, datetime
ROOT=Path(__file__).resolve().parents[1]
E=ROOT/'reports/local/native08-20260912-evidence'
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def write(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def main():
    assert subprocess.run(['powershell','-NoProfile','-Command','if (Get-Process -Name Manager,EdManager -ErrorAction SilentlyContinue) {exit 8}']).returncode==0
    pre=json.loads((E/'preflight.json').read_text())
    out=E/'final-cleanup';out.mkdir(exist_ok=False)
    result={'status':'PASS','processes':'Manager and EdManager closed','restored':[],'checks':[]}
    for group,base in [('saves',Path(r'C:\Users\Matej Uni\Documents\FM\Data\SaveGames')),('config',Path(r'C:\Users\Matej Uni\Documents\FM\Config'))]:
        for row in pre[group]:
            target=base/row['relative_path'];backup=Path(row['backup'])
            assert sha(backup)==row['sha256']
            if not target.exists() or sha(target)!=row['sha256']:
                retained=out/group/row['relative_path'];retained.parent.mkdir(parents=True,exist_ok=True)
                if target.exists():shutil.copyfile(target,retained);assert sha(retained)==sha(target)
                shutil.copyfile(backup,target)
                result['restored'].append({'group':group,'path':str(target),'retained':str(retained)})
            assert sha(target)==row['sha256']
            result['checks'].append({'group':group,'path':str(target),'sha256':row['sha256']})
    for row in pre['bound_files']:
        assert sha(Path(row['path']))==row['sha256'],'Identity mismatch: '+row['path']
    result['identity_files']=pre['bound_files']
    result['scope']='All 16 baseline saves and 12 baseline configs; original/Runtime07 Manager.exe and Master.dat only, not full installation tree.'
    master=ROOT/'runtime/loan-test-20260912-08/database/Master.dat'
    integration=json.loads((ROOT/'reports/local/NATIVE08_INTEGRATION.json').read_text())
    assert master.stat().st_size>0
    assert master.stat().st_mtime>datetime.datetime.fromisoformat(integration['timestamp']).timestamp()
    export={'status':'PASS','basis':'Operator confirms Editor export; newly created Master independently hashed','path':str(master),'bytes':master.stat().st_size,'sha256':sha(master),'mtime_utc':datetime.datetime.fromtimestamp(master.stat().st_mtime,datetime.timezone.utc).isoformat(),'combined_career_test':'NOT_TESTED'}
    write(E/'combined-editor-export.json',export)
    write(E/'final-cleanup.json',result)
    integration.update(status='INTEGRATED_EDITOR_EXPORTED',compiled_master=export,cleanup='native08-20260912-evidence/final-cleanup.json')
    write(ROOT/'reports/local/NATIVE08_INTEGRATION.json',integration)
    g=json.loads((ROOT/'reports/local/NATIVE08_GATE.json').read_text())
    g['status']='PARTIAL';g['closed']=True
    g['existing_save_integrity']={'status':'PASS','evidence':'native08-20260912-evidence/final-cleanup.json','count':16}
    g['original_install_integrity']={'status':'PASS','evidence':'native08-20260912-evidence/final-cleanup.json','scope':'Original and Runtime07 Manager.exe/Master.dat identities only; no full-tree audit'}
    g['cleanup']={'status':'PASS','evidence':'native08-20260912-evidence/final-cleanup.json','config_files':12,'test_saves':'Preserved; no unrelated files removed'}
    g['transition_2027']['structural_checks']='Original career crossed and reloaded; Bundesliga/CL present; Darvich returned; original Moore/Amissah defect reproduced. Separate corrected two-player experiment returned both per operator.'
    g['post_transition_structure']['blocker']='Original candidate loan defect; corrected experiment passed operator return check, combined candidate not runtime-tested.'
    c=g['loan_return_investigation']['controlled_experiment']
    c.update(status='PASS_OPERATOR_RETURN_CONFIRMED',result='User: Jup sind beide richtig, following requested Moore/Tottenham and Amissah/Fulham check. Post-transition reload of this variant not separately confirmed.',control_limit='Country-selection context may differ; not a fully controlled all-settings comparison.')
    g['observed_failures']=[{'status':'FAIL','scope':'Original Native07 Moore/Amissah loan semantics','resolution':'Two-player date projection return operator-confirmed; generalized to 744 adopted current loans in separate candidate; combined runtime check remains NOT_TESTED.'}]
    g['combined_candidate']={'status':'PARTIAL','offline_validation':'PASS','editor_export':'PASS','new_career_and_transition':'NOT_TESTED','evidence':['NATIVE08_INTEGRATION.json','native08-20260912-evidence/combined-editor-export.json']}
    g['next_recommended_milestone']='Fresh bounded task: combined-candidate new-career smoke for history views and active loans, then representative corrected loan return and post-transition save/reload. No repeat global audit or broad rating work.'
    write(ROOT/'reports/local/NATIVE08_GATE.json',g)
    print(json.dumps({'cleanup':'PASS','export':export,'restored_configs':[r['path'] for r in result['restored'] if r['group']=='config']}))
if __name__=='__main__':main()
