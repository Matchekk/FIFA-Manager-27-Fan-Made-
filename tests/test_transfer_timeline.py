import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fm27.transfer_timeline import canonical_events, incoming_kind, departure_plan
from fm27.transfermarkt import endpoint_kind, parse_profile
from fm27.matching import IdentityIndex, recover_profile_identity

SNAPSHOT = "2026-09-08"


def event(**kw):
    return {"event_id": "1", "player_tm_id": "10", "player": "Test Person", "league": "ENG1",
            "club_tm_id": "11", "direction": "Abgang", "old_club_tm_id": "11", "old_club": "Source",
            "new_club_tm_id": "22", "new_club": "Destination", "transfer_type": "PERMANENT",
            "explicit_event_date": "", "source_status": "CONFIRMED", "snapshot_date": SNAPSHOT,
            "source": "https://example.com/transfers", "source_sha256": "a" * 64, **kw}


class TimelineTests(unittest.TestCase):
    def test_full_profile_name_recovers_existing_person(self):
        index = IdentityIndex([{"name":"Test Full Person", "dob":"2000-01-02", "fifa_id":"0"}])
        evidence = {"player":"Nickname", "dob":"2000-01-02", "fifa_id":"123"}
        profile = {"player":"Nickname", "full_name":"Test Full Person", "dob":"2000-01-02", "club_tm_id":"22",
                   "source_status":"CONFIRMED", "snapshot_date":SNAPSHOT}
        self.assertEqual(recover_profile_identity(index,evidence,profile,SNAPSHOT,"22")[0], "PROFILE_DOB_NAME")
        profile["club_tm_id"] = "33"
        self.assertEqual(recover_profile_identity(index,evidence,profile,SNAPSHOT,"22")[0], "CONFLICT")
        direct = {**evidence, "player":"Test Full Person", "fifa_id":""}
        self.assertEqual(index.match(direct)[0], "DOB_NAME")
        self.assertEqual(recover_profile_identity(index,direct,profile,SNAPSHOT,"22")[0], "CONFLICT")

    def test_profile_name_does_not_override_different_fifa(self):
        index = IdentityIndex([{"name":"Test Full Person", "dob":"2000-01-02", "fifa_id":"321"}])
        evidence = {"player":"Nickname", "dob":"2000-01-02", "fifa_id":"123"}
        profile = {"player":"Nickname", "full_name":"Test Full Person", "dob":"2000-01-02", "club_tm_id":"22",
                   "source_status":"CONFIRMED", "snapshot_date":SNAPSHOT}
        self.assertEqual(recover_profile_identity(index,evidence,profile,SNAPSHOT,"22")[0], "MISSING_FROM_FM")

    def test_unassigned_fifa_reuses_exact_existing_person(self):
        index = IdentityIndex([{"name":"Test Person", "dob":"2000-01-02", "fifa_id":"0"}])
        evidence = {"player":"Test Person", "dob":"2000-01-02", "fifa_id":"123"}
        self.assertEqual(index.match(evidence)[0], "MISSING_FROM_FM")
        self.assertEqual(index.match_unassigned_fifa(evidence)[0], "DOB_NAME_UNASSIGNED_FIFA")

    def test_unassigned_fifa_never_overrides_nonzero_id(self):
        index = IdentityIndex([{"name":"Test Person", "dob":"2000-01-02", "fifa_id":"321"}])
        self.assertEqual(index.match_unassigned_fifa({"player":"Test Person", "dob":"2000-01-02", "fifa_id":"123"})[0], "MISSING_FROM_FM")

    def test_unassigned_fifa_requires_unique_dob_name(self):
        player = {"name":"Test Person", "dob":"2000-01-02", "fifa_id":"0"}
        index = IdentityIndex([player, dict(player)])
        self.assertEqual(index.match_unassigned_fifa({"player":"Test Person", "dob":"2000-01-02", "fifa_id":"123"})[0], "MISSING_FROM_FM")

    def test_duplicate_bookings_are_one_event(self):
        rows = canonical_events([event(), event(direction="Zugang", club_tm_id="22")], SNAPSHOT)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["observation_count"], 2)
        self.assertEqual(rows[0]["timeline_status"], "CURRENT_OR_UNDATED")

    def test_disagreeing_bookings_conflict(self):
        rows = canonical_events([event(), event(new_club_tm_id="33")], SNAPSHOT)
        self.assertEqual(rows[0]["timeline_status"], "CONFLICT")

    def test_future_return_is_not_current(self):
        row = event(transfer_type="LOAN_RETURN", explicit_event_date="2027-06-30")
        self.assertEqual(canonical_events([row], SNAPSHOT)[0]["timeline_status"], "FUTURE")
        self.assertEqual(incoming_kind([row], "22", SNAPSHOT), "UNVERIFIED")

    def test_mixed_snapshot_fails(self):
        with self.assertRaises(ValueError):
            canonical_events([event(snapshot_date="2026-09-07")], SNAPSHOT)

    def test_undated_loan_purchase_requires_review(self):
        self.assertEqual(incoming_kind([event(), event(transfer_type="LOAN")], "22", SNAPSHOT), "REVIEW_REQUIRED")

    def test_earlier_return_excluded_by_current_joined(self):
        rows = [event(), event(transfer_type="LOAN_RETURN", explicit_event_date="2026-06-30")]
        self.assertEqual(incoming_kind(rows, "22", SNAPSHOT, "2026-08-01"), "PERMANENT")

    def test_rumor_not_current_evidence(self):
        self.assertEqual(incoming_kind([event(source_status="RUMOR")], "22", SNAPSHOT), "REVIEW_REQUIRED")

    def test_linked_clubless_marker(self):
        self.assertEqual(endpoint_kind("PERMANENT", "515", "VereinslosVereinslos", "Abgang"), "FREE_AGENT")
        self.assertEqual(endpoint_kind("PERMANENT", "515", "VereinslosVereinslos", "Zugang"), "FREE_TRANSFER")

    def test_free_agent_is_not_a_normal_club(self):
        row = canonical_events([event(new_club_tm_id="515", new_club="VereinslosVereinslos")], SNAPSHOT)[0]
        self.assertEqual(row["transfer_type"], "FREE_AGENT")


