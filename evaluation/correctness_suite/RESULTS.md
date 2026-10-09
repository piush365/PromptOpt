# Correctness suite: vague vs optimized prompts

Are optimized prompts not just shorter but **correct**? 50 new, hand-written cases (10 per category) with one verifiable answer each, run as the user's vague prompt and as PromptOpt's optimized prompt on the same model. The pipeline is frozen at v1.0: no rule was changed because of these results.

- Cases: `cases.jsonl` (new; not from the dataset, checked in `validation.md`). Prompts: `prompts.json` (A+B; A+B+C for the 10 prompts Stage B routes to Stage C: cqa-04, ie-05, ie-09, cls-02, cls-04, cls-07, cls-10, sum-05, cod-07, cod-10). No case leaks its gold answer into the optimized prompt (leak check in `validation.md`).
- Settings: one user message, temperature 0, max 2048 tokens (gpt-oss's reasoning included), reasoning "low" for gpt-oss; both prompts get the same material (vague: pasted below the prompt; optimized: the GPT rendering's Document). Tokens are the provider's counts (input + output, reasoning included in output).
- Scoring (`app/correctness/checks.py`): closed_qa normalized match; extraction exact set (P/R/F1 shown); classification all items right (per-item accuracy shown); summarization all key facts + no forbidden statement + within the word limit (blind checklist judge); coding all hidden asserts pass in the bubblewrap sandbox. Extractor/judge: Groq `qwen/qwen3.8-27b`, blind (never sees the gold answer or which prompt was used), used only where a deterministic check cannot decide (see the method column).
- McNemar: exact two-sided test on the discordant cases (only optimized right vs only vague right).
- Code: `v1.0-5-ga5d031a`; generated 2026-10-09T22:09.
- Gold answers: **auto-validated; human review pending**.
- Human review: **pending**. `cases_review.xlsx` (3 sheets, one per team member) asks each reviewer to tick "gold correct Y/N"; import it with `python -m app.correctness.review --import <file>`. Until then the gold answers are checked automatically only (`validation.md`).

Not run: `gemini/gemini-2.5-flash` (future work: no API key, same as GPT and Claude).

In progress (reported once every case is answered): `cerebras/gpt-oss-120b` 9/50.

## Primary model: gpt-oss-120b on Groq (prompt rendered for GPT)

50 of 50 cases answered with both prompts.

| category | n | vague correct | optimized correct | both | only optimized | only vague | both wrong | McNemar p | total tokens: mean reduction per case | aggregate |
|---|---|---|---|---|---|---|---|---|---|---|
| closed_qa | 10 | 8/10 (80%) | 10/10 (100%) | 8 | 2 | 0 | 0 | 0.500 | +18.9% | +22.0% |
| information_extraction | 10 | 7/10 (70%) | 10/10 (100%) | 7 | 3 | 0 | 0 | 0.250 | +21.7% | +27.8% |
| classification | 10 | 7/10 (70%) | 8/10 (80%) | 6 | 2 | 1 | 1 | 1.000 | -0.3% | +6.3% |
| summarization | 10 | 7/10 (70%) | 5/10 (50%) | 5 | 0 | 2 | 3 | 0.500 | -8.6% | -7.9% |
| coding | 10 | 8/10 (80%) | 9/10 (90%) | 7 | 2 | 1 | 0 | 1.000 | +55.3% | +56.0% |
| **overall** | 50 | 37/50 (74%) | 42/50 (84%) | 33 | 9 | 4 | 4 | 0.267 | +17.4% | +29.6% |

2x2 (all cases):

| | optimized correct | optimized wrong |
|---|---|---|
| **vague correct** | 33 | 4 |
| **vague wrong** | 9 | 4 |

Mean tokens per case, vague -> optimized: input 229 -> 257, output 435 -> 211, total 664 -> 467 (reduction: positive = fewer tokens).

Graded metrics, vague -> optimized:

- information_extraction: mean F1 0.95 -> 1.00; precision 0.92 -> 1.00; recall 1.00 -> 1.00
- classification: per-item accuracy 96.5% -> 92.5%
- summarization: key-fact coverage 100% -> 100%; forbidden statements 0 -> 0; within the word limit 7/10 -> 5/10; mean words 68 -> 70
- coding: asserts passed 84% -> 95%

### Where optimization hurt correctness (4)

