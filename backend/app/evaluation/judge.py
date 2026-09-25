"""LLM-as-judge: one score (0-10) and a short reason for one response, blind to which prompt variant produced it.

The judge sees the request exactly as the target LLM received it (so "follows the requested format" is judged
against what that prompt asked for), the attached text (shortened), the dataset's reference answer and the response.
It is never told the variant name. For closed_qa it also answers whether the response is correct (task success).
Use a different model from the target LLM, so the judge does not favour its own answers.
"""
import json
import re
from dataclasses import dataclass

MAX_CONTEXT_CHARS = 2000
MAX_RESPONSE_CHARS = 6000

SYSTEM = """You are a strict, fair grader of answers written by an AI assistant.
You get the USER REQUEST exactly as the assistant received it, the TEXT attached to it (may be shortened), a
REFERENCE ANSWER written by a human, and the assistant's RESPONSE.

Score the RESPONSE from 0 to 10, considering together:
- correctness: agrees with the reference answer and the attached text; no invented facts
- relevance: answers what was asked, nothing off-topic
- format: follows any format, length or style the request asked for (if it asked for none, do not penalise)
- completeness: covers everything the request asked for
10 = correct, relevant, follows the requested format and complete. 0 = wrong, off-topic or empty.
The reference answer shows the expected content; a response can be correct with different wording or structure.
{extra}
Return ONLY a JSON object: {schema}"""

CLOSED_QA_EXTRA = ('Also decide "answers_correctly": true if the RESPONSE gives the same answer as the REFERENCE '
                   'ANSWER (wording may differ), false otherwise.')


@dataclass
class Judgment:
    score: float
    reason: str
    answers_correctly: bool | None = None


def messages(category: str, request: str, context: str | None, reference: str, response: str) -> list[dict]:
    closed_qa = category == "closed_qa"
    schema = ('{"score": <0-10>, "answers_correctly": <true|false>, "reason": "<one short sentence>"}' if closed_qa
              else '{"score": <0-10>, "reason": "<one short sentence>"}')
    system = SYSTEM.format(extra=CLOSED_QA_EXTRA if closed_qa else "", schema=schema)
    context = (context or "").strip()
    if len(context) > MAX_CONTEXT_CHARS:
        context = context[:MAX_CONTEXT_CHARS] + " [...]"
    response = response.strip() or "(empty response)"
    if len(response) > MAX_RESPONSE_CHARS:
        response = response[:MAX_RESPONSE_CHARS] + " [...]"
    user = "\n\n".join([f"USER REQUEST:\n{request.strip()}", f"TEXT:\n{context or '(none)'}",
                        f"REFERENCE ANSWER:\n{reference.strip()}", f"RESPONSE:\n{response}"])
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def parse(content: str, category: str) -> Judgment:
    """Read the judge's JSON (thinking tags and surrounding text are ignored). Raises ValueError if unusable."""
    text = re.sub(r"<think>.*?</think>", "", content or "", flags=re.DOTALL).strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    try:
        data = json.loads(match.group(0) if match else text)
        score = float(data["score"])
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
        raise ValueError(f"judge returned no usable JSON: {text[:200]!r}") from e
    correct = None
    if category == "closed_qa":
        value = data.get("answers_correctly")
        if isinstance(value, str):
            value = {"true": True, "false": False, "yes": True, "no": False}.get(value.strip().lower())
        if not isinstance(value, bool):
            raise ValueError(f"closed_qa judgment without answers_correctly: {text[:200]!r}")
        correct = value
    return Judgment(score=min(10.0, max(0.0, score)), reason=str(data.get("reason", "")).strip(),
                    answers_correctly=correct)
