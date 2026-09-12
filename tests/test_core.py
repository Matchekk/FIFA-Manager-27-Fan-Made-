import copy
import datetime as dt
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fm27 import benchmark, database, matching, pe, reconcile, sources, validate
from fm27.common import external_output


def fake_pe() -> bytes:
    image = bytearray(1024)
    image[:2] = b"MZ"
    struct.pack_into("<I", image, 60, 128)
    image[128:132] = b"PE\0\0"
    struct.pack_into("<HHIIIHH", image, 132, 0x14C, 1, 0, 0, 0, 224, 0x102)
    struct.pack_into("<H", image, 152, 0x10B)
    struct.pack_into("<I", image, 152 + 16, 0x1000)
    struct.pack_into("<I", image, 152 + 56, 0x3000)
    struct.pack_into("<II", image, 152 + 224 + 16, 512, 512)
    return bytes(image)


def player(**changes) -> dict:
    row = dict(fm_id="1", fifa_id="101", name="Test Person", common_name="Tester",
               dob="2000-01-01", nationality="21", club_id="10", squad="FIRST",
               position="CM", attributes="{}", starting_conditions="[]",
               contract_joined="2020-07-01", contract_until="2027-06-30")
    return {**row, **changes}


def evidence(**changes) -> dict:
    row = dict(league="GER1", player="Test Person", fifa_id="101", dob="2000-01-01",
               from_club_id="10", to_club_id="20", transfer_type="PERMANENT",
               status="CONFIRMED", source="https://club.example/announcement",
               source_date="2026-08-15", observed_at="2026-09-08", confidence="1")
    return {**row, **changes}


CLUBS = [{"club_id": "10", "club": "Test FC", "league": "GER1"},
         {"club_id": "20", "club": "Example FC", "league": "ENG1"}]
SNAPSHOT = dt.date(2026, 9, 8)


class PeTests(unittest.TestCase):
    def test_reads_without_mutation(self):
        image = fake_pe()
        before = image
        self.assertFalse(pe.inspect_bytes(image)["large_address_aware"])
        self.assertEqual(image, before)

    def test_detects_laa(self):
        image = bytearray(fake_pe())
        image[150] |= 0x20
        self.assertTrue(pe.inspect_bytes(image)["large_address_aware"])

    def test_rejects_truncated_and_hostile_headers(self):
        for size in (0, 20, 64, 140, 300, 1000):
            with self.subTest(size=size), self.assertRaises(ValueError):
                pe.inspect_bytes(fake_pe()[:size])
        image = bytearray(fake_pe())
        struct.pack_into("<I", image, 60, 0xFFFFFFFF)
        with self.assertRaises(ValueError):
            pe.inspect_bytes(image)

    def test_rejects_architecture_mismatch(self):
        image = bytearray(fake_pe())
        struct.pack_into("<H", image, 132, 0x8664)
        with self.assertRaises(ValueError):
            pe.inspect_bytes(image)


class MatchingTests(unittest.TestCase):
    def test_unicode_normalization(self):
        self.assertEqual(matching.normalize("  José  Šimek "), "jose simek")

    def test_fifa_primary(self):
        self.assertEqual(matching.IdentityIndex([player()]).match(evidence(player="Different name"))[0], "FIFA_ID")

    def test_dob_contradicts_fifa(self):
        self.assertEqual(matching.IdentityIndex([player()]).match(evidence(dob="1999-01-01"))[0], "CONFLICT")

    def test_no_name_only_match(self):
        self.assertEqual(matching.IdentityIndex([player()]).match(evidence(fifa_id="", dob=""))[0], "REVIEW_REQUIRED")

    def test_unknown_fifa_never_overrides(self):
        self.assertEqual(matching.IdentityIndex([player()]).match(evidence(fifa_id="999"))[0], "MISSING_FROM_FM")

    def test_duplicate_fifa(self):
        self.assertEqual(matching.IdentityIndex([player(), player(fm_id="2")]).match(evidence())[0], "AMBIGUOUS")

    def test_birthdate_name_fallback(self):
        self.assertEqual(matching.IdentityIndex([player()]).match(evidence(fifa_id=""))[0], "DOB_NAME")

    def test_common_name_fallback(self):
        self.assertEqual(matching.IdentityIndex([player()]).match(evidence(fifa_id="", player="Tester"))[0], "DOB_NAME")


