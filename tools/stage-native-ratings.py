"""Write a calibrated rating candidate only from bound native alternatives and a validated source world."""
import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'src'))
from fm27.common import sha256,write_json
p=argparse.ArgumentParser()
for name in ('binary','plan','candidate','report'):
    p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args()
if a.candidate.exists() or a.report.exists(): raise ValueError('New rating stage outputs required')
manifest_path=a.plan.with_suffix('.manifest.json')
manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
if (manifest['status']!='CALIBRATED_NATIVE_PLAN_GATES_PASS_NOT_WRITTEN'
        or sha256(a.plan)!=manifest['plan_sha256']
        or any(v['status']!='PASS' for v in (*manifest['holdout_checks'].values(),*manifest['league_checks'].values(),manifest['inflation_check']))):
    raise ValueError('Calibrated native plan gates are incomplete')
for name,digest in manifest['evidence_sha256'].items():
    if sha256(root/name)!=digest: raise ValueError('Calibrated rating evidence changed: '+name)
baseline_path=root/'reports/local/NATIVE_RATING_BASELINE_INSPECTION_01.json'
if manifest['evidence_sha256'].get(str(baseline_path.relative_to(root)))!=sha256(baseline_path):
    raise ValueError('Native source baseline is not bound')
baseline=json.loads(baseline_path.read_text(encoding='utf-8'))
source=Path(manifest['candidate']).resolve()
if Path(baseline['candidate']).resolve()!=source: raise ValueError('Rating source candidates differ')
database=source/'database'
def inventory():
    return {str(path.relative_to(database)):sha256(path) for path in sorted(database.rglob('*')) if path.is_file()}
if inventory()!=baseline['source_database_sha256']: raise ValueError('Native rating source changed')
build=json.loads(a.binary.with_suffix('.exe.build.json').read_text(encoding='utf-8-sig'))
native=json.loads((root/'reports/local/NATIVE_TESTS.json').read_text(encoding='utf-8'))
python=json.loads((root/'reports/local/AUTOMATED_TESTS.json').read_text(encoding='utf-8'))
if (build['status']!='PASS' or native['status']!='PASS' or native['tests']<123 or python['status']!='PASS'
        or native['binary_sha256']!=sha256(a.binary) or build['binary_sha256']!=sha256(a.binary)
        or native['source_sha256']!=build['source_sha256']):
    raise ValueError('Current tested rating binary required')
for name,digest in {**build['source_sha256'],**python['source_sha256']}.items():
    if sha256(root/name)!=digest: raise ValueError('Tested source changed')
started=dt.datetime.now(dt.timezone.utc).isoformat()
result=subprocess.run([str(a.binary.resolve()),str(database),str(a.candidate.resolve()),'--stage-ratings',str(a.plan.resolve())],cwd=root)
if result.returncode: raise RuntimeError('Native rating stage failed')
if inventory()!=baseline['source_database_sha256'] or sha256(a.plan)!=manifest['plan_sha256']:
    raise ValueError('Source or plan changed during rating stage')
report=dict(status='NATIVE_RATING_STAGE_WRITTEN_NOT_VALIDATED',started_at=started,
    finished_at=dt.datetime.now(dt.timezone.utc).isoformat(),candidate=str(a.candidate.resolve()),
    source_candidate=str(source),plan=manifest,plan_manifest_sha256=sha256(manifest_path),
    source_unchanged=True,binary_sha256=sha256(a.binary),build=build,native_tests=native,python_tests=python,
    release_ready=False,limitations='Native rating write only. Exact mutation scope, protected fields, full native reread and game gates remain required.')
write_json(a.report,report)
write_json(a.candidate/'NATIVE_BUILD_INPUTS.json',report)
print(json.dumps(dict(status=report['status'],players=manifest['rows'],candidate=str(a.candidate.resolve()))))
