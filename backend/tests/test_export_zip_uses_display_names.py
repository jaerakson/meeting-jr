"""GET /api/export (ZIP 전체 내보내기)가 라벨이 아니라 실명을 내보내야 한다
(PR C 2라운드, director 지시 T6).

## 배경
`export_all_meetings`(main.py:1750~)는 `job["transcript"]`를 **그대로**
`transcript.txt`와 `summary.md`의 스크립트 섹션에 쓴다. 새 계약(저장되는 transcript는
항상 라벨 그대로, 표시는 소비 시점에 렌더)에서는 여기도 `render(get_segments(job),
job.speakers)`로 이름을 적용해야 하는 **소비 지점**이다. 지금은 raw 라벨을 그대로
내보낸다.

## 이 파일이 도달 조건
TDD 1단계 — 구현 전. 빨간불이 정상이다.
"""

import io
import zipfile

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def tmp_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    import app.database as db_module
    monkeypatch.setattr(db_module, "DB_PATH", db_path)
    db_module.init_db()

    import app.main as main_module
    (tmp_path / "input").mkdir()
    monkeypatch.setattr(main_module, "INPUT_DIR", tmp_path / "input")
    yield db_path


@pytest.fixture()
def client(tmp_db):
    from app.main import app
    with TestClient(app) as c:
        yield c


def test_export_zip_transcript_txt_uses_display_names(client):
    """ZIP 안의 transcript.txt는 라벨이 아니라 실명이어야 한다."""
    import app.database as db
    job_id = "export-zip-names"
    db.create_job(job_id, f"{job_id}.webm", title="ZIP 내보내기 테스트")
    db.update_job_result(
        job_id,
        summary="## 요약\n내용",
        transcript="[00:00] SPEAKER_00: 첫마디\n[00:05] SPEAKER_01: 둘째마디",
        speakers={"SPEAKER_00": "김팀장", "SPEAKER_01": "이대리"},
        duration_sec=60,
        status="done",
    )

    res = client.get("/api/export")
    assert res.status_code == 200

    zf = zipfile.ZipFile(io.BytesIO(res.content))
    names = zf.namelist()
    transcript_entry = next((n for n in names if n.endswith("transcript.txt")), None)
    assert transcript_entry is not None, f"transcript.txt가 ZIP에 있어야 한다. 실제: {names}"

    transcript_txt = zf.read(transcript_entry).decode("utf-8")
    assert "김팀장:" in transcript_txt and "이대리:" in transcript_txt, (
        f"transcript.txt는 실명이 적용된 렌더본이어야 한다. 실제: {transcript_txt}"
    )
    assert "SPEAKER_00:" not in transcript_txt and "SPEAKER_01:" not in transcript_txt, (
        f"raw 라벨이 그대로 노출되면 안 된다. 실제: {transcript_txt}"
    )


def test_export_zip_summary_md_script_section_uses_display_names(client):
    """ZIP 안의 summary.md '## 스크립트' 섹션도 실명이어야 한다."""
    import app.database as db
    job_id = "export-zip-summary-names"
    db.create_job(job_id, f"{job_id}.webm", title="ZIP 내보내기 요약 테스트")
    db.update_job_result(
        job_id,
        summary="## 요약\n내용",
        transcript="[00:00] SPEAKER_00: 첫마디\n[00:05] SPEAKER_01: 둘째마디",
        speakers={"SPEAKER_00": "김팀장", "SPEAKER_01": "이대리"},
        duration_sec=60,
        status="done",
    )

    res = client.get("/api/export")
    assert res.status_code == 200

    zf = zipfile.ZipFile(io.BytesIO(res.content))
    names = zf.namelist()
    summary_entry = next((n for n in names if n.endswith("summary.md")), None)
    assert summary_entry is not None, f"summary.md가 ZIP에 있어야 한다. 실제: {names}"

    summary_md = zf.read(summary_entry).decode("utf-8")
    assert "김팀장:" in summary_md and "이대리:" in summary_md, (
        f"summary.md의 스크립트 섹션은 실명이 적용돼야 한다. 실제: {summary_md}"
    )
    assert "SPEAKER_00:" not in summary_md and "SPEAKER_01:" not in summary_md, (
        f"raw 라벨이 그대로 노출되면 안 된다. 실제: {summary_md}"
    )
