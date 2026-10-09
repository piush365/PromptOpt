# PromptOpt in 10 minutes (simple version)

Plain words, real numbers. Every number is from `evaluation/FINAL_RESULTS.md` (section in brackets).

## 1. The problem

People type short, lazy prompts like "write code for permutations". The AI has to guess what they want, so it
writes a long answer full of things nobody asked for. Long answers cost more money and take longer.

## 2. What PromptOpt does

It fixes your prompt **before** it goes to the AI, then checks whether the fix really helped.

Think of it as a spell-checker for prompts: it adds the details you forgot ("use Python", "give only the code",
"answer in two sentences"), so the AI gives a short, useful answer.

## 3. How it works: three steps

| step | what it does, simply |
|---|---|
| **Step A: read** | Looks at the prompt. What kind of task is it (question, pulling out facts, sorting into groups, summary, code)? What is missing (answer format, length, programming language)? Is anything unclear, like "this article"? |
| **Step B: fix with rules** | Simple fixed rules add only what is missing, and every change is shown before and after. If Step A is not sure about the task type (below 0.6 confidence), it does not guess. |
| **Step C: small AI, only when stuck** | If the rules cannot fix something (unclear task type, or an unclear word like "this"), a small AI model trained by us tries. Its answer is checked; if it is wrong, we keep Step B's version. Needed for only **6.4%** of prompts [4]. |

Then the fixed prompt is written in the style each AI likes best: **Claude**, **GPT** or **Gemini**. The content
is the same; only the layout differs.

Extra features:
* **Compare:** runs your original prompt and the fixed prompt on a real AI, side by side, and shows the tokens
  (cost), time and answers [9].
* **Image mode:** for image generators. It keeps your words exactly and only *suggests* extra details (lighting,
  style) as buttons you can click [8].

## 4. One example, start to finish

You type: **`write code to get all permutations of a string`**

1. **Step A:** it is a coding task. No language given. No answer format given.
2. **Step B:** adds "Use Python." and "Return only the code, in a single code block."
3. **Step C:** not needed; nothing was unclear.
4. **Result for Claude:**
   ```
   <task>
   Write code to get all permutations of a string.
   </task>

   <constraints>
   - Use Python.
   </constraints>

   <output_format>
   Return only the code, in a single code block.
   </output_format>
   ```
5. **Compare on a real AI:** tokens went from 768 to 248 (**67.7% fewer**). Both answers passed all 6/6 code tests
   [9].

## 5. The main results (the facts to say)

<!-- TOKEN:headline:start -->
**Optimized prompts reduce total tokens by 39.2% (95% CI 35.9–42.5%, n = 482)** (`evaluation/tokens/token_test.md`): input grows, the saving comes from shorter answers.
<!-- TOKEN:headline:end -->

In simple words: on 482 test prompts, the fixed prompt used **39.2% fewer tokens** in total. The prompt itself
gets a bit longer, but the AI's answer gets much shorter [9a].

| what we measured | before | after | source |
|---|---|---|---|
| Prompts that say what answer format they want | 3.1% | **95.0%** | [4] |
| Answer quality, scored 0-10 by another AI | 8.2 | **9.0** | [4] |
| Task done correctly | 67% | **85%** | [4] |
| Code that passes tests | 20.7% | **34.5%** | [7] |
| Tokens per prompt (benchmark) | 894 | **386** | [4] |

Other facts:
* **Dataset:** 5,184 prompt pairs we built; 482 kept aside only for the final test [2a].
* **Human check:** 3 team members rated 330 rows: 295 accepted, 35 thrown out [2a].
* **Step A** guesses the task type right **74.7%** of the time [3].
* **Step C (our small AI)** gives a usable answer **98.2%** of the time; without our training it was only 5.0%
  [5.1]. It runs in **0.74 s** on a laptop GPU [5.5].
* **Fair test:** the test prompts were used once, at the very end; nothing was tuned on them [2].

## 6. Weak points: say them honestly

| weak point | what to say |
|---|---|
| We never used the real GPT, Claude or Gemini | "We had no paid API keys, so a free model (gpt-oss-120b) stood in for all three, and the app says so." |
| The fixed prompt is longer | "Yes, the prompt grows a little, but the answer shrinks a lot. On average every category saves. 87 of 482 prompts did cost more, mostly ones whose answer was already short. A 'lean mode' is future work." |
| Step A is right only 74.7% of the time | "Code and sorting tasks are almost always right. Questions, fact-pulling and summaries look alike when the prompt is vague. So when it is unsure, it does not guess." |
| The human agreement score (kappa) looked bad | "Almost every answer was 'yes', and that breaks kappa. The raters actually agreed on 89-94% of rows. Another score, AC1, is 0.92-0.96." |
| Small tests in some places | "The code tests used 29 items, Python only. Step C only ran on 31 test prompts." |
| File and image features | "Tested on prompts we wrote ourselves. Tests by outsiders are future work." |

## 7. Top 10 questions and short answers

1. **How do you know the fixes are good?** Three checks: the fixed prompts state a format (3.1% -> 95.0%), another AI
   scores the answers higher (8.2 -> 9.0), and code passes more real tests (20.7% -> 34.5%).
2. **When does the small AI (Step C) run?** Only when the rules are stuck: unclear task type or an unclear word.
   Its answer is checked; if it is bad, we keep the rules' version.
3. **Why not use the small AI for every prompt?** We tried. It made prompts worse when the rules had already done
   the job (meaning kept: 0.886 -> 0.769). So it only helps where the rules are stuck.
4. **How do you count tokens?** For GPT, exactly (with its own tokenizer). For Claude and Gemini, an estimate
   (characters / 4), clearly labelled. In real runs we use the numbers the AI service reports.
5. **How can a longer prompt save tokens?** Because the answer gets much shorter. We count both: prompt plus
   answer. Result: 39.2% fewer in total.
6. **Why was kappa low?** Almost everyone said "yes" almost every time, which pushes kappa down even when people
   agree. Raw agreement was 89-94%.
7. **What went wrong with image mode at first?** Version 1 added words like "natural lighting" to every prompt,
   which turned a watercolor request into a photo. Version 2 keeps the user's words and only suggests.
8. **Did you cheat by tuning on the test set?** No. We tuned on a separate set, ran the test once, and a script
   proves the code did not change afterwards.
9. **Why rules first instead of just an AI?** Rules are free, instant, work offline, and every change can be
   explained. Using only the small AI was the worst option we tested.
10. **Are the GPT/Claude/Gemini results real?** No. A free model stood in for them, and we say so everywhere.
