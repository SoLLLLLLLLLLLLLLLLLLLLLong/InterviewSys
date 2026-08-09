from __future__ import annotations

import os
from collections import Counter
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select

from infrastructure.database import (
    AgentRun,
    AgentRunEvent,
    EvaluationResult,
    KnowledgeDocument,
    InterviewAnswer,
    InterviewQuestion,
    InterviewReport,
    InterviewTask,
    InterviewTemplate,
    QuestionBankItem,
    PromptVersion,
    Organization,
    PlatformUser,
    init_platform_database,
    platform_database_enabled,
    platform_session,
)
from infrastructure.run_store import agent_run_store


ROLES = {"candidate", "interviewer", "admin"}


def _email_set(env_name: str) -> set[str]:
    # 从环境变量中读取管理员/面试官邮箱白名单，例如 ADMIN_EMAILS=admin@qq.com。
    return {item.strip().lower() for item in os.getenv(env_name, "").split(",") if item.strip()}


def fallback_role_for_email(email: str) -> str:
    # 平台数据库未启用或用户第一次登录时，先按邮箱白名单推断默认角色。
    normalized = (email or "").strip().lower()
    if normalized in _email_set("ADMIN_EMAILS"):
        return "admin"
    if normalized in _email_set("INTERVIEWER_EMAILS"):
        return "interviewer"
    return "candidate"


def ensure_platform_user(auth_user: dict[str, Any]) -> dict[str, Any]:
    """Create/read the RBAC profile while preserving the current auth system."""
    # auth_user 是登录系统里的人，PlatformUser 是后台 RBAC 系统里的人。
    # 这里做一层映射：保证每个登录用户都有 role / organization_id，方便权限控制。
    fallback = {
        **auth_user,
        "role": fallback_role_for_email(auth_user.get("email", "")),
        "organization_id": None,
    }
    if not platform_database_enabled():
        # 没开 MySQL 时仍然能跑项目，只是后台管理能力会退化成环境变量角色。
        return fallback

    with platform_session() as session:
        # MySQL 模式下，如果第一次访问后台，就自动创建平台用户档案。
        profile = session.scalar(select(PlatformUser).where(PlatformUser.auth_user_id == int(auth_user["id"])))
        if profile is None:
            profile = PlatformUser(
                auth_user_id=int(auth_user["id"]),
                email=auth_user["email"],
                display_name=auth_user["display_name"],
                role=fallback["role"],
            )
            session.add(profile)
            session.flush()
        else:
            profile.email = auth_user["email"]
            profile.display_name = auth_user["display_name"]
        return {
            **auth_user,
            "platform_user_id": profile.id,
            "role": profile.role,
            "organization_id": profile.organization_id,
        }


def update_user_role(target_user_id: int, role: str, organization_id: int | None = None) -> dict[str, Any]:
    # 管理员在后台修改用户角色时会走这里。
    # 注意：真正的“是否是管理员”校验在 routers/platform.py 的 actor() 里完成。
    if role not in ROLES:
        raise ValueError("不支持的角色。")
    if not platform_database_enabled():
        raise RuntimeError("角色管理需要启用 MySQL 平台数据库。")
    with platform_session() as session:
        profile = session.get(PlatformUser, target_user_id)
        if profile is None:
            raise LookupError("用户不存在。")
        if organization_id is not None and session.get(Organization, organization_id) is None:
            raise ValueError("指定的组织不存在。")
        profile.role = role
        profile.organization_id = organization_id
        session.flush()
        return serialize_user(profile)


def create_organization(name: str) -> dict[str, Any]:
    # 组织可以理解成企业/团队，用于隔离面试官、候选人、文档、任务等数据。
    if not platform_database_enabled():
        raise RuntimeError("组织管理需要启用 MySQL 平台数据库。")
    normalized = name.strip()
    if not normalized:
        raise ValueError("组织名称不能为空。")
    with platform_session() as session:
        if session.scalar(select(Organization).where(Organization.name == normalized)):
            raise ValueError("组织名称已存在。")
        organization = Organization(name=normalized)
        session.add(organization)
        session.flush()
        return {"id": organization.id, "name": organization.name, "created_at": organization.created_at.isoformat()}


