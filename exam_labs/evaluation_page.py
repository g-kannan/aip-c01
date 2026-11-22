"""Eval Harness (Task 5.1, 4.3): golden dataset, A/B comparison, optional judge, and a release gate."""

from __future__ import annotations

import streamlit as st

from exam_labs.common import BEDROCK_ERRORS, converse_once, get_settings
from exam_labs.evaluation import (
    BASELINE, GOLDEN_CASES, IMPROVED, Candidate, GoldenCase, cases_from_json, cases_to_json, compare, evaluate,
    judge_prompt, parse_judge, release_gate,
)

RUNS = "eval_runs"


def make_runner(settings: dict):
    def runner(candidate: Candidate, case: GoldenCase) -> dict:
        result = converse_once(settings, case.prompt, system=candidate.system, model_id=candidate.model_id or None,
                               temperature=candidate.temperature, max_tokens=candidate.max_tokens)
        return {"text": result["text"], "latency_ms": result["latency_ms"],
                "input_tokens": result["usage"]["inputTokens"], "output_tokens": result["usage"]["outputTokens"]}
    return runner


def add_judge_scores(settings: dict, run, cases: list[GoldenCase]) -> None:
    by_name = {c.name: c for c in cases}
    for result in run.results:
        if result.error:
            continue
        try:
            reply = converse_once(settings, judge_prompt(by_name[result.case].prompt, result.output), max_tokens=120)
            parsed = parse_judge(reply["text"])
            result.judge_score = parsed[0] if parsed else None
        except BEDROCK_ERRORS:
            result.judge_score = None


def render_evaluation_page() -> None:
    st.title("Eval Harness")
    st.caption("Task 5.1 / 4.3. Compare two prompt or model configurations on a fixed golden dataset, then gate the release.")
    settings = get_settings()
    if not settings:
        st.warning("Fill in .env: this lab calls Bedrock for every case and candidate.")
        return

    with st.expander("Golden dataset (editable JSON)"):
        text = st.text_area("Cases", value=cases_to_json(GOLDEN_CASES), height=320, label_visibility="collapsed")
        st.caption("Fields: name, prompt, must_contain, must_not_contain, max_words, tag (quality, format, safety, grounding). "
                   "Keep the dataset fixed between runs: a moving dataset hides regressions.")
    try:
        cases = cases_from_json(text)
    except ValueError as error:
        st.error(str(error))
        return

    cols = st.columns(2)
    candidates = []
    for column, default, key in ((cols[0], BASELINE, "a"), (cols[1], IMPROVED, "b")):
        with column:
            st.markdown(f"**{default.name}**")
            system = st.text_area("System prompt", value=default.system, height=120, key=f"sys_{key}")
            model = st.text_input("Model ID (blank = .env default)", key=f"model_{key}")
            candidates.append(Candidate(default.name, system, model.strip(), 0.0, 200))
    price = st.columns(3)
    price_in = price[0].number_input("Input price per 1M tokens (USD)", 0.0, 100.0, 0.10, 0.05,
                                     help="Example value. Check your model's current price.")
    price_out = price[1].number_input("Output price per 1M tokens (USD)", 0.0, 100.0, 0.40, 0.05)
    use_judge = price[2].checkbox("Add an LLM-judge score (extra call per case)")
    st.caption(f"This makes {len(cases) * 2}{' + ' + str(len(cases) * 2) if use_judge else ''} Bedrock calls at temperature 0.")

    if st.button("Run evaluation", type="primary"):
        runner, runs = make_runner(settings), []
        progress = st.progress(0.0, "Starting...")
        for index, candidate in enumerate(candidates):
            progress.progress(index / 2, f"Running {candidate.name}...")
            run = evaluate(candidate, cases, runner)
            if use_judge:
                add_judge_scores(settings, run, cases)
            runs.append(run)
        progress.empty()
        st.session_state[RUNS] = {"runs": runs, "cases": cases}

    saved = st.session_state.get(RUNS)
    if not saved:
        return
    base_run, cand_run = saved["runs"]
    base_m, cand_m = base_run.metrics(price_in, price_out), cand_run.metrics(price_in, price_out)

    st.subheader("Scorecard")
    st.dataframe([
        {"metric": label, "A: baseline": base_m[key], "B: candidate": cand_m[key]}
        for label, key in [("Passed", "passed"), ("Pass rate", "pass_rate"), ("Errors", "errors"), ("p50 latency (ms)", "p50_ms"),
                           ("p95 latency (ms)", "p95_ms"), ("Input tokens", "input_tokens"), ("Output tokens", "output_tokens"),
                           ("Cost (USD)", "cost"), ("Avg judge score (1-4)", "avg_judge")]
    ], hide_index=True, width="stretch")

    st.subheader("Per-case changes")
    st.dataframe(compare(base_run, cand_run), hide_index=True, width="stretch")
    with st.expander("Outputs and failures"):
        for a, b in zip(base_run.results, cand_run.results):
            st.markdown(f"**{a.case}** ({a.tag})")
            left, right = st.columns(2)
            left.code(a.output or a.error, language="text", wrap_lines=True)
            left.caption("; ".join(a.failures) or "pass")
            right.code(b.output or b.error, language="text", wrap_lines=True)
            right.caption("; ".join(b.failures) or "pass")

    st.subheader("Release gate")
    gate = st.columns(4)
    min_rate = gate[0].slider("Min pass rate", 0.0, 1.0, 0.8, 0.05)
    max_drop = gate[1].slider("Max drop vs baseline", 0.0, 0.5, 0.0, 0.05)
    max_p95 = gate[2].number_input("Max p95 (ms)", 500, 60000, 5000, 500)
    max_cost = gate[3].number_input("Max cost rise (%)", 0, 500, 50, 10)
    safety_failed = sum(1 for r in cand_run.results if r.tag == "safety" and not r.passed)
    reasons = release_gate(base_m, cand_m, min_rate, max_drop, int(max_p95), float(max_cost), safety_failed)
    if reasons:
        st.error("BLOCKED. Do not promote candidate B.")
        for reason in reasons:
            st.markdown(f"- {reason}")
    else:
        st.success("PASSED every gate. Candidate B can be promoted (for a canary first, then everyone).")
    st.caption("In a pipeline this decision runs in CI/CD (Step Functions or CodePipeline) and publishes a CloudWatch metric, "
               "so a failed gate stops the deployment automatically.")
