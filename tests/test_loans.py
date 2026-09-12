import copy
import datetime as dt
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fm27.loans import plan_loans, plan_current_loans, project_added_loan_condition
from fm27.transfer_timeline import canonical_events
import test_transfer_timeline as fixtures

event, SNAPSHOT = fixtures.event, fixtures.SNAPSHOT


class LoanTests(unittest.TestCase):
    def test_native_condition_order_preserves_injury_and_ban(self):
        existing = [[1, 2460763, 2461040, 0, 19, 0], [2, 0, 0, 0, 2, 0]]
        result = json.loads(project_added_loan_condition(json.dumps(existing), "2026-09-01", "2027-05-31", "917529"))
        self.assertEqual(result[0], [4, 2461285, 2461557, 917529, 0, 0])
        self.assertEqual(result[1:], existing)

    def setUp(self):
        fixture = fixtures.DepartureTests()
        fixture.setUp()
        self.players, self.clubs, self.aliases = fixture.players, fixture.clubs, fixture.aliases
        self.profile = {**fixture.profile, "loan_owner_tm_id": "11", "loan_owner": "Source", "owner_contract_until": "2029-06-30",
                        "contract_until": "2027-05-31", "source_status": "CONFIRMED"}
        self.events = canonical_events([event(transfer_type="LOAN")], SNAPSHOT)

    def run_plan(self):
        return plan_loans(self.players, self.clubs, [self.profile], self.events, self.aliases, SNAPSHOT)

    def test_unconfirmed_profile_held(self):
        self.profile["source_status"] = "REVIEW_REQUIRED"
        self.assertFalse(self.run_plan()[1])

    def test_current_roster_fifa_resolution_must_agree(self):
        row = {"source_date":SNAPSHOT, "status":"REVIEW_REQUIRED", "classification":"LOAN_IN", "fm_id":"99",
               "player_tm_id":"10", "new_club_id":"222"}
        def run():
            return plan_current_loans(self.players,self.clubs,[self.profile],self.events,self.aliases,SNAPSHOT,[row])
        self.assertEqual(len(run()[1]), 1)
        row["fm_id"] = "100"
        self.assertFalse(run()[1])
        self.assertEqual(run()[0][0]["status"], "IDENTITY_CONFLICT")

    def test_current_primary_source_conflict_stays_held(self):
        row = {"source_date":SNAPSHOT, "status":"CONFLICT", "classification":"LOAN_IN", "fm_id":"99",
               "player_tm_id":"10", "new_club_id":"222"}
        reports, plans = plan_current_loans(self.players,self.clubs,[self.profile],self.events,self.aliases,SNAPSHOT,[row])
        self.assertFalse(reports)
        self.assertFalse(plans)

    def test_owner_and_borrower_are_distinct_native_fields(self):
        before = copy.deepcopy(self.players)
        rows, plans = self.run_plan()
        self.assertEqual(rows[0]["status"], "VALID")
        self.assertEqual(plans[0]["new_club_id"], "222")
        self.assertEqual(plans[0]["loan_owner_club_id"], "111")
        self.assertEqual(plans[0]["loan_end"], "2027-05-31")
        self.assertEqual(plans[0]["contract_until"], "2029-06-30")
        self.assertEqual(self.players, before)

    def test_missing_owner_held(self):
        self.profile.update(loan_owner_tm_id="99", loan_owner="Unresolved")
        rows, plans = self.run_plan()
        self.assertFalse(plans)
        self.assertEqual(rows[0]["status"], "MISSING_OWNER")

    def test_missing_return_held(self):
        self.profile["contract_until"] = ""
        rows, plans = self.run_plan()
        self.assertFalse(plans)
        self.assertEqual(rows[0]["status"], "MISSING_RETURN")

    def test_return_after_owner_contract_held(self):
        self.profile["owner_contract_until"] = "2027-01-01"
        rows, plans = self.run_plan()
        self.assertFalse(plans)
        self.assertEqual(rows[0]["status"], "DATE_CONFLICT")

    def test_existing_future_transfer_never_overwritten(self):
        self.players[0]["starting_conditions"] = "[[5, 1, 2, 3, 0, 0]]"
        rows, plans = self.run_plan()
        self.assertFalse(plans)
        self.assertIn("protected", rows[0]["reason"])

    def test_event_owner_disagreement_held(self):
        self.events = canonical_events([event(transfer_type="LOAN", old_club_tm_id="33")], SNAPSHOT)
        rows, plans = self.run_plan()
        self.assertFalse(plans)
        self.assertIn("matching loan event", rows[0]["reason"])

    def test_loan_profile_without_loan_event_held(self):
        self.events = canonical_events([event()], SNAPSHOT)
        rows, plans = self.run_plan()
        self.assertFalse(plans)
        self.assertEqual(rows[0]["status"], "MANUAL_REVIEW")

    def previous_loan(self):
        for club in self.clubs:
            club["reference_id"] = club["club_id"]
        self.clubs.append({"club_id":"333", "reference_id":"333", "club":"Former borrower"})
        self.players[0]["club_id"] = "333"
        days = lambda x: dt.date.fromisoformat(x).toordinal() + 1721425
        old = [4, days("2025-07-01"), days("2026-06-30"), 111, -1, 0]
        self.players[0]["starting_conditions"] = json.dumps([old, [2, 0, 0, 0, 2, 0]])
        return old

    def test_same_owner_can_send_player_from_expired_loan_to_new_borrower(self):
        self.previous_loan()
        before = copy.deepcopy(self.players)
        rows, plans = self.run_plan()
        self.assertEqual(rows[0]["status"], "VALID")
        self.assertEqual(plans[0]["action"], "REPLACE_EXPIRED_LOAN")
        self.assertEqual(plans[0]["previous_loan_owner_club_id"], "111")
        self.assertEqual(plans[0]["previous_loan_buy_option"], "-1")
        self.assertEqual(plans[0]["old_club_id"], "333")
        self.assertEqual(self.players, before)

    def test_successor_loan_cannot_change_owner_or_old_flags(self):
        old = self.previous_loan()
        for index, value in ((3, 222), (5, 1), (4, -2)):
            with self.subTest(field=index):
                altered = old.copy(); altered[index] = value
                self.players[0]["starting_conditions"] = json.dumps([altered])
                self.assertFalse(self.run_plan()[1])

    def test_unexpired_loan_is_never_replaced(self):
        old = self.previous_loan()
        old[2] = dt.date(2027, 6, 30).toordinal() + 1721425
        self.players[0]["starting_conditions"] = json.dumps([old])
        self.assertFalse(self.run_plan()[1])

    def test_successor_cannot_overlap_other_borrower(self):
        self.previous_loan()
        self.profile["joined"] = "2025-07-01"
        self.events = canonical_events([event(transfer_type="LOAN", explicit_event_date="")], SNAPSHOT)
        self.assertFalse(self.run_plan()[1])
        self.assertEqual(self.run_plan()[0][0]["reason"], "New loan overlaps previous borrower chronology")

    def test_same_borrower_extension_can_retain_original_join_date(self):
        self.previous_loan()
        self.players[0]["club_id"] = "222"
        self.profile["joined"] = "2025-07-01"
        self.events = canonical_events([event(transfer_type="LOAN", explicit_event_date="")], SNAPSHOT)
        self.assertEqual(self.run_plan()[1][0]["action"], "REPLACE_EXPIRED_LOAN")

    def test_successor_requires_confirmed_loan_event(self):
        self.previous_loan()
        self.events = []
        self.assertFalse(self.run_plan()[1])

    def test_successor_preserves_other_future_condition(self):
        old = self.previous_loan()
        self.players[0]["starting_conditions"] = json.dumps([old, [5, 1, 2, 3, 0, 0]])
        self.assertFalse(self.run_plan()[1])
