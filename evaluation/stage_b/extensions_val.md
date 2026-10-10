# Stage B extensions (B16) on the `val` split

Frozen rules vs frozen rules + extensions, same Stage A features. `auto` = Stage A's category (the evaluation setting); `dataset category` = the dataset's label as if the user had picked it. A stated label agrees when it appears in the dataset's LLM-written optimized prompt (a rough check: the target may use a synonym).

| category choice | prompts | B16 fired | label set added | label set changed | items moved to input | routed to Stage C: before -> after | labels agreeing with the target |
|---|---|---|---|---|---|---|---|
| auto | 149 | 8 | 0 | 0 | 8 | 10 -> 10 | 13/16 |
| dataset category | 149 | 8 | 0 | 0 | 8 | 1 -> 1 | 13/16 |

## Changed prompts (auto)

**dolly-1659** (classification, category auto)

```
Which instrument is string or percussion agiarut agung?

Use only these labels: "string", "percussion". For each item, output "item: label" on its own line.
```
->
```
Which instrument is string or percussion?

Input:
agiarut agung

Use only these labels: "string", "percussion". For each item, output "item: label" on its own line.
```
Dataset target: Classify each listed instrument as either "string" or "percussion". Output each instrument followed by its label on a separate line, e.g., "Agiarut: string".

Items: Agiarut, Agung

**dolly-8020** (classification, category auto)

```
Which one is string or percussion nagara sape?

Use only these labels: "string", "percussion". For each item, output "item: label" on its own line.
```
->
```
Which one is string or percussion?

Input:
nagara sape

Use only these labels: "string", "percussion". For each item, output "item: label" on its own line.
```
Dataset target: Classify each listed instrument as either "string" or "percussion". Output a JSON object with instrument names as keys and the label (string or percussion) as values.

Items: Nagara, Sape

**dolly-6777** (classification, category auto)

```
Which characters are dc or marvel? sif, wonder woman.

Use only these labels: "dc", "marvel". For each item, output "item: label" on its own line.
```
->
```
Which characters are dc or marvel?

Input:
sif, wonder woman

Use only these labels: "dc", "marvel". For each item, output "item: label" on its own line.
```
Dataset target: Classify each listed character as belonging to DC or Marvel. Output a JSON object mapping each character to its label ("DC" or "Marvel").

Items: Sif, Wonder Woman

**dolly-728** (classification, category auto)

```
Which instrument is string or percussion lummi stick timple?

Use only these labels: "string", "percussion". For each item, output "item: label" on its own line.
```
->
```
Which instrument is string or percussion?

Input:
lummi stick timple

Use only these labels: "string", "percussion". For each item, output "item: label" on its own line.
```
Dataset target: Determine for each instrument (Lummi stick, Timple) whether it is a string or percussion instrument. Output a JSON object with the instrument names as keys and the label "string" or "percussion" as the value.

**dolly-12192** (classification, category auto)

```
Which instrument is string or percussion repique neola?

Use only these labels: "string", "percussion". For each item, output "item: label" on its own line.
```
->
```
Which instrument is string or percussion?

Input:
repique neola

Use only these labels: "string", "percussion". For each item, output "item: label" on its own line.
```
Dataset target: Classify each instrument as "string" or "percussion". Instruments: Repique, Neola. Output a JSON object with fields "Repique" and "Neola" each set to the appropriate label.

**dolly-6542** (classification, category auto)

```
Which instrument is string or percussion fiddlesticks tricordia?

Use only these labels: "string", "percussion". For each item, output "item: label" on its own line.
```
->
```
Which instrument is string or percussion?

Input:
fiddlesticks tricordia

Use only these labels: "string", "percussion". For each item, output "item: label" on its own line.
```
Dataset target: Classify each listed instrument as either string or percussion. Output a JSON object with the instrument names as keys and the label ("string" or "percussion") as the value.

Items: Fiddlesticks, Tricordia

**dolly-2314** (classification, category auto)

```
Are these people actors or authors? Russell Crowe, Tom Hanks, Jamie Lee Curtis, Joanne Woodward, Sara Jessica Parker, Tom Cruise, Alexander Dumas, JK Rowling, Ingrid Bergman, Grace Kelly, Judi Dench, Kate Winslet, Jodie Foster, Doris Day, William Shakespeare, Jalal al-Din Muhammad Rumi.

Use only these labels: "people actors", "authors". For each item, output "item: label" on its own line.
```
->
```
Are these people actors or authors?

Input:
Russell Crowe, Tom Hanks, Jamie Lee Curtis, Joanne Woodward, Sara Jessica Parker, Tom Cruise, Alexander Dumas, JK Rowling, Ingrid Bergman, Grace Kelly, Judi Dench, Kate Winslet, Jodie Foster, Doris Day, William Shakespeare, Jalal al-Din Muhammad Rumi

Use only these labels: "people actors", "authors". For each item, output "item: label" on its own line.
```
Dataset target: Classify each name as 'actor' or 'author'. Return a JSON array of objects with keys 'name' and 'role'.

Items: Russell Crowe, Tom Hanks, Jamie Lee Curtis, Joanne Woodward, Sara Jessica Parker, Tom Cruise, Alexander Dumas, JK Rowling, Ingrid Bergman, Grace Kelly,  Judi Dench, Kate Winslet, Jodie Fost

**dolly-7818** (classification, category auto)

```
Which of these are flowers and which are european countries? roses, norway, tulips, the netherlands, sweden, france, spain, greece, italy, and sunflowers.

Use only these labels: "flowers", "european countries". For each item, output "item: label" on its own line.
```
->
```
Which of these are flowers and which are european countries?

Input:
roses, norway, tulips, the netherlands, sweden, france, spain, greece, italy, sunflowers

Use only these labels: "flowers", "european countries". For each item, output "item: label" on its own line.
```
Dataset target: Classify each item as either "Flower" or "European Country". Output a JSON object where keys are the items and values are the labels.

