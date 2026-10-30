# Content of the final MP1 report. Numbers: evaluation/FINAL_RESULTS.md, evaluation/tokens/token_test.md,
# evaluation/correctness_suite/RESULTS.md, docs/documentation/ (chapters 3-8), git; the review example was run
# through the real pipeline and Compare (see ../NOTES_SOURCES.md).
# Block kinds: p, h2, h3, bul, num, tbl(caption, header, rows, widths), tc, fig(file, caption, width),
# pair(f1, c1, f2, c2), code, eq.
from content_method import METHODOLOGY
from content_rest import DIAGRAMS, TESTPLAN, RESULTS, CONCLUSION

TITLE = "PromptOpt: Token-Efficient Prompt Optimization for LLMs"
TITLE_UP = "PROMPTOPT: TOKEN-EFFICIENT PROMPT OPTIMIZATION FOR LLMS"
GUIDE = "Prof. A. S. Pawar"
TEAM = [("Piush U. Gogi", "255200005"), ("Nirzara A. Manade", "255200006"), ("Siddhi S. Bolaikar", "255200008")]

ACK = [
    "We express our sincere gratitude to our guide, Prof. A. S. Pawar, for constant guidance, timely reviews and "
    "for pushing us to measure every claim instead of assuming it. The suggestions on evaluation, on the validation "
    "of our dataset and on presenting the system through one worked example shaped the way this project was carried "
    "out and reported.",
    "We thank Mr. H. R. Chandoba, Mini Project Coordinator, for organising the mini-project reviews, and Dr. A. R. Surve, "
    "Head of the Department of Computer Science and Engineering, for providing the facilities and the environment to "
    "work on this project. We also thank the faculty member who reviewed a sample of our dataset, and the students who "
    "answered our survey.",
    "Finally, we thank Walchand College of Engineering, Sangli, and our families and friends for their support "
    "throughout the project.",
]

ACRONYMS = [
    ("API", "Application Programming Interface"), ("CI", "Confidence Interval"),
    ("CLIP", "Contrastive Language-Image Pre-training"), ("CPU", "Central Processing Unit"),
    ("ER", "Entity-Relationship"), ("GPU", "Graphics Processing Unit"),
    ("IR", "Intermediate Representation"), ("JSON", "JavaScript Object Notation"),
    ("k-NN", "k-Nearest Neighbours"), ("LLM", "Large Language Model"), ("LoRA", "Low-Rank Adaptation"),
    ("ORM", "Object-Relational Mapping"), ("PEFT", "Parameter-Efficient Fine-Tuning"),
    ("PII", "Personally Identifiable Information"), ("QA", "Question Answering"),
    ("SD", "Stable Diffusion"), ("SDLC", "Software Development Life Cycle"),
    ("SRS", "Software Requirements Specification"), ("UI", "User Interface"),
    ("bwrap", "bubblewrap (Linux sandboxing tool)"),
]

ABSTRACT = [
    "People write prompts for large language models (LLMs) the way they type a search query: short, vague and "
    "without saying what the answer should look like. The model then guesses, often producing long, unrequested "
    "answers that cost output tokens, time and money and are harder to use. PromptOpt is a lightweight, self-hosted "
    "system that rewrites such a prompt into a clear, structured and token-efficient one for the model the user "
    "works with (GPT, Gemini or Claude), explains every change, and measures whether the rewrite helps.",
    "PromptOpt works in three stages. Stage A detects what a prompt is missing, Stage B fixes it with fifteen small, "
    "individually tested rules, and Stage C, a 0.5-billion-parameter model fine-tuned with LoRA, fills in only what "
    "the rules cannot resolve (6.4% of test prompts). The result is written in the layout each target LLM prefers and "
    "is served through a web application with a side-by-side Compare and a 30-day history.",
    "On 482 held-out test prompts, measured on OpenAI's GPT model gpt-oss-120b, optimized prompts reduce total "
    "tokens (input + output) by 39.2% (95% CI 35.9-42.5%): input grows slightly (226 to 241 tokens) while output "
    "falls from 682 to 165 tokens. An output format is stated in 95.0% of prompts instead of 3.1%; on the benchmark "
    "split, quality rises from 8.2 to 9.0 and task success from 67% to 85%. On 50 new hand-written cases with "
    "verifiable answers, optimized prompts were correct in 42 cases versus 37 for the vague prompts. The system is "
    "covered by 720 unit test cases (60 for each of 12 modules) and 16 browser tests, all passing.",
]

