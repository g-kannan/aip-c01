"""Resilience Simulator (Task 1.2, 2.1, 2.4): retries, jitter, circuit breaker, live fallback, agent guards."""

from __future__ import annotations

import time

import streamlit as st

from exam_labs.common import BEDROCK_ERRORS, converse_once, describe_error, error_code, get_settings
from exam_labs.resilience import (
    BACKOFF_MODES, LOOPING_AGENT, CircuitBreaker, call_with_retry, choose_tier, run_agent, run_with_breaker,
    simulate_herd,
)

OUTCOMES = ["ok", "429", "500", "503", "timeout", "400"]


def render_resilience_page() -> None:
    st.title("Resilience Simulator")
    st.caption("Task 1.2 / 2.1 / 2.4. Failure is normal: bound it, spread it, and fail over cleanly.")
    settings = get_settings()
    tabs = st.tabs(["Retry & backoff", "Thundering herd", "Circuit breaker", "Live fallback", "Routing", "Agent guards"])

    with tabs[0]:
        st.markdown("Replay a scripted failure sequence against a retry policy. Time is simulated, so nothing sleeps.")
        cols = st.columns(4)
        mode = cols[0].selectbox("Backoff", BACKOFF_MODES, index=3)
        attempts = cols[1].slider("Max attempts", 1, 8, 4)
        deadline = cols[2].slider("Deadline (s, 0 = none)", 0, 30, 5)
        base = cols[3].slider("Base delay (s)", 0.1, 2.0, 0.5, 0.1)
        script = st.multiselect("Outcome of each attempt (last one repeats)", OUTCOMES, default=["429", "429", "ok"])
        if script:
            result = call_with_retry(script, mode, attempts, deadline or None, base)
            (st.success if result.success else st.error)(
                f"{'Succeeded' if result.success else 'Failed'} after {result.attempts} attempt(s), {result.elapsed}s total.")
            st.dataframe(result.trace, hide_index=True, width="stretch")
        st.caption("Retry 429 and 5xx, never 400 or 403. Cap attempts *and* total time. The SDK's standard mode already "
                   "does exponential backoff with jitter, so do not stack your own retry loop on top without a budget.")

    with tabs[1]:
        st.markdown("Many clients hit a rate-limited service together. Without jitter they all retry at the same moment.")
        cols = st.columns(3)
        clients = cols[0].slider("Clients", 20, 200, 60, 10)
        capacity = cols[1].slider("Service capacity (requests/s)", 5, 50, 10)
        base = cols[2].slider("Base delay (s)", 1.0, 4.0, 2.0, 0.5, key="herd_base")
        pick = st.multiselect("Compare modes", BACKOFF_MODES, default=["exponential", "full jitter"])
        for mode in pick:
            sim = simulate_herd(clients, capacity, mode, base=base)
            st.markdown(f"**{mode}**: {sim['total_requests']} requests sent for {clients} clients, peak {sim['peak_load']}/s, "
                        f"{sim['succeeded']} succeeded, {sim['gave_up']} gave up")
            st.bar_chart(sim["load_by_second"], height=130)
        st.caption("Look for synchronized spikes with empty seconds between them: that is the herd. Jitter spreads the load.")

    with tabs[2]:
        st.markdown("After N consecutive failures the breaker **opens** and calls fail fast without touching the dependency. "
                    "After a cool-down one trial call is allowed (**half-open**).")
        cols = st.columns(3)
        threshold = cols[0].slider("Failures to open", 1, 6, 3)
        reset = cols[1].slider("Cool-down (s)", 5, 60, 15, 5)
        recovers_at = cols[2].slider("Dependency recovers at call #", 1, 14, 8)
        outcomes = ["500" if i < recovers_at - 1 else "ok" for i in range(14)]
        st.dataframe(run_with_breaker(outcomes, threshold, reset), hide_index=True, width="stretch")
        st.caption("Calls arrive every 5 seconds. Skipped calls cost no latency and no tokens, and protect the dependency while it recovers.")

    with tabs[3]:
        render_live_fallback(settings)
    with tabs[4]:
        render_routing()
    with tabs[5]:
        render_agent_guards()


