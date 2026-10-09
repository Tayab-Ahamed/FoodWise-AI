import pytest
from fastapi.testclient import TestClient
from backend.app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("FOODWISE_DB", str(tmp_path / "test.sqlite3"))
    monkeypatch.setenv("FOODWISE_DEMO", "true")
    with TestClient(app) as client:
        yield client
