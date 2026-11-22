from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parents[1]))
import knowledge_base as kb  # noqa: E402

ATTRIBUTES = {
    "year": {"type": "NUMBER", "values": [2020, 2024]},
    "topic": {"type": "STRING", "values": ["rag"]},
}
CONFIG = {"vectorSearchConfiguration": {"numberOfResults": 5}}


class FilterTests(unittest.TestCase):
    def test_no_rows_means_no_filter(self):
        self.assertIsNone(kb.build_filter([(None, "equals", ""), (None, "equals", "x")], ATTRIBUTES))

    def test_numeric_value_is_converted(self):
        result = kb.build_filter([("year", "greaterThanOrEquals", " 2024 ")], ATTRIBUTES)
        self.assertEqual(result, {"greaterThanOrEquals": {"key": "year", "value": 2024}})

    def test_two_rows_are_combined_with_and(self):
        result = kb.build_filter([("year", "equals", "2020"), ("topic", "equals", "rag")], ATTRIBUTES)
        self.assertEqual([next(iter(c)) for c in result["andAll"]], ["equals", "equals"])

    def test_invalid_rows_are_rejected(self):
        for row in [("year", "equals", "abc"), ("year", "equals", " "), ("topic", "greaterThan", "a"),
                    ("missing", "equals", "x"), ("year", "contains", "1")]:
            with self.subTest(row=row), self.assertRaises(ValueError):
                kb.build_filter([row], ATTRIBUTES)


class RequestTests(unittest.TestCase):
    def test_retrieval_configuration(self):
        config = kb.retrieval_configuration(3, "HYBRID", {"equals": {"key": "a", "value": "b"}})
        self.assertEqual(config["vectorSearchConfiguration"], {
            "numberOfResults": 3, "overrideSearchType": "HYBRID", "filter": {"equals": {"key": "a", "value": "b"}},
        })
        self.assertNotIn("overrideSearchType", kb.retrieval_configuration(3, "Default", None)["vectorSearchConfiguration"])
        for count in (0, 101):
            with self.assertRaises(ValueError):
                kb.retrieval_configuration(count, "Default", None)

    def test_retrieve_request_validates_inputs(self):
        request = kb.build_retrieve_request(" ABCDE12345 ", " why? ", CONFIG)
        self.assertEqual(request["knowledgeBaseId"], "ABCDE12345")
        self.assertEqual(request["retrievalQuery"], {"text": "why?"})
        for kb_id, query in [("short", "q"), ("ABCDE12345", "  ")]:
            with self.assertRaises(ValueError):
                kb.build_retrieve_request(kb_id, query, CONFIG)

    def test_generate_request_shape(self):
        request = kb.build_generate_request("ABCDE12345", "q", "arn:x", CONFIG, 256, 0.5)
        knowledge_base = request["retrieveAndGenerateConfiguration"]["knowledgeBaseConfiguration"]
        self.assertEqual(request["input"], {"text": "q"})
        self.assertEqual(knowledge_base["modelArn"], "arn:x")
        self.assertEqual(knowledge_base["retrievalConfiguration"], CONFIG)
        self.assertEqual(
            knowledge_base["generationConfiguration"]["inferenceConfig"]["textInferenceConfig"],
            {"maxTokens": 256, "temperature": 0.5},
        )
        with self.assertRaises(ValueError):
            kb.build_generate_request("ABCDE12345", "q", "arn:x", CONFIG, 0, 0.5)


class KnowledgeBaseTypeTests(unittest.TestCase):
    FILTER = {"equals": {"key": "year", "value": 2024}}

    def test_vector_store_uses_vector_search_configuration(self):
        config = kb.retrieval_configuration(4, "HYBRID", self.FILTER, kb.VECTOR_KB, "NONE")
        self.assertEqual(list(config), ["vectorSearchConfiguration"])
        self.assertEqual(config["vectorSearchConfiguration"], {
            "numberOfResults": 4, "filter": self.FILTER, "overrideSearchType": "HYBRID",
        })

    def test_managed_uses_managed_search_configuration(self):
        config = kb.retrieval_configuration(4, "HYBRID", self.FILTER, kb.MANAGED_KB, "MANAGED")
        self.assertEqual(config, {"managedSearchConfiguration": {
            "numberOfResults": 4, "filter": self.FILTER, "rerankingModelType": "MANAGED",
        }})
        default = kb.retrieval_configuration(5, "Default", None, kb.MANAGED_KB)
        self.assertEqual(default, {"managedSearchConfiguration": {"numberOfResults": 5}})

    def test_invalid_type_or_reranking_rejected(self):
        with self.assertRaises(ValueError):
            kb.retrieval_configuration(5, "Default", None, "Kendra")
        with self.assertRaises(ValueError):
            kb.retrieval_configuration(5, "Default", None, kb.MANAGED_KB, "CUSTOM")

    def test_detect_kb_type(self):
        session = MagicMock()
        client = session.client.return_value
        for kind, expected in (("VECTOR", kb.VECTOR_KB), ("MANAGED", kb.MANAGED_KB)):
            client.get_knowledge_base.return_value = {"knowledgeBase": {"knowledgeBaseConfiguration": {"type": kind}}}
            self.assertEqual(kb.detect_kb_type(session, "ABCDE12345"), expected)
        client.get_knowledge_base.return_value = {"knowledgeBase": {"knowledgeBaseConfiguration": {"type": "KENDRA"}}}
        with self.assertRaises(ValueError):
            kb.detect_kb_type(session, "ABCDE12345")

    def test_requests_match_the_boto3_api_model_for_both_types(self):
        """Validate against botocore's own service model (offline; no AWS call)."""
        from botocore.validate import validate_parameters
        import boto3
        model = boto3.client(
            "bedrock-agent-runtime", region_name="us-east-1",
            aws_access_key_id="test", aws_secret_access_key="test",
        ).meta.service_model
        for kb_type in (kb.VECTOR_KB, kb.MANAGED_KB):
            config = kb.retrieval_configuration(3, "Default", self.FILTER, kb_type, "Default")
            requests = {
                "Retrieve": kb.build_retrieve_request("ABCDE12345", "q", config),
                "RetrieveAndGenerate": kb.build_generate_request("ABCDE12345", "q", "arn:aws:bedrock:r::foundation-model/m", config),
            }
            for operation, request in requests.items():
                with self.subTest(kb_type=kb_type, operation=operation):
                    validate_parameters(request, model.operation_model(operation).input_shape)


