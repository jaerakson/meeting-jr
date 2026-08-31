"""[확정 결함, PR C 범위 — director 보고 완료, qa-c3] rename 이후 PATCH 편집이
새 레거시 행을 만든다.

## 근본 원인
`rename-speakers`/`apply-match`는 speaker_map에 이름이 있으면 transcript 본문에
표시 이름을 **직접 렌더**한다(`backend/app/transcript.py` render(): `display != label`
이면 정규형 렌더 — 이건 PR B/C에서 승인된 의도된 동작이고, `job.transcript`가
finalize/apply_match/rename_speakers/regenerate_summary 전부에서 이 값을 그대로
쓰므로 손댈 수 없다).

`frontend/components/MainArea.tsx`의 `handleStartEditTranscript`는 이 이름-렌더된
`job.transcript`를 그대로 textarea 초기값으로 쓰고, 저장 시 `PATCH
/api/jobs/{id}/transcript`에 그 문자열을 그대로 보낸다(`handleSaveTranscript`).
서버의 `patch_transcript`는 `parse_transcript(transcript)`로 라벨을 다시 뽑는데,
`parse()`는 콜론 앞 토큰을 라벨로 인식하므로 이미 이름이 렌더된 줄에서는
"김팀장" 같은 **실명이 새 라벨**이 된다.

결과: speaker_map 키(`SPEAKER_00`)와 segment label(`"김팀장"`)이 어긋나는
레거시 행이 새로 생긴다 — 정확히 PR C가 "생성자(TranscriptEditor.serialize)를
막았으므로 레거시 행이 더 생기지 않는다"고 주장한 그 카테고리의 손상이다.
`TranscriptEditor`(최초 STT 완료 직후 편집기)는 이 리팩터링에서 막혔지만,
`patch_transcript`(완료된 회의를 나중에 다시 고치는 "회의록 수정" 경로,
MainArea 전용)는 감사 대상에서 빠져 있었다.

## 실측 결과 (2026-08-31, qa-c3 재현)
1) rename-speakers로 이름 부여 → transcript 본문에 "김팀장:" 이 실제로 렌더됨(확인).
2) 그 본문을 그대로(줄 하나 추가) PATCH로 저장 → 200 OK.
3) 이후 segment label 집합 = {"김팀장", "이대리"}, speakers 키 집합 =
   {"SPEAKER_00", "SPEAKER_01"} — **완전히 어긋남**.
4) apply-match를 라벨 "김팀장"으로 호출하면 **200 OK로 조용히 성공**하며
   speakers에 "김팀장" 키가 새로 추가되고 "SPEAKER_00"은 고아로 남는다
   (save_speaker_profile처럼 422로 명시 거부되지도 않음 — 오히려 더 나쁘다:
   `_is_identity_mapped`가 감지하는 "혼합 상태" 레거시 행이 그대로 만들어진다).

이 테스트는 director 보고 완료 후 **현재(버그) 동작을 고정**해 회귀 감시자로
남긴다. 고쳐지면 이 assert들이 깨질 것이다 — 그때 이 파일을 director 지시에 따라
새 계약(고친 동작)으로 뒤집을 것. 통과시키려고 약화하지 말 것.
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


def test_edit_after_rename_creates_legacy_row(client):
    """MainArea 실제 경로(rename-speakers -> job.transcript를 textarea에 로드 -> PATCH)를
    그대로 재현하면 speaker_map 키와 segment label이 어긋나는 레거시 행이 생긴다."""
    import app.database as db

    job_id = "rename-then-edit-1"
    db.create_job(job_id, f"{job_id}.webm", title="테스트 회의")
    db.update_job_result(
        job_id,
        summary="## 요약",
        transcript="[00:00] SPEAKER_00: 안녕\n[00:05] SPEAKER_01: 네",
        speakers={"SPEAKER_00": "SPEAKER_00", "SPEAKER_01": "SPEAKER_01"},
        status="done",
    )

    # 1) rename-speakers로 실명 부여 -> transcript 본문에 이름이 직접 렌더된다(승인된 동작)
    res = client.post(f"/api/jobs/{job_id}/rename-speakers", json={
        "speaker_map": {"SPEAKER_00": "김팀장", "SPEAKER_01": "이대리"},
    })
    assert res.status_code == 200

    job = client.get(f"/api/jobs/{job_id}").json()
    assert "김팀장:" in job["transcript"], (
        f"전제 확인: rename 후 본문에 이름이 직접 렌더돼야 한다(PR B/C 승인 동작). "
        f"실제: {job['transcript']!r}"
    )

    # 2) MainArea.handleStartEditTranscript/handleSaveTranscript 그대로:
    #    job.transcript(이미 이름 렌더된 문자열)를 textarea 초기값으로 받아 한 줄 추가 후 PATCH
    edited = job["transcript"] + "\n[00:10] 김팀장: 추가 발언"
    res2 = client.patch(f"/api/jobs/{job_id}/transcript", json={"transcript": edited})
    assert res2.status_code == 200

    from app.transcript import get_segments
    job2 = client.get(f"/api/jobs/{job_id}").json()
    segments = get_segments(job_id)
    labels = {s["label"] for s in segments}
    speaker_keys = set(job2["speakers"].keys())

    # [확정 결함] 라벨이 실명으로 재키잉됐다 — SPEAKER_00/01이 segments에서 사라졌다.
    assert labels == {"김팀장", "이대리"}, (
        f"버그 재현 실패(더 이상 재현되지 않으면 고쳐진 것 — director 지시로 이 테스트를 "
        f"뒤집을 것). 실제 labels: {labels}"
    )
    # [확정 결함] speaker_map 키(SPEAKER_XX)와 segment label(실명)이 어긋난다 — 레거시 행.
    assert labels != speaker_keys, (
        "버그 재현 실패: speaker_map 키와 segment label이 여전히 일치한다 — "
        "레거시 행이 생기지 않는 것으로 보이면 고쳐진 것이니 director에게 확인 후 이 테스트를 뒤집을 것."
    )
    assert speaker_keys == {"SPEAKER_00", "SPEAKER_01"}, (
        f"speakers 딕셔너리 키는 그대로 SPEAKER_XX로 남아 segment label과 다리가 끊긴다. "
        f"실제: {speaker_keys}"
    )

    # 3) [확정 결함, 더 나쁜 경우] apply-match가 이 어긋난 라벨을 명시 거부(422)하지 않고
    #    오히려 200으로 조용히 받아들여 speakers에 고아 키를 남긴다.
    res3 = client.post(f"/api/jobs/{job_id}/apply-match", json={
        "matches": {"김팀장": "박부장"},
    })
    assert res3.status_code == 200, (
        f"버그 재현 실패(더 이상 200이 아니면 apply-match 쪽 방어가 생긴 것 — director에게 "
        f"확인 후 이 테스트를 뒤집을 것). 실제: {res3.status_code} {res3.text}"
    )
    job3 = client.get(f"/api/jobs/{job_id}").json()
    # SPEAKER_00은 더 이상 어떤 segment label과도 대응하지 않는 고아 키로 남는다.
    assert "SPEAKER_00" in job3["speakers"], (
        "버그 재현 실패: 고아 키가 정리된 것으로 보인다 — 고쳐졌다면 director에게 확인 후 뒤집을 것."
    )
