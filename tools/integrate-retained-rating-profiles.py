"""Integrate native-evaluated partial profiles while preserving prior approved rows exactly."""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'src'))
from fm27.common import read_csv, sha256, write_csv, write_json
from fm27.rating_calibration import attributes_for_variant, calibrated_level, family, holdout

p = argparse.ArgumentParser()
for name in ('plan', 'review', 'validation', 'output'):
    p.add_argument('--' + name, type=Path, required=True)
a = p.parse_args()
if a.output.exists() or a.output.with_suffix('.manifest.json').exists():
    raise ValueError('New integrated plan required')

def read(path):
    return json.loads(path.read_text(encoding='utf-8'))

manifest_path = a.plan.with_suffix('.manifest.json')
manifest = read(manifest_path)
review = read(a.review)
validation = read(a.validation)
if (manifest['status'] != 'CALIBRATED_NATIVE_PLAN_GATES_PASS_NOT_WRITTEN'
        or validation['status'] != 'NATIVE_RATINGS_PASS_GAME_GATES_OPEN'
        or validation['plan_sha256'] != sha256(a.plan)
        or manifest['plan_sha256'] != sha256(a.plan)
        or review['status'] != 'NATIVE_FIELD_RETENTION_EXPERIMENT_GATES_PASS'
        or review['frozen_models'] != manifest['models']
        or review['ratings_written_to_database'] is not False):
    raise ValueError('Passed native candidate and bound partial-profile experiment required')
if any(v['status'] != 'PASS' for v in (*review['holdout_checks'].values(),
        *review['league_checks'].values(), review['inflation_check'], *validation['checks'].values())):
    raise ValueError('Review or original native validation has unresolved gates')
evidence = dict(manifest['evidence_sha256'])
for name, digest in review['evidence_sha256'].items():
    if name in evidence and evidence[name] != digest:
        raise ValueError('Conflicting review source evidence')
    evidence[name] = digest
for name, digest in evidence.items():
    if sha256(root / name) != digest:
        raise ValueError('Changed source evidence: ' + name)
for name, digest in review['output_sha256'].items():
    path = (a.review.parent / name).resolve()
    if not path.is_relative_to(a.review.parent.resolve()) or sha256(path) != digest:
        raise ValueError('Review output changed')
    evidence[path.relative_to(root).as_posix()] = digest
if review['evidence_sha256'].get(manifest_path.resolve().relative_to(root).as_posix()) != sha256(manifest_path):
    raise ValueError('Review is not bound to this frozen calibration')
original = read_csv(a.plan)
additional = read_csv(a.review.parent / 'partial-profile-proposals.csv')
source = {r['fm_id']: r for r in read_csv(a.review.parent / 'masked-source-preview.csv')}
baseline = {r['fm_id']: r for r in read_csv(root / 'data/generated/native-rating-baseline-20260908-01/native_ratings.csv')}
native = {(r['fm_id'], r['variant'], r['source_percent'], r['offset']): r
          for r in read_csv(a.review.parent / 'native/native_rating_alternatives.csv')}
diagnostics = {r['fm_id']: dict(r) for r in manifest['diagnostics']}
reviews = {r['fm_id']: r for r in review['reviews']}
original_ids = {r['fm_id'] for r in original}
extra_ids = {r['fm_id'] for r in additional}
if (len(original_ids) != len(original) or len(extra_ids) != len(additional)
        or original_ids & extra_ids or review['original_approved_players'] != len(original)
        or review['partial_proposal_players'] != len(additional)
        or extra_ids != {i for i, r in reviews.items() if not r['remaining_profile_reasons']}):
    raise ValueError('Partial/original identity coverage differs')
