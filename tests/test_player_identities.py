import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from fm27.common import sha256, write_csv
from fm27.matching import IdentityIndex, recover_profile_identity
from fm27.player_identities import load_player_identities, verified_profile
from fm27.transfer_timeline import match_profile
from fm27.transfermarkt import parse_profile


class ReviewedPlayerIdentityTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.snapshot = "2026-09-08"
        self.url = "https://www.transfermarkt.de/source/profil/spieler/10"
        html = f'''<link rel="canonical" href="{self.url}"><h1>Source Spelling</h1>
        <div class="info-table"><span class="info-table__content--regular">Geb./Alter:</span>
        <span class="info-table__content--bold">02.01.2000</span>
        <span class="info-table__content--regular">Aktueller Verein:</span>
        <span class="info-table__content--bold"><a href="/club/verein/22">Club</a></span></div>'''
        digest = hashlib.sha256(html.encode()).hexdigest()
        self.raw = self.root / "data/raw/transfermarkt" / (digest + ".html")
        self.raw.parent.mkdir(parents=True)
        self.raw.write_bytes(html.encode("utf-8"))
        self.profile = {**parse_profile(html, "10"), "source": self.url,
                        "source_sha256": digest, "snapshot_date": self.snapshot}
        self.person = {"fm_id": "7", "fifa_id": "123", "dob": "2000-01-02",
                       "name": "Native Spelling", "nationality": "49", "club_id": "11"}
        self.players = [self.person]
        self.baseline = self.root / "players.csv"
        self.baseline.write_text("bound baseline", encoding="utf-8")
        self.aliases = {"22": {"club_id": "222"}}
        self.row = {"player_tm_id": "10", "fm_id": "7", "native_fifa_id": "123",
                    "source_name": "Source Spelling", "native_name": "Native Spelling",
                    "dob": "2000-01-02", "native_nationality": "49", "native_club_id": "11",
                    "current_club_tm_id": "22", "target_club_id": "222", "profile_source": self.url,
                    "profile_sha256": digest, "reviewed_on": self.snapshot, "reviewed_by": "Reviewer",
                    "reason": "Individually corroborated spelling", "public_sources": [
                        {"url": "https://example.com/official", "access": "BODY_READ", "supports": "DOB and spelling"}]}
        self.path = self.root / "data/overrides/player_identities.json"
        self.path.parent.mkdir(parents=True)

    def load(self, rows=None, profiles=None):
        self.path.write_text(json.dumps({"schema": 1, "snapshot_date": self.snapshot,
            "baseline_sha256": sha256(self.baseline), "rows": rows if rows is not None else [self.row]}), encoding="utf-8")
        return load_player_identities(self.root, self.snapshot, profiles if profiles is not None else [self.profile],
                                      self.players, self.baseline, self.aliases)

    def recover(self, profile, **changes):
        evidence = {**self.profile, **changes}
        return recover_profile_identity(IdentityIndex(self.players), evidence, profile, self.snapshot, "22", "222")

    def test_review_recovers_same_existing_person_in_both_workflows_without_mutation(self):
        original = copy.deepcopy((self.profile, self.players))
        profiles, proof = self.load()
        self.assertEqual(self.recover(profiles[0]), ("REVIEWED_IDENTITY", [self.person]))
        self.assertEqual(match_profile(profiles[0], IdentityIndex(self.players)), ("REVIEWED_IDENTITY", self.person))
        self.assertEqual(proof["reviewed_people"], 1)
        self.assertEqual((self.profile, self.players), original)

    def test_without_review_no_fuzzy_name_recovery(self):
        profiles, proof = load_player_identities(self.root, self.snapshot, [self.profile], self.players, self.baseline, self.aliases)
        self.assertEqual(proof, {})
        self.assertEqual(self.recover(profiles[0])[0], "MISSING_FROM_FM")
        self.assertEqual(match_profile(profiles[0], IdentityIndex(self.players))[0], "MISSING_FROM_FM")

    def test_profile_binding_changes_rejected(self):
        for field, value in (("dob", "2001-01-02"), ("club_tm_id", "33"), ("source", "https://example.com/other"),
                             ("source_sha256", "b" * 64), ("snapshot_date", "2026-09-09"), ("full_name", "Someone Else")):
            with self.subTest(field=field), self.assertRaises((ValueError, FileNotFoundError)):
                self.load(profiles=[{**self.profile, field: value}])

    def test_changed_raw_bytes_and_baseline_rejected(self):
        self.load()
        self.baseline.write_text("other baseline", encoding="utf-8")
        with self.assertRaises(ValueError):
            load_player_identities(self.root, self.snapshot, [self.profile], self.players, self.baseline, self.aliases)
        self.raw.write_text("different HTML", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.load()

    def test_native_identity_tuple_and_club_alias_cannot_drift(self):
        for field in ("fm_id", "fifa_id", "name", "dob", "nationality", "club_id"):
            with self.subTest(field=field):
                self.players = [{**self.person, field: "changed"}]
                with self.assertRaises(ValueError): self.load()
        self.players = [self.person]
        self.aliases["22"]["club_id"] = "333"
        with self.assertRaises(ValueError): self.load()

    def test_duplicate_review_source_native_and_fifa_id_rejected(self):
        with self.assertRaises(ValueError): self.load(rows=[self.row, dict(self.row)])
        with self.assertRaises(ValueError): self.load(profiles=[self.profile, dict(self.profile)])
        for extra in (dict(self.person), {**self.person, "fm_id": "8", "name": "Other Person"}):
            self.players = [self.person, extra]
            with self.assertRaises(ValueError): self.load()

    def test_other_source_cannot_claim_same_native_person(self):
        with self.assertRaises(ValueError):
            self.load(profiles=[self.profile, {**self.profile, "player_tm_id": "20", "player": self.person["name"]}])

    def test_review_provenance_required(self):
        for field in ("reviewed_on", "reviewed_by", "reason", "public_sources"):
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.load(rows=[{**self.row, field: ""}])

    def test_supplied_fifa_conflict_never_overridden(self):
        profiles, _ = self.load()
        self.assertEqual(self.recover(profiles[0], fifa_id="999")[0], "CONFLICT")
        self.assertEqual(match_profile({**profiles[0], "fifa_id": "999"}, IdentityIndex(self.players))[0], "CONFLICT")
        self.assertEqual(self.recover(profiles[0], fifa_id="123")[0], "FIFA_ID")

    def test_natural_identity_conflict_and_later_native_changes_remain_held(self):
        profiles, _ = self.load()
        other = {**self.person, "fm_id": "8", "fifa_id": "456", "name": self.profile["player"]}
        self.players.append(other)
        with self.assertRaises(ValueError): self.load()
        self.assertEqual(self.recover(profiles[0])[0], "CONFLICT")
        self.assertEqual(match_profile(profiles[0], IdentityIndex(self.players))[0], "CONFLICT")
        self.players = [{**self.person, "club_id": "33"}]
        self.assertEqual(self.recover(profiles[0])[0], "CONFLICT")

    def test_runtime_profile_and_snapshot_guards_still_apply(self):
        profiles, _ = self.load()
        for change in ({"source_sha256": "b" * 64}, {"dob": "2001-01-02"}, {"club_tm_id": "33"}):
            with self.subTest(change=change):
                self.assertEqual(self.recover({**profiles[0], **change})[0], "CONFLICT")
        self.assertEqual(self.recover(profiles[0], player_tm_id="20")[0], "CONFLICT")
        result = recover_profile_identity(IdentityIndex(self.players), self.profile, profiles[0], "2026-09-09", "22")
        self.assertEqual(result[0], "REVIEW_REQUIRED")

    def test_cached_profile_fields_are_reparsed(self):
        parsed = verified_profile(self.root, {**self.profile, "contract_until": "2099-01-01"}, self.snapshot)
        self.assertEqual(parsed["contract_until"], "")

    def bind_unassigned(self, name="Source Spelling", common_name=None):
        self.person["fifa_id"] = "0"
        self.row["native_fifa_id"] = "0"
        first, last = name.split(" ", 1)
        payload = {"props": {"pageProps": {"gameDetails": {"slug": "fc-27"},
            "teamGroup": {"id": "19", "gender": {"id": 0}, "teams": [{"id": 5}]},
            "ratingsEntries": {"totalItems": 1, "items": [{"id": 999, "gender": {"id": 0},
                "team": {"id": 5, "label": "Club"}, "firstName": first, "lastName": last,
                "commonName": common_name or "", "birthdate": "01/02/2000 00:00", "position": {"shortLabel": "ST"},
                "overallRating": 70, "stats": {}}]}}}}
        html = ('<script id="__NEXT_DATA__" type="application/json">' + json.dumps(payload) + '</script>').encode()
        digest = hashlib.sha256(html).hexdigest()
        self.ea_raw = self.root / "data/raw/ea" / (digest + ".html")
        self.ea_raw.parent.mkdir(parents=True, exist_ok=True)
        self.ea_raw.write_bytes(html)
        self.ea_row = {"fifa_id": "999", "league": "GER1", "player": name, "dob": self.person["dob"],
            "source": "https://www.ea.com/games/ea-sports-fc/ratings/leagues-ratings/bundesliga/19?page=1",
            "source_sha256": digest, "snapshot_date": self.snapshot}
        if common_name is not None:
            self.ea_row["common_name"] = common_name
        self.ea_csv = self.root / "data/intermediate/ea-fc27.csv"
        self.write_ea_proof()

    def write_ea_proof(self, duplicate=False):
        write_csv(self.ea_csv, list(self.ea_row), [self.ea_row] * (2 if duplicate else 1))
        self.row["unassigned_fifa_evidence"] = {**self.ea_row, "ea_csv_sha256": sha256(self.ea_csv)}

    def test_bound_source_fifa_recovers_native_zero_without_assigning_it(self):
        self.bind_unassigned()
        original = copy.deepcopy(self.person)
        profiles, _ = self.load()
        self.assertEqual(self.recover(profiles[0], fifa_id="999"), ("REVIEWED_IDENTITY", [self.person]))
        self.assertEqual(match_profile(profiles[0], IdentityIndex(self.players)), ("REVIEWED_IDENTITY", self.person))
        self.assertEqual(self.person, original)
        self.assertEqual(self.person["fifa_id"], "0")

    def test_unbound_or_different_source_fifa_remains_a_conflict_for_native_zero(self):
        self.bind_unassigned()
        proof = self.row.pop("unassigned_fifa_evidence")
        profiles, _ = self.load()
        self.assertEqual(self.recover(profiles[0], fifa_id="999")[0], "CONFLICT")
        self.row["unassigned_fifa_evidence"] = proof
        profiles, _ = self.load()
        self.assertEqual(self.recover(profiles[0], fifa_id="998")[0], "CONFLICT")

    def test_source_fifa_assigned_elsewhere_cannot_be_recovered(self):
        self.bind_unassigned()
        profiles, _ = self.load()
        self.players.append({**self.person, "fm_id": "8", "fifa_id": "999", "name": "Another Person"})
        self.assertEqual(self.recover(profiles[0], fifa_id="999")[0], "CONFLICT")
        self.assertEqual(match_profile(profiles[0], IdentityIndex(self.players))[0], "CONFLICT")
        with self.assertRaises(ValueError): self.load()

    def test_ea_source_and_csv_byte_changes_reject_unassigned_recovery(self):
        self.bind_unassigned()
        original = self.ea_csv.read_bytes()
        self.ea_csv.write_bytes(original + b"\n")
        with self.assertRaises(ValueError): self.load()
        self.ea_csv.write_bytes(original)
        self.ea_raw.write_bytes(b"changed source")
        with self.assertRaises(ValueError): self.load()

    def test_changed_ea_identity_cannot_be_authorized_by_rehashing_csv(self):
        self.bind_unassigned()
        original = dict(self.ea_row)
        for change in ({"player": "Different Person"}, {"dob": "2001-01-02"},
                       {"fifa_id": "998"}, {"snapshot_date": "2026-09-09"}, {"league": "ENG1"}):
            with self.subTest(change=change):
                self.ea_row = {**original, **change}
                self.write_ea_proof()
                with self.assertRaises(ValueError): self.load()

    def test_duplicate_ea_id_and_unrelated_source_name_remain_held(self):
        self.bind_unassigned()
        self.write_ea_proof(duplicate=True)
        with self.assertRaises(ValueError): self.load()
        self.bind_unassigned(name="Unrelated Person")
        with self.assertRaises(ValueError): self.load()

    def test_unassigned_proof_never_replaces_existing_native_fifa(self):
        self.bind_unassigned()
        self.person["fifa_id"] = self.row["native_fifa_id"] = "123"
        with self.assertRaises(ValueError): self.load()

    def test_explicit_source_common_name_recovers_same_person_without_native_id_assignment(self):
        self.bind_unassigned(name="Expanded Player Name", common_name="Source Spelling")
        original = copy.deepcopy(self.person)
        profiles, _ = self.load()
        self.assertEqual(self.recover(profiles[0], fifa_id="999"), ("REVIEWED_IDENTITY", [self.person]))
        self.assertEqual(match_profile(profiles[0], IdentityIndex(self.players)), ("REVIEWED_IDENTITY", self.person))
        self.assertEqual(self.person, original)

    def test_common_name_requires_explicit_review_and_nonempty_source_value(self):
        self.bind_unassigned(name="Expanded Player Name", common_name="Source Spelling")
        del self.row["unassigned_fifa_evidence"]["common_name"]
        with self.assertRaises(ValueError): self.load()
        self.bind_unassigned(common_name="")
        with self.assertRaises(ValueError): self.load()

    def test_rehashed_csv_cannot_invent_common_name_or_remove_source_binding(self):
        self.bind_unassigned(name="Expanded Player Name", common_name="Unrelated Alias")
        self.ea_row["common_name"] = "Source Spelling"
        self.write_ea_proof()
        with self.assertRaises(ValueError): self.load()
        del self.ea_row["common_name"]
        self.write_ea_proof()
        self.row["unassigned_fifa_evidence"]["common_name"] = "Source Spelling"
        with self.assertRaises(ValueError): self.load()

    def test_common_name_review_cannot_override_global_fifa_or_natural_identity_conflicts(self):
        self.bind_unassigned(name="Expanded Player Name", common_name="Source Spelling")
        profiles, _ = self.load()
        self.players.append({**self.person, "fm_id": "8", "fifa_id": "999", "name": "Another Person"})
        with self.assertRaises(ValueError): self.load()
        self.assertEqual(self.recover(profiles[0], fifa_id="999")[0], "CONFLICT")
        self.players[-1].update(fifa_id="456", name="Source Spelling")
        with self.assertRaises(ValueError): self.load()