KEYWORDS = "prompt optimization, large language models, token efficiency, rule-based NLP, LoRA, FastAPI."

CH = []

# ====================================================================== 1 Introduction
CH.append(("Introduction and Related work", [
    ("h2", "1.1 Background"),
    ("p", "Large language models such as GPT, Gemini and Claude are now used daily by students, developers and small "
          "teams for answering questions, summarising notices, sorting messages and writing code. Their cost and speed "
          "depend on tokens. A token is a piece of a word; every token of the prompt (the input) and every token of "
          "the answer (the output, including hidden reasoning tokens of reasoning models) is counted, billed on paid "
          "plans and charged against the daily budget on free plans. When the budget is used up, the free tier stops "
          "working for the rest of the day."),
    ("p", "A large part of this cost is caused by the prompt itself. A prompt such as “hey can you just tell me if "
          "this review is good or bad”, typed together with a short product review, does not say what the "
          "answer should look like. The model therefore writes a heading, a list of positive and negative points and a "
          "closing paragraph. In our measurement, OpenAI's GPT model gpt-oss-120b answered this vague prompt with 166 "
          "output tokens. The optimized prompt produced by PromptOpt adds one line, “Provide only the label.”, "
          "and the same model answered with 41 output tokens; the total for the request fell from 270 to 162 tokens "
          "(−40%) and the answer came back in 97 ms instead of 353 ms. This review example is followed through every "
          "stage of the system in this report (Chapter 4 and Chapter 5)."),
    ("h2", "1.2 Motivation and customer connect"),
    ("p", "Before designing the system we surveyed students, developers and members of small teams, the people who "
          "need more value from every token. The survey asked how often they had to ask an AI tool more than once to get "
          "the answer they wanted and what they noticed about token limits."),
    ("tbl", "Survey: how often users must ask an AI tool more than once to get the answer they want",
     ["Very often", "Often", "Sometimes", "Rarely", "Never"],
     [["20%", "30%", "25%", "15%", "10%"]], [1.3, 1.3, 1.3, 1.3, 1.3]),
    ("tbl", "Survey: what users notice about token consumption", ["Observation", "Share of respondents"],
     [["Run out of tokens very quickly", "72%"], ["Need multiple prompts to get one output", "58%"],
      ["Notice a big drop in quality as tokens run low", "46%"], ["Have to stop their work due to token limits", "31%"]],
     [4.5, 2.0]),
    ("p", "Half of the respondents need to repeat a request often or very often, and almost three quarters run out of "
          "tokens quickly. A tool that makes the first prompt clear enough to get a usable, short answer addresses both "
          "problems at once: fewer repeated requests and fewer output tokens per request."),
    ("h2", "1.3 Related work"),
    ("p", "We studied four lines of work that are close to this problem: automatic prompt optimization, cost-aware "
          "prompt optimization, prompt compression and the sensitivity of LLMs to prompt format. We also used two "
          "technical building blocks: parameter-efficient fine-tuning and sentence embeddings."),
    ("h3", "Automatic prompt optimization"),
    ("p", "Ramnath et al. [1] survey automatic prompt optimization and define it as a search over the space of prompts "
          "for a fixed task, scored on a labelled development set. Representative methods are APE (Zhou et al. [4]), "
          "which asks an LLM to propose candidate instructions and keeps the best scoring one, and OPRO (Yang et al. "
          "[5]), which uses an LLM as an optimizer that sees previous candidates and their scores. These methods "
          "improve a task prompt that will be reused many times, but each optimization costs many LLM calls, needs "
          "labelled examples of the task and returns a prompt without explaining why it is better. They do not fit a "
          "single user who types a single, one-off prompt and wants the improved version immediately."),
    ("h3", "Cost-aware prompt optimization"),
    ("p", "CAPO (Zehle et al. [3]) adds the length of the prompt to the objective of an evolutionary search, so that "
          "shorter prompts with the same accuracy are preferred. It is the closest work to our goal of token "
          "efficiency, but it still optimizes one task prompt with many LLM evaluations, and it counts input length "
          "only. It is too expensive for a lightweight, self-hosted tool that must answer in well under a second."),
    ("h3", "Prompt compression"),
    ("p", "LLMLingua (Jiang et al. [6]) removes tokens from long prompts with a small language model to reduce input "
          "cost. Our measurements show that for short, everyday prompts the opposite lever matters: the optimized "
          "prompt is slightly longer (input 226 to 241 tokens on average), and the saving comes from much shorter "
          "answers (output 682 to 165 tokens). An evaluation that counts only input tokens would miss this effect "
          "entirely, which is why we measure input and output tokens separately everywhere."),
    ("h3", "Sensitivity to prompt format"),
    ("p", "Ngweta et al. [2] show that LLM output quality changes with the formatting of the prompt alone, even when "
          "the content is the same. This motivates our renderers: the same content is laid out in the style each "
          "model family's own prompting guide recommends (XML tags for Claude, Markdown sections for GPT, plain "
          "labels with the instruction first for Gemini)."),
    ("h3", "Building blocks"),
    ("bul", [
        "Sentence-BERT (Reimers and Gurevych [11]) produces sentence embeddings whose cosine similarity reflects meaning; "
        "Stage A uses the small all-MiniLM-L6-v2 model of this family to find training prompts similar to a new prompt.",
        "LoRA (Hu et al. [7]) freezes a pretrained model and trains small low-rank matrices next to its weight matrices. "
        "With LoRA, fine-tuning the 0.5-billion-parameter Qwen2.5 model [10] fits on a 4 GB laptop GPU.",
        "The source datasets are Databricks Dolly-15k [8] (question answering, information extraction, classification "
        "and summarization) and CodeAlpaca-20k [9] (coding).",
    ]),
    ("h2", "1.4 Research gap"),
    ("p", "Table 1.4 compares PromptOpt with four existing prompt tools that we examined in the requirement phase. "
          "All of them rewrite prompts, but none evaluates the rewritten prompt on a real model, none reports the token "
          "effect of input and output together, and none combines deterministic rules with a fine-tuned fallback."),
    ("tbl", "Gap analysis: existing prompt tools vs PromptOpt", ["Feature", "PO.tools", "Aiven", "SiteGPT", "BenchLM", "PromptOpt"],
     [["Rewrite prompts", "Yes", "Yes", "Yes", "Yes", "Yes"],
      ["Goal / framework customization", "Limited", "Yes", "Yes", "Limited", "Yes"],
      ["Preserve constraints", "No", "-", "-", "Yes", "Yes"],
      ["LLM output evaluation", "No", "No", "No", "No", "Yes"],
      ["Token efficiency report", "-", "Yes", "-", "-", "Yes"],
      ["Multi-stage pipeline", "No", "No", "No", "No", "Yes"],
      ["Comprehensive reporting", "No", "No", "No", "Partial", "Yes"],
      ["Access", "Free", "Free", "Free", "Limited", "Self-hosted"]],
     [2.2, 0.85, 0.85, 0.85, 0.85, 0.9]),
    ("p", "From the literature and the tool comparison we identified four gaps, each of which PromptOpt addresses:"),
    ("num", [
        "No automated evaluation of optimized prompts against the original prompts on a real model. PromptOpt's "
        "Compare feature and its evaluation harness run both prompts on the same model and report tokens, latency, "
        "quality and correctness.",
        "Limited or unclear handling of constraints and requirements. PromptOpt keeps every word of the user's data, "
        "adds only missing constraints and logs every change with the text before and after it.",
        "No systematic measurement of token efficiency with its quality trade-off. PromptOpt measures input and "
        "output tokens separately on a held-out test split and reports quality and correctness next to them.",
        "No multi-stage pipeline that combines rule-based and learned methods. PromptOpt uses deterministic rules "
        "first and a small LoRA model only where the rules stop.",
    ]),
    ("h2", "1.5 Organisation of the report"),
    ("p", "Chapter 2 states the problem and Chapter 3 the objectives. Chapter 4 describes the methodology phase by phase "
          "of the software development life cycle (SDLC) we followed: requirement analysis, dataset preparation, "
          "design, implementation of the three stages including the training of Stage C, validation, testing and "
          "deployment. Chapter 5 collects the project diagrams, starting from the review example. Chapter 6 is the "
          "test plan (unit, integration and system testing), Chapter 7 the results with screenshots, and Chapter 8 "
          "concludes with limitations and future scope."),
]))

