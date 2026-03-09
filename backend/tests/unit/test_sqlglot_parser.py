"""
Unit tests for SqlGlotParser service.

Tests parse_and_transpile across supported dialects, unsupported dialects,
invalid SQL, and edge cases.
"""

import pytest

from services.sqlglot_parser import (
    DIALECT_MAP,
    UNSUPPORTED_DIALECTS,
    SqlGlotParser,
    SqlGlotResult,
)


@pytest.fixture
def parser():
    """Provide a fresh SqlGlotParser instance."""
    return SqlGlotParser()


# ---------------------------------------------------------------------------
# Success cases
# ---------------------------------------------------------------------------


class TestSuccessfulTranspile:
    """Tests where sqlglot should successfully parse and transpile."""

    def test_bigquery_select_to_redshift(self, parser):
        """Test transpiling a BigQuery SELECT to Redshift dialect."""
        source = "SELECT * FROM `dataset.table` WHERE created_at > CURRENT_TIMESTAMP()"
        result = parser.parse_and_transpile(source, "bigquery", "redshift")

        assert result.success is True
        assert result.warning is None
        assert result.transpiled_code is not None
        assert len(result.transpiled_code) > 0

    def test_mysql_to_postgres(self, parser):
        """Test transpiling MySQL to PostgreSQL."""
        source = "SELECT IFNULL(name, 'unknown') FROM users LIMIT 10"
        result = parser.parse_and_transpile(source, "mysql", "postgres")

        assert result.success is True
        assert result.warning is None
        assert result.transpiled_code is not None

    def test_postgres_to_snowflake(self, parser):
        """Test transpiling PostgreSQL to Snowflake."""
        source = "SELECT id, name FROM users WHERE active = TRUE"
        result = parser.parse_and_transpile(source, "postgres", "snowflake")

        assert result.success is True
        assert result.transpiled_code is not None

    def test_postgresql_alias_maps_to_postgres(self, parser):
        """Test that 'postgresql' alias works the same as 'postgres'."""
        source = "SELECT 1"
        result = parser.parse_and_transpile(source, "postgresql", "redshift")

        assert result.success is True
        assert result.transpiled_code is not None

    def test_mssql_alias_maps_to_tsql(self, parser):
        """Test that 'mssql' and 'sqlserver' aliases map to tsql."""
        source = "SELECT TOP 5 * FROM orders"
        result_mssql = parser.parse_and_transpile(source, "mssql", "postgres")
        result_sqlserver = parser.parse_and_transpile(source, "sqlserver", "postgres")

        assert result_mssql.success is True
        assert result_sqlserver.success is True

    def test_case_insensitive_dialect(self, parser):
        """Test that dialect names are case-insensitive."""
        source = "SELECT 1"
        result = parser.parse_and_transpile(source, "BigQuery", "Redshift")

        assert result.success is True

    def test_dialect_with_whitespace(self, parser):
        """Test that leading/trailing whitespace in dialect names is trimmed."""
        source = "SELECT 1"
        result = parser.parse_and_transpile(source, "  bigquery  ", "  redshift  ")

        assert result.success is True

    def test_multiple_statements(self, parser):
        """Test transpiling multiple SQL statements."""
        source = "SELECT 1; SELECT 2"
        result = parser.parse_and_transpile(source, "postgres", "mysql")

        assert result.success is True
        assert result.transpiled_code is not None


# ---------------------------------------------------------------------------
# Unsupported dialect cases
# ---------------------------------------------------------------------------


