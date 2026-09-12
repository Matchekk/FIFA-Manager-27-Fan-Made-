# Current checkpoint: native06 completed; historical transfer batch next

All processes are closed. The explicit master goal remains ACTIVE and incomplete.
Work in C:\FM27CommunityOverhaul. Original game installation remains untouched.
No new Editor/UAC attempt was made; authorization persists, technical elevation is unavailable.

{
  "status": "NATIVE_INCREMENT06_COMPLETED_ARCHIVE_VERIFIED",
  "session_id": null,
  "candidate": "data/generated/release-candidate/transfer-increment-20260909-06",
  "cumulative_validation": "reports/local/NATIVE_CUMULATIVE_VALIDATION_06.json",
  "cumulative_validation_sha256": "d33b023a5c175ed02b58cc3acffe205fe6f02e6275b9779d157be4224e7416b1",
  "archive": "data/generated/transfer-increment-20260909-06-evidence-v2",
  "evidence_sha256": "5e66047704fba69f058b9c5a144c176a8a1cd9c096b39e24ea8f06878e14f216",
  "archive_original_inputs": 4838,
  "archive_objects": 2006,
  "python_tests": 289,
  "native_tests": 123,
  "reviewed_identities": 28,
  "current_plan_rows": 4422,
  "source_loan_rows": 794,
  "source_expired_loan_rows": 296,
  "native_club_changes": 2880,
  "native_loans": 794,
  "native_expired_returns": 296,
  "rating_profiles": 3765,
  "next_work": "Implement strict natural-identity historical event binding, individually review prior-season candidates and missing origin aliases, then reconcile a larger existing-player transfer batch.",
  "historical_preview": "data/generated/prior-season-transfer-review-20260909-03/REVIEW.json",
  "historical_exact_candidates": 113,
  "historical_origin_alias_holds": 101,
  "note": "All jobs closed. Native06 preserves22prior05rows and addsNgom/Thomas/Obrador/Amissah/Liberato;27incrementrows26clubmoves7loans2expiredreturns1successor,4plannedreserve-to-FIRSTflags. All11steps and11cumulativechecksPASS. Source/code may now advance; completed evidence remains immutable.",
  "release_ready": false
}

## Next transfer work

Read data/generated/prior-season-transfer-review-20260909-03/REVIEW.json.
There are309current typed holds for missing transfer events,278with prior-season
joined dates. Collection01 preserved its failures on unrelated unidentified
counterpart rows. Selection02 uses the existing explicit event-ID parser against
the same immutable pages:235observations/232people,224PERMANENT8FREE_TRANSFER2RETURN1LOAN.
Preview03 compares exact current profiles, native people and origin mappings:
113exactnaturalDOB/name+event+mappednativeorigin candidates;101origin-alias holds;
10historical origin mismatches;54without unique permanent arrival;2identity holds.
These are REVIEW ONLY; no historical overrides or plans were changed.
Existing historical_transfers.py unnecessarily requires a spelling override for
every historical event, even natural exact identities. Add an explicitly bound
natural-identity path with meaningful negative tests, preserving all existing
reviewed-identity checks, source hashes, prior-season date constraints and origin
semantics. Preserve all3prior history rows and28identity reviews. Review aliases
and selected events individually; do not import entire old-season tables blindly.
Then current+departure reconciliation, preserve prior rows, new native candidate.

## New native06 implementation and evidence

src/fm27/reviewed_rosters.py +9tests, both reconciliation tools integrated.
Only exact Thomas permanent current disposition supersedes the exact old DFB row.
Three official sources are hashed. Other6265current observations and4421prior
plans preserved. Initial wrapper failed because its TM-ID dictionary collapsed
legitimate repeated observations; separate exact-row multiset assessor passed.
Failure retained in primary-roster-review-20260909-01/reconciliation/RESULT.json.
FulhamU21 source9262 maps to nativeFulham917521/RESERVE, external aliases now148.
Latest source plans4422current473departure794loans181free296expired255successor25purchase.
Native06 complete plan27rows, retains all22native05rows and adds5existing people.
Native04 failed archive is still preserved; native05 completed archive unchanged.
Current Python289PASS, native123PASS. No native C++ change in this block.

## Further held work

Belgium: reports/local/BELGIUM_COMPETITION_RULE_REVIEW_04.json now binds all12ACFF
members and UnionU23 explicitly. RWDM471091/Olympic462983 go to117506050;
Stockay471837/Namur458792/Crossing471807 go to117506052. No native league changes.
JPL18/CPL15/full calendars/pools/rules, VV/lower closure and finalU23eligibility remain.
Primary Mouscron D2table lists17observations, not accepted as final format proof.

Missing-player review223cases/104withoutnativecandidate/16DOBconflicts. Zero created.
NachoPerez exists native293428, sourceDOB2008-08-29 vs native2008-09-01.
Diouf native2004-12-28 is correct perPL; source29wrong. Wilke native15June2007
vsDFB25June2007. No DOB changes yet. See DOB_CORRECTION_DIRECTIONS_01.json.
MISSING_PRIMARY_HOLDS_02.json: Cisse2007 DOBofficial; weight90vs84andcontractdisplay
2026-2026 unresolved. Jahnilo native249273 exists. Earlier Patro/Anderlecht names were wrong: clubUID471346
is Houtvenne and loan reference458760 is Westerlo UID458763. See
JAHNILO_NATIVE_REFERENCE_CORRECTION_03.json; review identity and owner U21 alias next. Game/export/save/season/performance/release gates remain OPEN.
