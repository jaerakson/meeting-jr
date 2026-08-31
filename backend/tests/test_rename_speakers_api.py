"""POST /api/jobs/{id}/rename-speakers — 신규 테스트 (PR B). 기존 백엔드 테스트 0건.

main.py:2085는 현재 speakers만 저장하고 transcript를 전혀 건드리지 않아
구조적 desync가 보장된다(설계문서 부수 결함 1, `SpeakerMapper.tsx:50`가 실제 호출).
PR B가 재렌더를 붙여 이 desync를 해소한다.

빈 값 방어 2겹 (director 확정):
    1) 쓰기: speaker_map 저장 시 값 strip 후 빈 값은 매핑에서 제외 (신규 데이터 차단)
    2) 렌더: render()에서 display가 빈/공백뿐이면 라벨 유지 (레거시 행 방어,
       transcript.py의 display = (speaker_map.get(label) or "").strip() or label)

RED가 정상이다 — rename-speakers는 아직 재렌더를 붙이지 않은 옛 구현이다.

가정(director로부터 명시 확답을 받지 못해 QA가 결정 — 합격 기준 4가지를 흔들지 않는
범위): body의 speaker_map은 기존 값과 **병합이 아니라 완전 치환**이다. 현재 구현
`update_job_result(job_id, speakers=speaker_map)`이 이미 그렇게 동작하고, 프론트
SpeakerMapper.tsx가 완전한 현재 상태를 매번 보낸다고 가정하는 편이 더 단순하다
(카르파시 원칙 ②). 다르면 이 파일의 병합 관련 단언만 director 지시로 교체하면 된다.
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def tmp_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    import app.database as db_module
    monkeypatch.setattr(db_module, "DB_PATH", db_path)
    db_module.init_db()

    # rename-speakers는 _save_speakers()를 통해 SPEAKERS_FILE에도 쓴다 — 실제
    # backend/speakers.json을 건드리지 않도록 임시 경로로 격리한다.
    import app.main as main_module
    monkeypatch.setattr(main_module, "SPEAKERS_FILE", tmp_path / "speakers.json")
    yield db_path


@pytest.fixture()
def client(tmp_db):
    from app.main import app
    with TestClient(app) as c:
        yield c


def _create_done_meeting(job_id, transcript, speakers, diarization=None):
    import app.database as db
    db.create_job(job_id, f"{job_id}.webm", title="테스트 회의")
    db.update_job_result(
        job_id,
        summary="## 요약\n테스트",
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


# ===========================================================================
# 기본: transcript가 재렌더된다 (desync 해소 — 부수 결함 1)
# ===========================================================================

def test_rename_speakers_updates_transcript(client):
    """현재는 transcript가 그대로라 desync가 보장된다 — 재렌더로 고쳐지는지 확인한다."""
    _create_done_meeting(
        "rename-1",
        "[00:00] SPEAKER_00: 안녕\n[00:05] SPEAKER_01: 반갑습니다",
        speakers={"SPEAKER_00": "김팀장", "SPEAKER_01": "이대리"},
    )
    res = client.post("/api/jobs/rename-1/rename-speakers", json={
        "speaker_map": {"SPEAKER_00": "박부장", "SPEAKER_01": "이대리"},
    })
    assert res.status_code == 200
    job = client.get("/api/jobs/rename-1").json()
    assert "박부장:" in job["transcript"], f"실제: {job['transcript']}"
    assert "김팀장" not in job["transcript"]


def test_rename_speakers_rerender_matches_stored_transcript(client):
    """사후 정합성: render(get_segments(job_id), speakers) == job['transcript']."""
    from app.transcript import get_segments, render
    _create_done_meeting(
        "rename-2",
        "[00:00] SPEAKER_00: 안녕\n[00:05] SPEAKER_01: 반갑습니다",
        speakers={"SPEAKER_00": "김팀장", "SPEAKER_01": "이대리"},
    )
    client.post("/api/jobs/rename-2/rename-speakers", json={
        "speaker_map": {"SPEAKER_00": "박부장", "SPEAKER_01": "이대리"},
    })
    job = client.get("/api/jobs/rename-2").json()
    segments = get_segments("rename-2")
    assert render(segments, _get_speakers(job)) == job["transcript"]


# ===========================================================================
# 빈 값 방어 (director 확정 사양)
# ===========================================================================

def test_empty_value_keeps_label_not_erased(client):
    """프론트가 실제로 보내는 payload 그대로 — SPEAKER_01을 빈 값으로 보내도
    라벨이 유지되고 이름이 지워지지 않는다(SpeakerMapper.tsx:42 초기값이 ''이다)."""
    _create_done_meeting(
        "rename-3",
        "[00:00] SPEAKER_00: 안녕\n[00:05] SPEAKER_01: 반갑습니다",
        speakers={"SPEAKER_00": "김팀장", "SPEAKER_01": "이대리"},
    )
    res = client.post("/api/jobs/rename-3/rename-speakers", json={
        "speaker_map": {"SPEAKER_00": "김팀장", "SPEAKER_01": ""},
    })
    assert res.status_code == 200

    job = client.get("/api/jobs/rename-3").json()
    # 렌더 방어: 라벨(SPEAKER_01)이 이름을 잃지 않고 transcript에 유지된다
    assert "SPEAKER_01:" in job["transcript"], f"실제: {job['transcript']}"
    assert "반갑습니다" in job["transcript"]  # 본문 자체는 그대로

    # 쓰기 방어: DB speakers에 빈 값이 저장되지 않는다
    speakers = _get_speakers(job)
    assert speakers.get("SPEAKER_01") != "", f"실제: {speakers}"


def test_whitespace_only_value_keeps_label_not_erased(client):
    """공백만 있는 값도 빈 값과 동일하게 취급되어 라벨이 유지된다."""
    _create_done_meeting(
        "rename-4",
        "[00:00] SPEAKER_00: 안녕\n[00:05] SPEAKER_01: 반갑습니다",
        speakers={"SPEAKER_00": "김팀장", "SPEAKER_01": "이대리"},
    )
    res = client.post("/api/jobs/rename-4/rename-speakers", json={
        "speaker_map": {"SPEAKER_00": "김팀장", "SPEAKER_01": "   "},
    })
    assert res.status_code == 200
    job = client.get("/api/jobs/rename-4").json()
    assert "SPEAKER_01:" in job["transcript"], f"실제: {job['transcript']}"
    speakers = _get_speakers(job)
    assert (speakers.get("SPEAKER_01") or "").strip() == "", f"실제: {speakers}"
    # 저장이 되더라도(구현에 따라 완전 제외될 수도 있음) transcript에 공백 이름이
    # 노출되면 안 된다는 것이 핵심 — 위 transcript 단언이 이미 이를 보장한다.


def test_value_with_surrounding_whitespace_is_stripped(client):
    """`" 김철수 "` 처럼 앞뒤 공백이 있는 정상 값은 strip되어 저장·렌더된다."""
    _create_done_meeting(
        "rename-5",
        "[00:00] SPEAKER_00: 안녕",
        speakers={"SPEAKER_00": "김팀장"},
    )
    res = client.post("/api/jobs/rename-5/rename-speakers", json={
        "speaker_map": {"SPEAKER_00": " 김철수 "},
    })
    assert res.status_code == 200
    job = client.get("/api/jobs/rename-5").json()
    assert "김철수:" in job["transcript"], f"실제: {job['transcript']}"
    assert " 김철수 :" not in job["transcript"]
    speakers = _get_speakers(job)
    assert speakers.get("SPEAKER_00") == "김철수", f"실제: {speakers}"


def test_empty_value_does_not_crash_when_all_values_empty(client):
    """모든 값이 빈 문자열이어도(사용자가 전부 지우고 제출) 에러 없이 처리되고,
    모든 라벨이 원래 이름 그대로 유지된다."""
    _create_done_meeting(
        "rename-6",
        "[00:00] SPEAKER_00: 안녕\n[00:05] SPEAKER_01: 반갑습니다",
        speakers={"SPEAKER_00": "김팀장", "SPEAKER_01": "이대리"},
    )
    res = client.post("/api/jobs/rename-6/rename-speakers", json={
        "speaker_map": {"SPEAKER_00": "", "SPEAKER_01": ""},
    })
    assert res.status_code == 200
    job = client.get("/api/jobs/rename-6").json()
    assert "SPEAKER_00:" in job["transcript"]
    assert "SPEAKER_01:" in job["transcript"]
