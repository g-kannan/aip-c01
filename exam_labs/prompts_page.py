"""Prompt Lab (Task 1.6): version, approve, promote, roll back and regression-test a prompt."""

from __future__ import annotations

import streamlit as st

from exam_labs.common import BEDROCK_ERRORS, converse_once, describe_error, get_settings, make_session
from exam_labs.prompts import (
    DEFAULT_CASES, DEFAULT_TEMPLATE, IMPROVED_TEMPLATE, PromptRecord, RegressionCase, check_output,
    diff, extract_variables, lint, render,
)

STATE = "prompt_lab_record"


def record() -> PromptRecord:
    if STATE not in st.session_state:
        st.session_state[STATE] = PromptRecord(draft=DEFAULT_TEMPLATE)
    st.session_state.setdefault("draft_text", st.session_state[STATE].draft)
    return st.session_state[STATE]


def load_improved() -> None:
    st.session_state["draft_text"] = IMPROVED_TEMPLATE


def reset_lab() -> None:
    st.session_state.pop(STATE, None)
    st.session_state["draft_text"] = DEFAULT_TEMPLATE


def render_prompts_page() -> None:
    st.title("Prompt Lab")
    st.caption("Task 1.6. A prompt is code: edit a draft, freeze versions, approve, promote, roll back, regression-test.")
    settings = get_settings()
    if not settings:
        st.warning("Fill in .env to run regression tests against Bedrock. Versioning works without it.")
    rec = record()
    edit_tab, regress_tab, audit_tab, bedrock_tab = st.tabs(
        ["Draft & versions", "Regression test", "Audit log", "Bedrock Prompt management"])

    with edit_tab:
        left, right = st.columns([1.2, 1], gap="large")
        with left:
            rec.draft = st.text_area("Draft template", height=240, key="draft_text", help="Variables use {{name}}.")
            st.caption("Variables: " + (", ".join(extract_variables(rec.draft)) or "none"))
            for note in lint(rec.draft):
                st.warning(note)
            cols = st.columns(2)
            actor = cols[0].text_input("Your name", value="dev", key="actor")
            note = cols[1].text_input("Version note", key="note", placeholder="what changed?")
            buttons = st.columns(3)
            if buttons[0].button("Snapshot as version", type="primary"):
                try:
                    version = rec.snapshot(actor, note)
                    st.success(f"Created v{version.number} (sha256 {version.digest}). It is now immutable.")
                except ValueError as error:
                    st.error(str(error))
            buttons[1].button("Load improved draft", on_click=load_improved)
            buttons[2].button("Reset lab", on_click=reset_lab)
        with right:
            st.markdown(f"**Production:** {'v' + str(rec.production) if rec.production else 'nothing promoted yet'}")
            if not rec.versions:
                st.info("Snapshot the draft to create v1.")
            for version in reversed(rec.versions):
                badge = "approved by " + version.approved_by if version.approved_by else "not approved"
                prod = "  |  PRODUCTION" if rec.production == version.number else ""
                with st.expander(f"v{version.number} - {badge}{prod}"):
                    st.code(version.template, language="text", wrap_lines=True)
                    st.caption(f"sha256 {version.digest}  |  {version.created_at}  |  {version.note or 'no note'}")
                    action = st.columns(2)
                    if action[0].button("Approve", key=f"approve_{version.number}", disabled=bool(version.approved_by)):
                        try:
                            rec.approve(version.number, actor)
                            st.rerun()
                        except ValueError as error:
                            st.error(str(error))
                    if action[1].button("Promote to production", key=f"promote_{version.number}"):
                        try:
                            rec.promote(version.number, actor)
                            st.rerun()
                        except ValueError as error:
                            st.error(str(error))
            if len(rec.versions) >= 2:
                with st.expander("Diff latest two versions"):
                    st.code(diff(rec.versions[-2].template, rec.versions[-1].template), language="diff")
        st.caption("Rollback is just promoting an older approved version again; the audit log records both.")

    with regress_tab:
        render_regression(settings, rec)
    with audit_tab:
        if rec.audit:
            st.dataframe(rec.audit[::-1], hide_index=True, width="stretch")
        else:
            st.info("Nothing yet. Every snapshot, approval, promotion and rollback is logged here.")
        st.caption("In production the audit trail lives in CloudTrail and your own store, not in this browser session.")
    with bedrock_tab:
        render_prompt_management(settings, rec)


