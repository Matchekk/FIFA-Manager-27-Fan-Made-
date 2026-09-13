"""Bounded ENG/GER creation review using the complete Native08 corpus."""
from __future__ import annotations

import csv
import datetime as dt
import difflib
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/current/workers/eng-ger"
NATIVE_PATH = ROOT / "data/generated/native08-integrated-20260912-01-reread/native_players.csv"
SNAPSHOT = "2026-09-12"
sys.path.insert(0, str(ROOT / "src"))
from fm27.missing_player_review import DuplicateReviewIndex  # noqa: E402
from fm27.matching import IdentityIndex, person_name_key  # noqa: E402


def read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def date_value(value: str) -> str:
    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return dt.datetime.strptime((value or "").strip(), fmt).date().isoformat()
        except ValueError:
            pass
    return ""


def compact(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode().lower())


def main() -> None:
    leagues = {"ENG1", "GER1", "GER2", "GER3"}
    queue = [r for r in read(ROOT / "reports/current/integration/review-queue.csv") if r["league"] in leagues and r["queue"] == "PLAYER_CREATION"]
    profiles = {r["player_tm_id"]: r for r in read(OUT / "profiles.csv")}
    native = [{**r, "dob": date_value(r.get("dob", ""))} for r in read(NATIVE_PATH)]
    identity = IdentityIndex(native)
    duplicate = DuplicateReviewIndex(native)
    overrides = json.loads((ROOT / "data/overrides/player_identities.json").read_text(encoding="utf-8"))["rows"]
    alias_map = {r["player_tm_id"]: [r.get("source_name", ""), r.get("native_name", "")] for r in overrides}
    ready_fields = ["league", "club_name", "club_tm_id", "player_tm_id", "player", "dob", "nationality", "native_country_id", "position", "club_id", "contract_joined", "contract_until", "shirt_number", "fifa_id", "id_strategy", "source_urls", "source_hashes", "confidence", "zero_duplicate_proof", "eligibility"]
    review_fields = ["league", "club_name", "club_tm_id", "player_tm_id", "player", "dob", "club_id", "status", "decision", "profile_source", "profile_sha256", "source_url", "source_sha256", "exact_candidates", "duplicate_leads", "fuzzy_candidates", "known_aliases_searched", "review_reason", "provenance"]
    ready, reviewed = [], []
    decisions, candidate_counts = Counter(), Counter()
    for evidence in sorted(queue, key=lambda r: (r["league"], r["club_tm_id"], r["player_tm_id"])):
        pid = evidence["player_tm_id"]; profile = profiles.get(pid, {})
        profile_name = profile.get("full_name") or profile.get("player") or evidence["player"]
        names = list(dict.fromkeys([x for x in [evidence.get("player", ""), profile.get("player", ""), profile.get("full_name", "")] + alias_map.get(pid, []) if x]))
        dob = evidence.get("dob", "")
        exact = {}
        for name in names:
            for person in identity.by_dob_name.get((dob, person_name_key(name)), []): exact[person["fm_id"]] = person
        leads, lead_reasons = duplicate.candidates({"player": evidence["player"], "dob": dob, "snapshot_date": SNAPSHOT}, profile, SNAPSHOT, evidence.get("target_club_id", ""))
        fuzzy = []
        for person in native:
            if person.get("dob") != dob: continue
            score = difflib.SequenceMatcher(None, compact(profile_name), compact(person.get("name", ""))).ratio()
            if score >= 0.60: fuzzy.append((score, person))
        fuzzy.sort(key=lambda pair: (-pair[0], pair[1].get("fm_id", "")))
        exact_list = list(exact.values())
        candidate_counts["exact"] += bool(exact_list); candidate_counts["duplicate_index_leads"] += bool(leads); candidate_counts["fuzzy"] += bool(fuzzy)
        if exact_list or leads or fuzzy:
            decision, reason = "REVIEW_REQUIRED", "existing/fuzzy candidate retained for Sol review"
        else:
            missing = [f for f in ("nationality_text", "position", "joined", "contract_until") if not profile.get(f)]
            try: age = (dt.date.fromisoformat(SNAPSHOT) - dt.date.fromisoformat(dob)).days / 365.2425
            except ValueError: age = 0
            if missing: decision, reason = "REVIEW_REQUIRED", "missing profile fields: " + ";".join(missing)
            elif age < 18: decision, reason = "REVIEW_REQUIRED", "young academy edgecase; adult priority not established"
            else: decision, reason = "CREATE_READY", "adult profile with zero exact, DuplicateReviewIndex, and fuzzy candidates"
        decisions[decision] += 1
        proof = {"native_corpus": str(NATIVE_PATH.relative_to(ROOT)).replace("\\", "/"), "native_rows_searched": len(native), "exact_dob_name_candidates": len(exact_list), "duplicate_review_index_leads": len(leads), "fuzzy_threshold": 0.60, "fuzzy_candidates": len(fuzzy), "names_searched": names, "result": "ZERO_DUPLICATE_CANDIDATES" if not exact_list and not leads and not fuzzy else "CANDIDATE_RETAINED"}
        if decision == "CREATE_READY":
            ready.append({"league": evidence["league"], "club_name": evidence["club"], "club_tm_id": evidence["club_tm_id"], "player_tm_id": pid, "player": profile_name, "dob": dob, "nationality": profile.get("nationality_text", ""), "native_country_id": "", "position": profile.get("position", ""), "club_id": evidence["target_club_id"], "contract_joined": profile.get("joined", ""), "contract_until": profile.get("contract_until", ""), "shirt_number": profile.get("shirt_number", ""), "fifa_id": "0", "id_strategy": "NATIVE_FIFA0_CREATE_AFTER_SOL_REVIEW", "source_urls": json.dumps([profile.get("source", ""), evidence.get("source", "")], ensure_ascii=False), "source_hashes": json.dumps([profile.get("source_sha256", ""), evidence.get("source_sha256", "")]), "confidence": "HIGH", "zero_duplicate_proof": json.dumps(proof, ensure_ascii=False, separators=(",", ":")), "eligibility": "ADULT_SCOPED_SQUAD_ZERO_DUPLICATE"})
        reviewed.append({"league": evidence["league"], "club_name": evidence["club"], "club_tm_id": evidence["club_tm_id"], "player_tm_id": pid, "player": profile_name, "dob": dob, "club_id": evidence["target_club_id"], "status": evidence.get("status", ""), "decision": decision, "profile_source": profile.get("source", ""), "profile_sha256": profile.get("source_sha256", ""), "source_url": evidence.get("source", ""), "source_sha256": evidence.get("source_sha256", ""), "exact_candidates": json.dumps([{k: p.get(k, "") for k in ("fm_id", "fifa_id", "name", "dob", "club_id")} for p in exact_list], ensure_ascii=False), "duplicate_leads": json.dumps({"people": [{k: p.get(k, "") for k in ("fm_id", "fifa_id", "name", "dob", "club_id")} for p in leads], "reasons": lead_reasons}, ensure_ascii=False), "fuzzy_candidates": json.dumps([{"score": round(score, 4), **{k: p.get(k, "") for k in ("fm_id", "fifa_id", "name", "dob", "club_id")}} for score, p in fuzzy], ensure_ascii=False), "known_aliases_searched": json.dumps(names, ensure_ascii=False), "review_reason": reason, "provenance": f"Profile {profile.get('source', '')} sha256={profile.get('source_sha256', '')}; squad {evidence.get('source', '')} sha256={evidence.get('source_sha256', '')}; DuplicateReviewIndex over {NATIVE_PATH.relative_to(ROOT).as_posix()}"})
    for path, fields, rows in [(OUT / "create-ready.csv", ready_fields, ready), (OUT / "create-ready-review.csv", review_fields, reviewed)]:
        with path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fields); writer.writeheader(); writer.writerows(rows)
    meta = {"schema": 1, "snapshot_date": SNAPSHOT, "scope": sorted(leagues), "rows_audited": len(reviewed), "ready_rows": len(ready), "decision_counts": dict(decisions), "candidate_presence_counts": dict(candidate_counts), "native_corpus": str(NATIVE_PATH.relative_to(ROOT)).replace("\\", "/"), "native_corpus_rows": len(native), "duplicate_review_index": "src/fm27/missing_player_review.py:DuplicateReviewIndex", "fuzzy_threshold": 0.60, "ready_zero_duplicate_proof": "Every CREATE_READY row has zero exact DOB+name, zero DuplicateReviewIndex leads, and zero fuzzy candidates at threshold 0.60; all other candidates are retained in create-ready-review.csv.", "fifa_policy": "fifa_id=0 for every proposal; no external FIFA ID is assigned without verified EA evidence.", "canonical_mutation": False, "sol_action": "Review create-ready.csv and implement native creation mechanism; do not auto-apply."}
    (OUT / "create-ready-proof.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"rows_audited": len(reviewed), "ready_rows": len(ready), "decision_counts": dict(decisions), "candidate_presence_counts": dict(candidate_counts)}, ensure_ascii=False))


if __name__ == "__main__": main()
