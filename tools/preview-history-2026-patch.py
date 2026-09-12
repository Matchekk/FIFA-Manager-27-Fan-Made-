"""Produce review-only native diffs and external winner-file overlays, outside runtime."""
import csv
import hashlib
import importlib.util
import json
import re
from pathlib import Path

ROOT=Path(r'C:\FM27CommunityOverhaul')
OUT=ROOT/'data/generated/history-20260912-01'
RUNTIME=ROOT/'runtime/game-test-20260912-07'

def sha(data): return hashlib.sha256(data).hexdigest()

def main():
    spec=importlib.util.spec_from_file_location('draft',ROOT/'tools/prepare-history-2026-draft.py')
    draft=importlib.util.module_from_spec(spec);spec.loader.exec_module(draft)
    inspected=json.loads((OUT/'CURRENT_NATIVE_HISTORY.json').read_text(encoding='utf-8'))
    current_draft=OUT/'HISTORY_DRAFT.json'
    assert inspected['draft']['sha256']==sha(current_draft.read_bytes()), 'Inspector stale'
    preview=OUT/'preview';preview.mkdir(exist_ok=True)
    buffers={};native=[]
    reconciliation=json.loads((OUT/'FLAG_RECONCILIATION.json').read_text(encoding='utf-8'))
    assert reconciliation['draft_sha256']==sha(current_draft.read_bytes()), 'Flag reconciliation stale'
    for row in reconciliation['clear_proposals']:
        path=Path(row['source_file'])
        if path not in buffers:
            data=path.read_bytes();assert sha(data)==row['source_sha256']
            lines=data.decode('utf-8-sig').splitlines(keepends=True);buffers[path]=(data,lines,lines.copy())
        data,before,after=buffers[path];idx=row['source_line']-1
        assert int(before[idx].strip())==row['before_flags']
        ending='\r\n' if after[idx].endswith('\r\n') else '\n'
        after[idx]=str(int(after[idx].strip()) & ~row['clear_mask'])+ending
    for row in inspected['comparisons']:
        if row['comparison_status']!='READY_FOR_SEPARATE_MUTATION_REVIEW' or not row['would_change']:continue
        club=inspected['clubs_by_stable_uid'][str(row['club_id'])];path=Path(club['source_file'])
        if path not in buffers:
            data=path.read_bytes();assert sha(data)==club['source_file_sha256']
            lines=data.decode('utf-8-sig').splitlines(keepends=True);buffers[path]=(data,lines,lines.copy())
        data,before,after=buffers[path];idx=row['source_line']-1
        ending='\r\n' if after[idx].endswith('\r\n') else '\n'
        if row['target_field'].startswith('mHistory.'):
            after[idx]=','.join(map(str,row['proposed_result']))+ending
        else:
            mask=5 if row['target_field'].endswith('.mLeague') else 80
            flags={'Promoted':1,'Relegated':4,'Winner':16,'RunnerUp':64,'None':0}
            value=(int(after[idx].strip()) & ~mask) | flags[row['proposed_value']]
            after[idx]=str(value)+ending
    for path,(data,before,after) in buffers.items():
        # All mutations replace lines in place; avoid quadratic full-file matching
        # on multi-million-line native files during the operator simulation.
        changed=[i for i,(a,b) in enumerate(zip(before,after)) if a!=b]
        assert len(before)==len(after)
        parts=['--- a/database/data/'+path.name+'\n','+++ b/database/data/'+path.name+'\n']
        for i in changed:
            parts.extend([f'@@ -{i+1} +{i+1} @@\n','-'+before[i],'+'+after[i]])
        diff=''.join(parts)
        target=preview/(path.name+'.patch');target.write_text(diff,encoding='utf-8',newline='')
        assert path.read_bytes()==data, 'Source unexpectedly changed'
        native.append({'source':str(path),'source_sha256':sha(data),'patch':str(target),'changed_lines':sum(a!=b for a,b in zip(before,after))})
    with draft.CLUBS.open(encoding='utf-8-sig',newline='') as f:clubs=list(csv.DictReader(f))
    runners={21:'^Borussia Dortmund$',14:'^Manchester City$',27:'Napoli',45:'^Real Madrid C.F.$',18:'^RC Lens$',38:'^Sporting Clube de Portugal$',34:'^Feyenoord Rotterdam$',7:'^Royale Union Saint-Gilloise$',48:'^Fenerbah',12:'^AC Sparta Praha$'}
    scores={21:'3,0',14:'1,0',27:'2,0',45:'4,3,p',18:'3,1',38:'2,1,e',34:'5,1',7:'3,1,e',48:'2,1',12:'3,1'}
    external=[]
    for cid,champ,winner,cup_runner,_,_ in draft.TITLES:
        matches=[c for c in clubs if int(c['country_id'])==cid and re.search(runners[cid],c['club'],re.I)]
        assert len(matches)==1,(cid,matches)
        runner=int(matches[0]['club_id'])
        path=RUNTIME/f'fmdata/historic/{cid}cf.txt';data=path.read_bytes()
        # Latin-1 gives a reversible byte projection; added text is ASCII only.
        text=data.decode('latin-1');newline='\r\n' if '\r\n' in text else '\n'
        teams={int(uid,16):int(local) for local,uid in re.findall(r'^#TEAM\s*=\s*(\d+),([0-9A-Fa-f]+)',text,re.M)}
        assert len(teams)>0
        additions=[]
        next_id=max(teams.values())+1
        for uid in [champ,runner,winner,cup_runner]:
            if uid not in teams:
                teams[uid]=next_id;additions.append(f'#TEAM = {next_id},{uid:08X} // FM27 club UID {uid}');next_id+=1
        if additions:
            marker=re.search(r'BEGIN\(TEAMS\).*?^END\s*$',text,re.S|re.M);assert marker
            pos=text.rfind('END',marker.start(),marker.end())
            text=text[:pos]+newline.join(additions)+newline+text[pos:]
        added=[]
        for ctype,win,runner_id,score in [(1,champ,runner,None),(3,winner,cup_runner,scores[cid])]:
            keys=re.findall(r'^#COMP\s*=\s*([^,]+),'+str(cid)+','+str(ctype)+r',0,ROUND_FINAL',text,re.M);assert len(keys)==1
            key=keys[0];assert not re.search(r'^#MATCH\s*=\s*'+re.escape(key)+r',2026,',text,re.M)
            line=f'#MATCH = {key},2026,{teams[win]},{teams[runner_id]}' + (','+score if score else '')
            old=list(re.finditer(r'^#MATCH\s*=\s*'+re.escape(key)+r',[^\r\n]*',text,re.M));assert old
            pos=old[-1].end();text=text[:pos]+newline+line+text[pos:];added.append(line)
        target=preview/f'overlay/fmdata/historic/{cid}cf.txt';target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(text.encode('latin-1'))
        assert path.read_bytes()==data
        external.append({'source':str(path),'source_sha256':sha(data),'overlay':str(target),'overlay_sha256':sha(target.read_bytes()),'added_matches':added,'added_team_rows':additions})
    manifest={'status':'PREVIEW_ONLY_NOT_APPLIED_NOT_RELEASE_READY','native_patches':native,'winner_file_overlays':external,
              'limits':['No runtime/source/save mutation.','Held Czech administrative movements excluded from native preview.','Stale markers reconciled within covered scope; unreviewed lower-division league flags preserved.','1860 administrative drop is sourced, but candidate still lists GER3; membership integration remains required.','Full league-result histories remain absent; do not substitute trophy records for complete season results.','Source conflicts/primary verification and native reread/export/UI checks required before use.'],
              'stale_marker_clear_proposals':len(reconciliation['clear_proposals']),
              'out_of_scope_markers_preserved':len(reconciliation['out_of_scope_preserved']),
              'source_conflicts':['RSSSF Czech cup final incorrectly names Mlada Boleslav; official MOL Cup source establishes Jablonec. Overlay follows official source.'],
              'validation':'Source hashes checked before/after; unique club/competition keys; no existing 2026 rows overwritten; existing file bytes preserved except explicit additions.'}
    (preview/'PREVIEW_MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'native_patch_files':len(native),'winner_overlays':len(external),'added_competition_records':sum(len(x['added_matches']) for x in external)}))

if __name__=='__main__':main()
