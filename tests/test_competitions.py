import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fm27.competitions import fixture_errors, parse_leagues


class CompetitionStructureTests(unittest.TestCase):
    def setUp(self):
        self.league = {"team_count":4, "rounds":2, "team_references":[100,101,102,103],
                       "matchdays":[1,8,15,22,29,36], "matchdays2":[],
                       "fixtures":[[1,4,2,3],[1,3,4,2],[1,2,3,4],[4,1,3,2],[3,1,2,4],[2,1,4,3]]}

    def test_complete_round_robin(self):
        self.assertFalse(fixture_errors(self.league))

    def test_self_match_or_double_booking(self):
        self.league["fixtures"][0] = [1,1,2,3]
        self.assertIn("INVALID_MATCHDAY_PARTICIPATION", fixture_errors(self.league))

    def test_missing_return_match(self):
        self.league["fixtures"].pop()
        self.assertIn("PAIRING_COVERAGE", fixture_errors(self.league))

    def test_wrong_home_away_balance(self):
        self.league["fixtures"][3] = self.league["fixtures"][0]
        self.assertIn("HOME_AWAY_IMBALANCE", fixture_errors(self.league))

    def test_calendar_must_cover_new_team_count(self):
        self.league["team_count"] = 6
        self.assertIn("MATCHDAYS_COUNT_OR_ORDER", fixture_errors(self.league))
        self.assertIn("TEAM_COUNT_OR_DUPLICATE", fixture_errors(self.league))

    def test_duplicate_team(self):
        self.league["team_references"][1] = 100
        self.assertIn("TEAM_COUNT_OR_DUPLICATE", fixture_errors(self.league))

    def test_parser_preserves_reserve_reference(self):
        text = '%INDEX%VERSION\n538116114\n%INDEXEND%VERSION\n%INDEX%COMPETITION\nDB_LEAGUE\n{ 21, LEAGUE, 2 }\n2\n2\nREL_RULE_1\n0\n2\n%INDEX%TEAMS\n1150001,150002\n%INDEXEND%TEAMS\n%INDEX%MATCHDAYS\n1,8\n%INDEXEND%MATCHDAYS\n%INDEX%FIXTURE\n1,2\n2,1\n%INDEXEND%FIXTURE\n%INDEXEND%COMPETITION\n'
        league = parse_leagues(text)[0]
        self.assertEqual(league['team_references'][0], 0x1150001)
        self.assertEqual(league['division'], 2)
        self.assertFalse(fixture_errors(league))