- **cls-09** (classification; Stage A said coding 0.84; rules B07, B05, B03): Bhakti: safe (gold warning); Chinmay: safe (gold detained); Eshan: safe (gold detained); Farhan: safe (gold warning); Harsh: safe (gold warning). *Why:* Stage A misread the attendance table as code (coding 0.84 >= the 0.6 gate), so B05 added "Keep the language of the given code" and B03 "Return only the code, in a single code block". The model obeyed and returned a Python script instead of a label per student, so there are no labels to score (the extractor read the script's "Safe" branch). A Stage A error that the category rules then amplified; choosing the category in the UI avoids it.
- **sum-06** (summarization; Stage A said summarization 0.83; rules B07, B03): 92 words > 90. *Why:* B03 turned "4-5 lines" into "Use bullet points"; the bulleted answer has every key fact and no forbidden statement but is 92 words against the 90-word limit derived from "4-5 lines" (vague answer: 81). The optimized prompt does not carry the length as an explicit word limit.
- **sum-10** (summarization; Stage A said summarization 0.95; rules B07): 83 words > 80. *Why:* Only B07 (restructuring) fired, so the request says the same thing as the vague prompt ("under 80 words"). The answer is complete and correct but added a title line, "key points (under 80 words)", which counts: 83 words against 80 (vague answer: 71). A near miss, not a rule effect.
- **cod-10** (coding; Stage A said other 0.24; rules B07; Stage C): 4/8 asserts; first failure: `assert scale_quantity("1/2 tsp", 4, 10) == "1 1/4 tsp"` AssertionError. *Why:* Routed to Stage C (Stage A: other 0.24); Stage C accepted, category coding, added only a code-block format. The spec in the Document is identical in both prompts; the optimized answer's code parses quantities but rounds to the nearest 1/8 and formats mixed numbers wrongly (4 of 8 asserts fail, e.g. 1/2 tsp x 10/4 should be "1 1/4 tsp"). A model error under a near-identical request, not missing information.

### Where optimization fixed a wrong answer (9)

- **cqa-01** (closed_qa): vague was wrong: gold answer not in the response.
- **cqa-10** (closed_qa): vague was wrong: gold answer not in the response.
- **ie-07** (information_extraction): vague was wrong: also listed Wednesday: No lab (focus on mini-project), Friday: No lab scheduled.
- **ie-08** (information_extraction): vague was wrong: also listed 05‑09 | UPI – Reliance Digital | **5,000.00**.
- **ie-10** (information_extraction): vague was wrong: also listed (Optional) Declaration/Signature.
- **cls-05** (classification): vague was wrong: O9: dream (gold normal).
- **cls-10** (classification): vague was wrong: L9: mixed (gold hindi).
- **cod-05** (coding): vague was wrong: no_function: `format_inr` not defined; top-level functions: [].
- **cod-09** (coding): vague was wrong: 3/8 asserts; first failure: `assert second_highest([92, 92, 85]) == 85` AssertionError.

### Per case

| case | category | vague | optimized | tokens in vague -> opt | out | total | total reduction | scored by |
|---|---|---|---|---|---|---|---|---|
| cqa-01 | closed_qa | ❌ | ✅ | 254 -> 281 | 258 -> 157 | 512 -> 438 | +14.5% | deterministic / extractor |
| cqa-02 | closed_qa | ✅ | ✅ | 220 -> 247 | 165 -> 81 | 385 -> 328 | +14.8% | extractor / extractor |
| cqa-03 | closed_qa | ✅ | ✅ | 289 -> 316 | 163 -> 124 | 452 -> 440 | +2.7% | extractor / extractor |
| cqa-04 (C) | closed_qa | ✅ | ✅ | 180 -> 204 | 798 -> 325 | 978 -> 529 | +45.9% | extractor / deterministic |
| cqa-05 | closed_qa | ✅ | ✅ | 218 -> 245 | 156 -> 89 | 374 -> 334 | +10.7% | deterministic / deterministic |
| cqa-06 | closed_qa | ✅ | ✅ | 218 -> 246 | 369 -> 231 | 587 -> 477 | +18.7% | extractor / deterministic |
| cqa-07 | closed_qa | ✅ | ✅ | 207 -> 234 | 347 -> 129 | 554 -> 363 | +34.5% | deterministic / deterministic |
| cqa-08 | closed_qa | ✅ | ✅ | 216 -> 244 | 214 -> 154 | 430 -> 398 | +7.4% | extractor / deterministic |
| cqa-09 | closed_qa | ✅ | ✅ | 162 -> 189 | 267 -> 140 | 429 -> 329 | +23.3% | extractor / extractor |
| cqa-10 | closed_qa | ❌ | ✅ | 207 -> 234 | 344 -> 225 | 551 -> 459 | +16.7% | deterministic / extractor |
| ie-01 | information_extraction | ✅ | ✅ | 176 -> 203 | 261 -> 78 | 437 -> 281 | +35.7% | extractor / extractor |
| ie-02 | information_extraction | ✅ | ✅ | 206 -> 245 | 164 -> 109 | 370 -> 354 | +4.3% | extractor / deterministic |
| ie-03 | information_extraction | ✅ | ✅ | 215 -> 242 | 202 -> 73 | 417 -> 315 | +24.5% | extractor / extractor |
| ie-04 | information_extraction | ✅ | ✅ | 290 -> 328 | 232 -> 157 | 522 -> 485 | +7.1% | deterministic / deterministic |
| ie-05 (C) | information_extraction | ✅ | ✅ | 209 -> 231 | 242 -> 57 | 451 -> 288 | +36.1% | extractor / deterministic |
| ie-06 | information_extraction | ✅ | ✅ | 238 -> 272 | 156 -> 70 | 394 -> 342 | +13.2% | extractor / deterministic |
| ie-07 | information_extraction | ❌ | ✅ | 294 -> 322 | 302 -> 120 | 596 -> 442 | +25.8% | extractor / extractor |
| ie-08 | information_extraction | ❌ | ✅ | 305 -> 345 | 186 -> 242 | 491 -> 587 | -19.6% | extractor / deterministic |
| ie-09 (C) | information_extraction | ✅ | ✅ | 254 -> 276 | 247 -> 125 | 501 -> 401 | +20.0% | extractor / deterministic |
| ie-10 | information_extraction | ❌ | ✅ | 249 -> 276 | 897 -> 74 | 1146 -> 350 | +69.5% | extractor / deterministic |
| cls-01 | classification | ✅ | ✅ | 228 -> 259 | 134 -> 191 | 362 -> 450 | -24.3% | deterministic / deterministic |
| cls-02 (C) | classification | ✅ | ✅ | 219 -> 243 | 198 -> 196 | 417 -> 439 | -5.3% | deterministic / deterministic |
| cls-03 | classification | ✅ | ✅ | 226 -> 257 | 159 -> 93 | 385 -> 350 | +9.1% | deterministic / deterministic |
| cls-04 (C) | classification | ✅ | ✅ | 158 -> 191 | 226 -> 332 | 384 -> 523 | -36.2% | deterministic / deterministic |
| cls-05 | classification | ❌ | ✅ | 304 -> 336 | 544 -> 261 | 848 -> 597 | +29.6% | deterministic / deterministic |
| cls-06 | classification | ✅ | ✅ | 333 -> 360 | 432 -> 146 | 765 -> 506 | +33.9% | extractor / extractor |
| cls-07 (C) | classification | ❌ | ❌ | 240 -> 267 | 233 -> 374 | 473 -> 641 | -35.5% | deterministic / extractor |
| cls-08 | classification | ✅ | ✅ | 365 -> 405 | 581 -> 309 | 946 -> 714 | +24.5% | extractor / deterministic |
| cls-09 | classification | ✅ | ❌ | 234 -> 274 | 347 -> 445 | 581 -> 719 | -23.8% | deterministic / deterministic |
| cls-10 (C) | classification | ❌ | ✅ | 199 -> 223 | 351 -> 191 | 550 -> 414 | +24.7% | extractor / deterministic |
| sum-01 | summarization | ✅ | ✅ | 287 -> 308 | 185 -> 158 | 472 -> 466 | +1.3% | judge / judge |
| sum-02 | summarization | ✅ | ✅ | 279 -> 301 | 97 -> 102 | 376 -> 403 | -7.2% | judge / judge |
| sum-03 | summarization | ✅ | ✅ | 264 -> 276 | 159 -> 124 | 423 -> 400 | +5.4% | judge / judge |
| sum-04 | summarization | ✅ | ✅ | 254 -> 274 | 120 -> 352 | 374 -> 626 | -67.4% | judge / judge |
| sum-05 (C) | summarization | ❌ | ❌ | 265 -> 288 | 178 -> 163 | 443 -> 451 | -1.8% | judge / judge |
| sum-06 | summarization | ✅ | ❌ | 249 -> 269 | 180 -> 181 | 429 -> 450 | -4.9% | judge / judge |
| sum-07 | summarization | ❌ | ❌ | 257 -> 277 | 186 -> 170 | 443 -> 447 | -0.9% | judge / judge |
| sum-08 | summarization | ❌ | ❌ | 203 -> 214 | 121 -> 116 | 324 -> 330 | -1.9% | judge / judge |
| sum-09 | summarization | ✅ | ✅ | 254 -> 265 | 152 -> 158 | 406 -> 423 | -4.2% | judge / judge |
| sum-10 | summarization | ✅ | ❌ | 256 -> 267 | 173 -> 181 | 429 -> 448 | -4.4% | judge / judge |
| cod-01 | coding | ✅ | ✅ | 208 -> 235 | 867 -> 160 | 1075 -> 395 | +63.3% | sandbox / sandbox |
| cod-02 | coding | ✅ | ✅ | 146 -> 185 | 575 -> 156 | 721 -> 341 | +52.7% | sandbox / sandbox |
| cod-03 | coding | ✅ | ✅ | 185 -> 212 | 964 -> 286 | 1149 -> 498 | +56.7% | sandbox / sandbox |
| cod-04 | coding | ✅ | ✅ | 183 -> 222 | 1081 -> 329 | 1264 -> 551 | +56.4% | sandbox / sandbox |
| cod-05 | coding | ❌ | ✅ | 145 -> 183 | 2048 -> 390 | 2193 -> 573 | +73.9% | sandbox / sandbox |
| cod-06 | coding | ✅ | ✅ | 174 -> 213 | 949 -> 415 | 1123 -> 628 | +44.1% | sandbox / sandbox |
| cod-07 (C) | coding | ✅ | ✅ | 155 -> 181 | 602 -> 216 | 757 -> 397 | +47.6% | sandbox / sandbox |
| cod-08 | coding | ✅ | ✅ | 168 -> 207 | 1404 -> 402 | 1572 -> 609 | +61.3% | sandbox / sandbox |
| cod-09 | coding | ❌ | ✅ | 173 -> 212 | 792 -> 161 | 965 -> 373 | +61.3% | sandbox / sandbox |
| cod-10 (C) | coding | ✅ | ❌ | 220 -> 245 | 1753 -> 1024 | 1973 -> 1269 | +35.7% | sandbox / sandbox |

(C) = routed to Stage C (A+B+C). Reduction: positive = the optimized prompt used fewer tokens.

### Answers

<details><summary><b>cqa-01</b> Hostel fee notice: total payable by a second-year student who pays late: vague ❌, optimized ✅</summary>

Vague prompt: `im in 2nd yr, already in boys hostel. if i pay on 18 july how much total??`  
Gold: **80300**

**vague** ❌ (gold answer not in the response):

```text
**Total amount you need to pay on 18 July 2026**

| Fee component | Amount (₹) |
|---------------|------------|
| Room rent (Boys’ hostel) | 38,000 |
| Mess charges | 42,000 |
| Caution deposit* | 5,000 |
| **Subtotal** | **85,000** |
| Late fee (3 days × ₹100) | 300 |
| **Grand total** | **85,300** |

\*The caution deposit is a one‑time, refundable amount that you pay only at the time of your first admission to the hostel. If you have already paid it in a previous year, you do **not** need to pay it again.

So, if you make the payment on **18 July 2026**, the amount you should remit through the ERP portal is **₹ 85,300**.
```

**optimized** ✅:

```text
The annual room rent (₹38,000) plus mess charges (₹42,000) total ₹80,000. Paying on 18 July is 3 days late, incurring a ₹100 per‑day late fee → ₹300. Hence the amount due is **₹80,300**.
```

</details>

<details><summary><b>cqa-02</b> End-semester timetable with a corrigendum that moves one paper: vague ✅, optimized ✅</summary>

Vague prompt: `when is my CD paper`  
Gold: **17 Nov 2026**

**vague** ✅:

```text
Your **Computer Design (CD) / Compiler Design** paper was originally scheduled for **10 November 2026**, but because of the Diwali holiday it has been **rescheduled to 17 November 2026**.

- **New date:** **17 Nov 2026**  
- **Time:** 10:00 am – 1:00 pm (same as the other end‑semester exams)  

All other papers remain on their originally announced dates. Good luck with your preparation!
```

**optimized** ✅:

```text
Your Compiler Design (CD) paper is scheduled for **17 November 2026** (rescheduled from 10 Nov due to the Diwali holiday).
```

</details>

<details><summary><b>cqa-03</b> Inter-department T20 scorecard without the total: target for the chasing side: vague ✅, optimized ✅</summary>

Vague prompt: `wat was the target for mech?`  
Gold: **154**

**vague** ✅:

```text
**Target for Mechanical:** **154 runs**  

*Explanation:*  
- CSE total = 34 + 12 + 0 + 45 + 7 + 22 + 3 + 18 + 1 = 142 runs  
- Extras = 11 runs  
- Overall CSE score = 142 + 11 = 153 runs  

Therefore, Mechanical needs **154 runs** to win.
```

**optimized** ✅:

```text
The CSE side scored 142 runs off the bat plus 11 extras, for a total of **153 runs**.  
Therefore, the Mechanical team’s target was **154 runs** to win.
```

</details>

<details><summary><b>cqa-04</b> Recipe for 4 scaled to 10 people: vague ✅, optimized ✅</summary>

Vague prompt: `making this for 10 ppl in hostel, how much poha`  
Gold: **5 cups**

**vague** ✅:

```text
**Kanda Poha – Scaled for ≈ 10 people (about 2½ × the original 4‑serving recipe)**  

| Ingredient | Original (4 servings) | × 2.5 (≈10 servings) | How to measure / notes |
|------------|----------------------|---------------------|------------------------|
| Thick poha (flattened rice) | 2 cups | **5 cups** | Rinse in a strainer; do **not** soak. |
| Onion, large | 1 | **2½ large** (≈ 2 ½ medium) | Peel and chop finely. |
| Green chilies | 2 | **5 chilies** | Slit or finely chop (adjust to heat preference). |
| Turmeric powder | ½ tsp | **1 ¼ tsp** | Can round to 1 ¼ tsp or 1 ½ tsp if you like a deeper colour. |
| Mustard seeds | 1 tsp | **2½ tsp** (≈ ½ Tbsp) | |
| Curry leaves | 10‑12 | **25‑30 leaves** | Fresh is best; tear gently before adding. |
| Peanuts | ¼ cup | **⅝ cup** (≈ ½ cup + 2 Tbsp) | Roughly chopped or left whole. |
| Oil (vegetable, canola, or peanut) | 1 Tbsp | **2½ Tbsp** (≈ 2 Tbsp + 1½ tsp) | |
| Salt | to taste | to taste | Start with ½ tsp, adjust after mixing. |
| Sugar | to taste | to taste | ½ tsp is a good baseline; increase if you like a sweeter poha. |
| Lemon (for serving) | wedges | **1 ½ – 2 lemons** (cut into wedges) | Squeeze over each plate just before eating. |

### Quick Method (scaled)

1. **Rinse the poha** in a fine‑mesh strainer under running water until it’s clean but still separate. Set aside in a large bowl.
2. Heat **2½ Tbsp oil** in a wide pan (or wok) over medium heat. Add **2½ tsp mustard seeds**; when they pop, add the **25‑30 curry leaves** and **5 chopped green chilies**. Sauté 30 seconds.
3. Add the **chopped onion** and sauté until translucent (≈ 3‑4 min). Sprinkle **1¼ tsp turmeric** and stir quickly.
4. Toss in the **⅝ cup peanuts** and fry for another minute for extra crunch.
5. Add the rinsed poha, **salt**, and **½ tsp sugar** (or to taste). Mix gently, cooking 3‑4 min until the poha is heated through and evenly coated.
6. Taste and adjust seasoning. Remove from heat, garnish with extra peanuts or fresh coriander if you like, and serve with **lemon wedges** on the side.

> **Tip for a hostel kitchen:**  
> Use a large, shallow tray or a big sauté pan so the poha spreads out; this prevents it from steaming and becoming soggy. If you don’t have a 5‑cup measuring cup, simply measure 2 cups twice (4 cups) and then add another cup‑half.

Enjoy your hearty, hostel‑friendly Kanda Poha! 🍽️
```

**optimized** ✅:

```text
{
  "amount": "For 10 people (2.5 × the original recipe):\n- 5 cups thick poha\n- 2½ large onions (about 2‑3 onions)\n- 5 green chillies\n- 1¼ tsp turmeric\n- 2½ tsp mustard seeds\n- 25‑30 curry leaves\n- 5/8 cup peanuts (≈2/3 cup)\n- 2½ tbsp oil\n- Salt, sugar, and lemon to taste"
}
```

</details>

<details><summary><b>cqa-05</b> Placement notice with three companies: one company's CGPA cut-off for B.Tech: vague ✅, optimized ✅</summary>

Vague prompt: `infosys min cgpa for btech?`  
Gold: **6.5**

**vague** ✅:

```text
**Infosys – Specialist Programmer (B.Tech)**  

- **Minimum CGPA:** **6.5** (or 60 % aggregate) throughout the program.  
- **Backlog policy:** You may have **at most one dead backlog** (i.e., a backlog that has not been cleared).  
- **Eligible branches:** CSE, IT, E&TC.  

So, to be eligible for the Infosys campus drive as a B.Tech student, you need a CGPA of **6.5 or higher** and no more than one unresolved backlog.
```

**optimized** ✅:

```text
Infosys requires a minimum CGPA of **6.5** (or 60 % aggregate) for B.Tech students in CSE, IT, or E&TC. This is the eligibility criterion listed for the Specialist Programmer role.
```

</details>

<details><summary><b>cqa-06</b> Prepaid recharge plans: cheapest per day with at least 2 GB/day: vague ✅, optimized ✅</summary>

Vague prompt: `need min 2gb per day, which plan is cheapest per day?`  
Gold: **P5**

**vague** ✅:

```text
**Cheapest plan that gives you ≥ 2 GB per day**

| Plan | Price (₹) | Validity | Data per day | Cost per day (₹) |
|------|-----------|----------|--------------|------------------|
| **P5** | 2,999 | 365 days | 2.5 GB | **≈ 8.22** |
| P3 | 719 | 84 days | 2 GB | ≈ 8.56 |
| P4 | 859 | 84 days | 2.5 GB | ≈ 10.23 |
| P2 | 349 | 28 days | 2 GB | ≈ 12.46 |

All other plans either give less than 2 GB per day or have a higher cost per day.

**Therefore, the cheapest way to get at least 2 GB each day is the annual **P5** plan (₹2,999 for 365 days), costing about ₹8.22 per day.**
```

**optimized** ✅:

```text
The plan that meets the minimum 2 GB/day requirement and has the lowest cost per day is **P5** (Rs 2,999 for 365 days, giving 2.5 GB/day, which works out to about Rs 8.22 per day).
```

</details>

<details><summary><b>cqa-07</b> Library overdue fine with two slabs: vague ✅, optimized ✅</summary>

Vague prompt: `how much fine do i pay for the OS book`  
Gold: **34**

**vague** ✅:

```text
**Step‑by‑step calculation**

| Item | Date |
|------|------|
| Issue date | 19 Sep 2026 |
| Due date   | 3 Oct 2026 |
| Return date| 14 Oct 2026 |

1. **Determine the number of days overdue**  
   - The book was due on **3 Oct**.  
   - It was returned on **14 Oct**.  
   - Days of delay = 14 Oct – 3 Oct = **11 days** (the library counts Sundays as delay days, so no adjustment is needed).

2. **Apply the fine schedule**  

| Delay period | Rate per day | Days in period | Fine |
|--------------|--------------|----------------|------|
| First 7 days | Rs 2         | 7              | 7 × 2 = Rs 14 |
| After first 7 days | Rs 5 | 11 – 7 = 4 | 4 × 5 = Rs 20 |

3. **Total fine**  
   - Rs 14 + Rs 20 = **Rs 34**

---

**Answer:** You need to pay **Rs 34** as the fine for the overdue “Operating System Concepts” book.
```

**optimized** ✅:

```text
The book was returned 11 days after the due date.  
Fine = (7 days × Rs 2) + (4 days × Rs 5) = Rs 14 + Rs 20 = **Rs 34**.
```

</details>

<details><summary><b>cqa-08</b> Bus timetable on a Sunday: earliest arrival: vague ✅, optimized ✅</summary>

Vague prompt: `its sunday, i reach the stand at 8.10, which bus gets me to kolhapur earliest?`  
Gold: **08:30**

**vague** ✅:

```text
You’ll catch the **08:30 Ordinary** bus.

- **Departure:** 08:30 (you’re already at the stand by 08:10)  
- **Travel time:** 1 hour 50 minutes  
- **Estimated arrival in Kolhapur:** **10:20 am**

The later buses (09:00 Shivshahi and 09:30 Ordinary) would get you to Kolhapur at about 10:25 am and 11:20 am respectively, so the 08:30 Ordinary is the earliest option.
```

**optimized** ✅:

```text
The next bus after you reach the stand at 8:10 is the **08:30 Ordinary** service, which takes 1 hour 50 minutes and reaches Kolhapur at 10:20. This is the earliest possible arrival on Sunday.
```

</details>

<details><summary><b>cqa-09</b> Online deal: final price with coupon and a capped bank discount: vague ✅, optimized ✅</summary>

Vague prompt: `final price if i use sbi card n coupon?`  
Gold: **1149**

**vague** ✅:

```text
**Final price calculation**

| Step | Amount (₹) | Explanation |
|------|------------|-------------|
| Deal price | 1,299 | Base price after the 35 % off sale |
| Coupon discount | **‑50** | Rs 50 off applied on the deal price |
| Price after coupon | **1,249** | 1,299 ‑ 50 |
| SBI‑card instant discount | **‑100** (max) | 10 % of 1,249 = 124.9, but the offer caps at Rs 100 |
| **Final price** | **1,149** | 1,249 ‑ 100 |

**Result:** The SoundPods X1 TWS earbuds will cost **₹ 1,149** after applying the Rs 50 coupon and the SBI‑card instant discount (capped at Rs 100). Delivery is free.
```

**optimized** ✅:

```text
The deal price is Rs 1,299. After applying the Rs 50 coupon, the price becomes Rs 1,249. The SBI card gives a 10 % discount up to Rs 100, so you get the maximum Rs 100 off, making the final price Rs 1,149.
```

</details>

<details><summary><b>cqa-10</b> Attendance report: lectures one can still miss and keep 75%: vague ❌, optimized ✅</summary>

Vague prompt: `how many more dbms lectures can i bunk n still get 75`  
Gold: **5**

**vague** ❌ (gold answer not in the response):

```text
**Database Engineering (DBMS) – How many more lectures can you miss?**

| Item | Value |
|------|-------|
| Lectures planned for the whole semester | **60** |
| Minimum attendance required (75 % of 60) | **45** lectures |
| Lectures you have already attended | **38** |
| Lectures you can still attend to reach 45 | **45 – 38 = 7** |
| Lectures remaining in the semester (planned – conducted) | **60 – 48 = 12** |

You need **45** attended lectures to meet the 75 % rule. You have already attended **38**, so you can still attend **7** more lectures and still be at the required threshold.

Since there are **12** lectures left in the semester, you can afford to miss up to **7** of those remaining lectures and still end up with exactly 45 attended lectures (75 % attendance).

**Answer:** You can bunk **up to 7 more DBMS lectures** (out of the 12 that are still to be held) and still meet the 75 % attendance requirement.
```

**optimized** ✅:

```text
You need at least 45 attendances (75 % of 60). You already have 38, so you must attend at least 7 of the remaining 12 lectures. Therefore you can bunk at most 5 more DBMS lectures and still reach 75 %.
```

</details>

<details><summary><b>ie-01</b> Drive notice for two companies: branches eligible for one of them: vague ✅, optimized ✅</summary>

Vague prompt: `which branches can apply for persistent`  
Gold: **CSE**, **IT**, **E&TC**

**vague** ✅:

```text
**Branches eligible for the Persistent Systems – Graduate Engineer Trainee role**

| Eligible Branches | Notes |
|-------------------|-------|
| **Computer Science & Engineering (CSE)** | Core software development focus |
| **Information Technology (IT)** | Similar skill set to CSE, strong programming emphasis |
| **Electronics & Tele‑Communication (E&TC)** | Works on embedded and hardware‑software integration |

**Not eligible** (for this specific role): Mechanical, Civil, Electrical, and any other non‑listed streams.

---

### Quick recap of the Persistent Systems posting

- **Position:** Graduate Engineer Trainee (GET)  
- **Eligibility:** 6.0 CGPA (or higher) with **no active backlogs**  
- **Application window:** Open now (check the T&P Cell drive notice for exact dates)  
- **Selection process:** Online test scheduled for **20 Oct** (follow the T&P Cell portal for the exact time and test format)  

If you belong to one of the three eligible branches and meet the academic criteria, you can go ahead and submit your application through the T&P Cell drive portal. Good luck!
```

**optimized** ✅:

```text
The eligible branches for the Persistent Systems Graduate Engineer Trainee role are **Computer Science and Engineering (CSE), Information Technology (IT), and Electronics & Tele‑Communication (E&TC)**. Mechanical, Civil, and Electrical students are not eligible.
```

</details>

<details><summary><b>ie-02</b> Project coordinator's email with a revised schedule: the deadlines: vague ✅, optimized ✅</summary>

Vague prompt: `list all deadlines frm this mail`  
Gold: **14 Oct**, **21 Oct**, **30 Nov**

**vague** ✅:

```text
**Deadlines from the email**

| # | Task | Deadline | Notes |
|---|------|----------|-------|
| 1 | Synopsis submission (via department portal) | **14 Oct 2026** | Original date (7 Oct) was extended |
| 2 | Mid‑semester progress report upload | **21 Oct 2026** |  |
| 3 | Final project report (hard‑bound, 2 copies) | **30 Nov 2026** |  |

*Additional information:* The department will be closed on **20 Oct 2026** for Dussehra (not a deadline, but a day when the office will be unavailable).
```

**optimized** ✅:

```text
Synopsis submission: 14 Oct 2026  
Mid-semester progress report upload: 21 Oct 2026  
Final project report (hard‑bound, 2 copies): 30 Nov 2026
```

</details>

<details><summary><b>ie-03</b> Bug thread from the college app: OS versions that crash: vague ✅, optimized ✅</summary>

Vague prompt: `which os versions hv the crash`  
Gold: **Android 12**, **Android 13**, **iOS 17.2**

**vague** ✅:

```text
**Operating system versions where the crash occurs**

| Platform | OS version(s) where the crash is reproduced |
|----------|---------------------------------------------|
| Android  | 12 – 13 (e.g., Android 12 on Samsung, Android 13 on Redmi Note 12) |
| iOS      | 17.2 (e.g., iPhone 13 on iOS 17.2) |

**Not affected**

| Platform | OS version(s) where the crash does **not** occur |
|----------|---------------------------------------------------|
| Android  | 14 (e.g., Pixel 7) |
| iOS      | 17.4 (crash stopped after updating) |

So, the problematic OS versions are **Android 12, Android 13, and iOS 17.2**.
```

**optimized** ✅:

```text
The crash occurs on **Android 12**, **Android 13**, and **iOS 17.2**. It does not happen on Android 14 or iOS 17.4.
```

</details>

<details><summary><b>ie-04</b> Result sheet: students with a backlog (F or absent): vague ✅, optimized ✅</summary>

Vague prompt: `names of ppl with backlogs`  
Gold: **Rohan Patil**, **Vedant Joshi**, **Omkar Jadhav**

**vague** ✅:

```text
**Students with backlogs (i.e., at least one F or AB grade):**

- Rohan Patil – OS = **F**  
- Vedant Joshi – CN = **AB** (absent)  
- Omkar Jadhav – DBMS = **F**, TOC = **F**  

These are the only students in the provided result sheet who have a failing or absent grade.
```

**optimized** ✅:

```text
Rohan Patil  
Vedant Joshi  
Omkar Jadhav
```

</details>

<details><summary><b>ie-05</b> Recipe: the dairy ingredients, for a lactose-intolerant friend: vague ✅, optimized ✅</summary>

Vague prompt: `my frnd is lactose intolerant, which ingredients here have dairy`  
Gold: **paneer**, **butter**, **fresh cream**, **curd**, **ghee**

**vague** ✅:

```text
**Ingredients that contain dairy**

| Ingredient | Why it’s considered dairy |
|------------|---------------------------|
| **Paneer** (250 g) | Fresh cheese made from milk |
| **Butter** (2 Tbsp) | Made from churned cream |
| **Fresh cream** (¼ cup) | Whipped or thickened cream |
| **Curd** (2 Tbsp) | Yogurt – cultured milk |
| **Ghee** (1 tsp) | Clarified butter (still a dairy fat) |

**Non‑dairy ingredients** (for reference)

- Oil, onions, tomatoes, cashew paste, ginger‑garlic paste, kasuri methi, salt, sugar, Kashmiri chilli powder.

If you need to make the dish safe for a lactose‑intolerant friend, you can replace the dairy items with suitable alternatives (e.g., tofu or soy paneer, plant‑based butter, coconut cream, dairy‑free yogurt, and a splash of oil instead of ghee).
```

**optimized** ✅:

```text
- Paneer  
- Butter  
- Fresh cream  
- Curd (whisked)  
- Ghee (used for the tadka)
```

</details>

<details><summary><b>ie-06</b> Train PNR status after charting: passengers with confirmed berths: vague ✅, optimized ✅</summary>

Vague prompt: `who all got confirmed seats?`  
Gold: **Suresh Naik**, **Arjun Naik**

**vague** ✅:

```text
**Confirmed passengers (seats allocated):**

| Passenger | Age | Gender | Current status |
|-----------|-----|--------|----------------|
| Suresh Naik | 52 | M | **CNF** (S4/33) |
| Arjun Naik | 21 | M | **CNF** (S6/18) |

The other two travelers are still on wait‑list (RAC 14 for Lata Naik and WL 3 for Meera Naik).
```

**optimized** ✅:

```text
Suresh Naik (Seat 4/33) and Arjun Naik (Seat 6/18) have confirmed seats.
```

</details>

<details><summary><b>ie-07</b> Batch-wise lab timetable: labs one batch has: vague ❌, optimized ✅</summary>

Vague prompt: `which labs does T2 have this week`  
Gold: **CN Lab**, **OS Lab**, **Web Technology Lab**

**vague** ❌ (also listed Wednesday: No lab (focus on mini-project), Friday: No lab scheduled):

```text
**T2’s lab schedule for the week (CSE Div B – practical batches)**  

| Day | Time | Lab (Subject) | Lab Location |
|-----|------|----------------|--------------|
| **Monday** | 10:00 – 12:00 | **CN Lab** | Lab 5 |
| **Tuesday** | 14:00 – 16:00 | **OS Lab** | Lab 2 |
| **Wednesday** | 10:00 – 12:00 | *No lab* – mini‑project hours (work on your project, not a designated lab) |
| **Thursday** | 14:00 – 16:00 | **Web Technology Lab** (shared with T3) | Lab 4 |
| **Friday** | — | No practical session scheduled | — |

**Summary for T2**

- **Monday:** CN (Computer Networks) – Lab 5  
- **Tuesday:** OS (Operating Systems) – Lab 2  
- **Wednesday:** No lab (focus on mini‑project)  
- **Thursday:** Web Technology – Lab 4 (with T3)  
- **Friday:** No lab scheduled  

That’s the complete list of labs (and non‑lab work) for T2 this week. Let me know if you need any other details!
```

**optimized** ✅:

```text
This week T2 has the following labs: Monday – CN Lab (Lab 5); Tuesday – OS Lab (Lab 2); Thursday – Web Technology Lab (Lab 4). (Wednesday is a mini‑project session and Friday has no practical for T2.)
```

</details>

<details><summary><b>ie-08</b> Bank statement: payments (debits) above Rs 5,000: vague ❌, optimized ✅</summary>

Vague prompt: `list payments above 5000 i made this month`  
Gold: **WCE Sangli fees**, **Decathlon Sports**, **MakeMyTrip**

**vague** ❌ (also listed 05‑09 | UPI – Reliance Digital | **5,000.00**):

```text
**Payments > ₹5,000 (debits) for September 2026**

| Date | Description | Amount (Rs) |
|------|-------------|-------------|
| 03‑09 | NEFT – WCE Sangli Fees | **45,500.00** |
| 05‑09 | UPI – Reliance Digital | **5,000.00** |
| 10‑09 | UPI – Decathlon Sports | **6,299.00** |
| 18‑09 | UPI – MakeMyTrip | **8,740.00** |

*Only debit (Dr) entries above ₹5,000 are shown; credit entries and amounts ≤ ₹5,000 have been omitted.*
```

**optimized** ✅:

```text
'''text
Date  | Description          | Amount (Rs) | Dr/Cr
03-09 | NEFT/WCE SANGLI FEES |   45,500.00 | Dr
10-09 | UPI/Decathlon Sports |    6,299.00 | Dr
18-09 | UPI/MakeMyTrip       |    8,740.00 | Dr
'''
```

</details>

<details><summary><b>ie-09</b> Django traceback plus comments: files in the failing tracebacks: vague ✅, optimized ✅</summary>

Vague prompt: `list the files in the failing tracebacks here`  
Gold: **erp/marks/views.py**, **erp/marks/utils.py**, **erp/attendance/utils.py**, **erp/attendance/views.py**

**vague** ✅:

```text
Here are the Python modules that appear in the stack‑traces for the failures you described:

| Traceback location | File (relative to the project root) |
|--------------------|--------------------------------------|
| `upload_marks` → `parse_row` | **`erp/marks/views.py`** (line 142) |
| `parse_row` (KeyError) | **`erp/marks/utils.py`** (line 58) |
| Attendance upload → `parse_row` | **`erp/attendance/views.py`** (line 77) |
| `parse_row` (KeyError) | **`erp/attendance/utils.py`** (line 31) |

(You also mentioned a couple of other modules that are **not** part of the failing tracebacks: `erp/core/middleware.py` and `erp/timetable/views.py`.)
```

**optimized** ✅:

```text
- `erp/marks/views.py`  
- `erp/marks/utils.py`  
- `erp/attendance/views.py`  
- `erp/attendance/utils.py`
```

</details>

<details><summary><b>ie-10</b> Scholarship notice: documents for a renewal (not a fresh) application: vague ❌, optimized ✅</summary>

Vague prompt: `what docs do i need for scholarship renewal, i got it last yr`  
Gold: **income certificate**, **previous year's marksheet**, **fee receipt**, **bank passbook**

**vague** ❌ (also listed (Optional) Declaration/Signature):

```text
Here’s a quick checklist of exactly what you need to upload for **renewal** of the Post‑Matric Scholarship (Maha DBT) for the 2026‑27 academic year:

| Document | Why it’s needed | How to prepare / upload |
|----------|----------------|--------------------------|
| **Income certificate (FY 2025‑26)** | Confirms that your family’s annual income is still within the eligibility limit. | Obtain a fresh certificate from the Tahsildar/Revenue Department (or the online portal if your state offers it). Make sure the financial year shown is **2025‑26** (the same year you used for the original award). |
| **Previous year’s marksheet** (SSC/HSC/Diploma + College‑level if applicable) | Shows you maintained the required academic performance. | Scan the **final consolidated marksheet** (or the latest semester/term result) in PDF or high‑resolution JPG/PNG. The document should be legible and include the university/board seal. |
| **Fee receipt for 2026‑27** | Proves you have paid (or are about to pay) the tuition/fees for the current year. | Upload the **official receipt** from your college/university (or the online payment screenshot) that clearly shows: <br>• Your name & enrollment number <br>• Amount paid <br>• Academic year 2026‑27 <br>• Institution’s name and stamp/signature |
| **Aadhaar‑seeded bank passbook (or passbook screenshot)** | Required for direct transfer of the scholarship amount. | Ensure your bank account is linked to your Aadhaar. Take a clear photo or PDF of the **first page of the passbook** (showing account number, bank name, and Aadhaar‑seeding confirmation) or a **bank statement** that displays the same details. |
| **(Optional) Declaration/Signature** | Some portals ask you to tick a box or upload a signed declaration. | If prompted, type your name electronically or upload a scanned signature page. |

### What **NOT** to upload (since you’re renewing)

- Caste certificate / caste‑validity certificate  
- Domicile certificate  
- SSC marksheet (if you already submitted it last year and the portal doesn’t ask again)  

These were already verified during your 2025‑26 award, so you can skip them.

### Step‑by‑step upload guide

1. **Log in** to the Maha DBT scholarship portal with your registered username/password (or use the OTP‑based login if that’s the current method).  
2. Navigate to **“Renewal – 2026‑27”** (usually under “My Applications” → “Renew”).  
3. **Upload** each document in the order the portal asks:
   - Income certificate → *PDF, ≤ 2 MB*  
   - Previous year’s marksheet → *PDF/JPG, ≤ 2 MB*  
   - Fee receipt → *PDF/JPG, ≤ 2 MB*  
   - Aadhaar‑seeded bank passbook → *PDF/JPG, ≤ 2 MB*  
4. **Review** the preview to ensure everything is legible.  
5. **Submit** the application. You should receive an on‑screen confirmation number and an email/SMS acknowledgment.  
6. **Save** the acknowledgment screenshot or PDF for your records; you may need it if there’s any follow‑up.

### Important dates & tips

- **Last date to submit:** **31 Oct 2026** (midnight). Aim to finish at least a week earlier to avoid last‑minute glitches.  
- **Check your email** for any “missing document” alerts within 48 hours of submission.  
- **Keep originals** handy; you may be asked to present them during a physical verification or audit.  
- If your **income has changed** (e.g., increased above the eligibility limit), you must inform the scholarship office; otherwise the renewal will be rejected.  

That’s it! Gather those four documents, upload them before the deadline, and you should be all set for another year of support. Good luck with your studies!
```

**optimized** ✅:

```text
For renewal you need to upload:

1. Income certificate for FY 2025‑26.  
2. Your previous year’s marksheet.  
3. Fee receipt for the 2026‑27 academic year.  
4. An Aadhaar‑seeded bank passbook.
```

</details>

<details><summary><b>cls-01</b> Pressure-cooker reviews: positive / negative / mixed, incl. sarcasm: vague ✅, optimized ✅</summary>

Vague prompt: `classify these reviews pos neg or mixed`  
Gold: R1: **positive**; R2: **negative**; R3: **mixed**; R4: **negative**; R5: **positive**; R6: **mixed**; R7: **mixed**; R8: **positive**

**vague** ✅:

```text
**R1:** Positive  
**R2:** Negative  
**R3:** Mixed  
**R4:** Negative  
**R5:** Positive  
**R6:** Mixed  
**R7:** Mixed  
**R8:** Positive
```

**optimized** ✅:

```text
R1: pos  
R2: neg  
R3: mixed  
R4: neg  
R5: pos  
R6: mixed  
R7: mixed  
R8: pos
```

</details>

<details><summary><b>cls-02</b> Student's monthly expenses into four categories: vague ✅, optimized ✅</summary>

Vague prompt: `put these expenses in food travel education entertainment`  
Gold: E1: **food**; E2: **travel**; E3: **education**; E4: **entertainment**; E5: **travel**; E6: **food**; E7: **education**; E8: **entertainment**; E9: **travel**

**vague** ✅:

```text
**Food**  
- E1  Zomato – biryani order during exam week – Rs 289  
- E6  Canteen thali – Rs 70  

**Travel**  
- E2  Ola auto to college – Rs 74  
- E5  IRCTC – Sangli to Pune ticket (home visit) – Rs 335  
- E9  Rapido bike to the movie theatre – Rs 45  

**Education**  
- E3  Udemy – Python for Data Science course – Rs 449  
- E7  Xerox shop – assignment printouts – Rs 60  

**Entertainment**  
- E4  BookMyShow – movie tickets – Rs 520  
- E8  Spotify Premium, monthly – Rs 119
```

**optimized** ✅:

```text
- **Food**
  - E1  Zomato – biryani order during exam week – Rs 289  
  - E6  Canteen thali – Rs 70  

- **Travel**
  - E2  Ola auto to college – Rs 74  
  - E5  IRCTC – Sangli to Pune ticket, home visit – Rs 335  
  - E9  Rapido bike to the movie theatre – Rs 45  

- **Education**
  - E3  Udemy – Python for Data Science course – Rs 449  
  - E7  Xerox shop – assignment printouts – Rs 60  

- **Entertainment**
  - E4  BookMyShow – movie tickets – Rs 520  
  - E8  Spotify Premium, monthly – Rs 119
```

</details>

<details><summary><b>cls-03</b> College-app issue triage with the team's label guide: vague ✅, optimized ✅</summary>

Vague prompt: `label these issues bug feature or question`  
Gold: I1: **bug**; I2: **feature**; I3: **question**; I4: **bug**; I5: **feature**; I6: **question**; I7: **bug**; I8: **feature**

**vague** ✅:

```text
- I1: **bug**  
- I2: **feature**  
- I3: **question**  
- I4: **bug**  
- I5: **feature**  
- I6: **question**  
- I7: **bug**  
- I8: **feature**
```

**optimized** ✅:

```text
I1: bug  
I2: feature  
I3: question  
I4: bug  
I5: feature  
I6: question  
I7: bug  
I8: feature
```

</details>

<details><summary><b>cls-04</b> Mess menu: veg / non-veg under the mess committee's egg rule: vague ✅, optimized ✅</summary>

Vague prompt: `mark each dish veg or nonveg`  
Gold: D1: **veg**; D2: **non-veg**; D3: **non-veg**; D4: **veg**; D5: **non-veg**; D6: **veg**; D7: **non-veg**; D8: **veg**; D9: **veg**

**vague** ✅:

```text
**Hostel Mess Menu – Week 41 (Veg / Non‑Veg)**  

| Dish | Veg / Non‑Veg* |
|------|----------------|
| D1 Paneer tikka | **Veg** |
| D2 Egg bhurji | **Non‑Veg** (egg) |
| D3 Chicken biryani | **Non‑Veg** |
| D4 Dal tadka | **Veg** |
| D5 Fish fry | **Non‑Veg** |
| D6 Veg Manchurian | **Veg** |
| D7 Omelette sandwich | **Non‑Veg** (egg) |
| D8 Mushroom masala | **Veg** |
| D9 Eggless chocolate cake | **Veg** |

\*According to the mess committee rule, any dish containing egg is classified as **non‑veg**. All other dishes are classified based on their primary ingredients.
```

**optimized** ✅:

```text
'''json
[
  { "dish": "Paneer tikka", "label": "veg" },
  { "dish": "Egg bhurji", "label": "non-veg" },
  { "dish": "Chicken biryani", "label": "non-veg" },
  { "dish": "Dal tadka", "label": "veg" },
  { "dish": "Fish fry", "label": "non-veg" },
  { "dish": "Veg Manchurian", "label": "veg" },
  { "dish": "Omelette sandwich", "label": "non-veg" },
  { "dish": "Mushroom masala", "label": "veg" },
  { "dish": "Eggless chocolate cake", "label": "veg" }
]
'''
```

</details>

<details><summary><b>cls-05</b> Placement offers into Normal / Dream / Super Dream by CTC policy: vague ❌, optimized ✅</summary>

Vague prompt: `categorise these offers normal dream super dream as per policy`  
Gold: O1: **normal**; O2: **dream**; O3: **super dream**; O4: **dream**; O5: **dream**; O6: **dream**; O7: **super dream**; O8: **normal**; O9: **normal**

**vague** ❌ (O9: dream (gold normal)):

```text
**Categorisation (based only on the annual CTC – one‑time bonuses, joining or relocation payments are ignored):**

| Offer | Stated CTC (annual) | CTC used for categorisation* | Category |
|-------|--------------------|-----------------------------|----------|
| O1 – Infosys | Rs 3.6 LPA | Rs 3.6 LPA | **Normal** |
| O2 – Persistent Systems | Rs 6 LPA | Rs 6 LPA | **Dream** (lower bound inclusive) |
| O3 – Barclays | Rs 12 LPA | Rs 12 LPA | **Super Dream** |
| O4 – Finlytics (startup) | Rs 50,000 × 12 = Rs 6 LPA | Rs 6 LPA | **Dream** |
| O5 – Deloitte | Rs 6.6 LPA CTC + Rs 1 Lakh joining bonus | Rs 6.6 LPA (bonus excluded) | **Dream** |
| O6 – Amazon | Rs 10 LPA | Rs 10 LPA | **Dream** (upper bound inclusive) |
| O7 – Zeus Learning | Rs 10.5 LPA | Rs 10.5 LPA | **Super Dream** |
| O8 – Mphasis | Rs 4.2 LPA | Rs 4.2 LPA | **Normal** |
| O9 – Cognizant | Rs 6.3 LPA CTC + Rs 0.5 Lakh relocation bonus | Rs 6.3 LPA (bonus excluded) | **Dream** |

\*Only the recurring annual CTC is considered; any one‑time payments (joining bonus, relocation allowance, etc.) are **not** part of the categorisation.
```

**optimized** ✅:

```text
O1: Normal  
O2: Dream  
O3: Super Dream  
O4: Dream  
O5: Dream  
O6: Dream  
O7: Super Dream  
O8: Normal  
O9: Normal
```

</details>

<details><summary><b>cls-06</b> SMS inbox: legit / promo / scam: vague ✅, optimized ✅</summary>

Vague prompt: `which of these sms r legit, promo or scam`  
Gold: M1: **legit**; M2: **scam**; M3: **legit**; M4: **scam**; M5: **scam**; M6: **legit**; M7: **promo**; M8: **promo**; M9: **scam**

**vague** ✅:

```text
**Classification**

| Message | Category | Why |
|---------|----------|-----|
| **M1** | **Legit** | Contains a one‑time password for a known service (college ERP). No request for money or personal data. |
| **M2** | **Scam** | Claims a huge prize and asks for a “processing fee.” Classic lottery‑win scam. |
| **M3** | **Legit** (but could be **promo** if it’s a marketing push) | Looks like a routine bill reminder from an electricity board. No link or money‑up‑front request, just a payment instruction. |
| **M4** | **Scam** | Promises instant loan with “no documents” and a shortened link – typical loan‑advance fraud. |
| **M5** | **Scam** | Threatens account blockage and forces the user to a suspicious domain for KYC – phishing. |
| **M6** | **Legit** | Order‑status update from a food‑delivery service; no action beyond information. |
| **M7** | **Promo** | Advertising a discount (“Flat 70% OFF”) – a legitimate promotional message (assuming it comes from the brand). |
| **M8** | **Promo** | Offers a data‑top‑up deal; promotional in nature, not requesting personal info. |
| **M9** | **Scam** | Claims a parcel is held and demands payment via an unfamiliar website – classic “customs release” scam. |

**Summary**

- **Legit (transactional/notification)**: M1, M3, M6  
- **Promotional**: M7, M8  
- **Scam/Phishing**: M2, M4, M5, M9  

*Tip:* When in doubt, verify the sender’s official number/email, avoid clicking short links, and never pay fees to claim prizes or release parcels.
```

**optimized** ✅:

```text
M1 – legit; M2 – scam; M3 – legit; M4 – scam; M5 – scam; M6 – legit; M7 – promo; M8 – promo; M9 – scam.
```

</details>

<details><summary><b>cls-07</b> Student queries routed to the right office: vague ❌, optimized ❌</summary>

Vague prompt: `which office shud each query go to`  
Gold: Q1: **exam cell**; Q2: **accounts**; Q3: **library**; Q4: **hostel office**; Q5: **exam cell**; Q6: **accounts**; Q7: **library**; Q8: **hostel office**

**vague** ❌ (Q7: accounts (gold library)):

```text
**Office assignments**

| Query | Office that should handle it |
|-------|------------------------------|
| Q1: My hall ticket for the end‑sem exam has not been generated. | **Exam Cell** |
| Q2: I paid the tuition fee online but the receipt is not showing on ERP. | **Accounts** |
| Q3: I lost my library card and need a duplicate. | **Library** |
| Q4: The fan in room B‑214 has not been working for a week. | **Hostel Office** |
| Q5: I need the revaluation form for the Compiler Design paper. | **Exam Cell** |
| Q6: When will my hostel caution deposit be refunded? I left the hostel in May. | **Accounts** (refunds are processed by Accounts) |
| Q7: I paid my overdue fine but the system still shows it as pending. | **Accounts** |
| Q8: Complaint about the quality of mess food on weekends. | **Hostel Office** |
```

**optimized** ❌ (Q7: accounts (gold library)):

```text
{
  "queries": [
    {
      "question": "My hall ticket for the end-sem exam has not been generated.",
      "office": "Exam cell"
    },
    {
      "question": "I paid the tuition fee online but the receipt is not showing on ERP.",
      "office": "Accounts"
    },
    {
      "question": "I lost my library card and need a duplicate.",
      "office": "Library"
    },
    {
      "question": "The fan in room B-214 has not been working for a week.",
      "office": "Hostel office"
    },
    {
      "question": "I need the revaluation form for the Compiler Design paper.",
      "office": "Exam cell"
    },
    {
      "question": "When will my hostel caution deposit be refunded? I left the hostel in May.",
      "office": "Accounts"
    },
    {
      "question": "I paid my overdue fine but the system still shows it as pending.",
      "office": "Accounts"
    },
    {
      "question": "Complaint about the quality of mess food on weekends.",
      "office": "Hostel office"
    }
  ]
}
```

</details>

<details><summary><b>cls-08</b> Big-O of short Python snippets: vague ✅, optimized ✅</summary>

Vague prompt: `time complexity of each? o(1) o(logn) o(n) o(nlogn) or o(n2)`  
Gold: S1: **O(1)**; S2: **O(log n)**; S3: **O(n)**; S4: **O(n log n)**; S5: **O(n^2)**; S6: **O(n log n)**; S7: **O(1)**; S8: **O(n)**

**vague** ✅:

```text
Below is the (average‑case) asymptotic running time for each snippet, expressed using the standard Big‑O notation.  
For the “dictionary / set” operations we assume the usual average‑case O(1) cost for look‑ups, insertions and membership tests.

| # | Code (short description) | Dominant work | Time‑complexity |
|---|---------------------------|---------------|-----------------|
| **S1** | Return the middle element of a list | Direct indexing (`arr[i]`) | **O(1)** |
| **S2** | Repeatedly halve `i` until it becomes ≤ 1 | Loop runs ⌊log₂ n⌋ + 1 times | **O(log n)** |
| **S3** | Two nested loops: outer over `arr` (size n), inner runs a constant 10 times | `n · 10` operations | **O(n)** |
| **S4** | `sorted(arr)` then take the first element | Sorting dominates; Python’s Timsort is O(n log n) on average | **O(n log n)** |
| **S5** | Naïve duplicate‑search: for each `i` scan all later elements | ∑_{i=0}^{n‑1}(n‑i‑1) = n(n‑1)/2 ≈ n²/2 | **O(n²)** |
| **S6** | Outer loop runs `n` times; inner loop doubles `j` each iteration → runs ≈ log₂ n times each outer iteration | n · log n | **O(n log n)** |
| **S7** | Membership test in a dict (`key in d`) | Average‑case hash‑table lookup | **O(1)** |
| **S8** | Scan `arr`; for each element do a set‑membership test and possibly an insertion | Each test/insertion is O(1) on average, performed `n` times | **O(n)** |

**Summary**

| Symbol | Snippets |
|--------|----------|
| **O(1)** | S1, S7 |
| **O(log n)** | S2 |
| **O(n)** | S3, S8 |
| **O(n log n)** | S4, S6 |
| **O(n²)** | S5 |

These complexities assume the usual Python list indexing, integer arithmetic, and hash‑table operations all run in constant time, and that the input size `n` is the length of the list/array (or the integer argument `n` where appropriate).
```

**optimized** ✅:

```text
'''python
complexities = {
    "S1": "O(1)",          # direct index access
    "S2": "O(log n)",      # repeatedly halve i
    "S3": "O(n)",          # outer loop over arr, inner loop constant (10)
    "S4": "O(n log n)",    # sorting dominates
    "S5": "O(n^2)",        # double loop over all pairs
    "S6": "O(n log n)",    # outer loop n times, inner loop logarithmic
    "S7": "O(1)",          # dict membership test average‑case
    "S8": "O(n)",          # set membership/addition average‑case linear scan
}
'''
```

</details>

<details><summary><b>cls-09</b> Attendance status per student from attended/conducted: vague ✅, optimized ❌</summary>

Vague prompt: `mark each student safe warning or detained`  
Gold: Aarav: **safe**; Bhakti: **warning**; Chinmay: **detained**; Diya: **safe**; Eshan: **detained**; Farhan: **warning**; Gauri: **safe**; Harsh: **warning**

**vague** ✅:

```text
**Attendance percentages and status**

| Roll | Name   | Attended | Conducted | Attendance % | Status |
|------|--------|----------|-----------|--------------|--------|
| 1    | Aarav  | 30       | 40        | 75 %         | **Safe** |
| 2    | Bhakti | 29       | 40        | 72.5 %       | **Warning** |
| 3    | Chinmay| 25       | 40        | 62.5 %       | **Detained** |
| 4    | Diya   | 39       | 52        | 75 %         | **Safe** |
| 5    | Eshan  | 33       | 52        | 63.46 %      | **Detained** |
| 6    | Farhan | 34       | 52        | 65.38 %      | **Warning** |
| 7    | Gauri  | 52       | 52        | 100 %        | **Safe** |
| 8    | Harsh  | 26       | 40        | 65 %         | **Warning** |

**Rule applied**

- **Detained**: attendance < 65 %  
- **Warning**: 65 % ≤ attendance < 75 %  
- **Safe**: attendance ≥ 75 %  

All students have been classified accordingly.
```

**optimized** ❌ (Bhakti: safe (gold warning); Chinmay: safe (gold detained); Eshan: safe (gold detained); Farhan: safe (gold warning); Harsh: safe (gold warning)):

```text
'''python
# Attendance classification script
# Rule: 
#   < 65%   -> Detained
#   65%–<75% -> Warning
#   >=75%   -> Safe

students = [
    {"roll": 1, "name": "Aarav",   "attended": 30, "conducted": 40},
    {"roll": 2, "name": "Bhakti",  "attended": 29, "conducted": 40},
    {"roll": 3, "name": "Chinmay", "attended": 25, "conducted": 40},
    {"roll": 4, "name": "Diya",    "attended": 39, "conducted": 52},
    {"roll": 5, "name": "Eshan",   "attended": 33, "conducted": 52},
    {"roll": 6, "name": "Farhan",  "attended": 34, "conducted": 52},
    {"roll": 7, "name": "Gauri",   "attended": 52, "conducted": 52},
    {"roll": 8, "name": "Harsh",   "attended": 26, "conducted": 40},
]

def classify(attended, conducted):
    percent = (attended / conducted) * 100
    if percent < 65:
        return "Detained"
    elif percent < 75:
        return "Warning"
    else:
        return "Safe"

# Process and display results
for s in students:
    status = classify(s["attended"], s["conducted"])
    print(f"Roll {s['roll']:>2} | {s['name']:<7} | {status}")
'''
```

</details>

<details><summary><b>cls-10</b> Language of each class-group message (Marathi / Hindi / English / mixed): vague ❌, optimized ✅</summary>

Vague prompt: `which language is each line - marathi hindi english or mixed`  
Gold: L1: **marathi**; L2: **hindi**; L3: **english**; L4: **marathi**; L5: **hindi**; L6: **mixed**; L7: **marathi**; L8: **mixed**; L9: **hindi**

**vague** ❌ (L9: mixed (gold hindi)):

```text
**Language identification**

| Line | Text | Language |
|------|------|----------|
| L1 | उद्या कॉलेजला सुट्टी आहे का? | **Marathi** |
| L2 | कल कॉलेज बंद रहेगा। | **Hindi** |
| L3 | Tomorrow's lab is cancelled, inform everyone. | **English** |
| L4 | मला परीक्षेची खूप भीती वाटते. | **Marathi** |
| L5 | मुझे परीक्षा से बहुत डर लगता है। | **Hindi** |
| L6 | Bhai kal ka lecture cancel hai kya? | **Mixed** (Hindi + English) |
| L7 | आम्ही उद्या पुण्याला जाणार आहोत. | **Marathi** |
| L8 | Submit kar de yaar assignment, deadline aaj hai. | **Mixed** (Hindi + English) |
| L9 | आज मेस में पनीर बना है। | **Mixed** (Hindi with an English loan‑word “mes”) |
```

**optimized** ✅:

```text
L1: marathi  
L2: hindi  
L3: english  
L4: marathi  
L5: hindi  
L6: mixed  
L7: marathi  
L8: mixed  
L9: hindi
```

</details>

<details><summary><b>sum-01</b> Accounts circular on fee payment with an extended date: vague ✅, optimized ✅</summary>

Vague prompt: `summarise this fee circular in like 3-4 points for class grp`  
Gold: must state: The last date is 25 October 2026 (extended).; Payment is online through the ERP portal only (no cash or DD).; A late fee of Rs 500 applies after the last date.; Not paying by 5 November 2026 means the exam form cannot be filled. | must not: States 20 October 2026 as the current last date (mentioning it as the old, extended date is fine).; Says cash (or DD) payment is accepted at the counter. | at most 100 words

**vague** ✅:

```text
**WALCHAND COLLEGE – Tuition Fee (2nd instalment) – A.Y. 2026‑27**

1. **Extended deadline:** Pay the 2nd instalment by **25 Oct 2026** (originally 20 Oct).  
2. **Online‑only payment:** Use the ERP portal; cash or demand drafts are **not accepted**.  
3. **Late fee:** Payments after 25 Oct will incur a **₹500 penalty**.  
4. **Scholarship & exam rule:**  
   - Scholarship students (EBC/OBC/SC/ST) pay only the balance shown on their ERP fee page.  
   - Anyone who hasn’t paid by **5 Nov 2026** cannot fill the end‑semester exam form.
```

**optimized** ✅:

```text
- **Extended deadline:** The second‑installment tuition fee deadline is now **25 Oct 2026** (originally 20 Oct).  
- **Payment method:** Fees must be paid **online via the ERP portal**; cash or demand drafts are not accepted.  
- **Late fee & exam restriction:** Payments after 25 Oct incur a **Rs 500 late fee**, and anyone who hasn’t paid by **5 Nov 2026** cannot submit the end‑semester exam form.  
- **Scholarship students:** Those with government scholarships (EBC/OBC/SC/ST) pay only the **remaining amount shown on their ERP fee page**.
```

</details>

<details><summary><b>sum-02</b> Bug report summarised for a team lead: vague ✅, optimized ✅</summary>

Vague prompt: `tldr of this bug for my team lead, short, under 60 words`  
Gold: must state: Attendance CSV uploads larger than 5 MB fail (413 / Request Entity Too Large).; It started with the v2.3 release.; Workaround: split the CSV into files under 5 MB.; Suspected cause: Nginx client_max_body_size lowered to 5M. | must not: Says data was lost or earlier uploads were deleted/corrupted.; Says students are affected. | at most 60 words

**vague** ✅:

```text
**TL;DR:** Since v2.3 (1 Oct), faculty uploads of attendance CSVs >5 MB return 413 “Request Entity Too Large”. Nginx’s `client_max_body_size` was lowered to 5 M (was 20 M). Workaround: split files <5 MB. High priority – monthly report due 10 Oct.
```

**optimized** ✅:

```text
**TL;DR:** After v2.3 (1 Oct), faculty uploads of attendance CSVs >5 MB now hit a 413 “Request Entity Too Large” error because the new Nginx config set `client_max_body_size` to 5 M (down from 20 M). Split files <5 MB as a workaround; fix by raising the limit. (High priority).
```

</details>

<details><summary><b>sum-03</b> Six laptop reviews into pros and cons: vague ✅, optimized ✅</summary>

Vague prompt: `sum up what ppl say abt this laptop, pros n cons, max 80 words`  
Gold: must state: Battery life is good (about 7-8 hours).; The keyboard is praised.; It heats up during gaming.; The display is dim outdoors / in sunlight. | must not: Says the speakers are good or loud.; Makes any claim about the price or value for money. | at most 80 words

**vague** ✅:

```text
**Vortex 14 (i5, 16 GB RAM, 512 GB SSD)**  

**Pros (≈ 35 words)**  
- Battery life 7‑8 hrs, enough for a full day of classes.  
- Light, portable chassis.  
- Fast boot‑up and solid performance for coding/work.  
- Keyboard praised as comfortable and responsive.  

**Cons (≈ 35 words)**  
- Gets noticeably hot and the fan turns loud during gaming or long sessions.  
- Display is dim, especially in bright sunlight.  
- Speakers are weak and tinny.  
- One buyer received the wrong colour (seller issue).
```

**optimized** ✅:

```text
**Summary (78 words)**  
The Vortex 14’s standout strengths are its long‑lasting battery (≈7‑8 hours) and a highly praised, comfortable keyboard that makes typing and fast boot‑ups enjoyable. Users also like its lightweight portability. However, the laptop runs hot and the fan gets noisy during gaming or extended use, and the display is noticeably dim in bright or outdoor settings. Audio quality is weak and tinny, and one buyer received the wrong colour, though the hardware itself was fine.
```

</details>

<details><summary><b>sum-04</b> Placement-drive notice summarised for WhatsApp: vague ✅, optimized ✅</summary>

Vague prompt: `short summary of this drive for whatsapp, 50 words max`  
Gold: must state: Open to B.Tech CSE and IT, 2027 batch only.; Minimum 6.5 CGPA and no active backlogs.; Online test on 22 Oct (interviews 23 Oct).; Register on the T&P portal by 15 Oct, 5 pm. | must not: Presents Rs 4.5 LPA as this year's package (saying it was last year's is fine).; Says other branches (e.g. Mechanical, E&TC) or all branches can apply. | at most 50 words

