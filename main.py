import json
import os
import asyncio
import inspect
import threading
from contextlib import asynccontextmanager
from copy import deepcopy
from datetime import datetime
from typing import Any

from fastapi import FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from agent.agent_tools import get_city, get_weather
from agent.interview_role_manager import InterviewRoleManager
from infrastructure.database import init_platform_database
from infrastructure.settings import platform_settings
from infrastructure.run_store import agent_run_store
from routers.platform import build_platform_router
from services.platform_service import (
    can_access_agent_run,
    create_interview_task,
    ensure_platform_user,
    finalize_interview_task,
    get_interview_template_profile,
    mark_interview_ended,
    list_configured_role_names,
    record_interview_answer,
    record_interview_question,
    register_knowledge_documents,
)
from utils.auth_store import (
    create_interview_record,
    create_session,
    create_user,
    delete_session,
    get_interview_record,
    get_user_by_session,
    init_db,
    list_interview_records,
    verify_user,
)
from utils.file_handler import extract_text_from_file, get_file_md5_hex, save_binary_file
from utils.langsmith_handler import (
    configure_langsmith,
    get_langsmith_settings_from_env,
    tracing_context_if_enabled,
)
from utils.logger_handler import logger
from utils.path_tool import get_abs_path
from utils.user_history_store import (
    get_active_candidate_state,
    get_active_conversation,
    get_active_project,
    get_conversation_by_id,
    get_project_by_id,
    list_workspace_projects,
    update_active_candidate_state,
)
from services.workspace_repository import load_workspace, save_workspace


# main.py 是整个后端 API 的入口文件。
# 你可以把它理解成：
# 1. 接收前端 HTTP 请求
# 2. 调用 service / utils / 存储层
# 3. 把结果重新组织成 JSON 再返回给前端
SESSION_COOKIE_NAME = "interview_session"

ROLE_OPTIONS = [
    "后端开发",
    "前端开发",
    "数据分析",
    "算法工程",
    "Agent 开发",
    "产品经理",
    "通用技术岗位",
]

QA_WELCOME = {
    "title": "问答模式",
    "caption": "基于知识库和模型能力回答你的问题。",
    "empty_title": "很高兴为你服务",
    "empty_description": [
        "我是你的专业技术面试助手。",
        "你可以直接提技术问题，或者告诉我你正在准备的岗位方向。",
        "我会结合知识库内容和模型能力，给出结构化、清晰的回答。",
    ],
}

INTERVIEW_WELCOME = {
    "title": "模拟面试",
    "caption": "支持按岗位面试，也支持上传简历后按“岗位 + 简历”进行定制化提问。",
    "empty_title": "欢迎开始模拟面试",
    "empty_description": [
        "请选择目标岗位，也可以额外上传简历。",
        "如果上传了简历，我会结合你的经历和岗位要求来提问。",
        "面试结束后，系统会生成分数和结构化面试报告。",
    ],
}

HISTORY_META = {
    "title": "历史记录",
    "caption": "查看过往的模拟面试记录、分数和报告文件。",
}

QA_PENDING_MESSAGE = "面试助手正在整理答案中..."
INTERVIEW_PENDING_MESSAGE = "面试官正在组织语言中..."
ALLOWED_DOCUMENT_EXTENSIONS = {".pdf", ".txt", ".md", ".docx"}


class RegisterPayload(BaseModel):
    display_name: str = Field(min_length=1, max_length=60)
    email: str
    password: str = Field(min_length=6, max_length=120)


class LoginPayload(BaseModel):
    email: str
    password: str = Field(min_length=6, max_length=120)


class LangSmithConfigPayload(BaseModel):
    enabled: bool = False
    api_key: str = ""
    project: str = "interview-coach-debug"


class CandidatePayload(BaseModel):
    user_id: str = ""


class QaMessagePayload(BaseModel):
    user_id: str = ""
    message: str = ""
    action: str = "send"
    partial_reply: str = ""


class InterviewStartPayload(BaseModel):
    user_id: str = ""
    role: str


class InterviewMessagePayload(BaseModel):
    user_id: str = ""
    message: str = ""
    action: str = "send"
    partial_reply: str = ""


class GenerateReportPayload(BaseModel):
    user_id: str = ""


class NamedWorkspacePayload(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class WorkspacePreferencePayload(BaseModel):
    completed: bool = True


class ConversationPreferencePayload(BaseModel):
    preferred_mode: str = "qa"


def get_weather_snapshot() -> dict[str, str]:
    # 页面右上角天气卡片需要的数据来源。
    try:
        city = str(get_city.invoke({}))
    except Exception:
        city = "未知城市"
    try:
        weather = str(get_weather.invoke({"city": city}))
    except Exception:
        weather = "天气获取失败，请稍后重试。"
    return {"city": city, "text": weather}


def to_stream_line(payload: dict[str, Any]) -> str:
    # 流式接口统一使用“每行一个 JSON 事件”的格式返回给前端。
    return json.dumps(payload, ensure_ascii=False) + "\n"


def iter_text_chunks(text: str, chunk_size: int = 10):
    content = str(text or "")
    for index in range(0, len(content), chunk_size):
        yield content[index : index + chunk_size]


def get_current_user(request: Request, required: bool = True) -> dict[str, Any] | None:
    # 几乎所有需要登录态的接口，都会先走这个函数：
    # 从 Cookie 里取 session_token，再去数据库反查当前用户。
    token = request.cookies.get(SESSION_COOKIE_NAME, "")
    user = get_user_by_session(token)
    if required and not user:
        raise HTTPException(status_code=401, detail="当前未登录或登录已失效，请重新登录。")
    return user


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=platform_settings.secure_cookie,
        max_age=7 * 24 * 60 * 60,
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE_NAME)


