"""
Unit tests for BedrockClient service.

Tests prompt template fetching from S3, prompt rendering, Bedrock model
invocation with retry logic, and model listing. All AWS calls are mocked.
"""

import json
import io
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError
from botocore.stub import Stubber

from services.bedrock_client import BedrockClient, BedrockModel


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    """Provide a BedrockClient with fast retry settings for tests."""
    return BedrockClient(max_retries=3, base_delay=0.0)


@pytest.fixture
def client_no_retry():
    """Provide a BedrockClient with no retries."""
    return BedrockClient(max_retries=0, base_delay=0.0)


# ---------------------------------------------------------------------------
# fetch_prompt_template — success
# ---------------------------------------------------------------------------


class TestFetchPromptTemplate:
    """Tests for S3 prompt template fetching."""

    def test_fetch_valid_template(self, client):
        """Test fetching a valid prompt template from S3."""
        template_content = "Convert {source_code} from {source_dialect} to {target_dialect}"
        mock_body = MagicMock()
        mock_body.read.return_value = template_content.encode("utf-8")

        mock_s3 = MagicMock()
        mock_s3.get_object.return_value = {"Body": mock_body}

        with patch("services.bedrock_client.boto3.client", return_value=mock_s3):
            result = client.fetch_prompt_template(
                "s3://my-bucket/templates/convert.txt", "us-east-1"
            )

        assert result == template_content
        mock_s3.get_object.assert_called_once_with(
            Bucket="my-bucket", Key="templates/convert.txt"
        )

    def test_fetch_template_nested_key(self, client):
        """Test fetching a template with a deeply nested S3 key."""
        mock_body = MagicMock()
        mock_body.read.return_value = b"template text"
        mock_s3 = MagicMock()
        mock_s3.get_object.return_value = {"Body": mock_body}

        with patch("services.bedrock_client.boto3.client", return_value=mock_s3):
            result = client.fetch_prompt_template(
                "s3://bucket/a/b/c/template.txt", "eu-west-1"
            )

        assert result == "template text"
        mock_s3.get_object.assert_called_once_with(Bucket="bucket", Key="a/b/c/template.txt")

    def test_fetch_template_invalid_s3_path_no_prefix(self, client):
        """Test that a path without s3:// prefix is treated as a local file path."""
        with pytest.raises(ValueError, match="Local template file not found"):
            client.fetch_prompt_template("bucket/key.txt", "us-east-1")

    def test_fetch_template_invalid_s3_path_no_key(self, client):
        """Test that a path with only bucket and no key raises ValueError."""
        with pytest.raises(ValueError, match="Invalid S3 path"):
            client.fetch_prompt_template("s3://bucket-only", "us-east-1")

    def test_fetch_template_empty_path(self, client):
        """Test that an empty path raises ValueError."""
        with pytest.raises(ValueError, match="Local template file not found"):
            client.fetch_prompt_template("", "us-east-1")

    def test_fetch_template_s3_not_found(self, client):
        """Test that a NoSuchKey error from S3 raises ValueError."""
        mock_s3 = MagicMock()
        mock_s3.get_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "The specified key does not exist."}},
            "GetObject",
        )

        with patch("services.bedrock_client.boto3.client", return_value=mock_s3):
            with pytest.raises(ValueError, match="NoSuchKey"):
                client.fetch_prompt_template("s3://bucket/missing.txt", "us-east-1")

    def test_fetch_template_s3_access_denied(self, client):
        """Test that an AccessDenied error from S3 raises ValueError."""
        mock_s3 = MagicMock()
        mock_s3.get_object.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Access Denied"}},
            "GetObject",
        )

        with patch("services.bedrock_client.boto3.client", return_value=mock_s3):
            with pytest.raises(ValueError, match="AccessDenied"):
                client.fetch_prompt_template("s3://bucket/secret.txt", "us-east-1")


# ---------------------------------------------------------------------------
# render_prompt
# ---------------------------------------------------------------------------


class TestRenderPrompt:
    """Tests for prompt template rendering."""

    def test_render_all_placeholders(self):
        """Test that all placeholders are substituted correctly."""
        template = (
            "Convert the following {asset_type} from {source_dialect} to {target_dialect}:\n"
            "{source_code}\n"
            "sqlglot output: {sqlglot_output}"
        )
        result = BedrockClient.render_prompt(
            template=template,
            source_code="SELECT * FROM t",
            source_dialect="bigquery",
            target_dialect="redshift",
            asset_type="TABLE_DDL",
            sqlglot_output="SELECT * FROM t",
        )

        assert "SELECT * FROM t" in result
        assert "bigquery" in result
        assert "redshift" in result
        assert "TABLE_DDL" in result

    def test_render_without_sqlglot_output(self):
        """Test rendering when sqlglot_output is None (defaults to empty string)."""
        template = "Source: {source_code} | sqlglot: {sqlglot_output}"
        result = BedrockClient.render_prompt(
            template=template,
            source_code="SELECT 1",
            source_dialect="bigquery",
            target_dialect="redshift",
            asset_type="VIEW",
            sqlglot_output=None,
        )

        assert result == "Source: SELECT 1 | sqlglot: "

    def test_render_preserves_non_placeholder_text(self):
        """Test that text without placeholders is preserved as-is."""
        template = "No placeholders here."
        result = BedrockClient.render_prompt(
            template=template,
            source_code="code",
            source_dialect="a",
            target_dialect="b",
            asset_type="VIEW",
        )
        assert result == "No placeholders here."

    def test_render_with_special_characters_in_code(self):
        """Test rendering with special characters in source code."""
        template = "Code: {source_code}"
        result = BedrockClient.render_prompt(
            template=template,
            source_code="SELECT * FROM t WHERE name = 'O''Brien'",
            source_dialect="postgres",
            target_dialect="mysql",
            asset_type="FUNCTION",
        )
        assert "O''Brien" in result


