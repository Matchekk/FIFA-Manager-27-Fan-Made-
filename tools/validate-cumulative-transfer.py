"""Bind a native transfer increment to an already validated combined rating candidate."""
import argparse
import datetime as dt
import json
import sys
from collections import Counter
from pathlib import Path

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'src'))
from fm27.common import read_csv,sha256,write_json
from fm27.world_validation import compare_world,compare_global
from fm27.transfer_rating_validation import planned_squad_flags

p=argparse.ArgumentParser()
for name in ('source-validation','source-archive','increment-validation','inspection','reread','plan','output'):
    p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args()
if a.output.exists(): raise ValueError('New cumulative candidate validation required')
bound={}
def verify(path,digest=None):
    path=path.resolve(); actual=sha256(path)
    if digest is not None and actual!=digest: raise ValueError('Bound input changed: '+str(path))
    bound[str(path)]=actual
    return actual
def read(path):
    verify(path)
    return json.loads(path.read_text(encoding='utf-8'))

source_proof=read(a.source_validation)
archive=read(a.source_archive/'EVIDENCE.json')
increment=read(a.increment_validation)
manifest=read(a.plan.with_suffix('.manifest.json'))
source=Path(source_proof['candidate'])
candidate=Path(increment['candidate'])
stage=read(candidate/'NATIVE_BUILD_INPUTS.json')
inspection=read(a.inspection/'NATIVE_BUILD_INPUTS.json')
plan=read_csv(a.plan); verify(a.plan,manifest['plan_sha256'])
if (source_proof['status']!='NATIVE_RATINGS_PASS_GAME_GATES_OPEN'
    or any(v['status']!='PASS' for v in source_proof['checks'].values())
    or archive['status']!='FROZEN_NATIVE_PARTIAL_RATINGS_PASS_GAME_GATES_OPEN'
    or archive['candidate']!=source_proof['candidate']
    or archive['candidate_database_files_sha256']!=source_proof['candidate_database_files_sha256']):
    raise ValueError('Complete frozen source rating proof required')
relative_proof=a.source_validation.resolve().relative_to(root).as_posix()
if archive['files_sha256'].get(relative_proof)!=sha256(a.source_validation):
    raise ValueError('Source archive does not bind this validation')
for name,digest in archive['files_sha256'].items():
    path=(a.source_archive/name).resolve()
    if not path.is_relative_to(a.source_archive.resolve()): raise ValueError('Archive path escapes evidence root')
    verify(path,digest)
for name,digest in source_proof['candidate_database_files_sha256'].items():
    verify(source/'database'/name,digest)
if (increment['player_validation']!='PASS' or increment['extended_native_validation']!='PASS'
    or increment['native_support_validation']!='PASS' or increment['expanded_world_validation']['status']!='PASS'
    or increment['gates']['I_AUTOMATED_TESTS']!='PASS' or increment['plan_sha256']!=sha256(a.plan)
    or manifest['source_native_validation_sha256']!=sha256(a.source_validation)
    or manifest['source_evidence_manifest_sha256']!=sha256(a.source_archive/'EVIDENCE.json')
    or Path(manifest['source_database']).resolve()!=(source/'database').resolve()
    or Path(stage['source_database']).resolve()!=(source/'database').resolve()
    or Path(inspection['source_database']).resolve()!=(source/'database').resolve()
    or stage['plan_sha256']!=sha256(a.plan) or inspection['plan_sha256']!=sha256(a.plan)
    or not stage['immutable_inputs_unchanged'] or not inspection['immutable_inputs_unchanged']):
    raise ValueError('Transfer increment/source provenance differs')
for name,digest in manifest['evidence_sha256'].items(): verify(root/name,digest)
for name,digest in increment['candidate_database_files'].items(): verify(candidate/name,digest)
for name,digest in manifest['source_files_sha256'].items(): verify(source/name,digest)
checks={}
def counter(path,fields):
    verify(path)
    rows=read_csv(path)
    return Counter(tuple(r[f] for f in fields) for r in rows)
def equal(name,left,right):
    checks[name]=dict(status='PASS' if left and left==right else 'FAIL',
                     expected=left.total(),actual=right.total(),missing=(left-right).total(),added=(right-left).total())

player_fields=('fifa_id','dob','name','club_id','serialized_sha256')
before=a.inspection/'before-plan'
equal('source_player_state_exact',counter(source/'native_player_semantics.csv',player_fields),
      counter(before/'native_player_semantics.csv',player_fields))
equal('independent_inspection_matches_candidate',counter(a.inspection/'native_player_semantics.csv',player_fields),
      counter(candidate/'native_player_semantics.csv',player_fields))
