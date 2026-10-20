"""
Pure retrieval-metric functions, independently unit tested against
hand-computed expected values (see tests/test_retrieval_metrics.py).
Binary relevance is assumed throughout: a passage is either in the test
case's labeled relevant set or it isn't.
"""
from __future__ import annotations
import math

from app.enums import EvaluatorStatus
from app.evaluators.base import BaseEvaluator, EvaluationContext, EvaluationOutcome


def recall_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int) -> float | None:
    if not relevant_ids:
        return None
    top_k = retrieved_ids[:k]
    hits = len(set(top_k) & relevant_ids)
    return hits / len(relevant_ids)


def precision_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int) -> float | None:
    if k <= 0:
        return None
    top_k = retrieved_ids[:k]
    hits = len(set(top_k) & relevant_ids)
    return hits / k


def mean_reciprocal_rank(retrieved_ids: list[str], relevant_ids: set[str]) -> float:
    for rank, doc_id in enumerate(retrieved_ids, start=1):
        if doc_id in relevant_ids:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int) -> float | None:
    if not relevant_ids:
        return None

    top_k = retrieved_ids[:k]
    dcg = sum(
        (1.0 / math.log2(position + 1))
        for position, doc_id in enumerate(top_k, start=1)
        if doc_id in relevant_ids
    )

    ideal_hits = min(len(relevant_ids), k)
    idcg = sum(1.0 / math.log2(position + 1) for position in range(1, ideal_hits + 1))

    if idcg == 0:
        return 0.0
    return dcg / idcg


class RetrievalMetricsEvaluator(BaseEvaluator):
    """
    Computes Recall@K, Precision@K, MRR, and nDCG@K from the test case's
    labeled `relevant_passage_ids` and the adapter's actually-returned
    `retrieved_passages`. Reported unavailable (never scored as 0 or
    skipped as a silent pass) when either side provides nothing to
    compare -- a missing retrieval capability is not evidence of poor
    retrieval.
    """

    name = "retrieval_metrics"
    version = "1.0.0"

    def evaluate(self, ctx: EvaluationContext) -> EvaluationOutcome:
        relevant_ids = set(ctx.test_case.get("relevant_passage_ids", []))
        if not relevant_ids:
            return self.unavailable("test case declares no labeled relevant_passage_ids")

        if not ctx.retrieved_passages:
            return self.unavailable("adapter returned no retrieved passages for this execution")

        k = ctx.evaluator_config(self.name).get("k", 5)
        retrieved_ids = [p.get("passage_id") or f"{p.get('document_id')}:p{p.get('page')}" for p in ctx.retrieved_passages]

        recall = recall_at_k(retrieved_ids, relevant_ids, k)
        precision = precision_at_k(retrieved_ids, relevant_ids, k)
        mrr = mean_reciprocal_rank(retrieved_ids, relevant_ids)
        ndcg = ndcg_at_k(retrieved_ids, relevant_ids, k)

        metrics = {"recall_at_k": recall, "precision_at_k": precision, "mrr": mrr, "ndcg_at_k": ndcg, "k": k}
        threshold = ctx.evaluator_config(self.name).get("pass_threshold")

        status = EvaluatorStatus.PASS
        reason = f"recall@{k}={recall:.2f} precision@{k}={precision:.2f} mrr={mrr:.2f} ndcg@{k}={ndcg:.2f}"
        if threshold is not None and recall is not None and recall < threshold:
            status = EvaluatorStatus.FAIL
            reason += f" (below configured recall threshold {threshold})"

        return EvaluationOutcome(
            status=status,
            score=recall,
            expected_value={"relevant_passage_ids": sorted(relevant_ids)},
            actual_value={"retrieved_ids": retrieved_ids, "metrics": metrics},
            reason=reason,
            severity=ctx.test_case.get("severity") if status == EvaluatorStatus.FAIL else None,
        )
