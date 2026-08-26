import io

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


def test_upload_audio_file(client):
    """mp3 파일 업로드 시 200 + job_id 반환."""
    fake_audio = io.BytesIO(b"\xff\xfb\x90\x00" * 100)
    res = client.post(
        "/api/upload",
        files={"file": ("test.mp3", fake_audio, "audio/mpeg")},
        data={"category_id": "meeting"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "job_id" in data
    assert data["filename"].endswith(".mp3")


def test_upload_txt_file(client):
    """txt 파일 업로드 시 200 + job_id 반환 + awaiting_edit 상태."""
    content = "화자1: 안녕하세요\n화자2: 반갑습니다"
    fake_txt = io.BytesIO(content.encode("utf-8"))
    res = client.post(
        "/api/upload",
        files={"file": ("meeting.txt", fake_txt, "text/plain")},
        data={"category_id": "meeting"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "job_id" in data
    assert data["filename"].endswith(".txt")

    # job 상태가 awaiting_edit인지 확인
    job_res = client.get(f"/api/jobs/{data['job_id']}")
    assert job_res.status_code == 200
    assert job_res.json()["status"] == "awaiting_edit"


def test_upload_clovanote_txt(client):
    """ClovaNote 형식 txt 파일이 표준 형식으로 변환되어 저장된다."""
    clovanote_content = (
        "새로운 노트\n"
        "2026.08.19 수 오후 1:27\n"
        "손재락\n"
        "\n"
        "\n"
        "참석자 1 00:00\n"
        "어떤 위세 메타나 뭐 쓰고 계세요?\n"
        "\n"
        "참석자 2 00:03\n"
        "아니요. 기관 행안부에서 내려\n"
        "\n"
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
    data = res.json()
    job_id = data["job_id"]

    # job 상태가 awaiting_edit인지 확인
    job_res = client.get(f"/api/jobs/{job_id}")
    assert job_res.status_code == 200
    job = job_res.json()
    assert job["status"] == "awaiting_edit"

    # transcript가 표준 형식으로 변환되었는지 확인
    transcript = job["transcript"]
    assert "[00:00] SPEAKER_00:" in transcript
    assert "[00:03] SPEAKER_01:" in transcript
    assert "[00:05] SPEAKER_00:" in transcript
    # 멀티라인 텍스트가 하나의 줄로 합쳐졌는지 확인
    assert "그걸 쓰고 계신 거죠? 그러면 표준 사전이 따로 있진 않으시겠네요." in transcript

    # speakers에 suggested_names가 저장되었는지 확인
    speakers = job.get("speakers", {})
    assert speakers.get("SPEAKER_00") == "참석자 1"
    assert speakers.get("SPEAKER_01") == "참석자 2"


def test_parse_txt_standard_format():
    """표준 형식 txt는 변환 없이 그대로 반환된다."""
    from app.main import _parse_txt_transcript

    standard = "[00:00] SPEAKER_00: Hello\n[00:05] SPEAKER_01: World"
    converted, speakers, suggested = _parse_txt_transcript(standard)
    assert converted == standard
    assert speakers == ["SPEAKER_00", "SPEAKER_01"]
    assert suggested == {}


def test_parse_txt_clovanote_format():
    """ClovaNote 형식이 올바르게 변환된다."""
    from app.main import _parse_txt_transcript

    clova = "참석자 1 00:00\n안녕하세요\n\n참석자 2 00:03\n반갑습니다\n"
    converted, speakers, suggested = _parse_txt_transcript(clova)
    assert "[00:00] SPEAKER_00: 안녕하세요" in converted
    assert "[00:03] SPEAKER_01: 반갑습니다" in converted
    assert speakers == ["SPEAKER_00", "SPEAKER_01"]
    assert suggested == {"SPEAKER_00": "참석자 1", "SPEAKER_01": "참석자 2"}


def test_parse_txt_unrecognized_format():
    """인식 불가 형식은 원본 그대로 반환된다."""
    from app.main import _parse_txt_transcript

    raw = "그냥 일반 텍스트입니다.\n아무 패턴도 없습니다."
    converted, speakers, suggested = _parse_txt_transcript(raw)
    assert converted == raw
    assert speakers == []
    assert suggested == {}


def test_upload_invalid_extension(client):
    """.pdf 파일 업로드 시 422 반환."""
    fake_pdf = io.BytesIO(b"%PDF-1.4 fake content")
    res = client.post(
        "/api/upload",
        files={"file": ("document.pdf", fake_pdf, "application/pdf")},
    )
    assert res.status_code == 422
    assert "지원하지 않는 파일 형식" in res.json()["detail"]


def test_upload_empty_file(client):
    """빈 파일 업로드 시 422 반환."""
    empty = io.BytesIO(b"")
    res = client.post(
        "/api/upload",
        files={"file": ("empty.mp3", empty, "audio/mpeg")},
    )
    assert res.status_code == 422
    assert "비어 있습니다" in res.json()["detail"]
