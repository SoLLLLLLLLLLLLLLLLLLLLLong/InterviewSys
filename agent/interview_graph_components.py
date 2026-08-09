from __future__ import annotations

from typing import Any, Sequence

from agent.interview_role_manager import InterviewRoleManager
from rag.hybrid_retriever import tokenize


class InterviewPlanner:
    """Pure planning component, kept independent from the LangGraph runtime."""

    def __init__(self, role_manager: InterviewRoleManager) -> None:
        self.role_manager = role_manager

    def build(self, role: str, resume_analysis: dict[str, Any] | None = None, question_count: int = 8) -> list[dict[str, str]]:
        resume_focuses = list((resume_analysis or {}).get("recommended_focuses", []) or [])
        plan = []
        for index in range(question_count):
            dimension = self.role_manager.get_dimension_name(role, index)
            focus = self.role_manager.get_dimension_focus(role, index)
            if index < len(resume_focuses):
                focus = f"{focus}；结合简历重点：{resume_focuses[index]}"
            plan.append({"index": str(index + 1), "dimension": dimension, "focus": focus})
        return plan


class EvidenceJudge:
    """Pure evidence sufficiency check used by the graph and unit tests."""

    @staticmethod
    def judge(query: str, evidence: Sequence[dict[str, Any]]) -> dict[str, Any]:
        query_terms = set(tokenize(query))
        if not evidence:
            return {"sufficient": False, "reason": "没有召回知识库证据", "conflicts": [], "relevance": 0.0}
        hit_count = 0
        matched_evidence: list[tuple[str, str, bool]] = []
        for item in evidence:
            content = str(item.get("content", "")).lower()
            content_terms = set(tokenize(content))
            if not query_terms or query_terms.intersection(content_terms):
                hit_count += 1
                matched_evidence.append(
                    (
                        str(item.get("id", "unknown")),
                        str(item.get("source", "未知来源")),
                        any(marker in content for marker in ("不是", "不能", "不会", "没有", "未", "无")),
                    )
                )
        relevance = hit_count / max(1, len(evidence))
        positive = [item for item in matched_evidence if not item[2]]
        negative = [item for item in matched_evidence if item[2]]
        conflicts = []
        if positive and negative:
            conflicts.append(
                {
                    "positive_source": positive[0][1],
                    "negative_source": negative[0][1],
                    "reason": "相关证据中同时出现肯定与否定表述，需要人工或模型进一步核验。",
                }
            )
        sufficient = len(evidence) >= 2 and relevance >= 0.25 and not conflicts
        return {
            "sufficient": sufficient,
            "reason": "证据数量和相关性满足要求" if sufficient else ("证据存在潜在冲突" if conflicts else "证据数量或关键词相关性不足"),
            "conflicts": conflicts,
            "relevance": round(relevance, 4),
        }
