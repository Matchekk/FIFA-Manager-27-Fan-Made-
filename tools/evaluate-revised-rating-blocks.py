"""Evaluate a reviewed GK mapping revision using already-proven native player blocks."""
import argparse
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'src'))
from fm27.common import read_csv,sha256,write_json
p=argparse.ArgumentParser()
for name in ('binary','blocks','old-plan','plan','revision','preview-report','output','report'):
    p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args()
if a.output.exists() or a.report.exists(): raise ValueError('New revised batch outputs required')
revision=json.loads(a.revision.read_text(encoding='utf-8'))
preview=json.loads(a.preview_report.read_text(encoding='utf-8'))
blocks=json.loads((a.blocks/'BLOCKS.json').read_text(encoding='utf-8'))
old={r['fm_id']:r for r in read_csv(a.old_plan)};new={r['fm_id']:r for r in read_csv(a.plan)}
if (revision['status']!='REVIEWED_GOALKEEPER_SOURCE_MAPPING_REVISION'
        or sha256(a.old_plan)!=revision['original_plan_sha256'] or sha256(a.plan)!=revision['revised_plan_sha256']
        or blocks['plan_sha256']!=sha256(a.old_plan) or blocks['index_sha256']!=sha256(a.blocks/'players.csv')
        or preview['plan_sha256']!=sha256(a.old_plan) or set(old)!=set(new)):
    raise ValueError('Revision does not bind this native baseline and both plans')
for name,digest in revision['evidence_sha256'].items():
    if sha256(root/name)!=digest: raise ValueError('GK revision evidence changed')
for name,digest in preview['files_sha256'].items():
    if sha256(Path(name))!=digest: raise ValueError('Original full-world preview changed')
revised=set(revision['revised_player_ids'])
if {ident for ident in old if old[ident]!=new[ident]}!=revised:
    raise ValueError('Plan differs outside explicit goalkeeper revision')
cohort={r['fm_id']:r for r in json.loads(a.old_plan.with_suffix('.manifest.json').read_text(encoding='utf-8'))['cohort']}
if any(cohort[ident]['native_position']!='GK' or cohort[ident]['source_position']!='GK' for ident in revised):
    raise ValueError('Revised player is not an agreed goalkeeper')
tests=json.loads((root/'reports/local/NATIVE_TESTS.json').read_text(encoding='utf-8'))
build=json.loads(a.binary.with_suffix('.exe.build.json').read_text(encoding='utf-8-sig'))
if tests['status']!='PASS' or tests['tests']<123 or tests['binary_sha256']!=sha256(a.binary) or tests['source_sha256']!=build['source_sha256']:
    raise ValueError('Native batch build lacks current tests')
for name,digest in build['source_sha256'].items():
    if sha256(root/name)!=digest: raise ValueError('Native batch build changed')
result=subprocess.run([str(a.binary.resolve()),'--evaluate-rating-blocks',str(a.blocks.resolve()),str(a.plan.resolve()),str(a.output.resolve())],cwd=root)
if result.returncode: raise RuntimeError('Revised native batch failed')
alternatives_path=a.output/'native_rating_alternatives.csv'
alternatives=read_csv(alternatives_path)
direct={r['fm_id']:r for r in alternatives if r['variant']=='DIRECT'}
prior={r['fm_id']:r for r in read_csv(Path(preview['preview'])/'RATING_PREVIEW_DIFF.csv')}
if set(direct)!=set(new) or set(Counter(r['fm_id'] for r in alternatives).values())!={52}:
    raise ValueError('Native alternatives incomplete')
if any(int(direct[i]['level13'])!=int(prior[i]['level_preview']) for i in set(new)-revised):
    raise ValueError('Unchanged native outfield levels differ')
write_json(a.report,dict(status='NATIVE_CALIBRATION_ALTERNATIVES_PASS',players=len(new),alternatives=len(alternatives),
    full_world_direct_level_parity=False,unchanged_outfield_level_parity=len(new)-len(revised),
    revised_gk_levels_evaluated_by_native_reader=len(revised),baseline_native_input_parity=True,
    plan_sha256=sha256(a.plan),revision_sha256=sha256(a.revision),preview_report_sha256=sha256(a.preview_report),
    block_index_sha256=sha256(a.blocks/'players.csv'),alternatives_path=str(alternatives_path.resolve()),
    alternatives_sha256=sha256(alternatives_path),binary_sha256=sha256(a.binary),native_tests=tests,
    tool_sha256=sha256(Path(__file__)),release_ready=False,ratings_written_to_database=False,
    limitations='All isolated baseline inputs match full-world native baseline; changed GK alternatives use the same native level function. Final staged database still requires full-world write/reread validation.'))
print(json.dumps(dict(players=len(new),alternatives=len(alternatives),revised_goalkeepers=len(revised))))
