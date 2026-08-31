"""PATCH /api/jobs/{id}/transcript 가 speaker_map 을 수용해야 한다 (PR C 2라운드, 차단 2·3).

## 배경 (director 지시 — 2라운드 코드리뷰에서 확인된 실제 결함)
프론트는 이미 8c47a56·6a4b84d에서 새 계약(본문은 항상 라벨 그대로, 이름은
speaker_map으로 별도 전송)에 맞춰 고쳐졌다. `handleSaveTranscript`가 이제
`{"transcript": "<라벨 그대로>", "speaker_map": {...}}`를 PATCH로 보낸다.
그런데 `patch_transcript`(main.py:788~)는 여전히 body의 `speaker_map`을 완전히
무시하고, 공간(space_map)·복원(restore_map) 모두 **기존 `job.speakers`**만 쓴다.

## 확정 계약 (director)
저장되는 `job.transcript`는 항상 라벨 그대로(`SPEAKER_00`)다. 이름은 `job.speakers`가
나른다. 표시(화면·다운로드·복사·공유)는 소비 시점에 `displayName(label, speakers)`로
렌더한다.

## 실측 — 이 결함은 두 가지 얼굴을 갖는다(둘 다 잠근다)
1. **diarization 데이터가 없는 job** (예: `_create_done_meeting`처럼 diar 없이 만들어진
   회의, 또는 실제로 diar 매칭에 실패한 회의): `restore_segment_labels`의 라벨 공간이
   `job.speakers`(구 이름, 텅 빔)뿐이라 브랜드뉴 라벨이 전부 미해소 → **422**.
2. **diarization 데이터가 있는 job**(실사용 대부분): diar 라벨 공간 덕에 (a)에서
   라벨이 그대로 통과해 **200이 나지만, body의 새 speaker_map이 통째로 무시돼
   `job.speakers`가 갱신되지 않는다** — 사용자가 입력한 이름이 조용히 사라진다.
   422보다 훨씬 위험하다(성공한 것처럼 보이면서 데이터를 버린다).
   두 경로 모두 실측 확인함(이 파일 작성 중 TestClient로 직접 재현).

TDD 1단계 — 구현 전. 아래 단언들은 지금 **빨간불이 정상**이다. 통과시키려고
약화하지 말 것. 구현과 어긋나면 director에게 보고.
"""

import json

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
    speakers = job.get("speakers", {})
    if isinstance(speakers, str):
        speakers = json.loads(speakers)
    return speakers


# ---------------------------------------------------------------------------
# T1 — PATCH가 speaker_map을 수용한다 [차단 2]
# ---------------------------------------------------------------------------

def test_patch_transcript_accepts_new_speaker_map_without_diarization(client):
    """프론트가 실제로 보내는 payload 형태 그대로: 라벨 그대로 렌더된 본문 +
    한 번도 저장된 적 없는 새 이름의 speaker_map. diar 데이터가 없는 회의(예:
    txt 업로드 회의, 또는 diar 매칭 실패)에서는 현재 422가 난다."""
    job_id = "patch-new-names-nodiar"
    original_transcript = "[00:00] SPEAKER_00: 원본1\n[00:05] SPEAKER_01: 원본2"
    _create_done_meeting(
        job_id, original_transcript,
        speakers={},  # 아직 이름 없음 — TranscriptEditor에서 처음 이름을 붙이는 상황
        diarization=None,
    )

    res = client.patch(f"/api/jobs/{job_id}/transcript", json={
        "transcript": original_transcript,  # 라벨 그대로(새 계약)
        "speaker_map": {"SPEAKER_00": "김팀장", "SPEAKER_01": "이대리"},
    })
    assert res.status_code == 200, (
        f"speaker_map을 body로 보내면 200이어야 한다(현재는 라벨 공간에 diar 폴백이 "
        f"없어 422). 실제: {res.status_code} {res.text}"
    )

    job = client.get(f"/api/jobs/{job_id}").json()
    assert _get_speakers(job) == {"SPEAKER_00": "김팀장", "SPEAKER_01": "이대리"}, (
        f"새 이름이 job.speakers에 저장돼야 한다. 실제: {_get_speakers(job)}"
    )

    # 계약: 저장되는 transcript는 항상 라벨 그대로다 — 이름이 본문에 구워지면 안 된다.
    assert "SPEAKER_00:" in job["transcript"] and "SPEAKER_01:" in job["transcript"], (
        f"job.transcript는 라벨 그대로 저장돼야 한다(이름은 job.speakers가 나른다). "
        f"실제: {job['transcript']}"
    )
    assert "김팀장" not in job["transcript"] and "이대리" not in job["transcript"], (
        f"이름이 transcript 본문에 구워지면 계약 위반이다. 실제: {job['transcript']}"
    )

    # transcript_segments 라벨도 전부 SPEAKER_XX여야 한다 — 레거시 행(라벨=실명)이
    # 생기면 이후 apply-match 등에서 고아 키가 생긴다. 폐기된 overlap 휴리스틱이
    # 재유입돼 라벨을 추측했다면 이 정확한 라벨 집합이 깨진다.
    from app.transcript import get_segments
    labels = [s["label"] for s in get_segments(job_id)]
    assert labels == ["SPEAKER_00", "SPEAKER_01"], (
        f"segments 라벨이 원래 순서·값 그대로 SPEAKER_00/01이어야 한다(추측·재배열 없음). "
        f"실제: {labels}"
    )

    # 사람이 읽는 산출물(OUTPUT_DIR .txt)은 이름이 적용된 렌더본이어야 한다.
    script_path = tmp_db_output_path(client, job_id)
    assert script_path.exists(), f"{script_path} 가 생성돼야 한다"
    script_text = script_path.read_text(encoding="utf-8")
    assert "김팀장:" in script_text and "이대리:" in script_text, (
        f"사람이 읽는 스크립트 산출물은 이름이 적용돼야 한다(라벨 그대로면 안 됨). "
        f"실제: {script_text}"
    )
    assert "SPEAKER_00:" not in script_text and "SPEAKER_01:" not in script_text


