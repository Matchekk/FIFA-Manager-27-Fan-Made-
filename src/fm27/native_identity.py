"""Bind nonpersisted clubless IDs only to an actual native baseline read."""
from collections import defaultdict, Counter
import datetime as dt

from .matching import normalize


def bind_native_free_agent_ids(players, native):
    # FifamDate::ToStringA emits DD.MM.YYYY; projection uses ISO dates.
    native = [{**p, "dob": (dt.datetime.strptime(p["dob"], "%d.%m.%Y").date().isoformat()
                            if "." in p["dob"] else dt.date.fromisoformat(p["dob"]).isoformat())} for p in native]
    by_id = {p["fm_id"]:p for p in native}
    if len(by_id) != len(native) or len(native) != len(players):
        raise ValueError("Native baseline cardinality/ID mismatch")
    clubless = defaultdict(list)
    for p in native:
        if p["club_id"] == "0":
            clubless[(p["fifa_id"], p["dob"], normalize(p["name"]))].append(p)
    proposals = []
    for p in players:
        names = {normalize(p.get("name", "")), normalize(p.get("common_name", ""))} - {""}
        if p["fm_id"]:
            actual = by_id.get(p["fm_id"])
            if not actual or any(actual[k] != p[k] for k in ("fifa_id", "dob", "club_id")) or normalize(actual["name"]) not in names:
                raise ValueError("Native read differs from persisted baseline identity " + p["fm_id"] + ": " +
                                 str({k:(p.get(k), (actual or {}).get(k)) for k in ("name", "common_name", "fifa_id", "dob", "club_id")}))
            continue
        if p["club_id"] != "0":
            raise ValueError("Missing ID on contracted player")
        matches = {n["fm_id"]:n for name in names for n in clubless[(p["fifa_id"], p["dob"], name)]}
        if len(matches) == 1:
            proposals.append((p, next(iter(matches))))
    counts = Counter(ident for _, ident in proposals)
    bound = []
    for p, ident in proposals:
        if counts[ident] == 1:
            p["fm_id"] = ident
            bound.append({"fm_id":ident, "fifa_id":p["fifa_id"], "dob":p["dob"], "name":p["name"],
                          "source_file":p["source_file"], "source_line":p["source_line"]})
    return bound
