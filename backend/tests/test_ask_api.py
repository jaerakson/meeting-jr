"""AI 추가 질의 API 테스트 (TDD).

POST /api/jobs/{job_id}/ask — 회의 transcript 기반 Claude 질의
"""

import sys
import os
import asyncio
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


@pytest.fixture(autouse=True)
def tmp_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    import app.database as db_module
    monkeypatch.setattr(db_module, "DB_PATH", db_path)
    db_module.init_db()
    yield db_path


@pytest.fixture()
def client(tmp_db):
    from app.main import app
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------

def _create_done_meeting(job_id: str, title: str = "테스트 회의"):
    import app.database as db
    db.create_job(job_id, f"{job_id}.webm", title=title)
    db.update_job_result(
        job_id,
        summary="## 요약\n회의 내용입니다.",
        transcript="[00:00] SPEAKER_00: 안녕하세요\n[00:05] SPEAKER_01: 네 반갑습니다",
        speakers={"SPEAKER_00": "김철수", "SPEAKER_01": "박영희"},
        duration_sec=300,
        status="done",
    )


def _create_pending_meeting(job_id: str):
    import app.database as db
    db.create_job(job_id, f"{job_id}.webm", title="미완료 회의")


# ---------------------------------------------------------------------------
# mock: claude CLI 성공
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_claude_success(monkeypatch):
    async def mock_subprocess(*args, **kwargs):
        class MockProc:
            returncode = 0
            async def communicate(self):
                return (b"mock answer from claude", b"")
        return MockProc()

    monkeypatch.setattr("asyncio.create_subprocess_exec", mock_subprocess)


# ---------------------------------------------------------------------------
# mock: claude CLI 실패
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_claude_failure(monkeypatch):
    async def mock_subprocess_fail(*args, **kwargs):
        class MockProc:
            returncode = 1
            async def communicate(self):
                return (b"", b"error occurred")
        return MockProc()

    monkeypatch.setattr("asyncio.create_subprocess_exec", mock_subprocess_fail)


# ---------------------------------------------------------------------------
# 1. done 상태 회의에 질문 → 200, answer 포함
# ---------------------------------------------------------------------------

class TestAskSuccess:
    def test_ask_done_meeting(self, client, mock_claude_success):
        """done 상태 회의에 질문 → 200, answer 필드 반환."""
        _create_done_meeting("ask1")

        res = client.post(
            "/api/jobs/ask1/ask",
            json={"question": "이 프로젝트 마감일이 언제?"},
        )
        assert res.status_code == 200
        data = res.json()
        assert "answer" in data
        assert len(data["answer"]) > 0


# ---------------------------------------------------------------------------
# 2. pending 상태 회의 → 400
# ---------------------------------------------------------------------------

class TestAskPendingRejected:
    def test_ask_pending_meeting(self, client, mock_claude_success):
        """pending 상태 회의 → 400."""
        _create_pending_meeting("ask2")

        res = client.post(
            "/api/jobs/ask2/ask",
            json={"question": "질문입니다"},
        )
        assert res.status_code == 400


# ---------------------------------------------------------------------------
# 3. 존재하지 않는 job → 404
# ---------------------------------------------------------------------------

class TestAskNotFound:
    def test_ask_nonexistent_job(self, client):
        """존재하지 않는 job → 404."""
        res = client.post(
            "/api/jobs/nonexistent/ask",
            json={"question": "질문"},
        )
        assert res.status_code == 404


# ---------------------------------------------------------------------------
# 4. 빈 question → 422
# ---------------------------------------------------------------------------

class TestAskEmptyQuestion:
    def test_empty_question(self, client):
        """빈 문자열 question → 422."""
        _create_done_meeting("ask4")

        res = client.post(
            "/api/jobs/ask4/ask",
            json={"question": ""},
        )
        assert res.status_code == 422


# ---------------------------------------------------------------------------
# 5. question 필드 누락 → 422
# ---------------------------------------------------------------------------

class TestAskMissingQuestion:
    def test_missing_question_field(self, client):
        """question 필드 없음 → 422."""
        _create_done_meeting("ask5")

        res = client.post(
            "/api/jobs/ask5/ask",
            json={"wrong_key": "value"},
        )
        assert res.status_code == 422


# ---------------------------------------------------------------------------
# 6. claude CLI 실패 → 500
# ---------------------------------------------------------------------------

class TestAskClaudeFailure:
    def test_claude_cli_error(self, client, mock_claude_failure):
        """claude CLI 비정상 종료 → 500."""
        _create_done_meeting("ask6")

        res = client.post(
            "/api/jobs/ask6/ask",
            json={"question": "질문입니다"},
        )
        assert res.status_code == 500
