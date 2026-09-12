"""Transfer events from season-specific public transfer tables, never rumours."""
import datetime as dt
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

LEAGUES = {"ENG1": ("premier-league","GB1"), "ITA1": ("serie-a","IT1"),
           "ESP1": ("laliga","ES1"), "GER1": ("bundesliga","L1"),
           "FRA1": ("ligue-1","FR1"), "POR1": ("liga-portugal","PO1"),
           "NED1": ("eredivisie","NL1"), "BEL1": ("jupiler-pro-league","BE1"),
           "TUR1": ("super-lig","TR1"), "CZE1": ("chance-liga","TS1"),
           "GER2": ("2-bundesliga","L2"), "GER3": ("3-liga","L3")}


def club_link(anchor):
    if not anchor:
        raise ValueError("Club link missing")
    match = re.search(r"/verein/(\d+)", anchor["href"])
    if not match:
        raise ValueError("No club ID")
    name = anchor.get("title", "").removesuffix("Array") or anchor.get_text(" ", strip=True)
    if not name and anchor.find("img"):
        name = anchor.find("img").get("alt", "")
    return match[1], name


def parse_page(html, league):
    soup = BeautifulSoup(html, "html.parser")
    selected = soup.select_one('select[name="saison_id"] option[selected]')
    if not selected or selected.get("value") != "2026":
        raise ValueError("Source season is not 2026/27")
    if "Transfers 26/27" not in soup.title.get_text():
        raise ValueError("Not a confirmed-transfer season page")
    rows, clubs = [], {}
    for box in soup.select("div.box"):
        heading = box.find("h2", recursive=False)
        if not heading or not re.fullmatch(r"to-\d+", heading.get("id", "")):
            continue
        owner_id, owner = club_link(heading.find("a", href=True))
        clubs[owner_id] = owner
        for table in box.select("div.responsive-table > table"):
            first = table.find("th")
            direction = first.get_text(strip=True) if first else ""
            if direction not in {"Zugang", "Abgang"}:
                continue
            for tr in table.find("tbody").find_all("tr", recursive=False):
                cells = tr.find_all("td", recursive=False)
                if len(cells) != 9:
                    raise ValueError("Unexpected transfer row shape")
                anchor = cells[0].find("a", href=re.compile(r"/profil/spieler/\d+"))
                if not anchor:
                    raise ValueError("Transfer player identity missing")
                player_id = re.search(r"/spieler/(\d+)", anchor["href"])[1]
                other_anchor = cells[6].find("a", href=True) or cells[7].find("a", href=True)
                if other_anchor:
                    other_id, other = club_link(other_anchor)
                else:
                    other_id, other = "", cells[7].get_text(" ", strip=True)
                    if other not in {"Karriereende", "Vereinslos", "unbekannt", "Unknown"}:
                        raise ValueError("Unidentified counterpart club")
                fee = cells[8].get_text(" ", strip=True)
                event_link = cells[8].find("a", href=True)
                event_match = re.search(r"/transfer_id/(\d+)", event_link["href"]) if event_link else None
                kind = "LOAN_RETURN" if "Leih-Ende" in fee else "LOAN" if "Leih" in fee else "PERMANENT"
                if other in {"Karriereende", "Retired"}:
                    kind = "RETIRED"
                elif other in {"Vereinslos", "Without Club"}:
                    kind = "FREE_AGENT" if direction == "Abgang" else "FREE_TRANSFER"
                date = re.search(r"\d{2}\.\d{2}\.\d{4}", fee)
                rows.append({"league":league,"club":owner,"club_tm_id":owner_id,"direction":direction,
                             "player":anchor.get("title") or anchor.get_text(strip=True),"player_tm_id":player_id,
                             "profile_url":urljoin("https://www.transfermarkt.de",anchor["href"]),
                             "age":cells[1].get_text(strip=True),"position":cells[4].get_text(strip=True),
                             "old_club":other if direction=="Zugang" else owner,
                             "old_club_tm_id":other_id if direction=="Zugang" else owner_id,
                             "new_club":owner if direction=="Zugang" else other,
                             "new_club_tm_id":owner_id if direction=="Zugang" else other_id,
                             "transfer_type":kind,"event_id":event_match[1] if event_match else "",
                             "explicit_event_date":dt.datetime.strptime(date[0],"%d.%m.%Y").date().isoformat() if date else "",
                             "fee_text":fee,"source_status":"REVIEW_REQUIRED" if other in {"unbekannt","Unknown"} else "CONFIRMED","database_action":"REVIEW_REQUIRED"})
    if not rows or not clubs:
        raise ValueError("No transfer tables")
    return rows, clubs


def parse_squad(html, league, club_id):
    soup = BeautifulSoup(html, "html.parser")
    if "Kader im Detail 26/27" not in soup.title.get_text():
        raise ValueError("Not the requested detailed 2026/27 squad")
    selected = soup.select_one('select[name="saison_id"] option[selected]')
    if not selected or selected.get("value") != "2026":
        raise ValueError("Wrong squad season")
    table = soup.select_one("table.items")
    if not table or "Geb./Alter" not in table.find("thead").get_text() or "Vertrag" not in table.find("thead").get_text():
        raise ValueError("Required squad columns missing")
    heading = soup.select_one("h1.data-header__headline-wrapper")
    if not heading:
        raise ValueError("Club headline missing")
    rows, seen = [], set()
    def date_value(text):
        m = re.search(r"\d{2}\.\d{2}\.\d{4}", text)
        return dt.datetime.strptime(m[0],"%d.%m.%Y").date().isoformat() if m else ""
    for tr in table.find("tbody").find_all("tr",recursive=False):
        cells = tr.find_all("td",recursive=False)
        if len(cells) != 10:
            raise ValueError("Unexpected squad column count")
        anchor = cells[1].find("a",href=re.compile(r"/profil/spieler/\d+"))
        if not anchor:
            raise ValueError("Missing squad player link")
        identity = re.search(r"/spieler/(\d+)",anchor["href"])[1]
        if identity in seen:
            raise ValueError("Duplicate person in current squad")
        seen.add(identity)
        notes = sorted({a["title"] for a in cells[1].find_all("a",title=True) if "Datum:" in a["title"] or "Leihe" in a["title"]})
        inline = cells[1].select_one("table.inline-table")
        position = inline.find_all("tr")[-1].get_text(" ",strip=True) if inline else ""
        rows.append({"league":league,"club":heading.get_text(" ",strip=True),"club_tm_id":club_id,
                     "player":anchor.get_text(" ",strip=True),"player_tm_id":identity,
                     "dob":date_value(cells[2].get_text()),"position":position,
                     "shirt_number":cells[0].get_text(strip=True),"joined":date_value(cells[6].get_text()),
                     "contract_until":date_value(cells[8].get_text()),
                     "change_notes":__import__('json').dumps(notes,ensure_ascii=False),
                     "profile_url":urljoin("https://www.transfermarkt.de",anchor["href"]),
                     "source_status":"CONFIRMED","database_action":"REVIEW_REQUIRED"})
    if not rows:
        raise ValueError("Empty current squad")
    return rows
