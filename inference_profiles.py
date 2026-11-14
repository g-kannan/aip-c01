"""Browse Bedrock inference profiles using the existing local AWS CLI profile."""

from contextlib import closing
import re

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
import streamlit as st

from converse import load_settings


def list_profiles(profile_name: str, region: str, geography: str) -> list[dict]:
    """Read every result page, then filter system-defined profiles by geography."""
    prefix = {"APAC": "apac.", "US": "us."}[geography]
    region_prefix = "ap-" if geography == "APAC" else "us-"
    if not re.fullmatch(r"[a-z]{2}(?:-[a-z]+)+-\d+", region) or not region.startswith(region_prefix):
        raise ValueError(f"Enter a {geography} source region, such as "
                         f"{'ap-south-1' if geography == 'APAC' else 'us-east-1'}.")
    session = boto3.Session(profile_name=profile_name, region_name=region)
    with closing(session.client(
        "bedrock",
        config=Config(
            retries={"mode": "adaptive", "total_max_attempts": 3},
            connect_timeout=10, read_timeout=30,
        ),
    )) as client:
        pages = client.get_paginator("list_inference_profiles").paginate(typeEquals="SYSTEM_DEFINED")
        profiles = [
            profile for page in pages for profile in page.get("inferenceProfileSummaries", [])
            if profile["inferenceProfileId"].startswith(prefix)
        ]
    return sorted(profiles, key=lambda profile: profile["inferenceProfileId"])


def render_profiles_page() -> None:
    st.title("Inference profiles")
    st.caption("Choose a source region. Find the routing profile for your next request.")
    settings = None
    try:
        settings = load_settings(required=("AWS_PROFILE",))
    except ValueError as error:
        st.warning(str(error))
    with st.sidebar:
        st.caption("CONNECTION")
        if settings:
            st.text(f"AWS profile: {settings['AWS_PROFILE']}")
        st.caption("Listing uses the Bedrock control plane and does not invoke a model.")

    controls, output = st.columns([1, 1.65], gap="large")
    with controls:
        geography = st.radio("Geography", ["APAC", "US"], horizontal=True)
        default_region = "ap-south-1" if geography == "APAC" else "us-east-1"
        configured_region = (settings or {}).get("AWS_REGION", "")
        if configured_region.startswith("ap-" if geography == "APAC" else "us-"):
            default_region = configured_region
        with st.form("profile_search"):
            region = st.text_input(
                "Source AWS region", value=default_region, key=f"profiles_region_{geography}",
                help="The region receiving the API request, before any cross-region routing.",
            ).strip()
            submitted = st.form_submit_button(
                "List profiles", type="primary", disabled=settings is None, use_container_width=True,
            )
        st.caption("APAC: apac.* / US: us.*. Global and country-specific profiles are excluded.")

    if submitted and settings:
        st.session_state.pop("profile_catalog", None)
        st.session_state.pop("profiles_error", None)
        try:
            with st.spinner("Loading inference profiles..."):
                profiles = list_profiles(settings["AWS_PROFILE"], region, geography)
            st.session_state["profile_catalog"] = {
                "profiles": profiles, "region": region, "geography": geography,
                "aws_profile": settings["AWS_PROFILE"],
            }
        except ValueError as error:
            st.session_state["profiles_error"] = str(error)
        except (BotoCoreError, ClientError) as error:
            st.session_state["profiles_error"] = f"Could not list inference profiles: {error}"

    with output, st.container(height=520, border=True, key="profiles_output"):
        render_profile_results(settings, geography)


def render_profile_results(settings: dict | None, geography: str) -> None:
    if st.session_state.get("profiles_error"):
        st.error(st.session_state["profiles_error"])
        st.caption("Check your AWS login, source region, and bedrock:ListInferenceProfiles permission.")
        return

    result = st.session_state.get("profile_catalog")
    if not settings or not result or (
        result["geography"] != geography or result["aws_profile"] != settings["AWS_PROFILE"]
    ):
        st.info("Click List profiles to load current results from AWS.")
        return
    profiles = result["profiles"]
    st.caption(f"{result['geography']} / {result['region']}")
    if not profiles:
        st.info("No matching profiles were returned for this source region.")
        return
    search = st.text_input("Filter by model, profile name, or ID", key="profiles_filter").strip().lower()
    filtered = [profile for profile in profiles if search in " ".join((
        profile["inferenceProfileId"], profile.get("inferenceProfileName", ""),
        *(model.get("modelArn", "") for model in profile.get("models", [])),
    )).lower()]
    st.caption(f"{len(filtered)} of {len(profiles)} profiles. Search and selection use saved results.")
    if not filtered:
        st.info("No profiles match this filter.")
        return
    by_id = {profile["inferenceProfileId"]: profile for profile in filtered}
    identifier = st.selectbox(
        "Profile", list(by_id),
        format_func=lambda value: by_id[value].get("inferenceProfileName", value),
        key=f"profile_selection_{geography}_{result['region']}",
    )
    profile = by_id[identifier]
    overview, raw = st.tabs(["Overview", "Raw JSON"])
    with overview:
        st.caption(f"Status: {profile.get('status', 'Unknown')}")
        if profile.get("description"):
            st.write(profile["description"])
        destinations = sorted({
            model["modelArn"].split(":")[3] for model in profile.get("models", [])
        })
        st.write("Destination regions: " + (", ".join(destinations) or "Not returned"))
        st.caption("Copy to .env to use in the Converse lab:")
        st.code(f"AWS_REGION={result['region']}\nBEDROCK_MODEL_ID={identifier}", language="dotenv")
    with raw:
        st.json(profile, expanded=True)
    st.caption("A listed profile does not guarantee invocation permission or model access.")
    st.markdown("[AWS inference profile reference](https://docs.aws.amazon.com/bedrock/latest/userguide/inference-profiles-support.html)")
