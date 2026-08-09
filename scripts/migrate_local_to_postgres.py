"""One-time migration from the original SQLite/JSON storage to the platform database.

Run only after DATABASE_URL and ENABLE_PLATFORM_DB=true are configured:
    python scripts/migrate_local_to_postgres.py

The historical filename is retained for compatibility. The migration uses
SQLAlchemy and therefore supports the project's current MySQL configuration.
"""
from __future__ import annotations

import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy import select, text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from infrastructure.database import LegacyInterviewRecord, PlatformUser, init_platform_database, platform_session
from services.platform_service import fallback_role_for_email
from services.workspace_repository import save_workspace
from utils.path_tool import get_abs_path
from utils.user_history_store import load_user_state


def parse_datetime(value: str | None) -> datetime | None:
    """Convert SQLite ISO strings to values accepted by SQLAlchemy DateTime."""
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def main() -> None:
    if not init_platform_database():
        raise RuntimeError("请先配置 DATABASE_URL，并设置 ENABLE_PLATFORM_DB=true。")

    sqlite_path = get_abs_path("data/app.db")
    if not os.path.exists(sqlite_path):
        print("未找到原 SQLite 文件，无需迁移。")
        return

    connection = sqlite3.connect(sqlite_path)
    connection.row_factory = sqlite3.Row
    try:
        users = connection.execute("SELECT * FROM users ORDER BY id").fetchall()
        reports = connection.execute("SELECT * FROM interview_records ORDER BY id").fetchall()
    finally:
        connection.close()

    migrated_users: list[dict[str, object]] = []
    with platform_session() as session:
        for row in users:
            user = session.scalar(select(PlatformUser).where(PlatformUser.email == row["email"]))
            if user is None:
                user = PlatformUser(
                    id=row["id"],
                    auth_user_id=row["id"],
                    email=row["email"],
                    display_name=row["display_name"],
                    password_hash=row["password_hash"],
                    password_salt=row["password_salt"],
                    role=fallback_role_for_email(row["email"]),
                    created_at=parse_datetime(row["created_at"]) or datetime.utcnow(),
                )
                session.add(user)
            migrated_users.append({"id": row["id"], "email": row["email"], "display_name": row["display_name"]})
        session.flush()

        for row in reports:
            if session.get(LegacyInterviewRecord, row["id"]):
                continue
            session.add(
                LegacyInterviewRecord(
                    id=row["id"],
                    user_id=row["user_id"],
                    role_name=row["role_name"],
                    resume_filename=row["resume_filename"],
                    score=row["score"],
                    report_text=row["report_text"],
                    report_file=row["report_file"],
                    history_json=row["history_json"],
                    interview_state_json=row["interview_state_json"],
                    created_at=parse_datetime(row["created_at"]) or datetime.utcnow(),
                    updated_at=parse_datetime(row["updated_at"]) or datetime.utcnow(),
                )
            )

        session.execute(text("SELECT setval(pg_get_serial_sequence('platform_users','id'), COALESCE(MAX(id), 1)) FROM platform_users"))
        session.execute(text("SELECT setval(pg_get_serial_sequence('legacy_interview_records','id'), COALESCE(MAX(id), 1)) FROM legacy_interview_records"))

    # save_workspace writes a normalized MySQL copy when platform storage is enabled.
    for user in migrated_users:
        save_workspace(user, load_user_state(str(user["email"])))

    print(f"迁移完成：{len(users)} 个用户，{len(reports)} 条面试报告。")


if __name__ == "__main__":
    main()