**vague** ✅:

```text
🚀 Sahyadri Data Systems (Pune) seeks B.Tech CSE/IT 2027 grads (≥6.5 CGPA, no backlogs) for Graduate Engineer Trainee (Software). Aptitude & coding test: 22 Oct (on‑campus). Tech & HR interviews: 23 Oct. Register by 15 Oct 5 pm on T&P portal. Bring ID & 2 resumes. Package TBD (≈4.5 LPA last year).
```

**optimized** ✅:

```text
- Sahyadri Data Systems seeks B.Tech CSE/IT 2027 grads (≥6.5 CGPA, no backlogs).  
- Online aptitude & coding test: 22 Oct (on‑campus), followed by technical & HR interviews on 23 Oct.  
- Register via T&P portal by 15 Oct, 5 pm (no late entries).  
- Bring college ID and two resume copies.
```

</details>

<details><summary><b>sum-05</b> Recipe method condensed for a beginner: vague ❌, optimized ❌</summary>

Vague prompt: `give me short steps for this, im a hostel noob, under 70 words`  
Gold: must state: Rinse the poha briefly; do not soak it.; Temper mustard seeds, then curry leaves, chillies and peanuts in oil.; Add turmeric after the onion has softened.; Add poha, salt and sugar, cover about 2 minutes on low heat.; Finish with lemon juice and coriander. | must not: Tells you to soak the poha for some minutes.; Adds garlic (or any ingredient not in the recipe, such as tomato or potato). | at most 70 words

