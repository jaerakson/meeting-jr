"""PATCH /api/jobs/{job_id}/summary 엔드포인트 테스트."""

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


def _create_job(client) -> str:
    """테스트용 job을 생성하고 job_id를 반환한다."""
    import io
    fake_audio = io.BytesIO(b"\xff\xfb\x90\x00" * 100)
    res = client.post(
        "/api/upload",
        files={"file": ("test.mp3", fake_audio, "audio/mpeg")},
        data={"category_id": "meeting"},
    )
    return res.json()["job_id"]


def test_patch_summary_success(client, tmp_path):
    """정상적인 요약 수정 시 200 반환 및 파일 저장."""
    job_id = _create_job(client)
    new_summary = "## 핵심 요약\n테스트 요약입니다."

    res = client.patch(
        f"/api/jobs/{job_id}/summary",
        json={"summary": new_summary},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "updated"

    # DB에 저장되었는지 확인
    detail = client.get(f"/api/jobs/{job_id}").json()
    assert detail["summary"] == new_summary

    # 파일로도 저장되었는지 확인
    output_dir = tmp_path / "output"
    summary_file = output_dir / f"{job_id}_요약.md"
    assert summary_file.exists()
    assert summary_file.read_text(encoding="utf-8") == new_summary


def test_patch_summary_empty_body(client):
    """빈 요약 전송 시 422 반환."""
    job_id = _create_job(client)

    res = client.patch(
        f"/api/jobs/{job_id}/summary",
        json={"summary": ""},
    )
    assert res.status_code == 422


def test_patch_summary_not_found(client):
    """존재하지 않는 job_id로 요청 시 404 반환."""
    res = client.patch(
        "/api/jobs/nonexistent-id/summary",
        json={"summary": "test"},
    )
    assert res.status_code == 404
