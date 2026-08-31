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

    def _setup(speakers: dict, diarization: dict, *, save_diar_file: bool = True):
        # job 생성
        job = dbmod.create_job("test.webm", "meeting")
        job_id = job["id"]

        # job을 done 상태로 + speakers 매핑 + diarization DB 저장
        dbmod.update_job_result(
            job_id,
            transcript="[00:00] SPEAKER_00: 안녕하세요\n[00:05] SPEAKER_01: 반갑습니다",
            speakers=speakers,
            diarization=diarization,
            status="done",
        )

        if save_diar_file:
            # diarization JSON 파일 생성 (하위 호환)
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


# ─────────────────────────────────────────────────────────────────────
# 테스트 2-1: diarization 파일 없이 DB에만 있을 때 프로필 추출 성공
# ─────────────────────────────────────────────────────────────────────
@patch("app.audio_processor.extract_speaker_embedding", side_effect=_mock_embedding)
def test_save_profile_db_only_no_file(mock_emb, client, setup_job_with_diarization):
    """diarization JSON 파일이 없어도 DB에 저장된 데이터로 프로필 추출이 성공해야 한다."""
    speakers = {"SPEAKER_00": "김팀장", "SPEAKER_01": "이대리"}
    diarization = {
        "SPEAKER_00": [{"start": 0.0, "end": 5.0}, {"start": 10.0, "end": 15.0}],
        "SPEAKER_01": [{"start": 5.0, "end": 10.0}],
    }

    job_id = setup_job_with_diarization(speakers, diarization, save_diar_file=False)

    res = client.post(
        f"/api/jobs/{job_id}/save-speaker-profile",
        json={"speaker_label": "SPEAKER_00", "profile_name": "김팀장"},
    )

    assert res.status_code == 200, f"DB-only diarization 프로필 추출 실패: {res.json()}"
    data = res.json()
    assert "id" in data
    assert data["name"] == "김팀장"


# ─────────────────────────────────────────────────────────────────────
# 테스트 2-2: 파일만 있고 DB에 없을 때 lazy migration 확인
# ─────────────────────────────────────────────────────────────────────
@patch("app.audio_processor.extract_speaker_embedding", side_effect=_mock_embedding)
def test_save_profile_lazy_migration_from_file(mock_emb, tmp_path, client, setup_job_with_diarization):
    """파일에만 diarization이 있을 때 프로필 추출 후 DB에 lazy migration되어야 한다."""
    import app.database as dbmod

    speakers = {"SPEAKER_00": "김팀장"}
    diarization = {
        "SPEAKER_00": [{"start": 0.0, "end": 5.0}, {"start": 10.0, "end": 15.0}],
    }

    job_id = setup_job_with_diarization(speakers, diarization, save_diar_file=True)

    # DB에서 diarization 지우기 (파일만 남기기)
    conn = dbmod._get_conn()
    try:
        conn.execute("UPDATE meetings SET diarization = NULL WHERE id = ?", (job_id,))
        conn.commit()
    finally:
        conn.close()

    assert dbmod.get_job_diarization(job_id) is None

    res = client.post(
        f"/api/jobs/{job_id}/save-speaker-profile",
        json={"speaker_label": "SPEAKER_00", "profile_name": "김팀장"},
    )

    assert res.status_code == 200
    # lazy migration 확인: DB에 diarization이 저장되었는지
    migrated = dbmod.get_job_diarization(job_id)
    assert migrated is not None
    assert "SPEAKER_00" in migrated


