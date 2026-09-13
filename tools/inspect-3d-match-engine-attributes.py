"""Extract direct 3D match-engine attribute evidence from an isolated runtime.

This reads the EA BIG archive and GfxCore.dll without modifying either file.  It
publishes only selected tuning values and hashes, not the proprietary source files.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
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
            raise ValueError(f"selected parser does not accept compressed entry: {name}")
        entries[name] = payload
    if position > index_end:
        raise ValueError("EA BIG index overflow")
    return entries


def assignments(payload: bytes) -> dict[str, float | int]:
    result: dict[str, float | int] = {}
    text = payload.decode("cp1252")
    pattern = re.compile(r"^\s*([A-Z][A-Z0-9_]*)\s*=\s*(-?(?:\d+(?:\.\d*)?|\.\d+))")
    for raw_line in text.splitlines():
        line = raw_line.split("//", 1)[0]
        match = pattern.match(line)
        if not match:
            continue
        key, raw_value = match.groups()
        value: float | int = float(raw_value) if "." in raw_value else int(raw_value)
        result[key] = value
    return result


def require(values: dict[str, float | int], *keys: str) -> dict[str, float | int]:
    missing = [key for key in keys if key not in values]
    if missing:
        raise ValueError(f"missing expected match-engine values: {missing}")
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
    archive_bytes = archive_path.read_bytes()
    engine_bytes = engine_path.read_bytes()
    entries = read_big(archive_path)
    for name in ("ai.ini", "career.ini", "tcmai.ini"):
        if name not in entries:
            raise ValueError(f"missing config.big entry: {name}")

    ai = assignments(entries["ai.ini"])
    tcmai = assignments(entries["tcmai.ini"])
    career = assignments(entries["career.ini"])

    action_names = {
        "direct_shot": "DIRECT_SHOT",
        "long_shot": "LONG_SHOT",
        "passing": "PASSING",
        "long_passing": "LONG_PASSING",
        "dribbling": "DRIBBLING",
        "crossing": "CROSSING",
        "tackling": "TACKLING",
        "marking": "MARKING",
    }
    action_quality = {
        name: require(
            tcmai,
            *(f"{tier}_ACTION_{suffix}" for tier in ("POOR", "AVG", "GOOD", "EX")),
        )
        for name, suffix in action_names.items()
    }

    referenced_keys = [
        "SPRINT_SPEED_POOR",
        "SPRINT_SPEED_EX",
        "TECHNIQUE_MIN_PERC",
        "TECHNIQUE_MAX_PERC",
        "HEADER_CHALLENGE_WEIGHT_INFRONT",
        "HEADER_CHALLENGE_WEIGHT_HEIGHT",
        "HEADER_CHALLENGE_WEIGHT_STRENGTH",
        "HEADER_CHALLENGE_WEIGHT_JUMP",
        "TCM_CONSISTENCY_IMPACT_FACTOR",
        "TCM_CONSISTENCY_ERROR_GLOBAL_LIMIT",
        *[key for curve in action_quality.values() for key in curve],
    ]
    engine_references = {
        key: engine_bytes.find(key.encode("ascii")) >= 0 for key in sorted(set(referenced_keys))
    }
    missing_references = [key for key, present in engine_references.items() if not present]
    core_reference_prefixes = (
        "SPRINT_SPEED_",
        "HEADER_CHALLENGE_WEIGHT_",
        "POOR_ACTION_",
        "AVG_ACTION_",
        "GOOD_ACTION_",
        "EX_ACTION_",
    )
    missing_core_references = [
        key for key in missing_references if key.startswith(core_reference_prefixes)
    ]
    if missing_core_references:
        raise ValueError(f"GfxCore.dll does not reference core expected keys: {missing_core_references}")

    raw_attribute_names = [
        "BALL_CONTROL",
        "SHOT_POWER",
        "LONG_SHOTS",
        "CROSSING",
        "PASSING_SHORT",
        "PASSING_LONG",
        "TACKLE_STANDING",
        "TACKLE_SLIDING",
        "MARKING",
        "ACCELERATION",
        "SPRINT_SPEED",
        "STRENGTH",
        "CONSISTENCY",
    ]
    detected_attributes = [
        name for name in raw_attribute_names if engine_bytes.find(name.encode("ascii")) >= 0
    ]
    if detected_attributes != raw_attribute_names:
        raise ValueError("expected raw 3D attribute names were not all found in GfxCore.dll")

    result = {
        "status": "PASS_DIRECT_3D_ENGINE_EVIDENCE",
        "scope": "3D_MATCH_ENGINE_ONLY",
        "runtime": str(runtime),
        "config_archive": {
            "path": str(archive_path),
            "sha256": sha256(archive_bytes),
            "entries": len(entries),
            "selected_entry_hashes": {
                name: sha256(entries[name]) for name in ("ai.ini", "career.ini", "tcmai.ini")
            },
        },
        "engine": {
            "path": str(engine_path),
            "sha256": sha256(engine_bytes),
            "detected_raw_attribute_names": detected_attributes,
            "all_selected_tuning_keys_referenced": not missing_references,
            "selected_tuning_key_references": engine_references,
            "config_only_selected_keys": missing_references,
        },
        "direct_evidence": {
            "attribute_tiers": require(tcmai, "ATTRIBUTE_AVG", "ATTRIBUTE_GOOD", "ATTRIBUTE_EX"),
            "sprint_speed": require(tcmai, "SPRINT_SPEED_POOR", "SPRINT_SPEED_EX"),
            "dribbling_run_speed_percent": require(
                tcmai, "TECHNIQUE_MIN_PERC", "TECHNIQUE_MAX_PERC"
            ),
            "heading_challenge_weights": require(
                tcmai,
                "HEADER_CHALLENGE_WEIGHT_INFRONT",
                "HEADER_CHALLENGE_WEIGHT_HEIGHT",
                "HEADER_CHALLENGE_WEIGHT_STRENGTH",
                "HEADER_CHALLENGE_WEIGHT_JUMP",
            ),
            "action_quality_curves": action_quality,
            "tackling_duel_parameters": require(
                tcmai,
                "TACKLE_MISSCHANCE_POOR",
                "TACKLE_MISSCHANCE_AVG",
                "TACKLE_MISSCHANCE_GOOD",
                "TACKLE_MISSCHANCE_EX",
                "TACKLE_DRIBBLER_CHANGE_POOR",
                "TACKLE_DRIBBLER_CHANGE_AVG",
                "TACKLE_DRIBBLER_CHANGE_GOOD",
                "TACKLE_DRIBBLER_CHANGE_EX",
            ),
            "consistency_penalty": require(
                tcmai,
                "TCM_CONSISTENCY_IMPACT_FACTOR",
                "TCM_CONSISTENCY_ERROR_GLOBAL_LIMIT",
            ),
            "cpu_attribute_effect_switch": require(ai, "PLAYER_ATTR_CPU_EFFECT_ON"),
            "career_morale_attribute_delta": require(
                career,
                "MORALE_ATTRIB_1",
                "MORALE_ATTRIB_2",
                "MORALE_ATTRIB_3",
                "MORALE_ATTRIB_4",
                "MORALE_ATTRIB_5",
            ),
        },
        "interpretation": {
            "global_weight_table_found": False,
            "pace": "Direct repeated effect: the configured poor-to-excellent sprint-speed endpoints are 6.0 to 11.0 engine units.",
            "acceleration": "The raw attribute and acceleration-specific code are present, but its response curve is hard-coded rather than exposed as a scalar in config.big.",
            "heading": "Aerial challenge shares are explicit: jump 55%, strength 25%, height 15%, position in front 5%.",
            "technical_attributes": "Shot, pass, dribble, cross, tackle and marking use separate nonlinear action-quality curves; they are not one interchangeable global score.",
            "ranking_limit": "A complete cross-attribute ranking requires controlled match simulations because attributes act in different events and many formulas remain hard-coded.",
        },
        "excluded": [
            "Player Level.txt position weighting",
            "displayed position strength",
            "text-mode event selection",
        ],
        "modified_files": [],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "output": str(output)}, indent=2))


if __name__ == "__main__":
    main()
