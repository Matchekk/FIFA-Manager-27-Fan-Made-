"""Indexed identity reconciliation. Fuzzy names are never an identity authority."""
import datetime as dt
import unicodedata
from collections import defaultdict


def normalize(name: str) -> str:
    text = unicodedata.normalize("NFKD", name.casefold())
    return " ".join("".join(c if c.isalnum() else " " for c in text
                            if not unicodedata.combining(c)).split())


def valid_dob(value: str) -> str:
    return dt.date.fromisoformat(value).isoformat() if value else ""


class IdentityIndex:
    def __init__(self, players: list[dict]):
        self.by_fifa = defaultdict(list)
        self.by_dob_name = defaultdict(list)
        for player in players:
            fifa = str(player.get("fifa_id", ""))
            if fifa not in ("", "0"):
                self.by_fifa[fifa].append(player)
            dob = valid_dob(player.get("dob", ""))
            names = {normalize(player.get("name", "")), normalize(player.get("common_name", ""))}
            if dob:
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
        candidates = self.by_dob_name[(dob, normalize(evidence.get("player", "")))]
        nationality = evidence.get("nationality", "")
        if nationality:
            candidates = [p for p in candidates if str(p["nationality"]) == str(nationality)]
        if len(candidates) == 1:
            return "DOB_NAME", candidates
        return ("AMBIGUOUS" if candidates else "MISSING_FROM_FM"), candidates
