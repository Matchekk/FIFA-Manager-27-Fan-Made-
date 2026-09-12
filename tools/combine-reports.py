"""Publish combined review CSVs with explicit incomplete competition coverage."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fm27.common import read_csv, write_csv, write_json
from fm27.squad_compare import FIELDS

root = Path(__file__).resolve().parents[1]
reports = root / "reports"
current = reports / "local/current"
if (current / "RECONCILIATION.json").exists():
    current_meta=json.loads((current / "RECONCILIATION.json").read_text(encoding="utf-8"))
    for name in ("TRANSFER_DIFF.csv", "UNMATCHED_PLAYERS.csv", "AMBIGUOUS_MATCHES.csv"):
        rows=read_csv(current / name)
        with (current / name).open(encoding="utf-8-sig",newline="") as stream:
            fields=next(__import__('csv').reader(stream))
        if any(r["source_date"]!=current_meta["DATABASE_SNAPSHOT_DATE"] for r in rows):
            raise ValueError("Mixed current reconciliation snapshot")
        write_csv(reports / name,fields,rows)
    write_json(reports / "TRANSFER_COVERAGE.json",{
        "DATABASE_SNAPSHOT_DATE":current_meta["DATABASE_SNAPSHOT_DATE"],
        "coverage":current_meta["coverage"],"source_failures":current_meta["source_failures"],
        "status":"12_LEAGUE_CAPTURE_RECONCILIATION_INCOMPLETE","production_writes":0,
        "departure_report":"DEPARTURE_RECONCILIATION.csv","coverage_matrix":"TRANSFER_COVERAGE_MATRIX.csv",
        "limitations":"Fetched squads are not completed transfer coverage. See separate departure, loan and identity holds."})
    print("Published current twelve-league reconciliation; no production write")
    sys.exit(0)
sources = [reports / "local/premier-league", reports / "local/germany"]
metadata = [json.loads((p / "SQUAD_COMPARISON.json").read_text(encoding="utf-8")) for p in sources]
dates = {m["DATABASE_SNAPSHOT_DATE"] for m in metadata}
if len(dates) != 1:
    raise ValueError("Mixed snapshot dates: refresh sources before combining")
for name in ("TRANSFER_DIFF.csv", "UNMATCHED_PLAYERS.csv", "AMBIGUOUS_MATCHES.csv"):
    rows = [r for p in sources for r in read_csv(p / name)]
    fields = FIELDS + sorted({k for r in rows for k in r} - set(FIELDS))
    write_csv(reports / name, fields, rows)
write_json(reports / "TRANSFER_COVERAGE.json", {
    "DATABASE_SNAPSHOT_DATE": dates.pop(), "status": "INCOMPLETE_REVIEW_ONLY_NO_PRODUCTION_DATABASE",
    "roster_evidence": {"ENG1": 20, **metadata[1]["coverage"]},
    "missing_competitions": ["ITA1", "ESP1", "FRA1", "POR1", "NED1", "BEL1", "TUR1", "CZE1"],
    "source_failures": metadata[1]["source_failures"], "production_writes": 0,
    "limitations": "Roster associations do not certify transfer type, owner, contract or complete departures. All changes require further evidence."})
print("Combined review reports created; no game database changed")
