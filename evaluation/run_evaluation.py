from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from evaluation.metrics import accuracy, question_diversity, repetition_rate


DATASET_PATH = Path(__file__).parent / "datasets" / "interview_eval.json"


def heuristic_route(text: str) -> str:
    value = text.strip().lower()
    if any(word in value for word in ["结束", "到这里", "不面了"]):
        return "finish_interview"
    if any(word in value for word in ["提示", "不会", "不知道"]):
        return "give_hint"
    return "evaluate_answer"


def heuristic_tool(text: str) -> str:
    value = text.strip().lower()
    if "天气" in value:
        return "weather_search"
    return "knowledge_search"


def evaluate() -> dict:
    samples = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    route_samples = [item for item in samples if item["category"] == "router"]
    tool_samples = [item for item in samples if item["category"] == "tool"]
    interview_samples = [item for item in samples if item["category"] == "interview"]
    return {
        "router_accuracy": accuracy([item["expected"] for item in route_samples], [heuristic_route(item["input"]) for item in route_samples]),
        "tool_accuracy": accuracy([item["expected"] for item in tool_samples], [heuristic_tool(item["input"]) for item in tool_samples]),
        "question_diversity": sum(question_diversity(item["dimensions"]) for item in interview_samples) / max(1, len(interview_samples)),
        "question_repetition_rate": sum(repetition_rate(item["questions"]) for item in interview_samples) / max(1, len(interview_samples)),
        "sample_count": len(samples),
    }


def persist_results(metrics: dict) -> None:
    """Persist numeric metrics for the administrator dashboard when enabled."""
    from infrastructure.database import EvaluationResult, platform_database_enabled, platform_session

    if not platform_database_enabled():
        return
    with platform_session() as session:
        for metric_name, score in metrics.items():
            if metric_name == "sample_count":
                continue
            session.add(
                EvaluationResult(
                    dataset_name="interview-coach-evaluation",
                    metric_name=metric_name,
                    score=float(score),
                    details={"sample_count": metrics.get("sample_count", 0)},
                )
            )


def sync_langsmith_dataset() -> None:
    api_key = (os.getenv("LANGSMITH_API_KEY") or os.getenv("LANGCHAIN_API_KEY", "")).strip()
    if not api_key:
        print("未配置 LANGCHAIN_API_KEY，跳过 LangSmith Dataset 同步。")
        return
    from langsmith import Client

    client = Client(api_key=api_key)
    dataset_name = "interview-coach-evaluation"
    datasets = list(client.list_datasets(dataset_name=dataset_name))
    dataset = datasets[0] if datasets else client.create_dataset(dataset_name=dataset_name, description="智能面试 Agent 路由、工具与流程评测集")
    samples = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    for sample in samples:
        client.create_example(inputs={"input": sample.get("input", ""), "category": sample["category"]}, outputs={"expected": sample.get("expected", "")}, dataset_id=dataset.id)
    print(f"已同步 {len(samples)} 条样本到 LangSmith Dataset：{dataset_name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--sync-langsmith", action="store_true")
    arguments = parser.parse_args()
    results = evaluate()
    print(json.dumps(results, ensure_ascii=False, indent=2))
    persist_results(results)
    if arguments.sync_langsmith:
        sync_langsmith_dataset()