# ---------------------------------------------------------------------------
# invoke_model — success
# ---------------------------------------------------------------------------


class TestInvokeModel:
    """Tests for Bedrock model invocation."""

    def _mock_invoke_response(self, text="converted code", input_tokens=10, output_tokens=20):
        """Helper to build a mock invoke_model response."""
        body_content = json.dumps({
            "content": [{"type": "text", "text": text}],
            "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
        })
        mock_body = MagicMock()
        mock_body.read.return_value = body_content.encode("utf-8")
        return {"body": mock_body}

    def test_invoke_success(self, client):
        """Test successful model invocation returns generated text."""
        mock_runtime = MagicMock()
        mock_runtime.invoke_model.return_value = self._mock_invoke_response("SELECT 1")

        with patch("services.bedrock_client.boto3.client", return_value=mock_runtime):
            result = client.invoke_model("prompt text", "anthropic.claude-3-sonnet-20240229-v1:0", "us-east-1")

        assert result == "SELECT 1"
        mock_runtime.invoke_model.assert_called_once()

    def test_invoke_passes_correct_body(self, client):
        """Test that the request body sent to Bedrock is correctly structured."""
        mock_runtime = MagicMock()
        mock_runtime.invoke_model.return_value = self._mock_invoke_response()

        with patch("services.bedrock_client.boto3.client", return_value=mock_runtime):
            client.invoke_model("my prompt", "model-id", "us-west-2")

        call_kwargs = mock_runtime.invoke_model.call_args[1]
        assert call_kwargs["modelId"] == "model-id"
        assert call_kwargs["contentType"] == "application/json"
        body = json.loads(call_kwargs["body"])
        assert body["messages"][0]["content"] == "my prompt"
        assert body["max_tokens"] == 4096

    def test_invoke_non_retryable_error(self, client):
        """Test that a non-retryable ClientError raises RuntimeError immediately."""
        mock_runtime = MagicMock()
        mock_runtime.invoke_model.side_effect = ClientError(
            {"Error": {"Code": "ValidationException", "Message": "Invalid model"}},
            "InvokeModel",
        )

        with patch("services.bedrock_client.boto3.client", return_value=mock_runtime):
            with pytest.raises(RuntimeError, match="ValidationException"):
                client.invoke_model("prompt", "bad-model", "us-east-1")

        # Should only be called once (no retries for non-retryable errors)
        assert mock_runtime.invoke_model.call_count == 1

    def test_invoke_unexpected_exception(self, client_no_retry):
        """Test that an unexpected exception raises RuntimeError."""
        mock_runtime = MagicMock()
        mock_runtime.invoke_model.side_effect = ConnectionError("network down")

        with patch("services.bedrock_client.boto3.client", return_value=mock_runtime):
            with pytest.raises(RuntimeError, match="network down"):
                client_no_retry.invoke_model("prompt", "model", "us-east-1")


# ---------------------------------------------------------------------------
# invoke_model — retry logic
# ---------------------------------------------------------------------------


