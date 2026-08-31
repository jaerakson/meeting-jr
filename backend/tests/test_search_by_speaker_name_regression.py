"""화자 이름으로 검색이 걸려야 한다 — B4(라벨 그대로 저장) 수정의 검색 회귀
(PR C 2라운드, director 지시 T8).

## 배경
`database.py:444`의 `search_jobs`는 `transcript LIKE ?`로 스크립트 본문을 검색한다.
지금까지는 rename-speakers/apply-match가 `transcript` 컬럼에 실명을 구워 저장했기
때문에 화자 이름 검색이 우연히 걸렸다. B4가 "저장되는 transcript는 항상 라벨
그대로"로 고치면(director 확정 계약), `transcript` 컬럼에 더 이상 실명이 없으므로
**화자 이름으로 검색해도 그 회의가 안 걸린다** — 이 PR이 회의 데이터 모델을 바꾸며
만드는 새로운 회귀다.

이 테스트는 목표 계약(저장된 transcript=라벨, speakers=이름 map)을 직접 DB에
구성해 검증한다 — rename-speakers의 B4 수정 완료 여부와 무관하게 "그 상태에서
검색이 되는가"만 본다.

## 이 파일이 도달 조건
TDD 1단계 — 구현 전(search_jobs가 speakers 컬럼도 함께 검색하도록 고쳐지기 전).
빨간불이 정상이다.
"""

import pytest
from fastapi.testclient import TestClient


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


def _create_label_only_meeting(job_id, title="검색 회귀 회의"):
    """B4 수정 후의 목표 상태를 직접 구성한다: transcript는 라벨 그대로,
    speakers가 실명을 나른다. 제목·요약에는 화자 이름을 넣지 않는다 — title/summary
    LIKE로 우연히 걸리면 이 테스트의 판별력이 없어진다."""
    import app.database as db
    db.create_job(job_id, f"{job_id}.webm", title=title)
    db.update_job_result(
        job_id,
        summary="## 요약\n프로젝트 진행 상황을 공유했다.",
        transcript="[00:00] SPEAKER_00: 마이그레이션 진행 중입니다\n[00:05] SPEAKER_01: 네 알겠습니다",
        speakers={"SPEAKER_00": "김팀장", "SPEAKER_01": "이대리"},
        duration_sec=60,
        status="done",
    )


def test_search_by_speaker_display_name_finds_the_meeting(client):
    """화자 이름('김팀장')으로 검색하면 그 회의가 결과에 나와야 한다. transcript
    컬럼이 라벨 그대로라 title/summary/transcript LIKE만으로는 안 걸린다 —
    speakers 컬럼(또는 렌더된 표시 이름)까지 검색 대상에 포함해야 한다."""
    _create_label_only_meeting("search-by-name-1")

    res = client.get("/api/meetings", params={"q": "김팀장"})
    assert res.status_code == 200
    data = res.json()
    ids = [item["id"] for item in data["items"]]
    assert "search-by-name-1" in ids, (
        f"화자 이름으로 검색했는데 회의가 안 걸린다(현재 transcript LIKE만 검색해서 "
        f"라벨 그대로인 본문에는 실명이 없다). 실제 결과: {ids}"
    )


def test_search_snippet_does_not_expose_raw_speaker_label(client):
    """검색 결과 스니펫에 SPEAKER_00 같은 raw 라벨이 노출되면 안 된다 —
    스니펫도 사용자에게 보이는 화면(소비 지점)이다."""
    _create_label_only_meeting("search-by-name-2")

    res = client.get("/api/meetings", params={"q": "김팀장"})
    assert res.status_code == 200
    data = res.json()
    item = next((i for i in data["items"] if i["id"] == "search-by-name-2"), None)
    assert item is not None, f"검색 결과에 회의가 있어야 한다. 실제: {data['items']}"

    snippet = item.get("snippet", "")
    assert "SPEAKER_00" not in snippet and "SPEAKER_01" not in snippet, (
        f"검색 스니펫에 raw 라벨이 노출되면 안 된다. 실제 스니펫: {snippet!r}"
    )
