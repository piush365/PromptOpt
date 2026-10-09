# Stage C evaluation (test split)

Adapter `artifacts/stage_c_adapter`; base `Qwen/Qwen2.5-0.5B-Instruct`; greedy decoding, batch 1. Split `test` (482 prompts, 964 Stage C examples); final, one-time run. Plan: `docs/STAGE_C_PLAN.md`. Field targets come from the dataset's optimized prompts via the parser (known limitations in the plan). Similarities: cosine, all-MiniLM-L6-v2.

## (a) Zero-shot base vs LoRA

Kinds: `routed` = Stage B's real unresolved fields; `forced` = a random subset of task/output_format/constraints; `forced_all` = all three. `passes validation` = the answer would be used by the pipeline (contract in the plan, section 5).

| model | examples | n | JSON valid | exact keys | passes validation | category acc. | task present | task sim. | format null/non-null agree | format sim. | constraints empty/non-empty agree | constraints sim. |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| zero-shot base | routed | 31 | 93.5% | 19.4% | 9.7% | 20.8% | 57.1% | 0.534 | 50.0% | 0.156 | 50.0% | 0.045 |
| zero-shot base | forced | 451 | 89.1% | 29.9% | 6.7% | - | 82.1% | 0.670 | 52.5% | 0.266 | 56.5% | 0.161 |
| zero-shot base | forced_all | 482 | 97.5% | 73.2% | 3.1% | - | 97.1% | 0.668 | 58.7% | 0.241 | 52.5% | 0.155 |
| zero-shot base | all | 964 | 93.5% | 51.2% | 5.0% | 20.8% | 91.5% | 0.668 | 56.4% | 0.247 | 53.8% | 0.156 |
| LoRA | routed | 31 | 100.0% | 100.0% | 96.8% | 58.3% | 100.0% | 0.819 | 66.7% | 0.463 | 75.0% | 0.484 |
| LoRA | forced | 451 | 100.0% | 100.0% | 98.7% | - | 100.0% | 0.807 | 78.1% | 0.620 | 66.8% | 0.568 |
| LoRA | forced_all | 482 | 100.0% | 100.0% | 97.9% | - | 100.0% | 0.797 | 79.3% | 0.623 | 79.3% | 0.615 |
| LoRA | all | 964 | 100.0% | 100.0% | 98.2% | 58.3% | 100.0% | 0.801 | 78.5% | 0.617 | 75.0% | 0.605 |

## (b) Ablation

`routed` = prompts Stage B actually sends to Stage C (too few on their own); `forced` = every prompt of the split with task, output_format and constraints requested. A+B = current pipeline; A+B+C = Stage C fills the requested fields, Stage B's other fields locked, rejected answers fall back to Stage B; C-only = Stage C fills all three fields with no Stage B rules (rejected -> the raw prompt). Format stated = A02 (or the parser's layouts) finds a format.

**Intent preservation (main number): task intent sim.** = cosine similarity between the final IR's `task` field only and the dataset's original instruction, so added format and constraint sentences do not count against it. Reference rows: `degraded` = the degraded prompt itself; `dataset optimized` = the task parsed from the dataset's optimized prompt. The degraded prompt usually keeps the original instruction's own words, so it is close to the ceiling here; what matters is how much each system loses from it.

Full-prompt sim. (reference only) compares the whole final prompt (task + requirements + constraints + format) with the original instruction. It falls as a prompt gains the format and constraint sentences the optimizer is meant to add, so it is not an intent measure: the bare degraded prompts score higher on it than the dataset's own optimized prompts.

