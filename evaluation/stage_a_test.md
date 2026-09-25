> **STALE, regenerate at the end.** Produced before the A02/A03 pattern changes, the 2,265-row dataset and the logistic-regression category head; the numbers below no longer describe the current Stage A. Regenerate with `python -m app.stage_a.evaluate --split test --out ../evaluation/stage_a_test.md` once, after all tuning.

# Stage A evaluation: `test` split

Classifier: `embedding`. Mean time per prompt: 8.9 ms (CPU, batched).

## A01 Task category (degraded prompts)

Accuracy: **68.3%** on 202 prompts

| category | n | precision | recall | F1 |
|---|---|---|---|---|
| closed_qa | 40 | 43.9% | 72.5% | 0.55 |
| information_extraction | 42 | 60.6% | 47.6% | 0.53 |
| classification | 40 | 88.4% | 95.0% | 0.92 |
| summarization | 40 | 75.0% | 30.0% | 0.43 |
| coding | 40 | 100.0% | 97.5% | 0.99 |
| other | 0 | 0.0% | 0.0% | 0.00 |

Confusion matrix (rows = true, columns = predicted)

| true \ pred | closed_qa | information_extraction | classification | summarization | coding | other |
|---|---|---|---|---|---|---|
| closed_qa | 29 | 5 | 1 | 3 | 0 | 2 |
| information_extraction | 16 | 20 | 4 | 1 | 0 | 1 |
| classification | 2 | 0 | 38 | 0 | 0 | 0 |
| summarization | 19 | 7 | 0 | 12 | 0 | 2 |
| coding | 0 | 1 | 0 | 0 | 39 | 0 |

Out-of-scope prompts (held-out Dolly brainstorming/creative_writing, never in the index): **57.6%** classified as `other` (467 prompts).

## A02 Output format
| prompt | flagged as having a format | agreement with dataset label |
|---|---|---|
| original instruction | 10.4% | 92.6% |
| degraded prompt | 4.5% | (no label) |
| optimized prompt | 80.2% | 68.8% |

A good detector flags few degraded prompts and most optimized prompts.

## A03 Constraints stated (degraded vs optimized)
| category | constraint | degraded | optimized |
|---|---|---|---|
| classification | length | 0.0% | 15.0% |
| closed_qa | length | 0.0% | 85.0% |
| coding | length | 0.0% | 5.0% |
| coding | language | 57.5% | 97.5% |
| information_extraction | length | 0.0% | 38.1% |
| summarization | length | 0.0% | 92.5% |

Missing relevant constraints in degraded prompts: length 87, audience 21, tone 21, language 16

## A04 Redundancy
Prompts with filler or repetition: degraded 7.4%, optimized 0.0%.
Most common in degraded prompts: 'hey' (7), 'just' (6), 'can you' (5), 'you know' (1), 'actually' (1)

## A05 Ambiguous references
Degraded prompts whose source had no context (60): 8.3% flagged (these are mostly false alarms).
Degraded prompts whose source HAD a context, run without it (142): 26.8% flagged (a reference to a missing passage is exactly what A05 should catch).
