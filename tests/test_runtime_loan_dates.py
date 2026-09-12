from datetime import date
import unittest
from fm27.runtime_loan_dates import effective_current_loan_start as project

START=date(2026,7,1)
SNAPSHOT=date(2026,9,8)

class RuntimeLoanDatesTest(unittest.TestCase):
    def test_observed_late_current_loans_initialize_at_career_start(self):
        for actual in [date(2026,8,30),date(2026,8,31)]:
            with self.subTest(actual=actual):
                self.assertEqual(project(actual,date(2027,6,30),START,SNAPSHOT),START)

    def test_current_old_expired_and_beyond_snapshot_dates_are_preserved(self):
        for actual,end in [(START,date(2027,6,30)),(date(2025,7,1),date(2027,6,30)),
                           (date(2025,7,1),date(2026,6,30)),(date(2027,1,1),date(2027,6,30))]:
            with self.subTest(actual=actual,end=end):
                self.assertEqual(project(actual,end,START,SNAPSHOT),actual)

    def test_invalid_chronology_is_rejected(self):
        with self.assertRaises(ValueError):
            project(date(2027,7,1),date(2027,6,30),START,SNAPSHOT)
