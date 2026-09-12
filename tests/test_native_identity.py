import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from fm27.native_identity import bind_native_free_agent_ids


class NativeIdentityTests(unittest.TestCase):
    def setUp(self):
        self.p={"fm_id":"", "fifa_id":"0", "dob":"2000-01-02", "name":"Test Person", "common_name":"",
                "club_id":"0", "source_file":"Without.sav", "source_line":"4"}
        self.n={**self.p,"fm_id":"200","dob":"02.01.2000"}

    def test_unique_native_assignment(self):
        self.assertEqual(bind_native_free_agent_ids([self.p],[self.n])[0]["fm_id"],"200")
        self.assertEqual(self.p["fm_id"],"200")

    def test_duplicate_clubless_people_remain_unbound(self):
        ps=[dict(self.p),dict(self.p)]
        self.assertFalse(bind_native_free_agent_ids(ps,[self.n,{**self.n,"fm_id":"201"}]))
        self.assertTrue(all(not p["fm_id"] for p in ps))

    def test_native_fifa_mismatch_never_falls_back(self):
        self.n["fifa_id"]="123"
        self.assertFalse(bind_native_free_agent_ids([self.p],[self.n]))

    def test_different_native_baseline_refused(self):
        self.p["fm_id"]="200"
        self.n["dob"]="2001-01-02"
        with self.assertRaises(ValueError):
            bind_native_free_agent_ids([self.p],[self.n])
