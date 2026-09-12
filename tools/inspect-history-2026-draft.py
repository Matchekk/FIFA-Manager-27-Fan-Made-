"""Read-only inspection of Native07 club history fields referenced by HISTORY_DRAFT.json."""
import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DRAFT = ROOT / "data/generated/history-20260912-01/HISTORY_DRAFT.json"
DEFAULT_OUTPUT = ROOT / "data/generated/history-20260912-01/CURRENT_NATIVE_HISTORY.json"
HISTORY_FIELDS = (
    "mHistory.mLeagueWinYears",
    "mHistory.mCupWinYears",
    "mHistory.mSuperCupsWinYears",
    "mHistory.mLeagueCupWinYears",
    "mHistory.mEuroTrophyWinYears",
    "mHistory.mChampionsCupWinYears",
    "mHistory.mWorldChampionshipWinYears",
    "mHistory.mWorldClubChampionshipWinYears",
)
FLAG_FIELDS = {
    "mFirstTeamLastSeasonInfo.mLeague": ({"Promoted": 1, "Relegated": 4, "None": 0}, 1 | 4),
    "mFirstTeamLastSeasonInfo.mCup": ({"Winner": 16, "RunnerUp": 64, "None": 0}, 16 | 64),
}
CLUB_START = re.compile(r"%INDEX%CLUB(\d+)$")


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path):
    with path.open("r", encoding="utf-8-sig") as stream:
        return json.load(stream)


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def read_text_lines(path):
    raw = path.read_bytes()
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        text = raw.decode("utf-16")
    elif raw.startswith(b"\xef\xbb\xbf"):
        text = raw.decode("utf-8-sig")
    else:
        # Current candidate files are Windows text; strict UTF-8 first avoids hiding a format change.
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("cp1252")
    return text.splitlines()


def verify_upstream_layout(root):
    club_cpp = root / "upstream/fifam/fmapi/FifamClub.cpp"
    history_cpp = root / "upstream/fifam/fmapi/FifamClubHistory.cpp"
    country_cpp = root / "upstream/fifam/fmapi/FifamCountry.cpp"
    sources = {p: p.read_text(encoding="utf-8-sig") for p in (club_cpp, history_cpp, country_cpp)}
    club_text, history_text, country_text = sources[club_cpp], sources[history_cpp], sources[country_cpp]
    ordered_read = (
        "reader.ReadLine(lastSeasonFlags);",
        "reader.ReadLineArray(clubColors);",
        "mHistory.Read(reader);",
    )
    positions = [club_text.find(token) for token in ordered_read]
    if any(pos < 0 for pos in positions) or positions != sorted(positions):
        raise ValueError("Upstream club flags/history read order is not the verified FM13.12 layout")
    expected_history = [
        "mLeagueWinYears", "mCupWinYears", "mSuperCupsWinYears", "mLeagueCupWinYears",
        "mEuroTrophyWinYears", "mChampionsCupWinYears", "mWorldChampionshipWinYears",
        "mWorldClubChampionshipWinYears",
    ]
    history_positions = [history_text.find(f"{name} = reader.ReadLineArray<UShort>") for name in expected_history]
    if any(pos < 0 for pos in history_positions) or history_positions != sorted(history_positions):
        raise ValueError("Upstream eight-vector HIST order differs from the verified layout")
    for condition, assignment in (
        ("lastSeasonFlags & 1", "mFirstTeamLastSeasonInfo.mLeague = FifamClubLastSeasonLeague::Promoted"),
        ("lastSeasonFlags & 4", "mFirstTeamLastSeasonInfo.mLeague = FifamClubLastSeasonLeague::Relegated"),
        ("lastSeasonFlags & 16", "mFirstTeamLastSeasonInfo.mCup = FifamClubLastSeasonCup::Winner"),
        ("lastSeasonFlags & 64", "mFirstTeamLastSeasonInfo.mCup = FifamClubLastSeasonCup::RunnerUp"),
    ):
        if condition not in club_text or assignment not in club_text:
            raise ValueError("Upstream last-season flag mapping differs from the verified layout")
    if "club->Read(reader, i + 1);" not in country_text:
        raise ValueError("Upstream CLUB section reference-index rule differs from the verified layout")
    return {
        str(p.relative_to(root)).replace("\\", "/"): sha256(p)
        for p in (club_cpp, history_cpp, country_cpp)
    }


def parse_int_array(line, label):
    if not line.strip():
        return []
    values = []
    for item in line.split(","):
        item = item.strip()
        if not item.isdigit():
            raise ValueError(f"Non-integer value in {label}: {line!r}")
        value = int(item)
        if not 0 <= value <= 65535:
            raise ValueError(f"Out-of-range UShort in {label}: {value}")
        values.append(value)
    return values


