# PromptOpt LA-2: presentation script

Spoken script for `LA2_PromptOpt.pptx` (18 slides), LA-2 evaluation, Thursday 15 October 2026.
About **15 minutes of slides + 6 minutes of live demo**, then questions.

| Presenter | Slides | Time |
|---|---|---|
| Piush | 1-5 (intro, architecture, Stage A/B/C), 17 (drives the demo) | ~4.5 min + demo |
| Nirzara | 6-8 (renderers, transactions, database), 13-15 (prototype, Git, challenges) | ~5.5 min |
| Siddhi | 9-12 (testing, test cases, results), 16 (plans), 18 (close) | ~5 min |

How to use this: the **Say** blocks are written to be spoken. Don't read them word for word; learn the numbers in bold
and the order. **Point at** tells you what to show on the slide. **Hand-off** is the line that passes to the next speaker.

---

## Slide 1 · Title (Piush, 30 s)

**Say:**
"Good afternoon. We are Piush Gogi, Nirzara Manade and Siddhi Bolaikar, and our project, under the guidance of
Prof. A. S. Pawar, is **PromptOpt: token-efficient prompt optimization for LLMs**.

In one line: people type vague prompts into ChatGPT, Gemini or Claude, the model guesses what they want and writes a
long answer, and that wastes tokens and money. PromptOpt rewrites a vague prompt into a clear one for the model you
use, shows every change it made, and we measured that it actually helps.

At LA-1 we presented the problem, the design and the plan. Today is Release 2: what we built, how we tested it, and a
live demo."

---

## Slide 2 · Agenda (Piush, 20 s)

**Say:**
"We'll follow the LA-2 checklist in this order: the core modules, the transaction flow and database, unit testing,
integration and system testing, our test cases, results and the working prototype, how we used Git and GitHub, the
challenges we faced, and our plans. Then we'll show the app live."

---

## Slide 3 · System architecture (Piush, 60 s)

**Point at:** the diagram, left to right.

**Say:**
"Here is the whole system. The user types a prompt in the web app and picks a target model (GPT, Gemini or Claude),
a category or auto-detect, and optionally an attachment type like a PDF or an image.

The prompt goes through three stages.
**Stage A** reads the prompt and detects what is missing: is there an output format, a length, a programming language,
is there filler, does it say 'this' without any text attached?
**Stage B** fixes those gaps with rules, and every rule's change is logged.
Only if the rules can't decide something, for example the task category or what 'this' refers to, the prompt goes to
**Stage C**, a small fine-tuned model. That happens for only **6.4%** of prompts.

The result is one intermediate representation, which we render in the style each model prefers. Everything is stored
in the database, and Compare can run the old and new prompt on a real model side by side. Image generation is a
separate mode the user picks."

**Hand-off:** "Let me go a bit deeper into the stages."

---

## Slide 4 · Stage A detects, Stage B fixes (Piush, 75 s)

**Point at:** the five detectors on the left, then the rule chips, then the 3.1% → 95.0% box.

**Say:**
"Stage A uses spaCy, regular expressions and a sentence-embedding classifier. It gives the task category with a
confidence score and flags five kinds of problems: no output format, missing constraints, filler, repetition and
ambiguous references. On our held-out test set of **482 prompts** the category is right **74.7%** of the time. Coding and
classification are almost perfect; question answering, extraction and summarization are hard to tell apart when the
prompt is vague.

Stage B has **15 rules**, B01 to B15. Each one is a separate function with its own unit tests. For example, for 'write
code to get all permutations of a string', B05 adds 'Use Python' and B03 adds 'Return only the code, in a single code
block'. B09 to B15 are one rule per attachment type.

One design choice: category-specific rules only fire when Stage A is at least 60% confident. Below that, rule B08 handles
the whole question-answering group without guessing the exact category.

The result: before optimization only **3.1%** of test prompts said what format the answer should have; after Stage B,
**95%** do."

---

## Slide 5 · Stage C: LoRA only where rules stop (Piush, 75 s)

**Point at:** the contract diagram, then the four numbers.

**Say:**
"Stage C is Qwen 2.5 with half a billion parameters plus a LoRA adapter. We trained it on our own laptop GPU, which has
only 4 GB, in **51 minutes**.

The important part is the contract with Stage B, on the left. Stage C is only asked for the fields Stage B couldn't
resolve. It must answer in JSON with exactly those keys. We check its answer with Stage A's own detectors, and if it
fails, we keep Stage B's result. So the model can help, but it can never make the prompt worse without us noticing.

Without fine-tuning, only **5%** of the base model's answers passed that check. With LoRA, **98%** pass. On the prompts
that get routed to it, the output format is stated in **90%** of cases instead of 23%. It takes **0.74 seconds** per call
on the GPU.

