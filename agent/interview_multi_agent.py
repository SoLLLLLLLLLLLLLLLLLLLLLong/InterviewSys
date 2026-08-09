from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Callable, Sequence

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

from agent.interview_policy import InterviewDecision, InterviewPolicy
from agent.interview_role_manager import InterviewRoleManager
from agent.interview_state_machine import InterviewStateMachine
from model.factory import chat_model
from utils.logger_handler import logger
from utils.prompt_loader import load_report_prompts


def _trim_text(text: str, limit: int = 1800) -> str:
    # 给模型喂内容时做长度保护，避免 prompt 无限膨胀。
    content = str(text or "").strip()
    if len(content) <= limit:
        return content
    return content[:limit] + "\n...(内容过长，已截断)"


def _history_to_text(history: Sequence[dict], max_turns: int = 8) -> str:
    # 把内部消息数组转换成更适合 prompt 的纯文本格式。
    if not history:
        return "无历史对话"

    lines: list[str] = []
    for item in list(history)[-max_turns:]:
        role = item.get("role", "")
        content = str(item.get("content", "")).strip()
        if not content:
            continue
        prefix = "候选人" if role == "user" else "面试官"
        lines.append(f"{prefix}：{content}")
    return "\n".join(lines) if lines else "无历史对话"


def _safe_json_loads(raw: str) -> dict[str, Any]:
    text = str(raw or "").strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except Exception:
        return {}


def _resume_hash(resume_text: str) -> str:
    return hashlib.md5(str(resume_text or "").strip().encode("utf-8")).hexdigest()


def _build_multi_agent_state(state: dict[str, Any] | None = None) -> dict[str, Any]:
    # multi_agent 字段里保存的是多个子 Agent 共用的中间状态。
    # 比如：简历分析结果、最近一次路由决策、最近一次评估结果。
    data = dict(state or {})
    data.setdefault("workflow_version", "multi_agent_v1")
    data.setdefault("resume_analysis", {})
    data.setdefault("route_history", [])
    data.setdefault("evaluations", [])
    data.setdefault("last_route", {})
    data.setdefault("last_evaluation", {})
    data.setdefault("last_report_meta", {})
    return data


def _append_bounded_list(target: list[Any], item: Any, limit: int = 30) -> list[Any]:
    target.append(item)
    if len(target) > limit:
        return target[-limit:]
    return target


@dataclass
class RouterDecisionPlan:
    route: str
    reason: str
    should_analyze_resume: bool = False


class RouterAgent:
    """负责把当前回合分发给后续子 Agent。"""

    def __init__(self, policy: InterviewPolicy):
        # RouterAgent 的职责不是提问，而是“决定下一步谁来干活”。
        self.policy = policy
        self.route_chain = self._build_route_chain()

    @staticmethod
    def _build_route_chain():
        prompt = PromptTemplate.from_template(
            """你是一个模拟面试系统里的 Router Agent，负责决定当前回合应该交给哪个下游 Agent。

可选 route 只有三种：
- evaluate_answer：用户正在认真回答，需要进入回答评估 -> 提问生成流程
- give_hint：用户在求提示、跑题、打断，或者明显没有回答到点上，需要先给提示
- finish_interview：用户明确想结束当前面试

请只输出 JSON，字段固定为：
{{
  "route": "evaluate_answer | give_hint | finish_interview",
  "reason": "简短中文原因"
}}

当前问题：
{current_question}

最近对话：
{history}

用户输入：
{user_input}
"""
        )
        return prompt | chat_model | StrOutputParser()

    def route_start(self, role: str, resume_text: str, interview_state: dict[str, Any] | None = None) -> RouterDecisionPlan:
        # 面试刚开始时，Router 主要决定“是否需要先做简历分析”。
        analysis = ((interview_state or {}).get("multi_agent") or {}).get("resume_analysis") or {}
        cached_hash = str(analysis.get("resume_hash", "")).strip()
        current_hash = _resume_hash(resume_text) if resume_text else ""
        should_analyze = bool(resume_text and current_hash and current_hash != cached_hash)
        return RouterDecisionPlan(
            route="start_interview",
            reason="初始化面试流程，准备首轮提问",
            should_analyze_resume=should_analyze,
        )

    def route_turn(self, user_input: str, current_question: str, history: Sequence[dict]) -> RouterDecisionPlan:
        # 正常一轮面试中，Router 决定当前输入要走哪条分支：
        # evaluate_answer / give_hint / finish_interview
        history_text = _history_to_text(history, max_turns=6)
        try:
            raw = self.route_chain.invoke(
                {
                    "user_input": user_input,
                    "current_question": current_question or "暂无当前问题",
                    "history": history_text,
                }
            )
            data = _safe_json_loads(raw)
            route = str(data.get("route", "")).strip()
            reason = str(data.get("reason", "")).strip()
            if route in {"evaluate_answer", "give_hint", "finish_interview"}:
                return RouterDecisionPlan(route=route, reason=reason or "Router Agent 路由成功")
        except Exception as exc:
            logger.warning(f"[RouterAgent] 路由失败，回退到规则策略：{exc}")

        decision = self.policy.classify_intent(user_input, current_question, history)
        if decision.intent == "finish_interview":
            return RouterDecisionPlan(route="finish_interview", reason=decision.reason or "用户主动结束面试")
        if decision.intent in {"ask_hint", "chat_interrupt", "out_of_scope"} or decision.should_give_hint:
            return RouterDecisionPlan(route="give_hint", reason=decision.reason or "用户需要提示或当前输入不适合直接评估")
        return RouterDecisionPlan(route="evaluate_answer", reason=decision.reason or "进入回答评估流程")


