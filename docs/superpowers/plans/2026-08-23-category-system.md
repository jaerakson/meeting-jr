# 카테고리 시스템 구현 플랜

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Meeting Junior 앱에 카테고리 시스템을 추가한다. 회의록·강의노트·설교요약·인터뷰·브레인스토밍 5개 내장 카테고리 각각의 Claude 프롬프트로 문서를 생성하고, 설정 화면에서 카테고리를 관리한다.

**Architecture:** `categories` 테이블 신규 생성 + `meetings` 테이블에 `category_id` 컬럼 추가. 내장 카테고리 5개는 `categories.py`의 `DEFAULT_PROMPTS` 상수에서 관리. 녹음/편집/재요약 시 카테고리를 선택하고, 선택된 카테고리의 프롬프트로 Claude 요약을 실행.

**Tech Stack:** Python 3.11 FastAPI, SQLite, Next.js 15 App Router, Tailwind CSS, pytest+AsyncMock for tests

## Global Constraints

- Python 3.11: `/opt/homebrew/bin/python3.11`
- DB 파일: `backend/meetings.db`, 테이블명은 `meetings` (코드에서 "job"이라 부르지만 DB는 meetings)
- 내장 카테고리 ID (slug): `meeting`, `lecture`, `sermon`, `interview`, `brainstorm`
- `category_id = NULL` → 회의록(`meeting`) 카테고리 폴백
- 요약 프롬프트 우선순위: finalize body category_id → job.category_id → CLAUDE_PROMPT 설정 → summarizer.py DEFAULT_PROMPT
- `summarizer.py`는 수정하지 않는다 (`prompt_template` 파라미터 이미 지원)
- 커밋 메시지: `feat:`, `fix:`, `refactor:`, `docs:` 접두어 사용
- 테스트 실행: `cd /Users/liche/Documents/dev/meeting-jr/backend && /opt/homebrew/bin/python3.11 -m pytest tests/`

---

## 파일 구조

| 파일 | 변경 |
|------|------|
| `backend/app/categories.py` | **신규**: DEFAULT_PROMPTS + BUILTIN_CATEGORIES + seed 함수 |
| `backend/app/database.py` | **변경**: categories 테이블 CRUD + migration(category_id) + create_job 시그니처 |
| `backend/app/main.py` | **변경**: 카테고리 API 5개 + record/finalize/export-notion 수정 |
| `backend/app/notion_sync.py` | **변경**: 테이블·번호목록·인용·볼드 지원 + 카테고리 헤더 |
| `backend/tests/test_categories_db.py` | **신규**: DB CRUD 테스트 |
| `backend/tests/test_categories_api.py` | **신규**: API 엔드포인트 테스트 |
| `backend/tests/test_notion_sync.py` | **신규**: md_to_notion_blocks 파싱 테스트 |
| `frontend/types/index.ts` | **변경**: Category 타입 + Job에 category 필드 추가 |
| `frontend/components/CategorySelect.tsx` | **신규**: 공통 카테고리 드롭다운 |
| `frontend/components/RecordingZone.tsx` | **변경**: CategorySelect 추가 |
| `frontend/components/TranscriptEditor.tsx` | **변경**: CategorySelect + finalize body에 category_id |
| `frontend/components/MainArea.tsx` | **변경**: 카테고리 뱃지 + 재요약 카테고리 모달 |
| `frontend/components/SettingsModal.tsx` | **변경**: 카테고리 탭 추가 |

---

### Task 1: Backend 기반 — categories.py + database.py

**Files:**
- Create: `backend/app/categories.py`
- Modify: `backend/app/database.py`
- Test: `backend/tests/test_categories_db.py`

**Interfaces:**
- Produces: `get_categories() -> list[dict]`, `get_category(id) -> dict|None`, `create_category(...) -> dict`, `update_category(id, **kw) -> dict|None`, `delete_category(id) -> bool`, `update_job_category(job_id, category_id) -> None`
- Produces: `create_job(job_id, filename, title=None, category_id=None) -> dict` (시그니처 변경)
- Produces: `seed_categories(conn)` from categories.py
- Produces: `DEFAULT_PROMPTS: dict[str, str]`, `BUILTIN_CATEGORIES: list[dict]` from categories.py

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# backend/tests/test_categories_db.py
import os, tempfile, pytest
from pathlib import Path

@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    import app.database as dbmod
    monkeypatch.setattr(dbmod, "DB_PATH", db_path)
    dbmod.init_db()
    yield db_path

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
    import uuid
    from app.database import create_category, get_category
    cat_id = str(uuid.uuid4())
    result = create_category(cat_id, "테스트", "🧪", "테스트 설명", "요약해줘\n{script}")
    assert result["id"] == cat_id
    assert result["is_builtin"] == 0
    assert get_category(cat_id) is not None

def test_update_category():
    import uuid
    from app.database import create_category, update_category
    cat_id = str(uuid.uuid4())
    create_category(cat_id, "원래", "📝", "설명", "{script}")
    result = update_category(cat_id, name="변경됨")
    assert result is not None
    assert result["name"] == "변경됨"

def test_delete_custom_category():
    import uuid
    from app.database import create_category, delete_category, get_category
    cat_id = str(uuid.uuid4())
    create_category(cat_id, "삭제대상", "🗑️", "", "{script}")
    assert delete_category(cat_id) is True
    assert get_category(cat_id) is None

def test_create_job_with_category_id():
    import uuid
    from app.database import create_job, get_job
    job_id = str(uuid.uuid4())
    job = create_job(job_id, "test.webm", title="테스트", category_id="lecture")
    assert job["category_id"] == "lecture"

def test_create_job_without_category_id_is_none():
    import uuid
    from app.database import create_job, get_job
    job_id = str(uuid.uuid4())
    job = create_job(job_id, "test.webm")
    assert job.get("category_id") is None

def test_update_job_category():
    import uuid
    from app.database import create_job, update_job_category, get_job
    job_id = str(uuid.uuid4())
    create_job(job_id, "test.webm")
    update_job_category(job_id, "sermon")
    job = get_job(job_id)
    assert job["category_id"] == "sermon"
```

- [ ] **Step 2: 테스트 실행 — 모두 실패 확인**

```bash
cd /Users/liche/Documents/dev/meeting-jr/backend
/opt/homebrew/bin/python3.11 -m pytest tests/test_categories_db.py -v
```
Expected: ImportError 또는 AssertionError (모듈 없음)

- [ ] **Step 3: `backend/app/categories.py` 생성**

```python
"""
카테고리 시스템: DEFAULT_PROMPTS 상수 + BUILTIN_CATEGORIES + DB 시드 함수.
"""
from __future__ import annotations
import sqlite3

