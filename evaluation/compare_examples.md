# Compare: two live examples (2026-10-02)

Run through the app's API (`POST /api/compare`) on Groq's free tier, model `openai/gpt-oss-120b`, temperature 0, max 2048 tokens, reasoning "low", blind judge `qwen/qwen3.8-27b` (scores each answer against the user's original request, never told which prompt produced it). Raw responses: `evaluation/compare/live_examples.json`. These are illustrations of the feature, not evidence; the measured result is `token_test.md`.

## Coding: `write code to get all permutations of a string` (test item codealpaca-4815, 6 validated tests)

**GPT-rendered prompt, answered by gpt-oss-120b on Groq (a stand-in: GPT itself is not available here).**

| | original prompt | optimized prompt | change |
|---|---|---|---|
| input tokens | 80 | 106 | +32.5% |
| output tokens (reasoning) | 688 (10) | 142 (13) | -79.4% |
| total tokens | 768 | 248 | **-67.7%** |
| latency | 1474 ms | 311 ms | -78.9% |
| sandbox tests | pass 6/6 | pass 6/6 | |
| blind judge (0-10) | 10 | 10 | |

**Optimized prompt sent:**
```
### Task
Write code to get all permutations of a string.

### Constraints
- Use Python.

### Output format
Return only the code, in a single code block.
```

<details><summary>Answers</summary>

Original prompt's answer:
```
Here’s a compact, easy‑to‑read implementation that generates **all permutations** of a given string (or any iterable of hashable items).  
It works for Python 3.6+ and returns the permutations as a list of strings.

```python
from typing import List

def permutations(s: str) -> List[str]:
    """
    Return a list containing every possible permutation of the characters in `s`.

    Example
    -------
    >>> permutations("abc")
    ['abc', 'acb', 'bac', 'bca', 'cab', 'cba']
    """
    # Base case – a single character (or empty string) has only itself as a permutation
    if len(s) <= 1:
        return [s]

    # Recursive case – fix each character in turn and permute the rest
    result = []
    for i, ch in enumerate(s):
        # Characters before i + after i give the "remaining" substring
        rest = s[:i] + s[i+1:]
        # Recursively get permutations of the remaining characte
[... 1726 more characters]
```
Optimized prompt's answer:
```
```python
def permutations(s: str):
    """Return a list of all permutations of the input string `s`."""
    if len(s) <= 1:
        return [s]

    result = []
    for i, ch in enumerate(s):
        # Permutations of the remaining characters
        for perm in permutations(s[:i] + s[i+1:]):
            result.append(ch + perm)
    return result


# Example usage:
if __name__ == "__main__":
    test_str = "abc"
    for p in permutations(test_str):
        print(p)
```
```
</details>

## closed_qa: `which company bought hackpad according to that text?` + its passage (val item dolly-2272)

**Claude-rendered prompt, answered by gpt-oss-120b on Groq (a stand-in: Claude itself is not available here).**

| | original prompt | optimized prompt | change |
|---|---|---|---|
| input tokens | 214 | 259 | +21.0% |
| output tokens (reasoning) | 24 (6) | 20 (6) | -16.7% |
| total tokens | 238 | 279 | **+17.2%** |
| latency | 67 ms | 58 ms | -13.4% |
| blind judge (0-10) | 10 | 10 | |

**Optimized prompt sent:**
```
<context>
<document>
Hackpad was a web-based collaborative real-time text editor forked from Etherpad.

It was used as the company wikis by multiple prominent startups of the 2010s, such as Airbnb, Stripe, and Upworthy.

In April 2014, Hackpad was acquired by Dropbox. In April 2015, it was announced that Hackpad would be released as open source and source code was published on GitHub in August 2015, under the Apache license 2.0. On April 25, 2017, Hackpad announced that it is to shut down on July 19, 2017, permanently migrating to Dropbox Paper.
</document>
</context>

<task>
Which company bought hackpad according to that text?
</task>

<constraints>
- Answer in at most two sentences.
</constraints>

<output_format>
Start with the direct answer.
</output_format>
```

<details><summary>Answers</summary>

Original prompt's answer:
```
Hackpad was acquired by **Dropbox**.
```
Optimized prompt's answer:
```
Dropbox bought Hackpad.
```
</details>

## Reading

* Coding: both answers pass all 6 tests and get the same judge score, but the optimized prompt (code only, one block) cuts the answer from 688 to 142 tokens: total -67.7%, latency -79%.
* closed_qa: the user's question already got a one-line answer, so the longer optimized prompt cannot pay for itself here: total tokens +17%. Token savings come from long, unrequested answers; when the original answer is already short, the optimized prompt costs a few extra input tokens.
* Both are labelled as stand-ins: the prompts were rendered for GPT and Claude and answered by gpt-oss-120b, because no GPT or Claude API key is configured.
