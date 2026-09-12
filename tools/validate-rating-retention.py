"""Verify actual native partial-profile results against retained fields and the prior candidate."""
import argparse
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'src'))
from fm27.common import read_csv, sha256, write_json

p = argparse.ArgumentParser()
for name in ('validation', 'prior-validation', 'plan', 'output'):
    p.add_argument('--' + name, type=Path, required=True)
a = p.parse_args()
if a.output.exists():
    raise ValueError('New retention validation required')

def read(path):
    return json.loads(path.read_text(encoding='utf-8'))

current = read(a.validation)
prior = read(a.prior_validation)
manifest = read(a.plan.with_suffix('.manifest.json'))
if (current['status'] != 'NATIVE_RATINGS_PASS_GAME_GATES_OPEN'
        or prior['status'] != 'NATIVE_RATINGS_PASS_GAME_GATES_OPEN'
        or current['plan_sha256'] != sha256(a.plan)
        or manifest['prior_validated_plan_sha256'] != prior['plan_sha256']
        or current['source_candidate'] != prior['source_candidate']):
    raise ValueError('Prior/current native validations do not bind the integrated plan')
bound = {}
for proof in (current, prior):
    if any(check['status'] != 'PASS' for check in proof['checks'].values()):
        raise ValueError('Incomplete native validation')
    for name, digest in proof['bound_files_sha256'].items():
        if name in bound and bound[name] != digest:
            raise ValueError('Conflicting native evidence')
        bound[name] = digest
for name, digest in bound.items():
    if sha256(Path(name)) != digest:
        raise ValueError('Native evidence changed: ' + name)
for name, digest in manifest['evidence_sha256'].items():
    if sha256(root / name) != digest:
        raise ValueError('Integration evidence changed')
plan = read_csv(a.plan)
fields = list(plan[0])[6:-4]
source_before = {r['fm_id']: r for r in read_csv(Path(current['candidate']) / 'before-ratings/native_ratings.csv')}
native_current = {r['fm_id']: r for r in read_csv(Path(current['candidate']) / 'native_ratings.csv')}
native_prior = {r['fm_id']: r for r in read_csv(Path(prior['candidate']) / 'native_ratings.csv')}
prior_build = read(Path(prior['candidate']) / 'NATIVE_BUILD_INPUTS.json')
prior_ids = {r['fm_id'] for r in prior_build['plan']['diagnostics'] if not r['reasons']}
if len(prior_ids) != prior['changed_players'] or len(prior_ids) != manifest['prior_validated_rows_unchanged']:
    raise ValueError('Prior approved identity count differs')
for ident in prior_ids:
    if native_current[ident] != native_prior[ident]:
        raise ValueError('Previously validated actual native rating row changed: ' + ident)
retained = manifest['partial_profile_field_holds']
if len(retained) != manifest['partial_profile_players']:
    raise ValueError('Partial profile accounting differs')
retained_count = 0
changed_count = 0
for item in retained:
    ident = item['fm_id']
    old, new = source_before[ident], native_current[ident]
    if ident in prior_ids or new['fifa_id'] != item['fifa_id']:
        raise ValueError('Partial profile identity overlaps or differs')
    for field, values in item['retained_fields'].items():
        if field not in fields or int(new[field]) != values['native'] or old[field] != new[field]:
            raise ValueError('Retained disputed field changed in native candidate')
        retained_count += 1
    changes = sum(old[f] != new[f] for f in fields)
    if changes == 0:
        raise ValueError('No actual partial profile change')
    changed_count += changes
if retained_count != manifest['unresolved_retained_attributes']:
    raise ValueError('Unresolved retained attribute count differs')
write_json(a.output, dict(status='NATIVE_PARTIAL_RATING_RETENTION_PASS_GAME_GATES_OPEN',
    candidate=current['candidate'], prior_candidate=prior['candidate'],
    prior_actual_native_rows_unchanged=len(prior_ids), partial_profiles=len(retained),
    partial_changed_attributes=changed_count, disputed_native_attributes_unchanged=retained_count,
    unresolved_review_players=manifest['unresolved_review_players'],
    native_validation_sha256=sha256(a.validation), prior_validation_sha256=sha256(a.prior_validation),
    plan_sha256=sha256(a.plan), plan_manifest_sha256=sha256(a.plan.with_suffix('.manifest.json')),
    tool_sha256=sha256(Path(__file__)), release_ready=False,
    limitations='Retained disputed attributes remain unresolved. Full native reread is independently bound; editor and game tests remain open.'))
print(json.dumps(dict(status='PASS', prior_rows_preserved=len(prior_ids), partial_profiles=len(retained),
                      retained_attributes=retained_count, partial_changed_attributes=changed_count)))