# ====================================================================== 2 Problem statement
CH.append(("Problem statement", [
    ("p", "Problem definition: to build a lightweight, self-hosted system that rewrites a vague user prompt into a "
          "clear, structured prompt for the user's chosen LLM, shows every change it makes, and measures whether the "
          "rewritten prompt reduces total tokens (input + output) without lowering the quality of the answer."),
    ("h2", "2.1 Description"),
    ("p", "Users often write prompts that are vague, verbose or missing key details: the output format, a length, the "
          "programming language, the labels to choose from, or which text is meant by “this”. The model "
          "then guesses, which wastes output tokens, increases latency and gives answers that are inconsistent and "
          "harder to use. The problem addressed in this project is to detect these gaps in a single user prompt, fix "
          "them without changing what the user asked for, write the result in the layout the target model prefers, "
          "and prove with measurements on held-out data that the fix helps."),
    ("h2", "2.2 Formal statement"),
    ("p", "Given a user prompt ‘p’, a target LLM ‘t’ ∈ {GPT, Gemini, Claude}, a category "
          "‘c’ (one of five, or auto-detect) and an optional attachment type ‘a’, produce an "
          "optimized prompt ‘p′’ rendered for ‘t’ such that:"),
    ("num", [
        "the user's intent and every piece of data in ‘p’ are preserved;",
        "the missing output format and relevant constraints are stated;",
        "every change from ‘p’ to ‘p′’ is logged with the text before and after it;",
        "the total tokens (input + output) needed to answer ‘p′’ are lower than for ‘p’, "
        "without lowering answer quality or correctness, as measured on a held-out test split.",
    ]),
    ("h2", "2.3 Scope of the work done"),
    ("tbl", "What the project covers", ["Aspect", "Covered in this project"],
     [["Task categories", "closed_qa, information_extraction, classification, summarization, coding, plus “other”"],
      ["Target LLMs (rendering)", "GPT, Gemini and Claude layouts; exact token counts for GPT, approximate for the others"],
      ["Attachments", "image, PDF, PPTX, DOCX, spreadsheet, code file, other: as a modifier, not a category"],
      ["Optimizer", "Stage A detection, Stage B rules, Stage C LoRA fallback, offline (no API needed)"],
      ["Evaluation", "input, output and total tokens, quality, task success, correctness, ablation; answers from "
                     "OpenAI's GPT model gpt-oss-120b on free tiers"],
      ["Application", "FastAPI + React web app: Optimize, Compare, History (30 days), Test suite, Results, Image mode"]],
     [1.8, 4.7]),
    ("h2", "2.4 Alignment with the Sustainable Development Goals"),
    ("tbl", "Sustainable Development Goals addressed by PromptOpt", ["Goal", "How PromptOpt contributes"],
     [["SDG 9: Industry, innovation and infrastructure", "an open, self-hosted tool that makes everyday use of LLMs "
       "clearer and cheaper, built only on free and open components"],
      ["SDG 12: Responsible consumption and production", "fewer tokens per answer (39.2% fewer on the test split) "
       "means less computing, and so less energy, for every request"]],
     [2.2, 4.3]),
]))