# ─────────────────────────────────────────────────────────────────────
# 테스트 3-1: identity mapping ({아빠: 아빠}) — 레거시 행은 명시적으로 거부되어야 한다
# ─────────────────────────────────────────────────────────────────────
#
# [계약 뒤집힘, PR C] 이 테스트는 원래 "overlap 휴리스틱으로 SPEAKER_XX를 추론해
# 200을 반환해야 한다"를 단언했다. PR C에서 그 휴리스틱(diar↔transcript 구간
# overlap 면적 추론)을 의도적으로 삭제했으므로 지금은 **422가 맞는 동작**이다.
# 구현이 퇴행한 게 아니다 — 잘못 뒤집으면 폐기된 매칭 방식이 되살아난다.
#
# 왜 삭제했나 (DEVGUIDE.md §10 "[한계] 레거시 행에서 음성 프로필 추출 불가 (PR C)" 참조):
#   - speaker_map 키가 실명(레거시 행)이면 diar 라벨(SPEAKER_XX)과 다리가 없다.
#   - overlap 휴리스틱은 조용히 틀린 화자의 목소리를 프로필로 저장할 위험이 있고,
#     apply_match·participation에서 동일 부류 휴리스틱이 이미 제거되어(PR B)
#     이 엔드포인트만 다르게 동작하는 것 자체가 불일치였다(§10 "일관성 문제").
#   - 조용히 틀리는 대신 422로 명시 거부하는 쪽을 선택했다.
#
# ⚠️ 이 테스트를 다시 200/success로 뒤집지 말 것. 그건 overlap 휴리스틱의 재유입이며,
#    이 프로젝트에서 폐기된 매칭 방식이 두 번 재유입된 사고와 정확히 같은 형태다.
#    대신 422 응답의 오류 문구가 "왜 안 되는지"(레거시 행이라 라벨 다리가 없다는 사실)를
#    실제로 설명하는지까지 단언해서, 이 테스트 자체가 회귀 감시자가 되도록 한다.
@patch("app.audio_processor.extract_speaker_embedding", side_effect=_mock_embedding)
def test_save_profile_with_name_key_identity_mapping(mock_emb, client, setup_job_with_diarization):
    """speakers가 {아빠: 아빠}(레거시: 키가 실명)이고 diarization이 {SPEAKER_00: ...}일 때,
    라벨 공간이 어긋나 프로필 추출이 422로 명시 거부되어야 한다(overlap 휴리스틱 재유입 금지)."""
    import app.database as dbmod

    # identity mapping: 이름이 키 (레거시 행 — speaker_map 키가 diar 라벨과 다리가 없음)
    speakers = {"아빠": "아빠", "손주환": "손주환"}
    diarization = {
        "SPEAKER_00": [{"start": 0.0, "end": 5.0}, {"start": 10.0, "end": 15.0}],
        "SPEAKER_01": [{"start": 5.0, "end": 10.0}, {"start": 20.0, "end": 25.0}],
    }
    # transcript에서 아빠는 [00:00], [00:10]에 발화 → SPEAKER_00과 겹치지만,
    # PR C 이후 이 겹침은 더 이상 라벨 추론 근거로 쓰이지 않는다.
    transcript = "[00:00] 아빠: 안녕\n[00:05] 손주환: 네\n[00:10] 아빠: 뭐해\n[00:20] 손주환: 놀아요"

    job_id = setup_job_with_diarization(speakers, diarization)

    # transcript 업데이트 (fixture는 기본 transcript 사용)
    dbmod.update_job_result(job_id, transcript=transcript)

    res = client.post(
        f"/api/jobs/{job_id}/save-speaker-profile",
        json={"speaker_label": "아빠", "profile_name": "아빠"},
    )

    assert res.status_code == 422, (
        f"레거시 행(speaker_map 키가 실명)은 라벨 다리가 없어 422로 명시 거부되어야 한다. "
        f"200이 나온다면 폐기된 overlap 휴리스틱이 되살아난 것이다: {res.status_code} {res.text}"
    )
    detail = res.json().get("detail", "")
    # 원인(레거시 행이라 라벨 공간이 어긋난다)을 실제로 설명하는지까지 확인 —
    # 문구 없이 422만 통과시키면 "왜 안 되지" 하며 휴리스틱을 되살릴 여지가 남는다.
    assert "아빠" in detail, f"오류 문구에 어떤 화자인지 나와야 한다: {detail}"
    assert ("예전 방식" in detail or "레거시" in detail), (
        f"오류 문구가 '레거시 행이라 안 된다'는 원인을 설명하지 않는다: {detail}"
    )