| set | system | n | task intent sim. (main) | full-prompt sim. (reference) | format stated | JSON valid | fallback | category acc. | task sim. | format null/non-null agree | median s |
|---|---|---|---|---|---|---|---|---|---|---|---|
| routed | A+B | 31 | **0.869** | 0.843 | 22.6% | - | - | - | - | - | - |
| routed | A+B+C | 31 | **0.843** | 0.758 | 90.3% | 100.0% | 3.2% | 58.3% | 0.819 | 66.7% | 0.47 |
| routed | C-only | 31 | **0.712** | 0.604 | 90.3% | 100.0% | 6.5% | - | 0.751 | 67.7% | 0.68 |
| forced | A+B | 482 | **0.886** | 0.802 | 95.0% | - | - | - | - | - | - |
| forced | A+B+C | 482 | **0.769** | 0.711 | 90.2% | 100.0% | 2.1% | - | 0.797 | 79.3% | 0.68 |
| forced | C-only | 482 | **0.765** | 0.690 | 88.6% | 100.0% | 1.9% | - | 0.795 | 79.3% | 0.67 |
| reference | dataset optimized | 482 | 0.826 | 0.774 | 79.0% | - | - | - | - | - | - |
| reference | degraded | 482 | 0.903 | 0.903 | 3.1% | - | - | - | - | - | - |

### Category: Stage C vs Stage A, and the category policy

Policy (contract.category_decision, chosen on val): Stage C's category is never used on its own; when a prompt is routed for the category it is marked uncertain and the UI asks the user, pre-selecting Stage C's guess. So every valid guess lands in the `uncertain` row; the tables compare Stage C's guess with Stage A's prediction. Right = equals the dataset label.

Prompts routed for the task category:

| prompts | n | Stage A right | Stage C guess right |
|---|---|---|---|
| all prompts in this set | 31 | 16/31 (51.6%) | - |
| with a valid Stage C category | 24 | 9/24 (37.5%) | 14/24 (58.3%) |
| policy: accepted (Stage C's category used) | 0 | 0/0 | 0/0 |
| policy: uncertain (user asked, guess pre-selected) | 24 | 9/24 (37.5%) | 14/24 (58.3%) |

Forced: every prompt asked for its category the way a routed prompt is (the routed set alone is small).

All prompts:

| prompts | n | Stage A right | Stage C guess right |
|---|---|---|---|
| all prompts in this set | 482 | 360/482 (74.7%) | - |
| with a valid Stage C category | 476 | 354/476 (74.4%) | 293/476 (61.6%) |
| policy: accepted (Stage C's category used) | 0 | 0/0 | 0/0 |
| policy: uncertain (user asked, guess pre-selected) | 476 | 354/476 (74.4%) | 293/476 (61.6%) |

Only prompts with Stage A confidence < 0.6 (the range where the category is routed):

| prompts | n | Stage A right | Stage C guess right |
|---|---|---|---|
| all prompts in this set | 171 | 77/171 (45.0%) | - |
| with a valid Stage C category | 171 | 77/171 (45.0%) | 71/171 (41.5%) |
| policy: accepted (Stage C's category used) | 0 | 0/0 | 0/0 |
| policy: uncertain (user asked, guess pre-selected) | 171 | 77/171 (45.0%) | 71/171 (41.5%) |

## Named cases (illustrative, not evidence)

Hand-picked prompts reported by name (`evaluation/stage_c/named_cases.json`). Their expected categories were set or confirmed after a smoke run of Stage C had been seen, so they illustrate behaviour and are not part of the evidence; the split's numbers above are.

| case | prompt | Stage A | Stage C guess | expected | guess | policy | Stage C output |
|---|---|---|---|---|---|---|---|
| named-image-describe | `describe what is happening in the picture` | coding (0.37) | summarization | summarization | **right** | uncertain | `{"output_format": "Output as a single sentence describing each part.", "constraints": [], "category": "summarization"}` |

## (c) Latency per prompt (Stage C call only, batch 1, greedy)

| device | n | median s | p95 s | max s |
|---|---|---|---|---|
| GPU | 40 | 0.74 | 1.23 | 1.39 |
| CPU | 20 | 4.55 | 7.22 | 7.22 |
| zero-shot base (cuda) | 20 | 1.47 | 3.30 | 3.30 |

Requirement: under 3 s per prompt on the laptop GPU (median): **met** (0.74 s).