equal('complete_candidate_player_reread',counter(candidate/'native_player_semantics.csv',player_fields),
      counter(a.reread/'native_player_semantics.csv',player_fields))
source_ratings=source/'native_ratings.csv'
rating_rows=read_csv(source_ratings)
# Every rating/position/style/talent field, including native computed levels,
# must be identical across the transfer. Club and full hashes intentionally
# change with an approved contract/club move; person IDs can renumber on reread.
rating_fields=[f for f in rating_rows[0] if f not in {'fm_id','club_id','serialized_sha256','protected_sha256','in_reserve','in_youth'}]
equal('all_prior_rating_profiles_and_levels_unchanged',counter(source_ratings,rating_fields),
      counter(candidate/'native_ratings.csv',rating_fields))
equal('all_rating_profiles_and_levels_reread',counter(candidate/'native_ratings.csv',rating_fields),
      counter(a.reread/'native_ratings.csv',rating_fields))
# A reviewed transfer from reserves to a first team must update squad flags while
# retaining every rating field. Validate all memberships against the exact plan,
# rather than ignoring flags or requiring an obsolete reserve assignment.
source_reread=Path(source_proof['reread'])
baseline_ratings=source_reread/'native_ratings.csv'
baseline_semantics=source_reread/'native_player_semantics.csv'
for path in (baseline_ratings,baseline_semantics):
    key=path.resolve().relative_to(root).as_posix()
    digest=archive['files_sha256'].get(key)
    if not digest: raise ValueError('Source archive must bind native reread baseline')
    verify(path,digest)
equal('squad_baseline_native_ids_and_full_state_exact',
      counter(baseline_semantics,('fm_id',)+player_fields),
      counter(before/'native_player_semantics.csv',('fm_id',)+player_fields))
if checks['squad_baseline_native_ids_and_full_state_exact']['status']!='PASS':
    raise ValueError('Squad baseline native identities differ from inspected source')
checks['only_planned_squad_flags_changed']=planned_squad_flags(
    read_csv(baseline_ratings),read_csv(candidate/'native_ratings.csv'),plan)
flag_fields=('fifa_id','dob','name','club_id','in_reserve','in_youth')
equal('all_squad_flags_reread',counter(candidate/'native_ratings.csv',flag_fields),
      counter(a.reread/'native_ratings.csv',flag_fields))
checks['source_club_country_metadata_exact']=compare_world(source,before,metadata_only=True)
checks['source_globals_exact']=compare_global(source,before)
scripts={str(p.relative_to(source/'database')):sha256(p)
         for p in (source/'database/script').glob('CountryScript*.sav')}
actual_scripts={str(p.relative_to(candidate/'database')):sha256(p)
                for p in (candidate/'database/script').glob('CountryScript*.sav')}
checks['all_competition_scripts_unchanged']=dict(status='PASS' if len(scripts)==207 and scripts==actual_scripts else 'FAIL',
                                               scripts=len(scripts))
for name,digest in scripts.items():
    verify(source/'database'/name,digest)
    verify(candidate/'database'/name,digest)
verify(Path(__file__))
failed=[k for k,v in checks.items() if v['status']!='PASS']
if failed: raise ValueError('Cumulative preservation failed: '+repr(failed))
write_json(a.output,dict(status='NATIVE_CUMULATIVE_TRANSFER_RATINGS_PASS_GAME_GATES_OPEN',
    validated_at=dt.datetime.now(dt.timezone.utc).isoformat(),candidate=str(candidate.resolve()),
    source_candidate=str(source.resolve()),source_validation_sha256=sha256(a.source_validation),
    source_evidence_manifest_sha256=sha256(a.source_archive/'EVIDENCE.json'),
    increment_validation_sha256=sha256(a.increment_validation),increment_plan_sha256=sha256(a.plan),
    increment_changed_players=increment['actual_changed_players'],increment_club_changes=increment['club_changes'],
    inherited_rating_players=source_proof['changed_players'],inherited_rating_attributes=source_proof['changed_attributes'],
    inherited_partial_profiles=archive['partial_profiles'],
    retained_disputed_attributes=archive['disputed_native_attributes_unchanged'],
    native_reread_players=increment['native_reread_players'],checks=checks,bound_files_sha256=bound,
    candidate_files_sha256=increment['candidate_database_files'],release_ready=False,
    limitations='Preserves the full prior native rating world and exact competition scripts while applying only the validated transfer increment. '
        'Prior league formats, transfer coverage, rating review holds, file coverage, editor export and game/release gates remain open.'))
print(json.dumps(dict(status='PASS',increment_players=increment['actual_changed_players'],
    inherited_rating_players=source_proof['changed_players'],checks=len(checks))))
