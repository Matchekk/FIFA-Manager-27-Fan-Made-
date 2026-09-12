"""Individually reviewed spellings, bound to immutable sources and native people."""
import datetime as dt
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from urllib.parse import urlsplit

from .common import read_csv, sha256
from .ea import league_page, page_props
from .transfermarkt import parse_profile


PROFILE_FIELDS = ("player_tm_id", "player", "full_name", "dob", "club_tm_id",
                  "source", "source_sha256", "snapshot_date", "source_status")
NATIVE_FIELDS = ("fm_id", "fifa_id", "name", "dob", "nationality", "club_id")


def values(row, fields):
    return tuple(str(row.get(k, "")) for k in fields)


@dataclass(frozen=True)
class ReviewedIdentity:
    profile: tuple
    native: tuple
    source_fifa_id: str = ""


def verified_unassigned_fifa(root, row, profile, person, index, ea_rows):
    """Corroborating EA identity never assigns an ID to the native FIFA0 person."""
    proof = row.get("unassigned_fifa_evidence")
    if proof is None:
        return ""
    if person["fifa_id"] not in {"", "0"}:
        raise ValueError("Unassigned FIFA evidence cannot replace an assigned native ID")
    ident = proof["fifa_id"]
    if not re.fullmatch(r"[1-9][0-9]*", ident) or index.by_fifa[ident]:
        raise ValueError("Reviewed EA identity is already assigned to a native person")
    if proof["ea_csv_sha256"] != sha256(root / "data/intermediate/ea-fc27.csv"):
        raise ValueError("Reviewed EA identity table changed")
    selected = [r for r in ea_rows if r["fifa_id"] == ident]
    fields = ("fifa_id", "league", "player", "dob", "source", "source_sha256", "snapshot_date")
    if len(selected) != 1 or values(selected[0], fields) != values(proof, fields):
        raise ValueError("Reviewed EA identity is missing, changed or ambiguous")
    source = selected[0]
    url = urlsplit(source["source"])
    if (url.scheme != "https" or url.hostname != "www.ea.com" or url.username or url.password
            or not url.path.startswith("/games/ea-sports-fc/ratings/")
            or source["dob"] != profile["dob"] or source["snapshot_date"] != profile["snapshot_date"]):
        raise ValueError("Reviewed EA source/profile binding differs")
    digest = source["source_sha256"]
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("Invalid EA identity source digest")
    path = root / "data/raw/ea" / (digest + ".html")
    if sha256(path) != digest:
        raise ValueError("Reviewed EA source bytes changed")
    parsed, _, _ = league_page(page_props(path.read_text(encoding="utf-8-sig")), source["league"])
    parsed = [r for r in parsed if str(r["fifa_id"]) == ident]
    if len(parsed) != 1 or values(parsed[0], fields[:4]) != values(source, fields[:4]):
        raise ValueError("Reviewed EA identity differs from immutable HTML")
    from .matching import person_name_key
    source_names = {person_name_key(source["player"])}
    # An explicitly reviewed display name can corroborate a longer EA legal
    # name. Bind it to both the CSV and the original HTML, not just its label.
    if "common_name" in proof:
        common = proof["common_name"]
        if (not isinstance(common, str) or not person_name_key(common)
                or common != source.get("common_name") or common != parsed[0].get("common_name")):
            raise ValueError("Reviewed EA common name differs from immutable HTML or table")
        source_names.add(person_name_key(common))
    profile_names = {person_name_key(profile["player"]), person_name_key(profile.get("full_name", ""))} - {""}
    if not source_names.intersection(profile_names):
        raise ValueError("EA identity does not corroborate the reviewed source name")
    return ident


def verified_profile(root, row, snapshot):
    """Reparse cached bytes; stored CSV fields cannot override current parsing."""
    digest = row["source_sha256"]
    if not re.fullmatch(r"[0-9a-f]{64}", digest) or row["snapshot_date"] != snapshot:
        raise ValueError("Profile snapshot/digest mismatch")
    path = root / "data/raw/transfermarkt" / (digest + ".html")
    if sha256(path) != digest:
        raise ValueError("Profile source bytes changed")
    return {**row, **parse_profile(path.read_text(encoding="utf-8-sig"), row["player_tm_id"])}


