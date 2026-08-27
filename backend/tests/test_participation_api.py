"""발언 참여도 분석 API 테스트 (TDD).

GET /api/jobs/{job_id}/participation — 화자별 발언 시간/비율/턴수 분석

데이터 소스 우선순위:
  1. meetings.diarization (JSON, PyAnnote 세그먼트)
  2. transcript의 [MM:SS] SPEAKER_XX: 타임스탬프 폴백
응답: { speakers: [{ label, display_name, total_seconds, percentage, turn_count, avg_turn_seconds }], total_duration }
"""

import sys
import os
import json
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

def _create_meeting_with_diarization(
    job_id: str,
    diarization: dict,
    speakers: dict | None = None,
    transcript: str = "[00:00] SPEAKER_00: 테스트",
    title: str = "테스트 회의",
):
    """diarization 데이터가 있는 done 상태 회의 생성."""
    import app.database as db
    db.create_job(job_id, f"{job_id}.webm", title=title)
    db.update_job_result(
        job_id,
        summary="## 요약\n내용",
        transcript=transcript,
        speakers=speakers or {},
        diarization=diarization,
        duration_sec=60,
        status="done",
    )


def _create_meeting_transcript_only(
    job_id: str,
    transcript: str,
    speakers: dict | None = None,
    title: str = "테스트 회의",
):
    """diarization 없이 transcript만 있는 done 상태 회의 생성."""
    import app.database as db
    db.create_job(job_id, f"{job_id}.webm", title=title)
    db.update_job_result(
        job_id,
        summary="## 요약\n내용",
        transcript=transcript,
        speakers=speakers or {},
        duration_sec=60,
        status="done",
    )


def _create_empty_meeting(job_id: str, title: str = "빈 회의"):
    """diarization, transcript 둘 다 없는 done 상태 회의."""
    import app.database as db
    db.create_job(job_id, f"{job_id}.webm", title=title)
    db.update_job_result(
        job_id,
        summary="## 요약\n내용",
        transcript="",
        speakers={},
        duration_sec=60,
        status="done",
    )


# ===========================================================================
# 1. Diarization 기반 정상 집계
# ===========================================================================