fields = list(original[0])[6:-4]
partial_holds = []
for row in additional:
    ident = row['fm_id']
    detail = reviews[ident]
    prior = diagnostics[ident]
    old = baseline[ident]
    src = source[ident]
    if prior['reasons'] != ['EXTREME_SOURCE_PROFILE_REVIEW'] or not detail['retained_fields']:
        raise ValueError('Cannot integrate a person with other original review reasons')
    if (family(prior['position']) != family(prior['source_position'])
            or family(prior['position']) != detail['family']
            or detail['holdout'] != holdout(row['fifa_id'])):
        raise ValueError('Position or identity split changed')
    attrs = attributes_for_variant({f: int(old[f]) for f in fields},
                                   {f: int(src[f]) for f in fields}, 75, detail['offset'])
    expected = {**src, 'expected_level13': str(detail['selected_level']), **{f: str(v) for f, v in attrs.items()}}
    if row != expected:
        raise ValueError('Partial proposal differs from reviewed native variant')
    grid = native[(ident, 'CALIBRATION_GRID', '75', str(detail['offset']))]
    direct = native[(ident, 'DIRECT', '100', '0')]
    target = calibrated_level(manifest['models'][detail['family']], int(direct['level13']))
    if (int(grid['level13']) != int(row['expected_level13'])
            or abs(int(grid['level13']) - int(old['level13'])) > 6
            or abs(int(grid['level13']) - target) > 1
            or max(abs(attrs[f] - int(old[f])) for f in fields) > 20):
        raise ValueError('Partial native level or profile limits differ')
    for field, values in detail['retained_fields'].items():
        if (attrs[field] != int(old[field]) or values['native'] != int(old[field])
                or abs(values['source'] - values['native']) <= 35):
            raise ValueError('Disputed attribute was changed or misclassified')
    diagnostics[ident] = {**prior, 'reasons': [], 'level_direct': int(direct['level13']),
                          'target_level': round(target, 3), 'selected_level': int(grid['level13']),
                          'level_delta': int(grid['level13']) - int(old['level13']),
                          'offset': detail['offset'], 'max_attribute_delta': detail['max_attribute_delta'],
                          'partial_profile': True, 'unresolved_retained_fields': detail['retained_fields']}
    partial_holds.append(dict(fm_id=ident, fifa_id=row['fifa_id'], name=detail['name'],
                              status='PARTIAL_PROFILE_RETAINED_FIELDS_REVIEW_REQUIRED',
                              retained_fields=detail['retained_fields']))
combined = original + additional
if combined[:len(original)] != original:
    raise ValueError('Previously validated rows changed')
holds = [r for r in manifest['holds'] if r['fm_id'] not in extra_ids]
if len(holds) + len(partial_holds) != manifest['held_players']:
    raise ValueError('Original review accountability was lost')
for path in (a.plan, manifest_path, a.review, a.validation, Path(__file__)):
    evidence[path.resolve().relative_to(root).as_posix()] = sha256(path)
write_csv(a.output, list(original[0]), combined)
write_json(a.output.with_suffix('.manifest.json'), {
    **manifest, 'status': 'CALIBRATED_NATIVE_PLAN_GATES_PASS_NOT_WRITTEN',
    'plan_sha256': sha256(a.output), 'rows': len(combined), 'held_players': len(holds), 'holds': holds,
    'diagnostics': list(diagnostics.values()), 'evidence_sha256': evidence,
    'holdout_checks': review['holdout_checks'], 'league_checks': review['league_checks'],
    'inflation_check': review['inflation_check'], 'partial_profile_players': len(additional),
    'partial_profile_field_holds': partial_holds,
    'unresolved_review_players': len(holds) + len(partial_holds),
    'unresolved_retained_attributes': sum(len(r['retained_fields']) for r in partial_holds),
    'prior_validated_plan_sha256': sha256(a.plan), 'prior_validated_rows_unchanged': len(original),
    'partial_profile_source_plan_sha256': sha256(a.review.parent / 'masked-source-preview.csv'),
    'field_retention_review_sha256': sha256(a.review), 'calibration_complete': False,
    'method': manifest['method'] + ' Add only original sole-extreme-review cases as partial profiles: '
        'retain disputed attributes exactly, evaluate remaining detail with the native function and frozen models. '
        'Previously validated rows are unchanged. Retained fields remain explicitly unresolved.'})
print(json.dumps(dict(rows=len(combined), preserved_validated_rows=len(original),
                      partial_profiles=len(additional), held_whole_players=len(holds),
                      unresolved_review_players=len(holds) + len(partial_holds),
                      plan_sha256=sha256(a.output))))
