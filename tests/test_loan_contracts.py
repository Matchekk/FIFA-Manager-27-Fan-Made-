import copy
import datetime as dt
import json
import unittest

from fm27.loan_contracts import preserved_owner_contract
import test_loans as fixtures


class PreservedLoanContractTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.LoanTests()
        self.fixture.setUp()
        self.player = self.fixture.players[0]
        self.player.update(contract_until="2028-06-30", contract_joined="2024-07-01")
        self.start, self.end, self.snapshot = "2026-09-01", "2027-05-31", "2026-09-08"

    def retained(self, references=None):
        return preserved_owner_contract(self.player, "111", references or {111: ["111"]},
                                        self.start, self.end, self.snapshot)

    def test_same_owner_preserves_existing_value_without_mutating_inputs(self):
        before = copy.deepcopy(self.player)
        self.assertEqual(self.retained(), "2028-06-30")
        self.assertEqual(self.player, before)

    def test_expired_loan_uses_owner_reference_not_borrower(self):
        self.fixture.previous_loan()
        self.assertEqual(self.retained(), "2028-06-30")
        self.assertEqual(self.retained({111: ["222"]}), "")
        self.assertEqual(self.retained({111: ["111", "222"]}), "")

    def test_seller_or_unproved_borrower_contract_not_carried_to_new_owner(self):
        for club in ("222", "333", "0", ""):
            with self.subTest(club=club):
                self.player["club_id"] = club
                self.assertEqual(self.retained(), "")

    def test_expired_short_missing_or_malformed_contract_not_extended(self):
        for end in ("2026-06-30", "2027-01-01", "", "invalid", "2027-02-30"):
            with self.subTest(end=end):
                self.player["contract_until"] = end
                self.assertEqual(self.retained(), "")

    def test_invalid_or_future_native_joined_date_is_not_plausible(self):
        for joined in ("", "invalid", "1990-01-01", "2027-01-01"):
            with self.subTest(joined=joined):
                self.player["contract_joined"] = joined
                self.assertEqual(self.retained(), "")

    def test_protected_or_ambiguous_native_conditions_remain_held(self):
        old = self.fixture.previous_loan()
        future = list(old)
        future[2] = dt.date(2027, 6, 30).toordinal() + 1721425
        for conditions in ([old, old], [old, [5, 1, 2, 3, 0, 0]], [future], [[4]], [None]):
            with self.subTest(conditions=conditions):
                self.player["starting_conditions"] = json.dumps(conditions)
                self.assertEqual(self.retained(), "")
        self.player["starting_conditions"] = json.dumps([old])
        self.player["contract_loan_flag"] = "True"
        self.assertEqual(self.retained(), "")

    def test_injury_and_ban_do_not_prevent_contract_preservation(self):
        self.player["starting_conditions"] = "[[1, 1, 2, 0, 19, 0], [2, 0, 0, 0, 2, 0]]"
        self.assertEqual(self.retained(), "2028-06-30")

    def test_source_absence_uses_native_value_and_reports_provenance(self):
        self.fixture.profile['owner_contract_until'] = ''
        rows, plans = self.fixture.run_plan()
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0]['contract_until'], self.player['contract_until'])
        self.assertEqual(rows[0]['owner_contract_basis'], 'PRESERVED_NATIVE_SAME_OWNER')
        self.assertEqual(rows[0]['owner_contract_source_value'], '')
        self.assertEqual(rows[0]['native_owner_contract_value'], self.player['contract_until'])
        self.assertEqual(self.fixture.profile['owner_contract_until'], '')

    def test_explicit_source_conflict_cannot_be_replaced_by_native_date(self):
        for value in ('2027-01-01', 'invalid'):
            with self.subTest(source=value):
                self.fixture.profile['owner_contract_until'] = value
                rows, plans = self.fixture.run_plan()
                self.assertFalse(plans)
                self.assertEqual(rows[0]['owner_contract_basis'], 'CURRENT_PROFILE')

    def test_preserved_contract_does_not_bypass_loan_event_or_current_identity(self):
        self.fixture.profile['owner_contract_until'] = ''
        self.fixture.events = []
        self.assertFalse(self.fixture.run_plan()[1])
        self.assertIn('matching loan event', self.fixture.run_plan()[0][0]['reason'])

    def test_same_owner_successor_preserves_contract_and_old_loan_guard(self):
        self.fixture.profile['owner_contract_until'] = ''
        self.fixture.previous_loan()
        rows, plans = self.fixture.run_plan()
        self.assertEqual(plans[0]['action'], 'REPLACE_EXPIRED_LOAN')
        self.assertEqual(plans[0]['contract_until'], '2028-06-30')
        self.assertEqual(rows[0]['owner_contract_basis'], 'PRESERVED_NATIVE_SAME_OWNER')
        self.fixture.profile['joined'] = '2025-07-01'
        self.fixture.events[0]['explicit_event_date'] = ''
        self.assertFalse(self.fixture.run_plan()[1])
