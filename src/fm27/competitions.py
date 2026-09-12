"""Read-only 2013.12 league structure checks before any native league mutation."""
import re
from collections import Counter

from .database import check_versions


def parse_leagues(text):
    check_versions(text.lstrip("\ufeff").splitlines())
    result = []
    def section(block, key):
        match = re.search(rf"%INDEX%{key}\n(.*?)\n%INDEXEND%{key}", block, re.S)
        return match[1].splitlines() if match else []
    for block in text.replace("\r\n", "\n").split("%INDEX%COMPETITION\n")[1:]:
        block = block.split("%INDEXEND%COMPETITION")[0]
        lines = block.splitlines()
        if lines[0] != "DB_LEAGUE":
            continue
        ident = re.fullmatch(r"\{\s*(\d+),\s*([A-Z0-9_]+),\s*(\d+)\s*\}", lines[1])
        if not ident:
            raise ValueError("Unsupported league identifier")
        ints = lambda value: [int(v.strip()) for v in value.split(",") if v.strip()]
        teams = section(block, "TEAMS")
        if len(teams) != 1:
            raise ValueError("Unexpected league team section")
        result.append({"country_id": int(ident[1]), "competition_type": ident[2], "division": int(ident[3]), "team_count": int(lines[2]),
                       "league_level": int(lines[3]), "relegation_rule": lines[4], "rounds": int(lines[6]),
                       "team_references": [int(v.strip(), 16) for v in teams[0].split(",") if v.strip()],
                       "matchdays": ints(",".join(section(block, "MATCHDAYS"))),
                       "matchdays2": ints(",".join(section(block, "MATCHDAYS2"))),
                       "fixtures": [ints(line) for line in section(block, "FIXTURE")], "raw_block": block})
    return result


def fixture_errors(league):
    n, rounds = league["team_count"], league["rounds"]
    if not 2 <= n <= 24 or rounds < 1:
        return ["UNSUPPORTED_TEAM_OR_ROUND_COUNT"]
    errors = []
    expected_days = (n - 1 + n % 2) * rounds
    if len(league["team_references"]) != n or len(set(league["team_references"])) != n:
        errors.append("TEAM_COUNT_OR_DUPLICATE")
    if len(league["fixtures"]) != expected_days:
        errors.append("FIXTURE_DAY_COUNT")
    for key in ("matchdays", "matchdays2"):
        dates = league[key]
        if key == "matchdays2" and not dates:
            continue
        if len(dates) != expected_days or len(set(dates)) != len(dates) or dates != sorted(dates):
            errors.append(key.upper() + "_COUNT_OR_ORDER")
    opponents, directed = Counter(), Counter()
    for day in league["fixtures"]:
        if len(day) != (n // 2) * 2 or len(set(day)) != len(day) or any(t < 1 or t > n for t in day):
            errors.append("INVALID_MATCHDAY_PARTICIPATION")
            continue
        for a, b in zip(day[::2], day[1::2]):
            opponents[tuple(sorted((a, b)))] += 1
            directed[(a, b)] += 1
    if len(opponents) != n * (n - 1) // 2 or any(count != rounds for count in opponents.values()):
        errors.append("PAIRING_COVERAGE")
    if rounds % 2 == 0 and any(directed[(a, b)] != rounds // 2 for a in range(1, n + 1) for b in range(1, n + 1) if a != b):
        errors.append("HOME_AWAY_IMBALANCE")
    return sorted(set(errors))
