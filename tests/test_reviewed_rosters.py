import copy
import json
import tempfile
import unittest
from pathlib import Path

from fm27.common import sha256
from fm27.reviewed_rosters import (load_primary_roster_reviews,
    reviewed_primary_target, reviewed_departure_target)


class PrimaryRosterReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.baseline = self.root / 'players.csv'
        self.baseline.write_text('frozen baseline', encoding='utf-8')
        self.player = dict(fm_id='1', fifa_id='0', name='Dele Thomas', common_name='',
            dob='2007-07-23', club_id='10', nationality='34')
        def raw(folder, text):
            p = self.root / 'data/raw' / folder / 'temporary.html'
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding='utf-8')
            digest = sha256(p)
            p.rename(p.parent / (digest + '.html'))
            return digest
        roster_sha = raw('transfermarkt', 'roster')
        profile_sha = raw('transfermarkt', 'profile')
        dfb_sha = raw('dfb', 'old roster')
        self.row = dict(player_tm_id='100', club_tm_id='20', fm_id='1', fifa_id='0',
            dob='2007-07-23', player='Dele Thomas', old_club_id='10', new_club_id='20',
            source='https://source.test/roster', source_sha256=roster_sha,
            profile_source='https://source.test/profile', profile_sha256=profile_sha,
            joined='2026-09-01', contract_until='2030-06-30', transfer_type='PERMANENT',
            team_type='FIRST', shirt_number='77', source_date='2026-09-08',
            status='CONFLICT', database_action='REVIEW_REQUIRED')
        self.roster = [{**self.row, 'snapshot_date':'2026-09-08', 'source_status':'CONFIRMED'}]
        self.profiles = [dict(player_tm_id='100', club_tm_id='20', dob='2007-07-23',
            source=self.row['profile_source'], source_sha256=profile_sha,
            snapshot_date='2026-09-08', source_status='CONFIRMED', loan_owner_tm_id='')]
        self.observed = [dict(fm_id='1', source_sha256=dfb_sha, new_club='Old club')]
        evidence = []
        for role, host, facts in (
            ('DESTINATION_PROFILE','club.test',['23-07-2007','30-06-2030']),
            ('DESTINATION_ANNOUNCEMENT','club.test',['01-09-2026','Thomas']),
            ('LEAGUE_DEPARTURES','league.test',['Thomas (NEC)'])):
            digest = raw('player-biographies', '<p>'+' '.join(facts)+'</p>')
            evidence.append(dict(role=role,url='https://'+host+'/'+role,required=facts,
                status='REQUIRED_FACTS_PRESENT',sha256=digest,
                file='data/raw/player-biographies/'+digest+'.html'))
        self.review = dict(status='REVIEWED_PERMANENT_PRIMARY_ROSTER_SUPERSESSION',
            author='reviewer',reason='Three independent affirmative transfer records',
            snapshot_date='2026-09-08',native_fm_id='1',native_fifa_id='0',
            dob='2007-07-23',effective_date='2026-09-01',contract_until='2030-06-30',
            player_tm_id='100',destination_club_id='20',native_identity=self.player.copy(),
            expected_current_conflict=self.row.copy(),expected_dfb_observations=copy.deepcopy(self.observed),
            official_evidence=evidence,baseline_sha256=sha256(self.baseline))

    def load(self, reviews=None):
        path = self.root / 'data/overrides/primary_roster_reviews.json'
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(dict(snapshot_date='2026-09-08',
            rows=reviews if reviews is not None else [self.review])),encoding='utf-8')
        return load_primary_roster_reviews(self.root,'2026-09-08',[self.player],self.baseline,
            self.roster,self.profiles,self.observed,[dict(club_id='20')])

    def test_exact_move_accepted_without_mutating_observations(self):
        before=copy.deepcopy(self.observed)
        reviews,bound=self.load()
        self.assertTrue(reviewed_primary_target(self.row,reviews))
        self.assertEqual(self.observed,before)
        self.assertEqual(len(bound),7)

    def test_other_person_destination_loan_and_changed_dates_remain_held(self):
        reviews,_=self.load()
        for key,value in [('fm_id','2'),('new_club_id','30'),('transfer_type','LOAN'),
                          ('joined','2026-09-02'),('source_date','2026-09-09'),
                          ('profile_sha256','different'),('fifa_id','123')]:
            with self.subTest(key=key):
                self.assertFalse(reviewed_primary_target({**self.row,key:value},reviews))

    def test_changed_native_identity_or_baseline_rejected(self):
        self.player['dob']='2007-07-24'
        with self.assertRaises(ValueError): self.load()
        self.player['dob']='2007-07-23'
        self.baseline.write_text('changed baseline',encoding='utf-8')
        with self.assertRaises(ValueError): self.load()

    def test_changed_or_extra_primary_observation_rejected(self):
        self.observed.append(dict(fm_id='1',new_club='Third club'))
        with self.assertRaises(ValueError): self.load()

    def test_changed_roster_or_profile_rejected(self):
        self.roster[0]['contract_until']='2031-06-30'
        with self.assertRaises(ValueError): self.load()
        self.roster[0]['contract_until']='2030-06-30'
        self.profiles[0]['loan_owner_tm_id']='10'
        with self.assertRaises(ValueError): self.load()

    def test_corrupt_primary_source_and_missing_fact_rejected(self):
        item=self.review['official_evidence'][0]
        (self.root/item['file']).write_text('corrupted',encoding='utf-8')
        with self.assertRaises(ValueError): self.load()
        item['sha256']=sha256(self.root/item['file'])
        with self.assertRaises(ValueError): self.load()

    def test_future_or_duplicate_review_rejected(self):
        self.review['effective_date']='2026-09-09'
        with self.assertRaises(ValueError): self.load()
        self.review['effective_date']='2026-09-01'
        with self.assertRaises(ValueError): self.load([self.review,self.review])

    def test_independent_official_sources_and_exact_dates_required(self):
        self.review['official_evidence'][2]['url']='https://club.test/transfers'
        with self.assertRaises(ValueError): self.load()
        self.review['official_evidence'][2]['url']='https://league.test/transfers'
        self.review['official_evidence'][0]['required']=['2007','2030']
        with self.assertRaises(ValueError): self.load()

    def test_departure_needs_confirmed_matching_current_plan_and_profile(self):
        reviews,_=self.load()
        departure={**self.row,'snapshot_date':'2026-09-08','source_sha256':self.row['profile_sha256']}
        self.assertFalse(reviewed_departure_target(departure,[self.row],reviews))
        current={**self.row,'status':'CONFIRMED','database_action':'STAGE_CURRENT_SQUAD'}
        self.assertTrue(reviewed_departure_target(departure,[current],reviews))
        self.assertFalse(reviewed_departure_target({**departure,'new_club_id':'30'},[current],reviews))
        self.assertFalse(reviewed_departure_target(departure,[current,current],reviews))
