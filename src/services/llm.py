"""LLM providers behind one small interface.

Only Gemini is wired up and tested. The base class and the factory exist so a
second provider is a new file, not a rewrite. That swap is the point: the
client is never locked to one vendor.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass

from services.config import get_setting


MAX_ATTEMPTS = 3


class LLMError(RuntimeError):
    """Any failure talking to a model provider."""


def _is_transient(detail: str) -> bool:
    """A brief overload on the provider's side, worth one more try."""
    return "503" in detail or "UNAVAILABLE" in detail


def _as_llm_error(detail: str) -> LLMError:
    """Turn a raw SDK error into one line a person can act on."""
    if "429" in detail or "RESOURCE_EXHAUSTED" in detail:
        if "PerDay" in detail:
            return LLMError(
                "Daily free tier quota is used up for this model. Preview "
                "models are capped hardest, so set GEMINI_MODEL_ID to a stable "
                "model such as gemini-3.8-flash."
            )
        return LLMError("Rate limit reached. Wait a moment and try again.")

    if _is_transient(detail):
        return LLMError(
            "The model is busy right now. This is temporary, try again shortly."
        )

    if "API key not valid" in detail or "API_KEY_INVALID" in detail:
        return LLMError(
            "The API key was rejected. Check GEMINI_API_KEY in your .env file, "
            "or in the Secrets box if this is deployed."
        )

    return LLMError(f"Gemini request failed: {detail}")


@dataclass
class ChatMessage:
    """One turn of a conversation."""

    role: str  # "user" or "assistant"
    content: str


class BaseLLMProvider(ABC):
    """What every provider must offer. One method, on purpose."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human readable provider and model, shown in the UI."""

    @abstractmethod
    def generate(self, system_prompt: str, messages: list[ChatMessage]) -> str:
        """Send the conversation and return the raw text reply."""


class GeminiProvider(BaseLLMProvider):
    """Google Gemini, via the google-genai SDK."""

    def __init__(self, api_key: str, model_id: str) -> None:
        if not api_key:
            raise LLMError(
                "GEMINI_API_KEY is not set. Locally, put it in .env. "
                "On Streamlit Community Cloud, put it in the app's Secrets box."
            )
        if not model_id:
            raise LLMError(
                "GEMINI_MODEL_ID is not set. Locally, put it in .env. "
                "On Streamlit Community Cloud, put it in the app's Secrets box."
            )

        from google import genai

        self._model_id = model_id
        self._client = genai.Client(api_key=api_key)

    @property
    def name(self) -> str:
        return f"Google Gemini ({self._model_id})"

    def generate(self, system_prompt: str, messages: list[ChatMessage]) -> str:
        from google.genai import types

        contents = [
            types.Content(
                # Gemini calls the assistant "model".
                role="model" if m.role == "assistant" else "user",
                parts=[types.Part(text=m.content)],
            )
            for m in messages
        ]

        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
            temperature=0.7,
            # We never pass tools, so turn this off to keep the SDK from
            # printing an advisory warning on every call.
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                disable=True
            ),
        )

        # A 503 means the model is briefly overloaded, which is worth retrying.
        # A 429 or a bad key is not: retrying those only wastes quota.
        for attempt in range(MAX_ATTEMPTS):
            try:
                response = self._client.models.generate_content(
                    model=self._model_id,
                    contents=contents,
                    config=config,
                )
            except Exception as exc:
                detail = str(exc)
                is_last = attempt == MAX_ATTEMPTS - 1

                if _is_transient(detail) and not is_last:
                    time.sleep(2 * (attempt + 1))
                    continue

                raise _as_llm_error(detail) from exc

            text = (response.text or "").strip()
            if not text:
                raise LLMError("Gemini returned an empty response.")
            return text

        raise LLMError("Gemini could not be reached after several attempts.")


def create_provider() -> BaseLLMProvider:
    """Build the provider named by LLM_BACKEND. Defaults to Gemini."""
    backend = get_setting("LLM_BACKEND", "gemini").lower()

    if backend in ("gemini", "google"):
        return GeminiProvider(
            api_key=get_setting("GEMINI_API_KEY"),
            model_id=get_setting("GEMINI_MODEL_ID"),
        )

    raise LLMError(
        f"Unknown LLM_BACKEND '{backend}'. Supported values: gemini."
    )
