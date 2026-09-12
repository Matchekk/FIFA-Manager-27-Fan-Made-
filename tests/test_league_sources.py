import unittest
from fm27.league_sources import parse_league_members


class LeagueSourcesTests(unittest.TestCase):
    def page(self):
        return '''<title>Championship26/27 | Transfermarkt</title>
        <link rel="canonical" href="https://www.transfermarkt.de/championship/startseite/wettbewerb/GB2">
        <select name="saison_id"><option selected value="2026">26/27</option></select>
        <table class="items"><thead><tr><th>Verein</th><th>Kader</th></tr></thead><tbody>
        <tr><td class="hauptlink"><a href="/west-ham/startseite/verein/379/saison_id/2026">West Ham</a>
        <span class="icon-absteiger" title="Abstieg aus der1.Liga25/26"></span></td>
        <td><a href="/west-ham/kader/verein/379/saison_id/2026">28</a></td></tr>
        <tr><td class="hauptlink"><a href="/burnley/startseite/verein/1132/saison_id/2026">Burnley</a></td></tr>
        </tbody></table>'''

    def test_valid_keeps_explicit_relegation_and_ids(self):
        rows = parse_league_members(self.page(), 'GB2')
        self.assertEqual([r['club_tm_id'] for r in rows], ['379','1132'])
        self.assertEqual(rows[0]['relegation_note'], 'Abstieg aus der1.Liga25/26')
        self.assertEqual(rows[1]['relegation_note'], '')

    def test_wrong_competition(self):
        with self.assertRaisesRegex(ValueError, 'canonical'):
            parse_league_members(self.page(), 'IT2')

    def test_wrong_season(self):
        with self.assertRaisesRegex(ValueError, 'season'):
            parse_league_members(self.page().replace('value="2026"','value="2025"'), 'GB2')

    def test_stale_title(self):
        with self.assertRaisesRegex(ValueError, 'title'):
            parse_league_members(self.page().replace('Championship26/27','Championship25/26'), 'GB2')

    def test_duplicate_identity(self):
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            parse_league_members(self.page().replace('/1132/','/379/'), 'GB2')

    def test_conflicting_row_identity(self):
        with self.assertRaisesRegex(ValueError, 'Conflicting'):
            parse_league_members(self.page().replace('/west-ham/kader/verein/379/','/west-ham/kader/verein/543/'), 'GB2')

    def test_stale_club_season(self):
        with self.assertRaisesRegex(ValueError, 'stale'):
            parse_league_members(self.page().replace('/burnley/startseite/verein/1132/saison_id/2026','/burnley/startseite/verein/1132/saison_id/2025'), 'GB2')

    def test_missing_table_member_row(self):
        with self.assertRaises(ValueError):
            parse_league_members(self.page().replace('class="hauptlink"','class="different"'), 'GB2')
