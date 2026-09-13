"""Read-only candidate smoke selection and exclusive, verified save/config backup."""
import csv
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r'C:\FM27CommunityOverhaul')
LOCAL = ROOT / 'reports/local'
EVIDENCE = LOCAL / 'native08-20260912-evidence'
SAVES = Path(r'C:\Users\Matej Uni\Documents\FM\Data\SaveGames')
CONFIG = SAVES.parents[1] / 'Config'
RUNTIME = ROOT / 'runtime/game-test-20260912-07'
ORIGINAL = Path(r'C:\Fifa Manager 13\FUSSBALL MANAGER 13')

def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def write(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write('\n')

def select(path, ids):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return {r['fm_id']: r for r in csv.DictReader(stream) if r['fm_id'] in ids}

def match_baseline(path, candidate):
    # Serialization renumbers FM IDs: never join different exports on FM ID.
    matches = {key: [] for key in candidate}
    with path.open(encoding='utf-8-sig', newline='') as stream:
        for row in csv.DictReader(stream):
            for key, player in candidate.items():
                if row['dob'] == player['dob'] and row['name'] == player['name']:
                    matches[key].append(row)
    for key, rows in matches.items():
        if len(rows) != 1:
            raise ValueError(f'Baseline identity ambiguous or missing: {candidate[key]["name"]}')
    return {key: rows[0] for key, rows in matches.items()}

def main():
    EVIDENCE.mkdir(parents=True, exist_ok=False)
    preflight = {'created_utc': datetime.now(timezone.utc).isoformat(),
                 'saves': [], 'config': [], 'runtime': str(RUNTIME),
                 'autosave_disabled': None, 'simulation_authorized_by_gate': False}
    for label, directory in [('saves', SAVES), ('config', CONFIG)]:
        destination = EVIDENCE / (label + '-baseline')
        destination.mkdir()
        for source in sorted(directory.rglob('*')):
            if not source.is_file():
                continue
            relative = source.relative_to(directory)
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            before = digest(source)
            shutil.copy2(source, target)
            assert before == digest(target) == digest(source), str(source)
            preflight[label].append({'relative_path': str(relative), 'bytes': source.stat().st_size,
                                     'sha256': before, 'backup': str(target)})
    preflight['bound_files'] = []
    for root in [ORIGINAL, RUNTIME]:
        for relative in ['Manager.exe', 'database/Master.dat', 'season.ini']:
            path = root / relative
            if path.is_file():
                preflight['bound_files'].append({'path': str(path), 'bytes': path.stat().st_size,
                                                'sha256': digest(path)})
    preflight['integrity_scope'] = 'All shared saves/config backed up; original/runtime identity files hashed. Full-install comparison not yet performed.'
    write(EVIDENCE / 'preflight.json', preflight)
    ids = {'287889', '222419', '23675'}
    candidate_path = ROOT / 'data/generated/native-reread-increment-20260909-07/native_players.csv'
    baseline_path = ROOT / 'data/generated/native-baseline-semantic-20260908-01/native_players.csv'
    rating_path = candidate_path.with_name('native_ratings.csv')
    plan_path = ROOT / 'data/generated/transfer-increment-plan-20260909-07.csv'
    candidate, ratings, plan = [select(p, ids) for p in [candidate_path, rating_path, plan_path]]
    baseline = match_baseline(baseline_path, candidate)
    records = []
    for player_id in ['287889', '222419', '23675']:
        c, b, p, rating = candidate[player_id], baseline[player_id], plan[player_id], ratings[player_id]
        assert c['club_id'] == p['new_club_id']
        record = {'identity': c['name'], 'dob': c['dob'], 'fm_id': player_id, 'fifa_id': c['fifa_id'],
                  'role': 'loan' if p['loan_owner_club_id'] != '0' else 'permanent_transfer',
                  'baseline': b, 'native07': c,
                  'expected_contract': p['contract_until'], 'expected_shirt_number': int(p['shirt_number']),
                  'expected_loan': {'owner_club_id': p['loan_owner_club_id'], 'end': p['loan_end'] or None},
                  'profile_indicators': {k: rating[k] for k in ['main_position', 'style', 'level13', 'BallControl', 'Dribbling', 'Finishing', 'Acceleration', 'Pace']},
                  'baseline_contract': None, 'baseline_shirt_number': None,
                  'evidence_source': [str(candidate_path), str(baseline_path), str(rating_path), str(plan_path)],
                  'frozen_plan_row': p,
                  'baseline_field_limit': 'Null fields not available in the compact semantic export; do not infer them.',
                  'direct_career_observation': None}
        if player_id == '287889':
            record.update(baseline_contract='2026-06-30', baseline_shirt_number=11,
                          baseline_club_name='CF Estrela Amadora', native07_club_name='Grêmio Porto Alegre',
                          role='permanent_transfer_and_adopted_profile_reference')
            record['evidence_source'].append(str(LOCAL / 'RUNTIME_SMOKE_NATIVE07_20260912_04.json'))
        records.append(record)
    write(LOCAL / 'native08-smoke-player-manifest.json', {
        'selection': 'Fixed three identities: Cabral Editor/profile reference, Alysson permanent transfer, Amissah loan ending 2027-06-30.',
        'rating_limit': 'Adopted profile expected; no separate baseline-to-candidate rating-change claim without baseline attributes.',
        'sources_sha256': {str(p): digest(p) for p in [candidate_path, baseline_path, rating_path, plan_path]},
        'players': records})
    print(json.dumps({'backup_verified': True, 'save_count': len(preflight['saves']),
                      'config_count': len(preflight['config']), 'players': [r['identity'] for r in records]}, ensure_ascii=False))

if __name__ == '__main__':
    main()
