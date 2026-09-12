import datetime as dt
import sys
import json
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from fm27.expired_loans import plan_expired_loans, project_removed_expired_loan
from fm27.transfer_timeline import canonical_events
from test_transfer_timeline import event,SNAPSHOT


class ExpiredLoanTests(unittest.TestCase):
    def setUp(self):
        days=lambda value:dt.date.fromisoformat(value).toordinal()+1721425
        self.condition=[4,days("2025-07-01"),days("2026-06-30"),111,-1,0]
        self.p={"fm_id":"99","fifa_id":"123","dob":"2000-01-02","name":"Test Person","club_id":"222",
                "starting_conditions":json.dumps([self.condition]),"contract_loan_flag":"False","shirt_number":"7"}
        self.clubs=[{"club_id":"111","reference_id":"111","club":"Owner"},{"club_id":"222","reference_id":"222","club":"Borrower"}]
        self.observed={"fm_id":"99","player_tm_id":"10","club_tm_id":"11","dob":self.p["dob"],"new_club_id":"111",
                       "status":"REVIEW_REQUIRED","reason":"Installed future conditions need typed native review",
                       "source_date":SNAPSHOT,"joined":"2020-07-01","contract_until":"2028-06-30","shirt_number":"7","team_type":"FIRST"}
        self.profile={"player_tm_id":"10","player":"Test Person","dob":self.p["dob"],"club_tm_id":"11","club":"Owner",
                      "source_status":"CONFIRMED","snapshot_date":SNAPSHOT,"joined":"2020-07-01","contract_until":"2028-06-30",
                      "source":"https://example.com/profile","source_sha256":"a"*64}
        self.aliases={"11":{"club_id":"111"},"22":{"club_id":"222"}}
        self.events=canonical_events([event(old_club_tm_id="22",old_club="Borrower",new_club_tm_id="11",new_club="Owner",
                                           transfer_type="LOAN_RETURN",explicit_event_date="2026-06-30")],SNAPSHOT)

    def run_plan(self):
        self.p["starting_conditions"]=json.dumps([self.condition])
        return plan_expired_loans([self.p],self.clubs,[self.observed],[self.profile],self.events,self.aliases,SNAPSHOT)

    def test_evidenced_return_carries_exact_old_condition(self):
        row,plan=self.run_plan()
        self.assertEqual(row[0]["reason"],"EXPIRED_LOAN_RETURN")
        self.assertEqual(plan[0]["previous_loan_buy_option"],"-1")
        self.assertEqual(plan[0]["previous_loan_owner_club_id"],"111")

    def test_current_loan_is_not_removed(self):
        self.profile["loan_owner_tm_id"]="11"
        self.assertFalse(self.run_plan()[1])

    def test_not_yet_expired_is_protected(self):
        self.condition[2]=dt.date(2027,6,30).toordinal()+1721425
        self.assertEqual(self.run_plan()[0][0]["reason"],"OLD_LOAN_NOT_EXPIRED")

    def test_wrong_owner_reference_is_protected(self):
        self.condition[3]=999
        self.assertFalse(self.run_plan()[1])

    def test_purchase_is_not_inferred_from_buy_option(self):
        self.events=[]
        self.condition[4]=52000000
        self.assertFalse(self.run_plan()[1])

    def test_permanent_successor_can_keep_continuous_join_date(self):
        self.observed.update(club_tm_id="22",new_club_id="222")
        self.profile.update(club_tm_id="22",club="Borrower")
        self.events=canonical_events([event(transfer_type="PERMANENT",old_club_tm_id="11",new_club_tm_id="22")],SNAPSHOT)
        self.assertEqual(self.run_plan()[0][0]["reason"],"EXPIRED_LOAN_PERMANENT_SUCCESSOR")

    def test_profile_contract_disagreement_is_held(self):
        self.profile["contract_until"]="2029-06-30"
        self.assertFalse(self.run_plan()[1])

    def test_primary_source_conflict_not_eligible(self):
        self.observed["status"]="CONFLICT"
        self.assertFalse(self.run_plan()[1])

    def test_projection_removes_exact_loan_preserving_injury_and_ban(self):
        plan = self.run_plan()[1][0]
        remaining = [[1, 2461280, 2461300, 1, 0, 0], [2, 2, 0, 0, 0, 0]]
        self.assertEqual(json.loads(project_removed_expired_loan(json.dumps([self.condition] + remaining), plan, 111)), remaining)

    def test_projection_rejects_each_changed_native_precondition(self):
        plan = self.run_plan()[1][0]
        for index in (1, 2, 3, 4, 5):
            with self.subTest(field=index):
                altered = self.condition.copy()
                altered[index] += 1
                with self.assertRaises(ValueError):
                    project_removed_expired_loan(json.dumps([altered]), plan, 111)

    def test_projection_protects_future_conditions(self):
        plan = self.run_plan()[1][0]
        with self.assertRaises(ValueError):
            project_removed_expired_loan(json.dumps([self.condition, [3, 0, 0, 0, 0, 0]]), plan, 111)
