import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fm27.contracts import current_contract, retain_existing_end


class ContractEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.roster = {"dob":"2000-01-02", "club_tm_id":"10", "joined":"", "contract_until":""}
        self.profile = {**self.roster, "joined":"2026-08-01", "contract_until":"2028-06-30",
                        "source_status":"CONFIRMED", "snapshot_date":"2026-09-08"}

    def resolve(self):
        return current_contract(self.roster, self.profile, "2026-09-08")

    def test_missing_dates_completed_from_profile(self):
        self.assertEqual(self.resolve()["status"], "PROFILE_COMPLETED")
        self.assertEqual(self.resolve()["contract_until"], "2028-06-30")

    def test_different_nonempty_dates_conflict_even_if_roster_expired(self):
        self.roster["contract_until"] = "2026-06-30"
        self.assertEqual(self.resolve()["status"], "CONFLICT")

    def test_identity_club_and_snapshot_must_agree(self):
        for key, value in (("dob","2001-01-02"),("club_tm_id","20"),("snapshot_date","2026-09-07"),("source_status","RUMOR")):
            original = self.profile[key]
            self.profile[key] = value
            self.assertEqual(self.resolve()["status"], "CONFLICT")
            self.profile[key] = original

    def test_loan_end_is_not_permanent_contract(self):
        self.profile["loan_owner_tm_id"] = "20"
        self.assertEqual(self.resolve()["status"], "LOAN")
        self.assertFalse(self.resolve()["used_profile"])

    def test_no_profile_no_invented_date(self):
        result = current_contract(self.roster, {}, "2026-09-08")
        self.assertEqual(result["joined"], "")
        self.assertFalse(result["used_profile"])

    def test_incomplete_or_future_profile_remains_held(self):
        self.profile["joined"] = "2027-01-01"
        self.assertEqual(self.resolve()["status"], "INCOMPLETE")
        self.profile["joined"] = ""
        self.assertEqual(self.resolve()["status"], "INCOMPLETE")


class RetainedContractEndTests(unittest.TestCase):
    def setUp(self):
        self.native = {"dob": "2000-01-02", "contract_joined": "2024-07-01",
                       "contract_until": "2027-06-30", "contract_loan_flag": "False", "starting_conditions": "[]"}
        self.profile = {"dob": "2000-01-02", "source_status": "CONFIRMED", "snapshot_date": "2026-09-08",
                        "contract_until": "", "loan_owner_tm_id": "", "profile_notes": ""}
        self.contract = {"joined": "2026-07-01", "contract_until": "", "status": "INCOMPLETE", "used_profile": True}

    def resolve(self):
        return retain_existing_end(self.contract, self.native, self.profile, "2026-09-08")

    def test_existing_end_retained_exactly_without_extending_or_inventing_date(self):
        result = self.resolve()
        self.assertEqual(result["contract_until"], self.native["contract_until"])
        self.assertEqual(result["status"], "NATIVE_END_PRESERVED")
        self.assertEqual(self.contract["contract_until"], "")
        self.assertEqual(self.native["contract_until"], "2027-06-30")

    def test_explicit_source_end_and_source_conflicts_are_never_overridden(self):
        for value in ("2025-06-30", "2029-06-30", "invalid"):
            with self.subTest(value=value):
                self.profile["contract_until"] = value
                self.assertFalse(self.resolve().get("native_until_preserved"))
        self.profile["contract_until"] = ""
        for status in ("CONFLICT", "LOAN"):
            self.contract["status"] = status
            self.assertFalse(self.resolve().get("native_until_preserved"))

    def test_native_date_chronology_and_effective_start_required(self):
        original = dict(self.native)
        for changes in ({"contract_until": "2026-06-30"}, {"contract_until": "invalid"},
                        {"contract_joined": "2026-08-01"}, {"contract_joined": "1999-01-01"}):
            with self.subTest(changes=changes):
                self.native = {**original, **changes}
                self.assertFalse(self.resolve().get("native_until_preserved"))
        self.native = original
        for start in ("", "invalid", "2027-01-01", "1999-01-01"):
            self.contract["joined"] = start
            self.assertFalse(self.resolve().get("native_until_preserved"))

    def test_loans_future_conditions_and_unconfirmed_profiles_remain_held(self):
        for field, value in (("loan_owner_tm_id", "123"), ("profile_notes", "ausgeliehen"),
                             ("source_status", "RUMOR"), ("snapshot_date", "2026-09-09"), ("dob", "2001-01-02")):
            original = dict(self.profile)
            self.profile[field] = value
            self.assertFalse(self.resolve().get("native_until_preserved"))
            self.profile = original
        for value in ("True", ""):
            self.native["contract_loan_flag"] = value
            self.assertFalse(self.resolve().get("native_until_preserved"))
        self.native["contract_loan_flag"] = "False"
        for value in ("[[4,1,2,3,0,0]]", "[[5,1,2,3,0,0]]", "[[1]]", "null", "invalid"):
            self.native["starting_conditions"] = value
            self.assertFalse(self.resolve().get("native_until_preserved"))

    def test_injury_or_suspension_is_preserved(self):
        conditions = "[[1,1,2,0,0,0],[2,1,2,0,0,0]]"
        self.native["starting_conditions"] = conditions
        self.assertTrue(self.resolve()["native_until_preserved"])
        self.assertEqual(self.native["starting_conditions"], conditions)