class ModelArnTests(unittest.TestCase):
    def test_arn_forms(self):
        self.assertEqual(kb.model_arn_for("arn:aws:bedrock:r:1:inference-profile/p", "r"), "arn:aws:bedrock:r:1:inference-profile/p")
        self.assertEqual(
            kb.model_arn_for("apac.amazon.nova-micro-v1:0", "ap-south-1", account="123456789012"),
            "arn:aws:bedrock:ap-south-1:123456789012:inference-profile/apac.amazon.nova-micro-v1:0",
        )
        self.assertEqual(
            kb.model_arn_for("amazon.nova-micro-v1:0", "us-east-1"),
            "arn:aws:bedrock:us-east-1::foundation-model/amazon.nova-micro-v1:0",
        )
        with self.assertRaises(ValueError):
            kb.model_arn_for("  ", "us-east-1")

    def test_profile_id_looks_up_the_account(self):
        session = MagicMock(region_name="ap-south-1")
        session.client.return_value.get_caller_identity.return_value = {
            "Account": "123456789012", "Arn": "arn:aws:sts::123456789012:assumed-role/r/s",
        }
        self.assertEqual(
            kb.resolve_model_arn(session, "apac.amazon.nova-micro-v1:0"),
            "arn:aws:bedrock:ap-south-1:123456789012:inference-profile/apac.amazon.nova-micro-v1:0",
        )
        session.reset_mock()
        kb.resolve_model_arn(session, "amazon.nova-micro-v1:0")
        session.client.assert_not_called()


class ResponseHelperTests(unittest.TestCase):
    RESULT = {
        "content": {"text": "chunk"},
        "location": {"type": "S3", "s3Location": {"uri": "s3://bucket/resources/paper.pdf"}},
        "metadata": {"title": "A Paper", "year": 2020, "x-amz-bedrock-kb-chunk-id": "1"},
    }

    def test_chunk_helpers(self):
        self.assertEqual(kb.location_uri(self.RESULT["location"]), "s3://bucket/resources/paper.pdf")
        self.assertEqual(kb.user_metadata(self.RESULT["metadata"]), {"title": "A Paper", "year": 2020})
        self.assertEqual(kb.chunk_title(self.RESULT), "A Paper")
        self.assertEqual(kb.chunk_title({"location": self.RESULT["location"]}), "paper.pdf")
        self.assertEqual(kb.chunk_title({}), "Unknown source")

    def test_cited_texts(self):
        response = {"citations": [{"retrievedReferences": [{"content": {"text": "chunk"}}, {"content": {}}]}]}
        self.assertEqual(kb.cited_texts(response), {"chunk"})
        self.assertEqual(kb.cited_texts({}), set())

    def test_snippet_contains_calls_and_no_secrets(self):
        retrieve = kb.build_retrieve_request("ABCDE12345", "q", CONFIG)
        generate = kb.build_generate_request("ABCDE12345", "q", "arn:x", CONFIG)
        snippet = kb.make_code_snippet("agent", "ap-south-1", retrieve, generate)
        compile(snippet, "<snippet>", "exec")
        self.assertIn("client.retrieve(**request)", snippet)
        self.assertIn("client.retrieve_and_generate(**request)", snippet)
        self.assertNotIn("retrieve_and_generate", kb.make_code_snippet("agent", "r", retrieve, None))


class CatalogTests(unittest.TestCase):
    def test_reads_repository_sidecars(self):
        catalog = kb.load_metadata_catalog(Path(__file__).parents[1] / "resources")
        if not catalog:
            self.skipTest("No metadata sidecar files in resources/.")
        self.assertEqual(catalog["year"]["type"], "NUMBER")
        self.assertEqual(catalog["topic"]["type"], "STRING")
        self.assertNotIn("source_url", kb.filterable_attributes(catalog))

    def test_bad_files_are_skipped_and_empty_falls_back(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / "bad.pdf.metadata.json").write_text("not json", encoding="utf-8")
            catalog = kb.load_metadata_catalog(Path(folder))
        self.assertEqual(catalog, {})
        self.assertIs(kb.filterable_attributes(catalog), kb.DEFAULT_ATTRIBUTES)


if __name__ == "__main__":
    unittest.main()