def normalize_pending_messages(state: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    # 如果用户上一次流式生成时中断了，
    # 这里会把残留的 generating 消息改成 interrupted，避免前端误判状态。
    updated = False
    placeholders = {QA_PENDING_MESSAGE, INTERVIEW_PENDING_MESSAGE}
    for history_key in ["qa_history", "interview_history"]:
        for message in state.get(history_key, []) or []:
            if message.get("role") == "assistant" and message.get("status") == "generating":
                message["status"] = "interrupted"
                content = str(message.get("content", "")).strip()
                if not content or content in placeholders:
                    message["content"] = "上一条回复因网络波动或中断未能完整生成，你可以选择继续生成或重试本轮回答。"
                else:
                    message["content"] = content + "\n\n[这条回复在生成过程中中断了，可继续生成或重试。]"
                updated = True
    return state, updated


def get_workspace_state_for_user(user: dict[str, Any]) -> dict[str, Any]:
    storage_key = user["email"]
    workspace = load_workspace(user)
    candidate_state = get_active_candidate_state(workspace)
    candidate_state, updated = normalize_pending_messages(candidate_state)
    if updated:
        update_active_candidate_state(workspace, candidate_state)
        save_workspace(user, workspace)
    return workspace


def load_candidate_state_for_user(user: dict[str, Any]) -> dict[str, Any]:
    storage_key = user["email"]
    workspace = get_workspace_state_for_user(user)
    conversation = get_active_conversation(workspace)
    project = get_active_project(workspace)
    state = get_active_candidate_state(workspace)
    return {
        "user_id": storage_key,
        "display_name": user["display_name"],
        "email": user["email"],
        "project_id": project["id"],
        "project_name": project["name"],
        "conversation_id": conversation["id"],
        "conversation_name": conversation["name"],
        "conversation_preferred_mode": conversation.get("preferred_mode", "qa"),
        **state,
    }


def persist_candidate_state(user: dict[str, Any], state: dict[str, Any]) -> None:
    workspace = get_workspace_state_for_user(user)
    update_active_candidate_state(
        workspace,
        {
            "interview_history": state.get("interview_history", []),
            "qa_history": state.get("qa_history", []),
            "interview_questions": state.get("interview_questions", []),
            "interview_started": state.get("interview_started", False),
            "interview_finished": state.get("interview_finished", False),
            "interview_report": state.get("interview_report", ""),
            "interview_report_file": state.get("interview_report_file", ""),
            "latest_report_record_id": state.get("latest_report_record_id"),
            "resume_text": state.get("resume_text", ""),
            "resume_filename": state.get("resume_filename", ""),
            "interview_score": state.get("interview_score", 0),
            "interview_state": state.get("interview_state", {}),
            "pending_run_id": state.get("pending_run_id", ""),
        },
    )
    save_workspace(user, workspace)


def build_user_profile(user: dict[str, Any] | None) -> dict[str, Any]:
    if not user:
        return {"authenticated": False, "user": None}
    profile = ensure_platform_user(user)
    return {
        "authenticated": True,
        "user": {
            "id": user["id"],
            "email": user["email"],
            "display_name": user["display_name"],
            "role": profile.get("role", "candidate"),
            "organization_id": profile.get("organization_id"),
        },
    }


def build_app_payload(user: dict[str, Any] | None) -> dict[str, Any]:
    candidate = load_candidate_state_for_user(user) if user else None
    history_records = list_interview_records(user["id"]) if user else []
    workspace = get_workspace_state_for_user(user) if user else None
    role_options = list(ROLE_OPTIONS)
    if user:
        try:
            profile = ensure_platform_user(user)
            for role_name in list_configured_role_names(profile):
                if role_name not in role_options:
                    role_options.append(role_name)
        except Exception as exc:
            logger.warning("Failed to load configured role options: %s", exc)
    return {
        "auth": build_user_profile(user),
        "candidate": candidate,
        "history_records": history_records,
        "workspace": {
            "projects": list_workspace_projects(workspace) if workspace else [],
            "active_project_id": workspace.get("active_project_id") if workspace else "",
            "active_conversation_id": workspace.get("active_conversation_id") if workspace else "",
            "onboarding_completed": bool(workspace.get("onboarding_completed", False)) if workspace else False,
        },
        "weather": get_weather_snapshot(),
        "langsmith": get_langsmith_settings_from_env(),
        "meta": {
            "role_options": role_options,
            "qa": QA_WELCOME,
            "interview": INTERVIEW_WELCOME,
            "history": HISTORY_META,
        },
    }


def save_interview_report_file(candidate_state: dict[str, Any]) -> str:
    report_dir = get_abs_path("data/interview_reports")
    os.makedirs(report_dir, exist_ok=True)

    safe_name = str(candidate_state.get("display_name", "user")).strip().replace(" ", "_")
    safe_name = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in safe_name) or "user"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = os.path.join(report_dir, f"{safe_name}_{timestamp}_interview_report.md")

    role_name = candidate_state.get("interview_state", {}).get("target_role", "") or "未设置岗位"
    resume_name = candidate_state.get("resume_filename", "") or "未上传简历"
    score = candidate_state.get("interview_score", 0)
    report_content = candidate_state.get("interview_report", "")

    document = (
        "# 模拟面试报告\n\n"
        f"- 用户名：{candidate_state.get('display_name', '')}\n"
        f"- 邮箱：{candidate_state.get('email', '')}\n"
        f"- 目标岗位：{role_name}\n"
        f"- 简历文件：{resume_name}\n"
        f"- 面试得分：{score} / 100\n"
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        "---\n\n"
        f"{report_content}\n"
    )
    with open(file_path, "w", encoding="utf-8") as file:
        file.write(document)
    return file_path


def import_knowledge_files(files: list[UploadFile], user: dict[str, Any]) -> dict[str, Any]:
    from rag.vector_store import VectorStoreService

    upload_dir = get_abs_path("data/uploaded_knowledge")
    saved_names: list[str] = []
    saved_paths: list[str] = []
    for upload in files:
        extension = os.path.splitext(upload.filename or "")[1].lower()
        if extension not in ALLOWED_DOCUMENT_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f"不支持的知识库文件类型：{extension or '未知'}。")
        file_bytes = upload.file.read()
        if not file_bytes:
            continue
        if len(file_bytes) > platform_settings.max_upload_mb * 1024 * 1024:
            raise HTTPException(status_code=413, detail=f"单个文件不能超过 {platform_settings.max_upload_mb} MB。")
        save_path = save_binary_file(upload.filename or "knowledge.bin", file_bytes, upload_dir)
        saved_names.append(os.path.basename(save_path))
        saved_paths.append(save_path)
    profile = ensure_platform_user(user)
    load_results = VectorStoreService().load_document(
        metadata_context={
            "user_id": user["email"],
            "organization_id": profile.get("organization_id") or "",
            "visibility": "organization" if profile.get("role") in {"interviewer", "admin"} and profile.get("organization_id") else "private",
        },
        paths=saved_paths,
    )
    register_knowledge_documents(
        profile,
        [
            {
                "filename": os.path.basename(path),
                "checksum": get_file_md5_hex(path),
                "chunk_count": next(
                    (item.get("chunk_count", 0) for item in load_results if item.get("path") == path),
                    0,
                ),
                "metadata": {"source_path": path},
            }
            for path in saved_paths
        ],
    )
    return {"count": len(saved_names), "names": saved_names}


def get_retry_context(history: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str, str]:
    if not history:
        raise HTTPException(status_code=400, detail="当前没有可继续的历史消息。")

    base_history = deepcopy(history)
    partial_reply = ""
    if base_history and base_history[-1].get("role") == "assistant":
        partial_reply = str(base_history[-1].get("content", "")).strip()
        base_history.pop()

    for message in reversed(base_history):
        if message.get("role") == "user":
            return base_history, str(message.get("content", "")).strip(), partial_reply

    raise HTTPException(status_code=400, detail="未找到可继续的上一轮用户消息。")


def build_resume_message(last_user_message: str, partial_reply: str, explicit_partial: str) -> str:
    current_partial = explicit_partial.strip() or partial_reply.strip()
    if not current_partial:
        return last_user_message
    return (
        f"{last_user_message}\n\n"
        "你上一条回复在流式输出中断了。请直接从下面这段未完成内容之后继续，不要重复前面已经说过的话：\n"
        f"{current_partial}"
    )


def ensure_interview_started(candidate_state: dict[str, Any]) -> None:
    if not candidate_state.get("interview_started"):
        raise HTTPException(status_code=400, detail="请先开始面试。")
    if candidate_state.get("interview_finished"):
        raise HTTPException(status_code=400, detail="本轮面试已结束，请重新开始。")


def persist_workspace_state(user: dict[str, Any], workspace: dict[str, Any]) -> None:
    save_workspace(user, workspace)


def require_named_value(name: str, field_name: str) -> str:
    normalized = (name or "").strip()
    if not normalized:
        raise HTTPException(status_code=400, detail=f"{field_name}不能为空。")
    return normalized


