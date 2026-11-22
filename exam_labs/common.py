"""Shared helpers: settings, Bedrock clients, and a small Converse wrapper used by every demo."""

from __future__ import annotations

import time

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from converse import load_settings

BEDROCK_ERRORS = (BotoCoreError, ClientError)


def get_settings() -> dict | None:
    """Return .env settings, or None when the connection values are not filled in."""
    try:
        return load_settings()
    except ValueError:
        return None


def make_session(settings: dict):
    return boto3.Session(profile_name=settings["AWS_PROFILE"], region_name=settings["AWS_REGION"])


def runtime_client(settings: dict, max_attempts: int = 3):
    """bedrock-runtime client with bounded SDK retries (standard mode) and timeouts."""
    return make_session(settings).client(
        "bedrock-runtime",
        config=Config(retries={"mode": "standard", "total_max_attempts": max_attempts},
                      connect_timeout=10, read_timeout=60),
    )


def control_client(settings: dict):
    return make_session(settings).client("bedrock")


def converse_once(
    settings: dict,
    prompt: str,
    system: str | None = None,
    model_id: str | None = None,
    max_tokens: int = 512,
    temperature: float = 0.0,
    guardrail: dict | None = None,
    max_attempts: int = 3,
) -> dict:
    """One Converse call, returned as a flat dict: text, usage, latency_ms, wall_ms, stop_reason."""
    request = {
        "modelId": model_id or settings["BEDROCK_MODEL_ID"],
        "messages": [{"role": "user", "content": [{"text": prompt}]}],
        "inferenceConfig": {"maxTokens": max_tokens, "temperature": temperature},
    }
    if system and system.strip():
        request["system"] = [{"text": system}]
    if guardrail:
        request["guardrailConfig"] = guardrail
    started = time.perf_counter()
    response = runtime_client(settings, max_attempts).converse(**request)
    wall_ms = int((time.perf_counter() - started) * 1000)
    blocks = response["output"]["message"]["content"]
    return {
        "text": "".join(block.get("text", "") for block in blocks),
        "usage": response["usage"],
        "latency_ms": response["metrics"]["latencyMs"],
        "wall_ms": wall_ms,
        "stop_reason": response["stopReason"],
        "request": request,
        "raw": response,
    }


def error_code(error: Exception) -> str:
    if isinstance(error, ClientError):
        return error.response.get("Error", {}).get("Code", "ClientError")
    return type(error).__name__


def describe_error(error: Exception) -> str:
    """One line that names the error code, for display next to the exception text."""
    return f"{error_code(error)}: {error}"
