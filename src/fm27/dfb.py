"""DFB public squad pages: explicit season, typed teams, dated membership."""
import datetime as dt
import re
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

BASE = "https://datencenter.dfb.de"
COMPETITIONS = {"GER1": "bundesliga", "GER2": "2-bundesliga", "GER3": "3-liga"}
TITLES = {"GER1": "Bundesliga", "GER2": "2. Bundesliga", "GER3": "3. Liga"}
POSITIONS = {"Torwart": "GK", "Abwehr": "DEF", "Mittelfeld": "MID", "Sturm": "FWD"}


def parse_page(html: str, league: str, snapshot: dt.date) -> tuple[list[dict], list[str]]:
    soup = BeautifulSoup(html, "html.parser")
    club = soup.select_one("h2.m-ClubProfileHead-headline")
    if club is None:
        raise ValueError("DFB club headline not found")
    expected = f"Kader {TITLES[league]} 2026/2027"
    headings = [h for h in soup.find_all("h3") if h.get_text(" ", strip=True) == expected]
    if len(headings) != 1:
        raise ValueError(f"Expected exactly one {expected}; no old-season fallback")
    outer = headings[0].find_next("table")
    if outer is None or "Geburtstag" not in outer.get_text():
        raise ValueError("Expected DFB squad table")
    records, seen = [], {}
    for table in outer.find_all("table"):
        head = table.find("thead", recursive=False)
        position = head.get_text(" ", strip=True) if head else ""
        if position not in POSITIONS:
            continue  # Staff rows are not player records.
        body = table.find("tbody", recursive=False)
        if body is None:
            raise ValueError("Missing squad group body")
        for row in body.find_all("tr", recursive=False):
            cells = row.find_all("td", recursive=False)
            if len(cells) != 3:
                raise ValueError("Unexpected squad row shape")
            anchor = cells[1].find("a", href=True)
            url, identity = "", ""
            if anchor is not None:
                url = urljoin(BASE, anchor["href"])
                match = re.fullmatch(r"/profil/(\d+)", urlsplit(url).path)
                if not match or urlsplit(url).hostname != "datencenter.dfb.de":
                    raise ValueError("Unexpected DFB identity link")
                identity = match[1]
            birthday = cells[2].get_text(strip=True)
            dob = dt.datetime.strptime(birthday, "%d.%m.%Y").date().isoformat() if birthday else ""
            notes = cells[1].get_text(" ", strip=True)
            name = anchor.get_text(" ", strip=True) if anchor else re.sub(r"\s*\((?:bis|ab)\s+\d{2}\.\d{2}\.\d{4}\)", "", notes).strip()
            if not name:
                raise ValueError("Empty player name")
            end = re.search(r"bis\s+(\d{2}\.\d{2}\.\d{4})", notes)
            start = re.search(r"ab\s+(\d{2}\.\d{2}\.\d{4})", notes)
            active = not (end and dt.datetime.strptime(end[1], "%d.%m.%Y").date() < snapshot)
            active = active and not (start and dt.datetime.strptime(start[1], "%d.%m.%Y").date() > snapshot)
            record = {"league": league, "club": club.get_text(" ", strip=True),
                            "player": name, "dob": dob,
                            "source_person_id": identity, "fifa_id": "", "shirt_number": cells[0].get_text(strip=True),
                            "position_group": POSITIONS[position], "membership_at_snapshot": active,
                            "membership_notes": notes, "profile_url": url,
                            "snapshot_date": snapshot.isoformat(), "source_status": "CONFIRMED"}
            key = identity or (name, dob)
            if key in seen:
                if seen[key] != record:
                    seen[key]["source_status"] = "CONFLICT"
                    record["source_status"] = "CONFLICT"
                else:
                    continue  # Identical repeated source rows are one observation.
            seen[key] = record
            records.append(record)
    if not records:
        raise ValueError("Empty DFB player roster")
    # Discover only same-league, same-season peers from the published fixture list.
    prefix = f"/competitions/{COMPETITIONS[league]}/seasons/2026-2027/teams/"
    peers = set()
    for anchor in soup.find_all("a", href=True):
        url = urlsplit(urljoin(BASE, anchor["href"]))
        if url.hostname == "datencenter.dfb.de" and url.path.startswith(prefix):
            peers.add(BASE + url.path)
    return records, sorted(peers)
