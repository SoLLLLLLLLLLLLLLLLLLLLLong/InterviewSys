from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Iterator

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from infrastructure.settings import platform_settings


class Base(DeclarativeBase):
    # SQLAlchemy 2 的声明式基类。
    # 后面每个继承 Base 的类，都会映射成一张数据库表。
    pass


class Organization(Base):
    # 企业/组织表。
    # 面试官通常归属于某个组织，后续做数据隔离时会用 organization_id。
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PlatformUser(Base):
    """平台用户表：保存登录用户在平台里的角色和组织信息。

    面试要点：
    - auth_user_id：兼容旧用户体系的用户 id。
    - role：candidate / interviewer / admin。
    - organization_id：企业面试官所属组织，用于数据隔离。
    """

    __tablename__ = "platform_users"

    id: Mapped[int] = mapped_column(primary_key=True)
    auth_user_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(80))
    password_hash: Mapped[str] = mapped_column(String(128), default="")
    password_salt: Mapped[str] = mapped_column(String(64), default="")
    role: Mapped[str] = mapped_column(String(30), default="candidate", index=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"), nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    organization: Mapped[Organization | None] = relationship()


class UserSession(Base):
    # Cookie Session 表。
    # 浏览器 Cookie 里只保存 session_token，后端再用 token 查这张表确认登录用户。
    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("platform_users.id"), index=True)
    session_token: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class LegacyInterviewRecord(Base):
    """Compatibility table used by the existing history/report API."""

    __tablename__ = "legacy_interview_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("platform_users.id"), index=True)
    role_name: Mapped[str] = mapped_column(String(120))
    resume_filename: Mapped[str] = mapped_column(String(255), default="")
    score: Mapped[int] = mapped_column(Integer, default=0)
    report_text: Mapped[str] = mapped_column(Text)
    report_file: Mapped[str] = mapped_column(String(500), default="")
    history_json: Mapped[str] = mapped_column(Text, default="[]")
    interview_state_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class WorkspaceSnapshot(Base):
    # 工作区快照表。
    # 用 JSON 保存当前用户的项目空间、激活项目、激活会话等整体快照，
    # 便于兼容早期 JSON 工作区结构。
    __tablename__ = "workspace_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("platform_users.id"), unique=True, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class WorkspaceProject(Base):
    # 项目空间表。
    # 一个用户可以有多个项目，每个项目下可以再创建多个会话。
    __tablename__ = "workspace_projects"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("platform_users.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Conversation(Base):
    # 会话表。
    # preferred_mode 表示这个会话默认打开问答、面试还是历史模式。
    # state_json 保存该会话当前候选人状态快照。
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("workspace_projects.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("platform_users.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    preferred_mode: Mapped[str] = mapped_column(String(30), default="qa")
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    state_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Message(Base):
    # 消息表。
    # mode 区分 qa/interview，role 区分 user/assistant，status 区分 done/generating/interrupted。
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("platform_users.id"), index=True)
    mode: Mapped[str] = mapped_column(String(30), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    role: Mapped[str] = mapped_column(String(30))
    content: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="done")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ResumeRecord(Base):
    # 简历记录表。
    # content_text 是解析出来的简历纯文本，analysis_json 可保存 Resume Analyst 的分析结果。
    __tablename__ = "resumes"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("platform_users.id"), index=True)
    conversation_id: Mapped[str | None] = mapped_column(ForeignKey("conversations.id"), nullable=True, index=True)
    filename: Mapped[str] = mapped_column(String(255))
    content_text: Mapped[str] = mapped_column(Text)
    analysis_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class InterviewTask(Base):
    # 一次完整模拟面试任务。
    # 它把候选人、岗位、组织、会话、分数和状态关联起来。
    __tablename__ = "interview_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_user_id: Mapped[int] = mapped_column(ForeignKey("platform_users.id"), index=True)
    interviewer_user_id: Mapped[int | None] = mapped_column(ForeignKey("platform_users.id"), nullable=True, index=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"), nullable=True, index=True)
    conversation_id: Mapped[str | None] = mapped_column(ForeignKey("conversations.id"), nullable=True, index=True)
    role_name: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    score: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class InterviewQuestion(Base):
    # 面试题记录表。
    # evidence_json 用于保存 RAG 检索到的引用证据，方便报告溯源。
    __tablename__ = "interview_questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("interview_tasks.id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    dimension: Mapped[str] = mapped_column(String(120), default="")
    question_text: Mapped[str] = mapped_column(Text)
    evidence_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)


