"""app.transcript.get_segments() 백필 계약 테스트 — PR A.

설계 문서(docs/ai_analysis/20260831_화자매핑_라벨_리팩터링_설계.md)의 핵심 요구:
"lazy 파싱 + 조회 시 백필. 일괄 마이그레이션하지 않는다."
(diarization의 DB→파일 폴백 + update_job_result 백필 패턴과 동일 — main.py:2364-2367 참조)

## 가정한 API 계약 (QA가 확정, backend-dev와 정렬 필요)

    get_segments(job_id: str) -> list[dict]
        1. job.transcript_segments 컬럼이 NULL이 아니면 그것을 그대로 반환 (재파싱하지 않음).
        2. NULL이면 job.transcript 문자열을 parse()하고, 그 결과를 DB에 백필한 뒤 반환.
        3. job 자체가 없거나 transcript도 없으면 [] 반환 (예외를 던지지 않음).
    스키마: meetings.transcript_segments TEXT (JSON), _migrate()의 additive ALTER 목록에 추가.

가장 큰 회귀 위험(설계 문서 "회귀 위험" #1)을 정면으로 검증한다:
현재 모든 기존 회의는 transcript_segments가 NULL이므로, 백필 경로의 무손실성이
곧 기존 사용자 데이터 전체의 안전성이다.
"""

import json

import pytest


@pytest.fixture
def db(tmp_path, monkeypatch):
    import app.database as dbmod
    monkeypatch.setattr(dbmod, "DB_PATH", tmp_path / "test.db")
    dbmod.init_db()
    return dbmod


def _raw_column(dbmod, job_id: str, column: str):
    """테스트 전용: sqlite 컬럼 원값을 직접 조회 (백필 여부/원시 JSON 검증용)."""
    conn = dbmod._get_conn()
    try:
        row = conn.execute(
            f"SELECT {column} FROM meetings WHERE id = ?", (job_id,)
        ).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def _set_raw_column(dbmod, job_id: str, column: str, value):
    conn = dbmod._get_conn()
    try:
        conn.execute(f"UPDATE meetings SET {column} = ? WHERE id = ?", (value, job_id))
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 1) NULL인 기존 데이터 — lazy 파싱 + 백필 무손실성 (최대 회귀 위험)
# ---------------------------------------------------------------------------

EXISTING_ROW_CORPUS = {
    "표준 다중 화자": (
        "[00:00] SPEAKER_00: 안녕하세요\n"
        "[00:05] SPEAKER_01: 반갑습니다"
    ),
    "ClovaNote 유래 병합 텍스트": (
        "[00:00] SPEAKER_00: 어떤 위세 메타나 뭐 쓰고 계세요?\n"
        "[00:03] SPEAKER_01: 아니요. 기관 행안부에서 내려"
    ),
    "이름에 콜론 포함 (naive .replace 결과물)": "[00:00] PM:김철수: 오늘 안건입니다",
    "공백 포함 실명": "[00:00] 김 팀장: 회의 시작합니다",
    "100분 초과": "[123:45] SPEAKER_00: 마지막 안건입니다",
    "빈 줄과 깨진 라인 혼재": (
        "[00:00] SPEAKER_00: 시작\n"
        "\n"
        "(웃음)\n"
        "[00:05] SPEAKER_01: 이어서"
    ),
}


@pytest.mark.parametrize(
    "transcript", EXISTING_ROW_CORPUS.values(), ids=list(EXISTING_ROW_CORPUS.keys())
)
def test_backfill_is_byte_identical(db, transcript):
    """segments가 NULL인 기존 행에서 get_segments 호출 후,
    render(get_segments(...))가 원본 transcript 문자열과 바이트 단위로 동일하다."""
    from app.transcript import get_segments, render

    db.create_job("job1", "meeting.mp3")
    db.update_job_result("job1", transcript=transcript)

    # 백필 전: transcript_segments는 NULL이어야 한다
    assert _raw_column(db, "job1", "transcript_segments") is None

    segments = get_segments("job1")
    assert render(segments) == transcript