DEFAULT_PROMPTS: dict[str, str] = {
    "meeting": """당신은 전문 회의록 작성자입니다. 아래 회의 스크립트를 분석하여 실무에 바로 활용할 수 있는 한국어 회의록을 작성해주세요.

규칙:
- 발언 내용을 충실히 반영하되, 핵심만 간결하게 요약하세요.
- 추측이 아닌 실제 언급된 내용만 작성하세요.
- 액션 아이템은 누가·무엇을·언제까지 형식으로 명확히 기술하세요.
- 반드시 아래 마크다운 형식을 정확히 따르세요.

---

# [회의 주제]

| 항목 | 내용 |
|------|------|
| 일시 | (날짜 및 시간 추정) |
| 참석자 | (화자 목록) |
| 회의 목적 | (한 문장 요약) |

## 핵심 요약

> (회의 전체를 2~3문장으로 요약. 결정 사항과 다음 행동 중심)

## 주요 논의 및 안건

### 안건 1: [제목]
- 배경: ...
- 논의 내용: ...
- 결론: ...

### 안건 2: [제목]
- 배경: ...
- 논의 내용: ...
- 결론: ...

## 주요 결정 사항

- **결정 1**: ...
- **결정 2**: ...

## 액션 아이템

- [ ] @[담당자] — [구체적 작업 내용] (기한: MM/DD)
- [ ] @[담당자] — [구체적 작업 내용] (기한: MM/DD)

## 이슈 및 리스크

- **이슈**: ... / **영향**: ... / **대응**: ...

## 다음 회의

- 일정: (언급된 경우)
- 안건: (언급된 경우)

---
회의 스크립트:
{script}""",

    "lecture": """당신은 전문 학습 자료 정리 전문가입니다. 아래 강의 스크립트를 분석하여 복습과 레퍼런스에 최적화된 한국어 강의 노트를 작성해주세요.

규칙:
- 강사의 핵심 메시지와 설명 흐름을 충실히 반영하세요.
- 개념 간 관계와 위계가 드러나도록 구조화하세요.
- 예시와 사례는 반드시 포함하세요 (이해에 핵심적).
- 반드시 아래 마크다운 형식을 정확히 따르세요.

---

# [강의 제목]

| 항목 | 내용 |
|------|------|
| 일시 | (날짜 추정) |
| 강사 | (화자 이름) |
| 수강자 | (참석자 목록) |
| 강의 주제 | (한 문장 요약) |

## 핵심 요약

> (강의 전체를 2~3문장으로 요약. 배운 핵심과 실용 포인트 중심)

## 강의 목차 / 흐름

1. [주제 1]
2. [주제 2]
3. [주제 3]

## 핵심 개념

### [개념 1]
- **정의**: ...
- **설명**: ...
- **예시**: ...

### [개념 2]
- **정의**: ...
- **설명**: ...
- **예시**: ...

## 주요 학습 포인트

1. **[포인트 1]**: ...
2. **[포인트 2]**: ...
3. **[포인트 3]**: ...

## Q&A 정리

| 질문 | 답변 |
|------|------|
| ... | ... |

## 참고 키워드

`키워드1` `키워드2` `키워드3`

## 복습 체크리스트

- [ ] [개념 1] 이해 확인
- [ ] [개념 2] 이해 확인
- [ ] 추가 학습 자료 찾아보기: ...

---
강의 스크립트:
{script}""",

    "sermon": """당신은 설교 내용을 신앙 생활에 적용할 수 있도록 정리하는 전문가입니다. 아래 설교 스크립트를 분석하여 은혜롭고 실용적인 한국어 설교 요약문을 작성해주세요.

규칙:
- 설교자의 메시지를 왜곡 없이 충실히 반영하세요.
- 성경 구절은 정확하게 인용하세요 (언급된 구절만).
- 적용 포인트는 구체적이고 실천 가능하게 작성하세요.
- 반드시 아래 마크다운 형식을 정확히 따르세요.

---

# [설교 제목]

| 항목 | 내용 |
|------|------|
| 일시 | (날짜 추정) |
| 설교자 | (화자 이름) |
| 회중 | (참석자 목록) |
| 설교 핵심 주제 | (한 문장 요약) |

## 핵심 메시지

> (설교 전체를 2~3문장으로 요약. 하나님의 말씀과 삶의 적용 중심)

## 본문 말씀

| 구절 | 내용 |
|------|------|
| [성경 구절] | [핵심 내용] |

## 설교 전개

### 1부: [소제목]
- ...

### 2부: [소제목]
- ...

### 3부: [소제목]
- ...

## 핵심 포인트

1. **[포인트 1]**: ...
2. **[포인트 2]**: ...
3. **[포인트 3]**: ...

## 삶의 적용

- **이번 주 실천**: ...
- **기도 제목**: ...
- **나눔 포인트**: ...

## 묵상 질문

1. ...
2. ...
3. ...

## 인상 깊은 구절 / 말씀

> "..." — [출처]

---
설교 스크립트:
{script}""",

    "interview": """당신은 인터뷰 내용을 체계적으로 기록하는 전문 저널리스트입니다. 아래 인터뷰 스크립트를 분석하여 핵심 인사이트가 살아있는 한국어 인터뷰 기록을 작성해주세요.

규칙:
- 인터뷰이의 실제 발언 뉘앙스를 최대한 살리세요.
- 중요한 발언은 직접 인용("") 형식으로 포함하세요.
- 사실 관계와 의견을 명확히 구분하세요.
- 반드시 아래 마크다운 형식을 정확히 따르세요.

---

# [인터뷰 제목]

| 항목 | 내용 |
|------|------|
| 일시 | (날짜 추정) |
| 인터뷰어 | (화자 이름) |
| 인터뷰이 | (화자 이름 + 역할/직함) |
| 주제 | (한 문장 요약) |

## 핵심 요약

> (인터뷰 전체를 2~3문장으로 요약. 인터뷰이의 핵심 입장 중심)

## 인터뷰이 프로필

- **배경**: ...
- **전문 분야**: ...
- **주요 관심사**: ...

## 주요 Q&A

### Q1: [질문 요약]
> "[핵심 발언 직접 인용]"

**요약**: ...

### Q2: [질문 요약]
> "[핵심 발언 직접 인용]"

**요약**: ...

### Q3: [질문 요약]
> "[핵심 발언 직접 인용]"

**요약**: ...

## 핵심 인사이트

1. **[인사이트 1]**: ...
2. **[인사이트 2]**: ...
3. **[인사이트 3]**: ...

## 주목할 발언

> "..." (맥락: ...)

## 후속 조치

- [ ] @[담당자] — [확인·팩트체크 사항] (기한: MM/DD)
- [ ] @[담당자] — [후속 인터뷰 또는 자료 요청] (기한: MM/DD)

---
인터뷰 스크립트:
{script}""",

    "brainstorm": """당신은 창의적 아이디어 세션을 구조화하는 전문 퍼실리테이터입니다. 아래 브레인스토밍 세션 스크립트를 분석하여 아이디어가 손실 없이 정리된 한국어 세션 기록을 작성해주세요.

규칙:
- 제안된 아이디어는 평가 없이 모두 포함하세요 (비판 없는 수렴).
- 참여자별 기여도가 드러나도록 작성하세요.
- 결정된 방향과 미결 사항을 명확히 구분하세요.
- 반드시 아래 마크다운 형식을 정확히 따르세요.

---

# [세션 주제]

| 항목 | 내용 |
|------|------|
| 일시 | (날짜 추정) |
| 참여자 | (화자 목록) |
| 목표 | (이 세션에서 해결하고자 한 문제) |

## 핵심 요약

> (세션 전체를 2~3문장으로 요약. 나온 방향성과 결론 중심)

## 문제 정의

- **현재 상황**: ...
- **해결하려는 문제**: ...
- **성공 기준**: ...

## 제안된 아이디어 전체

| 아이디어 | 제안자 | 기대 효과 |
|---------|--------|----------|
| ... | ... | ... |
| ... | ... | ... |

## 유망 아이디어 (심화 검토 대상)

### [아이디어 A]
- **내용**: ...
- **장점**: ...
- **도전 과제**: ...
- **다음 단계**: ...

### [아이디어 B]
- **내용**: ...
- **장점**: ...
- **도전 과제**: ...

## 결정된 방향

- **채택**: ...
- **근거**: ...
- **보류**: ... (이유: ...)

## 실행 계획

- [ ] @[담당자] — [검증·리서치 과제] (기한: MM/DD)
- [ ] @[담당자] — [프로토타입·실험] (기한: MM/DD)

## 미결 사항

- [ ] [결정하지 못한 사항 1] — 담당: ...
- [ ] [결정하지 못한 사항 2] — 담당: ...

---
브레인스토밍 스크립트:
{script}""",
}

BUILTIN_CATEGORIES: list[dict] = [
    {"id": "meeting",    "name": "회의록",       "icon": "📋", "description": "팀 미팅·기획 회의 정리",      "sort_order": 1},
    {"id": "lecture",    "name": "강의노트",      "icon": "📚", "description": "강의·세미나·교육 내용 정리",  "sort_order": 2},
    {"id": "sermon",     "name": "설교요약",      "icon": "✝️", "description": "설교·예배·강론 정리",          "sort_order": 3},
    {"id": "interview",  "name": "인터뷰",        "icon": "🎙️", "description": "채용·취재·리서치 인터뷰 정리","sort_order": 4},
    {"id": "brainstorm", "name": "브레인스토밍",  "icon": "💡", "description": "아이디어 세션 정리",          "sort_order": 5},
]


def seed_categories(conn: sqlite3.Connection) -> None:
    """내장 카테고리 5개를 INSERT OR IGNORE로 삽입한다. 기존 데이터 보호."""
    for cat in BUILTIN_CATEGORIES:
        conn.execute(
            """
            INSERT OR IGNORE INTO categories (id, name, icon, description, prompt, is_builtin, sort_order)
            VALUES (?, ?, ?, ?, ?, 1, ?)
            """,
            (cat["id"], cat["name"], cat["icon"], cat["description"],
             DEFAULT_PROMPTS[cat["id"]], cat["sort_order"]),
        )
    conn.commit()
```

- [ ] **Step 4: `backend/app/database.py` 수정**

`_migrate` 함수에 `category_id` 컬럼 추가:

```python
def _migrate(conn: sqlite3.Connection) -> None:
    """기존 DB에 누락된 컬럼을 추가한다."""
    existing = {row[1] for row in conn.execute("PRAGMA table_info(meetings)")}
    for col, definition in [
        ("notion_url", "TEXT"),
        ("notion_page_id", "TEXT"),
        ("category_id", "TEXT"),  # 신규
    ]:
        if col not in existing:
            conn.execute(f"ALTER TABLE meetings ADD COLUMN {col} {definition}")
    conn.commit()