def list_users(actor: dict[str, Any], limit: int = 100) -> list[dict[str, Any]]:
    # actor 是当前登录用户的平台身份。
    # admin 可以看全部用户，interviewer 只能看自己组织下的用户。
    if not platform_database_enabled():
        return []
    if actor.get("role") == "interviewer" and actor.get("organization_id") is None:
        return []
    with platform_session() as session:
        statement = select(PlatformUser).order_by(PlatformUser.created_at.desc()).limit(min(limit, 200))
        if actor.get("role") == "interviewer":
            statement = statement.where(PlatformUser.organization_id == actor.get("organization_id"))
        return [serialize_user(item) for item in session.scalars(statement).all()]


def list_organizations(actor: dict[str, Any]) -> list[dict[str, Any]]:
    if not platform_database_enabled():
        return []
    with platform_session() as session:
        statement = select(Organization).order_by(Organization.created_at.desc())
        if actor.get("role") == "interviewer":
            if actor.get("organization_id") is None:
                return []
            statement = statement.where(Organization.id == actor["organization_id"])
        return [
            {"id": item.id, "name": item.name, "created_at": item.created_at.isoformat()}
            for item in session.scalars(statement).all()
        ]


def dashboard_summary(actor: dict[str, Any]) -> dict[str, Any]:
    # 后台首页统计数据。
    # 如果 MySQL 没启用，就从内存 run_store 里给一个轻量 fallback，保证页面不白屏。
    memory_runs = agent_run_store.list_recent(100)
    if actor.get("role") == "interviewer":
        organization_id = actor.get("organization_id")
        memory_runs = [item for item in memory_runs if organization_id is not None and item.get("organization_id") == organization_id]
    fallback = {
        "database_enabled": platform_database_enabled(),
        "users": 0,
        "organizations": 0,
        "documents": 0,
        "agent_runs": len(memory_runs),
        "failed_runs": sum(1 for item in memory_runs if item.get("status") == "failed"),
        "average_latency_ms": 0,
        "evaluation_average": 0.0,
        "runs_by_status": dict(Counter(item.get("status", "unknown") for item in memory_runs)),
    }
    if not platform_database_enabled():
        return fallback

    with platform_session() as session:
        user_filter = []
        document_filter = []
        run_filter = []
        if actor.get("role") == "interviewer":
            if actor.get("organization_id") is None:
                return fallback
            user_filter.append(PlatformUser.organization_id == actor.get("organization_id"))
            document_filter.append(KnowledgeDocument.organization_id == actor.get("organization_id"))
            run_filter.append(AgentRun.organization_id == actor.get("organization_id"))
        fallback["users"] = session.scalar(select(func.count(PlatformUser.id)).where(*user_filter)) or 0
        fallback["organizations"] = 1 if actor.get("role") == "interviewer" else (session.scalar(select(func.count(Organization.id))) or 0)
        fallback["documents"] = session.scalar(select(func.count(KnowledgeDocument.id)).where(*document_filter)) or 0
        fallback["agent_runs"] = session.scalar(select(func.count(AgentRun.id)).where(*run_filter)) or 0
        fallback["failed_runs"] = session.scalar(select(func.count(AgentRun.id)).where(AgentRun.status == "failed", *run_filter)) or 0
        fallback["average_latency_ms"] = int(session.scalar(select(func.avg(AgentRun.latency_ms)).where(*run_filter)) or 0)
        evaluation_statement = select(func.avg(EvaluationResult.score))
        if run_filter:
            evaluation_statement = evaluation_statement.join(AgentRun, EvaluationResult.run_id == AgentRun.id).where(*run_filter)
        fallback["evaluation_average"] = round(float(session.scalar(evaluation_statement) or 0.0), 4)
    return fallback


