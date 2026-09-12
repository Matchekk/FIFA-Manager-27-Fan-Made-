import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fm27.team_scope import attach_team_league, decode_reference, project_teams


class TeamScopeTests(unittest.TestCase):
    def test_reserve_bits_keep_same_owner(self):
        self.assertEqual(decode_reference(0x01150009), (0x150009, "RESERVE"))
        clubs = [{"reference_id": 0x150009, "club_id": 99, "club": "Synthetic FC"}]
        teams = project_teams(clubs, {0x150009: "GER1", 0x01150009: "GER3"})
        self.assertEqual([t["club_id"] for t in teams], [99, 99])
        players = [{"club_id": 99, "squad": kind} for kind in ("FIRST", "RESERVE", "YOUTH")]
        attach_team_league(players, teams)
        self.assertEqual([p["team_league"] for p in players], ["GER1", "GER3", ""])

    def test_bad_reference_not_guessed(self):
        for value in (0, 0x03150009, 0x01000000):
            with self.subTest(value=value), self.assertRaises(ValueError):
                decode_reference(value)
        with self.assertRaises(ValueError):
            project_teams([], {0x150001: "GER1"})
