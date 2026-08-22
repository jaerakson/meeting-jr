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
    """sqlite3.Row -> dict 변환. speakers JSON 문자열은 파싱."""
    d = dict(row)
    if d.get("speakers"):
        try:
            d["speakers"] = json.loads(d["speakers"])
        except (json.JSONDecodeError, TypeError):
            d["speakers"] = {}
    else:
        d["speakers"] = {}
    return d


# ---------------------------------------------------------------------------
# 초기화
# ---------------------------------------------------------------------------

def _migrate(conn: sqlite3.Connection) -> None:
    """기존 DB에 누락된 컬럼을 추가한다."""
    existing = {row[1] for row in conn.execute("PRAGMA table_info(meetings)")}
    for col, definition in [("notion_url", "TEXT"), ("notion_page_id", "TEXT")]:
        if col not in existing:
            conn.execute(f"ALTER TABLE meetings ADD COLUMN {col} {definition}")
    conn.commit()


def init_db() -> None:
    """meetings 테이블이 없으면 생성한다. 앱 시작 시 호출."""
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
                notion_page_id TEXT
            )
        """)
        _migrate(conn)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key        TEXT PRIMARY KEY,
                value      TEXT NOT NULL,
                updated_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
            )
        """)
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
) -> dict:
    """새 Job 레코드를 생성하고 dict로 반환."""
    now = datetime.now(timezone.utc).isoformat()
    conn = _get_conn()
    try:
        conn.execute(
            """
            INSERT INTO meetings (id, title, filename, status, created_at)
            VALUES (?, ?, ?, 'pending', ?)
            """,
            (job_id, title or filename, filename, now),
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
    """전체 Job 목록을 최신순(created_at DESC)으로 반환."""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM meetings ORDER BY created_at DESC"
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