class TestParticipationDiarization:
    """diarization 세그먼트가 있을 때 정확한 참여도 통계를 반환한다."""

    def test_basic_diarization_stats(self, client):
        """두 화자의 diarization → 시간 합계, percentage 합 ≈ 100, turn_count, avg."""
        diarization = {
            "SPEAKER_00": [
                {"start": 0.0, "end": 5.0, "speaker": "SPEAKER_00"},
                {"start": 10.0, "end": 15.0, "speaker": "SPEAKER_00"},
            ],
            "SPEAKER_01": [
                {"start": 5.0, "end": 10.0, "speaker": "SPEAKER_01"},
            ],
        }
        _create_meeting_with_diarization("p1", diarization)

        res = client.get("/api/jobs/p1/participation")
        assert res.status_code == 200
        data = res.json()

        assert "speakers" in data
        assert "total_duration" in data
        assert len(data["speakers"]) == 2

        # total_duration은 전체 발언 시간 합산 (또는 회의 전체 길이)
        assert data["total_duration"] > 0

        # 각 speaker 필드 존재 확인
        for sp in data["speakers"]:
            assert "label" in sp
            assert "display_name" in sp
            assert "total_seconds" in sp
            assert "percentage" in sp
            assert "turn_count" in sp
            assert "avg_turn_seconds" in sp

        # SPEAKER_00: 5+5=10초, 2턴
        sp00 = next(s for s in data["speakers"] if s["label"] == "SPEAKER_00")
        assert sp00["total_seconds"] == pytest.approx(10.0, abs=0.1)
        assert sp00["turn_count"] == 2
        assert sp00["avg_turn_seconds"] == pytest.approx(5.0, abs=0.1)

        # SPEAKER_01: 5초, 1턴
        sp01 = next(s for s in data["speakers"] if s["label"] == "SPEAKER_01")
        assert sp01["total_seconds"] == pytest.approx(5.0, abs=0.1)
        assert sp01["turn_count"] == 1
        assert sp01["avg_turn_seconds"] == pytest.approx(5.0, abs=0.1)

        # percentage 합 ≈ 100
        pct_sum = sum(s["percentage"] for s in data["speakers"])
        assert pct_sum == pytest.approx(100.0, abs=1.0)

    def test_single_speaker_100_percent(self, client):
        """단일 화자 → percentage 100%."""
        diarization = {
            "SPEAKER_00": [
                {"start": 0.0, "end": 30.0, "speaker": "SPEAKER_00"},
            ],
        }
        _create_meeting_with_diarization("p2", diarization)

        res = client.get("/api/jobs/p2/participation")
        assert res.status_code == 200
        data = res.json()

        assert len(data["speakers"]) == 1
        assert data["speakers"][0]["percentage"] == pytest.approx(100.0, abs=0.1)
        assert data["speakers"][0]["total_seconds"] == pytest.approx(30.0, abs=0.1)

    def test_three_speakers_uneven(self, client):
        """3명 화자, 불균등 분포 → 비율 정확도."""
        diarization = {
            "SPEAKER_00": [
                {"start": 0.0, "end": 10.0, "speaker": "SPEAKER_00"},
            ],
            "SPEAKER_01": [
                {"start": 10.0, "end": 30.0, "speaker": "SPEAKER_01"},
            ],
            "SPEAKER_02": [
                {"start": 30.0, "end": 60.0, "speaker": "SPEAKER_02"},
                {"start": 65.0, "end": 75.0, "speaker": "SPEAKER_02"},
            ],
        }
        _create_meeting_with_diarization("p3", diarization)

        res = client.get("/api/jobs/p3/participation")
        assert res.status_code == 200
        data = res.json()

        assert len(data["speakers"]) == 3

        sp00 = next(s for s in data["speakers"] if s["label"] == "SPEAKER_00")
        sp01 = next(s for s in data["speakers"] if s["label"] == "SPEAKER_01")
        sp02 = next(s for s in data["speakers"] if s["label"] == "SPEAKER_02")

        # SPEAKER_00: 10초, SPEAKER_01: 20초, SPEAKER_02: 30+10=40초 = 총 70초
        assert sp00["total_seconds"] == pytest.approx(10.0, abs=0.1)
        assert sp01["total_seconds"] == pytest.approx(20.0, abs=0.1)
        assert sp02["total_seconds"] == pytest.approx(40.0, abs=0.1)
        assert sp02["turn_count"] == 2

        pct_sum = sum(s["percentage"] for s in data["speakers"])
        assert pct_sum == pytest.approx(100.0, abs=1.0)


# ===========================================================================
# 2. Speakers 매핑 (display_name)
# ===========================================================================

