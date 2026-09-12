import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fm27.matching import IdentityIndex, normalize


class LatinIdentityTests(unittest.TestCase):
    def test_non_decomposing_latin_names_share_the_transliteration(self):
        for left, right in (("Frederik Rønnow", "Frederik Rönnow"), ("Łukasz", "Lukasz"),
                            ("Đurić", "Duric"), ("Þór", "Thor"), ("Kjær", "Kjaer")):
            with self.subTest(name=left):
                self.assertEqual(normalize(left), normalize(right))

    def test_transliteration_requires_matching_birthdate(self):
        index = IdentityIndex([{"name":"Frederik Rønnow", "dob":"1992-08-04", "fifa_id":"201269"}])
        self.assertEqual(index.match({"player":"Frederik Rönnow", "dob":"1992-08-04"})[0], "DOB_NAME")
        self.assertEqual(index.match({"player":"Frederik Rönnow", "dob":"1992-08-05"})[0], "MISSING_FROM_FM")

    def test_transliteration_does_not_resolve_collisions_or_fifa_conflicts(self):
        people = [{"name":name, "dob":"2000-01-01", "fifa_id":str(i)} for i,name in enumerate(("Kjær", "Kjaer"), 1)]
        index = IdentityIndex(people)
        self.assertEqual(index.match({"player":"Kjaer", "dob":"2000-01-01"})[0], "AMBIGUOUS")
        self.assertEqual(index.match_unassigned_fifa({"player":"Kjaer", "dob":"2000-01-01", "fifa_id":"3"})[0], "MISSING_FROM_FM")

    def test_given_and_family_name_order_preserves_every_component(self):
        index = IdentityIndex([{"name":"Seol Young-woo", "dob":"1998-12-05", "fifa_id":"123"}])
        self.assertEqual(index.match({"player":"Young-woo Seol", "dob":"1998-12-05"})[0], "DOB_NAME")
        for name in ("Young Seol", "Seol Young-woo Kim"):
            self.assertEqual(index.match({"player":name, "dob":"1998-12-05"})[0], "MISSING_FROM_FM")

    def test_reordered_name_collision_remains_ambiguous(self):
        index = IdentityIndex([{"name":name, "dob":"2000-01-01", "fifa_id":str(i)} for i,name in enumerate(("Foo Bar", "Bar Foo"), 1)])
        self.assertEqual(index.match({"player":"Bar Foo", "dob":"2000-01-01"})[0], "AMBIGUOUS")

    def test_reordered_name_never_overrides_a_different_fifa_id(self):
        index = IdentityIndex([{"name":"Foo Bar", "dob":"2000-01-01", "fifa_id":"1"}])
        self.assertEqual(index.match_unassigned_fifa({"player":"Bar Foo", "dob":"2000-01-01", "fifa_id":"2"})[0], "MISSING_FROM_FM")
