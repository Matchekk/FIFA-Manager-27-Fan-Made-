import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from fm27.primary_loans import load_primary_loans
from fm27.transfer_timeline import canonical_events
import test_loans as fixtures


class PrimaryLoanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.snapshot = '2026-09-08'
        content = b'<article>Test Person stays on loan from Source at Destination for the coming season.</article>'
        self.digest = hashlib.sha256(content).hexdigest()
        self.source = self.root / 'data/raw/primary-transfers' / (self.digest + '.html')
        self.source.parent.mkdir(parents=True)
        self.source.write_bytes(content)
        self.profile = {'player_tm_id':'10','player':'Test Person','dob':'2000-01-02','source_sha256':'a'*64,
                        'source':'https://example.com/profile','source_status':'CONFIRMED',
                        'snapshot_date':self.snapshot,'club_tm_id':'22'}
        self.item = {'player_tm_id':'10','profile_sha256':'a'*64,'dob':'2000-01-02','owner_tm_id':'11',
                     'borrower_tm_id':'22','owner_name':'Source','borrower_name':'Destination',
                     'source':'https://www.fcn.de/news/loan','source_sha256':self.digest,
                     'announcement_date':'2026-06-13','reviewed_on':self.snapshot,'reviewed_by':'Reviewer',
                     'reason':'Current season continuation verified against profile',
                     'evidence_fragments':['Test Person','on loan from Source at Destination']}

    def load(self, items=None):
        path = self.root / 'data/overrides/primary_loans.json'
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps({'schema':1,'snapshot_date':self.snapshot,'loans':items or [self.item]}),encoding='utf-8')
        return load_primary_loans(self.root,self.snapshot,[self.profile])

    def test_announcement_date_never_becomes_effective_loan_date(self):
        rows, proof = self.load()
        self.assertEqual(rows[0]['explicit_event_date'],'')
        self.assertEqual(rows[0]['announcement_date'],'2026-06-13')
        self.assertTrue(rows[0]['event_id'].startswith('primary-loan:'))
        self.assertEqual(canonical_events(rows,self.snapshot)[0]['timeline_status'],'CURRENT_OR_UNDATED')
        self.assertEqual(proof['rows'],1)

    def test_changed_source_bytes_rejected(self):
        self.source.write_text('changed',encoding='utf-8')
        with self.assertRaises(ValueError): self.load()

    def test_profile_binding_and_review_cannot_be_dropped(self):
        original = dict(self.item)
        for change in ({'profile_sha256':'b'*64},{'dob':'2001-01-02'},{'borrower_tm_id':'33'},
                       {'reviewed_by':''},{'reviewed_on':'2026-09-07'},{'announcement_date':'2026-10-01'},
                       {'source':'https://unreviewed.example/loan'},{'source_sha256':'../elsewhere'},
                       {'evidence_fragments':['unrelated transfer']},{'owner_tm_id':'22'}):
            with self.subTest(change=change):
                self.item = {**original,**change}
                with self.assertRaises(ValueError): self.load()

    def test_duplicate_announcements_and_ambiguous_profiles_rejected(self):
        with self.assertRaises(ValueError): self.load([self.item,copy.deepcopy(self.item)])
        self.load()
        with self.assertRaises(ValueError): load_primary_loans(self.root,self.snapshot,[self.profile,dict(self.profile)])

    def test_reviewed_parent_and_reserve_ids_have_same_legal_owner(self):
        f = fixtures.LoanTests(); f.setUp()
        f.profile['loan_owner_tm_id'] = '33'
        f.aliases['33'] = {'club_id':'111','team_type':'RESERVE'}
        self.assertEqual(len(f.run_plan()[1]),1)
        f.aliases['33']['club_id'] = '222'
        self.assertFalse(f.run_plan()[1])

    def test_same_name_with_unreviewed_different_owner_id_remains_held(self):
        f = fixtures.LoanTests(); f.setUp()
        f.profile['loan_owner_tm_id'] = '33'
        self.assertFalse(f.run_plan()[1])