**vague** ❌ (83 words > 70):

```text
**Kanda Poha (serves 4) – 7 quick steps**

1. Rinse 2 cups thick poha in a strainer 30 s; drain 5 min.  
2. Heat 1 Tbsp oil, add 1 tsp mustard seeds → splutter.  
3. Toss in curry leaves, 2 chopped green chilies, ¼ cup peanuts; fry till crisp.  
4. Add 1 chopped onion, sauté soft; stir in ½ tsp turmeric.  
5. Mix in poha, salt, 1 tsp sugar; cover, low heat 2 min.  
6. Turn off, squeeze lemon juice.  
7. Garnish with coriander. Enjoy!
```

**optimized** ❌ (76 words > 70):

```text
1. Rinse 2 cups thick poha in a strainer for 30 s; drain 5 min.  
2. Heat 1 tbsp oil, add 1 tsp mustard seeds. When they splutter, add curry leaves, 2 green chillies, ¼ cup peanuts; fry until crisp.  
3. Add 1 chopped onion, cook soft; stir in ½ tsp turmeric.  
4. Add poha, salt, 1 tsp sugar; mix gently, cover 2 min on low heat.  
5. Turn off, squeeze lemon juice, garnish with coriander.
```

</details>

<details><summary><b>sum-06</b> Class rep's industrial-visit message with a postponed date: vague ✅, optimized ❌</summary>

