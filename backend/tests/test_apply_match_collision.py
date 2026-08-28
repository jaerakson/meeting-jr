"""apply-match 키 충돌·해석 실패·공백 불일치 재현 테스트.

PR #78 코드리뷰에서 발견된 버그 1, 3, 4를 TDD로 재현한다.

Bug 1: replace_map 키 충돌 — 서로 다른 diar 라벨이 같은 이름으로 해석되면
        뒤엣것이 앞엣것을 덮어써 transcript↔speakers 정합성이 깨진다.
Bug 3: 해석 실패를 삼키고 성공 반환 — identity label 해석 실패 시
        전체 실패 → 422, 부분 실패 → 200 + skipped.
Bug 4: 공백 때문에 불일치 재발 — speakers 값에 앞뒤 공백이 있으면
        apply-match의 정규식 매칭이 실패한다.
"""

import json
import re
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


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------

def _create_done_meeting(
    job_id: str,
    transcript: str,
    speakers: dict,
    diarization: dict | None = None,
):
    """done 상태 회의를 DB에 직접 생성."""
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


def _extract_transcript_speakers(transcript: str) -> set[str]:
    """transcript에서 화자 토큰 집합을 추출한다."""
    return set(re.findall(r"\[\d+:\d{2}\]\s*(.+?):", transcript))


# ===========================================================================
# Bug 1: replace_map 키 충돌로 rename이 조용히 덮어써짐
# ===========================================================================

class TestReplaceMapKeyCollision:
    """서로 다른 diar 라벨이 _resolve_speaker_display로 같은 이름으로
    해석될 때, replace_map[current_name] = new_name 에서 뒤엣것이
    앞엣것을 덮어쓰는 버그를 재현한다.

    시나리오:
    - speakers = {"SPEAKER_00": "김팀장"} (SPEAKER_00만 존재)
    - diarization: SPEAKER_00=0~30초, SPEAKER_01=30~60초
    - transcript: 김팀장이 두 라인 모두 발화
    - matches = {"SPEAKER_00": "박과장", "SPEAKER_01": "이대리"}

    _resolve_speaker_display가 SPEAKER_01(30~60초)을 transcript의
    "김팀장"(30초 발화)으로 해석 → 충돌:
    - replace_map["김팀장"] = "박과장" (SPEAKER_00)
    - replace_map["김팀장"] = "이대리" (SPEAKER_01, 덮어씀!)
    → transcript 전체가 "이대리:"가 되고 "박과장"은 사라짐
    """

    def test_collision_transcript_speakers_consistency(self, client):
        """apply-match 후 speakers의 모든 값이 transcript 화자 토큰과 정합해야 한다.
        "박과장"이 transcript에서 사라지면 안 된다."""
        diarization = {
            "SPEAKER_00": [{"start": 0, "end": 30, "speaker": "SPEAKER_00"}],
            "SPEAKER_01": [{"start": 30, "end": 60, "speaker": "SPEAKER_01"}],
        }

        _create_done_meeting(
            job_id="collision-1",
            transcript="[00:00] 김팀장: 첫번째 안건\n[00:30] 김팀장: 두번째 안건",
            speakers={"SPEAKER_00": "김팀장"},
            diarization=diarization,
        )

        res = client.post("/api/jobs/collision-1/apply-match", json={
            "matches": {"SPEAKER_00": "박과장", "SPEAKER_01": "이대리"},
        })
        assert res.status_code == 200

        job = client.get("/api/jobs/collision-1").json()
        speakers = job.get("speakers", {})
        if isinstance(speakers, str):
            speakers = json.loads(speakers)
        transcript = job["transcript"]

        transcript_names = _extract_transcript_speakers(transcript)

        # 핵심 검증: speakers의 모든 값이 transcript에 존재해야 한다
        for label, name in speakers.items():
            assert name in transcript_names, (
                f"speakers['{label}'] = '{name}'인데 transcript에 없음. "
                f"transcript 화자: {transcript_names}, 전문: {transcript}"
            )

    def test_collision_both_names_in_transcript(self, client):
        """충돌 시에도 "박과장:"과 "이대리:" 모두 transcript에 존재해야 한다."""
        diarization = {
            "SPEAKER_00": [{"start": 0, "end": 30, "speaker": "SPEAKER_00"}],
            "SPEAKER_01": [{"start": 30, "end": 60, "speaker": "SPEAKER_01"}],
        }

        _create_done_meeting(
            job_id="collision-2",
            transcript="[00:00] 김팀장: 첫번째 안건\n[00:30] 김팀장: 두번째 안건",
            speakers={"SPEAKER_00": "김팀장"},
            diarization=diarization,
        )

        res = client.post("/api/jobs/collision-2/apply-match", json={
            "matches": {"SPEAKER_00": "박과장", "SPEAKER_01": "이대리"},
        })
        assert res.status_code == 200

        job = client.get("/api/jobs/collision-2").json()
        transcript = job["transcript"]

        # 두 이름 모두 transcript에 있어야 함
        assert "박과장:" in transcript, (
            f"'박과장:'이 transcript에 없음. 실제: {transcript}"
        )
        assert "이대리:" in transcript, (
            f"'이대리:'가 transcript에 없음. 실제: {transcript}"
        )

    def test_collision_speakers_map_correct(self, client):
        """충돌과 무관하게 speakers map은 올바르게 업데이트되어야 한다."""
        diarization = {
            "SPEAKER_00": [{"start": 0, "end": 30, "speaker": "SPEAKER_00"}],
            "SPEAKER_01": [{"start": 30, "end": 60, "speaker": "SPEAKER_01"}],
        }

        _create_done_meeting(
            job_id="collision-3",
            transcript="[00:00] 김팀장: 첫번째 안건\n[00:30] 김팀장: 두번째 안건",
            speakers={"SPEAKER_00": "김팀장"},
            diarization=diarization,
        )

        res = client.post("/api/jobs/collision-3/apply-match", json={
            "matches": {"SPEAKER_00": "박과장", "SPEAKER_01": "이대리"},
        })
        assert res.status_code == 200

        job = client.get("/api/jobs/collision-3").json()
        speakers = job.get("speakers", {})
        if isinstance(speakers, str):
            speakers = json.loads(speakers)

        assert speakers.get("SPEAKER_00") == "박과장"
        assert speakers.get("SPEAKER_01") == "이대리"


