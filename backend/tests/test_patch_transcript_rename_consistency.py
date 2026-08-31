"""PATCH /api/jobs/{id}/transcript → rename-speakers 경로에 걸친 회귀 테스트 (PR C).

배경 (director 지시 — 재현 확정 결함): PATCH로 transcript를 편집한 뒤 이어서
rename-speakers를 호출하면, PATCH가 transcript_segments를 갱신하지 않았을 경우
get_segments()가 **편집 전(낡은) segments**를 반환해 rename-speakers의 재렌더가
사용자의 편집을 통째로 덮어쓴다. finalize_job에서 PR B가 닫은 것과 같은 부류의
결함이고(`test_finalize_rename_consistency.py` 참고), PATCH 엔드포인트가 별도로
같은 함정을 갖고 있었다 — 엔드포인트가 다르면 같은 교훈이 다시 필요하다.

이 결함은 PATCH 하나만 보거나 rename-speakers 하나만 봐서는 안 잡힌다 — 두
엔드포인트에 걸친 상태(같은 job의 DB 컬럼)를 순서대로 거쳐야 재현된다.

단언을 통과시키려고 약화하지 말 것. 단언이 틀렸다고 판단되면 director에게 보고.
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
        summary="## 요약\n이전 버전",
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


def test_patch_transcript_edit_survives_subsequent_rename_speakers(client):
    """PATCH로 transcript를 편집(새 줄 추가)한 뒤 rename-speakers를 호출해도
    편집 내용이 사라지면 안 된다."""
    original_transcript = "[00:00] SPEAKER_00: 원본 문장\n[00:05] SPEAKER_01: 두번째"
    _create_done_meeting(
        "patch-rename-1", original_transcript,
        speakers={"SPEAKER_00": "김팀장", "SPEAKER_01": "이대리"},
    )

    # PATCH 이전에 segments를 먼저 확보해둔다 — "이미 lazy 백필된 (편집 전) segments가
    # DB에 남아있는" 상태를 명시적으로 재현한다.
    from app.transcript import get_segments
    pre_segments = get_segments("patch-rename-1")
    assert len(pre_segments) == 2

    edited_transcript = (
        "[00:00] SPEAKER_00: 수정된 문장\n"
        "[00:05] SPEAKER_01: 두번째\n"
        "[00:10] SPEAKER_00: 새로 추가한 발언"
    )
    res = client.patch("/api/jobs/patch-rename-1/transcript", json={
        "transcript": edited_transcript,
    })
    assert res.status_code == 200, f"실제: {res.status_code}, body: {res.text}"

    # PATCH 직후: 편집이 그대로 저장돼 있어야 한다.
    job_after_patch = client.get("/api/jobs/patch-rename-1").json()
    assert "새로 추가한 발언" in job_after_patch["transcript"], (
        f"PATCH 직후 편집이 반영돼야 함. 실제: {job_after_patch['transcript']}"
    )

    # rename-speakers 호출 — 편집이 여전히 살아있어야 한다.
    res2 = client.post("/api/jobs/patch-rename-1/rename-speakers", json={
        "speaker_map": {"SPEAKER_00": "박부장"},
    })
    assert res2.status_code == 200

    job = client.get("/api/jobs/patch-rename-1").json()
    assert "새로 추가한 발언" in job["transcript"], (
        f"PATCH로 추가한 발언이 이후 rename-speakers 호출 뒤 사라지면 안 됨 "
        f"(PATCH가 transcript_segments를 갱신하지 않으면, rename-speakers가 편집 전 "
        f"낡은 segments로 재렌더해 이 발언이 통째로 사라진다). 실제: {job['transcript']}"
    )
    assert job["transcript"].count("박부장:") == 2, (
        f"편집으로 늘어난 SPEAKER_00 발언 2건 모두 새 이름으로 반영돼야 함. "
        f"실제: {job['transcript']}"
    )
    assert "이대리:" in job["transcript"]

    from app.transcript import get_segments, render
    post_segments = get_segments("patch-rename-1")
    assert len(post_segments) == 3, (
        f"PATCH 이후 segments도 편집된 3줄로 갱신돼 있어야 함. 실제: {len(post_segments)}줄"
    )
    assert render(post_segments, _get_speakers(job)) == job["transcript"]
