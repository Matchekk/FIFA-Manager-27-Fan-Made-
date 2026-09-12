# Final Codex/Astra usage forensics report

## Primary cause

Repeated model requests carrying a very large active context are the dominant measured token source. Actual request inputs have a median of 139,718 tokens, with 262,759,770 cumulative input-token appearances across 1880 responses. The local source does not expose the server credit formula, so this is a measured token cause, not an asserted percentage of allowance.

## Secondary causes

- High response frequency: 1,832 observed tool actions across the selected sessions.
- Repeated tool-result ingestion and repository/build/test output inflated subsequent contexts; see TOOL_USAGE.csv and CONTEXT_GROWTH.csv.
- Context compaction was directly observed 16 times; post-compaction activity is quantified in COMPACTION_ANALYSIS.md.
- Reasoning-output tokens: 452,468; visible output tokens: 1,408,674; input tokens: 262,759,770.
- Observable child work contributes 5 sessions; exact hidden/background billing is not exposed.

## Medium vs xHigh result

The long-run xHigh comparison is INSUFFICIENT DATA: only a small xHigh sample is present. Medium is measured over 223 responses; the long High phase is measured over 1394 responses. These records do not support the claim that Medium used less raw usage per hour than High; they support the opposite for these specific sessions, without proving credit equivalence.

| question | result | evidence |
|---|---|---|
| A. Did Medium use more total usage per hour? | NO | Medium 5116286.2 vs High 15202317.9 raw tokens/hour |
| B. Did Medium generate more model responses? | NO | Medium 35.141 vs High 102.527 responses/hour |
| C. Was average context size comparable? | PARTIALLY | Medium median 155883.0; High median 148240.5 |
| D. Did repeated context processing dominate? | YES | Cumulative measured input tokens dominate the token ledger; requests repeatedly carried large input contexts. |
| E. Did xHigh use more reasoning tokens per response? | INSUFFICIENT DATA | The xHigh sample is too small for a long-run comparison. |
| F. Did xHigh compensate with fewer responses? | INSUFFICIENT DATA | No comparable long xHigh development run is present. |
| G. Which setting produced more implementation per unit of usage? | PARTIALLY | The local logs lack a complete server credit ledger and comparable milestone denominators; the available file-write proxy is Medium 309210.7 vs High 309890.0 tokens/write. |
| H. Is Medium-fast-exhaustion / High-longer-runtime supported? | PARTIALLY | The mechanism is plausible, but these FM27 logs show higher raw High throughput/hour and no long xHigh comparison. |

## Most wasteful observed behavior

The clearest avoidable pattern is dense read/inspect/validate activity with repeated large tool outputs and no meaningful file write for extended intervals. Conservative episodes are listed in ANALYSIS_LOOPS.md. Repeated reads, commands, and the largest per-response inputs are ranked in the CSV reports.

## Recommended reasoning level for FM27

High for one bounded, difficult implementation batch with an explicit gate; Medium for small, well-understood edits. Do not use xHigh as a default: the observed xHigh sample is too small to establish long-run efficiency.

## Top 5 changes that will reduce usage

1. Maintain and load compact PROJECT_STATE.md instead of re-reading broad project documentation.
2. Batch coherent edits and gate/commit them, reducing response/tool cycles.
3. Summarize directory scans, CSVs, compiler logs, tests, and diffs locally.
4. After compaction, reread only state and active files; avoid repository reconstruction.
5. Use targeted tests and milestone gates; avoid repeated full builds after tiny edits.

## Output size analysis

Measured input tokens are 99.47% of known total tokens; visible output is 0.53%; reasoning-output is 0.17%. Reasoning-output is a subset of output, so these percentages are non-additive.
This rules out visible response prose as the dominant measured token volume. It does not by itself prove how the service converts cached input or reasoning into allowance credits.

## Cache analysis

Primary Medium cached-input ratio: 97.17% (912708 uncached input tokens); primary High: 97.55% (5029319); xHigh: 94.03% (137379).
Medium therefore has a slightly worse cache ratio than High in this sample, but not more absolute uncached input: High processed much more total input. xHigh's lower ratio is based on only 16 responses. The logs do not expose cache-key invalidation or billing discounts, so cache misses cannot be converted to allowance units.

## Reasoning-token observation

Observed reasoning-output tokens per response were Medium 228.1, High 274.0, and xHigh 108.7. This small xHigh sample does not show xHigh using more reasoning tokens per response, but it is not sufficient to generalize about long xHigh runs.

## Ranked causal breakdown

1. HIGH — repeated large-context input: 262,759,770 measured input-token appearances across 1880 responses; cumulative context processing is the strongest local explanation.
2. MEDIUM — repeated tool-result and repository inspection cycles: 10,952,900 serialized execution-result bytes were observed, with 103 repeated file paths. Bytes are not billing tokens, so no percentage is assigned.
3. MEDIUM — compaction/reconstruction pressure: 16 compactions and 167 read/scan/git actions in the first 15 minutes after them. This is a causal pattern, not proof every reread was waste.
4. LOW by token volume — reasoning and visible output: 452,468 reasoning-output tokens and 1,408,674 output tokens versus 262,759,770 input tokens.
5. LOW-to-MEDIUM — failures/retries: 141 failed/nonzero execution results were observed; automatic retry is not proven locally, and the per-request usage linkage is reported in RETRIES_AND_FAILURES.csv.
6. MEDIUM — child work: 5 observable child sessions account for 22,693,338 known tokens; hidden/background activity is not visible in the local ledger.

## Evidence summary

- Project: C:\FM27CommunityOverhaul
- FM27 development sessions analyzed: 7 (5 observable child sessions).
- Responses: 1,880; tool actions: 1,832; known incremental tokens: 264,168,444.
- Known input tokens: 262,759,770; cached input: 256,081,408 (97.46%); uncached input: 6,678,362.
- Known output tokens: 1,408,674; reasoning-output tokens: 452,468.
- Direct compactions: 16; thread state totals are included in SESSIONS.csv where available.

### Reasoning groups

The table below uses primary threads for effort comparisons; the evidence totals above include the five observable child sessions. This prevents parent/child work from being counted twice in the main Medium/High/xHigh comparison.

| effort | sessions | responses | elapsed hours | median input | cached ratio | total tokens | tokens/hour |
|---|---:|---:|---:|---:|---:|---:|---:|
| medium | 2 | 223 | 6.346 | 155883.0 | 0.97174 | 32,467,121 | 5,116,286.2 |
| high | 1 | 1394 | 13.596 | 148240.5 | 0.97553 | 206,696,614 | 15,202,317.9 |
| xhigh | 1 | 16 | 0.099 | 147332.5 | 0.94035 | 2,311,371 | 23,281,270.5 |
| max | 0 | null | null | null | null | null | null |

### Interpretation and limits

The rollout schema exposes incremental request accounting, so cumulative input-token appearances are measured rather than inferred from context-window size. total_tokens is the sum of each record's incremental total and is not a billing credit total. Cached input ratios are directly measured; cache invalidation mechanics and credit discounts are not proven locally. Encrypted reasoning contents remain opaque.

Git correlation used metadata-only git log and git diff --stat plus action traces; a Git repository was available.

See REASONING_COMPARISON.md, COMPACTION_ANALYSIS.md, ANALYSIS_LOOPS.md, and the CSVs for detailed evidence.
