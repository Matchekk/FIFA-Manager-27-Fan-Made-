import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fm27.common import write_csv, write_json, sha256
from fm27.world_validation import compare_world, bind_world_inspection, compare_global, TABLES


class WorldValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.expected = Path(self.temp.name) / "expected"
        self.actual = Path(self.temp.name) / "actual"
        self.rows = {
            "clubs": [{"club_id": "123", "country_id": "14", "national": "0", "serialized_sha256": "a" * 64}],
            "countries": [{"country_id": "14", "serialized_sha256": "b" * 64}],
            "person_links": [{"kind": "CAPTAIN", "owner_id": "123", "slot": "0", "person_key": "PLAYER:abc@123"}],
        }
        self.meta = {"schema": 1, "clubs": 1, "countries": 1, "person_links": 1,
                     "link_errors": 0, "person_key_collisions": 0}
        for folder in (self.expected, self.actual):
            self.save(folder)

    def save(self, folder):
        folder.mkdir(exist_ok=True)
        for name, (filename, fields) in TABLES.items():
            write_csv(folder / filename, list(fields), self.rows[name])
        write_json(folder / "NATIVE_WORLD_SEMANTICS.json", self.meta)

    def compare(self, **kwargs):
        return compare_world(self.expected, self.actual, **kwargs)

    def test_exact_match_does_not_claim_release(self):
        report = self.compare()
        self.assertEqual(report["status"], "PASS")
        self.assertFalse(report["release_ready"])

    def test_changed_club_metadata_fails(self):
        self.rows["clubs"][0]["serialized_sha256"] = "c" * 64
        self.save(self.actual)
        self.assertEqual(self.compare()["status"], "FAIL")

    def test_changed_country_rule_fails(self):
        self.rows["countries"][0]["serialized_sha256"] = "d" * 64
        self.save(self.actual)
        self.assertEqual(self.compare()["status"], "FAIL")

    def test_changed_captain_slot_fails_reread(self):
        self.rows["person_links"][0]["slot"] = "1"
        self.save(self.actual)
        self.assertEqual(self.compare()["status"], "FAIL")
        report = self.compare(metadata_only=True)
        self.assertEqual(report["status"], "PASS")
        self.assertNotIn("person_links", report["checks"])
        self.assertEqual(report["comparison"], "UNCHANGED_CLUB_COUNTRY_METADATA")

    def test_duplicate_identity_fails_even_on_both_sides(self):
        self.rows["clubs"] *= 2
        self.meta["clubs"] = 2
        for folder in (self.expected, self.actual):
            self.save(folder)
        self.assertEqual(self.compare()["status"], "FAIL")

    def test_count_binding_detects_truncated_output(self):
        self.meta["person_links"] = 2
        self.save(self.actual)
        self.assertEqual(self.compare()["status"], "FAIL")

    def test_native_dangling_link_cannot_pass(self):
        self.meta["link_errors"] = 1
        self.save(self.actual)
        self.assertEqual(self.compare()["status"], "FAIL")

    def test_ambiguous_person_keys_cannot_pass(self):
        self.meta["person_key_collisions"] = 2
        self.save(self.actual)
        self.assertEqual(self.compare()["status"], "FAIL")

    def bind_fixture(self):
        self.save(self.expected / "before-plan")
        for folder in (self.expected / "before-plan", self.expected, self.actual):
            (folder / "native_player_semantics.csv").write_text("verified player bytes\n", encoding="utf-8")
        proof = {"status": "READ_ONLY_PLAN_INSPECTION_COMPLETED", "mode": "INSPECT_PLAN",
                 "plan_sha256": "plan", "immutable_inputs_unchanged": True, "binary_sha256": "binary",
                 "build": {"status": "PASS", "binary_sha256": "binary", "source_sha256": {"native.cpp": "source"}},
                 "native_tests": {"status": "PASS", "binary_sha256": "binary", "source_sha256": {"native.cpp": "source"}}}
        write_json(self.expected / "NATIVE_BUILD_INPUTS.json", proof)
        digest = sha256(self.expected / "native_player_semantics.csv")
        return dict(plan_hash="plan", before_hash=digest, expected_hash=digest, actual_hash=digest)

    def test_bound_world_requires_same_verified_player_bytes(self):
        args = self.bind_fixture()
        self.assertEqual(bind_world_inspection(self.expected, self.actual, **args)["status"], "PASS")
        (self.actual / "native_player_semantics.csv").write_text("different state\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "player state differs"):
            bind_world_inspection(self.expected, self.actual, **args)

    def test_bound_world_rejects_different_plan(self):
        args = self.bind_fixture()
        args["plan_hash"] = "other plan"
        with self.assertRaisesRegex(ValueError, "different frozen plan"):
            bind_world_inspection(self.expected, self.actual, **args)

    def test_bound_world_rejects_mismatched_test_binary(self):
        args = self.bind_fixture()
        path = self.expected / "NATIVE_BUILD_INPUTS.json"
        proof = json.loads(path.read_text(encoding="utf-8"))
        proof["native_tests"]["binary_sha256"] = "old binary"
        write_json(path, proof)
        with self.assertRaisesRegex(ValueError, "build/test evidence"):
            bind_world_inspection(self.expected, self.actual, **args)

    def global_fixture(self):
        rows = [{"kind": "RULES", "object_id": "0", "serialized_sha256": "a" * 64},
                {"kind": "ASSESSMENT", "object_id": "14", "serialized_sha256": "b" * 64}]
        meta = {"schema": 1, "records": 2, "cities": 0, "regions": 0, "appearance_definitions": 0,
                "cup_templates": 0, "legacy_standalone_stadiums": 0, "legacy_sponsors": 0}
        for folder in (self.expected, self.actual):
            write_csv(folder / "native_global_semantics.csv", list(rows[0]), rows)
            write_json(folder / "NATIVE_GLOBAL_SEMANTICS.json", meta)
        return rows, meta

    def test_global_rules_and_assessment_exact_match(self):
        self.global_fixture()
        self.assertEqual(compare_global(self.expected, self.actual)["status"], "PASS")

    def test_global_changed_rule_fails(self):
        rows, _ = self.global_fixture()
        rows[0]["serialized_sha256"] = "c" * 64
        write_csv(self.actual / "native_global_semantics.csv", list(rows[0]), rows)
        self.assertEqual(compare_global(self.expected, self.actual)["status"], "FAIL")

    def test_global_metadata_cannot_hide_missing_city(self):
        _, meta = self.global_fixture()
        meta["cities"] = 1
        write_json(self.actual / "NATIVE_GLOBAL_SEMANTICS.json", meta)
        self.assertEqual(compare_global(self.expected, self.actual)["status"], "FAIL")

    def test_global_legacy_objects_require_explicit_coverage(self):
        _, meta = self.global_fixture()
        meta["legacy_sponsors"] = 1
        write_json(self.actual / "NATIVE_GLOBAL_SEMANTICS.json", meta)
        self.assertEqual(compare_global(self.expected, self.actual)["status"], "FAIL")
