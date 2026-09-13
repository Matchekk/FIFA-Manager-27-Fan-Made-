"""Audit what the active FIFA Manager 13 3D engine proves about tactics.

The audit is read-only. It verifies the exact team-tactic payload exposed by the
available parser source, the active formation catalogue, and the situational
option-scoring constants referenced by GfxCore.dll. It intentionally does not
turn those context-dependent constants into an unsupported universal ranking.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_big(path: Path) -> dict[str, bytes]:
    data = path.read_bytes()
    if data[:4] not in (b"BIGF", b"BIG4") or len(data) < 16:
        raise ValueError("unsupported EA BIG archive")
    count, index_end = struct.unpack_from(">II", data, 8)
    if index_end > len(data) or index_end < 16:
        raise ValueError("invalid EA BIG index boundary")
    position = 16
    entries: dict[str, bytes] = {}
    for _ in range(count):
        if position + 8 > index_end:
            raise ValueError("truncated EA BIG index")
        offset, size = struct.unpack_from(">II", data, position)
        position += 8
        zero = data.find(b"\0", position, index_end)
        if zero < 0:
            raise ValueError("unterminated EA BIG file name")
        name = data[position:zero].decode("ascii").replace("\\", "/")
        position = zero + 1
        if offset + size > len(data) or name in entries:
            raise ValueError(f"invalid or duplicate EA BIG entry: {name}")
        payload = data[offset : offset + size]
        if payload[:2] == b"\x10\xfb":
            raise ValueError(f"compressed BIG entry is unsupported: {name}")
        entries[name] = payload
    return entries


def assignments(payload: bytes) -> dict[str, float | int]:
    result: dict[str, float | int] = {}
    pattern = re.compile(r"^\s*([A-Z][A-Z0-9_]*)\s*=\s*(-?(?:\d+(?:\.\d*)?|\.\d+))")
    for raw_line in payload.decode("cp1252").splitlines():
        match = pattern.match(raw_line.split("//", 1)[0])
        if match:
            key, raw = match.groups()
            result[key] = float(raw) if "." in raw else int(raw)
    return result


def require(values: dict[str, float | int], *keys: str) -> dict[str, float | int]:
    missing = [key for key in keys if key not in values]
    if missing:
        raise ValueError(f"missing expected active values: {missing}")
    return {key: values[key] for key in keys}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    runtime = args.runtime.resolve()
    output = args.output.resolve()
    if not runtime.is_relative_to((ROOT / "runtime").resolve()):
        raise ValueError("runtime must stay inside the project runtime directory")
    if not output.is_relative_to((ROOT / "reports").resolve()):
        raise ValueError("output must stay inside the project reports directory")

    archive_path = runtime / "config.big"
    engine_path = runtime / "GfxCore.dll"
    formations_path = runtime / "fmdata" / "Formations.xml"
    parser_source_path = ROOT / "upstream" / "fifam" / "fifa07api" / "Fifa07Team.cpp"

    archive_bytes = archive_path.read_bytes()
    engine_bytes = engine_path.read_bytes()
    formations_bytes = formations_path.read_bytes()
    parser_source_bytes = parser_source_path.read_bytes()
    entries = read_big(archive_path)
    tcmai = assignments(entries["tcmai.ini"])
    common = assignments(entries["common.ini"])

    parser_source = parser_source_bytes.decode("utf-8")
    payload_match = re.search(
        r"ParseTeamWrite\([^)]*\)\s*\{\s*line\s*>>\s*([^;]+);",
        parser_source,
        re.DOTALL,
    )
    if not payload_match:
        raise ValueError("unable to find ParseTeamWrite payload")
    payload_fields = [part.strip() for part in payload_match.group(1).split(">>")]
    expected_prefix = [
        "teamid",
        "offsidetrap",
        "withoutball",
        "formationid",
        "attack",
        "teammentality",
        "attacktactic1",
        "attacktactic2",
        "defensetactic1",
        "defensetactic2",
    ]
    if payload_fields[: len(expected_prefix)] != expected_prefix:
        raise ValueError("unexpected teamwrite tactical payload")

    root = ET.fromstring(formations_bytes)
    formations = root.findall("./Formation")
    declared_count = int(root.findtext("FormationsCount", "0"))
    formation_ids = [int(node.findtext("ID", "0")) for node in formations]
    if len(formation_ids) != len(set(formation_ids)):
        raise ValueError("duplicate formation IDs")
    first_tactics = formations[0].find("TeamTactics")
    if first_tactics is None:
        raise ValueError("formation catalogue has no TeamTactics")
    team_tactic_tags = [node.tag for node in list(first_tactics)]

    scoring_keys = (
        "OPTION_VALUE_MAX",
        "OPTION_VALUE_BASE",
        "OPTION_VALUE_FORWARD_MIN",
        "OPTION_VALUE_FORWARD",
        "OPTION_VALUE_FORWARD_MAX",
        "OPTION_VALUE_SAFE_MIN",
        "OPTION_VALUE_SAFE",
        "OPTION_VALUE_SAFE_MAX",
        "OPTION_VALUE_GOAL_ANGLE_BONUS",
        "OPTION_VALUE_PASS_FORWARD_MIN",
        "OPTION_VALUE_PASS_FORWARD_DEFAULT",
        "OPTION_VALUE_PASS_FORWARD_MAX",
        "OPTION_VALUE_RECV_SAFE",
        "OPTION_VALUE_THROUGH_PASS_FORWARD",
        "OPTION_VALUE_LOB_PASS_FORWARD",
        "OPTION_VALUE_LOB_PASS_SAFE",
        "OPTION_VALUE_DRIBBLE_DIRECTION",
        "OPTION_VALUE_DRIBBLE_SAFE",
        "OPTION_VALUE_DRIBBLE_FORWARD",
        "OPTION_VALUE_DRIBBLE_BACKWARDS",
        "OPTION_SHOOTING_YARDS_CLOSE",
        "OPTION_SHOOTING_YARDS_FAR",
        "OPTION_SHOOTING_FROM_DISTANCE_BIAS",
        "DRIBBLE_SPEED_PENALTY",
        "FBI_SECOND_MARKER_THRESHOLD",
        "FBI_SECOND_MARKER_DIFF_THRESHOLD",
        "FBI_HYSTERESIS_SECONDS",
    )
    score_values = require(tcmai, *scoring_keys)
    binary_references = {
        key: engine_bytes.find(key.encode("ascii")) >= 0 for key in scoring_keys
    }
    missing_binary_refs = [key for key, present in binary_references.items() if not present]
    expected_config_only = ["OPTION_VALUE_MAX", "OPTION_VALUE_GOAL_ANGLE_BONUS"]
    if missing_binary_refs != expected_config_only:
        raise ValueError(
            "unexpected GfxCore.dll scoring-key reference boundary: "
            f"{missing_binary_refs}"
        )

    engine_markers = (
        "tcm_tactics.cpp",
        "tcm_formation.cpp",
        "Passing Style -> at least NORMAL",
        "Passing Style -> at least DIRECT",
        "Passing Style -> at least RISKY",
        "TCM_TACTICS_QUICKCALCULATION",
        "TCM_TACTICS_ACCELERATION",
    )
    marker_offsets = {
        marker: engine_bytes.find(marker.encode("ascii")) for marker in engine_markers
    }
    if any(offset < 0 for offset in marker_offsets.values()):
        raise ValueError("expected tactics code markers are missing from GfxCore.dll")

    sku_text = entries["sku.ini"].decode("cp1252")
    benchmark_warning = "FIFAMARK Settings: Need to be fixed since new AI"
    benchmark_keys_commented = all(
        re.search(rf"^\s*//\s*{key}\s*=", sku_text, re.MULTILINE)
        for key in ("FIFAMARK_MODE", "FIFAMARK_LOOPCOUNT", "FIFAMARK_SCRIPT")
    )
    if benchmark_warning not in sku_text or not benchmark_keys_commented:
        raise ValueError("unexpected FIFAMARK benchmark state")

    result = {
        "status": "PASS_CODE_EVIDENCE_BOUNDARY",
        "conclusion": "NO_UNIVERSAL_BEST_TACTIC_PROVABLE_FROM_STATIC_CODE",
        "runtime": str(runtime),
        "inputs": {
            "GfxCore.dll": {"path": str(engine_path), "sha256": sha256(engine_bytes)},
            "config.big": {"path": str(archive_path), "sha256": sha256(archive_bytes)},
            "Formations.xml": {
                "path": str(formations_path),
                "sha256": sha256(formations_bytes),
            },
            "Fifa07Team.cpp": {
                "path": str(parser_source_path),
                "sha256": sha256(parser_source_bytes),
            },
        },
        "code_proven": {
            "teamwrite_tactical_payload": payload_fields[: len(expected_prefix)],
            "engine_source_markers": marker_offsets,
            "formation_catalogue": {
                "declared_count": declared_count,
                "serialized_nodes": len(formations),
                "unique_ids": len(set(formation_ids)),
                "normal_ids": [min(formation_ids), max(i for i in formation_ids if i < 100)],
                "short_handed_ids": [i for i in formation_ids if i >= 100],
                "team_tactic_tags": team_tactic_tags,
            },
            "situational_option_scoring": score_values,
            "direct_engine_key_references": binary_references,
            "config_only_selected_keys": missing_binary_refs,
            "offside_enabled": common.get("OFFSIDE"),
            "built_in_benchmark": {
                "warning": benchmark_warning,
                "configuration_commented_out": benchmark_keys_commented,
                "usable_as_proof_harness": False,
            },
        },
        "proof_logic": [
            "The runtime receives several independent tactical fields rather than one scalar tactic score.",
            "The action selector assigns different values to forward progress, safety, receiver safety, goal angle, distance, pass type and dribble direction.",
            "Those inputs change with players, opponents, ball position and match state, so static constants do not define a total ordering of formations or tactical payloads.",
            "The bundled repeat-match benchmark cannot close that gap because its own active configuration says it needs fixing for the new AI and leaves its controls commented out.",
        ],
        "required_for_best_tactic_claim": {
            "method": "controlled repeated 3D matches",
            "controls": [
                "same teams and player attributes",
                "same fitness, morale, injuries and venue",
                "many random seeds per tactical variant",
                "declared outcome metric such as points or goal difference",
                "holdout opponents and confidence intervals",
            ],
            "current_status": "NO_WORKING_AUTOMATED_MATCH_HARNESS",
        },
        "modified_game_files": [],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "output": str(output)}, indent=2))


if __name__ == "__main__":
    main()