We also tested sending every prompt through Stage C. That made results worse, so Stage C stays a fallback, used only
where the rules stop."

**Hand-off:** "Nirzara will now explain how the result is written out for each model and stored."

---

## Slide 6 · IR, renderers, attachments, image mode (Nirzara, 60 s)

**Point at:** the three code boxes, then the attachments bar, then the image-mode panel.

**Say:**
"After the stages we have one model-independent representation: the task, the context, constraints, output format and
attachment. We write it out three ways, because models respond differently to formatting. Claude gets XML tags, GPT gets
Markdown sections, Gemini gets plain labels with the instruction first. The content is identical; our tests parse every
rendering back to prove no field is lost. We also count input tokens per model: exactly for GPT, approximately for the
others, and the app labels which is which.

Attachments are modifiers, not new categories. Rules B09 to B15 add one requirement per file type, and they never fire
without an attachment. On our 30 hand-made test prompts, **30 out of 30** were correct.

Image mode is separate. Our first version filled every missing detail with default keywords, and that made the
generated images *worse*: a watercolor request turned into a photo. Version 2 keeps the user's words and offers the
missing details as suggestions the user can click. On a held-out set it does no measurable harm."

---

## Slide 7 · Transaction flow (Nirzara, 60 s)

**Point at:** follow the numbered boxes 1 → 11.

**Say:**
"This is what happens in one request, as one database transaction.
The user submits the prompt. Before anything else, the server deletes prompts older than 30 days. Then `create_prompt`
removes e-mail addresses and phone numbers and stores the prompt with its expiry date. Stage A's features go into one
table, the optimized result and one row per rule change into two more, then the renderings and token counts.

All of this goes through a single module, `repository.py`. Its functions never commit on their own; the endpoint commits
**once**, at the end. So if anything fails half-way, nothing is stored.

After that, the user can run Compare, look at History, and the 30-day retention cleans everything up automatically."

---

## Slide 8 · Database layer (Nirzara, 45 s)

**Point at:** the ER diagram, then the table on the right.

**Say:**
"We have **ten tables**, using SQLAlchemy: SQLite for development and PostgreSQL for deployment. The six tables in this
list are the ones written in one optimize request.

Child tables cascade on delete, so when a prompt expires, everything derived from it disappears with it. The evaluation
table is deliberately *not* linked to prompts, so our benchmark results are never purged. Rules like 'confidence must be
between 0 and 1' or 'every Stage B change must name a rule' are enforced by the database itself, not just by the code."

**Hand-off:** "Siddhi will take you through testing."

---

## Slide 9 · Unit testing (Siddhi, 60 s)

**Point at:** the bar chart, then the 'Run' box.

**Say:**
"We have **798 automated tests**, and all of them pass. We ran the full suite yesterday: it takes about 25 seconds and
needs no internet, because model calls are faked or replayed from recordings.

The chart shows where they are. The biggest groups are image mode, the Stage B rules, dataset tooling and rendering.
Every single Stage B rule has its own tests.

Some real examples: a test stores 'mail rahul.k@example.com or call 98765 43210' and checks that the database contains
one [EMAIL] and two [PHONE] tags instead. Another checks that a blank prompt returns a proper error, not a server crash.
Another checks that a wrong answer from Stage C falls back to Stage B. Running them is one command: `python -m pytest`."

---

## Slide 10 · Integration and system testing (Siddhi, 60 s)

**Point at:** each of the six cards.

**Say:**
"Beyond unit tests:
The **freeze check**: we tagged our final code in Git before running the test set. This script re-runs Stages A and B on
all 482 test prompts and compares a fingerprint with that tag. Yesterday it was **byte-identical**, so nothing changed after
the final numbers.
**13 browser tests** drive the real app in Chrome with Playwright, covering optimize, compare, history, image mode and no
console errors; all 13 pass.
API tests go end to end through FastAPI.
We ran the full pipeline **once** on the 482-prompt test split and on a 44-prompt benchmark with a real model and a blind
judge.
Code written by the model runs in a **sandbox** with no network.
And finally a correctness suite, which is the next slide."

---

## Slide 11 · Test cases and correctness (Siddhi, 75 s)

**Point at:** the table (especially the two FAIL rows), then the chart, then 42/50.

**Say:**
"The report has 38 test cases in a table; here are six of them, including two failures.

The correctness suite is 50 new questions we wrote ourselves, 10 per category, each with one answer we can check, for
example a hostel-fee calculation where the correct total is 80,300. All 50 answers were confirmed by the team.

With the vague prompt the model got **37 out of 50** right. With our optimized prompt, **42 out of 50**, while using
**29.6% fewer tokens**. Optimization fixed 9 answers and broke 4.