def decode_first_team_flags(raw):
    league_bits, cup_bits = raw & 5, raw & 80
    league = {0: "None", 1: "Promoted", 4: "Relegated"}.get(league_bits, "AMBIGUOUS")
    cup = {0: "None", 16: "Winner", 64: "RunnerUp"}.get(cup_bits, "AMBIGUOUS")
    return {"league": league, "cup": cup}


def parse_country_file(path, country_id, wanted_uids):
    lines = read_text_lines(path)
    if len(lines) < 6 or lines[0] != "%INDEX%COUNTRY" or lines[1] != "%INDEX%VERSION" or lines[3] != "%INDEXEND%VERSION":
        raise ValueError(f"Unexpected country header in {path}")
    file_version = lines[2]
    starts = [(i, int(match.group(1))) for i, line in enumerate(lines) if (match := CLUB_START.fullmatch(line))]
    found = defaultdict(list)
    for offset, (start, club_index) in enumerate(starts):
        end = starts[offset + 1][0] if offset + 1 < len(starts) else len(lines)
        block = lines[start:end]
        expected_end = f"%INDEXEND%CLUB{club_index}"
        if expected_end not in block:
            raise ValueError(f"Missing {expected_end} in {path}")
        try:
            version_start = block.index("%INDEX%VERSION")
            version_end = block.index("%INDEXEND%VERSION")
        except ValueError as error:
            raise ValueError(f"Missing CLUB version markers in {path}:{start + 1}") from error
        if version_start != 1 or version_end != 3 or block[2] != file_version:
            raise ValueError(f"Unexpected CLUB header/version positions in {path}:{start + 1}")
        uid_line = start + version_end + 1
        if uid_line >= end or not lines[uid_line].isdigit():
            raise ValueError(f"Invalid mUniqueID position in {path}:{uid_line + 1}")
        uid = int(lines[uid_line])
        if uid not in wanted_uids:
            continue
        # The club's HIST block is the first one. Later HIST markers can belong to
        # nested player records because club members are serialized in this CLUB block.
        hist_offsets = [i for i, value in enumerate(block) if value == "%INDEX%HIST"]
        if not hist_offsets:
            raise ValueError(f"Missing club HIST block for UID {uid} in {path}")
        hist_offset = hist_offsets[0]
        if hist_offset < 2 or hist_offset + 8 >= len(block):
            raise ValueError(f"Truncated HIST/flags layout for UID {uid} in {path}")
        colors = parse_int_array(block[hist_offset - 1], "club colours")
        if len(colors) != 5:
            raise ValueError(f"Expected five club colours immediately before HIST for UID {uid}")
        flags_text = block[hist_offset - 2].strip()
        if not flags_text.isdigit() or not 0 <= int(flags_text) <= 65535:
            raise ValueError(f"Invalid lastSeasonFlags two lines before HIST for UID {uid}")
        histories = {}
        history_lines = {}
        for field_offset, field in enumerate(HISTORY_FIELDS, 1):
            absolute = start + hist_offset + field_offset
            histories[field] = parse_int_array(lines[absolute], field)
            history_lines[field] = absolute + 1
        flags = int(flags_text)
        reference_id = (country_id << 16) | club_index
        found[uid].append({
            "club_id": uid,
            "country_id": country_id,
            "club_reference_index": club_index,
            "reference_id": reference_id,
            "source_file": str(path.resolve()),
            "source_file_sha256": sha256(path),
            "club_start_line": start + 1,
            "club_unique_id_line": uid_line + 1,
            "last_season_flags_line": start + hist_offset - 1,
            "history_start_line": start + hist_offset + 1,
            "history_value_lines": history_lines,
            "lastSeasonFlags": flags,
            "mFirstTeamLastSeasonInfo": decode_first_team_flags(flags),
            "history": histories,
        })
    return found, {"path": str(path.resolve()), "sha256": sha256(path), "version": file_version}