```

`init_db` 함수에 categories 테이블 생성 + 시드 추가:

```python
def init_db() -> None:
    """meetings/categories 테이블이 없으면 생성한다. 앱 시작 시 호출."""
    from .categories import seed_categories  # 순환 import 방지: 로컬 import
    conn = _get_conn()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS meetings (
                id          TEXT PRIMARY KEY,
                title       TEXT,
                filename    TEXT,
                status      TEXT NOT NULL DEFAULT 'pending',
                created_at  TEXT NOT NULL,
                duration_sec INTEGER,
                transcript  TEXT,
                summary     TEXT,
                speakers    TEXT,
                error_msg   TEXT,
                notion_url  TEXT,
                notion_page_id TEXT,
                category_id TEXT REFERENCES categories(id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id          TEXT PRIMARY KEY,
                name        TEXT NOT NULL,
                icon        TEXT NOT NULL DEFAULT '📋',
                description TEXT NOT NULL DEFAULT '',
                prompt      TEXT NOT NULL,
                is_builtin  INTEGER NOT NULL DEFAULT 0,
                sort_order  INTEGER NOT NULL DEFAULT 99,
                created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
                updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key        TEXT PRIMARY KEY,
                value      TEXT NOT NULL,
                updated_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
            )
        """)
        _migrate(conn)
        seed_categories(conn)
        conn.commit()
    finally:
        conn.close()
```

`create_job` 함수에 `category_id` 파라미터 추가:

```python
def create_job(
    job_id: str,
    filename: str,
    title: Optional[str] = None,
    category_id: Optional[str] = None,
) -> dict:
    """새 Job 레코드를 생성하고 dict로 반환."""
    now = datetime.now(timezone.utc).isoformat()
    conn = _get_conn()
    try:
        conn.execute(
            """
            INSERT INTO meetings (id, title, filename, status, created_at, category_id)
            VALUES (?, ?, ?, 'pending', ?, ?)
            """,
            (job_id, title or filename, filename, now, category_id),
        )
        conn.commit()
        return get_job(job_id)
    finally:
        conn.close()
```

categories CRUD 함수 추가 (파일 끝에):

```python
# ---------------------------------------------------------------------------
# Categories CRUD
# ---------------------------------------------------------------------------

def get_categories() -> list[dict]:
    """전체 카테고리 목록을 sort_order 오름차순으로 반환."""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM categories ORDER BY sort_order ASC, created_at ASC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_category(cat_id: str) -> Optional[dict]:
    """단일 카테고리 조회. 없으면 None."""
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM categories WHERE id = ?", (cat_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def create_category(
    cat_id: str,
    name: str,
    icon: str,
    description: str,
    prompt: str,
) -> dict:
    """사용자 카테고리를 생성하고 반환."""
    conn = _get_conn()
    try:
        conn.execute(
            """
            INSERT INTO categories (id, name, icon, description, prompt, is_builtin, sort_order)
            VALUES (?, ?, ?, ?, ?, 0, 99)
            """,
            (cat_id, name, icon, description, prompt),
        )
        conn.commit()
        return get_category(cat_id)
    finally:
        conn.close()


def update_category(cat_id: str, **kwargs) -> Optional[dict]:
    """카테고리 필드를 선택적으로 갱신한다."""
    allowed = {"name", "icon", "description", "prompt"}
    fields = [(k, v) for k, v in kwargs.items() if k in allowed]
    if not fields:
        return get_category(cat_id)

    set_clause = ", ".join(f"{k} = ?" for k, _ in fields)
    values = [v for _, v in fields] + [cat_id]
    conn = _get_conn()
    try:
        conn.execute(
            f"UPDATE categories SET {set_clause}, updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now') WHERE id = ?",
            values,
        )
        conn.commit()
        return get_category(cat_id)
    finally:
        conn.close()


def delete_category(cat_id: str) -> bool:
    """카테고리 삭제. 성공 시 True."""
    conn = _get_conn()
    try:
        cursor = conn.execute("DELETE FROM categories WHERE id = ?", (cat_id,))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def update_job_category(job_id: str, category_id: str) -> None:
    """job의 category_id를 갱신한다."""
    conn = _get_conn()
    try:
        conn.execute(
            "UPDATE meetings SET category_id = ? WHERE id = ?",
            (category_id, job_id),
        )
        conn.commit()
    finally:
        conn.close()
```

- [ ] **Step 5: 테스트 실행 — 모두 통과 확인**

```bash
cd /Users/liche/Documents/dev/meeting-jr/backend
/opt/homebrew/bin/python3.11 -m pytest tests/test_categories_db.py -v
```
Expected: 10개 테스트 모두 PASS

- [ ] **Step 6: 기존 테스트 회귀 확인**

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/ -v
```
Expected: 전체 PASS

- [ ] **Step 7: 커밋**

```bash
cd /Users/liche/Documents/dev/meeting-jr
git add backend/app/categories.py backend/app/database.py backend/tests/test_categories_db.py
git commit -m "feat: add categories.py with DEFAULT_PROMPTS and database CRUD for categories"
```

---

### Task 2: Backend — Category API 엔드포인트

**Files:**
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_categories_api.py`

**Interfaces:**
- Consumes: `get_categories()`, `get_category()`, `create_category()`, `update_category()`, `delete_category()` from database.py
- Consumes: `DEFAULT_PROMPTS` from categories.py
- Produces: `GET /api/categories` → `list[dict]`
- Produces: `POST /api/categories` → `dict` (201 equivalent, body에 id/name/icon/description/prompt)
- Produces: `PATCH /api/categories/{id}` → `dict`
- Produces: `DELETE /api/categories/{id}` → `{"status": "deleted"}`
- Produces: `POST /api/categories/{id}/reset` → `dict` (내장 카테고리 프롬프트 복원)

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# backend/tests/test_categories_api.py
import pytest, uuid
from fastapi.testclient import TestClient
from pathlib import Path

@pytest.fixture
def client(tmp_path, monkeypatch):
    import app.database as dbmod
    monkeypatch.setattr(dbmod, "DB_PATH", tmp_path / "test.db")
    # main.py의 경로 상수들도 tmp_path로 리다이렉트
    import app.main as mainmod
    monkeypatch.setattr(mainmod, "INPUT_DIR", tmp_path / "input")
    monkeypatch.setattr(mainmod, "OUTPUT_DIR", tmp_path / "output")
    monkeypatch.setattr(mainmod, "SPEAKERS_FILE", tmp_path / "speakers.json")
    (tmp_path / "input").mkdir()
    (tmp_path / "output").mkdir()
    dbmod.init_db()
    from app.main import app
    return TestClient(app)

def test_list_categories_returns_5_builtins(client):
    res = client.get("/api/categories")
    assert res.status_code == 200
    cats = res.json()
    assert len(cats) == 5
    assert cats[0]["id"] == "meeting"  # sort_order=1

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
    assert data["is_builtin"] == 0

def test_create_category_requires_prompt_placeholder(client):
    body = {"name": "잘못된", "icon": "❌", "description": "", "prompt": "스크립트 없음"}
    res = client.post("/api/categories", json=body)
    assert res.status_code == 422

def test_patch_builtin_category_prompt(client):
    res = client.patch("/api/categories/meeting", json={"prompt": "짧게 요약\n{script}"})
    assert res.status_code == 200
    assert res.json()["prompt"] == "짧게 요약\n{script}"

def test_delete_builtin_category_rejected(client):
    res = client.delete("/api/categories/meeting")
    assert res.status_code == 422

def test_delete_custom_category(client):
    # 먼저 생성
    cat = client.post("/api/categories", json={
        "name": "삭제", "icon": "🗑️", "description": "", "prompt": "{script}"
    }).json()
    res = client.delete(f"/api/categories/{cat['id']}")
    assert res.status_code == 200

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
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
cd /Users/liche/Documents/dev/meeting-jr/backend
/opt/homebrew/bin/python3.11 -m pytest tests/test_categories_api.py -v
```
Expected: 404 또는 ImportError (엔드포인트 없음)

- [ ] **Step 3: `main.py`에 import 추가 및 카테고리 API 추가**

`main.py` 상단 import 섹션에 추가:
```python
from .database import (
    init_db,
    create_job,
    get_job,
    get_all_jobs,
    update_job_status,
    update_job_result,
    update_job_title,
    update_job_notion,
    delete_job,
    search_jobs,
    get_categories,      # 신규
    get_category,        # 신규
    create_category,     # 신규
    update_category,     # 신규
    delete_category,     # 신규
    update_job_category, # 신규
)
```

파일 끝 (또는 settings 섹션 앞)에 카테고리 엔드포인트 추가:

```python
# ---------------------------------------------------------------------------
# Categories API
# ---------------------------------------------------------------------------

@app.get("/api/categories")
async def list_categories():
    """카테고리 목록 반환 (sort_order 오름차순)."""
    return get_categories()


@app.post("/api/categories")
async def create_category_endpoint(body: dict):
    """사용자 카테고리 생성."""
    name = (body.get("name") or "").strip()
    icon = (body.get("icon") or "📋").strip()
    description = (body.get("description") or "").strip()
    prompt = (body.get("prompt") or "").strip()

    if not name:
        raise HTTPException(status_code=422, detail="name이 비어 있습니다.")
    if "{script}" not in prompt:
        raise HTTPException(status_code=422, detail="prompt에 {script} 플레이스홀더가 필요합니다.")

    import uuid as _uuid
    cat_id = str(_uuid.uuid4())
    return create_category(cat_id, name, icon, description, prompt)


@app.patch("/api/categories/{cat_id}")
async def update_category_endpoint(cat_id: str, body: dict):
    """카테고리 이름·아이콘·설명·프롬프트 수정."""
    cat = get_category(cat_id)
    if not cat:
        raise HTTPException(status_code=404, detail="카테고리를 찾을 수 없습니다.")

    kwargs = {}
    if "name" in body:
        kwargs["name"] = body["name"]
    if "icon" in body:
        kwargs["icon"] = body["icon"]
    if "description" in body:
        kwargs["description"] = body["description"]
    if "prompt" in body:
        p = body["prompt"]
        if "{script}" not in p:
            raise HTTPException(status_code=422, detail="prompt에 {script} 플레이스홀더가 필요합니다.")
        kwargs["prompt"] = p

    result = update_category(cat_id, **kwargs)
    return result


@app.delete("/api/categories/{cat_id}")
async def delete_category_endpoint(cat_id: str):
    """카테고리 삭제. is_builtin=1이면 거부."""
    cat = get_category(cat_id)
    if not cat:
        raise HTTPException(status_code=404, detail="카테고리를 찾을 수 없습니다.")
    if cat.get("is_builtin"):
        raise HTTPException(status_code=422, detail="내장 카테고리는 삭제할 수 없습니다.")

    delete_category(cat_id)
    return {"status": "deleted", "id": cat_id}


@app.post("/api/categories/{cat_id}/reset")
async def reset_category_prompt(cat_id: str):
    """내장 카테고리 프롬프트를 DEFAULT로 복원."""
    from .categories import DEFAULT_PROMPTS
    cat = get_category(cat_id)
    if not cat:
        raise HTTPException(status_code=404, detail="카테고리를 찾을 수 없습니다.")
    if not cat.get("is_builtin"):
        raise HTTPException(status_code=422, detail="사용자 카테고리는 초기화할 수 없습니다.")
    if cat_id not in DEFAULT_PROMPTS:
        raise HTTPException(status_code=422, detail="해당 카테고리의 기본 프롬프트가 없습니다.")

    return update_category(cat_id, prompt=DEFAULT_PROMPTS[cat_id])
```

- [ ] **Step 4: 테스트 실행 — 모두 통과 확인**

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/test_categories_api.py -v
```
Expected: 8개 PASS

- [ ] **Step 5: 전체 테스트 회귀 확인**

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/ -v
```
Expected: 전체 PASS

- [ ] **Step 6: 커밋**

```bash
git add backend/app/main.py backend/tests/test_categories_api.py
git commit -m "feat: add category API endpoints (CRUD + reset)"
```

---

### Task 3: Backend — record/finalize 통합 + notion_sync 개선

**Files:**
- Modify: `backend/app/main.py` (record_audio, finalize_job, run_summary, export_notion)
- Modify: `backend/app/notion_sync.py` (md_to_notion_blocks, export_to_notion, update_notion_page)
- Test: `backend/tests/test_notion_sync.py`

**Interfaces:**
- Consumes: `get_category(id)` from database.py, `DEFAULT_PROMPTS` from categories.py
- `POST /api/record` body에 form field `category_id: str = Form("meeting")` 추가
- `POST /api/jobs/{id}/finalize` body에 `category_id?: string` 추가
- `export_to_notion(title, summary_md, upload_ts, category_icon, category_name)` 시그니처 변경
- `update_notion_page(page_id, title, summary_md, upload_ts, category_icon, category_name)` 시그니처 변경

- [ ] **Step 1: notion_sync 테스트 작성**

```python
# backend/tests/test_notion_sync.py
import pytest
from app.notion_sync import md_to_notion_blocks

def test_heading_1():
    blocks = md_to_notion_blocks("# 제목")
    assert len(blocks) == 1
    assert blocks[0]["type"] == "heading_1"
    assert blocks[0]["heading_1"]["rich_text"][0]["text"]["content"] == "제목"

def test_heading_2_with_spacer():
    blocks = md_to_notion_blocks("## 섹션")
    # spacer paragraph + heading_2
    assert any(b["type"] == "heading_2" for b in blocks)

def test_heading_3():
    blocks = md_to_notion_blocks("### 소제목")
    assert blocks[0]["type"] == "heading_3"

def test_bulleted_list():
    blocks = md_to_notion_blocks("- 항목")
    assert blocks[0]["type"] == "bulleted_list_item"

def test_numbered_list():
    blocks = md_to_notion_blocks("1. 첫째\n2. 둘째")
    types = [b["type"] for b in blocks]
    assert types == ["numbered_list_item", "numbered_list_item"]
    assert blocks[0]["numbered_list_item"]["rich_text"][0]["text"]["content"] == "첫째"

def test_todo_unchecked():
    blocks = md_to_notion_blocks("- [ ] 할 일")
    assert blocks[0]["type"] == "to_do"
    assert blocks[0]["to_do"]["checked"] is False

def test_todo_checked():
    blocks = md_to_notion_blocks("- [x] 완료")
    assert blocks[0]["type"] == "to_do"
    assert blocks[0]["to_do"]["checked"] is True

def test_quote_block():
    blocks = md_to_notion_blocks("> 인용 텍스트")
    assert blocks[0]["type"] == "quote"
    assert blocks[0]["quote"]["rich_text"][0]["text"]["content"] == "인용 텍스트"

def test_divider():
    blocks = md_to_notion_blocks("---")
    assert blocks[0]["type"] == "divider"

def test_table_basic():
    md = "| 항목 | 내용 |\n|------|------|\n| 일시 | 2024-01-01 |"
    blocks = md_to_notion_blocks(md)
    assert len(blocks) == 1
    tbl = blocks[0]
    assert tbl["type"] == "table"
    assert tbl["table"]["table_width"] == 2
    assert tbl["table"]["has_column_header"] is True
    rows = tbl["children"]
    assert len(rows) == 2  # 헤더행 + 데이터행
    assert rows[0]["table_row"]["cells"][0][0]["text"]["content"] == "항목"

def test_table_3col():
    md = "| A | B | C |\n|---|---|---|\n| 1 | 2 | 3 |"
    blocks = md_to_notion_blocks(md)
    assert blocks[0]["table"]["table_width"] == 3

def test_bold_annotation():
    blocks = md_to_notion_blocks("- **중요** 텍스트")
    rich = blocks[0]["bulleted_list_item"]["rich_text"]
    bold_parts = [r for r in rich if r.get("annotations", {}).get("bold")]
    assert len(bold_parts) == 1
    assert bold_parts[0]["text"]["content"] == "중요"

def test_paragraph_plain():
    blocks = md_to_notion_blocks("일반 텍스트 줄")
    assert blocks[0]["type"] == "paragraph"
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/test_notion_sync.py -v
```
Expected: `numbered_list`, `quote`, `table`, `bold_annotation` 테스트 실패

- [ ] **Step 3: `notion_sync.py`의 `_rich_text`를 bold 지원으로 업데이트**

```python
def _rich_text(text: str) -> list[dict]:
    """Notion rich_text 배열 생성. **bold** 인라인 변환 지원."""
    result: list[dict] = []
    bold_re = re.compile(r'\*\*(.+?)\*\*')
    last = 0
    for m in bold_re.finditer(text):
        if m.start() > last:
            result.append({"type": "text", "text": {"content": text[last:m.start()]}})
        result.append({
            "type": "text",
            "text": {"content": m.group(1)},
            "annotations": {"bold": True},
        })
        last = m.end()
    if last < len(text):
        result.append({"type": "text", "text": {"content": text[last:]}})
    return result if result else [{"type": "text", "text": {"content": text}}]
```

- [ ] **Step 4: `md_to_notion_blocks` 전체 재작성 (table/quote/numbered 지원)**

`notion_sync.py`의 `md_to_notion_blocks` 함수를 다음으로 교체:

```python
def md_to_notion_blocks(md_text: str) -> list[dict]:
    """
    마크다운 문자열을 Notion API 블록 배열로 변환한다.

    지원 문법:
      # heading   -> heading_1
      ## heading  -> heading_2 (섹션별 색상 + 이모지)
      ### heading -> heading_3
      - [ ] text  -> to_do (unchecked)
      - [x] text  -> to_do (checked)
      - text      -> bulleted_list_item
      1. text     -> numbered_list_item
      > text      -> quote
      | col |...| -> table (여러 줄 연속)
      ---         -> divider
      일반 텍스트  -> paragraph (핵심 요약 섹션 내에서는 callout)
    """
    blocks: list[dict] = []
    lines = md_text.split("\n")
    current_section: str = ""
    table_lines: list[str] = []

    def flush_table() -> None:
        """누적된 테이블 라인을 Notion table 블록으로 변환."""
        nonlocal table_lines
        if not table_lines:
            return
        rows: list[list[str]] = []
        for row_line in table_lines:
            stripped = row_line.strip()
            # 구분선 행 (|---|---| 패턴) 건너뜀
            if re.match(r'^\|[-:\s|]+\|$', stripped):
                continue
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            rows.append(cells)
        table_lines = []
        if not rows:
            return
        col_count = max(len(r) for r in rows)
        children = []
        for cells in rows:
            padded = cells + [""] * (col_count - len(cells))
            children.append({
                "object": "block",
                "type": "table_row",
                "table_row": {
                    "cells": [[{"type": "text", "text": {"content": c}}] for c in padded],
                },
            })
        blocks.append({
            "object": "block",
            "type": "table",
            "table": {
                "table_width": col_count,
                "has_column_header": True,
                "has_row_header": False,
            },
            "children": children,
        })

    for line in lines:
        stripped = line.strip()

        # 테이블 행: | 로 시작하고 끝남
        if stripped.startswith("|") and stripped.endswith("|"):
            table_lines.append(stripped)
            continue

        # 비테이블 행 → 누적된 테이블 플러시
        flush_table()

        # 빈 줄 무시
        if not stripped:
            continue

        # 구분선
        if re.match(r"^-{3,}$", stripped):
            blocks.append({"object": "block", "type": "divider", "divider": {}})
            current_section = ""
            continue

        # 인용 (> text)
        quote_match = re.match(r"^>\s+(.+)$", stripped)
        if quote_match:
            blocks.append({
                "object": "block",
                "type": "quote",
                "quote": {"rich_text": _rich_text(quote_match.group(1))},
            })
            continue

        # 헤딩 (### 먼저 검사)
        h3_match = re.match(r"^###\s+(.+)$", stripped)
        if h3_match:
            blocks.append({
                "object": "block",
                "type": "heading_3",
                "heading_3": {"rich_text": _rich_text(h3_match.group(1))},
            })
            continue

        h2_match = re.match(r"^##\s+(.+)$", stripped)
        if h2_match:
            section_title = h2_match.group(1)
            current_section = section_title
            color, emoji = _get_section_style(section_title)
            label = f"{emoji} {section_title}" if emoji else section_title
            blocks.append(_spacer())
            blocks.append({
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": _rich_text(label),
                    "color": color,
                },
            })
            continue

        h1_match = re.match(r"^#\s+(.+)$", stripped)
        if h1_match:
            blocks.append({
                "object": "block",
                "type": "heading_1",
                "heading_1": {"rich_text": _rich_text(h1_match.group(1))},
            })
            continue

        # 체크박스 — checked
        todo_checked = re.match(r"^-\s+\[x\]\s+(.+)$", stripped, re.IGNORECASE)
        if todo_checked:
            blocks.append({
                "object": "block",
                "type": "to_do",
                "to_do": {
                    "rich_text": _rich_text(todo_checked.group(1)),
                    "checked": True,
                },
            })
            continue

        # 체크박스 — unchecked
        todo_unchecked = re.match(r"^-\s+\[\s?\]\s+(.+)$", stripped)
        if todo_unchecked:
            blocks.append({
                "object": "block",
                "type": "to_do",
                "to_do": {
                    "rich_text": _rich_text(todo_unchecked.group(1)),
                    "checked": False,
                },
            })
            continue

        # 불릿 리스트
        bullet_match = re.match(r"^-\s+(.+)$", stripped)
        if bullet_match:
            blocks.append({
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": _rich_text(bullet_match.group(1)),
                },
            })
            continue

        # 번호 리스트 (1. / 2. / ...)
        numbered_match = re.match(r"^\d+\.\s+(.+)$", stripped)
        if numbered_match:
            blocks.append({
                "object": "block",
                "type": "numbered_list_item",
                "numbered_list_item": {
                    "rich_text": _rich_text(numbered_match.group(1)),
                },
            })
            continue

        # 일반 텍스트: 핵심 요약 섹션 → callout, 나머지 → paragraph
        if "핵심 요약" in current_section or "핵심 메시지" in current_section:
            blocks.append({
                "object": "block",
                "type": "callout",
                "callout": {
                    "rich_text": _rich_text(stripped),
                    "icon": {"type": "emoji", "emoji": "💡"},
                    "color": "yellow_background",
                },
            })
        else:
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": _rich_text(stripped)},
            })

    flush_table()  # 파일 마지막이 테이블인 경우 처리
    return blocks
```

- [ ] **Step 5: `export_to_notion`과 `update_notion_page` 시그니처 + 카테고리 헤더 추가**

```python
async def export_to_notion(
    title: str,
    summary_md: str,
    upload_ts: str = "",
    category_icon: str = "📋",
    category_name: str = "회의록",
) -> dict:
    """마크다운 회의록을 Notion 데이터베이스에 등록한다."""
    from .settings_manager import get_setting
    api_key = get_setting("NOTION_API_KEY")
    database_id = get_setting("NOTION_DATABASE_ID")

    if not api_key:
        raise ValueError("NOTION_API_KEY가 설정되지 않았습니다. 설정 화면에서 Notion API 키를 입력하세요.")
    if not database_id:
        raise ValueError("NOTION_DATABASE_ID가 설정되지 않았습니다. 설정 화면에서 Notion 데이터베이스 ID를 입력하세요.")

    notion = AsyncClient(auth=api_key)

    # 카테고리 헤더 prepend
    header = (
        f"📤 업로드 일시: {upload_ts}\n"
        f"📂 카테고리: {category_icon} {category_name}\n\n"
        f"────────────────────────────────────\n\n"
    )
    full_md = header + summary_md
    children = md_to_notion_blocks(full_md)

    first_batch = children[:100]
    remaining = children[100:]

    try:
        db_meta = await notion.databases.retrieve(database_id=database_id)
        title_prop_name = "title"
        for prop_name, prop_info in db_meta.get("properties", {}).items():
            if prop_info.get("type") == "title":
                title_prop_name = prop_name
                break

        page = await notion.pages.create(
            parent={"database_id": database_id},
            icon={"type": "emoji", "emoji": category_icon or "📋"},
            properties={
                title_prop_name: {"title": [{"text": {"content": title}}]},
            },
            children=first_batch,
        )

        page_id = page["id"]
        while remaining:
            batch = remaining[:100]
            remaining = remaining[100:]
            await notion.blocks.children.append(block_id=page_id, children=batch)

        page_url = page.get("url", "")
        logger.info("Notion 페이지 생성 완료: %s", page_url)
        return {"url": page_url, "page_id": page_id}

    except Exception as e:
        err_str = str(e)
        logger.error("Notion API 호출 실패: %s", err_str)
        if "Could not find database" in err_str or "object_not_found" in err_str:
            raise ValueError(
                "데이터베이스를 찾을 수 없습니다. Notion에서 Integration을 연결했는지 확인하세요."
            ) from e
        if "Unauthorized" in err_str or "unauthorized" in err_str or "API token" in err_str:
            raise ValueError("Notion API 키가 유효하지 않습니다.") from e
        raise


async def update_notion_page(
    page_id: str,
    title: str,
    summary_md: str,
    upload_ts: str = "",
    category_icon: str = "📋",
    category_name: str = "회의록",
) -> dict:
    """기존 Notion 페이지의 내용을 교체한다."""
    from .settings_manager import get_setting
    api_key = get_setting("NOTION_API_KEY")
    if not api_key:
        raise ValueError("NOTION_API_KEY가 설정되지 않았습니다.")

    notion = AsyncClient(auth=api_key)

    children_resp = await notion.blocks.children.list(block_id=page_id, page_size=100)
    for block in children_resp.get("results", []):
        await notion.blocks.delete(block_id=block["id"])

    page_info = await notion.pages.retrieve(page_id=page_id)
    parent = page_info.get("parent", {})
    database_id = parent.get("database_id")
    title_prop_name = "title"
    if database_id:
        try:
            db_meta = await notion.databases.retrieve(database_id=database_id)
            for prop_name, prop_info in db_meta.get("properties", {}).items():
                if prop_info.get("type") == "title":
                    title_prop_name = prop_name
                    break
        except Exception:
            logger.warning("DB 메타데이터 조회 실패, title property 이름 fallback 사용")

    await notion.pages.update(
        page_id=page_id,
        properties={title_prop_name: {"title": [{"text": {"content": title}}]}},
    )

    header = (
        f"📤 업로드 일시: {upload_ts}\n"
        f"📂 카테고리: {category_icon} {category_name}\n\n"
        f"────────────────────────────────────\n\n"
    )
    full_md = header + summary_md
    new_blocks = md_to_notion_blocks(full_md)
    remaining = new_blocks
    while remaining:
        batch = remaining[:100]
        remaining = remaining[100:]
        await notion.blocks.children.append(block_id=page_id, children=batch)

    page = await notion.pages.retrieve(page_id=page_id)
    page_url = page.get("url", "")
    logger.info("Notion 페이지 업데이트 완료: %s", page_url)
    return {"url": page_url, "page_id": page_id}
```

- [ ] **Step 6: `main.py`의 `record_audio` 수정 — category_id form field 추가**

```python
from fastapi import FastAPI, File, Form, UploadFile, HTTPException

@app.post("/api/record")
async def record_audio(
    audio: UploadFile = File(...),
    category_id: str = Form("meeting"),
):
    """브라우저에서 녹음된 webm Blob을 받아 처리 큐에 등록한다."""
    max_bytes = MAX_UPLOAD_MB * 1024 * 1024
    total_size = 0

    job_id = str(uuid.uuid4())
    content_type = audio.content_type or ""
    if "mp4" in content_type:
        ext = ".mp4"
    elif "ogg" in content_type:
        ext = ".ogg"
    else:
        ext = ".webm"
    filename = f"{job_id}{ext}"
    save_path = INPUT_DIR / filename

    async with aiofiles.open(save_path, "wb") as f:
        while chunk := await audio.read(1024 * 1024):
            total_size += len(chunk)
            if total_size > max_bytes:
                save_path.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=422,
                    detail=f"파일 크기가 {MAX_UPLOAD_MB}MB를 초과합니다.",
                )
            await f.write(chunk)

    if total_size == 0:
        save_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail="오디오 데이터가 없습니다.")

    _custom = get_setting("DEFAULT_MEETING_TITLE")
    title = _custom if _custom else "회의록"
    # category_id가 유효한지 확인, 없으면 "meeting" 폴백
    valid_cat = get_category(category_id) if category_id else None
    effective_category_id = category_id if valid_cat else "meeting"

    create_job(job_id, filename, title=title, category_id=effective_category_id)
    await job_queue.put(job_id)

    return {"job_id": job_id, "filename": filename}
```

- [ ] **Step 7: `main.py`의 `finalize_job` + `run_summary` 수정**

```python
@app.post("/api/jobs/{job_id}/finalize")
async def finalize_job(job_id: str, body: dict):
    """편집된 transcript와 speaker_map을 받아 Claude 요약을 시작한다."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job을 찾을 수 없습니다.")

    transcript: str = body.get("transcript", "").strip()
    speaker_map: dict = body.get("speaker_map", {})
    body_category_id: str | None = body.get("category_id")

    if not transcript:
        raise HTTPException(status_code=422, detail="transcript가 비어 있습니다.")

    # category_id 결정: body → job → "meeting" 폴백
    category_id = body_category_id or job.get("category_id") or "meeting"
    if body_category_id:
        update_job_category(job_id, category_id)

    update_job_result(job_id, transcript=transcript, speakers=speaker_map)

    if speaker_map:
        _save_speakers(speaker_map)

    final_transcript = transcript
    for speaker_id, name in speaker_map.items():
        if name.strip():
            final_transcript = final_transcript.replace(speaker_id, name)

    script_path = INPUT_DIR / f"{job_id}.txt"
    script_path.write_text(final_transcript, encoding="utf-8")

    update_job_status(job_id, "summarizing")
    progress_store.pop(job_id, None)

    asyncio.create_task(run_summary(job_id, str(script_path), speaker_map, category_id=category_id))

    return {"status": "summarizing", "job_id": job_id}


