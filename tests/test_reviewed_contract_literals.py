import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fm27.common import sha256
from fm27.reviewed_contracts import apply_reviewed_contract_end, exact_date_literal


class ContractDateLiteralTests(unittest.TestCase):
    def test_iso_and_full_english_date_are_locale_independent(self):
        for literal in ("2032-06-30", "30 June 2032", "30 JUNE 2032"):
            self.assertEqual(exact_date_literal(literal), "2032-06-30")

    def test_season_option_year_ambiguous_and_abbreviated_dates_are_not_inferred(self):
        for literal in ("summer 2032", "2032", "2031/32", "June 2032", "option until 30 June 2032",
                        "30/06/2032", "06/07/2032", "30 Jun 2032", "20320630", None):
            self.assertIsNone(exact_date_literal(literal), literal)

    def test_impossible_calendar_dates_are_rejected(self):
        for literal in ("31 June 2032", "29 February 2031", "2031-02-29", "0 June 2032", "30 June 0000"):
            self.assertIsNone(exact_date_literal(literal), literal)
        self.assertEqual(exact_date_literal("29 February 2032"), "2032-02-29")

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        source = self.root / "club.html"
        source.write_text("<p>Alejandro Gomes Furtado: signed until 30 June 2032.</p>", encoding="utf-8")
        self.row = dict(fm_id="302180", fifa_id="0", dob="2008-02-14", old_club_id="2949136",
            new_club_id="1769500", joined="2026-07-09", contract_until="2031-06-30",
            snapshot_date="2026-09-08", source_sha256="a"*64, status="CONFIRMED", team_type="FIRST")
        self.review = dict(status="REVIEWED_PERMANENT_CONTRACT_END", expected_plan_row=dict(self.row),
            snapshot_date="2026-09-08", contract_until="2032-06-30", reason="Official signed end supersedes profile",
            evidence=[dict(role="OFFICIAL_CLUB", status="REQUIRED_FACTS_PRESENT", url="https://club.example/announcement",
                file="club.html", sha256=sha256(source), required=["Alejandro Gomes Furtado", "30 June 2032"],
                contract_end_literal="30 June 2032")])

    def resolve(self):
        return apply_reviewed_contract_end(self.row, self.review, self.root)

    def test_official_full_date_changes_only_contract_end(self):
        corrected, files = self.resolve()
        self.assertEqual(corrected, {**self.row, "contract_until":"2032-06-30"})
        self.assertEqual(self.row["contract_until"], "2031-06-30")
        self.assertEqual(files, {"club.html":self.review["evidence"][0]["sha256"]})

    def test_literal_must_be_explicitly_selected_among_reviewed_facts(self):
        self.review["evidence"][0]["required"] = ["Alejandro Gomes Furtado"]
        with self.assertRaises(ValueError): self.resolve()

    def test_requested_end_must_match_the_exact_literal(self):
        self.review["contract_until"] = "2033-06-30"
        with self.assertRaises(ValueError): self.resolve()

    def test_date_literal_must_exist_in_hash_bound_source_body(self):
        self.review["evidence"][0]["contract_end_literal"] = "30 June 2033"
        self.review["evidence"][0]["required"] = ["Alejandro Gomes Furtado", "30 June 2033"]
        self.review["contract_until"] = "2033-06-30"
        with self.assertRaises(ValueError): self.resolve()
