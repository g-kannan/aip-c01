"""A small Streamlit playground for the Bedrock Converse certification lab."""

from pathlib import Path
from contextlib import closing

import streamlit as st
from botocore.exceptions import BotoCoreError, ClientError

from converse import DEFAULT_SYSTEM_PROMPT, build_request, invoke_converse, load_settings, stream_converse
from inference_profiles import render_profiles_page
from gateway_page import render_gateway_page
from knowledge_base_page import render_knowledge_base_page


def make_code_snippet(settings: dict, request: dict, streaming: bool = False) -> str:
    """Show only profile setup, the Converse call, and response text."""
    system_line = f"    system={request['system']!r},\n" if "system" in request else ""
    operation = "converse_stream" if streaming else "converse"
    output_code = '''for event in response["stream"]:
    delta = event.get("contentBlockDelta", {}).get("delta", {})
    print(delta.get("text", ""), end="", flush=True)''' if streaming else (
        'print(response["output"]["message"]["content"][0]["text"])'
    )
    return f'''# Streaming = progressive delivery; multi-turn chat = conversation history.
client = boto3.Session(
    profile_name={settings["AWS_PROFILE"]!r}, region_name={settings["AWS_REGION"]!r},
).client("bedrock-runtime")

response = client.{operation}(
    modelId={request["modelId"]!r},
    messages={request["messages"]!r},
{system_line}    inferenceConfig={request["inferenceConfig"]!r},
)
{output_code}
'''


def consume_stream(settings: dict, request: dict, response: dict, events: list):
    """Yield text for display while collecting final metadata and raw events."""
    text = []
    stop_reason = None
    metadata = None
    with closing(stream_converse(settings, request)) as stream:
        for event in stream:
            events.append(event)
            chunk = event.get("contentBlockDelta", {}).get("delta", {}).get("text", "")
            if chunk:
                text.append(chunk)
                yield chunk
            if "messageStop" in event:
                stop_reason = event["messageStop"]["stopReason"]
            if "metadata" in event:
                metadata = event["metadata"]
    if (stop_reason is None or metadata is None
            or not {"inputTokens", "outputTokens", "totalTokens"} <= metadata.get("usage", {}).keys()
            or "latencyMs" not in metadata.get("metrics", {})):
        raise RuntimeError("The stream ended before completion metadata was received. Try running the prompt again.")
    response.update({
        "output": {"message": {"role": "assistant", "content": [{"text": "".join(text)}]}},
        "stopReason": stop_reason, "usage": metadata["usage"], "metrics": metadata["metrics"],
    })


def toggle_raw_response(key: str = "show_raw_response") -> None:
    st.session_state[key] = not st.session_state.get(key, False)


def render_playground() -> None:
    st.title("Bedrock Converse Lab")
    st.caption("AIP-C01 / Prompt, inspect, learn.")

    settings = None
    try:
        settings = load_settings()
    except ValueError as error:
        st.warning(str(error))

    with st.sidebar:
        st.caption("CONNECTION")
        if settings:
            st.caption(f"{settings['AWS_PROFILE']} / {settings['AWS_REGION']}")
            with st.expander("Model & configuration"):
                st.code(settings["BEDROCK_MODEL_ID"], language="text")
                st.caption("Change profile, region, and model in .env.")

    converse_tab, stream_tab = st.tabs(["Converse", "ConverseStream"])
    with converse_tab:
        render_api_tab(settings)
    with stream_tab:
        render_api_tab(settings, streaming=True)


