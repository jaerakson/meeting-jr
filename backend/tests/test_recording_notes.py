"""Recording Notes API 테스트."""

import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import init_db, create_job, delete_job

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    init_db()


@pytest.fixture()
def job_id():
    jid = str(uuid.uuid4())
    create_job(jid, "test.webm", title="테스트 회의")
    yield jid
    delete_job(jid)


def test_save_and_list_notes(job_id):
    notes = [
        {"id": str(uuid.uuid4()), "timestamp": 10.5, "content": "중요 포인트"},
        {"id": str(uuid.uuid4()), "timestamp": 30.0},
    ]
    res = client.post(f"/api/jobs/{job_id}/notes", json={"notes": notes})
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 2
    assert data[0]["timestamp"] == 10.5
    assert data[0]["content"] == "중요 포인트"
    assert data[1]["content"] == ""

    # GET
    res2 = client.get(f"/api/jobs/{job_id}/notes")
    assert res2.status_code == 200
    assert len(res2.json()) == 2


def test_delete_note(job_id):
    note_id = str(uuid.uuid4())
    client.post(f"/api/jobs/{job_id}/notes", json={"notes": [
        {"id": note_id, "timestamp": 5.0, "content": "삭제 대상"}
    ]})

    res = client.delete(f"/api/jobs/{job_id}/notes/{note_id}")
    assert res.status_code == 200
    assert res.json()["status"] == "deleted"

    # 삭제 후 조회
    res2 = client.get(f"/api/jobs/{job_id}/notes")
    assert len(res2.json()) == 0


def test_delete_nonexistent_note(job_id):
    res = client.delete(f"/api/jobs/{job_id}/notes/{uuid.uuid4()}")
    assert res.status_code == 404


def test_notes_invalid_body(job_id):
    res = client.post(f"/api/jobs/{job_id}/notes", json={"notes": "not a list"})
    assert res.status_code == 422


def test_notes_404_job():
    fake_id = str(uuid.uuid4())
    res = client.get(f"/api/jobs/{fake_id}/notes")
    assert res.status_code == 404
