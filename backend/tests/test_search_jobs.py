import sys
import os
import tempfile
import pytest

# backend/ 를 sys.path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# 테스트용 임시 DB 경로를 환경변수로 주입
@pytest.fixture(autouse=True)
def tmp_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    import app.database as db_module
    monkeypatch.setattr(db_module, "DB_PATH", db_path)
    db_module.init_db()
    yield db_path

from app.database import create_job, update_job_result, search_jobs


def _make_job(job_id: str, title: str, summary: str = ""):
    create_job(job_id, f"{job_id}.webm", title=title)
    if summary:
        update_job_result(job_id, summary=summary)


def test_search_jobs_returns_all_when_no_query():
    _make_job("a1", "팀 주간회의")
    _make_job("a2", "기획 킥오프")
    result = search_jobs(q="", page=1, limit=12)
    assert result["total"] == 2
    assert result["pages"] == 1
    assert len(result["items"]) == 2


def test_search_jobs_filters_by_title():
    _make_job("b1", "팀 주간회의")
    _make_job("b2", "기획 킥오프")
    result = search_jobs(q="기획", page=1, limit=12)
    assert result["total"] == 1
    assert result["items"][0]["title"] == "기획 킥오프"


def test_search_jobs_filters_by_summary():
    _make_job("c1", "회의A", summary="액션 아이템 검토 필요")
    _make_job("c2", "회의B", summary="별다른 내용 없음")
    result = search_jobs(q="액션", page=1, limit=12)
    assert result["total"] == 1
    assert result["items"][0]["id"] == "c1"


def test_search_jobs_pagination():
    for i in range(15):
        _make_job(f"d{i}", f"회의 {i}")
    result = search_jobs(q="", page=1, limit=12)
    assert result["total"] == 15
    assert result["pages"] == 2
    assert len(result["items"]) == 12

    result2 = search_jobs(q="", page=2, limit=12)
    assert len(result2["items"]) == 3


def test_search_jobs_empty_result():
    _make_job("e1", "팀 회의")
    result = search_jobs(q="존재하지않는검색어", page=1, limit=12)
    assert result["total"] == 0
    assert result["pages"] == 1
    assert result["items"] == []
