"""
TDD 테스트: save_speaker_profile 엔드포인트의 화자 이름 매핑 버그.

버그: speaker_label에 매핑된 이름("김팀장")이 들어오면
diarization JSON에서 원래 키("SPEAKER_00")를 찾지 못해 422 에러 발생.
"""

import json
from unittest.mock import patch, AsyncMock

import numpy as np
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


@pytest.fixture
def setup_job_with_diarization(tmp_path, client):
    """diarization JSON + WAV + speakers 매핑이 있는 done 상태 job 생성."""
    import app.database as dbmod
    import app.main as mainmod

    input_dir = tmp_path / "input"

    def _setup(speakers: dict, diarization: dict):
        # job 생성
        job = dbmod.create_job("test.webm", "meeting")
        job_id = job["id"]

        # job을 done 상태로 + speakers 매핑 설정
        dbmod.update_job_result(
            job_id,
            transcript="[00:00] SPEAKER_00: 안녕하세요\n[00:05] SPEAKER_01: 반갑습니다",
            speakers=speakers,
            status="done",
        )

        # diarization JSON 파일 생성
        diar_path = input_dir / f"{job_id}_diarization.json"
        diar_path.write_text(json.dumps(diarization), encoding="utf-8")

        # 더미 WAV 파일 생성 (실제 embedding 추출은 mock)
        wav_path = input_dir / f"{job_id}_16k.wav"
        wav_path.write_bytes(b"\x00" * 100)

        return job_id

    return _setup


def _mock_embedding(*args, **kwargs):
    """extract_speaker_embedding mock: 192차원 랜덤 embedding 반환."""
    return np.random.randn(192).astype(np.float32)


# ─────────────────────────────────────────────────────────────────────
# 테스트 1-1: 매핑된 이름으로 diarization 조회 (현재 실패해야 함)
# ─────────────────────────────────────────────────────────────────────
@patch("app.audio_processor.extract_speaker_embedding", side_effect=_mock_embedding)
def test_save_profile_with_mapped_name(mock_emb, client, setup_job_with_diarization):
    """speaker_label이 매핑된 이름("김팀장")일 때도 정상 동작해야 한다.

    현재 코드: diar_data.get("김팀장") → None → 422 에러 (버그)
    수정 후: speakers 매핑을 역방향 조회하여 SPEAKER_00을 찾아야 함.
    """
    speakers = {"SPEAKER_00": "김팀장", "SPEAKER_01": "이대리"}
    diarization = {
        "SPEAKER_00": [{"start": 0.0, "end": 5.0}, {"start": 10.0, "end": 15.0}],
        "SPEAKER_01": [{"start": 5.0, "end": 10.0}],
    }

    job_id = setup_job_with_diarization(speakers, diarization)

    res = client.post(
        f"/api/jobs/{job_id}/save-speaker-profile",
        json={"speaker_label": "김팀장", "profile_name": "김팀장"},
    )

    assert res.status_code == 200, f"매핑된 이름으로 프로필 추출 실패: {res.json()}"
    data = res.json()
    assert "id" in data
    assert data["name"] == "김팀장"


# ─────────────────────────────────────────────────────────────────────
# 테스트 1-2: SPEAKER_XX 키로 직접 조회 (regression 방지)
# ─────────────────────────────────────────────────────────────────────
@patch("app.audio_processor.extract_speaker_embedding", side_effect=_mock_embedding)
def test_save_profile_with_original_speaker_key(mock_emb, client, setup_job_with_diarization):
    """speaker_label이 원래 키("SPEAKER_00")일 때 정상 동작해야 한다.

    이미 동작하는 케이스. 수정 후에도 깨지지 않아야 한다.
    """
    speakers = {"SPEAKER_00": "김팀장", "SPEAKER_01": "이대리"}
    diarization = {
        "SPEAKER_00": [{"start": 0.0, "end": 5.0}, {"start": 10.0, "end": 15.0}],
        "SPEAKER_01": [{"start": 5.0, "end": 10.0}],
    }

    job_id = setup_job_with_diarization(speakers, diarization)

    res = client.post(
        f"/api/jobs/{job_id}/save-speaker-profile",
        json={"speaker_label": "SPEAKER_00", "profile_name": "김팀장"},
    )

    assert res.status_code == 200, f"원래 키로 프로필 추출 실패: {res.json()}"
    data = res.json()
    assert "id" in data
    assert data["name"] == "김팀장"


# ─────────────────────────────────────────────────────────────────────
# 테스트 1-3: identity mapping (SPEAKER_00 → SPEAKER_00)
# ─────────────────────────────────────────────────────────────────────
@patch("app.audio_processor.extract_speaker_embedding", side_effect=_mock_embedding)
def test_save_profile_with_identity_mapping(mock_emb, client, setup_job_with_diarization):
    """speakers가 identity mapping일 때도 정상 동작해야 한다.

    speakers = {"SPEAKER_00": "SPEAKER_00"} 이고 speaker_label = "SPEAKER_00"
    """
    speakers = {"SPEAKER_00": "SPEAKER_00"}
    diarization = {
        "SPEAKER_00": [{"start": 0.0, "end": 5.0}, {"start": 10.0, "end": 15.0}],
    }

    job_id = setup_job_with_diarization(speakers, diarization)

    res = client.post(
        f"/api/jobs/{job_id}/save-speaker-profile",
        json={"speaker_label": "SPEAKER_00", "profile_name": "테스트화자"},
    )

    assert res.status_code == 200, f"identity mapping 프로필 추출 실패: {res.json()}"
    data = res.json()
    assert "id" in data
    assert data["name"] == "테스트화자"
