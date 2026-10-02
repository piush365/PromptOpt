# Stage C plan: LoRA fallback for unresolved IR fields

Stage C is a small fine-tuned model that fills the IR fields Stage B could not fill, and nothing else. This document
fixes the data format, the training configuration and the evaluation plan before any training run. All tuning uses
the val split; the test split is run once at the very end (then tag `final-for-test`).

## 1. Routing contract

* Stage A and Stage B are unchanged (frozen at `frozen-for-test`). Stage C runs after Stage B.
* A prompt goes to Stage C only for the reasons in `STAGE_C_REASONS` (`backend/app/stage_b/optimizer.py`):
  the task category is still unresolved after the 0.6 gate and B08, or there is an ambiguous reference.
* Fields Stage C may fill, by reason:

  | unresolved (from `ir.unresolved`) | fields Stage C fills |
  |---|---|
  | `task category` | `output_format`, `constraints`, `category` (Stage B added nothing category-specific) |
  | `ambiguous reference: ...` | `task` |
  | `output format` (recorded, not routed) | `output_format` |

* Every other field is **locked**: Stage B's value is kept even if Stage C returns something for it.
* Stage C's answer must be one JSON object with exactly the requested keys. It is validated with the same detectors
  as the rest of the pipeline (section 5); if it fails, the prompt keeps Stage B's result (fallback).

## 2. Data (`python -m app.stage_c.data`)

Source: PromptOpt Dataset v1.2 final, **train** split (4,509 rows) for training and **val** (149 rows) for early
stopping and evaluation. Test and benchmark are not touched.

### 2.1 Input
```json
{"prompt": "which season goes with flowers, snowflakes, leaves falling, beaches",
 "category": {"value": "classification", "source": "stage_a", "confidence": 0.29},
 "has_context": true, "attachment": "none",
 "ir": {"task": "Which season goes with flowers, snowflakes, leaves falling, beaches?",
        "output_format": null, "constraints": null, "requirements": [], "category": null},
 "unresolved": ["output_format", "constraints", "category"]}
```
The degraded prompt, the category Stage A (or the user) gave it with its confidence, and Stage B's IR with the fields
to fill set to `null` and listed in `unresolved`. The passage itself is not included (only `has_context`): Stage C
writes the instruction, not the answer, and this keeps sequences short.

### 2.2 Target
```json
{"output_format": "Output each item followed by its season on a separate line.", "constraints": [],
 "category": "classification"}
```
Exactly the unresolved keys. `task`, `output_format` and `constraints` come from the dataset's optimized prompt via
the parser below; `category` is the dataset label. `output_format: null` means the optimized prompt states no format
(common for closed_qa: only 152 of 951 state one), and `constraints: []` means none.

The chat format is system + user (input JSON) + assistant (target JSON); the system prompt is `SYSTEM_PROMPT` in
`backend/app/stage_c/data.py` and is also in `config.json`.

### 2.3 Which fields are marked unresolved

| kind | rows | rule |
|---|---|---|
| `routed` | train 377, val 10 | Stage B's real `unresolved` list, mapped as in section 1 |
| `forced` | train 4,132, val 139 | all other rows: a seeded random non-empty subset of task / output_format / constraints (each kept with p = 0.5) |
| `forced_all` | val 149 | every val row once more with all three fields requested, for the forced-routing evaluation |

Only 8.4% of train prompts route naturally (test: 6.4%), too few to train on, hence the forced subsets: they teach the
model to fill any requested field while respecting the locked ones. 53 train rows whose requested format is still
inside the parsed task are marked `clean: false` and left out of training.

**Stage A on train is cross-fitted.** The category index was built from the train split, so Stage A on train would
find each prompt as its own neighbour. Each train row is instead classified by an index and linear head built without
its fold (5 folds grouped by original instruction), reusing the embeddings stored in the index. Cross-fitted accuracy
on train is 73.9%, close to the 74.7% on test, so the routing labels are realistic. Val is not in the index and uses
it as is.

### 2.4 Parser: optimized prompt -> fields (`backend/app/stage_c/parse.py`)