def list_agent_runs(actor: dict[str, Any], limit: int = 50) -> list[dict[str, Any]]:
    # Agent Run 是一次问答/面试过程中产生的执行记录，
    # 后台用它观察节点耗时、失败原因、工具调用等信息。
    if not platform_database_enabled():
        runs = agent_run_store.list_recent(limit * 3)
        if actor.get("role") == "admin":
            return runs[:limit]
        if actor.get("role") == "interviewer" and actor.get("organization_id") is not None:
            return [item for item in runs if item.get("organization_id") == actor.get("organization_id")][:limit]
        return []
    if actor.get("role") == "interviewer" and actor.get("organization_id") is None:
        return []
    with platform_session() as session:
        statement = select(AgentRun).order_by(AgentRun.created_at.desc()).limit(min(limit, 200))
        if actor.get("role") == "interviewer":
            statement = statement.where(AgentRun.organization_id == actor.get("organization_id"))
        return [serialize_run(item) for item in session.scalars(statement).all()]


def list_evaluation_metrics(actor: dict[str, Any]) -> list[dict[str, Any]]:
    if not platform_database_enabled():
        return []
    with platform_session() as session:
        if actor.get("role") == "interviewer" and actor.get("organization_id") is None:
            return []
        statement = select(EvaluationResult.metric_name, func.avg(EvaluationResult.score), func.count(EvaluationResult.id))
        if actor.get("role") == "interviewer":
            statement = statement.join(AgentRun, EvaluationResult.run_id == AgentRun.id).where(
                AgentRun.organization_id == actor.get("organization_id")
            )
        rows = session.execute(statement.group_by(EvaluationResult.metric_name).order_by(EvaluationResult.metric_name)).all()
        return [{"metric": name, "score": round(float(score), 4), "samples": count} for name, score, count in rows]


def platform_chart_data(actor: dict[str, Any]) -> dict[str, Any]:
    """Return chart-friendly datasets for the platform console."""
    # 这里把后端统计数据整理成前端 ECharts 更容易消费的数组结构。
    # 例如 [{ name: "success", value: 10 }] 可以直接画饼图或柱状图。
    runs = list_agent_runs(actor, limit=200)
    tasks = list_interview_tasks(actor, limit=200)
    reports = list_interview_reports(actor, limit=200)
    configuration = list_business_configuration(actor)

    status_counter = Counter(str(item.get("status") or "unknown") for item in runs)
    role_counter = Counter(str(item.get("role_name") or "未命名岗位") for item in tasks)
    template_counter = Counter(str(item.get("role_name") or "未命名岗位") for item in configuration.get("templates", []))
    question_dimension_counter = Counter(str(item.get("dimension") or "未分类") for item in configuration.get("questions", []))

    score_trend = [
        {
            "label": str(item.get("created_at", ""))[:10] or f"报告{index}",
            "score": int(item.get("score") or 0),
            "candidate": item.get("candidate_name") or "候选人",
            "role_name": item.get("role_name") or "未命名岗位",
        }
        for index, item in enumerate(reversed(reports[-12:]), start=1)
    ]
    latency_trend = [
        {
            "label": str(item.get("created_at", ""))[5:16] or f"Run{index}",
            "latency_ms": int(item.get("latency_ms") or 0),
            "status": item.get("status") or "unknown",
        }
        for index, item in enumerate(reversed(runs[-12:]), start=1)
    ]
    return {
        "run_status": [{"name": key, "value": value} for key, value in status_counter.items()],
        "latency_trend": latency_trend,
        "score_trend": score_trend,
        "role_distribution": [{"name": key, "value": value} for key, value in role_counter.items()],
        "template_roles": [{"name": key, "value": value} for key, value in template_counter.items()],
        "question_dimensions": [{"name": key, "value": value} for key, value in question_dimension_counter.items()],
    }


