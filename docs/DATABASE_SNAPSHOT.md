# Datenbank-Snapshot

DATABASE_SNAPSHOT_DATE=2026-09-08

Der Quellen-Snapshot bleibt unverändert. Aktuelle Profile werden nur eingelesen,
wenn Abrufdatum und bestehender Tabellen-Snapshot denselben UTC-Tag haben.
Jede HTML-Datei liegt im vorhandenen Cache unter ihrem SHA-256; Metadaten
enthalten URL und Abrufzeit. Abgangsprofile enthalten zusätzlich Importzeit.
Ein erneuter Parserlauf nutzt dieselben Bytes und aktualisiert keine Quelle.

`tools/merge-stage-plans.py` friert disjunkte bestätigte Pläne ein und erzeugt
ein Begleitmanifest mit Eingabehashes, Planhash, Snapshot, Änderungs- und Leihzahl.
Der native Writer übernimmt das Snapshotdatum aus diesem Plan. Das technische
Builddatum steht separat in `BUILD_CAPTURE_DATE`; es datiert die Daten nicht um.

Quellenhierarchie: offizielle Vereine/Verbände/Ligen vor Transfermarkt und
anderen sekundären Datenbanken. Widersprüche zu vorhandenen DFB-Beobachtungen
bleiben zur Prüfung gesperrt. Ein Saisonereignis allein beweist keine aktuelle
Zuordnung; Abgänge brauchen ein aktuelles Identitäts-/Vereinsprofil und
passende Ereignisse. Leihen brauchen Eigentümer, Leihverein, Beginn, Ende und
Eigentümervertrag. Unbekannte Informationen bleiben unbekannt.

Manuell geprüfte externe Vereinszuordnungen stehen versioniert unter
`data/overrides/external_clubs.csv`; zusätzliche offizielle Transferbelege unter
`data/overrides/transfer_corroboration.csv`. Die Saudi-Liga wird dabei nicht
global aktualisiert, sondern nur als Transferziel betroffener Spieler genutzt.

Alle bisherigen Datenbanken sind Staging-Kandidaten. Eine neue Karriere wird
für eine spätere freigegebene Transfer-/Rating-/Ligadatenbank erforderlich.
