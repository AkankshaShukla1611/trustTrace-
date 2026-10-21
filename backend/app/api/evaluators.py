from __future__ import annotations

from fastapi import APIRouter

from app.evaluators import ALL_EVALUATORS

router = APIRouter(tags=["evaluators"])


@router.get("/evaluators")
def list_evaluators():
    """
    Describes every evaluator the runner actually applies (deterministic
    and optional), pulled straight from each evaluator class's own
    docstring -- so this endpoint can't drift out of sync with what the
    engine really does. `deterministic: false` marks a judgment-based
    evaluator (e.g. the optional LLM judge) so callers never confuse its
    output with a deterministic fact.
    """
    return [
        {
            "name": evaluator.name,
            "version": evaluator.version,
            "description": (type(evaluator).__doc__ or "").strip(),
            "deterministic": evaluator.deterministic,
        }
        for evaluator in ALL_EVALUATORS
    ]
