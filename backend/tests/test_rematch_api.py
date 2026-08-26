"""
TDD 테스트: rematch / apply-match API.

기능 2 — 기존 녹음에서 voice profile 자동 매칭 + 적용.
API가 아직 구현되지 않았으므로 현재는 모두 실패해야 정상.
"""

import json
from unittest.mock import patch, AsyncMock

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

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


@pytest.fixture
def create_done_job(tmp_path):
    """done 상태 job을 생성하는 헬퍼. diarization/speakers 옵션 지정 가능."""
    import app.database as dbmod

    def _create(
        *,
        speakers: dict | None = None,
        diarization: dict | None = None,
        transcript: str = "[00:00] SPEAKER_00: 안녕하세요\n[00:05] SPEAKER_01: 반갑습니다",
        status: str = "done",
    ):
        job = dbmod.create_job("test.webm", "meeting")
        job_id = job["id"]
        dbmod.update_job_result(
            job_id,
            transcript=transcript,
            speakers=speakers or {"SPEAKER_00": "SPEAKER_00", "SPEAKER_01": "SPEAKER_01"},
            diarization=diarization,
            status=status,
        )
        # 더미 WAV 파일 (embedding 추출은 mock)
        wav_path = tmp_path / "input" / f"{job_id}_16k.wav"
        wav_path.write_bytes(b"\x00" * 100)
        return job_id

    return _create


@pytest.fixture
def create_voice_profile():
    """voice_profile을 DB에 직접 생성하는 헬퍼."""
    import app.database as dbmod

    def _create(name: str = "김팀장"):
        emb = np.random.randn(192).astype(np.float32)
        profile = dbmod.create_voice_profile(name, emb.tobytes(), len(emb))
        return profile

    return _create


def _mock_embedding(*args, **kwargs):
    """extract_speaker_embedding mock: 192차원 랜덤 embedding 반환."""
    return np.random.randn(192).astype(np.float32)


def _mock_match_high_confidence(speaker_embedding):
    """match_speaker_to_profiles mock: 항상 높은 confidence로 매칭."""
    return {"profile_id": "test-profile-id", "name": "김팀장", "confidence": 85.2}


async def _async_mock_match_high_confidence(speaker_embedding):
    """async 버전 match mock."""
    return {"profile_id": "test-profile-id", "name": "김팀장", "confidence": 85.2}


async def _async_mock_match_none(speaker_embedding):
    """async 버전: 매칭 없음."""
    return None


# ===========================================================================
# POST /api/jobs/{job_id}/rematch 테스트
# ===========================================================================


@patch("app.main.match_speaker_to_profiles", side_effect=_async_mock_match_high_confidence)
@patch("app.audio_processor.extract_speaker_embedding", side_effect=_mock_embedding)
def test_rematch_done_job_success(
    mock_emb, mock_match, client, create_done_job, create_voice_profile
):
    """done 상태 job + diarization + voice profile → 200 + matches 반환."""
    diarization = {
        "SPEAKER_00": [{"start": 0.0, "end": 5.0}],
        "SPEAKER_01": [{"start": 5.0, "end": 10.0}],
    }
    job_id = create_done_job(diarization=diarization)
    create_voice_profile("김팀장")

    res = client.post(f"/api/jobs/{job_id}/rematch")

    assert res.status_code == 200, f"rematch 실패: {res.text}"
    data = res.json()
    assert "matches" in data
    # 각 화자에 대해 name, confidence, profile_id 필드 확인
    for speaker_key, match_info in data["matches"].items():
        assert "name" in match_info
        assert "confidence" in match_info
        assert "profile_id" in match_info


def test_rematch_not_done_returns_400(client, create_done_job):
    """done이 아닌 상태(pending, awaiting_edit 등) → 400."""
    diarization = {
        "SPEAKER_00": [{"start": 0.0, "end": 5.0}],
    }
    job_id = create_done_job(status="awaiting_edit", diarization=diarization)

    res = client.post(f"/api/jobs/{job_id}/rematch")

    assert res.status_code == 400, f"done 아닌 상태에서 400이 아님: {res.status_code}"


def test_rematch_no_diarization_returns_422(client, create_done_job):
    """diarization 데이터 없음 (txt 업로드 등) → 422."""
    job_id = create_done_job(diarization=None)

    res = client.post(f"/api/jobs/{job_id}/rematch")

    assert res.status_code == 422, f"diarization 없는데 422가 아님: {res.status_code}"