def render_regression(settings: dict | None, rec: PromptRecord) -> None:
    if len(rec.versions) < 1:
        st.info("Create at least one version first.")
        return
    numbers = [v.number for v in rec.versions]
    cols = st.columns(2)
    baseline = cols[0].selectbox("Baseline version", numbers, index=0, format_func=lambda n: f"v{n}")
    candidate = cols[1].selectbox("Candidate version", numbers, index=len(numbers) - 1, format_func=lambda n: f"v{n}")
    st.markdown("**Fixed test cases** (same inputs for every version, so differences come from the prompt):")
    st.dataframe([{"case": c.name, "must contain": ", ".join(c.must_contain), "must not contain": ", ".join(c.must_not_contain),
                   "max words": c.max_words or ""} for c in DEFAULT_CASES], hide_index=True, width="stretch")
    if not st.button("Run regression on Bedrock", type="primary", disabled=not settings):
        return
    results = {}
    for label, number in (("baseline", baseline), ("candidate", candidate)):
        template = rec.get(number).template
        rows = []
        for case in DEFAULT_CASES:
            try:
                with st.spinner(f"v{number} / {case.name}"):
                    answer = converse_once(settings, render(template, case.values), max_tokens=200)
                failures = check_output(case, answer["text"])
                rows.append({"case": case.name, "result": "PASS" if not failures else "FAIL",
                             "why": "; ".join(failures), "tokens": answer["usage"]["totalTokens"],
                             "output": answer["text"]})
            except (ValueError, *BEDROCK_ERRORS) as error:
                rows.append({"case": case.name, "result": "ERROR", "why": describe_error(error), "tokens": 0, "output": ""})
        results[label] = rows
    for label, number in (("baseline", baseline), ("candidate", candidate)):
        passed = sum(r["result"] == "PASS" for r in results[label])
        st.subheader(f"{label.title()} v{number}: {passed}/{len(DEFAULT_CASES)} passed")
        st.dataframe([{k: v for k, v in r.items() if k != "output"} for r in results[label]],
                     hide_index=True, width="stretch")
        with st.expander("Model outputs"):
            for r in results[label]:
                st.markdown(f"**{r['case']}**")
                st.code(r["output"] or "(none)", language="text", wrap_lines=True)
    base_pass = sum(r["result"] == "PASS" for r in results["baseline"])
    cand_pass = sum(r["result"] == "PASS" for r in results["candidate"])
    if cand_pass < base_pass:
        st.error("Regression: the candidate passes fewer cases than the baseline. Do not promote.")
    else:
        st.success("No regression against the baseline on these cases.")


def render_prompt_management(settings: dict | None, rec: PromptRecord) -> None:
    st.markdown(
        "Bedrock **Prompt management** stores a prompt with variables and model settings, and creating a "
        "*version* freezes it. You then call `Converse` with the **version ARN** as `modelId` and pass "
        "`promptVariables`. Draft edits never change a published version."
    )
    if not settings or not rec.versions:
        st.info("Configure .env and create a version first.")
        return
    version = rec.get(st.selectbox("Local version to publish", [v.number for v in rec.versions],
                                   index=len(rec.versions) - 1, format_func=lambda n: f"v{n}"))
    name = st.text_input("Prompt name", value="aip-c01-lab-support-summary")
    if st.button("Publish to Prompt management"):
        try:
            client = make_session(settings).client("bedrock-agent")
            created = client.create_prompt(
                name=name,
                variants=[{
                    "name": "default", "templateType": "TEXT", "modelId": settings["BEDROCK_MODEL_ID"],
                    "templateConfiguration": {"text": {
                        "text": version.template,
                        "inputVariables": [{"name": v} for v in extract_variables(version.template)]}},
                    "inferenceConfiguration": {"text": {"temperature": 0.0, "maxTokens": 200}},
                }],
                defaultVariant="default",
            )
            frozen = client.create_prompt_version(promptIdentifier=created["id"], description=f"local v{version.number}")
            st.session_state["prompt_version_arn"] = frozen["arn"]
            st.success(f"Created prompt {created['id']} and frozen version {frozen['version']}.")
        except BEDROCK_ERRORS as error:
            st.error(f"Could not publish: {describe_error(error)}")
    arn = st.text_input("Prompt version ARN", value=st.session_state.get("prompt_version_arn", ""))
    values = {name_: st.text_input(f"promptVariables.{name_}", key=f"pv_{name_}") for name_ in extract_variables(version.template)}
    if st.button("Invoke by version ARN", disabled=not arn):
        try:
            client = make_session(settings).client("bedrock-runtime")
            response = client.converse(modelId=arn, promptVariables={k: {"text": v} for k, v in values.items()})
            st.markdown(response["output"]["message"]["content"][0]["text"])
            st.caption(f"{response['usage']['totalTokens']} tokens, stop reason {response['stopReason']}")
        except BEDROCK_ERRORS as error:
            st.error(f"Invoke failed: {describe_error(error)}")
    st.caption("Needs bedrock:CreatePrompt, bedrock:CreatePromptVersion, and bedrock:GetPrompt plus "
               "bedrock:InvokeModel on the version ARN. Delete the prompt in the console afterwards.")