def test_patch_transcript_new_speaker_map_not_silently_dropped_with_diarization(client):
    """[더 위험한 변종] diar 데이터가 있는 회의(실사용 대부분)에서는 라벨이 diar
    라벨 공간 폴백으로 이미 통과해 **200이 나지만**, body의 새 speaker_map이
    조용히 무시돼 job.speakers가 비어있는 그대로 남는다 — 사용자가 방금 입력한
    화자 이름이 성공 응답과 함께 사라진다. 422보다 발견하기 어려운 사고다."""
    job_id = "patch-new-names-withdiar"
    original_transcript = "[00:00] SPEAKER_00: 원본1\n[00:05] SPEAKER_01: 원본2"
    _create_done_meeting(
        job_id, original_transcript,
        speakers={},
        diarization={
            "SPEAKER_00": [{"start": 0.0, "end": 2.0}],
            "SPEAKER_01": [{"start": 2.0, "end": 4.0}],
        },
    )

    res = client.patch(f"/api/jobs/{job_id}/transcript", json={
        "transcript": original_transcript,
        "speaker_map": {"SPEAKER_00": "김팀장", "SPEAKER_01": "이대리"},
    })
    assert res.status_code == 200, f"실제: {res.status_code} {res.text}"

    job = client.get(f"/api/jobs/{job_id}").json()
    assert _get_speakers(job) == {"SPEAKER_00": "김팀장", "SPEAKER_01": "이대리"}, (
        f"200 응답과 무관하게 이름이 저장돼야 한다. diar 폴백 덕에 200은 이미 나지만, "
        f"speaker_map을 안 읽으면 이름 없이 조용히 성공한다. 실제: {_get_speakers(job)}"
    )


# ---------------------------------------------------------------------------
# T2 — speaker_map 없는 요청은 기존 동작(하위호환) 그대로
# ---------------------------------------------------------------------------

