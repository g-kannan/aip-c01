"""Project 3: Amazon Bedrock Knowledge Bases helpers for the RAG lab (no Streamlit imports)."""

from contextlib import closing
import json
from pathlib import Path
import pprint
import re
import time

import boto3
from botocore.config import Config


KB_ID_PATTERN = re.compile(r"[0-9A-Za-z]{10}")
OPERATIONS = ("Retrieve", "RetrieveAndGenerate", "Compare both")
SEARCH_TYPES = ("Default", "SEMANTIC", "HYBRID")
RERANKING = ("Default", "MANAGED", "NONE")
VECTOR_KB, MANAGED_KB, AUTO_KB = "Vector store", "Managed", "Auto-detect"
KB_TYPES = (AUTO_KB, VECTOR_KB, MANAGED_KB)
# Control-plane type -> label used by this lab. Other types (KENDRA, SQL) use different retrieval settings.
CONTROL_PLANE_TYPES = {"VECTOR": VECTOR_KB, "MANAGED": MANAGED_KB}
# Bedrock filter operator name -> symbol shown in the UI.
OPERATORS = {
    "equals": "=", "notEquals": "≠",
    "greaterThan": ">", "greaterThanOrEquals": "≥",
    "lessThan": "<", "lessThanOrEquals": "≤",
}
TEXT_OPERATORS = ("equals", "notEquals")
# Geography prefixes that mark a system-defined inference profile ID.
PROFILE_PREFIXES = ("us", "eu", "apac", "global", "us-gov", "jp", "au", "ca")
# Used when the local metadata sidecar files are missing.
DEFAULT_ATTRIBUTES = {
    "year": {"type": "NUMBER", "values": []}, "version": {"type": "NUMBER", "values": []},
    "title": {"type": "STRING", "values": []}, "arxiv_id": {"type": "STRING", "values": []},
    "first_author": {"type": "STRING", "values": []}, "topic": {"type": "STRING", "values": []},
    "source": {"type": "STRING", "values": []},
}
CLIENT_CONFIG = Config(
    retries={"mode": "adaptive", "total_max_attempts": 3}, connect_timeout=10, read_timeout=60,
)
ERROR_HINTS = {
    "ResourceNotFoundException": "Check the knowledge base ID, and that AWS_REGION is the region where it was created.",
    "AccessDeniedException": "Check bedrock:Retrieve, bedrock:RetrieveAndGenerate, and bedrock:InvokeModel permissions, and model access.",
    "ValidationException": (
        "Check the metadata filter, search type, and model ID. If the message mentions vectorSearchConfiguration or "
        "managedSearchConfiguration, set Knowledge base type under Parameters. Some operators and HYBRID search "
        "depend on the vector store."
    ),
    "ThrottlingException": "Reduce request frequency and try again.",
}


def load_metadata_catalog(directory: Path) -> dict[str, dict]:
    """Read the attributes and values defined in the local `*.metadata.json` sidecar files."""
    catalog: dict[str, dict] = {}
    for path in sorted(directory.glob("*.metadata.json")):
        try:
            attributes = json.loads(path.read_text(encoding="utf-8"))["metadataAttributes"]
        except (OSError, ValueError, KeyError, TypeError):
            continue
        for name, entry in attributes.items():
            value = entry.get("value", {}) if isinstance(entry, dict) else {}
            kind = value.get("type")
            raw = value.get("numberValue") if kind == "NUMBER" else value.get("stringValue")
            if kind not in {"NUMBER", "STRING"} or raw is None:
                continue
            item = catalog.setdefault(name, {"type": kind, "values": []})
            if raw not in item["values"]:
                item["values"].append(raw)
    for item in catalog.values():
        item["values"].sort(key=lambda v: (isinstance(v, str), v.lower() if isinstance(v, str) else v))
    return catalog


def filterable_attributes(catalog: dict[str, dict]) -> dict[str, dict]:
    """Attributes offered in the filter builder; URLs are not useful filter targets."""
    usable = {name: item for name, item in catalog.items() if name != "source_url"}
    return usable or DEFAULT_ATTRIBUTES