Vague prompt: `summarize this IV msg in 4-5 lines`  
Gold: must state: The visit is on Friday 16 Oct (postponed).; The bus leaves the main gate at 6:30 am.; Pay Rs 750 by 12 Oct.; Formals, safety shoes and college ID are required.; Lunch is not provided; carry your own lunch or money. | must not: Gives 9 Oct as the date of the visit (mentioning it as the old date is fine).; Says lunch is provided. | at most 90 words

**vague** ✅:

```text
**Industrial Visit – Shree Engine Works, Kagal (T.Y. Mech)**  
- New date: **Friday, 16 Oct** (originally 9 Oct, delayed due to plant audit).  
- Bus departs **6:30 am** from the main gate – be there by **6:15 am**; return ≈ **7 pm**.  
- Cost: **₹750 per person**, payable to the organizer by **Mon, 12 Oct** (UPI accepted).  
- Dress code: **formals + safety shoes** (no sandals); bring college ID.  
- Lunch not provided – bring your own or money for the plant canteen. Professors Patil and Desai will accompany the group.
```

**optimized** ❌ (92 words > 90):

```text
- The industrial visit to Shree Engine Works, Kagal is now scheduled for **Friday, 16 Oct** (originally 9 Oct, postponed due to an audit).  
- Meet at the main gate by **6:15 am**; the bus departs at **6:30 am** and you’ll return around **7 pm**.  
- **Contribution:** Rs 750 per person, payable to the organizer by **Monday, 12 Oct** (UPI accepted).  
- Dress code: **formal attire + safety shoes** (no sandals); bring your college ID.  
- **Lunch is not provided** – bring your own meal or money for the plant canteen. Professors Patil and Desai will accompany the group.
```

</details>

<details><summary><b>sum-07</b> Fest committee minutes for members who missed the meeting: vague ❌, optimized ❌</summary>

Vague prompt: `summarize minutes for ppl who missed the meeting, 60 words`  
Gold: must state: Fest dates: 14-16 Feb 2027.; Approved budget: Rs 2.4 lakh.; DJ night cancelled; a live band night replaces it.; Tanvi Shinde leads the sponsorship team.; Next meeting on 17 Oct, 5 pm. | must not: Says the approved budget is Rs 3 lakh.; Says there will be a DJ night. | at most 60 words

**vague** ❌ (83 words > 60):

```text
**Meeting Summary – Rangtarang 2027 Core Committee (3 Oct 2026)**  
Present: 14 members + faculty advisor Dr. Kulkarni.  

1. Fest dates fixed for 14‑16 Feb 2027 (21‑23 Feb rejected due to mid‑sem exams).  
2. Budget: Council asked for ₹3 Lakh; principal approved ₹2.4 Lakh. Sponsorship goal: raise an additional ₹1 Lakh.  
3. DJ night cancelled after last year’s police‑permission issue; a live band will replace it.  
4. Sponsorship team headed by Tanvi Shinde (T.Y. E&TC).  
5. Next meeting: 17 Oct 2026, 5 pm, Seminar Hall.
```

**optimized** ❌ (72 words > 60):

```text
- **Date & Venue:** Rangtarang 2027 will be held 14‑16 Feb 2027 (the 21‑23 Feb slot was dropped due to mid‑semester exams).  
- **Budget:** Student council requested ₹3 lakh; principal approved ₹2.4 lakh. Additional sponsorship of ₹1 lakh is targeted.  
- **Entertainment:** DJ night cancelled after last year’s police‑permission issue; a live band will perform instead.  
- **Sponsorship Lead:** Tanvi Shinde (T.Y. E&TC) will head the sponsorship team.  
- **Next Meeting:** 17 Oct 2026, 5 pm, Seminar Hall.
```

</details>

<details><summary><b>sum-08</b> Municipal water-cut notice for the hostel group: vague ❌, optimized ❌</summary>

Vague prompt: `quick summary of water cut notice for hostel grp under 50 words`  
Gold: must state: Vishrambag, Vijaynagar and the college campus area are affected.; No water on Tuesday 13 Oct, 6 am to 6 pm.; Supply resumes 14 Oct at low pressure; normal from 15 Oct.; Store water in advance (tankers on request at the ward office). | must not: Says Miraj or Kupwad (or the whole city) is affected.; Says there is no water at all on 14 Oct or that the cut lasts two days. | at most 50 words

**vague** ❌ (63 words > 50):

```text
**Water Cut Notice (≤50 words)**  
Due to urgent repairs on the main pipeline near Vishrambag, water will be shut off in Vishrambag, Vijaynagar and the college campus on Tue 13 Oct 2026, 6 am–6 pm. Service resumes Wed 14 Oct (low pressure) and returns to normal Thu 15 Oct. Miraj & Kupwad are unaffected. Store water; tankers available on request at the ward office.
```

**optimized** ❌ (59 words > 50):

```text
**Water Cut Notice (≤50 words)**  
Urgent repairs on the main pipeline near Vishrambag will halt water supply to Vishrambag, Vijaynagar and the college campus on Tuesday 13 Oct 2026, 6 am–6 pm. Service resumes Wednesday 14 Oct at low pressure, normal pressure by Thursday 15 Oct. Miraj & Kupwad unaffected. Store water; tankers available on request at the ward office.
```

</details>

<details><summary><b>sum-09</b> Mini-project abstract condensed for a slide: vague ✅, optimized ✅</summary>

Vague prompt: `summarize this abstract in 3 lines for my ppt`  
Gold: must state: Goal: detect fake product reviews in Marathi and Hindi.; Method: fine-tuned MuRIL (multilingual BERT).; Result: 91.2% accuracy (0.89 F1) vs 84.0% for the baseline.; Limitation: code-mixed reviews drop to 78%. | must not: Gives 84% as the proposed model's accuracy.; Says the model is deployed or available as a browser extension. | at most 70 words

**vague** ✅:

```text
- Collected 12.4 K Marathi/Hindi product reviews (plus 2.1 K hand‑labeled) and fine‑tuned MuRIL (multilingual BERT) to detect fake vs. genuine reviews.  
- Achieved 91.2 % accuracy and 0.89 F1 on a 1.86 K‑review test set, outperforming a TF‑IDF + logistic‑regression baseline (84 % accuracy).  
- Performance drops to 78 % on code‑mixed (Hinglish) reviews; deployment (e.g., browser extension) is planned for future work.
```

**optimized** ✅:

```text
- Collected ≈ 12.4 k Marathi/Hindi product reviews (plus 2.1 k manually labeled) and fine‑tuned the multilingual BERT model MuRIL for fake‑review detection.  
- Achieved 91.2 % accuracy (F1 = 0.89) on a held‑out test set of 1.86 k reviews, outperforming a TF‑IDF + logistic‑regression baseline (84 % accuracy).  
- Performance drops to ~78 % on code‑mixed (Hinglish) reviews; the system is not yet deployed, with a browser‑extension planned for future work.
```

</details>

<details><summary><b>sum-10</b> PG (paying-guest) agreement summarised for parents: vague ✅, optimized ❌</summary>

Vague prompt: `summarize pg rules main points under 80 words, need to tell my parents`  
Gold: must state: Rent Rs 7,500 per month, due by the 5th.; Deposit Rs 15,000 (two months), refundable minus damage.; One month's notice before leaving.; Electricity is extra (sub-meter).; Food is not included (tiffin Rs 3,000 separately). | must not: Says the deposit is non-refundable.; Says food or meals are included in the rent. | at most 80 words

**vague** ✅:

```text
**Sai Krupa PG – Key Rules (≤80 words)**  

- **Rent:** ₹7,500/month per bed (twin sharing); due by the 5th. Late fee ₹50/day.  
- **Deposit:** ₹15,000 (2 months’ rent), refundable after deducting any damage.  
- **Notice:** 1 month written notice; otherwise ₹7,500 is taken from deposit.  
- **Electricity:** Billed separately from sub‑meter, split between the two occupants.  
- **Food:** Not included; tiffin service ₹3,000/month if desired.  
- **Rules:** No overnight guests; gate closes 10:30 pm; no cooking in rooms.
```

**optimized** ❌ (83 words > 80):

```text
**Sai Krupa PG – key points (under 80 words)**  

- Rent: ₹7,500 / month per bed (twin sharing); due by the 5th. Late fee ₹50 per day.  
- Security deposit: ₹15,000 (two months’ rent); refundable after deducting any damage.  
- Notice: 1 month written notice to vacate; otherwise one month’s rent is taken from the deposit.  
- Electricity: billed separately from the room’s sub‑meter, split between the two occupants.  
- Food: not included; optional tiffin service ₹3,000 / month.  
- Rules: no overnight guests, gate closes 10:30 pm, no cooking in rooms.
```

</details>

<details><summary><b>cod-01</b> SGPA from (grade, credits) pairs under the college's grade-point table: vague ✅, optimized ✅</summary>

Vague prompt: `write this sgpa fn pls`  
Gold: `sgpa` passes 6 hidden asserts

**vague** ✅:

```text
Here’s a clean, well‑documented implementation that follows the specification exactly.  
It handles upper‑ or lower‑case grade strings, includes failed courses (FF) in the denominator, returns `0.0` when the input list is empty, and rounds the result to two decimal places.

'''python
def sgpa(courses):
    """
    Compute the Semester Grade Point Average (SGPA).

    Parameters
    ----------
    courses : list[tuple[str, (int | float)]]
        A list of (grade, credits) tuples.
        * grade  – one of "AA", "AB", "BB", "BC", "CC", "CD", "DD", "FF"
                   (case‑insensitive).
        * credits – numeric credit value for the course (int or float).

    Returns
    -------
    float
        The SGPA rounded to two decimal places.
        If ``courses`` is empty the function returns 0.0.

    Example
    -------
    >>> sgpa([("AA", 4), ("bc", 3), ("FF", 2)])
    7.33
    """
    # Mapping from grade (upper‑case) to grade‑point value
    GRADE_POINTS = {
        "AA": 10,
        "AB": 9,
        "BB": 8,
        "BC": 7,
        "CC": 6,
        "CD": 5,
        "DD": 4,
        "FF": 0,
    }

    # No courses → SGPA is defined as 0.0
    if not courses:
        return 0.0

    total_weighted_points = 0.0   # Σ (credits × grade‑points)
    total_credits = 0.0          # Σ credits (including failed courses)

    for grade, credits in courses:
        # Normalise grade string to upper case to accept lower‑case input
        grade = grade.upper()

        # Defensive programming: raise a clear error if an unknown grade appears
        if grade not in GRADE_POINTS:
            raise ValueError(f"Invalid grade '{grade}'. Expected one of {list(GRADE_POINTS)}")

        # Convert credits to float in case the caller passes an int or a decimal string
        try:
            credits = float(credits)
        except (TypeError, ValueError) as exc:
            raise TypeError(f"Credits must be numeric, got {credits!r}") from exc

        # Accumulate
        total_weighted_points += credits * GRADE_POINTS[grade]
        total_credits += credits

    # Guard against division by zero (should not happen because we checked for empty list,
    # but a caller could pass courses with 0 credits only)
    if total_credits == 0:
        return 0.0

    sgpa_value = total_weighted_points / total_credits
    # Round to two decimal places as required
    return round(sgpa_value, 2)
'''

### How it works
1. **Grade‑point lookup** – A dictionary maps each allowed grade (upper‑case) to its numeric point value.
2. **Normalization** – The input grade string is converted to upper case so `"aa"` or `"Aa"` are accepted.
3. **Validation** – If a grade isn’t in the dictionary, a `ValueError` is raised, making debugging easier.
4. **Credit handling** – Credits are cast to `float` to support both integer and fractional credit values.
5. **Computation** – The weighted sum of points and the total credits (including failed courses) are accumulated.
6. **Edge cases** –  
   * Empty list → `0.0`.  
   * All courses have zero credits → also `0.0` (avoids division‑by‑zero).  
7. **Rounding** – The final SGPA is rounded to two decimal places with Python’s built‑in `round`.

You can now drop this function into any Python module or script and call it with a list of `(grade, credits)` pairs.
```

**optimized** ✅:

```text
'''python
def sgpa(courses):
    """courses: list of (grade, credits) tuples, e.g. [("AA", 4), ("BC", 3)]"""
    points = {"aa":10,"ab":9,"bb":8,"bc":7,"cc":6,"cd":5,"dd":4,"ff":0}
    total_credits = sum(c for _,c in courses)
    if total_credits == 0: return 0.0
    weighted = sum(points.get(g.lower(),0)*c for g,c in courses)
    return round(weighted/total_credits, 2)
'''
```

</details>

<details><summary><b>cod-02</b> Fix an attendance-percentage function (integer division, division by zero): vague ✅, optimized ✅</summary>

Vague prompt: `fix this its giving 0 always`  
Gold: `attendance_pct` passes 6 hidden asserts

**vague** ✅:

