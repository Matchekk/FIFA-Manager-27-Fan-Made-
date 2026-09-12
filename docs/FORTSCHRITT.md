# Aktueller Stand

Die Abgabe vor 15:00 Uhr steht in [ABGABE_1500.md](ABGABE_1500.md):
222 Mannschaften aller zwölf Zielligen erfasst; 3820 Anpassungen mit 948
Vereinswechseln im separaten Kandidaten. Der Inhaltsvergleich aller 266764
Spieler gegen den eingefrorenen Plan ist bestanden. Kein vollständiger,
spielgetesteter Overhaul und keine belegte Beschleunigung.

## Historischer Zwischenstand vor dieser Abgabe

# Stand vom 08.09.2026

Das Spiel läuft. Der Prozess wurde über seinen vollständigen Installationspfad
erkannt; der Fenstertitel lautet „Fussball Manager 2026 1.1.0“. Das Startwerkzeug
kann sich jetzt an ein laufendes Spiel anhängen und den Start über die
Auflösungsauswahl berücksichtigen.

## Kader und Datenbank

- England: 20 Premier-League-Vereine, 654 Einträge aus dem offiziellen FPL-Angebot.
- Deutschland: 18 Bundesliga-, 17 Zweitliga- und 20 Drittligamannschaften,
  1.430 DFB-Kadereinträge. Bielefelds DFB-Seiten liefern Serverfehler.
- Der deutsche Abgleich enthält 692 unveränderte Mannschaftszuordnungen,
  474 mögliche Zugänge, 119 mehrdeutige Fälle, 120 nicht gefundene Spieler
  und 25 weitere Identitätsprüfungen. 614 bisherige Einträge haben keine
  passende Beobachtung; daraus wird kein Abgang abgeleitet.
- Datenstand der Quellen: **DATABASE_SNAPSHOT_DATE=2026-09-08**.
- Leihstatus, Eigentümerverein, Rückkehrer und Vertragsänderungen müssen
  zusätzlich belegt werden. Widersprüche sind ausdrücklich markiert.
- Acht weitere Zielligen fehlen noch. Es gibt noch keine fertige Produktionsdatenbank.

Die zusammengeführten Dateien stehen unter `reports/TRANSFER_DIFF.csv`,
`reports/UNMATCHED_PLAYERS.csv`, `reports/AMBIGUOUS_MATCHES.csv` und
`reports/TRANSFER_COVERAGE.json`. Sie sind Prüfberichte, keine installierten Änderungen.

Der native FIFAM-Schreibtest arbeitet ausschließlich in einem separaten
Testordner. Nach erneutem Auslesen stimmen alle 266.764 projizierten
Spielerdatensätze in den geprüften Feldern überein, einschließlich Attributen,
Verträgen, Vereinszuordnung und Wechselbedingungen. Die Bibliothek nummeriert
interne Personen-IDs neu; deshalb erfolgt der Vergleich nach Inhalt.
Beziehungen, Wettbewerbsregeln, Personal, Historien und das Spielverhalten
sind damit noch nicht vollständig geprüft.

## Leistung und Stabilität

Eine 30-Sekunden-Beobachtung des laufenden Spiels ergab 114 Prozessmessungen.
Das ist noch kein kontrollierter Lade- oder Simulationstest und belegt keine
Beschleunigung. LAA ist bereits aktiviert.

Die Bildschirmaufnahme scheitert auf diesem Windows-10-System mit
`SetIsBorderRequired / E_NOINTERFACE`; der Textzugriff zeigt nur das Fenster
ohne bedienbare Elemente. Deshalb konnten keine sicheren automatisierten
Spielaktionen und Langzeitsimulationen durchgeführt werden.

39 automatisierte Tests, der native Build und die PowerShell-Syntaxprüfung
bestehen. Alle 943 zuvor erfassten relevanten Spiel-Dateien sind unverändert.
Spielerstärken, vollständige Transfers, echte Leistungsverbesserungen und
Langzeitkarrieren sind weiterhin offen. 3D- und XXL-Arbeiten wurden nicht begonnen.