# ====================================================================== 3 Objectives
CH.append(("Objectives", [
    ("p", "The objectives below describe what was built and measured in this project."),
    ("num", [
        "To detect what a user prompt is missing (task category with a confidence, output format, length, tone, "
        "audience, programming language, filler words and ambiguous references) using spaCy, regular expressions and "
        "a sentence-embedding classifier (Stage A).",
        "To fix the detected gaps with fifteen deterministic, individually unit-tested rules that log every change "
        "with the text before and after it (Stage B).",
        "To fine-tune a small language model (Qwen2.5-0.5B-Instruct with LoRA) on a 4 GB laptop GPU and use it only "
        "for what the rules cannot resolve, under a validated contract with a fallback to Stage B (Stage C).",
        "To build PromptOpt Dataset v1.2 final, 5,184 vague-to-optimized prompt pairs in five categories, validated "
        "by automatic checks and human raters, with train, validation, test and benchmark splits that share no "
        "instruction.",
        "To represent the optimized prompt in one model-agnostic intermediate representation and render it for GPT, "
        "Gemini and Claude, with token counts per target.",
        "To support an optional attachment type (image, PDF, PPTX, DOCX, spreadsheet, code file) as a modifier.",
        "To measure input, output and total tokens, quality, task success and correctness on held-out data with a "
        "real model, together with an ablation study of the three stages.",
        "To provide a working web application with Optimize, Compare (original vs optimized on the same model), "
        "a history with 30-day retention, removal of e-mail addresses and phone numbers before storage, and one "
        "database transaction per request.",
    ]),
]))

