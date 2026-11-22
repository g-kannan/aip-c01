"""Streamlit lab for Bedrock Knowledge Bases: Retrieve versus RetrieveAndGenerate."""

from pathlib import Path

import streamlit as st
from botocore.exceptions import BotoCoreError, ClientError

from converse import load_settings
from knowledge_base import (
    AUTO_KB, KB_TYPES, OPERATIONS, OPERATORS, RERANKING, SEARCH_TYPES, VECTOR_KB, build_filter,
    build_generate_request, build_retrieve_request, chunk_title, cited_texts, detect_kb_type, error_hint,
    filterable_attributes, list_knowledge_bases, load_metadata_catalog, location_uri, make_code_snippet,
    make_session, model_arn_for, resolve_model_arn, retrieval_configuration, run_retrieve,
    run_retrieve_and_generate, user_metadata, validate_inputs,
)

RESOURCES = Path(__file__).with_name("resources")
NO_FILTER = "(none)"
EXAMPLES = [
    {
        "label": "Grounded question",
        "query": "How does RAG combine a retriever with a generator?",
        "filter": None,
        "note": "On-topic question. Expect high scores, a cited answer, and the RAG paper near the top.",
    },
    {
        "label": "Metadata filter",
        "query": "How do language models learn to use tools?",
        "filter": ("year", "greaterThanOrEquals", "2024"),
        "note": "Only chunks from papers with year >= 2024 are eligible. Remove the filter and compare the sources.",
    },
    {
        "label": "Bad query",
        "query": "What is the best pizza recipe in Naples?",
        "filter": None,
        "note": "Off-topic. Retrieve still returns the nearest chunks, but with low scores. Check what the generator does.",
    },
    {
        "label": "Empty filter",
        "query": "What is retrieval-augmented generation?",
        "filter": ("year", "equals", "1999"),
        "note": "No document has year = 1999, so the filter excludes everything. Compare this with the bad query.",
    },
]
READING_GUIDE = (
    "- **Retrieve** is vector search only: it returns the nearest chunks and relevance scores. No model runs.\n"
    "- **RetrieveAndGenerate** retrieves, prompts the model with the chunks, and returns an answer with citations.\n"
    "- **Scores** rank chunks for one query. There is no universal cutoff, so compare scores across your queries.\n"
    "- An **unrelated query** still returns the nearest chunks, just with low scores. **No results** usually means "
    "a filter excluded everything, or the data source was never synced.\n"
    "- A **metadata filter** limits which chunks are eligible. It only works on attributes ingested from "
    "`.metadata.json` files that sit next to the documents in S3.\n"
    "- **Vector-store** and **managed** knowledge bases take different retrieval settings "
    "(`vectorSearchConfiguration` versus `managedSearchConfiguration`). Open **Request** to see which was sent.\n"
    "- In **Compare both**, chunks marked *cited* were used in the answer. The two calls retrieve separately, "
    "so the chunk lists can differ slightly."
)


def load_example(index: int, attribute_options: list[str]) -> None:
    example = EXAMPLES[index]
    attribute, operator, value = example["filter"] or (NO_FILTER, "equals", "")
    if attribute not in attribute_options:
        attribute, value = NO_FILTER, ""
    st.session_state.update({
        "kb_query": example["query"], "kb_example": index,
        "kb_f1_attr": attribute, "kb_f1_op": operator, "kb_f1_value": value,
        "kb_f2_attr": NO_FILTER, "kb_f2_op": "equals", "kb_f2_value": "",
    })


def use_knowledge_base() -> None:
    st.session_state["kb_id"] = st.session_state["kb_pick"]


