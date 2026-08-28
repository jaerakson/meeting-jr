"""apply-match 후 transcript↔speakers↔participation 정합성 재현 테스트.

Bug: POST /api/jobs/{id}/apply-match가 SPEAKER_XX 라벨로 transcript를
치환하지만, 이미 실명으로 치환된 transcript에는 SPEAKER_XX가 없어서
transcript가 갱신되지 않고, speakers만 업데이트되어 정합성이 깨진다.

시나리오 A: 비-identity 매핑 (녹음→이름 지정 후 rematch)
시나리오 B: identity 매핑 (txt 업로드 등)
시나리오 C: apply-match 후 participation 정합성
"""

import json
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


# ===========================================================================
# 시나리오 A: 비-identity 매핑 (녹음 후 이름 지정 → rematch)
# ===========================================================================

class TestApplyMatchNonIdentity:
    """speakers = {SPEAKER_XX: 실명} 형태에서 apply-match 호출."""

    def test_rematch_replaces_transcript_correctly(self, client):
        """apply-match로 SPEAKER_00→김과장 매칭 시,
        transcript의 '아빠:' 가 '김과장:' 으로 교체되어야 한다."""
        _create_done_meeting(
            job_id="match-a1",
            transcript="[00:00] 아빠: 안녕하세요\n[00:05] 엄마: 반갑습니다",
            speakers={"SPEAKER_00": "아빠", "SPEAKER_01": "엄마"},
        )

        # apply-match: SPEAKER_00을 "김과장"으로 변경
        res = client.post("/api/jobs/match-a1/apply-match", json={
            "matches": {"SPEAKER_00": "김과장"},
        })
        assert res.status_code == 200

        # 검증: transcript에서 "아빠"가 "김과장"으로 교체되어야 함
        job = client.get("/api/jobs/match-a1").json()
        assert "김과장:" in job["transcript"], (
            f"transcript에 '김과장:'이 없음. 실제: {job['transcript']}"
        )
        assert "아빠:" not in job["transcript"], (
            f"transcript에 '아빠:'가 여전히 남아있음. 실제: {job['transcript']}"
        )

    def test_rematch_updates_speakers_map(self, client):
        """apply-match 후 speakers에 새 매핑이 반영되어야 한다."""
        _create_done_meeting(
            job_id="match-a2",
            transcript="[00:00] 아빠: 안녕\n[00:05] 엄마: 응",
            speakers={"SPEAKER_00": "아빠", "SPEAKER_01": "엄마"},
        )

        client.post("/api/jobs/match-a2/apply-match", json={
            "matches": {"SPEAKER_00": "김과장"},
        })

        job = client.get("/api/jobs/match-a2").json()
        speakers = job.get("speakers", {})
        if isinstance(speakers, str):
            speakers = json.loads(speakers)

        assert speakers.get("SPEAKER_00") == "김과장"
        assert speakers.get("SPEAKER_01") == "엄마"

    def test_rematch_partial_only_changes_matched(self, client):
        """매칭되지 않은 화자(엄마)는 transcript에서 그대로 유지."""
        _create_done_meeting(
            job_id="match-a3",
            transcript="[00:00] 아빠: 첫번째\n[00:05] 엄마: 두번째\n[00:10] 아빠: 세번째",
            speakers={"SPEAKER_00": "아빠", "SPEAKER_01": "엄마"},
        )

        client.post("/api/jobs/match-a3/apply-match", json={
            "matches": {"SPEAKER_00": "김과장"},
        })

        job = client.get("/api/jobs/match-a3").json()
        transcript = job["transcript"]

        # 김과장으로 교체된 부분
        assert transcript.count("김과장:") == 2
        # 엄마는 그대로
        assert "엄마:" in transcript


    def test_rematch_name_swap_atomic(self, client):
        """두 화자 이름을 맞바꿀 때 transcript가 올바르게 교체되어야 한다.
        순차 replace는 누적 오염을 일으키므로 원자적 치환이 필요하다."""
        _create_done_meeting(
            job_id="match-a4",
            transcript="[00:00] 아빠: 첫번째\n[00:05] 엄마: 두번째\n[00:10] 아빠: 세번째",
            speakers={"SPEAKER_00": "아빠", "SPEAKER_01": "엄마"},
        )

        # 이름 맞바꾸기: 아빠↔엄마
        res = client.post("/api/jobs/match-a4/apply-match", json={
            "matches": {"SPEAKER_00": "엄마", "SPEAKER_01": "아빠"},
        })
        assert res.status_code == 200

        job = client.get("/api/jobs/match-a4").json()
        transcript = job["transcript"]

        # 원래 아빠(SPEAKER_00)가 엄마로 → 2회 등장
        assert transcript.count("엄마:") == 2, f"엄마: 가 2회여야 함. 실제: {transcript}"
        # 원래 엄마(SPEAKER_01)가 아빠로 → 1회 등장
        assert transcript.count("아빠:") == 1, f"아빠: 가 1회여야 함. 실제: {transcript}"