def activate_project_and_first_conversation(workspace: dict[str, Any], project_id: str) -> None:
    project = get_project_by_id(workspace, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在。")
    workspace["active_project_id"] = project["id"]
    if not project.get("conversations"):
        raise HTTPException(status_code=400, detail="当前项目下没有可用会话。")
    workspace["active_conversation_id"] = project["conversations"][0]["id"]


def create_project_in_workspace(workspace: dict[str, Any], name: str) -> dict[str, Any]:
    project_name = require_named_value(name, "项目名称")
    now = datetime.now().isoformat()
    project = {
        "id": os.urandom(8).hex(),
        "name": project_name,
        "pinned": False,
        "created_at": now,
        "updated_at": now,
        "conversations": [],
    }
    workspace.setdefault("projects", []).append(project)
    return project


def create_conversation_in_project(workspace: dict[str, Any], project_id: str, name: str) -> dict[str, Any]:
    project = get_project_by_id(workspace, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在。")
    conversation_name = require_named_value(name, "会话名称")
    now = datetime.now().isoformat()
    conversation = {
        "id": os.urandom(8).hex(),
        "name": conversation_name,
        "pinned": False,
        "preferred_mode": "qa",
        "created_at": now,
        "updated_at": now,
        "state": {
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
        },
    }
    project.setdefault("conversations", []).append(conversation)
    project["updated_at"] = now
    workspace["active_project_id"] = project["id"]
    workspace["active_conversation_id"] = conversation["id"]
    return conversation


def delete_project_from_workspace(workspace: dict[str, Any], project_id: str) -> None:
    projects = workspace.get("projects", [])
    if len(projects) <= 1:
        raise HTTPException(status_code=400, detail="至少需要保留一个项目。")
    next_projects = [project for project in projects if project.get("id") != project_id]
    if len(next_projects) == len(projects):
        raise HTTPException(status_code=404, detail="项目不存在。")
    workspace["projects"] = next_projects
    activate_project_and_first_conversation(workspace, next_projects[0]["id"])


def delete_conversation_from_workspace(workspace: dict[str, Any], conversation_id: str) -> None:
    active_project = None
    target_index = -1
    for project in workspace.get("projects", []):
        for index, conversation in enumerate(project.get("conversations", [])):
            if conversation.get("id") == conversation_id:
                active_project = project
                target_index = index
                break
        if active_project:
            break

    if not active_project or target_index < 0:
        raise HTTPException(status_code=404, detail="会话不存在。")
    if len(active_project.get("conversations", [])) <= 1:
        raise HTTPException(status_code=400, detail="每个项目至少需要保留一个会话。")

    active_project["conversations"].pop(target_index)
    active_project["updated_at"] = datetime.now().isoformat()
    workspace["active_project_id"] = active_project["id"]
    workspace["active_conversation_id"] = active_project["conversations"][0]["id"]


@asynccontextmanager
async def lifespan(_: FastAPI):
    # FastAPI 生命周期钩子：
    # 服务启动时会先执行 yield 之前的代码，服务关闭时执行 yield 之后的代码。
    # 当前项目在这里初始化数据库，确保 API 正式接收请求前数据层已经可用。
    # 只初始化当前选择的存储：正式模式使用 MySQL，
    # 未开启平台数据库时才创建本地 SQLite，保持轻量开发体验。
    try:
        if not init_platform_database():
            init_db()
    except Exception as exc:
        raise RuntimeError(
            "平台数据库连接失败。开发模式请设置 ENABLE_PLATFORM_DB=false；"
            "启用正式模式前请先启动 MySQL，并创建 DATABASE_URL 指定的数据库。"
        ) from exc
    yield


app = FastAPI(title="智能面试辅导系统 API", version="3.0.0", lifespan=lifespan)
# 允许前端开发服务（5173）和后端托管页面（8000/8080）访问接口。
# CORS 是浏览器同源策略相关配置：
# 如果前端跑在 http://localhost:5173，后端跑在 http://127.0.0.1:8080，
# 协议/域名/端口有一个不同就属于跨域，需要后端明确允许。
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# 把前端打包产物挂到 /frontend-assets 下，方便 FastAPI 同时托管前后端。
app.mount(
    "/frontend-assets",
    StaticFiles(directory=get_abs_path("frontend/dist"), check_dir=False),
    name="frontend-assets",
)

_service = None
_service_lock = threading.Lock()


def get_service():
    """Lazily initialize heavy LangChain/LangGraph model dependencies."""
    # 模型、Embedding、Chroma、LangGraph 初始化都比较重。
    # 如果应用启动时就初始化，可能导致启动很慢或数据库还没准备好。
    # 所以这里采用“懒加载”：第一次真正请求问答/面试时才创建服务实例。
    #
    # _service_lock 用于防止并发请求同时进来时重复创建多个 service。
    global _service
    if _service is None:
        with _service_lock:
            if _service is None:
                from agent.interview_assistant_service import InterviewAssistantService

                _service = InterviewAssistantService()
    return _service


def iter_qa_chat_stream(service, message: str, history: list[dict], tool_context: dict[str, Any]):
    """Call the QA stream method while tolerating older service implementations.

    Some deployed copies may still expose qa_chat_stream(message, history). The
    current implementation accepts an extra tenant/tool context so RAG and tool
    calls can filter data by user and organization.
    """
    try:
        # 新版本 service 支持 tool_context，用于把 user_id、organization_id、resume_text
        # 传给工具调用和 RAG 检索，做数据隔离和上下文增强。
        yield from service.qa_chat_stream(message, history, tool_context)
    except TypeError as exc:
        if "qa_chat_stream" not in str(exc) or "positional arguments" not in str(exc):
            raise
        logger.warning("qa_chat_stream does not accept tool_context; falling back to legacy signature.")
        yield from service.qa_chat_stream(message, history)


def call_interview_chat_compat(
    service,
    message: str,
    history: list[dict],
    interview_state: dict,
    interview_questions: list,
    run_id: str | None = None,
):
    """Call interview_chat while remaining compatible with older service signatures."""
    # 兼容层：之前的 interview_chat 可能没有 run_id 参数。
    # 新版通过 run_id 把 Agent 节点事件写入 RunStore/Redis，前端才能展示执行过程。
    signature = inspect.signature(service.interview_chat)
    if "run_id" in signature.parameters:
        return service.interview_chat(message, history, interview_state, interview_questions, run_id)
    return service.interview_chat(message, history, interview_state, interview_questions)


role_manager = InterviewRoleManager()
app.include_router(build_platform_router(get_current_user))


# ------------------------------
# 基础页与初始化接口
# ------------------------------
@app.get("/")
def frontend_index():
    dist_index = get_abs_path("frontend/dist/index.html")
    if os.path.exists(dist_index):
        return FileResponse(dist_index)
    return HTMLResponse(
        """
        <html lang="zh-CN">
          <head>
            <meta charset="UTF-8" />
            <title>前端尚未构建</title>
            <style>
              body { font-family: Arial, sans-serif; padding: 40px; line-height: 1.7; color: #1f3f63; }
              code { background: #eef5ff; padding: 2px 6px; border-radius: 6px; }
            </style>
          </head>
          <body>
            <h2>前端尚未构建</h2>
            <p>请先进入 <code>frontend</code> 目录安装依赖并构建：</p>
            <pre>npm install
npm run build</pre>
          </body>
        </html>
        """
    )


@app.get("/api/health")
def health_check():
    return {"status": "ok"}


@app.get("/api/bootstrap")
def bootstrap(request: Request):
    # 前端初始化时最关键的接口：
    # 一次性返回 auth / candidate / workspace / weather / meta 等首屏所需数据。
    user = get_current_user(request, required=False)
    return build_app_payload(user)


# ------------------------------
# 认证接口
# ------------------------------
@app.post("/api/auth/register")
def register(payload: RegisterPayload):
    try:
        user = create_user(payload.email, payload.display_name, payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    token = create_session(user["id"])
    response = JSONResponse(build_app_payload(user))
    set_session_cookie(response, token)
    return response


@app.post("/api/auth/login")
def login(payload: LoginPayload):
    user = verify_user(payload.email, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="邮箱或密码错误。")

    token = create_session(user["id"])
    response = JSONResponse(build_app_payload(user))
    set_session_cookie(response, token)
    return response


@app.post("/api/auth/logout")
def logout(request: Request):
    token = request.cookies.get(SESSION_COOKIE_NAME, "")
    delete_session(token)
    response = JSONResponse({"success": True})
    clear_session_cookie(response)
    return response


@app.get("/api/auth/me")
def get_me(request: Request):
    user = get_current_user(request)
    return build_user_profile(user)


# ------------------------------
# 工作台 / 项目 / 会话管理接口
# ------------------------------
@app.post("/api/candidate/load")
def load_candidate(request: Request, _: CandidatePayload):
    # 前端如果发现当前 candidate 还没准备好，会先调这个接口补齐当前会话状态。
    user = get_current_user(request)
    return build_app_payload(user)


@app.post("/api/workspace/onboarding")
def update_onboarding(request: Request, payload: WorkspacePreferencePayload):
    user = get_current_user(request)
    workspace = get_workspace_state_for_user(user)
    workspace["onboarding_completed"] = bool(payload.completed)
    persist_workspace_state(user, workspace)
    return build_app_payload(user)


@app.post("/api/workspace/projects")
def create_project(request: Request, payload: NamedWorkspacePayload):
    user = get_current_user(request)
    workspace = get_workspace_state_for_user(user)
    create_project_in_workspace(workspace, payload.name)
    persist_workspace_state(user, workspace)
    return build_app_payload(user)


@app.patch("/api/workspace/projects/{project_id}")
def rename_project(request: Request, project_id: str, payload: NamedWorkspacePayload):
    user = get_current_user(request)
    workspace = get_workspace_state_for_user(user)
    project = get_project_by_id(workspace, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在。")
    project["name"] = require_named_value(payload.name, "项目名称")
    project["updated_at"] = datetime.now().isoformat()
    persist_workspace_state(user, workspace)
    return build_app_payload(user)


@app.post("/api/workspace/projects/{project_id}/activate")
def activate_project(request: Request, project_id: str):
    user = get_current_user(request)
    workspace = get_workspace_state_for_user(user)
    activate_project_and_first_conversation(workspace, project_id)
    persist_workspace_state(user, workspace)
    return build_app_payload(user)


@app.post("/api/workspace/projects/{project_id}/pin")
def pin_project(request: Request, project_id: str):
    user = get_current_user(request)
    workspace = get_workspace_state_for_user(user)
    project = get_project_by_id(workspace, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在。")
    project["pinned"] = not bool(project.get("pinned", False))
    project["updated_at"] = datetime.now().isoformat()
    persist_workspace_state(user, workspace)
    return build_app_payload(user)


@app.delete("/api/workspace/projects/{project_id}")
def delete_project(request: Request, project_id: str):
    user = get_current_user(request)
    workspace = get_workspace_state_for_user(user)
    delete_project_from_workspace(workspace, project_id)
    persist_workspace_state(user, workspace)
    return build_app_payload(user)


@app.post("/api/workspace/projects/{project_id}/conversations")
def create_conversation(request: Request, project_id: str, payload: NamedWorkspacePayload):
    user = get_current_user(request)
    workspace = get_workspace_state_for_user(user)
    create_conversation_in_project(workspace, project_id, payload.name)
    persist_workspace_state(user, workspace)
    return build_app_payload(user)


@app.patch("/api/workspace/conversations/{conversation_id}")
def rename_conversation(request: Request, conversation_id: str, payload: NamedWorkspacePayload):
    user = get_current_user(request)
    workspace = get_workspace_state_for_user(user)
    conversation = get_conversation_by_id(workspace, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="会话不存在。")
    conversation["name"] = require_named_value(payload.name, "会话名称")
    conversation["updated_at"] = datetime.now().isoformat()
    persist_workspace_state(user, workspace)
    return build_app_payload(user)


@app.post("/api/workspace/conversations/{conversation_id}/activate")
def activate_conversation(request: Request, conversation_id: str):
    user = get_current_user(request)
    workspace = get_workspace_state_for_user(user)
    conversation = get_conversation_by_id(workspace, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="会话不存在。")
    workspace["active_conversation_id"] = conversation["id"]
    for project in workspace.get("projects", []):
        if any(item.get("id") == conversation["id"] for item in project.get("conversations", [])):
            workspace["active_project_id"] = project["id"]
            break
    persist_workspace_state(user, workspace)
    return build_app_payload(user)


@app.post("/api/workspace/conversations/{conversation_id}/pin")
def pin_conversation(request: Request, conversation_id: str):
    user = get_current_user(request)
    workspace = get_workspace_state_for_user(user)
    conversation = get_conversation_by_id(workspace, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="会话不存在。")
    conversation["pinned"] = not bool(conversation.get("pinned", False))
    conversation["updated_at"] = datetime.now().isoformat()
    persist_workspace_state(user, workspace)
    return build_app_payload(user)


@app.post("/api/workspace/conversations/{conversation_id}/mode")
def update_conversation_mode(request: Request, conversation_id: str, payload: ConversationPreferencePayload):
    user = get_current_user(request)
    workspace = get_workspace_state_for_user(user)
    conversation = get_conversation_by_id(workspace, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="会话不存在。")
    preferred_mode = (payload.preferred_mode or "qa").strip().lower()
    if preferred_mode not in {"qa", "interview", "history"}:
        raise HTTPException(status_code=400, detail="不支持的会话模式。")
    conversation["preferred_mode"] = preferred_mode
    conversation["updated_at"] = datetime.now().isoformat()
    persist_workspace_state(user, workspace)
    return build_app_payload(user)


@app.delete("/api/workspace/conversations/{conversation_id}")
def delete_conversation(request: Request, conversation_id: str):
    user = get_current_user(request)
    workspace = get_workspace_state_for_user(user)
    delete_conversation_from_workspace(workspace, conversation_id)
    persist_workspace_state(user, workspace)
    return build_app_payload(user)


# ------------------------------
# 配置 / 知识库 / 简历接口
# ------------------------------
@app.post("/api/qa/clear")
def clear_qa_history(request: Request, _: CandidatePayload):
    user = get_current_user(request)
    candidate_state = load_candidate_state_for_user(user)
    candidate_state["qa_history"] = []
    persist_candidate_state(user, candidate_state)
    return {"candidate": candidate_state}


@app.post("/api/langsmith/config")
def update_langsmith_config(payload: LangSmithConfigPayload):
    enabled, status_message = configure_langsmith(
        enabled=payload.enabled,
        api_key=payload.api_key,
        project=payload.project,
    )
    return {
        "enabled": enabled,
        "project": (payload.project or "interview-coach-debug").strip() or "interview-coach-debug",
        "status_message": status_message,
    }


@app.get("/api/weather")
def get_weather_panel():
    return get_weather_snapshot()


@app.post("/api/knowledge/import")
def import_knowledge(request: Request, files: list[UploadFile] = File(default=[])):
    # 知识库导入支持两种方式：
    # 1. 传新文件进来：保存文件并更新向量库
    # 2. 不传文件：直接扫描现有目录并刷新知识库
    user = get_current_user(request)
    from rag.vector_store import VectorStoreService

    with tracing_context_if_enabled("knowledge_import", tags=["knowledge-base", "import"]):
        if files:
            return import_knowledge_files(files, user)
        VectorStoreService().load_document()
        return {"count": 0, "names": [], "message": "已扫描并更新现有知识库。"}


@app.post("/api/resume/upload")
def upload_resume(request: Request, file: UploadFile = File(...)):
    # 上传简历后，后端会保存原文件、解析文本，
    # 再把 resume_text / resume_filename 写回当前会话状态。
    user = get_current_user(request)
    candidate_state = load_candidate_state_for_user(user)
    resume_dir = get_abs_path("data/uploaded_resumes")
    file_bytes = file.file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="上传的简历为空。")
    extension = os.path.splitext(file.filename or "")[1].lower()
    if extension not in ALLOWED_DOCUMENT_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"不支持的简历文件类型：{extension or '未知'}。")
    if len(file_bytes) > platform_settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"简历文件不能超过 {platform_settings.max_upload_mb} MB。")

    save_path = save_binary_file(file.filename or "resume.bin", file_bytes, resume_dir)
    candidate_state["resume_text"] = extract_text_from_file(save_path)
    candidate_state["resume_filename"] = os.path.basename(save_path)
    persist_candidate_state(user, candidate_state)
    return {"candidate": candidate_state}


@app.post("/api/resume/clear")
def clear_resume(request: Request, _: CandidatePayload):
    user = get_current_user(request)
    candidate_state = load_candidate_state_for_user(user)
    candidate_state["resume_text"] = ""
    candidate_state["resume_filename"] = ""
    persist_candidate_state(user, candidate_state)
    return {"candidate": candidate_state}


# ------------------------------
# 模拟面试主流程接口
# ------------------------------
@app.post("/api/interview/start")
def start_interview(request: Request, payload: InterviewStartPayload):
    # 开始面试时，后端会初始化 interview_state，
    # 并生成第一句“开场白 + 首个问题”。
    user = get_current_user(request)
    candidate_state = load_candidate_state_for_user(user)
    selected_role = payload.role.strip() or "通用技术岗位"
    profile = ensure_platform_user(user)

    with tracing_context_if_enabled(
        "start_interview",
        tags=["interview-mode", "start"],
        metadata={"user_id": user["email"], "role": selected_role},
    ):
        template_profile = get_interview_template_profile(profile, selected_role)
        if template_profile.get("dimensions") or template_profile.get("question_bank"):
            get_service().role_manager.set_runtime_profile(
                selected_role,
                template_profile.get("dimensions", []),
                [item.get("name", "") for item in template_profile.get("dimensions", [])],
                template_profile.get("question_bank", []),
            )
        try:
            start_result = get_service().start_role_interview(
                selected_role,
                candidate_state.get("interview_history", []),
                candidate_state.get("resume_text", ""),
                candidate_state.get("resume_filename", ""),
                {
                    "user_id": user["email"],
                    "platform_user_id": profile.get("platform_user_id", profile.get("id")),
                    "organization_id": profile.get("organization_id"),
                },
            )
        except Exception as exc:
            logger.exception("Failed to generate the first interview question, falling back to role template: %s", exc)
            fallback_state = get_service().state_machine.start_interview(selected_role)
            fallback_question = role_manager.get_first_question(selected_role)
            fallback_state = get_service().state_machine.update_current_question(fallback_state, fallback_question)
            fallback_state.setdefault("multi_agent", {})
            fallback_state["fallback_reason"] = "first_question_generation_failed"
            start_result = {
                "question": fallback_question,
                "question_to_record": fallback_question,
                "state": fallback_state,
                "evidence": [],
            }

    first_question = start_result["question"]
    try:
        task_id = create_interview_task(profile, selected_role)
    except Exception as exc:
        logger.warning("Failed to create interview task, continuing without dashboard task: %s", exc)
        task_id = None
    start_result["state"]["interview_task_id"] = task_id
    if template_profile:
        configured_plan = template_profile.get("dimensions", [])
        if not configured_plan and template_profile.get("question_bank"):
            seen_dimensions: set[str] = set()
            configured_plan = []
            for item in template_profile.get("question_bank", []):
                dimension_name = str(item.get("dimension", "")).strip()
                if dimension_name and dimension_name not in seen_dimensions:
                    seen_dimensions.add(dimension_name)
                    configured_plan.append(
                        {
                            "name": dimension_name,
                            "focus": f"{dimension_name} 相关能力、项目经验与问题解决思路",
                        }
                    )
        start_result["state"].setdefault("multi_agent", {})
        start_result["state"]["multi_agent"]["template_profile"] = template_profile
        start_result["state"]["multi_agent"].setdefault("interview_plan", configured_plan)
        start_result["state"]["multi_agent"].setdefault("question_bank", template_profile.get("question_bank", []))
        start_result["state"]["configured_question_count"] = template_profile.get("question_count", 8)
    try:
        record_interview_question(task_id, first_question, start_result.get("evidence", []))
    except Exception as exc:
        logger.warning("Failed to record first interview question: %s", exc)
    opener = (
        f"你好，我们今天面试的岗位是 {selected_role}。"
        + ("我也会结合你上传的简历来提问。\n\n" if candidate_state.get("resume_text") else "我们先按岗位要求展开。\n\n")
        + first_question
    )

    candidate_state["interview_history"] = [{"role": "assistant", "content": opener, "status": "done"}]
    candidate_state["interview_questions"] = [str(start_result.get("question_to_record", first_question)).strip() or first_question]
    candidate_state["interview_report"] = ""
    candidate_state["interview_report_file"] = ""
    candidate_state["latest_report_record_id"] = None
    candidate_state["interview_score"] = 0
    candidate_state["interview_started"] = True
    candidate_state["interview_finished"] = False
    candidate_state["interview_state"] = start_result["state"]
    persist_candidate_state(user, candidate_state)
    return {"candidate": candidate_state, "reply": opener}


@app.post("/api/interview/end")
def end_interview(request: Request, _: CandidatePayload):
    user = get_current_user(request)
    candidate_state = load_candidate_state_for_user(user)
    candidate_state["interview_finished"] = True
    candidate_state["interview_score"] = get_service().calculate_interview_score(
        candidate_state.get("interview_state", {}),
        candidate_state.get("interview_history", []),
    )
    interview_state = candidate_state.get("interview_state", {})
    if interview_state:
        interview_state["finished"] = True
        candidate_state["interview_state"] = interview_state
    mark_interview_ended(interview_state.get("interview_task_id"), candidate_state["interview_score"])
    persist_candidate_state(user, candidate_state)
    return {"candidate": candidate_state}


@app.post("/api/interview/report")
def generate_report(request: Request, _: GenerateReportPayload):
    # 报告生成阶段会完成：
    # 1. 计算分数
    # 2. 生成报告文本
    # 3. 落地成 Markdown 文件
    # 4. 同时写入 SQLite 历史记录
    user = get_current_user(request)
    candidate_state = load_candidate_state_for_user(user)

    with tracing_context_if_enabled(
        "interview_report",
        tags=["interview-mode", "report"],
        metadata={"user_id": user["email"], "role": candidate_state.get("interview_state", {}).get("target_role", "")},
    ):
        candidate_state["interview_score"] = get_service().calculate_interview_score(
            candidate_state.get("interview_state", {}),
            candidate_state.get("interview_history", []),
        )
        candidate_state["interview_report"] = get_service().generate_report(
            candidate_state.get("interview_history", []),
            candidate_state.get("interview_questions", []),
            candidate_state.get("interview_state", {}),
        )
        candidate_state["interview_report_file"] = save_interview_report_file(candidate_state)
        candidate_state["latest_report_record_id"] = create_interview_record(
            user_id=user["id"],
            role_name=candidate_state.get("interview_state", {}).get("target_role", ""),
            resume_filename=candidate_state.get("resume_filename", ""),
            score=candidate_state.get("interview_score", 0),
            report_text=candidate_state.get("interview_report", ""),
            report_file=candidate_state.get("interview_report_file", ""),
            history_json=json.dumps(candidate_state.get("interview_history", []), ensure_ascii=False),
            interview_state_json=json.dumps(candidate_state.get("interview_state", {}), ensure_ascii=False),
        )
        finalize_interview_task(
            candidate_state.get("interview_state", {}).get("interview_task_id"),
            candidate_state["interview_score"],
            candidate_state["interview_report"],
            candidate_state["interview_report_file"],
            candidate_state.get("interview_state", {}).get("multi_agent", {}).get("last_evidence", []),
        )

    persist_candidate_state(user, candidate_state)
    return {
        "candidate": candidate_state,
        "report": candidate_state["interview_report"],
        "report_file": candidate_state["interview_report_file"],
        "record_id": candidate_state["latest_report_record_id"],
    }


@app.get("/api/interview/report/download")
def download_latest_report(request: Request):
    user = get_current_user(request)
    candidate_state = load_candidate_state_for_user(user)
    report_file = str(candidate_state.get("interview_report_file", "")).strip()
    if not report_file or not os.path.exists(report_file):
        raise HTTPException(status_code=404, detail="当前用户还没有可下载的报告文件。")
    return FileResponse(report_file, media_type="text/markdown; charset=utf-8", filename=os.path.basename(report_file))


@app.get("/api/history/interviews")
def get_history_records(request: Request):
    user = get_current_user(request)
    return {"records": list_interview_records(user["id"])}


# ------------------------------
# 历史记录与下载接口
# ------------------------------
@app.get("/api/history/interviews/{record_id}")
def get_history_record_detail(request: Request, record_id: int):
    user = get_current_user(request)
    record = get_interview_record(user["id"], record_id)
    if not record:
        raise HTTPException(status_code=404, detail="未找到该历史面试记录。")
    return {
        "record": {
            **record,
            "history": json.loads(record["history_json"] or "[]"),
            "interview_state": json.loads(record["interview_state_json"] or "{}"),
        }
    }


@app.post("/api/history/interviews/{record_id}/restore")
def restore_history_record(request: Request, record_id: int):
    user = get_current_user(request)
    record = get_interview_record(user["id"], record_id)
    if not record:
        raise HTTPException(status_code=404, detail="未找到该历史面试记录。")

    candidate_state = load_candidate_state_for_user(user)
    candidate_state["interview_history"] = json.loads(record["history_json"] or "[]")
    candidate_state["interview_state"] = json.loads(record["interview_state_json"] or "{}")
    candidate_state["interview_questions"] = [
        item.get("content", "")
        for item in candidate_state["interview_history"]
        if item.get("role") == "assistant" and ("？" in str(item.get("content", "")) or "?" in str(item.get("content", "")))
    ]
    candidate_state["interview_started"] = True
    candidate_state["interview_finished"] = True
    candidate_state["interview_score"] = record["score"]
    candidate_state["interview_report"] = record["report_text"]
    candidate_state["interview_report_file"] = record["report_file"]
    candidate_state["latest_report_record_id"] = record["id"]
    persist_candidate_state(user, candidate_state)
    return {"candidate": candidate_state}


@app.get("/api/history/interviews/{record_id}/download")
def download_history_report(request: Request, record_id: int):
    user = get_current_user(request)
    record = get_interview_record(user["id"], record_id)
    if not record or not record.get("report_file") or not os.path.exists(record["report_file"]):
        raise HTTPException(status_code=404, detail="未找到该报告文件。")
    return FileResponse(
        record["report_file"],
        media_type="text/markdown; charset=utf-8",
        filename=os.path.basename(record["report_file"]),
    )


@app.get("/api/roles")
def get_role_options(request: Request):
    role_options = list(ROLE_OPTIONS)
    try:
        user = get_current_user(request)
        profile = ensure_platform_user(user)
        for role_name in list_configured_role_names(profile):
            if role_name not in role_options:
                role_options.append(role_name)
    except Exception as exc:
        logger.warning("Failed to load configured role options from /api/roles: %s", exc)
    return {"role_options": role_options, "role_dimensions": {role: role_manager.get_dimensions(role) for role in role_options}}


# ------------------------------
# 问答模式接口
# ------------------------------
@app.post("/api/qa/chat")
def qa_chat(request: Request, payload: QaMessagePayload):
    # 非流式问答：一次性生成完整答案再返回。
    user = get_current_user(request)
    candidate_state = load_candidate_state_for_user(user)
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="消息不能为空。")

    candidate_state["qa_history"].append({"role": "user", "content": message})
    profile = ensure_platform_user(user)
    tool_context = {
        "user_id": user["email"],
        "organization_id": profile.get("organization_id"),
        "resume_text": candidate_state.get("resume_text", ""),
    }
    with tracing_context_if_enabled("qa_chat", tags=["qa-mode"], metadata={"user_id": user["email"], "mode": "qa"}):
        answer = get_service().qa_chat(message, candidate_state["qa_history"], tool_context).strip()
    answer = answer or "这次没有成功生成回答，请稍后重试。"
    candidate_state["qa_history"].append({"role": "assistant", "content": answer, "status": "done"})
    persist_candidate_state(user, candidate_state)
    return {"candidate": candidate_state, "reply": answer}


@app.post("/api/qa/chat/stream")
async def qa_chat_stream(request: Request, payload: QaMessagePayload):
    # 流式问答：后端会持续产出 status / chunk / done 事件。
    #
    # FastAPI 关键点：
    # - 普通接口 return dict，前端一次性拿到 JSON。
    # - 流式接口 return StreamingResponse，内部生成器不断 yield 文本行。
    #
    # 前端关键点：
    # - fetch 读取这个响应体。
    # - getReader() 持续拿到每一行 NDJSON。
    # - 解析到 chunk 就追加到聊天气泡。
    user = get_current_user(request)
    candidate_state = load_candidate_state_for_user(user)
    action = (payload.action or "send").strip().lower()
    profile = ensure_platform_user(user)
    tool_context = {
        "user_id": user["email"],
        "organization_id": profile.get("organization_id"),
        "resume_text": candidate_state.get("resume_text", ""),
    }

    if action == "send":
        message = payload.message.strip()
        if not message:
            raise HTTPException(status_code=400, detail="消息不能为空。")
        candidate_state["qa_history"].append({"role": "user", "content": message})
        model_history = candidate_state["qa_history"]
    else:
        candidate_state["qa_history"], original_message, partial_reply = get_retry_context(candidate_state.get("qa_history", []))
        message = original_message if action == "retry" else build_resume_message(original_message, partial_reply, payload.partial_reply)
        model_history = candidate_state["qa_history"] if action == "retry" else candidate_state["qa_history"][:-1]

    async def event_stream():
        # event_stream 是一个异步生成器。
        # 每次 yield 一行 JSON，浏览器端就能更早收到一段内容。
        streamed_text = ""
        status = "done"
        try:
            yield to_stream_line({"type": "status", "content": "正在检索知识库..."})
            yield to_stream_line({"type": "status", "content": "正在组织回答..."})

            loop = asyncio.get_running_loop()
            chunk_queue: asyncio.Queue[tuple[str, Any]] = asyncio.Queue()

            def produce_model_chunks() -> None:
                # LangChain/模型 SDK 多数是同步迭代器。
                # 为了不阻塞 FastAPI 的事件循环，把同步模型流放到单独线程里跑，
                # 再通过 asyncio.Queue 把 chunk 送回异步 event_stream。
                try:
                    with tracing_context_if_enabled(
                        "qa_chat_stream",
                        tags=["qa-mode", "stream", action],
                        metadata={"user_id": user["email"], "mode": "qa"},
                    ):
                        for model_chunk in iter_qa_chat_stream(get_service(), message, model_history, tool_context):
                            loop.call_soon_threadsafe(chunk_queue.put_nowait, ("chunk", model_chunk))
                except Exception as producer_error:
                    loop.call_soon_threadsafe(chunk_queue.put_nowait, ("error", producer_error))
                finally:
                    loop.call_soon_threadsafe(chunk_queue.put_nowait, ("done", None))

            producer_task = asyncio.create_task(asyncio.to_thread(produce_model_chunks))
            while True:
                item_type, item = await chunk_queue.get()
                if item_type == "done":
                    break
                if item_type == "error":
                    raise item
                if await request.is_disconnected():
                    # 浏览器断开连接时，不继续向前端 yield。
                    # 问答模式这里把本轮状态标记为 interrupted。
                    status = "interrupted"
                    producer_task.add_done_callback(lambda completed: completed.exception() if not completed.cancelled() else None)
                    break
                chunk = str(item or "")
                streamed_text += chunk
                # chunk 事件是真正展示在 AI 气泡里的文本增量。
                yield to_stream_line({"type": "chunk", "content": chunk})

            final_text = streamed_text or "这次回复在生成过程中被中断了。"
            candidate_state["qa_history"].append({"role": "assistant", "content": final_text, "status": status})
            # 流式结束后再持久化完整 assistant 回复。
            # 这样刷新页面后，问答历史不会丢失。
            persist_candidate_state(user, candidate_state)

            if status == "done":
                yield to_stream_line({"type": "done", "candidate": candidate_state, "reply": final_text})
        except Exception as exc:
            error_text = str(exc) or "问答流式响应失败，请稍后重试。"
            candidate_state["qa_history"].append({"role": "assistant", "content": error_text, "status": "interrupted"})
            persist_candidate_state(user, candidate_state)
            yield to_stream_line({"type": "error", "detail": error_text})

    return StreamingResponse(event_stream(), media_type="application/x-ndjson; charset=utf-8")


@app.post("/api/interview/message")
def interview_message(request: Request, payload: InterviewMessagePayload):
    # 非流式面试回答处理：一次性返回完整下一轮回复。
    user = get_current_user(request)
    candidate_state = load_candidate_state_for_user(user)
    ensure_interview_started(candidate_state)

    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="回答不能为空。")

    candidate_state["interview_history"].append({"role": "user", "content": message})
    with tracing_context_if_enabled(
        "interview_chat",
        tags=["interview-mode"],
        metadata={"user_id": user["email"], "role": candidate_state.get("interview_state", {}).get("target_role", "")},
    ):
        result = call_interview_chat_compat(
            get_service(),
            message,
            candidate_state["interview_history"],
            candidate_state.get("interview_state", {}),
            candidate_state.get("interview_questions", []),
        )

    candidate_state["interview_state"] = result.get("state", candidate_state.get("interview_state", {}))
    evaluation_history = candidate_state["interview_state"].get("multi_agent", {}).get("evaluations", [])
    record_interview_answer(
        candidate_state["interview_state"].get("interview_task_id"),
        message,
        evaluation_history[-1] if evaluation_history else {},
    )
    candidate_state["interview_score"] = get_service().calculate_interview_score(
        candidate_state["interview_state"], candidate_state["interview_history"]
    )
    reply = str(result.get("reply", "")).strip() or "这轮没有成功生成追问，你可以再补充一下刚才的回答。"
    question_to_record = str(result.get("question_to_record", "")).strip()
    if question_to_record:
        candidate_state["interview_questions"].append(question_to_record)
        record_interview_question(
            candidate_state["interview_state"].get("interview_task_id"),
            question_to_record,
            result.get("evidence", []),
        )
    candidate_state["interview_history"].append({"role": "assistant", "content": reply, "status": "done"})
    if candidate_state.get("interview_state", {}).get("finished"):
        candidate_state["interview_finished"] = True
        mark_interview_ended(
            candidate_state["interview_state"].get("interview_task_id"),
            candidate_state["interview_score"],
        )
    persist_candidate_state(user, candidate_state)
    return {"candidate": candidate_state, "reply": reply, "action": str(result.get("action", "")).strip()}


