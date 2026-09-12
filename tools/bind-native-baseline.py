"""Create a new projected baseline with native-read IDs for unique free agents."""
import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fm27.common import read_csv, write_csv, write_json, sha256
from fm27.native_identity import bind_native_free_agent_ids

p = argparse.ArgumentParser()
p.add_argument("--baseline",type=Path,required=True)
p.add_argument("--native",type=Path,required=True)
p.add_argument("--output",type=Path,required=True)
a=p.parse_args()
if a.output.exists():
    raise ValueError("Bound baseline output must be new")
players=read_csv(a.baseline/"players.csv")
bound=bind_native_free_agent_ids(players,read_csv(a.native))
a.output.mkdir(parents=True)
for path in a.baseline.glob("*.csv"):
    if path.name != "players.csv":
        shutil.copy2(path,a.output/path.name)
write_csv(a.output/"players.csv",list(players[0]),players)
report={"status":"NATIVE_BASELINE_IDS_BOUND", "players":len(players), "free_agents_bound":len(bound),
        "unbound_players":sum(not p["fm_id"] for p in players), "baseline_players":str((a.baseline/"players.csv").resolve()),
        "baseline_players_sha256":sha256(a.baseline/"players.csv"),"native":str(a.native.resolve()),
        "native_sha256":sha256(a.native),"bound_players_sha256":sha256(a.output/"players.csv"),
        "limitations":"IDs are valid only for this unchanged native input; persisted country IDs are checked, clubless matches require exact FIFA/DOB/name uniqueness."}
write_csv(a.output/"NATIVE_FREE_AGENT_IDS.csv",["fm_id","fifa_id","dob","name","source_file","source_line"],bound)
write_json(a.output/"NATIVE_ID_BINDING.json",report)
print(json.dumps(report))
