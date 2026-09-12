"""Keep squad membership validation explicit beside unchanged rating profiles."""
from collections import Counter
from datetime import datetime


def identity_date(value):
    for pattern in ('%Y-%m-%d', '%d.%m.%Y'):
        try:
            return datetime.strptime(value, pattern).date()
        except ValueError:
            pass
    raise ValueError('Unsupported or invalid identity date')


def planned_squad_flags(before, after, plan):
    changes = {r['fm_id']: r for r in plan}
    if len(changes) != len(plan) or len({r['fm_id'] for r in before}) != len(before):
        raise ValueError('Duplicate planned or source person')
    fields = ('fifa_id', 'dob', 'name', 'club_id', 'in_reserve', 'in_youth')
    expected, actual = Counter(), Counter()
    applied = set()
    changed = 0
    for source in before:
        row = dict(source)
        change = changes.get(row['fm_id'])
        if change:
            if (change['fifa_id'] != row['fifa_id'] or identity_date(change['dob']) != identity_date(row['dob'])
                    or change['old_club_id'] != row['club_id']
                    or change['team_type'] not in {'FIRST', 'RESERVE'}):
                raise ValueError('Planned squad change does not match native source')
            flags = ('1' if change['team_type'] == 'RESERVE' else '0', '0')
            changed += flags != (row['in_reserve'], row['in_youth'])
            row.update(club_id=change['new_club_id'], in_reserve=flags[0], in_youth=flags[1])
            applied.add(row['fm_id'])
        expected[tuple(row[f] for f in fields)] += 1
    if applied != set(changes):
        raise ValueError('Planned squad person absent from native source')
    for row in after:
        actual[tuple(row[f] for f in fields)] += 1
    return dict(status='PASS' if expected and expected == actual else 'FAIL',
        expected=expected.total(), actual=actual.total(), planned_people=len(plan),
        planned_flag_changes=changed, missing=(expected-actual).total(), added=(actual-expected).total())