async def run_summary(job_id: str, script_path: str, speaker_map: dict, category_id: str = "meeting"):
    """백그라운드에서 Claude 요약을 실행한다."""
    try:
        update_progress(job_id, {
            "stage": "summarizing",
            "progress": 0,
            "message": "회의록 생성 중...",
        })

        from .summarizer import generate_summary

        _model = get_setting("CLAUDE_MODEL") or "claude-sonnet-4-6"

        # 프롬프트 우선순위: 카테고리 prompt → CLAUDE_PROMPT 설정 → DEFAULT_PROMPT
        cat = get_category(category_id)
        if cat:
            _prompt = cat["prompt"]
        else:
            _prompt = get_setting("CLAUDE_PROMPT") or None

        summary = await generate_summary(
            script_path,
            speaker_map,
            job_id,
            lambda jid, data: update_progress(jid, data),
            model=_model,
            prompt_template=_prompt,
        )

        output_path = OUTPUT_DIR / f"{job_id}_요약.md"
        output_path.write_text(summary, encoding="utf-8")

        update_job_result(job_id, summary=summary, status="done")
        update_progress(job_id, {
            "stage": "done",
            "progress": 100,
            "message": "완료",
        })

    except Exception as e:
        error_msg = f"{type(e).__name__}: {e}"
        update_job_status(job_id, "error", error_msg)
        update_progress(job_id, {
            "stage": "error",
            "progress": 0,
            "message": error_msg,
        })
