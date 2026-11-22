"""Input Cleaner (Task 1.3): normalize, extract, validate, and format requests per model family."""

from __future__ import annotations

import json

import streamlit as st

from exam_labs.cleaning import (
    EXTRACTION_PROMPT, FAMILIES, SAMPLE_NOTE, clean, extract_entities, format_request, parse_model_json,
    quality_report,
)
from exam_labs.common import BEDROCK_ERRORS, converse_once, describe_error, get_settings

GOOD = {"id": 1, "alarm_id": "E42", "firmware": "2.0.4", "visit_date": "2025-03-12", "note": "Pressure low."}
BAD_RECORDS = [
    GOOD,
    {"id": 2, "alarm_id": "e42", "firmware": "2.1", "visit_date": "12/03/2025", "note": "Reset done."},
    {"id": 3, "alarm_id": "E17", "firmware": "", "visit_date": "2025-03-14", "note": "No flame."},
    {"id": 4, "alarm_id": "E09", "firmware": "2.1", "visit_date": "2025-02-30", "note": "Frozen pipe."},
    {"id": 5, "alarm_id": "E42", "firmware": 2.1, "visit_date": "2025-03-15", "note": "Pressure low."},
]


def render_cleaning_page() -> None:
    st.title("Input Cleaner")
    st.caption("Task 1.3. Garbage in, garbage out: fix the input before spending tokens on it.")
    settings = get_settings()
    clean_tab, gate_tab, format_tab = st.tabs(["Normalize & extract", "Quality gate", "Request formats"])

    with clean_tab:
        raw = st.text_area("Noisy engineer note", value=SAMPLE_NOTE, height=190)
        cols = st.columns(2)
        day_first = cols[0].radio("Numeric dates are", ["day/month/year", "month/day/year"], horizontal=True) == "day/month/year"
        expand = cols[1].checkbox("Expand abbreviations (blr, fw, ck ...)", value=True)
        cleaned = clean(raw, day_first, expand)
        left, right = st.columns(2)
        left.markdown("**Cleaned text**")
        left.code(cleaned, language="text", wrap_lines=True)
        right.markdown("**Regex entities** (free, exact for fixed formats)")
        right.json(extract_entities(cleaned))
        st.caption(f"{len(raw)} characters in, {len(cleaned)} out. Fewer tokens, consistent dates, no signature or footer noise.")
        st.divider()
        st.markdown("**Entity extraction with a model** handles prose that regex cannot (`follow-up booked for the 20th`).")
        if st.button("Extract with Bedrock", type="primary", disabled=not settings):
            try:
                with st.spinner("Calling Bedrock..."):
                    result = converse_once(settings, EXTRACTION_PROMPT.format(note=cleaned), max_tokens=200)
                parsed = parse_model_json(result["text"])
                if parsed is None:
                    st.error("The model did not return a JSON object. Validate model output before using it.")
                    st.code(result["text"], language="text")
                else:
                    st.json(parsed)
                    st.caption(f"{result['usage']['totalTokens']} tokens, {result['latency_ms']} ms. "
                               "Compare with the regex result: do the dates agree?")
            except BEDROCK_ERRORS as error:
                st.error(f"Bedrock request failed: {describe_error(error)}")

    with gate_tab:
        st.markdown("A **data-quality gate** rejects bad records *before* they are embedded or sent to a model. "
                    "Edit the records below; the schema needs `id`, `alarm_id` (E## or F##), `firmware`, ISO `visit_date`, `note`.")
        text = st.text_area("Records (JSON list)", value=json.dumps(BAD_RECORDS, indent=2), height=260)
        try:
            records = json.loads(text)
            if not isinstance(records, list) or not all(isinstance(r, dict) for r in records):
                raise ValueError("Enter a JSON list of objects.")
        except ValueError as error:
            records = None
            st.error(f"Invalid JSON: {error}")
        if records:
            report = quality_report(records)
            metrics = st.columns(3)
            metrics[0].metric("Records", report["records"])
            metrics[1].metric("Invalid", report["invalid"])
            metrics[2].metric("Valid rate", f"{report['valid_rate']:.0%}")
            threshold = st.slider("Minimum valid rate to proceed", 0.5, 1.0, 0.9, 0.05)
            if report["valid_rate"] >= threshold:
                st.success("Gate passed.")
            else:
                st.error("Gate failed: quarantine the invalid records and fix the source before ingestion.")
            for key, problems in report["problems"].items():
                st.markdown(f"**record {key}:** " + "; ".join(problems))
            st.caption(f"Duplicate notes: {report['duplicate_notes']}.")

    with format_tab:
        st.markdown("Every provider has its own **InvokeModel body**. `Converse` hides the differences, which is why "
                    "switching models behind it needs no code change.")
        question = st.text_input("Prompt", value="Summarize alarm E42 in one sentence.")
        system = st.text_input("System prompt", value="You are a concise support assistant.")
        family = st.selectbox("Format", list(FAMILIES), format_func=FAMILIES.get)
        st.code(json.dumps(format_request(family, question, system), indent=2), language="json")
        if family != "converse":
            st.caption("Send this with `invoke_model(modelId=..., body=json.dumps(body))`. A body for the wrong family "
                       "is rejected with a ValidationException.")
        if st.button("Send with Converse", disabled=not settings):
            try:
                result = converse_once(settings, question, system=system, max_tokens=120)
                st.markdown(result["text"])
                st.caption(f"{result['usage']['totalTokens']} tokens, {result['latency_ms']} ms")
            except BEDROCK_ERRORS as error:
                st.error(f"Bedrock request failed: {describe_error(error)}")
