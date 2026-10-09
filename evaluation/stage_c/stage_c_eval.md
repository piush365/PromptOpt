# Stage C evaluation (val split)

Adapter `artifacts/stage_c_adapter`; base `Qwen/Qwen2.5-0.5B-Instruct`; greedy decoding, batch 1. Split `val` (149 prompts, 298 Stage C examples); the test split is not used. Plan: `docs/STAGE_C_PLAN.md`. Field targets come from the dataset's optimized prompts via the parser (known limitations in the plan). Similarities: cosine, all-MiniLM-L6-v2.

## (a) Zero-shot base vs LoRA

Kinds: `routed` = Stage B's real unresolved fields; `forced` = a random subset of task/output_format/constraints; `forced_all` = all three. `passes validation` = the answer would be used by the pipeline (contract in the plan, section 5).

| model | examples | n | JSON valid | exact keys | passes validation | category acc. | task present | task sim. | format null/non-null agree | format sim. | constraints empty/non-empty agree | constraints sim. |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| zero-shot base | routed | 10 | 100.0% | 0.0% | 0.0% | 11.1% | 100.0% | 0.792 | 55.6% | 0.227 | 44.4% | - |
| zero-shot base | forced | 139 | 92.1% | 28.1% | 5.0% | - | 85.9% | 0.683 | 65.0% | 0.256 | 58.5% | 0.142 |
| zero-shot base | forced_all | 149 | 97.3% | 73.8% | 2.0% | - | 97.3% | 0.658 | 68.5% | 0.245 | 44.3% | 0.140 |
| zero-shot base | all | 298 | 95.0% | 50.0% | 3.4% | 11.1% | 93.4% | 0.667 | 66.8% | 0.248 | 49.2% | 0.141 |
| LoRA | routed | 10 | 100.0% | 100.0% | 100.0% | 33.3% | 100.0% | 0.884 | 44.4% | 0.600 | 44.4% | 0.774 |
| LoRA | forced | 139 | 100.0% | 100.0% | 98.6% | - | 100.0% | 0.822 | 75.0% | 0.616 | 78.0% | 0.493 |
| LoRA | forced_all | 149 | 100.0% | 100.0% | 98.0% | - | 100.0% | 0.820 | 73.2% | 0.636 | 78.5% | 0.491 |
| LoRA | all | 298 | 100.0% | 100.0% | 98.3% | 33.3% | 100.0% | 0.821 | 72.7% | 0.628 | 77.1% | 0.501 |

## (b) Ablation

`routed` = val prompts Stage B actually sends to Stage C (too few on their own); `forced` = every val prompt with task, output_format and constraints requested. A+B = current pipeline; A+B+C = Stage C fills the requested fields, Stage B's other fields locked, rejected answers fall back to Stage B; C-only = Stage C fills all three fields with no Stage B rules (rejected -> the raw prompt). Format stated = A02 (or the parser's layouts) finds a format.

**Intent preservation (main number): task intent sim.** = cosine similarity between the final IR's `task` field only and the dataset's original instruction, so added format and constraint sentences do not count against it. Reference rows: `degraded` = the degraded prompt itself; `dataset optimized` = the task parsed from the dataset's optimized prompt. The degraded prompt usually keeps the original instruction's own words, so it is close to the ceiling here; what matters is how much each system loses from it.

Full-prompt sim. (reference only) compares the whole final prompt (task + requirements + constraints + format) with the original instruction. It falls as a prompt gains the format and constraint sentences the optimizer is meant to add, so it is not an intent measure: the bare degraded prompts score higher on it than the dataset's own optimized prompts.

