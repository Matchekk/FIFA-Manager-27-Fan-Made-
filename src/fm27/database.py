"""Read-only identity projection of audited 2013.12 text databases.

Not a replacement for FifamDatabase: no writer, no Master.dat decoder, no
simulation or level emulation. Field positions derive from pinned upstream
FifamClub::Read, FifamPlayer::Read and FifamPlayerContract::Read.
"""
import csv
import datetime as dt
import json
import re
from pathlib import Path

from .common import external_output, sha256, write_csv, write_json
from .team_scope import attach_team_league, project_teams

VERSION = 0x20130012
POSITIONS = "NONE GK RB LB CB DM RM LM CM RW LW AM CF ST".split()
ATTRIBUTES = ("BallControl Dribbling Finishing ShotPower LongShots Volleys Crossing "
              "Passing LongPassing Header TackleStanding TackleSliding ManMarking "
              "Acceleration Pace Agility Jumping Strength Stamina Balance PosOffensive "
              "PosDefensive Vision Aggression Reactions Composure Consistency "
              "TacticAwareness FreeKicks Corners PenaltyShot Diving Handling "
              "Positioning OneOnOne Reflexes Kicking").split()
PLAYER_FIELDS = ["fm_id", "fifa_id", "football_manager_id", "transfermarkt_id",
                 "name", "common_name", "dob", "nationality", "club_id", "club",
                 "country_id", "league", "team_league", "position", "squad", "shirt_number", "reserve_shirt_number",
                 "captain", "contract_until", "contract_joined", "contract_loan_flag",
                 "playing_style", "talent", "experience", "starting_conditions",
                 "attributes", "source_file", "source_line"]
CLUB_FIELDS = ["club_id", "reference_id", "fifa_id", "club", "country_id", "league"]


def lines_from(path: Path) -> list[str]:
    # Modern upstream Unicode output has a UTF-8 BOM. No lossy fallback decoding.
    return path.read_text(encoding="utf-8-sig").splitlines()


def check_versions(lines: list[str]) -> None:
    versions = [int(lines[n + 1]) for n, line in enumerate(lines) if line == "%INDEX%VERSION"]
    if not versions or any(v != VERSION for v in versions):
        raise ValueError("Only audited format 2013.12 is supported; refusing guessed offsets")


def split_csv(line: str) -> list[str]:
    return next(csv.reader([line], strict=True))


def player_record(body: list[str], fm_id: int | str, club: dict, path: Path, line: int) -> dict:
    if len(body) < 40 or body[0] != "0":
        raise ValueError(f"Unexpected PLAYER block at {path}:{line}")
    names = body[1].split("|")
    if len(names) < 4:
        raise ValueError("Truncated player names")
    dob = dt.date.fromisoformat(body[4]).isoformat()
    basics = body[5].split(",")
    if len(basics) != 5 or len(body[6].split(",")) != 14:
        raise ValueError("Invalid basic attributes or position biases")
    values = list(map(int, body[7].split(",")))
    if len(values) != len(ATTRIBUTES):
        raise ValueError("Unexpected detailed-attribute count")
    position = int(basics[4])
    if not 0 <= position < len(POSITIONS):
        raise ValueError("Invalid serialized position")
    contract_index = body.index("%INDEX%CONTRACT")
    contract_end = body.index("%INDEXEND%CONTRACT", contract_index)
    contract = body[contract_index + 1:contract_end]
    if len(contract) != 4 or len(contract[0].split(",")) != 24:
        raise ValueError("Unsupported contract structure")
    tail = body[contract_end + 1:]
    if len(tail) != 9:
        raise ValueError("Unsupported identity tail; refusing to guess FIFA ID")
    conditions_count = int(body[23])
    if body[24 + conditions_count] != "%INDEX%HIST":
        raise ValueError("Starting-conditions boundary mismatch")
    conditions = [list(map(int, value.split(","))) for value in body[24:24 + conditions_count]]
    if any(len(value) != 6 for value in conditions):
        raise ValueError("Invalid starting condition")
    flags = int(body[9])
    return {"fm_id": fm_id, "fifa_id": int(tail[6]), "football_manager_id": int(tail[7]),
            "transfermarkt_id": int(tail[8]), "name": " ".join(n for n in names[:2] if n),
            "common_name": names[3] or names[2], "dob": dob,
            "nationality": body[2].split(",")[0], "club_id": club.get("club_id", 0),
            "club": club.get("club", "FREE_AGENT"), "country_id": club.get("country_id", 0),
            "league": club.get("league", ""), "position": POSITIONS[position],
            "squad": "YOUTH" if flags & 8 else "RESERVE" if int(body[8]) else "FIRST",
            "shirt_number": int(body[15].split(",")[4]), "captain": bool(flags & 128),
            "reserve_shirt_number": int(body[15].split(",")[5]),
            "contract_until": contract[1], "contract_joined": contract[0].split(",")[-1],
            "contract_loan_flag": bool(int(contract[0].split(",")[11]) & 128),
            "playing_style": int(body[12]), "talent": int(basics[0]),
            "experience": int(basics[3]), "starting_conditions": json.dumps(conditions),
            "attributes": json.dumps(dict(zip(ATTRIBUTES, values)), sort_keys=True),
            "source_file": path.name, "source_line": line}


