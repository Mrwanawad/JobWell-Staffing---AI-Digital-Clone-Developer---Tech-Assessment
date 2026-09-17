"""Minimal Streamlit UI. Built-in widgets only, no custom HTML or CSS.

    uv run streamlit run src/app.py

This is a proof of concept, not a product. The point is to show the three
tasks working and the human loop around them.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

import streamlit as st

from services.clone_service import (
    ANNOUNCEMENT_REQUEST,
    PRICE_AND_DATES_QUESTION,
    CloneReply,
    CloneService,
    revision_request,
)
from services.config import where_from
from services.llm import LLMError, create_provider

st.set_page_config(page_title="Dr. Mark clone", layout="centered")


@st.cache_resource
def get_clone() -> CloneService:
    return CloneService(create_provider())


st.title("Dr. Mark, text clone")
st.caption("Writes in his voice. Never invents a price, a date or a venue.")

try:
    clone = get_clone()
except LLMError as exc:
    st.error(str(exc))
    st.stop()


def run_and_show_question(
    question: str,
    work: Callable[[], CloneReply],
) -> CloneReply:
    """Type the outgoing question out while the model is actually working.

    The request runs on a worker thread so the typing is not a fake delay bolted
    on in front of a blocking call: the two genuinely overlap, and the typing
    stops when the model answers. Only the main thread touches Streamlit.
    """
    placeholder = st.empty()

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(work)

        shown = ""
        for word in question.split():
            shown = f"{shown} {word}".strip()
            placeholder.info(f"Sending to the clone: {shown}")
            time.sleep(0.02)

        # Question fully typed, model still thinking.
        while not future.done():
            placeholder.info(f"Sending to the clone: {question}")
            time.sleep(0.1)

        try:
            result = future.result()
        except LLMError as exc:
            # Usually the free tier rate limit. Show one line, not a traceback.
            placeholder.empty()
            st.error(str(exc))
            st.stop()

    placeholder.empty()
    st.session_state.last_question = question
    return result


# -- sidebar ---------------------------------------------------------------

with st.sidebar:
    st.subheader("Model")
    st.write(clone.provider.name)
    st.caption(f"Key source: {where_from('GEMINI_API_KEY')}")
    st.caption(
        ":red[Free tier allows about 10 requests per minute. "
        "Give each task a moment before running the next one.]"
    )

    st.subheader("Not decided yet")
    for field in clone.knowledge.unknown_fields():
        st.write(f"- {field}")

    st.subheader("Waiting for Dr. Mark")
    pending = clone.list_pending_questions()
    if pending:
        for row in pending:
            st.write(f"- {row['question']}")
            st.caption(f"asked while: {row['first_asked_for']}")
    else:
        st.caption("Nothing queued.")

    st.subheader("His corrections")
    corrections = clone.list_corrections()
    if corrections:
        for row in corrections[-10:]:
            st.write(f"- {row['note']}")
    else:
        st.caption("None saved yet.")

# -- the three tasks -------------------------------------------------------

col1, col2, col3 = st.columns(3)

draft = st.session_state.get("announcement")

run_task1 = col1.button(
    "1. Write announcement",
    use_container_width=True,
    help=ANNOUNCEMENT_REQUEST,
)
run_task2 = col2.button(
    "2. Ask price and dates",
    use_container_width=True,
    help=PRICE_AND_DATES_QUESTION,
)
run_task3 = col3.button(
    "3. Make it casual, under 80 words",
    use_container_width=True,
    help=revision_request(draft) if draft else "Run task 1 first, there is nothing to revise yet.",
)

if run_task1:
    result = run_and_show_question(ANNOUNCEMENT_REQUEST, clone.write_announcement)
    st.session_state.announcement = result.reply
    st.session_state.result = result

if run_task2:
    st.session_state.result = run_and_show_question(
        PRICE_AND_DATES_QUESTION,
        lambda: clone.answer_question(PRICE_AND_DATES_QUESTION),
    )

if run_task3:
    if not draft:
        st.warning("Run task 1 first, there is nothing to revise yet.")
    else:
        result = run_and_show_question(
            revision_request(draft),
            lambda: clone.revise_announcement(draft),
        )
        st.session_state.announcement = result.reply
        st.session_state.result = result

# -- result ----------------------------------------------------------------

result = st.session_state.get("result")

if result:
    question = st.session_state.get("last_question")
    if question:
        with st.expander("What was sent to the clone"):
            st.code(question, language=None)

    st.divider()
    st.write(result.reply)
    st.caption(f"{result.word_count} words")

    if result.needs_human_input:
        st.warning(
            "Dr. Mark has to answer this. Missing: "
            + (", ".join(result.missing_info) or "unspecified")
            + ". The question was added to his queue."
        )

    with st.form("correction", clear_on_submit=True):
        note = st.text_input(
            "Correction from Dr. Mark",
            placeholder="e.g. Do not use exclamation marks.",
        )
        if st.form_submit_button("Save correction") and note.strip():
            clone.save_correction(result.reply, note)
            st.success("Saved. It will shape every later draft.")
            st.rerun()

# -- free chat -------------------------------------------------------------

st.divider()
st.subheader("Ask anything else")

for role, text in st.session_state.get("history", []):
    with st.chat_message(role):
        st.write(text)

if message := st.chat_input("Ask the clone something"):
    history = st.session_state.get("history", [])
    history.append(("user", message))

    reply = run_and_show_question(message, lambda: clone.chat(message))

    history.append(("assistant", reply.reply))
    st.session_state.history = history
    st.session_state.result = reply
    st.rerun()