| set | system | n | task intent sim. (main) | full-prompt sim. (reference) | format stated | JSON valid | fallback | category acc. | task sim. | format null/non-null agree | median s |
|---|---|---|---|---|---|---|---|---|---|---|---|
| routed | A+B | 10 | **0.911** | 0.901 | 10.0% | - | - | - | - | - | - |
| routed | A+B+C | 10 | **0.885** | 0.773 | 90.0% | 100.0% | 0.0% | 33.3% | 0.884 | 44.4% | 0.50 |
| routed | C-only | 10 | **0.766** | 0.700 | 90.0% | 100.0% | 10.0% | - | 0.751 | 40.0% | 0.67 |
| forced | A+B | 149 | **0.855** | 0.774 | 94.0% | - | - | - | - | - | - |
| forced | A+B+C | 149 | **0.773** | 0.703 | 92.6% | 100.0% | 2.0% | - | 0.820 | 73.2% | 0.67 |
| forced | C-only | 149 | **0.769** | 0.682 | 91.9% | 100.0% | 2.0% | - | 0.820 | 73.2% | 0.67 |
| reference | dataset optimized | 149 | 0.799 | 0.748 | 86.6% | - | - | - | - | - | - |
| reference | degraded | 149 | 0.872 | 0.872 | 4.7% | - | - | - | - | - | - |

### Category: Stage C vs Stage A, and the category policy

Policy (contract.category_decision, chosen on val): Stage C's category is never used on its own; when a prompt is routed for the category it is marked uncertain and the UI asks the user, pre-selecting Stage C's guess. So every valid guess lands in the `uncertain` row; the tables compare Stage C's guess with Stage A's prediction. Right = equals the dataset label.

Prompts routed for the task category:

| prompts | n | Stage A right | Stage C guess right |
|---|---|---|---|
| all prompts in this set | 10 | 3/10 (30.0%) | - |
| with a valid Stage C category | 9 | 2/9 (22.2%) | 3/9 (33.3%) |
| policy: accepted (Stage C's category used) | 0 | 0/0 | 0/0 |
| policy: uncertain (user asked, guess pre-selected) | 9 | 2/9 (22.2%) | 3/9 (33.3%) |

Forced: every prompt asked for its category the way a routed prompt is (the routed set alone is small).

All prompts:

| prompts | n | Stage A right | Stage C guess right |
|---|---|---|---|
| all prompts in this set | 149 | 113/149 (75.8%) | - |
| with a valid Stage C category | 148 | 112/148 (75.7%) | 83/148 (56.1%) |
| policy: accepted (Stage C's category used) | 0 | 0/0 | 0/0 |
| policy: uncertain (user asked, guess pre-selected) | 148 | 112/148 (75.7%) | 83/148 (56.1%) |

Only prompts with Stage A confidence < 0.6 (the range where the category is routed):

| prompts | n | Stage A right | Stage C guess right |
|---|---|---|---|
| all prompts in this set | 50 | 20/50 (40.0%) | - |
| with a valid Stage C category | 50 | 20/50 (40.0%) | 15/50 (30.0%) |
| policy: accepted (Stage C's category used) | 0 | 0/0 | 0/0 |
| policy: uncertain (user asked, guess pre-selected) | 50 | 20/50 (40.0%) | 15/50 (30.0%) |

## Named cases (illustrative, not evidence)

Hand-picked prompts reported by name (`evaluation/stage_c/named_cases.json`). Their expected categories were set or confirmed after a smoke run of Stage C had been seen, so they illustrate behaviour and are not part of the evidence; the val numbers above are.

| case | prompt | Stage A | Stage C guess | expected | guess | policy | Stage C output |
|---|---|---|---|---|---|---|---|
| named-image-describe | `describe what is happening in the picture` | coding (0.37) | summarization | summarization | **right** | uncertain | `{"output_format": "Output as a single sentence describing each part.", "constraints": [], "category": "summarization"}` |

## (c) Latency per prompt (Stage C call only, batch 1, greedy)

| device | n | median s | p95 s | max s |
|---|---|---|---|---|
| GPU | 40 | 0.71 | 1.15 | 1.28 |
| CPU | 20 | 4.63 | 7.61 | 7.61 |
| zero-shot base (cuda) | 20 | 1.37 | 3.25 | 3.25 |

Requirement: under 3 s per prompt on the laptop GPU (median): **met** (0.71 s).
