"""Individually reviewed permanent moves that supersede one primary roster.

Raw observations are retained. A review authorizes only the exact current row;
all ordinary chronology, ownership, collision and starting-condition gates remain.
It cannot approve a loan, release, different destination or future transfer.
"""
import datetime as dt
import json
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from .common import sha256


CURRENT_KEYS = ('player_tm_id', 'club_tm_id', 'fm_id', 'fifa_id', 'dob',
                'old_club_id', 'new_club_id', 'source', 'source_sha256',
                'profile_source', 'profile_sha256', 'joined', 'contract_until',
                'transfer_type', 'team_type', 'shirt_number')


def reviewed_primary_target(row, reviews):
    """Test the exact reconstructed current row, without changing it."""
    review = reviews.get(row.get('fm_id'))
    if not review:
        return False
    expected = review['expected_current_conflict']
    return (row.get('source_date') == review['snapshot_date']
            and all(row.get(k) == expected.get(k) for k in CURRENT_KEYS))


def reviewed_departure_target(row, current, reviews):
    """A departure must agree with the independently approved permanent roster."""
    review = reviews.get(row.get('fm_id'))
    if not review:
        return False
    approved = [r for r in current if r.get('fm_id') == row.get('fm_id')
                and r.get('status') == 'CONFIRMED'
                and r.get('database_action') == 'STAGE_CURRENT_SQUAD'
                and reviewed_primary_target(r, reviews)]
    expected = review['expected_current_conflict']
    return (len(approved) == 1 and row.get('snapshot_date') == review['snapshot_date']
            and all(row.get(k) == expected.get(k) for k in
                    ('player_tm_id', 'fm_id', 'fifa_id', 'dob', 'old_club_id', 'new_club_id'))
            and row.get('source_sha256') == expected['profile_sha256'])


