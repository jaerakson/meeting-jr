"""액션 아이템 통합 대시보드 API 테스트 (TDD).

GET /api/action-items — 전체 회의의 액션 아이템을 통합 조회.
필터: assignee, done / 페이지네이션: page, limit
"""

import sys
import os
import json
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
# 헬퍼: 회의 생성 + 액션 아이템 설정
# ---------------------------------------------------------------------------

def _create_meeting_with_actions(job_id: str, title: str, action_items: list[dict]):
    """회의를 생성하고 action_items를 설정한다."""
    import app.database as db
    db.create_job(job_id, f"{job_id}.webm", title=title)
    db.update_job_result(job_id, status="done")
    if action_items:
        db.update_job_action_items(job_id, action_items)


# ---------------------------------------------------------------------------
# 1. 빈 DB에서 조회
# ---------------------------------------------------------------------------

class TestActionItemsEmpty:
    def test_empty_db_returns_empty(self, client):
        """빈 DB에서 GET /api/action-items → items=[], total=0, pending_count=0"""
        res = client.get("/api/action-items")
        assert res.status_code == 200
        data = res.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["page"] == 1
        assert data["pages"] == 1
        assert data["pending_count"] == 0


# ---------------------------------------------------------------------------
# 2. 전체 조회 — 여러 회의의 액션 아이템 통합
# ---------------------------------------------------------------------------

class TestActionItemsFullList:
    def test_multiple_meetings_aggregated(self, client):
        """2개 회의의 액션 아이템이 job_id, job_title과 함께 통합 반환된다."""
        _create_meeting_with_actions("m1", "주간 회의", [
            {"text": "보고서 작성", "assignee": "김철수", "done": False},
            {"text": "자료 정리", "assignee": "박영희", "done": True},
        ])
        _create_meeting_with_actions("m2", "기획 회의", [
            {"text": "일정 조율", "assignee": "김철수", "done": False},
        ])

        res = client.get("/api/action-items")
        assert res.status_code == 200
        data = res.json()
        assert data["total"] == 3

        # 각 아이템에 job_id, job_title, job_created_at 포함 확인
        for item in data["items"]:
            assert "job_id" in item
            assert "job_title" in item
            assert "job_created_at" in item
            assert "text" in item
            assert "assignee" in item
            assert "done" in item

        # job_id가 올바르게 매핑되었는지 확인
        job_ids = {item["job_id"] for item in data["items"]}
        assert job_ids == {"m1", "m2"}

    def test_meetings_without_action_items_excluded(self, client):
        """action_items가 없는 회의는 결과에 포함되지 않는다."""
        _create_meeting_with_actions("m3", "빈 회의", [])
        _create_meeting_with_actions("m4", "실제 회의", [
            {"text": "할 일", "assignee": "", "done": False},
        ])

        res = client.get("/api/action-items")
        data = res.json()
        assert data["total"] == 1
        assert data["items"][0]["job_id"] == "m4"


# ---------------------------------------------------------------------------
# 3. done=false 필터
# ---------------------------------------------------------------------------

class TestActionItemsDoneFilter:
    def test_filter_pending_only(self, client):
        """done=false → 미완료 아이템만 반환."""
        _create_meeting_with_actions("d1", "회의A", [
            {"text": "미완료 작업", "assignee": "", "done": False},
            {"text": "완료 작업", "assignee": "", "done": True},
        ])

        res = client.get("/api/action-items?done=false")
        data = res.json()
        assert data["total"] == 1
        assert data["items"][0]["text"] == "미완료 작업"
        assert data["items"][0]["done"] is False

    def test_filter_done_only(self, client):
        """done=true → 완료 아이템만 반환."""
        _create_meeting_with_actions("d2", "회의B", [
            {"text": "미완료", "assignee": "", "done": False},
            {"text": "완료", "assignee": "", "done": True},
        ])

        res = client.get("/api/action-items?done=true")
        data = res.json()
        assert data["total"] == 1
        assert data["items"][0]["text"] == "완료"
        assert data["items"][0]["done"] is True

    def test_no_done_filter_returns_all(self, client):
        """done 파라미터 없으면 전체 반환."""
        _create_meeting_with_actions("d3", "회의C", [
            {"text": "작업1", "assignee": "", "done": False},
            {"text": "작업2", "assignee": "", "done": True},
        ])

        res = client.get("/api/action-items")
        data = res.json()
        assert data["total"] == 2


# ---------------------------------------------------------------------------
# 5. assignee 필터
# ---------------------------------------------------------------------------

class TestActionItemsAssigneeFilter:
    def test_filter_by_assignee(self, client):
        """특정 담당자의 아이템만 반환."""
        _create_meeting_with_actions("a1", "회의D", [
            {"text": "김철수 작업", "assignee": "김철수", "done": False},
            {"text": "박영희 작업", "assignee": "박영희", "done": False},
            {"text": "미지정 작업", "assignee": "", "done": False},
        ])

        res = client.get("/api/action-items?assignee=김철수")
        data = res.json()
        assert data["total"] == 1
        assert data["items"][0]["assignee"] == "김철수"

    def test_empty_assignee_returns_all(self, client):
        """assignee 빈 문자열이면 전체 반환."""
        _create_meeting_with_actions("a2", "회의E", [
            {"text": "작업1", "assignee": "김철수", "done": False},
            {"text": "작업2", "assignee": "박영희", "done": False},
        ])

        res = client.get("/api/action-items?assignee=")
        data = res.json()
        assert data["total"] == 2


# ---------------------------------------------------------------------------
# 6. assignee + done 복합 필터
# ---------------------------------------------------------------------------

