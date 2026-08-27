"""회의 시리즈 CRUD API 테스트 (TDD).

POST /api/series — 시리즈 생성
GET /api/series — 시리즈 목록 (meeting_count 포함)
GET /api/series/{id} — 시리즈 상세 + 연결 회의 목록
PATCH /api/series/{id} — 시리즈 수정
DELETE /api/series/{id} — 시리즈 삭제 (연결 회의 series_id → NULL)
PATCH /api/jobs/{job_id}/series — 회의에 시리즈 할당/해제
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

def _create_done_meeting(job_id: str, title: str = "테스트 회의"):
    """done 상태 회의 생성."""
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


def _create_series(client, name: str, description: str = "") -> dict:
    """시리즈를 API로 생성하고 응답 반환."""
    res = client.post("/api/series", json={"name": name, "description": description})
    assert res.status_code == 200
    return res.json()


# ===========================================================================
# 1. 시리즈 생성
# ===========================================================================

class TestSeriesCreate:
    def test_create_series(self, client):
        """시리즈 생성 성공 → id, name, description, created_at, updated_at 반환."""
        res = client.post("/api/series", json={
            "name": "주간 개발팀 회의",
            "description": "매주 월요일 오전",
        })
        assert res.status_code == 200
        data = res.json()
        assert "id" in data
        assert data["name"] == "주간 개발팀 회의"
        assert data["description"] == "매주 월요일 오전"
        assert "created_at" in data
        assert "updated_at" in data

    def test_create_series_missing_name(self, client):
        """name 없으면 422."""
        res = client.post("/api/series", json={"description": "설명만"})
        assert res.status_code == 422


# ===========================================================================
# 2. 시리즈 목록
# ===========================================================================

class TestSeriesList:
    def test_list_series_empty(self, client):
        """시리즈 없으면 빈 items."""
        res = client.get("/api/series")
        assert res.status_code == 200
        data = res.json()
        assert "items" in data
        assert data["items"] == []

    def test_list_series_with_count(self, client):
        """시리즈에 회의 연결 → meeting_count 반영."""
        # 시리즈 생성
        series = _create_series(client, "주간회의")
        series_id = series["id"]

        # 회의 3개 생성 후 시리즈 할당
        for i in range(3):
            _create_done_meeting(f"s{i}", f"회의 {i}")
            res = client.patch(
                f"/api/jobs/s{i}/series",
                json={"series_id": series_id},
            )
            assert res.status_code == 200

        # 목록 조회
        res = client.get("/api/series")
        assert res.status_code == 200
        items = res.json()["items"]
        assert len(items) == 1
        assert items[0]["name"] == "주간회의"
        assert items[0]["meeting_count"] == 3


# ===========================================================================
# 3. 시리즈 상세
# ===========================================================================

class TestSeriesDetail:
    def test_get_series_detail(self, client):
        """시리즈 상세 → 연결 회의 목록 포함."""
        series = _create_series(client, "스프린트 회고", "격주 금요일")
        series_id = series["id"]

        # 회의 2개 연결
        _create_done_meeting("d1", "스프린트 1 회고")
        _create_done_meeting("d2", "스프린트 2 회고")
        client.patch(f"/api/jobs/d1/series", json={"series_id": series_id})
        client.patch(f"/api/jobs/d2/series", json={"series_id": series_id})

        res = client.get(f"/api/series/{series_id}")
        assert res.status_code == 200
        data = res.json()

        assert data["id"] == series_id
        assert data["name"] == "스프린트 회고"
        assert "meetings" in data
        assert len(data["meetings"]) == 2
        for m in data["meetings"]:
            assert "id" in m
            assert "title" in m
            assert "created_at" in m
            assert "status" in m

    def test_get_series_not_found(self, client):
        """존재하지 않는 시리즈 → 404."""
        res = client.get("/api/series/nonexistent-id")
        assert res.status_code == 404


# ===========================================================================
# 4. 시리즈 수정
# ===========================================================================

class TestSeriesUpdate:
    def test_update_series(self, client):
        """name/description 변경."""
        series = _create_series(client, "원래 이름", "원래 설명")
        series_id = series["id"]

        res = client.patch(f"/api/series/{series_id}", json={
            "name": "변경된 이름",
            "description": "변경된 설명",
        })
        assert res.status_code == 200
        data = res.json()
        assert data["name"] == "변경된 이름"
        assert data["description"] == "변경된 설명"

        # 재조회로 영속성 확인
        res = client.get(f"/api/series/{series_id}")
        assert res.json()["name"] == "변경된 이름"


# ===========================================================================
# 5. 시리즈 삭제
# ===========================================================================

class TestSeriesDelete:
    def test_delete_series(self, client):
        """삭제 후 연결 회의의 series_id NULL 확인."""
        series = _create_series(client, "삭제 대상")
        series_id = series["id"]

        _create_done_meeting("del1", "연결 회의")
        client.patch(f"/api/jobs/del1/series", json={"series_id": series_id})

        # 삭제
        res = client.delete(f"/api/series/{series_id}")
        assert res.status_code == 200

        # 시리즈 조회 → 404
        res = client.get(f"/api/series/{series_id}")
        assert res.status_code == 404

        # 연결 회의의 series_id → NULL
        job_res = client.get("/api/jobs/del1")
        assert job_res.status_code == 200
        assert job_res.json().get("series_id") is None


# ===========================================================================
# 6. 회의에 시리즈 할당/해제
# ===========================================================================

class TestSeriesAssign:
    def test_assign_series_to_job(self, client):
        """회의에 시리즈 할당."""
        series = _create_series(client, "할당 테스트")
        _create_done_meeting("a1", "할당할 회의")

        res = client.patch(f"/api/jobs/a1/series", json={
            "series_id": series["id"],
        })
        assert res.status_code == 200

        # job 조회 시 series_id 확인
        job_res = client.get("/api/jobs/a1")
        assert job_res.json().get("series_id") == series["id"]

    def test_unassign_series(self, client):
        """series_id를 null로 → 해제."""
        series = _create_series(client, "해제 테스트")
        _create_done_meeting("u1", "해제할 회의")
        client.patch(f"/api/jobs/u1/series", json={"series_id": series["id"]})

        # 해제
        res = client.patch(f"/api/jobs/u1/series", json={"series_id": None})
        assert res.status_code == 200

        # job 조회 시 series_id NULL
        job_res = client.get("/api/jobs/u1")
        assert job_res.json().get("series_id") is None

    def test_assign_series_nonexistent_job(self, client):
        """존재하지 않는 job → 404."""
        series = _create_series(client, "없는 job 테스트")
        res = client.patch(f"/api/jobs/nonexistent/series", json={
            "series_id": series["id"],
        })
        assert res.status_code == 404