def league_memberships(db: Path, scope: dict) -> dict[int, str]:
    result = {}
    for competition in scope["competitions"]:
        country, division = competition["country_id"], competition["division"]
        lines = lines_from(db / "script" / f"CountryScript{country}.sav")
        check_versions(lines)
        blocks = "\n".join(lines).split("%INDEX%COMPETITION\n")[1:]
        selected = [block for block in blocks if re.match(
            rf"DB_LEAGUE\n\{{\s*{country},\s*LEAGUE,\s*{division}\s*\}}\n", block)]
        if len(selected) != 1:
            raise ValueError(f"Expected one league block for {competition['key']}")
        block = selected[0].split("%INDEXEND%COMPETITION")[0]
        teams = block.split("%INDEX%TEAMS\n")[1].split("\n%INDEXEND%TEAMS")[0]
        ids = [int(s.strip(), 16) for s in teams.split(",") if s.strip()]
        if len(ids) != int(block.splitlines()[2]) or len(set(ids)) != len(ids):
            raise ValueError("League participant count/uniqueness mismatch")
        for ref in ids:
            if ref in result:
                raise ValueError("Club reference appears in multiple covered divisions")
            result[ref] = competition["key"]
    return result


def read_country(path: Path, country: int, leagues: dict) -> tuple[list, list]:
    lines = lines_from(path)
    check_versions(lines)
    clubs, players, active = [], [], {}
    index = 0
    while index < len(lines):
        club_match = re.fullmatch(r"%INDEX%CLUB(\d+)", lines[index])
        if club_match:
            if lines[index + 1:index + 4] != ["%INDEX%VERSION", str(VERSION), "%INDEXEND%VERSION"]:
                raise ValueError("Unexpected club header")
            reference = country << 16 | int(club_match[1])
            names = split_csv(lines[index + 10])
            active = {"club_id": int(lines[index + 4]), "reference_id": reference,
                      "fifa_id": int(lines[index + 5]), "club": names[1] if len(names) > 1 else names[0],
                      "country_id": country, "league": leagues.get(reference, "")}
            clubs.append(active)
        elif re.fullmatch(r"%INDEXEND%CLUB\d+", lines[index]):
            active = {}
        elif lines[index] == "%INDEX%PLAYER":
            end = lines.index("%INDEXEND%PLAYER", index + 1)
            # Without.sav has no persisted FM person IDs. Native reader allocates
            # them after all countries; do not invent stable IDs for free agents.
            fm_id = "" if path.name == "Without.sav" else int(lines[index - 1])
            players.append(player_record(lines[index + 1:end], fm_id,
                                         active, path, index + 1))
            index = end
        index += 1
    return clubs, players


def export(db: Path, output: Path, scope_file: Path) -> dict:
    db = db.resolve(strict=True)
    output = external_output(output, db.parent)
    scope = json.loads(scope_file.read_text(encoding="utf-8"))
    memberships = league_memberships(db, scope)
    clubs, players, provenance = [], [], []
    paths = sorted((db / "data").glob("CountryData*.sav"))
    if not paths:
        raise ValueError("No CountryData files")
    if (db / "Without.sav").exists():
        paths.append(db / "Without.sav")
    for path in paths:
        country = int(re.search(r"CountryData(\d+)", path.name)[1]) if path.name != "Without.sav" else 0
        before = sha256(path)
        found_clubs, found_players = read_country(path, country, memberships)
        if sha256(path) != before:
            raise ValueError("Source changed during extraction; discard this run")
        clubs.extend(found_clubs)
        players.extend(found_players)
        provenance.append({"path": path.relative_to(db).as_posix(), "sha256": before})
    teams = project_teams(clubs, memberships)
    attach_team_league(players, teams)
    covered = [p for p in players if p["league"] or p["team_league"]]
    write_csv(output / "players.csv", PLAYER_FIELDS, players)
    write_csv(output / "clubs.csv", CLUB_FIELDS, clubs)
    write_csv(output / "covered_squads.csv", PLAYER_FIELDS, covered)
    write_csv(output / "covered_teams.csv", list(teams[0]), teams)
    report = {"status": "READ_ONLY_PROJECTION_NOT_A_GAME_DATABASE", "format": "2013.12",
              "database_path": str(db), "players": len(players), "clubs": len(clubs),
              "covered_players": len(covered), "covered_clubs": sum(bool(c["league"]) for c in clubs),
              "covered_teams": len(teams), "reserve_teams": sum(t["team_type"] == "RESERVE" for t in teams),
              "coverage_basis": "Installed league membership; real 2026/27 membership still requires reconciliation",
              "sources": provenance, "limitations": ["No Master.dat decode or native write/round-trip",
              "Loan/future conditions preserved as raw six-field records, not flattened into guessed ownership"]}
    write_json(output / "export.json", report)
    return report
