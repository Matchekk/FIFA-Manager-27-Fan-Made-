"""Prepare two guarded, offline loan-date variants; never alter a runtime."""
from pathlib import Path
from datetime import date
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'data/generated/release-candidate/transfer-increment-20260909-07/database/data'
RUNTIME = ROOT / 'runtime/game-test-20260912-07/database/data'
OUT = ROOT / 'data/generated/native08-loan-date-experiment-02'

def sha(data):
    return hashlib.sha256(data).hexdigest()

def main():
    OUT.mkdir(exist_ok=False)
    observations = []
    start = date(2026, 7, 1).toordinal() + 1721425
    for country, identity, old, owner in [
        (21, b'Mikey|Moore|||0', b'4,2461284,2461587,917521,0,0', 'Tottenham; stable UID 917514, serialized ref 917521'),
        (38, b'Samuel|Amissah|||0', b'4,2461283,2461587,917515,0,0', 'Fulham; stable UID 917521, serialized ref 917515'),
    ]:
        name = f'CountryData{country}.sav'
        source = BASE / name
        candidate_data = source.read_bytes()
        runtime_data = (RUNTIME / name).read_bytes()
        # Editor has rewritten unrelated fields. Preserve the actual Runtime07
        # input and demand byte equality of each selected player with candidate.
        data = runtime_data
        assert data.count(identity) == 1
        pos = data.index(identity)
        end = data.index(b'%INDEXEND%PLAYER', pos)
        block = data[pos:end]
        candidate_pos = candidate_data.index(identity)
        candidate_end = candidate_data.index(b'%INDEXEND%PLAYER', candidate_pos)
        assert block == candidate_data[candidate_pos:candidate_end], 'Selected player differs'
        assert block.count(old) == 1
        new = b'4,' + str(start).encode() + b',' + old.split(b',', 2)[2]
        offset = pos + block.index(old)
        modified = data[:offset] + new + data[offset + len(old):]
        assert modified[:offset] == data[:offset]
        assert modified[offset + len(new):] == data[offset + len(old):]
        assert old.split(b',')[2:] == new.split(b',')[2:]
        dest = OUT / 'variant/database/data' / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(modified)
        line = data[:offset].count(b'\n') + 1
        patch = f'--- a/database/data/{name}\n+++ b/database/data/{name}\n@@ -{line} +{line} @@\n-{old.decode()}\n+{new.decode()}\n'
        (OUT / (name + '.patch')).write_text(patch, encoding='utf-8')
        assert source.read_bytes() == candidate_data and (RUNTIME / name).read_bytes() == runtime_data
        observations.append(dict(player=identity.decode().split('|||')[0], source=str(RUNTIME / name),
            source_sha256=sha(data), variant=str(dest), variant_sha256=sha(modified),
            candidate_sha256=sha(candidate_data), candidate_source=str(source),
            source_line=line, before=old.decode(), after=new.decode(), owner=owner,
            changed_fields=['loan condition start date'], selected_player_candidate_runtime_identical=True))
    report = dict(status='DIAGNOSTIC_VARIANT_PREPARED_NOT_EXPORTED_NOT_TESTED',
        observations=observations, source_modified=False, runtime_modified=False,
        hypothesis='Future-dated current-loan conditions may not initialize as intended at July 1 career start.',
        limits=['This is not a proven fix or a complete candidate database.',
                'Master.dat conditions have not been decoded.',
                'No claim that all 794 loans fail.',
                'Existing career saves cannot validate a changed database export.'],
        experiment=['Use separate physical copy of Runtime07 including its Editor database as baseline.',
                    'Overlay only these two files for variant; export using that isolated Editor.',
                    'Start unique test career and observe explicit loan status at July 1.',
                    'If activation differs from control, cross June 30/July 1 and verify return destinations.',
                    'If unchanged, reject date-only hypothesis; investigate exported condition interpretation.'])
    (OUT / 'EXPERIMENT.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'status': report['status'], 'changed_lines': len(observations)}))

if __name__ == '__main__':
    main()
