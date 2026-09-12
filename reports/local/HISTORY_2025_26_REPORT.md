# Historie 2025/26 — Paketabschluss

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
