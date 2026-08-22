import sys
import os
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


@pytest.fixture(autouse=True)
def tmp_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    import app.database as db_module
    monkeypatch.setattr(db_module, "DB_PATH", db_path)
    db_module.init_db()
    yield db_path


@pytest.fixture()
def client(tmp_db):
    from app.main import app
    with TestClient(app) as c:
        yield c


def test_get_meetings_empty(client):
    res = client.get("/api/meetings")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 0
    assert data["items"] == []
    assert data["page"] == 1
    assert data["pages"] == 1


def test_get_meetings_with_query(client, tmp_db):
    import app.database as db
    db.create_job("x1", "x1.webm", title="팀 주간회의")
    db.create_job("x2", "x2.webm", title="기획 회의")

    res = client.get("/api/meetings?q=기획")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "기획 회의"


def test_get_meetings_pagination(client, tmp_db):
    import app.database as db
    for i in range(14):
        db.create_job(f"p{i}", f"p{i}.webm", title=f"회의 {i}")

    res = client.get("/api/meetings?page=1&limit=12")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 14
    assert data["pages"] == 2
    assert len(data["items"]) == 12

    res2 = client.get("/api/meetings?page=2&limit=12")
    assert len(res2.json()["items"]) == 2
