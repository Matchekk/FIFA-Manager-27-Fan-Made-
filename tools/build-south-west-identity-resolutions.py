"""Resolve the bounded south-west player-creation queue against current Native08.

This emits worker evidence only.  It does not modify native, override, or
integration production files.
"""
from __future__ import annotations

import csv
import datetime as dt
import difflib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LEAGUES = {"ITA1", "FRA1", "ESP1", "POR1", "NED1", "BEL1", "TUR1", "CZE1"}
SNAPSHOT = "2026-09-12"
QUEUE_PATH = ROOT / "reports/current/integration/review-queue.csv"
PROFILE_PATH = ROOT / "data/current/workers/south-west/profiles.csv"
PROFILE_META_PATH = ROOT / "data/current/workers/south-west/profile-capture.json"
OVERRIDE_PATH = ROOT / "data/overrides/player_identities.json"
NATIVE_PATH = ROOT / "data/generated/native08-integrated-20260912-01-reread/native_players.csv"
OUT_PATH = ROOT / "data/current/workers/south-west/identity-resolutions.csv"
META_PATH = ROOT / "data/current/workers/south-west/identity-resolutions.json"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def parse_date(value: str) -> str:
    value = (value or "").strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return dt.datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            pass
    return ""


def ascii_text(value: str) -> str:
    return unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode().lower()


