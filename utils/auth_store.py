import hashlib
import hmac
import os
import secrets
import sqlite3
from datetime import datetime, timedelta
from typing import Any

from utils.path_tool import get_abs_path
from infrastructure.database import platform_database_enabled


DB_PATH = get_abs_path("data/app.db")
SESSION_EXPIRE_DAYS = 7


def _get_connection() -> sqlite3.Connection:
    # 整个认证模块访问 SQLite 的统一入口。
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    # 启动时建表：如果表不存在就创建，已存在则保留原数据。
    with _get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                password_salt TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS user_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                session_token TEXT NOT NULL UNIQUE,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS interview_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                role_name TEXT NOT NULL,
                resume_filename TEXT NOT NULL,
                score INTEGER NOT NULL DEFAULT 0,
                report_text TEXT NOT NULL,
                report_file TEXT NOT NULL,
                history_json TEXT NOT NULL,
                interview_state_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );
            """
        )


def _hash_password(password: str, salt: str) -> str:
    # 不保存明文密码，而是保存“密码 + salt”计算后的哈希值。
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000).hex()


def create_user(email: str, display_name: str, password: str) -> dict[str, Any]:
    # 注册流程：清洗输入 -> 生成 salt -> 计算哈希 -> 写入 users 表。
    normalized_email = (email or "").strip().lower()
    normalized_name = (display_name or "").strip()
    if not normalized_email or not normalized_name or not password:
        raise ValueError("邮箱、用户名和密码不能为空。")

    salt = secrets.token_hex(16)
    password_hash = _hash_password(password, salt)
    created_at = datetime.now().isoformat()

    if platform_database_enabled():
        from infrastructure.postgres_auth import create_user as pg_create_user

        return pg_create_user(normalized_email, normalized_name, password_hash, salt)

    try:
        with _get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO users (email, display_name, password_hash, password_salt, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (normalized_email, normalized_name, password_hash, salt, created_at),
            )
            user_id = cursor.lastrowid
    except sqlite3.IntegrityError as exc:
        raise ValueError("该邮箱已注册，请直接登录。") from exc

    return {
        "id": user_id,
        "email": normalized_email,
        "display_name": normalized_name,
        "created_at": created_at,
    }


def verify_user(email: str, password: str) -> dict[str, Any] | None:
    # 登录校验：根据邮箱查用户，再重新计算输入密码的哈希做比对。
    normalized_email = (email or "").strip().lower()
    if platform_database_enabled():
        from infrastructure.postgres_auth import find_user_by_email

        row = find_user_by_email(normalized_email)
        if not row:
            return None
        actual_hash = _hash_password(password, row["password_salt"])
        if not hmac.compare_digest(row["password_hash"], actual_hash):
            return None
        return {key: value for key, value in row.items() if key not in {"password_hash", "password_salt"}}
    with _get_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (normalized_email,)).fetchone()
    if not row:
        return None

    expected_hash = row["password_hash"]
    actual_hash = _hash_password(password, row["password_salt"])
    if not hmac.compare_digest(expected_hash, actual_hash):
        return None

    return {
        "id": row["id"],
        "email": row["email"],
        "display_name": row["display_name"],
        "created_at": row["created_at"],
    }


def create_session(user_id: int) -> str:
    # 登录成功后生成 session_token，并保存到 user_sessions 表。
    token = secrets.token_urlsafe(32)
    now = datetime.now()
    expires_at = (now + timedelta(days=SESSION_EXPIRE_DAYS)).isoformat()
    if platform_database_enabled():
        from infrastructure.postgres_auth import create_session as pg_create_session

        pg_create_session(user_id, token, datetime.fromisoformat(expires_at))
        return token
    with _get_connection() as conn:
        conn.execute("DELETE FROM user_sessions WHERE expires_at < ?", (now.isoformat(),))
        conn.execute(
            """
            INSERT INTO user_sessions (user_id, session_token, expires_at, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, token, expires_at, now.isoformat()),
        )
    return token