def render_api_tab(settings: dict | None, streaming: bool = False) -> None:
    prefix = "stream_" if streaming else ""
    result_key, error_key = f"{prefix}last_result", f"{prefix}last_error"
    view_key, raw_key = f"{prefix}output_view", f"{prefix}show_raw_response"
    controls, output = st.columns([1, 1.65], gap="large")
    with controls:
        with st.form(f"{prefix}prompt_form"):
            prompt = st.text_area(
                "Prompt", value="Explain RAG versus fine-tuning with one example each.",
                height=200, key=f"{prefix}prompt",
            )
            with st.popover("Parameters", use_container_width=True):
                temperature = st.slider("Temperature", 0.0, 1.0, 0.2, 0.1, key=f"{prefix}temperature")
                max_tokens = st.number_input(
                    "Maximum output tokens", min_value=1, value=512, step=64, key=f"{prefix}max_tokens",
                )
                system_prompt = st.text_area(
                    "System instructions", value=DEFAULT_SYSTEM_PROMPT, height=100, key=f"{prefix}system_prompt",
                )
            run_column, preview_column = st.columns(2)
            submitted = run_column.form_submit_button(
                "Run prompt", type="primary", disabled=settings is None, use_container_width=True,
                key=f"{prefix}run",
            )
            preview = preview_column.form_submit_button(
                "Preview code", help="Update the code snippet without invoking Bedrock.",
                use_container_width=True,
                key=f"{prefix}preview",
            )
        st.caption("Independent prompts. AWS usage applies only when you run.")

    if submitted:
        st.session_state.pop(result_key, None)
        st.session_state.pop(error_key, None)
        st.session_state[raw_key] = False
        st.session_state[view_key] = "Response"
    if preview or st.session_state.get(view_key) == "Study":
        st.session_state[view_key] = "Code snippet"
    with output, st.container(height=520, border=True, key=f"{prefix}lab_output"):
        view = st.radio(
            "Output view", ["Response", "Request", "Raw JSON", "Code snippet"],
            horizontal=True, label_visibility="collapsed", key=view_key,
        )
        if view == "Code snippet":
            config = settings or {
                "AWS_PROFILE": "agent", "AWS_REGION": "ap-south-1",
                "BEDROCK_MODEL_ID": "apac.amazon.nova-micro-v1:0",
            }
            try:
                request = build_request(
                    prompt, config["BEDROCK_MODEL_ID"], max_tokens, temperature, system_prompt,
                )
                st.code(make_code_snippet(config, request, streaming), language="python", wrap_lines=True)
                st.caption("Preview code refreshes the form values without calling AWS.")
                if streaming:
                    st.caption("Streaming permission: bedrock:InvokeModelWithResponseStream. Text arrives in contentBlockDelta events.")
                with st.expander("Parameter notes"):
                    st.markdown(
                        "- `modelId`: model or inference profile ID.\n"
                        "- `messages`: role and prompt content.\n"
                        "- `system`: model instructions (optional).\n"
                        "- `maxTokens`: maximum output tokens.\n"
                        "- `temperature`: sampling variation (0 to 1)."
                    )
                if not settings:
                    st.caption("Example configuration shown until .env is configured.")
            except ValueError as error:
                st.info(str(error))
            return
        summary, body = st.empty(), st.empty()
        if submitted and settings:
            try:
                request = build_request(
                    prompt, settings["BEDROCK_MODEL_ID"], max_tokens, temperature, system_prompt,
                )
                response, events = {}, []
                with st.spinner("Streaming from Bedrock..." if streaming else "Waiting for Bedrock..."):
                    if streaming:
                        chunks = []
                        with closing(consume_stream(settings, request, response, events)) as stream:
                            for chunk in stream:
                                chunks.append(chunk)
                                body.markdown("".join(chunks))
                    else:
                        response = invoke_converse(settings, request)
                # Retain decoded API data only; credentials and open streams are never saved.
                st.session_state[result_key] = {
                    "request": request, "response": response, "region": settings["AWS_REGION"],
                    **({"events": events} if streaming else {}),
                }
            except (ValueError, RuntimeError) as error:
                st.session_state[error_key] = str(error)
            except (BotoCoreError, ClientError) as error:
                st.session_state[error_key] = f"Bedrock request failed: {error}"
        if st.session_state.get(error_key):
            body.error(st.session_state[error_key])
            return
        result = st.session_state.get(result_key)
        if not result:
            body.info("Run a prompt to see the response here, or preview the code to study the request.")
            return
        response = result["response"]
        if view == "Request":
            body.json(result["request"], expanded=True)
        elif view == "Raw JSON":
            with body.container():
                st.button(
                    "Hide raw response" if st.session_state.get(raw_key) else "Show raw response",
                    key=f"{prefix}toggle_raw_response", on_click=toggle_raw_response, args=(raw_key,),
                )
                if st.session_state.get(raw_key):
                    if streaming:
                        st.caption("Decoded stream events in arrival order.")
                    st.json(result["events"] if streaming else response, expanded=True)
        else:
            usage = response["usage"]
            summary.caption(
                f"{usage['inputTokens']} in / {usage['outputTokens']} out / {usage['totalTokens']} total tokens"
                f"  |  {response['metrics']['latencyMs']} ms  |  {response['stopReason']}"
            )
            with body.container():
                st.caption(f"{result['request']['modelId']} / {result['region']}")
                if response["stopReason"] == "max_tokens":
                    st.warning("Output limit reached. Increase maximum output tokens for a longer answer.")
                text = "\n\n".join(
                    block["text"] for block in response["output"]["message"]["content"] if "text" in block
                )
                if text:
                    st.markdown(text)
                else:
                    st.info("No text returned. Open Raw JSON to inspect the response.")


def main() -> None:
    st.set_page_config(page_title="Bedrock Converse Lab", layout="wide")
    styles = Path(__file__).with_name("styles.css").read_text(encoding="utf-8")
    st.html(f"<style>{styles}</style>")
    page = st.navigation([
        st.Page(render_playground, title="Converse Lab", default=True),
        st.Page(render_profiles_page, title="Inference profiles", url_path="inference-profiles"),
        st.Page(render_gateway_page, title="Bedrock Chat Gateway", url_path="bedrock-chat-gateway"),
        st.Page(render_knowledge_base_page, title="Knowledge Base Lab", url_path="knowledge-base-lab"),
    ])
    page.run()


if __name__ == "__main__":
    main()