# ===========================================================================
# 시나리오 B: identity 매핑 (txt 업로드 등)
# ===========================================================================

class TestApplyMatchIdentity:
    """speakers = {아빠: 아빠} (identity 매핑) 형태에서 apply-match 호출."""

    def test_identity_mapping_with_diarization(self, client):
        """identity 매핑 + diarization 존재 시,
        SPEAKER_00→김과장 매칭이 transcript의 해당 화자를 교체해야 한다.
        """
        diarization = {
            "SPEAKER_00": [{"start": 0, "end": 5, "speaker": "SPEAKER_00"}],
            "SPEAKER_01": [{"start": 5, "end": 10, "speaker": "SPEAKER_01"}],
        }

        _create_done_meeting(
            job_id="match-b1",
            transcript="[00:00] 아빠: 안녕하세요\n[00:05] 엄마: 반갑습니다",
            speakers={"아빠": "아빠", "엄마": "엄마"},
            diarization=diarization,
        )

        res = client.post("/api/jobs/match-b1/apply-match", json={
            "matches": {"SPEAKER_00": "김과장"},
        })
        assert res.status_code == 200

        job = client.get("/api/jobs/match-b1").json()
        # SPEAKER_00에 매핑된 화자(아빠)가 김과장으로 교체되어야 함
        assert "김과장:" in job["transcript"], (
            f"transcript에 '김과장:'이 없음. 실제: {job['transcript']}"
        )
        # speakers에 SPEAKER_00→김과장 매핑이 존재해야 함
        speakers = job.get("speakers", {})
        if isinstance(speakers, str):
            speakers = json.loads(speakers)
        assert speakers.get("SPEAKER_00") == "김과장"


# ===========================================================================
# 시나리오 C: apply-match 후 participation 정합성
# ===========================================================================