class InterviewAnswer(Base):
    # 候选人回答记录表。
    # evaluation_json 保存 Evaluation Agent 对回答质量的结构化评分和理由。
    __tablename__ = "interview_answers"

    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("interview_questions.id"), index=True)
    answer_text: Mapped[str] = mapped_column(Text)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    evaluation_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class InterviewReport(Base):
    # 面试报告表。
    # 报告文本和下载文件路径都保存在这里，前台历史记录页会读取它。
    __tablename__ = "interview_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("interview_tasks.id"), unique=True, index=True)
    report_text: Mapped[str] = mapped_column(Text)
    report_file: Mapped[str] = mapped_column(String(500), default="")
    citations_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class KnowledgeDocument(Base):
    # 知识库文档元数据表。
    # 真正的向量存在 Chroma，这里存文件名、checksum、切片数量和权限归属。
    __tablename__ = "knowledge_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_user_id: Mapped[int | None] = mapped_column(ForeignKey("platform_users.id"), nullable=True, index=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"), nullable=True, index=True)
    filename: Mapped[str] = mapped_column(String(255))
    checksum: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(30), default="ready", index=True)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class InterviewTemplate(Base):
    # 岗位面试模板。
    # 面试官后台新增岗位后，前台目标岗位列表和面试计划会读取这里的数据。
    __tablename__ = "interview_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"), nullable=True, index=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("platform_users.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    role_name: Mapped[str] = mapped_column(String(120), index=True)
    difficulty: Mapped[str] = mapped_column(String(30), default="medium")
    question_count: Mapped[int] = mapped_column(Integer, default=8)
    dimensions_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    rubric_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class QuestionBankItem(Base):
    # 题库表。
    # 按岗位、能力维度、难度组织问题，供 Interview Planner/Interview Agent 使用。
    __tablename__ = "question_bank_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"), nullable=True, index=True)
    role_name: Mapped[str] = mapped_column(String(120), index=True)
    dimension: Mapped[str] = mapped_column(String(120), index=True)
    difficulty: Mapped[str] = mapped_column(String(30), default="medium")
    question_text: Mapped[str] = mapped_column(Text)
    reference_answer: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PromptVersion(Base):
    # Prompt 版本表。
    # 管理员后台可以维护不同 prompt_key 的提示词版本，便于调试和回滚。
    __tablename__ = "prompt_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    prompt_key: Mapped[str] = mapped_column(String(100), index=True)
    version: Mapped[str] = mapped_column(String(40))
    content: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("platform_users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AgentRun(Base):
    # Agent Run 主表。
    # 一次问答/面试工作流对应一个 run_id，用于观测耗时、状态、错误和输出。
    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("platform_users.id"), nullable=True, index=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"), nullable=True, index=True)
    workflow: Mapped[str] = mapped_column(String(80), index=True)
    status: Mapped[str] = mapped_column(String(30), index=True)
    current_node: Mapped[str] = mapped_column(String(80), default="")
    input_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    output_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    error_text: Mapped[str] = mapped_column(Text, default="")
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class AgentRunEvent(Base):
    # Agent Run 事件表。
    # 保存 node_started、tool_called、token、run_error 等过程事件。
    __tablename__ = "agent_run_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("agent_runs.id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(String(40), index=True)
    node: Mapped[str] = mapped_column(String(80), default="")
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class EvaluationResult(Base):
    # 评测结果表。
    # 后续可以接 LangSmith Dataset 或自定义评测脚本，把 Router/RAG/评分一致性指标写入这里。
    __tablename__ = "evaluation_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[str | None] = mapped_column(ForeignKey("agent_runs.id"), nullable=True, index=True)
    dataset_name: Mapped[str] = mapped_column(String(120), index=True)
    metric_name: Mapped[str] = mapped_column(String(80), index=True)
    score: Mapped[float] = mapped_column(Float)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


_engine = None
_session_factory = None


def platform_database_enabled() -> bool:
    # 是否启用正式平台数据库由环境变量控制：
    # ENABLE_PLATFORM_DB=true 且 DATABASE_URL 不为空时，才走 MySQL。
    return bool(platform_settings.enable_platform_db and platform_settings.database_url)


def get_engine():
    # SQLAlchemy Engine 可以理解成“数据库连接工厂”。
    # pool_pre_ping=True 会在连接复用前先探活，减少 MySQL 空闲连接断开导致的报错。
    global _engine, _session_factory
    if not platform_database_enabled():
        return None
    if _engine is None:
        _engine = create_engine(platform_settings.database_url, pool_pre_ping=True, future=True)
        _session_factory = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


def init_platform_database() -> bool:
    # create_all 会根据上面的 ORM 模型创建缺失的数据表。
    # 真实生产项目更推荐 Alembic 迁移；这里保留 create_all 方便开发环境快速启动。
    engine = get_engine()
    if engine is None:
        return False
    Base.metadata.create_all(engine)
    return True


@contextmanager
def platform_session() -> Iterator[Any]:
    # 数据库会话上下文：
    # - 正常执行：commit 提交事务。
    # - 出现异常：rollback 回滚，避免写入半截数据。
    # - 最后一定 close，释放连接。
    if get_engine() is None or _session_factory is None:
        raise RuntimeError("Platform database is disabled. Configure DATABASE_URL and ENABLE_PLATFORM_DB=true.")
    session = _session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def json_safe(value: Any) -> Any:
    """Normalize Pydantic/SQLAlchemy payloads before storing in JSON columns."""
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))