We want to be honest: with 50 cases this difference is **not statistically significant**, and on a second provider the
result was 43 against 41. The failures are real: in one case Stage A thought an attendance table was code, so the model
wrote a Python script instead of labels; two summaries went 2 or 3 words over the word limit."

---

## Slide 12 · Results: -39.2% total tokens (Siddhi, 60 s)

**Point at:** the chart, then 682 → 165, then the limitation box.

**Say:**
"This is our headline result. On all 482 held-out test prompts, total tokens fall by **39.2%** per prompt, with a 95%
confidence interval of 35.9 to 42.5 percent.

Something interesting: the optimized prompt is actually slightly *longer*, 226 to 241 tokens. The saving comes from the
answer. Output drops from **682 to 165** tokens, because once the prompt says what format and length it wants, the model
stops writing long explanations nobody asked for. Every category saves on average.

On the benchmark with a blind judge, quality went from **8.2 to 9.0** out of 10 and task success from **67% to 85%**.

The limitation: for 87 of the 482 prompts the answer was already short, so the longer prompt cost more. That is our
first item for the next phase."

**Hand-off:** "Nirzara will show you the working app."

---

## Slide 13 · Working prototype (Nirzara, 45 s)

**Point at:** left screenshot, then right screenshot.

**Say:**
"This is the working application: a FastAPI back end and a React front end, running on our laptop with Stage C on the
GPU.

On the left is the Optimize page: you can see every stage, every rule with the text before and after, and the final
prompt for the chosen model. On the right is Compare: the same permutations prompt on a real model used **768 tokens**
before and **248** after, minus 67.7%, and both answers pass all 6 tests.

We don't have paid keys for GPT and Claude yet, so Compare uses an open model, gpt-oss-120b, and the app says clearly
that it is a stand-in."

---

## Slide 14 · Git and GitHub (Nirzara, 45 s)

**Point at:** the repository screenshot, then the three numbers, then the tag list.

**Say:**
"All our code is on GitHub, public, at piush365/PromptOpt. We have **92 commits** from August to October on three
branches.

We used tags as checkpoints for honest evaluation. 'frozen-for-test' marks the code that produced our final numbers;
after that tag we changed no rule and no threshold, and the freeze check proves it. 'final-for-test' is the single test
run, and v1.0 is the release with the trained model attached.

We didn't use GitHub Issues or Projects; we tracked work with a roadmap and phase tables inside the repository."

---

## Slide 15 · Challenges and how we solved them (Nirzara, 75 s)

**Point at:** one card at a time; don't read all of them in detail if time is short.

**Say:**
"A few problems we had to solve:
Our dataset's optimized prompts were written by an LLM, and sometimes it **dropped data** from the question. We wrote a
repair step that puts it back, and every change is logged.
When three of us rated the dataset, we agreed on about 90% of rows, but the kappa statistic was almost zero. That is
the known **kappa paradox** when almost every answer is 'yes', so we also report Gwet's AC1, which is 0.92 to 0.96.
**Free API limits**: we built a usage ledger and never use more than 70% of a day's quota.
The base model **invented fields**: only 5% valid, so we fine-tuned it and validate every answer.
**Image mode version 1** made images worse, so we redesigned it.
And training on a **4 GB GPU** needed tricks like gradient accumulation.

Our rule throughout: when something fails, we report it, we don't hide it."

**Hand-off:** "Siddhi will tell you what's next."

---

## Slide 16 · Plans for the upcoming phases (Siddhi, 45 s)

**Say:**
"Our plans, in priority order. First, a **lean mode** for prompts whose answer is short, so they don't cost more. Second,
smarter routing: send prompts with label sets and typos to Stage C, and let users confirm spelling fixes. Third, blind
tests with prompts written by people outside our team. Then, Compare on the real GPT, Claude and Gemini once we have API
keys, a bigger correctness suite so the result can become statistically significant, and finally deployment with
PostgreSQL, HTTPS and login."

**Hand-off:** "Now let's show it live."

---

## Slide 17 · Live demo (Piush drives; ~6 min)

Follow `DEMO_LA2.md`. Piush operates the laptop; Nirzara narrates steps 1-3, Siddhi narrates steps 4-5.