def compare_row(row, club):
    result = {
        "country_id": row.get("country_id"),
        "club_id": row.get("club_id"),
        "reference_id": row.get("reference_id"),
        "club": row.get("club"),
        "kind": row.get("kind"),
        "target_field": row.get("target_field"),
        "proposed_value": row.get("proposed_value"),
        "draft_status": row.get("status"),
        "draft_hold": row.get("hold"),
        "comparison_status": "HELD",
        "hold": None,
    }
    if club is None:
        result["hold"] = "Stable club UID is missing or ambiguous in the declared country file."
        return result
    if row.get("reference_id") != club["reference_id"]:
        result["hold"] = f"Draft reference_id differs from source order reference {club['reference_id']}."
        return result
    field = row.get("target_field")
    if field in HISTORY_FIELDS:
        current = club["history"][field]
        proposed = row.get("proposed_value")
        result.update({
            "current_value": current,
            "source_line": club["history_value_lines"][field],
            "proposed_result": sorted(set(current + [proposed])) if isinstance(proposed, int) else None,
            "would_change": isinstance(proposed, int) and proposed not in current,
        })
        if not isinstance(proposed, int) or not 0 <= proposed <= 65535:
            result["hold"] = "History proposal is not a UShort year."
        else:
            result["comparison_status"] = "DRAFT_HELD" if row.get("status") == "HOLD" or row.get("hold") else "READY_FOR_SEPARATE_MUTATION_REVIEW"
            result["hold"] = row.get("hold")
        return result
    if field in FLAG_FIELDS:
        values, mask = FLAG_FIELDS[field]
        proposed = row.get("proposed_value")
        current = club["mFirstTeamLastSeasonInfo"]["league" if field.endswith(".mLeague") else "cup"]
        result.update({
            "current_value": current,
            "current_flags": club["lastSeasonFlags"],
            "source_line": club["last_season_flags_line"],
            "proposed_flags": ((club["lastSeasonFlags"] & ~mask) | values[proposed]) if proposed in values else None,
            "would_change": proposed in values and proposed != current,
        })
        if current == "AMBIGUOUS":
            result["hold"] = "Current mutually exclusive last-season bits are ambiguous."
        elif proposed not in values:
            result["hold"] = "Unsupported last-season enum proposal."
        else:
            result["comparison_status"] = "DRAFT_HELD" if row.get("status") == "HOLD" or row.get("hold") else "READY_FOR_SEPARATE_MUTATION_REVIEW"
            result["hold"] = row.get("hold")
        return result
    result["hold"] = "Unsupported target_field."
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--draft", type=Path, default=DEFAULT_DRAFT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--project-status", type=Path, default=ROOT / "reports/PROJECT_STATUS.json")
    args = parser.parse_args()
    draft_path, output_path = args.draft.resolve(), args.output.resolve()
    draft = read_json(draft_path)
    rows = draft.get("rows")
    if not isinstance(rows, list):
        raise ValueError("HISTORY_DRAFT.json rows must be a list")
    upstream_hashes = verify_upstream_layout(ROOT)
    status = read_json(args.project_status.resolve())
    candidate = Path(status["latest_validated_candidate"]).resolve()
    country_dir = candidate / "database/data"
    wanted = defaultdict(set)
    for row in rows:
        if isinstance(row.get("country_id"), int) and isinstance(row.get("club_id"), int):
            wanted[row["country_id"]].add(row["club_id"])
    matches = defaultdict(list)
    source_files = []
    file_holds = []
    for country_id, uids in sorted(wanted.items()):
        path = country_dir / f"CountryData{country_id}.sav"
        if not path.is_file():
            file_holds.append({"country_id": country_id, "hold": "CountryData source file is missing.", "path": str(path)})
            continue
        try:
            found, source = parse_country_file(path, country_id, uids)
            source_files.append(source)
            for uid, entries in found.items():
                matches[(country_id, uid)].extend(entries)
        except ValueError as error:
            file_holds.append({"country_id": country_id, "hold": str(error), "path": str(path)})
    clubs = {}
    club_holds = []
    for country_id, uids in sorted(wanted.items()):
        for uid in sorted(uids):
            entries = matches[(country_id, uid)]
            if len(entries) == 1:
                clubs[str(uid)] = entries[0]
            else:
                club_holds.append({"country_id": country_id, "club_id": uid, "matches": len(entries), "hold": "Missing stable UID" if not entries else "Ambiguous stable UID"})
    comparisons = [compare_row(row, clubs.get(str(row.get("club_id")))) for row in rows]
    counts = Counter(item["comparison_status"] for item in comparisons)
    output = {
        "schema": 1,
        "status": "PASS_WITH_HOLDS" if file_holds or club_holds or counts.get("HELD") or counts.get("DRAFT_HELD") else "PASS",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "draft": {"path": str(draft_path), "sha256": sha256(draft_path), "rows": len(rows)},
        "native07_candidate": {"path": str(candidate), "declared_by": str(args.project_status.resolve()), "source_files": source_files},
        "layout_verification": {"status": "PASS", "upstream_source_sha256": upstream_hashes, "rules": "FM13.12 CLUB header; UID after version; flags two lines before HIST; eight ordered UShort vectors"},
        "summary": {"referenced_club_uids": sum(len(v) for v in wanted.values()), "matched_club_uids": len(clubs), "comparisons": len(comparisons), "comparison_statuses": dict(sorted(counts.items()))},
        "clubs_by_stable_uid": clubs,
        "comparisons": comparisons,
        "holds": {"source_files": file_holds, "clubs": club_holds},
        "limitations": "Inspection and hypothetical comparison only. No candidate, runtime, save, draft, or production data was changed.",
    }
    write_json(output_path, output)
    print(json.dumps({"output": str(output_path), "status": output["status"], **output["summary"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
