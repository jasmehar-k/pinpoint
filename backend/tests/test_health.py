from fastapi.testclient import TestClient

from api.main import app


def test_health_without_db(monkeypatch):
    monkeypatch.setattr("config.DATABASE_URL", "")
    res = TestClient(app).get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"
    assert res.json()["db"] is False
