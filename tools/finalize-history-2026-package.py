"""Bind native reread results, reproducible inputs and a compact history handoff."""
from pathlib import Path
import csv,hashlib,json,shutil
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/generated/history-20260912-03'
WORK=ROOT/'data/generated/history-20260912-01'
READ=ROOT/'data/generated/history-20260912-03-reread'
BASE=ROOT/'data/generated/native-reread-increment-20260909-07'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    checks={}
    for name in ['native_players.csv','native_ratings.csv','native_player_semantics.csv']:
        assert (READ/name).is_file(),f'Missing native reread {name}'
        # CSV record equality also permits harmless output newline differences.
        with (READ/name).open(encoding='utf-8-sig',newline='') as f:actual=list(csv.reader(f))
        with (BASE/name).open(encoding='utf-8-sig',newline='') as f:baseline=list(csv.reader(f))
        assert actual==baseline,f'Preservation failure: {name}'
        checks[name]={'status':'PASS','data_rows':len(actual)-1,'sha256':sha(READ/name)}
    field=json.loads((OUT/'FIELD_VALIDATION.json').read_text())
    assert field['status']=='PASS_INDEPENDENT_FIELD_REREAD'
    provenance=OUT/'provenance';provenance.mkdir(exist_ok=True)
    for name in ['HISTORY_DRAFT.json','CURRENT_NATIVE_HISTORY.json','FLAG_RECONCILIATION.json','SOURCE_RESOLUTIONS.json']:
        shutil.copyfile(WORK/name,provenance/name)
    shutil.copytree(WORK/'preview',provenance/'preview',dirs_exist_ok=True)
    package=json.loads((OUT/'PACKAGE.json').read_text())
    package['status']='PASS_OFFLINE_HISTORY_PACKAGE_NATIVE_REREAD_AND_PRESERVATION'
    package['native_preservation']=checks
    package['field_validation']=field
    package['installed']=False
    package['editor_export']='NOT_EXPORTED'
    package['note']='Complete for the declared title/cup/movement-marker scope; not a complete match-results archive or release candidate.'
    (OUT/'PACKAGE.json').write_text(json.dumps(package,indent=2)+'\n',encoding='utf-8')
    (OUT/'README.md').write_text('''# Historie 2025/26 — geprüftes Offline-Paket

Enthalten sind Meister der zehn abgedeckten höchsten Ligen, deren nationale
Pokalsieger und Finalisten, passende Vereinstitel sowie Auf-/Abstiegsmarkierungen
im Projektumfang einschließlich der deutschen zweiten und dritten Liga.

- Vollständige separate Datenbank: `database/` (638 Dateien, zehn geändert).
- Zusätzliche Historien-Dateien: `overlay/fmdata/historic/` (20 neue Wettbewerbszeilen).
- 103 vorgesehene Felder und 37 Entfernungen veralteter Markierungen unabhängig geprüft.
- Spieler, Verträge, Transfers und Ratings gegenüber Native07 unverändert.
- Quellen, Feldvergleich und exakte Patches: `provenance/`.

Die Dateien sind noch nicht in eine Runtime installiert oder durch den Editor
exportiert. Die komplette Datenbank basiert auf Native07 und darf nicht über die
laufende Leih-Testvariante kopiert werden: deren zwei Diagnoseänderungen sind hier
absichtlich nicht enthalten. Bestehende Karrieresaves wurden nicht bearbeitet.

Nicht enthalten: vollständige Ergebnisse aller Ligaspiele, Super-/Ligapokale und
kontinentale Historie. Artis/Karviná bleibt als spätere administrative Entscheidung
separat dokumentiert; die abgeschlossene Saison wird nicht rückwirkend geändert.
Die 1860/Havelse-Historienmarkierung korrigiert keine aktuelle Ligazusammensetzung.
''',encoding='utf-8')
    report={'status':package['status'],'package':str(OUT),'native_preservation':checks,
            'fields':field,'countries':10,'winner_records_added':20,'installed':False,
            'excluded':package['exclusions'],'main_native08_gate':'Not superseded; loan experiment remains separate'}
    (ROOT/'reports/local/HISTORY_2025_26_COMPLETION.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    (ROOT/'reports/local/HISTORY_2025_26_REPORT.md').write_text('''# Historie 2025/26 — Paketabschluss

Status: **PASS_OFFLINE_HISTORY_PACKAGE_NATIVE_REREAD_AND_PRESERVATION**.

Paket: `data/generated/history-20260912-03/`.
Die separate Datenbank umfasst alle 638 Ausgangsdateien; zehn Länderdateien sind
gezielt geändert. Zehn zusätzliche Historien-Dateien enthalten 20 neue Meister-
und Hauptpokaleinträge. Die zehn Länder entsprechen dem bestehenden Projektumfang;
bei den Auf-/Abstiegsmarkierungen sind auch GER2 und GER3 berücksichtigt.

## Prüfung

- 103 vorgesehene Felder und 37 veraltete Markierungen unabhängig nachgelesen.
- Nativer Datenbankleser erfolgreich; Spielerprojektion, vollständige
  Spielerserialisierung und Ratingprojektion entsprechen Native07.
- Sämtliche Spieler-/Mitarbeiterblöcke bytegleich; alle nicht vorgesehenen
  Datenbankdateien unverändert. Historien-Overlays lassen sich durch Entfernen
  ausschließlich der neuen Zeilen exakt auf die Ausgangsdateien zurückführen.
- Keine Änderung an Runtime07, der Leih-Testkopie, Saves oder Originalinstallation.

## Inhaltliche Abgrenzung

Das Paket enthält Titel, Pokalfinalisten, Vereinstitel und die beschriebenen
Vorjahresmarkierungen. Es ist kein vollständiges Archiv aller einzelnen Ligaspiele,
Super-/Ligapokale oder kontinentalen Wettbewerbe. Es ersetzt auch keine Korrektur
der aktuellen Ligazusammensetzung. Ein Editor-Export und eine sichtbare Prüfung
der Historienansichten wurden noch nicht ausgeführt.

Artis/Karviná werden nicht rückwirkend als sportliche Ereignisse der abgeschlossenen
Saison eingetragen. Der spätere administrative Vorgang bleibt separat dokumentiert.
1860/Havelse ist als administrative Veränderung gekennzeichnet; die bestehende
GER3-Mitgliedschaft im Ausgangskandidaten bleibt ein eigener Integrationspunkt.

Quellenauflösung: `data/generated/history-20260912-03/provenance/SOURCE_RESOLUTIONS.json`.
Der erste Paketentwurf 02 wurde nicht freigegeben: Die unabhängige Prüfung fand
einen Feldnamenfehler im Inspector. Paket 03 enthält die Korrektur und wurde erneut
geprüft. Nur Paket 03 ist der abgeschlossene Historienstand.

Die Native08-Leihdiagnose wird durch dieses Historienpaket nicht abgeschlossen.
Vor einer gemeinsamen Kandidatenfreigabe müssen beide Änderungen sauber kombiniert
und im isolierten Editor exportiert werden; vorhandene Saves bleiben erhalten.
''',encoding='utf-8')
    print(json.dumps({'status':report['status'],'player_rows':checks['native_players.csv']['data_rows'],'rating_rows':checks['native_ratings.csv']['data_rows']}))
if __name__=='__main__':main()
