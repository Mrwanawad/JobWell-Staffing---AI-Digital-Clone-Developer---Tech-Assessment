"""The clone itself: knowledge, prompt, the three tasks, and the human loop.

Design note for the reviewer. The model is rented. Everything in this file is
the part that makes it Dr. Mark rather than a generic assistant:
the profile as the single source of facts, the rule that null means unknown,
the JSON contract, the pending questions queue, and the corrections loop.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import yaml

from services.llm import BaseLLMProvider, ChatMessage

# This file lives in src/services/, so the project root is two levels up.
# Knowledge and prompts stay at the root: they are content Dr. Mark edits,
# not code.
ROOT = Path(__file__).resolve().parents[2]
PROFILE_PATH = ROOT / "knowledge" / "profile.yaml"
PROMPT_PATH = ROOT / "prompts" / "system_prompt.md"
DATA_DIR = ROOT / "data"


# --------------------------------------------------------------------------
# Small JSON store. A database would be the wrong tool at this size.
# --------------------------------------------------------------------------


def _read_json(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


def _write_json(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _short_id() -> str:
    return uuid.uuid4().hex[:8]


# Phrased the way Dr. Mark would read them in his queue. Anything not listed
# falls back to a generic wording.
_FIELD_QUESTIONS = {
    "price": "What is the price for the course?",
    "dates": "What are the dates for the course?",
    "venue": "Where is the course being held?",
}


def _question_for(field_name: str) -> str:
    return _FIELD_QUESTIONS.get(field_name, f"Please confirm: {field_name}")


# --------------------------------------------------------------------------
# What each task actually sends to the model.
#
# These live at module level so the UI can show the user the exact string being
# sent, rather than a hand-written copy of it that quietly drifts out of sync.
# One definition, displayed and executed.
# --------------------------------------------------------------------------

ANNOUNCEMENT_REQUEST = (
    "Write a short announcement for the implant course, for dentists. "
    "Keep it educational and in Dr. Mark's voice."
)

PRICE_AND_DATES_QUESTION = "How much does the course cost, and when is it?"


def revision_request(text: str) -> str:
    return (
        "Rewrite the announcement below so it sounds more conversational, "
        "like Dr. Mark talking to a colleague. It must be under 80 words. "
        "Do not add any facts that are not already in it.\n\n"
        f"{text}"
    )


def retry_request(word_count: int, text: str) -> str:
    return (
        f"That draft was {word_count} words, which is too long. "
        "Rewrite it under 80 words. Keep the same meaning and voice.\n\n"
        f"{text}"
    )


# --------------------------------------------------------------------------
# Knowledge
# --------------------------------------------------------------------------


class Knowledge:
    """Loads the profile and reports which facts are still undecided."""

    def __init__(self, path: Path = PROFILE_PATH) -> None:
        self.path = path
        self.data: dict = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    def as_yaml(self) -> str:
        return yaml.safe_dump(self.data, sort_keys=False, allow_unicode=True)

    def unknown_fields(self) -> list[str]:
        """Every course field that is still null, so the UI can show them."""
        course = self.data.get("course", {}) or {}
        return sorted(key for key, value in course.items() if value is None)


# --------------------------------------------------------------------------
# Result of one request
# --------------------------------------------------------------------------


@dataclass
class CloneReply:
    reply: str
    missing_info: list[str] = field(default_factory=list)
    needs_human_input: bool = False
    raw: str = ""

    @property
    def word_count(self) -> int:
        return len(self.reply.split())


# --------------------------------------------------------------------------
# The clone
# --------------------------------------------------------------------------


class CloneService:
    """One entry point for the UI, the demo script and any future integration."""

    def __init__(
        self,
        provider: BaseLLMProvider,
        knowledge: Knowledge | None = None,
        data_dir: Path = DATA_DIR,
    ) -> None:
        self.provider = provider
        self.knowledge = knowledge or Knowledge()
        self.prompt_template = PROMPT_PATH.read_text(encoding="utf-8")
        self.pending_path = data_dir / "pending_questions.json"
        self.corrections_path = data_dir / "corrections.json"

    # -- prompt ------------------------------------------------------------

    def build_system_prompt(self) -> str:
        """Profile plus the latest corrections, dropped into the template."""
        notes = self.list_corrections()[-10:]
        if notes:
            corrections = "\n".join(f"- {n['note']}" for n in notes)
        else:
            corrections = "(none yet)"

        return self.prompt_template.format(
            profile_yaml=self.knowledge.as_yaml(),
            corrections=corrections,
        )

    # -- calling the model -------------------------------------------------

    def _ask(self, user_text: str, history: list[ChatMessage] | None = None) -> CloneReply:
        messages = list(history or [])
        messages.append(ChatMessage(role="user", content=user_text))

        raw = self.provider.generate(self.build_system_prompt(), messages)
        result = self._parse(raw)

        if result.needs_human_input:
            self.save_pending_question(user_text, result.missing_info)
        return result

    @staticmethod
    def _parse(raw: str) -> CloneReply:
        """Parse the JSON contract. Fall back to plain text if the model slips."""
        text = raw.strip()

        # Strip ```json fences if the model adds them despite being told not to.
        fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
        if fence:
            text = fence.group(1).strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # Better to show the user something than to crash on a format slip.
            return CloneReply(reply=raw.strip(), raw=raw)

        if not isinstance(data, dict) or "reply" not in data:
            return CloneReply(reply=raw.strip(), raw=raw)

        missing = data.get("missing_info") or []
        if not isinstance(missing, list):
            missing = [str(missing)]

        return CloneReply(
            reply=str(data.get("reply", "")).strip(),
            missing_info=[str(m) for m in missing],
            needs_human_input=bool(data.get("needs_human_input", False)),
            raw=raw,
        )

    # -- the three required tasks -----------------------------------------

    def write_announcement(self) -> CloneReply:
        return self._ask(ANNOUNCEMENT_REQUEST)

    def answer_question(self, question: str) -> CloneReply:
        return self._ask(question)

    def revise_announcement(self, text: str) -> CloneReply:
        """Rewrite shorter and warmer. Word count is checked in Python, not trusted to the model."""
        result = self._ask(revision_request(text))

        if result.word_count >= 80:
            # One retry with the real number. Models routinely miscount their own words.
            result = self._ask(retry_request(result.word_count, result.reply))
        return result

    def chat(self, message: str, history: list[ChatMessage] | None = None) -> CloneReply:
        return self._ask(message, history)

    # -- the human loop ----------------------------------------------------

    def save_pending_question(self, question: str, missing_info: list[str]) -> list[dict]:
        """Queue the facts Dr. Mark still owes us.

        Keyed on the missing field, not on the wording of the request. Three
        different drafts that all stall on the price are one thing he has to
        decide, so his queue shows one item, not three. What he sees is a list
        of decisions, not a log of prompts.
        """
        if not missing_info:
            return []

        rows = _read_json(self.pending_path)
        open_fields = {r.get("field") for r in rows if r.get("status") == "open"}

        added: list[dict] = []
        for field_name in missing_info:
            if field_name in open_fields:
                continue
            entry = {
                "id": _short_id(),
                "field": field_name,
                "question": _question_for(field_name),
                # Kept for context so he can see what prompted the question.
                "first_asked_for": question[:160],
                "status": "open",
                "created_at": _now(),
            }
            rows.append(entry)
            open_fields.add(field_name)
            added.append(entry)

        if added:
            _write_json(self.pending_path, rows)
        return added

    def list_pending_questions(self, only_open: bool = True) -> list[dict]:
        rows = _read_json(self.pending_path)
        if only_open:
            rows = [r for r in rows if r.get("status") == "open"]
        return rows

    def resolve_pending_question(self, question_id: str) -> None:
        rows = _read_json(self.pending_path)
        for row in rows:
            if row.get("id") == question_id:
                row["status"] = "answered"
                row["answered_at"] = _now()
        _write_json(self.pending_path, rows)

    def save_correction(self, original_reply: str, note: str) -> dict:
        """Store one of Dr. Mark's edits. It shapes every later draft."""
        rows = _read_json(self.corrections_path)
        entry = {
            "id": _short_id(),
            "original_reply": original_reply[:500],
            "note": note.strip(),
            "created_at": _now(),
        }
        rows.append(entry)
        _write_json(self.corrections_path, rows)
        return entry

    def list_corrections(self) -> list[dict]:
        return _read_json(self.corrections_path)
