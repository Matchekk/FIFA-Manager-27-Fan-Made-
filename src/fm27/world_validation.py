"""Compare native FM13 club/country metadata and separately serialized links."""
import json
from collections import Counter
from pathlib import Path

from .common import read_csv, sha256

TABLES = {
    "clubs": ("native_world_clubs.csv", ("club_id", "country_id", "national", "serialized_sha256")),
    "countries": ("native_world_countries.csv", ("country_id", "serialized_sha256")),
    "person_links": ("native_world_person_links.csv", ("kind", "owner_id", "slot", "person_key")),
}


def compare_world(expected: Path, actual: Path, *, metadata_only=False) -> dict:
    metadata = [json.loads((folder / "NATIVE_WORLD_SEMANTICS.json").read_text(encoding="utf-8"))
                for folder in (expected, actual)]
    errors = []
    for label, meta in zip(("expected", "actual"), metadata):
        if meta.get("schema") != 1 or meta.get("link_errors") != 0 or meta.get("person_key_collisions") != 0:
            errors.append(f"{label}: unsupported schema or invalid/ambiguous native links")
    checks = {}
    for name, (filename, fields) in TABLES.items():
        if metadata_only and name == "person_links":
            continue
        sides = []
        for label, folder, meta in zip(("expected", "actual"), (expected, actual), metadata):
            rows = read_csv(folder / filename)
            counter = Counter(tuple(row[field] for field in fields) for row in rows)
            if len(rows) != meta.get(name) or (name != "person_links" and not rows):
                errors.append(f"{label}: {name} missing or count disagrees with native metadata")
            if name in ("clubs", "countries"):
                identity_field = "club_id" if name == "clubs" else "country_id"
                if len({row[identity_field] for row in rows}) != len(rows):
                    errors.append(f"{label}: duplicate {name} identity")
            sides.append(counter)
        before, after = sides
        checks[name] = {
            "status": "PASS" if before == after else "FAIL",
            "expected": before.total(), "actual": after.total(),
            "unexpected_missing": (before - after).total(), "unexpected_added": (after - before).total(),
            "examples_expected": list((before - after).items())[:5],
            "examples_actual": list((after - before).items())[:5],
            "expected_sha256": sha256(expected / filename), "actual_sha256": sha256(actual / filename),
        }
    return {
        "status": "PASS" if not errors and all(c["status"] == "PASS" for c in checks.values()) else "FAIL",
        "comparison": "UNCHANGED_CLUB_COUNTRY_METADATA" if metadata_only else "NATIVE_WORLD_REREAD",
        "checks": checks, "errors": errors,
        "expected_metadata_sha256": sha256(expected / "NATIVE_WORLD_SEMANTICS.json"),
        "actual_metadata_sha256": sha256(actual / "NATIVE_WORLD_SEMANTICS.json"),
        "limitations": "Club metadata including stadiums, country headers/rules/referees/CAC pool. "
                       + ("Player membership and captain changes are excluded from this metadata mutation check. "
                          if metadata_only else "Club member ordering, captain slots and country free-staff membership. ")
                       + "Requires separate player/staff/competition/relationship checks. Global cities, regions, "
                         "assessment, full world completeness and engine behavior remain unproved.",
        "release_ready": False,
    }