# ===========================================================================
# Bug 3: 해석 실패를 삼키고 성공 반환
# ===========================================================================

class TestSilentSkipOnResolveFail:
    """identity label 해석 실패 시 응답 스펙:
    - 전체 실패 → 422 {"detail": ..., "skipped": [...]}
    - 부분 실패 → 200 {"ok": true, "skipped": [...], "warning": ...}
    """

    def test_all_labels_skipped_returns_422(self, client):
        """3-A: 전체 실패 → 422 반환.

        ClovaNote/txt 업로드 회의 (identity-mapped, diarization 없음).
        모든 identity 라벨이 해석 실패 → 422.
        transcript와 speakers는 변경되지 않아야 한다.
        """
        _create_done_meeting(
            job_id="skip-all-1",
            transcript="[00:00] 아빠: 안녕하세요\n[00:30] 엄마: 반갑습니다",
            speakers={"아빠": "아빠", "엄마": "엄마"},
            diarization=None,
        )

        res = client.post("/api/jobs/skip-all-1/apply-match", json={
            "matches": {"SPEAKER_00": "김과장"},
        })

        # 전체 실패 → 422
        assert res.status_code == 422, (
            f"모든 라벨 해석 실패 시 422여야 함. 실제: {res.status_code}, body: {res.json()}"
        )

        response_data = res.json()
        assert "skipped" in response_data, (
            f"422 응답에 skipped 필드가 있어야 함: {response_data}"
        )
        assert "SPEAKER_00" in response_data["skipped"], (
            f"skipped에 SPEAKER_00이 있어야 함: {response_data['skipped']}"
        )

        # transcript·speakers 변경 없음 확인
        job = client.get("/api/jobs/skip-all-1").json()
        assert "김과장" not in job["transcript"], (
            "해석 실패한 라벨은 transcript에 반영되면 안 됨"
        )
        speakers = job.get("speakers", {})
        if isinstance(speakers, str):
            speakers = json.loads(speakers)
        assert speakers == {"아빠": "아빠", "엄마": "엄마"}, (
            f"speakers가 변경되면 안 됨. 실제: {speakers}"
        )

    def test_partial_skip_returns_200_with_skipped(self, client):
        """3-B: 부분 실패 → 200 + skipped + warning.

        SPEAKER_00은 speakers에 있으므로 성공, SPEAKER_99는 어디에도 없어 실패.
        """
        _create_done_meeting(
            job_id="skip-partial-1",
            transcript="[00:00] 아빠: 안녕하세요\n[00:30] 엄마: 반갑습니다",
            speakers={"SPEAKER_00": "아빠", "SPEAKER_01": "엄마"},
            diarization=None,
        )

        res = client.post("/api/jobs/skip-partial-1/apply-match", json={
            "matches": {"SPEAKER_00": "김과장", "SPEAKER_99": "박부장"},
        })

        # 부분 적용 → 200
        assert res.status_code == 200, (
            f"부분 적용 시 200이어야 함. 실제: {res.status_code}"
        )

        response_data = res.json()
        assert response_data.get("ok") is True
        assert "skipped" in response_data, (
            f"부분 실패 시 skipped 필드 필수: {response_data}"
        )
        assert response_data["skipped"] == ["SPEAKER_99"], (
            f"skipped에 SPEAKER_99만 있어야 함: {response_data['skipped']}"
        )
        assert "warning" in response_data, (
            f"부분 실패 시 warning 문자열 필수: {response_data}"
        )

        # 성공한 부분은 적용됨
        job = client.get("/api/jobs/skip-partial-1").json()
        assert "김과장:" in job["transcript"], (
            "speakers에 있는 SPEAKER_00은 정상 적용되어야 함"
        )

    def test_all_labels_skipped_multi(self, client):
        """전체 실패 — 여러 라벨이 모두 해석 실패."""
        _create_done_meeting(
            job_id="skip-all-2",
            transcript="[00:00] 아빠: 안녕하세요\n[00:30] 엄마: 반갑습니다",
            speakers={"아빠": "아빠", "엄마": "엄마"},
            diarization=None,
        )

        res = client.post("/api/jobs/skip-all-2/apply-match", json={
            "matches": {"SPEAKER_00": "김과장", "SPEAKER_01": "박부장"},
        })

        assert res.status_code == 422
        response_data = res.json()
        assert set(response_data["skipped"]) == {"SPEAKER_00", "SPEAKER_01"}, (
            f"모든 건너뛴 라벨이 skipped에 있어야 함: {response_data}"
        )


