"""Shared pytest fixtures for the whole backend. Apps add their own in <app>/tests/."""

import pytest
from rest_framework.test import APIClient


@pytest.fixture
def api_client() -> APIClient:
    """An unauthenticated DRF test client."""
    return APIClient()
