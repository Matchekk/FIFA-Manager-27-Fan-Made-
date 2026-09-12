# Rating calibration status

Calibration not performed. Transfer/ownership reconciliation takes priority.
5980 detailed FC27 website records have now been captured with official FIFA IDs
and source hashes. No ability/potential changes have been applied; no native
level validation of proposed ratings is claimed.
The native probe calls upstream `GetPlayerLevel13` and `GetBestStyleForPlayer`
for the installed attributes; it does not alter abilities, styles or talent.

Official EA's FC27 ratings page was verified on 2026-09-08:
https://www.ea.com/games/ea-sports-fc/ratings
The public fifaapi checkout still supports through version 26. Native FC27
schema support is not enabled. Do not label a dataset POST_TRANSFER merely
because the calendar reaches September 10: a source update must be detected
and cached before assigning that label.

Next: verified matched FC27 evidence, per-position robust monotonic calibration,
holdout checks, detailed-group mapping restricted to attributes actually
serialized by this FM format, native level recalculation and distribution
checks. Keep potential unless separately supported. No rating inflation or
profile-preservation claim has been made from an untested mapping.