```

- [ ] **Step 8: `main.py`의 `export_notion` 수정 — 카테고리 정보 전달**

`export_notion` 함수 내 summary_with_meta 부분을 다음으로 교체:

```python
        # 카테고리 정보 조회
        job_cat_id = job.get("category_id") or "meeting"
        cat = get_category(job_cat_id)
        cat_icon = cat["icon"] if cat else "📋"
        cat_name = cat["name"] if cat else "회의록"

        # 업로드 일시 (내보내기 실행 시점, KST)
        upload_ts = datetime.now(_KST).strftime("%Y-%m-%d %H:%M")
        summary_md = job["summary"] or ""

        if existing_page_id and mode == "update":
            result = await update_notion_page(
                existing_page_id, notion_title, summary_md,
                upload_ts=upload_ts, category_icon=cat_icon, category_name=cat_name,
            )
        else:
            result = await export_to_notion(
                notion_title, summary_md,
                upload_ts=upload_ts, category_icon=cat_icon, category_name=cat_name,
            )
            update_job_notion(job_id, result["url"], result["page_id"])
```

- [ ] **Step 9: 테스트 실행**

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/test_notion_sync.py tests/test_categories_api.py tests/test_categories_db.py -v
```
Expected: 전체 PASS

- [ ] **Step 10: 커밋**

