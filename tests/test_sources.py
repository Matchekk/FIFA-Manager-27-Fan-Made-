import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from fm27.ea import page_props,league_page
from fm27.transfermarkt import parse_squad

class SourceTests(unittest.TestCase):
    def test_ea_rejects_old_game_payload(self):
        data={"props":{"pageProps":{"gameDetails":{"slug":"fc-26"}}}}
        with self.assertRaises(ValueError):page_props('<script id="__NEXT_DATA__">'+json.dumps(data)+'</script>')

    def test_ea_ids_gender_and_birthdate(self):
        p={"id":17,"gender":{"id":0},"team":{"id":21,"label":"Synthetic"},"firstName":"Test","lastName":"Person",
           "commonName":None,"birthdate":"02/03/2000 0:00","position":{"shortLabel":"ST"},"overallRating":65,"stats":{"finishing":{"value":68}}}
        data={"teamGroup":{"id":"19","gender":{"id":0},"teams":[{"id":21}]},"ratingsEntries":{"items":[p],"totalItems":1}}
        rows,_,_=league_page(data,"GER1")
        self.assertEqual(rows[0]["fifa_id"],17)
        self.assertEqual(rows[0]["dob"],"2000-02-03")
        p["gender"]["id"]=1
        with self.assertRaises(ValueError):league_page(data,"GER1")

    def test_tm_squad_contract_and_notes(self):
        html='''<title>Synthetic - Kader im Detail 26/27</title><select name="saison_id"><option selected value="2026">26/27</option></select>
        <h1 class="data-header__headline-wrapper">Synthetic</h1><table class="items"><thead><tr><th>Geb./Alter Vertrag</th></tr></thead><tbody><tr>
        <td>7</td><td><a href="/test/profil/spieler/123">Test Person</a><a title="Neuzugang; Datum: 01.07.2026; Ablöse: Leihe"></a>
        <table class="inline-table"><tr><td>Mittelfeld</td></tr></table></td><td>03.02.2000 (26)</td><td></td><td></td><td></td><td>01.07.2026</td><td></td><td>30.06.2027</td><td></td>
        </tr></tbody></table>'''
        r=parse_squad(html,"GER1","1")[0]
        self.assertEqual(r["dob"],"2000-02-03")
        self.assertEqual(r["contract_until"],"2027-06-30")
        self.assertIn("Leihe",r["change_notes"])
        with self.assertRaises(ValueError):parse_squad(html.replace('value="2026"','value="2025"'),"GER1","1")
