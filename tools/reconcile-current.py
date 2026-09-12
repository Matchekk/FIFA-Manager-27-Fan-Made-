"""Reconcile current roster + transfer event evidence into guarded staging plans."""
import datetime as dt
import argparse
import json
import sys
from collections import Counter,defaultdict
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from fm27.common import read_csv,write_csv,write_json,sha256
from fm27.matching import IdentityIndex,recover_profile_identity
from fm27.squad_compare import FIELDS
from fm27.transfer_timeline import incoming_kind
from fm27.contracts import current_contract,retain_existing_end
from fm27.player_identities import load_player_identities, verified_profile
from fm27.historical_transfers import load_historical_transfers
from fm27.reviewed_rosters import load_primary_roster_reviews, reviewed_primary_target

root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument("--baseline",type=Path,default=root/"data/intermediate/installed-teams")
args=parser.parse_args()
args.baseline=args.baseline.resolve()
if (args.baseline/"NATIVE_ID_BINDING.json").exists():
    binding=json.loads((args.baseline/"NATIVE_ID_BINDING.json").read_text(encoding="utf-8"))
    if (sha256(args.baseline/"players.csv")!=binding["bound_players_sha256"] or
        sha256(Path(binding["native"]))!=binding["native_sha256"] or
        sha256(Path(binding["baseline_players"]))!=binding["baseline_players_sha256"]):
        raise ValueError("Native baseline identity binding evidence changed")
players=read_csv(args.baseline/"players.csv")
clubs=read_csv(args.baseline/"clubs.csv")
ea=read_csv(root/"data/intermediate/ea-fc27.csv")
roster=read_csv(root/"data/intermediate/tm-squads.csv")
events=read_csv(root/"data/intermediate/transfer-events.csv")
metadata=json.loads((root/"reports/local/TM_SQUADS_FETCH.json").read_text(encoding="utf-8"))
snapshot=metadata["DATABASE_SNAPSHOT_DATE"]
aliases=json.loads((root/"config/tm-club-aliases.json").read_text(encoding="utf-8"))
fm_index=IdentityIndex(players)
ea_index=IdentityIndex([{**p,"name":p["player"]} for p in ea])
official_clubs=defaultdict(set)
club_name_ids={c["club"]:c["club_id"] for c in clubs}
official_observations=read_csv(root/"reports/local/germany/TRANSFER_DIFF.csv")
for observed in official_observations:
    if observed.get("fm_id") and observed.get("source_status")=="CONFIRMED" and observed["classification"]!="AMBIGUOUS":
        destination=club_name_ids.get(observed["new_club"])
        if destination:official_clubs[observed["fm_id"]].add(destination)
for folder,records in (("ea",ea),("transfermarkt",roster+events)):
    for digest in {r["source_sha256"] for r in records}:
        if sha256(root/"data/raw"/folder/(digest+".html"))!=digest:
            raise ValueError("Source hash mismatch")
if any(r["snapshot_date"]!=snapshot for r in roster+ea+events):
    raise ValueError("Mixed snapshot dates")
by_tm=defaultdict(list)
profile_file=root/"data/intermediate/departure-profiles.csv"
profile_rows=read_csv(profile_file) if profile_file.exists() else []
if len({p["player_tm_id"] for p in profile_rows}) != len(profile_rows):
    raise ValueError("Duplicate current profile identities")
roster_ids={r["player_tm_id"] for r in roster}
profile_rows=[verified_profile(root,p,snapshot) if p["player_tm_id"] in roster_ids else p for p in profile_rows]
profile_rows,identity_evidence=load_player_identities(root,snapshot,profile_rows,players,args.baseline/"players.csv",aliases)
historical_aliases=dict(aliases)
external_aliases=root/"data/overrides/external_clubs.csv"
if external_aliases.exists():
    for alias in read_csv(external_aliases):
        if alias["club_tm_id"] in historical_aliases:
            raise ValueError("External club alias shadows a current club")
        historical_aliases[alias["club_tm_id"]]=alias
historical_events,historical_evidence=load_historical_transfers(root,snapshot,profile_rows,players,historical_aliases,events,
    baseline_path=args.baseline/"players.csv")
events+=historical_events
profiles={p["player_tm_id"]:p for p in profile_rows}
primary_reviews,primary_review_evidence=load_primary_roster_reviews(root,snapshot,players,
    args.baseline/"players.csv",roster,profile_rows,official_observations,clubs)
for e in events:by_tm[e["player_tm_id"]].append(e)
club_observations=defaultdict(set)
for r in roster:
    if r["club_tm_id"] in aliases:
        club_observations[r["player_tm_id"]].add(aliases[r["club_tm_id"]]["club_id"])
