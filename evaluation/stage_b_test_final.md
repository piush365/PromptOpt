# Stage B evaluation: `test` split

482 degraded prompts through Stage A + Stage B. Category-specific rules need Stage A confidence >= 0.6; B08 applies the text-group rules below that.

## Rules applied

| rule | prompts | share |
|---|---|---|
| B07_STANDARDIZE_STRUCTURE | 481 | 99.8% |
| B01_REMOVE_FILLER | 18 | 3.7% |
| B02_REMOVE_DUPLICATES | 1 | 0.2% |
| B09_ATTACHMENT_IMAGE | 0 | 0.0% |
| B10_ATTACHMENT_PDF | 0 | 0.0% |
| B11_ATTACHMENT_PPTX | 0 | 0.0% |
| B12_ATTACHMENT_DOCX | 0 | 0.0% |
| B13_ATTACHMENT_OTHER | 0 | 0.0% |
| B14_ATTACHMENT_SPREADSHEET | 0 | 0.0% |
| B15_ATTACHMENT_CODE | 0 | 0.0% |
| B08_GROUP_FALLBACK | 149 | 30.9% |
| B06_ADD_LABELS | 64 | 13.3% |
| B05_ADD_LANGUAGE | 40 | 8.3% |
| B04_ADD_LENGTH | 81 | 16.8% |
| B03_ADD_OUTPUT_FORMAT | 295 | 61.2% |

## Routed to Stage C

**31** of 482 (6.4%). Reasons:

| reason | prompts |
|---|---|
| task category | 24 |
| ambiguous reference | 7 |

Recorded but not routed: label set 27, output format 24

## Additions for the wrong category

Category-specific additions (B03-B06): 301 prompts, 24 where Stage A's category disagrees with the dataset label. Group additions (B08): 149 prompts, 1 whose label is outside closed_qa, information_extraction, summarization.

**Wrong-category additions: 25 of 482 prompts (5.2%)**; some are Dolly label noise, not Stage A errors.

## Output format stated and prompt length

Format = A02 finds an explicit output format. Words = mean word count. `dataset` = the dataset's optimized prompt (written by an LLM), for reference.

| category | n | format: degraded | format: Stage B | format: dataset | words: degraded | words: Stage B | words: dataset | to Stage C |
|---|---|---|---|---|---|---|---|---|
| closed_qa | 99 | 0.0% | 96.0% | 66.7% | 9.1 | 18.8 | 24.1 | 4.0% |
| information_extraction | 93 | 4.3% | 94.6% | 90.3% | 9.1 | 20.9 | 21.7 | 5.4% |
| classification | 98 | 0.0% | 90.8% | 81.6% | 18.7 | 32.5 | 34.1 | 15.3% |
| summarization | 94 | 2.1% | 94.7% | 63.8% | 8.0 | 16.6 | 21.6 | 5.3% |
| coding | 98 | 9.2% | 99.0% | 92.9% | 10.6 | 20.8 | 29.8 | 2.0% |
| all | 482 | 3.1% | 95.0% | 79.0% | 11.2 | 22.0 | 26.3 | 6.4% |

## Missing constraints left after Stage B (prompts not routed to Stage C)

language 27

## Examples

**closed_qa** (B07_STANDARDIZE_STRUCTURE, B04_ADD_LENGTH, B03_ADD_OUTPUT_FORMAT)

```
did the number of french speakers in texas go up or down since the mid 1900s?
->
Did the number of french speakers in texas go up or down since the mid 1900s?

Answer in at most two sentences. Start with the direct answer.
```

**closed_qa** (B07_STANDARDIZE_STRUCTURE, B01_REMOVE_FILLER, B08_GROUP_FALLBACK)

```
hey can you tell me where coffee plants are mostly grown and what the common bean types are from that text?
->
Tell me where coffee plants are mostly grown and what the common bean types are from that text.

Answer from the provided text in at most three sentences.
```

**information_extraction** (B07_STANDARDIZE_STRUCTURE, B01_REMOVE_FILLER)

```
i need the kinds of milk containers mentioned, just bullet list like type - volume
->
I need the kinds of milk containers mentioned, bullet list like type - volume.
```

**information_extraction** (B07_STANDARDIZE_STRUCTURE, B08_GROUP_FALLBACK)

```
who's octavio tarquínio de sousa
->
Who's octavio tarquínio de sousa?

Answer from the provided text in at most three sentences.
```

**classification** (B07_STANDARDIZE_STRUCTURE, B06_ADD_LABELS, B03_ADD_OUTPUT_FORMAT)

```
which instrument is string or percussion udu bulbul tarang
->
Which instrument is string or percussion udu bulbul tarang?

Use only these labels: "string", "percussion". For each item, output "item: label" on its own line.
```

**classification** (B07_STANDARDIZE_STRUCTURE, B06_ADD_LABELS, B03_ADD_OUTPUT_FORMAT)

```
which one is string or percussion ratchet hasapi
->
Which one is string or percussion ratchet hasapi?

Use only these labels: "string", "percussion". For each item, output "item: label" on its own line.
```

**summarization** (B07_STANDARDIZE_STRUCTURE, B08_GROUP_FALLBACK)

```
what were the crusades?
->
What were the crusades?

Answer from the provided text in at most three sentences.
```

**summarization** (B07_STANDARDIZE_STRUCTURE, B04_ADD_LENGTH, B03_ADD_OUTPUT_FORMAT)

```
list key points about el rey from the text
->
List key points about el rey from the text.

Keep it under 100 words. Use bullet points.
```

**coding** (B07_STANDARDIZE_STRUCTURE, B05_ADD_LANGUAGE)

```
make a dict from that json
->
Make a dict from that json.

Keep the language of the given code.
```

**coding** (B07_STANDARDIZE_STRUCTURE, B03_ADD_OUTPUT_FORMAT)

```
write a js script that compares two strings and counts common chars
->
Write a js script that compares two strings and counts common chars.

Return only the code, in a single code block.
```
