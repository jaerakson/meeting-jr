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
    """sqlite3.Row -> dict 변환.

    JSON 문자열로 저장된 컬럼(speakers/action_items/tags/suggested_speakers/diarization/
    followup_items/transcript_segments)은 파싱해서 돌려준다.
    """
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
    if d.get("suggested_speakers"):
        try:
            d["suggested_speakers"] = json.loads(d["suggested_speakers"])
        except (json.JSONDecodeError, TypeError):
            d["suggested_speakers"] = {}
    else:
        d["suggested_speakers"] = {}
    if d.get("diarization"):
        try:
            d["diarization"] = json.loads(d["diarization"])
        except (json.JSONDecodeError, TypeError):
            d["diarization"] = {}
    else:
        d["diarization"] = {}
    if d.get("transcript_segments"):
        try:
            d["transcript_segments"] = json.loads(d["transcript_segments"])
        except (json.JSONDecodeError, TypeError):
            d["transcript_segments"] = []
    else:
        d["transcript_segments"] = []
    if d.get("followup_items"):
        try:
            d["followup_items"] = json.loads(d["followup_items"])
        except (json.JSONDecodeError, TypeError):
            d["followup_items"] = None
    else:
        d["followup_items"] = None
    return d


# ---------------------------------------------------------------------------
# 초기화
# ---------------------------------------------------------------------------

def _migrate(conn: sqlite3.Connection) -> None:
    """기존 DB에 누락된 컬럼을 추가한다."""
    # categories 테이블에 model 컬럼 추가
    try:
        conn.execute("ALTER TABLE categories ADD COLUMN model TEXT DEFAULT 'claude-sonnet-4-6'")
    except sqlite3.OperationalError:
        pass  # 이미 존재

    # categories 테이블에 prompt_template 컬럼 추가
    try:
        conn.execute("ALTER TABLE categories ADD COLUMN prompt_template TEXT")
    except sqlite3.OperationalError:
        pass  # 이미 존재

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
        ("suggested_speakers", "TEXT"),
        ("rating", "INTEGER"),
        ("diarization", "TEXT"),
        ("share_token", "TEXT"),
        ("series_id", "TEXT"),
        ("followup_items", "TEXT"),
        ("transcript_segments", "TEXT"),
    ]:
        if col not in existing:
            conn.execute(f"ALTER TABLE meetings ADD COLUMN {col} {definition}")
    conn.commit()


