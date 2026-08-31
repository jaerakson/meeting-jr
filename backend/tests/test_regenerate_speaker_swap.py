"""POST /api/jobs/{id}/regenerate, /finalize — 이름 맞바꾸기(swap) 시 화자 붕괴 회귀 테스트.

배경 (코드리뷰 발견, director 지시): finalize_job·regenerate_summary가 과거
순차 `.replace()`로 speaker_map을 적용해, {"아빠":"엄마","엄마":"아빠"} 같은
맞바꾸기에서 두 화자가 한 명으로 붕괴했다(A→B 치환 직후 B→A 치환이 방금 만든
결과까지 덮어씀). PR B가 이 맞바꾸기를 정식 지원·테스트하면서 화면에서 실제로
도달 가능한 경로로 승격시켰다 — 이 PR 이전에는 rename-speakers/apply-match가
transcript를 안 건드려 메타데이터만 틀어졌지만, 재렌더가 붙은 지금은 사용자가
읽는 요약 스크립트의 데이터 손실이다.

main.py의 finalize_job·regenerate_summary는 이제 둘 다 render_transcript()로
스크립트를 만들어 이 문제를 main.py 선에서 피한다.

QA가 이 테스트를 작성하는 과정에서 **별도의 결함을 하나 더 찾았다**: 그 스크립트를
읽어 Claude에게 넘기는 app/summarizer.py의 generate_summary()가 자신의
_replace_speakers()로 같은 speaker_map을 한 번 더 순차 치환해, 이미 올바르게
렌더된 텍스트 위에서 붕괴를 재현했다. director에게 보고 후 backend-b가
generate_summary()에서 그 치환 호출을 제거하고, 곧이어 `_replace_speakers()`
함수 정의 자체도 삭제했다(폐기된 순차-치환 방식이 이 프로젝트에서 다섯 번째로
재유입됐던 사본 — 죽은 코드로 남겨두지 않고 바로 제거한 것이 맞는 판단이다).
지금은 GREEN이다.

단언을 통과시키려고 약화하지 말 것.
"""

import pytest
from unittest.mock import patch, AsyncMock
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

    # generate_summary()는 app.summarizer 모듈 자신의 OUTPUT_DIR/SPEAKERS_FILE을
    # 참조한다(main.py와 별개 바인딩) — 실제 backend/output, speakers.json 오염 방지.
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


def test_regenerate_with_swapped_names_keeps_two_distinct_speakers(client):
    """이름 맞바꾸기 map으로 요약을 재생성해도 Claude에게 전달되는 스크립트에
    두 화자가 서로 다른 이름으로 남아있어야 한다 — 한 명으로 붕괴하면 안 된다."""
    _create_done_meeting(
        "swap-regen-1",
        "[00:00] 아빠: 첫번째 발언\n[00:05] 엄마: 두번째 발언",
        speakers={"아빠": "엄마", "엄마": "아빠"},  # 맞바꾸기
    )

    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.communicate = AsyncMock(return_value=("# 요약".encode("utf-8"), b""))

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
        res = client.post("/api/jobs/swap-regen-1/regenerate", json={})

    assert res.status_code == 200, f"실제: {res.status_code}, body: {res.text}"

    prompt_args = mock_exec.call_args[0]
    prompt = prompt_args[prompt_args.index("-p") + 1]

    assert prompt.count("엄마:") == 1, (
        f"맞바꾸기 후 스크립트에 '엄마'가 정확히 한 번 남아야 함(label='아빠'였던 화자). "
        f"실제 prompt 발췌: {prompt[:400]!r}"
    )
    assert prompt.count("아빠:") == 1, (
        f"맞바꾸기 후 스크립트에 '아빠'가 정확히 한 번 남아야 함(label='엄마'였던 화자). "
        f"실제 prompt 발췌: {prompt[:400]!r}"
    )


def test_finalize_with_swapped_names_keeps_two_distinct_speakers_in_script(client, tmp_path):
    """finalize에 이름 맞바꾸기 speaker_map을 보내도, 요약용으로 저장되는 스크립트
    파일에 두 화자가 붕괴 없이 남아야 한다. 스크립트 파일은 백그라운드 요약 태스크가
    시작되기 전에 동기적으로 쓰이므로, 응답 직후 바로 검사할 수 있다."""
    _create_done_meeting(
        "finalize-swap-1",
        "[00:00] 아빠: 첫번째 발언\n[00:05] 엄마: 두번째 발언",
        speakers={"아빠": "아빠", "엄마": "엄마"},
    )

    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.communicate = AsyncMock(return_value=("# 요약".encode("utf-8"), b""))

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        res = client.post("/api/jobs/finalize-swap-1/finalize", json={
            "transcript": "[00:00] 아빠: 첫번째 발언\n[00:05] 엄마: 두번째 발언",
            "speaker_map": {"아빠": "엄마", "엄마": "아빠"},  # 맞바꾸기
        })
    assert res.status_code == 200, f"실제: {res.status_code}, body: {res.text}"

    script_path = tmp_path / "input" / "finalize-swap-1.txt"
    content = script_path.read_text(encoding="utf-8")
    assert content.count("엄마:") == 1, (
        f"맞바꾸기 후 finalize 스크립트에 '엄마'가 정확히 한 번 남아야 함. 실제: {content!r}"
    )
    assert content.count("아빠:") == 1, (
        f"맞바꾸기 후 finalize 스크립트에 '아빠'가 정확히 한 번 남아야 함. 실제: {content!r}"
    )
