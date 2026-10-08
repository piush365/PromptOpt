# PromptOpt

A lightweight, self-hosted system that rewrites vague prompts into clear, structured, token-efficient prompts for LLMs, and then **measures whether the rewrite actually helps**.

Final-year Mini Project-I (7CS345), Walchand College of Engineering, Sangli. Results: [`evaluation/FINAL_RESULTS.md`](evaluation/FINAL_RESULTS.md).

## What it does

You type a prompt, pick the target LLM (GPT, Gemini or Claude), a category (auto-detect or one of five) and, optionally, an attachment type. PromptOpt returns the prompt rewritten for that model, explains every change, and can run the original and the optimized prompt side by side on a real model (**Compare**).

| Stage | What it does | How |
|---|---|---|
| **A: feature detection** | Task category, missing output format, missing constraints (length/tone/audience/language), filler, ambiguous references | spaCy + regex + Sentence-Transformers → `PromptFeatures` |
| **B: rule-based optimization** | Deterministic, individually testable rules B01–B15 (B09–B15: attachments). Every change is logged | Category rules only at ≥ 0.6 confidence, with a group-level fallback (B08) |
| **C: LoRA fallback** | Fills only what Stage B could not resolve (an ambiguous reference, or format/constraints when the category is unclear); the category itself is only suggested to the user | Qwen2.5-0.5B-Instruct + LoRA, validated output, falls back to Stage B |
| **IR + rendering** | One intermediate representation, rendered per target, same content everywhere | Claude XML tags · GPT `###` sections · Gemini labelled sections; tests round-trip every rendering |
| **Image mode** | Separate, explicitly chosen "Image generation" category for DALL-E, Nano Banana (Gemini image) and Stable Diffusion | Keeps the user's words; missing attributes become clickable suggestions |
| **Compare** | Original vs optimized prompt on the same model: answers, tokens (incl. reasoning), latency, sandbox tests for coding, optional blind judge | Groq / Cerebras gpt-oss now; Gemini with a key; GPT/Claude once keys are added |

Categories: `closed_qa`, `information_extraction`, `classification`, `summarization` (from Dolly-15k), `coding` (from CodeAlpaca-20k), and `other`.

## Architecture

Stage A (blue) detects what is missing, Stage B (green) fixes it with rules, Stage C (amber) fills only what the rules leave unresolved. Plain-English walkthrough: [`docs/HOW_IT_WORKS.md`](docs/HOW_IT_WORKS.md); all diagrams (Mermaid source, SVG, PNG): [`docs/diagrams/`](docs/diagrams/).

<!-- DIAGRAM:01_system_architecture:start -->
```mermaid
%%{init: {"theme": "base", "themeVariables": {"fontSize": "18px", "fontFamily": "Arial, Helvetica, sans-serif", "primaryColor": "#f3f4f6", "primaryBorderColor": "#4b5563", "lineColor": "#374151", "textColor": "#111827"}}}%%
flowchart LR
  UI["Web UI (HTML/JS)<br/>prompt · category · attachment · target LLM"]
  subgraph API["FastAPI backend"]
    direction LR
    A["Stage A<br/>feature detection"]
    B["Stage B<br/>rules → IR"]
    R{"Category or<br/>reference unresolved?"}
    C["Stage C<br/>LoRA fallback"]
    IR["Final IR"]
    REN["Renderers"]
    IMG["Image mode v2<br/>(chosen explicitly)"]
    A --> B --> R
    R -- "no · 93.6%" --> IR
    R -- "yes · 6.4%" --> C --> IR
    IR --> REN
  end
  UI --> A
  UI -. "image mode" .-> IMG
  REN --> CL["Claude<br/>XML tags"]
  REN --> GP["GPT<br/>### sections"]
  REN --> GE["Gemini<br/>plain labels"]
  CL & GP & GE --> CMP["Compare<br/>original vs optimized"]
  CMP --> PROV["Providers<br/>Groq · Cerebras · Gemini"]
  API <-- "history, results" --> DB[("Database<br/>SQLite / PostgreSQL<br/>10 tables")]
  classDef stageA fill:#dbeafe,stroke:#1d4ed8,stroke-width:2px,color:#1e3a8a
  classDef stageB fill:#dcfce7,stroke:#15803d,stroke-width:2px,color:#14532d
  classDef stageC fill:#fef3c7,stroke:#b45309,stroke-width:2px,color:#78350f
  classDef neutral fill:#f3f4f6,stroke:#4b5563,stroke-width:1px,color:#111827
  classDef result fill:#ffffff,stroke:#111827,stroke-width:2px,color:#111827
  class A stageA
  class B stageB
  class C stageC
  class R,IR,REN,IMG,CL,GP,GE,CMP,PROV,UI neutral
```

