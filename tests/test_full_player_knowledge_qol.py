import importlib.util
import struct
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "full_player_knowledge", ROOT / "tools/install-full-player-knowledge-qol.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FullPlayerKnowledgeQolTests(unittest.TestCase):
    def test_packaged_plugin_is_x86_and_returns_level_ten(self):
        path = ROOT / "data/qol/full-player-knowledge/plugins/FM27.FullPlayerKnowledge.asi"
        payload = path.read_bytes()
        pe_offset = struct.unpack_from("<I", payload, 0x3C)[0]
        self.assertEqual(struct.unpack_from("<H", payload, pe_offset + 4)[0], 0x14C)
        self.assertIn(b"PATCH_APPLIED knowledge=10", payload)
        self.assertIn(bytes((0xB8, 0x0A, 0, 0, 0, 0xC2, 0x04, 0)), payload)

    def test_supported_build_is_signature_guarded(self):
        source = (ROOT / "src/plugins/full_player_knowledge/full_player_knowledge.cpp").read_text()
        self.assertIn("kExpectedGetter", source)
        self.assertIn("0xAB9BA0", source)
        self.assertIn(MODULE.EXPECTED_MANAGER_SHA256.upper(), source)


if __name__ == "__main__":
    unittest.main()
