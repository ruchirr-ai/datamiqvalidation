"""
AWS Bedrock Client Service

Handles AWS Bedrock model invocation and S3 prompt template retrieval for
the Code Conversion module. Uses IAM role-based auth (no hardcoded credentials).

Implements exponential backoff retry for throttling and transient Bedrock errors.
Logs invocation metadata (model_id, region, token usage, latency, workspace_id)
at INFO level. NEVER logs source code or converted output.
"""

import json
import logging
import os
import random
import re
import time
from dataclasses import dataclass
from typing import Optional

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# Transient Bedrock error codes that should trigger a retry.
_RETRYABLE_ERROR_CODES = frozenset({
    "ThrottlingException",
    "ServiceUnavailableException",
    "ModelTimeoutException",
    "InternalServerException",
    "TooManyRequestsException",
})

_S3_PATH_PATTERN = re.compile(r"^s3://([^/]+)/(.+)$")


@dataclass
class BedrockModel:
    """Lightweight representation of a Bedrock foundation model."""

    model_id: str
    model_name: str
    provider: str


def _get_aws_session(region: str) -> boto3.Session:
    """Build a boto3 Session using explicit credentials from environment variables.

    Precedence:
    1. AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_SESSION_TOKEN env vars
    2. AWS default credential chain (IAM role, ~/.aws/credentials, etc.)

    The Bedrock region falls back to AWS_BEDROCK_REGION → AWS_REGION → the
    ``region`` argument supplied by the caller.
    """
    access_key = os.getenv("AWS_ACCESS_KEY_ID")
    secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    session_token = os.getenv("AWS_SESSION_TOKEN")

    # Prefer the Bedrock-specific region override when available.
    effective_region = (
        os.getenv("AWS_BEDROCK_REGION")
        or os.getenv("AWS_REGION")
        or region
    )

    if access_key and secret_key:
        logger.debug(
            "Building AWS session with explicit credentials from environment",
            extra={"region": effective_region},
        )
        return boto3.Session(
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            aws_session_token=session_token,
            region_name=effective_region,
        )

    logger.debug(
        "No explicit AWS credentials found; falling back to default credential chain",
        extra={"region": effective_region},
    )
    return boto3.Session(region_name=effective_region)