rows,plans,unmatched,ambiguous=[],[],[],[]
seen_fm=defaultdict(list)
for r in roster:
    target=aliases[r["club_tm_id"]]
    em,ec=ea_index.match(r)
    evidence={**r,"fifa_id":ec[0]["fifa_id"]} if em=="DOB_NAME" else r
    profile=profiles.get(r["player_tm_id"],{})
    contract=current_contract(r,profile,snapshot)
    joined,until=contract["joined"],contract["contract_until"]
    method,candidates=recover_profile_identity(fm_index,evidence,profile,snapshot,r["club_tm_id"],target["club_id"])
    if em in {"AMBIGUOUS","CONFLICT"}:
        method,candidates="AMBIGUOUS",[]
    p=candidates[0] if method in {"FIFA_ID","DOB_NAME","DOB_NAME_UNASSIGNED_FIFA","PROFILE_DOB_NAME","PROFILE_FULL_NAME","REVIEWED_IDENTITY"} else {}
    source_contract_until=until
    if p:
        contract=retain_existing_end(contract,p,profile,snapshot)
        joined,until=contract["joined"],contract["contract_until"]
    row={"league":r["league"],"club":r["club"],"player":r["player"],"dob":r["dob"],
         "fifa_id":p.get("fifa_id",ec[0]["fifa_id"] if em=="DOB_NAME" else ""),"fm_id":p.get("fm_id",""),
         "old_club":p.get("club",""),"new_club":target["fm_name"],"transfer_type":"UNVERIFIED",
         "contract_until":until,"shirt_number":r["shirt_number"],"source":r["source"],
         "source_date":snapshot,"confidence":method,"database_action":"REVIEW_REQUIRED",
         "classification":method,"status":"REVIEW_REQUIRED","reason":"Identity unresolved",
         "player_tm_id":r["player_tm_id"],"club_tm_id":r["club_tm_id"],"source_sha256":r["source_sha256"],
         "old_club_id":p.get("club_id",""),"new_club_id":target["club_id"],"team_type":target["team_type"],
         "joined":joined,"change_notes":r["change_notes"],
         "source_fifa_id":evidence.get("fifa_id",""),
         "profile_source":profile.get("source",""), "profile_sha256":profile.get("source_sha256",""),
         "contract_evidence":contract["status"],"source_contract_until":source_contract_until}
    if not p:
        unmatched.append(row)
        if method in {"CONFLICT","AMBIGUOUS"}:
            row["status"]="CONFLICT" if method=="CONFLICT" else "REVIEW_REQUIRED"
            ambiguous.append(row)
    else:
        same=p["club_id"]==target["club_id"]
        row.update(classification="UNCHANGED" if same else "TRANSFER_IN",reason="Roster identity resolved; checking ownership evidence")
        notes=json.loads(r["change_notes"])
        incoming=[e for e in by_tm[r["player_tm_id"]] if e["new_club_tm_id"]==r["club_tm_id"]
                  and (not e["explicit_event_date"] or e["explicit_event_date"]<=snapshot)]
        kind=incoming_kind(incoming,r["club_tm_id"],snapshot,joined)
        row["transfer_type"]=kind
        conflict=len(club_observations[r["player_tm_id"]])>1
        loan_note=any(("Leihe" in n or "Leihgebühr" in n) and "Rückkehr" not in n for n in notes)
        future_note=any(d>snapshot for n in notes for d in
                        [dt.datetime.strptime(v,"%d.%m.%Y").date().isoformat() for v in __import__('re').findall(r"\d{2}\.\d{2}\.\d{4}",n)])
        contract_valid=until and until>=snapshot
        dated=joined and joined<=snapshot
        if (official_clubs.get(p["fm_id"]) and target["club_id"] not in official_clubs[p["fm_id"]]
                and not reviewed_primary_target(row,primary_reviews)):
            row.update(status="CONFLICT",classification="AMBIGUOUS",reason="DFB roster contradicts current Transfermarkt affiliation")
            ambiguous.append(row)
        elif conflict:
            row.update(status="CONFLICT",classification="AMBIGUOUS",reason="Multiple current roster owner clubs")
            ambiguous.append(row)
        elif not p["fm_id"]:
            row["reason"]="Free agent has no persisted ID; native identity mapping required"
        elif contract["status"]=="CONFLICT":
            row.update(status="CONFLICT",reason="Current roster and profile contract evidence disagree")
        elif kind=="REVIEW_REQUIRED":
            row["reason"]="Conflicting or undated acquisition types require timeline review"
        elif kind=="LOAN" or loan_note or contract["status"]=="LOAN":
            row.update(classification="LOAN_IN",reason="Loan: parent ownership and dates require native loan plan")
        elif future_note:
            row["reason"]="Future roster change annotation requires timeline review"
        elif not contract_valid or not dated:
            row["reason"]="Missing/expired contract or unverified effective date"
        elif not same and kind not in {"PERMANENT","FREE_TRANSFER","LOAN_RETURN"}:
            row["reason"]="Changed club without confirmed matching transfer event"
        elif any(c[0] in (3,4,5,6,7,8,9,10) for c in json.loads(p["starting_conditions"])) or p["contract_loan_flag"]=="True":
            row["reason"]="Installed future conditions need typed native review"
        else:
            row.update(status="CONFIRMED",database_action="STAGE_CURRENT_SQUAD",reason="Unique identity, dated current roster and valid contract chronology; transfer event required for club change")
            if contract.get("native_until_preserved"):
                row["reason"]+="; existing native contract end retained because current source end is missing"
            # Plan is numeric/tabular, never shell code. No production install is triggered.
            plans.append({"fm_id":p["fm_id"],"fifa_id":p["fifa_id"],"dob":p["dob"],
                          "old_club_id":p["club_id"],"new_club_id":target["club_id"],
                          "joined":joined,"contract_until":until,
                          "shirt_number":r["shirt_number"] if r["shirt_number"].isdigit() and int(r["shirt_number"])<=99 else p["shirt_number"],
                          "team_type":target["team_type"],"status":"CONFIRMED","source":profile["source"] if contract["used_profile"] else r["source"],
                          "source_sha256":profile["source_sha256"] if contract["used_profile"] else r["source_sha256"],"snapshot_date":snapshot})
        seen_fm[p["fm_id"]].append(row)
    rows.append(row)