```text
Here’s a clean, robust implementation that does exactly what you described:

'''python
def attendance_pct(attended: int, total: int) -> float:
    """
    Return the attendance percentage rounded to one decimal place.

    * If `total` is 0 (no lectures have been conducted yet) the function returns 0.0.
    * The result is always a float with one decimal digit (e.g. 75.0, 92.3).

    Parameters
    ----------
    attended : int
        Number of lectures the student attended.
    total : int
        Total number of lectures that have been held.

    Returns
    -------
    float
        Attendance percentage rounded to one decimal place.
    """
    # Guard against division‑by‑zero
    if total == 0:
        return 0.0

    # Compute the raw percentage as a float
    raw_pct = (attended / total) * 100

    # Round to one decimal place and return
    return round(raw_pct, 1)
'''

### What was wrong with the original code?

'''python
def attendance_pct(attended, total):
    return attended // total * 100
'''

1. **Integer division (`//`)** – This discards the fractional part, so anything less than a full‑attendance ratio becomes `0`.  
2. **No handling of `total == 0`** – Dividing by zero raises a `ZeroDivisionError`.  
3. **No rounding** – The function returns an integer, not a float with one decimal place.

### How the new version fixes it

| Issue | Fix |
|-------|-----|
| Integer division | Use true division (`/`) to keep the fractional part. |
| Division by zero | Return `0.0` immediately when `total` is `0`. |
| Rounding to 1 decimal | Apply `round(..., 1)` before returning. |
| Return type | Explicitly return a `float` (the result of `round` is already a float). |

### Quick sanity check

'''python
assert attendance_pct(0, 0)   == 0.0   # no lectures yet
assert attendance_pct(0, 10)  == 0.0   # 0% attendance
assert attendance_pct(5, 10)  == 50.0  # 50%
assert attendance_pct(7, 9)   == 77.8  # 77.777… → 77.8
assert attendance_pct(9, 9)   == 100.0 # full attendance
'''

All tests pass, and the function now behaves exactly as required.
```

**optimized** ✅:

```text
'''python
def attendance_pct(attended, total):
    """
    Calculate the attendance percentage.

    Parameters:
    attended (int or float): Number of lectures attended.
    total (int or float): Total number of lectures conducted.

    Returns:
    float: Attendance percentage rounded to one decimal place.
           Returns 0.0 when total is zero (no lectures conducted).
    """
    if total == 0:
        return 0.0
    return round((attended / total) * 100, 1)
'''
```

</details>

<details><summary><b>cod-03</b> Library fine with two slabs, a cap and double fines for reference books: vague ✅, optimized ✅</summary>

Vague prompt: `need python fn for library fine as per these rules`  
Gold: `library_fine` passes 8 hidden asserts

**vague** ✅:

```text
Here is a compact, well‑documented implementation that follows exactly the rules you described.

'''python
from datetime import date

def library_fine(due: date, returned: date, reference: bool = False) -> int:
    """
    Calculate the library fine for a single book.

    Parameters
    ----------
    due : datetime.date
        The date the book was supposed to be returned.
    returned : datetime.date
        The actual return date.
    reference : bool, optional
        ``True`` if the book is a reference book, ``False`` otherwise.
        Reference books have their fine *doubled* (the 100‑rupee cap is applied
        after the doubling).  The default is ``False``.

    Returns
    -------
    int
        The fine in rupees.  Zero if the book is returned on or before the due
        date.

    Rules (as given in the problem statement)
    -----------------------------------------
    * No fine if ``returned`` ≤ ``due``.
    * For the first 7 days of delay the charge is Rs 2 per day.
    * From day 8 onward the charge is Rs 5 per day.
    * The total fine for a normal book is capped at Rs 100.
    * For a reference book the computed fine is doubled, then the same Rs 100
      cap is applied (i.e. the maximum a patron can ever pay is Rs 100).

    Examples
    --------
    >>> from datetime import date
    >>> library_fine(date(2023, 5, 1), date(2023, 5, 5))
    0                         # returned early
    >>> library_fine(date(2023, 5, 1), date(2023, 5, 10))
    18                        # 9 days late → 7*2 + 2*5 = 24, capped at 100 → 24
    >>> library_fine(date(2023, 5, 1), date(2023, 6, 20))
    100                       # huge delay, capped
    >>> library_fine(date(2023, 5, 1), date(2023, 5, 10), reference=True)
    36                        # double of 18, still below cap
    >>> library_fine(date(2023, 5, 1), date(2023, 6, 20), reference=True)
    100                       # double would be 200, but cap brings it back to 100
    """
    # ------------------------------------------------------------------
    # 1. No fine if the book is returned on time or early.
    # ------------------------------------------------------------------
    if returned <= due:
        return 0

    # ------------------------------------------------------------------
    # 2. Compute the number of days late.
    # ------------------------------------------------------------------
    days_late = (returned - due).days

    # ------------------------------------------------------------------
    # 3. Apply the piece‑wise daily rate.
    #    * first 7 days → Rs 2 / day
    #    * thereafter   → Rs 5 / day
    # ------------------------------------------------------------------
    first_week = min(days_late, 7)          # days that fall in the first week
    after_week = max(days_late - 7, 0)      # days beyond the first week

    fine = first_week * 2 + after_week * 5

    # ------------------------------------------------------------------
    # 4. Double the fine for reference books.
    # ------------------------------------------------------------------
    if reference:
        fine *= 2

    # ------------------------------------------------------------------
    # 5. Enforce the maximum cap of Rs 100.
    # ------------------------------------------------------------------
    return min(fine, 100)
'''

### How it works
1. **Early/On‑time return** – the function returns `0` immediately.
2. **Days late** – calculated with simple subtraction of two `date` objects.
3. **Piece‑wise rate** – the first 7 days are charged at `2` rupees per day, any
   remaining days at `5` rupees per day.
4. **Reference books** – the whole amount is multiplied by `2`.
5. **Cap** – `min(fine, 100)` guarantees the final fine never exceeds Rs 100,
   even after the doubling for reference books.

The function is pure (no side‑effects), type‑annotated, and includes a
docstring with usage examples, making it ready to drop into any library‑management
codebase.
```

**optimized** ✅:

```text
'''python
from datetime import date

def library_fine(due: date, returned: date, reference: bool = False) -> int:
    """
    Calculate the library fine.

    Parameters
    ----------
    due : datetime.date
        The due date of the book.
    returned : datetime.date
        The date the book was actually returned.
    reference : bool, optional
        True if the book is a reference book (fine is doubled). Default is False.

    Returns
    -------
    int
        The fine amount in rupees.
    """
    # No fine if returned on or before the due date
    if returned <= due:
        return 0

    # Number of days late
    days_late = (returned - due).days

    # First 7 days: Rs 2 per day
    first_week_days = min(days_late, 7)
    fine = first_week_days * 2

    # Remaining days (if any): Rs 5 per day
    if days_late > 7:
        fine += (days_late - 7) * 5

    # Double fine for reference books
    if reference:
        fine *= 2

    # Apply the Rs 100 cap
    return min(fine, 100)
'''
```

</details>

<details><summary><b>cod-04</b> Timetable clash detection (back-to-back slots are not clashes): vague ✅, optimized ✅</summary>

Vague prompt: `write code to find clashes in timetable slots`  
Gold: `find_clashes` passes 7 hidden asserts

**vague** ✅:

```text
Here is a compact, well‑documented implementation that follows the specification exactly.  
It works for any iterable of slots where each slot is a 3‑tuple  

'''python
(day, start_time, end_time)          # e.g. ("Mon", "10:00", "11:00")
'''

The function returns a **sorted** list of index pairs `(i, j)` (`i < j`) for every pair of slots that clash (same day **and** overlapping time).  
A slot that ends at the exact moment another one starts is **not** considered a clash.

'''python
from typing import List, Tuple, Iterable

Slot = Tuple[str, str, str]          # (day, start, end)
IndexPair = Tuple[int, int]          # (i, j) with i < j


def _to_minutes(t: str) -> int:
    """
    Convert a HH:MM string to minutes since midnight.
    Assumes a valid, zero‑padded 24‑hour time.
    """
    hour, minute = map(int, t.split(":"))
    return hour * 60 + minute


def _overlap(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    """
    Return True if the half‑open intervals [a_start, a_end) and
    [b_start, b_end) intersect.
    The end point is exclusive, which implements the “ends exactly when the other starts → no clash”
    rule.
    """
    return a_start < b_end and b_start < a_end


def find_clashes(slots: Iterable[Slot]) -> List[IndexPair]:
    """
    Return a sorted list of (i, j) index pairs, i < j, of slots that clash.

    Parameters
    ----------
    slots : iterable of (day, start, end)
        * day   – any hashable identifier (e.g. "Mon", "Tue", …)
        * start – string "HH:MM"
        * end   – string "HH:MM"

    Returns
    -------
    List[Tuple[int, int]]
        Sorted list of index pairs (i, j) where slots[i] and slots[j] clash.
    """
    # Convert the input to a list so we can index it multiple times
    slots = list(slots)

    # Pre‑process each slot: keep the day and the numeric start/end minutes.
    # This makes the inner loop cheap.
    processed = [
        (day, _to_minutes(start), _to_minutes(end))
        for day, start, end in slots
    ]

    clashes: List[IndexPair] = []

    n = len(processed)
    for i in range(n):
        day_i, start_i, end_i = processed[i]
        for j in range(i + 1, n):
            day_j, start_j, end_j = processed[j]

            # Different days can never clash
            if day_i != day_j:
                continue

            # Check time overlap using half‑open intervals
            if _overlap(start_i, end_i, start_j, end_j):
                clashes.append((i, j))

    # The loops already generate pairs in increasing order, but we sort
    # explicitly to guarantee the contract even if the input iterable is
    # not a list (e.g. a generator that yields out‑of‑order).
    clashes.sort()
    return clashes
'''

### How it works
1. **Normalization** – each `"HH:MM"` string is turned into an integer number of minutes since midnight (`_to_minutes`).  
2. **Half‑open intervals** – we treat a slot as `[start, end)`. This automatically makes a slot that ends exactly when another starts *non‑overlapping* (`_overlap`).  
3. **Pairwise comparison** – we only compare slots that share the same day, then test the numeric intervals for overlap.  
4. **Result ordering** – pairs are collected with `i < j` and finally sorted, guaranteeing a deterministic output.

### Example usage

'''python
if __name__ == "__main__":
    timetable = [
        ("Mon", "09:00", "10:30"),
        ("Mon", "10:30", "11:30"),   # touches previous slot → no clash
        ("Mon", "10:00", "11:00"),   # overlaps both first and second
        ("Tue", "09:00", "10:00"),
        ("Tue", "09:30", "10:30"),
    ]

    print(find_clashes(timetable))
    # Output: [(0, 2), (1, 2), (3, 4)]
'''

The function runs in **O(n²)** time, which is optimal for the naïve pairwise‑check approach.  
If you need to handle thousands of slots more efficiently, you could first group by day and then sweep‑line each day's intervals – but for typical class‑schedule sizes the above solution is simple, clear, and fast enough.
```

**optimized** ✅:

```text
'''python
def _to_minutes(t: str) -> int:
    """Convert a HH:MM string to minutes since midnight."""
    h, m = map(int, t.split(":"))
    return h * 60 + m


def find_clashes(slots):
    """
    Return a sorted list of (i, j) index pairs, i < j, of slots that clash.

    Each slot is a tuple (day, start, end) where start and end are "HH:MM".
    A clash occurs when two slots are on the same day and their time intervals
    overlap (end == start is NOT a clash).
    """
    # Pre‑process slots: convert times to minutes for easy comparison
    processed = [
        (day, _to_minutes(start), _to_minutes(end))
        for day, start, end in slots
    ]

    clashes = []
    n = len(processed)
    for i in range(n):
        day_i, s_i, e_i = processed[i]
        for j in range(i + 1, n):
            day_j, s_j, e_j = processed[j]
            if day_i != day_j:
                continue
            # Overlap exists if the later start is before the earlier end
            if max(s_i, s_j) < min(e_i, e_j):
                clashes.append((i, j))

    # The loops already generate pairs in increasing order, but sort to guarantee
    return sorted(clashes)
'''
```

</details>

<details><summary><b>cod-05</b> Indian digit grouping for rupee amounts (lakh/crore commas): vague ❌, optimized ✅</summary>

Vague prompt: `fn to print amt in indian format with commas`  
Gold: `format_inr` passes 8 hidden asserts

**vague** ❌ (no_function: `format_inr` not defined; top-level functions: []):

```text
**Solution Overview**

The Indian numbering system groups the right‑most three digits together and then groups the remaining digits in pairs of two:

'''
   1 234 567 890  →  1,23,45,67,890
   45 00 000      →  45,00,000
   4 550 000      →  45,50,000
'''

The task is to write a small, pure‑Rust helper:

'''rust
fn format_inr(amount: i64) -> String
'''

* `amount` is a signed integer that represents a whole number of rupees.  
* The function must return a string with the correctly placed commas.  
* A negative value keeps the leading `-` sign (e.g. `-12345 → "-12,345"`).

The implementation works in **O(n)** time where *n* is the number of decimal digits and uses **O(n)** auxiliary memory for the output string.

---

## Algorithm

1. **Separate sign** – remember whether the number is negative and work with its absolute value (`u64`).  
2. **Convert to decimal string** – `abs_val.to_string()` gives us the digits in the natural order (most‑significant first).  
3. **Iterate from the right** – walk the digit slice backwards, inserting commas:
   * The first group (the right‑most three digits) is always size 3.  
   * After that, every subsequent group has size 2.  
   * While walking, push the current digit onto a temporary `Vec<char>` (which builds the result **reversed**).  
   * When the current group is finished, push a comma (unless we are at the very leftmost digit).
4. **Reverse** the temporary buffer to obtain the final order.  
5. **Add sign** – prepend `'-'` if the original number was negative.  

Because we only need to look at each digit once, the algorithm is linear and does not allocate any intermediate strings besides the final result.

---

## Correctness Proof  

We prove that `format_inr` returns exactly the Indian‑grouped representation of the input integer.

### Lemma 1  
During the backward scan the algorithm inserts a comma **iff** the next digit to the left belongs to a new group according to the Indian grouping rule.

*Proof.*  
The algorithm keeps a counter `group_len` that starts at `0`.  
* For the first three digits (`group_len < 3`) the counter is incremented and no comma is inserted.  
* After three digits have been processed, `group_len` is reset to `0` and the next group size is set to `2`.  
* For every subsequent digit, `group_len` is incremented; when it reaches `2` the algorithm inserts a comma, resets `group_len` to `0`, and continues.  

Thus commas are placed exactly after the 3‑rd digit from the right, then after every 2‑digit block, which matches the Indian rule. ∎



### Lemma 2  
The sequence of digits produced (ignoring commas) is identical to the decimal representation of `|amount|`.

*Proof.*  
The algorithm iterates over the digit slice obtained from `abs_val.to_string()`, which is precisely the decimal digits of `|amount|` in left‑to‑right order. The backward walk visits each digit exactly once and copies it unchanged into the output buffer. No digit is added, removed, or reordered. ∎



### Lemma 3  
If `amount < 0` the output string begins with a single `'-'`; otherwise it contains no sign character.

*Proof.*  
The sign is examined before any processing. If `amount < 0` the function stores `sign = true` and works with `abs_val = (-amount) as u64`. After the digit/comma buffer is built and reversed, the function prepends `'-'` only when `sign` is true. No other code adds a sign. ∎



### Theorem  
For any integer `amount` the function `format_inr(amount)` returns the exact Indian‑comma formatted representation of `amount`.

*Proof.*  
Consider two cases.

*Case 1 – `amount ≥ 0`.*  
By Lemma 2 the digits in the result are exactly those of `amount`. By Lemma 1 commas are inserted precisely at the positions required by the Indian grouping rule. No sign is added (Lemma 3). Hence the output matches the specification.

*Case 2 – `amount < 0`.*  
The absolute value part follows the same reasoning as Case 1, giving a correctly grouped representation of `|amount|`. Lemma 3 guarantees a leading `'-'`. Therefore the whole string is the required representation of the negative amount.

Both cases cover all possible inputs, completing the proof. ∎



---

## Complexity Analysis  

*Let* `d = number of decimal digits of |amount|` ( `d = ⌊log10|amount|⌋ + 1` for non‑zero, `d = 1` for zero).

* **Time:** The algorithm scans the digit slice once → **O(d)**.  
* **Space:** It stores the output characters (digits + commas) → at most `d + d/2` characters → **O(d)** auxiliary space (the final `String` itself).

Both bounds are optimal because any correct formatter must at least look at each digit.

---

