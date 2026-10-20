from app.evaluators.retrieval_metrics import (
    mean_reciprocal_rank,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
)


def test_recall_at_k_hand_computed():
    retrieved = ["a", "b", "c", "d", "e"]
    relevant = {"b", "e", "z"}  # z is relevant but never retrieved
    # top-5 hits: b, e -> 2 of 3 relevant found
    assert recall_at_k(retrieved, relevant, k=5) == 2 / 3
    # top-2 hits: only b -> 1 of 3
    assert recall_at_k(retrieved, relevant, k=2) == 1 / 3


def test_recall_at_k_no_relevant_is_undefined():
    assert recall_at_k(["a", "b"], set(), k=5) is None


def test_precision_at_k_hand_computed():
    retrieved = ["a", "b", "c", "d", "e"]
    relevant = {"a", "c"}
    # top-3: a, b, c -> 2 hits / 3
    assert precision_at_k(retrieved, relevant, k=3) == 2 / 3
    # top-1: a -> 1 hit / 1
    assert precision_at_k(retrieved, relevant, k=1) == 1.0


def test_mrr_hand_computed():
    relevant = {"c"}
    # c is at rank 3 -> MRR = 1/3
    assert mean_reciprocal_rank(["a", "b", "c", "d"], relevant) == 1 / 3
    # no relevant item retrieved -> 0.0
    assert mean_reciprocal_rank(["a", "b"], relevant) == 0.0
    # relevant item at rank 1 -> 1.0
    assert mean_reciprocal_rank(["c", "a"], relevant) == 1.0


def test_ndcg_at_k_perfect_ranking_is_one():
    retrieved = ["a", "b", "c"]
    relevant = {"a", "b"}
    # ideal ranking (a, b first) achieved -> nDCG == 1.0
    assert ndcg_at_k(retrieved, relevant, k=3) == 1.0


def test_ndcg_at_k_hand_computed_imperfect_ranking():
    import math

    retrieved = ["x", "a", "b"]  # relevant item 'a' pushed to rank 2
    relevant = {"a"}
    # DCG = 1/log2(3) (a at rank 2); IDCG = 1/log2(2) (a at rank 1)
    expected = (1 / math.log2(3)) / (1 / math.log2(2))
    assert math.isclose(ndcg_at_k(retrieved, relevant, k=3), expected)


def test_ndcg_at_k_no_relevant_is_undefined():
    assert ndcg_at_k(["a", "b"], set(), k=3) is None


def test_ndcg_at_k_no_hits_is_zero():
    assert ndcg_at_k(["x", "y"], {"a"}, k=2) == 0.0
