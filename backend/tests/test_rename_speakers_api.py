"""POST /api/jobs/{id}/rename-speakers — 신규 테스트 (PR B). 기존 백엔드 테스트 0건이었다.

main.py의 rename-speakers는 이제 speaker_map을 저장하는 동시에
render(get_segments(job_id), speaker_map)로 transcript를 재렌더한다 —
과거엔 speakers만 갱신하고 transcript를 전혀 안 건드려 구조적 desync가
보장됐었다(설계문서 부수 결함 1, `SpeakerMapper.tsx:50`가 실제 호출).

빈 값 방어 2겹 (director 확정):
    1) 쓰기: speaker_map 저장 시 값 strip 후 빈 값은 매핑에서 제외 (신규 데이터 차단)
    2) 렌더: render()에서 display가 빈/공백뿐이면 라벨 유지 (레거시 행 방어,
       transcript.py의 display = (speaker_map.get(label) or "").strip() or label)

병합 규칙 (director 확정 — **뒤집힌 이력 있음**): body의 speaker_map은 **완전 치환이
아니라 merge-safe**다. 기존 speakers를 베이스로 body에 있는 키만 덮어쓰고, body에
없는 라벨의 기존 이름은 보존된다(apply_match와 동일한 규칙). QA가 처음엔 "완전 치환"으로
가정했으나, 코드리뷰에서 이 가정이 뒤집혔다 — 신규 3파일이 전부 전체 키를 보내는
케이스만 테스트해 부분 map을 보내면 언급 안 된 라벨의 이름이 transcript에서
사라지는 회귀(PR B가 재렌더를 붙이며 메타데이터 손실을 본문 데이터 손실로 승격시킨
것)를 놓쳤었다. `TestPartialMapMergeSafe`가 이 회귀의 가드다.
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


def _assert_rerender_matches(job_id: str, job: dict):
    """왕복+치환 짝 단언의 '왕복' 축 (apply_match 테스트와 동일한 헬퍼).
    저장된 transcript가 render(segments, speaker_map)의 결과와 바이트 동일한지 확인한다."""
    from app.transcript import get_segments, render

    segments = get_segments(job_id)
    # PR C 계약: 저장된 transcript 컬럼은 **라벨 공간 렌더**와 바이트 동일해야 한다
    # (이름은 speakers가 나른다). 표시 문자열 검증은 _display_transcript가 맡는다.
    assert render(segments, {}) == job["transcript"]
    assert render(segments, _get_speakers(job)) == _display_transcript(job)


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
    assert "박부장:" in _display_transcript(job), f"실제: {_display_transcript(job)}"
    assert "김팀장" not in _display_transcript(job)
    _assert_rerender_matches("rename-1", job)


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
    # PR C 계약: 저장된 transcript 컬럼은 **라벨 공간 렌더**와 바이트 동일해야 한다
    # (이름은 speakers가 나른다). 표시 문자열 검증은 _display_transcript가 맡는다.
    assert render(segments, {}) == job["transcript"]
    assert render(segments, _get_speakers(job)) == _display_transcript(job)


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
    assert "SPEAKER_01:" in _display_transcript(job), f"실제: {_display_transcript(job)}"
    assert "반갑습니다" in _display_transcript(job)  # 본문 자체는 그대로

    # 쓰기 방어: DB speakers에 빈 값이 저장되지 않는다
    speakers = _get_speakers(job)
    assert speakers.get("SPEAKER_01") != "", f"실제: {speakers}"
    _assert_rerender_matches("rename-3", job)


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
    assert "SPEAKER_01:" in _display_transcript(job), f"실제: {_display_transcript(job)}"
    speakers = _get_speakers(job)
    assert (speakers.get("SPEAKER_01") or "").strip() == "", f"실제: {speakers}"
    # 저장이 되더라도(구현에 따라 완전 제외될 수도 있음) transcript에 공백 이름이
    # 노출되면 안 된다는 것이 핵심 — 위 transcript 단언이 이미 이를 보장한다.
    _assert_rerender_matches("rename-4", job)


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
    assert "김철수:" in _display_transcript(job), f"실제: {_display_transcript(job)}"
    assert " 김철수 :" not in _display_transcript(job)
    speakers = _get_speakers(job)
    assert speakers.get("SPEAKER_00") == "김철수", f"실제: {speakers}"
    _assert_rerender_matches("rename-5", job)


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
    assert "SPEAKER_00:" in _display_transcript(job)
    assert "SPEAKER_01:" in _display_transcript(job)
    _assert_rerender_matches("rename-6", job)


# ===========================================================================
# 코드리뷰 발견 — 부분 map은 merge-safe여야 한다 (신규 3파일에 0건이었던 공백)
#   기존: {"SPEAKER_00":"김팀장","SPEAKER_01":"이대리"} 저장 → {"SPEAKER_00":"박부장"}만
#   전송하면 SPEAKER_01의 "이대리"가 재렌더된 transcript에서 사라졌다 — 재렌더가
#   붙으며 메타데이터 손실이 사용자가 읽는 본문의 데이터 손실로 승격된 회귀.
# ===========================================================================

class TestPartialMapMergeSafe:
    def test_missing_label_keeps_existing_name_in_transcript_and_speakers(self, client):
        """부분 map을 보내도 언급되지 않은 라벨의 기존 이름은 transcript와 speakers
        양쪽에서 보존된다(merge-safe) — apply_match와 동일한 병합 규칙."""
        _create_done_meeting(
            "rename-partial-1",
            "[00:00] SPEAKER_00: 안녕\n[00:05] SPEAKER_01: 반갑습니다",
            speakers={"SPEAKER_00": "김팀장", "SPEAKER_01": "이대리"},
        )
        res = client.post("/api/jobs/rename-partial-1/rename-speakers", json={
            "speaker_map": {"SPEAKER_00": "박부장"},  # SPEAKER_01 누락
        })
        assert res.status_code == 200

        job = client.get("/api/jobs/rename-partial-1").json()
        assert "박부장:" in _display_transcript(job)
        assert "이대리:" in _display_transcript(job), (
            f"부분 map에서 언급 안 된 라벨의 기존 이름이 transcript에서 사라지면 안 됨. "
            f"실제: {_display_transcript(job)}"
        )
        assert "SPEAKER_01:" not in _display_transcript(job)

        speakers = _get_speakers(job)
        assert speakers.get("SPEAKER_00") == "박부장", f"실제: {speakers}"
        assert speakers.get("SPEAKER_01") == "이대리", (
            f"부분 map에서 언급 안 된 라벨의 speaker_map 값이 보존돼야 함. 실제: {speakers}"
        )
        _assert_rerender_matches("rename-partial-1", job)

    def test_two_separate_partial_calls_accumulate_without_losing_names(self, client):
        """부분 map을 두 번 나눠 보내도(SPEAKER_00 먼저, SPEAKER_01 나중) 두 이름
        모두 최종적으로 보존된다 — merge-safe가 매 호출마다 성립해야 한다."""
        _create_done_meeting(
            "rename-partial-2",
            "[00:00] SPEAKER_00: 안녕\n[00:05] SPEAKER_01: 반갑습니다\n[00:10] SPEAKER_02: 마지막",
            speakers={
                "SPEAKER_00": "김팀장",
                "SPEAKER_01": "이대리",
                "SPEAKER_02": "최부장",
            },
        )
        client.post("/api/jobs/rename-partial-2/rename-speakers", json={
            "speaker_map": {"SPEAKER_00": "박부장"},
        })
        res = client.post("/api/jobs/rename-partial-2/rename-speakers", json={
            "speaker_map": {"SPEAKER_01": "정과장"},
        })
        assert res.status_code == 200

        job = client.get("/api/jobs/rename-partial-2").json()
        transcript = _display_transcript(job)
        assert "박부장:" in transcript
        assert "정과장:" in transcript
        assert "최부장:" in transcript, (
            f"두 차례 부분 map 호출 이후에도 한 번도 언급 안 된 라벨의 이름이 "
            f"보존돼야 함. 실제: {transcript}"
        )
        speakers = _get_speakers(job)
        assert speakers.get("SPEAKER_00") == "박부장"
        assert speakers.get("SPEAKER_01") == "정과장"
        assert speakers.get("SPEAKER_02") == "최부장", f"실제: {speakers}"
        _assert_rerender_matches("rename-partial-2", job)


def _display_transcript(job: dict) -> str:
    """소비 시점 렌더로 **표시 문자열**을 만든다.

    PR C 확정 계약: 저장되는 `job.transcript` 컬럼은 **항상 라벨**(`SPEAKER_XX`)이고
    이름은 `job.speakers`가 나른다. 표시(화면·다운로드·복사·공유)는 소비 시점에
    `render(segments, speakers)`로 만든다. 따라서 "이름이 보이는가"를 검증하는 단언은
    저장 문자열이 아니라 **이 함수의 결과**를 봐야 한다. 단언의 판별력은 그대로다 —
    이름이 잘못 매핑되면 여기서 똑같이 실패한다.
    """
    from app.transcript import parse as _parse, render as _render
    speakers = job.get("speakers") or {}
    if isinstance(speakers, str):
        import json as _json
        speakers = _json.loads(speakers)
    segments = job.get("transcript_segments") or _parse(job.get("transcript") or "")
    if isinstance(segments, str):
        import json as _json
        segments = _json.loads(segments)
    return _render(segments, speakers)
