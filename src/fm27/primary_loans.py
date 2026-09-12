"""Reviewed official loan announcements supplement, never replace, source tables."""
import datetime as dt
import hashlib
import json
import re
from collections import defaultdict
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from .common import sha256
from .matching import normalize


def load_primary_loans(root, snapshot, profiles):
    path = root / "data/overrides/primary_loans.json"
    if not path.exists():
        return [], {}
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema") != 1 or manifest.get("snapshot_date") != snapshot:
        raise ValueError("Primary loan manifest schema/snapshot mismatch")
    by_person = defaultdict(list)
    for profile in profiles:
        by_person[profile["player_tm_id"]].append(profile)
    rows, seen = [], set()
    for item in manifest["loans"]:
        url = urlsplit(item["source"])
        if url.scheme != "https" or url.hostname not in {"www.fcn.de", "www.juventus.com"} or url.username or url.password:
            raise ValueError("Unreviewed primary loan source host")
        digest = item["source_sha256"]
        if not re.fullmatch("[0-9a-f]{64}", digest):
            raise ValueError("Invalid primary loan source digest")
        source = root / "data/raw/primary-transfers" / (digest + ".html")
        if sha256(source) != digest:
            raise ValueError("Changed primary loan source bytes")
        matched = by_person[item["player_tm_id"]]
        if len(matched) != 1:
            raise ValueError("Primary loan requires one bound current profile")
        profile = matched[0]
        if (profile["source_sha256"] != item["profile_sha256"] or profile["dob"] != item["dob"]
                or profile["snapshot_date"] != snapshot or profile["source_status"] != "CONFIRMED"
                or profile["club_tm_id"] != item["borrower_tm_id"]):
            raise ValueError("Primary loan profile binding changed")
        for field in ("owner_tm_id", "borrower_tm_id"):
            if not re.fullmatch("[1-9][0-9]*", item[field]):
                raise ValueError("Primary loan club identity missing")
        if item["owner_tm_id"] == item["borrower_tm_id"]:
            raise ValueError("Primary loan owner equals borrower")
        if (item.get("reviewed_on") != snapshot or not item.get("reviewed_by") or not item.get("reason")
                or not item.get("evidence_fragments")):
            raise ValueError("Primary loan review evidence missing")
        date = item["announcement_date"]
        dt.date.fromisoformat(date)
        if not profile["dob"] <= date <= snapshot:
            raise ValueError("Primary announcement is outside the current snapshot")
        text = normalize(BeautifulSoup(source.read_text(encoding="utf-8-sig"), "html.parser").get_text(" ", strip=True))
        if any(not normalize(fragment) or normalize(fragment) not in text for fragment in item["evidence_fragments"]):
            raise ValueError("Reviewed primary loan evidence is absent from source")
        # This opaque namespace is not a fabricated Transfermarkt event ID.
        key = "primary-loan:" + hashlib.sha256((item["source"] + "|" + item["player_tm_id"]).encode()).hexdigest()
        if key in seen:
            raise ValueError("Repeated primary loan announcement")
        seen.add(key)
        rows.append({"league":"SUPPLEMENTAL", "club":item["owner_name"], "club_tm_id":item["owner_tm_id"],
                     "direction":"Abgang", "player":profile["player"], "player_tm_id":item["player_tm_id"],
                     "profile_url":profile["source"], "age":"", "position":"",
                     "old_club":item["owner_name"], "old_club_tm_id":item["owner_tm_id"],
                     "new_club":item["borrower_name"], "new_club_tm_id":item["borrower_tm_id"],
                     "transfer_type":"LOAN", "event_id":key,
                     "explicit_event_date":"", "announcement_date":date,
                     "fee_text":"", "source_status":"CONFIRMED", "database_action":"REVIEW_REQUIRED",
                     "source":item["source"], "source_sha256":digest, "snapshot_date":snapshot})
    return rows, {"manifest_sha256":sha256(path), "rows":len(rows), "reviewed_announcements":manifest["loans"]}
