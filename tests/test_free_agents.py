import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fm27.free_agents import plan_free_agents
from fm27.transfer_timeline import canonical_events
from test_transfer_timeline import event, SNAPSHOT


class FreeAgentTests(unittest.TestCase):
    def setUp(self):
        self.players = [{"fm_id":"99", "fifa_id":"123", "name":"Test Person", "common_name":"", "dob":"2000-01-02",
                         "club_id":"111", "starting_conditions":"[]", "contract_loan_flag":"False"}]
        self.profile = {"player_tm_id":"10", "player":"Test Person", "full_name":"", "dob":"2000-01-02",
                        "club_tm_id":"515", "club":"Vereinslos", "joined":"2026-07-01", "contract_until":"",
                        "source_status":"CONFIRMED", "snapshot_date":SNAPSHOT,
                        "source":"https://example.com/profile", "source_sha256":"b"*64}
        self.events = canonical_events([event(new_club_tm_id="515", new_club="Vereinslos")], SNAPSHOT)
        self.aliases = {"11":{"club_id":"111"}}

    def run_plan(self, profiles=None, roster=None):
        return plan_free_agents(self.players, profiles if profiles is not None else [self.profile], self.events,
                                self.aliases, SNAPSHOT, roster or [])

    def test_release_preserves_person_and_uses_dated_expired_contract(self):
        original = copy.deepcopy(self.players)
        rows, plans = self.run_plan()
        self.assertEqual(rows[0]["status"], "CONFIRMED")
        self.assertEqual(plans[0]["new_club_id"], "0")
        self.assertEqual(plans[0]["action"], "FREE_AGENT")
        self.assertEqual(plans[0]["contract_until"], "2026-06-30")
        self.assertEqual(self.players, original)

    def test_current_roster_membership_blocks_release(self):
        self.assertEqual(self.run_plan(roster=[{"player_tm_id":"10"}]), ([], []))

    def test_missing_or_future_release_date(self):
        for value in ("", "2027-07-01"):
            self.profile["joined"] = value
            rows, plans = self.run_plan()
            self.assertFalse(plans)
            self.assertEqual(rows[0]["reason"], "MISSING_OR_INVALID_RELEASE_DATE")

    def test_different_installed_origin(self):
        self.players[0]["club_id"] = "222"
        self.assertEqual(self.run_plan()[0][0]["reason"], "INSTALLED_ORIGIN_CONFLICT")
        self.assertFalse(self.run_plan()[1])

    def test_existing_conditions_are_protected(self):
        for kind in range(3, 11):
            self.players[0]["starting_conditions"] = f"[[{kind}, 0, 0, 0, 0, 0]]"
            self.assertEqual(self.run_plan()[0][0]["reason"], "STARTING_CONDITION_CONFLICT")
            self.assertFalse(self.run_plan()[1])

    def test_loan_flag_blocks_release(self):
        self.players[0]["contract_loan_flag"] = "True"
        self.assertFalse(self.run_plan()[1])

    def test_unconfirmed_profile(self):
        self.profile["source_status"] = "REVIEW_REQUIRED"
        self.assertFalse(self.run_plan()[1])

    def test_explicit_event_date_must_agree(self):
        self.events[0]["explicit_event_date"] = "2026-08-01"
        self.assertEqual(self.run_plan()[0][0]["reason"], "NO_MATCHING_RELEASE_EVENT")
        self.assertFalse(self.run_plan()[1])

    def test_future_event_is_held(self):
        self.events[0]["timeline_status"] = "FUTURE"
        self.assertFalse(self.run_plan()[1])

    def test_different_sources_cannot_release_same_person_twice(self):
        second = {**self.profile, "player_tm_id":"20"}
        self.events.append({**self.events[0], "player_tm_id":"20"})
        rows, plans = self.run_plan(profiles=[self.profile, second])
        self.assertFalse(plans)
        self.assertTrue(all(r["reason"] == "IDENTITY_COLLISION" for r in rows))

    def test_already_clubless_does_not_get_a_fabricated_native_id(self):
        self.players[0].update(club_id="0", fm_id="")
        rows, plans = self.run_plan()
        self.assertEqual(rows[0]["status"], "ALREADY_FREE_AGENT")
        self.assertFalse(plans)

    def test_profile_contract_contradicts_release(self):
        self.profile["contract_until"] = "2028-06-30"
        self.assertFalse(self.run_plan()[1])

    def test_ambiguous_global_identity(self):
        self.players.append({**self.players[0], "fm_id":"100"})
        self.assertFalse(self.run_plan()[1])


if __name__ == "__main__":
    unittest.main()
