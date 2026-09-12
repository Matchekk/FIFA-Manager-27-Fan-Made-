"""Evaluate partial profiles while retaining disputed attributes; never stage a database."""
import argparse
import json
import statistics
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'src'))
from fm27.common import read_csv, sha256, write_csv, write_json
from fm27.rating_calibration import attributes_for_variant, calibrated_level, family, holdout

p = argparse.ArgumentParser()
for name in ('binary', 'blocks', 'source-plan', 'calibrated-plan', 'alternatives-report', 'output'):
    p.add_argument('--' + name, type=Path, required=True)
a = p.parse_args()
if a.output.exists():
    raise ValueError('A new field-retention experiment directory is required')

def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))

evidence = {}
def bind(path, digest=None):
    path = path.resolve()
    if not path.is_relative_to(root):
        raise ValueError('Input is outside project')
    actual = sha256(path)
    if digest is not None and actual != digest:
        raise ValueError('Changed input: ' + str(path))
    evidence[path.relative_to(root).as_posix()] = actual

source_manifest = read(a.source_plan.with_suffix('.manifest.json'))
calibration = read(a.calibrated_plan.with_suffix('.manifest.json'))
prior = read(a.alternatives_report)
blocks = read(a.blocks / 'BLOCKS.json')
native = read(root / 'reports/local/NATIVE_TESTS.json')
build = read(a.binary.with_suffix('.exe.build.json'))
if calibration['status'] != 'CALIBRATED_NATIVE_PLAN_GATES_PASS_NOT_WRITTEN':
    raise ValueError('Passed frozen calibration required')
if (prior['status'] != 'NATIVE_CALIBRATION_ALTERNATIVES_PASS'
        or calibration['source_plan_sha256'] != source_manifest['plan_sha256']
        or prior['plan_sha256'] != source_manifest['plan_sha256']):
    raise ValueError('Source and native calibration are not bound together')
if (native['status'] != 'PASS' or native['tests'] < 123 or build['status'] != 'PASS'
        or native['binary_sha256'] != build['binary_sha256']
        or native['source_sha256'] != build['source_sha256']):
    raise ValueError('Tested native batch build required')
bind(a.binary, native['binary_sha256'])
bind(a.source_plan, source_manifest['plan_sha256'])
bind(a.calibrated_plan, calibration['plan_sha256'])
bind(a.blocks / 'players.csv', blocks['index_sha256'])
prior_path = Path(prior['alternatives_path'])
bind(prior_path, prior['alternatives_sha256'])
for inputs in (calibration['evidence_sha256'], source_manifest['evidence_sha256'], build['source_sha256']):
    for name, digest in inputs.items():
        bind(root / name, digest)
for path in (a.source_plan.with_suffix('.manifest.json'), a.calibrated_plan.with_suffix('.manifest.json'),
             a.alternatives_report, a.blocks / 'BLOCKS.json', a.binary.with_suffix('.exe.build.json'),
             root / 'reports/local/NATIVE_TESTS.json', Path(__file__)):
    bind(path)

baseline_path = root / 'data/generated/native-rating-baseline-20260908-01/native_ratings.csv'
baseline_report = read(root / 'reports/local/NATIVE_RATING_BASELINE_INSPECTION_01.json')
# This exact baseline is already bound by the source/calibration evidence.
key = baseline_path.relative_to(root).as_posix()
expected_baseline = evidence.get(key)
if expected_baseline is None:
    raise ValueError('Source manifest does not bind the baseline inspection')
bind(baseline_path, expected_baseline)
baseline = {r['fm_id']: r for r in read_csv(baseline_path)}
source_rows = read_csv(a.source_plan)
source = {r['fm_id']: r for r in source_rows}
approved_rows = read_csv(a.calibrated_plan)
approved = {r['fm_id']: r for r in approved_rows}
cohort = {r['fm_id']: r for r in source_manifest['cohort']}
diagnostics = {r['fm_id']: r for r in calibration['diagnostics']}
fields = list(source_rows[0])[6:-4]
if len(fields) != 37 or len(source) != len(source_rows) or set(source) != set(cohort):
    raise ValueError('Source cohort schema/identity mismatch')
eligible = {r['fm_id'] for r in calibration['holds']
            if r['reasons'] == ['EXTREME_SOURCE_PROFILE_REVIEW']}
if not eligible or eligible & set(approved):
    raise ValueError('Eligible field review overlaps approved profiles')
