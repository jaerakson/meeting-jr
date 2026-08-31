"""rename-speakers/apply-match가 transcript 컬럼에 실명을 굽는다 — 레거시 행의 4번째
재발 경로 (PR C 2라운드, director 지시 최우선 T5).

## 배경
`rename_speakers`(main.py:2170)와 `apply_match`(main.py:2010)는 `transcript_segments`는
라벨 그대로 저장하면서 **`transcript` 컬럼에는 `render_transcript(segments, speaker_map)`로
실명을 구워 저장한다.** 이는 "저장되는 job.transcript는 항상 라벨 그대로다"라는 확정
계약(director) 위반이다.

## 왜 위험한가 — "전체 변경" 편집과 만나면 레거시 행이 생긴다
프론트(Transcript.tsx, 8c47a56)는 이제 `parse(job.transcript)`로 세그먼트 정체성을
만든다. `job.transcript`에 이미 실명이 라벨 자리에 구워져 있으면, parse()는 그 실명을
그대로 `label`로 인식한다. 사용자가 "전체 변경"으로 그 이름을 다시 바꾸면
`speakerMap[실명] = 새이름`(라벨=실명인 새 키)이 생기고, 이 페이로드가 PATCH로 오면
`patch_transcript`(124fa94, B1 수정본)의 `space_map = body_map`이 이 orphan 실명 키를
**라벨 공간의 정식 멤버로 인정**해 (a)에서 그대로 통과시킨다 — `transcript_segments`에
`label == "김팀장"`(라벨이 아니라 실명)인 **레거시 행**이 새로 생긴다.
이 PR이 4라운드째 죽이려는 것과 정확히 같은 부류의 결함이다.

## 이 파일이 도달 조건
TDD 1단계 — 구현 전. 빨간불이 정상이다. 통과시키려고 약화하지 말 것.
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
    (tmp_path / "input").mkdir()
    monkeypatch.setattr(main_module, "OUTPUT_DIR", tmp_path / "output")
    monkeypatch.setattr(main_module, "INPUT_DIR", tmp_path / "input")
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
        summary="## 요약",
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


def test_rename_speakers_stores_transcript_as_labels_not_names(client):
    """rename-speakers 직후 job.transcript는 라벨 그대로여야 한다(새 계약).
    지금은 render_transcript(segments, speaker_map)로 실명을 구워 저장한다."""
    job_id = "rename-bakes-names"
    original_transcript = "[00:00] SPEAKER_00: 첫마디\n[00:05] SPEAKER_01: 둘째마디"
    _create_done_meeting(job_id, original_transcript, speakers={})

    res = client.post(f"/api/jobs/{job_id}/rename-speakers", json={
        "speaker_map": {"SPEAKER_00": "김팀장", "SPEAKER_01": "이대리"},
    })
    assert res.status_code == 200

    job = client.get(f"/api/jobs/{job_id}").json()
    assert "SPEAKER_00:" in job["transcript"] and "SPEAKER_01:" in job["transcript"], (
        f"저장되는 transcript는 항상 라벨 그대로여야 한다(표시는 소비 시점에 "
        f"displayName으로 렌더). 실제: {job['transcript']}"
    )
    assert "김팀장" not in job["transcript"] and "이대리" not in job["transcript"], (
        f"이름이 transcript 본문에 구워지면 계약 위반이다. 실제: {job['transcript']}"
    )


def test_apply_match_stores_transcript_as_labels_not_names(client):
    """apply-match도 같은 계약 위반이다 — 같은 단언."""
    job_id = "apply-match-bakes-names"
    original_transcript = "[00:00] SPEAKER_00: 첫마디\n[00:05] SPEAKER_01: 둘째마디"
    _create_done_meeting(job_id, original_transcript, speakers={})

    res = client.post(f"/api/jobs/{job_id}/apply-match", json={
        "matches": {"SPEAKER_00": "김팀장"},
    })
    assert res.status_code == 200

    job = client.get(f"/api/jobs/{job_id}").json()
    assert "SPEAKER_00:" in job["transcript"], (
        f"저장되는 transcript는 항상 라벨 그대로여야 한다. 실제: {job['transcript']}"
    )
    assert "김팀장" not in job["transcript"], (
        f"이름이 transcript 본문에 구워지면 계약 위반이다. 실제: {job['transcript']}"
    )


def test_rename_then_bulk_rename_via_patch_does_not_create_legacy_row(client):
    """[핵심 재현 — 사용자 경로 전체] rename-speakers로 이름을 붙인 뒤(현재 버그로
    transcript에 실명이 구워짐), 그 화면을 그대로 프론트에서 편집해 "전체 변경"으로
    이름을 다시 바꾸면(김팀장→박부장) — 레거시 행(라벨=실명)이 새로 생기면 안 된다.

    프론트 시뮬레이션 근거:
    - Transcript.tsx는 `parse(job.transcript)`로 세그먼트를 만든다. job.transcript가
      이미 실명("김팀장")을 라벨 자리에 담고 있으면 parse()는 그 실명을 label로 본다.
    - MainArea.tsx는 편집 진입 시 localSpeakerMap을 job.speakers로 시드한다
      ({"SPEAKER_00": "김팀장", "SPEAKER_01": "이대리"}).
    - "전체 변경"(saveSpeakerAll)은 `speakerMap[현재 라벨] = 새 이름`을 추가한다.
      현재 라벨은 parse() 결과인 "김팀장"이므로, 새 키 "김팀장" -> "박부장"이 시드된
      speakerMap에 **추가로** 얹힌다(SPEAKER_00 키는 남아있다 — 둘 다 body로 나간다).
    - render(seg, {})는 라벨을 그대로 두므로 transcript 텍스트 자체는 안 바뀐다
      ("김팀장:"/"이대리:" 그대로) — speaker_map만 바뀐 채로 PATCH된다.
    """
    job_id = "rename-then-bulk-legacy"
    original_transcript = "[00:00] SPEAKER_00: 첫마디\n[00:05] SPEAKER_01: 둘째마디"
    _create_done_meeting(job_id, original_transcript, speakers={})

    client.post(f"/api/jobs/{job_id}/rename-speakers", json={
        "speaker_map": {"SPEAKER_00": "김팀장", "SPEAKER_01": "이대리"},
    })
    job = client.get(f"/api/jobs/{job_id}").json()
    # 프론트가 실제로 받는 job.transcript 그대로(현재 버그로 이름이 구워져 있다).
    baked_transcript = job["transcript"]

    body_speaker_map = {
        "SPEAKER_00": "김팀장", "SPEAKER_01": "이대리",  # localSpeakerMap 시드
        "김팀장": "박부장",  # "전체 변경"이 라벨("김팀장") 기준으로 추가한 신규 키
    }
    res = client.patch(f"/api/jobs/{job_id}/transcript", json={
        "transcript": baked_transcript,
        "speaker_map": body_speaker_map,
    })
    assert res.status_code == 200, res.text

    from app.transcript import get_segments
    segs = get_segments(job_id)
    labels = {s["label"] for s in segs}
    assert labels == {"SPEAKER_00", "SPEAKER_01"}, (
        f"레거시 행(라벨이 diar 라벨이 아니라 실명)이 생기면 안 된다. "
        f"실제: {labels}"
    )

    job2 = client.get(f"/api/jobs/{job_id}").json()
    speakers2 = _get_speakers(job2)
    assert "김팀장" not in speakers2, (
        f"job.speakers에 실명이 키인 고아 항목이 생기면 안 된다(레거시 행의 흔적). "
        f"실제: {speakers2}"
    )