class BedrockClient:
    """Client for AWS Bedrock model invocation and S3 prompt template retrieval."""

    def __init__(self, max_retries: int = 3, base_delay: float = 1.0) -> None:
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.demo_mode = os.getenv("DEMO_MODE", "false").lower() in ("true", "1", "yes")

    # ------------------------------------------------------------------
    # Prompt template loading (S3 or local file)
    # ------------------------------------------------------------------

    def fetch_prompt_template(self, template_path: str, region: str) -> str:
        """Fetch a prompt template from S3 or local file system."""
        if self.demo_mode:
            logger.info("DEMO_MODE: returning default prompt template")
            return (
                "Convert the following {source_dialect} {asset_type} to {target_dialect}.\n\n"
                "Source code:\n{source_code}\n\n"
                "sqlglot pre-processed output (if available):\n{sqlglot_output}\n\n"
                "Return ONLY the converted SQL code, no explanations."
            )

        if template_path.startswith("local://") or not template_path.startswith("s3://"):
            return self._fetch_local_template(template_path)

        return self._fetch_s3_template(template_path, region)

    def _fetch_local_template(self, template_path: str) -> str:
        """Fetch a prompt template from the local file system."""
        if template_path.startswith("local://"):
            template_path = template_path[8:]

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        full_path = os.path.join(base_dir, template_path)

        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                template = f.read()
            logger.info(
                "Prompt template loaded from local file",
                extra={"path": template_path, "full_path": full_path},
            )
            return template
        except FileNotFoundError:
            msg = f"Local template file not found: {template_path} (resolved to {full_path})"
            logger.error(msg)
            raise ValueError(msg)
        except Exception as exc:
            msg = f"Failed to read local template file '{template_path}': {exc}"
            logger.error(msg, exc_info=True)
            raise ValueError(msg) from exc

    def _fetch_s3_template(self, s3_path: str, region: str) -> str:
        """Fetch a prompt template from S3."""
        match = _S3_PATH_PATTERN.match(s3_path)
        if not match:
            msg = (
                f"Invalid S3 path '{s3_path}'. "
                "Expected format: s3://bucket-name/path/to/template.txt"
            )
            logger.error(msg)
            raise ValueError(msg)

        bucket = match.group(1)
        key = match.group(2)

        try:
            session = _get_aws_session(region)
            s3_client = session.client("s3")
            response = s3_client.get_object(Bucket=bucket, Key=key)
            template = response["Body"].read().decode("utf-8")
            logger.info(
                "Prompt template fetched from S3",
                extra={"bucket": bucket, "key": key, "region": region},
            )
            return template
        except ClientError as exc:
            error_code = exc.response["Error"]["Code"]
            msg = (
                f"Failed to fetch prompt template from '{s3_path}': "
                f"{error_code} — {exc.response['Error'].get('Message', '')}"
            )
            logger.error(msg)
            raise ValueError(msg) from exc
        except Exception as exc:
            msg = f"Unexpected error fetching prompt template from '{s3_path}': {exc}"
            logger.error(msg, exc_info=True)
            raise ValueError(msg) from exc

    # ------------------------------------------------------------------
    # Prompt rendering
    # ------------------------------------------------------------------

    @staticmethod
    def render_prompt(
        template: str,
        source_code: str,
        source_dialect: str,
        target_dialect: str,
        asset_type: str,
        sqlglot_output: Optional[str] = None,
        asset_name: Optional[str] = None,
        additional_context: Optional[str] = None,
    ) -> str:
        """Render a prompt template by substituting placeholders."""
        context_value = additional_context or ""

        replacements = {
            "{source_code}": source_code,
            "{source_dialect}": source_dialect,
            "{target_dialect}": target_dialect,
            "{asset_type}": asset_type,
            "{asset_name}": asset_name or "",
            "{sqlglot_output}": sqlglot_output or "",
            "{additional_context}": context_value,
            "{{SOURCE_CODE}}": source_code,
            "{{SOURCE_DIALECT}}": source_dialect,
            "{{TARGET_DIALECT}}": target_dialect,
            "{{ASSET_TYPE}}": asset_type,
            "{{ASSET_NAME}}": asset_name or "",
            "{{SQLGLOT_OUTPUT}}": sqlglot_output or "",
            "{{ADDITIONAL_CONTEXT}}": context_value,
        }

        rendered = template
        for placeholder, value in replacements.items():
            rendered = rendered.replace(placeholder, value)

        if additional_context:
            rendered += f"\n\nAdditional Context:\n{additional_context}"

        return rendered

    # ------------------------------------------------------------------
    # Model invocation
    # ------------------------------------------------------------------

    def invoke_model(self, prompt: str, model_id: str, region: str) -> str:
        """Invoke a Bedrock model with exponential backoff retry."""
        if self.demo_mode:
            return self._demo_invoke(prompt)

        session = _get_aws_session(region)
        bedrock_runtime = session.client("bedrock-runtime")

        last_exception: Optional[Exception] = None

        for attempt in range(self.max_retries + 1):
            start_time = time.time()
            try:
                body = json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 8192,
                    "messages": [
                        {"role": "user", "content": prompt},
                    ],
                })

                response = bedrock_runtime.invoke_model(
                    modelId=model_id,
                    contentType="application/json",
                    accept="application/json",
                    body=body,
                )

                latency_ms = (time.time() - start_time) * 1000
                response_body = json.loads(response["body"].read())

                usage = response_body.get("usage", {})
                input_tokens = usage.get("input_tokens", 0)
                output_tokens = usage.get("output_tokens", 0)

                logger.info(
                    "Bedrock model invocation succeeded",
                    extra={
                        "model_id": model_id,
                        "region": region,
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "latency_ms": round(latency_ms, 2),
                        "attempt": attempt + 1,
                    },
                )

                content_blocks = response_body.get("content", [])
                generated_text = "".join(
                    block.get("text", "")
                    for block in content_blocks
                    if block.get("type") == "text"
                )
                return generated_text

            except ClientError as exc:
                latency_ms = (time.time() - start_time) * 1000
                error_code = exc.response["Error"]["Code"]
                last_exception = exc

                if error_code in _RETRYABLE_ERROR_CODES and attempt < self.max_retries:
                    delay = self._backoff_delay(attempt)
                    logger.warning(
                        "Bedrock transient error, retrying",
                        extra={
                            "model_id": model_id,
                            "region": region,
                            "error_code": error_code,
                            "attempt": attempt + 1,
                            "retry_delay_s": round(delay, 2),
                            "latency_ms": round(latency_ms, 2),
                        },
                    )
                    time.sleep(delay)
                    continue

                logger.error(
                    "Bedrock model invocation failed",
                    extra={
                        "model_id": model_id,
                        "region": region,
                        "error_code": error_code,
                        "attempt": attempt + 1,
                        "latency_ms": round(latency_ms, 2),
                    },
                )
                raise RuntimeError(
                    f"Bedrock invocation failed after {attempt + 1} attempt(s): "
                    f"{error_code} — {exc.response['Error'].get('Message', '')}"
                ) from exc

            except Exception as exc:
                latency_ms = (time.time() - start_time) * 1000
                last_exception = exc
                logger.error(
                    "Unexpected error during Bedrock invocation",
                    extra={
                        "model_id": model_id,
                        "region": region,
                        "attempt": attempt + 1,
                        "latency_ms": round(latency_ms, 2),
                    },
                    exc_info=True,
                )
                raise RuntimeError(
                    f"Bedrock invocation failed: {exc}"
                ) from exc

        raise RuntimeError(
            f"Bedrock invocation failed after {self.max_retries + 1} attempts"
        ) from last_exception

    # ------------------------------------------------------------------
    # List local templates
    # ------------------------------------------------------------------

    @staticmethod
    def list_local_templates() -> list[dict]:
        """List available local prompt templates."""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        prompts_dir = os.path.join(base_dir, "prompts")

        templates = []

        if not os.path.exists(prompts_dir):
            logger.warning(f"Prompts directory not found: {prompts_dir}")
            return templates

        for filename in os.listdir(prompts_dir):
            if filename.endswith(".txt"):
                file_path = os.path.join(prompts_dir, filename)
                relative_path = f"prompts/{filename}"

                name_parts = filename.replace(".txt", "").split("-")

                template_info = {
                    "path": relative_path,
                    "name": filename.replace(".txt", "").replace("-", " ").title(),
                    "description": f"Conversion template from {file_path}",
                    "source_dialect": "unknown",
                    "target_dialect": "unknown",
                }

                if "to" in name_parts:
                    to_index = name_parts.index("to")
                    if to_index > 0 and to_index < len(name_parts) - 1:
                        template_info["source_dialect"] = name_parts[to_index - 1]
                        template_info["target_dialect"] = name_parts[to_index + 1]
                        template_info["description"] = (
                            f"{template_info['source_dialect'].upper()} to "
                            f"{template_info['target_dialect'].upper()} conversion template"
                        )

                templates.append(template_info)

        logger.info(f"Found {len(templates)} local prompt templates")
        return templates

    # ------------------------------------------------------------------
    # List models
    # ------------------------------------------------------------------

    def list_models(self, region: str) -> list[BedrockModel]:
        """List available Bedrock foundation models."""
        if self.demo_mode:
            logger.info("DEMO_MODE: returning hardcoded Bedrock model list")
            return [
                BedrockModel(
                    model_id="anthropic.claude-3-sonnet-20240229-v1:0",
                    model_name="Claude 3 Sonnet (Demo)",
                    provider="Anthropic",
                ),
                BedrockModel(
                    model_id="anthropic.claude-3-haiku-20240307-v1:0",
                    model_name="Claude 3 Haiku (Demo)",
                    provider="Anthropic",
                ),
                BedrockModel(
                    model_id="amazon.titan-text-express-v1",
                    model_name="Titan Text Express (Demo)",
                    provider="Amazon",
                ),
            ]

        logger.info("Returning curated Bedrock model list for SQL conversion")
        return [
            # Claude 4 — latest models first (require inference profile IDs)
            BedrockModel(
                model_id="us.anthropic.claude-sonnet-4-6",
                model_name="Claude Sonnet 4.6 (Latest)",
                provider="Anthropic",
            ),
            BedrockModel(
                model_id="us.anthropic.claude-opus-4-8",
                model_name="Claude Opus 4.8",
                provider="Anthropic",
            ),
            BedrockModel(
                model_id="us.anthropic.claude-opus-4-7",
                model_name="Claude Opus 4.7",
                provider="Anthropic",
            ),
            BedrockModel(
                model_id="us.anthropic.claude-opus-4-6-v1",
                model_name="Claude Opus 4.6",
                provider="Anthropic",
            ),
            BedrockModel(
                model_id="us.anthropic.claude-opus-4-5-20251101-v1:0",
                model_name="Claude Opus 4.5",
                provider="Anthropic",
            ),
            BedrockModel(
                model_id="us.anthropic.claude-opus-4-1-20250805-v1:0",
                model_name="Claude Opus 4.1",
                provider="Anthropic",
            ),
            BedrockModel(
                model_id="us.anthropic.claude-sonnet-4-5-20250929-v1:0",
                model_name="Claude Sonnet 4.5",
                provider="Anthropic",
            ),
            BedrockModel(
                model_id="us.anthropic.claude-sonnet-4-20250514-v1:0",
                model_name="Claude Sonnet 4",
                provider="Anthropic",
            ),
            BedrockModel(
                model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0",
                model_name="Claude Haiku 4.5",
                provider="Anthropic",
            ),
            # Claude 3.5
            BedrockModel(
                model_id="us.anthropic.claude-3-5-haiku-20241022-v1:0",
                model_name="Claude 3.5 Haiku",
                provider="Anthropic",
            ),
            # Claude 3
            BedrockModel(
                model_id="us.anthropic.claude-3-sonnet-20240229-v1:0",
                model_name="Claude 3 Sonnet",
                provider="Anthropic",
            ),
            BedrockModel(
                model_id="us.anthropic.claude-3-haiku-20240307-v1:0",
                model_name="Claude 3 Haiku",
                provider="Anthropic",
            ),
        ]

    # ------------------------------------------------------------------
    # Demo mode helper
    # ------------------------------------------------------------------

    def _demo_invoke(self, prompt: str) -> str:
        """Use sqlglot to transpile SQL from the prompt in demo mode.

        Supports both the legacy prompt format (Source Code: / convert the following)
        and the detailed XML-style prompt format (<source_sql> / <context> tags).
        When the detailed prompt is detected, returns a structured JSON response
        matching the expected output schema.
        """
        import re
        from services.sqlglot_parser import SqlGlotParser

        logger.info("DEMO_MODE: using sqlglot for conversion instead of Bedrock")

        source_code = ""
        source_dialect = ""
        target_dialect = ""

        # Try XML-style tags first (detailed prompt format)
        source_match = re.search(
            r"<source_sql>\s*(.*?)\s*</source_sql>", prompt, re.DOTALL
        )
        context_match = re.search(
            r"<context>\s*(.*?)\s*</context>", prompt, re.DOTALL
        )

        if source_match and context_match:
            source_code = source_match.group(1).strip()
            context_block = context_match.group(1)
            for ctx_line in context_block.split("\n"):
                ctx_line = ctx_line.strip()
                if ctx_line.lower().startswith("source dialect:"):
                    source_dialect = ctx_line.split(":", 1)[1].strip().lower()
                elif ctx_line.lower().startswith("target dialect:"):
                    target_dialect = ctx_line.split(":", 1)[1].strip().lower()
        else:
            # Fallback: legacy prompt format
            lines = prompt.split("\n")
            in_source = False
            for line in lines:
                lower = line.lower().strip()
                if "source code:" in lower:
                    in_source = True
                    continue
                if in_source and ("sqlglot" in lower or "return only" in lower):
                    in_source = False
                    continue
                if in_source:
                    source_code += line + "\n"
                if "convert the following" in lower:
                    parts = lower.split()
                    for i, p in enumerate(parts):
                        if p == "following" and i + 1 < len(parts):
                            source_dialect = parts[i + 1]
                        if p == "to" and i + 1 < len(parts):
                            target_dialect = parts[i + 1].rstrip(".")
            source_code = source_code.strip()

        if not source_code:
            return "-- Demo Mode: no source code detected in prompt"

        # Attempt sqlglot transpilation
        converted_sql = None
        if source_code and source_dialect and target_dialect:
            parser = SqlGlotParser()
            result = parser.parse_and_transpile(
                source_code, source_dialect, target_dialect
            )
            if result.success and result.transpiled_code:
                converted_sql = result.transpiled_code

        # If the prompt uses the detailed XML format, return structured JSON
        uses_detailed_format = source_match is not None and context_match is not None
        if uses_detailed_format:
            sql_output = converted_sql or source_code
            return json.dumps({
                "converted_sql": sql_output,
                "accuracy_score": 75 if converted_sql else 40,
                "risks_and_issues": [
                    {
                        "severity": "Medium",
                        "issue_type": "Feature Gap",
                        "description": "Demo mode uses sqlglot for basic transpilation. Complex BigQuery features may not be fully converted.",
                        "suggested_action": "Review the converted SQL and test against your Redshift cluster. Use production Bedrock for full conversion fidelity."
                    }
                ],
                "optimization_recommendations": [
                    {
                        "category": "Distribution",
                        "recommendation": "Review and add appropriate DISTKEY and SORTKEY based on your query patterns."
                    }
                ]
            }, indent=2)

        # Legacy format: return plain SQL with comment
        if converted_sql:
            return (
                f"-- Converted from {source_dialect} to {target_dialect} "
                f"(Demo Mode - sqlglot)\n{converted_sql}"
            )
        return (
            f"-- Demo Mode: conversion placeholder ({source_dialect} -> {target_dialect})\n"
            f"-- sqlglot could not transpile this code; Bedrock would handle it in production.\n"
            f"{source_code}"
        )


    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _backoff_delay(self, attempt: int) -> float:
        """Calculate exponential backoff delay with jitter."""
        delay = self.base_delay * (2 ** attempt)
        jitter = random.uniform(0, delay * 0.5)
        return delay + jitter