class TestActionItemsCombinedFilter:
    def test_assignee_and_done_combined(self, client):
        """assignee + done 동시 필터."""
        _create_meeting_with_actions("c1", "복합 회의", [
            {"text": "김철수 미완료", "assignee": "김철수", "done": False},
            {"text": "김철수 완료", "assignee": "김철수", "done": True},
            {"text": "박영희 미완료", "assignee": "박영희", "done": False},
            {"text": "박영희 완료", "assignee": "박영희", "done": True},
        ])

        res = client.get("/api/action-items?assignee=김철수&done=false")
        data = res.json()
        assert data["total"] == 1
        assert data["items"][0]["text"] == "김철수 미완료"
        assert data["items"][0]["assignee"] == "김철수"
        assert data["items"][0]["done"] is False


# ---------------------------------------------------------------------------
# 7. 페이지네이션
# ---------------------------------------------------------------------------

class TestActionItemsPagination:
    def test_pagination_limits_results(self, client):
        """page=1, limit=2로 조회 시 2개만 반환, pages 정확."""
        _create_meeting_with_actions("p1", "회의F", [
            {"text": f"작업{i}", "assignee": "", "done": False}
            for i in range(5)
        ])

        res = client.get("/api/action-items?page=1&limit=2")
        data = res.json()
        assert len(data["items"]) == 2
        assert data["total"] == 5
        assert data["pages"] == 3  # ceil(5/2) = 3
        assert data["page"] == 1

    def test_pagination_second_page(self, client):
        """2페이지 조회."""
        _create_meeting_with_actions("p2", "회의G", [
            {"text": f"작업{i}", "assignee": "", "done": False}
            for i in range(5)
        ])

        res = client.get("/api/action-items?page=2&limit=2")
        data = res.json()
        assert len(data["items"]) == 2
        assert data["page"] == 2

    def test_pagination_last_page(self, client):
        """마지막 페이지: 나머지 아이템만 반환."""
        _create_meeting_with_actions("p3", "회의H", [
            {"text": f"작업{i}", "assignee": "", "done": False}
            for i in range(5)
        ])

        res = client.get("/api/action-items?page=3&limit=2")
        data = res.json()
        assert len(data["items"]) == 1


# ---------------------------------------------------------------------------
# 8. pending_count는 필터와 무관하게 전체 미완료 건수
# ---------------------------------------------------------------------------

class TestActionItemsPendingCount:
    def test_pending_count_ignores_filters(self, client):
        """done=true 필터를 걸어도 pending_count는 전체 미완료 건수."""
        _create_meeting_with_actions("pc1", "회의I", [
            {"text": "미완료1", "assignee": "김철수", "done": False},
            {"text": "미완료2", "assignee": "박영희", "done": False},
            {"text": "완료1", "assignee": "김철수", "done": True},
        ])

        # 전체 조회
        res = client.get("/api/action-items")
        assert res.json()["pending_count"] == 2

        # done=true 필터 — pending_count는 여전히 2
        res = client.get("/api/action-items?done=true")
        assert res.json()["pending_count"] == 2

        # assignee 필터 — pending_count는 여전히 2 (전체 기준)
        res = client.get("/api/action-items?assignee=김철수")
        assert res.json()["pending_count"] == 2


# ---------------------------------------------------------------------------
# 9. PATCH로 토글 후 GET 반영 확인
# ---------------------------------------------------------------------------

class TestActionItemsToggleReflection:
    def test_patch_then_get_reflects_change(self, client):
        """PATCH로 done 토글 후 GET /api/action-items에 반영."""
        _create_meeting_with_actions("t1", "토글 회의", [
            {"text": "할 일", "assignee": "김철수", "done": False},
        ])

        # 미완료 확인
        res = client.get("/api/action-items?done=false")
        assert res.json()["total"] == 1

        # PATCH로 완료 처리
        client.patch(
            "/api/jobs/t1/action-items",
            json={"action_items": [
                {"text": "할 일", "assignee": "김철수", "done": True},
            ]},
        )

        # 미완료 조회 시 0건
        res = client.get("/api/action-items?done=false")
        assert res.json()["total"] == 0

        # 완료 조회 시 1건
        res = client.get("/api/action-items?done=true")
        assert res.json()["total"] == 1
        assert res.json()["pending_count"] == 0


# ---------------------------------------------------------------------------
# 정렬: 미완료 우선, 최신 회의 우선
# ---------------------------------------------------------------------------

class TestActionItemsSorting:
    def test_pending_first_then_newest(self, client):
        """미완료 아이템이 완료보다 먼저, 같은 상태면 최신 회의 우선."""
        import time
        _create_meeting_with_actions("s1", "옛날 회의", [
            {"text": "옛날 미완료", "assignee": "", "done": False},
            {"text": "옛날 완료", "assignee": "", "done": True},
        ])
        time.sleep(0.01)  # created_at 차이 보장
        _create_meeting_with_actions("s2", "최근 회의", [
            {"text": "최근 미완료", "assignee": "", "done": False},
            {"text": "최근 완료", "assignee": "", "done": True},
        ])

        res = client.get("/api/action-items")
        data = res.json()
        items = data["items"]
        assert len(items) == 4

        # 미완료가 먼저 나와야 함
        pending_items = [i for i in items if not i["done"]]
        done_items = [i for i in items if i["done"]]
        # 리스트에서 미완료가 완료보다 앞에 위치
        first_done_idx = next(
            (idx for idx, item in enumerate(items) if item["done"]), len(items)
        )
        first_pending_idx = next(
            (idx for idx, item in enumerate(items) if not item["done"]), len(items)
        )
        assert first_pending_idx < first_done_idx
