"""세그먼트 생산자 2곳 검증 — PR A.

설계 문서: "segments 생산 지점 2곳 (둘 다 새 정보 불필요)
  - merge_and_save(audio_processor.py:465) — diarization 경로
  - _parse_txt_transcript(main.py:1585) — txt·ClovaNote 경로"

## 범위와 제약

- `_parse_txt_transcript`, `merge_and_save`의 **기존 반환 시그니처는 바꾸지 않는다.**
  test_upload.py의 기존 3개 테스트(`test_parse_txt_standard_format` 등)가
  `converted, speakers, suggested = _parse_txt_transcript(...)` 로 3-tuple 언패킹하고
  있고, 이는 PR A의 "기존 215개 테스트 무수정 통과" 게이트에 걸린다.
  즉 segments 기록은 이 두 함수 **내부가 아니라 호출부**(main.py:286-288 /
  job_queue.py:63-74)에서 문자열을 만든 직후 `transcript.parse()`를 호출해
  `update_job_result(..., transcript_segments=...)`로 넘기는 방식이어야 한다.
  아래 첫 두 테스트는 그 호출부 통합 지점을 검증한다.

- audio 파이프라인 전체(FFmpeg/PyAnnote/MLX-Whisper)는 이 저장소에 목(mock) 없이
  단위 테스트하는 기존 패턴이 없다 (grep 결과 0건). merge_and_save는 DB에 직접 쓰지
  않는 순수 함수이므로, 여기서는 **출력 포맷이 새 파서와 호환되는지**(구조적 계약)만
  검증한다. job_queue.py가 실제로 DB에 transcript_segments를 채우는지는 이 테스트
  범위 밖 — director/backend-dev가 구현 시 별도로 확인 필요 (QA 보고에 명시).
"""

import io
import json

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


def _raw_transcript_segments(job_id: str):
    import app.database as dbmod
    conn = dbmod._get_conn()
    try:
        row = conn.execute(
            "SELECT transcript_segments FROM meetings WHERE id = ?", (job_id,)
        ).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 생산자 1: _parse_txt_transcript 경로 (txt 업로드 API)
# ---------------------------------------------------------------------------

def test_txt_upload_standard_format_writes_matching_segments(client):
    """표준 형식 txt 업로드 시, DB에 기록된 transcript_segments를 render()하면
    저장된 transcript 문자열과 정확히 일치한다."""
    from app.transcript import render

    content = "[00:00] SPEAKER_00: 안녕하세요\n[00:05] SPEAKER_01: 반갑습니다"
    fake_txt = io.BytesIO(content.encode("utf-8"))
    res = client.post(
        "/api/upload",
        files={"file": ("meeting.txt", fake_txt, "text/plain")},
        data={"category_id": "meeting"},
    )
    assert res.status_code == 200
    job_id = res.json()["job_id"]

    job = client.get(f"/api/jobs/{job_id}").json()
    raw_segments = _raw_transcript_segments(job_id)
    assert raw_segments is not None, "txt 업로드 직후 transcript_segments가 채워져 있어야 한다"

    segments = json.loads(raw_segments) if isinstance(raw_segments, str) else raw_segments
    assert render(segments) == job["transcript"]


def test_txt_upload_clovanote_format_writes_matching_segments(client):
    """ClovaNote 변환 결과도 동일하게 segments ↔ transcript 문자열이 일치한다."""
    from app.transcript import render

    clovanote_content = (
        "새로운 노트\n"
        "2026.08.19 수 오후 1:27\n"
        "손재락\n\n\n"
        "참석자 1 00:00\n"
        "어떤 위세 메타나 뭐 쓰고 계세요?\n\n"
        "참석자 2 00:03\n"
        "아니요. 기관 행안부에서 내려\n\n"
        "참석자 1 00:05\n"
        "그걸 쓰고 계신 거죠?\n"
        "그러면 표준 사전이 따로 있진 않으시겠네요.\n"
    )
    fake_txt = io.BytesIO(clovanote_content.encode("utf-8"))
    res = client.post(
        "/api/upload",
        files={"file": ("회의록.txt", fake_txt, "text/plain")},
        data={"category_id": "meeting"},
    )
    assert res.status_code == 200
    job_id = res.json()["job_id"]

    job = client.get(f"/api/jobs/{job_id}").json()
    raw_segments = _raw_transcript_segments(job_id)
    assert raw_segments is not None

    segments = json.loads(raw_segments) if isinstance(raw_segments, str) else raw_segments
    assert render(segments) == job["transcript"]

    labels = [s["label"] for s in segments if s["label"] is not None]
    assert labels == ["SPEAKER_00", "SPEAKER_01", "SPEAKER_00"]


