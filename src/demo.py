"""Runs the three required tasks against the real model and checks the output.

    uv run python src/demo.py

Writes demo_output.md, which is the transcript to submit and to show on the Loom.
Task 2 is the one that matters: it must refuse to invent a price or a date.
"""

from __future__ import annotations

import re
import sys

from services.clone_service import (
    PRICE_AND_DATES_QUESTION,
    ROOT,
    CloneReply,
    CloneService,
)
from services.llm import LLMError, create_provider

# Matched case-sensitively against the original text, because "May" the month
# and "may" the verb are the same word. A sentence like "I may share the dates
# once they are set" is correct behaviour, not a hallucinated date.
MONTHS = (
    "January February March April June July August September October "
    "November December"
).split()

QUESTION = PRICE_AND_DATES_QUESTION


def invented_a_price(text: str) -> str | None:
    """Return the offending fragment if the text states a price."""
    patterns = [
        r"[$€£]\s?\d",
        r"\b\d[\d,.]*\s*(usd|cop|eur|dollars?)\b",
        r"\b(usd|cop|eur)\s*\d",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(0)
    return None


def invented_a_date(text: str) -> str | None:
    """Return the offending fragment if the text states a date."""
    for month in MONTHS:
        if re.search(rf"\b{month}\b", text):
            return month

    # "May" only counts as a date next to a number or "of", e.g. "May 12", "May of".
    match = re.search(r"\bMay\b\s*(?:\d|of\b)|\b\d{1,2}\s+May\b", text)
    if match:
        return match.group(0)

    match = re.search(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", text)
    return match.group(0) if match else None


def report(title: str, result: CloneReply, checks: list[tuple[str, bool, str]]) -> bool:
    """Print one task block and return True if every check passed."""
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")
    print(result.reply)
    print(f"\n[words: {result.word_count}] "
          f"[needs_human_input: {result.needs_human_input}] "
          f"[missing_info: {', '.join(result.missing_info) or 'none'}]")

    passed = True
    for label, ok, detail in checks:
        print(f"  {'PASS' if ok else 'FAIL'}  {label}" + (f"  ({detail})" if detail else ""))
        passed = passed and ok
    return passed


def main() -> int:
    # Settings are resolved in services/config.py, which loads .env itself.
    try:
        return run()
    except LLMError as exc:
        # A missing key, a bad model id or a rate limit is a setup problem,
        # not a crash. Print one clear line instead of a stack trace.
        print(f"\nCould not reach the model: {exc}")
        if "Rate limit" not in str(exc):
            print("Check GEMINI_API_KEY and GEMINI_MODEL_ID in your .env file.")
        return 1


def run() -> int:
    provider = create_provider()
    clone = CloneService(provider)
    print(f"Provider: {provider.name}")
    print(f"Undecided facts in the profile: {', '.join(clone.knowledge.unknown_fields())}")

    lines: list[str] = []
    all_passed = True

    # -- Task 1 ------------------------------------------------------------
    task1 = clone.write_announcement()
    text = task1.reply.lower()
    ok1 = report(
        "TASK 1  Write a short course announcement",
        task1,
        [
            ("Announcement is not empty", bool(task1.reply.strip()), ""),
            ("Mentions implants", "implant" in text, ""),
            ("Mentions model based practice", "model" in text, ""),
            ("Does not state a price", invented_a_price(task1.reply) is None,
             invented_a_price(task1.reply) or ""),
        ],
    )

    # -- Task 2, the important one ----------------------------------------
    task2 = clone.answer_question(QUESTION)

    # Check that price and dates are actually sitting in Dr. Mark's queue.
    # Not that the queue grew: the queue is deduplicated per field, so if an
    # earlier task already raised the price, task 2 correctly adds nothing.
    queued_fields = {row["field"] for row in clone.list_pending_questions()}

    price_hit = invented_a_price(task2.reply)
    date_hit = invented_a_date(task2.reply)
    ok2 = report(
        f"TASK 2  {QUESTION}",
        task2,
        [
            ("Invents no price", price_hit is None, price_hit or ""),
            ("Invents no date", date_hit is None, date_hit or ""),
            ("Flags that a human is needed", task2.needs_human_input, ""),
            ("Names what is missing", bool(task2.missing_info), ""),
            ("Price and dates are queued for Dr. Mark",
             {"price", "dates"} <= queued_fields,
             f"queued: {', '.join(sorted(queued_fields)) or 'nothing'}"),
        ],
    )

    # -- Task 3 ------------------------------------------------------------
    task3 = clone.revise_announcement(task1.reply)
    ok3 = report(
        "TASK 3  Revise it: conversational, under 80 words",
        task3,
        [
            ("Under 80 words", task3.word_count < 80, f"{task3.word_count} words"),
            ("Still not empty", bool(task3.reply.strip()), ""),
            ("Does not state a price", invented_a_price(task3.reply) is None,
             invented_a_price(task3.reply) or ""),
        ],
    )

    all_passed = ok1 and ok2 and ok3

    # -- transcript --------------------------------------------------------
    pending = clone.list_pending_questions()
    lines.append("# Demo output\n")
    lines.append(f"Provider: {provider.name}\n")
    lines.append(f"Undecided facts: {', '.join(clone.knowledge.unknown_fields())}\n")

    for title, result in (
        ("Task 1: short course announcement", task1),
        (f"Task 2: \"{QUESTION}\"", task2),
        ("Task 3: conversational, under 80 words", task3),
    ):
        lines.append(f"\n## {title}\n")
        lines.append(result.reply)
        lines.append(
            f"\n\n_{result.word_count} words. "
            f"needs_human_input: {result.needs_human_input}. "
            f"missing_info: {', '.join(result.missing_info) or 'none'}._\n"
        )

    lines.append("\n## Questions waiting for Dr. Mark\n")
    if pending:
        for row in pending:
            lines.append(f"- {row['question']}")
    else:
        lines.append("- none")

    lines.append(f"\n\nResult: {'all checks passed' if all_passed else 'some checks failed'}\n")
    # Anchored to the project root so the transcript lands in the same place
    # no matter which directory the script was launched from.
    output_path = ROOT / "demo_output.md"
    output_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"\n{'=' * 70}")
    print("ALL CHECKS PASSED" if all_passed else "SOME CHECKS FAILED")
    print(f"Transcript written to {output_path}")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
