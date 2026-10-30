# PromptOpt final presentation: script

Deck: Canva "PromptOpt ESE PPT (final)" (https://www.canva.com/design/DAHZTt9e0xo/edit), 24 slides. The Canva speaker
notes carry the same lines, except slides 4, 5, 20 and 23, which have none there. One example runs through the whole
talk:

> **"hey can you just tell me if this review is good or bad"** + *"The battery lasts two days and the camera is great,
> but the phone heats up while gaming."*

Rules for the talk: plain words, no code names unless asked (say "small AI model", not "LoRA adapter"), one idea per
slide, and always say which AI answered: **gpt-oss-120b, OpenAI's open model, standing in for GPT**.

| Part | Slides | Speaker | Time |
|---|---|---|---|
| Why, what exists, how it is built | 1-9 | Piush | 4:15 |
| One example, step by step | 10-15 | Nirzara | 3:30 |
| Does it work, testing, app, wrap-up | 16-24 | Siddhi | 3:15 |
| Total | | | 11:00 |

If the slot is 10 minutes: keep slides 4, 8 and 9 to 0:15 each (-0:35), point at slides 20 and 21 and move on (-0:15),
and say slide 18 in one sentence (-0:10).

On slides 11-14 the left side shows how the step works and the right side ("Our example", with the A B C D pills)
shows what that step did to our example. Explain the left first, then the right.

---

## Piush (4:15)

**1. Title (0:15).** "Good morning. We are Piush, Nirzara and Siddhi; our guide is Prof. A. S. Pawar. PromptOpt takes a
vague prompt, makes it clear and short for the AI you use, shows every change, and we measured that it saves tokens.
We will follow one example prompt through the whole system."

**2. Agenda (0:10).** "The problem, what exists, our goal and our data, how the system is built; then one example
through every step; then results, testing, the app and what comes next."

**3. The problem (0:45).** "People type short, vague prompts, so the AI has to guess, and it writes long answers nobody
asked for. Every extra word costs tokens, time and money. Example: a student pastes a phone review and asks 'is this good
or bad'. The AI writes a whole page, 166 tokens, when one word was enough. Our survey agrees: 72% run out of tokens very
quickly, 58% need several prompts to get one answer, and half often ask the AI again."

**4. Literature review (0:20).** "Three recent papers. The first surveys automatic prompt optimization but proposes no
method of its own. The second shows that the format of a prompt alone changes the answer, but it trains the model to
cope instead of fixing the prompt. The third balances quality against cost, but its search is too expensive for a small,
self-hosted tool."

**5. Gap analysis (0:25).** "Existing tools rewrite prompts, but none checks the new prompt on a real AI, none reports
input and output tokens together, and none combines fixed rules with a small trained model. Those are the four gaps we
built PromptOpt for."

**6. Our goal (0:35).** "Five goals: to find what a prompt is missing; to fix it with simple rules and show every
change; to use a small AI model only when the rules are stuck; to write the prompt the way each AI likes it; and to
prove it with numbers on prompts the system never saw."

**7. Our data (0:45).** "No dataset pairs a vague prompt with a clear one, so we built it. We took real requests from two
public datasets, Dolly and CodeAlpaca; an AI wrote a vague and a clear version of each; the computer checked them and
put back data that was dropped; and we three and our guide read 330 pairs and kept 295. Result: 5,184 pairs, about a
thousand per task type. 482 are kept aside and used only once, for the final test."

**8. System architecture (0:35).** "How the system is built. The React web app talks to a FastAPI backend. The optimizer
runs Step A (detect what is missing), Step B (fix it with rules) and Step C (a small model, only when Step B is stuck).
The result is stored as one model-agnostic JSON form, then written out for GPT, Claude or Gemini. Everything is saved in
SQLite or PostgreSQL. For token usage analysis the app sends both prompts to a live model: Groq and Cerebras are used now
as stand-ins for GPT, and Gemini is wired in."

**9. Tech stack (0:25).** "The tools behind each layer: React and Tailwind for the web app; FastAPI with SQLite or
PostgreSQL behind it; Hugging Face Transformers and PEFT LoRA for our small model; spaCy, regular expressions and
sentence embeddings to read the prompt; tiktoken to count tokens; and our data comes from Dolly and CodeAlpaca,
rewritten with the Groq API."
*Hand over:* "Nirzara will now take one prompt through the system."

## Nirzara (3:30)

**10. Our example prompt (0:25).** "Here is one real prompt we will follow through the whole system. A user types: 'hey
can you just tell me if this review is good or bad', and pastes a phone review. What is wrong with it? There is no answer
format, so the AI does not know if we want one word or a page. It has filler words. And the task is not clear: summarise
the review, or just say good or bad? We now go step by step, A, B, C, D, and on every slide the box on the right shows
what that step did to this prompt."

**11. Step A: understand the prompt (0:40).** Left, the flowchart: "Step A only reads the prompt; it changes nothing. It
answers three questions. What task is it? It compares the prompt with over 9,000 example prompts from our data, plus
word rules. What is missing? For example the answer format or the length. And which words are filler? It must be at
least 60% sure of the task; below that it says 'not sure' and does not guess."
Right, our example: "It finds the filler words 'hey', 'can you', 'just'. It finds there is no answer format. And for
the task it is torn between 'summarise the review' and 'label it good or bad', not sure enough, so it does not guess.
These notes go to Step B."

**12. Step B: fix with simple rules (0:40).** Left, the three rule lanes: "Step B does the fixing, with 15 small rules.
Each rule is a separate, tested function, and every change is shown before and after. Clean-up rules always run; rules
that add something missing run only if the task is sure; attachment rules only if a file is attached."
Right, our example: "It continues from what Step A found. Rule B07 tidies the sentence: capital letter, full stop. Rule
B01 removes the filler, 'hey can you just'. Rule B03 would add an answer format, but Step A was not sure of the task, so
no rule guesses one. The two rules that fired are orange in the lanes. After Step B the prompt is 'Tell me if this
review is good or bad.' with the review kept as the document. Still open: the task type and the answer format. They go
to Step C."

**13. Step C: small model, only when stuck (0:45).** Left, the flow: "Step C is a small AI model that we trained
ourselves on a 4 GB laptop GPU, in 51 minutes. It is called only when the rules are stuck, about 6 prompts in 100. It may
fill only the open parts; everything else is locked. Its answer is checked, and if the check fails we keep Step B's
result, so nothing is lost. After our training, 98 answers in 100 pass the check; before, only 5."
Right, our example: "It arrives with two open parts: the task type and the answer format. The model suggests 'sort into
a label', which the app shows to the user to confirm, and adds the format 'Provide only the label.' The task sentence and
the review stay locked. The answer passes the check, so nothing is open any more."

**14. Step D: written for your AI (0:30).** Left, the fan-out: "Step D writes the finished prompt in the layout each
AI's makers recommend: XML tags for Claude, headed sections for GPT, plain labels for Gemini. The content is the same
everywhere, and our tests read every version back to check nothing is lost."
Right, our example: "Our example after all four steps: the task, the review as the document, and the format 'Provide
only the label.' For GPT it is 50 tokens. Now we send it to a real AI."

**15. The result for our example (0:30).** "In the app's token usage analysis we sent both prompts to the same AI,
gpt-oss-120b, OpenAI's open model, standing in for GPT. Total tokens: 270 for the vague prompt, 162 for ours, 40% fewer.
The answer itself: 166 tokens versus 41, the single word 'good'. And it came back in about a tenth of a second instead of
almost half a second."
*Hand over:* "One example is not proof. Siddhi will show the full test."

## Siddhi (3:15)

**16. Does it work on 482 new prompts? (0:50).** "We tested on 482 prompts the system had never seen, all answered by
gpt-oss-120b, OpenAI's open model, standing in for GPT. Our prompt is a little longer, 241 tokens instead of 226, but the
answers are much shorter, 165 instead of 682. In total, 39% fewer tokens per prompt. The answer format is stated in 95
prompts in 100 instead of 3, and a blind judge scored quality 9.0 instead of 8.2. One honest limit: 87 of the 482 cost a
little more, because their answer was already short. That is our next step, a lean mode."

**17. Testing (0:30).** "Three levels. Unit: 720 test cases, exactly 60 for each of our 12 modules, and all pass; the
next slide shows them. Integration: 50 new real-life questions, ten per task type, each with a known right answer. The
optimized prompts got 42 right, the vague ones 37, with 30% fewer tokens; the chart shows it per task type, and summaries
are our weak spot. System: 16 browser tests drive the whole app, simple view and developer view, all pass, and the 482
test prompts were run only once, at the end."

**18. Unit tests (0:20).** "Every module now has exactly 60 unit test cases: 12 modules, 720 in all, and every one
passes. Each test checks one behaviour, so a failure points at one thing. The database tests also run on PostgreSQL, 68
more, all pass."

**19. The working app (0:35).** Live demo, or point at the screenshots: "The app has three simple pages. One, Improve
prompt: you type your prompt, pick ChatGPT, Gemini or Claude, and copy the clear version; here is our review prompt with
Task, Context and Output format. Two, Token usage analysis: both prompts go to the same AI, here 40% fewer tokens in
total. The 50 tokens on the left are the prompt alone; the AI adds about 70 of its own, which is why the table shows 121.
Three, History keeps prompts for 30 days. Everything we showed earlier, every step and score, is in the developer view
at /dev, for monitoring."
*If the network fails:* the token usage analysis shows saved past runs.

**20. SDG alignment (0:15).** "PromptOpt fits two goals: SDG 9, industry, innovation and infrastructure, as an open,
self-hosted tool; and SDG 12, responsible consumption, because fewer tokens means less computing for every answer."

**21. Gantt chart (0:10).** "All ten tasks on the plan are done: from finding the problem and the literature review,
through the data, design, prototype and the model, to evaluation, testing, the final demo and documentation."

**22. Challenges and next steps (0:30).** "What was hard: AI-written data that dropped facts, a small model that made
things up before training, daily limits on free AI services, and a 4 GB GPU. Next: a lean mode for short answers, tests
on real GPT, Claude and Gemini with paid keys, bigger tests written by people outside our team, and a research paper."

**23. References.** Do not read out; leave on screen for a moment.

**24. Thank you (0:05).** "Thank you to the panel and to our guide. We are happy to take questions."

---

## Likely questions (short answers)

| Question | Answer |
|---|---|
| The vague answer said "mixed". Isn't that better than "good"? | The review is mixed, but the user asked "good or bad". The optimized prompt answers the question as asked. If the user wants "mixed", they choose the task type and add it as a label; Step B then lists the labels. |
| Did you test on ChatGPT, Claude or Gemini? | All answers come from gpt-oss-120b, OpenAI's open model, on free tiers. Claude and Gemini need paid keys; that is future work. Their prompt layouts are built and tested, but not run. |
| Step A was 52% sure of "summary". How is that calculated? | Half from the 25 most similar training prompts (each weighted by how similar it is), half from a small trained classifier; keyword hints add weight when present. The top score is the confidence. Below 0.6 we do not trust it. (Report Section 4.5.5.) |
| Why 0.6? | Chosen on the validation data: above 0.6 the guess was right 77-96% of the time, between 0.4 and 0.6 only about half the time. |
| Why not just use a big AI to rewrite the prompt? | Cost and trust: the rules are free, instant and explainable, and handle 94 prompts in 100. The small model is only for the rest, and its answer is checked. Sending everything through the model made results worse in our test. |
| Why is the prompt longer if you save tokens? | The saving is in the answer. Stating the format costs about 15 input tokens and saves about 500 output tokens on average. |
| How do you know you did not tune on the test? | All tuning used a separate validation set. Then the code was frozen with a git tag, the test set was run once, and a check proves the frozen code never changed. |
| Is 42 vs 37 significant? | Not with 50 cases (p = 0.27), and we say so. The token saving is significant (p < 0.001 on 482 prompts). |
| What is LoRA? | A way to train a model cheaply: the original weights stay frozen and only small extra matrices are trained, 1.8% of the model. That is why it fits a 4 GB laptop GPU. |
| What about privacy? | E-mail addresses and phone numbers are removed before anything is stored, and prompts are deleted after 30 days. |