class TestUnsupportedDialects:
    """Tests for dialects that sqlglot cannot handle."""

    def test_mongodb_source_returns_failure(self, parser):
        """Test that mongodb as source dialect returns success=False."""
        result = parser.parse_and_transpile(
            "db.collection.find({})", "mongodb", "redshift"
        )

        assert result.success is False
        assert result.transpiled_code is None
        assert result.warning is not None
        assert "mongodb" in result.warning.lower()

    def test_documentdb_source_returns_failure(self, parser):
        """Test that documentdb as source dialect returns success=False."""
        result = parser.parse_and_transpile(
            "db.find()", "documentdb", "postgres"
        )

        assert result.success is False
        assert result.transpiled_code is None
        assert result.warning is not None

    def test_mongodb_target_returns_failure(self, parser):
        """Test that mongodb as target dialect returns success=False."""
        result = parser.parse_and_transpile(
            "SELECT 1", "postgres", "mongodb"
        )

        assert result.success is False
        assert result.transpiled_code is None
        assert result.warning is not None
        assert "mongodb" in result.warning.lower()

    def test_dynamodb_returns_failure(self, parser):
        """Test that dynamodb returns success=False."""
        result = parser.parse_and_transpile("query", "dynamodb", "postgres")

        assert result.success is False
        assert result.warning is not None

    def test_unknown_source_dialect_returns_failure(self, parser):
        """Test that a completely unknown dialect returns success=False."""
        result = parser.parse_and_transpile(
            "SELECT 1", "foobardb", "postgres"
        )

        assert result.success is False
        assert result.transpiled_code is None
        assert result.warning is not None
        assert "foobardb" in result.warning

    def test_unknown_target_dialect_returns_failure(self, parser):
        """Test that an unknown target dialect returns success=False."""
        result = parser.parse_and_transpile(
            "SELECT 1", "postgres", "unknowndb"
        )

        assert result.success is False
        assert result.transpiled_code is None
        assert result.warning is not None
        assert "unknowndb" in result.warning


# ---------------------------------------------------------------------------
# Parse failure cases
# ---------------------------------------------------------------------------


class TestParseFailures:
    """Tests where sqlglot should fail to parse invalid SQL."""

    def test_invalid_sql_returns_failure(self, parser):
        """Test that completely invalid SQL returns success=False with warning."""
        result = parser.parse_and_transpile(
            "THIS IS NOT VALID SQL AT ALL !!!", "bigquery", "redshift"
        )

        assert result.success is False
        assert result.transpiled_code is None
        assert result.warning is not None

    def test_empty_source_code(self, parser):
        """Test that empty source code is handled gracefully."""
        result = parser.parse_and_transpile("", "bigquery", "redshift")

        # sqlglot may or may not parse empty string — either way, no exception
        assert isinstance(result, SqlGlotResult)
        assert result.warning is None or isinstance(result.warning, str)


# ---------------------------------------------------------------------------
# SqlGlotResult dataclass
# ---------------------------------------------------------------------------


class TestSqlGlotResult:
    """Tests for the SqlGlotResult dataclass."""

    def test_success_result(self):
        """Test creating a successful result."""
        result = SqlGlotResult(
            transpiled_code="SELECT 1",
            success=True,
            warning=None,
        )
        assert result.transpiled_code == "SELECT 1"
        assert result.success is True
        assert result.warning is None

    def test_failure_result(self):
        """Test creating a failure result."""
        result = SqlGlotResult(
            transpiled_code=None,
            success=False,
            warning="Parse failed",
        )
        assert result.transpiled_code is None
        assert result.success is False
        assert result.warning == "Parse failed"


# ---------------------------------------------------------------------------
# Dialect map coverage
# ---------------------------------------------------------------------------


class TestDialectMap:
    """Tests for the dialect mapping configuration."""

    def test_all_expected_dialects_present(self):
        """Test that key platform dialects are in the map."""
        expected = [
            "bigquery", "redshift", "postgres", "postgresql",
            "mysql", "snowflake", "oracle", "tsql", "mssql",
        ]
        for dialect in expected:
            assert dialect in DIALECT_MAP, f"{dialect} missing from DIALECT_MAP"

    def test_unsupported_dialects_not_in_map(self):
        """Test that unsupported dialects are not in the dialect map."""
        for dialect in UNSUPPORTED_DIALECTS:
            assert dialect not in DIALECT_MAP

    def test_no_exception_raised(self, parser):
        """Test that parse_and_transpile never raises, even with bad input."""
        # None of these should raise
        bad_inputs = [
            ("", "", ""),
            ("SELECT 1", "", ""),
            ("SELECT 1", "bigquery", ""),
        ]
        for source, src_d, tgt_d in bad_inputs:
            result = parser.parse_and_transpile(source, src_d, tgt_d)
            assert isinstance(result, SqlGlotResult)
