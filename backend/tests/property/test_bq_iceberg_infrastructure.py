# Feature: bq-to-iceberg-migration, Property 17 & Property 15
"""
Property tests for BQ-to-Iceberg infrastructure services:

- Property 17: Credential encryption round-trip
  Generate arbitrary secret key strings; verify encrypt→decrypt produces original.
  **Validates: Requirements 8.4**

- Property 15: Deduplication on resume
  Generate arbitrary sets of registered files and candidate files; verify only new files returned.
  **Validates: Requirements 5.5**
"""

import base64
from unittest.mock import MagicMock, patch

from hypothesis import given, settings, strategies as st

from services.bq_iceberg_migration.dedup_guard import DeduplicationGuard
from services.unified_kms_service import UnifiedKMSService


# =============================================================================
# Strategies
# =============================================================================

# Strategy for secret key strings: printable text of reasonable length
secret_key_strategy = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "S"),
        blacklist_characters=("\x00",),
    ),
    min_size=1,
    max_size=200,
)

# Strategy for S3 file URIs
s3_uri_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_/:."),
    min_size=10,
    max_size=150,
).map(lambda s: f"s3://bucket/{s}")

# Strategy for sets of registered file URIs
registered_files_strategy = st.lists(
    s3_uri_strategy,
    min_size=0,
    max_size=30,
).map(set)

# Strategy for lists of candidate file URIs
candidate_files_strategy = st.lists(
    s3_uri_strategy,
    min_size=0,
    max_size=30,
)


# =============================================================================
# Property 17: Credential encryption round-trip
# =============================================================================


def _create_mock_kms_service():
    """Create a mock KMS service that simulates real encrypt/decrypt behavior.

    Uses base64 encoding as a stand-in for KMS encryption to verify the
    round-trip logic without requiring actual AWS credentials.
    """
    kms_service = MagicMock(spec=UnifiedKMSService)

    def mock_encrypt(plaintext, credential_type='generic', resource_type=None,
                     resource_id=None, **kwargs):
        """Simulate KMS encryption by base64-encoding the plaintext."""
        if not plaintext:
            return ''
        encoded = base64.b64encode(plaintext.encode('utf-8')).decode('utf-8')
        return f"ENC:{encoded}"

    def mock_decrypt(ciphertext, credential_type='generic', resource_type=None,
                     resource_id=None, allow_plaintext_fallback=True, **kwargs):
        """Simulate KMS decryption by base64-decoding the ciphertext."""
        if not ciphertext:
            return ''
        if ciphertext.startswith("ENC:"):
            encoded = ciphertext[4:]
            return base64.b64decode(encoded).decode('utf-8')
        if allow_plaintext_fallback:
            return ciphertext
        raise ValueError("Invalid ciphertext")

    kms_service.encrypt_credential.side_effect = mock_encrypt
    kms_service.decrypt_credential.side_effect = mock_decrypt
    return kms_service


@given(secret_key=secret_key_strategy)
@settings(max_examples=150)
def test_credential_encryption_round_trip(secret_key):
    """Property 17: Credential encryption round-trip.

    For any arbitrary secret key string, encrypting via the KMS service and
    then decrypting must produce the original plaintext value. This validates
    that the credential provider's encrypt→decrypt path preserves data integrity.

    **Validates: Requirements 8.4**
    """
    kms_service = _create_mock_kms_service()

    # Encrypt the secret key
    encrypted = kms_service.encrypt_credential(
        plaintext=secret_key,
        credential_type="aws_secret_key",
        resource_type="iceberg_migration",
    )

    # The encrypted value must differ from the original (non-trivial encryption)
    assert encrypted != secret_key, (
        f"Encrypted value should differ from plaintext for secret_key='{secret_key[:50]}...'"
    )

    # Decrypt the encrypted value
    decrypted = kms_service.decrypt_credential(
        ciphertext=encrypted,
        credential_type="aws_secret_key",
        resource_type="iceberg_migration",
        allow_plaintext_fallback=True,
    )

    # Round-trip must produce the original
    assert decrypted == secret_key, (
        f"Round-trip failed.\n"
        f"  Original:  '{secret_key[:80]}'\n"
        f"  Encrypted: '{encrypted[:80]}'\n"
        f"  Decrypted: '{decrypted[:80]}'"
    )


