"""크로스 회의 인사이트 API 테스트 (TDD).

POST /api/insights — 여러 회의의 summary를 기반으로 Claude 크로스 질의
"""

import sys
import os
import time
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

def _create_done_meeting(
    job_id: str,
    title: str,
    summary: str = "## 요약\n내용",
    transcript: str = "[00:00] SP: 텍스트",
):
    import app.database as db
    db.create_job(job_id, f"{job_id}.webm", title=title)
    db.update_job_result(
        job_id,
        summary=summary,
        transcript=transcript,
        speakers={"SP": "화자"},
        duration_sec=300,
        status="done",
    )


def _create_pending_meeting(job_id: str, title: str = "미완료"):
    import app.database as db
    db.create_job(job_id, f"{job_id}.webm", title=title)


# ---------------------------------------------------------------------------
# mock: claude CLI 성공/실패
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_claude_success(monkeypatch):
    async def mock_subprocess(*args, **kwargs):
        class MockProc:
            returncode = 0
            async def communicate(self):
                return (b"cross-meeting insight answer", b"")
        return MockProc()

    monkeypatch.setattr("asyncio.create_subprocess_exec", mock_subprocess)


@pytest.fixture()
def mock_claude_failure(monkeypatch):
    async def mock_subprocess_fail(*args, **kwargs):
        class MockProc:
            returncode = 1
            async def communicate(self):
                return (b"", b"error")
        return MockProc()

    monkeypatch.setattr("asyncio.create_subprocess_exec", mock_subprocess_fail)


# ---------------------------------------------------------------------------
# 1. keyword로 관련 회의 매칭 → 200
# ---------------------------------------------------------------------------

class TestInsightsKeyword:
    def test_keyword_matches_meetings(self, client, mock_claude_success):
        """keyword로 done 회의 필터 → 200, answer/meeting_count/meetings 반환."""
        _create_done_meeting("i1", "프로젝트 킥오프", summary="## 요약\n프로젝트 일정 논의")
        _create_done_meeting("i2", "프로젝트 중간점검", summary="## 요약\n프로젝트 진행 상황")
        _create_done_meeting("i3", "팀 회식", summary="## 요약\n회식 장소 선정")

        res = client.post("/api/insights", json={
            "question": "프로젝트 관련 결정 요약",
            "keyword": "프로젝트",
        })
        assert res.status_code == 200
        data = res.json()
        assert "answer" in data
        assert data["meeting_count"] == 2
        assert len(data["meetings"]) == 2
        for m in data["meetings"]:
            assert "id" in m
            assert "title" in m
            assert "created_at" in m


# ---------------------------------------------------------------------------
# 2. 날짜 필터
# ---------------------------------------------------------------------------

class TestInsightsDateFilter:
    def test_date_range_filters(self, client, mock_claude_success):
        """date_from/date_to로 범위 내 회의만 사용."""
        import app.database as db
        # 회의 생성 (둘 다 done)
        _create_done_meeting("d1", "오래된 회의", summary="## 요약\n과거 내용")
        _create_done_meeting("d2", "최근 회의", summary="## 요약\n최근 내용")

        # 실제 저장된 날짜 조회
        conn = db._get_conn()
        rows = conn.execute(
            "SELECT id, DATE(created_at) as d FROM meetings ORDER BY created_at"
        ).fetchall()
        conn.close()
        stored_date = rows[0]["d"]

        # 미래 날짜 범위로 필터 → 0건 → 404
        res = client.post("/api/insights", json={
            "question": "분석해줘",
            "date_from": "2099-01-01",
            "date_to": "2099-12-31",
        })
        assert res.status_code == 404

        # 저장된 날짜 포함 범위 → 매칭
        res = client.post("/api/insights", json={
            "question": "분석해줘",
            "date_from": stored_date,
            "date_to": stored_date,
        })
        assert res.status_code == 200
        assert res.json()["meeting_count"] >= 1


