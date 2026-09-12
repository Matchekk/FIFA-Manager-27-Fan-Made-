import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fm27.common import sha256
from fm27.historical_transfers import load_historical_transfers, EVENT_FIELDS
from fm27.player_identities import ReviewedIdentity, PROFILE_FIELDS, NATIVE_FIELDS, values
from fm27.transfermarkt import parse_page, parse_profile
from fm27.transfer_timeline import canonical_events, incoming_kind


def page(season=2025):
    row = '''<tr><td><a href="/test/profil/spieler/10">Test Person</a></td>
    <td>26</td><td></td><td></td><td>Mittelfeld</td><td></td>
    <td><a href="/source/startseite/verein/11">Source</a></td><td></td>
    <td><a href="/jumplist/transfers/spieler/10/transfer_id/123">1 Mio. €</a></td></tr>'''
    return f'''<title>Transfers {season % 100:02d}/{(season + 1) % 100:02d}</title>
    <select name="saison_id"><option selected value="{season}">season</option></select>
    <div class="box"><h2 id="to-22"><a href="/destination/startseite/verein/22">Destination</a></h2>
    <div class="responsive-table"><table><thead><tr><th>Zugang</th></tr></thead><tbody>
    {row}{row.replace('/spieler/10', '/spieler/20').replace('/transfer_id/123', '/transfer_id/456')}
    </tbody></table></div></div>'''


class HistoricalTransferTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.snapshot = '2026-09-08'
        raw = self.root / 'data/raw/transfermarkt'
        raw.mkdir(parents=True)
        content = page()
        self.digest = hashlib.sha256(content.encode()).hexdigest()
        self.source = raw / (self.digest + '.html')
        self.source.write_bytes(content.encode('utf-8'))
        profile_html = '''<link rel="canonical" href="https://www.transfermarkt.de/test/profil/spieler/10">
        <h1>Test Person</h1><div class="info-table">
        <span class="info-table__content--regular">Geb./Alter:</span><span class="info-table__content--bold">03.02.2000</span>
        <span class="info-table__content--regular">Aktueller Verein:</span><span class="info-table__content--bold"><a href="/destination/verein/22">Destination</a></span>
        <span class="info-table__content--regular">Im Team seit:</span><span class="info-table__content--bold">18.01.2026</span>
        <span class="info-table__content--regular">Vertrag bis:</span><span class="info-table__content--bold">30.06.2029</span></div>'''
        digest = hashlib.sha256(profile_html.encode()).hexdigest()
        self.profile_source = raw / (digest + '.html')
        self.profile_source.write_bytes(profile_html.encode('utf-8'))
        self.profile = {**parse_profile(profile_html, '10'), 'source': 'https://www.transfermarkt.de/test/profil/spieler/10',
            'source_sha256': digest, 'snapshot_date': self.snapshot}
        self.person = {'fm_id': '9', 'fifa_id': '55', 'name': 'Test Person', 'dob': '2000-02-03', 'nationality': '14', 'club_id': '1'}
        self.profile['_reviewed_identity'] = ReviewedIdentity(values(self.profile, PROFILE_FIELDS), values(self.person, NATIVE_FIELDS))
        self.aliases = {'11': {'club_id': '1'}, '22': {'club_id': '2'}}
        self.identity_manifest = self.root / 'data/overrides/player_identities.json'
        self.identity_manifest.parent.mkdir(parents=True)
        self.identity_manifest.write_text('{}', encoding='utf-8')
        parsed = parse_page(content, 'GER1', expected_season=2025)[0][0]
        self.item = {'season': 2025, 'league': 'GER1', 'source': 'https://www.transfermarkt.de/bundesliga/transfers/wettbewerb/L1/saison_id/2025',
            'source_sha256': self.digest, 'event': {k: parsed[k] for k in EVENT_FIELDS},
            'profile_sha256': digest, 'dob': self.profile['dob'], 'joined': self.profile['joined'],
            'fm_id': '9', 'reviewed_on': self.snapshot, 'reviewed_by': 'Reviewer', 'reason': 'Reviewed winter transfer'}

    def load(self, items=None, profiles=None, events=None, players=None, baseline_path=None, baseline_digest=None):
        path = self.root / 'data/overrides/historical_transfers.json'
        path.write_text(json.dumps({'schema': 1, 'snapshot_date': self.snapshot,
            'identity_manifest_sha256': sha256(self.identity_manifest), 'rows': items or [self.item],
            'baseline_sha256': baseline_digest}), encoding='utf-8')
        return load_historical_transfers(self.root, self.snapshot, profiles or [self.profile],
            players or [self.person], self.aliases, events or [], baseline_path=baseline_path)

    def natural(self, **kwargs):
        self.profile.pop('_reviewed_identity', None)
        self.item['identity_basis'] = 'NATURAL_DOB_NAME'
        self.item.setdefault('native_identity', {k: self.person.get(k, '') for k in NATIVE_FIELDS + ('common_name',)})
        path = self.root / 'baseline.csv'
        if not path.exists(): path.write_text('bound baseline', encoding='utf-8')
        return self.load(**{'baseline_path': path, 'baseline_digest': sha256(path), **kwargs})

    def test_explicit_natural_identity_adds_only_bound_event(self):
        before = copy.deepcopy(self.person)
        rows, _ = self.natural()
        self.assertEqual([r['event_id'] for r in rows], ['123'])
        self.assertEqual(self.person, before)
        self.assertNotIn('_reviewed_identity', self.profile)

    def test_duplicate_review_still_rejected_when_source_page_is_cached(self):
        with patch('fm27.historical_transfers.parse_page', wraps=parse_page) as parser:
            with self.assertRaises(ValueError): self.natural(items=[self.item, copy.deepcopy(self.item)])
        self.assertEqual(parser.call_count, 1)
        self.assertEqual(parser.call_args.kwargs['selected_event_ids'], {'123'})

    def test_natural_identity_requires_frozen_baseline_and_supported_basis(self):
        for kwargs in ({'baseline_path': None}, {'baseline_digest': '0' * 64}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError): self.natural(**kwargs)
        self.item['identity_basis'] = 'FUZZY'
        with self.assertRaises(ValueError): self.load()

    def test_natural_identity_rejects_every_changed_native_identity_field(self):
        self.natural()
        for field in NATIVE_FIELDS + ('common_name',):
            original = self.item['native_identity'][field]
            self.item['native_identity'][field] = 'changed'
            with self.subTest(field=field), self.assertRaises(ValueError): self.natural()
            self.item['native_identity'][field] = original

    def test_natural_identity_rejects_ambiguous_name_fifa_and_fm_ids(self):
        for changes in ({'fm_id': '8', 'fifa_id': '66'},
                        {'fm_id': '8', 'name': 'Other Person'},
                        {'name': 'Other Person', 'fifa_id': '66'}):
            other = {**self.person, **changes}
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.natural(players=[self.person, other])

    def test_natural_identity_rejects_second_source_claim_and_foreign_fifa_id(self):
        other = {**self.profile, 'player_tm_id': '20'}
        with self.assertRaises(ValueError): self.natural(profiles=[self.profile, other])
        self.profile['fifa_id'] = '999'
        with self.assertRaises(ValueError): self.natural()

    def test_natural_identity_reparses_source_names_and_preserves_review_conflicts(self):
        for field in ('player', 'full_name', 'source_status'):
            before = self.profile.get(field, '')
            self.profile[field] = 'changed'
            with self.subTest(field=field), self.assertRaises(ValueError): self.natural()
            self.profile[field] = before
        self.natural()
        self.profile['_reviewed_identity'] = ReviewedIdentity(('invalid',), ('invalid',))
        path = self.root / 'baseline.csv'
        with self.assertRaises(ValueError): self.load(baseline_path=path, baseline_digest=sha256(path))

    def test_natural_identity_keeps_endpoint_loan_and_date_guards(self):
        self.natural()
        for field, value in (('joined', '2026-07-01'), ('loan_owner_tm_id', '11'), ('contract_until', '2030-06-30')):
            before = self.profile[field]
            self.profile[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError): self.natural()
            self.profile[field] = before
        self.aliases['11']['club_id'] = '3'
        with self.assertRaises(ValueError): self.natural()

    def test_old_season_requires_explicit_opt_in(self):
        with self.assertRaises(ValueError): parse_page(page(), 'GER1')
        self.assertEqual(len(parse_page(page(2026), 'GER1')[0]), 2)
        self.assertEqual(len(parse_page(page(), 'GER1', expected_season=2025)[0]), 2)
        for season in ('2025', True, 9999):
            with self.assertRaises(ValueError): parse_page(page(), 'GER1', expected_season=season)
        with self.assertRaises(ValueError): parse_page(page().replace('Transfers 25/26', 'Transfers 26/27'), 'GER1', expected_season=2025)

    def test_only_reviewed_event_is_added_without_inventing_date(self):
        rows, proof = self.load()
        self.assertEqual([r['event_id'] for r in rows], ['123'])
        self.assertEqual(rows[0]['explicit_event_date'], '')
        self.assertEqual(proof['rows'], 1)
        canonical = canonical_events(rows, self.snapshot)
        self.assertEqual(incoming_kind(canonical, '22', self.snapshot, '2026-01-18'), 'PERMANENT')
        self.assertEqual(self.person['club_id'], '1')

    def test_selection_does_not_require_unrelated_historical_counterparts(self):
        html = page().replace('<a href="/source/startseite/verein/11">Source</a>', '', 1)
        # Broken source123 is excluded only when the explicit selection requests456.
        with self.assertRaises(ValueError): parse_page(html, 'GER1', expected_season=2025)
        rows, _ = parse_page(html, 'GER1', expected_season=2025, selected_event_ids={'456'})
        self.assertEqual([r['event_id'] for r in rows], ['456'])
        for selected in ({'123'}, {'999'}, set(), ['456']):
            with self.assertRaises(ValueError): parse_page(html, 'GER1', expected_season=2025, selected_event_ids=selected)

    def test_same_league_mirror_must_agree_and_cannot_duplicate_arrival(self):
        mirror = '''<div class="box"><h2 id="to-11"><a href="/source/startseite/verein/11">Source</a></h2>
        <div class="responsive-table"><table><thead><tr><th>Abgang</th></tr></thead><tbody>
        <tr><td><a href="/test/profil/spieler/10">Test Person</a></td><td>26</td><td></td><td></td>
        <td>Mittelfeld</td><td></td><td><a href="/destination/startseite/verein/22">Destination</a></td><td></td>
        <td><a href="/jumplist/transfers/spieler/10/transfer_id/123">1 Mio. €</a></td></tr>
        </tbody></table></div></div>'''
        for suffix, valid in ((mirror, True), (mirror.replace('verein/22', 'verein/33'), False), (page(), False)):
            content = page() + suffix
            digest = hashlib.sha256(content.encode()).hexdigest()
            (self.source.parent / (digest + '.html')).write_bytes(content.encode())
            self.item['source_sha256'] = digest
            if valid:
                rows, _ = self.natural()
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]['direction'], 'Zugang')
            else:
                with self.assertRaises(ValueError): self.natural()

    def test_raw_source_and_endpoint_or_type_conflicts_rejected(self):
        original = copy.deepcopy(self.item)
        for change in ({'new_club_tm_id': '33'}, {'old_club_tm_id': '44'}, {'player_tm_id': '20'},
                       {'transfer_type': 'LOAN'}, {'event_id': '456'}, {'explicit_event_date': '2026-01-18'}):
            with self.subTest(change=change):
                self.item = {**original, 'event': {**original['event'], **change}}
                with self.assertRaises(ValueError): self.load()
        self.item = original
        self.source.write_text('changed', encoding='utf-8')
        with self.assertRaises(ValueError): self.load()

    def test_profile_dates_and_review_identity_remain_required(self):
        original = copy.deepcopy(self.profile)
        for change in ({'joined': '2026-07-01'}, {'dob': '2000-02-04'}, {'club_tm_id': '33'},
                       {'source_sha256': 'a' * 64}, {'loan_owner_tm_id': '11'}, {'_reviewed_identity': None}):
            with self.subTest(change=change):
                self.profile = {**original, **change}
                with self.assertRaises((ValueError, FileNotFoundError)): self.load()
        self.profile = original
        self.profile_source.write_text('changed', encoding='utf-8')
        with self.assertRaises(ValueError): self.load()

    def test_native_origin_and_global_identity_cannot_be_substituted(self):
        self.aliases['11']['club_id'] = '3'
        with self.assertRaises(ValueError): self.load()
        self.aliases['11']['club_id'] = '1'
        self.person['fifa_id'] = '56'
        with self.assertRaises(ValueError): self.load()

    def test_duplicate_or_conflicting_existing_events_are_rejected(self):
        with self.assertRaises(ValueError): self.load(items=[self.item, copy.deepcopy(self.item)])
        with self.assertRaises(ValueError): self.load(profiles=[self.profile, copy.deepcopy(self.profile)])
        with self.assertRaises(ValueError): self.load(events=[{**self.item['event'], 'transfer_type': 'LOAN'}])
        # A separate acquisition kind is preserved for the existing timeline conflict gate.
        rows, _ = self.load(events=[{**self.item['event'], 'event_id': '789', 'transfer_type': 'LOAN'}])
        conflicting = {**rows[0], 'event_id': '789', 'transfer_type': 'LOAN'}
        self.assertEqual(incoming_kind(rows + [conflicting], '22', self.snapshot, self.profile['joined']), 'REVIEW_REQUIRED')

    def test_unreviewed_manifest_provenance_and_season_are_rejected(self):
        original = copy.deepcopy(self.item)
        for change in ({'season': 2024}, {'season': '2025'}, {'league': 'OTHER'}, {'reviewed_by': ''},
                       {'source': 'https://example.com/transfers'}, {'source_sha256': '../bad'}, {'fm_id': '10'}):
            with self.subTest(change=change):
                self.item = {**original, **change}
                with self.assertRaises(ValueError): self.load()