def test_existing_parse_txt_transcript_signature_unchanged():
    """회귀 방지: _parse_txt_transcript는 여전히 3-tuple을 반환한다
    (test_upload.py의 기존 3개 테스트가 이 시그니처에 의존한다 — 절대 변경 금지)."""
    from app.main import _parse_txt_transcript

    result = _parse_txt_transcript("[00:00] SPEAKER_00: Hello")
    assert len(result) == 3


# ---------------------------------------------------------------------------
# 생산자 2: merge_and_save (오디오 파이프라인) — 출력 포맷 호환성
# ---------------------------------------------------------------------------

class _FakeTurn:
    def __init__(self, start, end):
        self.start = start
        self.end = end


class _FakeDiarization:
    """pyannote Annotation의 itertracks(yield_label=True) 인터페이스만 흉내낸다."""

    def __init__(self, turns):
        self._turns = turns  # list of (start, end, speaker)

    def itertracks(self, yield_label=True):
        for start, end, speaker in self._turns:
            yield _FakeTurn(start, end), None, speaker


@pytest.fixture
def audio_dirs(tmp_path, monkeypatch):
    import app.audio_processor as apmod
    monkeypatch.setattr(apmod, "INPUT_DIR", tmp_path / "input")
    return apmod


def test_merge_and_save_output_is_lossless_under_new_parser(audio_dirs):
    """merge_and_save가 만드는 [MM:SS] LABEL: text 형식이 새 parse()/render()와
    완전히 호환된다 (round-trip 무손실). PR A는 이 함수의 반환 시그니처를 바꾸지
    않고도, 호출부에서 이 출력에 transcript.parse()를 적용해 segments를 얻을 수 있어야
    한다는 전제를 검증한다."""
    from app.transcript import parse, render

    diarization = _FakeDiarization([
        (0.0, 4.0, "SPEAKER_00"),
        (4.0, 9.0, "SPEAKER_01"),
        (9.0, 15.0, "SPEAKER_00"),
    ])
    transcription = {
        "segments": [
            {"start": 0.5, "text": "안녕하세요"},
            {"start": 4.5, "text": "반갑습니다"},
            {"start": 9.5, "text": "오늘 회의 시작하겠습니다"},
        ]
    }

    script_path, speakers = audio_dirs.merge_and_save(
        diarization, transcription, "job1"
    )[:2]

    content = script_path.read_text(encoding="utf-8")
    segments = parse(content)
    assert render(segments) == content
    assert speakers == ["SPEAKER_00", "SPEAKER_01"]
    assert [s["label"] for s in segments] == ["SPEAKER_00", "SPEAKER_01", "SPEAKER_00"]


def test_merge_and_save_over_99_minutes_output_is_lossless(audio_dirs):
    """100분 초과 회의: merge_and_save의 {minutes:02d} 포맷(자릿수 무제한)이
    새 파서에서도 정확히 왕복된다."""
    from app.transcript import parse, render

    start_sec = 123 * 60 + 45  # 7425초 = 123:45
    diarization = _FakeDiarization([(0.0, start_sec + 5, "SPEAKER_00")])
    transcription = {"segments": [{"start": float(start_sec), "text": "마지막 안건입니다"}]}

    script_path, speakers = audio_dirs.merge_and_save(diarization, transcription, "job1")[:2]
    content = script_path.read_text(encoding="utf-8")

    assert "[123:45]" in content
    segments = parse(content)
    assert render(segments) == content
    assert segments[0]["start"] == start_sec
