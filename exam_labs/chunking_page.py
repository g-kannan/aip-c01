"""Chunking Playground (Task 1.5, 5.2): see how chunk size decides what the model is allowed to know."""

from __future__ import annotations

import streamlit as st

from exam_labs.chunking import (
    SAMPLE_DOCUMENT, approx_tokens, contains_all, fit_to_window, fixed_chunks, hierarchical_chunks, rank,
    sentence_chunks,
)
from exam_labs.common import BEDROCK_ERRORS, converse_once, describe_error, get_settings

STRATEGIES = ["Fixed size", "Sentence-aware", "Hierarchical (parent / child)"]
QUESTION = "How do I clear alarm E42 low pressure?"
EXCEPTION_MARKERS = ("firmware", "engineer")


def render_chunking_page() -> None:
    st.title("Chunking Playground")
    st.caption("Task 1.5 / 5.2. Retrieval can only return what chunking kept together. Sizes are in words.")
    settings = get_settings()
    controls, view = st.columns([1, 2], gap="large")
    with controls:
        strategy = st.radio("Strategy", STRATEGIES, key="chunk_strategy")
        if strategy == "Hierarchical (parent / child)":
            parent_size = st.slider("Parent size (words)", 60, 200, 120, 10)
            size = st.slider("Child size (words)", 10, 60, 30, 5)
        else:
            parent_size = 0
            size = st.slider("Chunk size (words)", 10, 120, 40, 5)
        overlap = 0 if strategy == "Sentence-aware" else st.slider("Overlap (%)", 0, 50, 0, 5)
        top_k = st.slider("Chunks retrieved (k)", 1, 5, 1)
        query = st.text_input("Question", value=QUESTION)
        document = st.text_area("Document", value=SAMPLE_DOCUMENT, height=220)
        st.caption("The sample manual has a safety exception right after the normal procedure.")

    try:
        parents = None
        if strategy == "Fixed size":
            searchable = fixed_chunks(document, size, overlap)
        elif strategy == "Sentence-aware":
            searchable = sentence_chunks(document, size)
        else:
            parents, searchable = hierarchical_chunks(document, parent_size, size, overlap)
    except ValueError as error:
        st.error(str(error))
        return

    hits = rank(query, searchable, top_k)
    context_chunks = [(parents[c.parent].text if parents else c.text) for c, _ in hits]
    # Several children can share one parent: send each parent once.
    context_chunks = list(dict.fromkeys(context_chunks))
    context = "\n\n".join(context_chunks)
    has_exception = contains_all(context, EXCEPTION_MARKERS)

    with view:
        st.subheader(f"{len(searchable)} searchable chunks")
        st.caption("Highlighted rows were retrieved. The score is a keyword stand-in for vector similarity.")
        retrieved = {c.index: score for c, score in hits}
        st.dataframe(
            [{"#": c.index, "retrieved": "yes" if c.index in retrieved else "", "score": retrieved.get(c.index, ""),
              "words": len(c.text.split()), "contains exception": "yes" if contains_all(c.text, EXCEPTION_MARKERS) else "",
              "text": c.text[:110] + ("..." if len(c.text) > 110 else "")} for c in searchable],
            hide_index=True, width="stretch", height=240)
        if has_exception:
            st.success("The context sent to the model includes the safety exception.")
        else:
            st.error("The context sent to the model is missing the safety exception. A correct-looking answer "
                     "can still be dangerous. Try a larger chunk, more overlap, a higher k, or hierarchical.")
        if parents:
            st.caption("Hierarchical: the child chunk is matched, then its larger parent is sent to the model.")

        st.subheader("Context window")
        budget = st.slider("Token budget for retrieved context", 20, 600, 150, 10,
                           help="Simulates a small remaining window. Real overflow raises a ValidationException or truncates.")
        kept, dropped = fit_to_window(context_chunks, budget)
        st.caption(f"Context needs about {approx_tokens(context)} tokens; budget {budget}. "
                   f"Kept {len(kept)} chunk(s), dropped {len(dropped)}.")
        if dropped:
            st.warning("Overflow: the last retrieved chunk(s) do not fit and would be dropped or cut off. "
                       "Reduce k, shrink chunks, or compress the context.")

        st.subheader("Ask the model")
        if st.button("Ask Bedrock with this context", type="primary", disabled=not settings):
            prompt = ("Answer using only the context. If the context has a warning or exception, include it.\n\n"
                      f"<context>\n{chr(10).join(kept)}\n</context>\n\nQuestion: {query}")
            try:
                with st.spinner("Calling Bedrock..."):
                    result = converse_once(settings, prompt, max_tokens=300)
                st.markdown(result["text"])
                mentions = contains_all(result["text"], ("firmware",))
                st.caption(f"{result['usage']['inputTokens']} input tokens, {result['latency_ms']} ms. "
                           + ("The answer mentions the firmware exception." if mentions
                              else "The answer does not mention the firmware exception."))
            except BEDROCK_ERRORS as error:
                st.error(f"Bedrock request failed: {describe_error(error)}")
        if not settings:
            st.caption("Configure .env to ask the model.")
