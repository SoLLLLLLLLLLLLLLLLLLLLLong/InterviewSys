from __future__ import annotations

import uuid
from typing import Any, Callable, Sequence, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from agent.interview_graph_components import EvidenceJudge, InterviewPlanner
from agent.interview_multi_agent import MultiAgentInterviewCoordinator
from agent.interview_policy import InterviewDecision, InterviewPolicy
from agent.interview_role_manager import InterviewRoleManager
from agent.interview_state_machine import InterviewStateMachine
from infrastructure.run_store import agent_run_store
from utils.logger_handler import logger


class InterviewAgentState(TypedDict, total=False):
    """一次面试工作流中所有 LangGraph 节点共享的状态结构。

    可以把它理解成“多 Agent 之间传递的一张任务单”：
    Router 写入 route，Resume Analyst 写入 resume_analysis，
    Planner 写入 plan，Evaluation 写入 evaluation，
    Report Agent 最后写入 report。
    """

    run_id: str
    operation: str
    role: str
    resume_text: str
    resume_filename: str
    history: list[dict[str, Any]]
    interview_questions: list[str]
    business_state: dict[str, Any]
    current_question: str
    user_input: str
    route: str
    route_reason: str
    plan: list[dict[str, str]]
    resume_analysis: dict[str, Any]
    evaluation: dict[str, Any]
    transition_action: str
    evidence: list[dict[str, Any]]
    evidence_judgement: dict[str, Any]
    evidence_retry_count: int
    should_retry_evidence: bool
    reply: str
    action: str
    question_to_record: str
    graph_events: list[dict[str, Any]]
    final_score: int
    report: str


