"""Create an honest deadline handoff from measured reports; no game installation."""
import datetime as dt
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from fm27.common import read_csv,write_csv,write_json
root=Path(__file__).resolve().parents[1]
reports=root/"reports"
current=reports/"local/current"
summary=json.loads((current/"RECONCILIATION.json").read_text(encoding="utf-8"))
rows=read_csv(current/"TRANSFER_DIFF.csv")
for r in rows:
    if r["classification"]=="CONFLICT":r["status"]="CONFLICT"
write_csv(reports/"TRANSFER_DIFF.csv",list(rows[0]),rows)
write_csv(reports/"UNMATCHED_PLAYERS.csv",list(rows[0]),(r for r in rows if not r["fm_id"]))
write_csv(reports/"AMBIGUOUS_MATCHES.csv",list(rows[0]),(r for r in rows if r["classification"] in {"CONFLICT","AMBIGUOUS","DUPLICATE"}))
events=read_csv(root/"data/intermediate/transfer-events.csv")
write_csv(reports/"TRANSFER_EVENTS.csv",list(events[0]),events)
ea=json.loads((reports/"local/EA_FETCH.json").read_text(encoding="utf-8"))
gate=reports/"local/CANDIDATE_VALIDATION.json"
validation=json.loads(gate.read_text(encoding="utf-8")) if gate.exists() else {"status":"PENDING","production_ready":False}
delivery={"DATABASE_SNAPSHOT_DATE":summary["DATABASE_SNAPSHOT_DATE"],"created_at":dt.datetime.now(dt.timezone.utc).isoformat(),
          "status":"TEST_CANDIDATE_NOT_COMPLETE_OVERHAUL","covered_competitions":len(summary["coverage"]),
          "covered_teams":sum(c["fetched"] for c in summary["coverage"].values()),"current_roster_records":len(rows),
          "transfer_event_rows":len(events),"ea_fc27_records":ea["records"],"staged_plan_rows":summary["staging_plan_rows"],
          "planned_club_changes":summary["staging_club_changes"],"statuses":dict(Counter(r["status"] for r in rows)),
          "validation":validation,"production_installed":False,"performance_improvement_measured":False,
          "open_work":["Missing players and complex loans","Outside-scope destination reconciliation for departures",
                       "Full 2026/27 competition and promotion/relegation integrity","Calibrated rating changes and native level validation",
                       "In-game/save validation and 1/3/5/10-year careers","Controlled non-3D benchmarks and measured optimization"]}
write_json(reports/"DELIVERY_1500.json",delivery)
write_json(reports/"TRANSFER_COVERAGE.json",{"DATABASE_SNAPSHOT_DATE":summary["DATABASE_SNAPSHOT_DATE"],
           "coverage":summary["coverage"],"source_failures":summary["source_failures"],
           "status":"12_LEAGUE_CAPTURE_COMPLETE_RECONCILIATION_INCOMPLETE","production_writes":0})
text=f'''# Abgabe zum 08.09.2026, 15:00 Uhr

**Ein geprüfter Entwicklungsstand, noch kein vollständig fertiger Overhaul.**

Quellenstand: **DATABASE_SNAPSHOT_DATE={delivery['DATABASE_SNAPSHOT_DATE']}**.
Erfasst: {delivery['covered_teams']} Mannschaften aus allen zwölf Zielligen,
{len(rows)} aktuelle Kadereinträge, {len(events)} Transferereignis-Zeilen
(einschließlich Gegenbuchungen und zukünftiger Leih-Rückkehrer) und
{ea['records']} FC27-Datensätze mit detaillierten Attributen und FIFA-IDs.

Der eingefrorene Testplan enthält {summary['staging_plan_rows']} eindeutig
zugeordnete Kader-/Vertrags-/Nummern-Einträge, darunter
{summary['staging_club_changes']} Vereinswechsel. Komplexe bestehende
Wechselbedingungen, Leihen, Quellenkonflikte und nicht eindeutig identifizierte
Spieler sind ausgespart. Nicht jeder erfasste Transfer wurde damit umgesetzt.

Validierungsstatus des nativen Kandidaten: **{validation['status']}**.
Ein erfolgreicher Inhaltsvergleich prüft die projizierten Spielerdaten gegen
genau den eingefrorenen Änderungsplan; er ersetzt keinen Spiel- oder Save-Test.

Die Spielinstallation wurde nicht mit dieser Testdatenbank überschrieben.
Der Kandidat liegt, sobald der native Lauf erfolgreich beendet ist, unter
`data/generated/candidate-20260908-1500/database`. Nur ein ausdrücklich
abgeschlossener Validierungsbericht unter `reports/local/CANDIDATE_VALIDATION.json`
bescheinigt den Inhaltsvergleich. Angefangene Ausgabeordner sind keine fertigen Builds.

## Noch offen

Leihen und fehlende Spieler, alle Abgänge zu externen Vereinen, vollständige
Auf-/Abstiegs- und Wettbewerbslogik für 2026/27, kalibrierte Spielerwerte,
Spiel-/Save-/Langzeittests und belegte Leistungsverbesserungen. LAA ist bereits
aktiv. Die Windows-10-Bildschirmaufnahme scheitert an E_NOINTERFACE; sichere
automatisierte Spielaktionen waren daher nicht möglich. Es wurden keine
Leistungsgewinne behauptet und keine 3D- oder XXL-Optimierungen entwickelt.

## Dateien

- `reports/TRANSFER_DIFF.csv`: aktueller Kaderabgleich mit Aktion und Prüfstatus.
- `reports/TRANSFER_EVENTS.csv`: bestätigte Saisonereignisse als Quellenevidenz.
- `reports/UNMATCHED_PLAYERS.csv` und `reports/AMBIGUOUS_MATCHES.csv`: offene Identitäten.
- `reports/DELIVERY_1500.json`: maschinenlesbarer Abgabestand.
- `dist/FM27CommunityToolkit-0.1.0.zip`: eigene Werkzeuge und Dokumentation, kein Spielpatch.

Da die Originalinstallation unverändert bleibt, ist zum Weiterspielen keine
Wiederherstellung nötig. Keine unvalidierte Kandidatendatenbank in die laufende
Installation kopieren.
'''
(root/"docs/ABGABE_1500.md").write_text(text,encoding="utf-8")
print(json.dumps({k:v for k,v in delivery.items() if k not in {'validation','open_work'}}))
