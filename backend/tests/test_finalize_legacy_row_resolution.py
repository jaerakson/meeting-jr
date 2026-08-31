"""[TDD, 코드리뷰 지적 1] finalize_job도 patch_transcript와 같은 부류로 레거시 행을
만든다 — 회귀 방지 (PR C 프리즈 해제 후속).

## 배경 (director 지시)
`MainArea.tsx`의 "재요약"(`handleResummarize`)이 `/finalize`에 **이름이 이미 렌더된
`job.transcript` + 갱신 안 된 옛 `job.speakers`**를 그대로 보낸다. `finalize_job`은
`patch_transcript`와 달리 파싱한 라벨을 원래 라벨로 되돌리는 처리가 전혀 없어
(abf0227에서 identity 재키잉 분기를 지운 뒤 무방비) 이 입력을 받으면 그대로
`speaker_map` 키(SPEAKER_XX) ≠ segment 라벨(실명)인 레거시 행을 새로 만든다 —
qa-c3가 앞서 잡은 `patch_transcript` 결함(f094860)과 정확히 같은 부류다.

## 수정 계약 (director 확정)
`patch_transcript`와 `finalize_job`이 **같은 (a)(b)(c)(d) 해소 헬퍼**를 공유한다:
- (a) 라벨이 body의 `speaker_map` 키 또는 diar 라벨이면 그대로
- (b)(c)는 **`job.speakers`**(그 텍스트가 렌더된 시점의 speaker_map) 기준으로 복원
- (d) 미해소 시 422, 부분 저장 금지

## 이 파일이 도달 조건
지금은 구현 전이라 아래 단언들은 **빨간불이 정상**이다(director 지시 — 확정된
수정 방향을 바로 테스트로 박고, 버그 동작을 고정하지 않는다). 단언을 통과시키려고
약화하지 말 것. 구현과 어긋나면 director에게 보고.
"""

import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    import app.database as db_module
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "test.db")
    db_module.init_db()

    import app.main as main_module
    (tmp_path / "input").mkdir()
    (tmp_path / "output").mkdir()
    monkeypatch.setattr(main_module, "INPUT_DIR", tmp_path / "input")
    monkeypatch.setattr(main_module, "OUTPUT_DIR", tmp_path / "output")
    monkeypatch.setattr(main_module, "SPEAKERS_FILE", tmp_path / "speakers.json")

    import app.summarizer as summarizer_module
    monkeypatch.setattr(summarizer_module, "OUTPUT_DIR", tmp_path / "output")
    monkeypatch.setattr(summarizer_module, "SPEAKERS_FILE", tmp_path / "speakers.json")

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


def _finalize(client, job_id, transcript, speaker_map):
    """실제 Claude CLI 서브프로세스를 mock해 finalize 호출을 완결시킨다
    (test_finalize_rename_consistency.py와 동일 패턴)."""
    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.communicate = AsyncMock(return_value=("# 요약".encode("utf-8"), b""))
    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        return client.post(f"/api/jobs/{job_id}/finalize", json={
            "transcript": transcript,
            "speaker_map": speaker_map,
        })


def test_resummarize_with_name_rendered_body_does_not_create_legacy_row(client):
    """handleResummarize가 실제로 보내는 payload 형태(이름 렌더된 본문 + 옛 speakers)를
    그대로 재현한다. finalize 후 segment 라벨이 diar 라벨로 복원되고, speaker_map 키와
    segment 라벨이 정확히 일치해야 한다(레거시 행이 생기면 안 된다)."""
    job_id = "resummarize-legacy-guard"
    _create_done_meeting(
        job_id,
        transcript="[00:00] SPEAKER_00: 원본1\n[00:05] SPEAKER_01: 원본2",
        speakers={"SPEAKER_00": "SPEAKER_00", "SPEAKER_01": "SPEAKER_01"},
    )

    # rename-speakers로 이름 부여 — 이후 job.transcript는 이름이 직접 렌더된 상태가 된다
    # (승인된 동작). handleResummarize는 이 상태의 job.transcript/job.speakers를 그대로
    # /finalize에 되돌려보낸다.
    res = client.post(f"/api/jobs/{job_id}/rename-speakers", json={
        "speaker_map": {"SPEAKER_00": "김팀장", "SPEAKER_01": "이대리"},
    })
    assert res.status_code == 200
    job = client.get(f"/api/jobs/{job_id}").json()
    assert "김팀장:" in job["transcript"], "전제: rename 후 본문에 이름이 직접 렌더돼야 한다"

    # handleResummarize 그대로: job.transcript(이름 렌더됨) + job.speakers(옛 그대로)를
    # /finalize에 보낸다. 재요약 카테고리 변경 없이 순수 재요약 시나리오.
    res2 = _finalize(client, job_id, job["transcript"], job["speakers"])
    assert res2.status_code == 200, f"실제: {res2.status_code} {res2.text}"

    job2 = client.get(f"/api/jobs/{job_id}").json()
    from app.transcript import get_segments
    segments = get_segments(job_id)
    labels = {s["label"] for s in segments}
    speaker_keys = set(job2["speakers"].keys())

    assert labels == {"SPEAKER_00", "SPEAKER_01"}, (
        f"재요약 후 segment 라벨이 diar 라벨로 복원돼야 한다(레거시 행 방지). 실제: {labels}"
    )
    assert labels == speaker_keys, (
        f"speaker_map 키와 segment 라벨이 정확히 일치해야 한다. labels={labels}, "
        f"speaker_keys={speaker_keys}"
    )

    # apply-match가 정상 동작하는지(레거시 행이면 고아 키가 생기거나 422가 났을 것).
    # finalize 직후 상태는 백그라운드 요약 완료 전이라 "summarizing"일 수 있다(apply-match
    # 대상 아님) — 이 테스트의 관심사는 요약 완료 타이밍이 아니라 라벨 공간 정합이므로
    # 상태만 done으로 맞춰 확인한다(요약 파이프라인 자체는 다른 테스트의 관심사).
    from app.database import update_job_result
    update_job_result(job_id, status="done")
    res3 = client.post(f"/api/jobs/{job_id}/apply-match", json={
        "matches": {"SPEAKER_00": "박부장"},
    })
    assert res3.status_code == 200
    job3 = client.get(f"/api/jobs/{job_id}").json()
    assert set(job3["speakers"].keys()) == {"SPEAKER_00", "SPEAKER_01"}, (
        "apply-match 후에도 고아 키가 생기면 안 된다"
    )