@patch("app.main.match_speaker_to_profiles", side_effect=_async_mock_match_none)
@patch("app.audio_processor.extract_speaker_embedding", side_effect=_mock_embedding)
def test_rematch_no_profiles_returns_empty(
    mock_emb, mock_match, client, create_done_job
):
    """voice profile이 없으면 → 200 + 빈 matches."""
    diarization = {
        "SPEAKER_00": [{"start": 0.0, "end": 5.0}],
    }
    job_id = create_done_job(diarization=diarization)

    res = client.post(f"/api/jobs/{job_id}/rematch")

    assert res.status_code == 200
    data = res.json()
    assert "matches" in data
    # 모든 화자가 매칭 실패 → matches 값이 비어있거나 None
    for speaker_key, match_info in data["matches"].items():
        assert match_info is None or match_info == {}


def test_rematch_job_not_found_returns_404(client):
    """존재하지 않는 job_id → 404."""
    res = client.post("/api/jobs/nonexistent-id/rematch")

    assert res.status_code == 404


# ===========================================================================
# POST /api/jobs/{job_id}/apply-match 테스트
# ===========================================================================


def test_apply_match_updates_transcript(client, create_done_job):
    """apply-match 적용 후 transcript에 화자명이 반영되어야 한다."""
    import app.database as dbmod

    transcript = "[00:00] SPEAKER_00: 안녕하세요\n[00:05] SPEAKER_01: 반갑습니다"
    job_id = create_done_job(
        transcript=transcript,
        diarization={
            "SPEAKER_00": [{"start": 0.0, "end": 5.0}],
            "SPEAKER_01": [{"start": 5.0, "end": 10.0}],
        },
    )

    matches = {"SPEAKER_00": "김팀장", "SPEAKER_01": "이대리"}
    res = client.post(f"/api/jobs/{job_id}/apply-match", json={"matches": matches})

    assert res.status_code == 200, f"apply-match 실패: {res.text}"

    # DB에서 transcript 확인
    job = dbmod.get_job(job_id)
    assert "김팀장" in job["transcript"]
    assert "이대리" in job["transcript"]
    # 원래 SPEAKER_XX 라벨이 치환되었는지
    assert "SPEAKER_00" not in job["transcript"]
    assert "SPEAKER_01" not in job["transcript"]


def test_apply_match_updates_speakers(client, create_done_job):
    """apply-match 적용 후 speakers dict가 업데이트되어야 한다."""
    import app.database as dbmod

    job_id = create_done_job(
        speakers={"SPEAKER_00": "SPEAKER_00", "SPEAKER_01": "SPEAKER_01"},
        diarization={
            "SPEAKER_00": [{"start": 0.0, "end": 5.0}],
            "SPEAKER_01": [{"start": 5.0, "end": 10.0}],
        },
    )

    matches = {"SPEAKER_00": "김팀장", "SPEAKER_01": "이대리"}
    res = client.post(f"/api/jobs/{job_id}/apply-match", json={"matches": matches})

    assert res.status_code == 200

    job = dbmod.get_job(job_id)
    speakers = json.loads(job["speakers"]) if isinstance(job["speakers"], str) else job["speakers"]
    assert speakers.get("SPEAKER_00") == "김팀장"
    assert speakers.get("SPEAKER_01") == "이대리"


def test_apply_match_not_done_returns_400(client, create_done_job):
    """done이 아닌 상태 → 400."""
    job_id = create_done_job(status="pending")

    res = client.post(
        f"/api/jobs/{job_id}/apply-match",
        json={"matches": {"SPEAKER_00": "김팀장"}},
    )

    assert res.status_code == 400


def test_apply_match_empty_matches(client, create_done_job):
    """빈 matches → 200 (변경 없음)."""
    import app.database as dbmod

    original_transcript = "[00:00] SPEAKER_00: 안녕하세요\n[00:05] SPEAKER_01: 반갑습니다"
    job_id = create_done_job(
        transcript=original_transcript,
        diarization={
            "SPEAKER_00": [{"start": 0.0, "end": 5.0}],
            "SPEAKER_01": [{"start": 5.0, "end": 10.0}],
        },
    )

    res = client.post(f"/api/jobs/{job_id}/apply-match", json={"matches": {}})

    assert res.status_code == 200

    # transcript가 변경되지 않았는지 확인
    job = dbmod.get_job(job_id)
    assert job["transcript"] == original_transcript
