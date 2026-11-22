"""Project 1: explore Amazon Bedrock Converse for AIP-C01 preparation."""

import argparse
from collections.abc import Iterator
from contextlib import closing
from pathlib import Path
import sys

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from dotenv import dotenv_values


DEFAULT_SYSTEM_PROMPT = "You are a concise AWS certification study assistant."


def load_settings(required: tuple[str, ...] = ("AWS_PROFILE", "AWS_REGION", "BEDROCK_MODEL_ID")) -> dict:
    """Read non-secret settings; credentials are resolved by the named AWS profile."""
    values = dotenv_values(Path(__file__).with_name(".env"), interpolate=False)
    settings = {
        name: (values.get(name) or "").strip()
        for name in (
            "AWS_PROFILE", "AWS_REGION", "BEDROCK_MODEL_ID", "GATEWAY_URL", "GATEWAY_INVOKE_ARN",
            "KNOWLEDGE_BASE_ID",
        )
    }
    missing = [name for name in required if not (settings.get(name) or "").strip()]
    if missing:
        raise ValueError(f"Fill in {', '.join(missing)} in .env before running.")
    return settings


def build_request(
    prompt: str,
    model_id: str,
    max_tokens: int = 512,
    temperature: float = 0.2,
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
) -> dict:
    """Build the same Converse request for the CLI and Streamlit app."""
    if not prompt.strip():
        raise ValueError("Prompt must not be blank.")
    if max_tokens < 1 or not 0 <= temperature <= 1:
        raise ValueError("Max tokens must be positive and temperature must be 0 to 1.")
    request = {
        "modelId": model_id,
        "messages": [{"role": "user", "content": [{"text": prompt}]}],
        "inferenceConfig": {"maxTokens": max_tokens, "temperature": temperature},
    }
    if system_prompt.strip():
        request["system"] = [{"text": system_prompt}]
    return request


def runtime_client(settings: dict):
    """Create an inference client using the selected AWS CLI profile."""
    session = boto3.Session(
        profile_name=settings["AWS_PROFILE"], region_name=settings["AWS_REGION"],
    )
    return session.client(
        "bedrock-runtime",
        config=Config(
            retries={"mode": "adaptive", "total_max_attempts": 3},
            connect_timeout=10,
            read_timeout=120,
        ),
    )


def invoke_converse(settings: dict, request: dict) -> dict:
    """Invoke Bedrock using credentials managed by the selected AWS CLI profile."""
    with closing(runtime_client(settings)) as client:
        return client.converse(**request)


def stream_converse(settings: dict, request: dict) -> Iterator[dict]:
    """Yield decoded ConverseStream events and close the connection on exit."""
    with closing(runtime_client(settings)) as client:
        response = client.converse_stream(**request)
        with closing(response["stream"]) as stream:
            yield from stream


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "prompt", nargs="?",
        default="Explain Amazon Bedrock Converse in three bullet points.",
    )
    parser.add_argument("--max-tokens", type=int, default=512)
    parser.add_argument("--temperature", type=float, default=0.2)
    args = parser.parse_args()
    if not args.prompt.strip():
        parser.error("prompt must not be blank")
    if args.max_tokens < 1 or not 0 <= args.temperature <= 1:
        parser.error("max-tokens must be positive and temperature must be 0 to 1")

    try:
        settings = load_settings()
        request = build_request(
            args.prompt, settings["BEDROCK_MODEL_ID"], args.max_tokens, args.temperature,
        )
        response = invoke_converse(settings, request)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1
    except (BotoCoreError, ClientError) as error:
        print(f"Bedrock request failed: {error}", file=sys.stderr)
        return 1

    for block in response["output"]["message"]["content"]:
        if "text" in block:
            print(block["text"])
    usage = response["usage"]
    print(f"\nModel: {settings['BEDROCK_MODEL_ID']}")
    print(f"Tokens: {usage['inputTokens']} input, {usage['outputTokens']} output, "
          f"{usage['totalTokens']} total")
    print(f"Latency: {response['metrics']['latencyMs']} ms")
    print(f"Stop reason: {response['stopReason']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