def list_business_configuration(actor: dict[str, Any]) -> dict[str, Any]:
    if not platform_database_enabled():
        return {"templates": [], "questions": [], "documents": [], "prompts": [], "models": public_model_configuration()}
    organization_id = actor.get("organization_id")
    if actor.get("role") == "interviewer" and organization_id is None:
        return {"templates": [], "questions": [], "documents": [], "prompts": [], "models": public_model_configuration()}
    with platform_session() as session:
        template_statement = select(InterviewTemplate).order_by(InterviewTemplate.created_at.desc())
        question_statement = select(QuestionBankItem).order_by(QuestionBankItem.created_at.desc()).limit(200)
        document_statement = select(KnowledgeDocument).order_by(KnowledgeDocument.created_at.desc()).limit(200)
        if actor.get("role") == "interviewer":
            template_statement = template_statement.where(InterviewTemplate.organization_id == organization_id)
            question_statement = question_statement.where(QuestionBankItem.organization_id == organization_id)
            document_statement = document_statement.where(KnowledgeDocument.organization_id == organization_id)
        templates = session.scalars(template_statement).all()
        questions = session.scalars(question_statement).all()
        documents = session.scalars(document_statement).all()
        prompts = session.scalars(select(PromptVersion).order_by(PromptVersion.created_at.desc()).limit(100)).all() if actor.get("role") == "admin" else []
        return {
            "templates": [{"id": item.id, "name": item.name, "role_name": item.role_name, "difficulty": item.difficulty, "question_count": item.question_count} for item in templates],
            "questions": [{"id": item.id, "role_name": item.role_name, "dimension": item.dimension, "difficulty": item.difficulty, "question_text": item.question_text} for item in questions],
            "documents": [{"id": item.id, "filename": item.filename, "status": item.status, "chunk_count": item.chunk_count, "organization_id": item.organization_id} for item in documents],
            "prompts": [{"id": item.id, "prompt_key": item.prompt_key, "version": item.version, "is_active": item.is_active} for item in prompts],
            "models": public_model_configuration(),
        }


def list_configured_role_names(actor: dict[str, Any]) -> list[str]:
    """Return role names created in the interviewer/admin configuration panel."""
    if not platform_database_enabled():
        return []
    organization_id = actor.get("organization_id")
    if actor.get("role") == "interviewer" and organization_id is None:
        return []
    with platform_session() as session:
        statement = select(InterviewTemplate.role_name).where(InterviewTemplate.role_name != "").distinct()
        if actor.get("role") == "interviewer":
            statement = statement.where(InterviewTemplate.organization_id == organization_id)
        rows = session.scalars(statement.order_by(InterviewTemplate.role_name)).all()
        return [str(item).strip() for item in rows if str(item).strip()]


def get_interview_template_profile(actor: dict[str, Any], role_name: str) -> dict[str, Any]:
    """Return the newest template profile for a role, used by the frontend and runtime planner."""
    if not platform_database_enabled():
        return {}
    normalized = str(role_name or "").strip()
    if not normalized:
        return {}
    organization_id = actor.get("organization_id")
    with platform_session() as session:
        statement = (
            select(InterviewTemplate)
            .where(InterviewTemplate.role_name == normalized)
            .order_by(InterviewTemplate.created_at.desc())
            .limit(1)
        )
        if actor.get("role") == "interviewer":
            if organization_id is None:
                return {}
            statement = statement.where(InterviewTemplate.organization_id == organization_id)
        template = session.scalar(statement)
        if template is None:
            return {}
        question_statement = (
            select(QuestionBankItem)
            .where(QuestionBankItem.role_name == normalized)
            .order_by(QuestionBankItem.created_at.desc())
            .limit(30)
        )
        if actor.get("role") == "interviewer":
            question_statement = question_statement.where(QuestionBankItem.organization_id == organization_id)
        question_bank = [
            {
                "id": item.id,
                "dimension": item.dimension,
                "difficulty": item.difficulty,
                "question_text": item.question_text,
                "reference_answer": item.reference_answer,
            }
            for item in session.scalars(question_statement).all()
        ]
        dimensions = template.dimensions_json or []
        return {
            "id": template.id,
            "name": template.name,
            "role_name": template.role_name,
            "difficulty": template.difficulty,
            "question_count": template.question_count,
            "dimensions": dimensions,
            "question_bank": question_bank,
            "rubric": template.rubric_json or {},
        }


