import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from fm27.transfer_rating_validation import planned_squad_flags


class PlannedSquadFlagsTests(unittest.TestCase):
    def setUp(self):
        self.before = [dict(fm_id='12', fifa_id='0', dob='30.10.2006', name='Tommy', club_id='10',
                            in_reserve='1', in_youth='0'),
                       dict(fm_id='13', fifa_id='456', dob='01.01.2000', name='Other', club_id='30',
                            in_reserve='0', in_youth='0')]
        self.plan = [dict(fm_id='12', fifa_id='0', dob='2006-10-30', old_club_id='10', new_club_id='20', team_type='FIRST')]
        self.after = [{**self.before[0], 'fm_id':'999', 'club_id':'20', 'in_reserve':'0'}, dict(self.before[1])]

    def check(self):
        return planned_squad_flags(self.before, self.after, self.plan)

    def test_reviewed_reserve_to_first_team_and_native_id_renumbering_pass(self):
        result = self.check()
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(result['planned_flag_changes'], 1)
        self.assertEqual(self.before[0]['in_reserve'], '1')

    def test_unplanned_flag_change_fails(self):
        self.after[1]['in_youth'] = '1'
        self.assertEqual(self.check()['status'], 'FAIL')

    def test_different_valid_birthday_is_rejected(self):
        self.plan[0]['dob'] = '2006-10-31'
        with self.assertRaises(ValueError): self.check()

    def test_iso_native_date_is_also_supported(self):
        self.before[0]['dob'] = self.after[0]['dob'] = '2006-10-30'
        self.assertEqual(self.check()['status'], 'PASS')

    def test_retaining_old_reserve_flag_at_confirmed_first_team_fails(self):
        self.after[0]['in_reserve'] = '1'
        self.assertEqual(self.check()['status'], 'FAIL')

    def test_changed_identity_old_club_or_unsupported_team_is_rejected(self):
        for field in ('fifa_id', 'dob', 'old_club_id', 'team_type'):
            old = self.plan[0][field]
            self.plan[0][field] = 'invalid'
            with self.assertRaises(ValueError): self.check()
            self.plan[0][field] = old

    def test_duplicate_and_missing_plan_people_are_rejected(self):
        self.plan.append(dict(self.plan[0]))
        with self.assertRaises(ValueError): self.check()
        self.plan.pop()
        self.plan[0]['fm_id'] = 'absent'
        with self.assertRaises(ValueError): self.check()

    def test_unchanged_flags_need_no_exception(self):
        self.before[0]['in_reserve'] = '0'
        self.assertEqual(self.check()['planned_flag_changes'], 0)
        self.assertEqual(self.check()['status'], 'PASS')

    def test_first_to_reserve_changes_only_planned_membership(self):
        self.before[0]['in_reserve'] = '0'
        self.plan[0]['team_type'] = 'RESERVE'
        self.after[0]['in_reserve'] = '1'
        self.assertEqual(self.check()['status'], 'PASS')
