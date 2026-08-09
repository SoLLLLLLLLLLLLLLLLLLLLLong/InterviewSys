from __future__ import annotations

from typing import Any, Sequence

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from agent.agent_tools import (
    fetch_external_data,
    get_city,
    get_current_month,
    get_id,
    get_weather,
    rag_summarize,
    knowledge_search,
    weather_search,
    tool_tenant_context,
    resume_lookup,
    question_search,
    save_report,
)
from agent.interview_multi_agent import MultiAgentInterviewCoordinator
from agent.interview_langgraph import LangGraphInterviewCoordinator
from agent.interview_policy import InterviewPolicy
from agent.interview_role_manager import InterviewRoleManager
from agent.interview_state_machine import InterviewStateMachine
from model.factory import chat_model
from utils.prompt_loader import load_system_prompts2
from infrastructure.settings import platform_settings


class ToolCallingQAAgent:
    """问答模式下的工具调用 Agent。"""

    def __init__(self, system_prompt: str, tools: Sequence[Any]):
        # 问答模式下，这个 Agent 负责：
        # 1. 读取系统提示词
        # 2. 把可用工具绑定给模型
        # 3. 在“模型决定调工具 -> 执行工具 -> 再把结果喂回模型”之间循环
        self.system_prompt = system_prompt.strip()
        self.tools = list(tools)
        self.tools_by_name = {tool.name: tool for tool in self.tools}
        self.max_tool_rounds = 6
        self.model_with_tools = self._bind_tools()

    def _bind_tools(self):
        if not hasattr(chat_model, "bind_tools"):
            return None
        try:
            return chat_model.bind_tools(self.tools)
        except Exception:
            return None

    def invoke(self, payload: dict) -> dict:
        # 一次 invoke() 就是一轮完整的 Tool Calling 流程。
        #
        # Tool Calling 核心思想：
        # 模型不是只能输出文字，它还可以“决定调用哪个工具”。
        # 当前代码循环做的是：
        # 1. 把历史消息交给绑定工具后的模型。
        # 2. 如果模型返回 tool_calls，就执行对应 Python 工具。
        # 3. 把工具结果作为 ToolMessage 放回消息列表。
        # 4. 再让模型基于工具结果生成最终回答。
        messages = payload.get("messages", []) or []
        if self.model_with_tools is None:
            return {"output": "当前模型未启用工具绑定能力，请稍后重试。"}

        lc_messages = [SystemMessage(content=self._build_system_prompt())]
        lc_messages.extend(self._to_lc_messages(messages))

        final_text = ""
        for _ in range(self.max_tool_rounds):
            # 先让模型判断：这一步是直接回答，还是先调用工具。
            ai_message = self.model_with_tools.invoke(lc_messages)
            lc_messages.append(ai_message)

            tool_calls = getattr(ai_message, "tool_calls", None) or []
            if not tool_calls:
                final_text = self._extract_message_content(ai_message)
                break

            for tool_call in tool_calls:
                # 如果模型发起了 tool call，这里就会真正执行对应的 Python 工具函数。
                # 例如：
                # - knowledge_search：查知识库。
                # - weather_search：查天气。
                # - resume_lookup：查当前简历信息。
                tool_name = str(tool_call.get("name", "")).strip()
                tool_args = tool_call.get("args", {})
                tool_id = tool_call.get("id")
                tool = self.tools_by_name.get(tool_name)

                if tool is None:
                    tool_output = f"工具 {tool_name} 不存在，无法执行。"
                else:
                    try:
                        invoke_payload = tool_args if isinstance(tool_args, dict) else tool_args
                        tool_output = tool.invoke(invoke_payload)
                    except Exception as exc:
                        tool_output = f"工具 {tool_name} 执行失败：{exc}"

                lc_messages.append(
                    ToolMessage(
                        content=str(tool_output),
                        tool_call_id=tool_id or tool_name or "tool_call",
                    )
                )

        if not final_text:
            last_message = lc_messages[-1] if lc_messages else None
            final_text = self._extract_message_content(last_message) if last_message else ""

        return {"output": final_text.strip()}

    def stream(self, payload: dict):
        """Run the tool loop and yield the model's real final-answer chunks."""
        # 流式 Tool Calling 比普通 invoke 多一步：
        # 模型最终回答阶段会逐段 yield 文本，前端才能看到“边生成边显示”。
        messages = payload.get("messages", []) or []
        if self.model_with_tools is None:
            yield "当前模型未启用工具绑定能力，请稍后重试。"
            return

        lc_messages = [SystemMessage(content=self._build_system_prompt()), *self._to_lc_messages(messages)]
        for _ in range(self.max_tool_rounds):
            aggregate = None
            for chunk in self.model_with_tools.stream(lc_messages):
                aggregate = chunk if aggregate is None else aggregate + chunk
                text = self._extract_message_content(chunk)
                if text:
                    yield text
            if aggregate is None:
                return
            lc_messages.append(aggregate)
            tool_calls = getattr(aggregate, "tool_calls", None) or []
            if not tool_calls:
                return
            for tool_call in tool_calls:
                tool_name = str(tool_call.get("name", "")).strip()
                tool = self.tools_by_name.get(tool_name)
                try:
                    output = tool.invoke(tool_call.get("args", {})) if tool else f"工具 {tool_name} 不存在，无法执行。"
                except Exception as exc:
                    output = f"工具 {tool_name} 执行失败：{exc}"
                lc_messages.append(
                    ToolMessage(content=str(output), tool_call_id=tool_call.get("id") or tool_name or "tool_call")
                )

    def _build_system_prompt(self) -> str:
        # 系统提示词告诉模型：
        # - 它是什么角色。
        # - 什么时候应该调用工具。
        # - 工具返回后怎么组织最终答案。
        return (
            f"{self.system_prompt}\n\n"
            "你现在是一个具备工具调用能力的中文智能面试辅导助手。\n"
            "请根据用户问题，自主判断是否需要调用工具。\n"
            "工具使用规则：\n"
            "1. 遇到天气、城市、出行相关问题时，优先调用城市和天气工具。\n"
            "2. 遇到技术知识点、面试题、概念解释、资料问答时，优先调用知识库检索工具。\n"
            "3. 如果需要当前用户、月份或外部记录信息，可调用对应工具。\n"
            "4. 如果不需要工具，直接回答。\n"
            "5. 工具返回后，请基于工具结果用自然中文整理最终答案，不要只原样复述工具返回值。\n"
            "6. 不要虚构工具结果；需要信息时优先调用工具确认。"
        )

    @staticmethod
    def _to_lc_messages(messages: Sequence[dict]) -> list[Any]:
        lc_messages: list[Any] = []
        for message in messages:
            role = message.get("role", "")
            content = str(message.get("content", "")).strip()
            if not content:
                continue
            if role == "user":
                lc_messages.append(HumanMessage(content=content))
            elif role == "assistant":
                lc_messages.append(AIMessage(content=content))
        return lc_messages

    @staticmethod
    def _extract_message_content(message: Any) -> str:
        if message is None:
            return ""
        content = getattr(message, "content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict):
                    text = item.get("text")
                    if text:
                        parts.append(str(text))
                elif isinstance(item, str):
                    parts.append(item)
            return "\n".join(parts).strip()
        return str(content).strip()


class InterviewAssistantService:
    """
    对外保持一个统一服务入口：
    - 问答模式仍然走 Tool Calling Agent
    - 模拟面试模式内部升级为多 Agent 协作
    """

    def __init__(self):
        # 这是后端“面向前端”的统一服务入口。
        # main.py 不直接写模型细节，而是把问答/面试都交给这一层。
        self._rag_service = None
        self.policy = InterviewPolicy()
        self.state_machine = InterviewStateMachine()
        self.role_manager = InterviewRoleManager()

        self.qa_tools = [
            knowledge_search,
            weather_search,
            resume_lookup,
            question_search,
            save_report,
        ]
        self.qa_executor = ToolCallingQAAgent(load_system_prompts2(), self.qa_tools)
        coordinator_class = LangGraphInterviewCoordinator if platform_settings.enable_langgraph else MultiAgentInterviewCoordinator
        self.interview_coordinator = coordinator_class(
            policy=self.policy,
            state_machine=self.state_machine,
            role_manager=self.role_manager,
            rag_service_getter=lambda: self.rag_service,
        )

    @property
    def rag_service(self):
        # RAG 服务采用懒加载：只有真正需要知识库检索时才初始化。
        if self._rag_service is None:
            from rag.rag_service import RagSummarizeService

            self._rag_service = RagSummarizeService()
        return self._rag_service

    @staticmethod
    def _to_agent_messages(history: Sequence[dict]) -> list[dict]:
        messages: list[dict] = []
        for message in history:
            role = message.get("role", "")
            content = message.get("content", "")
            if role == "user":
                messages.append({"role": "user", "content": content})
            elif role == "assistant":
                messages.append({"role": "assistant", "content": content})
        return messages

    @staticmethod
    def _yield_text_stream(text: str, chunk_size: int = 8):
        content = str(text or "")
        if not content:
            return
        for idx in range(0, len(content), chunk_size):
            yield content[idx : idx + chunk_size]

    @staticmethod
    def _extract_ai_output(response: dict) -> str:
        direct_output = response.get("output")
        if isinstance(direct_output, str) and direct_output.strip():
            return direct_output.strip()
        return ""

    def qa_chat(self, user_input: str, history: list[dict], tenant_context: dict | None = None) -> str:
        # 普通问答模式入口：输入“用户问题 + 历史”，输出最终答案文本。
        messages = self._to_agent_messages(history)
        if not messages or messages[-1].get("role") != "user" or messages[-1].get("content") != user_input:
            messages.append({"role": "user", "content": user_input})

        with tool_tenant_context(tenant_context):
            response = self.qa_executor.invoke({"messages": messages})
        output = self._extract_ai_output(response)
        if output:
            return output
        return "这次没有生成有效回答，请换一种问法再试一次。"

    def qa_chat_stream(self, user_input: str, history: list[dict], tenant_context: dict | None = None):
        messages = self._to_agent_messages(history)
        if not messages or messages[-1].get("role") != "user" or messages[-1].get("content") != user_input:
            messages.append({"role": "user", "content": user_input})

        emitted = False
        with tool_tenant_context(tenant_context):
            for chunk in self.qa_executor.stream({"messages": messages}):
                if chunk:
                    emitted = True
                    yield str(chunk)
        if not emitted:
            yield "这次没有生成有效回答，请换一种问法再试一次。"

    def start_role_interview(
        self,
        role: str,
        history: list[dict] | None = None,
        resume_text: str = "",
        resume_filename: str = "",
        tenant_context: dict | None = None,
    ) -> dict:
        _ = history  # 历史参数保留是为了兼容旧接口签名
        arguments = {"role": role, "resume_text": resume_text, "resume_filename": resume_filename, "interview_state": None}
        if isinstance(self.interview_coordinator, LangGraphInterviewCoordinator):
            arguments["tenant_context"] = tenant_context or {}
        return self.interview_coordinator.start_interview(**arguments)

    def interview_chat(
        self,
        user_input: str,
        history: list[dict],
        interview_state: dict | None = None,
        interview_questions: Sequence[str] | None = None,
        run_id: str | None = None,
    ) -> dict:
        arguments = {
            "user_input": user_input,
            "history": history,
            "interview_state": interview_state,
            "interview_questions": interview_questions or [],
        }
        if isinstance(self.interview_coordinator, LangGraphInterviewCoordinator):
            arguments["run_id"] = run_id
        return self.interview_coordinator.process_turn(**arguments)

    def interview_chat_stream(
        self,
        user_input: str,
        history: list[dict],
        interview_state: dict | None = None,
        interview_questions: Sequence[str] | None = None,
    ):
        result = self.interview_chat(user_input, history, interview_state, interview_questions)
        reply = result.get("reply", "")
        if reply:
            yield from self._yield_text_stream(reply)

    def calculate_interview_score(
        self,
        interview_state: dict | None = None,
        interview_history: Sequence[dict] | None = None,
    ) -> int:
        return self.interview_coordinator.calculate_interview_score(interview_state, interview_history)

    def generate_report(
        self,
        interview_history: list[dict],
        interview_questions: list[str],
        interview_state: dict | None = None,
    ) -> str:
        return self.interview_coordinator.generate_report(
            interview_history=interview_history,
            interview_questions=interview_questions,
            interview_state=interview_state,
        )