*System architecture*: [PNG](docs/diagrams/01_system_architecture.png) · [SVG](docs/diagrams/01_system_architecture.svg) · source [`01_system_architecture.mmd`](docs/diagrams/01_system_architecture.mmd)
<!-- DIAGRAM:01_system_architecture:end -->

<details><summary>Stage A internals</summary>

<!-- DIAGRAM:02_stage_a:start -->
```mermaid
%%{init: {"theme": "base", "themeVariables": {"fontSize": "18px", "fontFamily": "Arial, Helvetica, sans-serif", "primaryColor": "#f3f4f6", "primaryBorderColor": "#4b5563", "lineColor": "#374151", "textColor": "#111827"}}}%%
flowchart LR
  P["Prompt"] --> E["MiniLM embedding<br/>all-MiniLM-L6-v2"]
  P --> KW["Keyword cues<br/>(regex)"]
  E --> K["k-NN vote<br/>k = 25 train examples"]
  E --> H["Logistic head<br/>embedding + cues"]
  KW --> H
  K --> BL["Blend<br/>k-NN + cues + head"]
  KW --> BL
  H --> BL
  BL --> O{"Nearest example<br/>similarity < 0.3?"}
  O -- "yes" --> OT["'other' backstop"]
  O -- "no" --> CAT["Category + confidence<br/>(top score)"]
  OT --> CAT
  P --> DET
  subgraph DET["Rule detectors"]
    direction TB
    A2["A02 output format"]
    A3["A03 constraints"]
    A4["A04 filler / repeats"]
    A5["A05 ambiguous refs"]
  end
  CAT --> F["PromptFeatures<br/>accuracy 74.7% (test)"]
  DET --> F
  classDef stageA fill:#dbeafe,stroke:#1d4ed8,stroke-width:2px,color:#1e3a8a
  classDef stageB fill:#dcfce7,stroke:#15803d,stroke-width:2px,color:#14532d
  classDef stageC fill:#fef3c7,stroke:#b45309,stroke-width:2px,color:#78350f
  classDef neutral fill:#f3f4f6,stroke:#4b5563,stroke-width:1px,color:#111827
  classDef result fill:#ffffff,stroke:#111827,stroke-width:2px,color:#111827
  class E,KW,K,H,BL,OT,CAT,A2,A3,A4,A5 stageA
  class O neutral
  class P,F result
```

*Stage A internals*: [PNG](docs/diagrams/02_stage_a.png) · [SVG](docs/diagrams/02_stage_a.svg) · source [`02_stage_a.mmd`](docs/diagrams/02_stage_a.mmd)
<!-- DIAGRAM:02_stage_a:end -->

</details>

<details><summary>Stage B rule chain</summary>

