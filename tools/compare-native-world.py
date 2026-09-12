"""Read-only comparison of expanded native world exports."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fm27.common import write_json
from fm27.world_validation import compare_world, compare_global

p = argparse.ArgumentParser()
p.add_argument("--expected", type=Path, required=True)
p.add_argument("--actual", type=Path, required=True)
p.add_argument("--metadata-only", action="store_true")
p.add_argument("--global-only", action="store_true")
p.add_argument("--output", type=Path, required=True)
a = p.parse_args()
if a.global_only and a.metadata_only:
    raise ValueError("Choose either global objects or club/country metadata")
report = compare_global(a.expected, a.actual) if a.global_only else compare_world(a.expected, a.actual, metadata_only=a.metadata_only)
write_json(a.output, report)
print(json.dumps(report))
sys.exit(report["status"] != "PASS")