# Distinct TM people must never collapse into the same FM person.
collisions={k for k,v in seen_fm.items() if k and len({r["player_tm_id"] for r in v})>1}
for ident in collisions:
    for row in seen_fm[ident]:
        row.update(status="CONFLICT",classification="DUPLICATE",database_action="REVIEW_REQUIRED",reason="Multiple TM identities matched one FM person")
        ambiguous.append(row)
plans=[p for p in plans if p["fm_id"] not in collisions]
# Same owner can list a player in first and reserve squads: prefer explicit first-team evidence.
dedup={}
for p in plans:
    if p["fm_id"] not in dedup or p["team_type"]=="FIRST":dedup[p["fm_id"]]=p
plans=list(dedup.values())
out=root/"reports/local/current"
fields=FIELDS+[k for k in rows[0] if k not in FIELDS]
write_csv(out/"TRANSFER_DIFF.csv",fields,rows)
write_csv(out/"UNMATCHED_PLAYERS.csv",fields,unmatched)
write_csv(out/"AMBIGUOUS_MATCHES.csv",fields,ambiguous)
plan_fields=["fm_id","fifa_id","dob","old_club_id","new_club_id","joined","contract_until",
             "shirt_number","team_type","status","source","source_sha256","snapshot_date"]
write_csv(root/"data/intermediate/current-squad-plan.csv",plan_fields,plans)
write_json(out/"RECONCILIATION.json",{"DATABASE_SNAPSHOT_DATE":snapshot,"coverage":metadata["coverage"],
    "source_failures":metadata["failures"],"rows":len(rows),"classifications":dict(Counter(r["classification"] for r in rows)),
    "statuses":dict(Counter(r["status"] for r in rows)),"staging_plan_rows":len(plans),
    "staging_club_changes":sum(p["old_club_id"]!=p["new_club_id"] for p in plans),
    "baseline_players":str((args.baseline/"players.csv").resolve()),"baseline_players_sha256":sha256(args.baseline/"players.csv"),
    "reviewed_player_identities":identity_evidence,
    "reviewed_historical_transfers":historical_evidence,
    "reviewed_primary_rosters":primary_review_evidence,
    "external_aliases_sha256":sha256(external_aliases) if external_aliases.exists() else "",
    "profile_csv_sha256":sha256(profile_file),
    "code_sha256":{str(p.relative_to(root)):sha256(p) for p in [Path(__file__),root/"src/fm27/reviewed_rosters.py",root/"src/fm27/historical_transfers.py",root/"src/fm27/matching.py",root/"src/fm27/player_identities.py",root/"src/fm27/ea.py",root/"src/fm27/transfermarkt.py",root/"src/fm27/contracts.py",root/"src/fm27/transfer_timeline.py"]},
    "production_writes":0,"limitations":"Current squads only; outside-league departures, loans, missing people and conflicts remain review work. Staging is not game validation."})
print(json.dumps({"rows":len(rows),"staging_plan":len(plans),"statuses":dict(Counter(r['status'] for r in rows))}))