<!-- DIAGRAM:03_stage_b_rules:start -->
```mermaid
%%{init: {"theme": "base", "themeVariables": {"fontSize": "18px", "fontFamily": "Arial, Helvetica, sans-serif", "primaryColor": "#f3f4f6", "primaryBorderColor": "#4b5563", "lineColor": "#374151", "textColor": "#111827"}}}%%
flowchart LR
  IN["Prompt +<br/>PromptFeatures"] --> B07
  subgraph CHAIN["Stage B rules, in run order"]
    direction LR
    B07["B07<br/>structure"] --> B01["B01<br/>filler"] --> B02["B02<br/>duplicates"] --> ATT["B09–B15<br/>attachment<br/>(if attached)"] --> B08["B08<br/>group fallback<br/>(below gate)"] --> B06
    subgraph GATE["only if confidence ≥ 0.6"]
      direction LR
      B06["B06<br/>labels"] --> B05["B05<br/>language"] --> B04["B04<br/>length"] --> B03["B03<br/>format"]
    end
  end
  B03 --> OUT["IR +<br/>unresolved list"]
  CHAIN -. "every change:<br/>rule · before · after" .-> LOG[("Change log<br/>transformations")]
  classDef stageA fill:#dbeafe,stroke:#1d4ed8,stroke-width:2px,color:#1e3a8a
  classDef stageB fill:#dcfce7,stroke:#15803d,stroke-width:2px,color:#14532d
  classDef stageC fill:#fef3c7,stroke:#b45309,stroke-width:2px,color:#78350f
  classDef neutral fill:#f3f4f6,stroke:#4b5563,stroke-width:1px,color:#111827
  classDef result fill:#ffffff,stroke:#111827,stroke-width:2px,color:#111827
  class B07,B01,B02,ATT,B08,B06,B05,B04,B03 stageB
  class IN,OUT result
  class LOG neutral
  style GATE fill:#bbf7d0,stroke:#15803d,stroke-width:2px,stroke-dasharray:6 4
  style CHAIN fill:#f0fdf4,stroke:#15803d
```

*Stage B rule chain*: [PNG](docs/diagrams/03_stage_b_rules.png) · [SVG](docs/diagrams/03_stage_b_rules.svg) · source [`03_stage_b_rules.mmd`](docs/diagrams/03_stage_b_rules.mmd)
<!-- DIAGRAM:03_stage_b_rules:end -->

</details>

<details><summary>B → C contract</summary>

<!-- DIAGRAM:04_b_to_c_contract:start -->
```mermaid
%%{init: {"theme": "base", "themeVariables": {"fontSize": "18px", "fontFamily": "Arial, Helvetica, sans-serif", "primaryColor": "#f3f4f6", "primaryBorderColor": "#4b5563", "lineColor": "#374151", "textColor": "#111827"}}}%%
sequenceDiagram
  autonumber
  box rgb(220,252,231) Stage B
    participant B as Stage B
  end
  box rgb(254,243,199) Stage C
    participant C as Stage C (LoRA)
    participant V as Validator
  end
  participant IR as Final IR
  participant U as User (UI)
  Note over B: routed if "task category" or<br/>"ambiguous reference" is unresolved<br/>(6.4% of test prompts)
  B->>C: JSON: prompt + IR, requested fields = null
  Note over B,C: every other field is locked
  C->>V: JSON with the requested keys only
  Note over V: checks: valid JSON · exact keys ·<br/>no ambiguous ref (A05) ·<br/>format stated (A02) · valid category
  alt passes (98.2% of test answers)
    V->>IR: patch only the requested fields
    opt category was requested
      V->>U: "uncertain": ask the user,<br/>pre-select Stage C's guess
    end
  else fails
    V->>IR: fallback: keep Stage B's IR
  end
```

*B → C contract*: [PNG](docs/diagrams/04_b_to_c_contract.png) · [SVG](docs/diagrams/04_b_to_c_contract.svg) · source [`04_b_to_c_contract.mmd`](docs/diagrams/04_b_to_c_contract.mmd)
<!-- DIAGRAM:04_b_to_c_contract:end -->

</details>

<details><summary>Stage C training</summary>

