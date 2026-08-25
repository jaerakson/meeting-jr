"""
SQLite 기반 Job 영속성 관리.
DB 파일: backend/meetings.db
표준 sqlite3 모듈 사용 (동기 함수).
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

DB_PATH = Path(__file__).resolve().parent.parent / "meetings.db"

# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------

def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _row_to_dict(row: sqlite3.Row) -> dict:
    """sqlite3.Row -> dict 변환. speakers/action_items JSON 문자열은 파싱."""
    d = dict(row)
    if d.get("speakers"):
        try:
            d["speakers"] = json.loads(d["speakers"])
        except (json.JSONDecodeError, TypeError):
            d["speakers"] = {}
    else:
        d["speakers"] = {}
    if d.get("action_items"):
        try:
            d["action_items"] = json.loads(d["action_items"])
        except (json.JSONDecodeError, TypeError):
            d["action_items"] = []
    else:
        d["action_items"] = []
    if d.get("tags"):
        try:
            d["tags"] = json.loads(d["tags"])
        except (json.JSONDecodeError, TypeError):
            d["tags"] = []
    else:
        d["tags"] = []
    return d


# ---------------------------------------------------------------------------
# 초기화
# ---------------------------------------------------------------------------

def _migrate(conn: sqlite3.Connection) -> None:
    """기존 DB에 누락된 컬럼을 추가한다."""
    existing = {row[1] for row in conn.execute("PRAGMA table_info(meetings)")}
    for col, definition in [
        ("notion_url", "TEXT"),
        ("notion_page_id", "TEXT"),
        ("category_id", "TEXT"),
        ("language", "TEXT"),
        ("action_items", "TEXT"),
        ("bookmarked", "INTEGER NOT NULL DEFAULT 0"),
        ("memo", "TEXT"),
        ("tags", "TEXT"),
    ]:
        if col not in existing:
            conn.execute(f"ALTER TABLE meetings ADD COLUMN {col} {definition}")
    conn.commit()


def init_db() -> None:
    """meetings/categories 테이블이 없으면 생성한다. 앱 시작 시 호출."""
    from .categories import seed_categories
    conn = _get_conn()
    try:
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


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

def create_job(
    job_id: str,
    filename: str,
    title: Optional[str] = None,
    category_id: Optional[str] = None,
    language: Optional[str] = "ko",
) -> dict:
    """새 Job 레코드를 생성하고 dict로 반환."""
    now = datetime.now(timezone.utc).isoformat()
    conn = _get_conn()
    try:
        conn.execute(
            """
            INSERT INTO meetings (id, title, filename, status, created_at, category_id, language)
            VALUES (?, ?, ?, 'pending', ?, ?, ?)
            """,
            (job_id, title or filename, filename, now, category_id, language),
        )
        conn.commit()
        return get_job(job_id)
    finally:
        conn.close()


def get_job(job_id: str) -> Optional[dict]:
    """job_id로 단일 Job 조회. 없으면 None."""
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM meetings WHERE id = ?", (job_id,)
        ).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def get_all_jobs() -> list[dict]:
    """전체 Job 목록을 북마크 우선, 최신순으로 반환."""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM meetings ORDER BY bookmarked DESC, created_at DESC"
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def update_job_status(
    job_id: str,
    status: str,
    error_msg: Optional[str] = None,
) -> None:
    """Job 상태를 변경한다. error_msg가 주어지면 함께 갱신."""
    conn = _get_conn()
    try:
        if error_msg is not None:
            conn.execute(
                "UPDATE meetings SET status = ?, error_msg = ? WHERE id = ?",
                (status, error_msg, job_id),
            )
        else:
            conn.execute(
                "UPDATE meetings SET status = ? WHERE id = ?",
                (status, job_id),
            )
        conn.commit()
    finally:
        conn.close()


def update_job_result(
    job_id: str,
    *,
    transcript: Optional[str] = None,
    summary: Optional[str] = None,
    speakers: Optional[dict] = None,
    duration_sec: Optional[int] = None,
    status: Optional[str] = None,
) -> None:
    """처리 결과 필드를 선택적으로 갱신한다."""
    fields: list[str] = []
    values: list = []

    if transcript is not None:
        fields.append("transcript = ?")
        values.append(transcript)
    if summary is not None:
        fields.append("summary = ?")
        values.append(summary)
    if speakers is not None:
        fields.append("speakers = ?")
        values.append(json.dumps(speakers, ensure_ascii=False))
    if duration_sec is not None:
        fields.append("duration_sec = ?")
        values.append(duration_sec)
    if status is not None:
        fields.append("status = ?")
        values.append(status)

    if not fields:
        return

    values.append(job_id)
    conn = _get_conn()
    try:
        conn.execute(
            f"UPDATE meetings SET {', '.join(fields)} WHERE id = ?",
            values,
        )
        conn.commit()
    finally:
        conn.close()


def update_job_notion(job_id: str, notion_url: str, notion_page_id: str) -> None:
    """Notion 내보내기 결과(URL, page_id)를 저장한다."""
    conn = _get_conn()
    try:
        conn.execute(
            "UPDATE meetings SET notion_url = ?, notion_page_id = ? WHERE id = ?",
            (notion_url, notion_page_id, job_id),
        )
        conn.commit()
    finally:
        conn.close()


def update_job_title(job_id: str, title: str) -> None:
    """회의 제목을 변경한다."""
    conn = _get_conn()
    try:
        conn.execute(
            "UPDATE meetings SET title = ? WHERE id = ?",
            (title, job_id),
        )
        conn.commit()
    finally:
        conn.close()


def delete_job(job_id: str) -> bool:
    """Job 레코드를 삭제한다. 삭제 성공 시 True."""
    conn = _get_conn()
    try:
        cursor = conn.execute(
            "DELETE FROM meetings WHERE id = ?", (job_id,)
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def _extract_snippet(text: str, query: str, length: int = 100) -> str:
    """검색어 주변 텍스트 스니펫 추출."""
    if not text or not query:
        return ""
    idx = text.lower().find(query.lower())
    if idx == -1:
        return ""
    start = max(0, idx - 40)
    end = min(len(text), idx + len(query) + 60)
    snippet = text[start:end]
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."
    return snippet


def search_jobs(
    q: str = "",
    page: int = 1,
    limit: int = 12,
    category_id: str = "",
    date_from: str = "",
    date_to: str = "",
    tag: str = "",
) -> dict:
    """제목+요약+스크립트 LIKE 검색 + 카테고리/날짜 필터 + 페이지네이션.

    반환: {"items": list[dict], "total": int, "page": int, "pages": int}
    """
    if page < 1:
        page = 1
    offset = (page - 1) * limit
    conn = _get_conn()
    try:
        conditions: list[str] = []
        params: list = []

        if q:
            conditions.append("(title LIKE ? OR summary LIKE ? OR transcript LIKE ?)")
            pattern = f"%{q}%"
            params.extend([pattern, pattern, pattern])

        if category_id:
            conditions.append("category_id = ?")
            params.append(category_id)

        if date_from:
            # DATE() 함수로 ISO 8601 timezone suffix 무관하게 날짜만 비교
            conditions.append("DATE(created_at) >= ?")
            params.append(date_from[:10])

        if date_to:
            conditions.append("DATE(created_at) <= ?")
            params.append(date_to[:10])

        if tag:
            conditions.append("tags LIKE ?")
            params.append(f'%"{tag}"%')

        where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        rows = conn.execute(
            f"SELECT * FROM meetings {where_clause} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()
        total: int = conn.execute(
            f"SELECT COUNT(*) FROM meetings {where_clause}",
            params,
        ).fetchone()[0]

        pages = max(1, (total + limit - 1) // limit)
        items = [_row_to_dict(r) for r in rows]

        # 검색어가 있을 때 snippet 추가
        if q:
            for item in items:
                snippet = (
                    _extract_snippet(item.get("title") or "", q)
                    or _extract_snippet(item.get("summary") or "", q)
                    or _extract_snippet(item.get("transcript") or "", q)
                )
                item["snippet"] = snippet

        return {
            "items": items,
            "total": total,
            "page": page,
            "pages": pages,
        }
    finally:
        conn.close()


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


def update_job_action_items(job_id: str, action_items: list[dict]) -> None:
    """action_items를 JSON으로 저장한다."""
    conn = _get_conn()
    try:
        conn.execute(
            "UPDATE meetings SET action_items = ? WHERE id = ?",
            (json.dumps(action_items, ensure_ascii=False), job_id),
        )
        conn.commit()
    finally:
        conn.close()


def toggle_bookmark(job_id: str) -> Optional[dict]:
    """bookmarked 값을 토글(0↔1)하고 갱신된 Job을 반환한다."""
    conn = _get_conn()
    try:
        conn.execute(
            "UPDATE meetings SET bookmarked = CASE WHEN bookmarked = 1 THEN 0 ELSE 1 END WHERE id = ?",
            (job_id,),
        )
        conn.commit()
        return get_job(job_id)
    finally:
        conn.close()


def update_job_memo(job_id: str, memo: str) -> Optional[dict]:
    """메모를 저장하고 갱신된 Job을 반환한다."""
    conn = _get_conn()
    try:
        conn.execute("UPDATE meetings SET memo = ? WHERE id = ?", (memo, job_id))
        conn.commit()
        return get_job(job_id)
    finally:
        conn.close()


def update_job_tags(job_id: str, tags: list[str]) -> Optional[dict]:
    """태그 목록을 JSON으로 저장하고 갱신된 Job을 반환한다."""
    conn = _get_conn()
    try:
        conn.execute(
            "UPDATE meetings SET tags = ? WHERE id = ?",
            (json.dumps(tags, ensure_ascii=False), job_id),
        )
        conn.commit()
        return get_job(job_id)
    finally:
        conn.close()


def get_all_tags() -> list[str]:
    """전체 사용된 태그 목록을 반환한다."""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT tags FROM meetings WHERE tags IS NOT NULL AND tags != ''"
        ).fetchall()
        tag_set: set[str] = set()
        for row in rows:
            try:
                parsed = json.loads(row[0])
                if isinstance(parsed, list):
                    tag_set.update(parsed)
            except (json.JSONDecodeError, TypeError):
                pass
        return sorted(tag_set)
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