class LangGraphInterviewCoordinator:
    """Explicit LangGraph implementation of the multi-agent interview flow.

    The public methods intentionally match MultiAgentInterviewCoordinator so the
    existing API and frontend remain compatible while the orchestration changes.
    """

    def __init__(
        self,
        *,
        policy: InterviewPolicy,
        state_machine: InterviewStateMachine,
        role_manager: InterviewRoleManager,
        rag_service_getter: Callable[[], Any],
    ) -> None:
        self.policy = policy
        self.state_machine = state_machine
        self.role_manager = role_manager
        self.rag_service_getter = rag_service_getter
        self.legacy = MultiAgentInterviewCoordinator(
            policy=policy,
            state_machine=state_machine,
            role_manager=role_manager,
            rag_service_getter=rag_service_getter,
        )
        self.router_agent = self.legacy.router_agent
        self.resume_agent = self.legacy.resume_agent
        self.evaluation_agent = self.legacy.evaluation_agent
        self.interview_agent = self.legacy.interview_agent
        self.report_agent = self.legacy.report_agent
        self.planner = InterviewPlanner(role_manager)
        self.evidence_judge = EvidenceJudge()
        self.checkpointer = MemorySaver()
        self.start_graph = self._build_start_graph()
        self.turn_graph = self._build_turn_graph()
        self.report_graph = self._build_report_graph()

    def _build_start_graph(self):
        # 开始面试图：
        # router -> resume_analyst -> planner -> retrieval -> evidence_judge -> interview_agent
        # 用显式图结构控制流程，比完全让模型自由发挥更稳定。
        graph = StateGraph(InterviewAgentState)
        graph.add_node("router", self._start_router_node)
        graph.add_node("resume_analyst", self._resume_node)
        graph.add_node("planner", self._planner_node)
        graph.add_node("knowledge_retrieval", self._retrieval_node)
        graph.add_node("evidence_judge", self._evidence_node)
        graph.add_node("interview_agent", self._first_question_node)
        graph.add_edge(START, "router")
        graph.add_edge("router", "resume_analyst")
        graph.add_edge("resume_analyst", "planner")
        graph.add_edge("planner", "knowledge_retrieval")
        graph.add_edge("knowledge_retrieval", "evidence_judge")
        graph.add_conditional_edges(
            "evidence_judge",
            lambda state: "retry" if state.get("should_retry_evidence") else "continue",
            {"retry": "knowledge_retrieval", "continue": "interview_agent"},
        )
        graph.add_edge("interview_agent", END)
        return graph.compile(checkpointer=self.checkpointer)

    def _build_turn_graph(self):
        # 每一轮回答后的处理图：
        # 先 Router 判断用户意图，再根据情况提示、结束或评分。
        # 评分后交给状态机判断追问/切题/结束，再检索证据并生成下一问。
        graph = StateGraph(InterviewAgentState)
        graph.add_node("router", self._turn_router_node)
        graph.add_node("give_hint", self._hint_node)
        graph.add_node("finish", self._finish_node)
        graph.add_node("evaluation_agent", self._evaluation_node)
        graph.add_node("state_machine", self._transition_node)
        graph.add_node("knowledge_retrieval", self._retrieval_node)
        graph.add_node("evidence_judge", self._evidence_node)
        graph.add_node("interview_agent", self._next_question_node)
        graph.add_edge(START, "router")
        graph.add_conditional_edges(
            "router",
            lambda state: state.get("route", "evaluate_answer"),
            {"give_hint": "give_hint", "finish_interview": "finish", "evaluate_answer": "evaluation_agent"},
        )
        graph.add_edge("give_hint", END)
        graph.add_edge("finish", END)
        graph.add_edge("evaluation_agent", "state_machine")
        graph.add_conditional_edges(
            "state_machine",
            lambda state: state.get("transition_action", "next_question"),
            {"finish": "finish", "hint": "give_hint", "follow_up": "knowledge_retrieval", "next_question": "knowledge_retrieval"},
        )
        graph.add_edge("knowledge_retrieval", "evidence_judge")
        graph.add_conditional_edges(
            "evidence_judge",
            lambda state: "retry" if state.get("should_retry_evidence") else "continue",
            {"retry": "knowledge_retrieval", "continue": "interview_agent"},
        )
        graph.add_edge("interview_agent", END)
        return graph.compile(checkpointer=self.checkpointer)

    def _build_report_graph(self):
        # 报告生成图：当前比较简单，只让 Report Agent 根据历史记录生成报告。
        # 后续如果要加“证据校验/格式化/导出”等步骤，可以继续加节点。
        graph = StateGraph(InterviewAgentState)
        graph.add_node("report_agent", self._report_node)
        graph.add_edge(START, "report_agent")
        graph.add_edge("report_agent", END)
        return graph.compile(checkpointer=self.checkpointer)

    def _emit(self, state: InterviewAgentState, event_type: str, node: str, content: str = "", **payload: Any) -> dict[str, Any]:
        # 每个节点运行时都会写事件到 agent_run_store。
        # 前端轮询/流式读取这些事件，就能展示 Agent 执行过程。
        run_id = state["run_id"]
        if event_type not in {"run_finished", "run_error"} and agent_run_store.is_cancelled(run_id):
            raise RuntimeError("Agent run cancelled by user")
        return agent_run_store.append_event(run_id, event_type, node, content=content, **payload)

    def _event(
        self,
        state: InterviewAgentState,
        event_type: str,
        node: str,
        content: str = "",
        prior: Sequence[dict[str, Any]] = (),
    ) -> dict[str, Any]:
        event = self._emit(state, event_type, node, content)
        return {"graph_events": [*state.get("graph_events", []), *prior, event]}

    def _start_router_node(self, state: InterviewAgentState) -> dict[str, Any]:
        # Router Agent：决定这次开始面试应该走什么流程。
        # 当前 start 流程一般会进入简历分析和题目规划。
        started = self._emit(state, "node_started", "router", "正在识别面试任务")
        route = self.router_agent.route_start(state["role"], state.get("resume_text", ""), state.get("business_state"))
        business_state = self.state_machine.start_interview(state["role"])
        business_state["user_id"] = state.get("business_state", {}).get("user_id")
        business_state["organization_id"] = state.get("business_state", {}).get("organization_id")
        business_state["resume_text"] = state.get("resume_text", "")
        business_state["resume_filename"] = state.get("resume_filename", "")
        business_state = self.legacy.ensure_state(business_state)
        self.legacy._record_route(business_state, route.route, route.reason)
        return {
            "route": route.route,
            "route_reason": route.reason,
            "business_state": business_state,
            **self._event(state, "node_finished", "router", route.reason, [started]),
        }

    def _resume_node(self, state: InterviewAgentState) -> dict[str, Any]:
        started = self._emit(state, "node_started", "resume_analyst", "正在分析候选人简历")
        analysis = self.resume_agent.analyze(state["role"], state.get("resume_text", ""))
        business_state = state["business_state"]
        business_state["multi_agent"]["resume_analysis"] = analysis
        return {"resume_analysis": analysis, "business_state": business_state, **self._event(state, "node_finished", "resume_analyst", "简历分析完成", [started])}

    def _planner_node(self, state: InterviewAgentState) -> dict[str, Any]:
        started = self._emit(state, "node_started", "planner", "正在规划面试能力维度")
        plan = self.planner.build(state["role"], state.get("resume_analysis"))
        business_state = state["business_state"]
        business_state["multi_agent"]["interview_plan"] = plan
        return {"plan": plan, "business_state": business_state, **self._event(state, "node_finished", "planner", f"已规划 {len(plan)} 个能力维度", [started])}

    def _retrieval_node(self, state: InterviewAgentState) -> dict[str, Any]:
        started = self._emit(state, "node_started", "knowledge_retrieval", "正在检索面试知识")
        query = state.get("current_question") or state.get("user_input") or state.get("role", "技术面试")
        tool_event = self._emit(state, "tool_called", "knowledge_retrieval", "调用 knowledge_search", tool="knowledge_search", arguments={"query": query})
        evidence: list[dict[str, Any]] = []
        try:
            docs = self.rag_service_getter().retriever_docs(
                query,
                state.get("history", []),
                filters={
                    "user_id": state.get("business_state", {}).get("user_id"),
                    "organization_id": state.get("business_state", {}).get("organization_id"),
                },
            )
            for index, doc in enumerate(docs, start=1):
                metadata = dict(doc.metadata or {})
                evidence.append(
                    {
                        "id": metadata.get("chunk_id") or f"chunk-{index}",
                        "source": metadata.get("source") or metadata.get("filename") or "知识库文档",
                        "content": str(doc.page_content),
                        "score": metadata.get("rerank_score"),
                        "metadata": metadata,
                    }
                )
        except Exception as exc:
            logger.warning(f"[LangGraph] 知识检索失败，继续使用无证据降级路径：{exc}")
        event = self._event(state, "retrieval_finished", "knowledge_retrieval", f"召回 {len(evidence)} 条证据", [started, tool_event])
        return {"evidence": evidence, **event}

    def _evidence_node(self, state: InterviewAgentState) -> dict[str, Any]:
        started = self._emit(state, "node_started", "evidence_judge", "正在检查证据相关性与充分性")
        query = state.get("current_question") or state.get("user_input") or state.get("role", "")
        judgement = self.evidence_judge.judge(query, state.get("evidence", []))
        retry_count = int(state.get("evidence_retry_count", 0))
        should_retry = not judgement["sufficient"] and retry_count < 1
        business_state = state["business_state"]
        business_state["multi_agent"]["last_evidence"] = state.get("evidence", [])
        business_state["multi_agent"]["evidence_judgement"] = judgement
        return {
            "evidence_judgement": judgement,
            "evidence_retry_count": retry_count + (1 if should_retry else 0),
            "should_retry_evidence": should_retry,
            "business_state": business_state,
            **self._event(state, "node_finished", "evidence_judge", judgement["reason"], [started]),
        }

    def _first_question_node(self, state: InterviewAgentState) -> dict[str, Any]:
        started = self._emit(state, "node_started", "interview_agent", "正在生成首个面试问题")
        question = self.interview_agent.generate_question(
            role=state["role"],
            stage="first_question",
            history=[],
            current_question="",
            user_input="",
            question_index=0,
            resume_analysis=state.get("resume_analysis"),
            evaluation_result=None,
        )
        business_state = self.state_machine.update_current_question(state["business_state"], question, is_followup=False)
        return {
            "reply": question,
            "question_to_record": question,
            "action": "first_question",
            "business_state": business_state,
            **self._event(state, "node_finished", "interview_agent", "首题生成完成", [started]),
        }

    def _turn_router_node(self, state: InterviewAgentState) -> dict[str, Any]:
        started = self._emit(state, "node_started", "router", "正在识别候选人意图")
        route = self.router_agent.route_turn(state["user_input"], state["current_question"], state.get("history", []))
        business_state = state["business_state"]
        self.legacy._record_route(business_state, route.route, route.reason)
        return {"route": route.route, "route_reason": route.reason, "business_state": business_state, **self._event(state, "node_finished", "router", route.reason, [started])}

    def _evaluation_node(self, state: InterviewAgentState) -> dict[str, Any]:
        started = self._emit(state, "node_started", "evaluation_agent", "正在评估回答质量")
        evaluation = self.evaluation_agent.evaluate(
            role=state["role"],
            current_question=state["current_question"],
            user_input=state["user_input"],
            history=state.get("history", []),
            resume_analysis=state.get("resume_analysis"),
        )
        business_state = state["business_state"]
        self.legacy._record_evaluation(business_state, state["current_question"], state["user_input"], evaluation)
        scores = list(business_state.get("answer_scores", []))
        score = round(float(evaluation.get("score", 0.0)), 4)
        scores.append(score)
        business_state["answer_scores"] = scores
        business_state["latest_score"] = score
        business_state["poor_answer_count"] = int(business_state.get("poor_answer_count", 0)) + 1 if score < 0.45 else 0
        return {"evaluation": evaluation, "business_state": business_state, **self._event(state, "node_finished", "evaluation_agent", f"回答得分 {int(score * 100)}", [started])}

    def _transition_node(self, state: InterviewAgentState) -> dict[str, Any]:
        started = self._emit(state, "node_started", "state_machine", "正在决定追问、切题或结束")
        business_state = self.state_machine.mark_answered(state["business_state"])
        evaluation = state["evaluation"]
        transition = self.state_machine.decide_next_action(
            InterviewDecision(intent="answer_question", confidence=float(evaluation.get("score", 0)), reason=str(evaluation.get("reason", ""))),
            business_state,
            state.get("history", []),
            state.get("interview_questions", []),
        )
        action = "finish" if transition.should_end else transition.action
        return {"transition_action": action, "business_state": business_state, **self._event(state, "node_finished", "state_machine", transition.reason, [started])}

    def _hint_node(self, state: InterviewAgentState) -> dict[str, Any]:
        started = self._emit(state, "node_started", "interview_agent", "正在组织提示")
        reply = self.interview_agent.build_hint(
            state["user_input"],
            state["current_question"],
            state.get("history", []),
            state.get("evaluation"),
            on_token=lambda chunk: self._emit(state, "token", "interview_agent", chunk),
        )
        business_state = state["business_state"]
        business_state["awaiting_answer"] = True
        return {"reply": reply, "action": "hint", "business_state": business_state, **self._event(state, "node_finished", "interview_agent", "提示生成完成", [started])}

    def _finish_node(self, state: InterviewAgentState) -> dict[str, Any]:
        started = self._emit(state, "node_started", "state_machine", "正在结束本轮面试")
        business_state = state["business_state"]
        business_state["finished"] = True
        return {
            "reply": "好的，我们这轮模拟面试先到这里。稍后我会基于你本次的表现生成总结和评分。",
            "action": "finish",
            "business_state": business_state,
            **self._event(state, "node_finished", "state_machine", "面试结束", [started]),
        }

    def _next_question_node(self, state: InterviewAgentState) -> dict[str, Any]:
        started = self._emit(state, "node_started", "interview_agent", "正在生成下一轮问题")
        action = state.get("transition_action", "next_question")
        question = self.interview_agent.generate_question(
            role=state["role"],
            stage="follow_up" if action == "follow_up" else "next_question",
            history=state.get("history", []),
            current_question=state["current_question"],
            user_input=state["user_input"],
            question_index=max(0, int(state["business_state"].get("current_question_index", 0))),
            resume_analysis=state.get("resume_analysis"),
            evaluation_result=state.get("evaluation"),
            on_token=lambda chunk: self._emit(state, "token", "interview_agent", chunk),
        )
        business_state = self.state_machine.update_current_question(state["business_state"], question, is_followup=action == "follow_up")
        return {
            "reply": question,
            "action": action,
            "question_to_record": question,
            "business_state": business_state,
            **self._event(state, "node_finished", "interview_agent", "下一题生成完成", [started]),
        }

    def _report_node(self, state: InterviewAgentState) -> dict[str, Any]:
        started = self._emit(state, "node_started", "report_agent", "正在汇总评分、证据与面试记录")
        business_state = state.get("business_state", {})
        multi_agent = business_state.get("multi_agent", {})
        evidence = multi_agent.get("last_evidence", []) or []
        references = [
            f"{item.get('source', '知识库文档')}：{str(item.get('content', ''))[:240]}"
            for item in evidence
        ]
        report = self.report_agent.generate(
            final_score=int(state.get("final_score", 0)),
            interview_history=state.get("history", []),
            interview_questions=state.get("interview_questions", []),
            interview_state=business_state,
            resume_analysis=multi_agent.get("resume_analysis", {}),
            evaluation_records=multi_agent.get("evaluations", []),
            references=references,
        )
        return {
            "report": report,
            **self._event(state, "node_finished", "report_agent", "面试报告生成完成", [started]),
        }

    def _invoke(self, graph, payload: InterviewAgentState) -> InterviewAgentState:
        run_id = payload["run_id"]
        agent_run_store.append_event(run_id, "run_started", "workflow", content=payload["operation"])
        try:
            result = graph.invoke(payload, config={"configurable": {"thread_id": run_id}})
            # The recovery API needs enough output to rebuild the interrupted UI
            # and persist the final interview state after a temporary disconnect.
            recovery_result = {
                "action": result.get("action", ""),
                "reply": result.get("reply", ""),
                "question_to_record": result.get("question_to_record", ""),
                "state": result.get("business_state", {}),
                "evidence": result.get("evidence", []),
                "evidence_judgement": result.get("evidence_judgement", {}),
                "report": result.get("report", ""),
            }
            finish_event = agent_run_store.append_event(run_id, "run_finished", "workflow", result=recovery_result)
            result["graph_events"] = [*result.get("graph_events", []), finish_event]
            return result
        except Exception as exc:
            if not agent_run_store.is_cancelled(run_id):
                agent_run_store.append_event(run_id, "run_error", "workflow", detail=str(exc))
            raise

    def start_interview(self, role: str, resume_text: str = "", resume_filename: str = "", interview_state=None, run_id: str | None = None, tenant_context: dict[str, Any] | None = None) -> dict[str, Any]:
        tenant_context = tenant_context or {}
        run_id = run_id or agent_run_store.create(
            "interview_start",
            tenant_context.get("platform_user_id"),
            tenant_context.get("organization_id"),
            {"role": role, "has_resume": bool(resume_text)},
        )
        result = self._invoke(
            self.start_graph,
            {
                "run_id": run_id,
                "operation": "start",
                "role": role,
                "resume_text": resume_text,
                "resume_filename": resume_filename,
                "business_state": {**(interview_state or {}), **tenant_context},
                "history": [],
                "interview_questions": [],
                "graph_events": [],
            },
        )
        return {
            "state": result["business_state"],
            "question": result["reply"],
            "question_to_record": result["question_to_record"],
            "route": result.get("route", "start_interview"),
            "run_id": run_id,
            "events": result.get("graph_events", []),
            "evidence": result.get("evidence", []),
            "evidence_judgement": result.get("evidence_judgement", {}),
        }

    def process_turn(self, *, user_input: str, history: Sequence[dict], interview_state, interview_questions: Sequence[str], run_id: str | None = None) -> dict[str, Any]:
        business_state = self.legacy.ensure_state(interview_state)
        run_id = run_id or agent_run_store.create(
            "interview_turn",
            business_state.get("platform_user_id"),
            business_state.get("organization_id"),
            {"role": business_state.get("target_role", ""), "message": user_input[:500]},
        )
        result = self._invoke(
            self.turn_graph,
            {
                "run_id": run_id,
                "operation": "turn",
                "role": business_state.get("target_role", "通用技术岗位"),
                "history": list(history),
                "interview_questions": list(interview_questions),
                "business_state": business_state,
                "current_question": business_state.get("current_question") or self.legacy._get_current_question(history),
                "user_input": user_input,
                "resume_analysis": business_state.get("multi_agent", {}).get("resume_analysis", {}),
                "graph_events": [],
            },
        )
        return {
            "reply": result.get("reply", ""),
            "state": result["business_state"],
            "action": result.get("action", ""),
            "question_to_record": result.get("question_to_record", ""),
            "run_id": run_id,
            "events": result.get("graph_events", []),
            "evidence": result.get("evidence", []),
            "evidence_judgement": result.get("evidence_judgement", {}),
        }

    def calculate_interview_score(self, interview_state=None, interview_history=None) -> int:
        return self.legacy.calculate_interview_score(interview_state, interview_history)

    def generate_report(self, *, interview_history, interview_questions, interview_state=None) -> str:
        business_state = self.legacy.ensure_state(interview_state)
        run_id = agent_run_store.create(
            "interview_report",
            business_state.get("platform_user_id"),
            business_state.get("organization_id"),
            {"role": business_state.get("target_role", ""), "question_count": len(interview_questions)},
        )
        result = self._invoke(
            self.report_graph,
            {
                "run_id": run_id,
                "operation": "report",
                "business_state": business_state,
                "history": list(interview_history),
                "interview_questions": list(interview_questions),
                "final_score": self.calculate_interview_score(business_state, interview_history),
                "graph_events": [],
            },
        )
        return str(result.get("report", ""))
