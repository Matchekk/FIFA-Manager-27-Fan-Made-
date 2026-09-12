"""Prepare guarded old-loan resolutions; this does not change a database."""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from fm27.common import read_csv,write_csv,write_json,sha256
from fm27.expired_loans import plan_expired_loans
from fm27.transfermarkt import parse_profile
from fm27.transfer_timeline import canonical_events

root=Path(__file__).resolve().parents[1]
baseline=root/"data/intermediate/native-bound-baseline"
binding=json.loads((baseline/"NATIVE_ID_BINDING.json").read_text())
meta=json.loads((root/"reports/local/current/RECONCILIATION.json").read_text())
snapshot=meta["DATABASE_SNAPSHOT_DATE"]
if sha256(baseline/"players.csv")!=binding["bound_players_sha256"] or meta["baseline_players_sha256"]!=binding["bound_players_sha256"]:
    raise ValueError("Current reconciliation and native-bound baseline disagree")
current=read_csv(root/"reports/local/current/TRANSFER_DIFF.csv")
eligible={r["player_tm_id"] for r in current if r["status"]=="REVIEW_REQUIRED" and r["reason"]=="Installed future conditions need typed native review"}
profiles=[p for p in read_csv(root/"data/intermediate/departure-profiles.csv") if p["player_tm_id"] in eligible]
events=read_csv(root/"data/intermediate/transfer-events.csv")
for digest in {r["source_sha256"] for r in profiles+events}:
    if sha256(root/"data/raw/transfermarkt"/(digest+".html"))!=digest:
        raise ValueError("Expired-loan source hash mismatch")
profiles=[{**p,**parse_profile((root/"data/raw/transfermarkt"/(p["source_sha256"]+".html")).read_text(encoding="utf-8-sig"),p["player_tm_id"])} for p in profiles]
aliases=json.loads((root/"config/tm-club-aliases.json").read_text(encoding="utf-8"))
for row in read_csv(root/"data/overrides/external_clubs.csv"):
    if row["club_tm_id"] in aliases or not all(row[k] for k in ("reason","source","date","author")):
        raise ValueError("Invalid external club alias")
    aliases[row["club_tm_id"]]=row
rows,plans=plan_expired_loans(read_csv(baseline/"players.csv"),read_csv(baseline/"clubs.csv"),current,
                            profiles,canonical_events(events,snapshot),aliases,snapshot)
fields=["fm_id","fifa_id","dob","old_club_id","new_club_id","joined","contract_until","shirt_number","team_type",
        "status","source","source_sha256","snapshot_date","loan_owner_club_id","loan_end","action",
        "previous_loan_owner_club_id","previous_loan_start","previous_loan_end","previous_loan_buy_option"]
write_csv(root/"data/intermediate/expired-loan-plan.csv",fields,plans)
write_csv(root/"reports/EXPIRED_LOAN_RECONCILIATION.csv",list(rows[0]),rows)
report={"snapshot_date":snapshot,"plans":len(plans),"cases":len(rows),"profiles":len(profiles),
        "statuses":dict(Counter(r["status"] for r in rows)),"reasons":dict(Counter(r["reason"] for r in rows)),
        "status":"SOURCE_PLAN_REQUIRES_NATIVE_CANDIDATE_VALIDATION",
        "plan_sha256":sha256(root/"data/intermediate/expired-loan-plan.csv"),
        "current_report_sha256":sha256(root/"reports/local/current/TRANSFER_DIFF.csv"),
        "baseline_sha256":binding["bound_players_sha256"],
        "profile_sources":[{k:p[k] for k in ("player_tm_id","source","source_sha256")} for p in profiles],"release_ready":False}
write_json(root/"reports/local/EXPIRED_LOAN_RECONCILIATION.json",report)
print(json.dumps({k:v for k,v in report.items() if k!="profile_sources"}))
