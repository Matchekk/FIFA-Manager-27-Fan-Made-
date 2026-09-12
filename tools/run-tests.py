"""Run the existing Python suite and write evidence tied to exact local code."""
import datetime as dt
import json
import sys
import unittest
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "src"))
from fm27.common import sha256, write_json

suite = unittest.defaultTestLoader.discover(str(root / "tests"))
result = unittest.TextTestRunner(verbosity=2).run(suite)
report = {"status": "PASS" if result.wasSuccessful() else "FAIL", "tests": result.testsRun,
          "errors": len(result.errors), "failures": len(result.failures), "skipped": len(result.skipped),
          "run_at": dt.datetime.now(dt.timezone.utc).isoformat(),
          "source_sha256": {str(p.relative_to(root)): sha256(p) for folder in (root / "src/fm27", root / "tests")
                            for p in sorted(folder.glob("*.py"))},
          "scope": "Python automated tests only; native tests and engine tests have separate reports"}
write_json(root / "reports/local/AUTOMATED_TESTS.json", report)
print(json.dumps({k: v for k, v in report.items() if k != "source_sha256"}))
sys.exit(not result.wasSuccessful())