CH.append(METHODOLOGY)
CH.append(DIAGRAMS)
CH.append(TESTPLAN)
CH.append(RESULTS)
CH.append(CONCLUSION)

REFS = [
    "K. Ramnath et al., \"A Systematic Survey of Automatic Prompt Optimization Techniques,\" in Proc. EMNLP, 2025.",
    "L. Ngweta et al., \"Towards LLMs Robustness to Changes in Prompt Format Styles,\" in Proc. NAACL Student Research Workshop, 2025.",
    "T. Zehle et al., \"CAPO: Cost-Aware Prompt Optimization,\" in Proc. AutoML Conference, 2025.",
    "Y. Zhou et al., \"Large Language Models Are Human-Level Prompt Engineers,\" in Proc. ICLR, 2023.",
    "C. Yang et al., \"Large Language Models as Optimizers,\" in Proc. ICLR, 2024.",
    "H. Jiang et al., \"LLMLingua: Compressing Prompts for Accelerated Inference of Large Language Models,\" in Proc. EMNLP, 2023.",
    "E. J. Hu et al., \"LoRA: Low-Rank Adaptation of Large Language Models,\" in Proc. ICLR, 2022.",
    "M. Conover et al., \"Free Dolly: Introducing the World's First Truly Open Instruction-Tuned LLM,\" Databricks, 2023 (databricks-dolly-15k).",
    "S. Chaudhary, \"Code Alpaca: An Instruction-following LLaMA Model for Code Generation,\" GitHub repository, 2023.",
    "Qwen Team, \"Qwen2.5 Technical Report,\" arXiv:2412.15115, 2024.",
    "N. Reimers and I. Gurevych, \"Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks,\" in Proc. EMNLP-IJCNLP, 2019.",
    "K. L. Gwet, \"Computing inter-rater reliability and its variance in the presence of high agreement,\" British Journal of Mathematical and Statistical Psychology, vol. 61, no. 1, pp. 29-48, 2008.",
    "A. R. Feinstein and D. V. Cicchetti, \"High agreement but low kappa: I. The problems of two paradoxes,\" Journal of Clinical Epidemiology, vol. 43, no. 6, pp. 543-549, 1990.",
    "J. L. Fleiss, \"Measuring nominal scale agreement among many raters,\" Psychological Bulletin, vol. 76, no. 5, pp. 378-382, 1971.",
    "A. Radford et al., \"Learning Transferable Visual Models From Natural Language Supervision,\" in Proc. ICML, 2021.",
    "R. Rombach et al., \"High-Resolution Image Synthesis with Latent Diffusion Models,\" in Proc. CVPR, 2022.",
    "M. Chen et al., \"Evaluating Large Language Models Trained on Code,\" arXiv:2107.03374, 2021.",
    "I. Loshchilov and F. Hutter, \"Decoupled Weight Decay Regularization,\" in Proc. ICLR, 2019.",
    "B. Efron and R. J. Tibshirani, An Introduction to the Bootstrap. Chapman & Hall/CRC, 1993.",
    "F. Wilcoxon, \"Individual Comparisons by Ranking Methods,\" Biometrics Bulletin, vol. 1, no. 6, pp. 80-83, 1945.",
]

SCHOLARLY = [
    ("Research paper", "A research paper based on this project (the three-stage optimizer and its evaluation of input "
     "and output tokens on held-out data) is in preparation. [PLACEHOLDER: target conference or journal and status]"),
]