def build_filter(conditions, attributes: dict[str, dict]) -> dict | None:
    """Turn (attribute, operator, value) rows into a Knowledge Bases metadata filter.

    A row with no attribute is skipped. Several rows are combined with `andAll`.
    """
    clauses = []
    for attribute, operator, raw in conditions:
        if not attribute:
            continue
        if attribute not in attributes:
            raise ValueError(f"Unknown metadata attribute: {attribute}.")
        if operator not in OPERATORS:
            raise ValueError(f"Unsupported filter operator: {operator}.")
        text = str(raw).strip()
        if not text:
            raise ValueError(f"Enter a value for the {attribute} filter, or set its attribute to (none).")
        if attributes[attribute]["type"] == "NUMBER":
            try:
                value = int(text)
            except ValueError:
                try:
                    value = float(text)
                except ValueError:
                    raise ValueError(f"{attribute} is numeric; enter a number such as 2024.") from None
        else:
            if operator not in TEXT_OPERATORS:
                raise ValueError(f"{attribute} is text; use = or ≠ (range operators are for numbers).")
            value = text
        clauses.append({operator: {"key": attribute, "value": value}})
    if not clauses:
        return None
    return clauses[0] if len(clauses) == 1 else {"andAll": clauses}


def retrieval_configuration(
    number_of_results: int, search_type: str, metadata_filter: dict | None,
    kb_type: str = VECTOR_KB, reranking: str = "Default",
) -> dict:
    """Shared by Retrieve and RetrieveAndGenerate.

    Vector-store knowledge bases take `vectorSearchConfiguration` (with an optional search type override).
    Managed knowledge bases reject it and take `managedSearchConfiguration` (with optional reranking).
    """
    if not 1 <= number_of_results <= 100:
        raise ValueError("Number of results must be between 1 and 100.")
    if search_type not in SEARCH_TYPES:
        raise ValueError(f"Search type must be one of {', '.join(SEARCH_TYPES)}.")
    if reranking not in RERANKING:
        raise ValueError(f"Reranking must be one of {', '.join(RERANKING)}.")
    if kb_type not in (VECTOR_KB, MANAGED_KB):
        raise ValueError("Choose Vector store or Managed as the knowledge base type.")
    config: dict = {"numberOfResults": number_of_results}
    if metadata_filter:
        config["filter"] = metadata_filter
    if kb_type == MANAGED_KB:
        if reranking != "Default":
            config["rerankingModelType"] = reranking
        return {"managedSearchConfiguration": config}
    if search_type != "Default":
        config["overrideSearchType"] = search_type
    return {"vectorSearchConfiguration": config}


def validate_inputs(kb_id: str, query: str) -> tuple[str, str]:
    kb_id, query = kb_id.strip(), query.strip()
    if not KB_ID_PATTERN.fullmatch(kb_id):
        raise ValueError("Enter the 10-character knowledge base ID from the Bedrock console.")
    if not query:
        raise ValueError("Question must not be blank.")
    return kb_id, query


def build_retrieve_request(kb_id: str, query: str, retrieval_config: dict) -> dict:
    kb_id, query = validate_inputs(kb_id, query)
    return {
        "knowledgeBaseId": kb_id,
        "retrievalQuery": {"text": query},
        "retrievalConfiguration": retrieval_config,
    }


def build_generate_request(
    kb_id: str, query: str, model_arn: str, retrieval_config: dict,
    max_tokens: int = 512, temperature: float = 0.2,
) -> dict:
    kb_id, query = validate_inputs(kb_id, query)
    if max_tokens < 1 or not 0 <= temperature <= 1:
        raise ValueError("Max tokens must be positive and temperature must be 0 to 1.")
    return {
        "input": {"text": query},
        "retrieveAndGenerateConfiguration": {
            "type": "KNOWLEDGE_BASE",
            "knowledgeBaseConfiguration": {
                "knowledgeBaseId": kb_id,
                "modelArn": model_arn,
                "retrievalConfiguration": retrieval_config,
                "generationConfiguration": {
                    "inferenceConfig": {"textInferenceConfig": {"maxTokens": max_tokens, "temperature": temperature}},
                },
            },
        },
    }


def model_arn_for(model_id: str, region: str, account: str = "<ACCOUNT_ID>", partition: str = "aws") -> str:
    """RetrieveAndGenerate needs an ARN: an inference profile ARN or a foundation model ARN."""
    model_id = model_id.strip()
    if not model_id:
        raise ValueError("Enter a generation model or inference profile ID.")
    if model_id.startswith("arn:"):
        return model_id
    if model_id.split(".", 1)[0] in PROFILE_PREFIXES:
        return f"arn:{partition}:bedrock:{region}:{account}:inference-profile/{model_id}"
    return f"arn:{partition}:bedrock:{region}::foundation-model/{model_id}"


def make_session(profile: str, region: str):
    return boto3.Session(profile_name=profile, region_name=region)