<!-- DIAGRAM:05_stage_c_training:start -->
```mermaid
%%{init: {"theme": "base", "themeVariables": {"fontSize": "18px", "fontFamily": "Arial, Helvetica, sans-serif", "primaryColor": "#f3f4f6", "primaryBorderColor": "#4b5563", "lineColor": "#374151", "textColor": "#111827"}}}%%
flowchart LR
  D[("Train split<br/>v1.2 final")] --> XA["Stage A<br/>cross-fitted, 5 folds"]
  XA --> SB["Stage B<br/>real run"]
  D --> PT["Targets parsed from<br/>optimized prompts"]
  SB --> EX["4,456 train examples<br/>routed + forced fields"]
  PT --> EX
  EX --> TR["LoRA training<br/>Qwen2.5-0.5B-Instruct<br/>r 16 · batch 16 · bf16"]
  TR --> ES{"Val loss<br/>every 50 steps"}
  ES -- "best 0.7047<br/>at step 550" --> AD["Adapter<br/>(step 550)"]
  ES -- "3 evals no gain" --> ST["Early stop<br/>at step 700 · 51 min"]
  classDef stageA fill:#dbeafe,stroke:#1d4ed8,stroke-width:2px,color:#1e3a8a
  classDef stageB fill:#dcfce7,stroke:#15803d,stroke-width:2px,color:#14532d
  classDef stageC fill:#fef3c7,stroke:#b45309,stroke-width:2px,color:#78350f
  classDef neutral fill:#f3f4f6,stroke:#4b5563,stroke-width:1px,color:#111827
  classDef result fill:#ffffff,stroke:#111827,stroke-width:2px,color:#111827
  class XA stageA
  class SB stageB
  class PT,EX,TR,ES,AD,ST stageC
  class D neutral
```

*Stage C training*: [PNG](docs/diagrams/05_stage_c_training.png) · [SVG](docs/diagrams/05_stage_c_training.svg) · source [`05_stage_c_training.mmd`](docs/diagrams/05_stage_c_training.mmd)
<!-- DIAGRAM:05_stage_c_training:end -->

</details>

<details><summary>Dataset pipeline</summary>

<!-- DIAGRAM:06_dataset_pipeline:start -->
```mermaid
%%{init: {"theme": "base", "themeVariables": {"fontSize": "18px", "fontFamily": "Arial, Helvetica, sans-serif", "primaryColor": "#f3f4f6", "primaryBorderColor": "#4b5563", "lineColor": "#374151", "textColor": "#111827"}}}%%
flowchart LR
  DO["Dolly-15k<br/>4 text categories"] --> S["Sample<br/>instructions"]
  CA["CodeAlpaca-20k<br/>coding"] --> S
  S --> G["LLM writes<br/>degraded + optimized<br/>(Groq / Cerebras)"]
  G --> Q["Automatic checks<br/>+ deterministic repair"]
  Q --> H["Human review<br/>3 raters × 170 rows<br/>295 of 330 accepted<br/>faculty: 19 of 20"]
  H --> L["LLM-assisted filter<br/>9 rows removed"]
  L --> F[("v1.2 final<br/>5,184 pairs")]
  F --> TRN["train 4,509"]
  F --> VAL["val 149"]
  F --> TST["test 482"]
  F --> BEN["benchmark 44"]
  classDef stageA fill:#dbeafe,stroke:#1d4ed8,stroke-width:2px,color:#1e3a8a
  classDef stageB fill:#dcfce7,stroke:#15803d,stroke-width:2px,color:#14532d
  classDef stageC fill:#fef3c7,stroke:#b45309,stroke-width:2px,color:#78350f
  classDef neutral fill:#f3f4f6,stroke:#4b5563,stroke-width:1px,color:#111827
  classDef result fill:#ffffff,stroke:#111827,stroke-width:2px,color:#111827
  class DO,CA,S,G,Q,H,L neutral
  class F,TRN,VAL,TST,BEN result
```

*Dataset pipeline*: [PNG](docs/diagrams/06_dataset_pipeline.png) · [SVG](docs/diagrams/06_dataset_pipeline.svg) · source [`06_dataset_pipeline.mmd`](docs/diagrams/06_dataset_pipeline.mmd)
<!-- DIAGRAM:06_dataset_pipeline:end -->

</details>

<details><summary>Evaluation flow</summary>

