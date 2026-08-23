import io

import pytest


@pytest.fixture
def client(tmp_path, monkeypatch):
    import app.database as dbmod
    monkeypatch.setattr(dbmod, "DB_PATH", tmp_path / "test.db")
    import app.main as mainmod
    monkeypatch.setattr(mainmod, "INPUT_DIR", tmp_path / "input")
    monkeypatch.setattr(mainmod, "OUTPUT_DIR", tmp_path / "output")
    monkeypatch.setattr(mainmod, "SPEAKERS_FILE", tmp_path / "speakers.json")
    (tmp_path / "input").mkdir()
    (tmp_path / "output").mkdir()
    dbmod.init_db()
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


def test_upload_audio_file(client):
    """mp3 파일 업로드 시 200 + job_id 반환."""
    fake_audio = io.BytesIO(b"\xff\xfb\x90\x00" * 100)
    res = client.post(
        "/api/upload",
        files={"file": ("test.mp3", fake_audio, "audio/mpeg")},
        data={"category_id": "meeting"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "job_id" in data
    assert data["filename"].endswith(".mp3")


def test_upload_txt_file(client):
    """txt 파일 업로드 시 200 + job_id 반환 + awaiting_edit 상태."""
    content = "화자1: 안녕하세요\n화자2: 반갑습니다"
    fake_txt = io.BytesIO(content.encode("utf-8"))
    res = client.post(
        "/api/upload",
        files={"file": ("meeting.txt", fake_txt, "text/plain")},
        data={"category_id": "meeting"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "job_id" in data
    assert data["filename"].endswith(".txt")

    # job 상태가 awaiting_edit인지 확인
    job_res = client.get(f"/api/jobs/{data['job_id']}")
    assert job_res.status_code == 200
    assert job_res.json()["status"] == "awaiting_edit"


def test_upload_invalid_extension(client):
    """.pdf 파일 업로드 시 422 반환."""
    fake_pdf = io.BytesIO(b"%PDF-1.4 fake content")
    res = client.post(
        "/api/upload",
        files={"file": ("document.pdf", fake_pdf, "application/pdf")},
    )
    assert res.status_code == 422
    assert "지원하지 않는 파일 형식" in res.json()["detail"]


def test_upload_empty_file(client):
    """빈 파일 업로드 시 422 반환."""
    empty = io.BytesIO(b"")
    res = client.post(
        "/api/upload",
        files={"file": ("empty.mp3", empty, "audio/mpeg")},
    )
    assert res.status_code == 422
    assert "비어 있습니다" in res.json()["detail"]
