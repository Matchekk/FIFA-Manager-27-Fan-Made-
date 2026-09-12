"""Compare projected player semantics after native ID renumbering.

This is a validation gate, not full database/relationship certification.
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fm27.common import read_csv, write_json

parser = argparse.ArgumentParser()
parser.add_argument("--before", type=Path, required=True)
parser.add_argument("--after", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
before = read_csv(args.before / "players.csv")
after = read_csv(args.after / "players.csv")
if not before or not after or before[0].keys() != after[0].keys():
    raise ValueError("Missing players or incompatible projection schema")
fields = [f for f in before[0] if f not in {"fm_id", "source_file", "source_line"}]
old = Counter(tuple(p[f] for f in fields) for p in before)
new = Counter(tuple(p[f] for f in fields) for p in after)
def table_equal(name):
    a, b = read_csv(args.before / name), read_csv(args.after / name)
    if not a or not b or a[0].keys() != b[0].keys():
        return False
    return Counter(tuple(sorted(r.items())) for r in a) == Counter(tuple(sorted(r.items())) for r in b)
club_equal = table_equal("clubs.csv")
teams_equal = table_equal("covered_teams.csv")
report = {"status": "PROJECTED_SEMANTICS_EQUAL" if old == new and club_equal and teams_equal else "FAILED",
          "players_before": len(before), "players_after": len(after), "fields_compared": fields,
          "unmatched_before": sum((old-new).values()), "unmatched_after": sum((new-old).values()),
          "club_projections_equal": club_equal, "covered_team_projections_equal": teams_equal,
          "examples_before": [dict(zip(fields, row)) for row in list(old-new)[:10]],
          "examples_after": [dict(zip(fields, row)) for row in list(new-old)[:10]],
          "id_note": "Canonical writer recalculates person IDs. Compare semantic multisets, not old numeric IDs.",
          "limitations": "Projection only. Staff, finances, histories, person relations, competition rules, Master.dat and in-game/save behavior remain unvalidated. Not authorized for production installation."}
write_json(args.output, report)
print(json.dumps(report))
sys.exit(report["status"] == "FAILED")