class ReconcileTests(unittest.TestCase):
    def plan(self, rows=None, players=None):
        return reconcile.plan(players or [player()], CLUBS, rows or [evidence()], SNAPSHOT, {"GER1", "ENG1"})

    def test_confirmed_proposal_without_fee(self):
        self.assertEqual(self.plan()[0]["database_action"], "PROPOSE_NATIVE_CHANGE")

    def test_rumors_and_conflicts_blocked(self):
        for status in ("RUMOR", "CONFLICT", "REVIEW_REQUIRED", "UNKNOWN"):
            with self.subTest(status=status):
                self.assertEqual(self.plan([evidence(status=status)])[0]["database_action"], "REVIEW_REQUIRED")

    def test_duplicate_evidence_blocks_all(self):
        rows = self.plan([evidence(), evidence(to_club_id="10")])
        self.assertTrue(all(r["classification"] == "DUPLICATE" for r in rows))

    def test_loan_needs_parent_and_date(self):
        self.assertEqual(self.plan([evidence(transfer_type="LOAN")])[0]["database_action"], "REVIEW_REQUIRED")
        row = evidence(transfer_type="LOAN", loan_parent_club_id="10", loan_end="2027-06-30")
        self.assertEqual(self.plan([row])[0]["classification"], "LOAN_IN")

    def test_existing_conditions_require_review(self):
        row = self.plan(players=[player(starting_conditions="[[4,1,2,3,4,5]]")])[0]
        self.assertEqual(row["database_action"], "REVIEW_REQUIRED")

    def test_bad_source_dates_and_ids(self):
        for change in ({"source_date": "2027-01-01"}, {"observed_at": ""},
                       {"to_club_id": "999"}, {"contract_until": "2020-01-01"},
                       {"source": "file:///x"}, {"confidence": "NaN"}):
            with self.subTest(change=change):
                self.assertEqual(self.plan([evidence(**change)])[0]["database_action"], "REVIEW_REQUIRED")

    def test_inputs_immutable(self):
        people, rows = [player()], [evidence()]
        before = copy.deepcopy((people, rows))
        self.plan(rows, people)
        self.assertEqual((people, rows), before)

    def test_absence_not_departure(self):
        self.assertEqual(reconcile.plan([player()], CLUBS, [], SNAPSHOT, {"GER1"}), [])

    def test_same_club_metadata_update_not_discarded(self):
        row = self.plan([evidence(to_club_id="10", contract_until="2029-06-30")])[0]
        self.assertEqual(row["database_action"], "PROPOSE_NATIVE_CHANGE")

    def test_same_club_loan_not_assumed_unchanged(self):
        row = self.plan([evidence(to_club_id="10", transfer_type="LOAN_RETURN")])[0]
        self.assertEqual(row["database_action"], "REVIEW_REQUIRED")