<!-- DIAGRAM:07_evaluation_flow:start -->
```mermaid
%%{init: {"theme": "base", "themeVariables": {"fontSize": "18px", "fontFamily": "Arial, Helvetica, sans-serif", "primaryColor": "#f3f4f6", "primaryBorderColor": "#4b5563", "lineColor": "#374151", "textColor": "#111827"}}}%%
flowchart LR
  T[("Test 482<br/>Benchmark 44")] --> V1["Degraded<br/>prompt"]
  T --> V2["Optimized<br/>Stage A + B"]
  V1 --> M["Target LLM<br/>gpt-oss-120b<br/>temperature 0"]
  V2 --> M
  M --> TOK["Tokens from<br/>API usage"]
  M --> J["Blind judge<br/>qwen3.8-27b"]
  M --> TS["Task success"]
  M --> SBX["Sandbox tests<br/>Python"]
  TOK --> R1["Tokens −39.2%<br/>CI 35.9–42.5%<br/>test · n 482"]
  J --> R2["Quality<br/>8.2 → 9.0<br/>bench · n 44"]
  TS --> R3["Success<br/>67% → 85%<br/>bench · n 44"]
  SBX --> R4["pass@1<br/>20.7% → 34.5%<br/>test · n 29"]
  R1 & R2 & R3 & R4 --> FR["FINAL_RESULTS.md"]
  classDef stageA fill:#dbeafe,stroke:#1d4ed8,stroke-width:2px,color:#1e3a8a
  classDef stageB fill:#dcfce7,stroke:#15803d,stroke-width:2px,color:#14532d
  classDef stageC fill:#fef3c7,stroke:#b45309,stroke-width:2px,color:#78350f
  classDef neutral fill:#f3f4f6,stroke:#4b5563,stroke-width:1px,color:#111827
  classDef result fill:#ffffff,stroke:#111827,stroke-width:2px,color:#111827
  class V1 neutral
  class V2 stageB
  class T,M,TOK,J,TS,SBX neutral
  class R1,R2,R3,R4,FR result
```

*Evaluation flow*: [PNG](docs/diagrams/07_evaluation_flow.png) · [SVG](docs/diagrams/07_evaluation_flow.svg) · source [`07_evaluation_flow.mmd`](docs/diagrams/07_evaluation_flow.mmd)
<!-- DIAGRAM:07_evaluation_flow:end -->

</details>

<details><summary>Database (10 tables)</summary>

<!-- DIAGRAM:08_database_er:start -->
```mermaid
%%{init: {"theme": "base", "themeVariables": {"fontSize": "18px", "fontFamily": "Arial, Helvetica, sans-serif", "primaryColor": "#f3f4f6", "primaryBorderColor": "#4b5563", "lineColor": "#374151", "textColor": "#111827"}}}%%
erDiagram
  users ||--o{ prompts : writes
  prompts ||--o| prompt_features : "Stage A"
  prompts ||--o{ optimization_results : "optimized as"
  optimization_results ||--o{ transformations : "change log"
  optimization_results ||--o{ renderings : "per target"
  optimization_results ||--o{ token_usage : "per target"
  rules |o--o{ transformations : "rule_id"
  lora_models |o--o{ optimization_results : "lora_model_id"
  users {
    int id PK
    string display_name
  }
  prompts {
    int id PK
    int user_id FK
    text original_text "PII scrubbed"
    datetime expires_at "30-day retention"
  }
  prompt_features {
    int id PK
    int prompt_id FK
    string task_type
    float confidence
    json missing_constraints
  }
  optimization_results {
    int id PK
    int prompt_id FK
    int lora_model_id FK
    json ir
    text optimized_text
    bool used_lora
  }
  transformations {
    int id PK
    int result_id FK
    int rule_id FK
    string stage
    text before_text
    text after_text
  }
  renderings {
    int id PK
    int result_id FK
    string target_llm
    text rendered_text
  }
  token_usage {
    int id PK
    int result_id FK
    string target_llm
    int original_input_tokens
    int optimized_input_tokens
  }
  rules {
    int id PK
    string code "B01-B15"
    bool enabled
  }
  lora_models {
    int id PK
    string base_model
    int lora_rank
  }
  evaluation_runs {
    int id PK
    string run_name
    string variant
    int input_tokens
    int output_tokens
    float quality_score
    bool task_success
  }
```