## Reference Implementation (Rust 1.56+)

'''rust
/// Formats a signed integer as an Indian‑rupee amount with commas.
///
/// # Examples
///
/// '''
/// assert_eq!(format_inr(4550000), "45,50,000");
/// assert_eq!(format_inr(-12345678), "-1,23,45,678");
/// assert_eq!(format_inr(0), "0");
/// '''
pub fn format_inr(amount: i64) -> String {
    // 1. Remember the sign and work with the absolute value.
    let negative = amount < 0;
    // `i64::MIN` cannot be negated directly, so we cast to u64 first.
    let abs_val: u64 = if negative {
        // Two's complement trick: -(i64::MIN) overflows, but as u64 it is fine.
        amount.wrapping_abs() as u64
    } else {
        amount as u64
    };

    // 2. Decimal representation of the absolute value.
    let digits: Vec<char> = abs_val.to_string().chars().collect();

    // 3. Build the result backwards.
    let mut out_rev: Vec<char> = Vec::with_capacity(digits.len() + digits.len() / 2);
    let mut i = digits.len(); // index of the next digit to process (exclusive)
    let mut group_len = 0;    // how many digits we have placed in the current group
    let mut first_group = true; // the right‑most group is size 3, others size 2

    while i > 0 {
        // Take the next digit from the right.
        i -= 1;
        out_rev.push(digits[i]);
        group_len += 1;

        // Determine when a comma is needed.
        let needed_len = if first_group { 3 } else { 2 };
        if group_len == needed_len && i != 0 {
            out_rev.push(',');          // insert comma after the group
            group_len = 0;              // start a new group
            first_group = false;        // after the first group we always use size 2
        }
    }

    // 4. Reverse to obtain the correct order.
    out_rev.reverse();
    let mut result: String = out_rev.iter().collect();

    // 5. Prepend minus sign if needed.
    if negative {
        result.insert(0, '-');
    }
    result
}

// ---------------------------------------------------------------------------
// Unit tests (run with `cargo test`)

#[cfg(test)]
mod tests {
    use super::format_inr;

    #[test]
    fn basic_examples() {
        assert_eq!(format_inr(0), "0");
        assert_eq!(format_inr(5), "5");
        assert_eq!(format_inr(123), "123");
        assert_eq!(format_inr(1234), "1,234");
        assert_eq!(format_inr(12345), "12,345");
        assert_eq!(format_inr(123456), "1,23,456");
        assert_eq!(format_inr(1234567), "12,34,567");
        assert_eq!(format_inr(12345678), "1,23,45,678");
        assert_eq!(format_inr(4550000), "45,50,000");
    }

    #[test]
    fn negatives() {
        assert_eq!(format_inr(-1), "-1");
        assert_eq!(format_inr(-12345), "-12,345");
        assert_eq!(format_inr(-12345678), "-1,23,45,678");
    }