The first paragraph is the instruction; later paragraphs (`Items: ...`, `Input: ...`, code) are context. The first
sentence is the task; a few fixed clause shapes are cut out of it (a restrictive grounding clause, a length, a
trailing format clause, a format phrase like "in 3 bullet points"). Each later sentence goes to `output_format` if it
states a structure (Stage A's A02 patterns minus the length-only ones, plus three layouts A02 misses), to
`constraints` if it states a length, tone, audience, language or "only the provided text", and otherwise stays in the
task. Every sentence lands in exactly one field, so nothing is lost. Tests: `backend/tests/test_stage_c_parse.py`.

Coverage on train ("separated" = the stated format/constraint ends up in its own field, not inside the task):

| category | n | task | output_format separated | constraints separated |
|---|---|---|---|---|
| closed_qa | 951 | 100% | 112/152 (73.7%) | 620/812 (76.4%) |
| information_extraction | 867 | 100% | 710/714 (99.4%) | 38/91 (41.8%) |
| classification | 906 | 100% | 760/795 (95.6%) | 22/37 (59.5%) |
| summarization | 920 | 100% | 366/396 (92.4%) | 451/566 (79.7%) |
| coding | 865 | 100% | 745/808 (92.2%) | 57/77 (74.0%) |
| **all** | 4,509 | **100%** | 2,693/2,865 (**94.0%**) | 1,188/1,583 (**75.0%**) |

A hand check of 20 random parses: 17 fully correct; the two fixable misses (a layout A02 does not know) were fixed.

### 2.5 Known limitations (accepted)

* **Constraints coverage is 75%, below the 85% bar; accepted (decision of 2026-10-02).** Most misses are lengths
  embedded in the task wording ("Extract **a concise** definition ...", "in **one short** sentence"); they cannot be
  cut out without rewriting, so **embedded lengths stay in the `task` field**. The text is never lost, but when a
  target asks for `constraints` while `task` is locked, such a length is missing from the target: this affects
  **133 of 1,516 such train targets (8.8%)**.
* closed_qa formats are separated in 73.7% of the prompts that state one; the rest are phrased inside the first
  sentence ("Answer only with the number of ...") and stay in the task.
* **Only 111 train rows were individually human-validated.** The other targets are LLM-written optimized prompts
  that passed the human-rejection pass and the LLM-assisted filter (`docs/DATASET_CARD.md`), not individual review.
* `category` is part of the target when the routing reason is the task category (decision of 2026-10-02), although
  the original spec named only task / output_format / constraints.

### 2.6 Files

`data/stage_c/` (git-ignored, like all data): `train.jsonl`, `val.jsonl`, `stats.json`, `config.json`,
`train_stage_c.py`, `manifest.json`. `data/stage_c_data_v1.zip` holds exactly the last five minus stats (train/val,
config, the training script, manifest). The manifest (sha256, bytes, row counts) is committed as
`docs/stage_c_data_manifest.json`; the notebook refuses to train if any file's sha256 differs from it. Each JSONL row
also carries `id`, `category`, `kind`, `stage_a_category`, `stage_a_confidence`, `rules`, `clean`, `human_validated`
for analysis.

## 3. Model and training configuration (`config.json`, `backend/app/stage_c/train.py`)

| setting | value | why |
|---|---|---|
| base model | Qwen/Qwen2.5-0.5B-Instruct | smallest current Qwen instruct model; fits a free T4 and the 4 GB laptop GPU |
| method | LoRA (peft), r = 16, alpha = 32, dropout 0.05, all attention + MLP projections | |
| max length | 512 tokens | chat-templated examples: median 291, p99 371, max 446; nothing is truncated |
| loss | assistant tokens only | |
| optimizer | AdamW, lr 2e-4, linear warmup 3% then linear decay, grad clip 1.0 | |
| batch | 4 x 4 gradient accumulation = 16 | |
| epochs | up to 3 (279 steps each, 837 at most) | |
| early stopping | val loss every 50 steps, patience 3; best adapter kept | |
| precision | fp16 on T4, bf16 on the RTX 3050 (Ampere supports it, more stable than fp16), adapters in fp32 | |
| memory | gradient checkpointing | |
| seed | 13 (Python, NumPy, torch; data shuffling) | |
| decoding | greedy, max 192 new tokens | |

Where it runs: locally in `backend/.venv-gpu` (CUDA torch) if a 20-step estimate (`train.py --estimate`) shows it
fits in 4 GB and finishes within about 2 hours; otherwise in Colab with `notebooks/train_stage_c.ipynb`, which mounts
Drive, unzips `MyDrive/PromptOpt/stage_c/stage_c_data_v1.zip`, verifies the sha256s, runs a zero-shot baseline,
trains, prints 10 val predictions and saves `MyDrive/PromptOpt/stage_c/outputs/stage_c_adapter_v1.zip`.

## 4. Evaluation plan (Phase 3, val only)

All numbers on val; the test split is run once at the very end.

**(a) Base model vs LoRA**: same inputs, same greedy decoding, zero-shot base vs the trained adapter.

**(b) Ablation**, each on two sets:
* the **routed subset** (val prompts Stage B actually sends to Stage C; 10 prompts, too small alone), and
* **forced routing**: all 149 val prompts with task / output_format / constraints requested (`forced_all`).

| system | what runs |
|---|---|
| A+B | Stage A + Stage B only (current pipeline) |
| A+B+C | Stage B, then Stage C fills the unresolved fields under the contract; failures fall back to Stage B |
| C-only | Stage C fills all three fields from the prompt, with no Stage B rules applied (requirements empty) |

**Metrics**

| metric | definition |
|---|---|
| JSON validity | output parses as one JSON object |
| exact keys | its keys are exactly the requested ones |
| field accuracy vs target | `category`: exact match. `output_format`: null/non-null agreement, plus cosine similarity (all-MiniLM-L6-v2, the Stage A encoder) when both are non-null. `constraints`: same for the joined list. `task`: cosine similarity |
| intent similarity | cosine similarity between the final plain prompt and the dataset's original instruction (same encoder the dataset used for `sim_*`) |
| fallback rate | share of Stage C calls rejected by validation (Stage B result kept) |
| format-stated rate | A02 finds an output format in the final prompt |
| Stage C vs Stage A category | on routed prompts: accuracy of Stage C's `category` vs Stage A's prediction, against the dataset label |
| latency | seconds per prompt for Stage C, on the RTX 3050 GPU and on CPU, batch size 1, greedy, median and p95 |

**Requirement:** Stage C under 3 s per prompt on the laptop GPU (median); CPU time reported too.

## 5. Validation of Stage C output (fallback rules)

Stage C's output is accepted only if all hold; otherwise the prompt keeps Stage B's IR:
1. it is a single JSON object with exactly the requested keys;
2. `task`, if requested, is non-empty and Stage A's ambiguous-reference detector (A05) finds no dangling reference in
   it, given the same context flag as the original prompt;
3. `output_format`, if non-null, is accepted by A02 (`detect_format_spec`); `constraints` is a list of strings;
4. `category`, if requested, is one of the five categories;
5. locked fields are never taken from Stage C's output.