# ===========================================================================
# Bug 4: 공백 때문에 불일치 재발 (백엔드 방어)
# ===========================================================================

class TestWhitespaceDefense:
    """speakers 값에 앞뒤 공백이 있어도 apply-match가 정상 동작해야 한다.

    프론트 TranscriptEditor.serialize()는 .trim()하지만
    handleSubmit()은 speaker_map에 trim 없이 저장한다.
    speakers["SPEAKER_00"] = "김팀장 "인데 transcript는 "김팀장"이면
    앵커 정규식이 매칭되지 않는다.
    """

    def test_trailing_space_in_speakers_still_matches(self, client):
        """speakers 값에 trailing 공백이 있어도 apply-match가 작동해야 한다."""
        _create_done_meeting(
            job_id="ws-1",
            transcript="[00:00] 김팀장: 안녕하세요\n[00:30] 이대리: 반갑습니다",
            speakers={"SPEAKER_00": "김팀장 ", "SPEAKER_01": "이대리"},
        )

        res = client.post("/api/jobs/ws-1/apply-match", json={
            "matches": {"SPEAKER_00": "박과장"},
        })
        assert res.status_code == 200

        job = client.get("/api/jobs/ws-1").json()
        assert "박과장:" in job["transcript"], (
            f"trailing space가 있어도 transcript에서 교체가 되어야 함. "
            f"실제: {job['transcript']}"
        )
        assert "김팀장" not in job["transcript"], (
            f"원래 이름이 transcript에 남아있으면 안 됨. 실제: {job['transcript']}"
        )

    def test_leading_space_in_speakers_still_matches(self, client):
        """speakers 값에 leading 공백이 있어도 apply-match가 작동해야 한다."""
        _create_done_meeting(
            job_id="ws-2",
            transcript="[00:00] 김팀장: 안녕하세요\n[00:30] 이대리: 반갑습니다",
            speakers={"SPEAKER_00": " 김팀장", "SPEAKER_01": "이대리"},
        )

        res = client.post("/api/jobs/ws-2/apply-match", json={
            "matches": {"SPEAKER_00": "박과장"},
        })
        assert res.status_code == 200

        job = client.get("/api/jobs/ws-2").json()
        assert "박과장:" in job["transcript"], (
            f"leading space가 있어도 transcript에서 교체가 되어야 함. "
            f"실제: {job['transcript']}"
        )

    def test_spaces_both_sides_in_speakers(self, client):
        """speakers 값에 양쪽 공백이 있어도 apply-match가 작동해야 한다."""
        _create_done_meeting(
            job_id="ws-3",
            transcript="[00:00] 김팀장: 안녕하세요\n[00:30] 이대리: 반갑습니다",
            speakers={"SPEAKER_00": " 김팀장 ", "SPEAKER_01": " 이대리 "},
        )

        res = client.post("/api/jobs/ws-3/apply-match", json={
            "matches": {"SPEAKER_00": "박과장", "SPEAKER_01": "정부장"},
        })
        assert res.status_code == 200

        job = client.get("/api/jobs/ws-3").json()
        transcript = job["transcript"]
        assert "박과장:" in transcript, f"실제: {transcript}"
        assert "정부장:" in transcript, f"실제: {transcript}"
        assert "김팀장" not in transcript, f"원래 이름 잔존: {transcript}"
        assert "이대리" not in transcript, f"원래 이름 잔존: {transcript}"