class TestParticipationSpeakerMapping:
    """speakers 매핑이 있으면 display_name에 실명, 없으면 SPEAKER_XX 그대로."""

    def test_display_name_with_mapping(self, client):
        """speakers에 이름이 있으면 display_name이 실명으로 나온다."""
        diarization = {
            "SPEAKER_00": [
                {"start": 0.0, "end": 10.0, "speaker": "SPEAKER_00"},
            ],
            "SPEAKER_01": [
                {"start": 10.0, "end": 20.0, "speaker": "SPEAKER_01"},
            ],
        }
        speakers = {"SPEAKER_00": "홍길동", "SPEAKER_01": "김영희"}
        _create_meeting_with_diarization("m1", diarization, speakers=speakers)

        res = client.get("/api/jobs/m1/participation")
        assert res.status_code == 200
        data = res.json()

        sp00 = next(s for s in data["speakers"] if s["label"] == "SPEAKER_00")
        sp01 = next(s for s in data["speakers"] if s["label"] == "SPEAKER_01")

        assert sp00["display_name"] == "홍길동"
        assert sp01["display_name"] == "김영희"

    def test_display_name_without_mapping(self, client):
        """speakers 매핑이 없으면 label 그대로가 display_name."""
        diarization = {
            "SPEAKER_00": [
                {"start": 0.0, "end": 10.0, "speaker": "SPEAKER_00"},
            ],
        }
        _create_meeting_with_diarization("m2", diarization, speakers={})

        res = client.get("/api/jobs/m2/participation")
        assert res.status_code == 200
        data = res.json()

        sp = data["speakers"][0]
        assert sp["label"] == "SPEAKER_00"
        assert sp["display_name"] == "SPEAKER_00"

    def test_partial_mapping(self, client):
        """일부 화자만 매핑되어 있으면 매핑된 것만 실명, 나머지는 label."""
        diarization = {
            "SPEAKER_00": [
                {"start": 0.0, "end": 5.0, "speaker": "SPEAKER_00"},
            ],
            "SPEAKER_01": [
                {"start": 5.0, "end": 10.0, "speaker": "SPEAKER_01"},
            ],
        }
        speakers = {"SPEAKER_00": "홍길동"}  # SPEAKER_01 매핑 없음
        _create_meeting_with_diarization("m3", diarization, speakers=speakers)

        res = client.get("/api/jobs/m3/participation")
        assert res.status_code == 200
        data = res.json()

        sp00 = next(s for s in data["speakers"] if s["label"] == "SPEAKER_00")
        sp01 = next(s for s in data["speakers"] if s["label"] == "SPEAKER_01")

        assert sp00["display_name"] == "홍길동"
        assert sp01["display_name"] == "SPEAKER_01"


# ===========================================================================
# 3. Transcript 폴백 경로
# ===========================================================================

