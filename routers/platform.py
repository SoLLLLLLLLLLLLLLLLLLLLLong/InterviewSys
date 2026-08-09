"""RBAC-protected interviewer and administrator APIs."""
from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from infrastructure.run_store import agent_run_store
from services.platform_service import (
    can_access_agent_run,
    create_interview_template,
    create_organization,
    create_question_bank_item,
    create_prompt_version,
    dashboard_summary,
    get_interview_template_profile,
    ensure_platform_user,
    list_agent_runs,
    list_business_configuration,
    list_evaluation_metrics,
    list_interview_reports,
    list_interview_tasks,
    list_organizations,
    list_users,
    platform_chart_data,
    update_user_role,
)


class OrganizationPayload(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class RolePayload(BaseModel):
    role: str
    organization_id: int | None = None


class InterviewTemplatePayload(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    role_name: str = Field(min_length=1, max_length=120)
    difficulty: str = "medium"
    question_count: int = Field(default=8, ge=1, le=20)
    dimensions: list[dict[str, Any]] = Field(default_factory=list)
    rubric: dict[str, Any] = Field(default_factory=dict)


class QuestionBankPayload(BaseModel):
    role_name: str = Field(min_length=1, max_length=120)
    dimension: str = Field(min_length=1, max_length=120)
    difficulty: str = "medium"
    question_text: str = Field(min_length=1)
    reference_answer: str = ""


class PromptVersionPayload(BaseModel):
    prompt_key: str = Field(min_length=1, max_length=100)
    version: str = Field(min_length=1, max_length=40)
    content: str = Field(min_length=1)
    is_active: bool = False


def build_platform_router(get_current_user: Callable[..., dict[str, Any]]) -> APIRouter:
    # APIRouter 用于把后台相关接口单独组织起来。
    # main.py 里 app.include_router(...) 后，这些接口都会带上 /api/platform 前缀。
    router = APIRouter(prefix="/api/platform", tags=["platform"])

    def actor(request: Request, allowed: set[str] | None = None) -> dict[str, Any]:
        """
        后台接口统一鉴权入口。

        学习重点：
        - get_current_user：先根据 Cookie Session 找到登录用户。
        - ensure_platform_user：把登录用户转换成平台用户资料，里面包含 role/organization_id。
        - allowed：当前接口允许哪些角色访问。

        前端可以隐藏按钮，但安全边界一定在后端。
        """
        profile = ensure_platform_user(get_current_user(request))
        if allowed and profile.get("role") not in allowed:
            raise HTTPException(status_code=403, detail="当前账号没有访问该功能的权限。")
        return profile

    @router.get("/me")
    def platform_me(request: Request):
        return {"user": actor(request)}

    @router.get("/dashboard")
    def platform_dashboard(request: Request):
        # 管理员/面试官都可以看 dashboard，但 dashboard_summary 会根据角色过滤数据范围。
        current = actor(request, {"interviewer", "admin"})
        return {"summary": dashboard_summary(current)}

    @router.get("/charts")
    def platform_charts(request: Request):
        current = actor(request, {"interviewer", "admin"})
        return {"charts": platform_chart_data(current)}

    @router.get("/users")
    def platform_users(request: Request):
        current = actor(request, {"interviewer", "admin"})
        return {"users": list_users(current)}

    @router.patch("/users/{user_id}/role")
    def platform_update_role(request: Request, user_id: int, payload: RolePayload):
        # 修改用户角色是高权限操作，只允许 admin。
        actor(request, {"admin"})
        try:
            return {"user": update_user_role(user_id, payload.role, payload.organization_id)}
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.get("/organizations")
    def platform_organizations(request: Request):
        current = actor(request, {"interviewer", "admin"})
        return {"organizations": list_organizations(current)}

    @router.post("/organizations")
    def platform_create_organization(request: Request, payload: OrganizationPayload):
        actor(request, {"admin"})
        try:
            return {"organization": create_organization(payload.name)}
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/agent-runs")
    def platform_agent_runs(request: Request):
        current = actor(request, {"interviewer", "admin"})
        return {"runs": list_agent_runs(current)}

    @router.get("/agent-runs/{run_id}")
    def agent_run_detail(request: Request, run_id: str):
        # 不能只检查“是否登录”，还要检查当前用户是否有权访问这个 run_id。
        # 例如面试官只能看自己组织内的数据，候选人不能看别人的运行记录。
        current = actor(request)
        run = agent_run_store.get(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="运行记录不存在或已过期。")
        if not can_access_agent_run(current, run):
            raise HTTPException(status_code=403, detail="无权访问该运行记录。")
        return {"run": run}

    @router.post("/agent-runs/{run_id}/cancel")
    def cancel_agent_run(request: Request, run_id: str):
        # 取消运行：前端点击“停止”时会调用这里，后端写入 cancelled 标记。
        # Agent 执行过程中会读取这个标记，决定是否停止继续生成。
        current = actor(request)
        run = agent_run_store.get(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="运行记录不存在或已过期。")
        if not can_access_agent_run(current, run):
            raise HTTPException(status_code=403, detail="无权操作该运行记录。")
        if not agent_run_store.cancel(run_id):
            raise HTTPException(status_code=404, detail="运行记录不存在或已过期。")
        return {"success": True, "run_id": run_id}

    @router.get("/evaluations")
    def platform_evaluations(request: Request):
        current = actor(request, {"interviewer", "admin"})
        return {"metrics": list_evaluation_metrics(current)}

    @router.get("/interview-tasks")
    def platform_interview_tasks(request: Request):
        current = actor(request, {"interviewer", "admin"})
        return {"tasks": list_interview_tasks(current)}

    @router.get("/reports")
    def platform_reports(request: Request):
        current = actor(request, {"interviewer", "admin"})
        return {"reports": list_interview_reports(current)}

    @router.get("/configuration")
    def platform_configuration(request: Request):
        current = actor(request, {"interviewer", "admin"})
        return list_business_configuration(current)

    @router.get("/templates/profile/{role_name}")
    def platform_template_profile(request: Request, role_name: str):
        current = actor(request, {"interviewer", "admin", "candidate"})
        return {"profile": get_interview_template_profile(current, role_name)}

    @router.post("/templates")
    def platform_create_template(request: Request, payload: InterviewTemplatePayload):
        # 面试官后台新增岗位模板。
        # 这些配置会影响前台模拟面试的岗位选项、题量和能力维度。
        current = actor(request, {"interviewer", "admin"})
        try:
            return {"template": create_interview_template(current, payload.model_dump())}
        except RuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/questions")
    def platform_create_question(request: Request, payload: QuestionBankPayload):
        # 题库问题用于驱动模拟面试，不再让前台岗位题目完全写死。
        current = actor(request, {"interviewer", "admin"})
        try:
            return {"question": create_question_bank_item(current, payload.model_dump())}
        except RuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/prompts")
    def platform_create_prompt(request: Request, payload: PromptVersionPayload):
        # Prompt 配置属于平台级能力，只允许管理员维护。
        current = actor(request, {"admin"})
        try:
            return {"prompt": create_prompt_version(current, payload.model_dump())}
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return router
