import base64
import importlib.util
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")
spec = importlib.util.spec_from_file_location("gateway_handler", Path(__file__).parents[1] / "handler.py")
handler = importlib.util.module_from_spec(spec)
spec.loader.exec_module(handler)


class HandlerTests(unittest.TestCase):
    def setUp(self):
        self.context = Mock(aws_request_id="test")
        self.client = Mock()
        self.client.converse.return_value = {"output": {"message": {"content": [{"text": "Hello"}]}}, "usage": {"inputTokens": 1}, "stopReason": "end_turn"}
        self.client_patch = patch.object(handler, "client", self.client)
        self.client_patch.start()
        self.addCleanup(self.client_patch.stop)
        self.history = Mock()
        self.history_patch = patch.object(handler, "history_client", self.history)
        self.history_patch.start()
        self.addCleanup(self.history_patch.stop)
        self.env_patch = patch.dict(os.environ, {"MODEL_ID": "test-model", "HISTORY_TABLE": "history"})
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)

    def test_success_and_base64(self):
        body = base64.b64encode(json.dumps({"prompt": " hi "}).encode()).decode()
        result = handler.lambda_handler({"body": body, "isBase64Encoded": True}, self.context)
        self.assertEqual(result["statusCode"], 200)
        self.assertEqual(json.loads(result["body"])["answer"], "Hello")
        self.assertEqual(self.client.converse.call_args.kwargs["inferenceConfig"]["maxTokens"], 512)
        self.assertEqual(self.client.converse.call_args.kwargs["messages"][0]["content"][0]["text"], "hi")
        item = self.history.put_item.call_args.kwargs["Item"]
        self.assertEqual(item["requestId"], {"S": "test"})
        self.assertEqual(item["prompt"], {"S": "hi"})
        self.assertEqual(item["answer"], {"S": "Hello"})
        self.assertIn("createdAt", item)
        self.assertTrue(json.loads(result["body"])["historySaved"])

    def test_history_record_expires_after_retention_period(self):
        with patch.dict(os.environ, {"HISTORY_RETENTION_DAYS": "7"}):
            before = int(datetime.now(timezone.utc).timestamp())
            handler.lambda_handler({"body": '{"prompt":"hi"}'}, self.context)
            after = int(datetime.now(timezone.utc).timestamp())
        expires = self.history.put_item.call_args.kwargs["Item"]["expiresAt"]
        self.assertEqual(list(expires), ["N"])  # TTL attributes must be Numbers
        self.assertTrue(before + 7 * 86400 <= int(expires["N"]) <= after + 7 * 86400)

    def test_retention_defaults_to_30_days(self):
        os.environ.pop("HISTORY_RETENTION_DAYS", None)
        before = int(datetime.now(timezone.utc).timestamp())
        handler.lambda_handler({"body": '{"prompt":"hi"}'}, self.context)
        expires = int(self.history.put_item.call_args.kwargs["Item"]["expiresAt"]["N"])
        self.assertTrue(before + 30 * 86400 <= expires <= before + 30 * 86400 + 60)

    def test_invalid_input_never_calls_bedrock(self):
        for body in ("{", "[]", '{"prompt":" "}', json.dumps({"prompt": "x" * 16001})):
            self.assertEqual(handler.lambda_handler({"body": body}, self.context)["statusCode"], 400)
        self.assertEqual(handler.lambda_handler({"body": "x" * 32769}, self.context)["statusCode"], 413)
        self.client.converse.assert_not_called()
        self.history.put_item.assert_not_called()

    def test_service_errors_are_sanitized(self):
        from botocore.exceptions import ClientError
        self.client.converse.side_effect = ClientError({"Error": {"Code": "ThrottlingException", "Message": "secret"}}, "Converse")
        result = handler.lambda_handler({"body": '{"prompt":"hello"}'}, self.context)
        self.assertEqual(result["statusCode"], 503)
        self.assertNotIn("secret", result["body"])

    def test_history_failure_still_returns_the_answer(self):
        from botocore.exceptions import ClientError
        self.history.put_item.side_effect = ClientError({"Error": {"Code": "AccessDeniedException", "Message": "secret"}}, "PutItem")
        result = handler.lambda_handler({"body": '{"prompt":"hello"}'}, self.context)
        body = json.loads(result["body"])
        self.assertEqual(result["statusCode"], 200)
        self.assertEqual(body["answer"], "Hello")
        self.assertFalse(body["historySaved"])
        self.assertNotIn("secret", result["body"])

    def test_invalid_retention_setting_does_not_hide_the_answer(self):
        for value in ("0", "abc", "-5"):
            with self.subTest(value=value), patch.dict(os.environ, {"HISTORY_RETENTION_DAYS": value}):
                self.history.put_item.reset_mock()
                result = handler.lambda_handler({"body": '{"prompt":"hello"}'}, self.context)
                self.assertEqual(result["statusCode"], 200)
                self.assertFalse(json.loads(result["body"])["historySaved"])
                self.history.put_item.assert_not_called()


if __name__ == "__main__":
    unittest.main()