def delete_session(token: str) -> None:
    # 退出登录的本质就是删掉对应的会话记录。
    if not token:
        return
    if platform_database_enabled():
        from infrastructure.postgres_auth import delete_session as pg_delete_session

        pg_delete_session(token)
        return
    with _get_connection() as conn:
        conn.execute("DELETE FROM user_sessions WHERE session_token = ?", (token,))


def get_user_by_session(token: str) -> dict[str, Any] | None:
    # 根据浏览器 Cookie 里的 session_token 反查当前用户。
    if not token:
        return None
    if platform_database_enabled():
        from infrastructure.postgres_auth import get_user_by_session as pg_get_user_by_session

        return pg_get_user_by_session(token)
    now_iso = datetime.now().isoformat()
    with _get_connection() as conn:
        row = conn.execute(
            """
            SELECT users.id, users.email, users.display_name, users.created_at, user_sessions.expires_at
            FROM user_sessions
            JOIN users ON users.id = user_sessions.user_id
            WHERE user_sessions.session_token = ? AND user_sessions.expires_at > ?
            """,
            (token, now_iso),
        ).fetchone()
    if not row:
        return None
    return {
        "id": row["id"],
        "email": row["email"],
        "display_name": row["display_name"],
        "created_at": row["created_at"],
        "expires_at": row["expires_at"],
    }


def create_interview_record(
    user_id: int,
    role_name: str,
    resume_filename: str,
    score: int,
    report_text: str,
    report_file: str,
    history_json: str,
    interview_state_json: str,
) -> int:
    # 把一轮面试结果落成历史记录，供历史列表/恢复/下载使用。
    now = datetime.now().isoformat()
    if platform_database_enabled():
        from infrastructure.postgres_auth import create_interview_record as pg_create_interview_record

        return pg_create_interview_record(
            user_id=user_id,
            role_name=role_name,
            resume_filename=resume_filename,
            score=score,
            report_text=report_text,
            report_file=report_file,
            history_json=history_json,
            interview_state_json=interview_state_json,
        )
    with _get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO interview_records (
                user_id, role_name, resume_filename, score, report_text, report_file,
                history_json, interview_state_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                role_name,
                resume_filename,
                score,
                report_text,
                report_file,
                history_json,
                interview_state_json,
                now,
                now,
            ),
        )
        return int(cursor.lastrowid)


def list_interview_records(user_id: int) -> list[dict[str, Any]]:
    # 返回历史列表页需要的摘要数据。
    if platform_database_enabled():
        from infrastructure.postgres_auth import list_interview_records as pg_list_interview_records

        return pg_list_interview_records(user_id)
    with _get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, role_name, resume_filename, score, report_file, created_at, updated_at
            FROM interview_records
            WHERE user_id = ?
            ORDER BY created_at DESC
            """,
            (user_id,),
        ).fetchall()
    return [
        {
            "id": row["id"],
            "role_name": row["role_name"],
            "resume_filename": row["resume_filename"],
            "score": row["score"],
            "report_file": row["report_file"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
        for row in rows
    ]


def get_interview_record(user_id: int, record_id: int) -> dict[str, Any] | None:
    # 返回单条完整记录，给历史详情和恢复逻辑使用。
    if platform_database_enabled():
        from infrastructure.postgres_auth import get_interview_record as pg_get_interview_record

        return pg_get_interview_record(user_id, record_id)
    with _get_connection() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM interview_records
            WHERE user_id = ? AND id = ?
            """,
            (user_id, record_id),
        ).fetchone()
    if not row:
        return None
    return {
        "id": row["id"],
        "role_name": row["role_name"],
        "resume_filename": row["resume_filename"],
        "score": row["score"],
        "report_text": row["report_text"],
        "report_file": row["report_file"],
        "history_json": row["history_json"],
        "interview_state_json": row["interview_state_json"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
