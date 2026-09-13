import importlib.util
import unittest
from pathlib import Path


TOOL = Path(__file__).resolve().parents[1] / "tools" / "native10-semantic-diff.py"
SPEC = importlib.util.spec_from_file_location("native10_semantic_diff", TOOL)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def row(fm_id: str, club: str, serialized: str) -> dict[str, str]:
    return {
        "fm_id": fm_id,
        "fifa_id": "0",
        "dob": "28.12.1989",
        "name": "Chico Monteiro",
        "club_id": club,
        "history_sha256": "history",
        "protected_conditions_sha256": "protected",
        "future_conditions_sha256": "future",
        "serialized_sha256": serialized,
    }


class SemanticDuplicateTests(unittest.TestCase):
    def test_club_membership_change_is_semantic_with_byte_stable_player_block(self) -> None:
        before = row("20417", "8524039", "same-block")
        after = row("30417", "999", "same-block")
        self.assertNotEqual(MODULE.semantic_fingerprint(before), MODULE.semantic_fingerprint(after))
        self.assertEqual(before["serialized_sha256"], after["serialized_sha256"])

    def test_stable_multiset_preserves_duplicate_multiplicity(self) -> None:
        before = [row("20417", "8524039", "a"), row("20423", "8523778", "b")]
        after = [row("10417", "8524039", "x"), row("10423", "8523778", "y")]
        self.assertEqual(MODULE.multiset(before), MODULE.multiset(after))
        self.assertEqual(len(MODULE.group(before, MODULE.identity)[MODULE.identity(before[0])]), 2)

        after[0]["future_conditions_sha256"] = "changed"
        self.assertNotEqual(MODULE.multiset(before), MODULE.multiset(after))

    def test_planned_duplicate_maps_only_after_unchanged_sibling_consumed(self) -> None:
        baseline = row("20417", "8524039", "a")
        sibling = row("20423", "8523778", "b")
        changed = row("30417", "999", "c")
        actual, errors = MODULE.map_planned_group(
            [baseline, sibling], [row("30423", "8523778", "z"), changed], {"fm_id": "20417"}
        )
        self.assertEqual(errors, [])
        self.assertEqual(actual["club_id"], "999")

    def test_planned_duplicate_rejects_ambiguous_residual(self) -> None:
        baseline = row("20417", "8524039", "a")
        sibling = row("20423", "8523778", "b")
        actual, errors = MODULE.map_planned_group(
            [baseline, sibling],
            [row("30423", "8523778", "z"), row("30417", "999", "c"), row("30418", "998", "d")],
            {"fm_id": "20417"},
        )
        self.assertIsNone(actual)
        self.assertTrue(any("unambiguously" in error["error"] for error in errors))


if __name__ == "__main__":
    unittest.main()
