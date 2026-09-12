"""Isolated transfer-event snapshot for the fixed 12-league production sprint."""
import csv, json, sys, datetime
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from fm27.public_cache import DfbCache
from fm27.transfermarkt import parse_page, LEAGUES

def main():
    out = ROOT / 'data/current/evidence'; out.mkdir(parents=True, exist_ok=True)
    cache = DfbCache(ROOT / 'data/raw/transfermarkt', host='www.transfermarkt.de')
    rows, sources, failures, coverage = [], [], [], {}
    stamp = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    for league, (slug, code) in LEAGUES.items():
        url = f'https://www.transfermarkt.de/{slug}/transfers/wettbewerb/{code}/saison_id/2026'
        try:
            html, source = cache.fetch(url, reuse_today=True)
            batch, clubs = parse_page(html, league)
            if not clubs: raise ValueError('Empty club list')
            for row in batch: row.update(source=url, source_sha256=source['sha256'], snapshot_date=stamp)
            rows.extend(batch); sources.append(source); coverage[league] = dict(clubs=clubs, records=len(batch))
        except Exception as exc:
            failures.append(dict(league=league, source=url, error=str(exc)))
        print(json.dumps(dict(league=league, records=len(rows), failures=len(failures))), flush=True)
    if rows:
        with (out / 'transfer-events.csv').open('w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    (out / 'transfer-capture.json').write_text(json.dumps(dict(snapshot_date=stamp, sources=sources,
        failures=failures, coverage=coverage, records=len(rows)), indent=2), encoding='utf-8')

if __name__ == '__main__': main()
