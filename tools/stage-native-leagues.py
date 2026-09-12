"""Write an external native league candidate with frozen inputs and unchanged-source proof."""
import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'src'))
from fm27.common import sha256, write_json

p = argparse.ArgumentParser()
for name in ('binary', 'plan', 'candidate', 'report'):
    p.add_argument('--' + name, type=Path, required=True)
a = p.parse_args()
if a.candidate.exists() or a.report.exists():
    raise ValueError('New candidate and report required')
binary = a.binary.resolve()
build = json.loads(binary.with_suffix('.exe.build.json').read_text(encoding='utf-8-sig'))
tests = json.loads((root / 'reports/local/NATIVE_TESTS.json').read_text(encoding='utf-8'))
digest = sha256(binary)
if (build['status'] != 'PASS' or tests['status'] != 'PASS' or build['binary_sha256'] != digest
        or tests['binary_sha256'] != digest or build['source_sha256'] != tests['source_sha256']):
    raise ValueError('Native build/test evidence differs')
manifest_path = a.plan.with_suffix('.manifest.json')
manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
if manifest['status'] != 'FROZEN_PARTIAL_LEAGUE_MEMBERSHIP_NOT_RELEASE' or manifest['plan_sha256'] != sha256(a.plan):
    raise ValueError('League plan not frozen')
for name, digest_expected in {**build['source_sha256'], **manifest['evidence_sha256']}.items():
    path = (root / name).resolve()
    if not path.is_relative_to(root) or sha256(path) != digest_expected:
        raise ValueError('Stale source/evidence: ' + name)
database = Path(manifest['source_database']).resolve()
def inventory():
    return {str(p.relative_to(database)): sha256(p) for p in sorted(database.rglob('*')) if p.is_file()}
before = inventory()
if before != manifest['source_database_sha256']:
    raise ValueError('Source database no longer matches reviewed native membership')
report = dict(status='RUNNING', started_at=dt.datetime.now(dt.timezone.utc).isoformat(),
    binary_sha256=digest, build=build, native_tests=tests, plan=manifest, plan_manifest_sha256=sha256(manifest_path),
    candidate=str(a.candidate.resolve()), source_database=str(database), release_ready=False)
write_json(a.report, report)
result = subprocess.run([str(binary), str(database), str(a.candidate.resolve()), '--stage-league-membership', str(a.plan.resolve())], cwd=root)
intact = inventory() == before and sha256(binary) == digest and sha256(a.plan) == manifest['plan_sha256'] and sha256(manifest_path) == report['plan_manifest_sha256']
passed = result.returncode == 0 and intact and (a.candidate / 'STAGING_ONLY.txt').is_file()
report.update(status='NATIVE_LEAGUE_STAGE_WRITTEN_NOT_VALIDATED' if passed else 'FAIL',
    source_and_inputs_unchanged=intact, exit_code=result.returncode, finished_at=dt.datetime.now(dt.timezone.utc).isoformat())
write_json(a.report, report)
if a.candidate.exists():
    write_json(a.candidate / 'NATIVE_BUILD_INPUTS.json', report)
print(json.dumps({k: report[k] for k in ('status', 'candidate', 'source_and_inputs_unchanged', 'release_ready')}))
sys.exit(0 if passed else 1)