def init_state(settings: dict | None) -> None:
    defaults = {
        "kb_id": (settings or {}).get("KNOWLEDGE_BASE_ID", ""),
        "kb_operation": OPERATIONS[2], "kb_query": EXAMPLES[0]["query"], "kb_view": "Results",
        "kb_gen_model": (settings or {}).get("BEDROCK_MODEL_ID", ""),
    }
    for number in (1, 2):
        defaults.update({f"kb_f{number}_attr": NO_FILTER, f"kb_f{number}_op": "equals", f"kb_f{number}_value": ""})
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def render_finder(settings: dict | None) -> None:
    with st.expander("Find my knowledge bases"):
        st.caption("Lists knowledge bases in your AWS_REGION. Needs bedrock:ListKnowledgeBases; invokes no model.")
        if st.button("List knowledge bases", disabled=settings is None, key="kb_list"):
            st.session_state.pop("kb_catalog", None)
            st.session_state.pop("kb_catalog_error", None)
            try:
                with st.spinner("Loading knowledge bases..."):
                    session = make_session(settings["AWS_PROFILE"], settings["AWS_REGION"])
                    st.session_state["kb_catalog"] = list_knowledge_bases(session)
            except (BotoCoreError, ClientError) as error:
                st.session_state["kb_catalog_error"] = f"Could not list knowledge bases: {error}"
        if st.session_state.get("kb_catalog_error"):
            st.error(st.session_state["kb_catalog_error"])
        catalog = st.session_state.get("kb_catalog")
        if catalog is not None:
            if not catalog:
                st.info("No knowledge bases were returned for this region.")
                return
            by_id = {kb["knowledgeBaseId"]: kb for kb in catalog}
            st.selectbox(
                "Knowledge base", list(by_id), key="kb_pick",
                format_func=lambda value: f"{by_id[value].get('name', value)} ({value}) / {by_id[value].get('status', '')}",
            )
            st.button("Use selected", on_click=use_knowledge_base, key="kb_use")
            st.caption("To keep it, add KNOWLEDGE_BASE_ID=<id> to .env.")


def render_filters(attributes: dict[str, dict]) -> list[tuple]:
    st.caption("Metadata filter (optional; two rows are combined with AND)")
    options = [NO_FILTER, *attributes]
    conditions = []
    for number in (1, 2):
        attribute_column, operator_column, value_column = st.columns([1.3, 0.8, 1.2])
        attribute = attribute_column.selectbox(
            f"Filter {number} attribute", options, key=f"kb_f{number}_attr", label_visibility="collapsed",
        )
        operator = operator_column.selectbox(
            f"Filter {number} operator", list(OPERATORS), key=f"kb_f{number}_op",
            format_func=OPERATORS.get, label_visibility="collapsed",
        )
        value = value_column.text_input(
            f"Filter {number} value", key=f"kb_f{number}_value", placeholder="value", label_visibility="collapsed",
        )
        conditions.append((None if attribute == NO_FILTER else attribute, operator, value))
        known = attributes.get(attribute, {}).get("values", [])
        if known and attribute != "title":
            shown = ", ".join(str(item)[:28] for item in known[:8]) + (" ..." if len(known) > 8 else "")
            st.caption(f"{attribute} in resources/: {shown}")
    return conditions


def render_chunks(retrieve: dict, cited: set[str]) -> None:
    results = retrieve["response"].get("retrievalResults", [])
    st.markdown("**Retrieve** · nearest chunks")
    st.caption(f"{len(results)} chunks | round trip {retrieve['ms']} ms")
    if not results:
        st.warning(
            "No chunks matched. Check whether a metadata filter excludes every document, and whether the "
            "data source was synced. An unrelated query normally still returns low-scoring chunks."
        )
        return
    for position, result in enumerate(results, start=1):
        score = result.get("score")
        text = result.get("content", {}).get("text", "")
        flag = "  ·  cited" if text in cited else ""
        label = f"{position}. {chunk_title(result)}  ·  score {score:.3f}{flag}" if score is not None else (
            f"{position}. {chunk_title(result)}{flag}"
        )
        with st.expander(label, expanded=position == 1):
            details = [f"{key}: {value}" for key, value in user_metadata(result.get("metadata")).items()
                       if key != "source_url"]
            if details:
                st.caption(" | ".join(details))
            uri = location_uri(result.get("location"))
            if uri:
                st.caption(uri)
            st.code(text or "(empty chunk)", language="text", wrap_lines=True)


def render_answer(generate: dict) -> None:
    response = generate["response"]
    st.markdown("**RetrieveAndGenerate** · cited answer")
    st.caption(f"round trip {generate['ms']} ms | session {str(response.get('sessionId', ''))[:8]}")
    if response.get("guardrailAction") == "INTERVENED":
        st.warning("A guardrail intervened in this response.")
    st.markdown(response.get("output", {}).get("text") or "No text returned.")
    citations = response.get("citations", [])
    if not citations:
        st.info(
            "No citations were returned, so the answer is not grounded in retrieved text. "
            "The model may have declined to answer."
        )
        return
    st.caption(f"{len(citations)} citation(s)")
    for number, citation in enumerate(citations, start=1):
        part = citation.get("generatedResponsePart", {}).get("textResponsePart", {}).get("text", "")
        references = citation.get("retrievedReferences", [])
        with st.expander(f"Citation {number}: {part[:80]}" + ("..." if len(part) > 80 else "")):
            for reference in references:
                st.caption(f"{chunk_title(reference)}  |  {location_uri(reference.get('location'))}")
                st.code(reference.get("content", {}).get("text", ""), language="text", wrap_lines=True)


