"""Decode FIFAM club-link team bits without flattening reserve-team ownership."""
TEAM_TYPES = {0: "FIRST", 1: "RESERVE", 2: "YOUTH_A", 4: "YOUTH_B"}


def decode_reference(reference: int) -> tuple[int, str]:
    kind = reference >> 24
    if kind not in TEAM_TYPES or not reference & 0xFFFFFF:
        raise ValueError("Unsupported/empty FIFAM team reference")
    return reference & 0xFFFFFF, TEAM_TYPES[kind]


def project_teams(clubs: list[dict], memberships: dict[int, str]) -> list[dict]:
    by_reference = {int(c["reference_id"]): c for c in clubs}
    teams = []
    for reference, league in sorted(memberships.items()):
        base, kind = decode_reference(reference)
        if base not in by_reference:
            raise ValueError(f"Unresolved team reference: {reference:08x}")
        club = by_reference[base]
        teams.append({"league": league, "club_id": club["club_id"], "club": club["club"],
                      "team_type": kind, "reference_id": reference,
                      "team": club["club"] + (" II" if kind == "RESERVE" else "" if kind == "FIRST" else f" {kind}")})
    return teams


def attach_team_league(players: list[dict], teams: list[dict]) -> None:
    membership = {(str(t["club_id"]), t["team_type"]): t["league"] for t in teams}
    for player in players:
        # Generic YOUTH flags do not identify Youth A vs B; leave unresolved.
        player["team_league"] = membership.get((str(player["club_id"]), player["squad"]), "")
