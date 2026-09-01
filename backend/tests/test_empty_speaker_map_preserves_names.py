"""빈 `speaker_map({})`을 보내도 기존 `job.speakers`가 살아남아야 한다 (PR C 2라운드,
director 지시 T10 — 차단급).

## 배경
`database.py:update_job_result`의 `if speakers is not None:` 관문은 `{}`을 `None`과
**다르게** 취급해 그대로 `speakers` 컬럼을 `'{}'`로 덮어쓴다. `finalize_job`
(main.py:550~)이 body의 `speaker_map`을 **무조건** `update_job_result(..., speakers=speaker_map)`에
넘기므로, 프론트가 `speaker_map: {}`를 보내면(예: 이름 편집 없이 재요약만 할 때
`localSpeakerMap` 초기값이 `{}`인 채로 나가는 경로 — front-c4 커밋으로 원인이 이미
확인됨) **회의의 모든 화자 이름이 영구 소실**된다.

`patch_transcript`(main.py, B1 수정본)는 이미 `body_map = body.get("speaker_map") or {}`
+ `if body_map:` 게이트로 이 문제를 막아뒀다 — 그 방어를 `finalize_job`에도 똑같이
적용해야 한다.

## 확정 계약 (director)
빈 맵은 "이름 없음"이 아니라 "갱신 안 함"이다. 키 부재와 빈 맵은 **같은 쪽**으로
가야 한다.

## 이 파일이 도달 조건
TDD 1단계 — 구현 전. finalize 관련 항목(1, 4)은 빨간불이 정상이다. patch_transcript
항목(2, 3)은 B1 수정본에 이미 방어가 있어 **초록불일 수 있다** — 회귀 잠금으로 유지.
"""

import pytest
from unittest.mock import AsyncMock, patch as mock_patch
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
        summary="## 요약",
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


def _finalize(client, job_id, transcript, speaker_map):
    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.communicate = AsyncMock(return_value=("# 요약".encode("utf-8"), b""))
    with mock_patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        return client.post(f"/api/jobs/{job_id}/finalize", json={
            "transcript": transcript,
            "speaker_map": speaker_map,
        })


ORIGINAL = {"SPEAKER_00": "김팀장", "SPEAKER_01": "이대리"}


def test_finalize_with_empty_speaker_map_preserves_existing_names(client):
    """[1] POST /finalize에 speaker_map:{}를 보내도 기존 job.speakers가 살아있어야
    한다. diar 라벨 공간이 있어 저장 자체는 200으로 성공하는 실사용 경로를 쓴다 —
    diar가 없으면 라벨 미해소로 422가 나 이 경로에 도달하지 못한다(항목 4에서 별도로
    다룬다)."""
    job_id = "finalize-empty-map-preserve"
    transcript = "[00:00] SPEAKER_00: 원본1\n[00:05] SPEAKER_01: 원본2"
    _create_done_meeting(
        job_id, transcript, speakers=dict(ORIGINAL),
        diarization={
            "SPEAKER_00": [{"start": 0.0, "end": 2.0}],
            "SPEAKER_01": [{"start": 2.0, "end": 4.0}],
        },
    )

    res = _finalize(client, job_id, transcript, {})
    assert res.status_code == 200, res.text

    job = client.get(f"/api/jobs/{job_id}").json()
    assert _get_speakers(job) == ORIGINAL, (
        f"빈 맵은 '갱신 안 함'이어야 한다 — 기존 이름이 영구 소실되면 안 된다. "
        f"실제: {_get_speakers(job)}"
    )


def test_finalize_with_empty_speaker_map_still_resolves_label_space_from_job_speakers(client):
    """[4] finalize에서 speaker_map이 비어 있으면 restore_segment_labels의 라벨
    공간도 job.speakers로 살아나야 한다. 지금은 space_map=speaker_map(빈 맵)을
    그대로 써서 diar 데이터가 없는 회의는 미해소 라벨로 422가 난다 — 본문이 이미
    유효한 라벨 그대로인데도 저장 자체가 거부된다."""
    job_id = "finalize-empty-map-space"
    transcript = "[00:00] SPEAKER_00: 원본1\n[00:05] SPEAKER_01: 원본2"
    _create_done_meeting(job_id, transcript, speakers=dict(ORIGINAL), diarization=None)

    res = _finalize(client, job_id, transcript, {})
    assert res.status_code == 200, (
        f"빈 맵이어도 job.speakers가 라벨 공간을 살려야 한다(본문은 이미 유효한 "
        f"라벨 그대로다). 실제: {res.status_code} {res.text}"
    )
    job = client.get(f"/api/jobs/{job_id}").json()
    assert _get_speakers(job) == ORIGINAL


def test_patch_transcript_with_empty_speaker_map_preserves_existing_names(client):
    """[2, 회귀 잠금] PATCH /transcript에 speaker_map:{}를 보내도 기존 이름이
    살아있어야 한다. B1 수정본(main.py)이 이미 `if body_map:` 게이트로 막아둔
    상태 — 이 테스트는 이미 초록불일 수 있다(방어가 유지되는지 잠근다)."""
    job_id = "patch-empty-map-preserve"
    transcript = "[00:00] SPEAKER_00: 원본1\n[00:05] SPEAKER_01: 원본2"
    _create_done_meeting(job_id, transcript, speakers=dict(ORIGINAL), diarization=None)

    res = client.patch(f"/api/jobs/{job_id}/transcript", json={
        "transcript": transcript,
        "speaker_map": {},
    })
    assert res.status_code == 200, res.text
    job = client.get(f"/api/jobs/{job_id}").json()
    assert _get_speakers(job) == ORIGINAL, (
        f"빈 맵은 '갱신 안 함'이어야 한다. 실제: {_get_speakers(job)}"
    )


def test_patch_transcript_without_speaker_map_key_matches_empty_map_behavior(client):
    """[3, 회귀 잠금] PATCH /transcript에 speaker_map 키 자체가 없는 경우도 빈 맵과
    **같은 쪽**(갱신 안 함)으로 가야 한다 — 키 부재와 빈 맵이 다른 결과를 내면 계약이
    일관되지 않다."""
    job_id = "patch-missing-map-key-preserve"
    transcript = "[00:00] SPEAKER_00: 원본1\n[00:05] SPEAKER_01: 원본2"
    _create_done_meeting(job_id, transcript, speakers=dict(ORIGINAL), diarization=None)

    res = client.patch(f"/api/jobs/{job_id}/transcript", json={"transcript": transcript})
    assert res.status_code == 200, res.text
    job = client.get(f"/api/jobs/{job_id}").json()
    assert _get_speakers(job) == ORIGINAL, (
        f"speaker_map 키 부재는 빈 맵과 같은 쪽(갱신 안 함)이어야 한다. "
        f"실제: {_get_speakers(job)}"
    )
