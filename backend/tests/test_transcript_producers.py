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

import asyncio
import io
import json
import uuid
from pathlib import Path

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


def test_txt_upload_standard_format_raw_may_appear_but_still_roundtrips(client):
    """표준 형식 txt 업로드는 **업로드 원본 통과** 분기다 (사용자 파일 그대로 반환).
    정규형을 강제로 재조립하지 않으므로 raw가 생겨도 정상이다 — 여기서 요구하는 건
    오직 바이트 동일성. 비정규 공백(분 앞자리 0 과다)이 섞인 업로드 원본으로 확인한다."""
    from app.transcript import render

    content = "[007:05] SPEAKER_00: 안녕하세요\n[00:05] SPEAKER_01: 반갑습니다"
    fake_txt = io.BytesIO(content.encode("utf-8"))
    res = client.post(
        "/api/upload",
        files={"file": ("meeting.txt", fake_txt, "text/plain")},
        data={"category_id": "meeting"},
    )
    assert res.status_code == 200
    job_id = res.json()["job_id"]
    job = client.get(f"/api/jobs/{job_id}").json()

    assert job["transcript"] == content  # 표준 형식은 원본 그대로 통과
    raw_segments = _raw_transcript_segments(job_id)
    segments = json.loads(raw_segments) if isinstance(raw_segments, str) else raw_segments
    assert render(segments) == content  # raw 경로가 살아있어야 왕복이 성립한다


def test_txt_upload_clovanote_format_writes_matching_segments(client):
    """ClovaNote 변환 결과도 동일하게 segments ↔ transcript 문자열이 일치한다.
    이 경로는 코드가 정규형을 직접 조립하므로 raw가 생기면 안 된다(보강 1)."""
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

    # 보강 1: ClovaNote 변환은 코드가 정규형을 직접 조립하는 경로이므로 raw가 없어야 한다.
    assert all("raw" not in s or s["raw"] is None for s in segments)


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

    result = audio_dirs.merge_and_save(diarization, transcription, "job1")
    script_path, speakers = result[0], result[1]

    content = script_path.read_text(encoding="utf-8")
    assert render(parse(content)) == content  # 재파싱 경로도 무손실
    assert speakers == ["SPEAKER_00", "SPEAKER_01"]
    assert not content.endswith("\n")  # 저장 파일은 "\n".join — 후행 개행 없음

    # merge_and_save가 3-tuple을 반환한다면(설계 문서 확정 방식) 실제 생산 segments도
    # 재파싱 없이 그대로 render() 했을 때 파일 내용과 일치해야 한다.
    if len(result) >= 3:
        produced_segments = result[2]
        assert render(produced_segments) == content
        assert [s["label"] for s in produced_segments] == ["SPEAKER_00", "SPEAKER_01", "SPEAKER_00"]
        assert all("raw" not in s or s["raw"] is None for s in produced_segments)


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


# ---------------------------------------------------------------------------
# 배선 회귀 가드: job_queue.start_worker가 process_audio 결과의 segments를
# 실제로 DB(meetings.transcript_segments)까지 persist하는지.
#
# merge_and_save에 언패킹 테스트가 0건이라는 건 이 경로를 지키는 안전망이
# 없다는 뜻이다 — 3-tuple 확장이 process_audio/job_queue.py까지 안 이어지고
# 끊겨도 위의 단위 테스트들은 전부 초록으로 남는다. 이 테스트가 그 배선을 직접 지킨다.
#
# 무거운 의존성(FFmpeg/PyAnnote/MLX-Whisper)은 audio_processor.process_audio 자체를
# monkeypatch해서 우회한다. job_queue.py의 input_dir 계산은 `Path(__file__).parent.parent
# / "input"` 로 고정되어 있어(모듈 상수가 아니라 함수 내부 지역 계산) monkeypatch로
# 가로챌 수 없다 — 그래서 이 테스트만 실제 backend/input/ 에 더미 오디오 파일을 만들고
# finally에서 반드시 지운다.
# ---------------------------------------------------------------------------

@pytest.fixture
def queue_db(tmp_path, monkeypatch):
    import app.database as dbmod
    monkeypatch.setattr(dbmod, "DB_PATH", tmp_path / "test.db")
    dbmod.init_db()
    return dbmod


@pytest.mark.asyncio
async def test_audio_pipeline_wiring_persists_segments_to_db(queue_db, tmp_path, monkeypatch):
    """job_queue.start_worker 1회 처리 후, DB의 transcript_segments가 채워지고
    render(...)가 transcript 컬럼과 바이트 동일하며, transcript 컬럼은 파일 내용과 동일하다."""
    import app.job_queue as jq
    import app.audio_processor as apmod
    from app.transcript import parse as parse_transcript, render

    # job_queue.job_queue는 프로세스 전역 싱글턴이라 다른 테스트 파일(test_upload.py의
    # 오디오 업로드 등)이 워커 없이 남겨둔 미소비 job_id가 큐에 남아있을 수 있다.
    # 이 테스트만의 격리된 큐로 교체해 순서 의존적 오염을 원천 차단한다.
    monkeypatch.setattr(jq, "job_queue", asyncio.Queue(maxsize=0))

    job_id = f"qa-wiring-{uuid.uuid4().hex[:8]}"
    real_input_dir = Path(__file__).resolve().parent.parent / "input"
    real_input_dir.mkdir(parents=True, exist_ok=True)
    dummy_audio = real_input_dir / f"{job_id}.mp3"

    script_content = "[00:00] SPEAKER_00: 안녕하세요\n[00:05] SPEAKER_01: 반갑습니다"
    fake_script_path = tmp_path / f"{job_id}.txt"
    fake_script_path.write_text(script_content, encoding="utf-8")
    fake_segments = parse_transcript(script_content)

    async def fake_process_audio(file_path, jid, progress_callback, language="ko"):
        return {
            "script_path": str(fake_script_path),
            "speakers": ["SPEAKER_00", "SPEAKER_01"],
            "segments": fake_segments,
            "suggested_names": {},
            "duration_sec": 10,
            "wav_path": None,
            "diarization_segments": {},
        }

    try:
        dummy_audio.write_bytes(b"\xff\xfb\x90\x00")
        queue_db.create_job(job_id, f"{job_id}.mp3")
        monkeypatch.setattr(apmod, "process_audio", fake_process_audio)

        worker_task = asyncio.create_task(jq.start_worker())
        try:
            await jq.job_queue.put(job_id)
            await asyncio.wait_for(jq.job_queue.join(), timeout=5)
        finally:
            worker_task.cancel()
            try:
                await worker_task
            except asyncio.CancelledError:
                pass
    finally:
        dummy_audio.unlink(missing_ok=True)

    job = queue_db.get_job(job_id)
    assert job is not None
    assert job["status"] == "awaiting_edit", job.get("error_msg")
    assert job["transcript"] == script_content

    conn = queue_db._get_conn()
    try:
        row = conn.execute(
            "SELECT transcript_segments FROM meetings WHERE id = ?", (job_id,)
        ).fetchone()
    finally:
        conn.close()
    assert row is not None and row[0] is not None, (
        "process_audio가 반환한 segments가 job_queue.start_worker를 거쳐 "
        "DB까지 도달하지 못했다 — 배선이 끊겼다."
    )
    persisted_segments = json.loads(row[0]) if isinstance(row[0], str) else row[0]
    assert render(persisted_segments) == job["transcript"]
