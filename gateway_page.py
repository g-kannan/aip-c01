"""Streamlit client for the IAM-authenticated Bedrock Chat Gateway."""
import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

import boto3
import streamlit as st
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.exceptions import BotoCoreError

from converse import load_settings


def call_gateway(url: str, prompt: str, profile: str) -> dict:
    parsed = urlsplit(url)
    match = re.fullmatch(r"[a-z0-9]+\.execute-api\.([a-z0-9-]+)\.amazonaws\.com(?:\.cn)?", parsed.hostname or "")
    if parsed.scheme != "https" or not match or parsed.port or parsed.username or parsed.query or parsed.fragment or not parsed.path.endswith("/explain"):
        raise ValueError("Enter the HTTPS API Gateway /explain URL from the SAM stack output.")
    session = boto3.Session(profile_name=profile, region_name=match.group(1))
    credentials = session.get_credentials()
    if credentials is None:
        raise ValueError("AWS credentials are unavailable for this profile.")
    body = json.dumps({"prompt": prompt}).encode("utf-8")
    request = AWSRequest(method="POST", url=url, data=body, headers={"Content-Type": "application/json"})
    SigV4Auth(credentials.get_frozen_credentials(), "execute-api", match.group(1)).add_auth(request)
    signed = Request(url, data=body, headers=dict(request.headers.items()), method="POST")
    try:
        with urlopen(signed, timeout=35) as result:
            return json.load(result)
    except HTTPError as error:
        try:
            detail = json.loads(error.read()).get("error", "Request rejected by API Gateway.")
        except (ValueError, AttributeError):
            detail = "Request rejected by API Gateway."
        raise ValueError(f"Gateway returned HTTP {error.code}: {detail}") from error
    except (URLError, TimeoutError) as error:
        raise ValueError("Could not reach the gateway. Check the URL and network connection.") from error


def render_gateway_page() -> None:
    st.title("Bedrock Chat Gateway")
    st.caption("Send an independent prompt through API Gateway and Lambda to Bedrock Converse.")
    settings = load_settings(required=())
    profile = settings["AWS_PROFILE"] or "default"
    with st.form("gateway_form"):
        url = st.text_input("Gateway URL", value=settings["GATEWAY_URL"], placeholder="https://...execute-api.../prod/explain")
        aws_profile = st.text_input("AWS profile", value=profile)
        prompt = st.text_area("Prompt", height=180, max_chars=16000)
        submitted = st.form_submit_button("Send prompt", type="primary")
    if settings["GATEWAY_INVOKE_ARN"]:
        st.caption("Invoke ARN (for caller IAM permissions)")
        st.code(settings["GATEWAY_INVOKE_ARN"])
    st.caption("Requests are signed with the selected AWS profile. Each prompt is independent; model usage may incur charges.")
    if submitted:
        st.session_state.pop("gateway_result", None)
        if not prompt.strip():
            st.error("Enter a prompt.")
            return
        try:
            with st.spinner("Waiting for the gateway..."):
                st.session_state["gateway_result"] = call_gateway(url.strip(), prompt, aws_profile.strip())
        except (ValueError, BotoCoreError) as error:
            st.error(str(error))
            return
    if "gateway_result" in st.session_state:
        result = st.session_state["gateway_result"]
        st.subheader("Response")
        st.markdown(result.get("answer") or "No text returned.")
        st.caption(f"Stop reason: {result.get('stopReason', 'unknown')} | Usage: {result.get('usage', {})}")