def normalized(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", ascii_text(value))


def tokens(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", ascii_text(value)))


def source_ok(source_hash: str) -> bool:
    return bool(re.fullmatch(r"[0-9a-f]{64}", source_hash or ""))


def unique(rows: list[dict[str, str]]) -> dict[str, str] | None:
    return rows[0] if len(rows) == 1 else None


def controlled_name_variant(profile_name: str, candidate: dict[str, str]) -> bool:
    """Allow only strong, same-club, DOB-unique name variants.

    This is deliberately a small controlled bridge for names where the
    current profile carries a middle name, abbreviation, or an accent/spelling
    variant.  A candidate that merely shares a short nickname remains review.
    """
    p = normalized(profile_name)
    n = normalized(candidate["name"])
    if not p or not n:
        return False
    p_tokens, n_tokens = tokens(profile_name), tokens(candidate["name"])
    aliases = {"jr": "junior", "jef": "jeff", "santi": "santiago", "khaly": "kaly"}
    p_tokens = {aliases.get(x, x) for x in p_tokens}
    n_tokens = {aliases.get(x, x) for x in n_tokens}
    overlap = p_tokens & n_tokens
    ratio = difflib.SequenceMatcher(None, p, n).ratio()
    # Require a substantial overlap, or a high whole-name similarity.  This
    # excludes one-token nickname collisions such as an unrelated "Erick".
    related_token = any(
        (a == b or (len(a) >= 5 and len(b) >= 5 and (a.startswith(b) or b.startswith(a))))
        for a in p_tokens
        for b in n_tokens
    )
    return related_token and (ratio >= 0.75 or n_tokens <= p_tokens or p_tokens <= n_tokens)


def _club_groups(rows: list[dict[str, str]]):
    grouped: defaultdict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[(row["league"], row["club_tm_id"], row["club"])].append(row)
    return sorted(grouped.items())


def main() -> None:
    queue = [
        row
        for row in read_csv(QUEUE_PATH)
        if row.get("league") in LEAGUES and row.get("queue") == "PLAYER_CREATION"
    ]
    # Queue should already be unique, but retain a deterministic first row if
    # an upstream retry temporarily duplicated a player.
    deduped: dict[str, dict[str, str]] = {}
    for row in queue:
        deduped.setdefault(row.get("player_tm_id", ""), row)
    queue = list(deduped.values())

    profiles = {row.get("player_tm_id", ""): row for row in read_csv(PROFILE_PATH)}
    overrides_doc = json.loads(OVERRIDE_PATH.read_text(encoding="utf-8"))
    overrides = {row.get("player_tm_id", ""): row for row in overrides_doc.get("rows", [])}
    native = read_csv(NATIVE_PATH)

    by_fifa_dob: defaultdict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    by_name_dob: defaultdict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    by_dob_club: defaultdict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in native:
        ndob = parse_date(row.get("dob", ""))
        by_fifa_dob[(row.get("fifa_id", ""), ndob)].append(row)
        by_name_dob[(normalized(row.get("name", "")), ndob)].append(row)
        by_dob_club[(ndob, row.get("club_id", ""))].append(row)

    # These are the rows where the profile and current Native08 have a unique
    # same-DOB/same-target-club variant with enough name evidence.  The allow
    # list prevents a nickname collision from becoming an invented identity.
    controlled_allow = {
        "1184725", "467632", "1297674", "1086915", "746358", "1047861",
        "1241219", "902869", "1093061", "1076666", "1296109", "1181959",
        "1189059", "1442800", "1237420", "1152080",
    }

    output: list[dict[str, str]] = []
    method_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    league_status: defaultdict[str, Counter[str]] = defaultdict(Counter)
    review_reasons: Counter[str] = Counter()

    fields = [
        "league", "club", "club_tm_id", "player_tm_id", "source_player_name",
        "profile_name", "dob", "native_fm_id", "native_fifa_id", "native_name",
        "native_dob", "native_club_id", "target_club_id", "status", "identity_method",
        "attempts", "escalation", "source_url", "source_sha256", "queue_source",
        "queue_source_sha256", "profile_retrieved_at", "snapshot_date", "provenance",
        "candidate_fm_id", "candidate_fifa_id", "candidate_name", "candidate_club_id",
    ]

    for row in sorted(queue, key=lambda r: (r.get("league", ""), r.get("club", ""), r.get("player_tm_id", ""))):
        tm_id = row.get("player_tm_id", "")
        profile = profiles.get(tm_id)
        override = overrides.get(tm_id)
        profile_name = ((profile or {}).get("full_name") or (profile or {}).get("player") or "").strip()
        profile_dob = parse_date((profile or {}).get("dob", ""))
        if not profile_dob and override:
            profile_dob = parse_date(override.get("dob", ""))
        source_url = (profile or {}).get("source") or (override or {}).get("profile_source") or row.get("source", "")
        source_hash = (profile or {}).get("source_sha256") or (override or {}).get("profile_sha256") or row.get("source_sha256", "")

        match: dict[str, str] | None = None
        method = ""
        candidate: dict[str, str] | None = None

        # Existing reviewed overrides have priority, but FM IDs are only a
        # lookup hint.  Current Native08 FIFA+DOB/name+DOB supplies the ID.
        if override:
            odob = parse_date(override.get("dob", ""))
            ofifa = (override.get("native_fifa_id") or "").strip()
            if ofifa and ofifa != "0":
                candidate = unique(by_fifa_dob[(ofifa, odob)])
                if candidate:
                    method = "EXISTING_OVERRIDE_FIFA_DOB"
            if not candidate:
                candidate = unique(by_name_dob[(normalized(override.get("native_name", "")), odob)])
                if candidate:
                    method = "EXISTING_OVERRIDE_NAME_DOB"
            if candidate:
                profile_dob = odob

        # Fresh profile -> current Native08 exact DOB + normalized name.
        if not candidate and profile and profile_dob and profile_name:
            exact = unique(by_name_dob[(normalized(profile_name), profile_dob)])
            if exact:
                candidate, method = exact, "EXACT_PROFILE_DOB_NAME"

        # Controlled spelling/middle-name bridge, only with same target club.
        if not candidate and profile and tm_id in controlled_allow and profile_dob:
            same_club = [
                item for item in by_dob_club[(profile_dob, row.get("target_club_id", ""))]
                if controlled_name_variant(profile_name, item)
            ]
            candidate = unique(same_club)
            if candidate:
                method = "CONTROLLED_NAME_VARIANT"

        if candidate:
            match = candidate
            status = "CONFIRMED"
            attempts = "fresh_profile_capture;native08_bridge"
            escalation = ""
            provenance = (
                f"Transfermarkt profile {source_url} sha256={source_hash}; "
                f"Native08 reread {NATIVE_PATH.as_posix()} matched by {method}"
            )
            if override:
                provenance += f"; existing reviewed override {OVERRIDE_PATH.as_posix()}"
        else:
            status = "REVIEW_REQUIRED"
            attempts = (
                "fresh_profile_capture:NO_MATCH;native08_bridge:NO_UNIQUE_MATCH"
                if profile else "fresh_profile_capture:ABSENT;native08_bridge:NOT_ATTEMPTED"
            )
            escalation = "Sol"
            review_reasons["NO_FRESH_PROFILE"] += not bool(profile)
            review_reasons["NO_UNIQUE_NATIVE_BRIDGE"] += bool(profile)
            provenance = (
                f"Transfermarkt profile {source_url} sha256={source_hash}; "
                f"Native08 reread {NATIVE_PATH.as_posix()} produced no safe unique identity"
            )
            # Preserve the best same-DOB candidate as a review hint only; it is
            # never placed in native_* fields or counted as confirmed.
            if profile and profile_dob:
                possible = by_dob_club[(profile_dob, row.get("target_club_id", ""))]
                if len(possible) == 1:
                    candidate = possible[0]

        rec = {field: "" for field in fields}
        rec.update(
            league=row.get("league", ""), club=row.get("club", ""), club_tm_id=row.get("club_tm_id", ""),
            player_tm_id=tm_id, source_player_name=row.get("player", ""), profile_name=profile_name,
            dob=profile_dob or parse_date(row.get("dob", "")), target_club_id=row.get("target_club_id", ""),
            status=status, identity_method=method or "REVIEW_REQUIRED_AFTER_TWO_ATTEMPTS", attempts=attempts,
            escalation=escalation, source_url=source_url, source_sha256=source_hash,
            queue_source=row.get("source", ""), queue_source_sha256=row.get("source_sha256", ""),
            profile_retrieved_at=(profile or {}).get("retrieved_at", ""), snapshot_date=SNAPSHOT,
            provenance=provenance,
        )
        if match:
            rec.update(
                native_fm_id=match.get("fm_id", ""), native_fifa_id=match.get("fifa_id", ""),
                native_name=match.get("name", ""), native_dob=parse_date(match.get("dob", "")),
                native_club_id=match.get("club_id", ""),
            )
        elif candidate:
            rec.update(
                candidate_fm_id=candidate.get("fm_id", ""), candidate_fifa_id=candidate.get("fifa_id", ""),
                candidate_name=candidate.get("name", ""), candidate_club_id=candidate.get("club_id", ""),
            )
        output.append(rec)
        method_counts[rec["identity_method"]] += 1
        status_counts[status] += 1
        league_status[rec["league"]][status] += 1

    with OUT_PATH.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(output)

    profile_meta = json.loads(PROFILE_META_PATH.read_text(encoding="utf-8"))
    meta = {
        "schema": 1,
        "snapshot_date": SNAPSHOT,
        "scope": sorted(LEAGUES),
        "queue": str(QUEUE_PATH.relative_to(ROOT)).replace("\\", "/"),
        "source_profiles": str(PROFILE_PATH.relative_to(ROOT)).replace("\\", "/"),
        "source_profile_capture": profile_meta,
        "native_authority": str(NATIVE_PATH.relative_to(ROOT)).replace("\\", "/"),
        "override_source": str(OVERRIDE_PATH.relative_to(ROOT)).replace("\\", "/"),
        "rows": len(output),
        "status_counts": dict(status_counts),
        "method_counts": dict(method_counts),
        "league_status": {k: dict(v) for k, v in sorted(league_status.items())},
        "club_coverage": {
            f"{league}|{club_tm_id}|{club}": {
                "rows": len(group),
                "confirmed": sum(item["status"] == "CONFIRMED" for item in group),
                "review_required": sum(item["status"] == "REVIEW_REQUIRED" for item in group),
                "review_player_tm_ids": [item["player_tm_id"] for item in group if item["status"] == "REVIEW_REQUIRED"],
            }
            for (league, club_tm_id, club), group in _club_groups(output)
        },
        "review_reasons": {k: int(v) for k, v in review_reasons.items()},
        "review_escalation": "Sol",
        "canonical_mutation": False,
        "identity_rule": "Native08 current FIFA+DOB, then existing reviewed identity, then DOB+normalized name, then controlled same-club name variant; no FM-only bridge and no invented FIFA IDs.",
    }
    META_PATH.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"rows": len(output), "status_counts": dict(status_counts), "method_counts": dict(method_counts)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