def test_backfill_writes_back_to_db(db):
    """get_segments 호출 후 DB의 transcript_segments가 더 이상 NULL이 아니다 (백필 확인)."""
    from app.transcript import get_segments

    db.create_job("job1", "meeting.mp3")
    db.update_job_result("job1", transcript="[00:00] SPEAKER_00: 안녕")

    get_segments("job1")

    backfilled = _raw_column(db, "job1", "transcript_segments")
    assert backfilled is not None
    # JSON으로 파싱 가능해야 한다
    parsed = json.loads(backfilled) if isinstance(backfilled, str) else backfilled
    assert isinstance(parsed, list)
    assert len(parsed) == 1


def test_backfill_does_not_mutate_transcript_column(db):
    """백필은 transcript_segments만 채운다. transcript 문자열 컬럼 자체는 손대지 않는다
    (강제 불변식: transcript는 in-place 변경하지 않는다)."""
    from app.transcript import get_segments

    original = "[00:00] SPEAKER_00: 안녕하세요\n[00:05] SPEAKER_01: 반갑습니다"
    db.create_job("job1", "meeting.mp3")
    db.update_job_result("job1", transcript=original)

    get_segments("job1")

    assert db.get_job("job1")["transcript"] == original


# ---------------------------------------------------------------------------
# 2) 이미 segments가 있는 행 — 재파싱하지 않고 그대로 반환
# ---------------------------------------------------------------------------

def test_existing_segments_are_returned_as_is_without_reparsing(db):
    """transcript_segments가 이미 채워진 행은 transcript를 재파싱하지 않고
    저장된 값을 그대로 반환한다 (생산자가 기록한 값이 신뢰의 원천)."""
    from app.transcript import get_segments

    db.create_job("job1", "meeting.mp3")
    # transcript와 '고의로 다른' segments를 직접 심어, 재파싱이 아니라
    # 저장된 값을 그대로 쓰는지 검증한다.
    db.update_job_result("job1", transcript="[00:00] SPEAKER_00: 이것과는 다른 텍스트")
    sentinel_segments = [
        {"start": 0, "end": None, "label": "SPEAKER_00", "text": "SENTINEL"}
    ]
    _set_raw_column(
        db, "job1", "transcript_segments",
        json.dumps(sentinel_segments, ensure_ascii=False),
    )

    result = get_segments("job1")
    assert result == sentinel_segments


# ---------------------------------------------------------------------------
# 3) NULL인 기존 데이터에서 모든 기존 경로가 정상 동작 (운영 규칙 필수 조건)
# ---------------------------------------------------------------------------

def test_get_segments_on_nonexistent_job_returns_empty_list(db):
    from app.transcript import get_segments

    assert get_segments("no-such-job") == []


def test_get_segments_on_job_without_transcript_returns_empty_list(db):
    """transcript도 transcript_segments도 없는 갓 생성된(pending) job — 예외 없이 빈 리스트."""
    from app.transcript import get_segments

    db.create_job("job1", "meeting.mp3")
    assert get_segments("job1") == []


def test_get_segments_on_empty_transcript_returns_empty_list(db):
    from app.transcript import get_segments

    db.create_job("job1", "meeting.mp3")
    db.update_job_result("job1", transcript="")
    assert get_segments("job1") == []


# ---------------------------------------------------------------------------
# 4) identity-mapped 레거시 행 — speaker_map 키가 라벨이 아니라 실명인 경우
# ---------------------------------------------------------------------------

def test_identity_mapped_legacy_row_parses_without_corruption(db):
    """finalize_job의 identity 재키잉(main.py:396-401)을 이미 거친 기존 행:
    speaker_map = {"김철수": "김철수"} 이고 transcript 본문의 라벨도 이미 "김철수"로
    치환되어 있다. 새 파서가 이를 일반 라벨(실명)로 다루며 깨지지 않아야 한다."""
    from app.transcript import get_segments, render

    transcript = (
        "[00:00] 김철수: 오늘 회의 시작하겠습니다\n"
        "[00:10] 이영희: 네 준비됐습니다"
    )
    speaker_map = {"김철수": "김철수", "이영희": "이영희"}

    db.create_job("job1", "meeting.mp3")
    db.update_job_result("job1", transcript=transcript, speakers=speaker_map)

    segments = get_segments("job1")
    assert render(segments) == transcript
    labels = {s["label"] for s in segments if s["label"] is not None}
    assert labels == {"김철수", "이영희"}
