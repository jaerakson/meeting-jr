import pytest
import uuid


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    import app.database as dbmod
    monkeypatch.setattr(dbmod, "DB_PATH", tmp_path / "test.db")
    dbmod.init_db()
    yield tmp_path / "test.db"


def test_default_prompts_exist():
    from app.categories import DEFAULT_PROMPTS, BUILTIN_CATEGORIES
    assert set(DEFAULT_PROMPTS.keys()) == {"meeting", "lecture", "sermon", "interview", "brainstorm"}
    for prompt in DEFAULT_PROMPTS.values():
        assert "{script}" in prompt
        assert len(prompt) > 200


def test_builtin_categories_seeded():
    from app.database import get_categories
    cats = get_categories()
    assert len(cats) == 5
    ids = {c["id"] for c in cats}
    assert ids == {"meeting", "lecture", "sermon", "interview", "brainstorm"}


def test_categories_sorted_by_sort_order():
    from app.database import get_categories
    cats = get_categories()
    orders = [c["sort_order"] for c in cats]
    assert orders == sorted(orders)


def test_get_category_returns_none_for_unknown():
    from app.database import get_category
    assert get_category("nonexistent") is None


def test_get_category_returns_dict():
    from app.database import get_category
    cat = get_category("meeting")
    assert cat is not None
    assert cat["id"] == "meeting"
    assert cat["is_builtin"] == 1
    assert "{script}" in cat["prompt"]


def test_create_custom_category():
    from app.database import create_category, get_category
    cat_id = str(uuid.uuid4())
    result = create_category(cat_id, "테스트", "🧪", "테스트 설명", "요약해줘\n{script}")
    assert result["id"] == cat_id
    assert result["is_builtin"] == 0
    assert get_category(cat_id) is not None


def test_update_category():
    from app.database import create_category, update_category
    cat_id = str(uuid.uuid4())
    create_category(cat_id, "원래", "📝", "설명", "{script}")
    result = update_category(cat_id, name="변경됨")
    assert result is not None
    assert result["name"] == "변경됨"


def test_delete_custom_category():
    from app.database import create_category, delete_category, get_category
    cat_id = str(uuid.uuid4())
    create_category(cat_id, "삭제대상", "🗑️", "", "{script}")
    assert delete_category(cat_id) is True
    assert get_category(cat_id) is None


def test_create_job_with_category_id():
    from app.database import create_job, get_job
    job_id = str(uuid.uuid4())
    job = create_job(job_id, "test.webm", title="테스트", category_id="lecture")
    assert job["category_id"] == "lecture"


def test_create_job_without_category_id_is_none():
    from app.database import create_job, get_job
    job_id = str(uuid.uuid4())
    job = create_job(job_id, "test.webm")
    assert job.get("category_id") is None


def test_update_job_category():
    from app.database import create_job, update_job_category, get_job
    job_id = str(uuid.uuid4())
    create_job(job_id, "test.webm")
    update_job_category(job_id, "sermon")
    job = get_job(job_id)
    assert job["category_id"] == "sermon"
