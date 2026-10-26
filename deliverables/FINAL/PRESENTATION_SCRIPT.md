# PromptOpt final presentation: 10-minute script

Deck: `PromptOpt_Final.pptx` (16 main slides + Thank you + appendix). One example runs through the whole talk:

> **"hey can you just tell me if this review is good or bad"** + *"The battery lasts two days and the camera is great,
> but the phone heats up while gaming."*

Rules for the talk: plain words, no code names unless asked (say "small AI model", not "LoRA adapter"), one idea per
slide, and always say which AI answered: **OpenAI's GPT model (gpt-oss-120b)**.

| Part | Slides | Speaker | Time |
|---|---|---|---|
| Why | 1-6 | Piush | 3:00 |
| One example, step by step | 7-12 | Nirzara | 3:30 |
| Does it work, testing, app | 13-17 | Siddhi | 3:00 |
| Buffer | | | 0:30 |

---

## Piush (3:00)

**1. Title (0:15).** "Good morning. We are Piush, Nirzara and Siddhi; our guide is Prof. A. S. Pawar. PromptOpt takes a
vague prompt, makes it clear and short for the AI you use, shows every change, and we measured that it saves tokens.
We will follow one example prompt through the whole system."

**2. Agenda (0:10).** "Problem, what exists, our goal and data; then one example step by step; then results, testing,
the app and next steps."

**3. The problem (0:45).** "People type short, vague prompts, so the AI has to guess, and it writes long answers nobody
asked for. Every extra word costs tokens, time and money. Example: a student pastes a phone review and asks 'is this good
or bad'. The AI writes a whole page, 166 tokens, when one word was enough. Our survey agrees: 72% run out of tokens very
quickly, 58% need several prompts to get one answer, and half often ask the AI again."

**4. Gap analysis (0:30).** "Existing tools rewrite prompts, but none checks the new prompt on a real AI, none reports
input and output tokens together, and none combines fixed rules with a small trained model. Those are the four gaps we
built PromptOpt for."

**5. Our goal (0:35).** "Five goals: to find what a prompt is missing; to fix it with simple rules and show every
change; to use a small AI model only when the rules are stuck; to write the prompt the way each AI likes it; and to
prove it with numbers on prompts the system never saw."

**6. Our data (0:45).** "No dataset pairs a vague prompt with a clear one, so we built it. We took real requests from two
public datasets, Dolly and CodeAlpaca; an AI wrote a vague and a clear version of each; the computer checked them and
put back data that was dropped; and we three and our guide read 330 pairs and kept 295. Result: 5,184 pairs, about a
thousand per task type. 482 are kept aside and used only once, for the final test."
*Hand over:* "Nirzara will now take one prompt through the system."

## Nirzara (3:30)

**7. One example, start to finish (0:30).** "This is the whole journey of our example. One, the user types it with the
review. Two, Step A understands it. Three, Step B fixes it with rules. Four, a small model fills what the rules could
not. Five, it is written for GPT. Six, we run both prompts on the same AI. Step by step:"

**8. Step A: understand (0:40).** "Step A only reads. What kind of task is this? It thinks 'summary' at 52% and 'sort
into a label' at 35%. Below 60% we call it not sure, and we do not guess. It also finds what is missing: no answer format,
and filler words, 'hey', 'can you', 'just'. It decides by comparing the prompt with over 9,000 example prompts from our
data, plus word rules."

**9. Step B: fix with rules (0:40).** "Step B fixes with fixed rules and shows every change. Here two rules fired: tidy
the sentence, and remove 'hey can you just'. We have 15 rules, each a small tested function: add an answer format, a
length, a programming language, the list of labels, and so on. Because Step A was not sure of the task, no rule guesses
a format. That open question goes to Step C."

**10. Step C: a small model, only when stuck (0:45).** "Step C is a small AI model that we trained ourselves, on a 4 GB
laptop GPU, in 51 minutes. It is called only when the rules are stuck, which is 6 prompts in 100. It may fill only the
missing parts; everything else is locked. Its answer is checked: if the check fails, we keep Step B's result, so nothing
is lost. Before our training only 5 answers in 100 passed the check; after, 98. For our example it added 'Provide only
the label' and suggested 'sort into a label'. The app asks the user to confirm."