def init_db() -> None:
    """meetings/categories/voice_profiles 테이블이 없으면 생성한다. 앱 시작 시 호출."""
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
                model       TEXT DEFAULT 'claude-sonnet-4-6',
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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS voice_profiles (
                id            TEXT PRIMARY KEY,
                name          TEXT NOT NULL,
                embedding     BLOB NOT NULL,
                embedding_dim INTEGER NOT NULL DEFAULT 192,
                sample_count  INTEGER NOT NULL DEFAULT 1,
                created_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
                updated_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS recording_notes (
                id         TEXT PRIMARY KEY,
                job_id     TEXT NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
                timestamp  REAL NOT NULL,
                content    TEXT,
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS meeting_series (
                id          TEXT PRIMARY KEY,
                name        TEXT NOT NULL,
                description TEXT DEFAULT '',
                created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
                updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
            )
        """)
        _migrate(conn)
        # categories 테이블 마이그레이션: model 컬럼
        cat_cols = {row[1] for row in conn.execute("PRAGMA table_info(categories)")}
        if "model" not in cat_cols:
            conn.execute("ALTER TABLE categories ADD COLUMN model TEXT DEFAULT 'claude-sonnet-4-6'")
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
    suggested_speakers: Optional[dict] = None,
    diarization: Optional[dict] = None,
    transcript_segments: Optional[list] = None,
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
        # speaker_map **값** 쓰기 정규화 — 이 관문 한 곳에서만 한다.
        # 값 앞뒤 공백 제거, 빈 값은 매핑에서 제외(빈 이름을 저장하지 않는다).
        #
        # **이 관문이 보장하는 것은 값 정규화뿐이다.** 호출부가 모두 여기를 지난다는
        # 사실은 "구멍이 없다"는 뜻이 아니다 — 관문을 **지나는 것**과 관문이 **옳은
        # 값을 받는 것**은 다르다. 실제로 빈 맵(`{}`)이 넘어와 speakers 전체를 덮어써
        # 회의의 화자 이름이 통째로 사라진 사고가 있었다(PR C). 맵 전체를 교체하는
        # 입력은 여기서 막지 못하므로, **요청 경계(body를 받는 엔드포인트)에서** 막는다.
        normalized = {
            k: v.strip() if isinstance(v, str) else v
            for k, v in speakers.items()
            if not isinstance(v, str) or v.strip()
        }
        fields.append("speakers = ?")
        values.append(json.dumps(normalized, ensure_ascii=False))
    if suggested_speakers is not None:
        fields.append("suggested_speakers = ?")
        values.append(json.dumps(suggested_speakers, ensure_ascii=False))
    if diarization is not None:
        fields.append("diarization = ?")
        values.append(json.dumps(diarization, ensure_ascii=False))
    if transcript_segments is not None:
        fields.append("transcript_segments = ?")
        values.append(json.dumps(transcript_segments, ensure_ascii=False))
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


def get_job_diarization(job_id: str) -> Optional[dict]:
    """job_id의 diarization 데이터만 경량 조회. 없으면 None."""
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT diarization FROM meetings WHERE id = ?", (job_id,)
        ).fetchone()
        if not row or not row[0]:
            return None
        try:
            return json.loads(row[0])
        except (json.JSONDecodeError, TypeError):
            return None
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

        # 검색어가 있을 때 snippet + snippet_source 추가
        if q:
            for item in items:
                title_snip = _extract_snippet(item.get("title") or "", q)
                summary_snip = _extract_snippet(item.get("summary") or "", q)
                transcript_snip = _extract_snippet(item.get("transcript") or "", q)
                if title_snip:
                    item["snippet"] = title_snip
                    item["snippet_source"] = "title"
                elif summary_snip:
                    item["snippet"] = summary_snip
                    item["snippet_source"] = "summary"
                elif transcript_snip:
                    item["snippet"] = transcript_snip
                    item["snippet_source"] = "transcript"
                else:
                    item["snippet"] = ""
                    item["snippet_source"] = ""

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
    model: str = "claude-sonnet-4-6",
    prompt_template: str = "",
) -> dict:
    """사용자 카테고리를 생성하고 반환."""
    conn = _get_conn()
    try:
        conn.execute(
            """
            INSERT INTO categories (id, name, icon, description, prompt, is_builtin, sort_order, model, prompt_template)
            VALUES (?, ?, ?, ?, ?, 0, 99, ?, ?)
            """,
            (cat_id, name, icon, description, prompt, model, prompt_template),
        )
        conn.commit()
        return get_category(cat_id)
    finally:
        conn.close()


def update_category(cat_id: str, **kwargs) -> Optional[dict]:
    """카테고리 필드를 선택적으로 갱신한다."""
    allowed = {"name", "icon", "description", "prompt", "model", "prompt_template"}
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


def get_all_action_items(
    assignee: str = "",
    done: str | None = None,
    page: int = 1,
    limit: int = 20,
) -> dict:
    """전체 회의의 액션 아이템을 통합 조회한다.

    Returns:
        {"items": list, "total": int, "page": int, "pages": int, "pending_count": int}
    """
    from math import ceil

    if page < 1:
        page = 1

    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT id, title, created_at, action_items FROM meetings "
            "WHERE action_items IS NOT NULL AND action_items != '' AND action_items != '[]'"
        ).fetchall()

        # 플랫 리스트 구성
        all_items: list[dict] = []
        for row in rows:
            try:
                items = json.loads(row["action_items"])
            except (json.JSONDecodeError, TypeError):
                continue
            if not isinstance(items, list):
                continue
            for item in items:
                all_items.append({
                    **item,
                    "job_id": row["id"],
                    "job_title": row["title"],
                    "job_created_at": row["created_at"],
                })

        # pending_count: 필터 무관 전체 미완료 건수
        pending_count = sum(1 for it in all_items if not it.get("done", False))

        # 전체 아이템(필터 전)에서 고유 assignee 목록 추출
        assignees = sorted(set(it.get("assignee", "") for it in all_items if it.get("assignee")))

        # 필터 적용
        filtered = all_items
        if assignee:
            filtered = [it for it in filtered if it.get("assignee") == assignee]
        if done == "false":
            filtered = [it for it in filtered if not it.get("done", False)]
        elif done == "true":
            filtered = [it for it in filtered if it.get("done", False)]

        # 정렬: 미완료 우선, 최신 회의 우선
        filtered.sort(key=lambda it: (
            it.get("done", False),  # False(0) < True(1) → 미완료 우선
            -(datetime.fromisoformat(it["job_created_at"]).timestamp()
              if it.get("job_created_at") else 0),
        ))

        total = len(filtered)
        pages = max(1, ceil(total / limit))
        offset = (page - 1) * limit
        paged = filtered[offset:offset + limit]

        return {
            "items": paged,
            "total": total,
            "page": page,
            "pages": pages,
            "pending_count": pending_count,
            "assignees": assignees,
        }
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


def update_job_rating(job_id: str, rating: int) -> None:
    """별점(1~5)을 저장한다."""
    conn = _get_conn()
    try:
        conn.execute(
            "UPDATE meetings SET rating = ? WHERE id = ?",
            (rating, job_id),
        )
        conn.commit()
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


# ---------------------------------------------------------------------------
# Voice Profiles CRUD
# ---------------------------------------------------------------------------

def get_voice_profiles() -> list[dict]:
    """모든 목소리 프로필 반환 (embedding 제외)."""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT id, name, embedding_dim, sample_count, created_at, updated_at "
            "FROM voice_profiles ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_voice_profile(profile_id: str) -> Optional[dict]:
    """단일 프로필 반환 (embedding 포함)."""
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM voice_profiles WHERE id = ?", (profile_id,)
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["embedding"] = bytes(d["embedding"])
        return d
    finally:
        conn.close()


def get_all_voice_profiles_with_embeddings() -> list[dict]:
    """모든 프로필을 embedding 포함하여 반환."""
    conn = _get_conn()
    try:
        rows = conn.execute("SELECT * FROM voice_profiles").fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["embedding"] = bytes(d["embedding"])
            result.append(d)
        return result
    finally:
        conn.close()


def create_voice_profile(name: str, embedding: bytes, embedding_dim: int) -> dict:
    """새 목소리 프로필 생성."""
    import uuid
    profile_id = str(uuid.uuid4())
    conn = _get_conn()
    try:
        conn.execute(
            """
            INSERT INTO voice_profiles (id, name, embedding, embedding_dim, sample_count)
            VALUES (?, ?, ?, ?, 1)
            """,
            (profile_id, name, embedding, embedding_dim),
        )
        conn.commit()
        return {
            "id": profile_id,
            "name": name,
            "embedding_dim": embedding_dim,
            "sample_count": 1,
        }
    finally:
        conn.close()


def update_voice_profile_embedding(
    profile_id: str, new_embedding: bytes, sample_count: int
) -> Optional[dict]:
    """embedding 업데이트 (샘플 추가 시)."""
    conn = _get_conn()
    try:
        conn.execute(
            """
            UPDATE voice_profiles
            SET embedding = ?, sample_count = ?,
                updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now')
            WHERE id = ?
            """,
            (new_embedding, sample_count, profile_id),
        )
        conn.commit()
        row = conn.execute(
            "SELECT id, name, embedding_dim, sample_count, created_at, updated_at "
            "FROM voice_profiles WHERE id = ?",
            (profile_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def rename_voice_profile(profile_id: str, name: str) -> Optional[dict]:
    """프로필 이름 변경."""
    conn = _get_conn()
    try:
        conn.execute(
            """
            UPDATE voice_profiles
            SET name = ?, updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now')
            WHERE id = ?
            """,
            (name, profile_id),
        )
        conn.commit()
        row = conn.execute(
            "SELECT id, name, embedding_dim, sample_count, created_at, updated_at "
            "FROM voice_profiles WHERE id = ?",
            (profile_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def delete_voice_profile(profile_id: str) -> bool:
    """프로필 삭제."""
    conn = _get_conn()
    try:
        cursor = conn.execute(
            "DELETE FROM voice_profiles WHERE id = ?", (profile_id,)
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def get_voice_profile_threshold() -> float:
    """매칭 임계값 설정 조회 (기본 0.75)."""
    from .settings_manager import get_setting
    val = get_setting("VOICE_MATCH_THRESHOLD")
    try:
        return float(val) if val else 0.75
    except (ValueError, TypeError):
        return 0.75


def set_voice_profile_threshold(threshold: float) -> None:
    """매칭 임계값 저장."""
    from .settings_manager import set_setting
    set_setting("VOICE_MATCH_THRESHOLD", str(threshold))


# ---------------------------------------------------------------------------
# Recording Notes CRUD
# ---------------------------------------------------------------------------

def save_recording_notes(job_id: str, notes: list[dict]) -> list[dict]:
    """녹음 중 메모/북마크 일괄 저장. notes: [{id, timestamp, content?}]"""
    conn = _get_conn()
    try:
        for note in notes:
            conn.execute(
                """
                INSERT OR REPLACE INTO recording_notes (id, job_id, timestamp, content)
                VALUES (?, ?, ?, ?)
                """,
                (note["id"], job_id, note["timestamp"], note.get("content", "")),
            )
        conn.commit()
        return get_recording_notes(job_id)
    finally:
        conn.close()


def get_recording_notes(job_id: str) -> list[dict]:
    """해당 job의 녹음 노트 목록 (timestamp 오름차순)."""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM recording_notes WHERE job_id = ? ORDER BY timestamp ASC",
            (job_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def delete_recording_note(job_id: str, note_id: str) -> bool:
    """개별 노트 삭제. 성공 시 True."""
    conn = _get_conn()
    try:
        cursor = conn.execute(
            "DELETE FROM recording_notes WHERE id = ? AND job_id = ?",
            (note_id, job_id),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Share Token
# ---------------------------------------------------------------------------

def create_share_token(job_id: str) -> str:
    """uuid4 토큰 생성, share_token 컬럼에 저장. 이미 있으면 기존 반환."""
    import uuid
    job = get_job(job_id)
    if job and job.get("share_token"):
        return job["share_token"]
    token = str(uuid.uuid4())
    conn = _get_conn()
    try:
        conn.execute("UPDATE meetings SET share_token = ? WHERE id = ?", (token, job_id))
        conn.commit()
    finally:
        conn.close()
    return token


def get_job_by_share_token(token: str) -> dict | None:
    """share_token으로 회의 조회. 없으면 None."""
    conn = _get_conn()
    try:
        row = conn.execute("SELECT * FROM meetings WHERE share_token = ?", (token,)).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def revoke_share_token(job_id: str) -> None:
    """share_token을 NULL로 설정."""
    conn = _get_conn()
    try:
        conn.execute("UPDATE meetings SET share_token = NULL WHERE id = ?", (job_id,))
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Meeting Series CRUD
# ---------------------------------------------------------------------------

def create_series(series_id: str, name: str, description: str = "") -> dict:
    """시리즈를 생성하고 dict로 반환."""
    conn = _get_conn()
    try:
        conn.execute(
            """
            INSERT INTO meeting_series (id, name, description)
            VALUES (?, ?, ?)
            """,
            (series_id, name, description),
        )
        conn.commit()
        return get_series(series_id)
    finally:
        conn.close()


def get_all_series() -> list[dict]:
    """전체 시리즈 목록 + 각 시리즈의 meeting_count."""
    conn = _get_conn()
    try:
        rows = conn.execute(
            """
            SELECT s.*, COUNT(m.id) as meeting_count
            FROM meeting_series s
            LEFT JOIN meetings m ON m.series_id = s.id
            GROUP BY s.id
            ORDER BY s.created_at DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_series(series_id: str) -> Optional[dict]:
    """시리즈 단일 조회."""
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM meeting_series WHERE id = ?", (series_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_series_meetings(series_id: str) -> list[dict]:
    """시리즈에 연결된 회의 목록 (created_at 내림차순)."""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM meetings WHERE series_id = ? ORDER BY created_at DESC",
            (series_id,),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def update_series(series_id: str, **kwargs) -> Optional[dict]:
    """시리즈 name/description 수정."""
    allowed = {"name", "description"}
    fields = [(k, v) for k, v in kwargs.items() if k in allowed]
    if not fields:
        return get_series(series_id)

    set_clause = ", ".join(f"{k} = ?" for k, _ in fields)
    values = [v for _, v in fields] + [series_id]
    conn = _get_conn()
    try:
        conn.execute(
            f"UPDATE meeting_series SET {set_clause}, updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now') WHERE id = ?",
            values,
        )
        conn.commit()
        return get_series(series_id)
    finally:
        conn.close()


def delete_series(series_id: str) -> bool:
    """시리즈 삭제. 연결된 meetings.series_id는 NULL로."""
    conn = _get_conn()
    try:
        # 연결된 회의의 series_id를 NULL로
        conn.execute(
            "UPDATE meetings SET series_id = NULL WHERE series_id = ?",
            (series_id,),
        )
        cursor = conn.execute(
            "DELETE FROM meeting_series WHERE id = ?", (series_id,)
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def update_job_series(job_id: str, series_id: Optional[str]) -> None:
    """job의 series_id를 갱신. None이면 해제."""
    conn = _get_conn()
    try:
        conn.execute(
            "UPDATE meetings SET series_id = ? WHERE id = ?",
            (series_id, job_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_previous_series_meeting(job_id: str, series_id: str) -> Optional[dict]:
    """같은 시리즈에서 현재 회의 바로 이전 회의를 반환. created_at 기준."""
    conn = _get_conn()
    try:
        # 현재 회의의 created_at 조회
        cur = conn.execute(
            "SELECT created_at FROM meetings WHERE id = ?", (job_id,)
        ).fetchone()
        if not cur:
            return None
        cur_created = cur[0]
        # 같은 시리즈에서 현재 회의보다 이전인 것 중 가장 최근
        row = conn.execute(
            """
            SELECT * FROM meetings
            WHERE series_id = ? AND id != ? AND created_at < ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (series_id, job_id, cur_created),
        ).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def update_job_followup(job_id: str, followup_items) -> None:
    """followup_items를 JSON으로 저장."""
    conn = _get_conn()
    try:
        conn.execute(
            "UPDATE meetings SET followup_items = ? WHERE id = ?",
            (json.dumps(followup_items, ensure_ascii=False), job_id),
        )
        conn.commit()
    finally:
        conn.close()

