import pytest
from fastapi.testclient import TestClient

from config import settings
from main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "storage_dir", str(tmp_path))
    return TestClient(app)
