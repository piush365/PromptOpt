# 7. Rendering per target LLM, and token counting

[Back to the index](README.md)

The final IR is model-agnostic. `backend/app/rendering.py` turns it into a prompt for each target family — the same
content everywhere, laid out the way each provider's prompting guide recommends — and counts the input tokens of
each rendering.

---

## 7.1 Four sections, three layouts

Every rendering has the same four sections (each only when non-empty):

| section | contents (identical for every target) |
|---|---|
| task | `ir.task` |
| context | **Document** = text pasted next to the prompt; **Input** = data that was inside the prompt (`ir.context`, moved out by B07); **Attachment** = one sentence naming the attached file type ("The user attached a PDF named report.pdf.") |
| constraints | `ir.requirements` first (labels, attachment use), then `ir.constraints` (length, language, grounding), one bullet each |
| output format | `ir.output_format` |

Metadata (category, unresolved, category source, …) is **never** rendered.

| target | layout | basis (provider guidance the code follows) |
|---|---|---|
| **Claude** | XML tags; `<context>` (with `<document>`, `<input>`, `<attachment>` inside) **first**, then `<task>`, `<constraints>`, `<output_format>` | Anthropic's prompt-engineering guide: XML tags separate parts unambiguously, and long material placed at the top of the prompt improves answers |
| **GPT** | markdown sections `### Task`, `### Context`, `### Constraints`, `### Output format`; data in fenced blocks | OpenAI's prompting guide for the GPT-4.1/GPT-5 family: markdown headings and delimiters, so data cannot be read as instructions |
| **Gemini** | plain labels `Task:`, `Constraints:`, `Output format:`, then `Context:` **last** | Google's prompt design strategies: clearly labelled sections, the instruction first and the context after it |

### 7.1.1 Fencing data safely

Data blocks (Input, Document) in the GPT and Gemini renderings are wrapped in a code fence that the data cannot close
early (`fence`):

$$\text{fence length} = \max\big(3,\ L + 1\big), \qquad L = \text{longest run of consecutive backticks in the data}$$

A Markdown fence closes only on a backtick run at least as long as the opening one, so a fence one backtick longer
than anything inside is guaranteed to survive code or markdown in the user's data unchanged.

### 7.1.2 Example (the named case; real output)

IR: task `Describe what is happening in the picture.`; requirements = the two image sentences (B09); output format
from Stage C; attachment image.

*Claude*
```
<context>
<attachment>
The user attached an image.
</attachment>
</context>

<task>
Describe what is happening in the picture.
</task>

<constraints>
- Use what is visible in the attached image; describe the parts you rely on.
- If something is not visible or not readable in the image, say so instead of guessing.
</constraints>

<output_format>
Output as a single sentence describing each part.
</output_format>
```

*GPT*
```
### Task
Describe what is happening in the picture.

### Context
Attachment: The user attached an image.

### Constraints
- Use what is visible in the attached image; describe the parts you rely on.
- If something is not visible or not readable in the image, say so instead of guessing.

### Output format
Output as a single sentence describing each part.
```

*Gemini*
```
Task: Describe what is happening in the picture.

Constraints:
- Use what is visible in the attached image; describe the parts you rely on.
- If something is not visible or not readable in the image, say so instead of guessing.

Output format: Output as a single sentence describing each part.

Context:
Attachment: The user attached an image.
```

### 7.1.3 Nothing is lost: round-trip tests

`backend/tests/test_rendering.py` parses every rendering back (XML tags, `###` sections, labels) and checks that the
parsed sections equal the IR's fields, for 13 IRs × 3 targets: a full IR, a minimal one, a "tricky" one whose data
contains code fences, fake `# Output Format` / `Task:` headings and an `</input>` tag, and 9 real pipeline outputs with
and without pasted text and attachments. It also checks that metadata is never rendered, that requirements come
before constraints, and that the fence is longer than any backtick run.

*Known limit:* Claude's XML tags are not escaped, so data that itself contains a closing tag such as `</input>` cannot
be parsed back unambiguously (the test then only checks that every value is present). The content is never lost, but a
model could in principle read such a tag as the end of the block.

## 7.2 Counting input tokens (`count_tokens`, `token_counts`)

| target | method | exact? |
|---|---|---|
| GPT | `tiktoken.get_encoding("o200k_base")` — the tokenizer of the GPT-4o / GPT-4.1 / GPT-5 family | **exact** |
| Claude, Gemini | $\text{tokens} = \max\big(1, \operatorname{round}(\text{characters} / 4)\big)$ (0 for empty text) | approximate, labelled "approx. (characters / 4)" |

If `tiktoken` is not installed or its encoding file cannot be downloaded (first use offline), GPT falls back to the
approximation too, and is labelled accordingly.

**Basis of "characters ÷ 4".** Claude's and Gemini's tokenizers are not available offline, so the app uses the rule of
thumb that one token is about four characters of English text (`CHARS_PER_TOKEN = 4`). How good is it? Measured in
this review on the 482 test prompts' Stage A + B renderings (with their pasted text), against exact `o200k_base`
counts of the same text:

| rendering | (chars/4) ÷ exact o200k tokens: mean | median | 5th–95th percentile |
|---|---|---|---|
| Claude layout | 1.053 | 1.043 | 0.845 – 1.272 |
| GPT layout | 1.061 | 1.062 | 0.825 – 1.283 |
| Gemini layout | 1.076 | 1.081 | 0.843 – 1.297 |

The median rendering has **4.25 characters per o200k token**, so characters ÷ 4 **over-estimates by about 5–8%** on
average, and for 90% of prompts it is within roughly −17% to +30%. This measures the approximation against GPT's
tokenizer; Claude's and Gemini's own tokenizers differ from o200k by an amount that cannot be measured offline, which is
why those counts are always labelled approximate. Decisions in the project never depend on them: every reported token
result comes from the providers' own usage counts (chapter 8).

**What is stored.** For every optimized prompt and target, `token_usage` holds the method (`tokenizer` column), the
**original** input tokens (the prompt + `"\n\n"` + pasted text, counted the same way) and the optimized rendering's
input tokens. Output tokens are only known after a real model answers (Compare stores them as an extra row,
`tokenizer = "compare:<model>"`).

**Live counter:** `POST /api/ui/tokens` returns the three counts for any text (nothing stored), used by the UI as the
user types.
