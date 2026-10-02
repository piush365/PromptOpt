# Attachment rules on the hand-made test set

30 hand-written prompts (`evaluation/attachments/attachment_prompts.json`), 5 per attachment type, through the real Stage A + Stage B and all three renderers (`python -m app.attachment_eval`). Correct = the type's rule fired, no other attachment rule fired, its requirements and the attachment note are in all three renderings, and no ambiguous reference is left.

| type | rule | fired correctly | own rule fired | only its rule | requirements in all 3 renderings | ambiguous refs found -> resolved |
|---|---|---|---|---|---|---|
| image | B09_ATTACHMENT_IMAGE | **5/5** | 5/5 | 5/5 | 5/5 | 1 -> 1 |
| pdf | B10_ATTACHMENT_PDF | **5/5** | 5/5 | 5/5 | 5/5 | 2 -> 2 |
| pptx | B11_ATTACHMENT_PPTX | **5/5** | 5/5 | 5/5 | 5/5 | 2 -> 2 |
| docx | B12_ATTACHMENT_DOCX | **5/5** | 5/5 | 5/5 | 5/5 | 1 -> 1 |
| spreadsheet | B14_ATTACHMENT_SPREADSHEET | **5/5** | 5/5 | 5/5 | 5/5 | 1 -> 1 |
| code | B15_ATTACHMENT_CODE | **5/5** | 5/5 | 5/5 | 5/5 | 3 -> 3 |

**All: 30/30 correct.** Prompts still sent to Stage C after the attachment rule: 2 (only for the task category; the attachment resolves ambiguous references).

## Per prompt

| id | prompt | category (Stage A) | rules applied | correct | Stage C |
|---|---|---|---|---|---|
| img-1 | what's the total on this receipt | information_extraction | B07, B09, B08 | yes | - |
| img-2 | describe what is happening in the picture | coding | B07, B09 | yes | task category |
| img-3 | summarize the trends in this chart for me please | summarization | B07, B01, B09, B04, B03 | yes | - |
| img-4 | is each plant in the photo a herb or a weed | classification | B07, B09, B03 | yes | - |
| img-5 | can you write down the steps from the whiteboard | summarization | B07, B01, B09, B08 | yes | - |
| pdf-1 | when does the contract end | information_extraction | B07, B10, B08 | yes | - |
| pdf-2 | summarize this paper | summarization | B07, B10, B04, B03 | yes | - |
| pdf-3 | pull out all the dates and amounts mentioned | information_extraction | B07, B10, B03 | yes | - |
| pdf-4 | hey how do I reset the device according to the manual | other | B07, B01, B10 | yes | task category |
| pdf-5 | who issued it | closed_qa | B07, B10, B04, B03 | yes | - |
| ppt-1 | make notes from these slides | information_extraction | B07, B11, B08 | yes | - |
| ppt-2 | give me the main points of the deck | summarization | B07, B11, B04, B03 | yes | - |
| ppt-3 | what are the three causes listed in the lecture | summarization | B07, B11, B08 | yes | - |
| ppt-4 | list every number and metric on the slides | information_extraction | B07, B11, B03 | yes | - |
| ppt-5 | classify each slide as theory or exercise | classification | B07, B11, B06, B03 | yes | - |
| doc-1 | what decisions were made in the meeting | summarization | B07, B12, B08 | yes | - |
| doc-2 | summarize my essay in a few lines | summarization | B07, B12, B04, B03 | yes | - |
| doc-3 | extract the names and email addresses from the document | information_extraction | B07, B12, B03 | yes | - |
| doc-4 | is remote work allowed under this policy | closed_qa | B07, B12, B04, B03 | yes | - |
| doc-5 | could you please list the jobs on this cv | information_extraction | B07, B01, B12, B08 | yes | - |
| xls-1 | which month had the highest sales | closed_qa | B07, B14, B04, B03 | yes | - |
| xls-2 | compute the average grade per student | coding | B07, B14, B05, B03 | yes | - |
| xls-3 | summarize what this data shows | summarization | B07, B14, B04, B03 | yes | - |
| xls-4 | label each expense as fixed or variable | classification | B07, B14, B06, B03 | yes | - |
| xls-5 | list the items with stock below 10 | information_extraction (coding) | B07, B14, B03 | yes | - |
| code-1 | fix the bug in this file | coding | B07, B15, B05, B03 | yes | - |
| code-2 | add comments to every function | coding | B07, B15, B05, B03 | yes | - |
| code-3 | explain what this code does | coding | B07, B15, B05, B03 | yes | - |
| code-4 | write unit tests for it | coding | B07, B15, B05, B03 | yes | - |
| code-5 | can you make this query faster | coding | B07, B01, B15, B05, B03 | yes | - |

## Example: `summarize this paper` + paper.pdf

**claude**

```
<context>
<attachment>
The user attached a PDF named paper.pdf.
</attachment>
</context>

<task>
Summarize this paper.
</task>

<constraints>
- Use the attached PDF (paper.pdf) as the source.
- Cite the page or section numbers for the information you use.
- If the PDF does not contain the answer, say so.
- Keep it under 100 words.
</constraints>

<output_format>
Use bullet points.
</output_format>
```

**gpt**

```
### Task
Summarize this paper.

### Context
Attachment: The user attached a PDF named paper.pdf.

### Constraints
- Use the attached PDF (paper.pdf) as the source.
- Cite the page or section numbers for the information you use.
- If the PDF does not contain the answer, say so.
- Keep it under 100 words.

### Output format
Use bullet points.
```

**gemini**

```
Task: Summarize this paper.

Constraints:
- Use the attached PDF (paper.pdf) as the source.
- Cite the page or section numbers for the information you use.
- If the PDF does not contain the answer, say so.
- Keep it under 100 words.

Output format: Use bullet points.

Context:
Attachment: The user attached a PDF named paper.pdf.
```