def render_live_fallback(settings: dict | None) -> None:
    st.markdown("A real **fallback chain**: try each model ID in order and stop at the first that answers. "
                "The default primary is deliberately invalid, so the first attempt fails like an outage would.")
    if not settings:
        st.info("Configure .env to call Bedrock.")
        return
    chain_text = st.text_area("Model IDs, one per line", value="nonexistent.model-v1:0\n" + settings["BEDROCK_MODEL_ID"], height=90)
    prompt = st.text_input("Prompt", value="Reply with the single word: ready")
    breaker_on = st.checkbox("Use a circuit breaker per model (opens after 2 failures, 60s cool-down)", value=True)
    breakers = st.session_state.setdefault("fallback_breakers", {})
    if st.button("Run chain", type="primary"):
        rows = []
        for model in [m.strip() for m in chain_text.splitlines() if m.strip()]:
            breaker = breakers.setdefault(model, CircuitBreaker(2, 60.0))
            if breaker_on and not breaker.allow(time.monotonic()):
                rows.append({"model": model, "result": "skipped: circuit open", "ms": 0})
                continue
            started = time.perf_counter()
            try:
                result = converse_once(settings, prompt, model_id=model, max_tokens=20, max_attempts=1)
                breaker.record(True, time.monotonic())
                rows.append({"model": model, "result": "OK: " + result["text"].strip()[:40],
                             "ms": int((time.perf_counter() - started) * 1000)})
                break
            except BEDROCK_ERRORS as error:
                breaker.record(False, time.monotonic())
                rows.append({"model": model, "result": f"{error_code(error)}", "ms": int((time.perf_counter() - started) * 1000),
                             "detail": describe_error(error)[:140]})
        st.dataframe(rows, hide_index=True, width="stretch")
        st.caption("Run it again: after two failures the breaker skips the dead model instantly. "
                   "Cross-Region inference profiles add a second layer: Bedrock itself spreads load across Regions.")
    if st.button("Reset breakers"):
        breakers.clear()


def render_routing() -> None:
    st.markdown("Route each request to the cheapest model that can handle it.")
    mode = st.radio("Routing rule", ["static", "content", "performance"], horizontal=True)
    if mode == "static":
        task = st.selectbox("Task type", ["classification", "extraction", "analysis", "code"])
        st.success(f"Route to the **{choose_tier('', mode, task=task)}** model. A fixed table: predictable, zero overhead.")
    elif mode == "content":
        prompt = st.text_area("Prompt", value="Compare the two designs step by step and explain why one scales better.", height=90)
        st.success(f"Route to the **{choose_tier(prompt, mode)}** model. Decided from the prompt itself (length and keywords here; "
                   "a small classifier model in real systems).")
    else:
        cols = st.columns(2)
        stats = {"model-a (primary)": cols[0].number_input("p95 latency A (ms)", 100, 10000, 2400, 100),
                 "model-b (secondary)": cols[1].number_input("p95 latency B (ms)", 100, 10000, 900, 100)}
        st.success(f"Route to **{choose_tier('', mode, stats)}**. Decided from live latency signals, so traffic shifts when a model slows down.")


def render_agent_guards() -> None:
    st.markdown("An agent that loops forever is a cost and safety incident. Every loop needs **stopping conditions**.")
    cols = st.columns(4)
    max_steps = cols[0].slider("Max steps", 1, 12, 8)
    time_budget = cols[1].slider("Time budget (s)", 5, 40, 30)
    token_budget = cols[2].slider("Token budget", 500, 6000, 5000, 250)
    repeat = cols[3].checkbox("Stop on repeated action", value=True)
    result = run_agent(LOOPING_AGENT, max_steps, float(time_budget), token_budget, repeat)
    (st.success if result["stopped"] == "finished normally" else st.warning)(
        f"Stopped: {result['stopped']} after {result['steps']} step(s), {result['seconds']:g}s, {result['tokens']} tokens.")
    st.dataframe(result["trace"], hide_index=True, width="stretch")
    st.caption("This scripted agent keeps calling search_docs. Turn each guard off in turn and see which one saves you.")