```bash
git add backend/app/main.py backend/app/notion_sync.py backend/tests/test_notion_sync.py
git commit -m "feat: integrate category_id in record/finalize/export-notion + enhance notion_sync markdown support"
```

---

### Task 4: Frontend — 타입 정의 + CategorySelect 컴포넌트

**Files:**
- Modify: `frontend/types/index.ts`
- Create: `frontend/components/CategorySelect.tsx`

**Interfaces:**
- Produces: `Category` interface, `Job.category_id`, `Job.category_icon`, `Job.category_name`
- Produces: `<CategorySelect value={string} onChange={(id: string) => void} className?: string />`

- [ ] **Step 1: `frontend/types/index.ts` 수정**

```typescript
export type JobStatus =
  | 'pending'
  | 'converting'
  | 'diarizing'
  | 'transcribing'
  | 'awaiting_edit'
  | 'summarizing'
  | 'done'
  | 'error'

export interface Category {
  id: string
  name: string
  icon: string
  description: string
  prompt: string
  is_builtin: number
  sort_order: number
}

export interface Job {
  id: string
  title: string
  filename: string
  status: JobStatus
  created_at: string
  duration_sec?: number
  transcript?: string
  summary?: string
  speakers?: Record<string, string>
  error_msg?: string
  notion_url?: string
  notion_page_id?: string
  category_id?: string
  category_icon?: string
  category_name?: string
}

export interface ProgressEvent {
  stage: string
  progress: number
  message: string
  transcript?: string
  speakers?: string[]
  suggested_names?: Record<string, string>
}

export interface SettingsStatus {
  HF_TOKEN: { set: boolean; preview: string | null }
  NOTION_API_KEY: { set: boolean; preview: string | null }
  NOTION_DATABASE_ID: { set: boolean; preview: string | null }
}

export interface ClaudeStatus {
  installed: boolean
  logged_in: boolean
  email?: string
  auth_method?: string
  subscription_type?: string
}
```

- [ ] **Step 2: `frontend/components/CategorySelect.tsx` 생성**

```tsx
'use client'
import { useState, useEffect } from 'react'
import { Category } from '@/types'

interface Props {
  value: string
  onChange: (id: string) => void
  className?: string
}

export default function CategorySelect({ value, onChange, className = '' }: Props) {
  const [categories, setCategories] = useState<Category[]>([])

  useEffect(() => {
    fetch('/api/categories')
      .then(r => r.json())
      .then(setCategories)
      .catch(() => {})
  }, [])

  if (categories.length === 0) return null

  return (
    <select
      value={value}
      onChange={e => onChange(e.target.value)}
      className={`px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent ${className}`}
    >
      {categories.map(cat => (
        <option key={cat.id} value={cat.id} title={cat.description}>
          {cat.icon} {cat.name}
        </option>
      ))}
    </select>
  )
}
```

- [ ] **Step 3: 커밋**

```bash
git add frontend/types/index.ts frontend/components/CategorySelect.tsx
git commit -m "feat: add Category type and CategorySelect component"
```

---

### Task 5: Frontend — RecordingZone + TranscriptEditor

**Files:**
- Modify: `frontend/components/RecordingZone.tsx`
- Modify: `frontend/components/TranscriptEditor.tsx`

**Interfaces:**
- Consumes: `<CategorySelect value onChange />` from CategorySelect.tsx
- RecordingZone: `POST /api/record` FormData에 `category_id` field 추가
- TranscriptEditor: props에 `initialCategoryId?: string` 추가, `POST /api/jobs/{id}/finalize` body에 `category_id` 추가

- [ ] **Step 1: `RecordingZone.tsx` 수정**

파일 상단 import에 추가:
```tsx
import CategorySelect from './CategorySelect'
```

컴포넌트 상태에 `categoryId` 추가 (localStorage 연동):
```tsx
const CATEGORY_KEY = 'meeting-jr-last-category'

export default function RecordingZone({ onRecordingComplete }: Props) {
  // ... 기존 상태들 ...
  const [categoryId, setCategoryId] = useState<string>(() => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem(CATEGORY_KEY) || 'meeting'
    }
    return 'meeting'
  })

  const handleCategoryChange = (id: string) => {
    setCategoryId(id)
    localStorage.setItem(CATEGORY_KEY, id)
  }
  // ...
```

`uploadRecording` 함수에 category_id 추가:
```tsx
const uploadRecording = async (blob: Blob) => {
  setUploading(true)
  const formData = new FormData()
  formData.append('audio', blob, 'recording.webm')
  formData.append('category_id', categoryId)
  try {
    const res = await fetch('/api/record', { method: 'POST', body: formData })
    const data = await res.json()
    setUploadDone(true)
    onRecordingComplete(data.job_id)
  } catch {
    alert('업로드 실패. 다시 시도해주세요.')
  } finally {
    setUploading(false)
  }
}
```

RecordingZone의 녹음 버튼 영역 바로 위에 CategorySelect 추가 (return 내부, `!isRecording && !audioBlob` 조건 블록 상단):
```tsx
{!isRecording && !audioBlob && (
  <>
    <div className="mb-4">
      <CategorySelect
        value={categoryId}
        onChange={handleCategoryChange}
        className="w-full"
      />
    </div>
    <button onClick={startRecording} className="w-16 h-16 rounded-full bg-red-500 hover:bg-red-600 text-white flex items-center justify-center mx-auto mb-4 transition-colors shadow-lg">
      <span className="w-5 h-5 rounded-full bg-white" />
    </button>
    <p className="text-sm text-gray-400">버튼을 눌러 녹음을 시작하세요</p>
  </>
)}
```

- [ ] **Step 2: `TranscriptEditor.tsx` 수정**

Props 인터페이스에 `initialCategoryId` 추가:
```tsx
interface Props {
  jobId: string
  initialTranscript: string
  initialSpeakers: string[]
  suggestedNames: Record<string, string>
  initialCategoryId?: string
  onComplete: () => void
}
```

컴포넌트에 `categoryId` 상태 추가:
```tsx
import CategorySelect from './CategorySelect'

export default function TranscriptEditor({
  jobId,
  initialTranscript,
  initialSpeakers,
  suggestedNames,
  initialCategoryId = 'meeting',
  onComplete,
}: Props) {
  // ... 기존 상태들 ...
  const [categoryId, setCategoryId] = useState(initialCategoryId)
```

`handleSubmit` 함수에 `category_id` 추가:
```tsx
const handleSubmit = async () => {
  setSubmitting(true)
  const speaker_map: Record<string, string> = {}
  speakers.forEach(s => { speaker_map[s] = names[s] || s })
  const transcript = serialize(lines, names)
  try {
    await fetch(`/api/jobs/${jobId}/finalize`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ transcript, speaker_map, category_id: categoryId }),
    })
    onComplete()
  } catch {
    alert('오류가 발생했습니다.')
  } finally {
    setSubmitting(false)
  }
}
```

하단 버튼 영역에 CategorySelect 추가 (버튼 위):
```tsx
{/* ── 하단 버튼 ── */}
<div className="px-4 py-3 border-t bg-white flex-shrink-0 space-y-2">
  <div className="flex items-center gap-2">
    <span className="text-xs text-gray-500 flex-shrink-0">카테고리:</span>
    <CategorySelect value={categoryId} onChange={setCategoryId} className="flex-1" />
  </div>
  <button
    onClick={handleSubmit}
    disabled={submitting}
    className="w-full py-2.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg font-medium text-sm transition-colors"
  >
    {submitting ? '처리 중...' : '문서 생성'}
  </button>
</div>
```

- [ ] **Step 3: `MainArea.tsx`에서 TranscriptEditor에 `initialCategoryId` 전달**

MainArea.tsx의 두 TranscriptEditor 사용 부분에 `initialCategoryId` 추가:

```tsx
// editData 기반 (line ~186)
<TranscriptEditor
  jobId={job.id}
  initialTranscript={editData.transcript}
  initialSpeakers={editData.speakers}
  suggestedNames={editData.suggestedNames}
  initialCategoryId={job.category_id || 'meeting'}
  onComplete={() => { setEditData(null); onJobsChange() }}
/>

// job.transcript 기반 (line ~197)
<TranscriptEditor
  jobId={job.id}
  initialTranscript={job.transcript}
  initialSpeakers={Object.keys(job.speakers || {})}
  suggestedNames={job.speakers || {}}
  initialCategoryId={job.category_id || 'meeting'}
  onComplete={() => { setEditData(null); onJobsChange() }}
/>
```

- [ ] **Step 4: 커밋**

```bash
git add frontend/components/RecordingZone.tsx frontend/components/TranscriptEditor.tsx frontend/components/MainArea.tsx
git commit -m "feat: add category selection to RecordingZone and TranscriptEditor"
```

---

### Task 6: Frontend — MainArea 카테고리 뱃지 + 재요약 모달

**Files:**
- Modify: `frontend/components/MainArea.tsx`

