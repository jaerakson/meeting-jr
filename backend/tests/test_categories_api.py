import pytest


@pytest.fixture
def client(tmp_path, monkeypatch):
    import app.database as dbmod
    monkeypatch.setattr(dbmod, "DB_PATH", tmp_path / "test.db")
    import app.main as mainmod
    monkeypatch.setattr(mainmod, "INPUT_DIR", tmp_path / "input")
    monkeypatch.setattr(mainmod, "OUTPUT_DIR", tmp_path / "output")
    monkeypatch.setattr(mainmod, "SPEAKERS_FILE", tmp_path / "speakers.json")
    (tmp_path / "input").mkdir()
    (tmp_path / "output").mkdir()
    dbmod.init_db()
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


def test_list_categories_returns_5_builtins(client):
    res = client.get("/api/categories")
    assert res.status_code == 200
    cats = res.json()
    assert len(cats) == 5
    assert cats[0]["id"] == "meeting"  # sort_order=1 이 첫번째


def test_list_categories_sorted(client):
    res = client.get("/api/categories")
    cats = res.json()
    orders = [c["sort_order"] for c in cats]
    assert orders == sorted(orders)


def test_create_custom_category(client):
    body = {
        "name": "커스텀",
        "icon": "🎯",
        "description": "테스트용",
        "prompt": "요약해줘\n{script}",
    }
    res = client.post("/api/categories", json=body)
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "커스텀"
    assert data["icon"] == "🎯"
    assert data["is_builtin"] == 0

    # 목록에도 반영되는지 확인
    cats = client.get("/api/categories").json()
    assert any(c["id"] == data["id"] for c in cats)


def test_create_category_requires_name(client):
    res = client.post("/api/categories", json={"name": "", "prompt": "{script}"})
    assert res.status_code == 422


def test_create_category_requires_script_placeholder(client):
    res = client.post("/api/categories", json={"name": "잘못된", "icon": "❌", "description": "", "prompt": "스크립트 없음"})
    assert res.status_code == 422


def test_patch_builtin_category_prompt(client):
    res = client.patch("/api/categories/meeting", json={"prompt": "짧게 요약\n{script}"})
    assert res.status_code == 200
    assert res.json()["prompt"] == "짧게 요약\n{script}"


def test_patch_category_validates_prompt_placeholder(client):
    res = client.patch("/api/categories/meeting", json={"prompt": "플레이스홀더 없음"})
    assert res.status_code == 422


def test_patch_nonexistent_category(client):
    res = client.patch("/api/categories/nonexistent", json={"name": "없음"})
    assert res.status_code == 404


def test_delete_builtin_category_rejected(client):
    res = client.delete("/api/categories/meeting")
    assert res.status_code == 422
    assert "내장" in res.json()["detail"]


def test_delete_custom_category(client):
    cat = client.post("/api/categories", json={
        "name": "삭제", "icon": "🗑️", "description": "", "prompt": "{script}"
    }).json()
    res = client.delete(f"/api/categories/{cat['id']}")
    assert res.status_code == 200
    assert res.json()["status"] == "deleted"

    # 삭제 후 목록에 없어야 함
    cats = client.get("/api/categories").json()
    assert not any(c["id"] == cat["id"] for c in cats)


def test_reset_builtin_category_prompt(client):
    # 프롬프트 변경 후 reset
    client.patch("/api/categories/lecture", json={"prompt": "임시프롬프트\n{script}"})
    res = client.post("/api/categories/lecture/reset")
    assert res.status_code == 200
    from app.categories import DEFAULT_PROMPTS
    assert res.json()["prompt"] == DEFAULT_PROMPTS["lecture"]


def test_reset_custom_category_rejected(client):
    cat = client.post("/api/categories", json={
        "name": "커스텀", "icon": "🎯", "description": "", "prompt": "{script}"
    }).json()
    res = client.post(f"/api/categories/{cat['id']}/reset")
    assert res.status_code == 422


def test_reset_nonexistent_category(client):
    res = client.post("/api/categories/nonexistent/reset")
    assert res.status_code == 404
