"""
설정값 암호화 저장/복호화 조회.
SECRET_KEY는 .env에서만 관리, 실제 값은 DB settings 테이블에 암호화 저장.
"""

import os
from pathlib import Path
from cryptography.fernet import Fernet
import sqlite3

DB_PATH = Path(__file__).resolve().parent.parent / "meetings.db"
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"

SETTING_KEYS = ["HF_TOKEN", "NOTION_API_KEY", "NOTION_DATABASE_ID", "DEFAULT_MEETING_TITLE"]


def _get_fernet() -> Fernet:
    key = os.getenv("SECRET_KEY")
    if not key:
        key = Fernet.generate_key().decode()
        _append_to_env("SECRET_KEY", key)
        os.environ["SECRET_KEY"] = key
    return Fernet(key.encode())


def _append_to_env(name: str, value: str) -> None:
    """SECRET_KEY가 없을 때 .env 파일에 추가."""
    with open(ENV_PATH, "a", encoding="utf-8") as f:
        f.write(f"\n{name}={value}\n")


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def get_setting(name: str) -> str | None:
    """DB에서 복호화해서 반환. 없으면 os.getenv() 폴백."""
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT value FROM settings WHERE key = ?", (name,)
        ).fetchone()
        if row:
            try:
                return _get_fernet().decrypt(row["value"].encode()).decode()
            except Exception:
                return None
        return os.getenv(name)
    finally:
        conn.close()


def set_setting(name: str, value: str) -> None:
    """암호화 후 DB upsert. 빈 문자열이면 삭제."""
    conn = _get_conn()
    try:
        if not value:
            conn.execute("DELETE FROM settings WHERE key = ?", (name,))
        else:
            encrypted = _get_fernet().encrypt(value.encode()).decode()
            conn.execute(
                """
                INSERT INTO settings (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value,
                updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now')
                """,
                (name, encrypted),
            )
        conn.commit()
    finally:
        conn.close()


def _make_preview(value: str) -> str:
    """앞 5자 + *** + 뒤 3자 형태의 미리보기 생성."""
    if not value:
        return ""
    if len(value) <= 8:
        return value[:5] + "***"
    return f"{value[:5]}***{value[-3:]}"


def get_settings_status() -> dict[str, dict]:
    """각 키의 설정 여부와 앞 4자 미리보기를 반환. 전체 값은 노출 안 함."""
    result = {}
    conn = _get_conn()
    try:
        for key in SETTING_KEYS:
            row = conn.execute(
                "SELECT value FROM settings WHERE key = ?", (key,)
            ).fetchone()
            if row:
                try:
                    decrypted = _get_fernet().decrypt(row["value"].encode()).decode()
                    result[key] = {"set": True, "preview": _make_preview(decrypted)}
                except Exception:
                    result[key] = {"set": False, "preview": None}
            else:
                env_val = os.getenv(key, "")
                result[key] = {
                    "set": bool(env_val),
                    "preview": _make_preview(env_val) if env_val else None,
                }
        return result
    finally:
        conn.close()