**Interfaces:**
- Consumes: `job.category_id`, `job.category_icon`, `job.category_name` from Job type
- Consumes: `<CategorySelect />` component
- 카테고리 뱃지: done 화면 제목 오른쪽에 `{icon} {name}` span 표시
- 재요약 클릭 → 모달에서 카테고리 선택 후 `handleResummarize(categoryId)` 호출

**Note:** `job.category_icon` / `job.category_name`은 백엔드 `GET /api/jobs/{id}` 응답에 포함되지 않는다. 대신 `job.category_id`를 사용해 프론트에서 `/api/categories` 데이터를 참조한다. 구현을 단순화하기 위해 별도 fetch 없이 CategorySelect 내부에서 이미 로드한 카테고리 목록을 활용한다.

- [ ] **Step 1: MainArea.tsx 수정**

파일 상단에 import 추가:
```tsx
import CategorySelect from './CategorySelect'
import { Category } from '@/types'
```

상태 추가:
```tsx
const [showResummarizeModal, setShowResummarizeModal] = useState(false)
const [resummarizeCategory, setResummarizeCategory] = useState<string>('meeting')
const [categories, setCategories] = useState<Category[]>([])
```

카테고리 목록 로드 (useEffect 추가):
```tsx
useEffect(() => {
  fetch('/api/categories').then(r => r.json()).then(setCategories).catch(() => {})
}, [])
```

job 변경 시 resummarizeCategory 초기화:
```tsx
useEffect(() => {
  setIsEditingTranscript(false)
  setLocalTranscript('')
  setNotionUrl(job?.notion_url ?? null)
  setResummarizeCategory(job?.category_id || 'meeting')
}, [job?.id])
```

`handleResummarize` 시그니처 변경 (categoryId 파라미터 추가):
```tsx
const handleResummarize = async (categoryId?: string) => {
  if (!job) return
  setResummaryLoading(true)
  try {
    const speaker_map = job.speakers || {}
    await fetch(`/api/jobs/${job.id}/finalize`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        transcript: localTranscript || job.transcript,
        speaker_map,
        category_id: categoryId || job.category_id || 'meeting',
      }),
    })
    setIsEditingTranscript(false)
    setLocalTranscript('')
    setShowResummarizeModal(false)
    onJobsChange()
  } catch {
    alert('재요약 요청에 실패했습니다.')
  } finally {
    setResummaryLoading(false)
  }
}
```

기존 재요약 버튼 클릭 핸들러를 모달 오픈으로 변경:
```tsx
// 기존: onClick={handleResummarize}
// 변경: onClick={() => { setResummarizeCategory(job?.category_id || 'meeting'); setShowResummarizeModal(true) }}
<button
  onClick={() => { setResummarizeCategory(job?.category_id || 'meeting'); setShowResummarizeModal(true) }}
  disabled={resummaryLoading}
  className="text-xs px-3 py-1 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-md font-medium transition-colors"
>
  {resummaryLoading ? '처리 중...' : '재요약'}
</button>
```

done 화면 헤더 제목 옆에 카테고리 뱃지 추가. `job?.category_id`를 참조해 categories에서 찾는다.

`renderContent`의 done 조건 블록 밖, 헤더(h1) 오른쪽 영역에 뱃지를 추가:

```tsx
{job && status === 'done' && (() => {
  const cat = categories.find(c => c.id === (job.category_id || 'meeting'))
  return cat ? (
    <span className="text-xs px-2 py-0.5 bg-gray-100 text-gray-600 rounded-full flex-shrink-0">
      {cat.icon} {cat.name}
    </span>
  ) : null
})()}
```

구체적으로, 헤더 `h1` 태그 뒤, Notion 버튼 앞에 다음 코드 삽입:

```tsx
{job.status === 'done' && (() => {
  const cat = categories.find(c => c.id === (job.category_id || 'meeting'))
  return cat ? (
    <span className="hidden md:inline-flex text-xs px-2 py-0.5 bg-gray-100 text-gray-600 rounded-full flex-shrink-0 items-center gap-1">
      {cat.icon} {cat.name}
    </span>
  ) : null
})()}
```

재요약 모달 추가 (Notion confirm 모달 바로 앞에):
```tsx
{showResummarizeModal && (
  <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
    <div className="bg-white rounded-xl shadow-xl p-6 w-80 space-y-4">
      <h3 className="font-semibold text-gray-800">재요약 카테고리 선택</h3>
      <p className="text-sm text-gray-500">재요약에 사용할 카테고리를 선택하세요.</p>
      <CategorySelect
        value={resummarizeCategory}
        onChange={setResummarizeCategory}
        className="w-full"
      />
      <div className="flex flex-col gap-2">
        <button
          onClick={() => handleResummarize(resummarizeCategory)}
          disabled={resummaryLoading}
          className="w-full py-2 px-4 bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white rounded-lg text-sm font-medium"
        >
          {resummaryLoading ? '처리 중...' : '재요약 실행'}
        </button>
        <button
          onClick={() => setShowResummarizeModal(false)}
          className="w-full py-2 text-sm text-gray-400 hover:text-gray-600"
        >
          취소
        </button>
      </div>
    </div>
  </div>
)}
```

- [ ] **Step 2: 커밋**

```bash
git add frontend/components/MainArea.tsx
git commit -m "feat: add category badge and resummarize category modal to MainArea"
```

---

### Task 7: Frontend — SettingsModal 카테고리 탭

**Files:**
- Modify: `frontend/components/SettingsModal.tsx`

**Interfaces:**
- 탭 구성: `일반` | `Claude` | `카테고리`
- 카테고리 목록: GET /api/categories
- 편집 패널: 인라인 펼침, 저장 PATCH, 삭제 DELETE, 초기화 POST /reset
- 새 카테고리 추가: POST /api/categories

- [ ] **Step 1: SettingsModal.tsx 전체 수정**

기존 SettingsModal.tsx를 탭 기반으로 리팩터링한다. 기존 내용을 `일반` 탭과 `Claude` 탭으로 분리하고 `카테고리` 탭을 추가한다.

파일 상단에 import 추가:
```tsx
import { Category } from '@/types'
```

탭 상태 추가:
```tsx
type Tab = 'general' | 'claude' | 'categories'
const [activeTab, setActiveTab] = useState<Tab>('general')
```

카테고리 관련 상태 추가:
```tsx
const [categories, setCategories] = useState<Category[]>([])
const [editingCatId, setEditingCatId] = useState<string | null>(null)
const [editCatForm, setEditCatForm] = useState({ name: '', icon: '', description: '', prompt: '' })
const [catSaving, setCatSaving] = useState(false)
const [showNewCatForm, setShowNewCatForm] = useState(false)
const [newCatForm, setNewCatForm] = useState({ name: '', icon: '📋', description: '', prompt: '{script}' })
```

카테고리 로드 함수:
```tsx
const loadCategories = () => {
  fetch('/api/categories').then(r => r.json()).then(setCategories).catch(() => {})
}
```

useEffect에 `loadCategories()` 추가:
```tsx
useEffect(() => {
  // 기존 fetch들...
  loadCategories()
}, [])
```

카테고리 탭 핸들러 함수들:
```tsx
const handleEditCat = (cat: Category) => {
  setEditingCatId(cat.id)
  setEditCatForm({ name: cat.name, icon: cat.icon, description: cat.description, prompt: cat.prompt })
  setShowNewCatForm(false)
}

const handleSaveCat = async (catId: string) => {
  if (!editCatForm.prompt.includes('{script}')) {
    alert("프롬프트에 {script} 플레이스홀더가 필요합니다.")
    return
  }
  setCatSaving(true)
  try {
    await fetch(`/api/categories/${catId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(editCatForm),
    })
    setEditingCatId(null)
    loadCategories()
  } catch {
    alert('저장 실패')
  } finally {
    setCatSaving(false)
  }
}

const handleDeleteCat = async (catId: string) => {
  if (!confirm('이 카테고리를 삭제하시겠습니까?')) return
  await fetch(`/api/categories/${catId}`, { method: 'DELETE' })
  setEditingCatId(null)
  loadCategories()
}

const handleResetCatPrompt = async (catId: string) => {
  const res = await fetch(`/api/categories/${catId}/reset`, { method: 'POST' })
  const data = await res.json()
  setEditCatForm(prev => ({ ...prev, prompt: data.prompt }))
}

