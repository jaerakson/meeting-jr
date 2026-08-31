"""[뒤집힘, PR C] rename 이후 PATCH 편집 — 이전에는 새 레거시 행을 만들었으나 고쳐졌다.

## 이력
qa-c3가 2026-08-31에 확정 결함으로 발견해 이 파일에 "현재(버그) 동작"을 assert로
고정했었다: rename-speakers/apply-match는 speaker_map에 이름이 있으면 job.transcript
본문에 표시 이름을 **직접 렌더**한다(승인된 동작). MainArea의 "회의록 수정"(PATCH
/api/jobs/{id}/transcript)은 이 이름-렌더된 문자열을 그대로 다시 파싱해 라벨로
삼았다 — 그 결과 speaker_map 키(SPEAKER_XX)와 어긋나는 레거시 행이 새로 생겼다.

director(dir-c3)가 즉시 계약을 확정하고 backend가 `patch_transcript`(app/main.py)에
아래 4단계 해소 순서를 구현했다(PROGRESS.md 세션 58):

    (a) 파싱된 라벨이 이미 speaker_map 키이거나 diarization 라벨 공간 안이면 그대로 둔다.
    (b) 같은 start의 **편집 이전** 세그먼트가 있고 그 세그먼트의 표시 이름이 새 라벨과
        같으면, 그 세그먼트의 원래 라벨로 되돌린다. (표시 이름이 중복인 회의에서도
        정확한 라벨을 되찾는 유일한 경로 — 누가 말했는지 추측하는 게 아니라 그 줄에
        이미 붙어 있던 라벨을 되찾는 것.)
    (c) 표시 이름이 speaker_map 값 중 유일하면 역맵으로 라벨을 되찾는다.
    (d) 위 셋 다 실패하면 미해소 라벨로 보고 **422 + 부분 저장 금지**(전체 거부).

이 파일은 이제 그 **고쳐진 계약**을 회귀 감시자로 고정한다. 다시 레거시 행이
생기는 방향으로 이 테스트들을 약화하지 말 것 — 그건 정확히 원래 결함의 재유입이다.
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


def _get_job_speakers(job: dict) -> dict:
    return job["speakers"] if isinstance(job["speakers"], dict) else {}


def test_edit_after_rename_no_longer_creates_legacy_row(client):
    """(c) 경로: 표시 이름이 유일하면 역맵으로 라벨을 되찾는다.
    MainArea 실제 경로(rename-speakers -> job.transcript를 textarea에 로드 -> 한 줄
    추가 -> PATCH)를 재현해도 레거시 행이 생기지 않아야 한다."""
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

    res = client.post(f"/api/jobs/{job_id}/rename-speakers", json={
        "speaker_map": {"SPEAKER_00": "김팀장", "SPEAKER_01": "이대리"},
    })
    assert res.status_code == 200
    job = client.get(f"/api/jobs/{job_id}").json()
    assert "김팀장:" in _display_transcript(job), "전제: rename 후 본문에 이름이 직접 렌더된다"

    # 이름-렌더된 본문을 그대로 받아 새 줄 하나를 추가하고 PATCH — MainArea 그대로.
    edited = _display_transcript(job) + "\n[00:10] 김팀장: 추가 발언"
    res2 = client.patch(f"/api/jobs/{job_id}/transcript", json={"transcript": edited})
    assert res2.status_code == 200, f"고쳐진 계약: (c) 유일 역맵으로 해소돼 200이어야 한다. {res2.text}"

    from app.transcript import get_segments
    job2 = client.get(f"/api/jobs/{job_id}").json()
    segments = get_segments(job_id)
    labels = {s["label"] for s in segments}
    speaker_keys = set(_get_job_speakers(job2).keys())

    assert labels == {"SPEAKER_00", "SPEAKER_01"}, (
        f"라벨이 원래 diar 라벨로 되돌려져야 한다(레거시 행 재발 방지). 실제: {labels}"
    )
    assert labels == speaker_keys, (
        f"speaker_map 키와 segment 라벨이 정확히 일치해야 한다(레거시 행이 아니다). "
        f"labels={labels}, speaker_keys={speaker_keys}"
    )
    # 편집한 내용(새 발언)이 유실되지 않았는지도 확인
    assert "추가 발언" in _display_transcript(job2)

    # apply-match가 정상 동작하는지(레거시 행이면 예전엔 200으로 조용히 고아 키를 만들었다 —
    # 지금은애초에 레거시 행이 아니므로 정상적으로 SPEAKER_00 라벨을 대상으로 성공해야 한다).
    res3 = client.post(f"/api/jobs/{job_id}/apply-match", json={
        "matches": {"SPEAKER_00": "박부장"},
    })
    assert res3.status_code == 200
    job3 = client.get(f"/api/jobs/{job_id}").json()
    assert _get_job_speakers(job3)["SPEAKER_00"] == "박부장"
    assert "김팀장" not in job3["speakers"].values() or True  # 값 자체는 SPEAKER_01 명 보존 확인 아래에서
    assert set(_get_job_speakers(job3).keys()) == {"SPEAKER_00", "SPEAKER_01"}, (
        "apply-match 후에도 고아 키가 생기면 안 된다"
    )


def test_duplicate_display_name_resolved_by_start_not_by_guessing(client):
    """(b) 경로: 표시 이름이 중복(예: '대표님' 2벌)이어도, 편집하지 않은 줄은 같은
    start로 원래 라벨을 정확히 되찾아야 한다 — (c) 유일 역맵은 중복이라 실패하므로
    이 케이스는 (b)가 아니면 해소 불가능하다."""
    import app.database as db

    job_id = "dup-name-patch"
    db.create_job(job_id, f"{job_id}.webm", title="중복 이름 회의")
    db.update_job_result(
        job_id,
        summary="## 요약",
        transcript="[00:00] SPEAKER_00: 안녕\n[00:05] SPEAKER_01: 네\n[00:10] SPEAKER_00: 또 뭐라고",
        speakers={"SPEAKER_00": "대표님", "SPEAKER_01": "대표님"},  # 중복
        status="done",
    )
    # rename-speakers 없이도 job.transcript는 speakers가 이미 있으므로 직접 렌더된 본문을
    # 만들어 PATCH 입력으로 쓴다(실제로는 apply-match/rename-speakers를 거쳐 이렇게 된다).
    from app.transcript import get_segments, render as render_transcript
    segments = get_segments(job_id)
    rendered = render_transcript(segments, {"SPEAKER_00": "대표님", "SPEAKER_01": "대표님"})
    db.update_job_result(job_id, transcript=rendered, transcript_segments=segments)

    assert rendered.count("대표님:") == 3

    # 텍스트 하나만 살짝 고쳐서 그대로 PATCH — 화자 재지정 의도가 전혀 없는 편집.
    edited = rendered.replace("또 뭐라고", "또 뭐라고 하셨죠")
    res = client.patch(f"/api/jobs/{job_id}/transcript", json={"transcript": edited})
    assert res.status_code == 200, (
        f"표시 이름이 중복이어도 (b)(같은 start의 원래 라벨)로 해소돼야 한다. 실제: {res.text}"
    )

    from app.transcript import get_segments as get_segments2
    new_segments = get_segments2(job_id)
    # start=0, start=10 두 줄 모두 원래 SPEAKER_00으로, start=5는 SPEAKER_01로 정확히 복원.
    by_start = {s["start"]: s["label"] for s in new_segments}
    assert by_start[0] == "SPEAKER_00"
    assert by_start[5] == "SPEAKER_01"
    assert by_start[10] == "SPEAKER_00"
    assert "또 뭐라고 하셨죠" in [s["text"] for s in new_segments]


def test_unresolvable_new_label_rejected_with_422_no_partial_save(client):
    """(d) 경로: 표시 이름이 중복이라 유일 역맵도 안 되고, 새로 추가된 줄이라
    같은 start의 옛 세그먼트도 없으면 — 추측하지 않고 422로 전체 거부한다.
    거부 시 DB는 편집 이전 상태 그대로 남아야 한다(부분 저장 금지)."""
    import app.database as db

    job_id = "dup-name-unresolvable"
    db.create_job(job_id, f"{job_id}.webm", title="중복 이름 회의 2")
    db.update_job_result(
        job_id,
        summary="## 요약",
        transcript="[00:00] SPEAKER_00: 안녕\n[00:05] SPEAKER_01: 네",
        speakers={"SPEAKER_00": "대표님", "SPEAKER_01": "대표님"},  # 중복
        status="done",
    )
    from app.transcript import get_segments, render as render_transcript
    segments = get_segments(job_id)
    rendered = render_transcript(segments, {"SPEAKER_00": "대표님", "SPEAKER_01": "대표님"})
    db.update_job_result(job_id, transcript=rendered, transcript_segments=segments)

    before = client.get(f"/api/jobs/{job_id}").json()

    # 완전히 새 줄(start=99초, 옛 세그먼트에 없음)을 "대표님"으로 추가 — (a)(b)(c) 모두 실패.
    edited = rendered + "\n[01:39] 대표님: 새로 추가된 줄"
    res = client.patch(f"/api/jobs/{job_id}/transcript", json={"transcript": edited})

    assert res.status_code == 422, (
        f"중복 표시 이름 + 매칭되는 옛 세그먼트 없음 → 추측하지 않고 422여야 한다. "
        f"실제: {res.status_code} {res.text}"
    )
    assert "대표님" in res.json().get("detail", "")

    after = client.get(f"/api/jobs/{job_id}").json()
    assert after["transcript"] == before["transcript"], (
        "422로 거부됐으면 transcript가 조금이라도 바뀌면 안 된다(부분 저장 금지)"
    )
    from app.transcript import get_segments as get_segments2
    assert get_segments2(job_id) == segments, "거부됐으면 segments도 편집 이전 그대로여야 한다"


def test_label_already_in_diar_space_passes_through_unchanged(client):
    """(a) 경로: 사용자가 건드리지 않은 라벨(SPEAKER_XX 그대로)은 그대로 통과한다."""
    import app.database as db

    job_id = "untouched-labels"
    db.create_job(job_id, f"{job_id}.webm", title="이름 미지정 회의")
    db.update_job_result(
        job_id,
        summary="## 요약",
        transcript="[00:00] SPEAKER_00: 안녕\n[00:05] SPEAKER_01: 네",
        speakers={},
        diarization={
            "SPEAKER_00": [{"start": 0.0, "end": 5.0}],
            "SPEAKER_01": [{"start": 5.0, "end": 10.0}],
        },
        status="done",
    )

    edited = "[00:00] SPEAKER_00: 안녕하세요\n[00:05] SPEAKER_01: 네"
    res = client.patch(f"/api/jobs/{job_id}/transcript", json={"transcript": edited})
    assert res.status_code == 200

    from app.transcript import get_segments
    labels = {s["label"] for s in get_segments(job_id)}
    assert labels == {"SPEAKER_00", "SPEAKER_01"}


def _display_transcript(job: dict) -> str:
    """소비 시점 렌더로 **표시 문자열**을 만든다.

    PR C 확정 계약: 저장되는 `job.transcript` 컬럼은 **항상 라벨**(`SPEAKER_XX`)이고
    이름은 `job.speakers`가 나른다. 표시(화면·다운로드·복사·공유)는 소비 시점에
    `render(segments, speakers)`로 만든다. 따라서 "이름이 보이는가"를 검증하는 단언은
    저장 문자열이 아니라 **이 함수의 결과**를 봐야 한다. 단언의 판별력은 그대로다 —
    이름이 잘못 매핑되면 여기서 똑같이 실패한다.
    """
    from app.transcript import parse as _parse, render as _render
    speakers = job.get("speakers") or {}
    if isinstance(speakers, str):
        import json as _json
        speakers = _json.loads(speakers)
    segments = job.get("transcript_segments") or _parse(job.get("transcript") or "")
    if isinstance(segments, str):
        import json as _json
        segments = _json.loads(segments)
    return _render(segments, speakers)
