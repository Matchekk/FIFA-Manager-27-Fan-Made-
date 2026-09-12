"""Publish combined review CSVs with explicit incomplete competition coverage."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fm27.common import read_csv, write_csv, write_json
from fm27.squad_compare import FIELDS

root = Path(__file__).resolve().parents[1]
reports = root / "reports"
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
