"""IAM-protected API Gateway HTTP API Lambda integration."""
import base64
import binascii
import json
import logging
import os
from datetime import datetime, timezone

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
client = boto3.client("bedrock-runtime", config=Config(
    connect_timeout=3, read_timeout=20, retries={"total_max_attempts": 1, "mode": "standard"},
))

history_client = boto3.client("dynamodb", config=Config(
    connect_timeout=2, read_timeout=2, retries={"total_max_attempts": 1, "mode": "standard"},
))


def retention_days() -> int:
    """Days to keep a history record; set by the HistoryRetentionDays stack parameter."""
    days = int(os.environ.get("HISTORY_RETENTION_DAYS", "30"))
    if days < 1:
        raise ValueError("HISTORY_RETENTION_DAYS must be at least 1.")
    return days


def response(status, payload):
    return {"statusCode": status, "headers": {"Content-Type": "application/json"}, "body": json.dumps(payload)}


def lambda_handler(event, context):
    request_id = getattr(context, "aws_request_id", "unknown")
    try:
        body = event.get("body") or ""
        if event.get("isBase64Encoded"):
            body = base64.b64decode(body, validate=True).decode("utf-8")
        if len(body.encode("utf-8")) > 32768:
            return response(413, {"error": "Request body is too large."})
        data = json.loads(body)
        prompt = data.get("prompt") if isinstance(data, dict) else None
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 16000:
            return response(400, {"error": "prompt must be a non-empty string of at most 16000 characters."})
    except (ValueError, UnicodeError, binascii.Error, AttributeError):
        return response(400, {"error": "Invalid JSON request body."})

    try:
        result = client.converse(
            modelId=os.environ["MODEL_ID"],
            messages=[{"role": "user", "content": [{"text": prompt.strip()}]}],
            inferenceConfig={"maxTokens": 512},
        )
        text = "\n".join(block["text"] for block in result["output"]["message"]["content"] if "text" in block)
    except ClientError as error:
        code = error.response.get("Error", {}).get("Code", "Unknown")
        logger.warning("request_id=%s bedrock_error=%s", request_id, code)
        if code in {"ThrottlingException", "ServiceUnavailableException", "ModelNotReadyException"}:
            return response(503, {"error": "Bedrock is temporarily unavailable. Try again."})
        return response(502, {"error": "Bedrock could not process the request."})
    except (BotoCoreError, KeyError, TypeError):
        logger.exception("request_id=%s invocation_failed", request_id)
        return response(502, {"error": "The model request failed."})

    # The model call already succeeded and was billed, so a history failure must not hide the answer.
    history_saved = True
    try:
        now = datetime.now(timezone.utc)
        history_client.put_item(
            TableName=os.environ["HISTORY_TABLE"],
            Item={
                "requestId": {"S": request_id},
                "createdAt": {"S": now.isoformat()},
                # DynamoDB TTL reads this attribute: epoch seconds, stored as a Number.
                "expiresAt": {"N": str(int(now.timestamp()) + retention_days() * 86400)},
                "modelId": {"S": os.environ["MODEL_ID"]},
                "prompt": {"S": prompt.strip()},
                "answer": {"S": text or ""},
            },
            ConditionExpression="attribute_not_exists(requestId)",
        )
    except (BotoCoreError, ClientError, KeyError, ValueError) as error:
        code = error.response.get("Error", {}).get("Code", "Unknown") if isinstance(error, ClientError) else type(error).__name__
        logger.warning("request_id=%s history_write_failed=%s", request_id, code)
        history_saved = False

    logger.info("request_id=%s status=success history_saved=%s", request_id, history_saved)
    return response(200, {
        "answer": text, "usage": result.get("usage", {}), "stopReason": result.get("stopReason"),
        "historySaved": history_saved,
    })