Items: roses, Norway, tulips, the Netherlands, Sweden, France, Spain, Greece, Italy, and sunflowers


## Changed prompts (dataset category)

**dolly-1659** (classification, category classification)

```
Which instrument is string or percussion agiarut agung?

Use only these labels: "string", "percussion". For each item, output "item: label" on its own line.
```
->
```
Which instrument is string or percussion?

Input:
agiarut agung

Use only these labels: "string", "percussion". For each item, output "item: label" on its own line.
```
Dataset target: Classify each listed instrument as either "string" or "percussion". Output each instrument followed by its label on a separate line, e.g., "Agiarut: string".

Items: Agiarut, Agung

**dolly-8020** (classification, category classification)

```
Which one is string or percussion nagara sape?

Use only these labels: "string", "percussion". For each item, output "item: label" on its own line.
```
->
```
Which one is string or percussion?

Input:
nagara sape

Use only these labels: "string", "percussion". For each item, output "item: label" on its own line.
```
Dataset target: Classify each listed instrument as either "string" or "percussion". Output a JSON object with instrument names as keys and the label (string or percussion) as values.

Items: Nagara, Sape

**dolly-6777** (classification, category classification)

```
Which characters are dc or marvel? sif, wonder woman.

Use only these labels: "dc", "marvel". For each item, output "item: label" on its own line.
```
->
```
Which characters are dc or marvel?

Input:
sif, wonder woman

Use only these labels: "dc", "marvel". For each item, output "item: label" on its own line.
```
Dataset target: Classify each listed character as belonging to DC or Marvel. Output a JSON object mapping each character to its label ("DC" or "Marvel").

Items: Sif, Wonder Woman

**dolly-728** (classification, category classification)

```
Which instrument is string or percussion lummi stick timple?

Use only these labels: "string", "percussion". For each item, output "item: label" on its own line.
```
->
```
Which instrument is string or percussion?

Input:
lummi stick timple

Use only these labels: "string", "percussion". For each item, output "item: label" on its own line.
```
Dataset target: Determine for each instrument (Lummi stick, Timple) whether it is a string or percussion instrument. Output a JSON object with the instrument names as keys and the label "string" or "percussion" as the value.

**dolly-12192** (classification, category classification)

```
Which instrument is string or percussion repique neola?

Use only these labels: "string", "percussion". For each item, output "item: label" on its own line.
```
->
```
Which instrument is string or percussion?

Input:
repique neola

Use only these labels: "string", "percussion". For each item, output "item: label" on its own line.
```
Dataset target: Classify each instrument as "string" or "percussion". Instruments: Repique, Neola. Output a JSON object with fields "Repique" and "Neola" each set to the appropriate label.

**dolly-6542** (classification, category classification)

```
Which instrument is string or percussion fiddlesticks tricordia?

Use only these labels: "string", "percussion". For each item, output "item: label" on its own line.
```
->
```
Which instrument is string or percussion?

Input:
fiddlesticks tricordia

Use only these labels: "string", "percussion". For each item, output "item: label" on its own line.
```
Dataset target: Classify each listed instrument as either string or percussion. Output a JSON object with the instrument names as keys and the label ("string" or "percussion") as the value.

Items: Fiddlesticks, Tricordia

**dolly-2314** (classification, category classification)

```
Are these people actors or authors? Russell Crowe, Tom Hanks, Jamie Lee Curtis, Joanne Woodward, Sara Jessica Parker, Tom Cruise, Alexander Dumas, JK Rowling, Ingrid Bergman, Grace Kelly, Judi Dench, Kate Winslet, Jodie Foster, Doris Day, William Shakespeare, Jalal al-Din Muhammad Rumi.

Use only these labels: "people actors", "authors". For each item, output "item: label" on its own line.
```
->
```
Are these people actors or authors?

Input:
Russell Crowe, Tom Hanks, Jamie Lee Curtis, Joanne Woodward, Sara Jessica Parker, Tom Cruise, Alexander Dumas, JK Rowling, Ingrid Bergman, Grace Kelly, Judi Dench, Kate Winslet, Jodie Foster, Doris Day, William Shakespeare, Jalal al-Din Muhammad Rumi

Use only these labels: "people actors", "authors". For each item, output "item: label" on its own line.
```
Dataset target: Classify each name as 'actor' or 'author'. Return a JSON array of objects with keys 'name' and 'role'.

Items: Russell Crowe, Tom Hanks, Jamie Lee Curtis, Joanne Woodward, Sara Jessica Parker, Tom Cruise, Alexander Dumas, JK Rowling, Ingrid Bergman, Grace Kelly,  Judi Dench, Kate Winslet, Jodie Fost

**dolly-7818** (classification, category classification)

```
Which of these are flowers and which are european countries? roses, norway, tulips, the netherlands, sweden, france, spain, greece, italy, and sunflowers.

Use only these labels: "flowers", "european countries". For each item, output "item: label" on its own line.
```
->
```
Which of these are flowers and which are european countries?

Input:
roses, norway, tulips, the netherlands, sweden, france, spain, greece, italy, sunflowers

Use only these labels: "flowers", "european countries". For each item, output "item: label" on its own line.
```
Dataset target: Classify each item as either "Flower" or "European Country". Output a JSON object where keys are the items and values are the labels.

Items: roses, Norway, tulips, the Netherlands, Sweden, France, Spain, Greece, Italy, and sunflowers