@app.post("/api/interview/message/stream")
async def interview_message_stream(request: Request, payload: InterviewMessagePayload):
    # 流式面试回答处理：这是模拟面试模式最关键的接口之一。
    #
    # 和问答流式相比，面试流式多了 Agent Run：
    # - 每次用户回答都会创建一个 run_id。
    # - LangGraph / 多 Agent 执行时把节点事件写入 agent_run_store。
    # - 后端轮询这些事件并 yield 给前端。
    # - 前端用 AgentExecutionPanel 展示“分析简历/评估回答/检索知识”等过程。
    user = get_current_user(request)
    candidate_state = load_candidate_state_for_user(user)
    ensure_interview_started(candidate_state)

    action = (payload.action or "send").strip().lower()
    if action == "send":
        message = payload.message.strip()
        if not message:
            raise HTTPException(status_code=400, detail="回答不能为空。")
        candidate_state["interview_history"].append({"role": "user", "content": message})
        model_history = candidate_state["interview_history"]
        model_state = candidate_state.get("interview_state", {})
    else:
        candidate_state["interview_history"], original_message, partial_reply = get_retry_context(candidate_state.get("interview_history", []))
        message = original_message if action == "retry" else build_resume_message(original_message, partial_reply, payload.partial_reply)
        model_history = candidate_state["interview_history"]
        model_state = candidate_state.get("interview_state", {})

    async def event_stream():
        streamed_text = ""
        status = "done"
        profile = ensure_platform_user(user)
        # run_id 是一次 Agent 工作流的唯一编号。
        # 它既用于前端取消生成，也用于断线后恢复结果。
        run_id = agent_run_store.create(
            "interview_turn",
            profile.get("platform_user_id", profile.get("id")),
            profile.get("organization_id"),
            {"message": message[:500], "action": action},
        )
        candidate_state["pending_run_id"] = run_id
        # 先把 pending_run_id 持久化，防止前端连接断开后找不回本次运行。
        persist_candidate_state(user, candidate_state)
        try:
            yield to_stream_line({"type": "run_started", "run_id": run_id, "node": "workflow", "content": "面试工作流已启动"})
            if candidate_state.get("resume_text"):
                yield to_stream_line({"type": "status", "content": "正在分析简历..."})

            with tracing_context_if_enabled(
                "interview_chat_stream",
                tags=["interview-mode", "stream", action],
                metadata={"user_id": user["email"], "role": model_state.get("target_role", "")},
            ):
                task = asyncio.create_task(
                    asyncio.to_thread(
                        lambda: call_interview_chat_compat(
                            get_service(),
                            message,
                            model_history,
                            model_state,
                            candidate_state.get("interview_questions", []),
                            run_id,
                        )
                    )
                )

                emitted_sequences: set[int] = set()
                while not task.done():
                    if await request.is_disconnected():
                        # Network disconnect is not the same as an explicit stop.
                        # Keep the graph running so the client can recover by run_id.
                        # 网络断开不等于用户主动取消。
                        # 这里不 cancel 后端任务，而是让 Agent 继续跑，稍后可按 run_id 恢复。
                        status = "interrupted"
                        break
                    run_snapshot = agent_run_store.get(run_id) or {}
                    for event in run_snapshot.get("events", []):
                        sequence = int(event.get("sequence", 0))
                        if sequence in emitted_sequences:
                            continue
                        emitted_sequences.add(sequence)
                        if event.get("type") == "token":
                            streamed_text += str(event.get("content", ""))
                        # 把 Agent 节点事件原样转成 NDJSON 推给前端。
                        # 这就是前端“Agent 执行过程可视化”的数据来源。
                        yield to_stream_line(event)
                    await asyncio.sleep(0.08)

                if status == "interrupted":
                    candidate_state["interview_history"].append(
                        {"role": "assistant", "content": "这轮回复在生成过程中被中断了。", "status": "interrupted"}
                    )
                    persist_candidate_state(user, candidate_state)
                    return
                result = await task
                # Flush persisted events once more because a short model response
                # may finish between two 80 ms polling intervals.
                # 最后再刷一次事件，避免模型很快结束时漏掉最后几个 token/node 事件。
                final_snapshot = agent_run_store.get(run_id) or {}
                for event in [*final_snapshot.get("events", []), *result.get("events", [])]:
                    sequence = int(event.get("sequence", 0))
                    if sequence not in emitted_sequences:
                        emitted_sequences.add(sequence)
                        if event.get("type") == "token":
                            streamed_text += str(event.get("content", ""))
                        yield to_stream_line(event)

            next_state = result.get("state", model_state)
            reply = str(result.get("reply", "")).strip() or "这轮没有成功生成追问，你可以再补充一下刚才的回答。"
            question_to_record = str(result.get("question_to_record", "")).strip()
            # Rule-based fallback messages do not pass through model.stream(), so
            # only those rare paths use a small compatibility chunker.
            if not streamed_text:
                # 有些兜底回复不是模型流式产生的，而是后端规则直接返回完整文本。
                # 为了前端体验一致，这里把完整文本切成小段模拟 token 事件。
                for chunk in iter_text_chunks(reply):
                    if await request.is_disconnected():
                        status = "interrupted"
                        break
                    streamed_text += chunk
                    yield to_stream_line({"type": "token", "run_id": run_id, "node": "interview_agent", "content": chunk})

            final_text = reply if status == "done" else (streamed_text or "这轮回复在生成过程中被中断了。")
            # 生成完成后，把 Agent 返回的新状态写回 candidate_state。
            # 这里会影响：面试分数、是否结束、已问问题、报告生成依据等。
            candidate_state["interview_state"] = next_state
            evaluation_history = next_state.get("multi_agent", {}).get("evaluations", [])
            record_interview_answer(
                next_state.get("interview_task_id"),
                message,
                evaluation_history[-1] if evaluation_history else {},
            )
            candidate_state["interview_score"] = get_service().calculate_interview_score(
                candidate_state["interview_state"], candidate_state["interview_history"]
            )
            if question_to_record:
                candidate_state["interview_questions"].append(question_to_record)
                record_interview_question(next_state.get("interview_task_id"), question_to_record, result.get("evidence", []))
            candidate_state["interview_history"].append({"role": "assistant", "content": final_text, "status": status})
            if candidate_state.get("interview_state", {}).get("finished") and status == "done":
                candidate_state["interview_finished"] = True
                mark_interview_ended(next_state.get("interview_task_id"), candidate_state["interview_score"])
            persist_candidate_state(user, candidate_state)

            if status == "done":
                candidate_state["pending_run_id"] = ""
                persist_candidate_state(user, candidate_state)
                # done 事件是前端同步最终状态的关键。
                # 前端收到 candidate 后，会用后端状态覆盖本地乐观状态。
                yield to_stream_line(
                    {
                        "type": "done",
                        "candidate": candidate_state,
                        "reply": final_text,
                        "action": str(result.get("action", "")).strip(),
                        "run_id": run_id,
                        "evidence": result.get("evidence", []),
                        "evidence_judgement": result.get("evidence_judgement", {}),
                    }
                )
        except Exception as exc:
            if agent_run_store.is_cancelled(run_id):
                candidate_state["pending_run_id"] = ""
                candidate_state["interview_history"].append(
                    {"role": "assistant", "content": streamed_text or "本轮生成已由用户停止。", "status": "interrupted"}
                )
                persist_candidate_state(user, candidate_state)
                return
            error_text = str(exc) or "面试流式响应失败，请稍后重试。"
            candidate_state["pending_run_id"] = ""
            candidate_state["interview_history"].append({"role": "assistant", "content": error_text, "status": "interrupted"})
            persist_candidate_state(user, candidate_state)
            agent_run_store.append_event(run_id, "run_error", "workflow", detail=error_text)
            yield to_stream_line({"type": "run_error", "run_id": run_id, "node": "workflow", "detail": error_text})

    return StreamingResponse(event_stream(), media_type="application/x-ndjson; charset=utf-8")


