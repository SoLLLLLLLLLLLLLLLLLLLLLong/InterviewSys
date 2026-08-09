from agent.interview_graph_components import EvidenceJudge, InterviewPlanner
from agent.interview_role_manager import InterviewRoleManager


def test_evidence_judge_requires_multiple_relevant_documents():
    result = EvidenceJudge.judge("Redis 持久化", [{"source": "a", "content": "Redis 持久化包含 RDB"}, {"source": "b", "content": "AOF 记录写命令"}])
    assert result["sufficient"] is True


def test_planner_covers_multiple_dimensions():
    plan = InterviewPlanner(InterviewRoleManager()).build("前端开发", question_count=8)
    assert len(plan) == 8
    assert len({item["dimension"] for item in plan}) >= 3