def load_player_identities(root, snapshot, profiles, players, baseline_path, aliases):
    """Return copies with opt-in metadata; never change native or source identity."""
    from .matching import IdentityIndex

    path = root / "data/overrides/player_identities.json"
    copied = [dict(p) for p in profiles]
    if any("_reviewed_identity" in p for p in copied):
        raise ValueError("Identity metadata must originate in the review loader")
    if not path.exists():
        return copied, {}
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if (manifest.get("schema") != 1 or manifest.get("snapshot_date") != snapshot
            or manifest.get("baseline_sha256") != sha256(baseline_path)):
        raise ValueError("Identity review schema/snapshot/baseline changed")
    by_tm = defaultdict(list)
    for p in copied:
        by_tm[p["player_tm_id"]].append(p)
    index = IdentityIndex(players)
    ea_rows = read_csv(root / "data/intermediate/ea-fc27.csv") if any(
        r.get("unassigned_fifa_evidence") is not None for r in manifest["rows"]) else []
    seen_tm, seen_fm = set(), set()
    for row in manifest["rows"]:
        tm, fm = row["player_tm_id"], row["fm_id"]
        if tm in seen_tm or fm in seen_fm:
            raise ValueError("Repeated reviewed source/native person")
        seen_tm.add(tm)
        seen_fm.add(fm)
        if len(by_tm[tm]) != 1 or len(index.by_fm[fm]) != 1:
            raise ValueError("Reviewed source/native person is missing or ambiguous")
        if (row.get("reviewed_on") != snapshot or not row.get("reviewed_by")
                or not row.get("reason") or not row.get("public_sources")):
            raise ValueError("Identity review lacks provenance")
        dt.date.fromisoformat(row["dob"])
        for source in row["public_sources"]:
            url = urlsplit(source["url"])
            if (url.scheme != "https" or not url.hostname or url.username or url.password
                    or not source.get("access") or not source.get("supports")):
                raise ValueError("Invalid identity corroboration provenance")
        profile, person = by_tm[tm][0], index.by_fm[fm][0]
        parsed = verified_profile(root, profile, snapshot)
        if values(profile, PROFILE_FIELDS) != values(parsed, PROFILE_FIELDS):
            raise ValueError("Reviewed profile differs from immutable HTML")
        expected = (tm, row["source_name"], row["dob"], row["current_club_tm_id"],
                    row["profile_source"], row["profile_sha256"], snapshot, "CONFIRMED")
        if values(profile, tuple(k for k in PROFILE_FIELDS if k != "full_name")) != expected:
            raise ValueError("Reviewed profile binding changed")
        expected_native = (fm, row["native_fifa_id"], row["native_name"], row["dob"],
                           row["native_nationality"], row["native_club_id"])
        if values(person, NATIVE_FIELDS) != expected_native:
            raise ValueError("Reviewed native identity changed")
        fifa = person["fifa_id"]
        if fifa not in {"", "0"} and len(index.by_fifa[fifa]) != 1:
            raise ValueError("Reviewed native FIFA ID is ambiguous")
        if aliases.get(row["current_club_tm_id"], {}).get("club_id") != row["target_club_id"]:
            raise ValueError("Reviewed destination club binding changed")
        source_fifa = verified_unassigned_fifa(root, row, profile, person, index, ea_rows)
        review = ReviewedIdentity(values(profile, PROFILE_FIELDS), expected_native, source_fifa)
        profile["_reviewed_identity"] = review
        # Also reject a natural-name match to another native person globally.
        for name in {profile["player"], profile.get("full_name", ""), person["name"]} - {""}:
            method, found = index.match({"player": name, "dob": profile["dob"]})
            if method in {"CONFLICT", "AMBIGUOUS"} or any(p["fm_id"] != fm for p in found):
                raise ValueError("Reviewed spelling conflicts with an existing identity")
        for other in copied:
            if other["player_tm_id"] == tm or other.get("dob") != person["dob"]:
                continue
            for name in {other.get("player", ""), other.get("full_name", "")} - {""}:
                _, found = index.match({"player": name, "dob": person["dob"]})
                if any(p["fm_id"] == fm for p in found):
                    raise ValueError("Another source identity already claims the reviewed native person")
    return copied, {"manifest_sha256": sha256(path), "baseline_sha256": sha256(baseline_path),
                    "reviewed_people": len(seen_tm), "rows": manifest["rows"]}


def reviewed_profile_match(index, evidence, profile, original):
    review = profile.get("_reviewed_identity")
    if review is None:
        return original
    if (not isinstance(review, ReviewedIdentity)
            or values(profile, PROFILE_FIELDS) != review.profile
            or evidence.get("dob") != profile.get("dob")
            or (evidence.get("player_tm_id") and evidence["player_tm_id"] != profile["player_tm_id"])):
        return "CONFLICT", []
    found = index.by_fm[review.native[0]]
    if len(found) != 1 or values(found[0], NATIVE_FIELDS) != review.native:
        return "CONFLICT", []
    person = found[0]
    fifa = person["fifa_id"]
    if fifa not in {"", "0"} and len(index.by_fifa[fifa]) != 1:
        return "CONFLICT", []
    if review.source_fifa_id and (fifa not in {"", "0"} or index.by_fifa[review.source_fifa_id]):
        return "CONFLICT", []
    if any(str(source.get("fifa_id", "")) not in {"", "0", fifa, review.source_fifa_id} for source in (evidence, profile)):
        return "CONFLICT", []
    method, candidates = original
    if method in {"CONFLICT", "AMBIGUOUS"}:
        return original
    if any(p.get("fm_id") != person["fm_id"] for p in candidates):
        return "CONFLICT", []
    # Name-based conflicts discovered after loading still remain holds.
    for name in {evidence.get("player", ""), profile["player"], profile.get("full_name", ""), person["name"]} - {""}:
        method, natural = index.match({"player": name, "dob": profile["dob"]})
        if method in {"CONFLICT", "AMBIGUOUS"} or any(p.get("fm_id") != person["fm_id"] for p in natural):
            return "CONFLICT", []
    return original if candidates else ("REVIEWED_IDENTITY", found)
