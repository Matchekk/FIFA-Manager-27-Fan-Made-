import copy
import datetime as dt
import json
import unittest

import test_loans as loan_fixtures
from test_transfer_timeline import event, SNAPSHOT
from fm27.loans import plan_loans
from fm27.transfer_timeline import canonical_events


class PurchaseLoanTests(unittest.TestCase):
    def setUp(self):
        f = loan_fixtures.LoanTests(); f.setUp()
        self.players, self.clubs, self.aliases, self.profile = f.players, f.clubs, f.aliases, f.profile
        for c in self.clubs:
            c["reference_id"] = c["club_id"]
        self.clubs.append({"club_id": "333", "reference_id": "444", "club": "Seller"})
        self.players[0]["club_id"] = "333"
        self.purchase = event(event_id="999", old_club_tm_id="33", old_club="Seller",
                              new_club_tm_id="11", new_club="Source")
        self.loan = event(event_id="1", transfer_type="LOAN")

    def run_plan(self, extra=()):
        return plan_loans(self.players, self.clubs, [self.profile],
                          canonical_events([self.purchase, self.loan, *extra], SNAPSHOT), self.aliases, SNAPSHOT)

    def old_loan(self):
        days = lambda v: dt.date.fromisoformat(v).toordinal() + 1721425
        self.players[0]["club_id"] = "222"
        self.players[0]["starting_conditions"] = json.dumps([
            [4, days("2025-07-01"), days("2026-06-30"), 444, 4000000, 0], [2, 0, 0, 0, 2, 0]])

    def test_structural_chain_keeps_purchase_date_unknown_and_id_order_irrelevant(self):
        before = copy.deepcopy(self.players)
        rows, plans = self.run_plan()
        self.assertEqual(plans[0]["action"], "PURCHASE_AND_LOAN")
        self.assertEqual(plans[0]["acquisition_seller_club_id"], "333")
        self.assertEqual(plans[0]["loan_owner_club_id"], "111")
        self.assertEqual(plans[0]["new_club_id"], "222")
        self.assertEqual(plans[0]["acquisition_date"], "")
        self.assertEqual(json.loads(rows[0]["acquisition_evidence"])["event_key"], "999")
        self.assertEqual(json.loads(rows[0]["loan_event_keys"]), ["1"])
        self.assertEqual(self.players, before)

    def test_expired_loan_owner_uses_reference_to_uid_not_borrower_or_buy_option(self):
        self.old_loan()
        plan = self.run_plan()[1][0]
        self.assertEqual(plan["previous_loan_owner_club_id"], "333")
        self.assertEqual(plan["previous_loan_buy_option"], "4000000")
        self.assertEqual(plan["acquisition_seller_club_id"], "333")
        self.purchase["old_club_tm_id"] = "22"; self.purchase["old_club"] = "Destination"
        self.assertFalse(self.run_plan()[1])

    def test_buy_option_alone_never_proves_acquisition(self):
        self.old_loan()
        self.purchase["transfer_type"] = "LOAN_RETURN"
        self.assertFalse(self.run_plan()[1])

    def test_purchase_dates_obey_old_end_and_current_start(self):
        self.old_loan()
        for date in ("2026-06-29", "2026-08-02"):
            with self.subTest(date=date):
                self.purchase["explicit_event_date"] = date
                self.assertFalse(self.run_plan()[1])
        self.purchase["explicit_event_date"] = "2026-07-01"
        self.assertEqual(self.run_plan()[1][0]["acquisition_date"], "2026-07-01")

    def test_wrong_seller_unconfirmed_or_missing_hash_held(self):
        original = dict(self.purchase)
        for change in ({"old_club":"Unknown", "old_club_tm_id":"44"}, {"source_status":"REVIEW_REQUIRED"},
                       {"source_sha256":""}, {"source":""}, {"explicit_event_date":"2027-01-01"}):
            with self.subTest(change=change):
                self.purchase = {**original, **change}
                self.assertFalse(self.run_plan()[1])

    def test_competing_acquisition_is_held(self):
        self.assertFalse(self.run_plan([event(event_id="2", new_club_tm_id="11", old_club_tm_id="55", old_club="Unknown")])[1])
        self.assertFalse(self.run_plan([{**self.purchase, "event_id":"2"}])[1])

    def test_owner_exit_conflicts_but_earlier_return_is_allowed(self):
        exit_event = event(event_id="2", new_club_tm_id="55")
        self.assertFalse(self.run_plan([exit_event])[1])
        earlier = {**exit_event, "transfer_type":"LOAN_RETURN", "explicit_event_date":"2026-06-30",
                   "new_club_tm_id":"33", "new_club":"Seller"}
        self.assertEqual(len(self.run_plan([earlier])[1]), 1)

    def test_earlier_sale_requires_explicitly_later_purchase(self):
        earlier = event(event_id="2", new_club_tm_id="55", explicit_event_date="2026-06-30")
        self.assertFalse(self.run_plan([earlier])[1])
        self.purchase["explicit_event_date"] = "2026-07-01"
        self.assertEqual(len(self.run_plan([earlier])[1]), 1)
        self.purchase["explicit_event_date"] = "2026-06-29"
        self.assertFalse(self.run_plan([earlier])[1])

    def test_undated_purchase_does_not_hide_return_to_unrelated_owner(self):
        earlier = event(event_id="2", new_club_tm_id="55", new_club="Unknown",
                        transfer_type="LOAN_RETURN", explicit_event_date="2026-06-30")
        self.assertFalse(self.run_plan([earlier])[1])

    def test_later_loan_between_same_clubs_disagrees_with_profile(self):
        later = {**self.loan, "event_id":"2", "explicit_event_date":"2026-08-02"}
        self.assertFalse(self.run_plan([later])[1])

    def test_unexpired_or_overlapping_old_loan_remains_protected(self):
        self.old_loan()
        old = json.loads(self.players[0]["starting_conditions"])
        old[0][2] = dt.date(2027, 6, 30).toordinal() + 1721425
        self.players[0]["starting_conditions"] = json.dumps(old)
        self.assertFalse(self.run_plan()[1])
        self.old_loan()
        self.profile["joined"] = "2025-07-01"
        self.assertFalse(self.run_plan()[1])

    def test_current_identity_and_protected_flags_remain_held(self):
        for change in ({"contract_loan_flag":"True"}, {"starting_conditions":"[[5, 1, 2, 3, 0, 0]]"},
                       {"dob":"2001-01-02"}):
            old = dict(self.players[0]); self.players[0].update(change)
            self.assertFalse(self.run_plan()[1])
            self.players[0] = old
