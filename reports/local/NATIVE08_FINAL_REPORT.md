# Native08 — Abschlussbericht, 12.09.2026

**Ergebnis: PARTIAL, abgegrenzter Meilenstein abgeschlossen.** Die Native07-Karriere
enthält nachweislich die geänderten Daten, läuft durch die erste Saison und lässt
sich nach dem Saisonwechsel wieder laden. Dabei wurde ein konkreter Fehler bei
übernommenen Leihen gefunden. Eine Korrektur wurde an zwei Spielern erfolgreich
beobachtet, auf die betroffenen übernommenen Leihen angewandt und zusammen mit
dem Historienpaket in einer separaten Test-Runtime exportiert.

Eine uneingeschränkte Gesamtfreigabe erfolgt nicht: Der separate Day1-Test wurde
auf Benutzerwunsch ausgelassen; die abschließende kombinierte Fassung wurde noch
nicht in einer neuen Karriere geprüft. Kein Nachweis für mehrjährige Stabilität.

## Laufzeitnachweise

| Prüfung | Ergebnis | Grundlage / Grenze |
|---|---|---|
| Native07-Daten in echter Karriere | PASS | Jovane Cabral, DOB 14.06.1998, Grêmio, Nummer 77, Vertragsende 30.06.2027 direkt sichtbar; eindeutig gegenüber Estrela/11/2026 |
| Day1 | PARTIAL | Separater 02.07.-Checkpoint ausdrücklich ausgelassen |
| Day7 | PASS | Lauf bis 11.07.2026, Bedienbarkeit und Save/Reload vom Bediener bestätigt |
| Day30 | PASS | Angeforderter August-Checkpoint und Save/Reload bestätigt; keine separate Bildschirmaufnahme jeder Unterfunktion |
| Vor Saisonwechsel speichern | PASS | 30.06.2027, Marek Wrona, 1. FC Köln; Save gesichert und gehasht |
| Saisonwechsel 2027 | PARTIAL | Datumswechsel und Bedienbarkeit erfolgreich, ursprüngliche Leihabweichung verhindert uneingeschränkten Struktur-PASS |
| Nach Saisonwechsel Save/Reload | PASS | Ursprüngliche Karriere am 01.07.2027 laut Bediener richtig geladen; Datei unabhängig gesichert |
| Wettbewerbe | PARTIAL | Bundesliga mit 18 Vereinen, Champions-League-Tabelle und Qualifikationspaarungen sichtbar; keine vollständige Mitgliedschaftsprüfung oder weitere nationale Liga dokumentiert |
| Bestehende Saves | PASS | Alle 16 ursprünglichen Dateien wieder identisch zum Preflight |
| Originalinstallation / Runtime07 | PASS im Prüfumfang | Manager.exe und Master.dat hashgleich; kein vollständiger Installationsbaum-Audit |

Die Nachweise bestehen aus Bedienerrückmeldungen, bereitgestellten Screenshots
und unabhängigen Datei-/Hashprüfungen. Automatische Bildschirmaufnahme wurde
wegen des bekannten Capture-Fehlers nicht wiederholt. Das Gate-JSON enthält
die einzelnen Belegpfade und Abweichungen.

## Leihkorrektur

Im ursprünglichen Lauf blieben Mikey Moore und Samuel Amissah bei den Leihvereinen.
Noah Darvich kehrte dagegen nachweislich von Elversberg nach Stuttgart zurück;
ein allgemeiner Ausfall aller Leih-Rückkehrvorgänge ist damit widerlegt.

Ein separater Versuch änderte nur den Beginn der beiden aktuellen Leihbedingungen
auf den Karrierestart 01.07.2026. Moore wurde anschließend ausdrücklich als Leihe
von Tottenham bis 30.06.2027 angezeigt; am 30.06. erschien die Rückkehrnachricht.
Die korrekte Rückkehr beider Spieler wurde vom Bediener bestätigt. Ein eigener
Post-Transition-Reload dieses Versuchs wurde nicht ausdrücklich bestätigt;
abweichende Länderauswahl ist als mögliche Vergleichsgrenze dokumentiert.

Im kombinierten Kandidaten wurden **744 von 794 aktuellen Leihbeginnen** auf den
Karrierestart projiziert; **50 bleiben unverändert**. Die eingefrorenen Quellen
behalten ihre historischen Daten. Leihenden, Eigentümer, Hauptvertragsdaten,
Ratings und ausdrücklich zukünftige Bedingungen bleiben unverändert.
Diese Generalisierung ist offline validiert, keine Einzel-Laufzeitprüfung aller
744 Fälle. Bestehende Spielstände werden dadurch nicht nachträglich repariert.

