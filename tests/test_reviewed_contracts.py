import copy
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fm27.common import sha256
from fm27.reviewed_contracts import apply_reviewed_contract_end


class ReviewedContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        path = self.root / "source.html"
        path.write_text("<p>Player Name Club 2031-06-30</p>", encoding="utf-8")
        self.row = dict(fm_id="123", fifa_id="456", dob="2004-10-27", old_club_id="11",
            new_club_id="22", joined="2026-08-30", contract_until="2027-06-30",
            snapshot_date="2026-09-08", source_sha256="a" * 64, status="CONFIRMED", team_type="FIRST")
        self.review = dict(status="REVIEWED_PERMANENT_CONTRACT_END", expected_plan_row=dict(self.row),
            snapshot_date="2026-09-08", contract_until="2031-06-30", reason="Signed agreement supersedes old fallback",
            evidence=[dict(role="OFFICIAL_CLUB", status="REQUIRED_FACTS_PRESENT", url="https://club.example/announcement",
                           file="source.html", sha256=sha256(path), required=["Player Name", "Club", "2031-06-30"])])

    def resolve(self):
        return apply_reviewed_contract_end(self.row, self.review, self.root)

    def test_corrects_only_end_and_preserves_source_inputs(self):
        before = copy.deepcopy((self.row, self.review))
        corrected, evidence = self.resolve()
        self.assertEqual(corrected, {**self.row, "contract_until": "2031-06-30"})
        self.assertEqual((self.row, self.review), before)
        self.assertEqual(evidence, {"source.html": sha256(self.root / "source.html")})

    def test_stale_identity_club_and_profile_are_rejected(self):
        for key in ("fm_id", "fifa_id", "dob", "new_club_id", "old_club_id", "source_sha256", "joined", "contract_until"):
            with self.subTest(key=key):
                old = self.row[key]
                self.row[key] = "changed"
                with self.assertRaises(ValueError): self.resolve()
                self.row[key] = old

    def test_loan_and_unconfirmed_rows_cannot_be_bypassed_by_review(self):
        for key, value in (("loan_owner_club_id", "123"), ("loan_end", "2027-06-30"),
                           ("action", "RESOLVE_EXPIRED_LOAN"), ("previous_loan_owner_club_id", "123"),
                           ("previous_loan_start", "2025-07-01"), ("status", "HOLD"), ("team_type", "RESERVE")):
            with self.subTest(key=key):
                row = {**self.row, key: value}
                review = {**self.review, "expected_plan_row": row}
                with self.assertRaises(ValueError): apply_reviewed_contract_end(row, review, self.root)

    def test_changed_cached_bytes_fail_even_when_facts_still_present(self):
        with (self.root / "source.html").open("a", encoding="utf-8") as stream: stream.write("changed")
        with self.assertRaises(ValueError): self.resolve()

    def test_missing_official_source_and_missing_exact_date_fail(self):
        self.review["evidence"][0]["role"] = "SECONDARY"
        with self.assertRaises(ValueError): self.resolve()
        self.review["evidence"][0]["role"] = "OFFICIAL_CLUB"
        self.review["evidence"][0]["required"] = ["Player Name", "Club"]
        with self.assertRaises(ValueError): self.resolve()

    def test_forged_fact_or_path_escape_fails(self):
        self.review["evidence"][0]["required"].append("missing")
        with self.assertRaises(ValueError): self.resolve()
        self.review["evidence"][0]["required"].pop()
        self.review["evidence"][0]["file"] = "../source.html"
        with self.assertRaises(ValueError): self.resolve()

    def test_invalid_expired_unchanged_end_and_changed_snapshot_fail(self):
        for value in ("invalid", "2026-06-30", "2027-06-30"):
            self.review["contract_until"] = value
            with self.assertRaises(ValueError): self.resolve()
        self.review["contract_until"] = "2031-06-30"
        self.review["snapshot_date"] = "2026-09-09"
        with self.assertRaises(ValueError): self.resolve()

    def test_future_start_cannot_be_approved(self):
        self.row["joined"] = "2027-01-01"
        self.review["expected_plan_row"] = dict(self.row)
        with self.assertRaises(ValueError): self.resolve()
