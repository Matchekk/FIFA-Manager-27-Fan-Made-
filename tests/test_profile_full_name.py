import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from fm27.matching import IdentityIndex, recover_profile_identity


class FullNameCorroborationTests(unittest.TestCase):
    def setUp(self):
        self.native={"name":"Benjamin White", "dob":"1997-10-08", "fifa_id":"123", "club_id":"111"}
        self.evidence={"player":"Ben White", "dob":"1997-10-08"}
        self.profile={"player":"Ben White", "full_name":"Benjamin William White", "dob":"1997-10-08",
                      "club_tm_id":"11", "source_status":"CONFIRMED", "snapshot_date":"2026-09-08"}

    def match(self, extras=()):
        return recover_profile_identity(IdentityIndex([self.native,*extras]),self.evidence,self.profile,"2026-09-08","11","111")

    def test_full_name_dob_and_current_club_resolve_omitted_middle_name(self):
        self.assertEqual(self.match()[0],"PROFILE_FULL_NAME")

    def test_full_name_is_insufficient_when_club_differs(self):
        self.native["club_id"]="222"
        self.assertEqual(self.match()[0],"MISSING_FROM_FM")

    def test_global_collision_is_not_disambiguated_by_club(self):
        other={**self.native,"club_id":"222","name":"William White","fifa_id":"456"}
        self.assertEqual(self.match([other])[0],"AMBIGUOUS")

    def test_source_cannot_override_conflicting_fifa_id(self):
        self.evidence["fifa_id"]="456"
        self.assertEqual(self.match()[0],"CONFLICT")

    def test_similar_spelling_is_not_a_full_name_component(self):
        self.native["name"]="Benjamen White"
        self.assertEqual(self.match()[0],"MISSING_FROM_FM")

    def test_single_informative_component_is_not_identity(self):
        self.native["name"]="De White"
        self.profile["full_name"]="Benjamin de White"
        self.assertEqual(self.match()[0],"MISSING_FROM_FM")

    def test_profile_birthdate_and_club_must_agree_with_roster(self):
        for key,value in (("dob","1997-10-09"),("club_tm_id","12")):
            original=self.profile[key];self.profile[key]=value
            self.assertEqual(self.match()[0],"CONFLICT")
            self.profile[key]=original
