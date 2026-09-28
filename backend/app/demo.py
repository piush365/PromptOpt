"""Offline demo of the pipeline on one prompt: Stage A features, each Stage B rule with before/after, the optimized
prompt (plain and rendered for a target LLM) and whether it would go to Stage C. No API call, no database.

    python -m app.demo "summarize this for me please"
    python -m app.demo "classify these as fruit or veg: tomato, apple" --category classification --target claude
    python -m app.demo --examples                  # five ready prompts, one per category
"""
import argparse
import os
import textwrap
from typing import Any

from app.rendering import render
from app.stage_b.optimizer import OptimizationOutput, apply_category_choice, optimize
from app.stage_b.rules import CATEGORY_MIN_CONFIDENCE, KNOWN_CATEGORIES

TARGETS = ("gpt", "gemini", "claude")
# One ready prompt per category, typed the way a rushed user would. The summarization one refers to text that was
# never given, so it shows a prompt going to Stage C.
EXAMPLES = [
    ("closed_qa", "when did apollo 11 land? text: Apollo 11 landed on the Moon on 20 July 1969."),
    ("information_extraction", "pull out the names and dates from this: Hi Sam, the review with Priya moved to "
                               "12 March and Dev starts on 3 April."),
    ("classification", "classify these as fruit or vegetable: tomato, carrot, apple, spinach, banana"),
    ("summarization", "hey can you just summarize this article for me"),
    ("coding", "write a python function that checks if a string is a palindrome"),
]
RULE = "-" * 78


def _indent(text: str, prefix: str = "    ") -> str:
    return textwrap.indent(text, prefix) if text else prefix + "(empty)"


def _yes(flag: bool) -> str:
    return "yes" if flag else "no"


def explain(prompt: str, detector: Any, category: str = "auto", target: str | None = None) -> tuple[str, OptimizationOutput]:
    """The demo report for one prompt, and the Stage B output it describes."""
    f = detector.detect(prompt)
    out = optimize(prompt, f, category=category, target_llm=target)
    used, _ = apply_category_choice(f, category)            # a user-chosen category changes the relevant constraints
    top = sorted(f.category_scores.items(), key=lambda kv: kv[1], reverse=True)[:3]
    lines = [RULE, "PROMPT", _indent(prompt), "",
             "STAGE A: feature detection",
             f"  category:            {f.task_type} (confidence {f.confidence:.2f}, {f.classifier} classifier; "
             f"Stage B's category rules need >= {CATEGORY_MIN_CONFIDENCE})",
             "  top scores:          " + ", ".join(f"{c} {s:.2f}" for c, s in top)]
    if out.ir.category_source == "user":
        lines.append(f"  category used:       {out.ir.category} (chosen by the user; overrides Stage A)")
    lines += [
        f"  output format given: {_yes(f.has_format_spec)}"
        + (f" ({', '.join(f.format_evidence)})" if f.format_evidence else " -> missing format"),
        f"  constraints stated:  {', '.join(f.constraints_present) or 'none'}",
        f"  constraints missing: {', '.join(used.missing_constraints) or 'none'}",
        f"  filler / repetition: {', '.join(repr(p) for p in f.redundant_phrases) or 'none'}",
        f"  ambiguous refs:      {', '.join(repr(r) for r in f.ambiguous_refs) or 'none'}",
        f"  text to work on:     {_yes(f.has_context)}", "",
        f"STAGE B: rule-based optimization ({len(out.steps)} rule(s) changed the prompt)"]
    for i, s in enumerate(out.steps, start=1):
        lines += [f"  [{i}] {s['rule_code']}", "    before:", _indent(s["before"], "      "),
                  "    after:", _indent(s["after"], "      ")]
    if not out.steps:
        lines.append("  no rule changed the prompt")
    lines += ["", "OPTIMIZED PROMPT", _indent(out.optimized_text)]
    if target:
        lines += ["", f"RENDERED FOR {target.upper()}", _indent(render(out.ir, target))]
    lines += ["", "STAGE C (LoRA fallback)",
              f"  would go to Stage C: {_yes(out.needs_stage_c)}"
              + (f" ({'; '.join(out.stage_c_reasons)})" if out.needs_stage_c else ""),
              f"  recorded, not routed: "
              + (", ".join(u for u in out.unresolved if u not in out.stage_c_reasons) or "nothing"),
              f"  confidence stored:   {out.confidence:.2f}", RULE]
    return "\n".join(lines), out


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("prompt", nargs="?", help="the prompt to optimize")
    ap.add_argument("--category", default="auto", choices=["auto", *sorted(KNOWN_CATEGORIES)],
                    help="override Stage A's category (default: auto-detect)")
    ap.add_argument("--target", choices=TARGETS, help="also render the optimized prompt for this LLM")
    ap.add_argument("--examples", action="store_true", help="run five ready prompts, one per category")
    args = ap.parse_args(argv)
    if not args.prompt and not args.examples:
        ap.error("give a prompt, or --examples")

    os.environ.setdefault("HF_HUB_OFFLINE", "1")      # the sentence model is cached locally: never go online
    from app.stage_a.detector import FeatureDetector

    detector = FeatureDetector()
    todo = [(c, p) for c, p in EXAMPLES] if args.examples else [(None, args.prompt)]
    for expected, prompt in todo:
        text, _ = explain(prompt, detector, args.category, args.target)
        if expected:
            print(f"\nEXAMPLE: {expected}")
        print(text)


if __name__ == "__main__":
    main()