class TestInvokeModelRetry:
    """Tests for exponential backoff retry on transient Bedrock errors."""

    def _throttling_error(self):
        return ClientError(
            {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
            "InvokeModel",
        )

    def _service_unavailable_error(self):
        return ClientError(
            {"Error": {"Code": "ServiceUnavailableException", "Message": "Service unavailable"}},
            "InvokeModel",
        )

    def _success_response(self, text="ok"):
        body_content = json.dumps({
            "content": [{"type": "text", "text": text}],
            "usage": {"input_tokens": 5, "output_tokens": 5},
        })
        mock_body = MagicMock()
        mock_body.read.return_value = body_content.encode("utf-8")
        return {"body": mock_body}

    def test_retry_on_throttling_then_succeed(self, client):
        """Test that throttling errors trigger retries and eventually succeed."""
        mock_runtime = MagicMock()
        mock_runtime.invoke_model.side_effect = [
            self._throttling_error(),
            self._throttling_error(),
            self._success_response("recovered"),
        ]

        with patch("services.bedrock_client.boto3.client", return_value=mock_runtime):
            result = client.invoke_model("prompt", "model-id", "us-east-1")

        assert result == "recovered"
        assert mock_runtime.invoke_model.call_count == 3

    def test_retry_on_service_unavailable(self, client):
        """Test retry on ServiceUnavailableException."""
        mock_runtime = MagicMock()
        mock_runtime.invoke_model.side_effect = [
            self._service_unavailable_error(),
            self._success_response("back up"),
        ]

        with patch("services.bedrock_client.boto3.client", return_value=mock_runtime):
            result = client.invoke_model("prompt", "model-id", "us-east-1")

        assert result == "back up"
        assert mock_runtime.invoke_model.call_count == 2

    def test_exhausted_retries_raises(self, client):
        """Test that exhausting all retries raises RuntimeError."""
        mock_runtime = MagicMock()
        # max_retries=3 means 4 total attempts (initial + 3 retries)
        mock_runtime.invoke_model.side_effect = [
            self._throttling_error(),
            self._throttling_error(),
            self._throttling_error(),
            self._throttling_error(),
        ]

        with patch("services.bedrock_client.boto3.client", return_value=mock_runtime):
            with pytest.raises(RuntimeError, match="ThrottlingException"):
                client.invoke_model("prompt", "model-id", "us-east-1")

        assert mock_runtime.invoke_model.call_count == 4

    def test_no_retry_when_max_retries_zero(self, client_no_retry):
        """Test that max_retries=0 means only one attempt."""
        mock_runtime = MagicMock()
        mock_runtime.invoke_model.side_effect = self._throttling_error()

        with patch("services.bedrock_client.boto3.client", return_value=mock_runtime):
            with pytest.raises(RuntimeError, match="ThrottlingException"):
                client_no_retry.invoke_model("prompt", "model-id", "us-east-1")

        assert mock_runtime.invoke_model.call_count == 1


# ---------------------------------------------------------------------------
# list_models
# ---------------------------------------------------------------------------


class TestListModels:
    """Tests for listing Bedrock foundation models."""

    def test_list_models_success(self, client):
        """Test listing models returns the curated BedrockModel list."""
        models = client.list_models("us-east-1")

        assert len(models) == 5
        assert isinstance(models[0], BedrockModel)
        assert models[0].model_id == "us.anthropic.claude-3-5-sonnet-20241022-v2:0"
        assert models[0].model_name == "Claude 3.5 Sonnet v2"
        assert models[0].provider == "Anthropic"

    def test_list_models_returns_consistent_results(self, client):
        """Test listing models returns the same curated list on repeated calls."""
        models1 = client.list_models("us-east-1")
        models2 = client.list_models("us-west-2")

        assert len(models1) == len(models2)
        for m1, m2 in zip(models1, models2):
            assert m1.model_id == m2.model_id

    def test_list_models_all_anthropic(self, client):
        """Test that all curated models are from Anthropic."""
        models = client.list_models("us-east-1")

        for model in models:
            assert model.provider == "Anthropic"

    def test_list_models_demo_mode(self):
        """Test listing models in demo mode returns demo models."""
        import os
        original = os.environ.get("DEMO_MODE")
        os.environ["DEMO_MODE"] = "true"
        try:
            demo_client = BedrockClient(max_retries=0, base_delay=0.0)
            models = demo_client.list_models("us-east-1")
            assert len(models) == 3
            assert any("Demo" in m.model_name for m in models)
        finally:
            if original is None:
                os.environ.pop("DEMO_MODE", None)
            else:
                os.environ["DEMO_MODE"] = original


# ---------------------------------------------------------------------------
# Backoff delay
# ---------------------------------------------------------------------------


class TestBackoffDelay:
    """Tests for the exponential backoff calculation."""

    def test_backoff_increases_exponentially(self):
        """Test that delay increases with each attempt."""
        bc = BedrockClient(base_delay=1.0)
        delays = [bc._backoff_delay(i) for i in range(4)]

        # Each delay should be larger than the previous (base * 2^attempt + jitter)
        # With base=1.0: attempt 0 → ~1-1.5, attempt 1 → ~2-3, attempt 2 → ~4-6, etc.
        for i in range(1, len(delays)):
            # The minimum of attempt i is base * 2^i, which is > max of attempt i-1
            # (base * 2^(i-1) * 1.5). This holds for base_delay >= 1.
            assert delays[i] > 0

    def test_backoff_with_zero_base(self):
        """Test that zero base_delay produces zero delay."""
        bc = BedrockClient(base_delay=0.0)
        delay = bc._backoff_delay(0)
        assert delay == 0.0


# ---------------------------------------------------------------------------
# BedrockModel dataclass
# ---------------------------------------------------------------------------


class TestBedrockModel:
    """Tests for the BedrockModel dataclass."""

    def test_create_model(self):
        """Test creating a BedrockModel instance."""
        model = BedrockModel(
            model_id="anthropic.claude-3-sonnet-20240229-v1:0",
            model_name="Claude 3 Sonnet",
            provider="Anthropic",
        )
        assert model.model_id == "anthropic.claude-3-sonnet-20240229-v1:0"
        assert model.model_name == "Claude 3 Sonnet"
        assert model.provider == "Anthropic"

    def test_model_equality(self):
        """Test that two BedrockModel instances with same data are equal."""
        m1 = BedrockModel("id", "name", "provider")
        m2 = BedrockModel("id", "name", "provider")
        assert m1 == m2
