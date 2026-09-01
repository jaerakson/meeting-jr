"""[한계 고정, director 지시] 중복 표시 이름 회의에서 구버전 경로(이름 구운 본문 +
speaker_map 없음)로는 줄 재지정을 표현할 수 없다 — (b)가 항상 원래 start의 라벨로
되돌린다.

## 배경
표시 이름이 중복인 회의(`대표님`×3, 마이그레이션 병합복구가 만드는 상태 — DEVGUIDE
§10 "마이그레이션의 중복 이름 병합" 참조)에서, `speaker_map` 없이 이름이 이미 구워진
본문만 보내는 **구버전 클라이언트**가 `PATCH /transcript`를 호출하면
`restore_segment_labels`의 (b)("같은 start의 옛 세그먼트 표시 이름과 일치하면 그
라벨로 되돌린다")가 **항상** 그 줄의 원래(수정 전) 라벨로 되돌린다.

표시 이름이 전부 같으므로 본문 텍스트만으로는 "이 줄을 다른 화자에게 재귀속시키고
싶다"는 의도를 애초에 표현할 방법이 없다 — 어떤 텍스트를 보내든 라벨은 시작
시각(start) 기준으로만 복원된다. 이건 버그가 아니라 **의도된 방어**다: 추측해서
틀린 화자에게 배정하는 것보다 "원래 라벨 유지"가 안전하다(save_speaker_profile·
마이그레이션과 같은 판단 축).

## 이 테스트가 고정하는 것
- (b)는 손대지 않는다 — 이 테스트는 (b)를 고치라는 요구가 아니라, **지금의 동작을
  의도된 한계로 명시적으로 잠그는 것**이다. 나중에 (b)를 수정하다가 이 한계가
  조용히 사라지거나(=추측이 들어가거나) 반대로 더 심해지면(=텍스트 편집 자체가
  막히면) 이 테스트가 신호를 준다.
- 텍스트 편집(발화 내용 수정) 자체는 이 상황에서도 정상 동작해야 한다 — 라벨만
  원래대로 복원되고 편집한 텍스트는 살아있어야 한다.
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def tmp_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    import app.database as db_module
    monkeypatch.setattr(db_module, "DB_PATH", db_path)
    db_module.init_db()

    import app.main as main_module
    (tmp_path / "output").mkdir()
    monkeypatch.setattr(main_module, "OUTPUT_DIR", tmp_path / "output")
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
        summary="## 요약",
        transcript=transcript,
        speakers=speakers,
        diarization=diarization,
        duration_sec=60,
        status="done",
    )


def test_legacy_name_baked_body_always_restores_original_per_start_label(client):
    """구버전 클라이언트(speaker_map 없음)가 중복 표시 이름 회의의 본문을 편집해
    보내면, 텍스트 편집은 반영되지만 라벨은 항상 원래 start 기준 라벨로 복원된다
    — 어떤 재지정 의도도 이 경로로는 반영되지 않는다(현재 동작, 의도된 한계)."""
    job_id = "legacy-dup-name-limit"
    dup_speakers = {"SPEAKER_00": "대표님", "SPEAKER_01": "대표님", "SPEAKER_02": "대표님"}
    original_transcript = (
        "[00:00] SPEAKER_00: 발언1\n"
        "[00:05] SPEAKER_01: 발언2\n"
        "[00:10] SPEAKER_02: 발언3"
    )
    _create_done_meeting(job_id, original_transcript, speakers=dup_speakers, diarization=None)

    # 구버전 클라이언트: speaker_map 없이, 이름이 이미 구워진 본문. 첫 줄 텍스트만
    # 편집한다(재지정을 "시도"할 방법 자체가 없다 — 헤더가 전부 "대표님"이라 어느
    # 화자에게 재귀속시키고 싶은지 표현할 수 없다).
    body = {
        "transcript": (
            "[00:00] 대표님: 발언1 수정됨\n"
            "[00:05] 대표님: 발언2\n"
            "[00:10] 대표님: 발언3"
        )
    }
    res = client.patch(f"/api/jobs/{job_id}/transcript", json=body)
    assert res.status_code == 200, res.text

    from app.transcript import get_segments
    segs = get_segments(job_id)
    labels = [s["label"] for s in segs]
    texts = [s["text"] for s in segs]

    # 현재 동작(의도된 한계): 라벨은 항상 원래 start 기준으로 복원된다.
    assert labels == ["SPEAKER_00", "SPEAKER_01", "SPEAKER_02"], (
        f"[한계 고정] 중복 표시 이름 회의에서 구버전 경로는 항상 원래 라벨로 복원돼야 "
        f"한다 — 재지정을 시도해도 반영되지 않는다(추측하지 않는다는 방어). "
        f"실제: {labels}"
    )
    # 텍스트 편집 자체는 살아있어야 한다 — 라벨 복원이 편집 내용을 지우면 안 된다.
    assert texts == ["발언1 수정됨", "발언2", "발언3"], (
        f"라벨 복원과 무관하게 텍스트 편집은 반영돼야 한다. 실제: {texts}"
    )
