from evaluation.metrics import accuracy, citation_precision, question_diversity, recall_at_k, reciprocal_rank, repetition_rate


def test_routing_accuracy():
    assert accuracy(["a", "b", "c"], ["a", "x", "c"]) == 2 / 3


def test_retrieval_metrics():
    assert recall_at_k({"a", "c"}, ["a", "b", "c"], 2) == 0.5
    assert reciprocal_rank({"c"}, ["a", "b", "c"]) == 1 / 3
    assert citation_precision(["a", "x"], {"a", "b"}) == 0.5


def test_interview_question_metrics():
    assert question_diversity(["基础", "项目", "设计", "项目"]) == 0.75
    assert repetition_rate(["什么是 Redis", "什么是 Redis", "如何做缓存"]) == 1 / 3