*Database (10 tables)*: [PNG](docs/diagrams/08_database_er.png) · [SVG](docs/diagrams/08_database_er.svg) · source [`08_database_er.mmd`](docs/diagrams/08_database_er.mmd)
<!-- DIAGRAM:08_database_er:end -->

</details>


## How to run

Tested from a fresh clone on Linux (Fedora 44) with Python 3.14. All commands run inside `backend/`.

### 1. Setup (CPU, no GPU needed)

```bash
git clone https://github.com/piush365/PromptOpt.git && cd PromptOpt/backend
python3.14 -m venv .venv && source .venv/bin/activate
pip install -r requirements-lock.txt     # exact versions; CPU torch; includes spaCy's en_core_web_sm
```

`requirements-lock.txt` pins every package as used for the results. `requirements.txt` lists the direct dependencies
with lower bounds, if you prefer a looser install (then also `pip install torch --index-url
https://download.pytorch.org/whl/cpu` first and `python -m spacy download en_core_web_sm` after). The first run
downloads the sentence-transformers model `all-MiniLM-L6-v2` (about 90 MB) from Hugging Face.

### 2. Database

```bash
python -m app.init_db                  # SQLite at backend/promptopt.db: 10 tables, rules seeded (safe to re-run)
```

PostgreSQL instead: set `DATABASE_URL` in `backend/.env` (see `backend/README.md`).

### 3. Optional: Stage A's trained category classifier

Without it, Stage A uses its keyword classifier, so everything runs but categories are less accurate on hard
prompts. The results (Stage A 74.7%) use the trained index, which you can get either way:

```bash
# a) download the exact index used for the results (GitHub release v1.0)
mkdir -p artifacts && curl -L -o artifacts/category_index.npz \
  https://github.com/piush365/PromptOpt/releases/download/v1.0/category_index.npz
# b) or build it from the dataset's train split (needs the dataset, see "Dataset and Stage C adapter")
python -m app.stage_a.build_index
```

### 4. Web app

```bash
uvicorn app.api:app                    # open http://127.0.0.1:8000  (FastAPI docs: /docs)
```

This runs **without Stage C**: Stage A + B + rendering, fully offline. When a prompt needs Stage C (try
"hey can you just summarize this article for me"), the page says Stage C is not installed and shows Stage B's result.

**With Stage C (LoRA, GPU recommended):** a second venv with CUDA torch, transformers and peft, plus the adapter:

```bash
python3.14 -m venv .venv-gpu && source .venv-gpu/bin/activate
pip install -r requirements-gpu-lock.txt                 # CUDA 13.2 build of torch; needs an NVIDIA driver
curl -L -o /tmp/stage_c_adapter.zip \
  https://github.com/piush365/PromptOpt/releases/download/v1.0/stage_c_adapter.zip
unzip /tmp/stage_c_adapter.zip -d artifacts/             # -> artifacts/stage_c_adapter/
uvicorn app.api:app                                      # GET /api/options now shows "stage_c": {"available": true, ...}
```

On that prompt the "Stage C" panel now shows Stage C's fields. The base model `Qwen/Qwen2.5-0.5B-Instruct` (about 1 GB) is downloaded from Hugging Face on first use. Without a
GPU it also runs on CPU (`STAGE_C_DEVICE=cpu`, about 5 s per routed prompt instead of 0.7 s). `STAGE_C_ENABLED=0`
switches Stage C off.

**In the browser:** type a prompt, choose target (Claude, GPT, Gemini) and category (auto or one of five), optionally
an attachment type, then *Optimize*. The page shows Stage A's findings, the rules that fired with before/after,
whether Stage C was used, the prompt for each target with its input tokens, and the history (kept 30 days). With an
API key, choose a model under *Run on* and press *Compare*. For image prompts, pick *Image generation*.

**API:** `POST /api/optimize`, `POST /api/compare`, `GET /api/compare/models`, `GET /api/history`,
`GET /api/history/{id}`, `POST /api/coding-tests`, `GET /api/options`.

### 5. Demo in the terminal (offline)

```bash
python -m app.demo --examples                       # five prompts, one per category: Stage A, each Stage B rule, Stage C routing
python -m app.demo "summarize this for me" --target claude
```

