import json
import os
import re
import uuid
from copy import deepcopy
from datetime import datetime
from typing import Any

from utils.path_tool import get_abs_path


USER_HISTORY_DIR = get_abs_path("data/user_histories")


def _normalize_user_id(user_id: str) -> str:
    # 把邮箱/用户名转成适合做文件名的格式。
    normalized = (user_id or "").strip()
    if not normalized:
        normalized = "guest"
    normalized = re.sub(r'[<>:"/\\|?*]', "_", normalized)
    normalized = re.sub(r"\s+", "_", normalized)
    return normalized


def _get_user_file(user_id: str) -> str:
    # 当前模块按“每个用户一个 JSON 文件”的方式保存工作台状态。
    os.makedirs(USER_HISTORY_DIR, exist_ok=True)
    safe_user_id = _normalize_user_id(user_id)
    return os.path.join(USER_HISTORY_DIR, f"{safe_user_id}.json")


def _now_iso() -> str:
    return datetime.now().isoformat()


def create_empty_candidate_state() -> dict[str, Any]:
    # 单个会话的核心业务状态：
    # 问答历史、面试历史、简历、报告、多 Agent 中间状态都放在这里。
    return {
        "interview_history": [],
        "qa_history": [],
        "interview_questions": [],
        "interview_started": False,
        "interview_finished": False,
        "interview_report": "",
        "interview_report_file": "",
        "latest_report_record_id": None,
        "resume_text": "",
        "resume_filename": "",
        "interview_score": 0,
        # 多 Agent 的中间产物统一放在 interview_state 里，方便持久化和历史恢复。
        "interview_state": {
            "multi_agent": {
                "workflow_version": "multi_agent_v1",
                "resume_analysis": {},
                "route_history": [],
                "evaluations": [],
                "last_route": {},
                "last_evaluation": {},
                "last_report_meta": {},
            }
        },
    }


def _create_conversation(name: str = "默认会话", preferred_mode: str = "qa") -> dict[str, Any]:
    now = _now_iso()
    return {
        "id": uuid.uuid4().hex,
        "name": (name or "默认会话").strip(),
        "pinned": False,
        "preferred_mode": preferred_mode,
        "created_at": now,
        "updated_at": now,
        "state": create_empty_candidate_state(),
    }


def _create_project(name: str = "默认项目") -> dict[str, Any]:
    now = _now_iso()
    return {
        "id": uuid.uuid4().hex,
        "name": (name or "默认项目").strip(),
        "pinned": False,
        "created_at": now,
        "updated_at": now,
        "conversations": [_create_conversation()],
    }


def create_default_workspace_state() -> dict[str, Any]:
    default_project = _create_project()
    default_conversation = default_project["conversations"][0]
    return {
        "workspace_version": 2,
        "onboarding_completed": False,
        "active_project_id": default_project["id"],
        "active_conversation_id": default_conversation["id"],
        "projects": [default_project],
    }


def _normalize_candidate_state(candidate_state: dict[str, Any] | None) -> dict[str, Any]:
    # 兼容旧数据：如果某些字段缺失，就按默认结构补齐。
    base = create_empty_candidate_state()
    data = deepcopy(candidate_state or {})
    for key, value in base.items():
        data.setdefault(key, value)
    return data


def _normalize_workspace_state(raw_state: dict[str, Any] | None) -> dict[str, Any]:
    if not raw_state:
        return create_default_workspace_state()

    # 兼容旧版本：历史上一个用户只保存一份当前工作态。
    if "projects" not in raw_state:
        workspace = create_default_workspace_state()
        project = workspace["projects"][0]
        conversation = project["conversations"][0]
        conversation["state"] = _normalize_candidate_state(raw_state)
        return workspace

    workspace = {
        "workspace_version": int(raw_state.get("workspace_version", 2)),
        "onboarding_completed": bool(raw_state.get("onboarding_completed", False)),
        "active_project_id": str(raw_state.get("active_project_id", "")).strip(),
        "active_conversation_id": str(raw_state.get("active_conversation_id", "")).strip(),
        "projects": [],
    }

    for project_data in raw_state.get("projects", []) or []:
        now = _now_iso()
        project = {
            "id": str(project_data.get("id") or uuid.uuid4().hex),
            "name": str(project_data.get("name") or "未命名项目").strip() or "未命名项目",
            "pinned": bool(project_data.get("pinned", False)),
            "created_at": str(project_data.get("created_at") or now),
            "updated_at": str(project_data.get("updated_at") or now),
            "conversations": [],
        }

        for conversation_data in project_data.get("conversations", []) or []:
            conversation = {
                "id": str(conversation_data.get("id") or uuid.uuid4().hex),
                "name": str(conversation_data.get("name") or "未命名会话").strip() or "未命名会话",
                "pinned": bool(conversation_data.get("pinned", False)),
                "preferred_mode": str(conversation_data.get("preferred_mode") or "qa"),
                "created_at": str(conversation_data.get("created_at") or now),
                "updated_at": str(conversation_data.get("updated_at") or now),
                "state": _normalize_candidate_state(conversation_data.get("state")),
            }
            project["conversations"].append(conversation)

        workspace["projects"].append(project)

    if not workspace["projects"]:
        return create_default_workspace_state()

    if not workspace["active_project_id"]:
        workspace["active_project_id"] = workspace["projects"][0]["id"]

    active_project = get_project_by_id(workspace, workspace["active_project_id"])
    if not active_project:
        active_project = workspace["projects"][0]
        workspace["active_project_id"] = active_project["id"]

    if not workspace["active_conversation_id"]:
        for project in workspace["projects"]:
            if project.get("conversations"):
                workspace["active_conversation_id"] = project["conversations"][0]["id"]
                break

    active_conversation = get_conversation_by_id(workspace, workspace["active_conversation_id"])
    if not active_conversation:
        for project in workspace["projects"]:
            if project.get("conversations"):
                workspace["active_conversation_id"] = project["conversations"][0]["id"]
                break
        else:
            return create_default_workspace_state()

    return workspace


