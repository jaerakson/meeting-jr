"""회의 후속조치 API 테스트 (TDD).

GET /api/jobs/{job_id}/followup — 후속조치 조회
PATCH /api/jobs/{job_id}/followup — 사용자 확정 (user_status, confirmed)
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
# 헬퍼
# ---------------------------------------------------------------------------

def _create_done_meeting(
    job_id: str,
    title: str = "테스트 회의",
    action_items: list | None = None,
):
    """done 상태 회의 생성. action_items 선택적."""
    import app.database as db
    db.create_job(job_id, f"{job_id}.webm", title=title)
    db.update_job_result(
        job_id,
        summary="## 요약\n내용",
        transcript="[00:00] SPEAKER_00: 테스트",
        speakers={"SPEAKER_00": "화자"},
        duration_sec=300,
        status="done",
    )
    if action_items is not None:
        db.update_job_action_items(job_id, action_items)


def _create_series_via_api(client, name: str) -> str:
    """시리즈 생성 후 id 반환."""
    res = client.post("/api/series", json={"name": name})
    assert res.status_code == 200
    return res.json()["id"]


def _assign_series(client, job_id: str, series_id: str):
    """회의에 시리즈 할당."""
    res = client.patch(f"/api/jobs/{job_id}/series", json={"series_id": series_id})
    assert res.status_code == 200


def _set_followup_items(job_id: str, items: list[dict]):
    """DB에 직접 followup_items 저장 (JSON TEXT 컬럼)."""
    import sqlite3
    import app.database as db_module
    conn = sqlite3.connect(str(db_module.DB_PATH))
    conn.execute(
        "UPDATE meetings SET followup_items = ? WHERE id = ?",
        (json.dumps(items, ensure_ascii=False), job_id),
    )
    conn.commit()
    conn.close()


# ===========================================================================
# 1. 존재하지 않는 job → 404
# ===========================================================================

class TestFollowupNotFound:
    def test_followup_not_found(self, client):
        """존재하지 않는 job_id → 404."""
        res = client.get("/api/jobs/nonexistent/followup")
        assert res.status_code == 404


# ===========================================================================
# 2. 시리즈 미할당 → 빈 결과
# ===========================================================================

class TestFollowupNoSeries:
    def test_followup_no_series(self, client):
        """시리즈 미할당 회의 → source_job_id null, 빈 items."""
        _create_done_meeting("ns1", "단독 회의")

        res = client.get("/api/jobs/ns1/followup")
        assert res.status_code == 200
        data = res.json()
        assert data["source_job_id"] is None
        assert data["items"] == []


# ===========================================================================
# 3. 시리즈 첫 회의 → 빈 items
# ===========================================================================

class TestFollowupFirstMeeting:
    def test_followup_no_previous_meeting(self, client):
        """시리즈의 첫 번째 회의 → 직전 회의 없으므로 빈 items."""
        series_id = _create_series_via_api(client, "첫 회의 시리즈")
        _create_done_meeting("f1", "시리즈 첫 회의")
        _assign_series(client, "f1", series_id)

        res = client.get("/api/jobs/f1/followup")
        assert res.status_code == 200
        data = res.json()
        assert data["items"] == []
        assert data["source_job_id"] is None


# ===========================================================================
# 4. followup_items가 있는 회의 → 정상 반환
# ===========================================================================

class TestFollowupWithData:
    def test_followup_with_data(self, client):
        """followup_items 저장된 회의 → 정상 반환."""
        series_id = _create_series_via_api(client, "후속조치 시리즈")

        # 직전 회의: 액션 아이템 포함
        _create_done_meeting("prev1", "1차 회의", action_items=[
            {"text": "서버 마이그레이션", "assignee": "김팀장", "done": False},
            {"text": "디자인 리뷰", "assignee": "박디자이너", "done": True},
        ])
        _assign_series(client, "prev1", series_id)

        # 현재 회의: followup_items 포함
        _create_done_meeting("cur1", "2차 회의")
        _assign_series(client, "cur1", series_id)

        followup_items = [
            {
                "text": "서버 마이그레이션",
                "assignee": "김팀장",
                "ai_status": "completed",
                "ai_evidence": "회의록에서 마이그레이션 완료 보고 확인",
                "user_status": None,
                "confirmed": False,
            },
            {
                "text": "디자인 리뷰",
                "assignee": "박디자이너",
                "ai_status": "in_progress",
                "ai_evidence": "진행 중이라고 언급됨",
                "user_status": None,
                "confirmed": False,
            },
        ]
        _set_followup_items("cur1", followup_items)

        res = client.get("/api/jobs/cur1/followup")
        assert res.status_code == 200
        data = res.json()

        assert data["source_job_id"] == "prev1"
        assert data["source_job_title"] == "1차 회의"
        assert len(data["items"]) == 2

        item0 = data["items"][0]
        assert item0["text"] == "서버 마이그레이션"
        assert item0["assignee"] == "김팀장"
        assert item0["ai_status"] == "completed"
        assert "ai_evidence" in item0
        assert item0["confirmed"] is False


# ===========================================================================
# 5. 사용자 확정 (PATCH)
# ===========================================================================

class TestFollowupPatch:
    def test_followup_patch_confirm(self, client):
        """user_status 확정 + confirmed=true 저장."""
        series_id = _create_series_via_api(client, "확정 시리즈")

        _create_done_meeting("pp1", "직전 회의", action_items=[
            {"text": "작업1", "assignee": "A", "done": False},
        ])
        _assign_series(client, "pp1", series_id)

        _create_done_meeting("pc1", "현재 회의")
        _assign_series(client, "pc1", series_id)

        _set_followup_items("pc1", [{
            "text": "작업1",
            "assignee": "A",
            "ai_status": "completed",
            "ai_evidence": "완료 보고됨",
            "user_status": None,
            "confirmed": False,
        }])

        # 사용자 확정
        res = client.patch("/api/jobs/pc1/followup", json={
            "items": [{"index": 0, "user_status": "completed", "confirmed": True}],
        })
        assert res.status_code == 200

        # 재조회로 영속성 확인
        res = client.get("/api/jobs/pc1/followup")
        assert res.status_code == 200
        item = res.json()["items"][0]
        assert item["user_status"] == "completed"
        assert item["confirmed"] is True

    def test_followup_patch_partial(self, client):
        """여러 항목 중 일부만 확정 (index 지정)."""
        series_id = _create_series_via_api(client, "부분 확정 시리즈")

        _create_done_meeting("pp2", "직전", action_items=[
            {"text": "작업A", "assignee": "X", "done": False},
            {"text": "작업B", "assignee": "Y", "done": False},
        ])
        _assign_series(client, "pp2", series_id)

        _create_done_meeting("pc2", "현재")
        _assign_series(client, "pc2", series_id)

        _set_followup_items("pc2", [
            {
                "text": "작업A", "assignee": "X",
                "ai_status": "completed", "ai_evidence": "...",
                "user_status": None, "confirmed": False,
            },
            {
                "text": "작업B", "assignee": "Y",
                "ai_status": "not_mentioned", "ai_evidence": "",
                "user_status": None, "confirmed": False,
            },
        ])

        # index=1만 확정
        res = client.patch("/api/jobs/pc2/followup", json={
            "items": [{"index": 1, "user_status": "in_progress", "confirmed": True}],
        })
        assert res.status_code == 200

        # 재조회
        res = client.get("/api/jobs/pc2/followup")
        items = res.json()["items"]

        # index 0은 미확정
        assert items[0]["confirmed"] is False
        assert items[0]["user_status"] is None

        # index 1은 확정
        assert items[1]["confirmed"] is True
        assert items[1]["user_status"] == "in_progress"

    def test_followup_patch_not_found(self, client):
        """존재하지 않는 job → 404."""
        res = client.patch("/api/jobs/nonexistent/followup", json={
            "items": [{"index": 0, "user_status": "completed", "confirmed": True}],
        })
        assert res.status_code == 404


# ===========================================================================
# 6. 기존 회의 마이그레이션 안전성
# ===========================================================================

class TestFollowupMigrationSafety:
    def test_followup_existing_meetings_no_series(self, client):
        """기존 회의(series_id NULL, followup_items NULL) → 정상 동작, 빈 결과."""
        _create_done_meeting("legacy1", "레거시 회의")

        res = client.get("/api/jobs/legacy1/followup")
        assert res.status_code == 200
        data = res.json()
        assert data["source_job_id"] is None
        assert data["items"] == []