| Step | Who narrates | Do | Say (short) |
|---|---|---|---|
| 1 | Nirzara | Optimize → click "write code to get all permutations of a string" | "Stage A says coding, 100% sure, and finds no format and no language. Stage B adds 'Use Python' and 'return only the code'. Stage C isn't needed. Here's the GPT version; switching to Claude, same content in XML tags." |
| 2 | Nirzara | Type `hey can you just summarize this article for me` | "Filler removed, a length and a format added. But 'this article' is still unclear, so it goes to Stage C. Its answer failed our check, so the app keeps Stage B's result and tells the user why." |
| 3 | Nirzara | Back to prompt 1 → Compare this → Run comparison | "Same model, both prompts. Total tokens drop about two-thirds and both answers pass the tests." |
| 4 | Siddhi | Image mode → `oil painting of a sailboat in a storm` | "The user's words stay exactly as typed. Missing details are suggestions; I click one and it's added and marked." |
| 5 | Siddhi | History → Test suite → Results | "Every prompt we just ran is in History for 30 days. The test suite shows 37 to 42 out of 50. Results shows the minus 39.2% headline." |

**If the network fails:** show the Past comparisons table on the Compare page and say "here are earlier live runs".
**If the GPU fails:** the app falls back to Stages A and B and says so; carry on.

---

## Slide 18 · Thank you (Siddhi, 15 s)

**Say:**
"Thank you. We'd like to thank Prof. Pawar for the guidance throughout. We're happy to take your questions."

---

## Likely questions and how to answer

Answer short, give the number, and say honestly when something is a limitation. Whoever owns that part answers.

| Question | Answer (who) |
|---|---|
| Why rules first, and not just ask an LLM to rewrite the prompt? | Rules are free, instant, offline, explainable and testable; each change is logged. An LLM rewrite costs tokens, can change the meaning and can't be verified. We use a model only where rules stop (6.4%), and even then we validate it. Forcing every prompt through Stage C made results worse (task intent 0.886 → 0.769). (Piush) |
| The optimized prompt is longer. How can it save tokens? | Input grows by 15 tokens on average, output falls by about 517 (682 → 165). Models write long answers when the format isn't stated. Total: -39.2%. (Siddhi) |
| How do you know you didn't tune on the test set? | Splits share no instruction. All decisions were made on the validation split, the code was tagged `frozen-for-test` before the test run, the test split was run once, and the freeze check shows Stage A/B are byte-identical to that tag. (Siddhi) |
| 74.7% category accuracy is low. | Coding and classification are 0.98 and 0.94 F1; the weak group is QA/extraction/summarization, which look alike when vague. We don't guess there: below 0.6 confidence B08 handles the group, and the UI asks the user to confirm the category. (Piush) |
| Is 42 vs 37 out of 50 significant? | No: McNemar p = 0.267, and on Cerebras it was 41 vs 43. We report it as a positive but not significant result; a larger suite is in our plans. The token saving held on both providers (-29.6%, -28.2%). (Siddhi) |
| You didn't test on real GPT, Claude, Gemini. | Correct: no paid keys. We used gpt-oss-120b on Groq/Cerebras as a stand-in, and the app labels it as such. Gemini is wired in and runs with a key. (Nirzara) |
| Why is kappa near zero if raters agree? | Kappa paradox: with 96-98% "yes" answers, chance agreement is already near 1, so kappa collapses although raters agree on 89-94% of rows. Gwet's AC1 is 0.92-0.96. We report the kappa target as not met. (Nirzara) |
| Why such a small model for Stage C? | It fits a 4 GB laptop GPU for training and inference, answers in 0.74 s, and only fills a few fields. 98.2% of its answers pass validation. (Piush) |
| What happens to user data? | E-mails and phone numbers are removed before storing, every prompt expires after 30 days and is deleted with everything derived from it, and Compare sends only the scrubbed text. (Nirzara) |
| How is Compare fair? | Same model, temperature 0, same max tokens, same pasted material for both prompts; optional blind judge that doesn't know which prompt is which. (Nirzara) |
| What did each member do? | [FILL IN before the presentation: agree on one sentence each.] |
| Most commits are from one account. Why? | [FILL IN: e.g. how work was divided and committed. Answer honestly.] |
| What's the biggest weakness? | Short-answer prompts can cost more (87 of 482), and all results use stand-in models. Lean mode and real-model runs are our next steps. (Siddhi) |

---

## Numbers to remember

- **-39.2%** total tokens (95% CI 35.9-42.5%, n = 482); output **682 → 165**, input 226 → 241
- Output format stated **3.1% → 95.0%**; Stage A accuracy **74.7%**; **6.4%** routed to Stage C
- Benchmark: quality **8.2 → 9.0**, task success **67% → 85%**
- Stage C: **5% → 98%** valid answers; **0.74 s** on GPU; trained in **51 min** on 4 GB
- Correctness: **37 → 42 / 50**, **-29.6%** tokens, p = 0.267 (not significant)
- Tests: **798** pytest, **13/13** Playwright, freeze check **byte-identical**
- Git: **92** commits, **3** branches, **4** tags, **1** release
