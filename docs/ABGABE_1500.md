# Abgabe zum 08.09.2026, 15:00 Uhr

**Ein geprüfter Entwicklungsstand, noch kein vollständig fertiger Overhaul.**

Quellenstand: **DATABASE_SNAPSHOT_DATE=2026-09-08**.
Erfasst: 222 Mannschaften aus allen zwölf Zielligen,
6266 aktuelle Kadereinträge, 7178 Transferereignis-Zeilen
(einschließlich Gegenbuchungen und zukünftiger Leih-Rückkehrer) und
5980 FC27-Datensätze mit detaillierten Attributen und FIFA-IDs.

Der eingefrorene Testplan enthält 3820 eindeutig
zugeordnete Kader-/Vertrags-/Nummern-Einträge, darunter
948 Vereinswechsel. Komplexe bestehende
Wechselbedingungen, Leihen, Quellenkonflikte und nicht eindeutig identifizierte
Spieler sind ausgespart. Nicht jeder erfasste Transfer wurde damit umgesetzt.

Validierungsstatus des nativen Kandidaten: **PROJECTED_STAGE_MATCHES_PLAN**.
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
