"""LLM providers behind one small interface.

Only Gemini is wired up and tested. The base class and the factory exist so a
second provider is a new file, not a rewrite. That swap is the point: the
client is never locked to one vendor.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from services.config import get_setting


class LLMError(RuntimeError):
    """Any failure talking to a model provider."""


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

        try:
            response = self._client.models.generate_content(
                model=self._model_id,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    response_mime_type="application/json",
                    temperature=0.7,
                    # We never pass tools, so turn this off to keep the SDK
                    # from printing an advisory warning on every call.
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(
                        disable=True
                    ),
                ),
            )
        except Exception as exc:  # SDK raises several types, all mean the same here
            detail = str(exc)
            if "429" in detail or "RESOURCE_EXHAUSTED" in detail:
                # The free tier allows roughly 10 requests per minute. Running
                # the three tasks back to back can trip it, so say what happened
                # in one line instead of printing the raw API payload.
                raise LLMError(
                    "Rate limit reached. The free tier allows about 10 requests "
                    "per minute. Wait a moment and try again."
                ) from exc
            raise LLMError(f"Gemini request failed: {detail}") from exc

        text = (response.text or "").strip()
        if not text:
            raise LLMError("Gemini returned an empty response.")
        return text


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
