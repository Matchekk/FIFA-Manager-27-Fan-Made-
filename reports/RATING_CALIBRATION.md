# Rating calibration status

Latest candidate ratings-20260909-02 passes all21 native validation checks for3765
players/82863attribute changes and644support files. `validate-rating-retention.py`
also proves that all3009prior actual native rating rows remain identical and all
1096disputed attributes in756partial profiles are preserved exactly. These partial
profiles add17553changes to other attributes; retainedfields are still unresolved.
474whole-player holds plus756partial-profile reviews account for the original1230
reviewed people. No review case disappears merely because a partial update passes.

The field-retention experiment uses frozen calibration models and identity holdouts,
unchanged20point attribute and6level limits, and native recalculation for every
alternative. All3483unaffected players have exactly matching52native variants.
All7holdout and12league checks pass. Actual world85+count is62,90+count10,max94;
worldtop10mean91.4 andtop500mean81.19. The updated actual AFTER and detailed diff
are now the canonical report files. Their prior01 versions remain frozen.
Plan03 archive292files and completed02 archive155files bind this evidence.
The limits below and the game-scale interpretation are unchanged; no football
truth or complete rating coverage is inferred from aggregate distribution checks.

## Previous completed rating01 checkpoint

The calibrated plan02 now passes positional holdout, league-distribution and
inflation checks for3009players;1230source/position/outlier cases remain held.
The external native rating candidate passes full write/reread validation:
3009 players and 65310 attribute changes, with all protected fields preserved.
123 native and 241 Python tests pass. All 644 support files pass their audit.

The direct4239player experiment produced551changes exceeding fiveFMlevels and
lowered the cohort mean69.717→67.869. Its worldtop10mean fell91.1→87.6. This
showed a scale mismatch, especially among goalkeeper and centre-back profiles.
The native block evaluator subsequently computed220428alternatives; its original
direct values match all4239full-world preview values. It uses the real FM13reader
and GetPlayerLevel13, including serialized position bias, style and experience.

Calibration uses monotonic native-level quantile anchors within seven position
families. A deterministic20percent identity holdout remains outside fitting;
training uses mature, position-consistent players without extreme source-level
disagreement.75percent detailed-source weight and25percent retained profile,
with20point attribute bounds, preserve detail. Native-evaluated offsets select
the closest calibrated level. This tests game-scale drift, not individual football
performance truth. Large profile changes, position conflicts and level outliers
remain explicit review cases.

Goalkeepers use five directly comparable GK skills plus four explicit upstream
GK mappings: Jumping=max(diving,jumping); LongPassing=(EAoverall+kicking+1)//2;
Passing=LongPassing; ShotPower=kicking. Symmetric random jitter is omitted.
EAoverall participates only in that existing passing mapping and never becomes
an FMlevel. Generic EA goalkeeper outfield/physical values are retained fromFM
until their scale correspondence is established. OneOnOne,Consistency and
TacticAwareness remain unchanged. The revised486GKalternatives were evaluated
natively; unchanged3753outfield alternatives retain full-world preview parity.

The actual native reread confirms world85+players at64,90+players13→10,
maximum94,top10mean91.1→91.3 andtop500mean81.154→81.216.
RATING_DISTRIBUTION_AFTER.csv covers 56 groups using the fixed original cohort;
its 5800 scoped players have mean69.32 versus69.2972 before. PLAYER_RATING_DIFF.csv
records all3009 actual changes and their detailed attributes and source evidence.
The original BEFORE distribution was reproduced exactly. League membership changes
are excluded from this comparison so they cannot masquerade as rating effects.
The full 266764-player world, staff, competitions, relationships and global data
pass native validation. This does not close the1230 review holds or game gates.
Evidence is frozen in data/generated/ratings-20260909-01-evidence (151 files).
Source capture remains2026-09-08/PRE_ANNOUNCED_SEPTEMBER_10_UPDATE.

## Previous native preview checkpoint

Native calibration is in progress; no rating update has been staged to a database.
The new native writer restricts changes to37persisted FM13 attributes, checks each
player's full baseline serialization, validates all rows before mutation and
recalculates the reviewed level through GetPlayerLevel13.119native tests pass.
The protected-field hash masks only these37attributes, retaining talent, position
biases, playing style, experience, contracts and other persisted player fields.
The old mPotential member belongs to FM07/08; FM13 persists mTalent instead.

`local/NATIVE_RATING_BASELINE_INSPECTION_01.json` proves all266764players from
combined01 match the validated native reread and exposes their current37attributes.
`rating-preview-plan-20260908-01.csv` contains4239source-bound target-squad proposals.
The original EA pages were reparsed. Five unmapped fields, irrelevant outfield GK
attributes and four GK fields with special upstream overrides remain unchanged.
This direct-detail substitution is an uncalibrated experiment. Empty expected-level
columns make it preview-only; the native stage rejects those rows. The in-memory
preview and distribution analysis are running. No inflation claim is made yet.

Transfer/ownership reconciliation still has unresolved coverage cases.
`local/RATING_MAPPING_SOURCE_REVIEW_01.json` now inspects the actual upstream
converter and FM13 serializer. Only37attributes are persisted by this format;
32have direct detailed EA website field candidates. These are mapping references,
not a calibrated mutation plan. The converter also changes potential/talent and
adds random jitter; the full conversion routine must not be applied to existing
players under the requested preservation rules. Goalkeeper overrides and the
modern defensiveAwareness-to-marking name bridge require explicit treatment.
`RATING_SOURCE_JOIN_01.csv` contains4914unambiguous FIFA-ID/DOB/name matches against
the fixed original native cohort.203name cases,831missing native FIFA IDs and32DOB
conflicts remain excluded. This is not a current-club or attribute-update claim.

The unchanged native baseline is now measured in `RATING_DISTRIBUTION_BEFORE.csv`
with hash-bound evidence and the top500 identities in `local/RATING_BASELINE_01.json`.
`tools/report-rating-baseline.py` checks the complete266764-person identity universe
against the native FM13 projection before aggregating existing-style levels.
It reports top10/50/100/500, all12 scoped leagues, positions and age groups.
League groups follow original installed membership (5800people), not desired2026/27
membership; reserve players explicitly assigned to a scoped league remain included.
The scoped mean is69.2972, with63players at85+ and13at90+. World maximum is94.
These are observations of the existing database, not target values for calibration.
Best-style level differences are diagnostic only. No style, attribute or talent changed.
Future before/after comparisons must preserve the cohort or separate membership effects.
`local/RATING_BASELINE_NATIVE_14_VALIDATION.json` confirms these native level/style
values against candidate14's independent reread. Clubless IDs are transient there;
the audit uses complete canonical serialized identities, not reread IDs alone.

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
