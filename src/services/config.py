"""One place that answers "what is this setting?".

Two environments, one lookup order:

1. Streamlit secrets, which is what Streamlit Community Cloud provides. There
   is no .env file on the cloud, so this has to come first.
2. Environment variables, loaded from .env. This is how demo.py runs locally,
   where there is no Streamlit runtime at all.

Placeholder values from the committed example files are treated as missing, so
a half-filled template fails with a clear message instead of sending a fake key
to the API.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

# override=True so the .env file wins over a stale value already exported in
# the shell. Without it an old key in the environment silently shadows the file.
load_dotenv(override=True)

_PLACEHOLDER_MARKERS = ("your-", "paste-", "changeme", "xxx")


def _looks_like_placeholder(value: str) -> bool:
    return value.strip().lower().startswith(_PLACEHOLDER_MARKERS)


def _from_streamlit_secrets(name: str) -> str | None:
    """Read from st.secrets, or None if Streamlit is not running this process."""
    try:
        import streamlit as st
    except ModuleNotFoundError:
        return None

    try:
        value = st.secrets[name]
    except Exception:
        # No secrets file, no such key, or no Streamlit runtime. All mean
        # "not available here", so fall through to the environment.
        return None

    text = str(value).strip()
    return text or None


def get_setting(name: str, default: str = "") -> str:
    """Streamlit secrets first, then environment. Placeholders count as unset."""
    for candidate in (_from_streamlit_secrets(name), os.getenv(name)):
        if candidate:
            text = candidate.strip()
            if text and not _looks_like_placeholder(text):
                return text
    return default


def where_from(name: str) -> str:
    """Which source supplied this setting. Shown in the UI so deploys are debuggable."""
    if _from_streamlit_secrets(name):
        return "Streamlit secrets"
    if os.getenv(name):
        return ".env file"
    return "not set"
