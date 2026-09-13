"""Select genuinely absent south-west people after a global duplicate review.

The output is a worker proposal for Sol's native creation mechanism.  This
script never allocates a native ID, FIFA ID, or database row.
"""
from __future__ import annotations

import csv
import datetime as dt
import difflib
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/current/workers/south-west"
NATIVE_PATH = ROOT / "data/generated/native08-integrated-20260912-01-reread/native_players.csv"
RESOLUTION_PATH = OUT / "identity-resolutions.csv"
PROFILE_PATH = OUT / "profiles.csv"
OVERRIDE_PATH = ROOT / "data/overrides/player_identities.json"
SNAPSHOT = "2026-09-12"

sys.path.insert(0, str(ROOT / "src"))
from fm27.missing_player_review import DuplicateReviewIndex  # noqa: E402
from fm27.matching import IdentityIndex, person_name_key  # noqa: E402


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def date_value(value: str) -> str:
    value = (value or "").strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return dt.datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            pass
    return ""


def compact_name(value: str) -> str:
    return re.sub(
        r"[^a-z0-9]", "", unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode().lower()
    )


def native_person(row: dict[str, str]) -> dict[str, str]:
    return {**row, "dob": date_value(row.get("dob", ""))}


def main() -> None:
    resolutions = read_csv(RESOLUTION_PATH)
    profiles = {row["player_tm_id"]: row for row in read_csv(PROFILE_PATH)}
    native = [native_person(row) for row in read_csv(NATIVE_PATH)]
    native_index = IdentityIndex(native)
    duplicate_index = DuplicateReviewIndex(native)
    override_doc = json.loads(OVERRIDE_PATH.read_text(encoding="utf-8"))
    aliases = {
        row["player_tm_id"]: [row.get("source_name", ""), row.get("native_name", "")]
        for row in override_doc.get("rows", [])
    }

    ready_fields = [
        "league", "club_name", "club_tm_id", "player_tm_id", "player", "dob", "nationality", "native_country_id", "position",
        "club_id", "contract_joined", "contract_until", "shirt_number", "fifa_id",
        "id_strategy", "source_urls", "source_hashes", "confidence", "zero_duplicate_proof",
        "eligibility",
    ]
    review_fields = [
        "league", "club_name", "club_tm_id", "player_tm_id", "player", "dob", "club_id", "status", "decision", "profile_source",
        "profile_sha256", "source_url", "source_sha256", "exact_candidates", "duplicate_leads",
        "fuzzy_candidates", "known_aliases_searched", "review_reason", "provenance",
    ]
    ready: list[dict[str, str]] = []
    reviewed: list[dict[str, str]] = []
    counts: Counter[str] = Counter()
    candidate_counts: Counter[str] = Counter()

    for evidence in sorted(resolutions, key=lambda row: (row["league"], row["club_tm_id"], row["player_tm_id"])):
        pid = evidence["player_tm_id"]
        profile = profiles.get(pid, {})
        profile_name = profile.get("full_name") or profile.get("player") or evidence.get("source_player_name", "")
        names = [x for x in [evidence.get("source_player_name", ""), profile.get("player", ""), profile.get("full_name", "")] if x]
        names.extend(aliases.get(pid, []))
        names = list(dict.fromkeys(names))
        dob = evidence.get("dob", "")

        exact: dict[str, dict[str, str]] = {}
        for name in names:
            for person in native_index.by_dob_name.get((dob, person_name_key(name)), []):
                exact[person["fm_id"]] = person
        exact_list = list(exact.values())

        # DuplicateReviewIndex is the authoritative cross-DOB/full-name
        # component pass.  Its leads are always retained in the review CSV.
        leads, lead_reasons = duplicate_index.candidates(
            {"player": evidence.get("source_player_name", ""), "dob": dob, "snapshot_date": SNAPSHOT},
            profile,
            SNAPSHOT,
            evidence.get("club_id", evidence.get("target_club_id", "")),
        )

        fuzzy: list[tuple[float, dict[str, str]]] = []
        profile_key = compact_name(profile_name)
        for person in native:
            if person.get("dob") != dob:
                continue
            score = difflib.SequenceMatcher(None, profile_key, compact_name(person.get("name", ""))).ratio()
            if score >= 0.60:
                fuzzy.append((score, person))
        fuzzy.sort(key=lambda pair: (-pair[0], pair[1].get("fm_id", "")))

        # A row previously confirmed in identity-resolutions is never a new
        # person proposal, even though its profile may still be visible here.
        if evidence.get("status") == "CONFIRMED":
            decision, reason = "KNOWN_IDENTITY", "already confirmed in identity-resolutions.csv"
        elif pid in aliases:
            # A reviewed source/native alias with no current Native08 row is
            # still an existing identity lead.  Keep it held for Sol; never
            # turn an override miss into a new person.
            decision, reason = "REVIEW_REQUIRED", "existing reviewed alias has no current Native08 bridge"
        elif exact_list or leads or fuzzy:
            decision, reason = "REVIEW_REQUIRED", "existing/fuzzy candidate retained for Sol review"
        else:
            missing = [field for field in ("nationality_text", "position", "joined", "contract_until") if not profile.get(field)]
            try:
                age = (dt.date.fromisoformat(SNAPSHOT) - dt.date.fromisoformat(dob)).days / 365.2425
            except ValueError:
                age = 0
            if missing:
                decision, reason = "REVIEW_REQUIRED", "missing profile fields: " + ";".join(missing)
            elif age < 18:
                decision, reason = "REVIEW_REQUIRED", "young academy edgecase; adult-first-team priority not established"
            else:
                decision, reason = "CREATE_READY", "adult scoped-squad profile with zero exact, duplicate-index, and fuzzy candidates"

        candidate_counts["exact"] += bool(exact_list)
        candidate_counts["duplicate_index_leads"] += bool(leads)
        candidate_counts["fuzzy"] += bool(fuzzy)
        candidate_counts["existing_reviewed_alias"] += pid in aliases
        counts[decision] += 1
        proof = {
            "native_corpus": str(NATIVE_PATH.relative_to(ROOT)).replace("\\", "/"),
            "native_rows_searched": len(native),
            "exact_dob_name_candidates": len(exact_list),
            "duplicate_review_index_leads": len(leads),
            "fuzzy_candidates_threshold": 0.60,
            "fuzzy_candidates": len(fuzzy),
            "names_searched": names,
            "result": "ZERO_DUPLICATE_CANDIDATES" if not exact_list and not leads and not fuzzy else "CANDIDATE_RETAINED",
        }
        if decision == "CREATE_READY":
            ready.append({
                "league": evidence.get("league", ""), "club_name": evidence.get("club", ""), "club_tm_id": evidence.get("club_tm_id", ""),
                "player_tm_id": pid,
                "player": profile_name,
                "dob": dob,
                "nationality": profile.get("nationality_text", ""),
                "native_country_id": "",
                "position": profile.get("position", ""),
                "club_id": evidence.get("target_club_id", ""),
                "contract_joined": profile.get("joined", ""),
                "contract_until": profile.get("contract_until", ""),
                "shirt_number": profile.get("shirt_number", ""),
                "fifa_id": "0",
                "id_strategy": "NATIVE_FIFA0_CREATE_AFTER_SOL_REVIEW",
                "source_urls": json.dumps([profile.get("source", ""), evidence.get("queue_source", "")], ensure_ascii=False),
                "source_hashes": json.dumps([profile.get("source_sha256", ""), evidence.get("queue_source_sha256", "")]),
                "confidence": "HIGH",
                "zero_duplicate_proof": json.dumps(proof, ensure_ascii=False, separators=(",", ":")),
                "eligibility": "ADULT_SCOPED_SQUAD_ZERO_DUPLICATE",
            })

        reviewed.append({
            "league": evidence.get("league", ""), "club_name": evidence.get("club", ""), "club_tm_id": evidence.get("club_tm_id", ""),
            "player_tm_id": pid, "player": profile_name, "dob": dob,
            "club_id": evidence.get("target_club_id", ""), "status": evidence.get("status", ""),
            "decision": decision, "profile_source": profile.get("source", ""),
            "profile_sha256": profile.get("source_sha256", ""), "source_url": evidence.get("queue_source", ""),
            "source_sha256": evidence.get("queue_source_sha256", ""),
            "exact_candidates": json.dumps([
                {k: person.get(k, "") for k in ("fm_id", "fifa_id", "name", "dob", "club_id")}
                for person in exact_list
            ], ensure_ascii=False),
            "duplicate_leads": json.dumps({
                "people": [{k: person.get(k, "") for k in ("fm_id", "fifa_id", "name", "dob", "club_id")} for person in leads],
                "reasons": lead_reasons,
            }, ensure_ascii=False),
            "fuzzy_candidates": json.dumps([
                {"score": round(score, 4), **{k: person.get(k, "") for k in ("fm_id", "fifa_id", "name", "dob", "club_id")}}
                for score, person in fuzzy
            ], ensure_ascii=False),
            "known_aliases_searched": json.dumps(names, ensure_ascii=False),
            "review_reason": reason,
            "provenance": f"Profile {profile.get('source', '')} sha256={profile.get('source_sha256', '')}; queue {evidence.get('queue_source', '')} sha256={evidence.get('queue_source_sha256', '')}; DuplicateReviewIndex over {NATIVE_PATH.relative_to(ROOT).as_posix()}",
        })

    ready_path = OUT / "create-ready.csv"
    with ready_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=ready_fields)
        writer.writeheader()
        writer.writerows(ready)
    review_path = OUT / "create-ready-review.csv"
    with review_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=review_fields)
        writer.writeheader()
        writer.writerows(reviewed)

    meta = {
        "schema": 1, "snapshot_date": SNAPSHOT,
        "scope": "remaining identity holds in south-west identity-resolutions.csv",
        "rows_audited": len(reviewed), "ready_rows": len(ready),
        "decision_counts": dict(counts), "candidate_presence_counts": dict(candidate_counts),
        "native_corpus": str(NATIVE_PATH.relative_to(ROOT)).replace("\\", "/"),
        "native_corpus_rows": len(native),
        "duplicate_review_index": "src/fm27/missing_player_review.py:DuplicateReviewIndex",
        "fuzzy_threshold": 0.60,
        "ready_zero_duplicate_proof": "Each CREATE_READY row has zero exact DOB+name, zero DuplicateReviewIndex leads, and zero fuzzy candidates at threshold 0.60 across the complete current Native08 corpus; all other candidates are retained in create-ready-review.csv.",
        "known_aliases": "Existing reviewed source/native aliases plus current profile player/full_name were searched; FM ID alone was never used.",
        "fifa_policy": "fifa_id=0 for every proposal; no external FIFA ID is assigned without verified EA evidence.",
        "canonical_mutation": False,
        "sol_action": "Review create-ready.csv and implement native creation mechanism; do not auto-apply.",
    }
    (OUT / "create-ready.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"rows_audited": len(reviewed), "ready_rows": len(ready), "decision_counts": dict(counts), "candidate_presence_counts": dict(candidate_counts)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