@app.post("/api/interview/runs/{run_id}/recover")
def recover_interview_run(request: Request, run_id: str):
    """Persist and return a completed graph result after a client disconnect."""
    user = get_current_user(request)
    profile = ensure_platform_user(user)
    run = agent_run_store.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="运行记录不存在或已过期。")
    if not can_access_agent_run(profile, run):
        raise HTTPException(status_code=403, detail="无权恢复该运行记录。")
    if run.get("status") == "running":
        raise HTTPException(status_code=409, detail="模型仍在生成，请稍后重试恢复。")
    if run.get("status") != "completed":
        raise HTTPException(status_code=409, detail="该运行未成功完成，无法恢复。")

    result = run.get("result") or {}
    reply = str(result.get("reply", "")).strip()
    if not reply:
        raise HTTPException(status_code=409, detail="运行结果中没有可恢复的回复。")

    candidate_state = load_candidate_state_for_user(user)
    history = candidate_state.get("interview_history", [])
    recovered_message = {"role": "assistant", "content": reply, "status": "done"}
    if history and history[-1].get("role") == "assistant" and history[-1].get("status") in {"generating", "interrupted"}:
        history[-1] = recovered_message
    elif not history or history[-1].get("content") != reply:
        history.append(recovered_message)
    candidate_state["interview_history"] = history
    if result.get("state"):
        candidate_state["interview_state"] = result["state"]
        candidate_state["interview_finished"] = bool(result["state"].get("finished"))
    question = str(result.get("question_to_record", "")).strip()
    if question and question not in candidate_state.get("interview_questions", []):
        candidate_state.setdefault("interview_questions", []).append(question)
    evaluation_history = candidate_state.get("interview_state", {}).get("multi_agent", {}).get("evaluations", [])
    record_interview_answer(
        candidate_state.get("interview_state", {}).get("interview_task_id"),
        str((run.get("input") or {}).get("message", "")),
        evaluation_history[-1] if evaluation_history else {},
    )
    record_interview_question(
        candidate_state.get("interview_state", {}).get("interview_task_id"),
        question,
        result.get("evidence", []),
    )
    candidate_state["interview_score"] = get_service().calculate_interview_score(
        candidate_state.get("interview_state", {}), history
    )
    candidate_state["pending_run_id"] = ""
    if candidate_state.get("interview_finished"):
        mark_interview_ended(
            candidate_state.get("interview_state", {}).get("interview_task_id"),
            candidate_state["interview_score"],
        )
    persist_candidate_state(user, candidate_state)
    return {
        "candidate": candidate_state,
        "reply": reply,
        "run_id": run_id,
        "evidence": result.get("evidence", []),
        "recovered": True,
    }


@app.exception_handler(Exception)
async def unhandled_exception_handler(_, exc: Exception):
    # Detailed stack traces stay in server logs; the browser receives a stable,
    # non-sensitive message so API keys, SQL details or local paths are not leaked.
    logger.exception("Unhandled API exception", exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "服务内部异常，请稍后重试。"})