## Historienpaket und kombinierter Export

Das Paket deckt den vereinbarten bestehenden Umfang von zehn Ländern ab:
England, Italien, Spanien, Deutschland, Frankreich, Portugal, Niederlande,
Belgien, Türkei und Tschechien. Enthalten sind 20 Meister-/Hauptpokaleinträge,
103 vorgesehene Felder und die Bereinigung von 37 veralteten Markierungen;
deutsche Auf-/Abstiegsmarkierungen umfassen auch Liga 2 und 3.
Es ist kein vollständiges Archiv einzelner Spiele, Super-/Ligapokale oder
kontinentaler Titel. Zwei spätere tschechische administrative Änderungen bleiben
begründet außerhalb der sportlichen Saisonhistorie. Ligamitgliedschaft ist ein
separater Datenumfang.

Kandidat: `data/generated/release-candidate/native08-integrated-20260912-01`.
Installationsziel: `runtime/loan-test-20260912-08`.
Die vorherige diagnostische Datenbank einschließlich Master.dat ist gesichert.

- Unabhängiger Bytevergleich aller 638 Datenbankdateien bestanden.
- Nativer Reread bestanden: sämtliche 266.764 Spieler-/Ratingwerte erhalten;
  Serialisierung ändert sich genau bei den 744 vorgesehenen Leihdatensätzen.
- Drei gezielte Unit-Tests mit sieben Fällen bestanden.
- Editor-Export vom Bediener bestätigt; neue Master.dat unabhängig geprüft:
  **71.965.789 Bytes**, Änderungszeit **12.09.2026 19:42:10 UTC**.
- SHA-256: `379c38ced8093e4bbbac3ca1f620fe885b5c124ce2d54c50786c26344dbbd5ae`.
- Sichtprüfung der integrierten Historien und neue Karriere mit diesem Export:
  **NOT_TESTED**. Frühere Karriereergebnisse werden nicht darauf übertragen.

## Beobachtete Zeiten

| Vorgang | Zeit |
|---|---:|
| Speichern, einschließlich Bedienerreaktion | 8,39 s |
| Laden bis bedienbare Karriere, einschließlich Bedienerreaktion | 19,58 s |
| Folgeintervall ab etwa 11.07. Richtung Anfang August | 1:07,89 |
| Ab August-Checkpoint bis sichtbar 30.06.2027 | 15:25,24 |

Einzelmessungen, **BASELINE / OBSERVATIONAL**. Die kurzen Intervallgrenzen beruhen
teilweise auf Gesprächskontext; keine gemessene volle 30-Tage-Dauer. Für einen Tag,
genau sieben Tage und ausschließlich den Saisonübergang liegen keine Zeiten vor.
Während des langen Laufs erfolgte Offline-Historienarbeit. Keine Aussage über
eine Performanceverbesserung.

## Cleanup und offene Punkte

Manager und Editor sind geschlossen. Die vier testveränderten ursprünglichen
Saves wurden vor der Wiederherstellung als Belege behalten. Alle 16 ursprünglichen
Saves einschließlich quickstart.ea stimmen wieder mit dem Preflight überein.
Benannte Test-Saves bleiben erhalten. Die veränderten GameOptions.dat,
ManagerProfiles.dat und ucp.ini wurden vor Rücksetzung gesichert; alle zwölf
ursprünglichen Konfigurationsdateien sind wieder hashgleich.

Ungeklärt bleibt Cabrals Vertragsende: eingefrorener Plan 31.12.2027 gegenüber
sichtbarem Karriereende 30.06.2027. Sein anschließender vereinsloser Status passt
zum angezeigten Ablauf, beweist aber nicht das geplante Vertragsdatum.
Ctrl+C/Ctrl+V-Unterstützung wurde nicht implementiert. Weder breite Ratingarbeit
noch Performanceoptimierung oder Langzeitsimulation wurden begonnen.

**Nächster abgegrenzter Meilenstein in frischem Kontext:** Neue Karriere mit dem
kombinierten Export, gezielte Sichtprüfung der Historien und aktiven Leihen,
repräsentative korrigierte Leih-Rückkehr und anschließendes Save/Reload. Danach
erst über weitere Daten- oder Mehrjahresprüfungen entscheiden. Dieser nächste
Meilenstein wird hier nicht gestartet.

Maschinenlesbarer Abschluss: `reports/local/NATIVE08_GATE.json`.
Export/Cleanup: `native08-20260912-evidence/combined-editor-export.json` und
`native08-20260912-evidence/final-cleanup.json`.
