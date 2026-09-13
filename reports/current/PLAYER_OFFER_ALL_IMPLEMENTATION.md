# Spieler allen Vereinen anbieten

## Ergebnis

Der Dialog `13TransfersOfferToClub` enthält einen zusätzlichen breiten Button
`Spieler allen Vereinen anbieten`. Er verwendet in normalem und dunklem Design
dieselben nativen Texturen, Zustände, Maße und Abstände wie `Spieler anbieten`.

Beim Klick friert die Erweiterung die IDs aller Vereine in der aktuell sichtbaren
Liste ein, entfernt doppelte IDs und führt für jeden Verein die bestehende native
Angebotsprüfung und Angebotsroutine aus. Transferart, Ablösesumme, Leihgebühr und
alle normalen Spielregeln kommen damit weiterhin aus dem vorhandenen Dialog.
Unzulässige Zeilen werden still übersprungen, damit keine Folge modaler Hinweise
entsteht. Anschließend wird die Vereinsliste einmal nativ aktualisiert. Die
Rückmeldung verwendet dieselbe native Ingame-Dialogfunktion und dieselben
lokalisierten Meldungen wie die Einzelaktion. Dadurch bleibt das Spiel im Vollbild
und öffnet kein externes Windows-Fenster. Interessierte Vereine melden sich danach
wie bei der Einzelaktion mit ihrem konkreten Angebot und erscheinen im Spiel.

## Technische Umsetzung

- Der bisher unsichtbare UI-Slot `BtPlayerDetails` wird als Klon von `BtAccept`
  bei `703,795,503,32` bereitgestellt. Die bestehende Ereignisbindung bleibt erhalten.
- Die deutsche Beschriftung steht direkt im Dialog. Ein nicht registrierbarer neuer
  Laufzeit-Lokalisierungsschlüssel wird dadurch nicht als `$IDS_...` angezeigt.
- `FM27.PlayerOfferAll.asi` ersetzt ausschließlich die alte Handler-Routine dieses
  Slots. `Manager.exe` und `screens.big` bleiben unverändert.
- Der Hook ist an SHA-256
  `8ebe1291fbcc1291bfee182995a165194156a0b4b8e0d6c80994cadb087a857c`
  und eine 16-Byte-Laufzeitsignatur gebunden. Bei einer anderen Version wird nicht
  gepatcht und `PATCH_SKIPPED_SIGNATURE_MISMATCH` protokolliert.
- Eine Reentrancy-Sperre und strukturierte Ausnahmebehandlung verhindern parallele
  Ausführung und lassen einen Fehler geschlossen enden.

## Installation und Prüfung

`tools/build-player-offer-all-plugin.ps1` baut die x86-ASI deterministisch.
`tools/install-player-offer-all-qol.py` extrahiert die beiden Quelldialoge aus
`screens.big`, erzeugt die losen Theme-Overrides und installiert Plugin sowie
Lokalisierung ausschließlich in eine direkte Projekt-Runtime.

Geprüft:

- erzeugte XML-Dateien sind parsebar und enthalten genau einen sichtbaren neuen Slot;
- normaler und dunkler Button verwenden die jeweils richtigen nativen Ressourcen;
- Plugin ist ein x86-PE und wird vom vorhandenen ASI-Loader geladen;
- Laufzeitlog: `PATCH_APPLIED` für die unterstützte `Manager.exe`;
- reproduzierbarer Plugin-SHA-256:
  `4d1f7a7783c68052509b7aac6347129ef28ebba1cb5cc945bd4c93230aa79c78`;
- der installierte Sprung endet innerhalb des geladenen Plugin-Moduls;
- gestartete isolierte Runtime: `Fussball Manager 2026 1.1.0`, reagiert;
- automatisierte Projekttests: PASS, 308/308;
- geschützte Originalinstallation wurde nicht verändert.

Ein manueller Klicktest im geöffneten Karriere-Dialog bleibt die abschließende
Bedienprüfung, weil die lokale Automationsschnittstelle keine native Spielsteuerung
bereitstellt.
