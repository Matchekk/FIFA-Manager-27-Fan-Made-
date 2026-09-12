import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fm27.dfb import parse_page


def fixture(note="", birthday="02.03.2000", season="2026/2027"):
    return f'''<h2 class="m-ClubProfileHead-headline">Synthetic FC II</h2>
    <h3>Kader 3. Liga {season}</h3><table><thead><tr><th>Geburtstag</th></tr></thead>
    <tbody><tr><td><table><thead><tr><th>Trainer</th></tr></thead><tbody>
    <tr><td></td><td><a href="/profil/2">Test Coach</a></td><td>01.01.1970</td></tr></tbody></table>
    <table><thead><tr><th>Torwart</th></tr></thead><tbody>
    <tr><td>1</td><td><a href="/profil/1">Test Person</a> {note}</td><td>{birthday}</td></tr>
    </tbody></table></td></tr></tbody></table>
    <a href="/competitions/3-liga/seasons/2026-2027/teams/synthetic">Synthetic FC II</a>
    <a href="/competitions/3-liga/seasons/2025-2026/teams/old">Old FC</a>'''


class DfbTests(unittest.TestCase):
    def test_identity_dates_and_no_staff(self):
        records, peers = parse_page(fixture(), "GER3", dt.date(2026, 9, 8))
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["dob"], "2000-03-02")
        self.assertEqual(records[0]["fifa_id"], "")
        self.assertEqual(len(peers), 1)

    def test_old_season_rejected(self):
        with self.assertRaises(ValueError):
            parse_page(fixture(season="2025/2026"), "GER3", dt.date(2026, 9, 8))

    def test_departed_and_future_members_not_current(self):
        for note in ("(bis 01.09.2026)", "(ab 01.01.2027)"):
            rows, _ = parse_page(fixture(note), "GER3", dt.date(2026, 9, 8))
            self.assertFalse(rows[0]["membership_at_snapshot"])

    def test_missing_dob_kept_unresolved(self):
        rows, _ = parse_page(fixture(birthday=""), "GER3", dt.date(2026, 9, 8))
        self.assertEqual(rows[0]["dob"], "")

    def test_unlinked_player_preserves_name_without_inventing_id(self):
        html = fixture().replace('<a href="/profil/1">Test Person</a>', 'Test Person')
        rows, _ = parse_page(html, "GER3", dt.date(2026, 9, 8))
        self.assertEqual(rows[0]["player"], "Test Person")
        self.assertEqual(rows[0]["source_person_id"], "")
        self.assertEqual(rows[0]["dob"], "2000-03-02")

    def test_duplicate_observations_and_conflicts(self):
        row = '<tr><td>1</td><td><a href="/profil/1">Test Person</a> </td><td>02.03.2000</td></tr>'
        html = fixture().replace(row, row + row)
        rows, _ = parse_page(html, "GER3", dt.date(2026, 9, 8))
        self.assertEqual(len(rows), 1)
        html = fixture().replace(row, row + row.replace('<td>1</td>', '<td>9</td>'))
        rows, _ = parse_page(html, "GER3", dt.date(2026, 9, 8))
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(r["source_status"] == "CONFLICT" for r in rows))