def load_primary_roster_reviews(root, snapshot, players, baseline_path,
                               roster, profiles, observations, clubs):
    path = root / 'data/overrides/primary_roster_reviews.json'
    if not path.exists():
        return {}, {}
    document = json.loads(path.read_text(encoding='utf-8'))
    if document.get('snapshot_date') != snapshot or not document.get('rows'):
        raise ValueError('Primary roster review snapshot or rows missing')
    bound = {path.relative_to(root).as_posix(): sha256(path)}
    reviews = {}
    baseline_digest = sha256(baseline_path)

    def bind(file, digest, facts=()):
        file = (root / file).resolve()
        if not file.is_relative_to(root.resolve()) or sha256(file) != digest:
            raise ValueError('Primary roster evidence changed or outside project')
        if facts:
            body = BeautifulSoup(file.read_bytes(), 'html.parser').get_text(' ', strip=True)
            if any(f.casefold() not in body.casefold() for f in facts):
                raise ValueError('Primary roster source facts absent')
        bound[file.relative_to(root.resolve()).as_posix()] = digest

    for review in document['rows']:
        fm_id = review.get('native_fm_id')
        if (not fm_id or fm_id in reviews or not review.get('author') or not review.get('reason')
                or review.get('status') != 'REVIEWED_PERMANENT_PRIMARY_ROSTER_SUPERSESSION'
                or review.get('snapshot_date') != snapshot
                or review.get('baseline_sha256') != baseline_digest):
            raise ValueError('Incomplete, duplicate or stale primary roster review')
        expected = review['expected_current_conflict']
        try:
            born, joined, snap, end = [dt.date.fromisoformat(v) for v in
                (review['dob'], review['effective_date'], snapshot, review['contract_until'])]
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError('Invalid primary roster review dates') from exc
        if not born < joined <= snap <= end:
            raise ValueError('Primary roster review chronology is invalid')
        required = dict(fm_id=fm_id, fifa_id=review['native_fifa_id'], dob=born.isoformat(),
            player_tm_id=review['player_tm_id'], new_club_id=review['destination_club_id'],
            transfer_type='PERMANENT', team_type='FIRST', joined=joined.isoformat(),
            contract_until=end.isoformat(), source_date=snapshot)
        if any(expected.get(k) != v for k, v in required.items()):
            raise ValueError('Primary roster disposition differs from reviewed move')
        persons = [p for p in players if p['fm_id'] == fm_id]
        identity = review['native_identity']
        if (len(persons) != 1 or set(identity) !=
                {'fm_id', 'fifa_id', 'name', 'common_name', 'dob', 'club_id', 'nationality'}
                or any(persons[0].get(k) != v for k, v in identity.items())
                or any(identity.get(k) != required[k] for k in ('fm_id', 'fifa_id', 'dob'))
                or expected['old_club_id'] != identity['club_id']):
            raise ValueError('Primary roster native identity changed')
        if len([c for c in clubs if c['club_id'] == expected['new_club_id']]) != 1:
            raise ValueError('Primary roster destination missing or ambiguous')
        sources = [r for r in roster if r['player_tm_id'] == review['player_tm_id']]
        if (len(sources) != 1 or sources[0].get('snapshot_date') != snapshot
                or sources[0].get('source_status') != 'CONFIRMED'
                or any(sources[0].get(k) != expected.get(k) for k in
                    ('player_tm_id', 'club_tm_id', 'player', 'dob', 'shirt_number',
                     'source', 'source_sha256', 'joined', 'contract_until'))):
            raise ValueError('Primary roster source row changed')
        matching = [p for p in profiles if p['player_tm_id'] == review['player_tm_id']]
        if (len(matching) != 1 or matching[0].get('snapshot_date') != snapshot
                or matching[0].get('source_status') != 'CONFIRMED'
                or matching[0].get('source_sha256') != expected['profile_sha256']
                or matching[0].get('source') != expected['profile_source']
                or matching[0].get('dob') != expected['dob']
                or matching[0].get('club_tm_id') != expected['club_tm_id']
                or matching[0].get('loan_owner_tm_id')):
            raise ValueError('Primary roster profile identity or ownership changed')
        for digest in (expected['source_sha256'], expected['profile_sha256']):
            bind('data/raw/transfermarkt/' + digest + '.html', digest)
        actual = [r for r in observations if r.get('fm_id') == fm_id]
        normalize = lambda rows: sorted(json.dumps(r, sort_keys=True) for r in rows)
        if not actual or normalize(actual) != normalize(review['expected_dfb_observations']):
            raise ValueError('Primary roster observations changed')
        for observed in actual:
            bind('data/raw/dfb/' + observed['source_sha256'] + '.html', observed['source_sha256'])
        evidence = review['official_evidence']
        roles = {e.get('role'): e for e in evidence}
        if len(evidence) != 3 or set(roles) != {'DESTINATION_PROFILE', 'DESTINATION_ANNOUNCEMENT', 'LEAGUE_DEPARTURES'}:
            raise ValueError('Three reviewed primary evidence roles required')
        for e in evidence:
            url = urlsplit(e.get('url', ''))
            if (e.get('status') != 'REQUIRED_FACTS_PRESENT' or url.scheme != 'https'
                    or not url.hostname or not e.get('required')
                    or not all(isinstance(f, str) and f.strip() for f in e['required'])):
                raise ValueError('Incomplete official roster evidence')
            bind(e['file'], e['sha256'], e['required'])
        profile = roles['DESTINATION_PROFILE']
        announcement = roles['DESTINATION_ANNOUNCEMENT']
        league = roles['LEAGUE_DEPARTURES']
        if (urlsplit(profile['url']).hostname != urlsplit(announcement['url']).hostname
                or urlsplit(league['url']).hostname == urlsplit(profile['url']).hostname
                or born.strftime('%d-%m-%Y') not in profile['required']
                or end.strftime('%d-%m-%Y') not in profile['required']
                or joined.strftime('%d-%m-%Y') not in announcement['required']):
            raise ValueError('Independent official sources and explicit dates required')
        reviews[fm_id] = review
    return reviews, bound
