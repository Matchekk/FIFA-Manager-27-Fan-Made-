import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fm27.squad_compare import compare

parser = argparse.ArgumentParser(description="Review official FPL squads against an installed identity export")
parser.add_argument("--export", type=Path, required=True)
parser.add_argument("--source", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("--aliases", type=Path, default=Path(__file__).resolve().parents[1] / "config/fpl-club-aliases.json")
args = parser.parse_args()
print(json.dumps(compare(args.export, args.source, args.aliases, args.output), ensure_ascii=False))
