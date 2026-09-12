"""Inspect all persisted FM13 attributes from a hash-bound combined candidate."""
import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'src'))
from fm27.common import read_csv,sha256,write_json
p=argparse.ArgumentParser()
for name in ('binary','candidate-validation','output','report'):
    p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args()
if a.output.exists() or a.report.exists():
    raise ValueError('New inspection outputs required')
proof=json.loads(a.candidate_validation.read_text(encoding='utf-8'))
if proof['status']!='NATIVE_COMBINED_PASS_GAME_GATES_OPEN':
    raise ValueError('Completed combined native proof required')
candidate=Path(proof['candidate']).resolve()
database=candidate/'database'
expected={str(Path(name).relative_to(database)):digest for name,digest in proof['bound_files_sha256'].items()
          if Path(name).is_relative_to(database)}
def inventory():
    return {str(path.relative_to(database)):sha256(path) for path in sorted(database.rglob('*')) if path.is_file()}
if not expected or inventory()!=expected:
    raise ValueError('Combined candidate database differs from validation')
build=json.loads(a.binary.with_suffix('.exe.build.json').read_text(encoding='utf-8-sig'))
tests=json.loads((root/'reports/local/NATIVE_TESTS.json').read_text(encoding='utf-8'))
if (build['status']!='PASS' or tests['status']!='PASS' or tests['tests']<119
        or sha256(a.binary)!=build['binary_sha256'] or tests['binary_sha256']!=build['binary_sha256']
        or tests['source_sha256']!=build['source_sha256']):
    raise ValueError('Native rating build and completed tests required')
for name,digest in build['source_sha256'].items():
    if sha256(root/name)!=digest:
        raise ValueError('Native rating source changed')
result=subprocess.run([str(a.binary.resolve()),str(database),str(a.output.resolve()),'--inspect-ratings'],cwd=root)
if result.returncode:
    raise RuntimeError('Native rating inspection failed')
path=a.output/'native_ratings.csv'
rows=read_csv(path)
if len(rows)!=proof['native_reread_players'] or len({r['fm_id'] for r in rows})!=len(rows):
    raise ValueError('Native rating player coverage differs')
# Compare stable canonical identities with the already validated reread. Reread
# free-player numeric IDs can change and are not treated as persistent identity.
from collections import Counter
reread=Path(json.loads((root/'reports/local/NATIVE_COMBINED_LEAGUE_VALIDATION_01.json').read_text())['reread'])
semantic=reread/'native_player_semantics.csv'
verify_digest=proof['bound_files_sha256'].get(str(semantic.resolve()))
if verify_digest is None or sha256(semantic)!=verify_digest:
    raise ValueError('Combined reread semantics not bound')
fields=('fifa_id','dob','name','club_id','serialized_sha256')
if Counter(tuple(r[f] for f in fields) for r in rows)!=Counter(tuple(r[f] for f in fields) for r in read_csv(semantic)):
    raise ValueError('Rating inspection differs from validated player serialization')
if inventory()!=expected:
    raise ValueError('Source database changed during inspection')
write_json(a.report,dict(status='NATIVE_RATING_BASELINE_INSPECTION_PASS',
    captured_at=dt.datetime.now(dt.timezone.utc).isoformat(),candidate=str(candidate),players=len(rows),
    output=str(path.resolve()),output_sha256=sha256(path),
    candidate_validation_sha256=sha256(a.candidate_validation),source_database_sha256=expected,
    native_reread_semantics_sha256=sha256(semantic),binary_sha256=sha256(a.binary),
    native_tests=tests,source_unchanged=True,ratings_modified=False,release_ready=False,
    limitations='37 persisted attributes and protected canonical fields inspected. No calibrated proposal or game validation yet.'))
print(json.dumps(dict(status='PASS',players=len(rows),ratings_modified=False)))