class ResumeAnalystAgent:
    """负责把简历内容结构化成后续提问可复用的分析结果。"""

    def __init__(self):
        self.analysis_chain = self._build_analysis_chain()

    @staticmethod
    def _build_analysis_chain():
        prompt = PromptTemplate.from_template(
            """你是一个 Resume Analyst Agent，负责把候选人简历整理成后续技术面试可复用的信息。

请严格输出 JSON，字段固定为：
{{
  "summary": "2-4 句中文总结",
  "project_highlights": ["..."],
  "strengths": ["..."],
  "risk_points": ["..."],
  "recommended_focuses": ["..."],
  "suggested_questions": ["..."],
  "keywords": ["..."]
}}

要求：
1. 聚焦技术项目、职责、技术栈、落地结果和可追问点
2. risk_points 指的是值得深挖或容易暴露深度不足的地方，不要攻击性表述
3. 如果简历信息不完整，也要尽量给出保守总结

目标岗位：
{role}

简历内容：
{resume_text}
"""
        )
        return prompt | chat_model | StrOutputParser()

    def analyze(self, role: str, resume_text: str) -> dict[str, Any]:
        content = str(resume_text or "").strip()
        if not content:
            return {
                "summary": "未上传简历，本轮按岗位通用能力进行面试。",
                "project_highlights": [],
                "strengths": [],
                "risk_points": [],
                "recommended_focuses": [],
                "suggested_questions": [],
                "keywords": [],
                "resume_hash": "",
            }

        try:
            raw = self.analysis_chain.invoke({"role": role or "通用技术岗位", "resume_text": _trim_text(content, 3200)})
            data = _safe_json_loads(raw)
            if data:
                data["resume_hash"] = _resume_hash(content)
                return {
                    "summary": str(data.get("summary", "")).strip() or "简历已解析，可结合项目经历进行提问。",
                    "project_highlights": [str(item).strip() for item in data.get("project_highlights", []) if str(item).strip()],
                    "strengths": [str(item).strip() for item in data.get("strengths", []) if str(item).strip()],
                    "risk_points": [str(item).strip() for item in data.get("risk_points", []) if str(item).strip()],
                    "recommended_focuses": [str(item).strip() for item in data.get("recommended_focuses", []) if str(item).strip()],
                    "suggested_questions": [str(item).strip() for item in data.get("suggested_questions", []) if str(item).strip()],
                    "keywords": [str(item).strip() for item in data.get("keywords", []) if str(item).strip()],
                    "resume_hash": data["resume_hash"],
                }
        except Exception as exc:
            logger.warning(f"[ResumeAnalystAgent] 简历分析失败，使用兜底摘要：{exc}")

        excerpt = _trim_text(content, 260)
        return {
            "summary": f"简历已上传，后续提问会优先围绕项目经历展开。简历摘要：{excerpt}",
            "project_highlights": [],
            "strengths": [],
            "risk_points": [],
            "recommended_focuses": [],
            "suggested_questions": [],
            "keywords": [],
            "resume_hash": _resume_hash(content),
        }


