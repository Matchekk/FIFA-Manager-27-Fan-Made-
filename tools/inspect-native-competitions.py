"""Bind a read-only native competition inspection to exact database/build bytes."""
import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from fm27.common import sha256, write_json
root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--binary', type=Path, required=True)
parser.add_argument('--database', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--report', type=Path, required=True)
args = parser.parse_args()
for name in ('binary', 'database', 'output', 'report'):
    setattr(args, name, getattr(args, name).resolve())
if args.output.exists() or args.report.exists():
    raise ValueError('Inspection outputs must be new')
build = json.loads(args.binary.with_suffix('.exe.build.json').read_text(encoding='utf-8-sig'))
tests = json.loads((root / 'reports/local/NATIVE_TESTS.json').read_text(encoding='utf-8'))
if build['status'] != 'PASS' or tests['status'] != 'PASS' or build['binary_sha256'] != sha256(args.binary) or tests['binary_sha256'] != sha256(args.binary):
    raise ValueError('Native competition inspector build/test evidence mismatch')
for name, digest in build['source_sha256'].items():
    if sha256(root / name) != digest:
        raise ValueError('Native inspector source changed: ' + name)
def hashes():
    return {str(p.relative_to(args.database)): sha256(p) for p in sorted(args.database.rglob('*')) if p.is_file()}
before = hashes()
if not before:
    raise ValueError('Empty database input')
print('Native competition inspection: source files=' + str(len(before)), flush=True)
result = subprocess.run([str(args.binary), str(args.database), str(args.output), '--inspect-competitions'], cwd=root)
if result.returncode:
    raise ValueError('Native competition inspection failed')
if hashes() != before:
    raise ValueError('Read-only inspection changed source bytes')
metadata = json.loads((args.output / 'COMPETITION_INSPECTION.json').read_text(encoding='utf-8'))
write_json(args.report, {**metadata, 'database': str(args.database), 'binary': str(args.binary),
    'binary_sha256': sha256(args.binary), 'build_source_sha256': build['source_sha256'],
    'native_tests_sha256': sha256(root / 'reports/local/NATIVE_TESTS.json'),
    'input_files_sha256': before, 'source_unchanged': True,
    'output_files_sha256': {str(p.relative_to(args.output)): sha256(p) for p in sorted(args.output.iterdir()) if p.is_file()},
    'output': str(args.output), 'finished_at': dt.datetime.now(dt.timezone.utc).isoformat(), 'release_ready': False})
print(json.dumps(metadata))
