"""Stage B extensions: rules added after the final test run (2026-10-10). They run only when the caller asks for them
(`optimize(..., extensions=True)`, which the app's pipeline does); the frozen pipeline, the freeze check and every
reported test number are unchanged. Each rule is measured on val (`python -m app.stage_b.extensions_eval`).

B16 wider labels: B06 finds labels only in "classify as X or Y", "which are X and which are Y" and "is it X or Y".
Prompts such as "frm the list tell me prog lang or animal panda python java snake" name the labels after a request
verb ("tell me / say / decide / check whether ... X or Y") and often glue the items on without a colon. When B06
recorded `label set` as unresolved, B16 looks for that shape, states the labels, and moves trailing items into the
input block (as B07 does for "task: items").
When B06 did find the labels but the items are still glued onto the task ("say whether these are fruits or
vegetables tomato carrot apple"), B16 moves them into the input block too, and undoes B06's known glue error when a
comma shows where the items start and exactly one word was glued on ("city or a country paris, france, berlin": B06
says "country paris"; B16 makes the label "country" and the items "paris, france, berlin").
"""
import re

from app.stage_a.schema import PromptFeatures
from app.stage_b.ir import PromptIR
from app.stage_b.rules import tidy

_I = re.IGNORECASE
_ARTICLE = r"(?:(?:an?|the)\s+)?"
_WORDS = r"[A-Za-z][\w'-]*(?:\s+[A-Za-z][\w'-]*)?"             # the first label: 1-2 words right after the trigger
_TRIGGER = re.compile(
    # "classify / sort / label / group ... as X or Y" is B06's shape; with an object noun in between ("classify these
    # teams epl or la liga") the label boundary cannot be found reliably, so those verbs are not triggers here
    r"\b(?:tell me|say|decide|determine|figure out|check|find out|indicate)\b"
    r"(?:\s+(?:if|whether|which|what))?(?:\s+(?:each|every|it|they|these|those|the items?)(?:\s+(?:one|item|word))?)?"
    r"(?:\s+(?:is|are|'s|belongs? to|goes? (?:in|with)))?\s+" + _ARTICLE, _I)
_OR = re.compile(rf"(?P<a>{_WORDS})\s+or\s+{_ARTICLE}(?P<rest>.+)$", _I | re.S)
_PUNCT = re.compile(r"[,:;?!.()\n]")
_LABELS_STATED = re.compile(r"\bUse only these labels:", _I)


def _split_labels(after_trigger: str) -> tuple[list[str], str] | None:
    """'prog lang or animal panda python java' -> (['prog lang', 'animal'], 'panda python java')."""
    m = _OR.match(after_trigger.strip())
    if not m:
        return None
    a = m["a"].strip()
    rest = m["rest"].strip()
    stop = _PUNCT.search(rest)
    if stop:                                            # "... or an animal: panda, python" / "... or animal?"
        b, tail = rest[:stop.start()].strip(), rest[stop.end():].strip(" :,;")
        if len(b.split()) > 3:
            return None
    else:                                               # items glued on: the second label is one word
        words = rest.split()
        b, tail = words[0], " ".join(words[1:])
    if not a or not b or a.lower() == b.lower() or len(a.split()) > 2:
        return None
    return [a, b], tail


_LABEL_REQ = "Use only these labels: "


def _items(tail: str) -> str | None:
    """The items as the input block: comma-separated items one per comma; without commas the words are kept as typed
    (where one multi-word item ends and the next begins cannot be known: "lummi stick timple"). None if there is no
    item list (fewer than 2 words / items)."""
    tail = " ".join(tail.strip(" ,:;.?!").split())
    if "," in tail:
        items = [re.sub(r"^(?:and|or)\s+", "", w.strip(), flags=_I) for w in tail.split(",") if w.strip()]
        return ", ".join(items) if len(items) >= 2 else None
    return tail if len(tail.split()) >= 2 else None


def _unglue(ir: PromptIR) -> PromptIR:
    """B06 found two labels; items glued after the second one in the task move to the input block."""
    req = next((r for r in ir.requirements if r.startswith(_LABEL_REQ)), None)
    labels = re.findall(r'"([^"]+)"', req or "")
    if ir.context is not None or len(labels) != 2:
        return ir
    a, b = labels
    task = ir.task.rstrip(".?!")
    i = task.lower().rfind(b.lower())
    if i < 0:
        return ir
    tail, new_b = task[i + len(b):], b
    extra = len(b.split()) - len(a.split())
    if tail.lstrip().startswith(",") and extra > 1:          # several words glued on: where the item starts is unclear
        return ir
    if tail.lstrip().startswith(",") and extra == 1:         # B06 glued the first item on
        new_b = " ".join(b.split()[:len(a.split())])
        tail = " ".join(b.split()[len(a.split()):]) + tail
    items = _items(tail)
    if items is None:
        return ir
    new_req = _LABEL_REQ + f'"{a}", "{new_b}".'
    return ir.model_copy(update={"task": tidy(task[:i] + new_b), "context": items,
                                 "requirements": tuple(new_req if r == req else r for r in ir.requirements),
                                 "unresolved": _refs_resolved(ir.unresolved)})


def _refs_resolved(unresolved: tuple[str, ...]) -> tuple[str, ...]:
    """The items are now the input block, which is what "these" / "the list" referred to."""
    return tuple(u for u in unresolved if not u.startswith("ambiguous reference"))


def b16_labels_wider(ir: PromptIR, f: PromptFeatures) -> PromptIR:
    """Classification: state the labels a "tell me X or Y" prompt names, and move glued-on items into the input.
    (Labels only when B06 found none; items typed after the labels without a colon go to the input block.)"""
    if ir.category != "classification":
        return ir
    if "label set" not in ir.unresolved:
        return _unglue(ir)
    m = _TRIGGER.search(ir.task)
    if not m:
        return ir
    found = _split_labels(ir.task[m.end():].rstrip(".?!"))
    if found is None:
        return ir
    labels, tail = found
    update: dict = {"requirements": (*ir.requirements, "Use only these labels: "
                                     + ", ".join(f'"{x}"' for x in labels) + "."),
                    "unresolved": tuple(u for u in ir.unresolved if u != "label set")}
    items = _items(tail)
    if ir.context is None and items is not None:
        head = ir.task[:m.end()] + ir.task[m.end():].split(tail, 1)[0] if tail in ir.task else ir.task
        update.update(task=tidy(head), context=items, unresolved=_refs_resolved(update["unresolved"]))
    return ir.model_copy(update=update)


EXTENSION_RULES = [("B16_LABELS_WIDER", b16_labels_wider)]
