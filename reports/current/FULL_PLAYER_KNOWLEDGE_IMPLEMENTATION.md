# FM27 Full Player Knowledge QoL

Status: **IMPLEMENTED / LIVE VALIDATION PASS**

The isolated FM27 runtime now reports player-knowledge level **10** for every
query. Player profiles therefore expose their complete information without a
prior scouting assignment.

## Technical implementation

The supported `Manager.exe` build contains one central player-knowledge getter
at RVA `0xAB9BA0`. The routine is used by player information, scouting, transfer
and comparison screens and clamps its normal result to 10. Runtime inspection
found 134 direct call sites to this getter.

`FM27.FullPlayerKnowledge.asi` replaces only this getter's result with 10. It
does not edit player attributes, potential, contracts, transfer logic, scout
staff, budgets or database records. The patch is guarded by both the supported
executable hash and the original 16-byte function signature; an unknown build
is left untouched.

## Validation

- x86 plugin build: PASS
- packaged PE architecture and patch-payload tests: PASS
- isolated runtime `Manager.exe` hash: PASS
- live function signature before activation: PASS
- live patched bytes reread: PASS
- running process responsive after activation: PASS
- protected original installation changed: NO

The active process was patched in memory without closing the user's running
game. The installed ASI applies the same guarded patch automatically on every
future start of the isolated runtime.

## Files

- Source: `src/plugins/full_player_knowledge/full_player_knowledge.cpp`
- Build: `tools/build-full-player-knowledge-plugin.ps1`
- Installer: `tools/install-full-player-knowledge-qol.py`
- Package: `data/qol/full-player-knowledge/plugins/FM27.FullPlayerKnowledge.asi`
- Test: `tests/test_full_player_knowledge_qol.py`

Rollback: delete `plugins/FM27.FullPlayerKnowledge.asi` from the isolated
runtime and restart the game.
