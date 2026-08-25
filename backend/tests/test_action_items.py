"""액션 아이템 파싱 및 API 테스트."""

import re
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# 파싱 로직 (main.py run_summary 내부와 동일)
# ---------------------------------------------------------------------------

def parse_action_items(summary: str) -> list[dict]:
    action_items = []
    for line in summary.splitlines():
        m = re.match(r'^-\s*\[[ xX]\]\s*(?:@(\S+)\s*-?\s*)?(.+)$', line.strip())
        if m:
            done = '[x]' in line.lower()
            assignee = m.group(1) or ''
            text = m.group(2).strip()
            action_items.append({"text": text, "assignee": assignee, "done": done})
    return action_items


# ---------------------------------------------------------------------------
# 파싱 단위 테스트
# ---------------------------------------------------------------------------

class TestParseActionItems:
    def test_unchecked_no_assignee(self):
        result = parse_action_items("- [ ] 보고서 작성")
        assert len(result) == 1
        assert result[0] == {"text": "보고서 작성", "assignee": "", "done": False}

    def test_checked(self):
        result = parse_action_items("- [x] 코드 리뷰 완료")
        assert len(result) == 1
        assert result[0]["done"] is True
        assert result[0]["text"] == "코드 리뷰 완료"

    def test_checked_uppercase_X(self):
        result = parse_action_items("- [X] 대문자 체크")
        assert len(result) == 1
        assert result[0]["done"] is True

    def test_with_assignee(self):
        result = parse_action_items("- [ ] @김철수 - 디자인 시안 검토")
        assert len(result) == 1
        assert result[0]["assignee"] == "김철수"
        assert result[0]["text"] == "디자인 시안 검토"
        assert result[0]["done"] is False

    def test_with_assignee_no_dash(self):
        result = parse_action_items("- [ ] @박영희 일정 조율")
        assert len(result) == 1
        assert result[0]["assignee"] == "박영희"
        assert result[0]["text"] == "일정 조율"

    def test_multiple_items(self):
        text = """# 요약
회의 내용 요약입니다.

## 액션 아이템
- [ ] @김철수 - 보고서 작성
- [x] @박영희 - 자료 정리
- [ ] 회의실 예약
"""
        result = parse_action_items(text)
        assert len(result) == 3
        assert result[0]["assignee"] == "김철수"
        assert result[0]["done"] is False
        assert result[1]["assignee"] == "박영희"
        assert result[1]["done"] is True
        assert result[2]["assignee"] == ""
        assert result[2]["text"] == "회의실 예약"

    def test_no_action_items(self):
        result = parse_action_items("일반 텍스트\n다른 줄")
        assert result == []

    def test_regular_list_not_matched(self):
        result = parse_action_items("- 일반 목록 항목")
        assert result == []


# ---------------------------------------------------------------------------
# PATCH /api/jobs/{job_id}/action-items API 테스트
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    """TestClient with mocked database."""
    with patch("app.main.init_db"), \
         patch("app.main.start_worker", return_value=MagicMock()):
        from app.main import app
        with TestClient(app) as c:
            yield c


class TestActionItemsAPI:
    def test_patch_action_items_success(self, client):
        mock_job = {
            "id": "test-123",
            "title": "테스트",
            "status": "done",
            "action_items": [{"text": "할 일", "assignee": "", "done": True}],
            "speakers": {},
        }
        with patch("app.main.get_job", return_value=mock_job), \
             patch("app.main.update_job_action_items") as mock_update:
            resp = client.patch(
                "/api/jobs/test-123/action-items",
                json={"action_items": [{"text": "할 일", "assignee": "", "done": True}]},
            )
            assert resp.status_code == 200
            mock_update.assert_called_once()

    def test_patch_action_items_not_found(self, client):
        with patch("app.main.get_job", return_value=None):
            resp = client.patch(
                "/api/jobs/nonexistent/action-items",
                json={"action_items": []},
            )
            assert resp.status_code == 404

    def test_patch_action_items_invalid_body(self, client):
        mock_job = {"id": "test-123", "status": "done", "speakers": {}, "action_items": []}
        with patch("app.main.get_job", return_value=mock_job):
            resp = client.patch(
                "/api/jobs/test-123/action-items",
                json={"wrong_key": "value"},
            )
            assert resp.status_code == 422