def load_user_state(user_id: str) -> dict[str, Any]:
    # 从磁盘读取当前用户的完整工作台状态。
    file_path = _get_user_file(user_id)
    if not os.path.exists(file_path):
        return create_default_workspace_state()

    with open(file_path, "r", encoding="utf-8") as file:
        raw_state = json.load(file)
    return _normalize_workspace_state(raw_state)


def save_user_state(user_id: str, state: dict[str, Any]) -> None:
    # 把当前用户完整 workspace 持久化到 JSON 文件。
    file_path = _get_user_file(user_id)
    payload = _normalize_workspace_state(state)
    with open(file_path, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)


def get_project_by_id(workspace: dict[str, Any], project_id: str) -> dict[str, Any] | None:
    for project in workspace.get("projects", []) or []:
        if project.get("id") == project_id:
            return project
    return None


def get_conversation_by_id(workspace: dict[str, Any], conversation_id: str) -> dict[str, Any] | None:
    for project in workspace.get("projects", []) or []:
        for conversation in project.get("conversations", []) or []:
            if conversation.get("id") == conversation_id:
                return conversation
    return None


def get_active_project(workspace: dict[str, Any]) -> dict[str, Any]:
    # 获取当前正在查看的项目；如果 active_project_id 丢失，就兜底到第一个项目。
    project = get_project_by_id(workspace, workspace.get("active_project_id", ""))
    if project:
        return project
    project = (workspace.get("projects") or [])[0]
    workspace["active_project_id"] = project["id"]
    return project


def get_active_conversation(workspace: dict[str, Any]) -> dict[str, Any]:
    # 获取当前正在查看的会话；问答和模拟面试都围绕它继续进行。
    conversation = get_conversation_by_id(workspace, workspace.get("active_conversation_id", ""))
    if conversation:
        return conversation
    project = get_active_project(workspace)
    conversation = project["conversations"][0]
    workspace["active_conversation_id"] = conversation["id"]
    return conversation


def get_active_candidate_state(workspace: dict[str, Any]) -> dict[str, Any]:
    return get_active_conversation(workspace)["state"]


def update_active_candidate_state(workspace: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    # 一轮问答/面试处理完后，最终都会通过这里把最新 state 写回当前活动会话。
    conversation = get_active_conversation(workspace)
    conversation["state"] = _normalize_candidate_state(state)
    conversation["updated_at"] = _now_iso()
    project = get_active_project(workspace)
    project["updated_at"] = conversation["updated_at"]
    return workspace


def list_workspace_projects(workspace: dict[str, Any]) -> list[dict[str, Any]]:
    # 给前端侧边栏返回轻量摘要数据，不把完整聊天历史全部带出去。
    def keep_manual_order_with_pinned_first(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        pinned_items = [item for item in items if bool(item.get("pinned", False))]
        normal_items = [item for item in items if not bool(item.get("pinned", False))]
        return pinned_items + normal_items

    project_summaries: list[dict[str, Any]] = []
    for project in keep_manual_order_with_pinned_first(workspace.get("projects", []) or []):
        conversations = []
        for conversation in keep_manual_order_with_pinned_first(project.get("conversations", []) or []):
            state = conversation.get("state", {})
            conversations.append(
                {
                    "id": conversation["id"],
                    "name": conversation["name"],
                    "pinned": bool(conversation.get("pinned", False)),
                    "preferred_mode": conversation.get("preferred_mode", "qa"),
                    "created_at": conversation.get("created_at", ""),
                    "updated_at": conversation.get("updated_at", ""),
                    "qa_count": len(state.get("qa_history", []) or []),
                    "interview_count": len(state.get("interview_history", []) or []),
                }
            )

        project_summaries.append(
            {
                "id": project["id"],
                "name": project["name"],
                "pinned": bool(project.get("pinned", False)),
                "created_at": project.get("created_at", ""),
                "updated_at": project.get("updated_at", ""),
                "conversation_count": len(project.get("conversations", []) or []),
                "conversations": conversations,
            }
        )

    return project_summaries
