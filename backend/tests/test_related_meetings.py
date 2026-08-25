"""연관 회의 검색 API 테스트."""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    with patch("app.main.init_db"), \
         patch("app.main.start_worker", return_value=MagicMock()):
        from app.main import app
        with TestClient(app) as c:
            yield c


class TestExtractKeywords:
    def test_basic(self):
        from app.main import _extract_keywords
        result = _extract_keywords("프로젝트 일정 프로젝트 설계 리뷰 설계")
        assert "프로젝트" in result
        assert "설계" in result

    def test_stopwords_removed(self):
        from app.main import _extract_keywords
        result = _extract_keywords("회의 합니다 했습니다 프로젝트")
        assert "회의" not in result
        assert "합니다" not in result
        assert "프로젝트" in result

    def test_empty_text(self):
        from app.main import _extract_keywords
        assert _extract_keywords("") == []

    def test_top_n_limit(self):
        from app.main import _extract_keywords
        text = " ".join(f"단어{i}" for i in range(20))
        result = _extract_keywords(text, top_n=5)
        assert len(result) <= 5


class TestRelatedMeetingsAPI:
    def test_not_found(self, client):
        with patch("app.main.get_job", return_value=None):
            resp = client.get("/api/jobs/nonexistent/related")
            assert resp.status_code == 404

    def test_no_keywords(self, client):
        with patch("app.main.get_job", return_value={"id": "j1", "summary": "", "title": "", "speakers": {}}):
            resp = client.get("/api/jobs/j1/related")
            assert resp.status_code == 200
            assert resp.json()["items"] == []

    def test_returns_related(self, client):
        main_job = {"id": "j1", "summary": "프로젝트 설계 리뷰 진행", "title": "설계 회의", "speakers": {}}
        other_jobs = [
            {"id": "j1", "title": "설계 회의", "summary": "프로젝트 설계 리뷰 진행", "speakers": {}, "created_at": "2026-01-01"},
            {"id": "j2", "title": "설계 검토", "summary": "프로젝트 설계 관련", "speakers": {}, "created_at": "2026-01-02"},
            {"id": "j3", "title": "점심 메뉴", "summary": "짜장면 짬뽕", "speakers": {}, "created_at": "2026-01-03"},
        ]
        with patch("app.main.get_job", return_value=main_job), \
             patch("app.main.get_all_jobs", return_value=other_jobs):
            resp = client.get("/api/jobs/j1/related")
            data = resp.json()
            assert len(data["items"]) == 1
            assert data["items"][0]["id"] == "j2"
            assert data["items"][0]["score"] > 0

    def test_max_5_results(self, client):
        main_job = {"id": "j0", "summary": "키워드 반복 테스트", "title": "테스트", "speakers": {}}
        other_jobs = [
            {"id": f"j{i}", "title": "테스트", "summary": "키워드 반복", "speakers": {}, "created_at": f"2026-01-{i:02d}"}
            for i in range(1, 10)
        ]
        with patch("app.main.get_job", return_value=main_job), \
             patch("app.main.get_all_jobs", return_value=other_jobs):
            resp = client.get("/api/jobs/j0/related")
            assert len(resp.json()["items"]) <= 5