**11. Step D: written for your AI (0:25).** "Step D writes the same content in the layout each AI's makers recommend:
tags for Claude, headed sections for GPT, plain labels for Gemini. Our tests read every version back to check nothing is
lost."

**12. The result for our example (0:30).** "We sent both prompts to the same AI, OpenAI's GPT model. Total tokens: 270
for the vague prompt, 162 for ours, 40% fewer. The answer itself: 166 tokens versus 41, the single word 'good'. And it
came back in about a tenth of a second instead of a third."
*Hand over:* "One example is not proof. Siddhi will show the full test."

## Siddhi (3:00)

**13. Does it work on 482 new prompts? (0:50).** "We tested on 482 prompts the system had never seen, all answered by
OpenAI's GPT model. Our prompt is a little longer, 241 tokens instead of 226, but the answers are much shorter, 165
instead of 682. In total, 39% fewer tokens per prompt. The answer format is stated in 95 prompts in 100 instead of 3,
and a blind judge scored quality 9.0 instead of 8.2. One honest limit: 87 of the 482 cost a little more, because their
answer was already short. That is our next step, a lean mode."

**14. Testing (0:45).** "Three levels. Unit: 798 automatic tests, every rule tested on its own, all pass; the report shows
four sample cases from each module. Integration: 50 new real-life questions, ten per task type, each with a known right
answer. The optimized prompts got 42 right, the vague ones 37, with 30% fewer tokens; the chart shows it per task type,
and summaries are our weak spot. System: 13 browser tests drive the whole app, all pass, and the 482 test prompts were
run only once, at the end."

**15. The working app (0:35).** Live demo, or point at the screenshot: "Optimize shows each step for our example;
Compare runs both prompts on a real AI; History keeps prompts for 30 days; the test suite shows the 50 questions."
*If the network fails:* Compare shows saved past runs.

**16. Challenges and next steps (0:30).** "What was hard: AI-written data that dropped facts, a small model that made
things up before training, daily limits on free AI services, and a 4 GB GPU. Next: a lean mode for short answers, tests
on real GPT, Claude and Gemini with paid keys, bigger tests written by people outside our team, and a research paper."

**17. Thank you (0:05).** "Thank you. We are happy to take questions."

---

## Likely questions (short answers)

| Question | Answer |
|---|---|
| The vague answer said "mixed". Isn't that better than "good"? | The review is mixed, but the user asked "good or bad". The optimized prompt answers the question as asked. If the user wants "mixed", they choose the task type and add it as a label; Step B then lists the labels. |
| Did you test on ChatGPT, Claude or Gemini? | All answers come from OpenAI's GPT model gpt-oss-120b on free tiers. Claude and Gemini need paid keys; that is future work. Their prompt layouts are built and tested, but not run. |
| How is the confidence calculated? | Half from the 25 most similar training prompts (each weighted by how similar it is), half from a small trained classifier; keyword hints add weight when present. The top score is the confidence. Below 0.6 we do not trust it. (Report Section 4.5.5.) |
| Why 0.6? | Chosen on the validation data: above 0.6 the guess was right 77-96% of the time, between 0.4 and 0.6 only about half the time. |
| Why not just use a big AI to rewrite the prompt? | Cost and trust: the rules are free, instant and explainable, and handle 94 prompts in 100. The small model is only for the rest, and its answer is checked. Sending everything through the model made results worse in our test. |
| Why is the prompt longer if you save tokens? | The saving is in the answer. Stating the format costs about 15 input tokens and saves about 500 output tokens on average. |
| How do you know you did not tune on the test? | All tuning used a separate validation set. Then the code was frozen with a git tag, the test set was run once, and a check proves the frozen code never changed. |
| Is 42 vs 37 significant? | Not with 50 cases (p = 0.27), and we say so. The token saving is significant (p < 0.001 on 482 prompts). |
| What is LoRA? | A way to train a model cheaply: the original weights stay frozen and only small extra matrices are trained, 1.8% of the model. That is why it fits a 4 GB laptop GPU. |
| What about privacy? | E-mail addresses and phone numbers are removed before anything is stored, and prompts are deleted after 30 days. |

Appendix slides (after Thank you): tech stack, literature review, SDG alignment, Gantt chart, pipeline flow of one
request (with the commit decision at step 7), references.