    #[test]
    fn edge_cases() {
        // i64::MIN = -9_223_372_036_854_775_808
        // Its absolute value cannot be represented as i64, but we handle it via u64.
        let min = i64::MIN;
        let formatted = format_inr(min);
        // Verify that the formatted string, when we strip commas and sign,
        // equals the decimal representation of i64::MIN.
        let stripped
```

**optimized** ✅:

```text
'''python
def format_inr(amount: int) -> str:
    """
    Format an integer amount of rupees in the Indian numbering system.

    Example:
        >>> format_inr(4550000)
        '45,50,000'
        >>> format_inr(-12345678)
        '-1,23,45,678'

    Parameters
    ----------
    amount : int
        The amount in rupees (can be negative).

    Returns
    -------
    str
        The amount formatted with commas according to Indian conventions.
    """
    # Preserve sign and work with absolute value
    sign = '-' if amount < 0 else ''
    n = abs(amount)

    # Convert to string for easier manipulation
    s = str(n)

    # If the number has 3 or fewer digits, no commas are needed
    if len(s) <= 3:
        return f"{sign}{s}"

    # Split the string into the last three digits and the remaining prefix
    last_three = s[-3:]
    prefix = s[:-3]

    # Process the prefix in groups of two digits from right to left
    groups = []
    while len(prefix) > 2:
        groups.append(prefix[-2:])   # take last two digits
        prefix = prefix[:-2]        # remove them
    # Whatever is left (1 or 2 digits) is the most‑significant group
    groups.append(prefix)

    # The groups were collected from right to left, so reverse them
    groups.reverse()

    # Join all parts with commas
    formatted = ','.join(groups + [last_three])

    return f"{sign}{formatted}"
'''
```

</details>

<details><summary><b>cod-06</b> PRN (registration number) format validation: vague ✅, optimized ✅</summary>

Vague prompt: `make validation fn for prn as per format below`  
Gold: `is_valid_prn` passes 8 hidden asserts

**vague** ✅:

```text
Here is a compact, well‑documented implementation that follows the specification exactly:

'''python
import re

# ----------------------------------------------------------------------
# Regular‑expression that describes a valid PRN
# ----------------------------------------------------------------------
#  ^\s*                     – optional leading whitespace (will be ignored)
#  (201[8-9]|202[0-6])      – admission year 2018‑2026 (4 digits)
#  (BT|MT)                  – programme code
#  (CS|IT|EN|ME|CV|EL)      – branch code
#  (?!0{5})\d{5}            – 5‑digit serial that is NOT 00000
#  \s*$                     – optional trailing whitespace (will be ignored)
# ----------------------------------------------------------------------
_PRN_PATTERN = re.compile(
    r"""^\s*
        (201[8-9]|202[0-6])      # year 2018‑2026
        (BT|MT)                  # programme
        (CS|IT|EN|ME|CV|EL)      # branch
        (?!0{5})\d{5}            # serial, not all zeros
        \s*$""",
    re.VERBOSE,
)

def is_valid_prn(prn: str) -> bool:
    """
    Validate a Programme Registration Number (PRN).

    The PRN must satisfy **all** of the following rules:

    1. May contain leading or trailing whitespace – these are ignored.
    2. Starts with a 4‑digit admission year between 2018 and 2026 inclusive.
    3. Followed by the programme code ``BT`` or ``MT``.
    4. Followed by a branch code chosen from
       ``CS, IT, EN, ME, CV, EL``.
    5. Ends with a 5‑digit serial number that is **not** ``00000``.
    6. All alphabetic characters are upper‑case.

    Parameters
    ----------
    prn: str
        The PRN string to validate. It may contain surrounding spaces.

    Returns
    -------
    bool
        ``True`` if the string conforms to the format, ``False`` otherwise.
    """
    # The compiled regex already strips leading/trailing spaces via ^\s* … \s*$
    # and checks every rule in one pass.
    return bool(_PRN_PATTERN.match(prn))


# ----------------------------------------------------------------------
# Simple sanity‑check (can be removed or placed under a `if __name__ == "__main__":` guard)
# ----------------------------------------------------------------------
if __name__ == "__main__":
    test_cases = {
        "2022BTCS00041": True,
        " 2022BTCS00041 ": True,   # leading/trailing spaces are ignored
        "2018MTEL12345": True,
        "2026BTME54321": True,
        "2027BTCS00001": False,    # year out of range
        "2020ATCS00001": False,    # invalid programme
        "2020BTXX00001": False,    # invalid branch
        "2020BTCS00000": False,    # serial cannot be all zeros
        "2020btcs00041": False,    # lower‑case letters not allowed
        "2020BTCS041":   False,    # serial not 5 digits
    }

    for prn, expected in test_cases.items():
        result = is_valid_prn(prn)
        print(f"{prn!r:20} → {result} (expected {expected})")
'''

### How it works
* **Whitespace handling** – `^\s*` and `\s*$` allow any amount of leading/trailing spaces, which are effectively ignored.
* **Year check** – `(201[8-9]|202[0-6])` matches exactly the years 2018‑2026.
* **Programme & branch** – simple alternations enforce the allowed upper‑case codes.
* **Serial number** – `(?!0{5})\d{5}` first asserts that the next five digits are **not** all zeros (negative look‑ahead) and then consumes exactly five digits.
* The compiled regex is reused for every call, making the function fast even when invoked many times.

Feel free to drop the function into any module; the test harness at the bottom demonstrates typical usage.
```

**optimized** ✅:

```text
'''python
import re

# Pre‑compiled pattern for performance and readability
_PRN_PATTERN = re.compile(
    r"""
    ^                                   # start of string
    (?:201[8-9]|202[0-6])               # admission year 2018‑2026
    (?:BT|MT)                           # programme code
    (?:CS|IT|EN|ME|CV|EL)               # branch code
    (?!00000)                           # serial must not be 00000
    \d{5}                               # 5‑digit serial
    $                                   # end of string
    """,
    re.VERBOSE,
)

def is_valid_prn(prn: str) -> bool:
    """
    Validate a PRN according to the specification:
    - 4‑digit year between 2018 and 2026 inclusive
    - Programme code: "BT" or "MT"
    - Branch code: one of CS, IT, EN, ME, CV, EL
    - 5‑digit serial that is not "00000"
    - Upper‑case letters only
    - Leading/trailing whitespace is ignored
    """
    # Strip any surrounding whitespace before validation
    prn = prn.strip()
    return bool(_PRN_PATTERN.match(prn))
'''
```

</details>

<details><summary><b>cod-07</b> Fix a class-average function that crashes on 'AB' (absent): vague ✅, optimized ✅</summary>

Vague prompt: `this crashes when someone is absnt, fix`  
Gold: `class_average` passes 7 hidden asserts

**vague** ✅:

```text
Here’s a robust implementation that:

* **Ignores** the `"AB"` entries (absent students) instead of treating them as 0.  
* Returns **`None`** when the list is empty **or** when every entry is `"AB"`.  
* Rounds the result to **two decimal places** (as a `float`).  
* Includes a small test harness so you can see it work.

'''python
def class_average(marks):
    """
    Compute the average of a class’s marks, ignoring absent students.

    Parameters
    ----------
    marks : list
        A list containing either integers (0‑100) or the string "AB"
        for an absent student.

    Returns
    -------
    float or None
        The average of the present students rounded to 2 decimal places,
        or None if the list is empty or all students are absent.
    """
    # Filter out the absent entries
    present_marks = [m for m in marks if m != "AB"]

    # If nobody is present, return None
    if not present_marks:
        return None

    # Compute the average and round to 2 decimal places
    avg = sum(present_marks) / len(present_marks)
    return round(avg, 2)


# ----------------------------------------------------------------------
# Simple sanity‑check tests (you can delete or expand them as needed)
# ----------------------------------------------------------------------
if __name__ == "__main__":
    test_cases = [
        ([80, 90, 70], 80.0),                     # no absences
        ([80, "AB", 70, 90], 80.0),               # one absent
        (["AB", "AB"], None),                    # all absent
        ([], None),                              # empty list
        ([100, 95, "AB", 85, 90], 92.5),          # mixed
    ]

    for i, (inp, expected) in enumerate(test_cases, 1):
        result = class_average(inp)
        assert result == expected, f"Test {i} failed: got {result}, expected {expected}"
        print(f"Test {i} passed → {result}")
'''

### What changed compared to the original version?

'''python
def class_average(marks):
    return sum(marks) / len(marks)
'''

* The original code tried to sum the whole list, which raises a `TypeError` when `"AB"` is present because you can’t add a string to an integer.
* It also counted absent students as `0`, which is not what the specification requires.
* No handling for the “all absent” or “empty list” edge‑cases.

The new version filters out `"AB"` entries first, checks for the empty‑result case, then safely computes and rounds the average.
```

**optimized** ✅:

```text
'''python
def class_average(marks):
    """
    Calculate the average of a list of marks, ignoring absent students.

    Parameters
    ----------
    marks : list
        A list containing integers (0‑100) or the string "AB" for an absent student.

    Returns
    -------
    float or None
        The average of the present students rounded to two decimal places,
        or None if the list is empty or all students are absent.
    """
    # Filter out absent entries
    present_marks = [m for m in marks if m != "AB"]

    # If there are no present marks, return None
    if not present_marks:
        return None

    # Compute the average and round to 2 decimal places
    avg = sum(present_marks) / len(present_marks)
    return round(avg, 2)
'''
```

</details>

<details><summary><b>cod-08</b> Trip expense splitter: balances per member: vague ✅, optimized ✅</summary>

Vague prompt: `code for splitting trip expenses`  
Gold: `balances` passes 7 hidden asserts

**vague** ✅:

```text
**Solution Overview**

We need a function `balances(expenses, members)` that:

1. Validates that every payer appearing in `expenses` is also present in `members`.  
   If not, raise `ValueError` with a helpful message.
2. Computes the *fair share* for each member:  
   `total_spent / len(members)`.
3. Calculates each member’s net balance = *amount they actually paid* – *fair share*.  
   The result must be a dictionary mapping every member (including those who never paid) to a
   balance rounded to **two decimal places**. Positive balances mean the member is owed money,
   negative balances mean they owe money.

The implementation is straightforward:

* Use a `defaultdict(float)` to accumulate how much each member paid.
* After the validation step, sum all amounts, compute the per‑person share, and then build the
  final dictionary, rounding each value with `round(..., 2)`.

Below is clean, well‑documented Python code that follows the specification and includes a few
unit‑tests to illustrate the expected behaviour.

'''python
from collections import defaultdict
from typing import List, Tuple, Dict, Iterable


def balances(
    expenses: Iterable[Tuple[str, float]],
    members: Iterable[str],
) -> Dict[str, float]:
    """
    Compute how much each member of a trip should receive or pay back.

    Parameters
    ----------
    expenses : iterable of (payer, amount)
        Each tuple records who paid and how much they paid.
    members : iterable of str
        All people who participated in the trip.  The list may contain names that never
        appear as a payer.

    Returns
    -------
    dict
        Mapping ``member -> balance`` where ``balance = amount_paid - fair_share``.
        The balance is rounded to two decimal places.  Positive means the member is
        owed money, negative means they owe money.

    Raises
    ------
    ValueError
        If any payer in ``expenses`` is not present in ``members``.
    """
    # Convert members to a set for O(1) membership tests and to keep a stable order later.
    member_set = set(members)

    # 1️⃣ Validate payers
    for payer, _ in expenses:
        if payer not in member_set:
            raise ValueError(f"Payer '{payer}' is not listed among the trip members.")

    # 2️⃣ Accumulate how much each member actually paid
    paid = defaultdict(float)          # member -> total amount they paid
    total_spent = 0.0

    for payer, amount in expenses:
        # Guard against negative or non‑numeric amounts (optional, but nice)
        if not isinstance(amount, (int, float)):
            raise TypeError(f"Amount for payer '{payer}' must be a number, got {type(amount)}.")
        if amount < 0:
            raise ValueError(f"Amount for payer '{payer}' cannot be negative ({amount}).")
        paid[payer] += amount
        total_spent += amount

    # 3️⃣ Compute the fair share (split equally among *all* members)
    n_members = len(member_set)
    if n_members == 0:
        raise ValueError("The members list cannot be empty.")
    fair_share = total_spent / n_members

    # 4️⃣ Build the result dictionary, ensuring every member appears
    result: Dict[str, float] = {}
    for member in member_set:
        net = paid.get(member, 0.0) - fair_share
        # Round to 2 decimal places as required
        result[member] = round(net, 2)

    return result


# ----------------------------------------------------------------------
# Example usage & simple tests
# ----------------------------------------------------------------------
if __name__ == "__main__":
    # Example 1 – the classic case
    expenses1 = [
        ("Alice", 120.0),
        ("Bob",  60.0),
        ("Alice", 30.0),
    ]
    members1 = ["Alice", "Bob", "Charlie"]
    # Total = 210, fair share = 70 each
    # Alice paid 150 → +80, Bob paid 60 → -10, Charlie paid 0 → -70
    print(balances(expenses1, members1))
    # Expected: {'Alice': 80.0, 'Bob': -10.0, 'Charlie': -70.0}

    # Example 2 – payer not in members → raises ValueError
    try:
        balances([("Dave", 50)], ["Alice", "Bob"])
    except ValueError as e:
        print("Caught expected error:", e)

    # Example 3 – members with no expenses at all
    print(balances([], ["A", "B", "C"]))   # all balances are -0.0 (i.e. 0.0)

    # Example 4 – rounding check
    expenses4 = [("A", 10), ("B", 20)]
    members4 = ["A", "B", "C"]
    # total = 30, share = 10.0 → A: 0, B: +10, C: -10
    print(balances(expenses4, members4))
    # Expected: {'A': 0.0, 'B': 10.0, 'C': -10.0}
'''

### How the code satisfies the requirements

| Requirement | How it’s met |
|-------------|--------------|
| **Validate payers** | Loop over `expenses` and raise `ValueError` if a payer isn’t in `members`. |
| **Split equally among *all* members** | `fair_share = total_spent / len(member_set)`. |
| **Return a dict with every member** | The final loop iterates over `member_set`, inserting a key for each member, even if they never paid. |
| **Balance = paid – fair share** | `net = paid.get(member, 0.0) - fair_share`. |
| **Round to 2 decimals** | `round(net, 2)` before storing in the result. |
| **Positive = should get money back** | By definition `paid - fair_share` is positive when the member over‑paid. |
| **Raise `ValueError` for unknown payer** | Implemented in the validation step. |

Feel free to drop the function into any project, import it, and use it directly. The included `if __name__ == "__main__":` block demonstrates typical usage and serves as a quick sanity‑check.
```

**optimized** ✅:

```text
'''python
def balances(expenses, members):
    """
    Calculate each member's balance for a trip expense split.

    Parameters
    ----------
    expenses : list of tuple
        Each tuple is (payer, amount) where `payer` is a string and `amount` is a number.
    members : iterable
        All members who participated in the trip.

    Returns
    -------
    dict
        Mapping of member -> balance (rounded to 2 decimals). Positive balance means the member
        should receive money back, negative means they owe money.

    Raises
    ------
    ValueError
        If any payer in `expenses` is not present in `members`.
    """
    # Ensure members is a set for fast lookup and to preserve unique entries
    members_set = set(members)

    # Validate payers
    for payer, _ in expenses:
        if payer not in members_set:
            raise ValueError(f"Payer '{payer}' is not a member of the trip")

    # Total amount spent
    total_spent = sum(amount for _, amount in expenses)

    # Number of members (split among all members)
    n_members = len(members_set)
    if n_members == 0:
        # No members – return empty dict (nothing to split)
        return {}

    # Fair share per member
    fair_share = total_spent / n_members

    # Initialize balances with zero for every member
    balances_dict = {member: 0.0 for member in members_set}

    # Add amounts paid by each payer
    for payer, amount in expenses:
        balances_dict[payer] += amount

    # Subtract the fair share for each member
    for member in balances_dict:
        balances_dict[member] = round(balances_dict[member] - fair_share, 2)

    return balances_dict
'''
```

</details>

<details><summary><b>cod-09</b> Fix a second-highest-marks function (ties, small classes, mutation): vague ❌, optimized ✅</summary>

Vague prompt: `second highest marks code is wrong sometimes fix it`  
Gold: `second_highest` passes 8 hidden asserts

**vague** ❌ (3/8 asserts; first failure: `assert second_highest([92, 92, 85]) == 85` AssertionError):

```text
**What went wrong**

'''python
def second_highest(marks):
    marks.sort()          # mutates the caller’s list
    return marks[-2]      # just picks the penultimate element
'''

* It **modifies** the list that the caller passed in – the problem statement explicitly forbids that.  
* It returns the *penultimate* element, not the *second‑distinct* element.  
  When the highest mark occurs more than once (`[95, 95, 80]`) the function returns `95` again.  
* If the list has fewer than two elements (`[]` or `[73]`) the slice `marks[-2]` raises an `IndexError`.

---

## Fixed implementation

'''python
from typing import List, Optional, Any

def second_highest(marks: List[int]) -> Optional[int]:
    """
    Return the second highest **distinct** mark in *marks*.
    If there is no such mark (empty list, only one distinct value, etc.) return None.
    The input list is never modified.
    """
    # Guard against empty / single‑element input early
    if not marks:
        return None

    # Use a set to keep only distinct values, then sort them.
    # Converting to a set also guarantees we don’t touch the original list.
    distinct = sorted(set(marks))

    # After sorting, the highest distinct mark is at -1, the second highest at -2.
    # If there is only one distinct value, return None.
    if len(distinct) < 2:
        return None

    return distinct[-2]
'''

### Why this works

| Situation                               | `set(marks)` | `sorted(...)` | Result (`distinct[-2]`) |
|----------------------------------------|--------------|---------------|--------------------------|
| `[]`                                    | `set()`      | `[]`          | `len < 2` → `None`       |
| `[73]`                                  | `{73}`       | `[73]`        | `len < 2` → `None`       |
| `[85, 85, 85]`                          | `{85}`       | `[85]`        | `len < 2` → `None`       |
| `[92, 78, 92, 61]`                      | `{92,78,61}` | `[61,78,92]`  | `78`                     |
| `[100, 99, 99, 98]`                     | `{100,99,98}`| `[98,99,100]` | `99`                     |
| `[55, 70, 70, 70, 80]`                  | `{55,70,80}` | `[55,70,80]`  | `70`                     |

* **No mutation** – we never call `list.sort()` or any in‑place method on the original list.
* **Distinctness** – converting to a `set` removes duplicates before we look for the second highest.
* **Safety** – we explicitly check the length of the distinct list and return `None` when a second distinct mark does not exist, avoiding `IndexError`.

---

### One‑liner alternative (if you prefer brevity)

'''python
def second_highest(marks: List[int]) -> Optional[int]:
    d = sorted(set(marks))
    return d[-2] if len(d) > 1 else None
'''

Both versions satisfy the requirements:

* **Do not modify** the caller’s list.
* Return the **second highest distinct** mark.
* Return **`None`** when a second distinct mark cannot be determined.
```

**optimized** ✅:

```text
'''python
def second_highest(marks):
    """
    Return the second highest distinct mark from the given list.
    If there is no such distinct mark (empty list, only one distinct value, etc.),
    return None. The original list is not modified.
    """
    # Use a set to get distinct marks, then sort them.
    distinct = sorted(set(marks))
    # Need at least two distinct values.
    if len(distinct) < 2:
        return None
    # The second highest is the penultimate element.
    return distinct[-2]
'''
```

</details>

<details><summary><b>cod-10</b> Recipe quantity scaler with fractions and mixed numbers: vague ✅, optimized ❌</summary>

Vague prompt: `write the scale fn for recipe app`  
Gold: `scale_quantity` passes 8 hidden asserts

**vague** ✅:

```text
**`scale_quantity` – a pure‑Python helper for the Hostel recipe app**

'''python
from __future__ import annotations
import math
import re
from fractions import Fraction
from typing import Tuple

# ----------------------------------------------------------------------
# Helper functions
# ----------------------------------------------------------------------
def _parse_amount(amount_str: str) -> Fraction:
    """
    Convert a string that may be an integer, decimal, simple fraction or mixed
    number into a ``Fraction`` (exact rational value).

    Supported forms:
        "2"          → 2
        "0.5"        → 1/2
        "1/2"        → 1/2
        "1 1/2"      → 3/2
        "  3  3/4 "  → 15/4   (extra whitespace is ignored)
    """
    amount_str = amount_str.strip()
    # Mixed number: "<whole> <num>/<den>"
    if " " in amount_str:
        whole, frac = amount_str.split(maxsplit=1)
        whole = int(whole)
        frac = Fraction(frac)          # Fraction can parse "1/2"
        return Fraction(whole) + frac

    # Simple fraction or decimal or integer
    if "/" in amount_str:               # "3/4"
        return Fraction(amount_str)
    if "." in amount_str:               # "0.75"
        # Use Fraction.from_float to keep the exact binary representation,
        # then limit denominator to a reasonable size (we only need 1/8 steps).
        return Fraction(float(amount_str)).limit_denominator(1000)
    # plain integer
    return Fraction(int(amount_str))


def _format_fraction(frac: Fraction) -> str:
    """
    Turn a ``Fraction`` that is already reduced to the nearest 1/8 into a
    human‑readable string:

        1/2   → "1/2"
        3/2   → "1 1/2"
        2     → "2"
    The fraction part is always a proper fraction (numerator < denominator)
    and is expressed in lowest terms.
    """
    # Whole part
    whole = frac.numerator // frac.denominator
    remainder = frac - whole

    if remainder == 0:
        return str(whole)                     # pure integer
    if whole == 0:
        # proper fraction only
        return f"{remainder.numerator}/{remainder.denominator}"
    # mixed number
    return f"{whole} {remainder.numerator}/{remainder.denominator}"


def _round_to_nearest_eighth(frac: Fraction) -> Fraction:
    """
    Round a ``Fraction`` to the nearest 1/8 (i.e. denominator 8) and then
    reduce it to lowest terms.  ``Fraction`` automatically reduces, so we
    only need to quantise the value.
    """
    # Multiply by 8, round to nearest integer, then divide back by 8
    eighths = round(frac * 8)
    return Fraction(eighths, 8)   # automatically reduced


# ----------------------------------------------------------------------
# Main public function
# ----------------------------------------------------------------------
def scale_quantity(qty: str, from_servings: int | float, to_servings: int | float) -> str:
    """
    Scale a quantity string from one serving size to another.

    Parameters
    ----------
    qty : str
        The original quantity, e.g. ``"1 1/2 cups thick poha"``.
        The *amount* part (everything up to the first whitespace) may be:
            * integer      – ``"2"``
            * decimal      – ``"0.5"``
            * simple fraction – ``"1/2"``
            * mixed number – ``"1 1/2"``
        The *unit* part is everything after the amount (including any extra
        words) and is returned unchanged.

    from_servings : int | float
        Original number of servings the recipe is written for.

    to_servings : int | float
        Desired number of servings.

    Returns
    -------
    str
        The scaled quantity, rounded to the nearest 1/8, expressed as a
        whole number, a proper fraction or a mixed number in lowest terms,
        followed by a single space and the original unit.

    Example
    -------
    >>> scale_quantity("1 1/2 cups thick poha", 2, 5)
    '3 3/4 cups thick poha'
    """
    # ------------------------------------------------------------------
    # 1️⃣  Split the input into amount and unit
    # ------------------------------------------------------------------
    # The amount is the first token(s) that form a number; the rest is the unit.
    # A simple regex that captures the amount (including a possible space for
    # mixed numbers) and the remainder:
    match = re.match(r'\s*([^\s]+(?:\s+[^\s/]+/[^\s/]+)?)\s+(.*)', qty)
    if not match:
        raise ValueError(f'Unable to parse quantity: "{qty}"')
    amount_str, unit = match.groups()

    # ------------------------------------------------------------------
    # 2️⃣  Convert the amount to a Fraction (exact rational)
    # ------------------------------------------------------------------
    amount = _parse_amount(amount_str)

    # ------------------------------------------------------------------
    # 3️⃣  Apply the scaling factor
    # ------------------------------------------------------------------
    factor = Fraction(to_servings, from_servings)   # exact rational factor
    scaled = amount * factor

    # ------------------------------------------------------------------
    # 4️⃣  Round to the nearest 1/8
    # ------------------------------------------------------------------
    rounded = _round_to_nearest_eighth(scaled)

    # ------------------------------------------------------------------
    # 5️⃣  Format back to a string (whole / proper fraction / mixed)
    # ------------------------------------------------------------------
    formatted_amount = _format_fraction(rounded)

    # ------------------------------------------------------------------
    # 6️⃣  Return the final string
    # ------------------------------------------------------------------
    return f"{formatted_amount} {unit.strip()}"
'''

### How it works, step‑by‑step

| Step | What we do | Why |
|------|------------|-----|
| **Parse** | Split the input into *amount* and *unit* using a regex. | Keeps the unit untouched (it may contain several words). |
| **Convert** | Turn the amount into a `Fraction`. Handles integers, decimals, simple fractions, and mixed numbers. | `Fraction` gives exact arithmetic, avoiding floating‑point drift. |
| **Scale** | Multiply by `to_servings / from_servings` (also a `Fraction`). | Exact scaling, even for non‑integer serving ratios. |
| **Round** | Quantise to the nearest 1/8 (`round(frac * 8) / 8`). | Recipes usually work with 1/8‑cup, 1/8‑tsp, etc. |
| **Reduce & format** | Reduce to lowest terms and output as whole, proper fraction, or mixed number. | Human‑readable, matches the required format. |
| **Combine** | Append the original unit. | The unit stays exactly as the user wrote it. |

### Quick sanity‑check

'''python
tests = [
    ("2 cups flour", 4, 6, "3 cups flour"),
    ("0.5 tsp salt", 2, 5, "1 1/4 tsp salt"),
    ("1/3 cup oil", 1, 2, "2/3 cup oil"),
    ("1 1/2 tbsp sugar", 3, 2, "1 tsp sugar"),
    ("3 3/4 liters broth", 5, 3, "2 1/4 liters broth"),
]

for qty, frm, to, expected in tests:
    result = scale_quantity(qty, frm, to)
    assert result == expected, f"{qty} → {result} (expected {expected})"
print("All demo tests passed!")
'''

Running the snippet prints **“All demo tests passed!”**, confirming that the function behaves as specified.

Feel free to drop `scale_quantity` into any module of the Hostel recipe app – it has no external dependencies beyond the Python standard library. Happy cooking!
```

**optimized** ❌ (4/8 asserts; first failure: `assert scale_quantity("1/2 tsp", 4, 10) == "1 1/4 tsp"` AssertionError):

```text
'''python
from fractions import Fraction
import re
from typing import Tuple

def _parse_quantity(qty: str) -> Tuple[Fraction, str]:
    """
    Split a quantity string into a numeric Fraction and the unit string.

    The numeric part may be:
        - an integer:          "2"
        - a decimal:           "0.5"
        - a simple fraction:   "1/2"
        - a mixed number:      "1 1/2"
    The unit is everything after the numeric part (including leading spaces trimmed).

    Returns:
        (amount_as_fraction, unit_string)
    """
    # Regex to capture the numeric part (including optional mixed number) at the start
    match = re.match(r'\s*([0-9]+(?:\s+[0-9]+/[0-9]+)?|[0-9]+/[0-9]+|[0-9]*\.[0-9]+)\s*(.*)', qty)
    if not match:
        raise ValueError(f"Unable to parse quantity: {qty!r}")

    num_str, unit = match.groups()
    unit = unit.strip()

    # Convert the numeric string to a Fraction
    if ' ' in num_str:                     # mixed number, e.g. "1 1/2"
        whole, frac = num_str.split()
        amount = Fraction(int(whole)) + Fraction(frac)
    elif '/' in num_str:                   # simple fraction, e.g. "3/4"
        amount = Fraction(num_str)
    elif '.' in num_str:                   # decimal, e.g. "0.75"
        amount = Fraction(str(float(num_str)))   # go via float to keep precision
    else:                                  # integer
        amount = Fraction(int(num_str))

    return amount, unit


def _round_to_nearest_eighth(frac: Fraction) -> Fraction:
    """
    Round a Fraction to the nearest 1/8 (i.e. nearest 0.125).
    """
    # Multiply by 8, round to nearest integer, then divide back
    eighths = round(frac * 8)
    return Fraction(eighths, 8)


def _format_fraction(frac: Fraction) -> str:
    """
    Convert a Fraction (already rounded to 1/8) into a string:
        - whole number: "3"
        - proper fraction: "3/4"
        - mixed number: "1 1/2"
    The fraction part is always in lowest terms.
    """
    # Ensure denominator is positive
    if frac.denominator < 0:
        frac = -frac

    whole = frac.numerator // frac.denominator
    remainder = frac - whole

    if remainder == 0:
        return str(whole)
    elif whole == 0:
        # proper fraction
        return f"{remainder.numerator}/{remainder.denominator}"
    else:
        # mixed number
        return f"{whole} {remainder.numerator}/{remainder.denominator}"


def scale_quantity(qty: str, from_servings: int, to_servings: int) -> str:
    """
    Scale a quantity string from one serving size to another.

    Parameters
    ----------
    qty : str
        Quantity string in the form "<amount> <unit>", where <amount> can be an integer,
        decimal, simple fraction, or mixed number.
    from_servings : int
        Original number of servings the quantity corresponds to.
    to_servings : int
        Desired number of servings.

    Returns
    -------
    str
        Scaled quantity, rounded to the nearest 1/8, expressed as a whole number,
        proper fraction, or mixed number (lowest terms), followed by a space and the unit.
        Example: "1 1/4 tsp".
    """
    if from_servings == 0:
        raise ValueError("from_servings must be non‑zero")
    if to_servings < 0:
        raise ValueError("to_servings must be non‑negative")

    amount, unit = _parse_quantity(qty)

    # Scale
    scaled = amount * Fraction(to_servings, from_servings)

    # Round to nearest 1/8
    rounded = _round_to_nearest_eighth(scaled)

    # Format the numeric part
    numeric_str = _format_fraction(rounded)

    # Combine with unit (if unit is empty we just return the number)
    return f"{numeric_str} {unit}" if unit else numeric_str
'''
```

</details>

