"""회의록 공유 링크 API 테스트 (TDD).

POST /api/jobs/{job_id}/share — 공유 토큰 생성
GET /api/shared/{token} — 공유 페이지 읽기 전용 조회
DELETE /api/jobs/{job_id}/share — 토큰 폐기
"""

import sys
import os
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
# 헬퍼: done 상태 회의 생성
# ---------------------------------------------------------------------------

def _create_done_meeting(
    job_id: str,
    title: str = "테스트 회의",
    summary: str = "## 요약\n회의 내용 요약입니다.",
    transcript: str = "[00:00] SPEAKER_00: 안녕하세요\n[00:05] SPEAKER_01: 네 안녕하세요",
    speakers: dict = None,
    duration_sec: int = 300,
):
    import app.database as db
    db.create_job(job_id, f"{job_id}.webm", title=title)
    db.update_job_result(
        job_id,
        summary=summary,
        transcript=transcript,
        speakers=speakers or {"SPEAKER_00": "김철수", "SPEAKER_01": "박영희"},
        duration_sec=duration_sec,
        status="done",
    )


def _create_pending_meeting(job_id: str, title: str = "미완료 회의"):
    import app.database as db
    db.create_job(job_id, f"{job_id}.webm", title=title)


# ---------------------------------------------------------------------------
# 1. done 상태 회의에서 공유 토큰 생성
# ---------------------------------------------------------------------------

class TestShareCreate:
    def test_share_done_meeting(self, client):
        """done 상태 회의 → 200, token과 url 반환."""
        _create_done_meeting("s1", title="주간 회의")

        res = client.post("/api/jobs/s1/share")
        assert res.status_code == 200
        data = res.json()
        assert "token" in data
        assert "url" in data
        assert len(data["token"]) > 0
        assert data["url"] == f"/shared/{data['token']}"

    # -------------------------------------------------------------------
    # 2. 미완료 회의에서 공유 시도 → 400
    # -------------------------------------------------------------------

    def test_share_pending_meeting_rejected(self, client):
        """pending 상태 회의 → 400."""
        _create_pending_meeting("s2")

        res = client.post("/api/jobs/s2/share")
        assert res.status_code == 400

    # -------------------------------------------------------------------
    # 3. 존재하지 않는 job_id → 404
    # -------------------------------------------------------------------

    def test_share_nonexistent_job(self, client):
        """존재하지 않는 job → 404."""
        res = client.post("/api/jobs/nonexistent/share")
        assert res.status_code == 404

    # -------------------------------------------------------------------
    # 4. 이미 공유된 회의 재요청 → 기존 토큰 동일 반환
    # -------------------------------------------------------------------

    def test_share_idempotent(self, client):
        """이미 share_token이 있으면 기존 토큰 반환."""
        _create_done_meeting("s3")

        res1 = client.post("/api/jobs/s3/share")
        token1 = res1.json()["token"]

        res2 = client.post("/api/jobs/s3/share")
        token2 = res2.json()["token"]

        assert token1 == token2


# ---------------------------------------------------------------------------
# 5. 유효한 토큰으로 공유 페이지 조회
# ---------------------------------------------------------------------------

class TestShareGet:
    def test_get_shared_page(self, client):
        """유효한 토큰 → 200, 읽기 전용 데이터 반환."""
        _create_done_meeting(
            "g1",
            title="공유 회의",
            summary="요약 내용",
            transcript="[00:00] SPEAKER_00: 테스트",
            speakers={"SPEAKER_00": "김철수"},
            duration_sec=600,
        )

        res = client.post("/api/jobs/g1/share")
        token = res.json()["token"]

        res = client.get(f"/api/shared/{token}")
        assert res.status_code == 200
        data = res.json()

        assert data["title"] == "공유 회의"
        assert data["summary"] == "요약 내용"
        assert data["transcript"] == "[00:00] SPEAKER_00: 테스트"
        assert data["speakers"] == {"SPEAKER_00": "김철수"}
        assert "created_at" in data
        assert data["duration_sec"] == 600

    # -------------------------------------------------------------------
    # 6. 민감 필드 미포함
    # -------------------------------------------------------------------

    def test_shared_page_excludes_sensitive_fields(self, client):
        """공유 응답에 id, share_token, action_items, memo, error_msg 미포함."""
        _create_done_meeting("g2")

        res = client.post("/api/jobs/g2/share")
        token = res.json()["token"]

        res = client.get(f"/api/shared/{token}")
        data = res.json()

        sensitive_fields = ["id", "share_token", "action_items", "memo", "error_msg"]
        for field in sensitive_fields:
            assert field not in data, f"민감 필드 '{field}'가 응답에 포함됨"

    # -------------------------------------------------------------------
    # 7. 잘못된 토큰 → 404
    # -------------------------------------------------------------------

    def test_invalid_token(self, client):
        """잘못된 토큰 → 404."""
        res = client.get("/api/shared/invalid-token-12345")
        assert res.status_code == 404


# ---------------------------------------------------------------------------
# 8~10. 토큰 폐기
# ---------------------------------------------------------------------------

class TestShareRevoke:
    def test_revoke_share(self, client):
        """토큰 폐기 → 200."""
        _create_done_meeting("r1")
        client.post("/api/jobs/r1/share")

        res = client.delete("/api/jobs/r1/share")
        assert res.status_code == 200
        assert res.json()["status"] == "revoked"

    def test_revoke_nonexistent_job(self, client):
        """존재하지 않는 job → 404."""
        res = client.delete("/api/jobs/nonexistent/share")
        assert res.status_code == 404

    def test_revoked_token_not_accessible(self, client):
        """폐기 후 기존 토큰으로 GET → 404."""
        _create_done_meeting("r2")
        res = client.post("/api/jobs/r2/share")
        token = res.json()["token"]

        # 폐기
        client.delete("/api/jobs/r2/share")

        # 기존 토큰으로 조회 → 404
        res = client.get(f"/api/shared/{token}")
        assert res.status_code == 404

    def test_reshare_after_revoke_creates_new_token(self, client):
        """폐기 후 재공유 → 새 토큰 생성."""
        _create_done_meeting("r3")

        res1 = client.post("/api/jobs/r3/share")
        old_token = res1.json()["token"]

        client.delete("/api/jobs/r3/share")

        res2 = client.post("/api/jobs/r3/share")
        new_token = res2.json()["token"]

        assert old_token != new_token