# ---------------------------------------------------------------------------
# 3. keyword + 날짜 복합 필터
# ---------------------------------------------------------------------------

class TestInsightsCombinedFilter:
    def test_keyword_and_date_combined(self, client, mock_claude_success):
        """keyword + 날짜 동시 필터."""
        import app.database as db
        _create_done_meeting("c1", "프로젝트A", summary="## 요약\n프로젝트 논의")
        _create_done_meeting("c2", "기타 회의", summary="## 요약\n기타 내용")

        conn = db._get_conn()
        row = conn.execute("SELECT DATE(created_at) as d FROM meetings LIMIT 1").fetchone()
        conn.close()
        today = row["d"]

        res = client.post("/api/insights", json={
            "question": "프로젝트 진행 상황은?",
            "keyword": "프로젝트",
            "date_from": today,
            "date_to": today,
        })
        assert res.status_code == 200
        data = res.json()
        assert data["meeting_count"] == 1
        assert data["meetings"][0]["title"] == "프로젝트A"


# ---------------------------------------------------------------------------
# 4. 빈 question → 422
# ---------------------------------------------------------------------------

class TestInsightsEmptyQuestion:
    def test_empty_question(self, client):
        """빈 question → 422."""
        _create_done_meeting("e1", "회의")

        res = client.post("/api/insights", json={"question": ""})
        assert res.status_code == 422


# ---------------------------------------------------------------------------
# 5. question 필드 누락 → 422
# ---------------------------------------------------------------------------

class TestInsightsMissingQuestion:
    def test_missing_question(self, client):
        """question 필드 없음 → 422."""
        res = client.post("/api/insights", json={"keyword": "뭔가"})
        assert res.status_code == 422


# ---------------------------------------------------------------------------
# 6. 관련 회의 0건 → 404
# ---------------------------------------------------------------------------

class TestInsightsNoMeetings:
    def test_no_matching_meetings(self, client, mock_claude_success):
        """매칭 회의 0건 → 404."""
        # done 회의 없음
        res = client.post("/api/insights", json={
            "question": "분석해줘",
            "keyword": "존재하지않는키워드",
        })
        assert res.status_code == 404

    def test_only_pending_meetings(self, client, mock_claude_success):
        """pending 회의만 있으면 → 404."""
        _create_pending_meeting("p1", "미완료 회의")

        res = client.post("/api/insights", json={
            "question": "분석해줘",
        })
        assert res.status_code == 404


# ---------------------------------------------------------------------------
# 7. keyword 없으면 done 전체 (최근 10개 제한)
# ---------------------------------------------------------------------------

class TestInsightsNoKeyword:
    def test_no_keyword_uses_all_done(self, client, mock_claude_success):
        """keyword 없으면 done 상태 전체 회의 사용."""
        _create_done_meeting("a1", "회의1", summary="## 요약\n내용1")
        _create_done_meeting("a2", "회의2", summary="## 요약\n내용2")

        res = client.post("/api/insights", json={"question": "전체 분석"})
        assert res.status_code == 200
        assert res.json()["meeting_count"] == 2

    def test_no_keyword_limits_to_10(self, client, mock_claude_success):
        """keyword 없으면 최근 10개로 제한."""
        for i in range(12):
            _create_done_meeting(f"lim{i}", f"회의{i}", summary=f"## 요약\n내용{i}")

        res = client.post("/api/insights", json={"question": "전체 분석"})
        assert res.status_code == 200
        assert res.json()["meeting_count"] <= 10


# ---------------------------------------------------------------------------
# 8. claude CLI 실패 → 500
# ---------------------------------------------------------------------------

class TestInsightsClaudeFailure:
    def test_claude_cli_error(self, client, mock_claude_failure):
        """claude CLI 실패 → 500."""
        _create_done_meeting("f1", "회의", summary="## 요약\n내용")

        res = client.post("/api/insights", json={"question": "분석해줘"})
        assert res.status_code == 500
