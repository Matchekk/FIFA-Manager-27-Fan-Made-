"""Explicit, cached public-source retrieval; no network in parser/tests."""
import datetime as dt
import hashlib
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

from .common import write_csv, write_json

FPL_URL = "https://fantasy.premierleague.com/api/bootstrap-static/"


def fetch_fpl(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now(dt.timezone.utc)
    request = urllib.request.Request(FPL_URL, headers={"User-Agent": "FM27Research/0.1 (local, no telemetry)"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = response.read(16 * 1024 * 1024 + 1)
                if len(payload) > 16 * 1024 * 1024:
                    raise ValueError("Source exceeds bounded snapshot size")
                headers = {k: response.headers.get(k) for k in ("Date", "Last-Modified", "ETag", "Content-Type")}
            break
        except urllib.error.HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt == 2:
                raise
            time.sleep(2 ** attempt)
        except (TimeoutError, urllib.error.URLError):
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)
    digest = hashlib.sha256(payload).hexdigest()
    path = output / f"fpl-{stamp.strftime('%Y%m%dT%H%M%SZ')}-{digest[:12]}.json"
    with path.open("xb") as stream:
        stream.write(payload)
    manifest = {"url": FPL_URL, "retrieved_at": stamp.isoformat(), "sha256": digest,
                "snapshot": path.name, "headers": headers,
                "source_role": "Official fantasy roster evidence, not a complete player registration database"}
    write_json(path.with_suffix(".provenance.json"), manifest)
    return manifest


def parse_fpl(payload: dict, expected_season_start: int) -> list[dict]:
    teams = payload["teams"]
    elements = payload["elements"]
    if not isinstance(teams, list) or not isinstance(elements, list) or len(teams) != 20:
        raise ValueError("Unexpected FPL schema/team count")
    events = payload["events"]
    first = next(e for e in events if e["id"] == 1)
    if dt.datetime.fromisoformat(first["deadline_time"].replace("Z", "+00:00")).year != expected_season_start:
        raise ValueError("FPL snapshot is not for the requested season; no relabeling")
    club_ids = {t["id"]: t["name"] for t in teams}
    if len(club_ids) != len(teams):
        raise ValueError("Duplicate FPL team IDs")
    rows, seen = [], set()
    for player in elements:
        if player["id"] in seen or player["team"] not in club_ids:
            raise ValueError("Duplicate player/unknown team in FPL source")
        seen.add(player["id"])
        rows.append({"fpl_id": player["id"], "opta_code": player.get("opta_code", ""),
                     "player": (player["first_name"] + " " + player["second_name"]).strip(),
                     "common_name": player["web_name"], "club": club_ids[player["team"]],
                     "position_group": player["element_type"], "fpl_status": player["status"],
                     "fifa_id": "", "dob": player.get("birth_date") or "",
                     "shirt_number": player.get("squad_number") or "",
                     "removed": player.get("removed", False),
                     "database_action": "IDENTITY_REVIEW_REQUIRED"})
    return rows


def project_fpl(source: Path, output: Path, year: int = 2026) -> dict:
    rows = parse_fpl(json.loads(source.read_text(encoding="utf-8")), year)
    if not rows:
        raise ValueError("Empty source roster")
    write_csv(output, list(rows[0]), rows)
    return {"rows": len(rows), "season_start": year,
            "note": "FPL IDs and Opta IDs are NOT FIFA IDs; no implicit identity conversion"}
