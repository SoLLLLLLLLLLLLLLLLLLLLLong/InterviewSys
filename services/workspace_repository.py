from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import delete, select

from infrastructure.database import (
    Conversation,
    Message,
    WorkspaceProject,
    WorkspaceSnapshot,
    json_safe,
    platform_database_enabled,
    platform_session,
)
from services.platform_service import ensure_platform_user
from utils.user_history_store import create_default_workspace_state, load_user_state, save_user_state


def load_workspace(user: dict[str, Any]) -> dict[str, Any]:
    # 读取当前用户的工作区状态。
    # 工作区包含：项目列表、会话列表、当前激活项目/会话、每个会话下的问答和面试历史。
    if not platform_database_enabled():
        # 开发兜底模式：不开 MySQL 时，继续使用本地 JSON 文件保存用户工作区。
        return load_user_state(user["email"])

    # 正式模式：开启 MySQL 后，优先从 WorkspaceSnapshot 表里读取完整快照。
    profile = ensure_platform_user(user)
    with platform_session() as session:
        snapshot = session.scalar(select(WorkspaceSnapshot).where(WorkspaceSnapshot.user_id == profile["platform_user_id"]))
        if snapshot and snapshot.payload:
            return snapshot.payload

    # 第一次切到 MySQL 时，如果数据库里还没有快照，就把旧 JSON 数据导入 MySQL。
    # 这样从开发模式迁移到正式模式时，不会直接丢失之前的历史记录。
    workspace = load_user_state(user["email"])
    save_workspace(user, workspace)
    return workspace


def save_workspace(user: dict[str, Any], workspace: dict[str, Any]) -> None:
    # 保存当前用户的工作区状态。
    # 前端创建项目、切换会话、发送消息、生成报告后，后端都会更新 candidate/workspace，再走这里持久化。
    if not platform_database_enabled():
        save_user_state(user["email"], workspace)
        return
    profile = ensure_platform_user(user)
    platform_user_id = int(profile["platform_user_id"])
    payload = json_safe(workspace)
    with platform_session() as session:
        # Snapshot 是完整 JSON 快照，方便快速恢复整个工作区。
        snapshot = session.scalar(select(WorkspaceSnapshot).where(WorkspaceSnapshot.user_id == platform_user_id))
        if snapshot is None:
            session.add(WorkspaceSnapshot(user_id=platform_user_id, payload=payload))
        else:
            snapshot.payload = payload
            snapshot.updated_at = datetime.utcnow()
        # 同时把项目、会话、消息拆成结构化表，方便后台统计、搜索、看板分析。
        _sync_normalized_workspace(session, platform_user_id, payload)


def _sync_normalized_workspace(session, user_id: int, workspace: dict[str, Any]) -> None:
    """Dual-write normalized rows used by dashboards and future analytics."""
    # 双写策略：
    # 1. WorkspaceSnapshot 保存完整 JSON，恢复方便。
    # 2. WorkspaceProject / Conversation / Message 保存结构化数据，查询统计方便。
    project_ids = [str(item.get("id")) for item in workspace.get("projects", []) if item.get("id")]
    existing_projects = {item.id: item for item in session.scalars(select(WorkspaceProject).where(WorkspaceProject.user_id == user_id)).all()}

    for project_payload in workspace.get("projects", []):
        # 同步项目表。
        project_id = str(project_payload.get("id"))
        project = existing_projects.get(project_id)
        if project is None:
            project = WorkspaceProject(id=project_id, user_id=user_id, name=str(project_payload.get("name", "未命名项目")))
            session.add(project)
        project.name = str(project_payload.get("name", "未命名项目"))
        project.pinned = bool(project_payload.get("pinned", False))

        for conversation_payload in project_payload.get("conversations", []):
            # 同步会话表。
            conversation_id = str(conversation_payload.get("id"))
            conversation = session.get(Conversation, conversation_id)
            if conversation is None:
                conversation = Conversation(id=conversation_id, project_id=project_id, user_id=user_id, name="")
                session.add(conversation)
            conversation.name = str(conversation_payload.get("name", "未命名会话"))
            conversation.preferred_mode = str(conversation_payload.get("preferred_mode", "qa"))
            conversation.pinned = bool(conversation_payload.get("pinned", False))
            conversation.state_json = json_safe(conversation_payload.get("state", {}))
            session.flush()

            # 简单起见，这里先删除旧消息再重建消息表。
            # 数据量较小时实现更稳定；如果后续消息量很大，可以优化成增量 upsert。
            session.execute(delete(Message).where(Message.conversation_id == conversation_id))
            state = conversation_payload.get("state", {}) or {}
            for mode, history_key in (("qa", "qa_history"), ("interview", "interview_history")):
                # 把 qa_history / interview_history 拆成 Message 行，后台就能按会话、模式、顺序查询。
                for sequence, message in enumerate(state.get(history_key, []) or []):
                    session.add(
                        Message(
                            conversation_id=conversation_id,
                            user_id=user_id,
                            mode=mode,
                            sequence=sequence,
                            role=str(message.get("role", "assistant")),
                            content=str(message.get("content", "")),
                            status=str(message.get("status", "done")),
                        )
                    )

    for project_id, project in existing_projects.items():
        # 如果某个项目在最新 workspace JSON 里不存在，说明用户已经删除，需要同步删除结构化表记录。
        if project_id not in project_ids:
            session.execute(delete(Message).where(Message.conversation_id.in_(select(Conversation.id).where(Conversation.project_id == project_id))))
            session.execute(delete(Conversation).where(Conversation.project_id == project_id))
            session.delete(project)
