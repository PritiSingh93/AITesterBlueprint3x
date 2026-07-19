"""QABuddyAI — Streamlit chat UI. Calls the backend /ask endpoint and shows
the answer with expandable, cited sources.

Run locally:  streamlit run frontend/app.py
"""
from __future__ import annotations

import os

import httpx
import streamlit as st

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")

SOURCE_TYPES = [
    "selenium_code", "playwright_code", "test_case", "jira", "doc",
    "design", "meeting", "diagram", "prd", "jenkins",
]
BADGES = {
    "selenium_code": "🧩", "playwright_code": "🎭", "test_case": "✅",
    "jira": "🐞", "doc": "📄", "design": "🎨", "meeting": "🗒️",
    "diagram": "🔀", "prd": "📘", "jenkins": "⚙️",
}

st.set_page_config(page_title="QABuddyAI", page_icon="🤝", layout="wide")
st.title("🤝 QABuddyAI")
st.caption("Ask one question — get a cited answer grounded in our frameworks, "
           "test cases, JIRA history, PRDs, and Jenkins results.")

with st.sidebar:
    st.header("Filters")
    picked_types = st.multiselect("Source types", SOURCE_TYPES, default=[])
    module = st.text_input("Module / component")
    top_k = st.slider("Context chunks", min_value=3, max_value=15, value=8)
    st.divider()
    if st.button("Clear chat"):
        st.session_state.messages = []
        st.rerun()
    try:
        health = httpx.get(f"{BACKEND_URL}/health", timeout=10).json()
        st.success("Backend healthy") if health.get("healthy") else st.warning(
            "Backend degraded: "
            + ", ".join(f"{k}: {v}" for k, v in health["services"].items()
                        if not str(v).startswith("ok"))
        )
    except Exception:
        st.error(f"Backend unreachable at {BACKEND_URL}")

if "messages" not in st.session_state:
    st.session_state.messages = []


def render_sources(sources: list) -> None:
    if not sources:
        return
    with st.expander(f"📎 Sources ({len(sources)})"):
        for s in sources:
            badge = BADGES.get(s["source_type"], "📁")
            st.markdown(
                f"**[{s['n']}] {badge} {s['source']}** "
                f"`{s['source_type']}` · score {s['score']}"
                + (f" · module: {s['module']}" if s.get("module") else "")
            )
            st.code(s["text"][:1500] + ("…" if len(s["text"]) > 1500 else ""))


for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant":
            render_sources(msg.get("sources", []))

if question := st.chat_input("e.g. Which test cases cover checkout?"):
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    filters = {}
    if picked_types:
        filters["source_type"] = picked_types
    if module.strip():
        filters["module"] = module.strip()

    with st.chat_message("assistant"):
        with st.spinner("Searching the QA knowledge base…"):
            try:
                resp = httpx.post(
                    f"{BACKEND_URL}/ask",
                    json={"question": question,
                          "filters": filters or None,
                          "top_k": top_k},
                    timeout=120,
                )
                resp.raise_for_status()
                data = resp.json()
            except httpx.HTTPStatusError as exc:
                data = {"answer": f"Backend error: {exc.response.text}",
                        "sources": []}
            except Exception as exc:
                data = {"answer": f"Request failed: {exc}", "sources": []}
        st.markdown(data["answer"])
        render_sources(data.get("sources", []))

    st.session_state.messages.append(
        {"role": "assistant", "content": data["answer"],
         "sources": data.get("sources", [])}
    )