class TestParticipationTranscriptFallback:
    """diarization이 없을 때 transcript의 [MM:SS] 타임스탬프 기반 근사 폴백."""

    def test_transcript_fallback_basic(self, client):
        """diarization 없이 transcript만 있을 때 → 타임스탬프 기반 집계."""
        transcript = (
            "[00:00] SPEAKER_00: 안녕하세요, 시작하겠습니다.\n"
            "[00:10] SPEAKER_01: 네, 준비됐습니다.\n"
            "[00:20] SPEAKER_00: 첫 번째 안건입니다.\n"
            "[00:30] SPEAKER_01: 좋습니다."
        )
        _create_meeting_transcript_only("t1", transcript)

        res = client.get("/api/jobs/t1/participation")
        assert res.status_code == 200
        data = res.json()

        assert len(data["speakers"]) == 2
        assert data["total_duration"] > 0

        sp00 = next(s for s in data["speakers"] if s["label"] == "SPEAKER_00")
        sp01 = next(s for s in data["speakers"] if s["label"] == "SPEAKER_01")

        # 각 화자 2턴씩
        assert sp00["turn_count"] == 2
        assert sp01["turn_count"] == 2

        # total_seconds > 0
        assert sp00["total_seconds"] > 0
        assert sp01["total_seconds"] > 0

        # percentage 합 ≈ 100
        pct_sum = sum(s["percentage"] for s in data["speakers"])
        assert pct_sum == pytest.approx(100.0, abs=1.0)

    def test_transcript_fallback_with_speaker_names(self, client):
        """transcript 폴백 + speakers 매핑 → display_name 반영."""
        transcript = (
            "[00:00] SPEAKER_00: 안녕하세요\n"
            "[00:15] SPEAKER_01: 반갑습니다\n"
        )
        speakers = {"SPEAKER_00": "김철수", "SPEAKER_01": "박영희"}
        _create_meeting_transcript_only("t2", transcript, speakers=speakers)

        res = client.get("/api/jobs/t2/participation")
        assert res.status_code == 200
        data = res.json()

        sp00 = next(s for s in data["speakers"] if s["label"] == "SPEAKER_00")
        sp01 = next(s for s in data["speakers"] if s["label"] == "SPEAKER_01")

        assert sp00["display_name"] == "김철수"
        assert sp01["display_name"] == "박영희"

    def test_transcript_single_line(self, client):
        """transcript 1줄만 있는 경우에도 정상 반환."""
        transcript = "[00:00] SPEAKER_00: 혼자 말하기"
        _create_meeting_transcript_only("t3", transcript)

        res = client.get("/api/jobs/t3/participation")
        assert res.status_code == 200
        data = res.json()

        assert len(data["speakers"]) == 1
        assert data["speakers"][0]["turn_count"] == 1
        assert data["speakers"][0]["percentage"] == pytest.approx(100.0, abs=0.1)

    def test_transcript_fallback_with_real_names(self, client):
        """실제 이름 형태 화자 라벨의 transcript 폴백 동작 검증."""
        transcript = (
            "[00:00] 김철수: 안녕하세요 회의 시작하겠습니다\n"
            "[01:30] 박영희: 네 준비되었습니다\n"
            "[02:00] 김철수: 첫 번째 안건입니다\n"
            "[03:30] 이민준: 의견 있습니다\n"
        )
        _create_meeting_transcript_only("t4", transcript)

        res = client.get("/api/jobs/t4/participation")
        assert res.status_code == 200
        data = res.json()

        assert len(data["speakers"]) == 3

        sp_kim = next(s for s in data["speakers"] if s["label"] == "김철수")
        sp_park = next(s for s in data["speakers"] if s["label"] == "박영희")
        sp_lee = next(s for s in data["speakers"] if s["label"] == "이민준")

        # 김철수: 2턴, 00:00~01:30(90초) + 02:00~03:30(90초) = 180초
        assert sp_kim["turn_count"] == 2
        assert sp_kim["total_seconds"] == pytest.approx(180.0, abs=0.1)

        # 박영희: 1턴, 01:30~02:00(30초)
        assert sp_park["turn_count"] == 1
        assert sp_park["total_seconds"] == pytest.approx(30.0, abs=0.1)

        # 이민준: 1턴, 마지막 발언 기본 10초
        assert sp_lee["turn_count"] == 1
        assert sp_lee["total_seconds"] == pytest.approx(10.0, abs=0.1)

        # label과 display_name이 실제 이름 그대로
        assert sp_kim["display_name"] == "김철수"
        assert sp_park["display_name"] == "박영희"
        assert sp_lee["display_name"] == "이민준"

        # percentage 합 ≈ 100
        pct_sum = sum(s["percentage"] for s in data["speakers"])
        assert pct_sum == pytest.approx(100.0, abs=1.0)

    def test_transcript_fallback_mixed_format(self, client):
        """한글 이름과 영어 이름이 섞인 transcript 폴백."""
        transcript = (
            "[00:00] 김대리: 시작합니다\n"
            "[01:00] John: Let me explain\n"
            "[02:30] 김대리: 감사합니다\n"
        )
        _create_meeting_transcript_only("t5", transcript)

        res = client.get("/api/jobs/t5/participation")
        assert res.status_code == 200
        data = res.json()

        assert len(data["speakers"]) == 2

        sp_kim = next(s for s in data["speakers"] if s["label"] == "김대리")
        sp_john = next(s for s in data["speakers"] if s["label"] == "John")

        # 김대리: 2턴, 00:00~01:00(60초) + 02:30~끝(10초 기본) = 70초
        assert sp_kim["turn_count"] == 2
        assert sp_kim["total_seconds"] == pytest.approx(70.0, abs=0.1)

        # John: 1턴, 01:00~02:30(90초)
        assert sp_john["turn_count"] == 1
        assert sp_john["total_seconds"] == pytest.approx(90.0, abs=0.1)

        assert sp_kim["display_name"] == "김대리"
        assert sp_john["display_name"] == "John"

        pct_sum = sum(s["percentage"] for s in data["speakers"])
        assert pct_sum == pytest.approx(100.0, abs=1.0)


# ===========================================================================
# 4. 빈 케이스 (diarization/transcript 둘 다 없음)
# ===========================================================================

