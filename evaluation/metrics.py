from __future__ import annotations

from collections import Counter
from typing import Iterable, Sequence


def accuracy(expected: Sequence[str], predicted: Sequence[str]) -> float:
    if not expected:
        return 0.0
    return sum(left == right for left, right in zip(expected, predicted)) / len(expected)


def recall_at_k(relevant_ids: set[str], retrieved_ids: Sequence[str], k: int) -> float:
    if not relevant_ids:
        return 0.0
    return len(relevant_ids.intersection(retrieved_ids[:k])) / len(relevant_ids)


def reciprocal_rank(relevant_ids: set[str], retrieved_ids: Sequence[str]) -> float:
    for rank, item_id in enumerate(retrieved_ids, start=1):
        if item_id in relevant_ids:
            return 1.0 / rank
    return 0.0


def citation_precision(cited_ids: Sequence[str], supporting_ids: set[str]) -> float:
    if not cited_ids:
        return 0.0
    return sum(item in supporting_ids for item in cited_ids) / len(cited_ids)


def question_diversity(dimensions: Sequence[str]) -> float:
    if not dimensions:
        return 0.0
    return len(set(item for item in dimensions if item)) / len(dimensions)


def repetition_rate(questions: Sequence[str]) -> float:
    normalized = [" ".join(str(item).lower().split()) for item in questions if str(item).strip()]
    if len(normalized) < 2:
        return 0.0
    repeated = sum(count - 1 for count in Counter(normalized).values() if count > 1)
    return repeated / len(normalized)


def average(values: Iterable[float]) -> float:
    items = list(values)
    return sum(items) / len(items) if items else 0.0
