from __future__ import annotations

import secrets
from datetime import datetime
from typing import Any

from sqlalchemy import delete, select

from infrastructure.database import LegacyInterviewRecord, PlatformUser, UserSession, platform_session
from services.platform_service import fallback_role_for_email


def create_user(email: str, display_name: str, password_hash: str, salt: str) -> dict[str, Any]:
    with platform_session() as session:
        if session.scalar(select(PlatformUser).where(PlatformUser.email == email)):
            raise ValueError("该邮箱已注册，请直接登录。")
        user = PlatformUser(
            # auth_user_id must be unique before MySQL assigns the real id.
            # Replace this short-lived negative value immediately after flush.
            auth_user_id=-(secrets.randbelow(2_000_000_000) + 1),
            email=email,
            display_name=display_name,
            password_hash=password_hash,
            password_salt=salt,
            role=fallback_role_for_email(email),
        )
        session.add(user)
        session.flush()
        user.auth_user_id = user.id
        return serialize_user(user)


def find_user_by_email(email: str) -> dict[str, Any] | None:
    with platform_session() as session:
        user = session.scalar(select(PlatformUser).where(PlatformUser.email == email))
        return serialize_user(user, include_password=True) if user else None


def create_session(user_id: int, token: str, expires_at: datetime) -> None:
    with platform_session() as session:
        session.execute(delete(UserSession).where(UserSession.expires_at < datetime.utcnow()))
        session.add(UserSession(user_id=user_id, session_token=token, expires_at=expires_at))


def delete_session(token: str) -> None:
    with platform_session() as session:
        session.execute(delete(UserSession).where(UserSession.session_token == token))


def get_user_by_session(token: str) -> dict[str, Any] | None:
    with platform_session() as session:
        statement = (
            select(PlatformUser, UserSession.expires_at)
            .join(UserSession, UserSession.user_id == PlatformUser.id)
            .where(UserSession.session_token == token, UserSession.expires_at > datetime.utcnow())
        )
        row = session.execute(statement).first()
        if not row:
            return None
        user, expires_at = row
        return {**serialize_user(user), "expires_at": expires_at.isoformat()}


def create_interview_record(**payload: Any) -> int:
    with platform_session() as session:
        record = LegacyInterviewRecord(**payload)
        session.add(record)
        session.flush()
        return int(record.id)


def list_interview_records(user_id: int) -> list[dict[str, Any]]:
    with platform_session() as session:
        records = session.scalars(
            select(LegacyInterviewRecord)
            .where(LegacyInterviewRecord.user_id == user_id)
            .order_by(LegacyInterviewRecord.created_at.desc())
        ).all()
        return [serialize_record(item, detail=False) for item in records]


def get_interview_record(user_id: int, record_id: int) -> dict[str, Any] | None:
    with platform_session() as session:
        item = session.scalar(
            select(LegacyInterviewRecord).where(
                LegacyInterviewRecord.user_id == user_id,
                LegacyInterviewRecord.id == record_id,
            )
        )
        return serialize_record(item, detail=True) if item else None


def serialize_user(user: PlatformUser, include_password: bool = False) -> dict[str, Any]:
    payload = {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "created_at": user.created_at.isoformat(),
        "role": user.role,
        "organization_id": user.organization_id,
    }
    if include_password:
        payload["password_hash"] = user.password_hash
        payload["password_salt"] = user.password_salt
    return payload


def serialize_record(item: LegacyInterviewRecord, detail: bool) -> dict[str, Any]:
    payload = {
        "id": item.id,
        "role_name": item.role_name,
        "resume_filename": item.resume_filename,
        "score": item.score,
        "report_file": item.report_file,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }
    if detail:
        payload.update(
            report_text=item.report_text,
            history_json=item.history_json,
            interview_state_json=item.interview_state_json,
        )
    return payload
