"""Read the official FC27 website payload, not a guessed native FC27 schema."""
import datetime as dt
import json

from bs4 import BeautifulSoup

LEAGUES = {"ENG1": "13", "ITA1": "31", "ESP1": "53", "GER1": "19", "FRA1": "16",
           "POR1": "308", "NED1": "10", "BEL1": "4", "TUR1": "68", "CZE1": "319",
           "GER2": "20", "GER3": "2076"}


def page_props(html):
    nodes = BeautifulSoup(html, "html.parser").find_all("script", id="__NEXT_DATA__")
    if len(nodes) != 1:
        raise ValueError("Expected one EA website data payload")
    props = json.loads(nodes[0].string)["props"]["pageProps"]
    if props["gameDetails"]["slug"] != "fc-27":
        raise ValueError("EA source is not FC27; refuse old-game fallback")
    return props


def league_page(props, league):
    group = props["teamGroup"]
    if str(group["id"]) != LEAGUES[league] or group["gender"]["id"] != 0:
        raise ValueError("Wrong league/gender response")
    allowed = {t["id"] for t in group["teams"]}
    entries = props["ratingsEntries"]
    rows, seen = [], set()
    for p in entries["items"]:
        if p["gender"]["id"] != 0 or p["team"]["id"] not in allowed:
            raise ValueError("Player outside requested men's league")
        if type(p["id"]) is not int or p["id"] <= 0 or p["id"] in seen:
            raise ValueError("Invalid or repeated EA ID in response")
        seen.add(p["id"])
        stats = {k: v["value"] for k, v in p["stats"].items()}
        if any(type(v) is not int or not 0 <= v <= 99 for v in stats.values()):
            raise ValueError("Unexpected EA attribute value")
        rows.append({"league": league, "fifa_id": p["id"], "club_fifa_id": p["team"]["id"],
                     "club": p["team"]["label"], "player": " ".join(n for n in (p["firstName"],p["lastName"]) if n),
                     "common_name": p["commonName"] or "", "dob": dt.datetime.strptime(p["birthdate"], "%m/%d/%Y %H:%M").date().isoformat(),
                     "position": p["position"]["shortLabel"], "ea_overall": p["overallRating"],
                     "attributes": json.dumps(stats, sort_keys=True),
                     "affiliation_status": "REVIEW_REQUIRED", "rating_evidence_status": "CONFIRMED",
                     "source_phase": "PRE_ANNOUNCED_SEPTEMBER_10_UPDATE"})
    return rows, entries["totalItems"], group
