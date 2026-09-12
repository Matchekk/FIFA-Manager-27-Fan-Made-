# Save compatibility

| Component | Category | Current behaviour |
|---|---|---|
| Installation audit / identity export | SAVE_COMPATIBLE | Read-only, no save inspection |
| Native database probe | SAVE_COMPATIBLE | Offline read-only export, no injection |
| Transfer and squad reports | SAVE_COMPATIBLE | CSV/JSON proposals outside installation |
| Process measurement | SAVE_COMPATIBLE | Reads process counters, does not manipulate memory |
| New transfers, ratings, league structure | NEW_CAREER_REQUIRED | Not yet installed/exported as production data |
| Future runtime patches | EXPERIMENTAL | None implemented or enabled |

Starting a game normally can write its own configuration/logs. The toolkit
does not alter existing saves or silently migrate career data. A future
database build requires a fresh career and validated season/competition dates.
Changing season.ini alone is not a validated 2026/27 database migration.

The 15:00 candidate changes the source database only in an external test directory. It is not an existing-save migration. Native serialization renumbers internal person IDs. Existing careers must not be rewritten with this candidate or assumed compatible; the original game/database/save files remain intact.
