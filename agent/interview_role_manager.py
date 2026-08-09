from __future__ import annotations

from typing import Dict, List

from utils.logger_handler import logger


class InterviewRoleManager:
    DEFAULT_ROLE = "通用技术岗位"

    ROLE_PROFILES: Dict[str, Dict[str, List[dict] | List[str]]] = {
        "后端开发": {
            "keywords": ["Java", "接口设计", "数据库", "缓存", "并发", "系统设计", "排障"],
            "dimensions": [
                {"name": "项目经历", "focus": "候选人的代表项目、职责边界、技术选型和业务结果"},
                {"name": "服务设计", "focus": "接口设计、分层架构、模块划分和可维护性"},
                {"name": "数据库", "focus": "SQL 优化、索引设计、事务和一致性"},
                {"name": "缓存与并发", "focus": "Redis、缓存一致性、并发控制和热点问题"},
                {"name": "系统设计", "focus": "高并发、扩展性、容灾和监控"},
            ],
        },
        "前端开发": {
            "keywords": ["React", "组件设计", "工程化", "性能优化", "状态管理", "浏览器原理"],
            "dimensions": [
                {"name": "项目经历", "focus": "候选人的代表项目、页面职责、关键交互和业务价值"},
                {"name": "组件与状态", "focus": "组件抽象、状态管理、复用和边界设计"},
                {"name": "性能优化", "focus": "首屏加载、渲染性能、资源优化和定位手段"},
                {"name": "工程化", "focus": "构建流程、发布质量、规范治理和团队协作"},
                {"name": "浏览器与场景", "focus": "浏览器机制、事件循环、跨端兼容和复杂交互"},
            ],
        },
        "数据分析": {
            "keywords": ["SQL", "指标体系", "实验分析", "数据清洗", "业务理解", "可视化"],
            "dimensions": [
                {"name": "项目经历", "focus": "做过的分析项目、业务背景、目标和产出"},
                {"name": "指标设计", "focus": "指标拆解、口径统一和业务解释能力"},
                {"name": "数据处理", "focus": "清洗、缺失值、异常值和样本质量"},
                {"name": "分析方法", "focus": "归因分析、实验分析、漏斗分析和建模思路"},
                {"name": "业务表达", "focus": "如何把分析结果讲给业务方并推动落地"},
            ],
        },
        "算法工程": {
            "keywords": ["模型训练", "特征工程", "评估指标", "推理服务", "召回", "精排"],
            "dimensions": [
                {"name": "项目经历", "focus": "最有代表性的算法项目、职责和效果提升"},
                {"name": "模型方法", "focus": "模型选型、训练流程、特征和调参思路"},
                {"name": "评估与分析", "focus": "指标设计、误差分析和实验对比"},
                {"name": "工程落地", "focus": "推理服务、稳定性、资源成本和迭代机制"},
                {"name": "场景优化", "focus": "线上效果波动、召回精排协同和问题排查"},
            ],
        },
        "Agent开发": {
            "keywords": ["LLM", "Prompt", "Tool Calling", "RAG", "Memory", "Workflow", "Evaluation", "Observability"],
            "dimensions": [
                {"name": "项目经历", "focus": "最有代表性的 Agent 或 LLM 应用项目、职责和业务结果"},
                {"name": "Agent 架构", "focus": "单智能体、多智能体、工作流编排、状态管理和任务拆分"},
                {"name": "工具调用与 RAG", "focus": "Tool Calling、函数调用、知识库检索、召回和重排"},
                {"name": "记忆与稳定性", "focus": "短期记忆、长期记忆、消息持久化、中断恢复和超时兜底"},
                {"name": "评测与优化", "focus": "Prompt 优化、效果评估、失败案例分析、成本和延迟优化"},
            ],
        },
        "产品经理": {
            "keywords": ["需求分析", "用户研究", "指标", "协作推进", "优先级", "增长"],
            "dimensions": [
                {"name": "项目经历", "focus": "最有代表性的产品项目、角色分工和结果"},
                {"name": "需求分析", "focus": "需求来源、用户问题、价值判断和优先级"},
                {"name": "方案设计", "focus": "功能设计、交互思路、边界和取舍"},
                {"name": "数据与复盘", "focus": "指标跟踪、效果评估和迭代策略"},
                {"name": "协作推进", "focus": "跨团队沟通、风险处理和推动落地"},
            ],
        },
        "通用技术岗位": {
            "keywords": ["项目经历", "基础能力", "问题分析", "优化思路", "落地经验"],
            "dimensions": [
                {"name": "项目经历", "focus": "候选人的代表项目、职责和关键成果"},
                {"name": "基础能力", "focus": "核心技术原理、常见问题和理解深度"},
                {"name": "问题解决", "focus": "遇到过的难点、排查思路和解决方案"},
                {"name": "优化思路", "focus": "性能、稳定性、可维护性的改进经验"},
                {"name": "综合表达", "focus": "复盘能力、总结能力和成长反思"},
            ],
        },
    }

    def normalize_role(self, role: str) -> str:
        text = (role or "").strip()
        if not text:
            return self.DEFAULT_ROLE
        return text

    def set_runtime_profile(
        self,
        role: str,
        dimensions: List[dict] | None = None,
        keywords: List[str] | None = None,
        question_bank: List[dict] | None = None,
    ) -> None:
        """Register a role profile loaded from the platform admin/interviewer console."""
        normalized = self.normalize_role(role)
        clean_dimensions = []
        for item in dimensions or []:
            name = str(item.get("name", "")).strip()
            focus = str(item.get("focus", "")).strip()
            if name:
                clean_dimensions.append({"name": name, "focus": focus or f"{name} 相关能力与项目经验"})
        if not clean_dimensions:
            seen_dimensions = set()
            for item in question_bank or []:
                name = str(item.get("dimension", "")).strip()
                if name and name not in seen_dimensions:
                    seen_dimensions.add(name)
                    clean_dimensions.append({"name": name, "focus": f"{name} 相关能力、项目经验与问题解决思路"})
        if not clean_dimensions:
            clean_dimensions = [{"name": normalized, "focus": f"{normalized} 岗位核心能力与项目落地经验"}]
        self.ROLE_PROFILES[normalized] = {
            "keywords": [str(item).strip() for item in keywords or [] if str(item).strip()] or [normalized],
            "dimensions": clean_dimensions,
            "question_bank": [
                {
                    "dimension": str(item.get("dimension", "")).strip(),
                    "difficulty": str(item.get("difficulty", "")).strip(),
                    "question_text": str(item.get("question_text", "")).strip(),
                }
                for item in question_bank or []
                if str(item.get("question_text", "")).strip()
            ],
        }

    def get_role_profile(self, role: str) -> Dict:
        normalized = self.normalize_role(role)
        for key, profile in self.ROLE_PROFILES.items():
            if key in normalized:
                return profile
        logger.info(f"[InterviewRoleManager] 未命中预设岗位，使用通用岗位：{normalized}")
        return self.ROLE_PROFILES[self.DEFAULT_ROLE]

    def get_role_keywords(self, role: str) -> List[str]:
        return list(self.get_role_profile(role).get("keywords", []))

    def get_dimensions(self, role: str) -> List[dict]:
        return list(self.get_role_profile(role).get("dimensions", []))

    def get_dimension(self, role: str, index: int) -> dict:
        dimensions = self.get_dimensions(role)
        if not dimensions:
            return {"name": "综合能力", "focus": "项目经验、技术理解和落地能力"}
        return dimensions[index % len(dimensions)]

    def get_dimension_name(self, role: str, index: int) -> str:
        return str(self.get_dimension(role, index).get("name", "综合能力"))

    def get_dimension_focus(self, role: str, index: int) -> str:
        return str(self.get_dimension(role, index).get("focus", "项目经验、技术理解和落地能力"))

    def get_reference_questions(self, role: str, index: int, limit: int = 3) -> List[str]:
        """Return interviewer-configured question-bank references for the current turn."""
        questions = list(self.get_role_profile(role).get("question_bank", []))
        if not questions:
            return []
        start = max(0, index) % len(questions)
        ordered = questions[start:] + questions[:start]
        return [
            f"{item.get('dimension') or '综合'}：{item.get('question_text')}"
            for item in ordered[: max(1, limit)]
            if str(item.get("question_text", "")).strip()
        ]

    def get_first_question(self, role: str) -> str:
        return "先从你最有代表性的项目开始吧。你在这个项目里负责的核心工作和最终结果分别是什么？"

    def get_next_question(self, role: str, index: int) -> str:
        dimension = self.get_dimension(role, index)
        name = dimension.get("name", "综合能力")
        focus = dimension.get("focus", "项目经验、技术理解和落地能力")
        return f"我们切换一个方向，聊聊{name}。你可以结合{focus}，展开说说你的理解和实际经验。"
