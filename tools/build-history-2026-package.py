"""Build a separate complete database copy and validate the exact history-only diff."""
from pathlib import Path
import hashlib,json,re,shutil
ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'data/generated/history-20260912-01'
BASE=ROOT/'data/generated/release-candidate/transfer-increment-20260909-07/database'
OUT=ROOT/'data/generated/history-20260912-03'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    assert not OUT.exists(),'Exclusive output required'
    manifest=json.loads((WORK/'preview/PREVIEW_MANIFEST.json').read_text(encoding='utf-8'))
    OUT.mkdir()
    shutil.copytree(BASE,OUT/'database')
    changed={}
    for row in manifest['native_patches']:
        source=Path(row['source']);assert sha(source)==row['source_sha256']
        target=OUT/'database/data'/source.name
        raw=source.read_bytes();lines=raw.splitlines(keepends=True)
        patch=Path(row['patch']).read_text(encoding='utf-8').splitlines()
        edits=[]
        for i,line in enumerate(patch):
            if not line.startswith('@@'):continue
            m=re.fullmatch(r'@@ -(\d+) \+(\d+) @@',line);assert m and m[1]==m[2]
            index=int(m[1])-1
            assert patch[i+1].startswith('-') and patch[i+2].startswith('+')
            before=patch[i+1][1:].encode();after=patch[i+2][1:].encode()
            assert lines[index].rstrip(b'\r\n')==before
            ending=b'\r\n' if lines[index].endswith(b'\r\n') else b'\n' if lines[index].endswith(b'\n') else b''
            lines[index]=after+ending;edits.append(index)
        assert len(edits)==row['changed_lines'] and len(edits)==len(set(edits))
        output=b''.join(lines);target.write_bytes(output)
        original_lines=raw.splitlines(keepends=True)
        assert {i for i,(a,b) in enumerate(zip(original_lines,lines)) if a!=b}==set(edits)
        assert len(original_lines)==len(lines)
        # No player or staff byte is allowed to change.
        for kind in (b'PLAYER',b'STAFF'):
            pattern=rb'%INDEX%'+kind+rb'\r?\n.*?%INDEXEND%'+kind
            assert re.findall(pattern,raw,re.S)==re.findall(pattern,output,re.S)
        changed[source.relative_to(BASE).as_posix()]={'before':sha(source),'after':sha(target),'changed_lines':len(edits)}
    overlays=[]
    for row in manifest['winner_file_overlays']:
        source=Path(row['source']);overlay=Path(row['overlay'])
        assert sha(source)==row['source_sha256'] and sha(overlay)==row['overlay_sha256']
        data=overlay.read_bytes();additions=set(row['added_matches']+row['added_team_rows'])
        restored=b''.join(line for line in data.splitlines(keepends=True) if line.decode('latin-1').rstrip('\r\n') not in additions)
        assert restored==source.read_bytes(),'Existing historic bytes changed'
        teams=re.findall(rb'(?m)^#TEAM\s*=\s*(\d+),([0-9A-Fa-f]+)',data)
        local_ids=[int(x[0]) for x in teams];assert len(local_ids)==len(set(local_ids))
        for entry in row['added_matches']:
            fields=entry.split('=',1)[1].strip().split(',')
            assert int(fields[2]) in local_ids and int(fields[3]) in local_ids
            assert data.count(entry.encode('ascii'))==1
        dest=OUT/'overlay/fmdata/historic'/overlay.name;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(overlay,dest);overlays.append({'path':str(dest),'sha256':sha(dest),'added_records':len(row['added_matches'])})
    verified=0
    for source in BASE.rglob('*'):
        if source.is_file():
            rel=source.relative_to(BASE).as_posix();target=OUT/'database'/rel
            if rel not in changed:assert sha(source)==sha(target),rel
            else:assert sha(source)==changed[rel]['before'],rel
            verified+=1
    result=dict(status='PACKAGE_BUILT_BYTE_VALIDATED_NATIVE_REREAD_PENDING',base=str(BASE),
                changed_database_files=changed,unchanged_database_files=verified-len(changed),
                player_staff_blocks='BYTE_IDENTICAL',winner_overlays=overlays,
                source_unchanged=True,runtime_modified=False,
                scope='2025/26 top-flight champions, main domestic cup winners/runners and scoped movement markers for ten countries',
                exclusions=['Full match-by-match league history','Supercups/league cups/continental history',
                            'Czech July 3 administrative membership replacement','League membership fixes including 1860'],
                provenance=str(WORK/'HISTORY_DRAFT.json'))
    (OUT/'PACKAGE.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'database_files':verified,'changed_files':len(changed),'added_competition_records':sum(x['added_records'] for x in overlays),'status':result['status']}))
if __name__=='__main__':main()
