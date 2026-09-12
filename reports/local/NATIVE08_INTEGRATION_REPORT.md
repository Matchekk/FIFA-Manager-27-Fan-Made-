# Native08 — Historienintegration und Leihkorrektur

Status: **INTEGRATED_EDITOR_EXPORT_REQUIRED**.

Der neue Kandidat `data/generated/release-candidate/native08-integrated-20260912-01`
ist in `runtime/loan-test-20260912-08` integriert. Der vorherige Stand einschließlich
Master.dat liegt hashgeprüft unter
`reports/local/native08-20260912-evidence/before-combined-integration`.
Die alte diagnostische Master.dat wurde erst nach ihrer Sicherung entfernt;
der kombinierte Stand benötigt einen neuen Editor-Export.

## Änderungen und Prüfung

- Historienpaket 2025/26: zehn Länder, 20 Meister-/Hauptpokaleinträge,
  103 vorgesehene Felder und 37 veraltete Markierungen. Vollständige Spielarchive
  und spätere tschechische Verwaltungsentscheidungen sind nicht enthalten.
- 744 von 794 übernommenen aktuellen Leihen beginnen in der Runtime-Projektion
  am Karrierestart 01.07.2026; 50 bleiben unverändert. Die eingefrorenen Quellen
  behalten ihre tatsächlichen Daten. Rückkehrvereine, Leihenden, Vertragsdaten
  und ausdrücklich zukünftige Bedingungen werden nicht geändert.
- Moore und Amissah wurden im separaten Zwei-Spieler-Versuch als aktive Leihen
  erkannt; ihre korrekten Rückkehrvereine wurden vom Bediener bestätigt.
  Das ist keine Einzelprüfung aller 744 Fälle und kein vollständig kontrollierter
  Vergleich sämtlicher Karriere-Einstellungen.
- Exakter Bytevergleich aller 638 Datenbankdateien: außer den dokumentierten
  Leihstartdaten keine zusätzliche Abweichung vom validierten Historienpaket.
- Nativer Leser erfolgreich; 266.764 Spieler-/Ratingwerte unverändert.
  Serialisierungs- und Protected-Hashes ändern sich genau bei den 744 betroffenen
  Spielern, weil diese Hashes auch Leihbedingungen einschließen.
- Drei gezielte Unit-Tests mit sieben Fällen bestanden.

## Sicherheit und verbleibender Schritt

Alle 16 vorbestehenden Saves entsprechen wieder dem ursprünglichen Preflight.
Vier während der Tests veränderte Saves wurden zuvor als Belegkopien erhalten
und aus verifizierten Backups wiederhergestellt. Originalinstallation und
Runtime07 wurden bei dieser Integration nicht verändert; ihre vorhandene
Identitätsprüfung umfasst Manager.exe und Master.dat, keinen vollständigen
Installationsbaum. Temporäre gemeinsame Konfiguration wird beim finalen Cleanup
noch abgeglichen.

Der kombinierte Kandidat ist noch nicht Editor-exportiert oder als neue Karriere
geprüft. Bestehende Karrieren werden durch diesen Datenbankwechsel nicht repariert.
Native08 bleibt insgesamt PARTIAL: der separate Day1-Test wurde ausdrücklich
ausgelassen; die übrige Laufzeit-Evidenz wird nicht rückwirkend auf den neuen
Kandidaten übertragen.