### 6. Tests

```bash
python -m pytest -q                    # about 700 tests, offline, no API calls (more with the dataset or TEST_POSTGRES_URL)
python -m app.freeze_check             # Stage A/B byte-identical to the frozen tag (needs the dataset and the index)
```

### 7. API keys (Compare, evaluation)

```bash
cp .env.example .env                   # .env is git-ignored; never commit keys
```

Then uncomment and fill in what you have:

| key | used for | where to get it |
|---|---|---|
| `GROQ_API_KEY` | Compare on gpt-oss-120b (Groq), evaluation judge | https://console.groq.com/keys (free tier) |
| `CEREBRAS_API_KEY` | Compare on gpt-oss-120b (Cerebras), evaluation target, coding test generation | https://cloud.cerebras.ai (free tier) |
| `GEMINI_API_KEY` | Compare on Gemini 2.5 Flash | https://aistudio.google.com/apikey (free tier) |

Restart `uvicorn` after editing `.env`. Calls stay within 70% of each free daily limit; usage is logged in
`data/*_usage.json`. GPT and Claude are listed as "add API key" (no client yet; future work). Compare's sandbox tests
for coding prompts need `bubblewrap` (`sudo dnf install bubblewrap`); without it, generated code is never run.

## Dataset and Stage C adapter

Neither is in git (`data/` and `backend/artifacts/` are git-ignored).

| what | where | how to use |
|---|---|---|
| PromptOpt Dataset v1.2 final (5,184 rows, 7 MB CSV) | Google Drive: [`promptopt_dataset_v1_2_final`](https://drive.google.com/drive/folders/1gk-38Y3gZv7TzwsW14pgfcqEcZciODZG) (access on request from the team; derived from Dolly-15k, CC BY-SA 3.0, and CodeAlpaca-20k) | put the folder in `data/` at the repo root: `data/promptopt_dataset_v1_2_final/promptopt_dataset_v1_2_final.csv` (or set `DATASET_DIR`) |
| Dataset description | [`docs/DATASET_CARD.md`](docs/DATASET_CARD.md) | |
| Stage C training data manifest (file hashes, row counts) | [`docs/stage_c_data_manifest.json`](docs/stage_c_data_manifest.json); also attached to the release | rebuild the data with `python -m app.stage_c.data` (needs the dataset) |
| Stage C LoRA adapter (Qwen2.5-0.5B-Instruct, r 16, 45 MB) | [GitHub release v1.0](https://github.com/piush365/PromptOpt/releases/tag/v1.0): `stage_c_adapter.zip` | unzip into `backend/artifacts/` (see step 4) |
| Stage A category index | GitHub release v1.0: `category_index.npz` | `backend/artifacts/category_index.npz` (see step 3) |

Degraded -> optimized prompt pairs built from Dolly-15k and CodeAlpaca-20k, split into train/val/test/benchmark with
no instruction shared across splits; human-validated sample and LLM-assisted filter.

## Results and reports

[`evaluation/FINAL_RESULTS.md`](evaluation/FINAL_RESULTS.md) is the summary; the project report is
[`docs/PROJECT_REPORT.md`](docs/PROJECT_REPORT.md), the demo walkthrough [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md)
and a 10-minute cheat sheet [`docs/EXPLAIN_IN_10_MIN.md`](docs/EXPLAIN_IN_10_MIN.md).
Every evaluation command is listed in FINAL_RESULTS section "Reproduce" and in each report's header.

## Repo layout

```
backend/app/         Stage A/B/C, IR + rendering, pipeline, API + web UI (static/), DB layer,
                     coding/ (sandbox, tests), image/ (image mode), compare/ (providers), evaluation/
backend/tests/       offline test suite
docs/                dataset card, Stage C plan, coding tests, category templates, milestone review
evaluation/          all reports; FINAL_RESULTS.md is the summary
notebooks/           Stage C training notebook (Colab); dataset_prep/: dataset EDA and annotation sheets
```

More detail on the backend and database: [`backend/README.md`](backend/README.md).
