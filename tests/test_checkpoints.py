import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fm27.common import write_csv, read_csv


class CheckpointTests(unittest.TestCase):
    def test_failed_checkpoint_preserves_previous_complete_data(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "profiles.csv"
            write_csv(path, ["id"], [{"id": "old"}])
            def interrupted():
                yield {"id": "new"}
                raise RuntimeError("source interrupted")
            with self.assertRaises(RuntimeError):
                write_csv(path, ["id"], interrupted())
            self.assertEqual(read_csv(path), [{"id": "old"}])
            self.assertEqual(list(Path(folder).glob("*.tmp")), [])
            write_csv(path, ["id"], [{"id": "complete"}])
            self.assertEqual(read_csv(path), [{"id": "complete"}])
