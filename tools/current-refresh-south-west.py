"""Capture bounded current-squad evidence without touching inherited staging inputs."""
import csv, json, sys, datetime
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from fm27.public_cache import DfbCache
from fm27.transfermarkt import parse_squad
from fm27.matching import normalize

LEAGUES = {'ITA1', 'FRA1', 'ESP1', 'POR1', 'NED1', 'BEL1', 'TUR1', 'CZE1'}
OUT = ROOT / 'data/current/workers/south-west'

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    metadata = json.loads((ROOT / 'reports/local/TRANSFER_FETCH.json').read_text(encoding='utf-8'))
    cache = DfbCache(ROOT / 'data/raw/transfermarkt', host='www.transfermarkt.de')
    records, sources, failures, clubs = [], [], [], []
    stamp = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    def save():
        for name, rows in [('rosters.csv', records), ('club-capture.csv', clubs)]:
            if rows:
                with (OUT / name).open('w', encoding='utf-8', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
        (OUT / 'capture.json').write_text(json.dumps(dict(snapshot_date=stamp, sources=sources, failures=failures,
            records=len(records), clubs=len(clubs), membership_authority=False), indent=2), encoding='utf-8')
    for league in sorted(LEAGUES):
        for club_id, name in metadata['coverage'][league]['clubs'].items():
            url = f'https://www.transfermarkt.de/{normalize(name).replace(" ", "-")}/kader/verein/{club_id}/saison_id/2026/plus/1'
            try:
                html, source = cache.fetch(url, reuse_today=True)
                batch = parse_squad(html, league, club_id)
                if not batch:
                    raise ValueError('No roster rows parsed')
                for row in batch:
                    row.update(source=url, source_sha256=source['sha256'], snapshot_date=stamp)
                records.extend(batch); sources.append(source)
                clubs.append(dict(league=league, club=name, club_tm_id=club_id, players=len(batch), status='CAPTURED', source=url))
            except Exception as exc:
                failures.append(dict(league=league, club=name, club_tm_id=club_id, source=url, error=str(exc)))
                clubs.append(dict(league=league, club=name, club_tm_id=club_id, players=0, status='BLOCKED', source=url))
            save()
        print(json.dumps(dict(league=league, clubs=len(clubs), records=len(records), failures=len(failures))), flush=True)

if __name__ == '__main__': main()