class EvaluationAgent:
    """负责判断候选人回答质量，并给提问 Agent 提供追问线索。"""

    def __init__(self, policy: InterviewPolicy):
        self.policy = policy
        self.evaluation_chain = self._build_evaluation_chain()

    @staticmethod
    def _build_evaluation_chain():
        prompt = PromptTemplate.from_template(
            """你是一个 Evaluation Agent，负责评估候选人这轮回答的质量。

请只输出 JSON，字段固定为：
{{
  "score": 0.0,
  "verdict": "strong | medium | weak",
  "reason": "简短中文判断",
  "strengths": ["..."],
  "weaknesses": ["..."],
  "followup_focus": "最值得继续追问的点"
}}

说明：
1. score 范围 0 到 1
2. 如果回答偏弱，weaknesses 要指出缺少的是原理、细节、案例还是结果
3. 如果回答较好，followup_focus 尽量给出具体技术点，便于继续追问

目标岗位：
{role}

当前问题：
{current_question}

候选人回答：
{user_input}

最近对话：
{history}

简历分析摘要：
{resume_summary}
"""
        )
        return prompt | chat_model | StrOutputParser()

    def evaluate(
        self,
        role: str,
        current_question: str,
        user_input: str,
        history: Sequence[dict],
        resume_analysis: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        history_text = _history_to_text(history, max_turns=6)
        resume_summary = str((resume_analysis or {}).get("summary", "")).strip() or "无简历分析"

        try:
            raw = self.evaluation_chain.invoke(
                {
                    "role": role or "通用技术岗位",
                    "current_question": current_question or "暂无当前问题",
                    "user_input": user_input,
                    "history": history_text,
                    "resume_summary": resume_summary,
                }
            )
            data = _safe_json_loads(raw)
            if data:
                score = max(0.0, min(1.0, float(data.get("score", 0.0) or 0.0)))
                verdict = str(data.get("verdict", "")).strip().lower() or self._score_to_verdict(score)
                return {
                    "score": score,
                    "verdict": verdict,
                    "reason": str(data.get("reason", "")).strip() or "评估完成",
                    "strengths": [str(item).strip() for item in data.get("strengths", []) if str(item).strip()],
                    "weaknesses": [str(item).strip() for item in data.get("weaknesses", []) if str(item).strip()],
                    "followup_focus": str(data.get("followup_focus", "")).strip() or "关键实现",
                }
        except Exception as exc:
            logger.warning(f"[EvaluationAgent] 回答评估失败，使用策略兜底：{exc}")

        score = self.policy.score_answer_quality(user_input, current_question, history)
        return {
            "score": score,
            "verdict": self._score_to_verdict(score),
            "reason": "使用规则策略完成回答评估",
            "strengths": [],
            "weaknesses": [],
            "followup_focus": self.policy.extract_followup_focus(user_input, current_question, history),
        }

    @staticmethod
    def _score_to_verdict(score: float) -> str:
        if score >= 0.75:
            return "strong"
        if score >= 0.45:
            return "medium"
        return "weak"


class InterviewAgent:
    """负责输出自然提问或提示，不直接做路由和评分。"""

    def __init__(self, role_manager: InterviewRoleManager, policy: InterviewPolicy):
        self.role_manager = role_manager
        self.policy = policy
        self.question_chain = self._build_question_chain()
        self.hint_chain = self._build_hint_chain()

    @staticmethod
    def _build_question_chain():
        prompt = PromptTemplate.from_template(
            """你是一个真实、专业、自然的中文技术面试官。

你的任务是根据当前阶段，只输出一句自然的提问。

要求：
1. 一次只问一个问题，不要连着问多个子问题
2. 语气像真实面试官，简洁、自然，不要模板腔
3. 如果 stage 是 first_question，要优先从项目经历或岗位核心能力切入
4. 如果 stage 是 follow_up，要围绕 followup_focus 深挖，不要突然跳题
5. 如果 stage 是 next_question，要明显切到新的能力维度，避免继续纠缠上一个点
6. 如果有简历分析，优先结合简历里的项目、职责、技术选型和结果来问
7. 如果有后台题库参考，可以参考它的考察方向，但不要机械照抄，仍然要结合上下文自然提问
8. 只输出问题本身，不要输出解释、评分或前置说明

岗位：
{role}

阶段：
{stage}

当前能力维度：
{dimension_name}

当前维度关注点：
{dimension_focus}

简历摘要：
{resume_summary}

简历可追问点：
{resume_focuses}

上一题：
{current_question}

候选人刚刚的回答：
{user_input}

回答评估：
{evaluation_summary}

建议追问点：
{followup_focus}

后台题库参考：
{question_bank}

最近对话：
{history}
"""
        )
        return prompt | chat_model | StrOutputParser()

    @staticmethod
    def _build_hint_chain():
        prompt = PromptTemplate.from_template(
            """你是一个专业但友好的技术面试官，现在需要给候选人一个不泄题的提示。

要求：
1. 只给 1 到 3 句中文提示
2. 给方向，不直接给标准答案
3. 尽量指出可以从哪些角度组织回答
4. 最后一句鼓励候选人继续补充

当前问题：
{current_question}

候选人输入：
{user_input}

回答薄弱点：
{weaknesses}

最近对话：
{history}
"""
        )
        return prompt | chat_model | StrOutputParser()

    def generate_question(
        self,
        *,
        role: str,
        stage: str,
        history: Sequence[dict],
        current_question: str,
        user_input: str,
        question_index: int,
        resume_analysis: dict[str, Any] | None = None,
        evaluation_result: dict[str, Any] | None = None,
        on_token: Callable[[str], None] | None = None,
    ) -> str:
        dimension_name = self.role_manager.get_dimension_name(role, question_index)
        dimension_focus = self.role_manager.get_dimension_focus(role, question_index)
        resume_summary = str((resume_analysis or {}).get("summary", "")).strip() or "未上传简历，按岗位通用能力提问"
        resume_focuses = "；".join((resume_analysis or {}).get("recommended_focuses", [])[:4]) or "无"
        evaluation_summary = str((evaluation_result or {}).get("reason", "")).strip() or "暂无"
        followup_focus = str((evaluation_result or {}).get("followup_focus", "")).strip() or "关键实现"
        question_bank = "\n".join(self.role_manager.get_reference_questions(role, question_index)) or "无"

        try:
            prompt_payload = {
                "role": role or "通用技术岗位",
                "stage": stage,
                "dimension_name": dimension_name,
                "dimension_focus": dimension_focus,
                "resume_summary": _trim_text(resume_summary, 800),
                "resume_focuses": resume_focuses,
                "current_question": current_question or "无",
                "user_input": user_input or "无",
                "evaluation_summary": evaluation_summary,
                "followup_focus": followup_focus,
                "question_bank": question_bank,
                "history": _history_to_text(history),
            }
            if on_token:
                parts = []
                for chunk in self.question_chain.stream(prompt_payload):
                    text_chunk = str(chunk or "")
                    if text_chunk:
                        parts.append(text_chunk)
                        on_token(text_chunk)
                question = "".join(parts)
            else:
                question = self.question_chain.invoke(prompt_payload)
            text = str(question or "").strip()
            if text:
                return text
        except Exception as exc:
            logger.warning(f"[InterviewAgent] 生成问题失败，使用规则兜底：{exc}")

        if stage == "first_question" and (resume_analysis or {}).get("summary"):
            return "我们先从你的代表性项目开始。你在这个项目里承担的核心职责是什么，最后做出了什么结果？"
        if stage == "follow_up":
            return f"刚才这个点我想再往下追问一层。围绕{followup_focus}，你当时具体是怎么做判断和落地的？"
        return f"我们换一个方向，聊聊{dimension_name}。你可以结合{dimension_focus}，说说你的理解和实际经验。"

    def build_hint(
        self,
        user_input: str,
        current_question: str,
        history: Sequence[dict],
        evaluation_result: dict[str, Any] | None = None,
        on_token: Callable[[str], None] | None = None,
    ) -> str:
        weaknesses = "；".join((evaluation_result or {}).get("weaknesses", [])[:3]) or "可以从原理、流程、案例和结果几个角度展开"
        try:
            prompt_payload = {
                "current_question": current_question or "暂无当前问题",
                "user_input": user_input or "无",
                "weaknesses": weaknesses,
                "history": _history_to_text(history, max_turns=6),
            }
            if on_token:
                parts = []
                for chunk in self.hint_chain.stream(prompt_payload):
                    text_chunk = str(chunk or "")
                    if text_chunk:
                        parts.append(text_chunk)
                        on_token(text_chunk)
                hint = "".join(parts)
            else:
                hint = self.hint_chain.invoke(prompt_payload)
            text = str(hint or "").strip()
            if text:
                return text
        except Exception as exc:
            logger.warning(f"[InterviewAgent] 生成提示失败，使用策略兜底：{exc}")

        return self.policy.build_hint(user_input, current_question, history)


class ReportAgent:
    """负责把面试日志、评估结果和知识库参考整理成最终报告。"""

    def __init__(self):
        self.report_chain = self._build_report_chain()

    @staticmethod
    def _build_report_chain():
        report_prompt = PromptTemplate.from_template(load_report_prompts())
        return report_prompt | chat_model | StrOutputParser()

    def generate(
        self,
        *,
        final_score: int,
        interview_history: Sequence[dict],
        interview_questions: Sequence[str],
        interview_state: dict[str, Any] | None = None,
        resume_analysis: dict[str, Any] | None = None,
        evaluation_records: Sequence[dict] | None = None,
        references: Sequence[str] | None = None,
    ) -> str:
        full_log = []
        for message in interview_history:
            role = "候选人" if message.get("role") == "user" else "面试官"
            full_log.append(f"{role}：{message.get('content', '')}")

        question_text = "\n".join(f"{idx + 1}. {question}" for idx, question in enumerate(interview_questions)) or "本轮未记录到问题"
        resume_summary = str((resume_analysis or {}).get("summary", "")).strip() or "未上传简历，本轮按岗位通用能力进行面试。"
        strengths = "；".join((resume_analysis or {}).get("strengths", [])[:5]) or "暂无"
        risks = "；".join((resume_analysis or {}).get("risk_points", [])[:5]) or "暂无"
        references_text = "\n".join(references or []) or "暂无知识库参考"

        eval_lines = []
        for idx, item in enumerate(evaluation_records or [], start=1):
            eval_lines.append(
                f"{idx}. 得分 {int(round(float(item.get('score', 0.0)) * 100))}/100；"
                f"结论：{item.get('verdict', '')}；"
                f"原因：{item.get('reason', '')}；"
                f"追问点：{item.get('followup_focus', '')}"
            )
        evaluation_text = "\n".join(eval_lines) or "暂无逐轮评估记录"

        interview_log = (
            f"【本次面试得分】\n{final_score} 分\n\n"
            f"【岗位】\n{(interview_state or {}).get('target_role', '未设置岗位')}\n\n"
            f"【简历分析摘要】\n{resume_summary}\n\n"
            f"【简历亮点】\n{strengths}\n\n"
            f"【建议重点深挖处】\n{risks}\n\n"
            f"【本次面试问题】\n{question_text}\n\n"
            f"【逐轮回答评估】\n{evaluation_text}\n\n"
            f"【完整对话记录】\n{chr(10).join(full_log)}\n\n"
            f"【知识库参考】\n{references_text}"
        )

        report = self.report_chain.invoke({"interview_log": interview_log})
        return f"本次模拟面试得分：{final_score} / 100\n\n{str(report or '').strip()}"


class MultiAgentInterviewCoordinator:
    """把多个专职 Agent 编排成一条完整的模拟面试链路。"""

    def __init__(
        self,
        *,
        policy: InterviewPolicy,
        state_machine: InterviewStateMachine,
        role_manager: InterviewRoleManager,
        rag_service_getter: Callable[[], Any],
    ):
        self.policy = policy
        self.state_machine = state_machine
        self.role_manager = role_manager
        self.rag_service_getter = rag_service_getter

        self.router_agent = RouterAgent(policy)
        self.resume_agent = ResumeAnalystAgent()
        self.evaluation_agent = EvaluationAgent(policy)
        self.interview_agent = InterviewAgent(role_manager, policy)
        self.report_agent = ReportAgent()

    def ensure_state(self, interview_state: dict[str, Any] | None = None) -> dict[str, Any]:
        state = self.state_machine.ensure_state(interview_state)
        state["multi_agent"] = _build_multi_agent_state(state.get("multi_agent"))
        return state

    def start_interview(
        self,
        role: str,
        resume_text: str = "",
        resume_filename: str = "",
        interview_state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        state = self.state_machine.start_interview(role)
        state["resume_text"] = (resume_text or "").strip()
        state["resume_filename"] = (resume_filename or "").strip()
        state["multi_agent"] = _build_multi_agent_state((interview_state or {}).get("multi_agent"))

        route_plan = self.router_agent.route_start(role, resume_text, interview_state)
        self._record_route(state, route_plan.route, route_plan.reason)

        resume_analysis = state["multi_agent"].get("resume_analysis", {})
        if route_plan.should_analyze_resume:
            resume_analysis = self.resume_agent.analyze(role, resume_text)
            state["multi_agent"]["resume_analysis"] = resume_analysis
        elif resume_text and not resume_analysis:
            state["multi_agent"]["resume_analysis"] = self.resume_agent.analyze(role, resume_text)
            resume_analysis = state["multi_agent"]["resume_analysis"]

        first_question = self.interview_agent.generate_question(
            role=role,
            stage="first_question",
            history=[],
            current_question="",
            user_input="",
            question_index=0,
            resume_analysis=resume_analysis,
            evaluation_result=None,
        )
        state = self.state_machine.update_current_question(state, first_question, is_followup=False)
        return {
            "state": state,
            "question": first_question,
            "question_to_record": first_question,
            "route": route_plan.route,
        }

    def process_turn(
        self,
        *,
        user_input: str,
        history: Sequence[dict],
        interview_state: dict[str, Any] | None,
        interview_questions: Sequence[str],
    ) -> dict[str, Any]:
        state = self.ensure_state(interview_state)
        current_question = state.get("current_question") or self._get_current_question(history)
        role = state.get("target_role", "")
        resume_analysis = state.get("multi_agent", {}).get("resume_analysis", {})

        route_plan = self.router_agent.route_turn(user_input, current_question, history)
        self._record_route(state, route_plan.route, route_plan.reason)

        if route_plan.route == "finish_interview":
            state["finished"] = True
            return {
                "reply": "好的，我们这轮模拟面试先到这里。稍后我会基于你本次的表现生成总结和评分。",
                "state": state,
                "action": "finish",
            }

        if route_plan.route == "give_hint":
            hint = self.interview_agent.build_hint(user_input, current_question, history, None)
            state["awaiting_answer"] = True
            return {"reply": hint, "state": state, "action": "hint"}

        evaluation = self.evaluation_agent.evaluate(
            role=role,
            current_question=current_question,
            user_input=user_input,
            history=history,
            resume_analysis=resume_analysis,
        )
        self._record_evaluation(state, current_question, user_input, evaluation)

        scores = list(state.get("answer_scores", []))
        scores.append(round(float(evaluation.get("score", 0.0) or 0.0), 4))
        state["answer_scores"] = scores
        state["latest_score"] = round(float(evaluation.get("score", 0.0) or 0.0), 4)
        if float(evaluation.get("score", 0.0) or 0.0) < 0.45:
            state["poor_answer_count"] = int(state.get("poor_answer_count", 0)) + 1
        else:
            state["poor_answer_count"] = 0

        state = self.state_machine.mark_answered(state)
        transition = self.state_machine.decide_next_action(
            InterviewDecision(
                intent="answer_question",
                confidence=float(evaluation.get("score", 0.0) or 0.0),
                reason=str(evaluation.get("reason", "")).strip(),
            ),
            state,
            history,
            interview_questions,
        )

        if transition.should_end:
            state["finished"] = True
            return {
                "reply": "这一轮我们先到这里，稍后我会根据你前面的回答整理总结和评分。",
                "state": state,
                "action": "finish",
            }

        if transition.action == "hint":
            hint = self.interview_agent.build_hint(user_input, current_question, history, evaluation)
            state["awaiting_answer"] = True
            return {"reply": hint, "state": state, "action": "hint"}

        next_stage = "follow_up" if transition.action == "follow_up" else "next_question"
        question_index = max(0, int(state.get("current_question_index", 0)))
        question = self.interview_agent.generate_question(
            role=role,
            stage=next_stage,
            history=history,
            current_question=current_question,
            user_input=user_input,
            question_index=question_index,
            resume_analysis=resume_analysis,
            evaluation_result=evaluation,
        )
        state = self.state_machine.update_current_question(state, question, is_followup=transition.action == "follow_up")
        return {
            "reply": question,
            "state": state,
            "action": transition.action,
            "question_to_record": question,
        }

    def calculate_interview_score(
        self,
        interview_state: dict[str, Any] | None = None,
        interview_history: Sequence[dict] | None = None,
    ) -> int:
        state = self.ensure_state(interview_state)
        scores = [float(item) for item in state.get("answer_scores", []) if isinstance(item, (int, float))]
        if not scores:
            evaluations = state.get("multi_agent", {}).get("evaluations", []) or []
            scores = [float(item.get("score", 0.0) or 0.0) for item in evaluations]

        if not scores and interview_history:
            current_question = state.get("current_question", "")
            for item in interview_history:
                if item.get("role") == "user":
                    scores.append(self.policy.score_answer_quality(item.get("content", ""), current_question, interview_history))

        if not scores:
            return 0
        return max(0, min(100, int(round(sum(scores) / len(scores) * 100))))

    def generate_report(
        self,
        *,
        interview_history: Sequence[dict],
        interview_questions: Sequence[str],
        interview_state: dict[str, Any] | None = None,
    ) -> str:
        state = self.ensure_state(interview_state)
        role = state.get("target_role", "")
        evaluations = state.get("multi_agent", {}).get("evaluations", []) or []
        resume_analysis = state.get("multi_agent", {}).get("resume_analysis", {}) or {}
        question_query = "；".join(interview_questions) if interview_questions else "本次面试问题"

        references: list[str] = []
        try:
            docs = self.rag_service_getter().retriever_docs(question_query, interview_history)
            for idx, doc in enumerate(docs, start=1):
                references.append(f"【参考资料 {idx}】{doc.page_content}")
        except Exception as exc:
            logger.warning(f"[MultiAgentInterviewCoordinator] 报告阶段检索知识库失败：{exc}")

        final_score = self.calculate_interview_score(state, interview_history)
        report = self.report_agent.generate(
            final_score=final_score,
            interview_history=interview_history,
            interview_questions=interview_questions,
            interview_state=state,
            resume_analysis=resume_analysis,
            evaluation_records=evaluations,
            references=references,
        )
        state["multi_agent"]["last_report_meta"] = {
            "question_count": len(interview_questions),
            "evaluation_count": len(evaluations),
            "role": role,
            "final_score": final_score,
        }
        return report

    @staticmethod
    def _get_current_question(history: Sequence[dict]) -> str:
        for message in reversed(history):
            if message.get("role") == "assistant":
                content = str(message.get("content", "")).strip()
                if content:
                    return content
        return ""

    @staticmethod
    def _record_route(state: dict[str, Any], route: str, reason: str) -> None:
        multi_agent = _build_multi_agent_state(state.get("multi_agent"))
        route_item = {"route": route, "reason": reason}
        multi_agent["last_route"] = route_item
        multi_agent["route_history"] = _append_bounded_list(list(multi_agent.get("route_history", [])), route_item, limit=20)
        state["multi_agent"] = multi_agent

    @staticmethod
    def _record_evaluation(
        state: dict[str, Any],
        current_question: str,
        user_input: str,
        evaluation: dict[str, Any],
    ) -> None:
        multi_agent = _build_multi_agent_state(state.get("multi_agent"))
        evaluation_item = {
            "question": current_question,
            "answer": user_input,
            **evaluation,
        }
        multi_agent["last_evaluation"] = evaluation_item
        multi_agent["evaluations"] = _append_bounded_list(list(multi_agent.get("evaluations", [])), evaluation_item, limit=25)
        state["multi_agent"] = multi_agent
