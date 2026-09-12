"""Evaluate calibration alternatives, binding isolated native reads to the full-world preview."""
import argparse
import json
import subprocess
import sys
from pathlib import Path
from collections import Counter
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'src'))
from fm27.common import read_csv,sha256,write_json
p=argparse.ArgumentParser()
for name in ('binary','blocks','plan','preview-report','output','report'):
    p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args()
if a.output.exists() or a.report.exists(): raise ValueError('New native alternatives required')
block_report=json.loads((a.blocks/'BLOCKS.json').read_text(encoding='utf-8'))
preview=json.loads(a.preview_report.read_text(encoding='utf-8'))
build=json.loads(a.binary.with_suffix('.exe.build.json').read_text(encoding='utf-8-sig'))
tests=json.loads((root/'reports/local/NATIVE_TESTS.json').read_text(encoding='utf-8'))
if (preview['status']!='NATIVE_PREVIEW_VALIDATED_CALIBRATION_REQUIRED'
        or block_report['index_sha256']!=sha256(a.blocks/'players.csv')
        or block_report['plan_sha256']!=sha256(a.plan) or preview['plan_sha256']!=sha256(a.plan)
        or tests['status']!='PASS' or tests['tests']<123 or tests['binary_sha256']!=sha256(a.binary)
        or tests['source_sha256']!=build['source_sha256'] or build['binary_sha256']!=sha256(a.binary)):
    raise ValueError('Validated blocks, full native preview and tested build required')
for name,digest in build['source_sha256'].items():
    if sha256(root/name)!=digest: raise ValueError('Native batch source changed')
for name,digest in preview['files_sha256'].items():
    if sha256(Path(name))!=digest: raise ValueError('Full native preview changed')
result=subprocess.run([str(a.binary.resolve()),'--evaluate-rating-blocks',str(a.blocks.resolve()),str(a.plan.resolve()),str(a.output.resolve())],cwd=root)
if result.returncode: raise RuntimeError('Native block evaluation failed')
alternatives=read_csv(a.output/'native_rating_alternatives.csv')
expected={r['fm_id']:r for r in read_csv(Path(preview['preview'])/'RATING_PREVIEW_DIFF.csv')}
direct={r['fm_id']:r for r in alternatives if r['variant']=='DIRECT'}
counts=Counter(r['fm_id'] for r in alternatives)
if (set(direct)!=set(expected) or set(counts.values())!={52}
        or any(int(r['level13'])!=int(expected[ident]['level_preview']) for ident,r in direct.items())):
    raise ValueError('Isolated native levels differ from full-world preview')
write_json(a.report,dict(status='NATIVE_CALIBRATION_ALTERNATIVES_PASS',players=len(expected),
    alternatives=len(alternatives),full_world_direct_level_parity=True,plan_sha256=sha256(a.plan),
    preview_report_sha256=sha256(a.preview_report),block_index_sha256=sha256(a.blocks/'players.csv'),
    alternatives_path=str((a.output/'native_rating_alternatives.csv').resolve()),
    alternatives_sha256=sha256(a.output/'native_rating_alternatives.csv'),
    binary_sha256=sha256(a.binary),native_tests=tests,tool_sha256=sha256(Path(__file__)),
    release_ready=False,ratings_written_to_database=False))
print(json.dumps(dict(status='PASS',players=len(expected),alternatives=len(alternatives))))