retained = {}
masked_rows = []
for row in source_rows:
    ident = row['fm_id']
    masked = dict(row)
    if ident in eligible:
        old = baseline[ident]
        if family(cohort[ident]['native_position']) != family(cohort[ident]['source_position']):
            raise ValueError('Position-conflicting person cannot enter attribute-only review')
        disputed = [f for f in fields if abs(int(row[f]) - int(old[f])) > 35]
        if not disputed:
            raise ValueError('Review entry lacks an actual disputed attribute')
        retained[ident] = {f: dict(native=int(old[f]), source=int(row[f])) for f in disputed}
        masked.update({f: old[f] for f in disputed})
    masked_rows.append(masked)
masked = {r['fm_id']: r for r in masked_rows}
a.output.mkdir(parents=True)
source_output = a.output / 'masked-source-preview.csv'
write_csv(source_output, list(source_rows[0]), masked_rows)
native_output = a.output / 'native'
result = subprocess.run([str(a.binary.resolve()), '--evaluate-rating-blocks', str(a.blocks.resolve()),
                         str(source_output.resolve()), str(native_output.resolve())], cwd=root)
if result.returncode:
    raise RuntimeError('Native field-retention experiment failed')
alternatives_path = native_output / 'native_rating_alternatives.csv'
alternatives = read_csv(alternatives_path)
old_alternatives = read_csv(prior_path)
def variant_key(row):
    return tuple(row[k] for k in ('fm_id', 'variant', 'source_percent', 'offset', 'attribute_cap'))
previous = {variant_key(r): r for r in old_alternatives}
current = {variant_key(r): r for r in alternatives}
if (set(previous) != set(current) or len(current) != len(alternatives)
        or set(Counter(r['fm_id'] for r in alternatives).values()) != {52}):
    raise ValueError('Native variant coverage differs')
if any(row != previous[key] for key, row in current.items() if row['fm_id'] not in eligible):
    raise ValueError('Unchanged source profile produced different native alternatives')
direct = {r['fm_id']: int(r['level13']) for r in alternatives if r['variant'] == 'DIRECT'}
grid = defaultdict(list)
for row in alternatives:
    if row['variant'] == 'CALIBRATION_GRID' and row['source_percent'] == '75':
        grid[row['fm_id']].append(row)

reviews = []
partial_rows = []
selected_levels = {i: int(r['expected_level13']) for i, r in approved.items()}
for ident in sorted(eligible, key=int):
    old = baseline[ident]
    row = masked[ident]
    role = family(cohort[ident]['native_position'])
    # Keep the existing fitted model and identity split frozen. The changed
    # detailed input is evaluated by the native function before using that scale.
    target = calibrated_level(calibration['models'][role], direct[ident])
    best = min(grid[ident], key=lambda r: (abs(int(r['level13']) - target),
                                        abs(int(r['offset'])), int(r['source_squared_distance'])))
    old_attrs = {f: int(old[f]) for f in fields}
    source_attrs = {f: int(row[f]) for f in fields}
    attrs = attributes_for_variant(old_attrs, source_attrs, 75, int(best['offset']))
    deltas = [abs(attrs[f] - old_attrs[f]) for f in fields]
    if (max(deltas) != int(best['max_attribute_delta'])
            or sum(d > 0 for d in deltas) != int(best['changed_attributes'])
            or sum((attrs[f] - source_attrs[f]) ** 2 for f in fields) != int(best['source_squared_distance'])
            or any(attrs[f] != old_attrs[f] for f in retained[ident])):
        raise ValueError('Materialized partial profile differs from native variant or retained fields')
    level = int(best['level13'])
    shift = level - int(old['level13'])
    reasons = []
    if abs(shift) > 6:
        reasons.append('LARGE_LEVEL_CHANGE_REVIEW')
    if abs(level - target) > 1:
        reasons.append('TARGET_NOT_REACHABLE_WITH_PROFILE_LIMITS')
    if not any(deltas):
        reasons.append('NO_ATTRIBUTE_CHANGE')
    review = dict(fm_id=ident, fifa_id=row['fifa_id'], name=cohort[ident]['name'],
                  family=role, league=cohort[ident]['target_league'], holdout=holdout(row['fifa_id']),
                  level_before=int(old['level13']), level_direct=direct[ident],
                  target_level=round(target, 3), selected_level=level, level_delta=shift,
                  offset=int(best['offset']), max_attribute_delta=max(deltas),
                  retained_fields=retained[ident], unresolved_fields=len(retained[ident]),
                  remaining_profile_reasons=reasons, source=row['source'], source_sha256=row['source_sha256'])
    reviews.append(review)
    if not reasons:
        # Not a stageable plan: the report status and the absence of a calibrated
        # plan manifest require a separate explicit review/integration step.
        partial_rows.append({**row, 'expected_level13': str(level), **{f: str(v) for f, v in attrs.items()}})
        selected_levels[ident] = level