const handleCreateCat = async () => {
  if (!newCatForm.name.trim()) { alert('이름을 입력하세요.'); return }
  if (!newCatForm.prompt.includes('{script}')) {
    alert("프롬프트에 {script} 플레이스홀더가 필요합니다.")
    return
  }
  setCatSaving(true)
  try {
    await fetch('/api/categories', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(newCatForm),
    })
    setNewCatForm({ name: '', icon: '📋', description: '', prompt: '{script}' })
    setShowNewCatForm(false)
    loadCategories()
  } catch {
    alert('생성 실패')
  } finally {
    setCatSaving(false)
  }
}
```

모달 JSX 구조를 탭 기반으로 변경. 헤더 아래에 탭 바 추가:
```tsx
{/* 탭 바 */}
<div className="flex border-b px-2">
  {([['general', '일반'], ['claude', 'Claude'], ['categories', '카테고리']] as [Tab, string][]).map(([id, label]) => (
    <button
      key={id}
      onClick={() => setActiveTab(id)}
      className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
        activeTab === id
          ? 'border-blue-600 text-blue-600'
          : 'border-transparent text-gray-500 hover:text-gray-700'
      }`}
    >
      {label}
    </button>
  ))}
</div>
```

본문 영역을 탭별로 분기:
```tsx
<div className="px-6 py-5 overflow-y-auto max-h-[60vh]">
  {activeTab === 'general' && (
    <div className="space-y-5">
      {/* 기본 회의 제목 섹션 — 기존 코드 그대로 */}
      {/* Claude CLI 섹션 — 기존 코드 그대로 */}
      {/* API 키 섹션 — 기존 코드 그대로 */}
    </div>
  )}

  {activeTab === 'claude' && (
    <div className="space-y-5">
      {/* 모델 선택 — 기존 코드 그대로 */}
      {/* 프롬프트 커스터마이징 — 기존 코드 그대로 */}
    </div>
  )}

  {activeTab === 'categories' && (
    <div className="space-y-3">
      {categories.map(cat => (
        <div key={cat.id} className="border border-gray-200 rounded-lg overflow-hidden">
          {/* 카테고리 헤더 행 */}
          <div className="flex items-center justify-between px-3 py-2 bg-gray-50">
            <div className="flex items-center gap-2">
              <span className="text-lg">{cat.icon}</span>
              <div>
                <span className="text-sm font-medium text-gray-800">{cat.name}</span>
                {cat.description && (
                  <p className="text-xs text-gray-400">{cat.description}</p>
                )}
              </div>
              {cat.is_builtin === 1 && (
                <span className="text-xs px-1.5 py-0.5 bg-blue-50 text-blue-600 rounded">내장</span>
              )}
            </div>
            <div className="flex items-center gap-1">
              <button
                onClick={() => editingCatId === cat.id ? setEditingCatId(null) : handleEditCat(cat)}
                className="text-xs px-2.5 py-1 border rounded hover:bg-white text-gray-600 transition-colors"
              >
                {editingCatId === cat.id ? '접기' : '편집'}
              </button>
              {cat.is_builtin === 0 && (
                <button
                  onClick={() => handleDeleteCat(cat.id)}
                  className="text-xs px-2.5 py-1 border border-red-200 rounded hover:bg-red-50 text-red-500 transition-colors"
                >
                  삭제
                </button>
              )}
            </div>
          </div>

          {/* 편집 패널 — 인라인 펼침 */}
          {editingCatId === cat.id && (
            <div className="p-3 space-y-2 border-t bg-white">
              <div className="flex gap-2">
                <input
                  type="text"
                  value={editCatForm.icon}
                  onChange={e => setEditCatForm(p => ({ ...p, icon: e.target.value }))}
                  placeholder="아이콘"
                  className="w-16 px-2 py-1.5 border rounded text-sm text-center"
                />
                <input
                  type="text"
                  value={editCatForm.name}
                  onChange={e => setEditCatForm(p => ({ ...p, name: e.target.value }))}
                  placeholder="이름"
                  className="flex-1 px-2 py-1.5 border rounded text-sm"
                />
              </div>
              <input
                type="text"
                value={editCatForm.description}
                onChange={e => setEditCatForm(p => ({ ...p, description: e.target.value }))}
                placeholder="설명 (선택)"
                className="w-full px-2 py-1.5 border rounded text-sm"
              />
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-xs text-gray-500">프롬프트</label>
                  {cat.is_builtin === 1 && (
                    <button
                      onClick={() => handleResetCatPrompt(cat.id)}
                      className="text-xs text-gray-400 hover:text-blue-600 transition-colors"
                    >
                      기본값으로 초기화
                    </button>
                  )}
                </div>
                <textarea
                  value={editCatForm.prompt}
                  onChange={e => setEditCatForm(p => ({ ...p, prompt: e.target.value }))}
                  rows={8}
                  className="w-full px-2 py-1.5 border rounded text-xs font-mono focus:outline-none focus:ring-1 focus:ring-blue-500 resize-y"
                  placeholder="{script} 위치에 스크립트가 삽입됩니다."
                />
              </div>
              <button
                onClick={() => handleSaveCat(cat.id)}
                disabled={catSaving}
                className="w-full py-1.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded text-sm font-medium transition-colors"
              >
                {catSaving ? '저장 중...' : '저장'}
              </button>
            </div>
          )}
        </div>
      ))}

      {/* 새 카테고리 추가 */}
      {showNewCatForm ? (
        <div className="border border-dashed border-gray-300 rounded-lg p-3 space-y-2 bg-gray-50">
          <div className="flex gap-2">
            <input
              type="text"
              value={newCatForm.icon}
              onChange={e => setNewCatForm(p => ({ ...p, icon: e.target.value }))}
              placeholder="아이콘"
              className="w-16 px-2 py-1.5 border rounded text-sm text-center bg-white"
            />
            <input
              type="text"
              value={newCatForm.name}
              onChange={e => setNewCatForm(p => ({ ...p, name: e.target.value }))}
              placeholder="이름"
              className="flex-1 px-2 py-1.5 border rounded text-sm bg-white"
            />
          </div>
          <input
            type="text"
            value={newCatForm.description}
            onChange={e => setNewCatForm(p => ({ ...p, description: e.target.value }))}
            placeholder="설명 (선택)"
            className="w-full px-2 py-1.5 border rounded text-sm bg-white"
          />
          <textarea
            value={newCatForm.prompt}
            onChange={e => setNewCatForm(p => ({ ...p, prompt: e.target.value }))}
            rows={6}
            className="w-full px-2 py-1.5 border rounded text-xs font-mono focus:outline-none focus:ring-1 focus:ring-blue-500 resize-y bg-white"
            placeholder="{script} 위치에 스크립트가 삽입됩니다."
          />
          <div className="flex gap-2">
            <button
              onClick={handleCreateCat}
              disabled={catSaving}
              className="flex-1 py-1.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded text-sm font-medium"
            >
              {catSaving ? '생성 중...' : '추가'}
            </button>
            <button
              onClick={() => setShowNewCatForm(false)}
              className="px-3 py-1.5 border rounded text-sm text-gray-600 hover:bg-gray-100"
            >
              취소
            </button>
          </div>
        </div>
      ) : (
        <button
          onClick={() => { setShowNewCatForm(true); setEditingCatId(null) }}
          className="w-full py-2 border border-dashed border-gray-300 rounded-lg text-sm text-gray-500 hover:bg-gray-50 hover:border-gray-400 transition-colors"
        >
          + 새 카테고리 추가
        </button>
      )}
    </div>
  )}
</div>
```

푸터 저장 버튼 조건 (카테고리 탭에서는 숨김):
```tsx
{activeTab !== 'categories' && (
  <div className="flex justify-end gap-3 px-6 py-4 border-t bg-gray-50 rounded-b-xl">
    {/* 기존 취소/저장 버튼 */}
  </div>
)}
{activeTab === 'categories' && (
  <div className="flex justify-end px-6 py-4 border-t bg-gray-50 rounded-b-xl">
    <button onClick={onClose} className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800 font-medium">
      닫기
    </button>
  </div>
)}
```

- [ ] **Step 2: 커밋**

```bash
git add frontend/components/SettingsModal.tsx
git commit -m "feat: add categories tab to SettingsModal with CRUD"
```

---

### Task 8: PROGRESS.md 갱신 + 전체 검증

**Files:**
- Modify: `PROGRESS.md`

- [ ] **Step 1: 백엔드 서버 실행 후 API 수동 테스트**

```bash
# 터미널 1: 백엔드
cd /Users/liche/Documents/dev/meeting-jr/backend
/opt/homebrew/bin/python3.11 -m uvicorn app.main:app --reload --port 8000

# 터미널 2: API 테스트
curl http://localhost:8000/api/categories | python3 -m json.tool
# Expected: 5개 내장 카테고리 목록

curl -X POST http://localhost:8000/api/categories \
  -H "Content-Type: application/json" \
  -d '{"name":"테스트","icon":"🧪","description":"테스트","prompt":"요약\n{script}"}' | python3 -m json.tool
# Expected: 새 카테고리 반환
```

- [ ] **Step 2: 프론트엔드 실행 + 시각적 확인**

```bash
# 터미널 3: 프론트엔드
cd /Users/liche/Documents/dev/meeting-jr/frontend
npm run dev
```

브라우저 `http://localhost:3000` 에서 확인:
- [ ] RecordingZone에 카테고리 드롭다운 표시
- [ ] 카테고리 선택 후 녹음 → 업로드 시 category_id 전송됨
- [ ] 설정 모달 → 카테고리 탭 표시, 5개 내장 카테고리 목록
- [ ] 내장 카테고리 편집 가능, 삭제 버튼 비활성
- [ ] 새 카테고리 추가 동작

- [ ] **Step 3: 전체 백엔드 테스트 최종 확인**

```bash
cd /Users/liche/Documents/dev/meeting-jr/backend
/opt/homebrew/bin/python3.11 -m pytest tests/ -v
```
Expected: 전체 PASS

- [ ] **Step 4: PROGRESS.md 갱신**

```markdown
## 2026-08-23 (작업 PC: 로컬) — 세션 4
- 브랜치: main
- 완료: 카테고리 시스템 전체 구현
- 현재 상태: 서버 재시작 필요 (코드 변경), 기능 정상
- 다음 할 일: 서버 재시작 후 전체 기능 테스트
- 구현 내용:
  - backend/app/categories.py: DEFAULT_PROMPTS 5개 + BUILTIN_CATEGORIES + seed_categories()
  - backend/app/database.py: categories 테이블 CRUD + _migrate에 category_id 추가 + create_job 시그니처 변경
  - backend/app/main.py: 카테고리 API 5개 엔드포인트 + record/finalize/run_summary/export_notion 수정
  - backend/app/notion_sync.py: table/numbered_list/quote/bold 지원 + 카테고리 헤더 추가
  - frontend/types/index.ts: Category 타입 + Job에 category 필드
  - frontend/components/CategorySelect.tsx: 공통 드롭다운
  - frontend/components/RecordingZone.tsx: 카테고리 선택 (localStorage 연동)
  - frontend/components/TranscriptEditor.tsx: 카테고리 선택 + finalize body에 category_id
  - frontend/components/MainArea.tsx: 카테고리 뱃지 + 재요약 카테고리 모달
  - frontend/components/SettingsModal.tsx: 일반/Claude/카테고리 탭 구조 + 카테고리 CRUD
- 관련 커밋: (이전 커밋들)
- 푸시 여부: 미푸시
```

- [ ] **Step 5: 최종 커밋**

```bash
git add PROGRESS.md
git commit -m "docs: update PROGRESS.md for category system implementation"
```
