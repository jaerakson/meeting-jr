"""Claude에 넘기는 프롬프트(호출부 3곳)에 raw 라벨이 아니라 실명이 들어가야 한다
(PR C 2라운드, director 지시 T7·T9).

## 호출부 3곳
1. `POST /api/jobs/{id}/ask` (main.py:972~) — `claude -p` 서브프로세스에 직접
   `job.get("transcript", "")`를 프롬프트에 꽂는다.
2. `PATCH /api/jobs/{id}/series` (main.py:2292~) — 시리즈 할당 시 자동 후속조치
   생성. `generate_followup_comparison(pending, job.get("transcript",""), ...)`.
3. `POST /api/jobs/{id}/followup/generate` (main.py:2394~) — 수동 후속조치 재생성.
   같은 함수를 같은 방식으로 호출.

## 왜 T9(2·3)가 T7(1)보다 중요한가 (director)
후속조치 대조의 산출물이 액션아이템의 **assignee(담당자)**다. 입력이 `SPEAKER_00`이면
담당자 귀속이 곧바로 깨진다. B2(레거시 행 방지) 수정 이후 신규 행은 전부 라벨이므로
여기를 안 고치면 확정 회귀다.

## 외부 CLI 호출 금지
`claude -p`는 실제로 호출하지 않는다 — `asyncio.create_subprocess_exec`
(ask 경로) 또는 `app.summarizer.generate_followup_comparison`(followup 경로 2곳)을
monkeypatch해 넘어온 인자를 캡처한다.

## 이 파일이 도달 조건
TDD 1단계 — 구현 전. 빨간불이 정상이다.
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    import app.database as db_module
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "test.db")
    db_module.init_db()
    from app.main import app
    with TestClient(app) as c:
        yield c


def _create_done_meeting(job_id, transcript, speakers, title="테스트 회의", action_items=None):
    import app.database as db
    db.create_job(job_id, f"{job_id}.webm", title=title)
    db.update_job_result(
        job_id,
        summary="## 요약\n내용",
        transcript=transcript,
        speakers=speakers,
        duration_sec=60,
        status="done",
    )
    if action_items is not None:
        db.update_job_action_items(job_id, action_items)


TRANSCRIPT = "[00:00] SPEAKER_00: 마이그레이션 진행 중입니다\n[00:05] SPEAKER_01: 네 알겠습니다"
SPEAKERS = {"SPEAKER_00": "김팀장", "SPEAKER_01": "이대리"}


# ---------------------------------------------------------------------------
# T7 — POST /ask
# ---------------------------------------------------------------------------

def test_ask_prompt_uses_display_names_not_raw_labels(client, monkeypatch):
    """POST /ask가 claude -p에 넘기는 prompt에 SPEAKER_00이 아니라 실명이 들어가야
    한다. 외부 CLI는 실제로 부르지 않는다 — subprocess 인자를 캡처한다."""
    job_id = "ask-display-name"
    _create_done_meeting(job_id, TRANSCRIPT, SPEAKERS)

    captured = {}

    async def fake_subprocess_exec(*args, **kwargs):
        captured["args"] = args

        class _Proc:
            returncode = 0

            async def communicate(self):
                return (b"mock answer", b"")

        return _Proc()

    monkeypatch.setattr("asyncio.create_subprocess_exec", fake_subprocess_exec)

    res = client.post(f"/api/jobs/{job_id}/ask", json={"question": "진행 상황은?"})
    assert res.status_code == 200, res.text

    assert "args" in captured, "claude -p 서브프로세스가 호출돼야 한다."
    prompt = captured["args"][2]  # ("claude", "-p", prompt, "--model", model)
    assert "김팀장" in prompt and "이대리" in prompt, (
        f"프롬프트에 실명이 들어가야 한다. 실제 프롬프트: {prompt}"
    )
    assert "SPEAKER_00" not in prompt and "SPEAKER_01" not in prompt, (
        f"프롬프트에 raw 라벨이 노출되면 안 된다. 실제 프롬프트: {prompt}"
    )


# ---------------------------------------------------------------------------
# T9 — 후속조치 대조 호출부 2곳
# ---------------------------------------------------------------------------

def _capture_followup_call(monkeypatch):
    import app.summarizer as summarizer_mod
    captured = {}

    async def fake_generate_followup_comparison(pending_items, transcript, summary, model="claude-sonnet-4-6"):
        captured["transcript"] = transcript
        return [
            {
                "text": pending_items[0]["text"] if pending_items else "",
                "assignee": pending_items[0].get("assignee") if pending_items else "",
                "ai_status": "mentioned",
                "ai_evidence": "mock",
                "user_status": None,
                "confirmed": False,
            }
        ]

    monkeypatch.setattr(summarizer_mod, "generate_followup_comparison", fake_generate_followup_comparison)
    return captured


def _create_series_via_api(client, name: str) -> str:
    res = client.post("/api/series", json={"name": name})
    assert res.status_code == 200
    return res.json()["id"]


def test_followup_auto_generate_on_series_assign_uses_display_names(client, monkeypatch):
    """[호출부 1/2] PATCH /series로 시리즈 할당 시 자동 트리거되는 후속조치 대조에
    넘어가는 transcript가 raw 라벨이 아니라 실명이어야 한다."""
    captured = _capture_followup_call(monkeypatch)

    series_id = _create_series_via_api(client, "T9 자동대조 시리즈")

    _create_done_meeting(
        "t9-auto-prev", "[00:00] SPEAKER_00: 이전 발언", SPEAKERS,
        title="1차 회의",
        action_items=[{"text": "마이그레이션", "assignee": "김팀장", "done": False}],
    )
    res_assign_prev = client.patch("/api/jobs/t9-auto-prev/series", json={"series_id": series_id})
    assert res_assign_prev.status_code == 200

    _create_done_meeting("t9-auto-cur", TRANSCRIPT, SPEAKERS, title="2차 회의")
    res = client.patch("/api/jobs/t9-auto-cur/series", json={"series_id": series_id})
    assert res.status_code == 200, res.text

    assert "transcript" in captured, "자동 후속조치 대조가 호출돼야 한다."
    assert "김팀장" in captured["transcript"] and "이대리" in captured["transcript"], (
        f"자동 대조에 넘어간 transcript는 실명이어야 한다. 실제: {captured['transcript']}"
    )
    assert "SPEAKER_00" not in captured["transcript"] and "SPEAKER_01" not in captured["transcript"], (
        f"raw 라벨이 노출되면 담당자 귀속이 깨진다. 실제: {captured['transcript']}"
    )


def test_followup_manual_generate_uses_display_names(client, monkeypatch):
    """[호출부 2/2] POST /followup/generate(수동 재생성)에 넘어가는 transcript도
    실명이어야 한다."""
    captured = _capture_followup_call(monkeypatch)

    series_id = _create_series_via_api(client, "T9 수동대조 시리즈")

    _create_done_meeting(
        "t9-manual-prev", "[00:00] SPEAKER_00: 이전 발언", SPEAKERS,
        title="1차 회의",
        action_items=[{"text": "마이그레이션", "assignee": "김팀장", "done": False}],
    )
    res_assign_prev = client.patch("/api/jobs/t9-manual-prev/series", json={"series_id": series_id})
    assert res_assign_prev.status_code == 200

    # 현재 회의는 시리즈 할당 시점에는 자동 트리거를 피하려 series_id 없이 만들고
    # 이후 series 컬럼을 직접 세팅해 "수동 재생성" 경로만 단독으로 검증한다.
    _create_done_meeting("t9-manual-cur", TRANSCRIPT, SPEAKERS, title="2차 회의")
    import app.database as db
    db.update_job_series("t9-manual-cur", series_id)

    res = client.post("/api/jobs/t9-manual-cur/followup/generate")
    assert res.status_code == 200, res.text

    assert "transcript" in captured, "수동 후속조치 대조가 호출돼야 한다."
    assert "김팀장" in captured["transcript"] and "이대리" in captured["transcript"], (
        f"수동 재생성에 넘어간 transcript는 실명이어야 한다. 실제: {captured['transcript']}"
    )
    assert "SPEAKER_00" not in captured["transcript"] and "SPEAKER_01" not in captured["transcript"], (
        f"raw 라벨이 노출되면 담당자 귀속이 깨진다. 실제: {captured['transcript']}"
    )


def test_ask_and_followup_call_sites_produce_identical_rendered_transcript(client, monkeypatch):
    """[헬퍼 공유 검증] director는 T7·T9 3개 호출부를 공용 헬퍼 하나로 구현하도록
    지시했다. 세 호출부에 넘어가는 '실명 렌더 결과' 문자열이 동일 입력에 대해
    바이트 동일해야 한다 — 사본이 갈라지면(하나만 고치는 사고) 이 단언이 깨진다."""
    ask_captured = {}

    async def fake_subprocess_exec(*args, **kwargs):
        ask_captured["prompt"] = args[2]

        class _Proc:
            returncode = 0

            async def communicate(self):
                return (b"mock answer", b"")

        return _Proc()

    monkeypatch.setattr("asyncio.create_subprocess_exec", fake_subprocess_exec)
    followup_captured = _capture_followup_call(monkeypatch)

    _create_done_meeting("t9-parity-ask", TRANSCRIPT, SPEAKERS, title="patiry-ask")
    client.post("/api/jobs/t9-parity-ask/ask", json={"question": "요약해줘"})

    series_id = _create_series_via_api(client, "T9 정합성 시리즈")
    _create_done_meeting(
        "t9-parity-prev", "[00:00] SPEAKER_00: 이전 발언", SPEAKERS,
        title="patiry-prev",
        action_items=[{"text": "마이그레이션", "assignee": "김팀장", "done": False}],
    )
    client.patch("/api/jobs/t9-parity-prev/series", json={"series_id": series_id})
    _create_done_meeting("t9-parity-cur", TRANSCRIPT, SPEAKERS, title="patiry-cur")
    client.patch("/api/jobs/t9-parity-cur/series", json={"series_id": series_id})

    assert "prompt" in ask_captured and "transcript" in followup_captured
    # ask는 prompt 문자열 안에 렌더된 transcript를 포함한다 — followup이 캡처한
    # 렌더 결과가 ask 프롬프트 안에 그대로(부분 문자열로) 들어있어야 한다.
    assert followup_captured["transcript"] in ask_captured["prompt"], (
        f"두 호출부가 같은 입력에 다른 렌더 결과를 내면 헬퍼가 공유되지 않은 것이다.\n"
        f"followup 렌더: {followup_captured['transcript']!r}\nask 프롬프트: {ask_captured['prompt']!r}"
    )
