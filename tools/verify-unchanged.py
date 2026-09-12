"""Re-hash inventoried executables, plugins, configs and database files."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fm27.common import read_csv, sha256, write_json

parser = argparse.ArgumentParser()
parser.add_argument("--game-root", type=Path, required=True)
parser.add_argument("--manifest", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
changed, verified = [], 0
root = args.game_root.resolve(strict=True)
for row in read_csv(args.manifest):
    if not row["sha256"]:
        continue
    path = (root / row["path"]).resolve()
    if not path.is_relative_to(root):
        raise ValueError("Manifest escapes installation")
    if not path.is_file() or sha256(path) != row["sha256"]:
        changed.append(row["path"])
    else:
        verified += 1
report = {"verified_hashes": verified, "changed_or_missing": changed,
          "scope": "original inventoried relevant files; not a scan for newly added files"}
write_json(args.output, report)
print(json.dumps(report))
sys.exit(bool(changed))
