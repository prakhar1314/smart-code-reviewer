"""Smart Code Reviewer — Streamlit UI.

Paste code, get a structured pre-review before sending to a human reviewer.
Built for the Careem Founding Forward Deployed Engineer (WorkOS) assignment.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import streamlit as st

from reviewer import review_code

st.set_page_config(page_title="Smart Code Reviewer", page_icon="🔍", layout="wide")

SAMPLES_DIR = Path(__file__).parent / "samples"


def load_samples() -> dict[str, str]:
    if not SAMPLES_DIR.exists():
        return {}
    return {p.name: p.read_text(encoding="utf-8") for p in sorted(SAMPLES_DIR.glob("*"))}


def score_badge(label: str, value: int) -> str:
    color = {1: "#c0392b", 2: "#e67e22", 3: "#f1c40f", 4: "#27ae60", 5: "#16a085"}.get(value, "#7f8c8d")
    return (
        f"<div style='display:inline-block;padding:8px 14px;margin-right:8px;"
        f"border-radius:8px;background:{color};color:white;font-weight:600'>"
        f"{label}: {value}/5</div>"
    )


def priority_emoji(p: str) -> str:
    return {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(p, "•")


st.title("🔍 Smart Code Reviewer")
st.caption(
    "Pre-review for human reviewers — readability, structure, maintainability. "
    "Returns a structured verdict in seconds so humans only spend attention where it counts."
)

with st.sidebar:
    st.header("⚙️ Settings")
    api_key = st.text_input(
        "Gemini API Key",
        type="password",
        value=os.environ.get("GEMINI_API_KEY", ""),
        help="Only used in this session. Not stored.",
    )
    if api_key:
        os.environ["GEMINI_API_KEY"] = api_key

    language_hint = st.selectbox(
        "Language hint (optional)",
        ["auto-detect", "python", "typescript", "javascript", "go", "java", "rust"],
    )

    st.divider()
    st.subheader("📂 Sample snippets")
    samples = load_samples()
    sample_choice = st.selectbox("Load a sample", ["(none)"] + list(samples.keys()))

    st.divider()
    st.markdown(
        "**Model:** `gemini-2.5-flash` <br>"
        "**Structured output:** schema-constrained JSON",
        unsafe_allow_html=True,
    )

col_input, col_output = st.columns([1, 1])

with col_input:
    st.subheader("Paste your code")
    default_code = samples.get(sample_choice, "") if sample_choice != "(none)" else ""
    code = st.text_area(
        "Code snippet",
        value=default_code,
        height=420,
        placeholder="Paste a function, class, or short file...",
    )
    review_btn = st.button("🔍 Review code", type="primary", use_container_width=True)

with col_output:
    st.subheader("Review")
    if review_btn:
        if not os.environ.get("GEMINI_API_KEY"):
            st.error("Add your Gemini API key in the sidebar to run a review.")
        elif not code.strip():
            st.warning("Paste some code first.")
        else:
            with st.spinner("Reviewing..."):
                lang = None if language_hint == "auto-detect" else language_hint
                result = review_code(code, language_hint=lang)

            if "error" in result:
                st.error(f"Reviewer error: {result['error']}")
                with st.expander("Raw output"):
                    st.code(result.get("raw", ""), language="text")
            else:
                st.markdown(f"**Summary** — {result.get('summary', '')}")

                scores = result.get("scores", {})
                badges = "".join(
                    score_badge(k.capitalize(), v) for k, v in scores.items()
                )
                st.markdown(badges, unsafe_allow_html=True)

                ready = result.get("ready_for_human_review", True)
                if ready:
                    st.success("✅ Ready for human review")
                else:
                    st.error("⛔ Not ready — see blockers")
                    for b in result.get("blockers", []):
                        st.markdown(f"- {b}")

                st.markdown("### 🛠 Improvements")
                for imp in result.get("improvements", []):
                    with st.expander(
                        f"{priority_emoji(imp.get('priority', 'low'))} "
                        f"[{imp.get('category', '?')}] {imp.get('issue', '')}"
                    ):
                        st.markdown(f"**Where:** `{imp.get('location', 'general')}`")
                        st.markdown(f"**Fix:** {imp.get('suggestion', '')}")
                        if imp.get("example"):
                            st.code(imp["example"])

                st.markdown("### ✨ What's good")
                st.info(result.get("positive", ""))

                with st.expander("📄 Raw JSON (for downstream tooling)"):
                    st.code(json.dumps(result, indent=2), language="json")

st.divider()
st.caption(
    "Built for Careem Founding Forward Deployed Engineer (WorkOS) assignment · "
    "Prompt + Streamlit + Gemini 2.5 Flash · Source: github.com/<your-handle>/smart-code-reviewer"
)
