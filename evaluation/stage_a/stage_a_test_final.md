# Stage A evaluation: `test` split

Classifier: `embedding`. Mean time per prompt: 7.9 ms (CPU, batched).

## A01 Task category (degraded prompts)

Accuracy: **74.7%** on 482 prompts

| category | n | precision | recall | F1 |
|---|---|---|---|---|
| closed_qa | 99 | 56.7% | 76.8% | 0.65 |
| information_extraction | 93 | 73.2% | 55.9% | 0.63 |
| classification | 98 | 93.1% | 95.9% | 0.94 |
| summarization | 94 | 60.0% | 44.7% | 0.51 |
| coding | 98 | 99.0% | 98.0% | 0.98 |
| other | 0 | 0.0% | 0.0% | 0.00 |

Confusion matrix (rows = true, columns = predicted)

| true \ pred | closed_qa | information_extraction | classification | summarization | coding | other |
|---|---|---|---|---|---|---|
| closed_qa | 76 | 5 | 2 | 13 | 0 | 3 |
| information_extraction | 23 | 52 | 2 | 15 | 1 | 0 |
| classification | 2 | 0 | 94 | 0 | 0 | 2 |
| summarization | 33 | 14 | 2 | 42 | 0 | 3 |
| coding | 0 | 0 | 1 | 0 | 96 | 1 |

Out-of-scope prompts (held-out Dolly brainstorming/creative_writing, never in the index): **68.5%** classified as `other` (467 prompts).

## A02 Output format
| prompt | flagged as having a format | agreement with dataset label |
|---|---|---|
| original instruction | 6.8% | 95.2% |
| degraded prompt | 3.1% | (no label) |
| optimized prompt | 79.0% | 67.0% |

A good detector flags few degraded prompts and most optimized prompts.

## A03 Constraints stated (degraded vs optimized)
| category | constraint | degraded | optimized |
|---|---|---|---|
| classification | length | 0.0% | 24.5% |
| classification | language | 2.0% | 2.0% |
| closed_qa | length | 0.0% | 81.8% |
| coding | length | 1.0% | 6.1% |
| coding | language | 57.1% | 96.9% |
| information_extraction | length | 0.0% | 25.8% |
| summarization | length | 4.3% | 88.3% |

Missing relevant constraints in degraded prompts: length 209, audience 79, tone 79, language 41

## A04 Redundancy
Prompts with filler or repetition: degraded 3.9%, optimized 0.4%.
Most common in degraded prompts: 'hey' (8), 'can you' (8), 'just' (6), 'you know' (1), 'actually' (1), 'ling ling' (1)

## A05 Ambiguous references
Degraded prompts whose source had no context (141): 5.0% flagged (these are mostly false alarms).
Degraded prompts whose source HAD a context, run without it (341): 20.5% flagged (a reference to a missing passage is exactly what A05 should catch).
