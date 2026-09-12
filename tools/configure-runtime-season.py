"""Select the existing TheSeason start-year setting only in a verified test copy."""
import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fm27.common import sha256, write_json

p = argparse.ArgumentParser()
p.add_argument("--runtime", type=Path, required=True)
p.add_argument("--copy-report", type=Path, required=True)
p.add_argument("--year", type=int, required=True)
p.add_argument("--output", type=Path, required=True)
a = p.parse_args()
project = Path(__file__).resolve().parents[1]
runtime = a.runtime.resolve()
if not runtime.is_relative_to(project / "runtime") or a.output.exists() or not 2010 <= a.year < 2090:
    raise ValueError("Require a new report, external runtime tree and supported modern start year")
copy = json.loads(a.copy_report.read_text(encoding="utf-8"))
if copy.get("status") != "PHYSICAL_RUNTIME_COPY_VERIFIED_EDITOR_EXPORT_REQUIRED" or Path(copy["destination"]) != runtime:
    raise ValueError("Runtime copy has not completed with exact file verification")
path = runtime / "plugins/season.ini"
before_hash = sha256(path)
if before_hash != copy["files"]["plugins/season.ini"]["sha256"]:
    raise ValueError("The copied season configuration has already changed")
before = path.read_bytes()
pattern = rb"(?m)^([ \t]*SEASON_START_YEAR[ \t]+)\d{4}([ \t]*\r?$)"
after, count = re.subn(pattern, rb"\g<1>" + str(a.year).encode("ascii") + rb"\g<2>", before)
if count != 1:
    raise ValueError("Missing or ambiguous TheSeason start-year setting")
path.write_bytes(after)
if path.read_bytes() != after:
    raise ValueError("Runtime season configuration readback failed")
report = {"status": "EXTERNAL_RUNTIME_CONFIGURED_NOT_GAME_VALIDATED", "runtime": str(runtime),
          "start_year": a.year, "before_sha256": before_hash, "after_sha256": sha256(path),
          "plugin_sha256": sha256(runtime / "plugins/TheSeason.asi"),
          "copy_report_sha256": sha256(a.copy_report), "configured_at": dt.datetime.now(dt.timezone.utc).isoformat(),
          "basis": "Pinned TheSeason source reads SEASON_START_YEAR from plugins/season.ini; installed plugin contains this setting name. Verify actual date in the editor/game.",
          "original_installation_changed": False, "release_ready": False}
write_json(a.output, report)
print(json.dumps(report))
