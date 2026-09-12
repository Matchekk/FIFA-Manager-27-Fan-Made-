"""Explicitly reviewed prior-season permanent arrivals, bound to current people."""
import datetime as dt
import json
import re
from collections import defaultdict

from .common import sha256
from .matching import IdentityIndex
from .player_identities import (NATIVE_FIELDS, PROFILE_FIELDS, reviewed_profile_match,
                                values, verified_profile)
from .transfermarkt import LEAGUES, parse_page

EVENT_FIELDS = ('event_id', 'player_tm_id', 'old_club_tm_id', 'new_club_tm_id',
                'transfer_type', 'direction', 'club_tm_id', 'explicit_event_date')


def load_historical_transfers(root, snapshot, profiles, players, aliases, current_events,
                              *, baseline_path=None):
    path = root / 'data/overrides/historical_transfers.json'
    if not path.exists():
        return [], {}
    manifest = json.loads(path.read_text(encoding='utf-8'))
    if manifest.get('schema') != 1 or manifest.get('snapshot_date') != snapshot:
        raise ValueError('Historical event manifest schema/snapshot mismatch')
    if manifest.get('identity_manifest_sha256') != sha256(root / 'data/overrides/player_identities.json'):
        raise ValueError('Historical event identity review changed')
    today = dt.date.fromisoformat(snapshot)
    by_person = defaultdict(list)
    for profile in profiles:
        by_person[profile['player_tm_id']].append(profile)
    index = IdentityIndex(players)
    natural_items = [r for r in manifest['rows'] if r.get('identity_basis') == 'NATURAL_DOB_NAME']
    claims = defaultdict(set)
    if natural_items:
        if baseline_path is None or manifest.get('baseline_sha256') != sha256(baseline_path):
            raise ValueError('Historical natural identity baseline changed or missing')
        # A second source person must not claim the same native identity.
        for profile in profiles:
            for name in {profile.get('player', ''), profile.get('full_name', '')} - {''}:
                _, found = index.match({'player': name, 'dob': profile.get('dob', '')})
                for person in found:
                    claims[person['fm_id']].add(profile['player_tm_id'])
    seen, seen_people, rows, cache = set(), set(), [], {}
    selections = defaultdict(set)
    for item in manifest['rows']:
        selections[(item['source_sha256'], item['league'], item['season'])].add(item['event']['event_id'])
    for item in manifest['rows']:
        event = item['event']
        ident, event_id = event['player_tm_id'], event['event_id']
        if (not re.fullmatch(r'[1-9][0-9]*', event_id) or event_id in seen or ident in seen_people
                or event['transfer_type'] != 'PERMANENT'):
            raise ValueError('Historical event must be a unique reviewed permanent arrival')
        seen.add(event_id)
        seen_people.add(ident)
        if item.get('reviewed_on') != snapshot or not item.get('reviewed_by') or not item.get('reason'):
            raise ValueError('Historical event review is missing')
        season = item['season']
        if type(season) is not int or season != today.year - 1:
            raise ValueError('Historical supplement is restricted to the preceding season')
        league = item['league']
        if league not in LEAGUES:
            raise ValueError('Historical event league is outside scope')
        slug, code = LEAGUES[league]
        url = f'https://www.transfermarkt.de/{slug}/transfers/wettbewerb/{code}/saison_id/{season}'
        if item['source'] != url or not re.fullmatch('[0-9a-f]{64}', item['source_sha256']):
            raise ValueError('Historical event URL or digest mismatch')
        key = (item['source_sha256'], league, season)
        if key not in cache:
            source = root / 'data/raw/transfermarkt' / (item['source_sha256'] + '.html')
            if sha256(source) != item['source_sha256']:
                raise ValueError('Historical transfer source bytes changed')
            cache[key], _ = parse_page(source.read_text(encoding='utf-8-sig'), league,
                expected_season=season, selected_event_ids=selections[key])
        observations = [r for r in cache[key] if r['event_id'] == event_id]
        matches = [r for r in observations if all(r.get(k) == event.get(k) for k in EVENT_FIELDS)]
        # Same-league moves have an incoming and an outgoing observation. Select
        # exactly the reviewed incoming row, and require its mirror to agree.
        endpoints = ('player_tm_id', 'old_club_tm_id', 'new_club_tm_id',
                     'transfer_type', 'explicit_event_date')
        if (len(matches) != 1 or event['direction'] != 'Zugang'
                or event['club_tm_id'] != event['new_club_tm_id']
                or any(any(r.get(k) != event.get(k) for k in endpoints) for r in observations)):
            raise ValueError('Historical event identity/endpoints/type differ from raw source')
        parsed = matches[0]
        if parsed['source_status'] != 'CONFIRMED' or event['explicit_event_date']:
            raise ValueError('Historical supplement requires the reviewed undated permanent table row')
        matched_profiles = by_person[ident]
        if len(matched_profiles) != 1:
            raise ValueError('Historical event needs one current profile')
        profile = matched_profiles[0]
        verified = verified_profile(root, profile, snapshot)
        profile_fields = PROFILE_FIELDS + ('joined', 'contract_until', 'loan_owner_tm_id')
        if any(profile.get(k) != verified.get(k) for k in profile_fields):
            raise ValueError('Historical event profile differs from immutable source')
        if (profile['source_sha256'] != item['profile_sha256'] or profile['dob'] != item['dob']
                or profile['club_tm_id'] != event['new_club_tm_id'] or profile['joined'] != item['joined']
                or profile['loan_owner_tm_id'] or profile.get('source_status') != 'CONFIRMED'):
            raise ValueError('Historical event current profile binding changed')
        joined = dt.date.fromisoformat(profile['joined'])
        if not dt.date(season, 7, 1) <= joined <= dt.date(season + 1, 6, 30) <= today:
            raise ValueError('Historical event is outside the reviewed prior season')
        original = index.match({'player': profile['player'], 'dob': profile['dob']})
        basis = item.get('identity_basis', 'REVIEWED_IDENTITY')
        if basis == 'NATURAL_DOB_NAME':
            method, people = original
            if method != 'DOB_NAME' or len(people) != 1:
                raise ValueError('Historical natural identity is not a unique exact DOB/name match')
            person = people[0]
            fields = NATIVE_FIELDS + ('common_name',)
            native = item.get('native_identity', {})
            if (set(native) != set(fields) or values(person, fields) != values(native, fields)
                    or len(index.by_fm[person['fm_id']]) != 1
                    or claims[person['fm_id']] != {ident}):
                raise ValueError('Historical natural identity binding changed or multiply claimed')
            fifa = person.get('fifa_id', '')
            if (fifa not in {'', '0'} and len(index.by_fifa[fifa]) != 1
                    or str(profile.get('fifa_id', '')) not in {'', '0', fifa}):
                raise ValueError('Historical natural FIFA identity conflicts')
            for name in {profile['player'], profile.get('full_name', '')} - {''}:
                name_method, found = index.match({'player': name, 'dob': profile['dob']})
                if name_method == 'AMBIGUOUS' or any(p['fm_id'] != person['fm_id'] for p in found):
                    raise ValueError('Historical profile names conflict with native identities')
            # Existing spelling reviews remain authoritative if present.
            method, people = reviewed_profile_match(index, profile, profile, original)
        elif basis == 'REVIEWED_IDENTITY' and profile.get('_reviewed_identity') is not None:
            method, people = reviewed_profile_match(index, profile, profile, original)
        else:
            raise ValueError('Historical event requires an explicit supported identity review')
        if method in {'CONFLICT', 'AMBIGUOUS'} or len(people) != 1 or people[0]['fm_id'] != item['fm_id']:
            raise ValueError('Historical event existing native identity is unresolved')
        origin = aliases.get(event['old_club_tm_id'], {})
        destination = aliases.get(event['new_club_tm_id'], {})
        if (origin.get('club_id') != people[0]['club_id'] or not destination.get('club_id')
                or destination['club_id'] == origin.get('club_id')):
            raise ValueError('Historical event native origin/destination binding is invalid')
        for current in current_events:
            if current.get('event_id') == event_id and any(current.get(k) != event.get(k) for k in
                    ('player_tm_id', 'old_club_tm_id', 'new_club_tm_id', 'transfer_type', 'explicit_event_date')):
                raise ValueError('Historical event conflicts with an already captured event ID')
        rows.append({**parsed, 'source': url, 'source_sha256': item['source_sha256'],
            'snapshot_date': snapshot, 'source_season': str(season),
            'historical_profile_sha256': profile['source_sha256']})
    return rows, {'manifest_sha256': sha256(path), 'rows': len(rows), 'reviewed_events': manifest['rows']}