def test_patch_transcript_without_speaker_map_keeps_legacy_name_baked_restore(client):
    """구버전 번들이 speaker_map 없이 **이름이 이미 구워진 본문**만 보내는 경우
    (예전 계약). 기존 restore_segment_labels 방어(job.speakers를 공간/복원 양쪽에
    사용)가 그대로 동작해 라벨을 되돌려야 한다. 이 방어를 제거하는 방향으로
    바꾸면 안 된다 — 유지가 요구사항이다."""
    job_id = "patch-legacy-no-map"
    original_transcript = "[00:00] SPEAKER_00: 원본1\n[00:05] SPEAKER_01: 원본2"
    _create_done_meeting(
        job_id, original_transcript,
        speakers={"SPEAKER_00": "김팀장", "SPEAKER_01": "이대리"},
        diarization=None,
    )

    body = {"transcript": "[00:00] 김팀장: 수정된 발언\n[00:05] 이대리: 원본2"}
    res = client.patch(f"/api/jobs/{job_id}/transcript", json=body)
    assert res.status_code == 200, f"실제: {res.status_code} {res.text}"

    job = client.get(f"/api/jobs/{job_id}").json()
    # speaker_map을 안 보냈으므로 job.speakers는 그대로여야 한다.
    assert _get_speakers(job) == {"SPEAKER_00": "김팀장", "SPEAKER_01": "이대리"}

    from app.transcript import get_segments, render
    segs = get_segments(job_id)
    labels = [s["label"] for s in segs]
    assert labels == ["SPEAKER_00", "SPEAKER_01"], (
        f"이름이 구워진 본문이 들어와도 라벨(SPEAKER_XX)로 복원돼야 한다. 실제: {labels}"
    )
    assert [s["text"] for s in segs] == ["수정된 발언", "원본2"], (
        "편집 내용(텍스트)은 보존돼야 한다 — 라벨 복원이 텍스트를 건드리면 안 된다."
    )
    # 라벨 복원이 render(segments, speakers)로 원문과 표시가 일치하는지도 확인한다.
    assert render(segs, _get_speakers(job)) == "[00:00] 김팀장: 수정된 발언\n[00:05] 이대리: 원본2"


# ---------------------------------------------------------------------------
# T3 — 중복 표시 이름 회의에서 줄 재지정이 보존된다 [차단 3]
# ---------------------------------------------------------------------------

def test_patch_transcript_reassignment_preserved_when_display_names_duplicate(client):
    """마이그레이션 병합복구가 만드는 상태(대표님×3처럼 여러 라벨이 같은 표시
    이름)를 재현한다. 프론트가 새 계약대로 라벨 그대로인 본문(한 줄을
    SPEAKER_00→SPEAKER_01로 재지정한 상태)과 speaker_map을 PATCH로 보내면,
    그 줄의 라벨이 SPEAKER_01로 **유지**돼야 한다 — 표시 이름이 같다는 이유로
    조용히 SPEAKER_00으로 되돌아가면 안 된다(폐기된 overlap 휴리스틱이 하던
    '같은 이름이면 같은 화자로 추측'과 결과적으로 같은 사고다)."""
    job_id = "patch-dup-display-name-reassign"
    dup_speakers = {"SPEAKER_00": "대표님", "SPEAKER_01": "대표님", "SPEAKER_02": "대표님"}
    original_transcript = (
        "[00:00] SPEAKER_00: 발언1\n"
        "[00:05] SPEAKER_01: 발언2\n"
        "[00:10] SPEAKER_02: 발언3"
    )
    _create_done_meeting(job_id, original_transcript, speakers=dup_speakers, diarization=None)

    # 첫 줄(원래 SPEAKER_00)을 SPEAKER_01로 재지정 — 나머지는 그대로.
    reassigned_transcript = (
        "[00:00] SPEAKER_01: 발언1\n"
        "[00:05] SPEAKER_01: 발언2\n"
        "[00:10] SPEAKER_02: 발언3"
    )
    res = client.patch(f"/api/jobs/{job_id}/transcript", json={
        "transcript": reassigned_transcript,
        "speaker_map": dup_speakers,
    })
    assert res.status_code == 200, f"실제: {res.status_code} {res.text}"

    from app.transcript import get_segments
    segs = get_segments(job_id)
    labels = [s["label"] for s in segs]
    assert labels == ["SPEAKER_01", "SPEAKER_01", "SPEAKER_02"], (
        f"재지정이 유지돼야 한다. 표시 이름이 전부 '대표님'으로 같다고 해서 (b)의 "
        f"같은-start·표시이름-일치 휴리스틱이 SPEAKER_00으로 되돌리면 안 된다 "
        f"(현재 구현·구계약에서 발생하던 결함). 실제: {labels}"
    )
    assert [s["text"] for s in segs] == ["발언1", "발언2", "발언3"]


def tmp_db_output_path(client, job_id):
    """현재 TestClient에 바인딩된 OUTPUT_DIR을 읽어 스크립트 파일 경로를 만든다."""
    import app.main as main_module
    return main_module.OUTPUT_DIR / f"{job_id}_스크립트.txt"
