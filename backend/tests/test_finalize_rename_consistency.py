"""finalize → rename-speakers 경로에 걸친 회귀 테스트 (PR B, director 지시).

배경: finalize_job으로 transcript를 편집(예: 새 발언 줄 추가)한 뒤, get_segments()가
lazy 백필한 **낡은(편집 전) segments**가 DB에 남아있으면, 이후 rename-speakers가
그 낡은 segments로 재렌더해 사용자의 편집을 통째로 덮어쓴다.

PR A 시점에는 transcript_segments의 소비자가 없어 이 낡음이 무해했다. PR B가
apply-match/rename-speakers에 재렌더를 붙이면서 **데이터 손실로 승격**됐다 —
부분 map(merge-safe) 회귀와 같은 부류다. backend-b가 finalize_job에서
parse_transcript(transcript)로 segments를 함께 갱신해 닫았다
(main.py:409-418, transcript_segments도 함께 update_job_result).

이 결함은 finalize_job 하나만 보거나 rename-speakers 하나만 봐서는 안 잡힌다 —
두 엔드포인트에 걸친 상태(같은 job의 DB 컬럼)를 순서대로 거쳐야 재현된다.

단언을 통과시키려고 약화하지 말 것.
"""

import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    import app.database as db_module
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "test.db")
    db_module.init_db()

    import app.main as main_module
    (tmp_path / "input").mkdir()
    (tmp_path / "output").mkdir()
    monkeypatch.setattr(main_module, "INPUT_DIR", tmp_path / "input")
    monkeypatch.setattr(main_module, "OUTPUT_DIR", tmp_path / "output")
    monkeypatch.setattr(main_module, "SPEAKERS_FILE", tmp_path / "speakers.json")

    import app.summarizer as summarizer_module
    monkeypatch.setattr(summarizer_module, "OUTPUT_DIR", tmp_path / "output")
    monkeypatch.setattr(summarizer_module, "SPEAKERS_FILE", tmp_path / "speakers.json")

    from app.main import app
    with TestClient(app) as c:
        yield c


def _create_done_meeting(job_id, transcript, speakers, diarization=None):
    import app.database as db
    db.create_job(job_id, f"{job_id}.webm", title="테스트 회의")
    db.update_job_result(
        job_id,
        summary="## 요약\n이전 버전",
        transcript=transcript,
        speakers=speakers,
        diarization=diarization,
        duration_sec=60,
        status="done",
    )


def _get_speakers(job: dict) -> dict:
    import json
    speakers = job.get("speakers", {})
    if isinstance(speakers, str):
        speakers = json.loads(speakers)
    return speakers


def test_finalize_edit_survives_subsequent_rename_speakers(client):
    """finalize로 transcript를 편집(새 줄 추가)한 뒤 rename-speakers를 호출해도
    편집 내용이 사라지면 안 된다."""
    original_transcript = "[00:00] SPEAKER_00: 원본 문장\n[00:05] SPEAKER_01: 두번째"
    _create_done_meeting(
        "finalize-rename-1", original_transcript,
        speakers={"SPEAKER_00": "김팀장", "SPEAKER_01": "이대리"},
    )

    # finalize 이전에 segments를 먼저 확보해둔다 — "이미 lazy 백필된 (편집 전)
    # segments가 DB에 남아있는" 상태를 명시적으로 재현한다. 이 백필 자체는 무해하며,
    # 문제는 finalize가 이 낡은 값을 갱신하는지 여부다.
    from app.transcript import get_segments
    pre_segments = get_segments("finalize-rename-1")
    assert len(pre_segments) == 2  # 편집 전 2줄

    edited_transcript = (
        "[00:00] SPEAKER_00: 수정된 문장\n"
        "[00:05] SPEAKER_01: 두번째\n"
        "[00:10] SPEAKER_00: 새로 추가한 발언"
    )
    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.communicate = AsyncMock(return_value=("# 요약".encode("utf-8"), b""))

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        res = client.post("/api/jobs/finalize-rename-1/finalize", json={
            "transcript": edited_transcript,
            "speaker_map": {"SPEAKER_00": "김팀장", "SPEAKER_01": "이대리"},
        })
    assert res.status_code == 200, f"실제: {res.status_code}, body: {res.text}"

    # finalize 직후: 편집이 그대로 저장돼 있어야 한다.
    job_after_finalize = client.get("/api/jobs/finalize-rename-1").json()
    assert "새로 추가한 발언" in job_after_finalize["transcript"], (
        f"finalize 직후 편집이 반영돼야 함. 실제: {job_after_finalize['transcript']}"
    )

    # rename-speakers 호출 — 편집이 여전히 살아있어야 한다.
    res2 = client.post("/api/jobs/finalize-rename-1/rename-speakers", json={
        "speaker_map": {"SPEAKER_00": "박부장"},
    })
    assert res2.status_code == 200

    job = client.get("/api/jobs/finalize-rename-1").json()
    assert "새로 추가한 발언" in job["transcript"], (
        f"finalize로 추가한 발언이 이후 rename-speakers 호출 뒤 사라지면 안 됨 "
        f"(finalize가 transcript_segments를 갱신하지 않으면, rename-speakers가 "
        f"편집 전 낡은 segments로 재렌더해 이 발언이 통째로 사라진다). "
        f"실제: {job['transcript']}"
    )
    assert job["transcript"].count("박부장:") == 2, (
        f"편집으로 늘어난 SPEAKER_00 발언 2건 모두 새 이름으로 반영돼야 함. "
        f"실제: {job['transcript']}"
    )
    assert "이대리:" in job["transcript"]

    from app.transcript import get_segments, render
    post_segments = get_segments("finalize-rename-1")
    assert len(post_segments) == 3, (
        f"finalize 이후 segments도 편집된 3줄로 갱신돼 있어야 함. 실제: {len(post_segments)}줄"
    )
    assert render(post_segments, _get_speakers(job)) == job["transcript"]