holdout_checks = {}
for role in sorted(calibration['models']):
    ids = [i for i in selected_levels if family(cohort[i]['native_position']) == role and holdout(cohort[i]['fifa_id'])]
    shifts = [selected_levels[i] - int(baseline[i]['level13']) for i in ids]
    passed = len(shifts) >= 20 and abs(statistics.mean(shifts)) <= 2 and abs(statistics.median(shifts)) <= 1.5
    holdout_checks[role] = dict(status='PASS' if passed else 'REVIEW_REQUIRED', players=len(shifts),
                                mean_shift=round(statistics.mean(shifts), 3), median_shift=statistics.median(shifts))
league_checks = {}
for league in sorted({r['target_league'] for r in cohort.values()}):
    ids = [i for i in cohort if cohort[i]['target_league'] == league]
    shift = statistics.mean(selected_levels.get(i, int(baseline[i]['level13'])) - int(baseline[i]['level13']) for i in ids)
    league_checks[league] = dict(status='PASS' if abs(shift) <= 2 else 'REVIEW_REQUIRED', mean_shift=round(shift, 3))
before_levels = sorted((int(r['level13']) for r in baseline.values()), reverse=True)
after_levels = sorted((selected_levels.get(i, int(r['level13'])) for i, r in baseline.items()), reverse=True)
before85 = sum(v >= 85 for v in before_levels)
after85 = sum(v >= 85 for v in after_levels)
before90 = sum(v >= 90 for v in before_levels)
after90 = sum(v >= 90 for v in after_levels)
inflation = dict(status='PASS' if after85 <= max(before85 + 25, int(before85 * 1.25))
                 and after90 <= before90 + 10 and after_levels[0] <= before_levels[0] + 1 else 'REVIEW_REQUIRED',
                 at85_before=before85, at85_after=after85, at90_before=before90, at90_after=after90,
                 maximum_before=before_levels[0], maximum_after=after_levels[0],
                 top10_mean=statistics.mean(after_levels[:10]), top500_mean=statistics.mean(after_levels[:500]))
partial_output = a.output / 'partial-profile-proposals.csv'
write_csv(partial_output, list(source_rows[0]), partial_rows)
passed = all(v['status'] == 'PASS' for v in (*holdout_checks.values(), *league_checks.values(), inflation))
write_json(a.output / 'FIELD_RETENTION_REVIEW.json', dict(
    status='NATIVE_FIELD_RETENTION_EXPERIMENT_GATES_PASS' if passed else 'FIELD_RETENTION_EXPERIMENT_REVIEW_REQUIRED',
    reviewed_players=len(eligible), partial_proposal_players=len(partial_rows),
    remaining_full_profile_holds=len(eligible) - len(partial_rows),
    unresolved_attribute_cases=sum(len(v) for v in retained.values()),
    field_counts=dict(Counter(f for fields_by_person in retained.values() for f in fields_by_person)),
    original_approved_players=len(approved), original_approved_rows_unchanged=True,
    unchanged_native_variants=sum(r['fm_id'] not in eligible for r in alternatives),
    native_evaluated_alternatives=len(alternatives), frozen_models=calibration['models'],
    holdout_checks=holdout_checks, league_checks=league_checks, inflation_check=inflation,
    reviews=reviews, evidence_sha256=evidence,
    output_sha256={source_output.name: sha256(source_output), partial_output.name: sha256(partial_output),
                   'native/native_rating_alternatives.csv': sha256(alternatives_path)},
    release_ready=False, ratings_written_to_database=False,
    limitations='Retained disputed fields remain unresolved. This partial-profile experiment is not a stageable plan. '
                'Models, holdout identities and limits are frozen. Aggregate checks measure scale drift, not football truth. '
                'Existing 3009 approved rating rows are not altered; a later integration requires full native roundtrip.'))
print(json.dumps(dict(status='PASS' if passed else 'REVIEW_REQUIRED', reviewed=len(eligible),
                      partial_proposals=len(partial_rows), unresolved_attributes=sum(len(v) for v in retained.values()),
                      holdout=holdout_checks, inflation=inflation)))