def test_transcript_editor_normal_finalize_still_returns_200(client):
    """[필수 — 앱 주 흐름 회귀 방지] TranscriptEditor의 정상 계약(라벨 왕복 + 새 이름
    speaker_map)이 여전히 200으로 통과해야 한다. finalize_job에 (a)(b)(c)(d) 해소를
    추가하다가 이 주 흐름을 깨면 앱이 죽는다 — 이 테스트가 그 회귀를 잡는다."""
    job_id = "finalize-normal-path"
    import app.database as db
    db.create_job(job_id, f"{job_id}.webm", title="새 회의")
    db.update_job_result(
        job_id,
        transcript="[00:00] SPEAKER_00: 안녕하세요\n[00:05] SPEAKER_01: 반갑습니다",
        speakers={},
        status="awaiting_edit",
    )

    # TranscriptEditor.handleSubmit 계약: render(segments, {}) — 라벨 그대로, 이름은
    # speaker_map으로만 전달.
    res = _finalize(
        client, job_id,
        "[00:00] SPEAKER_00: 안녕하세요\n[00:05] SPEAKER_01: 반갑습니다",
        {"SPEAKER_00": "신입팀장", "SPEAKER_01": "신입대리"},
    )
    assert res.status_code == 200, (
        f"TranscriptEditor의 정상 입력(라벨 왕복 + 새 이름)이 (a)(b)(c)(d) 도입 후에도 "
        f"200으로 통과해야 한다. 실제: {res.status_code} {res.text}"
    )

    job = client.get(f"/api/jobs/{job_id}").json()
    assert job["speakers"] == {"SPEAKER_00": "신입팀장", "SPEAKER_01": "신입대리"}
    from app.transcript import get_segments
    labels = {s["label"] for s in get_segments(job_id)}
    assert labels == {"SPEAKER_00", "SPEAKER_01"}


def test_patch_transcript_and_finalize_share_resolution_and_agree(client):
    """[헬퍼 공유 검증] 같은 '이름 렌더된 본문 + 편집' 입력을 PATCH /transcript와
    POST /finalize 양쪽에 동일하게 줬을 때, 재키잉된 segment 라벨 구성이 **동일**해야
    한다 — 사본 두 벌로 갈라져 있으면(하나만 고치고 하나는 안 고치는 사고) 이 단언이
    깨진다."""
    import app.database as db

    def _setup(job_id):
        _create_done_meeting(
            job_id,
            transcript="[00:00] SPEAKER_00: 원본1\n[00:05] SPEAKER_01: 원본2",
            speakers={"SPEAKER_00": "SPEAKER_00", "SPEAKER_01": "SPEAKER_01"},
        )
        r = client.post(f"/api/jobs/{job_id}/rename-speakers", json={
            "speaker_map": {"SPEAKER_00": "김팀장", "SPEAKER_01": "이대리"},
        })
        assert r.status_code == 200
        return client.get(f"/api/jobs/{job_id}").json()

    job_a = _setup("shared-helper-patch")
    job_b = _setup("shared-helper-finalize")

    edited = job_a["transcript"] + "\n[00:10] 김팀장: 추가 발언"

    res_patch = client.patch("/api/jobs/shared-helper-patch/transcript", json={
        "transcript": edited,
    })
    assert res_patch.status_code == 200, res_patch.text

    res_finalize = _finalize(client, "shared-helper-finalize", edited, job_b["speakers"])
    assert res_finalize.status_code == 200, res_finalize.text

    from app.transcript import get_segments
    labels_patch = [s["label"] for s in get_segments("shared-helper-patch")]
    labels_finalize = [s["label"] for s in get_segments("shared-helper-finalize")]

    assert labels_patch == labels_finalize == ["SPEAKER_00", "SPEAKER_01", "SPEAKER_00"], (
        f"두 엔드포인트가 같은 입력에 다른 결과를 내면 헬퍼가 공유되지 않은 것이다. "
        f"patch={labels_patch}, finalize={labels_finalize}"
    )