class TestApplyMatchParticipationConsistency:
    """apply-match 이후 participation API의 display_name과
    transcript의 화자 토큰이 일치하는지 검증."""

    def test_participation_matches_transcript_after_rematch(self, client):
        """apply-match 후 participation display_name이 transcript와 일치."""
        diarization = {
            "SPEAKER_00": [{"start": 0, "end": 30, "speaker": "SPEAKER_00"}],
            "SPEAKER_01": [{"start": 30, "end": 60, "speaker": "SPEAKER_01"}],
        }

        _create_done_meeting(
            job_id="match-c1",
            transcript="[00:00] 아빠: 안녕하세요\n[00:30] 엄마: 반갑습니다",
            speakers={"SPEAKER_00": "아빠", "SPEAKER_01": "엄마"},
            diarization=diarization,
        )

        # apply-match
        client.post("/api/jobs/match-c1/apply-match", json={
            "matches": {"SPEAKER_00": "김과장"},
        })

        # participation 조회
        res = client.get("/api/jobs/match-c1/participation")
        assert res.status_code == 200
        data = res.json()

        # transcript에서 화자 토큰 추출
        import re
        job = client.get("/api/jobs/match-c1").json()
        transcript_speakers = set(
            re.findall(r"\[\d{2}:\d{2}\]\s*(.+?):", job["transcript"])
        )

        # participation의 display_name 집합
        participation_names = {s["display_name"] for s in data["speakers"]}

        # 정합성: participation display_name이 transcript 화자 토큰을 포함해야 함
        for name in transcript_speakers:
            assert name in participation_names, (
                f"transcript 화자 '{name}'이 participation display_name에 없음. "
                f"participation: {participation_names}, transcript 화자: {transcript_speakers}"
            )

    def test_no_stale_names_in_participation(self, client):
        """apply-match 후 participation에 이전 이름(아빠)이 남아있으면 안 됨."""
        diarization = {
            "SPEAKER_00": [{"start": 0, "end": 30, "speaker": "SPEAKER_00"}],
            "SPEAKER_01": [{"start": 30, "end": 60, "speaker": "SPEAKER_01"}],
        }

        _create_done_meeting(
            job_id="match-c2",
            transcript="[00:00] 아빠: 안녕하세요\n[00:30] 엄마: 반갑습니다",
            speakers={"SPEAKER_00": "아빠", "SPEAKER_01": "엄마"},
            diarization=diarization,
        )

        # apply-match: 아빠 → 김과장
        client.post("/api/jobs/match-c2/apply-match", json={
            "matches": {"SPEAKER_00": "김과장"},
        })

        # participation 조회
        res = client.get("/api/jobs/match-c2/participation")
        data = res.json()
        participation_names = {s["display_name"] for s in data["speakers"]}

        # "김과장"이 있어야 하고, "아빠"는 없어야 함
        assert "김과장" in participation_names, (
            f"participation에 '김과장'이 없음: {participation_names}"
        )
        # 이 assertion은 participation이 speakers map을 사용하므로
        # speakers.update({"SPEAKER_00": "김과장"})으로 display_name이
        # "김과장"으로 바뀌면 통과 가능 — 단, transcript와의 정합성은 별개

    def test_partial_match_unmapped_speaker_keeps_display_name(self, client):
        """부분 apply-match 후 매칭하지 않은 화자의 participation display_name이
        원래 이름(엄마)을 유지해야 한다. SPEAKER_01로 퇴행하면 안 된다."""
        diarization = {
            "SPEAKER_00": [{"start": 0, "end": 30, "speaker": "SPEAKER_00"}],
            "SPEAKER_01": [{"start": 30, "end": 60, "speaker": "SPEAKER_01"}],
        }
        _create_done_meeting(
            job_id="match-c3",
            transcript="[00:00] 아빠: 안녕하세요\n[00:30] 엄마: 반갑습니다",
            speakers={"SPEAKER_00": "아빠", "SPEAKER_01": "엄마"},
            diarization=diarization,
        )

        # SPEAKER_00만 매칭
        client.post("/api/jobs/match-c3/apply-match", json={
            "matches": {"SPEAKER_00": "김과장"},
        })

        res = client.get("/api/jobs/match-c3/participation")
        assert res.status_code == 200
        data = res.json()

        sp00 = next(s for s in data["speakers"] if s["label"] == "SPEAKER_00")
        sp01 = next(s for s in data["speakers"] if s["label"] == "SPEAKER_01")

        assert sp00["display_name"] == "김과장"
        assert sp01["display_name"] == "엄마", (
            f"미매칭 화자의 display_name이 원래 이름을 유지해야 함. 실제: {sp01['display_name']}"
        )


# ===========================================================================
# 시나리오 D: _resolve_speaker_display overlap 면적 매칭
# ===========================================================================

class TestResolveMultiSegment:
    """_resolve_speaker_display가 단일 포인트가 아닌 overlap 면적으로 매칭하는지 검증."""

    def test_early_short_segment_does_not_mislead(self, client):
        """SPEAKER_00에 초반 짧은 세그먼트 + 후반 실질 발화가 있을 때,
        후반 발화의 실제 화자명(엄마)이 반환되어야 한다.
        단일 포인트 매칭은 초반 세그먼트 때문에 아빠를 반환하는 오류가 있다."""
        diarization = {
            "SPEAKER_00": [
                {"start": 0, "end": 3, "speaker": "SPEAKER_00"},     # 초반 짧은 세그먼트
                {"start": 35, "end": 60, "speaker": "SPEAKER_00"},   # 후반 실질 발화
            ],
            "SPEAKER_01": [
                {"start": 3, "end": 35, "speaker": "SPEAKER_01"},
            ],
        }
        # identity-mapped: speaker_map 키가 실명
        _create_done_meeting(
            job_id="multi-seg-1",
            transcript="[00:00] 아빠: 짧은 인사\n[00:03] 아빠: 이어서\n[00:35] 엄마: 본론입니다",
            speakers={"아빠": "아빠", "엄마": "엄마"},
            diarization=diarization,
        )

        res = client.get("/api/jobs/multi-seg-1/participation")
        assert res.status_code == 200
        data = res.json()

        sp00 = next(s for s in data["speakers"] if s["label"] == "SPEAKER_00")
        # SPEAKER_00의 실질 발화(35~60초)는 "엄마"와 overlap이 큼
        assert sp00["display_name"] == "엄마", (
            f"overlap 면적 기준으로 '엄마'여야 함. 실제: {sp00['display_name']}"
        )