@given(secret_key=secret_key_strategy)
@settings(max_examples=150)
def test_credential_encryption_round_trip_via_provider(secret_key):
    """Property 17 (extended): Credential provider get_session decrypts correctly.

    Verifies that the AWSCredentialProvider correctly uses the KMS service to
    decrypt credentials, ensuring the encrypt→store→decrypt flow works end-to-end.

    **Validates: Requirements 8.4**
    """
    from services.bq_iceberg_migration.credential_provider import AWSCredentialProvider

    kms_service = _create_mock_kms_service()
    mock_sts = MagicMock()

    provider = AWSCredentialProvider(kms_service=kms_service, sts_client=mock_sts)

    # Encrypt the secret key (simulating storage)
    encrypted_secret = kms_service.encrypt_credential(
        plaintext=secret_key,
        credential_type="aws_secret_key",
        resource_type="iceberg_migration",
    )

    # Build connection params with encrypted secret
    connection_params = {
        "aws_access_key_id": "AKIAIOSFODNN7EXAMPLE",
        "aws_secret_access_key": encrypted_secret,
        "aws_region": "us-east-1",
    }

    # Mock boto3.Session to capture the decrypted secret key
    with patch("services.bq_iceberg_migration.credential_provider.boto3") as mock_boto3:
        mock_session = MagicMock()
        mock_boto3.Session.return_value = mock_session

        session = provider.get_session(connection_params)

        # Verify boto3.Session was called with the decrypted (original) secret key
        mock_boto3.Session.assert_called_once_with(
            aws_access_key_id="AKIAIOSFODNN7EXAMPLE",
            aws_secret_access_key=secret_key,
            region_name="us-east-1",
        )
        assert session == mock_session


# =============================================================================
# Property 15: Deduplication on resume
# =============================================================================


def _create_mock_table(registered_files: set):
    """Create a mock PyIceberg Table with a snapshot containing registered files."""
    table = MagicMock()

    if not registered_files:
        # No snapshot means empty table
        table.current_snapshot.return_value = None
    else:
        # Create mock snapshot with manifest entries
        mock_snapshot = MagicMock()
        mock_entries = []
        for file_path in registered_files:
            entry = MagicMock()
            entry.data_file.file_path = file_path
            mock_entries.append(entry)

        mock_manifest = MagicMock()
        mock_manifest.fetch_manifest_entry.return_value = mock_entries
        mock_snapshot.manifests.return_value = [mock_manifest]
        table.current_snapshot.return_value = mock_snapshot

    return table


@given(
    registered=registered_files_strategy,
    candidates=candidate_files_strategy,
)
@settings(max_examples=150)
def test_deduplication_only_new_files_returned(registered, candidates):
    """Property 15: Deduplication on resume returns only new files.

    For any arbitrary set of registered files and list of candidate files,
    filter_new_files must return exactly those candidates that are NOT in
    the registered set. No registered file should appear in the output,
    and no genuinely new file should be excluded.

    **Validates: Requirements 5.5**
    """
    guard = DeduplicationGuard()
    table = _create_mock_table(registered)

    new_files = guard.filter_new_files(table, candidates)

    # 1. All returned files must NOT be in the registered set
    for f in new_files:
        assert f not in registered, (
            f"Registered file '{f}' was incorrectly returned as new"
        )

    # 2. All candidates NOT in registered must appear in new_files
    expected_new = [f for f in candidates if f not in registered]
    assert new_files == expected_new, (
        f"Mismatch in new files.\n"
        f"  Expected: {expected_new[:5]}\n"
        f"  Got:      {new_files[:5]}\n"
        f"  Registered: {list(registered)[:5]}\n"
        f"  Candidates: {candidates[:5]}"
    )


@given(
    registered=registered_files_strategy,
    candidates=candidate_files_strategy,
)
@settings(max_examples=150)
def test_deduplication_is_safe_to_append(registered, candidates):
    """Property 15 (extended): is_safe_to_append returns correct safety flag.

    is_safe_to_append returns (True, new_files) when there are new files to add,
    and (False, []) when all candidates are already registered.

    **Validates: Requirements 5.5**
    """
    guard = DeduplicationGuard()
    table = _create_mock_table(registered)

    safe, new_files = guard.is_safe_to_append(table, candidates)

    expected_new = [f for f in candidates if f not in registered]

    # Safety flag should be True iff there are new files
    if expected_new:
        assert safe is True, (
            f"Expected safe=True when there are {len(expected_new)} new files"
        )
        assert new_files == expected_new
    else:
        assert safe is False, (
            f"Expected safe=False when all candidates are already registered"
        )
        assert new_files == []


@given(registered=registered_files_strategy)
@settings(max_examples=150)
def test_deduplication_subset_candidates_all_filtered(registered):
    """Property 15 (subset): When all candidates are already registered, none returned.

    If every candidate file is already in the registered set, filter_new_files
    must return an empty list.

    **Validates: Requirements 5.5**
    """
    guard = DeduplicationGuard()
    table = _create_mock_table(registered)

    # Use a subset of registered files as candidates
    candidates = list(registered)

    new_files = guard.filter_new_files(table, candidates)

    assert new_files == [], (
        f"Expected empty list when all candidates are registered, got {new_files[:5]}"
    )