def resolve_model_arn(session, model_id: str) -> str:
    """Look up the caller's account (needs no IAM permission) to build an inference profile ARN."""
    model_id = model_id.strip()
    if model_id.startswith("arn:") or model_id.split(".", 1)[0] not in PROFILE_PREFIXES:
        return model_arn_for(model_id, session.region_name)
    with closing(session.client("sts", config=CLIENT_CONFIG)) as sts:
        identity = sts.get_caller_identity()
    return model_arn_for(
        model_id, session.region_name, account=identity["Account"], partition=identity["Arn"].split(":")[1],
    )


def _timed(method, request: dict) -> dict:
    start = time.perf_counter()
    response = method(**request)
    return {"request": request, "response": response, "ms": round((time.perf_counter() - start) * 1000)}


def run_retrieve(session, request: dict) -> dict:
    with closing(session.client("bedrock-agent-runtime", config=CLIENT_CONFIG)) as client:
        return _timed(client.retrieve, request)


def run_retrieve_and_generate(session, request: dict) -> dict:
    with closing(session.client("bedrock-agent-runtime", config=CLIENT_CONFIG)) as client:
        return _timed(client.retrieve_and_generate, request)


def detect_kb_type(session, kb_id: str) -> str:
    """Ask the control plane whether a knowledge base is vector-store or managed (needs bedrock:GetKnowledgeBase)."""
    with closing(session.client("bedrock-agent", config=CLIENT_CONFIG)) as client:
        configuration = client.get_knowledge_base(knowledgeBaseId=kb_id)["knowledgeBase"]["knowledgeBaseConfiguration"]
    kind = configuration.get("type", "")
    if kind not in CONTROL_PLANE_TYPES:
        raise ValueError(f"This lab supports vector-store and managed knowledge bases; this one is type {kind or 'unknown'}.")
    return CONTROL_PLANE_TYPES[kind]


def list_knowledge_bases(session) -> list[dict]:
    """List knowledge bases in the session's region (control plane; invokes no model)."""
    with closing(session.client("bedrock-agent", config=CLIENT_CONFIG)) as client:
        pages = client.get_paginator("list_knowledge_bases").paginate()
        return [kb for page in pages for kb in page.get("knowledgeBaseSummaries", [])]


def error_hint(code: str) -> str:
    return ERROR_HINTS.get(code, "")


def location_uri(location: dict | None) -> str:
    """Return the source URI of a retrieved chunk, whatever the data source type."""
    for value in (location or {}).values():
        if isinstance(value, dict):
            uri = value.get("uri") or value.get("url")
            if uri:
                return uri
    return ""


def user_metadata(metadata: dict | None) -> dict:
    """Drop Bedrock's internal `x-amz-bedrock-kb-*` keys, keeping the sidecar attributes."""
    return {k: v for k, v in (metadata or {}).items() if not k.startswith("x-amz-bedrock-kb")}


def chunk_title(result: dict) -> str:
    title = user_metadata(result.get("metadata")).get("title")
    if isinstance(title, str) and title:
        return title
    return location_uri(result.get("location")).rsplit("/", 1)[-1] or "Unknown source"


def cited_texts(generate_response: dict) -> set[str]:
    """Chunk texts the generator cited, used to mark retrieved chunks that fed the answer."""
    return {
        reference.get("content", {}).get("text", "")
        for citation in generate_response.get("citations", [])
        for reference in citation.get("retrievedReferences", [])
    } - {""}


def make_code_snippet(profile: str, region: str, retrieve_request: dict | None, generate_request: dict | None) -> str:
    """Minimal boto3 example: profile setup, the call(s), and printing the result."""
    def literal(value) -> str:
        return pprint.pformat(value, sort_dicts=False, width=88)

    parts = [
        "# Retrieve returns chunks; RetrieveAndGenerate also writes a cited answer.\n"
        f"client = boto3.Session(\n    profile_name={profile!r}, region_name={region!r},\n"
        ').client("bedrock-agent-runtime")\n'
    ]
    if retrieve_request:
        parts.append(
            f"\nrequest = {literal(retrieve_request)}\n"
            "response = client.retrieve(**request)\n"
            'for result in response["retrievalResults"]:\n'
            '    print(round(result["score"], 3), result["content"]["text"][:200])\n'
        )
    if generate_request:
        parts.append(
            f"\nrequest = {literal(generate_request)}\n"
            "response = client.retrieve_and_generate(**request)\n"
            'print(response["output"]["text"])\n'
            'for citation in response["citations"]:\n'
            '    for reference in citation["retrievedReferences"]:\n'
            '        print(reference["location"], reference["content"]["text"][:200])\n'
        )
    return "".join(parts)
