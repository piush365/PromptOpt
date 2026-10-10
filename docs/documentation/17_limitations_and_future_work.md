# 17. Limitations and future work

[Back to the index](README.md)

---

## 17.1 Limitations (what the results do and do not show)

**Models and measurement**
* All LLM numbers use **gpt-oss-120b** (Groq/Cerebras) as a stand-in for GPT, Gemini and Claude; real GPT/Claude/Gemini
  runs need API keys and are not done. Claude/Gemini token counts in the app are approximate (characters ÷ 4, which
  over-estimates GPT's tokenizer by ~5–8% on our prompts; chapter 7.2).
* The benchmark is small (44 prompts; 6–10 per category); the routed Stage C set is small (31); coding pass@1 rests
  on 29 Python items. The full-test token evaluation (482) is the large-sample result.
* One run per item at temperature 0; provider-side non-determinism is not averaged out per item.

**Tokens and cost**
* The optimized prompt is **longer**: input tokens grow in every category. The net saving depends on the model
  writing shorter answers. No category increases total tokens on average, but **87 of 482 test prompts (18.0%)**
  individually cost more, most in information_extraction (35/93), where the answer was already short.

**Stage A**
* 74.7% category accuracy; the closed_qa / information_extraction / summarization group is the weak spot
  (summarization F1 0.51), partly because of Dolly's noisy labels.
* The confidence is an uncalibrated score; the 0.6 gate is empirical.
* Regex detectors miss phrasings; known frozen issues in chapter 15.5.

**Stage B**
* "Format stated" is measured with Stage A's own A02 detector; quality and task success come from the judge and
  sandbox tests on smaller sets.
* Defaults (two sentences, 100 words, bullet points, Python) are design defaults, not tuned per user.
* Per-rule accuracy is agreement with **LLM-written** targets, not human gold labels.

**Stage C**
* Trained on LLM-written targets (111 train rows individually human-validated); the parser separates constraints in
  75% of prompts that state one; format/constraint content only moderately close to the targets (format similarity
  0.62).
* Validation checks form, not facts.
* Category accuracy where prompts are routed is about 40–45% for both Stage A and Stage C, hence the user is asked.

**Dataset and validation**
* Human validation covered 330 of 5,184 rows; the kappa target (> 0.6) was not met because of the kappa paradox
  (AC1 0.92–0.96); the LLM-assisted filter covered only the 90 overlap rows.
* Some CodeAlpaca references are wrong (excluded where known).

**Other features**
* Coding tests: Python only; the test writer is the same model as the target (validated on independent references).
* Image mode: Stable Diffusion 1.5 + CLIP only; DALL-E and Nano Banana untested; CLIP ignores negation.
* Attachment and image results are on **developer-written prompts only**.
* Correctness suite: gold answers reviewed by the team, not by outsiders; no significant correctness difference
  (Groq 37 → 42, p = 0.267; Cerebras 43 → 41, p = 0.688).

## 17.2 Future work (in the order the project recorded it)

1. **Lean mode** for short-answer prompts: add only the output-format line (or nothing) when the expected answer is
   already short, so the input overhead cannot exceed the output saving (targets the 87 prompts that cost more).
2. **Real target models:** Compare and the full evaluation on GPT, Claude and Gemini once API keys exist (Gemini is
   wired, never run live); exact token counters for Claude and Gemini.
3. **Blind sets** written by people outside the team: attachments (15 rows) and image prompts (10 rows); the tooling
   (`--blind`) is ready (`team_input/`).
4. **Stage A** on closed_qa / information_extraction / summarization: more human-labelled degraded prompts; calibrated
   confidence (e.g. temperature scaling on val) so the gate becomes a probability.
5. **Stage C:** more human-validated targets and a larger routed evaluation set.
6. Coding tests beyond Python; image mode on DALL-E / Nano Banana.
7. Fix the reported frozen issues (chapter 15.5) in a new, separately evaluated pipeline version (B06 label glue,
   the curly-quote typo, the training-script accumulation detail, XML escaping for Claude).
