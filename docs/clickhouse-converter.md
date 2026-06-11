# ClickHouse Converter — Complete Implementation Guide

## Overview

The ClickHouse converter adds **BigQuery → ClickHouse** as a supported conversion path across the full DataMIQ conversion pipeline. It enables both single-snippet (Quick Convert) and multi-asset (Batch Convert) SQL migration using AWS Bedrock (Claude) with optional SQLGlot pre-processing.

---

## Table of Contents

1. [Files Changed](#files-changed)
2. [Backend Changes](#backend-changes)
   - [Allowed Dialects](#1-allowed-dialects)
   - [SQLGlot Parser](#2-sqlglot-parser)
   - [AWS Bedrock Client](#3-aws-bedrock-client)
   - [Prompt Template](#4-prompt-template)
   - [Test Fixtures](#5-test-fixtures)
3. [Frontend Changes](#frontend-changes)
   - [Standalone Converter Page](#6-standalone-converter-page)
   - [Batch Converter Page](#7-batch-converter-page)
4. [Environment Configuration](#environment-configuration)
5. [Conversion Pipeline Flow](#conversion-pipeline-flow)
6. [Supported Conversions](#supported-conversions)
7. [Conversion Reference — BigQuery → ClickHouse](#conversion-reference)
   - [Data Types](#data-types)
   - [DDL / Table Creation](#ddl--table-creation)
   - [Query Syntax](#query-syntax)
   - [Function Mapping](#function-mapping)
   - [DML / Mutations](#dml--mutations)
   - [Views & Materialized Views](#views--materialized-views)
   - [Stored Procedures & UDFs](#stored-procedures--udfs)
   - [Known Feature Gaps](#known-feature-gaps)
8. [Testing](#testing)
9. [Architecture Decisions](#architecture-decisions)

---

## Files Changed

| File | Type | Change |
|------|------|--------|
| `backend/prompts/bigquery-to-clickhouse-conversion.txt` | **New** | Full conversion prompt template |
| `backend/models/conversion_schemas.py` | Modified | Added ClickHouse to `ALLOWED_TARGET_DIALECTS` |
| `backend/services/sqlglot_parser.py` | Modified | Added `clickhouse` to `SUPPORTED_DIALECTS` and `DIALECT_MAP` |
| `backend/services/bedrock_client.py` | Modified | Added `_get_aws_session()` helper for explicit credential loading |
| `backend/tests/fixtures/sample_payloads.py` | Modified | Added 7 ClickHouse-specific test payloads |
| `frontend/src/pages/StandaloneConverterPage.tsx` | Modified | Added ClickHouse to target options + auto-template selection |
| `frontend/src/pages/BatchConverterPage.tsx` | Modified | Added ClickHouse to target options + auto-template selection |
| `.env` | Modified | Updated default Bedrock model to Claude 3.5 Sonnet v2 |

---

## Backend Changes

### 1. Allowed Dialects

**File:** `backend/models/conversion_schemas.py`

```python
# Before
ALLOWED_TARGET_DIALECTS: set[str] = {
    "Redshift", "redshift",
    "SQL Server", "sql server",
    "BigQuery", "Bigquery", "bigquery"
}

# After
ALLOWED_TARGET_DIALECTS: set[str] = {
    "Redshift", "redshift",
    "SQL Server", "sql server",
    "BigQuery", "Bigquery", "bigquery",
    "ClickHouse", "Clickhouse", "clickhouse"   # ← added
}
```

This is the backend gate. Any conversion request whose `target_dialect` is not in this set is rejected with HTTP 400 before touching Bedrock.

---

### 2. SQLGlot Parser

**File:** `backend/services/sqlglot_parser.py`

Two additions:

**`SQLGlotParser.SUPPORTED_DIALECTS`** — used by the low-level parser class:
```python
SUPPORTED_DIALECTS = [
    'bigquery', 'redshift', 'postgres', 'mysql',
    'snowflake', 'oracle', 'mssql', 'tsql',
    'clickhouse',   # ← added
]
```

**`DIALECT_MAP`** — used by the `SqlGlotParser` compatibility wrapper that `ConversionService` calls:
```python
DIALECT_MAP: Dict[str, str] = {
    "bigquery":   "bigquery",
    "redshift":   "redshift",
    ...
    "clickhouse": "clickhouse",   # ← added
}
```

Without these additions, enabling the SQLGlot pre-processing toggle for a ClickHouse target would silently fall back to raw source code (the wrapper returns `success=False` for any key not in `DIALECT_MAP`). SQLGlot v25+ natively supports the ClickHouse dialect, so basic syntax transpilation — function renames, identifier quoting — is handled automatically before Bedrock receives the prompt.

---

### 3. AWS Bedrock Client

**File:** `backend/services/bedrock_client.py`

**Problem:** The Bedrock client called `boto3.client("bedrock-runtime", region_name=region)` with no explicit credentials. In development the `.env` file contains `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`, but `boto3` only picks those up if they are exported as real environment variables — `python-dotenv` loads them into `os.environ`, but a fresh process without the app bootstrapped would silently fall back to the default chain and likely fail.

**Fix:** Added a module-level `_get_aws_session()` helper:

```python
def _get_aws_session(region: str) -> boto3.Session:
    """Build a boto3 Session using explicit credentials from environment variables.

    Precedence:
    1. AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_SESSION_TOKEN env vars
    2. AWS default credential chain (IAM role, ~/.aws/credentials, etc.)

    The Bedrock region falls back to AWS_BEDROCK_REGION → AWS_REGION → the
    ``region`` argument supplied by the caller.
    """
    access_key    = os.getenv("AWS_ACCESS_KEY_ID")
    secret_key    = os.getenv("AWS_SECRET_ACCESS_KEY")
    session_token = os.getenv("AWS_SESSION_TOKEN")

    effective_region = (
        os.getenv("AWS_BEDROCK_REGION")
        or os.getenv("AWS_REGION")
        or region
    )

    if access_key and secret_key:
        return boto3.Session(
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            aws_session_token=session_token,
            region_name=effective_region,
        )
    return boto3.Session(region_name=effective_region)
```

All three `boto3.client()` calls in the class now go through this helper:

```python
# S3 template fetch
session = _get_aws_session(region)
s3_client = session.client("s3")

# Bedrock model invocation
session = _get_aws_session(region)
bedrock_runtime = session.client("bedrock-runtime")
```

**Additional change:** `max_tokens` bumped from `4096` → `8192` to handle complex DDL and stored procedure conversions that can produce long output.

---

### 4. Prompt Template

**File:** `backend/prompts/bigquery-to-clickhouse-conversion.txt`

A purpose-built conversion prompt covering the full semantic gap between BigQuery and ClickHouse. The template uses `{{DOUBLE_BRACE}}` placeholders matching the `BedrockClient.render_prompt()` substitution map.

**Structure:**

```
<context>        — asset type, name, source/target dialect
<source_sql>     — the raw BigQuery SQL
{{SQLGLOT_OUTPUT}} — optional pre-processed output (empty string if SQLGlot disabled)
<conversion_guidelines>   — 11 numbered sections (see Conversion Reference below)
<output_requirements>     — strict JSON schema for the response
```

**Output JSON schema** (same as other templates):
```json
{
  "converted_sql": "...",
  "accuracy_score": 0-100,
  "risks_and_issues": [
    {
      "severity": "High | Medium | Low",
      "issue_type": "Syntax | Performance | Feature Gap | Manual Intervention | Data Loss Risk",
      "description": "...",
      "suggested_action": "..."
    }
  ],
  "optimization_recommendations": [
    {
      "category": "Engine Selection | Order Key | Partitioning | Compression | Query Rewrite | Data Types",
      "recommendation": "..."
    }
  ]
}
```

**Template auto-discovery:** `BedrockClient.list_local_templates()` scans `backend/prompts/` for `*.txt` files and builds metadata from the filename. The file `bigquery-to-clickhouse-conversion.txt` is parsed as:
- `source_dialect`: `bigquery`
- `target_dialect`: `clickhouse`
- `name`: `Bigquery To Clickhouse Conversion`
- `path`: `prompts/bigquery-to-clickhouse-conversion.txt`

This path is what the frontend stores and sends back in the conversion request.

---

### 5. Test Fixtures

**File:** `backend/tests/fixtures/sample_payloads.py`

Seven new payloads added under the `# ClickHouse conversion payloads` section:

| Constant | Asset Type | Tests |
|----------|-----------|-------|
| `VALID_BQ_TO_CLICKHOUSE_QUERY` | QUERY | Date functions, COUNT DISTINCT, STRING_AGG |
| `VALID_BQ_TO_CLICKHOUSE_TABLE_DDL` | TABLE_DDL | PARTITION BY, CLUSTER BY, STRUCT, ARRAY, NUMERIC, JSON |
| `VALID_BQ_TO_CLICKHOUSE_VIEW` | VIEW | ROW_NUMBER + WHERE wrapper (QUALIFY equivalent) |
| `VALID_BQ_TO_CLICKHOUSE_SQLGLOT` | QUERY | Same as query but `use_sqlglot: True` |
| `VALID_BQ_TO_CLICKHOUSE_ARRAY_QUERY` | QUERY | UNNEST / ARRAY_LENGTH patterns |
| `VALID_BQ_TO_CLICKHOUSE_STORED_PROCEDURE` | STORED_PROCEDURE | Expected to surface High-risk flags (no CH equivalent) |
| `VALID_BQ_TO_CLICKHOUSE_BATCH` | Batch (3 assets) | DDL + VIEW + QUERY in a single batch request |

---

## Frontend Changes

### 6. Standalone Converter Page

**File:** `frontend/src/pages/StandaloneConverterPage.tsx`

**Change 1 — Target dialect option added:**
```tsx
// Before
const TARGET_DIALECT_OPTIONS = ['Redshift', 'SQL Server', 'BigQuery'];

// After
const TARGET_DIALECT_OPTIONS = ['Redshift', 'SQL Server', 'BigQuery', 'ClickHouse'];
```

**Change 2 — Auto-template selection `useEffect`:**

When the user changes either `sourceDialect` or `targetDialect`, this effect fires and tries to find a template whose filename contains both dialect slugs. For BigQuery → ClickHouse it matches `bigquery-to-clickhouse-conversion.txt` and sets it automatically so the user never has to scroll the template dropdown.

```tsx
useEffect(() => {
  if (templates.length === 0 || showCustomInput) return;
  const srcKey = sourceDialect.toLowerCase().replace(/\s+/g, '');
  const tgtKey = targetDialect.toLowerCase().replace(/\s+/g, '');
  const match = templates.find((t) => {
    const pathLower = t.path.toLowerCase();
    return pathLower.includes(srcKey) && pathLower.includes(tgtKey);
  });
  if (match) {
    setPromptTemplatePath(match.path);
  }
}, [sourceDialect, targetDialect, templates, showCustomInput]);
```

---

### 7. Batch Converter Page

**File:** `frontend/src/pages/BatchConverterPage.tsx`

Same two changes as the standalone page:

```tsx
// Target dialect options
const TARGET_DIALECT_OPTIONS = ['Redshift', 'SQL Server', 'BigQuery', 'ClickHouse'];
```

And the same auto-template-selection `useEffect` added after the `fetchTemplates` effect. Without this, users navigating the 5-step batch wizard would have to manually pick the ClickHouse template in Step 2 (Configuration).

---

## Environment Configuration

**File:** `.env`

```dotenv
# AWS credentials — used by BedrockClient._get_aws_session()
AWS_ACCESS_KEY_ID=<your-key>
AWS_SECRET_ACCESS_KEY=<your-secret>
AWS_REGION=us-east-1

# Bedrock region (takes priority over AWS_REGION for Bedrock calls)
AWS_BEDROCK_REGION=us-east-1

# Default model updated from anthropic.claude-v2 to Claude 3.5 Sonnet v2
AWS_BEDROCK_DEFAULT_MODEL=us.anthropic.claude-3-5-sonnet-20241022-v2:0
```

The `_get_aws_session()` helper resolves the effective region with this priority:
```
AWS_BEDROCK_REGION → AWS_REGION → caller-supplied region argument
```

---

## Conversion Pipeline Flow

### Quick Convert (Standalone)

```
User selects:
  Source dialect = BigQuery
  Target dialect = ClickHouse
  ↓
Auto-selects template: prompts/bigquery-to-clickhouse-conversion.txt
  ↓
POST /api/conversions/standalone
  ↓
ConversionService.create_standalone_conversion()
  ├─ _validate_dialects()            → "ClickHouse" ∈ ALLOWED_TARGET_DIALECTS ✓
  ├─ repo.create_job()               → status = "pending"
  ├─ [if use_sqlglot=True]
  │   SqlGlotParser.parse_and_transpile()
  │       DIALECT_MAP["bigquery"]   → "bigquery"
  │       DIALECT_MAP["clickhouse"] → "clickhouse"  ← now works
  │       sqlglot.transpile(sql, read="bigquery", write="clickhouse")
  │       → SqlGlotResult(success=True, transpiled_code=...)
  │   repo.update_job(sqlglot_success=True)
  └─ retry loop (max_retries):
      BedrockClient.fetch_prompt_template("prompts/bigquery-to-clickhouse-conversion.txt")
          → reads file from backend/prompts/ directory
      BedrockClient.render_prompt(template, source_code, "BigQuery", "ClickHouse", ...)
          → replaces {{SOURCE_CODE}}, {{SOURCE_DIALECT}}, {{TARGET_DIALECT}}, etc.
      _get_aws_session("us-east-1")
          → boto3.Session(aws_access_key_id=..., aws_secret_access_key=..., region_name="us-east-1")
      bedrock_runtime.invoke_model(modelId="us.anthropic.claude-3-5-sonnet-20241022-v2:0", ...)
          → Claude returns JSON: { "converted_sql": "...", "accuracy_score": 85, ... }
      unescape_code_output(target_code)
      repo.update_job(target_code=..., status="completed")
  ↓
ConversionJobResponse → frontend
  ↓
Side-by-side CodePane displays ClickHouse SQL
```

### Batch Convert

```
Step 1 (Assets)  → Select assets from completed assessment
Step 2 (Config)  → Pick ClickHouse as target dialect
                   Auto-selects bigquery-to-clickhouse-conversion.txt template
Step 3 (Review)  → Summary of selected assets and config
Step 4 (Progress) → POST /api/conversions/batch
                    Creates ConversionBatch + one ConversionJob per asset
                    FastAPI BackgroundTask: run_batch_background()
                      Processes each job sequentially with same pipeline above
                      Updates Redis cache after each job
                      Final status: completed / completed_with_errors / failed
Step 5 (Summary) → View results, export .sql, export to S3, deploy to target DB
```

---

## Supported Conversions

### What works (BigQuery → ClickHouse)

| Category | Coverage |
|----------|----------|
| SELECT queries | Full |
| CTEs (WITH clauses) | Full |
| JOINs (INNER, LEFT, RIGHT, FULL) | Full |
| Window functions | Full (with caveats for IGNORE NULLS, RANGE INTERVAL) |
| GROUP BY / ORDER BY / HAVING | Full |
| Subqueries | Full (correlated subqueries flagged as Medium risk) |
| ARRAY / UNNEST → ARRAY JOIN | Full (AI handles the idiom shift) |
| STRUCT → Tuple | Full |
| Date / Time functions | Full (80+ mappings in prompt) |
| String functions | Full |
| Math / aggregate functions | Full |
| SAFE_* functions → if/nullIf | Full |
| CREATE TABLE DDL | Full (with ENGINE/ORDER BY recommendations) |
| CREATE VIEW | Full |
| CREATE MATERIALIZED VIEW | Full |
| PARTITION BY / CLUSTER BY | Full (mapped to ORDER BY + PARTITION BY toYYYYMM) |
| TTL (partition_expiration_days) | Full |
| Data type mapping | Full |
| INSERT INTO ... SELECT | Full |

### What is flagged as High Risk (requires manual intervention)

| BigQuery Feature | ClickHouse Status | Prompt Action |
|-----------------|-------------------|---------------|
| MERGE statement | Not supported | Flagged High — rewrite as INSERT + ALTER UPDATE |
| CREATE PROCEDURE / scripting | Not supported | Flagged High — rewrite as app-layer logic or UDF |
| PIVOT / UNPIVOT keywords | Not supported | Flagged High — rewrite as conditional aggregation |
| WITH RECURSIVE | Not supported | Flagged High — rewrite with arrayMap or application loop |
| FOR SYSTEM_TIME AS OF (time travel) | Not supported | Flagged High — no equivalent |
| BigQuery ML (CREATE MODEL, ML.PREDICT) | Not supported | Flagged High |
| SELECT * EXCEPT / REPLACE | Not supported | Flagged High — list columns explicitly |
| Wildcard tables (events_*) | Not supported | Flagged High — use UNION ALL |
| GEOGRAPHY type | Not supported | Flagged High — store as String |
| JavaScript UDFs | Not supported | Flagged High |
| Row / column security policies | Not supported | Flagged High |
| TABLESAMPLE | Not supported | Rewrite with WHERE rand() < ratio |
| EXPORT DATA statement | Not supported | Use INSERT INTO ... SELECT with S3 engine |

---

## Conversion Reference

### Data Types

| BigQuery | ClickHouse | Notes |
|----------|-----------|-------|
| `STRING` | `String` | |
| `INT64` | `Int64` | |
| `FLOAT64` | `Float64` | |
| `BOOL` / `BOOLEAN` | `UInt8` | 0/1; `Bool` alias available in v22+ |
| `NUMERIC(p,s)` | `Decimal(p,s)` | |
| `BIGNUMERIC(p,s)` | `Decimal(p,s)` | Warn if precision exceeds Decimal128 |
| `DATE` | `Date` | Use `Date32` for pre-1970 dates |
| `DATETIME` | `DateTime` | No timezone; `DateTime64(3)` for ms precision |
| `TIMESTAMP` | `DateTime64(6, 'UTC')` | BQ TIMESTAMP is always UTC |
| `TIME` | `String` | No native TIME type in ClickHouse |
| `BYTES` | `String` | Store as hex or base64; warn user |
| `JSON` | `String` | JSON functions available in CH 22.6+ |
| `GEOGRAPHY` | `String` | **Not supported** — flag High risk |
| `INTERVAL` | Integer arithmetic | No direct equivalent |
| `ARRAY<T>` | `Array(T)` | |
| `STRUCT<f T,...>` | `Tuple(f T,...)` | Named Tuple in CH 22+ |
| `MAP<K,V>` | `Map(K,V)` | Requires CH 21.1+ |
| `ARRAY<STRUCT>` | `Array(Tuple(...))` | |

### DDL / Table Creation

```sql
-- BigQuery
CREATE OR REPLACE TABLE `project.dataset.table` (
  id INT64,
  name STRING,
  created_at TIMESTAMP,
  tags ARRAY<STRING>
)
PARTITION BY DATE(created_at)
CLUSTER BY id
OPTIONS (partition_expiration_days=90)

-- ClickHouse
CREATE OR REPLACE TABLE database.table
(
  id        Int64,
  name      String,
  created_at DateTime64(6, 'UTC'),
  tags      Array(String)
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(created_at)
ORDER BY (id)
TTL toDate(created_at) + INTERVAL 90 DAY
```

**Engine selection guide (included in prompt):**

| Use Case | Engine |
|----------|--------|
| Standard analytics, append-only | `MergeTree()` |
| Deduplication / updates by key | `ReplacingMergeTree([version_col])` |
| Pre-aggregated sums/max | `AggregatingMergeTree()` |
| Replicated production | `ReplicatedMergeTree('/zk/path', 'replica')` |

### Query Syntax

```sql
-- BigQuery: UNNEST
SELECT t.user_id, item
FROM my_table AS t, UNNEST(t.tags) AS item

-- ClickHouse: ARRAY JOIN
SELECT t.user_id, item
FROM my_table AS t
ARRAY JOIN t.tags AS item
```

```sql
-- BigQuery: QUALIFY (row deduplication)
SELECT * FROM my_table
QUALIFY ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY ts DESC) = 1

-- ClickHouse: wrap in subquery
SELECT * FROM (
  SELECT *, row_number() OVER (PARTITION BY user_id ORDER BY ts DESC) AS rn
  FROM my_table
) WHERE rn = 1
```

### Function Mapping

#### Date / Time

| BigQuery | ClickHouse |
|----------|-----------|
| `CURRENT_DATE()` | `today()` |
| `CURRENT_TIMESTAMP()` | `now()` / `now64()` |
| `DATE(ts)` | `toDate(ts)` |
| `DATE_TRUNC(date, unit)` | `date_trunc('unit', d)` (CH 22.6+) or `toStartOfMonth(d)` etc. |
| `TIMESTAMP_TRUNC(ts, unit)` | `date_trunc('unit', ts)` |
| `DATE_DIFF(d1, d2, unit)` | `dateDiff('unit', d2, d1)` — **args reversed** |
| `TIMESTAMP_DIFF(ts1, ts2, unit)` | `dateDiff('unit', ts2, ts1)` — **args reversed** |
| `DATE_ADD(d, INTERVAL n u)` | `d + INTERVAL n u` |
| `FORMAT_DATE('%Y-%m-%d', d)` | `formatDateTime(d, '%Y-%m-%d')` |
| `PARSE_DATE('%Y-%m-%d', s)` | `parseDateTime(s, '%Y-%m-%d')` |
| `UNIX_SECONDS(ts)` | `toUnixTimestamp(ts)` |
| `TIMESTAMP_SECONDS(n)` | `fromUnixTimestamp(n)` |

#### Aggregation

| BigQuery | ClickHouse |
|----------|-----------|
| `COUNT(DISTINCT x)` | `uniqExact(x)` (exact) / `uniq(x)` (approx) |
| `STRING_AGG(x, delim)` | `arrayStringConcat(groupArray(x), delim)` |
| `ARRAY_AGG(x)` | `groupArray(x)` |
| `ANY_VALUE(x)` | `any(x)` |
| `APPROX_COUNT_DISTINCT(x)` | `uniq(x)` |
| `COUNTIF(cond)` | `countIf(cond)` |
| `APPROX_TOP_COUNT(x, n)` | `topK(n)(x)` |

#### Conditional / Safety

| BigQuery | ClickHouse |
|----------|-----------|
| `IF(cond, t, f)` | `if(cond, t, f)` |
| `IFNULL(x, alt)` | `ifNull(x, alt)` |
| `SAFE_DIVIDE(a, b)` | `if(b = 0, NULL, a / b)` |
| `SAFE_CAST(x AS T)` | `accurateCastOrNull(x, 'T')` |
| `COALESCE(a, b, c)` | `coalesce(a, b, c)` |

#### String

| BigQuery | ClickHouse |
|----------|-----------|
| `SPLIT(s, delim)` | `splitByString(delim, s)` → 1-indexed Array |
| `REGEXP_CONTAINS(s, p)` | `match(s, p)` |
| `REGEXP_EXTRACT(s, p)` | `extract(s, p)` |
| `REGEXP_REPLACE(s, p, r)` | `replaceRegexpAll(s, p, r)` |
| `STARTS_WITH(s, prefix)` | `startsWith(s, prefix)` |
| `TO_JSON_STRING(val)` | `toJSONString(val)` |
| `JSON_EXTRACT_SCALAR(j, path)` | `JSONExtractString(j, 'key')` |

### DML / Mutations

```sql
-- BigQuery UPDATE
UPDATE my_table SET status = 'active' WHERE id = 1;

-- ClickHouse (asynchronous mutation)
ALTER TABLE my_table UPDATE status = 'active' WHERE id = 1;
-- ⚠️  Mutations are asynchronous and not transactional in ClickHouse
```

```sql
-- BigQuery DELETE
DELETE FROM my_table WHERE created_at < '2020-01-01';

-- ClickHouse (asynchronous mutation)
ALTER TABLE my_table DELETE WHERE created_at < '2020-01-01';
-- ✅  Lightweight DELETE available in CH 23.3+ without full mutation overhead
```

### Views & Materialized Views

```sql
-- BigQuery
CREATE OR REPLACE VIEW `project.dataset.my_view` AS
SELECT ...;

-- ClickHouse (identical syntax, just remove project qualifier)
CREATE OR REPLACE VIEW database.my_view AS
SELECT ...;
```

```sql
-- BigQuery Scheduled Query (approximation via Materialized View)
-- BigQuery has no CREATE MATERIALIZED VIEW with automatic refresh

-- ClickHouse
CREATE MATERIALIZED VIEW database.mv_name
TO database.target_table AS
SELECT ...;
```

### Stored Procedures & UDFs

```sql
-- BigQuery scalar function
CREATE FUNCTION my_dataset.add_tax(price FLOAT64, rate FLOAT64)
RETURNS FLOAT64
AS (price * (1 + rate));

-- ClickHouse UDF
CREATE FUNCTION add_tax AS (price, rate) -> price * (1 + rate);
```

> **Note:** BigQuery scripting-based `CREATE PROCEDURE` (with DECLARE, SET, loops) has **no equivalent** in ClickHouse. These must be rewritten as application-layer logic. The converter will produce a High-risk flag and suggest alternatives.

---

## Testing

### Test Payloads Available

Import from `backend/tests/fixtures/sample_payloads.py`:

```python
from tests.fixtures.sample_payloads import (
    VALID_BQ_TO_CLICKHOUSE_QUERY,
    VALID_BQ_TO_CLICKHOUSE_TABLE_DDL,
    VALID_BQ_TO_CLICKHOUSE_VIEW,
    VALID_BQ_TO_CLICKHOUSE_SQLGLOT,
    VALID_BQ_TO_CLICKHOUSE_ARRAY_QUERY,
    VALID_BQ_TO_CLICKHOUSE_STORED_PROCEDURE,
    VALID_BQ_TO_CLICKHOUSE_BATCH,
)
```

### Manual Test via API

```bash
# Quick Convert — BigQuery SELECT → ClickHouse
curl -X POST http://localhost:8000/api/conversions/standalone \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -H "X-Workspace-ID: 1" \
  -d '{
    "source_code": "SELECT user_id, DATE_TRUNC(event_time, DAY) AS day, COUNT(*) AS cnt FROM `proj.ds.events` GROUP BY 1, 2",
    "source_dialect": "BigQuery",
    "target_dialect": "ClickHouse",
    "asset_type": "QUERY",
    "asset_name": "daily_counts",
    "aws_region": "us-east-1",
    "bedrock_model": "us.anthropic.claude-3-5-sonnet-20241022-v2:0",
    "prompt_template_path": "prompts/bigquery-to-clickhouse-conversion.txt",
    "max_retries": 3,
    "use_sqlglot": false
  }'
```

Expected response shape:
```json
{
  "id": 42,
  "workspace_id": 1,
  "source_dialect": "BigQuery",
  "target_dialect": "ClickHouse",
  "status": "completed",
  "target_code": "SELECT user_id, date_trunc('day', event_time) AS day, count() AS cnt\nFROM database.events\nGROUP BY user_id, day",
  "accuracy_score": null,
  "retry_count": 0
}
```

> **Note:** `accuracy_score` is embedded in `target_code` as part of the raw JSON response from Bedrock. The service extracts the `converted_sql` field via `unescape_code_output()`. Full structured JSON (including score, risks, recommendations) is available in the Bedrock response — parsing it in the service layer is a potential future enhancement.

### Run Existing Tests

```bash
cd backend

# Unit tests (ConversionService layer)
pytest tests/unit/test_conversion_service.py -v

# Integration tests (full router → service → SQLite stack)
pytest tests/integration/test_conversion_router_integration.py -v

# All conversion tests
pytest tests/ -k "conversion" -v
```

---

## Architecture Decisions

### Why only BigQuery as source for ClickHouse?

ClickHouse is most commonly adopted as a migration target **from BigQuery** — both are columnar OLAP engines and share analytical workload patterns. The conversion complexity (ARRAY JOIN idioms, MergeTree engine selection, TTL, ORDER BY requirement) is specific to the BigQuery→ClickHouse semantic gap.

Other source → ClickHouse paths (Redshift→ClickHouse, SQL Server→ClickHouse) would require separate prompt templates. They are not blocked by the system — `ClickHouse` is a valid target regardless of source — but no dedicated template exists for them yet. The generic fallback template would be used, which produces lower accuracy.

### Why not add ClickHouse as a source dialect?

ClickHouse-to-X migrations are rare and outside the current product scope. It remains source-only for established warehouses (BigQuery, Redshift, SQL Server, Sybase, IBM Db2).

### Why SQLGlot pre-processing for ClickHouse?

SQLGlot handles straightforward mechanical transformations (function case normalization, basic syntax differences) in milliseconds without any API cost. Bedrock then handles the semantically complex parts (engine selection, ARRAY JOIN rewrite, data type decisions, risk assessment). The two-step approach improves accuracy and reduces token waste on trivially mechanical rewrites.

### Bedrock model choice

`us.anthropic.claude-3-5-sonnet-20241022-v2:0` is used as the default because:
- It has the strongest SQL reasoning capability in the Claude family
- It supports 200K context window (important for large DDL / stored procedures)
- The `max_tokens=8192` output limit is sufficient for even complex stored procedures
- Cross-region inference routing (`us.` prefix) provides higher availability and throughput

---

*Last updated: June 2026*
