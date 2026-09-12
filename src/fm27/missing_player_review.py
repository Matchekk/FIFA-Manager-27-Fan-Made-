"""Conservative duplicate leads; these never authorize identity or database writes."""
from collections import Counter, defaultdict
from datetime import date

from .matching import normalize, person_name_key

PARTICLES = {'de', 'da', 'do', 'dos', 'das', 'van', 'von', 'di', 'del', 'la', 'le', 'el', 'al', 'jr', 'junior'}


class DuplicateReviewIndex:
    def __init__(self, players):
        self.by_dob = defaultdict(list)
        self.by_name = defaultdict(list)
        for person in players:
            self.by_dob[person.get('dob', '')].append(person)
            for name in {person_name_key(person.get('name', '')), person_name_key(person.get('common_name', ''))} - {''}:
                self.by_name[name].append(person)

    def candidates(self, evidence, profile, snapshot, target_club_id):
        if (not profile or profile.get('source_status') != 'CONFIRMED'
                or profile.get('snapshot_date') != snapshot or evidence.get('snapshot_date') != snapshot
                or not evidence.get('dob') or profile.get('dob') != evidence['dob']):
            return [], {}
        source_date = date.fromisoformat(evidence['dob'])
        found, reasons = {}, defaultdict(list)

        def add(person, reason):
            found[person['fm_id']] = person
            if reason not in reasons[person['fm_id']]:
                reasons[person['fm_id']].append(reason)

        full = Counter(normalize(profile.get('full_name', '')).split())
        for person in self.by_dob[evidence['dob']]:
            native = Counter(normalize(person.get('name', '')).split())
            if len(set(native) - PARTICLES) >= 2 and native <= full:
                add(person, 'SAME_DOB_NATIVE_NAME_COMPONENTS_IN_VERIFIED_FULL_NAME')
        names = {evidence.get('player', ''), profile.get('player', ''), profile.get('full_name', '')}
        for name in names - {''}:
            if len(set(normalize(name).split()) - PARTICLES) < 2:
                continue
            for person in self.by_name[person_name_key(name)]:
                if not person.get('dob') or person['dob'] == evidence['dob']:
                    continue
                same_club = str(person.get('club_id', '')) == str(target_club_id) and str(target_club_id) not in {'', '0'}
                nearby_date = abs((date.fromisoformat(person['dob']) - source_date).days) <= 7
                if same_club or nearby_date:
                    add(person, 'EXACT_NAME_DIFFERENT_DOB_SAME_CLUB' if same_club else 'EXACT_NAME_NEARBY_DIFFERENT_DOB')
        return list(found.values()), dict(reasons)
