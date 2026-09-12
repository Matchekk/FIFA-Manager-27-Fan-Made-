"""Compare native staff/competition serialization and normalized person relations."""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from fm27.common import read_csv,write_json,sha256

p=argparse.ArgumentParser()
p.add_argument("--expected",type=Path,required=True)
p.add_argument("--actual",type=Path,required=True)
p.add_argument("--output",type=Path,required=True)
p.add_argument("--mutation-scope",action="store_true",help="Compare untouched world entities before writing; bind graph nodes to unchanged native person IDs")
a=p.parse_args()
expected_meta=json.loads((a.expected/"NATIVE_EXTENDED_SEMANTICS.json").read_text(encoding="utf-8"))
actual_meta=json.loads((a.actual/"NATIVE_EXTENDED_SEMANTICS.json").read_text(encoding="utf-8"))
node_maps={}
player_hashes={}
if a.mutation_scope:
    identities=[]
    for folder in (a.expected,a.actual):
        people=read_csv(folder/"native_player_semantics.csv")
        identities.append({p["fm_id"]:(p["fifa_id"],p["dob"],p["name"]) for p in people})
        nodes={p["serialized_sha256"]+"@"+p["club_id"]:p["fm_id"] for p in people}
        if len(nodes)!=len(people) or len(identities[-1])!=len(people):
            raise ValueError("World mutation graph identity is not unique")
        node_maps[folder]=nodes
        player_hashes[str(folder)]=sha256(folder/"native_player_semantics.csv")
    if identities[0]!=identities[1]:
        raise ValueError("Mutation-scope comparison requires pre-write native identity IDs, not renumbered reread IDs")
checks={}
for key,filename,fields in [
    ("staffs","native_staff_semantics.csv",("dob","name","club_id","serialized_sha256")),
    ("competitions","native_competition_semantics.csv",("competition_id","serialized_sha256")),
    ("relation_rows","native_player_relations.csv",("relation","from_key","to_key"))]:
    def records(folder):
        rows=read_csv(folder/filename)
        if a.mutation_scope and key=="relation_rows":
            rows=[{**r,"from_key":node_maps[folder][r["from_key"]],"to_key":node_maps[folder][r["to_key"]]} for r in rows]
        return Counter(tuple(row[f] for f in fields) for row in rows)
    expected,actual=records(a.expected),records(a.actual)
    bound=expected.total()==expected_meta[key] and actual.total()==actual_meta[key]
    if key!="relation_rows":
        bound=bound and bool(expected)
    checks[key]={"status":"PASS" if bound and expected==actual else "FAIL", "expected":expected.total(), "actual":actual.total(),
                 "unexpected_missing":(expected-actual).total(), "unexpected_added":(actual-expected).total(),
                 "examples_expected":list((expected-actual).items())[:3], "examples_actual":list((actual-expected).items())[:3],
                 "expected_sha256":sha256(a.expected/filename), "actual_sha256":sha256(a.actual/filename)}
graph_safe=all(meta["relation_errors"]==0 and meta["player_key_collisions"]==0 for meta in (expected_meta,actual_meta))
passed=graph_safe and all(check["status"]=="PASS" for check in checks.values())
report={"status":"PASS" if passed else "FAIL", "comparison":"UNCHANGED_WORLD_MUTATION_SCOPE" if a.mutation_scope else "NATIVE_REREAD", "checks":checks, "graph_identity_unique_and_valid":graph_safe,
        "player_identity_hashes":player_hashes,
        "expected_metadata_sha256":sha256(a.expected/"NATIVE_EXTENDED_SEMANTICS.json"),
        "actual_metadata_sha256":sha256(a.actual/"NATIVE_EXTENDED_SEMANTICS.json"),
        "limitations":"Extends native comparison to staff, competitions and brother/cousin relations. Does not prove club/country/rules/stadium completeness, game careers or saves.",
        "release_ready":False}
write_json(a.output,report)
print(json.dumps(report))
sys.exit(not passed)