def bind_world_inspection(expected: Path, actual: Path, *, plan_hash: str,
                          before_hash: str, expected_hash: str, actual_hash: str) -> dict:
    """Bind a read-only replay to the exact already validated player candidate."""
    provenance_path = expected / "NATIVE_BUILD_INPUTS.json"
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    if (provenance.get("status") != "READ_ONLY_PLAN_INSPECTION_COMPLETED"
            or provenance.get("mode") != "INSPECT_PLAN"
            or provenance.get("plan_sha256") != plan_hash
            or provenance.get("immutable_inputs_unchanged") is not True):
        raise ValueError("World inspection is incomplete or belongs to a different frozen plan")
    binary_hash = provenance.get("binary_sha256")
    for key in ("build", "native_tests"):
        if provenance.get(key, {}).get("status") != "PASS" or provenance[key].get("binary_sha256") != binary_hash:
            raise ValueError("World inspection lacks matching native build/test evidence")
    if not binary_hash or not provenance["build"].get("source_sha256") or provenance["build"]["source_sha256"] != provenance["native_tests"].get("source_sha256"):
        raise ValueError("World inspection build/test sources disagree")
    for folder, digest in ((expected / "before-plan", before_hash), (expected, expected_hash), (actual, actual_hash)):
        if sha256(folder / "native_player_semantics.csv") != digest:
            raise ValueError("World inspection player state differs from the verified candidate or baseline")
    reread = compare_world(expected, actual)
    mutation = compare_world(expected / "before-plan", expected, metadata_only=True)
    global_checks = None
    if any((folder / "NATIVE_GLOBAL_SEMANTICS.json").exists() for folder in (expected, actual)):
        global_checks = {"reread": compare_global(expected, actual),
                         "mutation_scope": compare_global(expected / "before-plan", expected)}
    passed = reread["status"] == mutation["status"] == "PASS"
    if global_checks is not None:
        passed = passed and all(c["status"] == "PASS" for c in global_checks.values())
    return {"status": "PASS" if passed else "FAIL",
            "reread": reread, "metadata_mutation_scope": mutation,
            "global_entities": global_checks,
            "inspection_inputs_sha256": sha256(provenance_path), "binary_sha256": binary_hash,
            "plan_sha256": plan_hash, "release_ready": False}


def compare_global(expected: Path, actual: Path) -> dict:
    """Global object counts, identities and contents must all survive reread."""
    sides, errors = [], []
    counts = {"CITY": "cities", "REGION": "regions", "APPEARANCE": "appearance_definitions",
              "CUP_TEMPLATE": "cup_templates"}
    for label, folder in (("expected", expected), ("actual", actual)):
        meta = json.loads((folder / "NATIVE_GLOBAL_SEMANTICS.json").read_text(encoding="utf-8"))
        world = json.loads((folder / "NATIVE_WORLD_SEMANTICS.json").read_text(encoding="utf-8"))
        rows = read_csv(folder / "native_global_semantics.csv")
        if meta.get("schema") != 1 or meta.get("records") != len(rows):
            errors.append(f"{label}: schema/count metadata mismatch")
        if meta.get("legacy_standalone_stadiums") != 0 or meta.get("legacy_sponsors") != 0:
            errors.append(f"{label}: legacy stadium/sponsor objects require additional coverage")
        kinds = Counter(r["kind"] for r in rows)
        for kind, count in {**{kind: meta.get(field) for kind, field in counts.items()},
                            "RULES": 1, "ASSESSMENT": world["countries"]}.items():
            if kinds[kind] != count:
                errors.append(f"{label}: {kind} object count disagrees with metadata")
        if set(kinds) - (set(counts) | {"RULES", "ASSESSMENT"}):
            errors.append(f"{label}: unknown global object kind")
        if len({(r["kind"], r["object_id"]) for r in rows}) != len(rows):
            errors.append(f"{label}: duplicate global object identity")
        sides.append(Counter((r["kind"], r["object_id"], r["serialized_sha256"]) for r in rows))
    before, after = sides
    return {"status": "PASS" if not errors and before == after else "FAIL",
            "expected": before.total(), "actual": after.total(), "errors": errors,
            "unexpected_missing": (before - after).total(), "unexpected_added": (after - before).total(),
            "examples_expected": list((before - after).items())[:5], "examples_actual": list((after - before).items())[:5],
            "expected_sha256": sha256(expected / "native_global_semantics.csv"),
            "actual_sha256": sha256(actual / "native_global_semantics.csv"),
            "expected_metadata_sha256": sha256(expected / "NATIVE_GLOBAL_SEMANTICS.json"),
            "actual_metadata_sha256": sha256(actual / "NATIVE_GLOBAL_SEMANTICS.json"),
            "scope": "Global rules, assessment, cities, regions, appearance definitions and cup templates.",
            "limitations": "Requires other native object and support-file comparisons, source-file coverage audit and engine tests.",
            "release_ready": False}
