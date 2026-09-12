"""Indexed identity reconciliation. Fuzzy names are never an identity authority."""
import datetime as dt
import unicodedata
from collections import Counter, defaultdict
from .player_identities import reviewed_profile_match

_LATIN_TRANSLITERATION = str.maketrans({"ø":"o", "ł":"l", "đ":"d", "ð":"d", "þ":"th",
                                      "æ":"ae", "œ":"oe", "ı":"i", "ħ":"h"})


def normalize(name: str) -> str:
    # NFKD does not decompose these Latin letters. Treat their established
    # transliterations like the other accent variants; DOB and global collision
    # checks still decide identity. Never transliterate whole writing systems.
    text = unicodedata.normalize("NFKD", name.casefold().translate(_LATIN_TRANSLITERATION))
    return " ".join("".join(c if c.isalnum() else " " for c in text
                            if not unicodedata.combining(c)).split())


def valid_dob(value: str) -> str:
    return dt.date.fromisoformat(value).isoformat() if value else ""


def person_name_key(value: str) -> str:
    """Permit given/family-name order changes without dropping any name part."""
    return " ".join(sorted(normalize(value).split()))


def normalize_club_name(name: str) -> str:
    """Club punctuation variants only; never drop FC/SC/reserve suffixes."""
    return normalize(name).replace(" ", "")


def recover_profile_identity(index, evidence, profile, snapshot, club_tm_id, current_native_club_id=None):
    result = _recover_profile_identity(index, evidence, profile, snapshot, club_tm_id, current_native_club_id)
    if (profile and (profile.get("snapshot_date") != snapshot or profile.get("club_tm_id") != club_tm_id
                     or profile.get("source_status") != "CONFIRMED")):
        return result
    return reviewed_profile_match(index, evidence, profile, result) if profile else result


def _recover_profile_identity(index, evidence, profile, snapshot, club_tm_id, current_native_club_id=None):
    """Use corroborating full profile names without bypassing FIFA-ID conflicts."""
    original = index.match_unassigned_fifa(evidence)
    if not profile:
        return original
    if profile.get("source_status") != "CONFIRMED" or profile.get("snapshot_date") != snapshot:
        return "REVIEW_REQUIRED", []
    if profile.get("dob") != evidence.get("dob") or profile.get("club_tm_id") != club_tm_id:
        return "CONFLICT", []
    if original[0] not in {"MISSING_FROM_FM", "REVIEW_REQUIRED"}:
        return original
    results = [index.match_unassigned_fifa({**evidence, "player": name})
               for name in {profile.get("player", ""), profile.get("full_name", "")} if name]
    if any(method in {"CONFLICT", "AMBIGUOUS"} for method, _ in results):
        return "AMBIGUOUS", []
    people = {id(p): p for method, candidates in results for p in candidates
              if method in {"FIFA_ID", "DOB_NAME", "DOB_NAME_UNASSIGNED_FIFA"}}
    if len(people) > 1:
        return "AMBIGUOUS", []
    if people:
        return "PROFILE_DOB_NAME", list(people.values())
    if current_native_club_id:
        full = Counter(normalize(profile.get("full_name", "")).split())
        candidates = []
        particles = {"de","da","dos","das","do","van","von","der","den","di","del","della","la","le","el","al","jr","junior"}
        for person in index.by_dob[valid_dob(evidence.get("dob", ""))]:
            native = Counter(normalize(person.get("name", "")).split())
            # A source's full name may include middle names omitted natively.
            # Require every native component, two informative words, exact DOB,
            # global uniqueness and the same current native club. No fuzzy score.
            if len(set(native) - particles) >= 2 and native <= full:
                candidates.append(person)
        if len(candidates) > 1:
            return "AMBIGUOUS", []
        if candidates and candidates[0].get("club_id") == str(current_native_club_id):
            supplied = str(evidence.get("fifa_id", ""))
            actual = str(candidates[0].get("fifa_id", ""))
            if supplied not in {"", "0"} and actual not in {"", "0", supplied}:
                return "CONFLICT", []
            return "PROFILE_FULL_NAME", candidates
    return original


class IdentityIndex:
    def __init__(self, players: list[dict]):
        self.by_fm = defaultdict(list)
        self.by_fifa = defaultdict(list)
        self.by_dob_name = defaultdict(list)
        self.by_dob = defaultdict(list)
        for player in players:
            self.by_fm[str(player.get("fm_id", ""))].append(player)
            fifa = str(player.get("fifa_id", ""))
            if fifa not in ("", "0"):
                self.by_fifa[fifa].append(player)
            dob = valid_dob(player.get("dob", ""))
            names = {person_name_key(player.get("name", "")), person_name_key(player.get("common_name", ""))}
            if dob:
                self.by_dob[dob].append(player)
                for name in names - {""}:
                    self.by_dob_name[(dob, name)].append(player)

    def match(self, evidence: dict) -> tuple[str, list[dict]]:
        fifa = str(evidence.get("fifa_id", ""))
        dob = valid_dob(evidence.get("dob", ""))
        if fifa not in ("", "0"):
            candidates = self.by_fifa[fifa]
            if len(candidates) > 1:
                return "AMBIGUOUS", candidates
            if candidates:
                if dob and candidates[0]["dob"] != dob:
                    return "CONFLICT", candidates
                return "FIFA_ID", candidates
            # Supplied but unknown ID must not silently collapse into a different ID.
            return "MISSING_FROM_FM", []
        if not dob:
            return "REVIEW_REQUIRED", []
        candidates = self.by_dob_name[(dob, person_name_key(evidence.get("player", "")))]
        nationality = evidence.get("nationality", "")
        if nationality:
            candidates = [p for p in candidates if str(p["nationality"]) == str(nationality)]
        if len(candidates) == 1:
            return "DOB_NAME", candidates
        return ("AMBIGUOUS" if candidates else "MISSING_FROM_FM"), candidates

    def match_unassigned_fifa(self, evidence: dict) -> tuple[str, list[dict]]:
        """Explicit recovery for a uniquely identified native person with FIFA ID 0.

        Never replace a different nonzero FIFA ID, or fall back from a duplicate
        or contradictory FIFA match. The source ID remains evidence, not a write.
        """
        method, candidates = self.match(evidence)
        if method != "MISSING_FROM_FM" or str(evidence.get("fifa_id", "")) in {"", "0"}:
            return method, candidates
        fallback, found = self.match({**evidence, "fifa_id": ""})
        if fallback == "DOB_NAME" and str(found[0].get("fifa_id", "")) in {"", "0"}:
            return "DOB_NAME_UNASSIGNED_FIFA", found
        return method, candidates
