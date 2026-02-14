"""
Pytest configuration and fixtures
"""

import pytest
from hypothesis import settings

# Configure Hypothesis for property-based testing
settings.register_profile("ci", max_examples=100)
settings.load_profile("ci")


@pytest.fixture
def sample_user():
    """Fixture providing a sample user"""
    return {
        "id": 1,
        "username": "testuser",
        "role": "user",
        "created_at": "2026-01-25T10:00:00Z"
    }


@pytest.fixture
def sample_admin():
    """Fixture providing a sample admin user"""
    return {
        "id": 2,
        "username": "admin",
        "role": "admin",
        "created_at": "2026-01-25T10:00:00Z"
    }
