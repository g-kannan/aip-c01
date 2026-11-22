"""AIP-C01 exam demos: one page per concept. Run with `uv run -m streamlit run exam_app.py`.

This is separate from app.py (the Converse, Gateway and Knowledge Base labs) so the exam demos can be
opened, shared and deleted on their own. The slide decks live in slides/ and open in a browser.
"""

from pathlib import Path

import streamlit as st

from exam_labs.chunking_page import render_chunking_page
from exam_labs.cleaning_page import render_cleaning_page
from exam_labs.evaluation_page import render_evaluation_page
from exam_labs.guardrails_page import render_guardrails_page
from exam_labs.prompts_page import render_prompts_page
from exam_labs.resilience_page import render_resilience_page

DEMOS = [
    ("Guardrails Lab", "3.1, 3.2", "Layered safety: input rules, validator, ApplyGuardrail, Detect vs Enforce", "Slides 06, 07"),
    ("Prompt Lab", "1.6", "Versions, approval, rollback, regression tests, Bedrock Prompt management", "Slide 12"),
    ("Chunking Playground", "1.5, 5.2", "How chunk size decides what the model can know; context overflow", "Slide 08"),
    ("Input Cleaner", "1.3", "Normalize, extract, quality gate, per-model request formats", "Slide 08"),
    ("Resilience Simulator", "1.2, 2.1, 2.4", "Backoff and jitter, circuit breaker, live fallback, routing, agent guards", "Slide 09"),
    ("Eval Harness", "5.1, 4.3", "Golden dataset, A/B, judge score, release gate", "Slides 10, 11"),
]


def render_home() -> None:
    st.title("AIP-C01 Exam Demos")
    st.caption("One interactive page per concept. Pair each with the matching slide deck in slides/.")
    st.dataframe(
        [{"Demo": d, "Exam tasks": t, "What you see": w, "Read first": s} for d, t, w, s in DEMOS],
        hide_index=True, width="stretch",
    )
    st.markdown(
        "**Setup:** the same `.env` as the main app (`AWS_PROFILE`, `AWS_REGION`, `BEDROCK_MODEL_ID`). "
        "Pages that call Bedrock say so and show the permission they need. Every call is billed to your account; "
        "`Create` buttons make real AWS resources, so delete them afterwards.\n\n"
        "**Slides:** open `slides/index.html` in a browser. Arrow keys move between slides."
    )
    st.markdown("Coverage and gaps by exam task are tracked in `docs/exam-domains.md`.")


def main() -> None:
    st.set_page_config(page_title="AIP-C01 Exam Demos", layout="wide")
    styles = Path(__file__).with_name("styles.css").read_text(encoding="utf-8")
    st.html(f"<style>{styles}</style>")
    page = st.navigation([
        st.Page(render_home, title="Overview", default=True),
        st.Page(render_guardrails_page, title="Guardrails Lab", url_path="guardrails"),
        st.Page(render_prompts_page, title="Prompt Lab", url_path="prompts"),
        st.Page(render_chunking_page, title="Chunking Playground", url_path="chunking"),
        st.Page(render_cleaning_page, title="Input Cleaner", url_path="cleaning"),
        st.Page(render_resilience_page, title="Resilience Simulator", url_path="resilience"),
        st.Page(render_evaluation_page, title="Eval Harness", url_path="evaluation"),
    ])
    page.run()


if __name__ == "__main__":
    main()