def explain(error: Exception) -> str:
    if isinstance(error, ClientError):
        hint = error_hint(error.response.get("Error", {}).get("Code", ""))
        return f"Knowledge base request failed: {error}" + (f"\n\n{hint}" if hint else "")
    return f"Knowledge base request failed: {error}\n\nCheck your AWS login for this profile."


def resolve_kb_type(session, choice: str, kb_id: str) -> str:
    """Use the chosen type, or detect it once per knowledge base and remember the answer."""
    if choice != AUTO_KB:
        return choice
    detected = st.session_state.setdefault("kb_types", {})
    if kb_id not in detected:
        try:
            detected[kb_id] = detect_kb_type(session, kb_id)
        except (BotoCoreError, ClientError) as error:
            raise ValueError(
                f"{explain(error)}\n\nCould not auto-detect the knowledge base type. "
                "Choose Vector store or Managed under Parameters."
            ) from error
    return detected[kb_id]


def render_knowledge_base_page() -> None:
    st.title("Knowledge Base Lab")
    st.caption("AIP-C01 / Retrieve chunks, generate cited answers, filter by metadata.")
    settings = None
    try:
        settings = load_settings(required=("AWS_PROFILE", "AWS_REGION"))
    except ValueError as error:
        st.warning(str(error))
    attributes = filterable_attributes(load_metadata_catalog(RESOURCES))
    init_state(settings)

    with st.sidebar:
        st.caption("CONNECTION")
        if settings:
            st.caption(f"{settings['AWS_PROFILE']} / {settings['AWS_REGION']}")
        st.caption("Each run calls Bedrock Knowledge Bases. Generation also invokes a model and incurs usage.")

    controls, output = st.columns([1, 1.65], gap="large")
    with controls:
        render_finder(settings)
        st.caption("EXAMPLES")
        example_columns = st.columns(2)
        for index, example in enumerate(EXAMPLES):
            example_columns[index % 2].button(
                example["label"], key=f"kb_example_btn_{index}", on_click=load_example,
                args=(index, [NO_FILTER, *attributes]), use_container_width=True,
            )
        if "kb_example" in st.session_state:
            st.caption(EXAMPLES[st.session_state["kb_example"]]["note"])
        st.text_input(
            "Knowledge base ID", key="kb_id", placeholder="10-character ID, e.g. ABCDE12345",
            help="Set KNOWLEDGE_BASE_ID in .env, or use Find my knowledge bases above.",
        )
        operation = st.radio("Operation", OPERATIONS, horizontal=True, key="kb_operation")
        query = st.text_area("Question", height=110, max_chars=2000, key="kb_query")
        conditions = render_filters(attributes)
        with st.popover("Parameters", use_container_width=True):
            number_of_results = st.slider("Number of results", 1, 20, 5, key="kb_results")
            kb_type_choice = st.selectbox(
                "Knowledge base type", KB_TYPES, key="kb_type",
                help="Vector-store and managed knowledge bases take different retrieval settings. "
                     "Auto-detect reads the type from AWS (needs bedrock:GetKnowledgeBase).",
            )
            search_type = st.selectbox(
                "Search type (vector store only)", SEARCH_TYPES, key="kb_search_type",
                help="Default lets the vector store decide. HYBRID combines semantic and keyword search where "
                     "supported. Ignored for managed knowledge bases.",
            )
            reranking = st.selectbox(
                "Reranking (managed only)", RERANKING, key="kb_reranking",
                help="MANAGED uses the service's default reranker; NONE turns reranking off. "
                     "Ignored for vector-store knowledge bases.",
            )
            st.text_input(
                "Generation model or inference profile ID", key="kb_gen_model",
                help="Used by RetrieveAndGenerate. Defaults to BEDROCK_MODEL_ID. A full ARN is also accepted.",
            )
            temperature = st.slider("Temperature", 0.0, 1.0, 0.2, 0.1, key="kb_temperature")
            max_tokens = st.number_input("Maximum output tokens", min_value=1, value=512, step=64, key="kb_max_tokens")
        run_column, preview_column = st.columns(2)
        submitted = run_column.button(
            "Run query", type="primary", disabled=settings is None, use_container_width=True, key="kb_run",
        )
        preview = preview_column.button(
            "Preview code", use_container_width=True, key="kb_preview",
            help="Update the code snippet without calling AWS.",
        )
        st.caption("Independent queries. AWS usage applies only when you run.")
        with st.expander("How to read the results"):
            st.markdown(READING_GUIDE)

    if submitted:
        st.session_state.pop("kb_result", None)
        st.session_state.pop("kb_error", None)
        st.session_state["kb_view"] = "Results"
    if preview:
        st.session_state["kb_view"] = "Code snippet"

    kb_id, model_id = st.session_state["kb_id"], st.session_state["kb_gen_model"]
    wants_generate = operation != "Retrieve"

    def build_requests(model_arn: str | None, kb_type: str) -> tuple[dict | None, dict | None]:
        config = retrieval_configuration(
            number_of_results, search_type, build_filter(conditions, attributes), kb_type, reranking,
        )
        retrieve_request = build_retrieve_request(kb_id, query, config) if operation != "RetrieveAndGenerate" else None
        generate_request = build_generate_request(
            kb_id, query, model_arn, config, int(max_tokens), temperature,
        ) if wants_generate else None
        return retrieve_request, generate_request

    with output, st.container(height=560, border=True, key="kb_lab_output"):
        view = st.radio(
            "Output view", ["Results", "Request", "Raw JSON", "Code snippet"],
            horizontal=True, label_visibility="collapsed", key="kb_view",
        )
        if view == "Code snippet":
            config = settings or {"AWS_PROFILE": "agent", "AWS_REGION": "ap-south-1"}
            try:
                arn = model_arn_for(model_id, config["AWS_REGION"]) if wants_generate else None
                known = st.session_state.get("kb_types", {}).get(kb_id.strip())
                preview_type = kb_type_choice if kb_type_choice != AUTO_KB else (known or VECTOR_KB)
                retrieve_request, generate_request = build_requests(arn, preview_type)
                st.code(
                    make_code_snippet(config["AWS_PROFILE"], config["AWS_REGION"], retrieve_request, generate_request),
                    language="python", wrap_lines=True,
                )
                st.caption("Preview code refreshes the form values without calling AWS.")
                if kb_type_choice == AUTO_KB and not known:
                    st.caption("Type not detected yet, so the preview assumes a vector store. Run a query to detect it.")
                if wants_generate:
                    st.caption("Replace <ACCOUNT_ID> with your account ID; running the page fills it in for you.")
            except ValueError as error:
                st.info(str(error))
            return

        message = st.empty()
        if submitted and settings:
            try:
                session = make_session(settings["AWS_PROFILE"], settings["AWS_REGION"])
                validate_inputs(kb_id, query)
                kb_type = resolve_kb_type(session, kb_type_choice, kb_id.strip())
                arn = resolve_model_arn(session, model_id) if wants_generate else None
                retrieve_request, generate_request = build_requests(arn, kb_type)
                result = {
                    "retrieve": None, "generate": None, "region": settings["AWS_REGION"], "kb_type": kb_type,
                }
                with st.spinner("Querying the knowledge base..."):
                    if retrieve_request:
                        result["retrieve"] = run_retrieve(session, retrieve_request)
                    if generate_request:
                        result["generate"] = run_retrieve_and_generate(session, generate_request)
                st.session_state["kb_result"] = result
            except ValueError as error:
                st.session_state["kb_error"] = str(error)
            except (BotoCoreError, ClientError) as error:
                st.session_state["kb_error"] = explain(error)
        if st.session_state.get("kb_error"):
            message.error(st.session_state["kb_error"])
            return
        result = st.session_state.get("kb_result")
        if not result:
            message.info("Run a question to see retrieved chunks and answers here, or preview the code to study the request.")
            return
        retrieve, generate = result["retrieve"], result["generate"]
        if view == "Request":
            st.json({
                **({"retrieve": retrieve["request"]} if retrieve else {}),
                **({"retrieve_and_generate": generate["request"]} if generate else {}),
            }, expanded=2)
        elif view == "Raw JSON":
            st.caption("Complete decoded API responses, including response metadata.")
            st.json({
                **({"retrieve": retrieve["response"]} if retrieve else {}),
                **({"retrieve_and_generate": generate["response"]} if generate else {}),
            }, expanded=1)
        else:
            st.caption(f"{result['region']} | {result['kb_type'].lower()} knowledge base")
            cited = cited_texts(generate["response"]) if generate else set()
            if retrieve:
                render_chunks(retrieve, cited)
            if retrieve and generate:
                st.divider()
            if generate:
                render_answer(generate)
