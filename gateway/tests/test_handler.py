import base64
import importlib.util
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
        self.env_patch = patch.dict(os.environ, {"MODEL_ID": "test-model"})
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)

    def test_success_and_base64(self):
        body = base64.b64encode(json.dumps({"prompt": " hi "}).encode()).decode()
        result = handler.lambda_handler({"body": body, "isBase64Encoded": True}, self.context)
        self.assertEqual(result["statusCode"], 200)
        self.assertEqual(json.loads(result["body"])["answer"], "Hello")
        self.assertEqual(self.client.converse.call_args.kwargs["inferenceConfig"]["maxTokens"], 512)
        self.assertEqual(self.client.converse.call_args.kwargs["messages"][0]["content"][0]["text"], "hi")

    def test_invalid_input_never_calls_bedrock(self):
        for body in ("{", "[]", '{"prompt":" "}', json.dumps({"prompt": "x" * 16001})):
            self.assertEqual(handler.lambda_handler({"body": body}, self.context)["statusCode"], 400)
        self.assertEqual(handler.lambda_handler({"body": "x" * 32769}, self.context)["statusCode"], 413)
        self.client.converse.assert_not_called()

    def test_service_errors_are_sanitized(self):
        from botocore.exceptions import ClientError
        self.client.converse.side_effect = ClientError({"Error": {"Code": "ThrottlingException", "Message": "secret"}}, "Converse")
        result = handler.lambda_handler({"body": '{"prompt":"hello"}'}, self.context)
        self.assertEqual(result["statusCode"], 503)
        self.assertNotIn("secret", result["body"])


if __name__ == "__main__":
    unittest.main()