class TestParticipationEmpty:
    """diarization과 transcript 둘 다 없으면 에러가 아닌 빈 결과."""

    def test_empty_meeting_returns_empty_speakers(self, client):
        """diarization/transcript 없는 done 회의 → 빈 speakers 배열."""
        _create_empty_meeting("e1")

        res = client.get("/api/jobs/e1/participation")
        assert res.status_code == 200
        data = res.json()

        assert data["speakers"] == []
        assert data["total_duration"] == 0

    def test_no_parsable_transcript(self, client):
        """transcript가 있지만 [MM:SS] SPEAKER_XX 형식이 아닌 경우 → 빈 결과."""
        _create_meeting_transcript_only("e2", "형식 없는 일반 텍스트입니다.")

        res = client.get("/api/jobs/e2/participation")
        assert res.status_code == 200
        data = res.json()

        assert data["speakers"] == []
        assert data["total_duration"] == 0


# ===========================================================================
# 5. 존재하지 않는 job_id → 404
# ===========================================================================

class TestParticipationNotFound:
    def test_nonexistent_job(self, client):
        """존재하지 않는 job_id → 404."""
        res = client.get("/api/jobs/nonexistent-id/participation")
        assert res.status_code == 404


# ===========================================================================
# 6. 엣지 케이스
# ===========================================================================

class TestParticipationEdgeCases:
    """경계 조건 테스트."""

    def test_diarization_overlapping_segments(self, client):
        """겹치는 세그먼트가 있어도 집계는 세그먼트 길이 기반으로 동작."""
        diarization = {
            "SPEAKER_00": [
                {"start": 0.0, "end": 10.0, "speaker": "SPEAKER_00"},
                {"start": 8.0, "end": 15.0, "speaker": "SPEAKER_00"},  # 2초 겹침
            ],
        }
        _create_meeting_with_diarization("edge1", diarization)

        res = client.get("/api/jobs/edge1/participation")
        assert res.status_code == 200
        data = res.json()

        # 세그먼트 길이 합산: 10 + 7 = 17초 (겹침 무관, 세그먼트 자체 길이 합)
        sp = data["speakers"][0]
        assert sp["total_seconds"] > 0
        assert sp["turn_count"] == 2

    def test_diarization_empty_segments(self, client):
        """diarization 키는 있지만 세그먼트 리스트가 비어있는 경우."""
        diarization = {
            "SPEAKER_00": [],
        }
        _create_meeting_with_diarization("edge2", diarization)

        res = client.get("/api/jobs/edge2/participation")
        assert res.status_code == 200
        data = res.json()

        # 빈 세그먼트 → speakers 비어있거나 0초
        if data["speakers"]:
            assert data["speakers"][0]["total_seconds"] == 0

    def test_pending_job_still_works(self, client):
        """pending 상태 회의에서도 diarization이 있으면 조회 가능 (또는 빈 결과)."""
        import app.database as db
        db.create_job("edge3", "edge3.webm", title="진행중 회의")
        # pending 상태, diarization/transcript 없음

        res = client.get("/api/jobs/edge3/participation")
        # 404가 아닌 200 + 빈 결과, 또는 구현에 따라 다를 수 있음
        # 최소한 서버 크래시는 아님
        assert res.status_code in (200, 404)

    def test_transcript_no_speaker_with_time_in_text(self, client):
        """타임스탬프만 있고 화자 라벨 없는 transcript + 본문 내 시각 → 빈 결과."""
        import app.database as db
        db.create_job("edge4", "edge4.webm", title="시각 오탐 테스트")
        db.update_job_result("edge4", status="done", transcript=(
            "[00:12] 다음 회의는 15:00입니다\n"
            "[01:30] 오늘 목표는 3가지입니다\n"
        ))

        res = client.get("/api/jobs/edge4/participation")
        assert res.status_code == 200
        data = res.json()
        assert data["speakers"] == []
        assert data["total_duration"] == 0