class DepartureTests(unittest.TestCase):
    def setUp(self):
        self.players = [{"fm_id": "99", "fifa_id": "123", "name": "Test Person", "common_name": "", "dob": "2000-01-02",
                         "club_id": "111", "starting_conditions": "[]", "contract_loan_flag": "False", "shirt_number": "7"}]
        self.clubs = [{"club_id": "111", "club": "Source"}, {"club_id": "222", "club": "Destination"}]
        self.profile = {"player_tm_id": "10", "player": "Test Person", "full_name": "", "dob": "2000-01-02",
                        "club_tm_id": "22", "club": "Destination", "snapshot_date": SNAPSHOT,
                        "source": "https://example.com/profile", "source_sha256": "b" * 64,
                        "joined": "2026-08-01", "contract_until": "2029-06-30", "profile_notes": ""}
        self.aliases = {"11": {"club_id": "111"}}
        self.events = canonical_events([event()], SNAPSHOT)

    def run_plan(self, profiles=None):
        return departure_plan(self.players, self.clubs, self.events,
                              [self.profile] if profiles is None else profiles, self.aliases, SNAPSHOT, [])

    def test_external_departure_uses_global_identity(self):
        before = copy.deepcopy(self.players)
        rows, plans = self.run_plan()
        self.assertEqual(plans[0]["new_club_id"], "222")
        self.assertEqual(rows[0]["status"], "CONFIRMED")
        self.assertEqual(self.players, before)

    def test_missing_end_can_retain_native_end_after_a_confirmed_permanent_move(self):
        self.players[0].update(contract_joined="2024-07-01", contract_until="2027-06-30")
        self.profile.update(contract_until="", source_status="CONFIRMED")
        rows, plans = self.run_plan()
        self.assertEqual(plans[0]["new_club_id"], "222")
        self.assertEqual(plans[0]["contract_until"], "2027-06-30")
        self.assertEqual(rows[0]["source_contract_until"], "")
        self.assertEqual(rows[0]["contract_evidence"], "NATIVE_END_PRESERVED")
        self.events = []
        self.assertFalse(self.run_plan()[1])

    def test_retained_contract_never_overrides_loan_or_origin_conflict(self):
        self.players[0].update(contract_joined="2024-07-01", contract_until="2027-06-30")
        self.profile.update(contract_until="", source_status="CONFIRMED")
        self.events = canonical_events([event(transfer_type="LOAN")], SNAPSHOT)
        self.assertFalse(self.run_plan()[1])
        self.events = canonical_events([event(old_club_tm_id="33")], SNAPSHOT)
        self.assertFalse(self.run_plan()[1])

    def test_external_reserve_alias_preserved(self):
        self.aliases["22"] = {"club_id": "222", "team_type": "RESERVE"}
        _, plans = self.run_plan()
        self.assertEqual(plans[0]["team_type"], "RESERVE")

    def test_club_punctuation_does_not_hide_exact_destination(self):
        self.profile["club"] = "Destination FC"
        self.clubs[1]["club"] = "Destination F.C."
        _, plans = self.run_plan()
        self.assertEqual(plans[0]["new_club_id"], "222")

    def test_club_reserve_suffix_is_not_discarded(self):
        self.profile["club"] = "Destination II"
        rows, plans = self.run_plan()
        self.assertFalse(plans)
        self.assertEqual(rows[0]["reason"], "DESTINATION_CLUB_UNRESOLVED")

    def test_name_without_matching_dob_never_moves(self):
        self.profile["dob"] = "2000-01-03"
        rows, plans = self.run_plan()
        self.assertFalse(plans)
        self.assertEqual(rows[0]["reason"], "MISSING_FROM_FM")

    def test_missing_profile_never_implies_release(self):
        rows, plans = self.run_plan([])
        self.assertFalse(plans)
        self.assertEqual(rows[0]["reason"], "MISSING_CURRENT_PROFILE")

    def test_future_conditions_preserved(self):
        self.players[0]["starting_conditions"] = json.dumps([[5, 1, 2, 3, 0, 0]])
        rows, plans = self.run_plan()
        self.assertFalse(plans)
        self.assertEqual(rows[0]["reason"], "STARTING_CONDITION_CONFLICT")

    def test_loan_not_permanent_move(self):
        self.events = canonical_events([event(transfer_type="LOAN")], SNAPSHOT)
        rows, plans = self.run_plan()
        self.assertFalse(plans)
        self.assertEqual(rows[0]["reason"], "LOAN_OR_RETURN_REQUIRES_TYPED_NATIVE_PLAN")

    def test_old_intermediate_destination_not_applied(self):
        self.profile.update(club_tm_id="33", club="Third")
        self.clubs.append({"club_id": "333", "club": "Third"})
        rows, plans = self.run_plan()
        self.assertFalse(plans)
        self.assertEqual(rows[0]["reason"], "NO_CURRENT_DESTINATION_EVENT")

    def test_contract_inverted_rejected(self):
        self.profile["contract_until"] = "2026-07-01"
        rows, plans = self.run_plan()
        self.assertFalse(plans)
        self.assertEqual(rows[0]["reason"], "MISSING_OR_INVALID_CURRENT_CONTRACT")

    def test_ambiguous_global_club_name_rejected(self):
        self.clubs.append({"club_id": "333", "club": "Destination"})
        rows, plans = self.run_plan()
        self.assertFalse(plans)
        self.assertEqual(rows[0]["reason"], "DESTINATION_CLUB_UNRESOLVED")

    def test_distinct_profiles_cannot_collapse(self):
        self.events += canonical_events([event(event_id="2", player_tm_id="20")], SNAPSHOT)
        rows, plans = self.run_plan([self.profile, {**self.profile, "player_tm_id": "20"}])
        self.assertFalse(plans)
        self.assertTrue(all(r["reason"] == "IDENTITY_COLLISION" for r in rows))


