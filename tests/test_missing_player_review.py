import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from fm27.missing_player_review import DuplicateReviewIndex


class DuplicateReviewTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = '2026-09-08'
        self.native = dict(fm_id='1', fifa_id='0', name='Guilherme Tomas de Aquino', common_name='Liberato',
                           dob='2001-06-16', club_id='old', squad='RESERVE')
        self.evidence = dict(player='Guilherme Liberato', dob='2001-06-16', snapshot_date=self.snapshot)
        self.profile = dict(player='Guilherme Liberato', full_name='Guilherme Liberato Tomas de Aquino',
                            dob='2001-06-16', snapshot_date=self.snapshot, source_status='CONFIRMED')

    def check(self, players=None, target='new'):
        return DuplicateReviewIndex(players or [self.native]).candidates(self.evidence, self.profile, self.snapshot, target)

    def test_cross_club_reserve_full_name_is_a_review_lead_without_mutation(self):
        before = dict(self.native)
        people, reasons = self.check()
        self.assertEqual([p['fm_id'] for p in people], ['1'])
        self.assertIn('SAME_DOB_NATIVE_NAME_COMPONENTS_IN_VERIFIED_FULL_NAME', reasons['1'])
        self.assertEqual(self.native, before)

    def test_free_agent_is_included(self):
        self.native['club_id'] = '0'
        self.assertEqual(len(self.check()[0]), 1)

    def test_conflicting_fifa_is_retained_for_caller_conflict_review(self):
        self.native['fifa_id'] = '123'
        self.evidence['fifa_id'] = '456'
        self.assertEqual(self.check()[0][0]['fifa_id'], '123')

    def test_two_possible_people_are_not_silently_disambiguated(self):
        people, _ = self.check([self.native, {**self.native, 'fm_id': '2'}])
        self.assertEqual({p['fm_id'] for p in people}, {'1', '2'})

    def test_unverified_stale_or_conflicting_profile_is_not_used(self):
        for field, value in [('source_status', 'REVIEW_REQUIRED'), ('snapshot_date', '2025-01-01'), ('dob', '2001-06-17')]:
            old = self.profile[field]
            self.profile[field] = value
            self.assertEqual(self.check(), ([], {}))
            self.profile[field] = old

    def test_one_informative_word_and_particles_are_insufficient(self):
        self.native['name'] = 'Guilherme de'
        self.assertEqual(self.check(), ([], {}))

    def test_no_fuzzy_name_edit_is_accepted(self):
        self.native['name'] = 'Guilherme Tamas de Aquino'
        self.assertEqual(self.check(), ([], {}))

    def nacho(self):
        self.native.update(name='Nacho Pérez', common_name='', dob='2008-09-01', club_id='Levante')
        self.evidence.update(player='Nacho Pérez', dob='2008-08-29')
        self.profile.update(player='Nacho Pérez', full_name='Nacho Pérez Gómez', dob='2008-08-29')

    def test_same_club_different_birthday_blocks_unreviewed_creation(self):
        self.nacho()
        people, reasons = self.check(target='Levante')
        self.assertEqual(people[0]['dob'], '2008-09-01')
        self.assertIn('EXACT_NAME_DIFFERENT_DOB_SAME_CLUB', reasons['1'])

    def test_nearby_birthday_lead_survives_a_transfer(self):
        self.nacho()
        self.assertIn('EXACT_NAME_NEARBY_DIFFERENT_DOB', self.check()[1]['1'])

    def test_same_name_other_generation_elsewhere_is_not_equated(self):
        self.nacho()
        self.native['dob'] = '1987-07-16'
        self.assertEqual(self.check(), ([], {}))

    def test_different_source_snapshot_is_not_used(self):
        self.evidence['snapshot_date'] = '2025-09-08'
        self.assertEqual(self.check(), ([], {}))
