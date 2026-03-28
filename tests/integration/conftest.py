"""
Integration conftest — fornisce il TestClient FastAPI per tutti i test API.
"""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def client():
    from api.app import create_app
    return TestClient(create_app())