class ProfileTests(unittest.TestCase):
    def fixture(self):
        return '''<link rel="canonical" href="https://www.transfermarkt.de/test/profil/spieler/10"><h1>#7 Test Person</h1>
        <div class="info-table"><span class="info-table__content--regular">Geb./Alter:</span>
        <span class="info-table__content--bold">02.01.2000 (26)</span>
        <span class="info-table__content--regular">Aktueller Verein:</span>
        <span class="info-table__content--bold"><a href="/destination/verein/22">Destination</a></span>
        <span class="info-table__content--regular">Im Team seit:</span><span class="info-table__content--bold">01.08.2026</span>
        <span class="info-table__content--regular">Vertrag bis:</span><span class="info-table__content--bold">-</span></div>'''

    def test_profile_dates_missing_not_invented(self):
        row = parse_profile(self.fixture(), "10")
        self.assertEqual(row["dob"], "2000-01-02")
        self.assertEqual(row["player"], "Test Person")
        self.assertEqual(row["club_tm_id"], "22")
        self.assertEqual(row["contract_until"], "")
        self.assertEqual(row["shirt_number"], "7")

    def test_wrong_person_rejected(self):
        with self.assertRaises(ValueError):
            parse_profile(self.fixture(), "11")

    def test_error_page_rejected(self):
        with self.assertRaises(ValueError):
            parse_profile("<title>Error</title>", "10")
