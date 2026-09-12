# Native07 Runtime Milestone — Completed

Editor export, new 2026/27 career and save/reload passed on 12 September 2026.
This closes only this bounded milestone; the full FM27 release remains open.

## Evidence

- Canonical runtime report: `reports/local/RUNTIME_SMOKE_NATIVE07_20260912_04.json`.
- Isolated runtime: `runtime/game-test-20260912-07`; do not use the original installation.
- Exported Master.dat SHA-256:
  `2c507e3d6e725cd36d0920f881dc4fbcfc954b8c4e413069621bd8002d931333`.
- Career before/after reload: Marek Wrona, 1. FC Köln, 01.07.2026, 7 unread,
  57.0 million cash, same visible offer. Reload completion was observed in the supplied
  app screenshot with the exact Runtime07 Manager process identity.
- Test save: `C:/Users/Matej Uni/Documents/FM/Data/SaveGames/Native07-Smoke-20260912.ea`,
  110,980,876 bytes, SHA-256
  `32117f2b8a30c3f97080658943004fdca46a49e877ae7058db23e1790fc21de8`.

## UI Fixes and Cleanup

218 existing 32px flag images were recovered from art_badges.big as loose assets in
Runtime07, without modifying the original installation. See
`tools/prepare-runtime-country-flags.py` and
`reports/local/RUNTIME_NATIVE07_FLAGS_FIX_20260912.json` for exact created paths and
rollback hashes. Flags were visible after the combined loose-file/windowed restart;
those two changes were not tested independently.

The pre-existing FM26 touchpad scroll fault was resolved by enabling the game's
"Ich benutze ein Touchpad" option, confirmed explicitly by the operator. No binary
hook was introduced. Slightly coarse scrolling was reported before that final setting.

The temporary WINDOWED setting was restored while preserving the game's newly saved
Editor-database and touchpad settings. The game's automatic quickstart.ea replacement
was restored from the verified backup. All 15 previous saves are hash-equal to their
pretest backups, and the new test save remains. Runtime Master.dat and original
Master.dat were verified unchanged after cleanup. Fullscreen was not retested after
restoring the preference. The completed smoke used windowed mode.

## Scope and Next Task

No native rebuild, rating integration, season transition or performance audit was run.
Native07 was identified in the Editor and the Editor database checkbox was observed
for the career; an additional in-game Cabral inspection was not performed.

End this task after its selected local checkpoint commit. Continue in a fresh task
from PROJECT_STATE.md: Jahnilo/EA/Belgium data work, season transition, performance and
reversible installer remain separate open work. Do not call the full FM27 release done.