def public_model_configuration() -> list[dict[str, str]]:
    """Expose model metadata but never return secret API keys to the browser."""
    return [
        {
            "purpose": "chat",
            "model": os.getenv("DEEPSEEK_MODEL", "deepseek-ai/DeepSeek-V4-Flash"),
            "base_url": os.getenv("DEEPSEEK_BASE_URL", "https://api.siliconflow.cn/v1"),
        },
        {
            "purpose": "embedding",
            "model": os.getenv("EMBEDDING_MODEL", "Qwen/Qwen3-Embedding-0.6B"),
            "base_url": os.getenv("EMBEDDING_BASE_URL", "https://api.siliconflow.cn/v1"),
        },
    ]


def create_prompt_version(actor: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    if actor.get("role") != "admin":
        raise RuntimeError("只有平台管理员可以管理 Prompt 版本。")
    if not platform_database_enabled():
        raise RuntimeError("Prompt 版本管理需要启用 MySQL 平台数据库。")
    prompt_key = str(payload.get("prompt_key", "")).strip()
    version = str(payload.get("version", "")).strip()
    content = str(payload.get("content", "")).strip()
    if not prompt_key or not version or not content:
        raise ValueError("Prompt 标识、版本和内容不能为空。")
    active = bool(payload.get("is_active", False))
    with platform_session() as session:
        if active:
            for item in session.scalars(select(PromptVersion).where(PromptVersion.prompt_key == prompt_key)).all():
                item.is_active = False
        item = PromptVersion(
            prompt_key=prompt_key,
            version=version,
            content=content,
            is_active=active,
            created_by=actor.get("platform_user_id"),
        )
        session.add(item)
        session.flush()
        return {"id": item.id, "prompt_key": item.prompt_key, "version": item.version, "is_active": item.is_active}


def create_interview_template(actor: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    if not platform_database_enabled():
        raise RuntimeError("面试模板需要启用 MySQL 平台数据库。")
    if actor.get("role") == "interviewer" and actor.get("organization_id") is None:
        raise RuntimeError("请先将面试官绑定到一个组织。")
    with platform_session() as session:
        item = InterviewTemplate(
            organization_id=actor.get("organization_id"), created_by=actor["platform_user_id"],
            name=str(payload.get("name", "")).strip(), role_name=str(payload.get("role_name", "")).strip(),
            difficulty=str(payload.get("difficulty", "medium")), question_count=max(1, min(20, int(payload.get("question_count", 8)))),
            dimensions_json=payload.get("dimensions", []), rubric_json=payload.get("rubric", {}),
        )
        session.add(item)
        session.flush()
        return {"id": item.id, "name": item.name, "role_name": item.role_name}


def create_question_bank_item(actor: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    if not platform_database_enabled():
        raise RuntimeError("题库管理需要启用 MySQL 平台数据库。")
    if actor.get("role") == "interviewer" and actor.get("organization_id") is None:
        raise RuntimeError("请先将面试官绑定到一个组织。")
    with platform_session() as session:
        item = QuestionBankItem(
            organization_id=actor.get("organization_id"), role_name=str(payload.get("role_name", "")).strip(),
            dimension=str(payload.get("dimension", "")).strip(), difficulty=str(payload.get("difficulty", "medium")),
            question_text=str(payload.get("question_text", "")).strip(), reference_answer=str(payload.get("reference_answer", "")).strip(),
        )
        session.add(item)
        session.flush()
        return {"id": item.id, "question_text": item.question_text}


def register_knowledge_documents(actor: dict[str, Any], documents: list[dict[str, Any]]) -> None:
    if not platform_database_enabled():
        return
    with platform_session() as session:
        for payload in documents:
            checksum = str(payload.get("checksum", ""))
            existing = session.scalar(
                select(KnowledgeDocument).where(
                    KnowledgeDocument.checksum == checksum,
                    KnowledgeDocument.owner_user_id == actor.get("platform_user_id"),
                )
            )
            if existing:
                existing.status = "ready"
                chunk_count = int(payload.get("chunk_count", 0) or 0)
                if chunk_count > 0:
                    existing.chunk_count = chunk_count
                continue
            session.add(
                KnowledgeDocument(
                    owner_user_id=actor.get("platform_user_id"),
                    organization_id=actor.get("organization_id"),
                    filename=str(payload.get("filename", "knowledge")),
                    checksum=checksum,
                    status="ready",
                    chunk_count=int(payload.get("chunk_count", 0)),
                    metadata_json=payload.get("metadata", {}),
                )
            )


def create_interview_task(actor: dict[str, Any], role_name: str, conversation_id: str | None = None) -> int | None:
    """Create the normalized interview record used by the enterprise dashboard."""
    if not platform_database_enabled():
        return None
    with platform_session() as session:
        task = InterviewTask(
            candidate_user_id=int(actor["platform_user_id"]),
            organization_id=actor.get("organization_id"),
            conversation_id=conversation_id,
            role_name=role_name,
            status="running",
        )
        session.add(task)
        session.flush()
        return int(task.id)


def record_interview_question(task_id: int | None, question: str, evidence: list[dict[str, Any]] | None = None) -> None:
    if not platform_database_enabled() or not task_id or not question.strip():
        return
    with platform_session() as session:
        latest = session.scalar(
            select(InterviewQuestion)
            .where(InterviewQuestion.task_id == task_id)
            .order_by(InterviewQuestion.sequence.desc())
            .limit(1)
        )
        if latest and latest.question_text.strip() == question.strip():
            if evidence:
                latest.evidence_json = evidence
            return
        count = session.scalar(select(func.count(InterviewQuestion.id)).where(InterviewQuestion.task_id == task_id)) or 0
        session.add(
            InterviewQuestion(
                task_id=task_id,
                sequence=int(count) + 1,
                question_text=question.strip(),
                evidence_json=evidence or [],
            )
        )


def record_interview_answer(task_id: int | None, answer: str, evaluation: dict[str, Any] | None = None) -> None:
    if not platform_database_enabled() or not task_id or not answer.strip():
        return
    with platform_session() as session:
        question = session.scalar(
            select(InterviewQuestion)
            .where(InterviewQuestion.task_id == task_id)
            .order_by(InterviewQuestion.sequence.desc())
            .limit(1)
        )
        if question is None:
            return
        existing = session.scalar(select(InterviewAnswer).where(InterviewAnswer.question_id == question.id))
        score = float((evaluation or {}).get("score", 0.0) or 0.0)
        if existing:
            existing.answer_text = answer.strip()
            existing.score = score
            existing.evaluation_json = evaluation or {}
        else:
            session.add(
                InterviewAnswer(
                    question_id=question.id,
                    answer_text=answer.strip(),
                    score=score,
                    evaluation_json=evaluation or {},
                )
            )


def mark_interview_ended(task_id: int | None, score: int = 0) -> None:
    if not platform_database_enabled() or not task_id:
        return
    with platform_session() as session:
        task = session.get(InterviewTask, task_id)
        if task:
            task.status = "awaiting_report"
            task.score = score
            task.finished_at = datetime.utcnow()


def finalize_interview_task(
    task_id: int | None,
    score: int,
    report_text: str,
    report_file: str,
    citations: list[dict[str, Any]] | None = None,
) -> None:
    if not platform_database_enabled() or not task_id:
        return
    with platform_session() as session:
        task = session.get(InterviewTask, task_id)
        if task is None:
            return
        task.status = "completed"
        task.score = score
        task.finished_at = datetime.utcnow()
        report = session.scalar(select(InterviewReport).where(InterviewReport.task_id == task_id))
        if report is None:
            session.add(
                InterviewReport(
                    task_id=task_id,
                    report_text=report_text,
                    report_file=report_file,
                    citations_json=citations or [],
                )
            )
        else:
            report.report_text = report_text
            report.report_file = report_file
            report.citations_json = citations or []


def list_interview_tasks(actor: dict[str, Any], limit: int = 100) -> list[dict[str, Any]]:
    if not platform_database_enabled():
        return []
    if actor.get("role") == "interviewer" and actor.get("organization_id") is None:
        return []
    with platform_session() as session:
        statement = (
            select(InterviewTask, PlatformUser)
            .join(PlatformUser, InterviewTask.candidate_user_id == PlatformUser.id)
            .order_by(InterviewTask.created_at.desc())
            .limit(min(limit, 200))
        )
        if actor.get("role") == "interviewer":
            statement = statement.where(InterviewTask.organization_id == actor.get("organization_id"))
        rows = session.execute(statement).all()
        return [
            {
                "id": task.id,
                "candidate_name": candidate.display_name,
                "candidate_email": candidate.email,
                "role_name": task.role_name,
                "status": task.status,
                "score": task.score,
                "created_at": task.created_at.isoformat(),
                "finished_at": task.finished_at.isoformat() if task.finished_at else None,
            }
            for task, candidate in rows
        ]


def list_interview_reports(actor: dict[str, Any], limit: int = 100) -> list[dict[str, Any]]:
    if not platform_database_enabled():
        return []
    if actor.get("role") == "interviewer" and actor.get("organization_id") is None:
        return []
    with platform_session() as session:
        statement = (
            select(InterviewReport, InterviewTask, PlatformUser)
            .join(InterviewTask, InterviewReport.task_id == InterviewTask.id)
            .join(PlatformUser, InterviewTask.candidate_user_id == PlatformUser.id)
            .order_by(InterviewReport.created_at.desc())
            .limit(min(limit, 200))
        )
        if actor.get("role") == "interviewer":
            statement = statement.where(InterviewTask.organization_id == actor.get("organization_id"))
        rows = session.execute(statement).all()
        return [
            {
                "id": report.id,
                "task_id": task.id,
                "candidate_name": candidate.display_name,
                "role_name": task.role_name,
                "score": task.score,
                "report_file": report.report_file,
                "citation_count": len(report.citations_json or []),
                "created_at": report.created_at.isoformat(),
            }
            for report, task, candidate in rows
        ]
def serialize_user(item: PlatformUser) -> dict[str, Any]:
    return {
        "id": item.id,
        "auth_user_id": item.auth_user_id,
        "email": item.email,
        "display_name": item.display_name,
        "role": item.role,
        "organization_id": item.organization_id,
        "is_active": item.is_active,
        "created_at": item.created_at.isoformat(),
    }


def serialize_run(item: AgentRun) -> dict[str, Any]:
    return {
        "run_id": item.id,
        "workflow": item.workflow,
        "status": item.status,
        "current_node": item.current_node,
        "latency_ms": item.latency_ms,
        "token_count": item.token_count,
        "error": item.error_text,
        "created_at": item.created_at.isoformat(),
        "finished_at": item.finished_at.isoformat() if item.finished_at else None,
    }


def can_access_agent_run(actor: dict[str, Any], run: dict[str, Any]) -> bool:
    """Check ownership/organization boundaries before exposing a run payload."""
    if actor.get("role") == "admin":
        return True

    actor_user_id = actor.get("platform_user_id", actor.get("id"))
    if actor.get("role") == "interviewer":
        organization_id = actor.get("organization_id")
        return organization_id is not None and run.get("organization_id") == organization_id
    return run.get("user_id") == actor_user_id
