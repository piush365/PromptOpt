# Chapter 4 of the final report: methodology, organised by the SDLC phases that were followed.
# Sources: docs/documentation/03-08, docs/STAGE_C_PLAN.md, evaluation/FINAL_RESULTS.md; the review example from the
# real pipeline (Stage A scores, Stage B steps, Stage C answer) and Compare on gpt-oss-120b.

EX = "\u201chey can you just tell me if this review is good or bad\u201d"

METHODOLOGY = ("Methodology", [
    ("p", "This chapter describes how PromptOpt was built, phase by phase. Each phase of the software development life "
          "cycle (SDLC) is described with its activities, the decisions taken and their basis, and the output it handed "
          "to the next phase. Throughout the chapter one running example is followed through the system: the prompt "
          + EX + " typed together with the review \u201cThe battery lasts two days and the camera is great, but the "
          "phone heats up while gaming.\u201d"),

    # ------------------------------------------------------------------ 4.1
    ("h2", "4.1 Development approach (SDLC)"),
    ("p", "The project followed an iterative waterfall model: the phases run in order, each with a clear output, but "
          "two feedback loops are allowed. Results on the validation split feed back into implementation (rule "
          "wording, thresholds, the Stage C policy), and problems found during implementation feed back into dataset "
          "preparation (the v1.1 repair and the v1.2 expansion). A strict rule separated tuning from testing: every "
          "decision was taken on the validation split, the code was then frozen, and the test split was run only once."),
    ("fig", "diag_sdlc.png", "SDLC phases followed in the project, with the two feedback loops", 6.5),
    ("tbl", "SDLC phases: activities and outputs", ["Phase", "Main activities", "Output"],
     [["1. Requirement analysis", "customer survey, literature review, research gap, functional and non-functional requirements (SRS)", "requirements, scope, five fixed categories"],
      ["2. Dataset preparation", "source selection, cleaning, sampling, LLM generation of prompt pairs, automatic checks, repair, splits, human validation", "PromptOpt Dataset v1.2 final (5,184 pairs)"],
      ["3. Design", "architecture, intermediate representation (IR), B-to-C contract, database schema (10 tables), API", "design documents, diagrams"],
      ["4. Implementation", "Stage A, Stage B rules, Stage C data and LoRA training, renderers, FastAPI back end, React UI", "working system"],
      ["5. Validation", "tuning on the validation split only; freeze of the code; freeze check", "frozen pipeline"],
      ["6. Testing", "unit, integration and system tests; evaluation on the test split (once) and the benchmark", "test reports, final numbers"],
      ["7. Deployment", "service on the laptop reachable on the local network; release v1.0 with the trained artefacts", "running application"]],
     [1.6, 3.4, 1.5]),
    ("p", "The work was planned as ten tasks over four months, from problem identification and customer connect in "
          "July to the final demo and documentation in October. Requirement and design tasks overlap in July and "
          "August; prototype development, model development (rules and LoRA) and evaluation follow from September. "
          "All ten tasks are done."),
    ("fig", "gantt.png", "Project schedule (Gantt chart): all ten tasks done", 6.3),

    # ------------------------------------------------------------------ 4.2
    ("h2", "4.2 Phase 1: Requirement analysis"),
    ("p", "The requirement phase combined three inputs: the customer survey (Section 1.2), the literature review and "
          "research gap (Sections 1.3 and 1.4), and the constraints of the environment the system had to run in. The "
          "requirements were written down in a Software Requirements Specification (SRS) before any code was written."),
    ("h3", "Functional requirements"),
    ("tbl", "Functional requirements", ["ID", "Requirement"],
     [["FR1", "The user enters any prompt and optionally pastes the text the prompt is about."],
      ["FR2", "The user selects a target LLM (GPT, Gemini or Claude), a category (one of five, or auto-detect) and optionally an attachment type."],
      ["FR3", "The system detects missing parts of the prompt and shows them to the user."],
      ["FR4", "The system adds only what is missing, keeps the user's data verbatim and shows every change with the text before and after it."],
      ["FR5", "A user-selected category overrides the automatic one; when the system is unsure, it asks the user."],
      ["FR6", "The optimized prompt is shown in the layout of the chosen target LLM, with the number of input tokens."],
      ["FR7", "Token usage analysis (Compare in the developer view) sends the original and the optimized prompt to the same real model and shows both answers, tokens and time."],
      ["FR8", "A history lists, searches, shows and deletes past prompts; prompts expire after 30 days."]],
     [0.7, 5.8]),
    ("h3", "Non-functional requirements"),
    ("tbl", "Non-functional requirements", ["ID", "Requirement", "How it was met"],
     [["NFR1", "Self-hosted and offline optimizer", "Stages A, B and C run locally; no API is needed to optimize"],
      ["NFR2", "Explainable", "every rule is a small pure function; every change is logged and shown"],
      ["NFR3", "Fast", "Stage A on CPU in milliseconds; Stage C under 3 s per prompt on the laptop GPU"],
      ["NFR4", "Privacy", "e-mail addresses and phone numbers are removed before storage; prompts expire after 30 days"],
      ["NFR5", "Reliable storage", "one database commit per request; a failure stores nothing"],
      ["NFR6", "Honest measurement", "tuning on the validation split only; the test split run once; the answering model always named"],
      ["NFR7", "Testable", "every rule and detector has unit tests; the whole suite runs without network"]],
     [0.7, 2.0, 3.8]),
    ("h3", "Constraints that shaped the design"),
    ("tbl", "Constraints and their consequences", ["Constraint", "Consequence in the design"],
     [["One laptop GPU with 4 GB of memory (NVIDIA RTX 3050) and a CPU-only default install",
       "Stage C uses a 0.5-billion-parameter model with LoRA; the application also runs fully without it"],
      ["Only free API tiers (Groq: 200,000 tokens per day per model; Cerebras: 1,000,000)",
       "every LLM call is recorded in a rolling 24-hour ledger; tools stop at 70% of a limit and resume the next day"],
      ["Examiners must be able to follow every change", "rules are small functions; every change is logged with before/after text"],
      ["Results must not be tuned on the test data", "split discipline, a frozen code version and a byte-level freeze check"],
      ["Privacy of users' prompts", "personal data removed before anything is stored; 30-day retention"]],
     [3.0, 3.5]),

    # ------------------------------------------------------------------ 4.3 dataset
    ("h2", "4.3 Phase 2: Dataset preparation"),
    ("p", "No public dataset pairs a vague prompt with a clear version of the same request, so we built one: PromptOpt "
          "Dataset. Each row is a pair of a degraded prompt (how a rushed, non-expert user types a request) and an "
          "optimized prompt (the same task stated clearly, with an explicit output format and only helpful "
          "constraints), together with the original instruction, the context passage and the reference answer of the "
          "source row. The dataset is used to train Stage A's classifier, to build Stage C's training data, and to "
          "evaluate every stage. It is stored outside the database and outside git."),
    ("fig", "diag_dataset.png", "Dataset pipeline: from Dolly-15k and CodeAlpaca-20k to PromptOpt Dataset v1.2 final", 6.5),
    ("h3", "4.3.1 Sources"),
    ("tbl", "Source datasets", ["Source", "Rows", "Used for"],
     [["Databricks Dolly-15k [8]", "15,011", "closed_qa (1,773), information_extraction (1,506), classification (2,136), summarization (1,188); brainstorming and creative writing as \u201cother\u201d examples for Stage A only"],
      ["CodeAlpaca-20k [9]", "20,022", "coding"]],
     [1.8, 0.8, 3.9]),
    ("p", "Every source row keeps a permanent identifier (its row number in the original file, e.g. dolly-4205), "
          "assigned before any filtering, so a row can always be traced back to its source even after the dataset is "
          "rebuilt."),
    ("h3", "4.3.2 Cleaning"),
    ("num", [
        "Category filter: Dolly rows of the four categories with a non-empty instruction and response.",
        "De-duplication on the normalised instruction and context (lower case, whitespace collapsed); the first copy is kept.",
        "Removal of reference answers that are extremely long for their category (rule below).",
        "Removal of e-mail addresses and phone numbers with the same patterns the application uses.",
        "CodeAlpaca: de-duplication, and outputs of fewer than three words dropped (they are not code).",
        "Attributes added to every row: whether it has a context, whether it states a format, word counts, and a "
        "length bucket (short, medium or long: the tertile of instruction + context length within the category).",
    ]),
    ("p", "A Dolly row \u2018i\u2019 in category \u2018c\u2019 is dropped when its reference answer is longer than the "
          "category's cut-off:"),
    ("eq", "cutoff(c) = median(w) + 3 \u00b7 \u03c3(w),   drop row i if w(i) > cutoff(c)"),
    ("p", "where \u2018w\u2019 is the number of words in the reference answer and \u03c3 the sample standard deviation. "
          "The median is a robust centre for right-skewed word counts, and three standard deviations is the classical "
          "outlier tail; the rule removes a few very long answers that would otherwise dominate the evaluation."),
    ("tbl", "Answer-length cut-offs per category", ["Category", "Rows after de-dup", "Median words", "\u03c3", "Cut-off", "Dropped"],
     [["closed_qa", "1,759", "17", "48.3", "162.0", "36"], ["information_extraction", "1,501", "19", "105.1", "334.4", "45"],
      ["classification", "2,133", "14", "36.4", "123.3", "37"], ["summarization", "1,186", "54", "154.5", "517.5", "10"]],
     [1.9, 1.1, 1.0, 0.7, 0.8, 0.8]),
    ("h3", "4.3.3 Generation of prompt pairs"),
    ("p", "For each sampled source row, an LLM (gpt-oss-120b or gpt-oss-20b on Groq and Cerebras, qwen3.8-27b as a "
          "fallback) wrote both prompts in one JSON answer. The instructions to the generator describe the degraded "
          "prompt (short, casual, no format, may refer to \u201cthis\u201d) and the optimized prompt, with requirements "
          "per category: closed_qa answers only from the text and states a length; extraction states what to extract "
          "and the output structure; classification lists the labels and ends with the items; summarization states a "
          "length and a focus; coding names the language, behaviour, inputs and outputs. A data rule requires that "
          "any data written inside the instruction (items to classify, code, numbers, the named subject) appears "
          "verbatim in both prompts. Settings: temperature 0.7 for variety, JSON output, context truncated to 1,000 "
          "characters, up to three attempts per row."),
    ("p", "To use the free daily quotas efficiently, five rows were sent per call (one shared system prompt). On the "
          "same ten rows this reduced the cost from about 1,070 to 400 tokens per row with checks as good or better; "
          "every reply echoes the row's identifier and results are matched only by identifier, never by position."),
    ("h3", "4.3.4 Automatic quality checks"),
    ("p", "Similarity between two texts is the cosine of their all-MiniLM-L6-v2 embeddings; since the embeddings are "
          "normalised to length 1, it is their dot product:"),
    ("eq", "sim(a, b) = e(a) \u00b7 e(b) = cos \u03b8,  between \u22121 and 1"),
    ("p", "A generated pair is rejected if any of the following flags is set:"),
    ("tbl", "Automatic quality checks on every generated pair", ["Flag", "Condition", "Why"],
     [["degraded drifted", "sim(original, degraded) < 0.45", "the degraded prompt must ask the same thing"],
      ["not degraded", "degraded equals the original (or sim > 0.98) and the original stated a format", "nothing was degraded"],
      ["degraded keeps a format", "the format patterns match the degraded prompt", "degraded prompts have no format"],
      ["degraded longer", "words(degraded) \u2212 words(data) > 1.25 \u00d7 words(original) + 3", "degraded prompts are short"],
      ["optimized drifted", "sim(original, optimized) < 0.35, or no shared key word and sim < 0.50", "the optimized prompt keeps the task"],
      ["coding target not code", "coding row whose optimized prompt names no code word", "\u2013"],
      ["optimized too long", "words(optimized) \u2212 words(data) > 120", "over-specification"]],
     [1.5, 3.1, 1.9]),
    ("h3", "4.3.5 Repair of dropped data (v1 to v1.1)"),
    ("p", "The first generation often dropped the literal data of the instruction. For example, the original "
          "\u201cIdentify which instrument is string or percussion: Sheker, Taishogoto\u201d became an optimized prompt "
          "that asked to classify \u201ceach listed instrument\u201d without listing them, so it could not be answered. "
          "A deterministic repair finds the data in the original instruction (an item list, code on later lines, an "
          "arithmetic expression), decides whether a prompt lost it, and appends it verbatim. For non-classification "
          "prompts, data is considered lost when less than half of its content words are still present:"),
    ("eq", "coverage = |content words of data also in prompt| / |content words(data)|,   lost if coverage < 0.5"),
    ("p", "Optimized prompts that stopped naming the instruction's subject (\u201cthe temple\u201d instead of "
          "\u201cDoleshwor Mahadeva temple\u201d) were sent back to the generator for a minimal edit, accepted only if "
          "the edit names every lost subject and adds at most 12 words. Result: 349 optimized and 20 degraded prompts "
          "repaired, 75 subjects restored, 9 rows removed because their data existed nowhere; every change is "
          "written to a log file."),
    ("h3", "4.3.6 Expansion to about 1,000 rows per category (v1.2)"),
    ("p", "To reach about 1,000 rows per category, new rows were generated only from source rows never used before. "
          "The number to sample in category \u2018c\u2019 accounts for the share of rows that survive the checks:"),
    ("eq", "needed(c) = max(0, 1000 \u2212 rows(c)),   to_sample(c) = min(unused(c), ceil(needed(c) / rate(c) \u00d7 1.05))"),
    ("p", "where rate(c) is the survival rate of the first generation and 1.05 adds a 5% margin. Rows were drawn by "
          "stratified sampling over length bucket and has-context, with the largest-remainder method so that every "
          "stratum keeps its share."),
    ("tbl", "Expansion plan per category", ["Category", "v1.1 rows", "Survival rate", "Needed", "Unused source rows", "Sampled"],
     [["closed_qa", "425", "0.850", "575", "1,223", "711"], ["information_extraction", "449", "0.898", "551", "956", "645"],
      ["classification", "474", "0.948", "526", "1,596", "583"], ["summarization", "436", "0.872", "564", "676", "676 (all)"],
      ["coding", "472", "0.944", "528", "18,524", "588"], ["all", "", "", "", "", "3,203"]],
     [1.9, 0.9, 1.0, 0.8, 1.2, 0.9]),
    ("p", "Of the 3,203 generated pairs, 2,983 passed the checks and 2,972 were added after repair, giving v1.2 with "
          "5,228 rows."),
    ("h3", "4.3.7 Splits"),
    ("p", "Rows are split by original instruction, so the same instruction (or a paraphrase of it) never appears in two "
          "splits. Each category has 100 test rows, 30 validation rows and 10 benchmark rows; the rest is training data. "
          "The extra test rows of v1.2 came only from new rows that no tuning had seen."),
    ("tbl", "Purpose of each split", ["Split", "Used for", "Who may look at it"],
     [["train", "Stage A's index and classifier head; Stage C's training data", "every phase"],
      ["validation", "every tuning decision (thresholds, rule wording, Stage C policy, judge wording)", "development"],
      ["test", "the final offline numbers of Stage A, B and C and the full token evaluation", "run once, after the code was frozen"],
      ["benchmark", "the final run with a real model and a blind judge", "run once"]],
     [1.1, 3.6, 1.8]),
    ("h3", "4.3.8 Human validation"),
    ("p", "The three team members and the faculty guide rated rows with five yes/no questions. A row is accepted only "
          "if all five answers are yes."),
    ("num", [
        "Q1: the degraded prompt asks for the same task as the original instruction.",
        "Q2: the degraded prompt is a realistic, vaguer version a real user might type.",
        "Q3: the optimized prompt keeps the task and intent, without adding facts, answers or unwanted requirements, and without dropping data.",
        "Q4: the optimized prompt is clearer and better specified than the degraded one.",
        "Q5: the category label is correct.",
    ]),
    ("tbl", "Rating design", ["Who", "Rows", "Purpose"],
     [["all three team members", "90 overlap rows (18 per category)", "agreement between raters"],
      ["each team member alone", "60 extra rows (test and benchmark splits and borderline rows first)", "filtering bad pairs"],
      ["each team member alone", "20 rows of the new v1.2 generation", "human check of the new rows"],
      ["faculty guide", "20 of the overlap rows", "independent check (never decides a row)"]],
     [1.8, 3.0, 1.7]),
    ("p", "Overlap rows are decided by majority vote per question (2 of 3); other rows by their single rater. In total "
          "330 distinct rows were rated: 295 accepted and 35 rejected. The faculty guide accepted 19 of 20 rows."),
    ("p", "Agreement on the overlap rows is reported with Fleiss' kappa [14], Gwet's AC1 [12] and the raw agreement. "
          "With \u2018n\u2019 = 3 raters and n(i,j) the number of raters giving answer j to item i, the agreement on "
          "item i and the mean over the I items are"),
    ("eq", "P(i) = [\u03a3 n(i,j)\u00b2 \u2212 n] / [n(n \u2212 1)],     P\u0304 = (1/I) \u03a3 P(i)"),
    ("p", "Kappa compares P\u0304 with the agreement expected by chance from the answer frequencies p(j), while AC1 uses "
          "a chance term that stays small when one answer dominates:"),
    ("eq", "\u03ba = (P\u0304 \u2212 P\u2091) / (1 \u2212 P\u2091),  P\u2091 = \u03a3 p(j)\u00b2;     AC1 = (P\u0304 \u2212 P\u2091\u02b9) / (1 \u2212 P\u2091\u02b9),  P\u2091\u02b9 = 2\u03c0(1 \u2212 \u03c0)"),
    ("p", "Worked example for Q1: 81 items were answered yes by all three raters, 8 split 2-1 and 1 split 1-2, with "
          "260 yes answers out of 270. Then P\u0304 = (81 + 9/3)/90 = 0.933, p(yes) = 0.963, P\u2091 = 0.963\u00b2 + "
          "0.037\u00b2 = 0.929, so \u03ba = (0.933 \u2212 0.929)/(1 \u2212 0.929) = 0.065, while AC1 = (0.933 \u2212 "
          "0.071)/(1 \u2212 0.071) = 0.928. Because almost every answer is yes, the chance term of kappa approaches 1 "
          "and a handful of disagreements decides its value; this is the known kappa paradox [13]. We therefore report "
          "kappa and AC1 together."),
    ("tbl", "Agreement of the three team raters on the 90 overlap rows", ["Question", "% yes", "All three agree", "Fleiss' \u03ba", "Gwet's AC1"],
     [["Q1 degraded asks the same task", "96.3%", "90.0%", "0.065", "0.928"],
      ["Q2 degraded is realistic", "96.3%", "88.9%", "\u22120.038", "0.920"],
      ["Q3 optimized keeps the intent", "96.3%", "90.0%", "0.065", "0.928"],
      ["Q4 optimized is better", "98.1%", "94.4%", "\u22120.019", "0.962"],
      ["Q5 category is correct", "98.1%", "94.4%", "\u22120.019", "0.962"],
      ["accept (all five yes)", "86.3%", "67.8%", "0.092", "0.719"]],
     [2.4, 0.8, 1.2, 1.0, 1.1]),
    ("p", "After the human review, an LLM-assisted filter re-read the 90 overlap rows as a strict reviewer, without "
          "seeing the human answers. Only rows where the optimized prompt adds facts, leaks the answer, sets an "
          "impossible constraint or changes the task were removed: 9 rows. The filter never overrides a human answer "
          "and is not part of any agreement statistic."),
    ("h3", "4.3.9 Final dataset"),
    ("p", "PromptOpt Dataset v1.2 final = 5,228 rows \u2212 35 rows rejected by the raters \u2212 9 rows removed by the "
          "filter = 5,184 rows."),
    ("tbl", "PromptOpt Dataset v1.2 final: rows per category and split", ["Category", "Train", "Validation", "Test", "Benchmark", "Total"],
     [["closed_qa", "951", "29", "99", "10", "1,089"], ["information_extraction", "867", "30", "93", "10", "1,000"],
      ["classification", "906", "30", "98", "8", "1,042"], ["summarization", "920", "30", "94", "6", "1,050"],
      ["coding", "865", "30", "98", "10", "1,003"], ["all", "4,509", "149", "482", "44", "5,184"]],
     [1.9, 0.9, 1.0, 0.8, 1.0, 0.9]),
    ("p", "Known limitations of the dataset: the optimized prompts are written by an LLM and only 330 rows were rated by "
          "people; Dolly's category labels are noisy in the question / extraction / summary group; and some CodeAlpaca "
          "reference answers are wrong (these are listed and excluded from the evaluation summaries)."),

    # ------------------------------------------------------------------ 4.4 design
    ("h2", "4.4 Phase 3: System design"),
    ("p", "The design starts from the user's request and follows it through three stages that each do one job. "
          "Figure 4.4 shows the running example as it passes through the whole system; the rest of this chapter "
          "explains each block."),
    ("fig", "diag_story.png", "The review example through every stage of PromptOpt", 6.5),
    ("p", "Stage A reads the prompt and writes down what is missing; it never changes the prompt. Stage B turns the "
          "prompt into a structured intermediate representation (IR) and applies deterministic rules to it. Stage C, "
          "a small fine-tuned model, is called only when Stage B leaves the task category or an ambiguous reference "
          "unresolved. The final IR is written out by a renderer for the chosen LLM, and Compare can run the original "
          "and the optimized prompt on the same real model."),
    ("fig", "diag_architecture.png", "System architecture, with the review example under each component", 6.5),
    ("h3", "4.4.1 The intermediate representation (IR)"),
    ("p", "All stages work on one model-agnostic data structure instead of editing a string. Rules return a new IR "
          "instead of changing the old one, so every change is small, testable and can be logged."),
    ("tbl", "Fields of the intermediate representation", ["Field", "Meaning", "Review example after Stage C"],
     [["task", "what to do, in the user's words, cleaned", "Tell me if this review is good or bad."],
      ["context / context_ref", "data moved out of the prompt; where the material is", "the pasted review (separate)"],
      ["constraints", "length, programming language, grounding", "(none)"],
      ["requirements", "task-specific rules: allowed labels, how to use an attachment", "(none)"],
      ["output_format", "how to lay out the answer", "Provide only the label."],
      ["attachment", "attachment type and optional file name", "none"],
      ["category / category_source", "category used and where it came from", "unresolved: user asked to confirm \u201cclassification\u201d"],
      ["target_llm", "the user's target", "GPT"],
      ["unresolved", "what Stage B could not fix", "task category (waiting for the user)"]],
     [1.5, 2.5, 2.5]),
    ("h3", "4.4.2 Design decisions"),
    ("tbl", "Main design decisions and their basis", ["Decision", "Basis"],
     [["Rules first, model last", "rules are cheap, explainable and testable; a model is used only where rules cannot decide (6.4% of test prompts)"],
      ["Category rules only above a confidence of 0.6", "a wrong format is worse than none; on the validation split Stage A was right 77-96% of the time above 0.6 and only 47-59% between 0.4 and 0.6"],
      ["Stage C fills only requested fields", "everything else is locked, so the model cannot damage what the rules already fixed"],
      ["Stage C's category is only a suggestion", "on validation prompts routed for the category, Stage A was right 40% and Stage C 30% of the time: neither is reliable, so the user decides"],
      ["One IR, several renderers", "the content is decided once; only the layout differs per model, and tests prove no field is lost"],
      ["One repository module and one commit per request", "a failure half-way stores nothing; privacy rules are applied in one place"]],
     [2.2, 4.3]),

    # ------------------------------------------------------------------ 4.5 implementation: Stage A
    ("h2", "4.5 Phase 4: Implementation of Stage A (feature detection)"),
    ("p", "Stage A turns the raw prompt into a PromptFeatures object. It combines a learned classifier for the task "
          "category with rule-based detectors for everything else."),
    ("fig", "diag_stage_a.png", "Stage A: every arrow is labelled with what flows along it", 6.5),
    ("tbl", "Output of Stage A for the review example", ["Field", "Meaning", "Review example"],
     [["task_type, confidence", "the category with the highest score, and that score", "summarization, 0.52"],
      ["category_scores", "the score of every category (they sum to 1)", "summarization 0.52, classification 0.35, other 0.09, extraction 0.03, coding 0.01, closed_qa 0.00"],
      ["has_format_spec (A02)", "an output format is stated", "no"],
      ["missing_constraints (A03)", "constraints relevant to the category that are not stated", "length, audience, tone"],
      ["redundant_phrases (A04)", "filler and repeated text", "\u201chey\u201d, \u201ccan you\u201d, \u201cjust\u201d"],
      ["ambiguous_refs (A05)", "references to material that is not there", "none (the review is pasted)"],
      ["has_context", "material to work on was pasted or embedded", "yes"]],
     [1.7, 2.4, 2.4]),
    ("h3", "4.5.1 Sentence embedding and the labelled index"),
    ("p", "The prompt is encoded by all-MiniLM-L6-v2, a six-layer transformer that maps a sentence to a vector of 384 "
          "numbers, normalised to length 1. The model is small (about 90 MB) and fast on a CPU: 7.9 ms per prompt on "
          "average. The labelled index is built once from the training split only: for each of the 4,509 training "
          "rows, its degraded prompt and its original instruction, labelled with the row's category (9,018 texts), "
          "plus 500 out-of-scope instructions (Dolly brainstorming and creative writing) labelled \u201cother\u201d. "
          "Validation and test prompts never enter the index."),
    ("h3", "4.5.2 k-nearest-neighbour vote"),
    ("p", "For the query vector q, the similarity to every index vector e(i) is s(i) = e(i) \u00b7 q. The k = 25 most "
          "similar examples vote for their category, each with a weight that falls quickly with its distance from the "
          "nearest one (a softmax with temperature \u03c4 = 0.05):"),
    ("eq", "w(i) = exp((s(i) \u2212 s\u2098\u2090\u2093) / \u03c4),     knn(c) = \u03a3 w(i) over neighbours of category c / \u03a3 w(i) over all 25"),
    ("tbl", "How a neighbour's weight falls with its distance (\u03c4 = 0.05)", ["s\u2098\u2090\u2093 \u2212 s(i)", "0.01", "0.02", "0.05", "0.10", "0.20"],
     [["weight w(i)", "0.819", "0.670", "0.368", "0.135", "0.018"]], [1.6, 0.9, 0.9, 0.9, 0.9, 0.9]),
    ("h3", "4.5.3 Keyword cues"),
    ("p", "Hand-written regular expressions with weights add explicit evidence. A cue counts once if it matches "
          "anywhere in the prompt; the raw score of a category is the sum of its matching weights, normalised over "
          "the categories."),
    ("tbl", "Keyword cues per category (weights in brackets)", ["Category", "Cues"],
     [["coding", "programming terms such as function, script, array, regex (1.0); a language name such as Python, Java (1.5); \u201cwrite/create/build \u2026 function/program/script/query\u201d (2.0)"],
      ["summarization", "summary, summarize, TL;DR, sum up, recap, gist, condense (3.0); \u201cmain/key points\u201d (1.5)"],
      ["classification", "classify, categorize, label, sort into, sentiment (3.0); \u201cwhich of these is\u201d (1.5); \u201ctell me which\u201d (2.0); \u201cX or Y:\u201d (1.0)"],
      ["information_extraction", "extract (3.0); \u201clist/pull out/find \u2026 names/dates/places\u201d (2.0); \u201cmentioned in\u201d (1.5); \u201clist all\u201d (1.5)"],
      ["closed_qa", "starts with a question word (1.5); ends with \u201c?\u201d (1.0); \u201caccording to the text\u201d (1.5)"]],
     [1.7, 4.8]),
    ("h3", "4.5.4 Logistic-regression head"),
    ("p", "A multinomial logistic regression is trained on the same index: its input is the 384-number embedding plus "
          "six keyword features (five normalised cue scores and whether the prompt ends with a question mark), and it "
          "outputs a probability for each of the six categories:"),
    ("eq", "p(c | x) = exp(w(c) \u00b7 x + b(c)) / \u03a3 exp(w(c\u02b9) \u00b7 x + b(c\u02b9)),     x has 390 numbers"),
    ("p", "It is trained with L2 regularisation (C = 4.0, chosen by 5-fold cross-validation on the training split) and "
          "balanced class weights, so that the 500 \u201cother\u201d examples count as much in total as about 1,800 "
          "examples of each task category."),
    ("h3", "4.5.5 Confidence calculation"),
    ("p", "The confidence of Stage A is the final score of the winning category. The final score of every category "
          "combines the three signals:"),
    ("eq", "blend(c) = 0.7 \u00b7 knn(c) + 0.3 \u00b7 kw(c)   (if any keyword cue fired; otherwise blend(c) = knn(c))"),
    ("eq", "score(c) = 0.5 \u00b7 blend(c) + 0.5 \u00b7 p(c | x),     confidence = max over c of score(c)"),
    ("p", "If even the nearest example is not similar (s\u2098\u2090\u2093 < 0.3), nothing in the data looks like the "
          "prompt: every score is multiplied by keep = s\u2098\u2090\u2093 / 0.6 and \u201cother\u201d receives the rest, "
          "so \u201cother\u201d always wins. The weights (0.7 / 0.3 and 0.5 / 0.5), k = 25, \u03c4 = 0.05 and the 0.3 "
          "threshold were tuned on the validation split. In 5-fold cross-validation on the training split the blend "
          "reached 72.9% accuracy, against 69.3% for the k-NN vote alone and 70.4% for the head alone."),
    ("p", "Worked example. For the review prompt no keyword cue fires (\u201cgood or bad\u201d is not followed by a "
          "colon or question mark), so blend(c) = knn(c). The table shows the calculation; Figure 4.7 shows it as a "
          "chart."),
    ("tbl", "Confidence calculation for the review example", ["Category", "k-NN vote", "Head", "0.5 \u00b7 k-NN + 0.5 \u00b7 head"],
     [["closed_qa", "0.000", "0.001", "0.001"], ["information_extraction", "0.050", "0.003", "0.026"],
      ["classification", "0.690", "0.008", "0.349"], ["summarization", "0.181", "0.858", "0.520"],
      ["coding", "0.019", "0.010", "0.014"], ["other", "0.060", "0.120", "0.090"]],
     [2.0, 1.3, 1.3, 1.9]),
    ("p", "The similar training prompts mostly vote for classification (0.69), while the head, which learned that "
          "\u201ctell me \u2026 this review\u201d often asks for a summary, prefers summarization (0.86). The blend "
          "picks summarization with a confidence of 0.52. Because 0.52 is below the 0.6 gate, Stage B will not trust "
          "this category, which is the right decision here: the prompt is actually a classification request. The "
          "nearest example has a similarity of 0.53, above 0.3, so the \u201cother\u201d backstop does not apply."),
    ("fig", "diag_confidence.png", "Stage A scores for the review example: k-NN vote, head and final score against the 0.6 gate", 6.2),
    ("p", "The confidence is a blended score, not a calibrated probability, which is why the 0.6 gate was chosen "
          "empirically on the validation split rather than derived from it."),
    ("h3", "4.5.6 Rule-based detectors (A02-A05)"),
    ("tbl", "Rule-based detectors of Stage A", ["Detector", "What it finds", "Examples of patterns"],
     [["A02 output format (26 patterns)", "an explicitly stated output format", "JSON, a table, a bulleted list, \u201cin 3 sentences\u201d, \u201conly the label\u201d, \u201cyes or no\u201d"],
      ["A03 constraints", "length, tone, audience, programming language", "\u201cbrief\u201d, \u201cformal tone\u201d, \u201cexplain to a beginner\u201d, \u201cin Python\u201d"],
      ["A04 redundancy (17 patterns)", "filler and repeated sentences or words", "\u201chey\u201d, \u201ccan you\u201d, \u201cjust\u201d, \u201cthe the\u201d"],
      ["A05 ambiguous references", "references to material that is not there (only when no text is given)", "\u201csummarize this\u201d, \u201cthe above\u201d, \u201cfix it\u201d"]],
     [1.9, 2.1, 2.5]),
    ("p", "Which constraints are worth asking for depends on the category: a length for closed_qa; length, audience "
          "and tone for summarization; the programming language for coding; none for extraction and classification, "
          "whose output size is fixed by the data. For the review example (detected as summarization) A03 therefore "
          "reports length, audience and tone as missing; Stage B fills none of them because the category is below the "
          "gate. Each detector returns the exact words it matched, so the user interface can highlight them."),

    # ------------------------------------------------------------------ Stage B
    ("h2", "4.6 Phase 4: Implementation of Stage B (rule-based optimization)"),
    ("p", "Stage B fixes what fixed rules can fix. It creates the IR from the prompt, runs fifteen rules over it in a "
          "fixed order, logs every change with the text before and after it, and records what it could not fix."),
    ("fig", "diag_stage_b.png", "Stage B: rule order, the 0.6 confidence gate and the group fallback", 6.5),
    ("h3", "4.6.1 Rule order"),
    ("p", "The rules always run in this order: B07 (structure) first, then B01 (filler) and B02 (duplicates), the "
          "attachment rules B09-B15, the group rule B08, and finally the category rules B06 (labels), B05 (language), "
          "B04 (length) and B03 (format). B07 runs first so that the user's data is moved out of the task before any "
          "other rule edits text; B03 runs last because it must know whether B08 already handled the prompt."),
    ("tbl", "Stage B rule catalogue", ["Code", "Rule", "Condition", "Action", "Example"],
     [["B07", "Structure", "always; data moves only if clearly data", "moves pasted data or code into its own block; capital letter, full stop", "\u201cclassify these as fruit or vegetable: apple, carrot\u201d \u2192 items in a separate block"],
      ["B01", "Remove filler", "a filler phrase from A04", "deletes it unless quoted or part of the content", "\u201chey can you just tell me \u2026\u201d \u2192 \u201cTell me \u2026\u201d"],
      ["B02", "Remove duplicates", "repeated sentence or doubled word", "keeps one copy", "\u201csort the the list\u201d \u2192 \u201cSort the list\u201d"],
      ["B09-B15", "Attachment", "an attachment of that type is given", "adds how to use it and \u201csay so instead of guessing\u201d", "PDF: \u201cCite the page or section numbers \u2026\u201d"],
      ["B08", "Group fallback", "confidence < 0.6, text attached, QA + extraction + summary \u2265 0.6", "adds what is missing of \u201cAnswer from the provided text in at most three sentences.\u201d", "\u201cwhat are the big inventions from berkeley in that text?\u201d"],
      ["B06", "Labels", "classification, reliable, no labels stated", "states the allowed labels", "\u201cUse only these labels: \u201cstring\u201d, \u201cpercussion\u201d.\u201d"],
      ["B05", "Language", "coding, reliable, no language", "\u201cUse Python.\u201d or \u201cKeep the language of the given code.\u201d", "\u201cwrite code to get all permutations of a string\u201d"],
      ["B04", "Length", "closed_qa or summarization, reliable, no length", "\u201cAnswer in at most two sentences.\u201d / \u201cKeep it under 100 words.\u201d", "\u201csummarize this article\u201d + text"],
      ["B03", "Output format", "no format stated; reliable; no group", "adds the category's default format", "coding: \u201cReturn only the code, in a single code block.\u201d"]],
     [0.6, 0.9, 1.6, 1.8, 1.6]),
    ("tbl", "Default output format added by B03 per category", ["Category", "Format added"],
     [["closed_qa", "Start with the direct answer."],
      ["information_extraction", "List each extracted item on its own line; if the text does not contain it, reply \u201cNot found\u201d."],
      ["classification", "For each item, output \u201citem: label\u201d on its own line (or \u201cOutput only the label.\u201d for a single item)."],
      ["summarization", "Use bullet points."], ["coding", "Return only the code, in a single code block."]],
     [1.9, 4.6]),
    ("h3", "4.6.2 The 0.6 gate and the group fallback B08"),
    ("p", "Rules B03-B06 add category-specific content (a format, a length, a language, labels). A classification "
          "layout on a summarization request would mislead the model, so these rules act only when the category is "
          "reliable: Stage A's confidence is at least 0.6, or the user chose the category. Below the gate, Stage A "
          "often cannot tell closed_qa, information_extraction and summarization apart, but it is much surer that the "
          "prompt is one of the three. B08 therefore acts at group level when"),
    ("eq", "max score < 0.6   and   text attached   and   score(closed_qa) + score(extraction) + score(summarization) \u2265 0.6"),
    ("p", "and adds only what is missing of \u201cAnswer from the provided text in at most three sentences.\u201d When "
          "it was introduced, it reduced the share of validation prompts sent to Stage C from 52.0% to 11.3% without any "
          "new wrong-category additions. On the test split it fires on 149 of 482 prompts (30.9%)."),
    ("h3", "4.6.3 Routing to Stage C"),
    ("tbl", "Items Stage B may leave unresolved", ["Unresolved item", "Set by", "Sent to Stage C?"],
     [["task category", "category \u201cother\u201d or confidence < 0.6, not cleared by B08", "yes"],
      ["ambiguous reference", "A05 found a reference and no attachment explains it", "yes"],
      ["output format", "B03, when the category is not reliable", "no (shown to the user)"],
      ["label set", "B06, when no labels could be found", "no (shown to the user)"]],
     [1.7, 3.3, 1.5]),
    ("p", "Stage B also stores a confidence for the user interface: the Stage A confidence minus 0.2 for every "
          "unresolved item (0.3 as the base for \u201cother\u201d), clipped to [0, 1]. It is not used for routing."),
    ("h3", "4.6.4 The review example in Stage B"),
    ("tbl", "Stage B steps for the review example", ["Step", "Text before", "Text after"],
     [["B07 structure", "hey can you just tell me if this review is good or bad", "Hey can you just tell me if this review is good or bad."],
      ["B01 filler", "Hey can you just tell me if this review is good or bad.", "Tell me if this review is good or bad."],
      ["B08", "not applied: the group score (0.00 + 0.03 + 0.52 = 0.55) is below 0.6", "\u2013"],
      ["B03-B06", "not applied: confidence 0.52 < 0.6", "\u2013"]],
     [1.3, 2.6, 2.6]),
    ("p", "Stage B leaves two items unresolved, the task category and the output format. The task category routes the "
          "prompt to Stage C."),

    # ------------------------------------------------------------------ Stage C
    ("h2", "4.7 Phase 4: Implementation of Stage C (LoRA fallback) and its training"),
    ("p", "Stage C is Qwen2.5-0.5B-Instruct with a LoRA adapter that we trained. It fills only the IR fields that "
          "Stage B left unresolved; every other field is locked. Its answer is checked by the same detectors as the "
          "rest of the pipeline, and if the check fails, the prompt keeps Stage B's result."),
    ("fig", "diag_stage_c.png", "Stage C in block form: routing, request, model, checker, fallback and the user's confirmation", 6.5),
    ("h3", "4.7.1 When Stage C runs and what it may fill"),
    ("tbl", "Fields Stage C is asked to fill", ["Unresolved item", "Fields requested", "Reason"],
     [["task category", "output_format, constraints, category", "Stage B added nothing category-specific, so format and constraints are missing too"],
      ["ambiguous reference", "task", "the task must be rewritten to be self-contained"]],
     [1.6, 2.2, 2.7]),
    ("p", "The model receives a short system prompt and the request as JSON: the user's prompt, Stage A's category and "
          "confidence, whether text is attached, the attachment type, Stage B's IR with the unresolved fields set to "
          "null, and the list of fields to fill. The pasted text itself is not sent: Stage C writes the instruction, "
          "not the answer, and this keeps the input short. For the review example the request asks for "
          "output_format, constraints and category, and the model answered:"),
    ("code", "{\"output_format\": \"Provide only the label.\", \"constraints\": [], \"category\": \"classification\"}"),
    ("h3", "4.7.2 Base model and LoRA"),
    ("tbl", "Base model Qwen2.5-0.5B-Instruct [10]", ["Property", "Value"],
     [["parameters", "about 494 million"], ["transformer layers", "24"], ["hidden size", "896"],
      ["attention", "14 query heads of 64 dimensions; 2 key/value heads (grouped-query attention)"],
      ["feed-forward", "SwiGLU, 896 \u2192 4,864 \u2192 896"], ["vocabulary", "151,936 tokens"], ["weights", "bfloat16"]],
     [2.0, 4.5]),
    ("p", "LoRA [7] freezes every base weight W\u2080 and learns a low-rank update next to it:"),
    ("eq", "h = W\u2080x + (\u03b1 / r) \u00b7 B A x,     A: r \u00d7 d_in matrix,  B: d_out \u00d7 r matrix"),
    ("p", "A is initialised randomly and B with zeros, so at the start the model equals the base model. We used rank "
          "r = 16, \u03b1 = 32 (scale 2) and dropout 0.05 on all attention and feed-forward projections. A LoRA pair on a "
          "d_in \u2192 d_out projection has r(d_in + d_out) parameters:"),
    ("tbl", "Trainable LoRA parameters per transformer layer (r = 16)", ["Projection", "Shape", "r (d_in + d_out)"],
     [["q_proj", "896 \u2192 896", "28,672"], ["k_proj", "896 \u2192 128", "16,384"], ["v_proj", "896 \u2192 128", "16,384"],
      ["o_proj", "896 \u2192 896", "28,672"], ["gate_proj", "896 \u2192 4,864", "92,160"], ["up_proj", "896 \u2192 4,864", "92,160"],
      ["down_proj", "4,864 \u2192 896", "92,160"], ["per layer", "", "366,592"]],
     [1.6, 2.0, 2.0]),
    ("p", "Over 24 layers this gives 8,798,208 trainable parameters, 1.78% of the model, stored in a 34 MB file. At "
          "inference the update is merged into the weights (W = W\u2080 + (\u03b1/r)BA), so Stage C costs the same as the "
          "base model."),
    ("h3", "4.7.3 Training data"),
    ("fig", "diag_training.png", "Stage C training pipeline", 6.5),
    ("p", "One training example is built per dataset row. Stage A is run on the training rows with cross-fitting: the "
          "rows are split into five folds by instruction, and each fold is classified by an index built without it. "
          "Otherwise every training prompt would find itself as its own nearest neighbour and Stage A would look "
          "unrealistically accurate (cross-fitted accuracy on train: 73.9%, close to 74.7% on test). Stage B is then "
          "run for real, and the target is parsed out of the dataset's optimized prompt."),
    ("tbl", "Stage C examples per split", ["Kind", "Rule", "Train", "Validation", "Test"],
     [["routed", "Stage B really sends the row to Stage C: its natural fields", "377", "10", "31"],
      ["forced", "every other row: a random non-empty subset of {task, output_format, constraints}", "4,132", "139", "451"],
      ["forced_all", "validation and test only: every row once more with all three fields", "\u2013", "149", "482"],
      ["examples", "", "4,509", "298", "964"]],
     [1.0, 3.3, 0.7, 0.8, 0.7]),
    ("p", "Only 8.4% of training rows are routed naturally, too few to learn from, so forced examples teach the model "
          "to fill any requested field while respecting the locked ones. Each field is kept independently with "
          "probability 0.5 (an empty draw is replaced by one field), so an example asks for one field with probability "
          "1/2, two with 3/8 and three with 1/8. 53 examples whose target was not cleanly separable were left out, "
          "giving 4,456 training examples."),
    ("p", "The targets come from a parser that splits the dataset's optimized prompt into IR fields, reusing Stage A's "
          "detectors so that every sentence goes to exactly one field: the first sentence is the task; later sentences "
          "go to output_format if they state a structure, to constraints if they state a length, tone, audience, "
          "language or grounding, and otherwise stay in the task. The task was separated in 100% of rows, the output "
          "format in 94.0% and constraints in 75.0%; a hand check of 20 random parses found 17 fully correct."),
    ("h3", "4.7.4 Training procedure"),
    ("p", "The model sees the system prompt and the request, and learns to produce the JSON answer. The loss is the "
          "mean cross-entropy over the answer tokens only (the prompt tokens are masked), because the model must learn "
          "to write the JSON, not to repeat its input:"),
    ("eq", "L(\u03b8) = \u2212 (1 / |T|) \u03a3 log p\u03b8(x(t) | x(<t)),   t over the answer tokens T"),
    ("tbl", "Training settings", ["Setting", "Value", "Reason"],
     [["effective batch", "16 examples per step (micro-batch 1 \u00d7 16 accumulation)", "fits the 4 GB GPU with the same effective batch"],
      ["optimizer", "AdamW [18], learning rate 2 \u00d7 10\u207b\u2074, weight decay 0", "usual LoRA learning rate"],
      ["schedule", "linear warm-up for 25 steps, then linear decay to 0", "avoids large early updates"],
      ["epochs", "at most 3, with early stopping", "stop when validation loss stops improving"],
      ["gradient clipping", "L2 norm \u2264 1.0", "stability"],
      ["precision and memory", "bf16 autocast, LoRA weights in fp32, gradient checkpointing", "fits 4 GB"],
      ["sequence length", "\u2264 512 tokens (longest example 446)", "no example dropped"],
      ["seed", "13", "reproducibility"]],
     [1.5, 2.8, 2.2]),
    ("p", "Every 50 steps the validation loss (token-weighted mean over all validation examples) is computed; the "
          "adapter is saved when it improves, and training stops after three evaluations without improvement."),
    ("tbl", "Validation loss during training", ["Step", "50", "100", "200", "300", "400", "500", "550", "600", "700"],
     [["val loss", "0.852", "0.789", "0.745", "0.726", "0.716", "0.706", "0.705", "0.744", "0.761"]],
     [0.9, 0.62, 0.62, 0.62, 0.62, 0.62, 0.62, 0.62, 0.62, 0.62]),
    ("p", "The best validation loss, 0.7047, was reached at step 550 (a perplexity of e^0.7047 = 2.02 per answer token). "
          "After the third epoch began, the validation loss rose for three evaluations while training continued, the "
          "usual sign of over-fitting, and training stopped at step 700 after 51 minutes on the RTX 3050 laptop GPU."),
    ("h3", "4.7.5 Checker, fallback and category policy"),
    ("p", "Stage C answers with greedy decoding (at most 192 new tokens). The answer is accepted only if all checks pass:"),
    ("num", [
        "it parses as one JSON object;",
        "its keys are exactly the requested keys;",
        "a rewritten task has at least two words and A05 finds no ambiguous reference in it;",
        "an output format, if present, states a format according to A02;",
        "constraints are a list of non-empty strings;",
        "a category is one of the five categories.",
    ]),
    ("p", "Any failure keeps Stage B's result. For example, for \u201chey can you just summarize this article for me\u201d "
          "without the article, Stage C answered \u201cSummarize the provided text \u2026\u201d, which still refers to a "
          "text that is not there, so it was rejected. When the category was requested, Stage C's category is never "
          "applied on its own: the user interface asks the user and pre-selects Stage C's suggestion, while the "
          "format and constraints are applied. For the review example all checks passed, \u201cProvide only the "
          "label.\u201d was applied, and the user was asked to confirm \u201cclassification\u201d."),
    ("p", "Without fine-tuning, the base model passed these checks in only 5.0% of test examples (only 51.2% of its "
          "answers had exactly the requested keys); with the LoRA adapter, 98.2% passed."),

    # ------------------------------------------------------------------ rendering, app
    ("h2", "4.8 Phase 4: Rendering, token counting and the web application"),
    ("p", "The final IR is written out for the chosen model family with the same four sections everywhere (task, "
          "context, constraints, output format), laid out the way each provider's prompting guide recommends."),
    ("tbl", "Layouts per target LLM", ["Target", "Layout", "Review example (output format section)"],
     [["Claude", "XML tags; the context first, then task, constraints, output format", "<output_format> Provide only the label. </output_format>"],
      ["GPT", "Markdown sections ### Task / ### Context / ### Constraints / ### Output format", "### Output format  Provide only the label."],
      ["Gemini", "plain labels, the instruction first and the context last", "Output format: Provide only the label."]],
     [0.9, 3.0, 2.6]),
    ("p", "Data blocks are wrapped in a code fence one backtick longer than any backtick run inside the data, so pasted "
          "code cannot close the block early. Tests parse every rendering back and check that no field is lost. Input "
          "tokens are counted exactly for GPT with the tiktoken o200k_base tokenizer; for Claude and Gemini, whose "
          "tokenizers are not available offline, they are estimated as characters divided by 4 and labelled as "
          "approximate (on the test renderings this estimate is within about 5-8% of the GPT count on average). For "
          "the review example the GPT rendering has 50 input tokens against 33 for the user's prompt alone."),
    ("p", "The web application is a FastAPI back end serving a React and TypeScript front end with two views. The "
          "simple app at / is for everyday users and uses no pipeline terms: Improve prompt (type the prompt, "
          "optionally paste the text it is about, pick ChatGPT, Gemini or Claude, copy the improved prompt), Token "
          "usage analysis (both prompts sent to the same real model) and History (30 days); Section 7.1.1 shows it. "
          "The developer view at /dev is for monitoring: Optimize shows each stage in turn (Section 7.1.2); Compare, "
          "History, Test suite, Results, How it works, Image mode and Status complete it. All database access goes "
          "through one repository module (Chapter 5)."),

    # ------------------------------------------------------------------ validation
    ("h2", "4.9 Phase 5: Validation"),
    ("p", "Every tuning decision was taken on the validation split (149 rows), never on the test split. The table "
          "below lists the main decisions and the validation evidence behind them."),
    ("tbl", "Decisions taken on the validation split", ["Decision", "Validation evidence"],
     [["category gate at 0.6", "Stage A right 77-96% of the time at confidence \u2265 0.6, 47-59% between 0.4 and 0.6"],
      ["group fallback B08", "prompts routed to Stage C fell from 52.0% to 11.3%, no new wrong-category additions"],
      ["Stage A settings (k, \u03c4, weights, threshold)", "tuned on validation accuracy (75.8% on validation)"],
      ["Stage C only for routed prompts", "forcing every prompt through Stage C lowered task intent from 0.855 to 0.773 on validation"],
      ["Stage C category only as a suggestion", "on routed validation prompts Stage A was right 40% and Stage C 30% of the time"],
      ["single-label classification format", "an earlier rule wrongly picked it for 8 validation prompts with several items; made stricter"]],
     [2.4, 4.1]),
    ("p", "After the last decision, the code was frozen with a git tag. From then on no Stage A or Stage B rule, "
          "threshold or judge setting was changed; bugs found later were reported, not fixed. Features added afterwards "
          "had to prove that they change nothing on the frozen pipeline: a freeze check runs Stage A and Stage B of "
          "the frozen and the current code on all 482 test prompts, writes every feature, IR, text, change and routing "
          "decision as JSON, and compares the SHA-256 hashes of the two dumps. A single changed character anywhere "
          "changes the hash; the two hashes are identical."),

    # ------------------------------------------------------------------ testing & metrics
    ("h2", "4.10 Phase 6: Testing and evaluation method"),
    ("p", "Testing has two parts: functional tests of the software (unit, integration and system tests, Chapter 6) and "
          "the evaluation of the optimizer's effect on real answers (Chapter 7). All answers in the evaluation come from "
          "OpenAI's GPT model gpt-oss-120b on the Groq or Cerebras free tier, at temperature 0, with at most 2,048 "
          "output tokens and reasoning effort \u201clow\u201d. Input and output token counts are the provider's own "
          "counts; output tokens include the model's hidden reasoning tokens, as billed. Claude and Gemini were not "
          "run, so all output-token numbers in this report are for the GPT model only."),
    ("h3", "Token reduction"),
    ("p", "For a prompt \u2018i\u2019 with b(i) tokens before (vague prompt) and a(i) tokens after (optimized prompt), "
          "for input, output or total tokens:"),
    ("eq", "r(i) = 100 \u00b7 (b(i) \u2212 a(i)) / b(i),     mean reduction = (1/n) \u03a3 r(i)"),
    ("eq", "aggregate reduction R = 100 \u00b7 (\u03a3 b(i) \u2212 \u03a3 a(i)) / \u03a3 b(i)"),
    ("p", "The mean of the per-prompt reductions (39.2% for total tokens) counts every prompt equally and is the "
          "headline; the aggregate reduction (55.4%) weights prompts by their size and is larger, because prompts with "
          "long unrequested answers shrink most."),
    ("h3", "Confidence interval and significance"),
    ("p", "The 95% confidence interval of the mean reduction is a percentile bootstrap [19] with 10,000 resamples of the "
          "per-prompt reductions. Significance of the paired token counts is tested with the Wilcoxon signed-rank test "
          "[20], which uses only the signs and ranks of the paired differences and so suits heavy-tailed token counts. "
          "For small paired yes/no outcomes (correct or not) the exact McNemar test is used on the discordant pairs:"),
    ("eq", "p = min(1, 2 \u00b7 \u03a3 from i = 0 to k of C(n, i) \u00b7 2^(\u2212n)),   n = wins + losses,  k = min(wins, losses)"),
    ("h3", "Quality, task success and correctness"),
    ("bul", [
        "Quality: a blind judge from a different model family (qwen3.8-27b) scores each answer from 0 to 10 against the "
        "reference answer, without knowing which prompt produced it.",
        "Task success: checked automatically where possible (classification: every item gets the reference label; "
        "coding: a code block that parses; closed_qa: the judge's yes/no).",
        "Correctness suite: 50 new hand-written cases, 10 per category, each with one verifiable gold answer, checked "
        "deterministically or with hidden unit tests run in a sandbox.",
    ]),
    ("h3", "Cost"),
    ("p", "The project ran on free tiers, so the money spent was zero. For a paid model with input price p(in) and "
          "output price p(out) per million tokens, cost = (T(in) \u00b7 p(in) + T(out) \u00b7 p(out)) / 10\u2076. Because "
          "the saving comes from output tokens, which usually cost several times more than input tokens, the cost "
          "saving is larger than the token saving: with output priced 4 times input, the test-split means give a "
          "saving of 69.5%."),

    # ------------------------------------------------------------------ deployment & stack
    ("h2", "4.11 Phase 7: Deployment"),
    ("p", "The application runs on the development laptop as a user service (uvicorn app.api:app on port 8080), "
          "reachable on the local network with an optional password; Stage C runs on the laptop GPU and the "
          "application falls back to Stages A and B when the GPU or the adapter is not available. The trained Stage C "
          "adapter, the Stage A category index and the data manifest are published as a GitHub release (v1.0), so a "
          "fresh clone can be run by following the README. SQLite is used in development and PostgreSQL is supported "
          "for deployment by changing one setting."),
    ("h2", "4.12 Technology stack"),
    ("tbl", "Technology stack", ["Layer", "Technologies"],
     [["Front end", "React 19 + TypeScript, Vite, Tailwind CSS, Radix UI, Recharts; Playwright for end-to-end tests"],
      ["Back end", "Python 3.14, FastAPI, Uvicorn, Pydantic"],
      ["Database", "SQLAlchemy 2.0 ORM; SQLite (development), PostgreSQL (deployment)"],
      ["NLP / features", "spaCy, regular expressions, Sentence-Transformers (all-MiniLM-L6-v2), pyspellchecker"],
      ["Model / fine-tuning", "Hugging Face Transformers, PEFT (LoRA), PyTorch (CUDA), Qwen2.5-0.5B-Instruct"],
      ["Tokenization", "tiktoken (o200k_base)"],
      ["LLM providers (live models)", "Groq and Cerebras free tiers: OpenAI's gpt-oss-120b as the stand-in for GPT; "
                                      "qwen3.8-27b as judge; Gemini wired in (needs a key, not yet run)"],
      ["Data", "Dolly-15k and CodeAlpaca-20k, rewritten into prompt pairs with the Groq API"],
      ["Testing / tooling", "pytest, Playwright, bubblewrap sandbox, Git and GitHub"]],
     [1.8, 4.7]),
])