class ParserTests(unittest.TestCase):
    def test_version_guard(self):
        database.check_versions(["%INDEX%VERSION", str(database.VERSION)])
        for lines in ([], ["%INDEX%VERSION", "123"]):
            with self.assertRaises(ValueError):
                database.check_versions(lines)

    def test_player_identity_tail(self):
        # Entirely synthetic block, not copied from installed player/save data.
        body = ["0", "Test|Person|Tester||0", "21,0", "1,0,0,0", "2000-01-01",
                "5,5,5,10,8", ",".join(["50"] * 14), ",".join(["50"] * 37),
                "0", "128", "66", "0", "1", "0", "0", "0,0,180,75,8,0", "0",
                "0,0", "0", "0", "0", "0", "0", "0", "%INDEX%HIST", "0",
                "%INDEXEND%HIST", "%INDEX%CONTRACT",
                ",".join(["0"] * 23 + ["2020-07-01"]), "2027-06-30", "0,0,0,0,0",
                "0,0,0,0000-00-00", "%INDEXEND%CONTRACT", "0,0,0,0", "0", "0",
                "FIFAID:wrong_comment", "0", "2", "101", "999", "888"]
        row = database.player_record(body, 1, {}, Path("synthetic.sav"), 5)
        self.assertEqual((row["fifa_id"], row["football_manager_id"], row["position"]), (101, 999, "CM"))
        self.assertTrue(row["captain"])
        self.assertEqual(database.player_record(body, "", {}, Path("Without.sav"), 5)["fm_id"], "")
        with self.assertRaises(ValueError):
            database.player_record(body + ["unexpected"], 1, {}, Path("x"), 1)

    def test_no_source_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(ValueError):
                external_output(root / "database" / "output.csv", root)

    def test_fpl_wrong_season(self):
        fixture = {"teams": [{"id": i, "name": f"Club {i}"} for i in range(20)],
                   "events": [{"id": 1, "deadline_time": "2025-08-01T10:00:00Z"}], "elements": []}
        with self.assertRaises(ValueError):
            sources.parse_fpl(fixture, 2026)


class ValidationTests(unittest.TestCase):
    def test_native_clubless_expired_interval_is_valid(self):
        row = player(club_id="0", contract_joined="2026-07-01", contract_until="2026-06-30")
        self.assertNotIn("CONTRACT_ORDER", {r["code"] for r in validate.validate([row], CLUBS, SNAPSHOT)})

    def test_expired_interval_does_not_hide_active_club_or_arbitrary_date_errors(self):
        row = player(contract_joined="2026-07-01", contract_until="2026-06-30")
        self.assertIn("CONTRACT_ORDER", {r["code"] for r in validate.validate([row], CLUBS, SNAPSHOT)})
        row["club_id"] = "0"
        row["contract_until"] = "2025-06-30"
        self.assertIn("CONTRACT_ORDER", {r["code"] for r in validate.validate([row], CLUBS, SNAPSHOT)})

    def test_duplicate_id_fatal(self):
        result = validate.validate([player(), player()], CLUBS, SNAPSHOT)
        self.assertTrue(any(r["severity"] == "FATAL" for r in result))

    def test_bad_contract_attribute_and_reference(self):
        row = player(club_id="999", contract_until="2019-01-01", attributes='{"Pace": 100}')
        codes = {r["code"] for r in validate.validate([row], CLUBS, SNAPSHOT)}
        self.assertTrue({"MISSING_CLUB", "CONTRACT_ORDER", "ATTRIBUTE_RANGE"} <= codes)


class BenchmarkTests(unittest.TestCase):
    def runs(self):
        return [dict(status="MANUAL_BOUNDARIES", scenario="week", workload_id="synthetic-v1",
                     executable_sha256="abc", graphics_profile="installed",
                     summary={key: number for key in benchmark.METRICS}) for number in (10, 12, 11)]

    def test_median_and_improvement(self):
        runs = self.runs()
        self.assertEqual(benchmark.aggregate(runs)["median"]["wall_seconds"], 11)
        self.assertEqual(benchmark.compare(runs, runs)["percent_reduction"]["wall_seconds"], 0)

    def test_refuse_insufficient_or_idle(self):
        with self.assertRaises(ValueError):
            benchmark.aggregate(self.runs()[:2])
        runs = self.runs()
        runs[0]["status"] = "OBSERVATION_ONLY"
        with self.assertRaises(ValueError):
            benchmark.aggregate(runs)

    def test_mismatched_workload(self):
        runs = self.runs()
        runs[0]["workload_id"] = "other"
        with self.assertRaises(ValueError):
            benchmark.aggregate(runs)


if __name__ == "__main__":
    unittest.main()
